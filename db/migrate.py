#!/usr/bin/env python
"""Tiny migration + seed runner for Neon (no ORM).

Applies every `db/migrations/*.sql` in filename order exactly once (tracked in a
`schema_migrations` table), then seeds `score_rules` from
`db/seed/score_rules_content_v2.json` and `dasha_content` from
`db/seed/dasha_content_v1.json` with idempotent upserts. Older versions keep
their rows — versions are additive, enabling rollback.

    NEON_DATABASE_URL=postgres://... uv run python db/migrate.py
    ...                              uv run python db/migrate.py --seed-only
    ...                              uv run python db/migrate.py --no-seed

Secrets come from the environment only (never committed) — this keeps the AGPL
engine repo free of credentials while still owning the seeding step.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Json

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "migrations"
SEED = ROOT / "seed" / "score_rules_content_v2.json"
DASHA_SEED = ROOT / "seed" / "dasha_content_v1.json"


def _dsn() -> str:
    dsn = os.environ.get("NEON_DATABASE_URL")
    if not dsn:
        raise SystemExit("NEON_DATABASE_URL is not set")
    return dsn


def _statements(sql: str):
    """Yield individual statements (comment lines stripped before splitting so a
    ``;`` inside a comment never splits a statement)."""
    code = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )
    for raw in code.split(";"):
        stmt = raw.strip()
        if stmt:
            yield stmt


def migrate(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cur.execute("SELECT filename FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in applied:
                continue
            for statement in _statements(path.read_text()):
                cur.execute(statement)
            cur.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
            )
            print(f"applied {path.name}")
    conn.commit()


def seed(conn: psycopg.Connection) -> None:
    data = json.loads(SEED.read_text())
    version = data["version"]
    with conn.cursor() as cur:
        for rule_key, params in data["rules"].items():
            cur.execute(
                "INSERT INTO score_rules (version, rule_key, params) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (version, rule_key) DO UPDATE SET params = EXCLUDED.params",
                (version, rule_key, Json(params)),
            )
    conn.commit()
    print(f"seeded {len(data['rules'])} score_rules (version {version})")


def seed_dasha_content(conn: psycopg.Connection) -> None:
    data = json.loads(DASHA_SEED.read_text())
    version = data["version"]
    count = 0
    with conn.cursor() as cur:
        for key_type in ("maha", "maha_antar"):
            for key, payload in data[key_type].items():
                cur.execute(
                    "INSERT INTO dasha_content (version, key_type, key, payload) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (version, key_type, key) "
                    "DO UPDATE SET payload = EXCLUDED.payload",
                    (version, key_type, key, Json(payload)),
                )
                count += 1
    conn.commit()
    print(f"seeded {count} dasha_content entries (version {version})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="apply migrations and seed score_rules + dasha_content"
    )
    ap.add_argument("--seed-only", action="store_true", help="skip migrations")
    ap.add_argument("--no-seed", action="store_true", help="skip seeding")
    args = ap.parse_args(argv)

    with psycopg.connect(_dsn()) as conn:
        if not args.seed_only:
            migrate(conn)
        if not args.no_seed:
            seed(conn)
            seed_dasha_content(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
