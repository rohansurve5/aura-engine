-- knowledge_content: the interpretive significations corpus — 27 nakshatra,
-- 9 planet and 12 house entries, authored against docs/voice/KNOWLEDGE.md.
--
-- ONE TABLE, NOT THREE. The three categories share ONE spine by design
-- (KNOWLEDGE.md §5: title / governs / demand / source / source_ref /
-- distinct_from), which already removes the payload-shape argument that made
-- the question live for identity_content. What decides it here is the same
-- three reasons migration 008 gave, each of which is *stronger* for this
-- corpus:
--
--   * ONE version marker. The §7d fear-symmetry gates are comparative — a
--     demand is legal only relative to its category's median length and to the
--     hard group's density against the rest of its own category. Those are
--     statements about a SET. Three markers would make "planets at v2, houses
--     at v1" expressible, and the v2 planets would then be live having been
--     length-gated against a median no longer in the database. That is not a
--     stale row; it is a gate silently voided. identity_content's version of
--     this argument was about a screen; this one is about the gate itself.
--   * ONE transaction, ONE endpoint, ONE query. /v1/knowledge/content returns
--     all three categories in a single payload — the explainer may cite a
--     planet, a house and a nakshatra in one answer, so a category is not a
--     unit anything reads alone.
--   * The payload is JSONB either way, so a split buys no schema precision.
--
-- Versions are additive, as in score_rules, dasha_content, identity_content and
-- report_content: every version ever seeded keeps its rows, so rollback is
-- repointing KNOWLEDGE_SEED_PATH in engine/content.py and re-running
-- db/migrate.py — never a data restore.
--
-- The `active_content` marker (kind 'knowledge_content') is used from version
-- ONE. score_rules and dasha_content both had to be migrated off max(version)
-- after shipping, the second because a lexical max over TEXT ranks '..._v10'
-- BELOW '..._v2'. That bug is unreachable for this corpus by construction.
--
-- key_type 'nakshatra' → key is a nakshatra name ('Hasta')
-- key_type 'planet'    → key is a graha name ('Saturn')
-- key_type 'house'     → key is 'house_1' .. 'house_12'
-- payload for all three → {title, governs, demand, source, source_ref, distinct_from}
--
-- key_type 'corpus'    → key is '_about', payload {status, shippable, spec}
--
-- The fourth key_type is not a fourth category. It carries ONE row of corpus
-- metadata, and it exists because of KNOWLEDGE.md §8: this corpus may not reach
-- a reader until an astrologer has reviewed the full 48, and that fact has to be
-- readable by the Worker that serves it. Recording `shippable` only in the seed
-- file would leave the block enforced in aura-engine's CI and nowhere near the
-- surface that actually renders copy — which is the same shape as the
-- content_v3_2 incident, where every individual step was verified and the JOIN
-- between them was not. It is a row rather than a column so that the metadata
-- travels with its VERSION: rolling the corpus back rolls its review state back
-- with it, which a column on active_content could not express.
CREATE TABLE IF NOT EXISTS knowledge_content (
    version  TEXT  NOT NULL,
    key_type TEXT  NOT NULL CHECK (key_type IN ('nakshatra', 'planet', 'house', 'corpus')),
    key      TEXT  NOT NULL,
    payload  JSONB NOT NULL,
    PRIMARY KEY (version, key_type, key)
);
