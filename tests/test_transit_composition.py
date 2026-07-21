"""Composition gates for the transit reading, and the Sade Sati cross-check.

Two classes of check live here.

THE COMPOSITION GATES ask the question the report suites ask: does the reading
contradict its own data? A transit reading's falsifiable claims are its dates —
a passage that says it runs to October must really run to October — and its
`next_change`, which is the whole cadence argument made checkable.

THE CROSS-CHECK ASKS SOMETHING ELSE, and it is the reason this file matters
more than its size suggests. Sade Sati is the single most asked-about transit
in the Indian market and the highest-liability computation in the product: a
reader arrives already believing they are in one, having been told a date by
some other source. If our dates disagree with the published ones and we cannot
say exactly why, we are simply wrong in public about the thing we are most
visible on. So the engine's episode bounds are compared against published
sidereal (Lahiri) Saturn ingress dates for FOUR Moon signs, and the one
systematic deviation is stated and explained rather than absorbed into a
tolerance.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import pytest

import engine.transits as T
from engine.positions import SIGNS
from engine.reports import load_report_content_from_json
from engine.transits import (
    INDEPENDENT_MOVERS,
    INGRESS_EPOCH,
    WEATHER_VARIANTS,
    build_transit_reading,
    ingress_index,
    sade_sati_episodes,
    sade_sati_state,
    sign_runs,
)


@pytest.fixture(autouse=True)
def _cached_sky(monkeypatch):
    monkeypatch.setattr(T, "sidereal_positions", lru_cache(maxsize=None)(T.sidereal_positions))


@pytest.fixture(scope="module")
def corpus():
    return load_report_content_from_json(report_kind="transit")


# ═════════════════════════════════════════════════════════════════════════════
# THE SADE SATI CROSS-CHECK — the highest-liability claim in the product
# ═════════════════════════════════════════════════════════════════════════════

#: PUBLISHED REFERENCE: sidereal (Lahiri) Saturn sign-ingress dates as given by
#: Drik Panchang and AstroSage, the two sources an Indian reader is most likely
#: to have checked before opening this app. These are the dates the market
#: treats as canonical.
#:
#: Retrograde re-entries are included deliberately — they are the whole reason
#: the run model exists, and a reference that listed one ingress per sign would
#: agree with a wrong implementation.
PUBLISHED_SATURN_INGRESSES = [
    (date(2014, 11, 2), "Scorpio"),
    (date(2017, 1, 26), "Sagittarius"),
    (date(2017, 6, 21), "Scorpio"),      # retrograde re-entry
    (date(2017, 10, 26), "Sagittarius"),  # and back again
    (date(2020, 1, 24), "Capricorn"),
    (date(2022, 4, 29), "Aquarius"),
    (date(2022, 7, 12), "Capricorn"),     # retrograde re-entry
    (date(2023, 1, 17), "Aquarius"),      # and back again
    (date(2025, 3, 29), "Pisces"),
    (date(2027, 6, 3), "Aries"),
]

#: THE ONE DEVIATION, STATED. Every engine run starts EXACTLY ONE DAY after the
#: published ingress date, with no exceptions across all ten crossings above.
#:
#: It is not an error and it is not a tolerance — it is the day-boundary
#: convention, and it is forced. A published "Saturn enters Aquarius on
#: 2022-04-29" means the ingress INSTANT falls somewhere during that date. This
#: engine reads a date's transit state at 00:00 IST (`transits._instant`),
#: because that is the boundary `/v1/today` is CDN-cached to and a reader who
#: opens the app at 6 a.m. and again at 11 p.m. must not be told the sky changed
#: underneath them. At 00:00 IST on the ingress date Saturn is therefore STILL
#: in the old sign, so:
#:
#:     engine run START  ==  published ingress date + 1 day
#:     engine run END    ==  the next published ingress date, exactly
#:
#: Both halves fall out of the same convention, which is why the check below
#: asserts both. A reader comparing our dates to Drik Panchang sees at most a
#: one-day difference on a passage measured in years, and the app should
#: present the ingress date rather than the first full date if that is ever
#: found to confuse anyone.
IST_BOUNDARY_OFFSET = timedelta(days=1)


def test_saturn_ingresses_match_the_published_lahiri_reference():
    """The base fact everything about Sade Sati is derived from.

    If Saturn's sign runs are right, the Sade Sati episodes are right by
    construction — they are just those runs filtered to three houses. So this
    is checked first and separately, against the published dates rather than
    against ourselves.
    """
    runs = sign_runs("Saturn", date(2014, 1, 1), date(2028, 1, 1))
    starts = {(r.start, r.sign_name) for r in runs}
    for published, sign in PUBLISHED_SATURN_INGRESSES:
        expected = published + IST_BOUNDARY_OFFSET
        assert (expected, sign) in starts, (
            f"published Saturn -> {sign} on {published} implies an engine run "
            f"starting {expected}; engine has "
            f"{sorted(s for s, n in starts if n == sign)}"
        )


def test_the_published_offset_is_exactly_one_day_with_no_exceptions():
    """The deviation is SYSTEMATIC, which is what makes it a convention rather
    than an accuracy problem. If a future ayanamsa or day-boundary change made
    it vary — one day here, two there — that would be drift, and this fails."""
    runs = sign_runs("Saturn", date(2014, 1, 1), date(2028, 1, 1))
    starts = sorted(r.start for r in runs if r.start > date(2014, 1, 1))
    published = sorted(p for p, _ in PUBLISHED_SATURN_INGRESSES)
    matched = [s for s in starts if s - IST_BOUNDARY_OFFSET in published]
    assert len(matched) == len(published), (
        f"matched {len(matched)} of {len(published)} published ingresses"
    )
    for s in matched:
        assert (s - IST_BOUNDARY_OFFSET) in published
        # And the end of the preceding run is the published date itself.
        prev = [r for r in runs if r.end == s - timedelta(days=1)]
        assert len(prev) == 1
        assert prev[0].end == s - IST_BOUNDARY_OFFSET


#: Sade Sati bounds for four Moon signs, derived from the published ingresses
#: above by the classical definition (Saturn over the 12th, 1st and 2nd from
#: the natal Moon). Stated as PUBLISHED dates; the engine's bounds are the
#: published start + 1 day and the published end exactly, per the convention.
#:
#: Four signs, not three: Sagittarius and Pisces are the two cases the audit
#: measured as market-breaking (a detaching episode and a short dip that is not
#: Sade Sati), and Capricorn and Aquarius are ordinary passages included as
#: controls — a check that only ever ran on the interesting cases would not
#: prove the ordinary ones are right.
PUBLISHED_SADE_SATI = {
    # Moon sign      12th enters      2nd leaves      full passage?
    "Sagittarius": (date(2014, 11, 2), date(2022, 4, 29)),
    "Capricorn":   (date(2017, 10, 26), date(2025, 3, 29)),
    "Aquarius":    (date(2020, 1, 24), date(2027, 6, 3)),
    "Pisces":      (date(2023, 1, 17), date(2029, 8, 8)),
}


@pytest.mark.parametrize("sign_name", sorted(PUBLISHED_SADE_SATI))
def test_sade_sati_full_passages_match_the_published_reference(sign_name):
    """THE CLAIM WITH THE MOST DOWNSIDE IN THE PRODUCT, checked against the
    sources a reader will have checked.

    Note what is being compared: the bounds of the FULL passage, selected by
    `is_full_passage`. The detached runs around it are deliberately not folded
    in — that is the entire point of the run model, and the next three tests
    check them individually.
    """
    ms = SIGNS.index(sign_name)
    pub_start, pub_end = PUBLISHED_SADE_SATI[sign_name]
    episodes = sade_sati_episodes(ms, date(2010, 1, 1), date(2035, 1, 1))
    full = [e for e in episodes if e.is_full_passage]
    assert len(full) == 1, [(e.start, e.end, e.is_full_passage) for e in episodes]
    e = full[0]
    assert e.start == pub_start + IST_BOUNDARY_OFFSET, (
        f"{sign_name}: engine {e.start}, published {pub_start} (+1 expected)"
    )
    assert e.end == pub_end, f"{sign_name}: engine {e.end}, published {pub_end}"
    # And it is the length the market expects a Sade Sati to be.
    assert 6.0 <= e.days / 365.25 <= 8.5, e.days


def test_the_sagittarius_episode_detaches_and_the_reading_says_resuming():
    """CASE ONE: an episode that detaches, end to end through composition.

    Moon in Sagittarius: the full passage ends 2022-04-29 and Saturn RETURNS
    2022-07-13 to 2023-01-17. An app publishing "start + 7.5 years" tells this
    reader the hard period ended in April and then goes silent when it resumes
    ten weeks later — the failure that destroys trust permanently.

    So the check runs past the maths and into the copy: on a date inside the
    tail the reading must select `resuming`, which is authored to say the
    passage is BACK rather than that it is beginning.
    """
    ms = SIGNS.index("Sagittarius")
    eps = sade_sati_episodes(ms, date(2010, 1, 1), date(2035, 1, 1))
    assert len(eps) == 2
    main, tail = eps
    assert main.is_full_passage and not tail.is_full_passage
    assert (tail.start - main.end).days > 1, "the gap is what makes them two episodes"
    assert tail.start == date(2022, 7, 13) and tail.end == date(2023, 1, 17)

    inside_tail = sade_sati_state(ms, date(2022, 10, 1))
    assert inside_tail is not None
    assert inside_tail["key"] == "resuming"
    assert inside_tail["is_full_passage"] is False
    assert inside_tail["episode_start"] == "2022-07-13"

    # And between the two episodes the reader is in NO Sade Sati at all — the
    # gap is real and must be reported as one.
    assert sade_sati_state(ms, date(2022, 6, 1)) is None


def test_the_virgo_phases_recur_and_every_recurrence_is_authored():
    """CASE TWO: phases are not monotone.

    Moon in Virgo runs 12, 1, 12, 1, 2, 1, 2 in ONE episode, because Saturn
    retrogrades back across each boundary. Copy keyed on "you have entered the
    setting phase" must survive saying it twice without contradicting itself —
    which is why the sade_sati cells are keyed by the phase run the reader is
    IN, recomputed per date, rather than by how far through the episode they
    are.
    """
    ms = SIGNS.index("Virgo")
    eps = sade_sati_episodes(ms, date(2036, 1, 1), date(2044, 1, 1))
    main = max(eps, key=lambda e: e.days)
    seq = [p.house for p in main.phases]
    assert seq == [12, 1, 12, 1, 2, 1, 2], seq

    # Every phase run resolves to a key, including the repeats, and a repeated
    # house resolves to the SAME key both times — the copy is stable.
    keys = []
    for p in main.phases:
        mid = p.start + (p.end - p.start) // 2
        st = sade_sati_state(ms, mid)
        assert st is not None, (p.house, p.start, p.end)
        keys.append(st["key"])
    assert keys == ["rising", "peak", "rising", "peak", "setting", "peak", "setting"]


def test_the_pisces_dip_is_not_called_a_sade_sati():
    """CASE THREE: a short dip that satisfies the naive predicate.

    Moon in Pisces has a 74-day episode from 2022-04-30 to 2022-07-12 —
    Saturn crossing into Aquarius (the 12th) and retrograding straight back
    out — eight months before the real 6.5-year passage begins. Calling that
    Sade Sati would frighten someone about a fortnight of sky.

    It resolves to `brief`, NOT to `resuming`: no full passage precedes it. The
    distinction is the whole reason both keys exist, and it is directional —
    `resuming` looks backward to a passage that happened, `brief` says the
    thing the reader has heard about is not this.

    (docs/REPORTS.md § 6.5 quotes this as "73-day, 2022-04-29 to 2022-07-11".
    Those are the pre-boundary-convention dates; at the 00:00 IST boundary this
    module reads by, it is 74 days from 2022-04-30. Recorded here rather than
    silently re-stated — the doc is corrected in the same commit.)
    """
    ms = SIGNS.index("Pisces")
    eps = sade_sati_episodes(ms, date(2020, 1, 1), date(2031, 1, 1))
    dip = [e for e in eps if e.days < 120]
    assert len(dip) == 1, [(e.start, e.end, e.days) for e in eps]
    d = dip[0]
    assert d.start == date(2022, 4, 30) and d.end == date(2022, 7, 12)
    assert d.days == 74
    assert not d.is_full_passage and len(d.phases) == 1

    st = sade_sati_state(ms, date(2022, 6, 1))
    assert st is not None
    assert st["key"] == "brief", "a short dip must not be sold as the long passage"
    assert st["episode_days"] == 74


def test_a_reader_outside_any_episode_gets_no_sade_sati_block():
    """The common case, and it must be silence rather than reassurance — a
    "you are not in Sade Sati" line is still a line about Sade Sati, and it
    teaches every reader to worry about the next one."""
    ms = SIGNS.index("Cancer")
    assert sade_sati_state(ms, date(2026, 7, 21)) is None


# ═════════════════════════════════════════════════════════════════════════════
# INGRESS INDEX — the rotation driver, and the week_index bug seen coming
# ═════════════════════════════════════════════════════════════════════════════

def test_ingress_index_advances_by_exactly_one_per_ingress():
    """The property that makes it usable as a rotation driver at all, and the
    exact analogue of `week_index` advancing by 1 per week."""
    day = date(2026, 1, 1)
    prev = ingress_index(day)
    changes = 0
    while day < date(2029, 1, 1):
        day += timedelta(days=1)
        cur = ingress_index(day)
        assert cur - prev in (0, 1), f"{day}: jumped {cur - prev}"
        if cur > prev:
            changes += 1
            # An increment must coincide with a real sign change.
            moved = [
                b for b in INDEPENDENT_MOVERS
                if T.sign_of(b, day) != T.sign_of(b, day - timedelta(days=1))
            ]
            assert moved, f"{day}: index advanced with no mover changing sign"
        prev = cur
    assert changes > 10, f"only {changes} ingresses in 3 years — work-list too thin"


def test_ingress_index_is_absolute_not_merely_monotone():
    """THE week_index ORIGIN BUG, PINNED BEFORE IT CAN HAPPEN.

    src/report.ts once computed `week_index` from days-since-Unix-epoch. It
    advanced by exactly 1 per week, exactly as the engine's `toordinal() // 7`
    does, so every self-consistency property held ON BOTH SIDES — and the two
    implementations still selected different copy, because they started from
    different origins. Only agreement on an ABSOLUTE value catches that.

    The Worker derives this number by COUNTING transit_ingress rows rather than
    by recomputing runs, so the two can only agree if they share an origin.
    That origin is asserted here as a fixed date and again, against the seeded
    span, in `test_ingress_epoch_matches_the_seeder`.
    """
    assert INGRESS_EPOCH == date(2000, 1, 1)
    assert ingress_index(INGRESS_EPOCH) == 0, "the epoch itself counts nothing"
    # A specific absolute value, so a changed origin fails loudly rather than
    # continuing to increment correctly from the wrong place.
    assert ingress_index(date(2026, 7, 21)) == 79


def test_ingress_epoch_matches_the_seeder():
    """The engine counts runs from INGRESS_EPOCH; the Worker counts rows in a
    table the seeder fills from its own start date. Two origins that both
    advance by 1 per ingress but begin in different places is precisely the bug
    above, so the equality is asserted rather than commented."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "aura_migrate", Path(__file__).resolve().parent.parent / "db" / "migrate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.INGRESS_EPOCH == INGRESS_EPOCH
    assert mod.INGRESS_END > date(2040, 1, 1), "the seeded span must outlast the app"


def test_seven_consecutive_states_draw_seven_distinct_weather_lines(corpus):
    """The rotation guarantee, by the same argument the weekly corpus's 17
    openings make: `ingress_index` advances by exactly 1 per ingress, so seven
    consecutive configurations take seven consecutive indices and cannot
    collide mod 7.

    This is the ONLY rotated cell in the transit corpus, and it is rotated
    because `weather` is a three-class claim over ~37 states per decade — a
    reader meets `demanding` some sixteen times in ten years. Everything else
    recurs once per sidereal period and needs no rotation at all.
    """
    ms = 3
    seen: list[str] = []
    day = date(2026, 1, 1)
    last_state = None
    while day < date(2032, 1, 1) and len(seen) < WEATHER_VARIANTS:
        state = tuple(
            (p.body, p.house) for p in sorted(T.active_passages(ms, day), key=lambda p: p.body)
        )
        if state != last_state:
            reading = build_transit_reading(ms, day, corpus)
            seen.append(reading["weather_line"])
            last_state = state
        day += timedelta(days=1)
    assert len(seen) == WEATHER_VARIANTS
    assert len(set(seen)) == WEATHER_VARIANTS, "consecutive states repeated a weather line"


# ═════════════════════════════════════════════════════════════════════════════
# THE READING — determinism, and not contradicting its own data
# ═════════════════════════════════════════════════════════════════════════════

def test_the_reading_is_byte_identical_inside_one_configuration(corpus):
    """THE CADENCE ARGUMENT, MADE A TEST.

    Two dates inside the same standing configuration compose the same reading,
    apart from the fields that are genuinely per-date (`date`,
    `days_remaining`, and `phase` where a third boundary falls between them).
    That is CORRECT, not a defect: the claim has not changed, so the words must
    not either. It is also exactly why transit is not issued on a calendar —
    a weekly transit report would ship this same payload a dozen times running.
    """
    a = build_transit_reading(3, date(2026, 7, 21), corpus)
    b = build_transit_reading(3, date(2026, 7, 28), corpus)
    assert a["weather_line"] == b["weather_line"]
    assert a["ingress_index"] == b["ingress_index"]
    assert a["next_change"] == b["next_change"]
    assert [p["line"] for p in a["passages"]] == [p["line"] for p in b["passages"]]
    # Determinism proper: same inputs, identical object.
    assert build_transit_reading(3, date(2026, 7, 21), corpus) == a


def test_next_change_is_the_day_after_the_first_passage_ends(corpus):
    """The reading's expiry, and its only self-referential claim. If this is
    wrong the client caches a stale configuration past an ingress — the one
    failure mode an ingress-cadence artefact has."""
    for ms in (0, 5, 11):
        r = build_transit_reading(ms, date(2027, 3, 1), corpus)
        ends = [date.fromisoformat(p["end"]) for p in r["passages"]]
        assert r["next_change"] == (min(ends) + timedelta(days=1)).isoformat()
        # And the configuration really does differ on that date.
        change = date.fromisoformat(r["next_change"])
        before = build_transit_reading(ms, change - timedelta(days=1), corpus)
        after = build_transit_reading(ms, change, corpus)
        assert [(p["body"], p["house"]) for p in before["passages"]] != [
            (p["body"], p["house"]) for p in after["passages"]
        ]


def test_the_reading_never_contradicts_its_own_dates(corpus):
    """A passage that names a start and an end must really be standing on the
    asked-for date, and its stated remaining days must be arithmetic on those
    dates — the transit analogue of the weekly report's anchor assertions."""
    for ms in range(12):
        on = date(2027, 3, 1)
        r = build_transit_reading(ms, on, corpus)
        assert len(r["passages"]) == len(INDEPENDENT_MOVERS)
        for p in r["passages"]:
            start = date.fromisoformat(p["start"])
            end = date.fromisoformat(p["end"])
            assert start <= on <= end
            assert p["days_remaining"] == (end - on).days
            assert p["days"] == (end - start).days + 1
            assert p["phase"] == T.phase_of(start, end, on)
            assert p["supportive"] == (p["house"] in T.SUPPORTIVE_HOUSES[p["body"]])


def test_ketu_is_rendered_at_rahu_plus_six_and_carries_no_authored_line(corpus):
    """Ketu is a position, not a claim. It appears in the payload because
    readers look for it, and it carries no `line` because its house is a
    function of Rahu's — authoring one would be duplication dressed as
    coverage."""
    for ms in (0, 4, 9):
        r = build_transit_reading(ms, date(2026, 7, 21), corpus)
        rahu = next(p for p in r["passages"] if p["body"] == "Rahu")
        assert (r["ketu"]["sign"] - rahu["sign"]) % 12 == 6
        assert (r["ketu"]["house"] - rahu["house"]) % 12 == 6
        assert "line" not in r["ketu"]
        assert not any(p["body"] == "Ketu" for p in r["passages"])


def test_the_reading_refuses_an_out_of_range_moon_sign(corpus):
    """404-rather-than-guess, at the composition layer. 9 of 27 nakshatras
    straddle a sign boundary, so a caller without a stored Moon sign genuinely
    cannot have one inferred — and a guess would be wrong for a third of
    readers on the product's most confidently-worded screen."""
    for bad in (-1, 12, 27):
        with pytest.raises(ValueError):
            build_transit_reading(bad, date(2026, 7, 21), corpus)


def test_every_moon_sign_composes_a_complete_reading(corpus):
    """Coverage: no (moon_sign, date) pair may hit a missing corpus cell. The
    36 passage cells and 9 phase cells must between them cover every
    configuration the sky can produce."""
    day = date(2026, 1, 1)
    seen_houses = set()
    while day < date(2032, 1, 1):
        for ms in range(12):
            r = build_transit_reading(ms, day, corpus)
            assert r["weather_line"] and r["next_change"]
            for p in r["passages"]:
                assert p["line"] and p["phase_line"]
                seen_houses.add((p["body"], p["house"]))
        day += timedelta(days=61)
    # Over six years every mover is seen in several houses; this is a coverage
    # floor, not a claim that all 36 cells are reachable in that span (Saturn
    # visits ~3 signs in six years).
    assert len(seen_houses) >= 20, seen_houses
