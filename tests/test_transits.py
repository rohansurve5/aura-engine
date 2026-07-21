"""Gates for the gochara layer — the facts the transit design rests on.

Every assertion here corresponds to a claim made in `engine/transits.py`'s
docstrings or in docs/REPORTS.md § the transit audit. The point is that the
design's load-bearing measurements cannot rot silently: if a future change to
the ayanamsa, the node convention or the day boundary moves them, these fail.

THE CLASS OF CHECK THAT IS NEW HERE. The report gates ask "does the copy
contradict its own data?". These ask a question one level earlier: **is the
data shaped the way the design claims it is?** The transit design was chosen
over a range-aggregate design because the state changes every ~98 days, and it
models runs rather than start-plus-duration because retrograde re-entry is
real. Both are empirical claims about the sky, and both are pinned below.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import pytest

import engine.transits as T
from engine.positions import SIGNS
from engine.transits import (
    INDEPENDENT_MOVERS,
    MOVERS,
    SADE_SATI_HOUSES,
    house_from_moon,
    phase_of,
    sade_sati_episodes,
    sign_of,
    sign_runs,
    weather,
)
from engine.vimshottari import NAKSHATRAS


@pytest.fixture(autouse=True)
def _cached_sky(monkeypatch):
    """Memoise the ephemeris across the module. Every call here is a pure
    function of (body, date), so caching changes nothing except the runtime of
    the several thousand daily samples the measurement gates take."""
    monkeypatch.setattr(T, "sidereal_positions", lru_cache(maxsize=None)(T.sidereal_positions))


# ── counting from the Moon sign ──────────────────────────────────────────────

def test_the_moon_sign_itself_is_the_first_house():
    """The classical convention, and the reason gochara needs no ascendant."""
    for ms in range(12):
        assert house_from_moon(ms, ms) == 1


def test_house_counting_is_forward_inclusive_and_wraps():
    assert house_from_moon(1, 0) == 2          # next sign is the 2nd
    assert house_from_moon(11, 0) == 12        # previous sign is the 12th
    assert house_from_moon(0, 11) == 2         # wraps across Pisces → Aries
    for ms in range(12):
        assert sorted(house_from_moon(s, ms) for s in range(12)) == list(range(1, 13))


def test_house_counting_rejects_an_out_of_range_sign():
    with pytest.raises(ValueError):
        house_from_moon(12, 0)
    with pytest.raises(ValueError):
        house_from_moon(0, -1)


def test_nakshatra_index_cannot_determine_the_moon_sign():
    """THE DELIVERY CONSTRAINT, pinned as arithmetic.

    The rest of the product is keyed by `natalNakshatraIndex` (0-26). Gochara
    needs the Moon SIGN, and 9 of the 27 nakshatras straddle a sign boundary —
    each is 13°20' against a 30° sign, so 4 padas of 3°20' do not nest inside
    one sign. For a third of readers the sign is genuinely not recoverable
    from the index, which is why `/v1/natal` returns `moon_sign`, why
    `UserProfile.natalMoonSign` stores it, and why anything transit-shaped
    must 404 rather than guess when it is missing.
    """
    straddlers = []
    for n in range(27):
        signs = {(4 * n + pada) // 9 for pada in range(4)}
        if len(signs) > 1:
            straddlers.append(NAKSHATRAS[n])
    assert len(straddlers) == 9, straddlers
    # Named, so a change to the catalogue is visible rather than just a count.
    assert straddlers == [
        "Krittika", "Mrigashira", "Punarvasu", "Uttara Phalguni", "Chitra",
        "Vishakha", "Uttara Ashadha", "Dhanishta", "Purva Bhadrapada",
    ]


# ── what is modelled, and what is deliberately not ───────────────────────────

def test_only_the_slow_movers_are_modelled():
    """Mars and everything faster is cut, not forgotten. Asking for one is an
    error rather than a silently wrong reading at the wrong timescale."""
    assert set(MOVERS) == {"Saturn", "Jupiter", "Rahu", "Ketu"}
    for fast in ("Mars", "Sun", "Mercury", "Venus", "Moon"):
        with pytest.raises(ValueError):
            sign_of(fast, date(2026, 1, 1))


def test_ketu_is_always_six_houses_from_rahu():
    """Why Ketu is in MOVERS but not INDEPENDENT_MOVERS: it is a position to
    render and not a claim to author. Ketu is defined as Rahu + 180°, so this
    is true by construction — pinned so that a future switch to a different
    node convention cannot quietly make the authored corpus wrong."""
    assert "Ketu" not in INDEPENDENT_MOVERS
    day = date(2026, 1, 1)
    for _ in range(40):
        r = sign_of("Rahu", day)
        k = sign_of("Ketu", day)
        assert (k - r) % 12 == 6, day
        day += timedelta(days=91)


def test_rahu_is_always_retrograde_so_no_copy_may_key_on_it():
    """The mean node moves backwards by construction. A "Rahu is retrograde"
    line would be true in every reading ever composed — the Barnum failure in
    its purest mechanical form — so the flag is meaningful only for Saturn and
    Jupiter."""
    day = date(2026, 1, 1)
    for _ in range(40):
        assert T.is_retrograde("Rahu", day) is True, day
        assert T.is_retrograde("Ketu", day) is True, day
        day += timedelta(days=91)


def test_saturn_and_jupiter_retrograde_state_actually_varies():
    """The other half: the flag must not be constant for the bodies that do
    use it, or it carries no information there either."""
    for body in ("Saturn", "Jupiter"):
        seen = {T.is_retrograde(body, date(2026, 1, 1) + timedelta(days=30 * i))
                for i in range(24)}
        assert seen == {True, False}, f"{body}: {seen}"


# ── runs, and the retrograde re-entry trap ───────────────────────────────────

def test_runs_tile_the_window_without_gap_or_overlap():
    """Structural: whatever the sky does, the runs partition the window."""
    start, end = date(2026, 1, 1), date(2031, 1, 1)
    for body in INDEPENDENT_MOVERS:
        runs = sign_runs(body, start, end)
        assert runs[0].start == start
        assert runs[-1].end == end
        for a, b in zip(runs, runs[1:], strict=False):
            assert b.start == a.end + timedelta(days=1), (body, a, b)
            assert a.sign != b.sign, f"{body}: adjacent runs share a sign"


def test_retrograde_re_entry_produces_a_separate_run_never_a_merge():
    """THE CORRECTNESS TRAP, on the measured case.

    Saturn enters Aries 2027-06-04, retrogrades back to Pisces 2027-10-21, and
    re-enters Aries 2028-02-24. A model that recorded one ingress date per
    sign would report a single unbroken Aries passage from 2027-06-04 and be
    wrong by four months about a period it is telling someone how to live
    through.

    (Dates are at this module's 00:00 IST boundary and sit one day later than
    a noon-UTC sample would put them — which is exactly why the convention is
    stated in `_instant` rather than left implicit.)
    """
    runs = sign_runs("Saturn", date(2027, 1, 1), date(2029, 1, 1))
    aries = [r for r in runs if r.sign_name == "Aries"]
    assert len(aries) == 2, [(r.sign_name, r.start, r.end) for r in runs]
    assert aries[0].start == date(2027, 6, 4)
    assert aries[0].end == date(2027, 10, 20)
    assert aries[1].start == date(2028, 2, 24)
    # And the intervening Pisces run was entered backwards.
    pisces = [r for r in runs if r.sign_name == "Pisces" and r.start == date(2027, 10, 21)]
    assert len(pisces) == 1 and pisces[0].entry_retrograde is True


def test_jupiter_re_crosses_most_of_its_boundaries_within_a_decade():
    """Why the run model is not Saturn-specific. Measured 2024-2034: Jupiter
    crosses 24 boundaries and re-crosses 7 of the 12."""
    runs = sign_runs("Jupiter", date(2024, 1, 1), date(2034, 1, 1))
    from collections import Counter
    repeated = {s: n for s, n in Counter(r.sign for r in runs).items() if n > 1}
    assert len(repeated) >= 7, repeated


# ── the measurement that chose the design ────────────────────────────────────

def _state_runs(moon_sign: int, start: date, end: date) -> list[tuple[date, date]]:
    day, prev, out, cur = start, None, [], None
    while day <= end:
        st = tuple(house_from_moon(sign_of(b, day), moon_sign) for b in INDEPENDENT_MOVERS)
        if st != prev:
            if cur is not None:
                out.append((cur, day - timedelta(days=1)))
            cur, prev = day, st
        day += timedelta(days=1)
    out.append((cur, end))
    return out


def test_the_transit_state_changes_far_too_slowly_to_be_a_periodic_report():
    """THE FINDING THAT SET THE ARCHITECTURE.

    A weekly report has a new range every 7 days and a monthly every ~30. The
    slow-mover state for one Moon sign holds for a median of ~3 months and, in
    the measured decade, for as long as a year. So a "transit report" issued
    on a calendar cadence would ship a byte-identical payload to the previous
    issue most of the time, and any rotation applied to hide that would be
    changing the words while the claim stood still — decorative variety, which
    docs/REPORTS.md § determinism rejects by name.

    If this ever fails because the state moves faster, the range-aggregate
    design becomes worth revisiting. Until then it is settled empirically.

    Measured here over the same window the docstrings quote (Moon in Aries,
    Saturn/Jupiter/Rahu, 2026-2036, daily): 37 states, median 89 days, mean 99,
    longest 375.
    """
    runs = _state_runs(0, date(2026, 1, 1), date(2036, 1, 1))
    lengths = sorted((b - a).days + 1 for a, b in runs)
    median = lengths[len(lengths) // 2]
    assert median > 60, f"median state length {median}d — faster than the design assumes"
    assert max(lengths) > 300, f"max state length {max(lengths)}d — no year-long holds"
    # And it is nowhere near a weekly or monthly cadence: a reader on a weekly
    # cadence would receive the SAME claim a dozen times running.
    assert median > 12 * 7
    assert median > 2 * 30


# ── phase: the only within-passage variation ─────────────────────────────────

def test_phase_splits_a_passage_into_exact_thirds():
    start, end = date(2026, 1, 1), date(2026, 1, 30)  # 30 days
    assert phase_of(start, end, date(2026, 1, 1)) == "early"
    assert phase_of(start, end, date(2026, 1, 10)) == "early"
    assert phase_of(start, end, date(2026, 1, 11)) == "middle"
    assert phase_of(start, end, date(2026, 1, 20)) == "middle"
    assert phase_of(start, end, date(2026, 1, 21)) == "late"
    assert phase_of(start, end, date(2026, 1, 30)) == "late"


def test_phase_is_computed_from_the_real_run_not_a_nominal_duration():
    """A 22-day interrupted passage gets all three phases, exactly as an
    800-day one does — so an interrupted passage is described honestly rather
    than as a fragment of a passage that never happened."""
    short = (date(2027, 6, 3), date(2027, 6, 24))
    assert {phase_of(*short, short[0] + timedelta(days=d)) for d in range(22)} == {
        "early", "middle", "late"
    }


def test_phase_rejects_a_date_outside_the_passage():
    with pytest.raises(ValueError):
        phase_of(date(2026, 1, 1), date(2026, 1, 30), date(2026, 2, 1))


# ── Sade Sati: the highest-liability computation ─────────────────────────────

SAGITTARIUS = SIGNS.index("Sagittarius")
VIRGO = SIGNS.index("Virgo")
PISCES = SIGNS.index("Pisces")


def test_sade_sati_episodes_detach_so_it_cannot_be_start_plus_duration():
    """MEASURED: for Moon in Sagittarius the main episode ends 2022-04-28 and
    Saturn RETURNS 2022-07-12 to 2023-01-17.

    An app publishing "start date + 7.5 years" tells this reader the hard
    period ended in April and is then silent when it resumes ten weeks later.
    That is the failure this whole run-based model exists to prevent, and it
    is why nothing in engine/transits.py merges across a gap.
    """
    eps = sade_sati_episodes(SAGITTARIUS, date(2015, 1, 1), date(2024, 1, 1))
    assert len(eps) == 2, [(e.start, e.end) for e in eps]
    main, tail = eps
    assert main.end == date(2022, 4, 29)
    assert tail.start == date(2022, 7, 13)
    assert tail.end == date(2023, 1, 17)
    assert (tail.start - main.end).days > 1, "the gap is what makes them two episodes"
    # The tail is a single setting-phase run, NOT a second Sade Sati: the copy
    # must be able to say "it resumes" without saying "it begins again".
    assert main.is_full_passage and not tail.is_full_passage
    assert [p.house for p in tail.phases] == [2]


def test_sade_sati_phases_are_not_a_monotone_twelfth_first_second():
    """MEASURED: Moon in Virgo runs 12, 1, 12, 1, 2, 1, 2 in ONE episode.

    Copy keyed on "you have entered the setting phase" must survive saying it
    twice, because Saturn retrogrades back into the peak and out again. The
    classical three-phase story is a summary of the passage, not a description
    of its day-to-day order.
    """
    eps = sade_sati_episodes(VIRGO, date(2036, 1, 1), date(2044, 1, 1))
    main = max(eps, key=lambda e: e.days)
    seq = [p.house for p in main.phases]
    assert len(seq) == 7, seq
    assert seq == [12, 1, 12, 1, 2, 1, 2], seq
    assert any(seq[i] == seq[i + 2] for i in range(len(seq) - 2)), "a phase recurs"


def test_a_short_boundary_dip_is_not_a_sade_sati():
    """MEASURED: Moon in Pisces has a 73-day episode in 2022 that satisfies the
    naive predicate months before the real 6.5-year passage begins.

    Calling that Sade Sati would frighten someone about a fortnight of sky.
    `is_full_passage` is what keeps the seven-and-a-half-year copy off it.
    """
    eps = sade_sati_episodes(PISCES, date(2022, 1, 1), date(2031, 1, 1))
    short = [e for e in eps if e.days < 120]
    assert short, [(e.start, e.end, e.days) for e in eps]
    for e in short:
        assert not e.is_full_passage
        assert len(e.phases) == 1
    full = [e for e in eps if e.is_full_passage]
    assert len(full) == 1
    assert full[0].days > 6 * 365, full[0].days


def test_a_full_sade_sati_passage_is_about_seven_and_a_half_years():
    """The sanity check on the whole model: whatever the run structure, a
    complete passage must come out near Saturn's 2.5 years per sign x 3.

    Episodes touching a window edge are EXCLUDED, not fudged. `sign_runs`
    clips at the window and says so, so an episode that starts on the first
    day or ends on the last is a fragment of unknown true length — measuring
    it here would be grading the window rather than the sky. (Dropping the
    edges is what took Capricorn's clipped 5.42y and Pisces' clipped 6.14y out
    of this check; both are partial passages, not short ones.)
    """
    lo, hi = date(1970, 1, 1), date(2010, 1, 1)
    checked = 0
    for ms in range(12):
        for e in sade_sati_episodes(ms, lo, hi):
            if not e.is_full_passage or e.start == lo or e.end == hi:
                continue
            years = e.days / 365.25
            checked += 1
            assert 6.0 <= years <= 8.5, (SIGNS[ms], e.start, e.end, years)
    assert checked >= 8, f"only {checked} complete passages measured — work-list too thin"


def test_sade_sati_only_ever_names_the_twelfth_first_and_second():
    eps = sade_sati_episodes(0, date(2015, 1, 1), date(2035, 1, 1))
    assert eps
    for e in eps:
        for p in e.phases:
            assert p.house in SADE_SATI_HOUSES
            assert p.body == "Saturn"


# ── weather: the only second-order claim ─────────────────────────────────────

def test_weather_classes_are_all_reachable_and_none_dominates():
    """The check the weekly `even` class failed. Measured over 12 signs x 6
    years: every class occurs, and none is so rare that its copy is dead.

    Observed: demanding 43.5% / mixed 46.4% / supported 10.1%.
    """
    from collections import Counter
    seen: Counter[str] = Counter()
    for ms in range(12):
        day = date(2026, 1, 1)
        while day < date(2032, 1, 1):
            seen[weather(T.active_passages(ms, day))] += 1
            day += timedelta(days=30)
    assert set(seen) == {"supported", "mixed", "demanding"}, dict(seen)
    total = sum(seen.values())
    for cls, n in seen.items():
        assert n / total > 0.05, f"{cls} is effectively dead copy: {n}/{total}"


def test_adding_rahu_as_a_third_voter_would_kill_a_class_either_way():
    """WHY `WEATHER_MOVERS` IS TWO, pinned as the measurement that decided it.

    This is the `even`-class lesson applied BEFORE authoring rather than after:
    with Rahu voting, unanimity makes `supported` unreachable (1.8%) and
    majority makes `mixed` unreachable (3 voters cannot split evenly). Either
    way a third of the corpus would be copy no real sky can select. The gate
    exists so that a future "let's include Rahu, it's a major transit" is
    argued against data rather than taste.
    """
    from collections import Counter
    counts: Counter[int] = Counter()
    for ms in range(12):
        day = date(2026, 1, 1)
        while day < date(2032, 1, 1):
            active = T.active_passages(ms, day, ("Saturn", "Jupiter", "Rahu"))
            counts[sum(1 for p in active if p.supportive)] += 1
            day += timedelta(days=30)
    total = sum(counts.values())
    assert counts[3] / total < 0.05, "unanimity over three would be reachable after all"
    # A majority rule over three voters can never return a tie, so `mixed`
    # would have no source at all.
    assert 3 % 2 == 1


def test_weather_is_a_count_over_the_set_not_a_property_of_any_member():
    """What makes it second-order at all: the same passage sits in readings
    with different weather, so no single passage determines it."""
    p_good = T.Passage("Jupiter", 5, 0, date(2026, 1, 1), date(2026, 6, 1), False, True)
    p_bad = T.Passage("Saturn", 12, 0, date(2026, 1, 1), date(2026, 6, 1), False, False)
    p_sat_good = T.Passage("Saturn", 11, 0, date(2026, 1, 1), date(2026, 6, 1), False, True)
    p_jup_bad = T.Passage("Jupiter", 12, 0, date(2026, 1, 1), date(2026, 6, 1), False, False)
    assert weather([p_good, p_sat_good]) == "supported"
    assert weather([p_bad, p_jup_bad]) == "demanding"
    assert weather([p_good, p_bad]) == "mixed"
    assert weather([p_sat_good, p_jup_bad]) == "mixed"


def test_weather_refuses_to_judge_on_a_partial_set():
    """A missing voter must be an error, never a silent one-mover verdict —
    that is how "Jupiter is well placed" would come to be published as
    "supported" with Saturn simply absent from the count."""
    only_jupiter = [T.Passage("Jupiter", 5, 0, date(2026, 1, 1), date(2026, 6, 1), False, True)]
    with pytest.raises(ValueError):
        weather([])
    with pytest.raises(ValueError):
        weather(only_jupiter)
    # Rahu present but a voter missing is still a refusal.
    with pytest.raises(ValueError):
        weather(only_jupiter + [
            T.Passage("Rahu", 3, 0, date(2026, 1, 1), date(2026, 6, 1), True, True)
        ])


# ── determinism ──────────────────────────────────────────────────────────────

def test_the_whole_layer_is_deterministic():
    """Same inputs → identical objects, the property every composition system
    in this repo holds. No now(), no randomness anywhere in the path."""
    args = (0, date(2026, 1, 1), date(2029, 1, 1))
    assert T.passages(*args) == T.passages(*args)
    assert sade_sati_episodes(*args) == sade_sati_episodes(*args)
    assert sign_runs("Saturn", args[1], args[2]) == sign_runs("Saturn", args[1], args[2])


def test_active_passages_report_true_bounds_not_the_window_edge():
    """A passage that began years before the asked-for date must report its
    real start, or every reading would claim its passages started today."""
    on = date(2029, 6, 15)
    for p in T.active_passages(0, on):
        assert p.start <= on <= p.end
    starts = {p.start for p in T.active_passages(0, on)}
    assert any(s < on - timedelta(days=200) for s in starts), starts


def test_every_active_passage_has_a_house_and_a_judgment():
    for ms in (0, 5, 11):
        active = T.active_passages(ms, date(2027, 3, 1))
        assert {p.body for p in active} == set(INDEPENDENT_MOVERS)
        for p in active:
            assert 1 <= p.house <= 12
            assert isinstance(p.supportive, bool)
            assert p.supportive == (p.house in T.SUPPORTIVE_HOUSES[p.body])
