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
-- (docs/REPORTS.md § the arc), one key_type each:
--
--   'shape'    → key is a shape id (rising|falling|cresting|dipping|
--                volatile|flat); payload {openings: [11 variants]}
--   'turn'     → key is a turn kind (peak_early|peak_mid|peak_late|
--                trough_mid|no_turn); payload {lines: [7 variants]}
--   'standing' → key is '<area>.<role>' where role is leads|lags|steadies;
--                payload {lines: [5 variants]}
--   'close'    → key is a shape id; payload {lines: [5 variants]}
--
-- ONE TABLE, following 008's reasoning exactly: the four key types are
-- authored together, gated together (the consecutive-week distinctness gate
-- spans all four, because all four render into one report), and read by one
-- endpoint in one query. Splitting them would make a half-rolled-back state
-- expressible — a 'shape' half at v2 and a 'turn' half at v1, whose pairing
-- was never gated — for no gain, since the payload is JSONB either way.
--
-- VARIANT COUNTS ARE PRIME AND MUTUALLY COPRIME (11, 7, 5) BY DESIGN. A
-- report cadence is a *cycle*, and any rotation whose period shares a factor
-- with that cycle collapses: a 12-row table indexed by month would hand every
-- January the same row forever. 11 is coprime with 52 (weeks/year), and
-- lcm(11,7,5) = 385 weeks, so the variant triple a reader sees cannot recur
-- inside seven years of continuous reading. See docs/REPORTS.md § determinism.
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
