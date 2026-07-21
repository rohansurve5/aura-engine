"""Cross-validate the Worker's A5 score adjustment against the engine — deploy gate.

aura-api applies the ascendant to the daily reading at read time
(src/scores.ts). The reference implementation is engine/scoring.py
apply_ascendant. This script composes real guidance rows (active rules, real
skies) for a deterministic grid of (date × natal nakshatra × lagna sign)
cases, runs BOTH implementations — the TypeScript via
aura-api/scripts/scores-batch.ts, no reimplementation — and requires the
adjusted payloads to be DEEP-EQUAL, string for string: scores, band labels,
score-why (recognition + swapped house cause), narrative, opportunity,
warning. Numbers agreeing while copy drifts is exactly the incoherence A5 §2
prohibits, so the gate compares everything.

On success it (re)writes aura-api/test/golden/scores_crossval.json (rules
embedded, so aura-api CI needs no database and no Python) and the same
expectations gate `npm test` on every deploy.

Run:  uv run python scripts/crossval_scores.py
Exit: non-zero on ANY difference (do not tune here; fix the port).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from engine.daily import build_daily_sky
from engine.scoring import (
    SCORE_RULES_VERSION,
    apply_ascendant,
    guidance_for_nakshatra,
    load_rules_from_json,
)

ENGINE_ROOT = Path(__file__).resolve().parent.parent
AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "scores_crossval.json"

# Fixed dates (not "today"-relative): the golden must be reproducible
# byte-for-byte from a clean checkout at any time.
START = date(2026, 7, 21)
N_DATES = 6


def build_cases(rules: dict) -> list[dict]:
    cases = []
    for k in range(N_DATES):
        day = START + timedelta(days=7 * k)
        sky = build_daily_sky(day)
        sky_subset = {
            "planet_signs": sky["planet_signs"],
            "day_nakshatra_index": sky["day_nakshatra_index"],
        }
        # 9 nakshatras and 3 ascendants per date, phased by the date index so
        # all 27 naks and all 12 ascs are exercised across the grid.
        for i in range(9):
            nak = (3 * i + k) % 27
            row = guidance_for_nakshatra(nak, sky, rules)
            for j in range(3):
                asc = (nak + 4 * j + k) % 12
                cases.append({
                    "date": day.isoformat(),
                    "nakshatra_index": nak,
                    "asc": asc,
                    "sky": sky_subset,
                    "row": row,
                    "expected": apply_ascendant(row, sky_subset, asc, rules),
                })
    return cases


def worker_scores(rules: dict, cases: list[dict]) -> list[dict]:
    batch = {
        "rules": rules,
        "cases": [{"row": c["row"], "sky": c["sky"], "asc": c["asc"]} for c in cases],
    }
    proc = subprocess.run(
        ["node", "scripts/scores-batch.ts"],
        input=json.dumps(batch),
        capture_output=True,
        text=True,
        cwd=AURA_API,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    rules = load_rules_from_json()
    if "house_significators" not in rules:
        raise SystemExit("active rules carry no house tables — is content_v4 active?")
    cases = build_cases(rules)
    print(f"cross-validating {len(cases)} (date × nakshatra × asc) adjustments "
          f"under {SCORE_RULES_VERSION} ...")

    actual = worker_scores(rules, cases)

    mismatches = []
    for c, act in zip(cases, actual, strict=True):
        if act != c["expected"]:
            diff_keys = [k for k in c["expected"]
                         if c["expected"].get(k) != act.get(k)]
            mismatches.append((c, diff_keys))

    n = len(cases)
    print(f"agreement: {n - len(mismatches)}/{n}")
    if mismatches:
        print(f"\nFAILURES ({len(mismatches)}):")
        for c, keys in mismatches[:10]:
            print(f"  {c['date']} nak {c['nakshatra_index']} asc {c['asc']}: "
                  f"differs in {keys}")
            for k in keys[:2]:
                print(f"    engine: {json.dumps(c['expected'][k])[:200]}")
        return 1

    GOLDEN_PATH.write_text(json.dumps(
        {"rules_version": SCORE_RULES_VERSION, "rules": rules, "cases": cases},
        indent=1,
    ) + "\n")
    print(f"wrote {GOLDEN_PATH.relative_to(AURA_API.parent)} ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
