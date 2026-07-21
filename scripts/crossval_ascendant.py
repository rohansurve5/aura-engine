"""Cross-validate the Worker's ascendant against Swiss Ephemeris — the deploy gate.

The binding condition recorded in docs/ASCENDANT.md (A3, triggered by A5): no
app-visible ascendant ships without a 1,001-birth cross-validation identical
in kind to the natal one. aura-api computes the lagna in-Worker
(src/ascendant.ts, astronomy-engine + the natal.ts Vondrák stack); this script
resolves the same 1,001 births with BOTH

  (a) this engine (swe.houses_ex, lahiri_vp285 — the source of truth), and
  (b) the exact TypeScript the Worker runs (via aura-api/scripts/
      ascendant-batch.ts — no reimplementation),

and requires longitude within 1 arc-min on every birth, plus sign agreement on
every birth that is not a BOUNDARY CASE. A boundary case is a birth both sides
place within 1′ of the SAME sign ingress (1′ of ascendant ≈ 4 seconds of birth
time): there the sign is genuinely contested — the reference sites themselves
disagree by ~2.5 min at ingresses — and pretending one side is "right" would
be tuning, not validation. Boundary cases are counted, flagged in the golden
(`boundary: true`) and asserted AS boundary cases by the vitest gate; expected
rate ~1 in 3,000 births. This is the boundary-honesty policy ASCENDANT.md says
lands with the first app-visible ascendant — /v1/natal exposes the same fact
to the app as `ascendant.near_boundary` (within 0.5° ≈ ±2 min of birth time).

Births: seeded, 1930-2025, population-weighted over the 20 largest Indian
cities (the launch market) plus a fixed world-city panel (diaspora + southern
hemisphere + a +05:45 zone), all resolved through IANA zones AT the birth
instant — so the 1943 war-time Kolkata offset is exercised on both sides.

On success it (re)writes aura-api/test/golden/ascendant_crossval.json so the
same expectations gate `npm test` in aura-api CI on every deploy.

Run:  uv run python scripts/crossval_ascendant.py
Exit: non-zero on ANY disagreement (failing births are printed; do not tune).
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from engine.chart import ascendant_sidereal
from engine.timezones import local_to_utc

ENGINE_ROOT = Path(__file__).resolve().parent.parent
AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "ascendant_crossval.json"

SEED = 285
N_INDIA = 960
START = datetime(1930, 1, 1, 0, 0)
END = datetime(2025, 12, 31, 23, 59)
ARC_MIN_DEG = 1.0 / 60.0

# (city, lat, lon, population-millions) — 2011-census metro weights.
INDIA_CITIES = [
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
INDIA_WEIGHTS = [c[3] for c in INDIA_CITIES]

# Diaspora / stress panel: southern hemisphere, DST-observing zones, a
# fractional-offset zone, and the 1943 war-time-DST Kolkata birth the golden
# chart tests pin. 40 births spread across these + the seeded remainder = 1001.
WORLD_CITIES = [
    ("London", 51.5074, -0.1278, "Europe/London"),
    ("New York", 40.7128, -74.0060, "America/New_York"),
    ("Singapore", 1.3521, 103.8198, "Asia/Singapore"),
    ("Dubai", 25.2048, 55.2708, "Asia/Dubai"),
    ("Sydney", -33.8688, 151.2093, "Australia/Sydney"),
    ("Toronto", 43.6532, -79.3832, "America/Toronto"),
    ("Kathmandu", 27.7172, 85.3240, "Asia/Kathmandu"),
    ("Wellington", -41.2866, 174.7756, "Pacific/Auckland"),
]
KNOWN_CASE = {
    "dob": "1943-06-15", "time": "06:30", "zone": "Asia/Kolkata",
    "lat": 22.5626, "lon": 88.3630,
}


def generate_cases() -> list[dict]:
    rng = random.Random(SEED)
    span_minutes = int((END - START).total_seconds() // 60)
    cases = []
    for _ in range(N_INDIA):
        when = START + timedelta(minutes=rng.randrange(span_minutes + 1))
        city = rng.choices(INDIA_CITIES, weights=INDIA_WEIGHTS)[0]
        cases.append({
            "dob": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"),
            "zone": "Asia/Kolkata", "lat": city[1], "lon": city[2],
        })
    for i in range(40):
        when = START + timedelta(minutes=rng.randrange(span_minutes + 1))
        city = WORLD_CITIES[i % len(WORLD_CITIES)]
        cases.append({
            "dob": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"),
            "zone": city[3], "lat": city[1], "lon": city[2],
        })
    cases.append(KNOWN_CASE)
    return cases


def engine_ascendant(case: dict) -> dict:
    birth = datetime.strptime(f"{case['dob']} {case['time']}", "%Y-%m-%d %H:%M")
    asc = ascendant_sidereal(local_to_utc(birth, case["zone"]), case["lat"], case["lon"])
    return {
        "longitude": asc.longitude,
        "sign_index": asc.sign_index,
        "sign": asc.sign,
    }


def worker_ascendant(cases: list[dict]) -> list[dict]:
    proc = subprocess.run(
        ["node", "scripts/ascendant-batch.ts"],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        cwd=AURA_API,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    cases = generate_cases()
    print(f"cross-validating {len(cases)} births (seed={SEED}, 1930-2025, "
          f"20 Indian cities + {len(WORLD_CITIES)} world cities) ...")

    expected = [engine_ascendant(c) for c in cases]
    actual = worker_ascendant(cases)

    def boundary_distance(lon: float) -> float:
        """Degrees to the nearest sign ingress."""
        return min(lon % 30, 30 - lon % 30)

    mismatches = []
    boundary_cases = []
    max_delta_asec = 0.0
    for case, exp, act in zip(cases, expected, actual, strict=True):
        delta = abs((act["longitude"] - exp["longitude"] + 180) % 360 - 180)
        max_delta_asec = max(max_delta_asec, delta * 3600)
        if delta >= ARC_MIN_DEG:
            mismatches.append((case, exp, act, delta * 3600))
        elif act["sign_index"] != exp["sign_index"]:
            # Same point on the sky to <1'; the SIGN disagrees only if that
            # point straddles an ingress. Both sides within 1' of it → the
            # contested-boundary case, recorded rather than adjudicated.
            if (boundary_distance(exp["longitude"]) < ARC_MIN_DEG
                    and boundary_distance(act["longitude"]) < ARC_MIN_DEG):
                boundary_cases.append((case, exp, act, delta * 3600))
            else:
                mismatches.append((case, exp, act, delta * 3600))

    n = len(cases)
    agree = n - len(mismatches) - len(boundary_cases)
    print(f"sign agreement: {agree}/{n} = {agree / n:.2%} "
          f"(+{len(boundary_cases)} boundary case(s) within 1' of an ingress)")
    print(f'max ascendant-longitude delta: {max_delta_asec:.2f}" '
          f"({max_delta_asec / 60:.4f} arc-min)")
    for case, exp, act, dsec in boundary_cases:
        print(f"  boundary: {case['dob']} {case['time']} {case['zone']} — engine "
              f"{exp['sign']} {exp['longitude']:.4f}° vs worker {act['sign']} "
              f"{act['longitude']:.4f}° (Δ {dsec:.1f}\", "
              f"{boundary_distance(exp['longitude']) * 240:.1f} s of birth time "
              f"from the ingress)")

    if mismatches:
        print(f"\nFAILURES ({len(mismatches)}):")
        for case, exp, act, dsec in mismatches[:20]:
            print(f"  {case['dob']} {case['time']} {case['zone']} "
                  f"({case['lat']:.2f},{case['lon']:.2f}): engine {exp['sign']} "
                  f"{exp['longitude']:.4f} vs worker {act['sign']} "
                  f"{act['longitude']:.4f} (Δ {dsec:.1f}\")")
        return 1

    boundary_keys = {id(case) for case, *_ in boundary_cases}
    golden = [
        {**case, "boundary": id(case) in boundary_keys, "expected": exp}
        for case, exp in zip(cases, expected, strict=True)
    ]
    GOLDEN_PATH.write_text(json.dumps(golden, indent=1) + "\n")
    print(f"wrote {GOLDEN_PATH.relative_to(AURA_API.parent)} ({len(golden)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
