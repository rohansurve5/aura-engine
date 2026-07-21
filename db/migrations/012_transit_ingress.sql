-- transit_ingress: precomputed slow-mover sign runs, seeded by this engine.
--
-- WHY A TABLE RATHER THAN IN-WORKER COMPUTATION (docs/REPORTS.md § 6.10).
-- /v1/natal had to recompute the natal Moon in-Worker with astronomy-engine,
-- because a natal position is a function of an arbitrary birth instant and
-- there is no finite set of answers to precompute. That forced a second
-- ephemeris implementation and a 1,000-birth cross-validation to gate every
-- deploy.
--
-- Transit has no such problem. The sign runs of three slow movers over a wide
-- span are a few HUNDRED rows that are the same for every user on Earth and
-- change never. A lookup needs no second implementation, so there is no drift
-- surface for the astronomy and no crossval burden for the maths — only for
-- the composition, which is ordinary arithmetic over these rows. That is a
-- strictly better trade than /v1/natal was able to take, and it is the reason
-- the Worker never links an ephemeris for this feature.
--
-- ONE ROW PER CONTIGUOUS OCCUPANCY — never a start date plus a nominal
-- duration, and never a merge across a gap. This is the correctness trap the
-- whole transit design is built around: a slow mover does not enter a sign
-- once and leave once. Measured 2024-2034, Saturn re-crosses Pisces->Aries
-- twice and Jupiter re-crosses SEVEN of its twelve boundaries. So
-- "Saturn enters Aries on 2027-06-04" is not a fact about a passage — Saturn
-- leaves again on 2027-10-20 and returns on 2028-02-24, and an app that
-- published the first date alone would be wrong by four months about a period
-- it is telling someone how to live through.
--
-- The consequence for Sade Sati is the sharpest version of this and is the
-- single highest-liability computation in the product. It is derived FROM
-- these rows (Saturn's runs over the 12th/1st/2nd from the reader's Moon
-- sign), never from a start date plus 7.5 years — see engine/transits.py
-- `sade_sati_episodes`.
--
-- `entry_retrograde` records whether the body BACKED INTO this sign rather
-- than advancing into it. It is the difference between a passage beginning and
-- a passage resuming, which is a distinction the copy has to be able to make:
-- "Saturn is back over this ground" is a different sentence from "Saturn moves
-- onto it".
--
-- SIGN, NOT HOUSE. Rows are absolute sky facts (body in sidereal sign),
-- shared by every reader. The house is computed per request by counting from
-- the reader's natal Moon sign — which is why one row set serves all twelve
-- Moon signs and why this table is cohort-level rather than per-user.
--
-- WINDOW AND REFRESH. The seeder writes a wide span (see db/migrate.py
-- INGRESS_START / INGRESS_END). Rows are idempotent upserts keyed by
-- (body, start), so re-seeding a wider span is additive and safe. The first
-- and last run of the span are CLIPPED by it and are therefore not known to be
-- complete passages; `transit_ingress_span` records the seeded bounds so a
-- reader near an edge can be refused rather than served a passage whose true
-- start or end is unknown.

CREATE TABLE IF NOT EXISTS transit_ingress (
    body             TEXT    NOT NULL CHECK (body IN ('Saturn', 'Jupiter', 'Rahu', 'Ketu')),
    sign             INTEGER NOT NULL CHECK (sign BETWEEN 0 AND 11),
    start_date       DATE    NOT NULL,
    end_date         DATE    NOT NULL,
    entry_retrograde BOOLEAN NOT NULL,
    PRIMARY KEY (body, start_date),
    CHECK (end_date >= start_date)
);

-- Lookup is always "which run is standing on this date, for these bodies".
CREATE INDEX IF NOT EXISTS transit_ingress_body_dates
    ON transit_ingress (body, start_date, end_date);

-- The seeded bounds, one row. A reading asked for a date outside these bounds
-- must be refused: outside the span there are no rows at all, and a reading
-- composed from an empty passage set would silently claim "nothing is
-- standing" — which is never true of the real sky. Kept as a table rather than
-- inferred with min()/max() over transit_ingress for the same reason
-- active_content exists: the clipped first and last runs would make an
-- inferred span wider than the span actually known to be complete.
CREATE TABLE IF NOT EXISTS transit_ingress_span (
    id         INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    start_date DATE NOT NULL,
    end_date   DATE NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
