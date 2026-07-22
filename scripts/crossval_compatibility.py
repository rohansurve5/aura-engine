"""Freeze the Ashtakoota + Mangal breakdown for a curated couple set.

WHY THIS IS A "PIN", NOT AN EPHEMERIS CROSS-VALIDATION. Unlike
`crossval_dasha.py` / `crossval_natal.py`, compatibility is not an independent
numerical computation to be reproduced against a reference site's ephemeris —
it is a deterministic table lookup keyed off the Moon nakshatra and rashi, both
of which ARE already cross-validated to the dasha standard (that is what makes
the inputs trustworthy). So this script pins two things:

  1. the encoded classical tables (Nadi/Gana/Yoni/Varna/Vashya/Bhakoot), each
     verified against its cited canonical source in tests/test_compatibility.py;
  2. the full per-koota breakdown for a couple set engineered to exercise every
     contested case — Nadi dosha, Bhakoot dosha, both with and without the
     recognised parihar, Yoni sworn-enemy, the Gana asymmetry, a same-nakshatra
     pair, and a high/low tally — so a table edit that silently moves a score
     is caught by the sha256 pin.

Live per-couple cross-validation against AstroSage / DrikPanchang was NOT
possible headlessly: both are POST-only form calculators (documented in
docs/COMPATIBILITY.md). That matters far less here than for the ephemeris,
because the only thing that can differ is the *choice of table* where the
tradition itself disagrees (parihar, Graha Maitri fractions, Vashya, Yoni
middles) — and those divergences are documented and asserted, not smoothed.

Run:  uv run python scripts/crossval_compatibility.py
Exit: 0 on success; rewrites tests/golden/compatibility_couples.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from engine.compatibility import (  # noqa: E402
    Person,
    bhakoot_parihar,
    describe_match,
    guna_milan,
    nadi_parihar,
)
from engine.vimshottari import NAKSHATRA_ARC, NAKSHATRAS  # noqa: E402

GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "compatibility_couples.json"


def person_at(nak_index: int, pada: int) -> Person:
    """A Person whose Moon sits at the midpoint of (nakshatra, pada). Both the
    nakshatra AND the rashi fall out of this one longitude — as they do in
    reality — so the fixtures never pretend nakshatra and sign are independent."""
    pada_arc = NAKSHATRA_ARC / 4
    lon = nak_index * NAKSHATRA_ARC + (pada - 0.5) * pada_arc
    return Person(lon)


# (label, (groom_nak, groom_pada), (bride_nak, bride_pada), what it exercises).
# Nakshatra indices are 0-based (0 = Ashwini ... 26 = Revati).
COUPLES = [
    ("same-nakshatra (Nadi dosha + pada parihar)", (0, 1), (0, 3),
     "same nakshatra => same Nadi => dosha; parihar 'same nakshatra, different pada'"),
    ("Aries x Scorpio (Bhakoot 6/8 + same-lord parihar + Nadi dosha)", (1, 1), (16, 2),
     "Bhakoot 6/8 dosha, lords both Mars => parihar; Bharani/Anuradha both Madhya => Nadi dosha"),
    ("Taurus x Capricorn (Bhakoot 5/9 + friendly-lord parihar)", (3, 1), (21, 2),
     "Bhakoot 5/9 dosha, Venus & Saturn mutual friends => parihar"),
    ("Yoni sworn enemy Cow/Tiger", (11, 2), (13, 1),
     "Uttara Phalguni (Cow) vs Chitra (Tiger) => Yoni 0, a recognised dosha pole"),
    ("Gana asymmetry: Deva groom x Rakshasa bride", (0, 1), (2, 1),
     "Ashwini (Deva) x Krittika (Rakshasa) => low Gana one way"),
    ("Gana asymmetry: Rakshasa groom x Deva bride", (2, 1), (0, 1),
     "the reverse of the above — the classical asymmetry, 0 this direction"),
    ("Nadi dosha, no parihar (different rashi)", (0, 1), (5, 1),
     "Ashwini & Ardra both Aadi, different signs => Nadi dosha, no exception"),
    ("high tally", (3, 1), (11, 2),
     "Rohini x Uttara Phalguni — a broadly aligned pair"),
    ("Revati x Hasta", (26, 2), (12, 3), "spread coverage"),
    ("Magha x Mula", (9, 1), (18, 1), "two Rakshasa/Kshatriya-heavy stars"),
    ("Punarvasu x Shravana", (6, 3), (21, 1), "spread coverage"),
    ("Vishakha x Krittika", (15, 2), (2, 2), "spread coverage"),
    ("Bharani x Purva Phalguni", (1, 2), (10, 1), "spread coverage"),
    ("Jyeshtha x Dhanishta", (17, 1), (22, 4), "spread coverage"),
]


def breakdown(label: str, g: tuple[int, int], b: tuple[int, int], note: str) -> dict:
    groom, bride = person_at(*g), person_at(*b)
    res = guna_milan(groom, bride)
    desc = describe_match(groom, bride)
    return {
        "label": label,
        "note": note,
        "groom": {"nakshatra": NAKSHATRAS[g[0]], "pada": g[1], "sign": groom.sign_index},
        "bride": {"nakshatra": NAKSHATRAS[b[0]], "pada": b[1], "sign": bride.sign_index},
        "kootas": [
            {"name": k.name, "got": k.got, "max": k.maximum, "detail": k.detail,
             "is_dosha": k.is_dosha}
            for k in res.kootas
        ],
        "total": res.total,
        "nadi_parihar": nadi_parihar(groom, bride).__dict__,
        "bhakoot_parihar": bhakoot_parihar(groom, bride).__dict__,
        "lines": desc["lines"],
    }


def main() -> int:
    rows = [breakdown(*c) for c in COUPLES]
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(rows, indent=1) + "\n")
    print(f"wrote {GOLDEN.relative_to(GOLDEN.parent.parent.parent)} ({len(rows)} couples)")
    doshas = sum(1 for r in rows if any(k["is_dosha"] for k in r["kootas"]))
    parihars = sum(
        1 for r in rows if r["nadi_parihar"]["applies"] or r["bhakoot_parihar"]["applies"]
    )
    print(f"couples with >=1 dosha: {doshas}/{len(rows)}")
    print(f"couples with an applicable parihar: {parihars}/{len(rows)}")
    print(f"total range: {min(r['total'] for r in rows)}..{max(r['total'] for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
