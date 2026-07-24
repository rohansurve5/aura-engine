-- credit_ledger + credit_purchases: the money layer (5.1b).
--
-- DECISION (5.1b §1): a SINGLE server-side ledger, keyed on the anonymous
-- device_id, with cross-reinstall recovery anchored on Play purchase TOKENS
-- (not the device_id, which a reinstall wipes). This is the only design that
-- survives a reinstall for PURCHASED credit without shipping auth first — the
-- Japam failure (took money, reinstall destroyed the credit) is exactly what a
-- device-only ledger would reproduce. Personal astrology data still stays on
-- device; what lands here is an anonymous commercial balance + the purchase
-- tokens needed to restore it. The privacy policy carries a matching clause.
--
-- Three sources are kept DISTINGUISHABLE, because they have different rules:
--   * free_remaining       — the 5-credit free grant, ONCE ever (default 5).
--   * plus_allowance_*      — Aura Plus monthly allowance (30), use-it-or-lose-it,
--                             reset each IST month; does NOT roll over.
--   * purchased_remaining   — recharge (₹100=50) + Lifetime (200). NEVER EXPIRE.
-- Spend order is perishable-first: plus allowance -> free -> purchased, so the
-- credit a user PAID for is always the last to be spent (binding: purchased is
-- consumed only after allowance).
CREATE TABLE IF NOT EXISTS credit_ledger (
    device_id                TEXT        PRIMARY KEY,
    free_remaining           INTEGER     NOT NULL DEFAULT 5,
    plus_allowance_remaining INTEGER     NOT NULL DEFAULT 0,
    -- The IST month ('YYYY-MM') the current allowance belongs to. NULL until the
    -- user is first seen as Plus. A period roll refills the allowance to 30.
    plus_period              TEXT,
    purchased_remaining      INTEGER     NOT NULL DEFAULT 0,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- A balance can never go negative. The spend path is an optimistic-lock UPDATE
    -- that already refuses to charge an empty bucket; this constraint is the
    -- backstop that turns any arithmetic bug into a loud failure, not lost money.
    CONSTRAINT credit_ledger_nonneg CHECK (
        free_remaining >= 0
        AND plus_allowance_remaining >= 0
        AND purchased_remaining >= 0
    )
);

-- credit_purchases: one row per Play purchase token — the DURABLE anchor.
--
-- The PRIMARY KEY on purchase_token makes granting idempotent for free: a
-- replayed grant (network retry, or the same purchase re-presented after a
-- reinstall) inserts nothing and adds no credit. `device_id` records which
-- ledger the grant was applied to and is REPOINTED on reconcile so a reinstalled
-- device's Play purchase history moves the remaining purchased balance to the
-- new anonymous id. `credits_granted` is the face value at grant time, kept for
-- audit and for the support path (§5) to reason about a disputed purchase.
CREATE TABLE IF NOT EXISTS credit_purchases (
    purchase_token   TEXT        PRIMARY KEY,
    product_id       TEXT        NOT NULL,
    credits_granted  INTEGER     NOT NULL,
    device_id        TEXT        NOT NULL,
    granted_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Reconcile looks up "which device(s) own these tokens" to move a remaining
-- purchased balance to a reinstalled device — indexed for that read.
CREATE INDEX IF NOT EXISTS credit_purchases_device ON credit_purchases (device_id);
