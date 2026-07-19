"""Cross-validate the Worker's natal math against Swiss Ephemeris — the deploy gate.

aura-api computes natal nakshatras in-Worker with astronomy-engine (MIT).
This script is the accuracy contract: it generates 1,000 seeded-random birth
datetimes (1930-2025 IST), resolves each with BOTH

  (a) this engine (Swiss Ephemeris, lahiri_vp285 — the source of truth), and
  (b) the exact TypeScript used by the Worker (aura-api/src/natal.ts, executed
      by node via aura-api/scripts/natal-batch.ts — no reimplementation),

and requires 100% agreement on nakshatra_index and moon_sign. It also logs the
maximum Moon-longitude delta (expected well under 1 arc-min) and asserts the
known golden chart (1989-09-23 04:47 IST -> Ardra pada 4, Gemini Moon, Virgo
Sun) on both sides.

On success it (re)writes aura-api/test/golden/natal_crossval.json so the same
1,000 expectations are enforced by `npm test` in aura-api CI on every deploy,
without needing Python there.

Run:  uv run python scripts/crossval_natal.py
Exit: non-zero on ANY disagreement (failing datetimes are printed; do not tune).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from engine.positions import positions_from_ist
from engine.vimshottari import nakshatra_of

ENGINE_ROOT = Path(__file__).resolve().parent.parent
AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "natal_crossval.json"

SEED = 285  # the VP285 zero-ayanamsa year; any fixed seed works
N_CASES = 1000
START = datetime(1930, 1, 1, 0, 0)
END = datetime(2025, 12, 31, 23, 59)
KNOWN_CASE = {"dob": "1989-09-23", "time": "04:47", "tz": "+05:30"}
KNOWN_EXPECT = {"nakshatra": "Ardra", "pada": 4, "moon_sign": "Gemini", "sun_sign": "Virgo"}


def generate_cases() -> list[dict]:
    rng = random.Random(SEED)
    span_minutes = int((END - START).total_seconds() // 60)
    cases = []
    for _ in range(N_CASES):
        when = START + timedelta(minutes=rng.randrange(span_minutes + 1))
        cases.append(
            {
                "dob": when.strftime("%Y-%m-%d"),
                "time": when.strftime("%H:%M"),
                "tz": "+05:30",
            }
        )
    return cases


def engine_natal(case: dict) -> dict:
    birth = datetime.strptime(f"{case['dob']} {case['time']}", "%Y-%m-%d %H:%M")
    positions = positions_from_ist(birth)
    moon = positions["Moon"]
    sun = positions["Sun"]
    nak = nakshatra_of(moon.longitude)
    return {
        "nakshatra_index": nak.index,
        "nakshatra": nak.name,
        "pada": nak.pada,
        "moon_sign": moon.sign,
        "sun_sign": sun.sign,
        "moon_longitude": moon.longitude,
        "sun_longitude": sun.longitude,
    }


def worker_natal(cases: list[dict]) -> list[dict]:
    proc = subprocess.run(
        ["node", "scripts/natal-batch.ts"],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        cwd=AURA_API,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    cases = generate_cases() + [KNOWN_CASE]
    print(f"cross-validating {len(cases)} births (seed={SEED}, 1930-2025 IST) ...")

    expected = [engine_natal(c) for c in cases]
    actual = worker_natal(cases)

    mismatches = []
    max_moon_delta_asec = 0.0
    max_sun_delta_asec = 0.0
    for case, exp, act in zip(cases, expected, actual, strict=True):
        moon_d = abs((act["moon_longitude"] - exp["moon_longitude"] + 180) % 360 - 180) * 3600
        sun_d = abs((act["sun_longitude"] - exp["sun_longitude"] + 180) % 360 - 180) * 3600
        max_moon_delta_asec = max(max_moon_delta_asec, moon_d)
        max_sun_delta_asec = max(max_sun_delta_asec, sun_d)
        if (
            act["nakshatra_index"] != exp["nakshatra_index"]
            or act["moon_sign"] != exp["moon_sign"]
        ):
            mismatches.append((case, exp, act, moon_d))

    n = len(cases)
    agree = n - len(mismatches)
    print(f"agreement: {agree}/{n} = {agree / n:.2%}")
    arc_min = max_moon_delta_asec / 60
    print(f'max Moon-longitude delta: {max_moon_delta_asec:.3f}" ({arc_min:.4f} arc-min)')
    print(f"max Sun-longitude delta:  {max_sun_delta_asec:.3f}\"")

    if mismatches:
        print(f"\nFAIL — {len(mismatches)} disagreement(s); DO NOT TUNE, investigate:")
        for case, exp, act, moon_d in mismatches:
            print(
                f"  {case['dob']} {case['time']} IST: engine={exp['nakshatra']}"
                f"/{exp['moon_sign']} worker={act['nakshatra']}/{act['moon_sign']}"
                f" (moon delta {moon_d:.2f}\")"
            )
        return 1

    # Known golden chart must resolve identically on both sides.
    for label, res in (("engine", expected[-1]), ("worker", actual[-1])):
        got = {k: res[k] for k in KNOWN_EXPECT}
        if got != KNOWN_EXPECT:
            print(f"FAIL — known case wrong in {label}: {got} != {KNOWN_EXPECT}")
            return 1
    print("known case (1989-09-23 04:47 IST -> Ardra pada 4, Gemini, Virgo): OK")

    golden = [
        {
            "dob": c["dob"],
            "time": c["time"],
            "tz": c["tz"],
            "expected": {
                "nakshatra_index": e["nakshatra_index"],
                "nakshatra": e["nakshatra"],
                "moon_sign": e["moon_sign"],
                "moon_longitude": round(e["moon_longitude"], 9),
            },
        }
        for c, e in zip(cases, expected, strict=True)
    ]
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(golden, indent=1) + "\n")
    rel = GOLDEN_PATH.relative_to(ENGINE_ROOT.parent)
    print(f"golden file written: {rel} ({len(golden)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
