"""Does keying the DAILY reading on the ascendant change the daily claim?

The A4 gate measurement. A3 proved the ascendant is computable and that a
(nakshatra, asc-sign) key would cut identical-reading collisions from 1-in-27
to 1-in-286. This script measures whether the extra key actually changes the
DAILY claim, or only relabels it — the difference between real gochara and
27 readings repeated 12 times under a bigger cache key.

Whole Sign houses (what we ship): house(planet, asc) = (sign(planet) − asc)
mod 12 + 1. Everything below follows from real sky over a full year, sampled
at the 00:00 IST day boundary — the same convention engine/transits.py reads
by.

  1. STRUCTURE — per day, the 12 ascendants' house-configurations: how many
     are distinct as labeled vectors, and how many up to rotation. If every
     day is 12-labeled / 1-canonical, the asc axis holds exactly one degree
     of freedom: the shared sky, rotated.
  2. CADENCE — per planet, sign-dwell at the day boundary over the year and
     inside the live 40-day precompute window: which movers change house on
     a daily-reading cadence and which are standing configuration (owned by
     the transit report).
  3. THE MOON LINE — the only fast mover: for a fixed user, how often does
     the Moon's house actually change day-over-day, the run-length
     distribution, and how often the Moon changes sign INSIDE a civil day
     (making "the Moon is in your Nth today" partly false for any key).
  4. INFORMATION — what a 324-row day would actually contain: distinct
     asc-dependent fragments per day and over the whole year, vs the 27
     nakshatra rows.

Deterministic: fixed span, no wall-clock reads. Results are pasted into
docs/ASCENDANT.md; re-run with  uv run python scripts/measure_gochara_daily.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from engine.ephemeris import ist_to_utc
from engine.positions import BODIES, sidereal_positions

START = date(2026, 7, 21)          # audit date; fixed for reproducibility
DAYS = 366
PRECOMPUTE_WINDOW = 40             # the live buffer: today .. today+39


def signs_at_ist_midnight(day: date) -> dict[str, int]:
    utc = ist_to_utc(datetime.combine(day, time(0, 0)))
    return {b: int(p.longitude // 30) for b, p in sidereal_positions(utc).items()}


def house_vector(signs: dict[str, int], asc: int) -> tuple[int, ...]:
    return tuple((signs[b] - asc) % 12 + 1 for b in BODIES)


def main() -> None:
    days = [START + timedelta(d) for d in range(DAYS + 1)]  # +1 for day-over-day
    daily_signs = [signs_at_ist_midnight(d) for d in days]

    # -- 1 · STRUCTURE ------------------------------------------------------
    labeled_counts, canonical_counts = set(), set()
    for signs in daily_signs[:DAYS]:
        vecs = [house_vector(signs, asc) for asc in range(12)]
        labeled_counts.add(len(set(vecs)))
        # canonical form: rotate each vector to asc=0's frame; if all 12
        # reduce to one orbit, the asc axis is a pure rotation of shared sky.
        canon = {tuple((h - 1 + asc) % 12 + 1 for h in vec) for asc, vec in enumerate(vecs)}
        canonical_counts.add(len(canon))
    print(f"1. STRUCTURE over {DAYS} days:")
    print(f"   distinct labeled house-vectors per day, across 12 ascs: {sorted(labeled_counts)}")
    print(f"   distinct configurations UP TO ROTATION per day:          {sorted(canonical_counts)}")

    # -- 2 · CADENCE --------------------------------------------------------
    print(f"\n2. CADENCE at the 00:00 IST boundary ({DAYS} days / {PRECOMPUTE_WINDOW}-day window):")
    print(f"   {'planet':8} {'changes/yr':>10} {'mean dwell d':>13} {'changes in window':>18}")
    for b in BODIES:
        series = [s[b] for s in daily_signs]
        changes = sum(1 for i in range(1, DAYS + 1) if series[i] != series[i - 1])
        window_changes = sum(
            1 for i in range(1, PRECOMPUTE_WINDOW) if series[i] != series[i - 1]
        )
        dwell = DAYS / changes if changes else float("inf")
        print(f"   {b:8} {changes:>10} {dwell:>13.1f} {window_changes:>18}")

    # -- 3 · THE MOON LINE --------------------------------------------------
    moon = [s["Moon"] for s in daily_signs]
    # house-change probability is asc-independent: house changes iff sign does
    flips = [moon[i] != moon[i - 1] for i in range(1, DAYS + 1)]
    p_change = sum(flips) / len(flips)
    runs: list[int] = []
    run = 1
    for f in flips:
        if f:
            runs.append(run)
            run = 1
        else:
            run += 1
    runs.append(run)
    rc = Counter(runs)
    intraday = 0
    for d in days[:DAYS]:
        s0 = signs_at_ist_midnight(d)["Moon"]
        s24 = signs_at_ist_midnight(d + timedelta(1))["Moon"]
        intraday += s0 != s24
    print("\n3. THE MOON LINE (the only fast mover), fixed user:")
    print(f"   P(Moon house changes day-over-day): {p_change:.1%}")
    print(f"   unchanged-run lengths (days): {dict(sorted(rc.items()))}")
    print(f"   days where the Moon changes sign INSIDE the civil day: "
          f"{intraday}/{DAYS} = {intraday / DAYS:.1%}")

    # -- 4 · INFORMATION in a 324-row day -----------------------------------
    # row(day, nak, asc) = row27(day, nak) + moon-house fragment, where the
    # fragment is fully determined by (moon_sign(day) − asc) mod 12.
    frag_values_per_day = {
        len({(s["Moon"] - asc) % 12 for asc in range(12)}) for s in daily_signs[:DAYS]
    }
    frag_pool_year = {
        (s["Moon"] - asc) % 12 for s in daily_signs[:DAYS] for asc in range(12)
    }
    print("\n4. INFORMATION in a 324-row/day scheme (27 nak x 12 asc):")
    print(f"   asc-dependent fragment values per day: "
          f"{sorted(frag_values_per_day)} (of 12 possible)")
    print(f"   distinct fragment values over the whole year: {len(frag_pool_year)}")
    print(f"   rows/year at 324/day: {324 * DAYS:,} — containing {27 * DAYS:,} nakshatra "
          f"readings + a static {len(frag_pool_year)}-entry house-line table")


if __name__ == "__main__":
    main()
