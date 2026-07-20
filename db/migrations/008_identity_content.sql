-- identity_content: the "About your star" corpus — 27 nakshatra profiles and
-- 12 moon-sign trait entries, authored against docs/voice/IDENTITY.md.
--
-- ONE TABLE, NOT TWO. The two corpora have different payload shapes (nakshatra
-- carries title/core/cost/misread/contrast; moon_sign carries
-- title/need/unsettles) and different sizes, which is an argument for two
-- tables right up until you notice that `dasha_content` already carries two
-- shapes ('maha' {title,essence,favours,watch} vs 'maha_antar' {line,now}) in
-- one table and has not suffered for it. What actually decides it:
--
--   * ONE version marker. Both corpora are authored together, gated together
--     (the cross-corpus collision gate in IDENTITY.md §6d spans BOTH), and are
--     read on the SAME screen. Two tables would mean either two `active_content`
--     kinds — which makes a half-rolled-back state expressible, where the
--     nakshatra half is v2 and the moon-sign half is v1 and the collision gate
--     that was run against neither combination is silently void — or one marker
--     governing two tables, which is the same coupling with extra joins.
--   * ONE transaction, ONE endpoint, ONE query. `/v1/identity/content` returns
--     both halves in a single payload because the profile screen needs both.
--   * The payload is JSONB either way, so a shared table costs no schema
--     precision that a split would have bought.
--
-- Versions are additive, as in score_rules and dasha_content: every version
-- ever seeded keeps its rows, so rollback is repointing IDENTITY_SEED_PATH in
-- engine/content.py and re-running db/migrate.py — never a data restore.
--
-- key_type 'nakshatra' → key is a nakshatra name ('Krittika'),
--                        payload {title, core, cost, misread, contrast[2]}
-- key_type 'moon_sign' → key is a sign name ('Taurus'),
--                        payload {title, need, unsettles}
CREATE TABLE IF NOT EXISTS identity_content (
    version  TEXT  NOT NULL,
    key_type TEXT  NOT NULL CHECK (key_type IN ('nakshatra', 'moon_sign')),
    key      TEXT  NOT NULL,
    payload  JSONB NOT NULL,
    PRIMARY KEY (version, key_type, key)
);
