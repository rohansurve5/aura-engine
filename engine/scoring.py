"""content_v2 scoring + copy composition: (natal nakshatra × today's sky) → daily guidance.

This module is the deterministic *engine* that applies a rules dict. It holds no
magic numbers and no copy of its own — every tunable value and every line of
user-visible text lives in the `score_rules` table (seeded from
db/seed/score_rules_content_v2.json). Load the rules with `load_rules_from_db`
(job) or `load_rules_from_json` (tests), then call `all_guidance(sky, rules)`.

Vedic basis (unchanged from v1): **Tarabala** — the 9-fold auspiciousness cycle
counted from the natal (janma) nakshatra to the day's Moon nakshatra — sets the
base energy. The weekday (hora) lord and paksha modulate it per life-area; lucky
colour/number/direction come from the day lord (dik + Vedic numerology).

content_v2 additions composed here from the seed's content library:
  • `scores` now use the USER-FACING six areas — Love, Money, Career, Mind,
    Health, Mood — matching the app screens key-for-key.
  • `area_lines` — one warm, actionable line per area from the 54-cell
    (area × tara) library, variant-rotated by date so consecutive days differ.
  • `narrative` — the two-sentence "story of your day" (energy band opener +
    best-area / caution-area closer).
  • `opportunity` / `warning` (+ `_detail`) — rewritten generators, same voice.
  • `why` — the "why this reading" credibility line; the ONLY field where
    tara/nakshatra jargon leads. Headline copy stays jargon-free.

Determinism: pure integer arithmetic with fixed rounding, stable tie-breaks and
date-ordinal variant rotation — no `now()` / randomness. Same `sky` + same
`rules` → byte-identical output.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .vimshottari import NAKSHATRAS, TOTAL_NAKSHATRAS

SCORE_RULES_VERSION = "content_v2"
SEED_PATH = (
    Path(__file__).resolve().parent.parent / "db" / "seed" / "score_rules_content_v2.json"
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


def _pick(variants: list, day_ordinal: int, natal_index: int, salt: int):
    """Deterministic variant rotation: consecutive dates always advance the
    index (7 is coprime with 2 and 3, the variant-list lengths), the natal index
    de-syncs users, and `salt` de-syncs fields from each other."""
    return variants[(day_ordinal * 7 + natal_index * 3 + salt) % len(variants)]


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
