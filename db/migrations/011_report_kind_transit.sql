-- transit: a third report_kind, and the widened key_type CHECK it needs.
--
-- WHY THIS TABLE AND NOT A dasha_content SIBLING. docs/REPORTS.md § 6.1 found
-- that transit is structurally a PERIOD reading, not a range aggregate: it
-- reads no daily_guidance row, aggregates nothing, and is keyed by a (mover,
-- relative-position) pair dated by an externally computed timeline — which is
-- dasha_content's shape, not a report's. That finding is recorded and it
-- stands. It is not, however, an argument about storage.
--
-- What the table choice actually governs is the VERSIONING MECHANICS, and
-- there the decision is forced by 010's own reasoning. The cross-kind gate now
-- runs three ways — weekly x monthly x transit (tests/test_report_cross_kind.py)
-- — so the corpora are gated as ONE set. A dasha_content sibling would put
-- that comparison across two tables behind two activation markers, which makes
-- "transit v1 beside weekly v2, a pairing no gate ever saw" an expressible
-- state. That is precisely the state 010 exists to make unreachable. One
-- marker is worth more than taxonomic tidiness; transit's dasha-like structure
-- governs its COMPOSITION code (engine/transits.py, its own cadence, its own
-- rotation rule), not its storage.
--
-- KEY TYPES ARE DISJOINT FROM THE RANGE-REPORT SET. weekly and monthly share
-- shape|turn|standing|close because both are range aggregates with the same
-- four movements. Transit has different movements because it makes a different
-- kind of claim:
--
--   'weather'    → key is supported|mixed|demanding; payload {lines: [...]}
--                  the count over the movers — the only second-order feature a
--                  transit reading has (§ 6.4). Occupies the slot weekly's
--                  'shape' openings hold.
--   'passage'    → key is '<mover>.<house>' (3 movers x 12 houses = 36);
--                  payload {lines: [...]}. The per-item judgment slot, the
--                  analogue of 'standing'. Ketu is absent by design: its house
--                  is always Rahu's + 6, so it is a position to render and not
--                  a claim to author.
--   'phase'      → key is '<mover>.<early|middle|late>' (9); payload
--                  {lines: [...]}. The ONLY within-passage variation the data
--                  supports (§ 6.8) — computed from the real run length.
--   'sade_sati'  → key is rising|peak|setting|resuming|brief (5); payload
--                  {lines: [...]}. See engine/transits.py on why 'resuming'
--                  and 'brief' exist: episodes detach and short dips are not
--                  Sade Sati, and copy that conflates them is the single most
--                  damaging thing this product could publish.
--
-- Because they are disjoint, widening the CHECK cannot collide with an
-- existing row: no transit key_type can ever be mistaken for a weekly one, and
-- the primary key already carries report_kind (010) so the namespaces are
-- separate regardless.
--
-- VARIANT COUNTS ARE NOT COPIED FROM THE RANGE REPORTS, and that is the
-- load-bearing difference. A weekly cell recurs every 52 weeks and a monthly
-- every 12 months, so both need a rotation coprime with their cadence.
-- Transit's cadence is a PLANETARY PERIOD: a reader returns to a given
-- (mover, house) cell once per that mover's sidereal period — Jupiter's 11.9
-- years is the shortest — so consecutive distinctness is free and a rotation
-- would be actively wrong, changing the words while the claim stands still
-- (§ 3 rejects that by name as decorative variety). Cells are therefore
-- authored at ONE line each, EXCEPT 'weather', whose three classes recur every
-- ingress (~37 states per decade) and which alone carries a rotation, driven
-- by the ingress count rather than by any calendar. See engine/transits.py
-- WEATHER_VARIANTS.
--
-- Versions stay additive and marker-based (active_content, 007). No
-- max(version) anywhere — the live version is recorded intent, never inferred,
-- and the single 'report_content' marker now moves all THREE kinds at once.

ALTER TABLE report_content
    DROP CONSTRAINT IF EXISTS report_content_report_kind_check;

ALTER TABLE report_content
    ADD CONSTRAINT report_content_report_kind_check
    CHECK (report_kind IN ('weekly', 'monthly', 'transit'));

-- The key_type CHECK is an inline (unnamed) constraint from 009, so it carries
-- a generated name. Dropped by that generated name — Postgres names an inline
-- column CHECK '<table>_<column>_check'.
ALTER TABLE report_content
    DROP CONSTRAINT IF EXISTS report_content_key_type_check;

ALTER TABLE report_content
    ADD CONSTRAINT report_content_key_type_check
    CHECK (key_type IN (
        -- weekly + monthly: the four movements of a range-aggregate report
        'shape', 'turn', 'standing', 'close',
        -- transit: the four movements of a passage reading
        'weather', 'passage', 'phase', 'sade_sati'
    ));
