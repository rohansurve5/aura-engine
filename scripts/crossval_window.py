"""Cross-validate the Worker's choghadiya window against Swiss Ephemeris — deploy gate.

aura-api serves GET /v1/window, computing sunrise/sunset in-Worker with
astronomy-engine (MIT) and splitting the day with a TypeScript port of
engine/choghadiya.py. This script is the accuracy contract for both halves: it
generates a seeded-random set of (place, date) cases and resolves each with BOTH

  (a) this engine — swe.rise_trans for rise/set (the source of truth) plus
      engine/choghadiya.py itself for the slots, and
  (b) the exact TypeScript the Worker runs (aura-api/src/window.ts, executed by
      node via aura-api/scripts/window-batch.ts — no reimplementation),

and requires agreement on every slot NAME exactly, and every rise/set and slot
BOUNDARY within a tolerance.

WHY A TOLERANCE AND NOT EQUALITY. Unlike natal (where both sides agree on a
longitude to well under an arc-minute) rise/set is a *model* difference, not a
precision one. Swiss Ephemeris with bare CALC_RISE uses upper-limb + refraction
at 1013.25 mbar / 0 °C; astronomy-engine applies its own standard refraction and
body-radius correction. Measured spread on the case set is ~12 s at Indian
latitudes, rising with latitude (~45 s at Reykjavik) as the Sun's path flattens.
TOLERANCE_S is set well inside the ±2 min the engine's own choghadiya tests hold
against DrikPanchang, so a real regression cannot hide underneath it.

PLACES span the launch market and the edges that break naive implementations:
southern hemisphere, a half-hour zone, a DST zone, a negative-longitude zone,
the antimeridian, and a near-polar city. Polar cases where the Sun genuinely
does not rise are asserted to fail on BOTH sides rather than being skipped.

On success it (re)writes aura-api/test/golden/window_crossval.json so the same
expectations are enforced by `npm test` in aura-api CI and by the `predeploy`
hook on every deploy, without needing Python there.

Run:  uv run python scripts/crossval_window.py
Exit: non-zero on ANY disagreement (failing cases are printed; do not tune).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

from engine.choghadiya import (
    day_choghadiya,
    gulika_kaal,
    night_choghadiya,
    rahu_kaal,
    yamaganda_kaal,
)

ENGINE_ROOT = Path(__file__).resolve().parent.parent
AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "window_crossval.json"

SEED = 285  # same seed convention as crossval_natal.py
N_DATES = 12  # per place; 12 × 14 places = 168 cases
TOLERANCE_S = 90  # see the module docstring — a model gap, not a precision one

# (name, lat, lon, IANA zone). Deliberately not all-India.
PLACES = [
    ("Pune", 18.5204, 73.8567, "Asia/Kolkata"),
    ("Delhi", 28.6139, 77.2090, "Asia/Kolkata"),
    ("Chennai", 13.0827, 80.2707, "Asia/Kolkata"),
    ("Kolkata", 22.5726, 88.3639, "Asia/Kolkata"),
    ("Mumbai", 19.0760, 72.8777, "Asia/Kolkata"),
    ("Guwahati", 26.1445, 91.7362, "Asia/Kolkata"),
    ("London", 51.5074, -0.1278, "Europe/London"),  # DST
    ("New York", 40.7128, -74.0060, "America/New_York"),  # DST, negative lon
    ("Sydney", -33.8688, 151.2093, "Australia/Sydney"),  # southern hemisphere
    ("Kathmandu", 27.7172, 85.3240, "Asia/Kathmandu"),  # +05:45 quarter-hour
    ("Adelaide", -34.9285, 138.6007, "Australia/Adelaide"),  # +09:30 half-hour
    ("Auckland", -36.8485, 174.7633, "Pacific/Auckland"),  # near antimeridian
    ("Dubai", 25.2048, 55.2708, "Asia/Dubai"),
    ("Reykjavik", 64.1466, -21.9426, "Atlantic/Reykjavik"),  # near-polar
]

# Where the Sun genuinely does not rise or set on the given date. Both sides must
# refuse; a side that invents a window here is a failure, not a pass.
POLAR_CASES = [
    ("Longyearbyen midsummer", 78.2232, 15.6267, "Arctic/Longyearbyen", "2026-06-21"),
    ("Longyearbyen midwinter", 78.2232, 15.6267, "Arctic/Longyearbyen", "2026-12-21"),
]

START = datetime(2026, 1, 1)
END = datetime(2026, 12, 31)


def generate_cases() -> list[dict]:
    rng = random.Random(SEED)
    span_days = (END - START).days
    cases = []
    for name, lat, lon, zone in PLACES:
        for _ in range(N_DATES):
            day = START + timedelta(days=rng.randrange(span_days + 1))
            cases.append(
                {
                    "place": name,
                    # Rounded to 1dp: the route rounds internally and the client
                    # rounds in the URL, so the gate must validate the SAME
                    # coordinates the Worker will actually be asked about.
                    "lat": round(lat, 1),
                    "lon": round(lon, 1),
                    "zone": zone,
                    "date": day.strftime("%Y-%m-%d"),
                }
            )
    return cases


def _rise_set(jd_start: float, lat: float, lon: float, *, rise: bool) -> float:
    """Next sunrise/sunset (JD UT) after jd_start — identical call to panchang.py."""
    flag = swe.CALC_RISE if rise else swe.CALC_SET
    res, times = swe.rise_trans(jd_start, swe.SUN, flag, (lon, lat, 0.0))
    if res != 0:
        raise ValueError("no rise/set")
    return times[0]


def _jd_to_utc(jd: float) -> datetime:
    y, m, d, hours = swe.revjul(jd)
    return datetime(y, m, d) + timedelta(hours=hours)


def engine_window(case: dict) -> dict | None:
    """Sunrise/sunset from Swiss Ephemeris, slots from engine/choghadiya.py."""
    tz = ZoneInfo(case["zone"])
    lat, lon = case["lat"], case["lon"]

    # Local midnight at the place, as a UTC julian day — the same search origin
    # the Worker uses, so "the sunrise on date D" means the same event.
    local_midnight = datetime.strptime(case["date"], "%Y-%m-%d").replace(tzinfo=tz)
    utc_mid = local_midnight.astimezone(ZoneInfo("UTC"))
    jd_mid = swe.julday(
        utc_mid.year, utc_mid.month, utc_mid.day, utc_mid.hour + utc_mid.minute / 60
    )

    try:
        jd_rise = _rise_set(jd_mid, lat, lon, rise=True)
        jd_set = _rise_set(jd_rise, lat, lon, rise=False)
        jd_next = _rise_set(jd_set, lat, lon, rise=True)
    except ValueError:
        return None

    def utc(jd: float) -> datetime:
        return _jd_to_utc(jd).replace(tzinfo=ZoneInfo("UTC"))

    rise_u, set_u, next_u = utc(jd_rise), utc(jd_set), utc(jd_next)

    # FIXED-OFFSET LOCAL TIME, and the reason matters.
    #
    # choghadiya.py keys its weekday off `.date()`, so it must be fed LOCAL
    # datetimes. But it also does `start + step * i`, and on a zone-AWARE
    # datetime Python defines that as WALL-CLOCK arithmetic — so across a DST
    # transition it would divide the night into 8 equal wall-clock parts and
    # silently swallow the repeated (or skipped) hour. A choghadiya is 1/8 of
    # the real elapsed night, so that is wrong; it just never surfaces in the
    # engine because every precomputed row is IST, which has no DST.
    #
    # Feeding NAIVE datetimes offset by a single reference offset per half
    # gives both properties at once: the civil date (hence weekday) is the
    # local one, and subtraction/addition stay exact absolute durations. The
    # reference is the offset at the start of each half — sunrise for the day,
    # sunset for the night — so a transition inside the half is carried by the
    # span rather than distorting the slot widths.
    # Auckland 2026-04-04 (NZ DST ends overnight) is the case that proves it.
    def naive_at(instant: datetime, ref: datetime) -> datetime:
        off = ref.astimezone(tz).utcoffset()
        return (instant + off).replace(tzinfo=None)

    rise = naive_at(rise_u, rise_u)
    sset_day = naive_at(set_u, rise_u)
    sset_night = naive_at(set_u, set_u)
    nxt = naive_at(next_u, set_u)

    day = day_choghadiya(rise, sset_day)
    night = night_choghadiya(sset_night, nxt)

    # Timestamps must come from the true UTC instants, not the shifted naives.
    day_starts = [rise_u.timestamp() + (w.start - rise).total_seconds() for w in day]
    night_starts = [set_u.timestamp() + (w.start - sset_night).total_seconds() for w in night]
    kaal_windows = (
        ("rahu", rahu_kaal(rise, sset_day)),
        ("gulika", gulika_kaal(rise, sset_day)),
        ("yamaganda", yamaganda_kaal(rise, sset_day)),
    )
    return {
        "sunrise_ts": rise_u.timestamp(),
        "sunset_ts": set_u.timestamp(),
        "next_sunrise_ts": next_u.timestamp(),
        "day": [{"name": w.name, "start_ts": ts} for w, ts in zip(day, day_starts, strict=True)],
        "night": [
            {"name": w.name, "start_ts": ts} for w, ts in zip(night, night_starts, strict=True)
        ],
        "kaals": {
            k: {
                "name": w.name,
                "start_ts": rise_u.timestamp() + (w.start - rise).total_seconds(),
            }
            for k, w in kaal_windows
        },
    }


def worker_window(cases: list[dict]) -> list[dict]:
    payload = [
        {"lat": c["lat"], "lon": c["lon"], "zone": c["zone"], "date": c["date"]} for c in cases
    ]
    proc = subprocess.run(
        ["node", "scripts/window-batch.ts"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=AURA_API,
        check=True,
    )
    return json.loads(proc.stdout)


def compare(case: dict, exp: dict, act: dict) -> list[str]:
    """Every disagreement for one case, as human-readable lines."""
    problems: list[str] = []
    tag = f"{case['place']} {case['date']}"

    if "error" in act:
        return [f"{tag}: worker refused ({act['error']}) but engine computed a window"]

    for key in ("sunrise", "sunset", "next_sunrise"):
        delta = abs(act[f"{key}_ms"] / 1000 - exp[f"{key}_ts"]) if f"{key}_ms" in act else None
        if delta is None:
            problems.append(f"{tag}: worker payload missing {key}_ms")
        elif delta > TOLERANCE_S:
            problems.append(f"{tag}: {key} differs by {delta:.1f}s (> {TOLERANCE_S}s)")

    for half in ("day", "night"):
        if len(act[half]) != 8:
            problems.append(f"{tag}: {half} has {len(act[half])} slots, expected 8")
            continue
        for i, (e, a) in enumerate(zip(exp[half], act[half], strict=True)):
            if e["name"] != a["name"]:
                problems.append(f"{tag}: {half}[{i}] name {a['name']!r} != {e['name']!r}")
            d = abs(a["start_ms"] / 1000 - e["start_ts"])
            if d > TOLERANCE_S:
                problems.append(f"{tag}: {half}[{i}] start differs by {d:.1f}s")

    for k in ("rahu", "gulika", "yamaganda"):
        e, a = exp["kaals"][k], act["kaals"][k]
        if e["name"] != a["name"]:
            problems.append(f"{tag}: kaal {k} name {a['name']!r} != {e['name']!r}")
        d = abs(a["start_ms"] / 1000 - e["start_ts"])
        if d > TOLERANCE_S:
            problems.append(f"{tag}: kaal {k} start differs by {d:.1f}s")

    return problems


def main() -> int:
    swe.set_ephe_path(str(ENGINE_ROOT / "ephe"))
    cases = generate_cases()
    print(f"cross-validating {len(cases)} (place, date) windows (seed={SEED}, 2026) ...")

    expected = [engine_window(c) for c in cases]
    actual = worker_window(cases)

    problems: list[str] = []
    max_delta = 0.0
    for case, exp, act in zip(cases, expected, actual, strict=True):
        if exp is None:
            # Engine says no rise/set; the Worker must agree and refuse.
            if "error" not in act:
                problems.append(f"{case['place']} {case['date']}: engine found no rise, worker did")
            continue
        problems.extend(compare(case, exp, act))
        if "sunrise_ms" in act:
            max_delta = max(max_delta, abs(act["sunrise_ms"] / 1000 - exp["sunrise_ts"]))

    # Polar refusal must be symmetric: both sides decline to invent a window.
    polar_payload = [
        {"lat": round(lat, 1), "lon": round(lon, 1), "zone": zone, "date": date}
        for _, lat, lon, zone, date in POLAR_CASES
    ]
    polar_actual = worker_window(
        [{**p, "place": n} for p, (n, *_) in zip(polar_payload, POLAR_CASES, strict=True)]
    )
    for (name, lat, lon, zone, date), act in zip(POLAR_CASES, polar_actual, strict=True):
        eng = engine_window({"lat": round(lat, 1), "lon": round(lon, 1), "zone": zone, "date": date})
        if eng is not None:
            problems.append(f"{name}: engine unexpectedly found a rise/set")
        if "error" not in act:
            problems.append(f"{name}: worker returned a window where the Sun does not rise/set")

    print(f"max sunrise delta: {max_delta:.1f}s (tolerance {TOLERANCE_S}s)")

    if problems:
        print(f"\nFAILED — {len(problems)} disagreement(s):", file=sys.stderr)
        for p in problems[:40]:
            print(f"  {p}", file=sys.stderr)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more", file=sys.stderr)
        return 1

    # Golden = the ENGINE's expectations, so the vitest replay in aura-api is
    # checking the Worker against Swiss Ephemeris, not against its own output.
    golden = {
        "tolerance_s": TOLERANCE_S,
        "cases": [
            {
                "place": c["place"],
                "lat": c["lat"],
                "lon": c["lon"],
                "zone": c["zone"],
                "date": c["date"],
                "expected": {
                    "sunrise_ts": round(e["sunrise_ts"], 3),
                    "sunset_ts": round(e["sunset_ts"], 3),
                    "next_sunrise_ts": round(e["next_sunrise_ts"], 3),
                    "day": [
                        {"name": w["name"], "start_ts": round(w["start_ts"], 3)} for w in e["day"]
                    ],
                    "night": [
                        {"name": w["name"], "start_ts": round(w["start_ts"], 3)} for w in e["night"]
                    ],
                    "kaals": {
                        k: {"name": v["name"], "start_ts": round(v["start_ts"], 3)}
                        for k, v in e["kaals"].items()
                    },
                },
            }
            for c, e in zip(cases, expected, strict=True)
            if e is not None
        ],
        "polar": [
            {"place": n, "lat": round(lat, 1), "lon": round(lon, 1), "zone": z, "date": d}
            for n, lat, lon, z, d in POLAR_CASES
        ],
    }
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(golden, indent=1) + "\n")
    print(f"OK — {len(golden['cases'])} cases agree; wrote {GOLDEN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
