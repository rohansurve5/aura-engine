-- app_events.received_at: the server's own clock, stamped by the API on insert.
--
-- `ts` is CLIENT-SUPPLIED and therefore untrusted: a device with a wrong clock,
-- a queued offline batch, or a hostile caller can put it anywhere on the number
-- line. It is kept because it is genuinely useful for reconstructing what the
-- user experienced (session ordering on-device), but it must never define an
-- analytics window.
--
-- RULE: every admin/analytics query that buckets by time uses received_at.
-- `ts` is display-only. See aura-admin/README.md → "Which timestamp".
-- Added nullable FIRST and constrained afterwards, deliberately. Adding it as
-- `NOT NULL DEFAULT now()` in one step would stamp every pre-existing row with
-- the migration timestamp, collapsing all history into a single fake spike on
-- the admin panel's activity chart.
ALTER TABLE app_events
    ADD COLUMN IF NOT EXISTS received_at TIMESTAMPTZ;

-- Backfill the rows written before this column existed. Pre-hardening rows had
-- only the client ts, so it is the best estimate we have for them.
UPDATE app_events SET received_at = ts WHERE received_at IS NULL;

ALTER TABLE app_events ALTER COLUMN received_at SET DEFAULT now();
ALTER TABLE app_events ALTER COLUMN received_at SET NOT NULL;

-- The admin panel's hot paths: recent-events feed, and per-device timeline.
CREATE INDEX IF NOT EXISTS app_events_received_at ON app_events (received_at DESC);
CREATE INDEX IF NOT EXISTS app_events_device_received_at
    ON app_events (device_id, received_at DESC);
