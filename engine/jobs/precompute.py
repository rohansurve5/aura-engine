"""Nightly precompute: seed daily_sky + 27 daily_guidance rows into Neon.

For each date in `[start .. start + days)` (default: today through today+13, a
14-day lookahead so one missed night never blanks the app) this computes the
canonical daily_sky payload and the 27 per-nakshatra guidance payloads, then
upserts them idempotently. Re-running is safe: same date + same rules version
overwrites with byte-identical payloads.

    NEON_DATABASE_URL=postgres://... uv run python -m engine.jobs.precompute
    ...  uv run python -m engine.jobs.precompute --start 2026-07-18 --days 14

Rules are read from the score_rules table (see db/migrate.py) — the job holds no
scoring constants of its own.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from ..daily import build_daily_sky
from ..scoring import SCORE_RULES_VERSION, all_guidance, load_rules_from_db
from .db import connect

LOOKAHEAD_DAYS = 14


def _canonical(payload: dict | list) -> str:
    """Stable JSON text — sorted keys, no incidental whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


_SKY_SQL = (
    "INSERT INTO daily_sky (date, payload) VALUES (%s, %s::jsonb) "
    "ON CONFLICT (date) DO UPDATE SET payload = EXCLUDED.payload, computed_at = now()"
)
_GUIDANCE_SQL = (
    "INSERT INTO daily_guidance (date, nakshatra_index, rules_version, payload) "
    "VALUES (%s, %s, %s, %s::jsonb) "
    "ON CONFLICT (date, nakshatra_index) DO UPDATE SET "
    "rules_version = EXCLUDED.rules_version, payload = EXCLUDED.payload, computed_at = now()"
)


def precompute(conn, start: date, days: int, version: str = SCORE_RULES_VERSION) -> int:
    """Upsert sky + guidance for `days` dates from `start`. Returns rows written.

    Rows are collected and sent as two batched `executemany` calls (psycopg
    pipelines them) so the job is not bottlenecked on per-row network latency.
    """
    rules = load_rules_from_db(conn, version)
    sky_rows: list[tuple] = []
    guidance_rows: list[tuple] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        sky = build_daily_sky(day)
        sky_rows.append((day, _canonical(sky)))
        for row in all_guidance(sky, rules):
            guidance_rows.append((day, row["nakshatra_index"], version, _canonical(row)))

    with conn.cursor() as cur:
        cur.executemany(_SKY_SQL, sky_rows)
        cur.executemany(_GUIDANCE_SQL, guidance_rows)
    conn.commit()
    return len(sky_rows) + len(guidance_rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="precompute daily_sky + daily_guidance")
    ap.add_argument("--start", type=date.fromisoformat, default=None,
                    help="first date YYYY-MM-DD (default: today)")
    ap.add_argument("--days", type=int, default=LOOKAHEAD_DAYS,
                    help=f"number of dates (default: {LOOKAHEAD_DAYS})")
    ap.add_argument("--rules-version", default=SCORE_RULES_VERSION)
    args = ap.parse_args(argv)

    start = args.start or date.today()
    with connect() as conn:
        rows = precompute(conn, start, args.days, args.rules_version)
    end = start + timedelta(days=args.days - 1)
    print(f"precomputed {start}..{end} ({args.days} days) — {rows} rows upserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
