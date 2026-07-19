-- daily_sky: one precomputed "sky" row per civil date.
--
-- MVP LIMITATION (documented): the payload is computed for ONE canonical
-- location (Pune, IST) — see engine/daily.py:CANONICAL_LOCATION. Sunrise/sunset
-- and every window are that location's solar times. City-level per-lat/lon
-- solar times are deferred; the app reads this single canonical set for now.
--
-- Read pattern is a single-row lookup by PK (date), so no extra indexes needed.
CREATE TABLE IF NOT EXISTS daily_sky (
    date        DATE PRIMARY KEY,
    payload     JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
