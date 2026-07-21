"""Birth-time sensitivity of the ascendant — the A3 justification number.

Measures, on a seeded synthetic user population (birth years 1961-2008 =
ages ~18-65 at launch; city drawn population-weighted from the 20 largest
Indian cities, the launch market — all IST, so wall clock = instant):

  1. P(ascendant SIGN changes | birth shifted 4 minutes)
  2. What changes when a birth shifts 2 hours (asc sign, Moon nakshatra,
     Moon sign, house assignments)
  3. Same instant, different city: P(asc sign differs) + degree spread
  4. THE NUMBER: fraction of random user PAIRS whose personalisation key
     collides — before A3 (Moon nakshatra only, the measured 1-in-27) vs
     after (nakshatra + ascendant sign, and the full sign-level chart).

Deterministic: seeded RNG, no wall-clock reads. Results are pasted into
docs/ASCENDANT.md; re-run with  uv run python scripts/sensitivity_ascendant.py
"""

from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from engine.chart import ascendant_sidereal, compute_chart
from engine.timezones import local_to_utc
from engine.vimshottari import nakshatra_of

SEED = 285
N_BIRTHS = 40_000       # base pool (metrics 1-3 use slices of it)
N_PAIRS = 200_000       # pairs drawn from the pool for metric 4
START = datetime(1961, 1, 1)
END = datetime(2008, 12, 31, 23, 59)

# (city, lat, lon, population-millions) — 2011-census metro weights.
CITIES = [
    ("Mumbai", 19.0760, 72.8777, 12.4), ("Delhi", 28.6139, 77.2090, 11.0),
    ("Bangalore", 12.9716, 77.5946, 8.4), ("Hyderabad", 17.3850, 78.4867, 6.8),
    ("Ahmedabad", 23.0225, 72.5714, 5.6), ("Chennai", 13.0878, 80.2785, 4.6),
    ("Kolkata", 22.5626, 88.3630, 4.5), ("Surat", 21.1702, 72.8311, 4.5),
    ("Pune", 18.5204, 73.8567, 3.1), ("Jaipur", 26.9124, 75.7873, 3.1),
    ("Lucknow", 26.8467, 80.9462, 2.8), ("Kanpur", 26.4499, 80.3319, 2.8),
    ("Nagpur", 21.1458, 79.0882, 2.4), ("Indore", 22.7196, 75.8577, 1.9),
    ("Thane", 19.2183, 72.9781, 1.8), ("Bhopal", 23.2599, 77.4126, 1.8),
    ("Visakhapatnam", 17.6868, 83.2185, 1.7), ("Patna", 25.5941, 85.1376, 1.7),
    ("Vadodara", 22.3072, 73.1812, 1.7), ("Ghaziabad", 28.6692, 77.4538, 1.6),
]
WEIGHTS = [c[3] for c in CITIES]


def main() -> None:
    rng = random.Random(SEED)
    span_min = int((END - START).total_seconds() // 60)

    print(f"pool: {N_BIRTHS} births, 1961-2008, 20 Indian cities (pop-weighted)")
    births = []
    for _ in range(N_BIRTHS):
        when = START + timedelta(minutes=rng.randrange(span_min + 1))
        city = rng.choices(CITIES, weights=WEIGHTS)[0]
        births.append((when, city))

    # Full sign-level chart per birth (vp285, the product ayanamsa).
    charts = []
    for when, (_, lat, lon, _) in births:
        c = compute_chart(local_to_utc(when, "+05:30"), lat, lon)
        moon = c.placements["Moon"].position.longitude
        charts.append(
            (
                c.ascendant.sign_index,
                nakshatra_of(moon).index,
                tuple(int(p.position.longitude // 30) for p in c.placements.values()),
            )
        )

    # 1. four minutes
    n_flip = 0
    sub = births[:10_000]
    for when, (_, lat, lon, _) in sub:
        a0 = ascendant_sidereal(local_to_utc(when, "+05:30"), lat, lon)
        a1 = ascendant_sidereal(local_to_utc(when + timedelta(minutes=4), "+05:30"), lat, lon)
        n_flip += a0.sign_index != a1.sign_index
    print(f"\n1. birth +4 min: ascendant SIGN changes in {n_flip}/{len(sub)} "
          f"= {n_flip / len(sub):.2%} of births")

    # 2. two hours
    n_asc = n_nak = n_moonsign = 0
    for i, (when, (_, lat, lon, _)) in enumerate(sub):
        c2 = compute_chart(local_to_utc(when + timedelta(hours=2), "+05:30"), lat, lon)
        asc0, nak0, signs0 = charts[i]
        moon2 = c2.placements["Moon"].position.longitude
        n_asc += asc0 != c2.ascendant.sign_index
        n_nak += nak0 != nakshatra_of(moon2).index
        n_moonsign += signs0[1] != int(moon2 // 30)
    n = len(sub)
    print(f"\n2. birth +2 h: asc sign changes {n_asc / n:.1%}, "
          f"Moon nakshatra {n_nak / n:.1%}, Moon sign {n_moonsign / n:.1%} "
          f"(when the asc sign changes, all 12 Whole Sign house assignments shift)")

    # 3. same instant, different city
    n_diff = 0
    deg = []
    for when, (name, lat, lon, _) in sub:
        other = rng.choices(CITIES, weights=WEIGHTS)[0]
        while other[0] == name:
            other = rng.choices(CITIES, weights=WEIGHTS)[0]
        a0 = ascendant_sidereal(local_to_utc(when, "+05:30"), lat, lon)
        a1 = ascendant_sidereal(local_to_utc(when, "+05:30"), other[1], other[2])
        n_diff += a0.sign_index != a1.sign_index
        deg.append(abs((a0.longitude - a1.longitude + 180) % 360 - 180))
    deg.sort()
    print(f"\n3. same instant, different Indian city: asc sign differs "
          f"{n_diff / n:.1%}; |asc delta| median {deg[n // 2]:.2f} deg, "
          f"p90 {deg[int(n * 0.9)]:.2f} deg, max {deg[-1]:.2f} deg")

    # 4. THE NUMBER — random-pair collisions
    same_nak = same_nak_asc = same_chart = 0
    for _ in range(N_PAIRS):
        a = charts[rng.randrange(N_BIRTHS)]
        b = charts[rng.randrange(N_BIRTHS)]
        if a[1] == b[1]:
            same_nak += 1
            if a[0] == b[0]:
                same_nak_asc += 1
                if a[2] == b[2]:
                    same_chart += 1
    print(f"\n4. random user pairs ({N_PAIRS}):")
    print(f"   same Moon nakshatra (BEFORE A3 key):        {same_nak}  "
          f"= {same_nak / N_PAIRS:.3%}  (~1 in {N_PAIRS / max(same_nak, 1):.0f})")
    print(f"   same nakshatra + asc sign (minimal A4 key):  {same_nak_asc}  "
          f"= {same_nak_asc / N_PAIRS:.3%}  (~1 in {N_PAIRS / max(same_nak_asc, 1):.0f})")
    print(f"   fully identical sign-level chart:            {same_chart}  "
          f"= {same_chart / N_PAIRS:.4%}")


if __name__ == "__main__":
    main()
