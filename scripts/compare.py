"""Print a full delta report: engine vs the AstroSage golden table.

    uv run python scripts/compare.py            # AstroSage-matching ayanamsa
    uv run python scripts/compare.py lahiri     # any registered ayanamsa

Shows the balance, every maha boundary, and every antar end date with its delta
in days, so a mismatch is auditable rather than hidden behind a pass/fail.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from engine.ephemeris import ASTROSAGE_AYANAMSA  # noqa: E402
from engine.positions import positions_from_ist  # noqa: E402
from engine.vimshottari import compute_dasha  # noqa: E402

_ROOT = os.path.join(os.path.dirname(__file__), os.pardir)
GOLDEN = os.path.join(_ROOT, "tests", "golden", "astrosage_dasha.json")
BIRTH = datetime(1989, 9, 23, 4, 47)


def _d(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    ayanamsa = sys.argv[1] if len(sys.argv) > 1 else ASTROSAGE_AYANAMSA
    golden = json.load(open(GOLDEN))
    moon = positions_from_ist(BIRTH, ayanamsa=ayanamsa)["Moon"].longitude
    res = compute_dasha(moon, BIRTH, year_mode="solar", levels=2, cycles=2)

    print(f"Birth: 23/09/1989 04:47 IST   Moon(sid)={moon:.5f}°   ayanamsa={ayanamsa}")
    print(f"Nakshatra: {res.nakshatra.name} pada {res.nakshatra.pada} "
          f"(lord {res.nakshatra.lord})")
    gb = golden["balance"]
    print(f"Balance:  engine {res.balance}   |   AstroSage "
          f"{gb['lord'].upper()} {gb['years']} Y {gb['months']} M {gb['days']} D")
    print("=" * 64)

    maha_deltas: list[int] = []
    antar_deltas: list[int] = []
    for gi, gm in enumerate(golden["maha"]):
        maha = res.mahas[gi]
        de = (maha.end.date() - _d(gm["end"])).days
        maha_deltas.append(abs(de))
        print(f"\n{gm['lord']:8} MAHA  end engine {maha.end.date()} "
              f"golden {gm['end']}  Δ{de:+d}d")
        for ai, ga in enumerate(gm["antar"]):
            if ga["end"] is None:
                continue
            da = (maha.children[ai].end.date() - _d(ga["end"])).days
            antar_deltas.append(abs(da))
            flag = "  <-- >1d" if abs(da) > 1 else ""
            print(f"    {ga['lord']:8} engine {maha.children[ai].end.date()} "
                  f"golden {ga['end']}  Δ{da:+d}d{flag}")

    print("\n" + "=" * 64)
    print(f"MAHA   : n={len(maha_deltas)} maxΔ={max(maha_deltas)}d "
          f"avgΔ={sum(maha_deltas) / len(maha_deltas):.2f}d "
          f"within±1={sum(1 for d in maha_deltas if d <= 1)}/{len(maha_deltas)}")
    print(f"ANTAR  : n={len(antar_deltas)} maxΔ={max(antar_deltas)}d "
          f"avgΔ={sum(antar_deltas) / len(antar_deltas):.2f}d "
          f"within±1={sum(1 for d in antar_deltas if d <= 1)}/{len(antar_deltas)}")


if __name__ == "__main__":
    main()
