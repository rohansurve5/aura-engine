-- dasha_content: the human interpretation layer for the Vimshottari timeline.
--
-- The dasha MATHS (period dates) is pure computation served by /v1/dasha with an
-- immutable cache; the WORDS about what each period means live here as data,
-- seeded from db/seed/dasha_content_v1.json. Keeping the two separate means
-- admin v2 can reword any entry (users see it next day via the short-cached
-- /v1/dasha/content) without ever invalidating the immutable maths cache.
--
-- One row per (version, key_type, key):
--   key_type 'maha'       → key is a lord name ('Saturn'),
--                           payload {title, essence, favours[], watch[]}
--   key_type 'maha_antar' → key is 'Maha-Antar' ('Saturn-Jupiter'),
--                           payload {line, now}
-- Versions are additive (like score_rules), enabling rollback.
CREATE TABLE IF NOT EXISTS dasha_content (
    version  TEXT  NOT NULL,
    key_type TEXT  NOT NULL CHECK (key_type IN ('maha', 'maha_antar')),
    key      TEXT  NOT NULL,
    payload  JSONB NOT NULL,
    PRIMARY KEY (version, key_type, key)
);
