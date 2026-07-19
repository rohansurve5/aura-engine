-- daily_guidance: 27 rows per date, one per natal nakshatra (0-26).
--
-- payload holds the v1 heuristic output: headline energy %, six life-area
-- scores, lucky colour/number/direction, good-for / avoid tags and an
-- opportunity / warning line. rules_version records which score_rules version
-- produced the row, so a rules change can be rolled out date-by-date.
--
-- Read pattern: (date, nakshatra_index) point lookup — served by the PK.
CREATE TABLE IF NOT EXISTS daily_guidance (
    date            DATE     NOT NULL,
    nakshatra_index SMALLINT NOT NULL CHECK (nakshatra_index BETWEEN 0 AND 26),
    rules_version   TEXT     NOT NULL,
    payload         JSONB    NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (date, nakshatra_index)
);
