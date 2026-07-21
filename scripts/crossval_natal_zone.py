"""Cross-validate IANA zone handling: engine (zoneinfo) vs Worker (Intl).

The sibling script crossval_natal.py covers the FIXED-OFFSET contract — 1,001
births all tagged "+05:30", which means that literal offset at every date. Those
cases are frozen and are never regenerated.

This script covers the separate, additive IANA input class, where the offset is
resolved AT THE BIRTH INSTANT. Two independent tz databases must agree:

  (a) aura-engine — Python `zoneinfo` + Swiss Ephemeris (the source of truth);
  (b) aura-api    — `Intl.DateTimeFormat` in V8, via aura-api/src/natal.ts
                    executed verbatim through aura-api/scripts/natal-batch.ts.

Agreement is required on the resolved UTC offset, the nakshatra, the pada and
the Moon sign, with the Moon longitude inside 1 arc-minute.

The case list is hand-picked rather than random, because the whole point is to
hit specific historical transitions that random sampling would almost never
reach. Coverage, per the launch requirement:

  * Indian war-time DST  (+06:30, 1942-09-01 → 1945-10-15)
  * Indian normal        (+05:30, before and after the window)
  * A DST-observing foreign city in BOTH seasons
  * A historical NON-DST permanent offset change

On success it (re)writes aura-api/test/golden/natal_zone_crossval.json, which
aura-api's vitest suite enforces on every deploy.

Run:  uv run python scripts/crossval_natal_zone.py
Exit: non-zero on ANY disagreement (do not tune — investigate).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
# Running a script file puts scripts/ on sys.path, not the repo root, so the
# `engine` package is invisible unless we say where it is.
sys.path.insert(0, str(ENGINE_ROOT))

from engine.positions import sidereal_positions  # noqa: E402
from engine.timezones import local_to_utc, offset_minutes_at  # noqa: E402
from engine.vimshottari import nakshatra_of  # noqa: E402

AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "natal_zone_crossval.json"

ARC_MIN_DEG = 1.0 / 60.0

# (dob, time, zone, why this case is here)
CASES: list[tuple[str, str, str, str]] = [
    # ── Indian war-time DST: +06:30 ────────────────────────────────────────
    ("1942-09-02", "10:30", "Asia/Kolkata", "first full day of the war-time window"),
    ("1943-06-15", "10:30", "Asia/Kolkata", "mid-window, the canonical 1943 Calcutta birth"),
    ("1944-07-07", "17:56", "Asia/Kolkata", "war-time golden that crosses a nakshatra boundary"),
    ("1945-09-18", "06:05", "Asia/Kolkata", "war-time golden: Shravana -> Uttara Ashadha"),
    ("1945-01-18", "14:46", "Asia/Kolkata", "war-time golden that crosses a MOON SIGN boundary"),
    ("1945-10-14", "23:30", "Asia/Kolkata", "last day of the window"),
    ("1941-10-02", "08:00", "Asia/Kolkata", "the earlier 1941-42 window, often forgotten"),
    # ── Indian normal: +05:30, on both sides of the window ─────────────────
    ("1935-06-15", "10:30", "Asia/Kolkata", "pre-war, must equal the fixed-offset path"),
    ("1941-06-15", "10:30", "Asia/Kolkata", "between the two windows"),
    ("1945-10-16", "10:30", "Asia/Kolkata", "first day after the window"),
    ("1946-06-15", "10:30", "Asia/Kolkata", "post-war"),
    ("1989-09-23", "04:47", "Asia/Kolkata", "the known golden chart (Ardra pada 4)"),
    ("1990-06-15", "10:30", "Asia/Kolkata", "modern"),
    ("2025-03-09", "23:45", "Asia/Kolkata", "recent, near midnight"),
    # ── A DST-observing foreign city, BOTH seasons ─────────────────────────
    ("1975-06-15", "10:30", "Europe/London", "BST (+01:00) — summer"),
    ("1975-01-15", "10:30", "Europe/London", "GMT (00:00) — winter"),
    ("1943-06-15", "10:30", "Europe/London", "British DOUBLE Summer Time (+02:00), wartime"),
    ("2001-07-04", "09:15", "America/New_York", "EDT (-04:00) — summer"),
    ("2001-01-04", "09:15", "America/New_York", "EST (-05:00) — winter"),
    ("2010-12-25", "18:00", "Australia/Sydney", "southern hemisphere: DST in December"),
    # ── Historical NON-DST permanent offset changes ────────────────────────
    ("1981-06-15", "10:30", "Asia/Singapore", "+07:30, before the 1982 change"),
    ("1990-06-15", "10:30", "Asia/Singapore", "+08:00, after it — no DST involved"),
    ("1985-06-15", "10:30", "Asia/Kathmandu", "+05:45, a 45-minute offset"),
    ("1930-06-15", "10:30", "Asia/Kathmandu", "+05:41:16 — a pre-1986 non-integer offset"),
]


def engine_natal(dob: str, tm: str, zone: str) -> dict:
    naive = datetime.strptime(f"{dob} {tm}", "%Y-%m-%d %H:%M")
    utc = local_to_utc(naive, zone)
    positions = sidereal_positions(utc)
    moon, sun = positions["Moon"], positions["Sun"]
    nak = nakshatra_of(moon.longitude)
    return {
        "utc_offset_minutes": offset_minutes_at(zone, naive),
        "nakshatra_index": nak.index,
        "nakshatra": nak.name,
        "pada": nak.pada,
        "moon_sign": moon.sign,
        "sun_sign": sun.sign,
        "moon_longitude": moon.longitude,
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
    cases = [{"dob": d, "time": t, "zone": z} for d, t, z, _ in CASES]
    whys = [w for *_, w in CASES]
    print(f"cross-validating {len(cases)} IANA-zoned births (engine zoneinfo vs Worker Intl) ...")

    expected = [engine_natal(c["dob"], c["time"], c["zone"]) for c in cases]
    actual = worker_natal(cases)

    failures: list[str] = []
    max_delta_asec = 0.0
    for case, exp, act, why in zip(cases, expected, actual, whys, strict=True):
        tag = f"{case['dob']} {case['time']} {case['zone']} ({why})"
        if "error" in act:
            failures.append(f"{tag}: worker rejected the case: {act['error']}")
            continue
        delta = abs((act["moon_longitude"] - exp["moon_longitude"] + 180) % 360 - 180)
        max_delta_asec = max(max_delta_asec, delta * 3600)
        if act["utc_offset_minutes"] != exp["utc_offset_minutes"]:
            failures.append(
                f"{tag}: OFFSET disagreement — engine {exp['utc_offset_minutes']} "
                f"vs worker {act['utc_offset_minutes']} (tz database mismatch)"
            )
        for field in ("nakshatra_index", "nakshatra", "pada", "moon_sign"):
            if act[field] != exp[field]:
                failures.append(f"{tag}: {field} engine={exp[field]} worker={act[field]}")
        if delta > ARC_MIN_DEG:
            failures.append(f"{tag}: Moon longitude off by {delta * 60:.4f} arc-min")

    n = len(cases)
    print(f"agreement: {n - len({f.split(':')[0] for f in failures})}/{n}")
    print(f'max Moon-longitude delta: {max_delta_asec:.3f}" ({max_delta_asec / 60:.4f} arc-min)')

    if failures:
        print(f"\nFAIL — {len(failures)} disagreement(s); DO NOT TUNE, investigate:")
        for f in failures:
            print(f"  {f}")
        return 1

    # Sanity: the coverage the launch requirement named must actually be present.
    offsets = {e["utc_offset_minutes"] for e in expected}
    for need, label in (
        (390, "Indian war-time +06:30"),
        (330, "Indian normal +05:30"),
        (60, "a foreign DST offset"),
        (0, "a foreign standard offset"),
        (450, "Singapore's pre-1982 +07:30"),
        (480, "Singapore's post-1982 +08:00"),
    ):
        if need not in offsets:
            print(f"FAIL — coverage gap: no case resolved to {need} min ({label})")
            return 1
    print(f"coverage OK — resolved offsets present: {sorted(offsets)}")

    golden = [
        {
            "dob": c["dob"],
            "time": c["time"],
            "zone": c["zone"],
            "why": why,
            "expected": {
                "utc_offset_minutes": e["utc_offset_minutes"],
                "nakshatra_index": e["nakshatra_index"],
                "nakshatra": e["nakshatra"],
                "pada": e["pada"],
                "moon_sign": e["moon_sign"],
                "moon_longitude": round(e["moon_longitude"], 9),
            },
        }
        for c, e, why in zip(cases, expected, whys, strict=True)
    ]
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(golden, indent=1) + "\n")
    rel = GOLDEN_PATH.relative_to(ENGINE_ROOT.parent)
    print(f"golden file written: {rel} ({len(golden)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
