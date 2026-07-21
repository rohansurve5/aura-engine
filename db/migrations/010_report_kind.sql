-- report_kind: discriminate the weekly and monthly corpora inside report_content.
--
-- WHY NOW. 009 shipped with the weekly corpus as the only occupant, keyed by
-- (version, key_type, key). The monthly report reuses the same four movement
-- names at month scale — a monthly 'shape'/'front' cell is a different sentence
-- about a different span — so without a discriminator the two corpora would
-- collide on the same primary key. Cheaper to add the column while one corpus
-- exists than to untangle two.
--
-- ONE ACTIVATION MARKER, NOT ONE PER KIND — the identity_content reasoning
-- (008), applied at the next level up. identity's two key_types share one
-- version and one marker because its cross-key gates are only meaningful over a
-- matched pair; a nakshatra half at v2 beside a moon_sign half at v1 would be a
-- screen whose paragraphs were never gated together, so that state is made
-- inexpressible. The report corpora have the same property one level up: the
-- distinctness and share gates run over the whole seed file, weekly and monthly
-- together, so "weekly v2 + monthly v1" would be a pairing no gate ever saw.
-- With a single 'report_content' marker and a single seed file carrying every
-- kind, a half-rolled-back state is not a row that can exist — rollback
-- repoints REPORT_SEED_PATH and moves BOTH kinds in one transaction, exactly
-- like 008's two key_types.
--
-- EXISTING ROWS are all weekly (v1 predates any other kind), so the column
-- backfills to 'weekly' via a default that is then DROPPED: a future seeder
-- that forgets to state the kind must error, not silently author weekly rows.
--
-- Versions stay additive and marker-based (active_content, 007). No
-- max(version) anywhere — the live version is recorded intent, never inferred.

ALTER TABLE report_content
    ADD COLUMN IF NOT EXISTS report_kind TEXT NOT NULL DEFAULT 'weekly';

ALTER TABLE report_content
    ALTER COLUMN report_kind DROP DEFAULT;

ALTER TABLE report_content
    ADD CONSTRAINT report_content_report_kind_check
    CHECK (report_kind IN ('weekly', 'monthly'));

ALTER TABLE report_content
    DROP CONSTRAINT report_content_pkey;

ALTER TABLE report_content
    ADD PRIMARY KEY (version, report_kind, key_type, key);
