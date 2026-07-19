-- score_rules: the tunable v1 rule set that maps
-- (natal nakshatra × today's sky) -> scores.
--
-- v1 is a HEURISTIC, subject to astrologer review. Every magic number and every
-- line of copy lives here as data (seeded from db/seed/score_rules_v1.json), so
-- the numbers can be retuned WITHOUT a code change — the precompute job holds no
-- hardcoded scoring constants of its own and reads its rules from this table.
--
-- One row per (version, rule_key); params is the rule's JSON blob.
CREATE TABLE IF NOT EXISTS score_rules (
    version  TEXT  NOT NULL,
    rule_key TEXT  NOT NULL,
    params   JSONB NOT NULL,
    PRIMARY KEY (version, rule_key)
);
