#!/usr/bin/env python
"""Tiny migration + seed runner for Neon (no ORM).

Applies every `db/migrations/*.sql` in filename order exactly once (tracked in a
`schema_migrations` table), then seeds `score_rules` and `dasha_content` from
the active seed files named by `engine/content.py`, with idempotent upserts.
Older versions keep their rows — versions are additive, enabling rollback:
`dasha_content_v1` stays in the table, so a rollback is repointing the seed path
in `engine/content.py` and re-running this script, not a data restore.

Seeding **either** corpus also stamps `active_content` with that seed file's
declared version, in the same transaction — seeding a corpus and activating it
are one act, never two. Nothing infers the live version from the data itself:
`max(version)` is a lexical max over TEXT and would serve `dasha_content_v2`
once `dasha_content_v10` exists.

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
import sys
from pathlib import Path

import psycopg
from psycopg.types.json import Json

# This module is run as a script (`python db/migrate.py`), so sys.path[0] is
# db/, not the repo root, and `engine` is not importable by default. The repo
# root is added explicitly rather than duplicating the seed path here: one
# declaration of the active version is worth three lines of path setup.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.content import DASHA_SEED_PATH as CONTENT_DASHA_SEED_PATH
from engine.content import IDENTITY_SEED_PATH as CONTENT_IDENTITY_SEED_PATH
from engine.content import REPORT_SEED_PATH as CONTENT_REPORT_SEED_PATH
from engine.content import SEED_PATH as CONTENT_SEED_PATH  # noqa: E402

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "migrations"

# The score_rules seed path is NOT declared here — it comes from
# engine/content.py, the single place the active content version is set, so
# that what gets seeded and what precompute reads back are the same file by
# construction rather than by two people remembering to edit two constants.
SEED = CONTENT_SEED_PATH
DASHA_SEED = CONTENT_DASHA_SEED_PATH
IDENTITY_SEED = CONTENT_IDENTITY_SEED_PATH
REPORT_SEED = CONTENT_REPORT_SEED_PATH


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
    """Seed the active score_rules corpus AND mark it active, atomically.

    Both facts come from the same file and are committed together, so the
    database can never be left holding a corpus nobody activated (the
    content_v3_2 failure) or an activation marker with no corpus behind it.
    """
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
        cur.execute(
            "INSERT INTO active_content (kind, version) VALUES ('score_rules', %s) "
            "ON CONFLICT (kind) DO UPDATE SET "
            "version = EXCLUDED.version, updated_at = now()",
            (version,),
        )
    conn.commit()
    print(f"seeded {len(data['rules'])} score_rules and marked ACTIVE (version {version})")


def seed_dasha_content(conn: psycopg.Connection) -> None:
    """Seed the active dasha_content corpus AND mark it active, atomically.

    Same contract as `seed()` above, for the same reason. `/v1/dasha/content`
    used to pick its version with `max(version)`, which is a lexical max over
    TEXT: at `dasha_content_v10` Postgres ranks `'dasha_content_v10'` below
    `'dasha_content_v2'` and the library would have silently rolled back eight
    versions. The live version is now a recorded fact, not an inference.
    """
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
        cur.execute(
            "INSERT INTO active_content (kind, version) VALUES ('dasha_content', %s) "
            "ON CONFLICT (kind) DO UPDATE SET "
            "version = EXCLUDED.version, updated_at = now()",
            (version,),
        )
    conn.commit()
    print(f"seeded {count} dasha_content entries and marked ACTIVE (version {version})")


def seed_identity_content(conn: psycopg.Connection) -> None:
    """Seed the active identity_content corpus AND mark it active, atomically.

    Same contract as the two above. This corpus uses the `active_content` marker
    from its FIRST version — it never had a max(version) phase to migrate off,
    which is the whole point: the lexical-sort bug (`'..._v10' < '..._v2'` in
    Postgres) has now been closed twice in this repo, and the cheapest place to
    close it a third time is before any code depends on the wrong thing.

    Both key types are written in one transaction with the marker, because the
    cross-corpus collision gate (IDENTITY.md §6d) is only meaningful over a
    matched pair of halves. A state where the nakshatra half is v2 and the
    moon-sign half is v1 would be a screen whose two paragraphs were never gated
    against each other — so that state is made unreachable rather than detected.
    """
    data = json.loads(IDENTITY_SEED.read_text())
    version = data["version"]
    count = 0
    with conn.cursor() as cur:
        for key_type in ("nakshatra", "moon_sign"):
            for key, payload in data[key_type].items():
                cur.execute(
                    "INSERT INTO identity_content (version, key_type, key, payload) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (version, key_type, key) "
                    "DO UPDATE SET payload = EXCLUDED.payload",
                    (version, key_type, key, Json(payload)),
                )
                count += 1
        cur.execute(
            "INSERT INTO active_content (kind, version) VALUES ('identity_content', %s) "
            "ON CONFLICT (kind) DO UPDATE SET "
            "version = EXCLUDED.version, updated_at = now()",
            (version,),
        )
    conn.commit()
    print(f"seeded {count} identity_content entries and marked ACTIVE (version {version})")


def seed_report_content(conn: psycopg.Connection) -> None:
    """Seed the active report_content corpus AND mark it active, atomically.

    Same contract as the three above, and like identity_content this corpus
    uses the `active_content` marker from its FIRST version — there was never a
    max(version) phase to migrate off. That lexical-sort bug
    (`'..._v10' < '..._v2'` in Postgres) has now been closed twice in this repo
    by retrofit; closing it up front costs nothing.

    EVERY report_kind in the seed file (weekly today, monthly when authored)
    and all four key types are written in ONE transaction with ONE marker.
    Within a kind, the four movements are gated as a set (the consecutive-week
    distinctness gate spans all four); across kinds, the corpus gates run over
    the whole seed file, so a weekly at v2 beside a monthly at v1 would be a
    pairing no gate ever saw. Both halves of that argument are 008's — made
    unreachable rather than merely detected. A kind present in the file but
    unknown here fails loudly rather than seeding a partial corpus.
    """
    data = json.loads(REPORT_SEED.read_text())
    version = data["version"]
    kinds = [k for k in ("weekly", "monthly") if k in data]
    unknown = set(data) - {"version", "_about", "weekly", "monthly"}
    if unknown:
        raise SystemExit(f"report seed {REPORT_SEED.name} has unknown keys: {sorted(unknown)}")
    count = 0
    with conn.cursor() as cur:
        for report_kind in kinds:
            corpus = data[report_kind]
            for key_type in ("shape", "turn", "standing", "close"):
                for key, payload in corpus[key_type].items():
                    cur.execute(
                        "INSERT INTO report_content "
                        "(version, report_kind, key_type, key, payload) "
                        "VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (version, report_kind, key_type, key) "
                        "DO UPDATE SET payload = EXCLUDED.payload",
                        (version, report_kind, key_type, key, Json(payload)),
                    )
                    count += 1
        cur.execute(
            "INSERT INTO active_content (kind, version) VALUES ('report_content', %s) "
            "ON CONFLICT (kind) DO UPDATE SET "
            "version = EXCLUDED.version, updated_at = now()",
            (version,),
        )
    conn.commit()
    print(
        f"seeded {count} report_content entries across kinds {kinds} "
        f"and marked ACTIVE (version {version})"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "apply migrations and seed score_rules + dasha_content + "
            "identity_content + report_content"
        )
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
            seed_identity_content(conn)
            seed_report_content(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
