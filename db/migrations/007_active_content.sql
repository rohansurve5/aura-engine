-- The ACTIVE content version, as a fact in the database.
--
-- score_rules is additive: every version ever seeded keeps its rows, which is
-- what makes rollback cheap. The cost of that is that the table cannot answer
-- "which version is live?" — max(version) is a *lexical* max (and would pick
-- content_v3_1 over content_v3_10), not a statement of intent.
--
-- This table records intent. db/migrate.py writes it in the same transaction
-- that seeds the rules, from the same seed file, so "seeded" and "activated"
-- cannot come apart. /v1/health compares it against the rules_version actually
-- stamped on today's daily_guidance rows to detect seeded-but-not-served drift.

CREATE TABLE IF NOT EXISTS active_content (
  kind       TEXT PRIMARY KEY,
  version    TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
