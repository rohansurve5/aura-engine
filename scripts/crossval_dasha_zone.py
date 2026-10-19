"""Cross-validate /v1/dasha's IANA zone path: engine (zoneinfo) vs Worker (Intl).

The sibling crossval_dasha.py covers the FIXED-OFFSET contract — 1,001 births
all tagged "+05:30". That is the frozen legacy path, and it is exactly the bug
this script exists for: a caller that sent no tz got IST, so a New York birth
was read as an Indian wall clock and its Moon sampled 9½ hours early.

Here every birth carries an IANA zone, resolved AT THE BIRTH INSTANT by two
independent tz databases:

  (a) aura-engine — Python `zoneinfo` + Swiss Ephemeris + engine/vimshottari.py
      (the source of truth);
  (b) aura-api    — `Intl.DateTimeFormat` in V8 + src/dasha.ts, executed
      verbatim through aura-api/scripts/dasha-batch.ts.

Required, per birth: the same resolved UTC offset; the same nakshatra index,
pada, lord and maha sequence; every maha and antar boundary (10 blocks × 9)
within ±1 day; the balance within ±1 day. Same contract as crossval_dasha.py.

The list is hand-picked, not random: the point is to hit births abroad, both
DST seasons, southern-hemisphere DST, historical non-DST offset changes and
India's war-time +06:30 — none of which a seeded IST sample ever reaches.

On success it (re)writes aura-api/test/golden/dasha_zone_crossval.json, which
aura-api's vitest suite enforces on every deploy.

Run:  uv run python scripts/crossval_dasha_zone.py
Exit: non-zero on ANY disagreement (do not tune — investigate).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))

from engine.positions import positions_from_local  # noqa: E402
from engine.timezones import offset_minutes_at  # noqa: E402
from engine.vimshottari import compute_dasha  # noqa: E402

AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "dasha_zone_crossval.json"

BLOCKS = 10
DAY = timedelta(days=1)

# (dob, time, zone, why this case is here)
CASES: list[tuple[str, str, str, str]] = [
    # ── Abroad, DST-observing, both seasons ────────────────────────────────
    ("1990-07-04", "10:00", "America/New_York", "EDT (-04:00) — the headline bug case"),
    ("1990-01-15", "10:00", "America/New_York", "EST (-05:00) — same city, winter"),
    ("1978-11-05", "23:10", "America/Los_Angeles", "PST (-08:00), a week after fall-back"),
    ("1985-06-15", "08:30", "Europe/London", "BST (+01:00) — summer"),
    ("1985-12-15", "08:30", "Europe/London", "GMT (00:00) — winter"),
    ("1969-01-15", "12:00", "Europe/London", "British Standard Time: +01:00 IN WINTER, 1968-71"),
    ("2010-12-25", "18:00", "Australia/Sydney", "southern hemisphere: DST in December"),
    ("2003-04-12", "06:45", "Europe/Berlin", "CEST (+02:00), two weeks after spring-forward"),
    # ── Abroad, no DST ─────────────────────────────────────────────────────
    ("1995-03-10", "14:00", "Asia/Dubai", "+04:00, no DST"),
    ("1981-06-15", "10:30", "Asia/Singapore", "+07:30, before the 1982 change"),
    ("1990-06-15", "10:30", "Asia/Singapore", "+08:00, after it"),
    ("1985-06-15", "10:30", "Asia/Kathmandu", "+05:45, a 45-minute offset"),
    # ── India, which must keep matching the fixed-offset path ──────────────
    ("1989-09-23", "04:47", "Asia/Kolkata", "the known golden chart (Ardra pada 4)"),
    ("1943-06-15", "10:30", "Asia/Kolkata", "war-time +06:30 — differs from tz=+05:30"),
    ("2001-03-02", "23:55", "Asia/Kolkata", "modern, near midnight"),
]


def engine_dasha(dob: str, tm: str, zone: str) -> dict:
    birth = datetime.strptime(f"{dob} {tm}", "%Y-%m-%d %H:%M")
    moon = positions_from_local(birth, zone)["Moon"].longitude
    res = compute_dasha(moon, birth, year_mode="solar", levels=2, cycles=2)
    mahas = res.mahas[:BLOCKS]
    iso = lambda d: d.isoformat(timespec="milliseconds")  # noqa: E731
    return {
        "utc_offset_minutes": offset_minutes_at(zone, birth),
        "nakshatra_index": res.nakshatra.index,
        "nakshatra": res.nakshatra.name,
        "pada": res.nakshatra.pada,
        "lord": res.nakshatra.lord,
        "balance": {
            "years": res.balance.years,
            "months": res.balance.months,
            "days": res.balance.days,
            "total_days": res.balance.total_days,
        },
        "maha_start": iso(mahas[0].start),
        "maha_lords": [m.lord for m in mahas],
        "maha_ends": [iso(m.end) for m in mahas],
        "antar_ends": [[iso(a.end) for a in m.children] for m in mahas],
    }


def worker_dasha(cases: list[dict]) -> list[dict]:
    proc = subprocess.run(
        ["node", "scripts/dasha-batch.ts"],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        cwd=AURA_API,
        check=True,
    )
    return json.loads(proc.stdout)


def compare(exp: dict, act: dict) -> tuple[list[str], float]:
    fails: list[str] = []
    for key in ("utc_offset_minutes", "nakshatra_index", "nakshatra", "pada", "lord",
                "maha_lords"):
        if act[key] != exp[key]:
            fails.append(f"{key}: engine={exp[key]} worker={act[key]}")
    max_delta = abs(act["balance"]["total_days"] - exp["balance"]["total_days"])
    if max_delta > 1.0:
        fails.append(f"balance total_days off by {max_delta:.3f}d")
    pairs = [(exp["maha_start"], act["maha_start"])]
    pairs += list(zip(exp["maha_ends"], act["maha_ends"], strict=True))
    for e_row, a_row in zip(exp["antar_ends"], act["antar_ends"], strict=True):
        pairs += list(zip(e_row, a_row, strict=True))
    for e_iso, a_iso in pairs:
        delta = abs(datetime.fromisoformat(a_iso) - datetime.fromisoformat(e_iso))
        max_delta = max(max_delta, delta / DAY)
        if delta > DAY:
            fails.append(f"boundary {e_iso} vs {a_iso} (Δ{delta / DAY:.3f}d)")
    return fails, max_delta


def main() -> int:
    cases = [{"dob": d, "time": t, "zone": z} for d, t, z, _ in CASES]
    whys = [w for *_, w in CASES]
    print(f"cross-validating {len(cases)} zoned dasha tables (engine zoneinfo vs Worker Intl) ...")

    expected = [engine_dasha(c["dob"], c["time"], c["zone"]) for c in cases]
    actual = worker_dasha(cases)

    failures: list[str] = []
    max_delta_days = 0.0
    for case, exp, act, why in zip(cases, expected, actual, whys, strict=True):
        tag = f"{case['dob']} {case['time']} {case['zone']} ({why})"
        if "error" in act:
            failures.append(f"{tag}: worker rejected the case: {act['error']}")
            continue
        fails, max_d = compare(exp, act)
        max_delta_days = max(max_delta_days, max_d)
        failures += [f"{tag}: {f}" for f in fails]

    n = len(cases)
    print(f"max boundary delta: {max_delta_days:.4f} days")
    if failures:
        print(f"\nFAIL — {len(failures)} disagreement(s); DO NOT TUNE, investigate:")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"agreement (offset + identity + all boundaries ±1d): {n}/{n}")

    golden = [
        {"dob": c["dob"], "time": c["time"], "zone": c["zone"], "why": w, "expected": e}
        for c, w, e in zip(cases, whys, expected, strict=True)
    ]
    GOLDEN_PATH.write_text(json.dumps(golden, indent=1) + "\n")
    print(f"golden file written: {GOLDEN_PATH.relative_to(ENGINE_ROOT.parent)} ({n} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
