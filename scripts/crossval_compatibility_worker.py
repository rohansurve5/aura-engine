"""Cross-validate the Worker's Ashtakoota + Mangal port against this engine — deploy gate.

The binding condition in docs/COMPATIBILITY.md §2: if compatibility becomes
app-visible via the Worker, it must ship a TS port with a golden-parity gate
identical in kind to natal/dasha. This script is that gate, in three layers:

  1. SINGLE SOURCE OF TRUTH FOR THE TABLES. The classical tables live ONCE, in
     `engine/compatibility.py` (pinned there by tests/test_compatibility.py).
     This script machine-generates `aura-api/src/compatibilityTables.gen.ts`
     from the live Python module — the Worker never retypes a table, so engine
     and Worker cannot diverge by transcription. A hand edit to the generated
     file is caught by layer 2.

  2. EXHAUSTIVE FUNCTIONAL PARITY. Every koota is a finite table lookup, so
     unlike an ephemeris the whole input domain is enumerable: all 108×108
     (nakshatra, pada)-midpoint couples = 11,664 pairs, which exercises EVERY
     cell of every koota table, every parihar branch and both directions of
     every asymmetry. The Worker's real code (scripts/compatibility-batch.ts —
     no reimplementation) must agree deep-equal on all of them. The 14 curated
     couples from crossval_compatibility.py are additionally replayed with the
     FULL breakdown — details, parihar reasons and the composed voice lines —
     byte-equal.

  3. MANGAL BIRTHS. Mangal Dosha needs Mars/Venus/Moon signs and the lagna —
     real ephemeris quantities. Seeded births (same convention as
     crossval_ascendant.py) are resolved by BOTH engine `compute_chart` (Swiss
     Ephemeris, the source of truth) and the Worker (astronomy-engine), and
     must agree on every longitude within 1 arc-minute and on every sign,
     house and dosha flag — except births flagged as BOUNDARY cases, where a
     body sits within 1' of a sign ingress on both sides and the sign is
     genuinely contested at the stated birth-time precision (the
     crossval_ascendant.py policy, extended to Mars/Venus/Moon).

The ETHICS GATES cross the port through layer 1 + the golden: the falsification
batteries (tests/test_compatibility_gates_falsify.py) run against the engine's
DESCRIPTORS corpus at authoring time; this script exports that exact corpus to
the Worker and embeds it in the golden, and the vitest gate asserts the
Worker's served corpus is byte-equal to it. The Worker composes lines ONLY from
that corpus, so ungated copy cannot reach users without failing the deploy gate.

On success it (re)writes aura-api/test/golden/compatibility_crossval.json so the
same expectations gate `npm test` in aura-api CI and the `predeploy` hook.

Run:  uv run python scripts/crossval_compatibility_worker.py
Exit: non-zero on ANY disagreement (failing cases are printed; do not tune).
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

from engine import compatibility as compat  # noqa: E402
from engine.chart import compute_chart  # noqa: E402
from engine.compatibility import (  # noqa: E402
    CUSTOMARY_THRESHOLD,
    DESCRIPTORS,
    GANA_BY_NAK,
    NADI_BY_NAK,
    Person,
    SIGN_LORDS,
    VARNA_BY_SIGN,
    VASHYA_GROUP_BY_SIGN,
    YONI_BY_NAK,
    YONI_NAMES,
    bhakoot_parihar,
    describe_match,
    guna_milan,
    mangal_dosha,
    nadi_parihar,
)
from engine.timezones import local_to_utc  # noqa: E402
from engine.vimshottari import NAKSHATRA_ARC, NAKSHATRAS  # noqa: E402
from crossval_compatibility import COUPLES, person_at  # noqa: E402

ENGINE_ROOT = Path(__file__).resolve().parent.parent
AURA_API = ENGINE_ROOT.parent / "aura-api"
TABLES_PATH = AURA_API / "src" / "compatibilityTables.gen.ts"
GOLDEN_PATH = AURA_API / "test" / "golden" / "compatibility_crossval.json"

SEED = 285
N_MANGAL = 240
START = datetime(1930, 1, 1, 0, 0)
END = datetime(2025, 12, 31, 23, 59)
ARC_MIN_DEG = 1.0 / 60.0

# Same city panels as crossval_ascendant.py — the launch market plus the
# diaspora/stress zones, all resolved through IANA zones at the birth instant.
INDIA_CITIES = [
    ("Mumbai", 19.0760, 72.8777, 12.4), ("Delhi", 28.6139, 77.2090, 11.0),
    ("Bangalore", 12.9716, 77.5946, 8.4), ("Hyderabad", 17.3850, 78.4867, 6.8),
    ("Ahmedabad", 23.0225, 72.5714, 5.6), ("Chennai", 13.0878, 80.2785, 4.6),
    ("Kolkata", 22.5626, 88.3630, 4.5), ("Surat", 21.1702, 72.8311, 4.5),
    ("Pune", 18.5204, 73.8567, 3.1), ("Jaipur", 26.9124, 75.7873, 3.1),
]
INDIA_WEIGHTS = [c[3] for c in INDIA_CITIES]
WORLD_CITIES = [
    ("London", 51.5074, -0.1278, "Europe/London"),
    ("New York", 40.7128, -74.0060, "America/New_York"),
    ("Singapore", 1.3521, 103.8198, "Asia/Singapore"),
    ("Sydney", -33.8688, 151.2093, "Australia/Sydney"),
    ("Kathmandu", 27.7172, 85.3240, "Asia/Kathmandu"),
]
KNOWN_CASE = {
    "dob": "1943-06-15", "time": "06:30", "zone": "Asia/Kolkata",
    "lat": 22.5626, "lon": 88.3630,
}


# ── Layer 1: export the tables + corpus from the live Python module ──────────
def _pairs(fsets: frozenset) -> list[list[int]]:
    return sorted(sorted(p) for p in fsets)


def _intify(x):
    """JSON-normalise: floats that are whole numbers become ints, recursively,
    so 2.0 (Python float) and 2 (JS number) are the same JSON token."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, dict):
        return {k: _intify(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_intify(v) for v in x]
    return x


def export_tables() -> dict:
    tables = {
        "signLords": list(SIGN_LORDS),
        "varnaBySign": list(VARNA_BY_SIGN),
        "varnaRank": compat._VARNA_RANK,
        "vashyaGroupBySign": list(VASHYA_GROUP_BY_SIGN),
        "vashyaPoints": compat._VASHYA_POINTS,
        "taraBadRemainders": sorted(compat._TARA_BAD_REMAINDERS),
        "yoniByNak": list(YONI_BY_NAK),
        "yoniNames": list(YONI_NAMES),
        "yoniSwornEnemies": _pairs(compat._YONI_SWORN_ENEMIES),
        "yoniEnemies": _pairs(compat._YONI_ENEMIES),
        "yoniFriends": _pairs(compat._YONI_FRIENDS),
        "naisargika": {
            p: {"friends": sorted(f), "enemies": sorted(e)}
            for p, (f, e) in compat._NAISARGIKA.items()
        },
        "grahaMaitriPoints": {
            f"{a}|{b}": v for (a, b), v in compat._GRAHA_MAITRI_POINTS.items()
        },
        "ganaByNak": list(GANA_BY_NAK),
        "ganaPoints": compat._GANA_POINTS,
        "bhakootDoshaCounts": [list(c) for c in sorted(compat._BHAKOOT_DOSHA_COUNTS)],
        "nadiByNak": list(NADI_BY_NAK),
        "customaryThreshold": CUSTOMARY_THRESHOLD,
        "bandHigh": 28,  # _band(): >= 28 high, < threshold low, else mid
        "mangalHousesStrict": sorted(compat._MANGAL_HOUSES_STRICT),
        "mangalHousesInclusive": sorted(compat._MANGAL_HOUSES_INCLUSIVE),
        "nakshatras": list(NAKSHATRAS),
        "descriptors": DESCRIPTORS,
    }
    return _intify(tables)


def write_tables(tables: dict) -> None:
    body = json.dumps(tables, indent=2, ensure_ascii=False)
    TABLES_PATH.write_text(
        "// GENERATED by aura-engine/scripts/crossval_compatibility_worker.py — DO NOT EDIT.\n"
        "//\n"
        "// Single source of truth: aura-engine/engine/compatibility.py. Every koota\n"
        "// table, threshold and voice line here is machine-exported from the live\n"
        "// Python module whose encodings are pinned by tests/test_compatibility.py and\n"
        "// whose voice corpus is gated by tests/test_compatibility_gates_falsify.py.\n"
        "// A hand edit here diverges from the engine and fails the exhaustive\n"
        "// 11,664-couple crossval in test/compatibility.crossval.test.ts.\n"
        "// Regenerate:  uv run python scripts/crossval_compatibility_worker.py\n"
        f"export const COMPAT = {body};\n"
    )


# ── Engine-side breakdowns ──────────────────────────────────────────────────
def full_breakdown(groom: Person, bride: Person) -> dict:
    res = guna_milan(groom, bride)
    desc = describe_match(groom, bride)
    return _intify({
        "kootas": [
            {"name": k.name, "got": k.got, "max": k.maximum, "detail": k.detail,
             "is_dosha": k.is_dosha}
            for k in res.kootas
        ],
        "total": res.total,
        "nadi_parihar": nadi_parihar(groom, bride).__dict__,
        "bhakoot_parihar": bhakoot_parihar(groom, bride).__dict__,
        "lines": desc["lines"],
    })


def compact_row(gn: int, gp: int, bn: int, bp: int) -> list:
    groom, bride = person_at(gn, gp), person_at(bn, bp)
    res = guna_milan(groom, bride)
    return _intify([
        gn, gp, bn, bp,
        [k.got for k in res.kootas],
        res.total,
        [1 if k.is_dosha else 0 for k in res.kootas],
        1 if nadi_parihar(groom, bride).applies else 0,
        1 if bhakoot_parihar(groom, bride).applies else 0,
    ])


def generate_mangal_cases() -> list[dict]:
    rng = random.Random(SEED)
    span_minutes = int((END - START).total_seconds() // 60)
    cases = []
    for i in range(N_MANGAL - len(WORLD_CITIES) - 1):
        when = START + timedelta(minutes=rng.randrange(span_minutes + 1))
        city = rng.choices(INDIA_CITIES, weights=INDIA_WEIGHTS)[0]
        cases.append({
            "dob": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"),
            "zone": "Asia/Kolkata", "lat": city[1], "lon": city[2],
        })
    for i, city in enumerate(WORLD_CITIES):
        when = START + timedelta(minutes=rng.randrange(span_minutes + 1))
        cases.append({
            "dob": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"),
            "zone": city[3], "lat": city[1], "lon": city[2],
        })
    cases.append(KNOWN_CASE)
    return cases


def engine_mangal(case: dict) -> dict:
    birth = datetime.strptime(f"{case['dob']} {case['time']}", "%Y-%m-%d %H:%M")
    chart = compute_chart(local_to_utc(birth, case["zone"]), case["lat"], case["lon"])
    m = mangal_dosha(chart)
    lons = {
        "moon": chart.placements["Moon"].position.longitude,
        "mars": chart.placements["Mars"].position.longitude,
        "venus": chart.placements["Venus"].position.longitude,
        "asc": chart.ascendant.longitude,
    }
    return {
        "longitudes": lons,
        "signs": {k: int(v // 30) for k, v in lons.items()},
        "points": [
            {"reference": p.reference, "house": p.house,
             "strict": p.strict, "inclusive": p.inclusive}
            for p in m.points
        ],
        "flagged_strict": m.flagged_strict,
        "flagged_inclusive": m.flagged_inclusive,
    }


def boundary_distance(lon: float) -> float:
    return min(lon % 30, 30 - lon % 30)


def worker_batch(payload: dict) -> list:
    proc = subprocess.run(
        ["node", "scripts/compatibility-batch.ts"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=AURA_API,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    tables = export_tables()
    write_tables(tables)
    print(f"wrote {TABLES_PATH.relative_to(AURA_API.parent)}")

    # Layer 2a — the 14 curated couples, full breakdown incl. voice lines.
    couple_inputs = [
        {"g": [g[0], g[1]], "b": [b[0], b[1]]} for _, g, b, _ in COUPLES
    ]
    couples_expected = [
        {
            "label": label,
            "g": [g[0], g[1]], "b": [b[0], b[1]],
            "expected": full_breakdown(person_at(*g), person_at(*b)),
        }
        for label, g, b, _ in COUPLES
    ]

    # Layer 2b — the exhaustive (nakshatra, pada)-midpoint grid: every
    # (nak, pada) against every (nak, pada), 108×108 = 11,664 couples.
    grid = [
        compact_row(gn, gp, bn, bp)
        for gn in range(27) for gp in (1, 2, 3, 4)
        for bn in range(27) for bp in (1, 2, 3, 4)
    ]
    print(f"engine grid computed: {len(grid)} couples (exhaustive 108×108)")

    grid_inputs = [
        {"g": row[0] * NAKSHATRA_ARC + (row[1] - 0.5) * NAKSHATRA_ARC / 4,
         "b": row[2] * NAKSHATRA_ARC + (row[3] - 0.5) * NAKSHATRA_ARC / 4}
        for row in grid
    ]

    print("running the Worker's compatibility over the same inputs ...")
    act_couples = worker_batch({
        "mode": "couples",
        "cases": [
            {"g": person_at(*c["g"]).moon_longitude, "b": person_at(*c["b"]).moon_longitude}
            for c in couple_inputs
        ],
    })
    act_grid = worker_batch({"mode": "grid", "cases": grid_inputs})

    problems: list[str] = []
    for exp, act in zip(couples_expected, act_couples, strict=True):
        if _intify(act) != exp["expected"]:
            problems.append(f"couple {exp['label']!r}: worker breakdown differs\n"
                            f"  engine: {json.dumps(exp['expected'])}\n"
                            f"  worker: {json.dumps(_intify(act))}")

    for row, act in zip(grid, act_grid, strict=True):
        if _intify(act) != row[4:]:
            problems.append(
                f"grid ({row[0]},{row[1]})x({row[2]},{row[3]}): "
                f"engine {row[4:]} vs worker {_intify(act)}")
            if len(problems) > 20:
                break

    # Layer 3 — Mangal births, engine chart vs Worker astronomy-engine.
    mangal_cases = generate_mangal_cases()
    print(f"cross-validating Mangal over {len(mangal_cases)} births ...")
    mangal_expected = [engine_mangal(c) for c in mangal_cases]
    mangal_actual = worker_batch({"mode": "mangal", "cases": mangal_cases})

    max_delta_asec = 0.0
    n_boundary = 0
    mangal_golden = []
    for case, exp, act in zip(mangal_cases, mangal_expected, mangal_actual, strict=True):
        tag = f"{case['dob']} {case['time']} {case['zone']}"
        deltas = {
            k: abs((act["longitudes"][k] - exp["longitudes"][k] + 180) % 360 - 180)
            for k in ("moon", "mars", "venus", "asc")
        }
        max_delta_asec = max(max_delta_asec, max(deltas.values()) * 3600)
        over = {k: d for k, d in deltas.items() if d >= ARC_MIN_DEG}
        if over:
            problems.append(f"mangal {tag}: longitude delta over 1' — "
                            + ", ".join(f"{k} {d * 3600:.1f}\"" for k, d in over.items()))
            continue
        boundary_bodies = sorted(
            k for k in deltas
            if boundary_distance(exp["longitudes"][k]) < ARC_MIN_DEG
            and boundary_distance(act["longitudes"][k]) < ARC_MIN_DEG
        )
        if boundary_bodies:
            n_boundary += 1
        else:
            if act["signs"] != exp["signs"]:
                problems.append(f"mangal {tag}: signs {act['signs']} != {exp['signs']}")
            elif (act["points"] != exp["points"]
                  or act["flagged_strict"] != exp["flagged_strict"]
                  or act["flagged_inclusive"] != exp["flagged_inclusive"]):
                problems.append(f"mangal {tag}: dosha facts differ\n"
                                f"  engine: {json.dumps(exp['points'])}\n"
                                f"  worker: {json.dumps(act['points'])}")
        mangal_golden.append({
            **case,
            "boundary_bodies": boundary_bodies,
            "expected": _intify(exp),
        })

    print(f"max longitude delta: {max_delta_asec:.2f}\" "
          f"({max_delta_asec / 60:.4f} arc-min); "
          f"boundary births: {n_boundary}/{len(mangal_cases)}")

    if problems:
        print(f"\nFAILED — {len(problems)} disagreement(s):", file=sys.stderr)
        for p in problems[:25]:
            print(f"  {p}", file=sys.stderr)
        return 1

    golden = {
        "tolerance_arcmin": 1,
        "descriptors": DESCRIPTORS,  # the gated corpus, byte-pinned for vitest
        "threshold": CUSTOMARY_THRESHOLD,
        "couples": couples_expected,
        # grid rows: [g_nak, g_pada, b_nak, b_pada, [8 gots], total,
        #             [8 is_dosha], nadi_parihar_applies, bhakoot_parihar_applies]
        "grid": grid,
        "mangal": mangal_golden,
    }
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(golden, indent=None, separators=(",", ":")) + "\n")
    print(f"OK — wrote {GOLDEN_PATH.relative_to(AURA_API.parent)} "
          f"({len(grid)} grid + {len(couples_expected)} couples + "
          f"{len(mangal_golden)} mangal births)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
