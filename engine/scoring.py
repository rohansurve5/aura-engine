"""v1 heuristic scoring: (natal nakshatra × today's sky) → daily guidance.

This module is the deterministic *engine* that applies a rules dict. It holds no
magic numbers of its own — every tunable value and every line of copy lives in
the `score_rules` table (seeded from db/seed/score_rules_v1.json). Load the rules
with `load_rules_from_db` (job) or `load_rules_from_json` (tests), then call
`all_guidance(sky, rules)`.

Vedic basis: **Tarabala** — the 9-fold auspiciousness cycle counted from the
natal (janma) nakshatra to the day's Moon nakshatra — sets the base energy. The
weekday (hora) lord and paksha modulate it per life-area; lucky
colour/number/direction come from the day lord (dik + Vedic numerology).

Determinism: pure integer arithmetic with fixed rounding and stable tie-breaks,
no `now()` / randomness. Same `sky` + same `rules` → byte-identical output.
"""

from __future__ import annotations

import json
from pathlib import Path

from .vimshottari import NAKSHATRAS, TOTAL_NAKSHATRAS

SCORE_RULES_VERSION = "v1"
SEED_PATH = Path(__file__).resolve().parent.parent / "db" / "seed" / "score_rules_v1.json"

# The nine taras (1-indexed), in cycle order from the natal nakshatra.
TARA_NAMES = (
    "Janma", "Sampat", "Vipat", "Kshema", "Pratyak",
    "Sadhaka", "Vadha", "Mitra", "Parama Mitra",
)


def tara_of(natal_index: int, day_moon_index: int) -> int:
    """Tarabala 1–9: count natal→day-Moon nakshatra, folded into the 9-cycle."""
    count = ((day_moon_index - natal_index) % TOTAL_NAKSHATRAS) + 1  # 1..27
    return ((count - 1) % 9) + 1                                     # 1..9


def _clamp(value: float) -> int:
    return max(0, min(100, int(round(value))))


def guidance_for_nakshatra(natal_index: int, sky: dict, rules: dict) -> dict:
    """The daily_guidance payload for one natal nakshatra against `sky`."""
    tara = tara_of(natal_index, sky["day_nakshatra_index"])
    tconf = rules["tara"][str(tara)]
    wd = str(sky["weekday_index"])

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

    lucky = rules["lucky_by_weekday"][wd]
    return {
        "nakshatra_index": natal_index,
        "nakshatra": NAKSHATRAS[natal_index],
        "tara": {"number": tara, "name": TARA_NAMES[tara - 1]},
        "energy": energy,
        "scores": {labels[a]: scores[a] for a in order},
        "lucky": {
            "color": lucky["color"],
            "number": lucky["number"],
            "direction": lucky["direction"],
        },
        "good_for": list(tconf["good_for"]),
        "avoid": list(tconf["avoid"]),
        "opportunity": tconf["opportunity"].format(area=labels[best]),
        "warning": tconf["warning"].format(area=labels[worst]),
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
