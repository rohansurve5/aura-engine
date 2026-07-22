"""Cross-validate the Worker's full natal chart against Swiss Ephemeris — the gate.

Block 8 §2 (binding): no app-visible birth chart ships without a 1,001-birth
cross-validation identical in kind to the natal, dasha and ascendant gates. The
chart adds nine graha placements (sign + Whole Sign house + direction) and the
mean lunar node to the ascendant already gated by crossval_ascendant.py, so
this script covers EVERY quantity the three chart screens will display:

  * ascendant sidereal longitude (≤ 1′) and sign,
  * each graha's sidereal longitude (≤ 1′), sign and Whole Sign house,
  * retrogradity (the FD sign vs Swiss' analytic speed), and
  * the 12 Whole Sign house cusps (house → sign).

aura-api computes the chart in-Worker (src/chart.ts on the astronomy-engine
stack src/natal.ts / src/planets.ts / src/ascendant.ts already prove); this
script resolves the same 1,001 births with BOTH

  (a) this engine (swe compute_chart, lahiri_vp285 — the source of truth), and
  (b) the exact TypeScript the Worker runs (via aura-api/scripts/chart-batch.ts
      — no reimplementation),

and requires longitude within 1 arc-min on the ascendant and every graha, plus
sign, house and retrogradity agreement on every non-contested birth. TWO kinds
of contested case are recorded rather than adjudicated, each with its own
honesty flag in the /v1/chart payload:

  * SIGN INGRESS — a body both sides place within 1′ of the SAME sign ingress
    (1′ ≈ 4 s of birth time for the ascendant). The sign is genuinely contested
    there; flagged `sign_boundary`, asserted as still-near-an-ingress by the
    vitest gate. This is the ascendant boundary policy extended to all bodies.
  * STATION — a body both sides find within STATION_EPS (0.02°/day) of zero
    apparent speed is stationing; its direct/retrograde bit is genuinely
    ambiguous within hours of the turn. Flagged `station_boundary`, asserted as
    still-near-a-station (`near_station`) rather than by the bit. To guarantee
    the station machinery is actually exercised (random births almost never
    land inside 0.02°/day of a station), the case set is SEEDED with a genuine
    near-station birth for each of the slow movers, found by scanning the
    engine's own speed for a sign change and bisecting to the turn.

Births: seeded, 1930-2025, population-weighted over the 20 largest Indian
cities plus a world panel that exercises high latitude (Tromsø 69.6°N,
Anchorage 61.2°N — Whole Sign is defined where Placidus is not), the southern
hemisphere (Wellington, Sydney), a +05:45 zone (Kathmandu), and the 1943
war-time-DST Kolkata birth — all resolved through IANA zones AT the birth
instant.

On success it (re)writes aura-api/test/golden/chart_crossval.json so the same
expectations gate `npm test` in aura-api CI on every deploy.

Run:  uv run python scripts/crossval_chart.py
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

from engine.chart import compute_chart
from engine.positions import BODIES, sidereal_positions
from engine.timezones import local_to_utc

ENGINE_ROOT = Path(__file__).resolve().parent.parent
AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "chart_crossval.json"

SEED = 285
# 945 India + 50 world + 5 seeded stations + 1 war-time Kolkata = 1001, the
# gate size the natal/dasha/ascendant crossvals all hold to.
N_INDIA = 945
START = datetime(1930, 1, 1, 0, 0)
END = datetime(2025, 12, 31, 23, 59)
ARC_MIN_DEG = 1.0 / 60.0
# Must equal STATION_EPS in aura-api/src/chart.ts — the ambiguous-direction band.
STATION_EPS = 0.02

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

# Diaspora / stress panel: high latitude (Anchorage 61.2°N — below the arctic
# circle, where the closed-form ascendant still agrees with Swiss to arcsec),
# southern hemisphere, DST-observing zones, a +05:45 fractional offset.
#
# THE ARCTIC-CIRCLE BOUNDARY (measured, docs/CHART.md): the port and Swiss
# agree to ≤ 15″ everywhere up to 66.5°, then diverge sharply — 67°N picks the
# descending root ~180° away, because above the polar circle the ecliptic goes
# circumpolar and the ascending horizon intersection is no longer uniquely
# defined. That is the SAME latitude at which engine/chart.py already publishes
# `placidus_cusps = None` (_PLACIDUS_LAT_LIMIT = 66.0): both the reliable
# ascendant and Placidus fail for the one physical reason. So /v1/chart is
# defined for |lat| < 66.0 and refuses above it (chart null, explicit reason —
# never a wrong lagna), and this gate only feeds births it would actually
# serve. Tromsø (69.6°N) is therefore the REFUSED example, not a golden case.
WORLD_CITIES = [
    ("London", 51.5074, -0.1278, "Europe/London"),
    ("New York", 40.7128, -74.0060, "America/New_York"),
    ("Singapore", 1.3521, 103.8198, "Asia/Singapore"),
    ("Dubai", 25.2048, 55.2708, "Asia/Dubai"),
    ("Sydney", -33.8688, 151.2093, "Australia/Sydney"),
    ("Toronto", 43.6532, -79.3832, "America/Toronto"),
    ("Kathmandu", 27.7172, 85.3240, "Asia/Kathmandu"),
    ("Wellington", -41.2866, 174.7756, "Pacific/Auckland"),
    ("Anchorage", 61.2181, -149.9003, "America/Anchorage"),
]
KNOWN_CASE = {
    "dob": "1943-06-15", "time": "06:30", "zone": "Asia/Kolkata",
    "lat": 22.5626, "lon": 88.3630,
}

# Slow movers whose stations are astrologically notable and whose near-station
# window is wide enough to seed reliably; the Moon and nodes never station.
STATION_BODIES = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
STATION_START = datetime(2000, 1, 3, 0, 0)  # scan forward from here per body


def _speed(body: str, when_utc: datetime) -> float:
    return sidereal_positions(when_utc)[body].speed


def find_station_case(body: str, start: datetime) -> dict:
    """A birth within STATION_EPS of `body`'s next station after `start`.

    Scans day by day for a sign change in the engine's own sidereal speed, then
    bisects on time to the turn — where |speed| ≈ 0, i.e. deep inside the
    ambiguous band. Placed at Delhi, expressed as Asia/Kolkata wall-clock.
    """
    step = timedelta(days=1)
    lo = start
    s_lo = _speed(body, lo)
    hi = lo + step
    while True:
        s_hi = _speed(body, hi)
        if (s_lo < 0) != (s_hi < 0):
            break
        lo, s_lo, hi = hi, s_hi, hi + step
    # Bisect the sign change to the instant of zero speed.
    for _ in range(48):
        mid = lo + (hi - lo) / 2
        s_mid = _speed(body, mid)
        if (s_lo < 0) != (s_mid < 0):
            hi = mid
        else:
            lo, s_lo = mid, s_mid
    turn_utc = lo + (hi - lo) / 2
    local = turn_utc + timedelta(hours=5, minutes=30)  # Asia/Kolkata wall clock
    delhi = INDIA_CITIES[1]
    return {
        "dob": local.strftime("%Y-%m-%d"), "time": local.strftime("%H:%M"),
        "zone": "Asia/Kolkata", "lat": delhi[1], "lon": delhi[2],
        "_station_body": body,
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
    for i in range(50):
        when = START + timedelta(minutes=rng.randrange(span_minutes + 1))
        city = WORLD_CITIES[i % len(WORLD_CITIES)]
        cases.append({
            "dob": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"),
            "zone": city[3], "lat": city[1], "lon": city[2],
        })
    # Seeded genuine near-station births — one per slow mover — so the station
    # policy is exercised rather than merely coded.
    offset = timedelta(0)
    for body in STATION_BODIES:
        cases.append(find_station_case(body, STATION_START + offset))
        offset += timedelta(days=400)
    cases.append(KNOWN_CASE)
    return cases


def sign_index(longitude: float) -> int:
    return int(longitude // 30)


def engine_chart(case: dict) -> dict:
    birth = datetime.strptime(f"{case['dob']} {case['time']}", "%Y-%m-%d %H:%M")
    chart = compute_chart(local_to_utc(birth, case["zone"]), case["lat"], case["lon"])
    placements = {}
    for name in BODIES:
        p = chart.placements[name]
        placements[name] = {
            "longitude": p.position.longitude,
            "sign_index": sign_index(p.position.longitude),
            "sign": p.position.sign,
            "house": p.house,
            "retrograde": p.position.retrograde,
            "speed": p.position.speed,
        }
    return {
        "ascendant": {
            "longitude": chart.ascendant.longitude,
            "sign_index": chart.ascendant.sign_index,
            "sign": chart.ascendant.sign,
        },
        "house_signs": list(chart.house_signs),
        "placements": placements,
    }


def worker_chart(cases: list[dict]) -> list[dict]:
    payload = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases]
    proc = subprocess.run(
        ["node", "scripts/chart-batch.ts"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=AURA_API,
        check=True,
    )
    return json.loads(proc.stdout)


def boundary_distance(lon: float) -> float:
    """Degrees to the nearest sign ingress."""
    return min(lon % 30, 30 - lon % 30)


def main() -> int:
    cases = generate_cases()
    print(f"cross-validating {len(cases)} charts (seed={SEED}, 1930-2025, "
          f"20 Indian cities + {len(WORLD_CITIES)} world cities + "
          f"{len(STATION_BODIES)} seeded stations) ...")

    expected = [engine_chart(c) for c in cases]
    actual = worker_chart(cases)

    mismatches: list[str] = []
    max_delta_asec = 0.0
    golden: list[dict] = []

    for case, exp, act in zip(cases, expected, actual, strict=True):
        tag = f"{case['dob']} {case['time']} {case.get('zone', case.get('tz'))}"
        sign_boundary_bodies: list[str] = []
        station_boundary_bodies: list[str] = []

        # Ascendant.
        d_asc = abs((act["ascendant"]["longitude"] - exp["ascendant"]["longitude"]
                     + 180) % 360 - 180)
        max_delta_asec = max(max_delta_asec, d_asc * 3600)
        asc_boundary = False
        if d_asc >= ARC_MIN_DEG:
            mismatches.append(f"{tag}: asc Δ {d_asc * 3600:.1f}\"")
        elif act["ascendant"]["sign_index"] != exp["ascendant"]["sign_index"]:
            if (boundary_distance(exp["ascendant"]["longitude"]) < ARC_MIN_DEG
                    and boundary_distance(act["ascendant"]["longitude"]) < ARC_MIN_DEG):
                asc_boundary = True
            else:
                mismatches.append(f"{tag}: asc sign {exp['ascendant']['sign']} vs "
                                  f"{act['ascendant']['sign']}")

        # House cusps (Whole Sign) — a deterministic rotation of the asc sign,
        # asserted exact because an off-by-one in the rotation is a silent
        # every-house-wrong screen bug.
        if act["house_signs"] != exp["house_signs"]:
            if not asc_boundary:  # a boundary asc legitimately rotates the ring
                mismatches.append(f"{tag}: house_signs differ")

        # Each graha.
        for name in BODIES:
            e = exp["placements"][name]
            a = act["placements"][name]
            d = abs((a["longitude"] - e["longitude"] + 180) % 360 - 180)
            max_delta_asec = max(max_delta_asec, d * 3600)
            if d >= ARC_MIN_DEG:
                mismatches.append(f"{tag}: {name} Δ {d * 3600:.1f}\"")
                continue
            # Sign (and therefore house) — contested only at an ingress.
            if a["sign_index"] != e["sign_index"]:
                if (boundary_distance(e["longitude"]) < ARC_MIN_DEG
                        and boundary_distance(a["longitude"]) < ARC_MIN_DEG):
                    sign_boundary_bodies.append(name)
                else:
                    mismatches.append(
                        f"{tag}: {name} sign {e['sign']} vs {a['sign']}")
            elif not asc_boundary and a["house"] != e["house"]:
                # A contested asc sign rotates the ENTIRE Whole Sign ring by one
                # house; that is the asc_boundary case, not nine house bugs.
                mismatches.append(
                    f"{tag}: {name} house {e['house']} vs {a['house']}")
            # Direction — contested only within STATION_EPS of a station.
            if a["retrograde"] != e["retrograde"]:
                if abs(e["speed"]) < STATION_EPS and abs(a["speed"]) < STATION_EPS:
                    station_boundary_bodies.append(name)
                else:
                    mismatches.append(
                        f"{tag}: {name} direction {'R' if e['retrograde'] else 'D'} "
                        f"vs {'R' if a['retrograde'] else 'D'} "
                        f"(engine {e['speed']:+.4f}°/d, worker {a['speed']:+.4f}°/d)")

        golden.append({
            **{k: v for k, v in case.items() if not k.startswith("_")},
            "asc_boundary": asc_boundary,
            "sign_boundary_bodies": sign_boundary_bodies,
            "station_boundary_bodies": station_boundary_bodies,
            "expected": exp,
        })

    n = len(cases)
    n_sign_b = sum(1 for g in golden if g["sign_boundary_bodies"] or g["asc_boundary"])
    n_stat_b = sum(1 for g in golden if g["station_boundary_bodies"])
    n_near_stat = sum(
        1 for act in actual for p in act["placements"].values()
        if abs(p["speed"]) < STATION_EPS
    )
    print(f"agree: {n - len(mismatches)}/{n} charts clean "
          f"({n_sign_b} with a contested sign ingress, "
          f"{n_stat_b} with a contested station)")
    print(f'max longitude delta (asc + 9 grahas): {max_delta_asec:.2f}" '
          f"({max_delta_asec / 60:.4f} arc-min)")
    print(f"near-station placements exercised: {n_near_stat}")

    if mismatches:
        print(f"\nFAILURES ({len(mismatches)}):")
        for m in mismatches[:30]:
            print(f"  {m}")
        return 1

    GOLDEN_PATH.write_text(json.dumps(golden, indent=1) + "\n")
    print(f"wrote {GOLDEN_PATH.relative_to(AURA_API.parent)} ({len(golden)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
