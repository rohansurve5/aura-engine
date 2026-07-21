-- report_content: the period-report corpus. v1 ships the WEEKLY report only.
--
-- WHY A REPORT IS NOT A LONGER DAILY CARD
--
-- daily_guidance answers "what is today like?" — one date, one reading. A
-- report answers "what does this stretch of time DO?", and that question is
-- not answerable from any single day in the stretch. Its content is composed
-- from RANGE-DERIVED features that exist only at the range level: the trend
-- across the span, the spread between its best and worst day, where the peak
-- falls inside the window, which area leads and which lags in aggregate.
-- Concatenating seven daily cards produces seven readings, not one report,
-- which is exactly the failure mode this corpus is shaped to avoid.
--
-- THE SHAPE OF THE CORPUS follows the four movements of the report arc
-- (docs/REPORTS.md § the arc), one key_type each. Shapes are DISTRIBUTION
-- classes — where the strong days fall — not trend classes; the first
-- rising/falling/cresting/dipping taxonomy described a trend the sawtooth
-- energy data does not have and was replaced before shipping (see the SHAPES
-- docstring in engine/reports.py):
--
--   'shape'    → key is a shape id (even|split|front|back|centre|scattered);
--                payload {openings: [...]}
--   'turn'     → key is a turn kind (peak_early|peak_mid|peak_late|
--                whiplash|no_turn); payload {lines: [...]}
--   'standing' → key is '<area>.<role>' where role is leads|lags|steadies;
--                payload {lines: [...]}
--   'close'    → key is a shape id; payload {lines: [...]}
--
-- Variant counts per cell are declared by the active seed file and pinned by
-- the corpus gates (tests/test_report_content_seed.py), not by this schema.
--
-- ONE TABLE, following 008's reasoning exactly: the four key types are
-- authored together, gated together (the consecutive-week distinctness gate
-- spans all four, because all four render into one report), and read by one
-- endpoint in one query. Splitting them would make a half-rolled-back state
-- expressible — a 'shape' half at v2 and a 'turn' half at v1, whose pairing
-- was never gated — for no gain, since the payload is JSONB either way.
--
-- VARIANT COUNTS ARE PRIME AND MUTUALLY COPRIME BY DESIGN. A report cadence
-- is a *cycle*, and any rotation whose period shares a factor with that cycle
-- collapses: a 12-row table indexed by month would hand every January the
-- same row forever. Every count is coprime with 52 (weeks/year) and with the
-- others, so the variant tuple a reader sees cannot recur inside years of
-- continuous reading. See docs/REPORTS.md § determinism.
--
-- (010 adds a report_kind discriminator so the weekly and monthly corpora
-- coexist in this table; this file is left as it ran, comments aside.)
--
-- Versions are additive, as in score_rules / dasha_content / identity_content:
-- rollback is repointing REPORT_SEED_PATH in engine/content.py and re-running
-- migrate, never a data restore.
CREATE TABLE IF NOT EXISTS report_content (
    version  TEXT  NOT NULL,
    key_type TEXT  NOT NULL CHECK (key_type IN ('shape', 'turn', 'standing', 'close')),
    key      TEXT  NOT NULL,
    payload  JSONB NOT NULL,
    PRIMARY KEY (version, key_type, key)
);
