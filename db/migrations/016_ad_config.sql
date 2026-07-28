-- ad_config: the server-driven advertising configuration.
--
-- WHY THIS TABLE EXISTS. Block 1 removed every purchase surface, so ads are now
-- the whole revenue model and DAU is the revenue variable. That makes a bad
-- placement cost money twice — once in the impression that annoys someone, once
-- in the session they never come back for. A compiled-in ad config would make
-- every tuning decision a Play release and a review cycle, which is a week's
-- latency on the one knob that can damage retention. So formats, caps,
-- cooldowns and placements are DATA, tunable from the admin panel, exactly the
-- way content already is.
--
-- ── SAME PATTERN AS THE CONTENT CORPORA, WITH ONE DELIBERATE DIFFERENCE ──────
--
-- Shape, versioning and activation follow score_rules / dasha_content /
-- identity_content / report_content / knowledge_content precisely: rows keyed by
-- (version, ...), versions additive so rollback is repointing a seed path, and
-- the live version recorded in `active_content` (kind 'ad_config') from version
-- ONE rather than inferred. `max(version)` is a LEXICAL max over TEXT and ranks
-- 'ad_config_v10' BELOW 'ad_config_v2'; that bug has been closed by retrofit
-- twice in this repo and is unreachable here by construction.
--
-- THE DIFFERENCE: this table is OPERATIONALLY MUTABLE. A content corpus is
-- immutable once seeded — new copy means a new version. An ad config is turned
-- up and down by a human during the day, from the admin panel, and that human's
-- edit must survive the night. The nightly precompute workflow runs
-- `db/migrate.py` at 01:00 IST before it seeds guidance, so a seeder that
-- upserted operational state would silently revert every ad decision Rohan made
-- that day, every day, with no error anywhere. `seed_ad_config` therefore
-- inserts ON CONFLICT DO NOTHING: the seed file establishes a version's
-- CATALOGUE (which placements exist, in which format, with which safe starting
-- numbers); once a row exists, the panel owns it. Changing a default for an
-- existing placement is a new version, not an edit to this file.
--
-- ── THE FAIL-SAFE, EXPRESSED IN THE SCHEMA ──────────────────────────────────
--
-- Every row is off by default, including the master. `enabled` means the same
-- thing on every row in the table — "this may serve" — so there is no inverted
-- boolean to misread at 2am while an AdMob policy mail is open:
--
--   kind='global',    key='master'    enabled=false → NO AD SERVES ANYWHERE.
--   kind='placement', key=<placement> enabled=false → that placement serves nothing.
--
-- The master row is the kill switch. It is a row rather than a column on
-- `active_content` for knowledge_content's reason: metadata that travels with
-- its VERSION, so a rollback rolls the switch state back with it too.
--
-- daily_cap = 0 MEANS "SERVE NOTHING", never "unlimited". That reading is not
-- arbitrary — it is what makes a zeroed, missing or unparseable cap fail closed.
-- The Worker enforces it (aura-api/src/ads.ts: a placement with cap <= 0 is
-- served disabled no matter what its `enabled` column says), so "enabled with a
-- zero cap" is not a state the system can express. cooldown_seconds = 0 and
-- min_sessions = 0 mean exactly zero, because there is no unsafe reading of
-- either: no cooldown and no warm-up are permissive only in degree, while an
-- uncapped placement is unbounded in kind.
--
-- format is NULL for the master row and required for a placement — asserted, not
-- conventional, so a placement cannot be seeded formatless and served as a
-- shape no client knows how to render.
--
-- params carries the format-specific fields: list slotting for native, the
-- session-scope declaration for rewarded (Block 1's binding constraint — a
-- rewarded unlock is session-scoped and is NOT an entitlement), and so on.
-- JSONB because those fields differ per format and a column per format would be
-- eleven mostly-NULL columns.
CREATE TABLE IF NOT EXISTS ad_config (
    version          TEXT        NOT NULL,
    kind             TEXT        NOT NULL CHECK (kind IN ('placement', 'global')),
    key              TEXT        NOT NULL,
    format           TEXT        CHECK (format IN ('rewarded', 'native', 'banner', 'interstitial', 'app_open')),
    enabled          BOOLEAN     NOT NULL DEFAULT false,
    daily_cap        INTEGER     NOT NULL DEFAULT 0 CHECK (daily_cap >= 0),
    cooldown_seconds INTEGER     NOT NULL DEFAULT 0 CHECK (cooldown_seconds >= 0),
    min_sessions     INTEGER     NOT NULL DEFAULT 0 CHECK (min_sessions >= 0),
    params           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (version, kind, key),
    -- A placement has a format; the master row does not. Both directions.
    CONSTRAINT ad_config_format_matches_kind
        CHECK ((kind = 'placement') = (format IS NOT NULL))
);
