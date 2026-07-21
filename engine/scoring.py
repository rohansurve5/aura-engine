"""content_v3 scoring + copy composition: (natal nakshatra × today's sky) → daily guidance.

This module is the deterministic *engine* that applies a rules dict. It holds no
magic numbers and no copy of its own — every tunable value and every line of
user-visible text lives in the `score_rules` table (seeded from
db/seed/score_rules_content_v3.json). Load the rules with `load_rules_from_db`
(job) or `load_rules_from_json` (tests), then call `all_guidance(sky, rules)`.

Vedic basis (unchanged from v1): **Tarabala** — the 9-fold auspiciousness cycle
counted from the natal (janma) nakshatra to the day's Moon nakshatra — sets the
base energy. The weekday (hora) lord and paksha modulate it per life-area; lucky
colour/number/direction come from the day lord (dik + Vedic numerology).

content_v2 (carried over): user-facing six areas — Love, Money, Career, Mind,
Health, Mood; `area_lines` (54-cell area × tara library, date-rotated);
`narrative`; rewritten `opportunity`/`warning`; the jargon-carrying `why`.

content_v3 additions (see docs/CONTENT_KEYS.md for the key scheme):
  • `band_labels` — per-area score-band label from a 6 × 5 vocabulary in which
    no label is shared between two areas.
  • `score_why` — the score-detail "why today", composed per area as
    RECOGNITION (area × band × moon_group) + CAUSE. CAUSE lines are
    band-neutral so every pairing reads coherently. Two areas can never render
    the same copy: the corpora are disjoint per area and CI
    (tests/test_content_diversity.py) fails on any shared label, line or
    sentence skeleton.

content_v3_1 (the multi-source CAUSE fix): v3 drew every area's CAUSE from one
source — (day lord × paksha) — so on any single date all six cards explained
themselves through the weekday's planet in near-identical framings. The
corpus-wide diversity gate could not see this: the unit that matters is what
one person reads in one day. v3_1 keeps that corpus as one source among six
(`daylord`, `nakshatra`, `paksha`, `tara`, `phase`, `none`) and `cause_rotation`
hands the six areas six DIFFERENT sources on every date. Enforced by
tests/test_per_day_distinctness.py.

Determinism: pure integer arithmetic with fixed rounding, stable tie-breaks and
date-ordinal variant rotation — no `now()` / randomness. Same `sky` + same
`rules` → byte-identical output.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .content import ACTIVE_SCORE_RULES_VERSION, SEED_PATH
from .vimshottari import NAKSHATRAS, TOTAL_NAKSHATRAS

# Both derived from engine/content.py — the single place the active version is
# set. Never hand-type a version here: a constant that can drift from SEED_PATH
# is exactly how content_v3_2 was seeded but never served.
SCORE_RULES_VERSION = ACTIVE_SCORE_RULES_VERSION

# The nine taras (1-indexed), in cycle order from the natal nakshatra.
TARA_NAMES = (
    "Janma", "Sampat", "Vipat", "Kshema", "Pratyak",
    "Sadhaka", "Vadha", "Mitra", "Parama Mitra",
)

# Energy → narrative band (thresholds mirror the app's energy labels).
_BANDS = ((85, "radiant"), (70, "bright"), (55, "steady"), (40, "quiet"))


def tara_of(natal_index: int, day_moon_index: int) -> int:
    """Tarabala 1–9: count natal→day-Moon nakshatra, folded into the 9-cycle."""
    count = ((day_moon_index - natal_index) % TOTAL_NAKSHATRAS) + 1  # 1..27
    return ((count - 1) % 9) + 1                                     # 1..9


def _clamp(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _band(energy: int) -> str:
    for threshold, name in _BANDS:
        if energy >= threshold:
            return name
    return "tender"


def _score_band(score: int, bands: dict) -> str:
    """An area score → its content_v3 band id (peak/high/mid/low/deep)."""
    thresholds = bands["thresholds"]
    for name in bands["order"]:
        if name in thresholds and score >= thresholds[name]:
            return name
    return bands["order"][-1]


def _pick(variants: list, day_ordinal: int, natal_index: int, salt: int):
    """Deterministic variant rotation: consecutive dates always advance the
    index (7 is coprime with 2 and 3, the variant-list lengths), the natal index
    de-syncs users, and `salt` de-syncs fields from each other."""
    return variants[(day_ordinal * 7 + natal_index * 3 + salt) % len(variants)]


def cause_sources_for(day_ordinal: int, rules: dict) -> dict[str, str]:
    """area → cause source id for one date (docs/CONTENT_KEYS.md § rotation).

    One row of `cause_rotation` per date. Every row is a permutation of the six
    sources over the six areas, so no two areas can explain themselves the same
    way on the same date; the row advances daily, so no area is permanently
    wedded to one kind of explanation.
    """
    rotation = rules["cause_rotation"]
    row = rotation[day_ordinal % len(rotation)]
    return dict(zip(rules["areas"]["order"], row, strict=True))


def _cause(source: str, area: str, sky: dict, rules: dict, tara: int, pick) -> str:
    """The CAUSE half for one area under one source id ("" for `none`)."""
    if source == "none":
        return ""
    if source == "daylord":
        paksha_key = "waxing" if sky["waxing"] else "waning"
        return rules["why_cause"][area][str(sky["weekday_index"])][paksha_key]
    if source == "nakshatra":
        moon_index = sky["day_nakshatra_index"]
        trait = rules["nakshatra_traits"][str(moon_index)]
        return rules["why_cause_nakshatra"][area][trait].format(
            nakshatra=NAKSHATRAS[moon_index]
        )
    if source == "paksha":
        paksha_key = "waxing" if sky["waxing"] else "waning"
        return pick(rules["why_cause_paksha"][area][paksha_key])
    if source == "tara":
        return rules["why_cause_tara"][area][str(tara)]
    if source == "phase":
        return rules["why_cause_phase"][area][sky["moon_phase"]["name"]]
    raise KeyError(f"unknown cause source {source!r}")


def guidance_for_nakshatra(natal_index: int, sky: dict, rules: dict) -> dict:
    """The daily_guidance payload for one natal nakshatra against `sky`."""
    tara = tara_of(natal_index, sky["day_nakshatra_index"])
    tconf = rules["tara"][str(tara)]
    wd = str(sky["weekday_index"])
    day_ordinal = date.fromisoformat(sky["date"]).toordinal()

    paksha_mod = rules["paksha"]["waxing" if sky["waxing"] else "waning"]
    base = tconf["energy"] + paksha_mod

    order = rules["areas"]["order"]
    labels = rules["areas"]["labels"]
    area_mod = rules["weekday_area_mod"][wd]
    scores = {area: _clamp(base + area_mod.get(area, 0)) for area in order}
    energy = _clamp(base + rules["weekday_energy_mod"][wd])

    # Stable tie-breaks: on a tie the earlier area in `order` wins either way.
    best = max(order, key=lambda a: (scores[a], -order.index(a)))
    worst = min(order, key=lambda a: (scores[a], order.index(a)))

    def pick(variants: list, salt: int):
        return _pick(variants, day_ordinal, natal_index, salt)

    # One human line per area from the 54-cell (area × tara) content library.
    area_lines = {
        labels[a]: pick(rules["area_lines"][a][str(tara)], salt=i)
        for i, a in enumerate(order)
    }

    # content_v3_1: per-area band labels + the score-detail "why".
    # Key scheme (docs/CONTENT_KEYS.md): band from the area's own score,
    # RECOGNITION from (area, band, day-Moon texture group), CAUSE from the
    # source this date's rotation row hands this area — fully determined by
    # date + natal. Under the `none` source the recognition stands alone.
    moon_group = rules["moon_groups"][str(sky["day_nakshatra_index"])]
    sources = cause_sources_for(day_ordinal, rules)
    band_labels = {}
    score_why = {}
    causes = {}
    for i, a in enumerate(order):
        band = _score_band(scores[a], rules["score_bands"])
        band_labels[labels[a]] = rules["band_labels"][a][band]
        recognition = rules["why_recognition"][a][band][moon_group]
        cause = _cause(
            sources[a], a, sky, rules, tara, lambda v, i=i: pick(v, salt=23 + i)
        )
        causes[labels[a]] = cause
        score_why[labels[a]] = f"{recognition} {cause}".strip()

    # Two-sentence "story of your day": energy-band opener + best/caution closer.
    narrative_conf = rules["narrative"]
    focus = narrative_conf["focus"]
    opener = pick(narrative_conf["bands"][_band(energy)], salt=11)
    closer_template = pick(narrative_conf["closers"], salt=13)
    closer = closer_template.format(best=focus[best], caution=focus[worst])
    narrative = f"{opener} {closer}"

    day_nakshatra = NAKSHATRAS[sky["day_nakshatra_index"]]
    why = tconf["why"].format(
        day_nakshatra=day_nakshatra,
        tara_name=TARA_NAMES[tara - 1],
        natal=NAKSHATRAS[natal_index],
    )

    opportunity_template = pick(tconf["opportunity"], salt=17)
    warning_template = pick(tconf["warning"], salt=19)

    lucky = rules["lucky_by_weekday"][wd]
    payload = {
        "nakshatra_index": natal_index,
        "nakshatra": NAKSHATRAS[natal_index],
        "tara": {"number": tara, "name": TARA_NAMES[tara - 1]},
        "energy": energy,
        "scores": {labels[a]: scores[a] for a in order},
        "area_lines": area_lines,
        "band_labels": band_labels,
        "score_why": score_why,
        "narrative": narrative,
        "why": why,
        "lucky": {
            "color": lucky["color"],
            "number": lucky["number"],
            "direction": lucky["direction"],
        },
        "good_for": list(tconf["good_for"]),
        "avoid": list(tconf["avoid"]),
        "opportunity": opportunity_template.format(area=labels[best]),
        "warning": warning_template.format(area=labels[worst]),
        "opportunity_detail": tconf["opportunity_detail"],
        "warning_detail": tconf["warning_detail"],
    }

    # content_v4 (A5): the compose bundle — every (date, nakshatra)-determined
    # PIECE the read-time ascendant adjustment recombines, so the Worker can
    # recompose scores/best/worst-dependent copy without holding any corpus of
    # its own. Emitted only when the rules carry the v4 house tables; under
    # v3_2 rules the payload above is byte-identical to what it always was.
    # `score_base` is the UNCLAMPED per-area base: clamp(clamped(x) + t) would
    # differ from clamp(x + t) exactly on the strong days where t matters most.
    if "house_significators" in rules:
        payload["compose"] = {
            "score_base": {labels[a]: base + area_mod.get(a, 0) for a in order},
            "score_why_cause": causes,
            "narrative_opener": opener,
            "narrative_closer": closer_template,
            "opportunity": opportunity_template,
            "warning": warning_template,
        }
    return payload


def all_guidance(sky: dict, rules: dict) -> list[dict]:
    """The 27 daily_guidance payloads (natal nakshatra 0–26) for `sky`."""
    return [guidance_for_nakshatra(i, sky, rules) for i in range(TOTAL_NAKSHATRAS)]


# ── content_v4 (A5): read-time ascendant adjustment ──────────────────────────
#
# The A4 §1 verdict (docs/ASCENDANT.md) is binding: the daily corpus stays 27
# rows/day, and the ascendant enters the daily product as SCORE-TIME ARITHMETIC
# over those rows — never as row multiplication. These functions are that
# arithmetic. In production they run in aura-api per request (src/scores.ts);
# this Python copy is the REFERENCE implementation, the source of truth the
# Worker port is cross-validated against (scripts/crossval_scores.py), exactly
# as natal_service.py is for /v1/natal. It consumes only what the Worker has:
# the guidance row (with its compose bundle), the daily_sky payload, the
# user's lagna sign index, and the score_rules tables.
#
# Measured before building (scripts/measure_a5_scores.py, 20,000 seeded births,
# 90 days): exact-vector prediction of the six scores from (energy, weekday)
# collapses from A1's 100% to 2.7%; distinct rank orders across users go from
# 1/day to mean 15/day; births 2 h apart score differently on 95.1% of
# user-days, different-city same-instant births on 17.6%.


def transit_houses(asc_sign: int, planet_signs: dict[str, int]) -> dict[str, int]:
    """Each graha's transit Whole Sign house (1–12) counted from the lagna."""
    return {p: ((s - asc_sign) % 12) + 1 for p, s in planet_signs.items()}


def _gochara(planet: str, house: int, rules: dict) -> int:
    """Gochara favourability of `planet` transiting `house` (from the lagna)."""
    weights = rules["gochara_weights"]
    if house in rules["gochara_extra_bad"].get(planet, ()):
        return weights["extra_bad"]
    if house in rules["gochara_fav"][planet]:
        return weights["fav"]
    return weights["unfav"]


def house_terms(asc_sign: int, planet_signs: dict[str, int], rules: dict) -> dict[str, int]:
    """area → its house term T: significator condition + own-house occupancy.

    T[area] = Σ_(p ∈ significators) w_p · gochara(p, house_of(p))
            + Σ_(q occupying the area's own house(s)) occupancy(q),
    with malefic occupancy flipped positive in the upachaya houses (3/6/10/11),
    where malefics classically do well.
    """
    houses = transit_houses(asc_sign, planet_signs)
    upachaya = set(rules["upachaya_houses"])
    occupancy = rules["occupancy_mod"]
    terms = {}
    for area in rules["areas"]["order"]:
        conf = rules["house_significators"][area]
        t = sum(w * _gochara(p, houses[p], rules) for p, w in conf["planets"].items())
        own = set(conf["houses"])
        for q, h in houses.items():
            if h in own:
                b = occupancy[q]
                if b < 0 and h in upachaya:
                    b = -b
                t += b
        terms[area] = t
    return terms


def apply_ascendant(row: dict, sky: dict, asc_sign: int, rules: dict) -> dict:
    """The ascendant-adjusted daily reading for one user — the A5 read path.

    Takes a precomputed 27-row guidance payload (which must carry the v4
    `compose` bundle), the day's sky payload (for `planet_signs` and the Moon
    texture group) and the user's natal lagna sign, and returns a NEW payload
    in which every quantity downstream of the six area scores is recomputed
    coherently: scores, band labels, the score-detail "why" (recognition
    re-selected for the ACTUAL band; the biggest-|T| area's cause swapped to
    the house line that names the actual mover), narrative closer, opportunity
    and warning. Everything else — energy, tara, area_lines, lucky, why — is
    (nakshatra, date) ground and passes through untouched.

    Coherence contract (A5 §2): a score is never explained by a cause that did
    not move it. The base half (tara + weekday + paksha) keeps its rotated
    cause; the house half is voiced by the primary significator's actual
    transit house for the area where that half matters most today.
    """
    compose = row["compose"]
    order = rules["areas"]["order"]
    labels = rules["areas"]["labels"]
    planet_signs = sky["planet_signs"]

    terms = house_terms(asc_sign, planet_signs, rules)
    scores = {a: _clamp(compose["score_base"][labels[a]] + terms[a]) for a in order}
    best = max(order, key=lambda a: (scores[a], -order.index(a)))
    worst = min(order, key=lambda a: (scores[a], order.index(a)))

    # The area the house arithmetic moved hardest explains itself through the
    # house; ties resolve to the earlier area in `order`, as everywhere else.
    top = max(order, key=lambda a: (abs(terms[a]), -order.index(a)))
    houses = transit_houses(asc_sign, planet_signs)
    primary = rules["house_significators"][top]["primary"]
    house_cause = rules["why_cause_house"][top][str(houses[primary])]

    moon_group = rules["moon_groups"][str(sky["day_nakshatra_index"])]
    band_labels = {}
    score_why = {}
    for a in order:
        band = _score_band(scores[a], rules["score_bands"])
        band_labels[labels[a]] = rules["band_labels"][a][band]
        recognition = rules["why_recognition"][a][band][moon_group]
        cause = house_cause if a == top else compose["score_why_cause"][labels[a]]
        score_why[labels[a]] = f"{recognition} {cause}".strip()

    focus = rules["narrative"]["focus"]
    closer = compose["narrative_closer"].format(best=focus[best], caution=focus[worst])

    out = dict(row)
    out["scores"] = {labels[a]: scores[a] for a in order}
    out["band_labels"] = band_labels
    out["score_why"] = score_why
    out["narrative"] = f"{compose['narrative_opener']} {closer}"
    out["opportunity"] = compose["opportunity"].format(area=labels[best])
    out["warning"] = compose["warning"].format(area=labels[worst])
    out["ascendant"] = {"sign_index": asc_sign, "applied": True}
    return out


def load_rules_from_json(path: Path | str = SEED_PATH) -> dict:
    """The rules dict (rule_key → params) from the seed JSON file."""
    data = json.loads(Path(path).read_text())
    return data["rules"]


def load_rules_from_db(conn, version: str = SCORE_RULES_VERSION) -> dict:
    """The rules dict (rule_key → params) for `version` from score_rules."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT rule_key, params FROM score_rules WHERE version = %s", (version,)
        )
        rows = cur.fetchall()
    if not rows:
        raise SystemExit(f"no score_rules rows for version {version!r}; run db/migrate.py")
    return {rule_key: params for rule_key, params in rows}
