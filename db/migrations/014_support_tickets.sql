-- support_tickets + support_messages: the in-app support desk.
--
-- DECISION (support desk): a real support path must exist BEFORE any prepaid
-- credit ships. Japam's public anger came from prepaid money with nobody
-- answering — a mailto: link to a personal inbox is not a support path. The
-- design is in-app form -> Neon -> admin panel -> Rohan replies -> delivered
-- IN-APP. No outbound email infra on the main path: someone with a billing
-- problem has the app open, so they are answered there. These two tables are
-- the Neon half of that loop.
--
-- Keyed on the SAME anonymous device_id the credit ledger and analytics use
-- (migration 013), so a ticket correlates to a balance and an event history
-- without an account. A support message is user-written PERSONAL DATA; the
-- privacy policy carries a matching clause (legal/privacy.html, marker
-- '/v1/support/tickets') and the Flutter egress test asserts that clause is
-- present. RETENTION: a ticket and its messages are kept while the issue is
-- open and for up to 24 months after it is closed (dispute / refund audit for
-- prepaid purchases), then deleted; a user may request earlier deletion
-- through the same support channel.
--
-- No seed content and no active_content marker: like credit_ledger (013) this
-- is a runtime write table, not a versioned corpus. Additive and idempotent
-- (CREATE TABLE IF NOT EXISTS), so a re-run cannot leave it worse than it
-- started.
CREATE TABLE IF NOT EXISTS support_tickets (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id      TEXT        NOT NULL,
    -- new     : awaiting a human reply.
    -- replied : Rohan has replied at least once; the ball is with the user.
    -- closed  : resolved; still readable, no longer in the active queue.
    status         TEXT        NOT NULL DEFAULT 'new',
    -- Diagnostics captured ONCE at creation so Rohan can diagnose without a
    -- back-and-forth. These are the app's own facts about itself, not new
    -- tracking: the app version, which surface the ticket was raised from
    -- ('recharge' | 'out_of_credits' | 'settings'), the credit balance and
    -- Plus state at the moment of writing, and the last client-side error the
    -- app saw (NULL when there was none).
    app_version    TEXT,
    from_screen    TEXT,
    credit_balance INTEGER,
    is_premium     BOOLEAN,
    last_error     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT support_tickets_status CHECK (status IN ('new', 'replied', 'closed'))
);

-- One row per message in a ticket thread. author is WHO wrote it:
--   * user  — the person, from the in-app form.
--   * auto  — the immediate acknowledgement inserted at ticket creation
--             (receipt + the 48-hour commitment). Stored, not just shown
--             client-side, so the admin sees exactly what the user was told.
--   * admin — Rohan's reply from the admin panel; lands back in the app.
-- time-to-first-reply is derived as (first author='admin' created_at) minus
-- the ticket created_at.
CREATE TABLE IF NOT EXISTS support_messages (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id  UUID        NOT NULL REFERENCES support_tickets (id) ON DELETE CASCADE,
    author     TEXT        NOT NULL,
    body       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT support_messages_author CHECK (author IN ('user', 'auto', 'admin'))
);

-- GET /v1/support/tickets?device_id=… reads a device's tickets newest-first.
CREATE INDEX IF NOT EXISTS support_tickets_device ON support_tickets (device_id, created_at DESC);

-- The admin queue lists by status, newest-first.
CREATE INDEX IF NOT EXISTS support_tickets_status ON support_tickets (status, created_at DESC);

-- A thread is always read in creation order for one ticket.
CREATE INDEX IF NOT EXISTS support_messages_ticket ON support_messages (ticket_id, created_at);
