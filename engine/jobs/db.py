"""Neon connection helper — a single place that reads NEON_DATABASE_URL."""

from __future__ import annotations

import os

import psycopg


def connect(dsn: str | None = None) -> psycopg.Connection:
    """Connect to Neon using `dsn` or the NEON_DATABASE_URL env var (pooled)."""
    dsn = dsn or os.environ.get("NEON_DATABASE_URL")
    if not dsn:
        raise SystemExit("NEON_DATABASE_URL is not set")
    return psycopg.connect(dsn)
