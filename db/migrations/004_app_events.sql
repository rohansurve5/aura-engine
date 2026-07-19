-- app_events: the analytics sink the app posts to later (write-heavy append).
-- No engine code writes here; it exists so the schema is complete and the future
-- private API has a landing table. Indexed for the two obvious read slices
-- (per device over time, per event name over time).
CREATE TABLE IF NOT EXISTS app_events (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id TEXT        NOT NULL,
    name      TEXT        NOT NULL,
    props     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    ts        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS app_events_device_ts ON app_events (device_id, ts);
CREATE INDEX IF NOT EXISTS app_events_name_ts ON app_events (name, ts);
