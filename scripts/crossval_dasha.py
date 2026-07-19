"""Cross-validate the Worker's Vimshottari dasha math against this engine — the deploy gate.

aura-api computes the dasha timeline in-Worker (src/dasha.ts on top of the
astronomy-engine Moon in src/natal.ts). This script is the accuracy contract:
it generates the SAME 1,000 seeded-random birth datetimes as crossval_natal.py
(seed 285, 1930-2025 IST) plus the known golden chart, resolves each with BOTH

  (a) this engine (Swiss Ephemeris lahiri_vp285 + engine/vimshottari.py — the
      source of truth), and
  (b) the exact TypeScript used by the Worker (aura-api/src/dasha.ts, executed
      by node via aura-api/scripts/dasha-batch.ts — no reimplementation),

and requires:
  * 100% agreement on nakshatra index/name, pada, lord and the maha sequence;
  * every maha and antar boundary (exact-float canonical dates, 10 blocks of
    9 antars each) within ±1 day;
  * the balance within ±1 day (it IS the first boundary: birth → first maha
    end). The Y/M/D presentation tuple is additionally reported: it derives
    from day-rounding a continuous quantity, so a sub-arcsecond Moon delta can
    legitimately flip the day component on boundary-straddling births.

It also asserts the known golden chart (1989-09-23 04:47 IST -> Ardra pada 4,
balance RAHU 3Y 10M 24D) EXACTLY on both sides.

On success it (re)writes aura-api/test/golden/dasha_crossval.json so the same
1,001 expectations are enforced by `npm test` in aura-api CI on every deploy,
without needing Python there.

Run:  uv run python scripts/crossval_dasha.py
Exit: non-zero on ANY disagreement beyond the contract (failing datetimes are
printed; do not tune).
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

from engine.positions import positions_from_ist  # noqa: E402
from engine.vimshottari import compute_dasha  # noqa: E402

ENGINE_ROOT = Path(__file__).resolve().parent.parent
AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "dasha_crossval.json"

SEED = 285  # same seed as crossval_natal.py — identical birth set
N_CASES = 1000
START = datetime(1930, 1, 1, 0, 0)
END = datetime(2025, 12, 31, 23, 59)
BLOCKS = 10  # maha blocks compared/served (the AstroSage table)
DAY = timedelta(days=1)

KNOWN_CASE = {"dob": "1989-09-23", "time": "04:47", "tz": "+05:30"}
KNOWN_EXPECT = {
    "nakshatra": "Ardra",
    "pada": 4,
    "lord": "Rahu",
    "balance": {"years": 3, "months": 10, "days": 24},
}


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


def engine_dasha(case: dict) -> dict:
    birth = datetime.strptime(f"{case['dob']} {case['time']}", "%Y-%m-%d %H:%M")
    moon = positions_from_ist(birth)["Moon"].longitude
    res = compute_dasha(moon, birth, year_mode="solar", levels=2, cycles=2)
    mahas = res.mahas[:BLOCKS]
    iso = lambda d: d.isoformat(timespec="milliseconds")  # noqa: E731
    return {
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


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def compare(case: dict, exp: dict, act: dict) -> tuple[list[str], float, bool]:
    """(hard failures, max boundary delta in days, balance tuple exact)."""
    fails: list[str] = []
    for key in ("nakshatra_index", "nakshatra", "pada", "lord", "maha_lords"):
        if act[key] != exp[key]:
            fails.append(f"{key}: engine={exp[key]} worker={act[key]}")

    bal_delta_d = abs(act["balance"]["total_days"] - exp["balance"]["total_days"])
    if bal_delta_d > 1.0:
        fails.append(f"balance total_days off by {bal_delta_d:.3f}d")
    bal_exact = all(act["balance"][k] == exp["balance"][k] for k in ("years", "months", "days"))

    max_delta = bal_delta_d
    pairs = [(exp["maha_start"], act["maha_start"])]
    pairs += list(zip(exp["maha_ends"], act["maha_ends"], strict=True))
    for e_row, a_row in zip(exp["antar_ends"], act["antar_ends"], strict=True):
        pairs += list(zip(e_row, a_row, strict=True))
    for e_iso, a_iso in pairs:
        delta = abs(_dt(a_iso) - _dt(e_iso))
        max_delta = max(max_delta, delta / DAY)
        if delta > DAY:
            fails.append(f"boundary {e_iso} vs {a_iso} (Δ{delta / DAY:.3f}d)")
    return fails, max_delta, bal_exact


def check_known(label: str, res: dict) -> list[str]:
    fails = []
    for key in ("nakshatra", "pada", "lord"):
        if res[key] != KNOWN_EXPECT[key]:
            fails.append(f"{label} {key}: {res[key]} != {KNOWN_EXPECT[key]}")
    got = {k: res["balance"][k] for k in ("years", "months", "days")}
    if got != KNOWN_EXPECT["balance"]:
        fails.append(f"{label} balance: {got} != {KNOWN_EXPECT['balance']}")
    return fails


def main() -> int:
    cases = generate_cases() + [KNOWN_CASE]
    print(f"cross-validating dasha tables for {len(cases)} births (seed={SEED}) ...")

    expected = [engine_dasha(c) for c in cases]
    actual = worker_dasha(cases)

    bad: list[tuple[dict, list[str]]] = []
    max_delta_days = 0.0
    balance_exact = 0
    for case, exp, act in zip(cases, expected, actual, strict=True):
        fails, max_d, bal_exact = compare(case, exp, act)
        max_delta_days = max(max_delta_days, max_d)
        balance_exact += bal_exact
        if fails:
            bad.append((case, fails))

    n = len(cases)
    print(f"agreement (identity + all boundaries ±1d): {n - len(bad)}/{n}")
    print(f"max boundary delta: {max_delta_days:.4f} days")
    print(f"balance Y/M/D presentation tuple exact: {balance_exact}/{n}")

    if bad:
        print(f"\nFAIL — {len(bad)} birth(s) beyond contract; DO NOT TUNE, investigate:")
        for case, fails in bad[:20]:
            print(f"  {case['dob']} {case['time']} IST:")
            for f in fails:
                print(f"    {f}")
        return 1

    # Known golden chart must resolve EXACTLY (incl. balance tuple) on both sides.
    known_fails = check_known("engine", expected[-1]) + check_known("worker", actual[-1])
    if known_fails:
        print("FAIL — known golden chart:")
        for f in known_fails:
            print(f"  {f}")
        return 1
    print("known case (1989-09-23 04:47 IST -> Ardra pada 4, RAHU 3Y 10M 24D): OK")

    golden = [
        {"dob": c["dob"], "time": c["time"], "tz": c["tz"], "expected": e}
        for c, e in zip(cases, expected, strict=True)
    ]
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(golden, indent=1) + "\n")
    rel = GOLDEN_PATH.relative_to(ENGINE_ROOT.parent)
    print(f"golden file written: {rel} ({len(golden)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
