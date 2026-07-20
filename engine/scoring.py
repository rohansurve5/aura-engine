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

from .vimshottari import NAKSHATRAS, TOTAL_NAKSHATRAS

SCORE_RULES_VERSION = "content_v3_1"
SEED_PATH = (
    Path(__file__).resolve().parent.parent / "db" / "seed" / "score_rules_content_v3_1.json"
)

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
    for i, a in enumerate(order):
        band = _score_band(scores[a], rules["score_bands"])
        band_labels[labels[a]] = rules["band_labels"][a][band]
        recognition = rules["why_recognition"][a][band][moon_group]
        cause = _cause(
            sources[a], a, sky, rules, tara, lambda v, i=i: pick(v, salt=23 + i)
        )
        score_why[labels[a]] = f"{recognition} {cause}".strip()

    # Two-sentence "story of your day": energy-band opener + best/caution closer.
    narrative_conf = rules["narrative"]
    focus = narrative_conf["focus"]
    opener = pick(narrative_conf["bands"][_band(energy)], salt=11)
    closer = pick(narrative_conf["closers"], salt=13).format(
        best=focus[best], caution=focus[worst]
    )
    narrative = f"{opener} {closer}"

    day_nakshatra = NAKSHATRAS[sky["day_nakshatra_index"]]
    why = tconf["why"].format(
        day_nakshatra=day_nakshatra,
        tara_name=TARA_NAMES[tara - 1],
        natal=NAKSHATRAS[natal_index],
    )

    lucky = rules["lucky_by_weekday"][wd]
    return {
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
        "opportunity": pick(tconf["opportunity"], salt=17).format(area=labels[best]),
        "warning": pick(tconf["warning"], salt=19).format(area=labels[worst]),
        "opportunity_detail": tconf["opportunity_detail"],
        "warning_detail": tconf["warning_detail"],
    }


def all_guidance(sky: dict, rules: dict) -> list[dict]:
    """The 27 daily_guidance payloads (natal nakshatra 0–26) for `sky`."""
    return [guidance_for_nakshatra(i, sky, rules) for i in range(TOTAL_NAKSHATRAS)]


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
