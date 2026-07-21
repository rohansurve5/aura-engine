"""Gochara — transits of the slow movers, reckoned from the natal Moon sign.

SCOPE, AND WHY THIS IS NOT engine/reports.py
============================================

`engine/reports.py` composes RANGE AGGREGATES: it holds N consecutive
`daily_guidance` rows and states second-order features of the range (where the
strong days fall, which week carries the month). This module reads **no**
`daily_guidance` row at all. It answers a different question entirely:

    daily guidance   one DATE      → what is today like?
    weekly report    a RANGE       → where did the strong days fall?
    monthly report   a RANGE       → which week carried the month?
    dasha content    one PERIOD    → what is this era about?
    THIS MODULE      a PASSAGE     → which slow mover is standing where,
                                     counted from your Moon sign, and for
                                     how much longer?

MEASURED, NOT ASSUMED (docs/REPORTS.md § the transit audit): the tuple of
slow-mover positions for one Moon sign changes on average every **98 days**,
with a measured maximum of **374 days unchanged** (Saturn/Jupiter/Rahu/Ketu,
2026-2036, daily scan). A weekly or monthly artefact built on this would be
byte-identical to the previous issue for months at a stretch. So a transit
reading is NOT a periodic report — it is a **period reading on an irregular
clock**, structurally a sibling of `dasha_content`, and its natural cadence is
the INGRESS, never the calendar.

WHAT WE CAN AND CANNOT COMPUTE
==============================

The engine has sidereal longitudes for all nine grahas at any instant
(`engine/positions.py`, Swiss Ephemeris, Lahiri VP285) and **no ascendant, no
houses, no aspects, no divisional charts**. Classical gochara is reckoned from
the **Moon sign**, not the ascendant — which is exactly the quantity we compute
and cross-validate — so it needs no new astrology maths. That is the whole
reason transit is buildable when career/marriage/finance are not.

The Moon sign is a required input and is NOT derivable from the natal nakshatra
index: **9 of the 27 nakshatras straddle a sign boundary** (Krittika,
Mrigashira, Punarvasu, Uttara Phalguni, Chitra, Vishakha, Uttara Ashadha,
Dhanishtha, Purva Bhadrapada), so a third of readers cannot have their sign
inferred from the index the rest of the product is keyed by. `/v1/natal`
already returns `moon_sign` and `UserProfile.natalMoonSign` already stores it;
anything transit-shaped must key on THAT and 404 rather than guess when it is
absent. `test_transits.py::test_nakshatra_index_cannot_determine_the_moon_sign`
pins the fact so nobody later "optimises" the sign away.

CUT RATHER THAN FAKED. Only the slow movers are modelled: Saturn, Jupiter and
the Rahu/Ketu axis. Mars crosses a sign every ~45 days (66 crossings measured
in 10 years) and the Sun every 30 — at that rate a "transit reading" is a daily
card wearing a longer name, and Mars in particular is the Mangal Dosha fear
vector. Ketu is carried but is **not independent**: Ketu is always exactly six
houses from Rahu (asserted over all 360 measured states), so it adds a position
to render and no information to author.

RETROGRADE RE-ENTRY IS THE CORRECTNESS TRAP
===========================================

A slow mover does not enter a sign once and leave once. Measured 2024-2034:
Saturn crosses 8 sign boundaries, 2 of them backwards, and re-crosses
Pisces→Aries twice; Jupiter crosses 24, 7 of them backwards, and re-crosses
**seven** of its boundaries. So "Saturn enters Aries on 2027-06-03" is not a
fact about a passage — Saturn leaves again on 2027-10-20 and returns on
2028-02-24.

Everything here is therefore modelled as **runs of contiguous occupancy**, never
as a start date plus a nominal duration. `sign_runs` is the primitive and it
emits a separate run per contiguous occupancy; nothing in this module ever
merges them or interpolates across a gap.

The consequence for Sade Sati is the sharpest version of this and is the single
highest-liability computation in the product — see `sade_sati_episodes`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .positions import SIGNS, sidereal_positions

#: The movers slow enough for a passage to be a claim about a season of life
#: rather than about a fortnight. Rahu and Ketu move together; see the module
#: docstring on why Mars and everything faster is deliberately absent.
MOVERS = ("Saturn", "Jupiter", "Rahu", "Ketu")

#: The movers that carry INDEPENDENT information. Ketu is omitted because its
#: house is always Rahu's + 6 — pinned by
#: `test_ketu_is_always_six_houses_from_rahu`, which is what makes authoring
#: Ketu copy separately a duplication rather than a gap.
INDEPENDENT_MOVERS = ("Saturn", "Jupiter", "Rahu")

#: A date's transit state is the state at **00:00 IST** of that date — the same
#: boundary `/v1/today` is CDN-cached to, so a reader who opens the app at
#: 6 a.m. and again at 11 p.m. is never told the sky changed under them. IST is
#: UTC+5:30, so 00:00 IST is 18:30 UTC on the PREVIOUS day.
_IST_OFFSET = timedelta(hours=5, minutes=30)

#: Classical gochara: the houses **counted from the Moon sign** in which each
#: mover's transit is traditionally read as supportive. Everything else is
#: `demanding`. This is a DOCUMENTED HEURISTIC subject to astrologer review,
#: exactly as the v1 scoring rules are, and it moves into a seeded, tunable
#: table (the `score_rules` precedent) at the same time the transit corpus
#: lands — it is here rather than in a seed file only because no transit copy
#: ships yet, and a table nothing reads is a table nobody maintains.
#:
#: NOTE THE VOCABULARY. `supportive` / `demanding`, never `benefic`/`malefic`
#: and never `good`/`bad`. A demanding passage is weather to dress for; the
#: voice specs forbid reading it as a verdict, and `BANNED_WORDS` already
#: carries `malefic` and `inauspicious`.
SUPPORTIVE_HOUSES = {
    "Saturn": frozenset({3, 6, 11}),
    "Jupiter": frozenset({2, 5, 7, 9, 11}),
    "Rahu": frozenset({3, 6, 10, 11}),
    "Ketu": frozenset({3, 6, 11}),
}

#: Saturn over the 12th, 1st and 2nd from the natal Moon — the ~7.5-year
#: passage, and the single most asked-about transit in the Indian market.
SADE_SATI_HOUSES = (12, 1, 2)

#: The classical names of Sade Sati's three phases, by house from the Moon.
#: Deliberately plain-English glosses rather than transliterations: the voice
#: spec bans astrological jargon in user-visible copy.
SADE_SATI_PHASES = {12: "rising", 1: "peak", 2: "setting"}

#: Saturn's ~2.5-year passage over the 4th or the 8th — "dhaiya", the other
#: Saturn period the market asks about. Modelled for the same reason Sade Sati
#: is: readers arrive already believing they are in one, and the honest move is
#: to compute it accurately rather than to leave the question to worse sources.
DHAIYA_HOUSES = (4, 8)


@dataclass(frozen=True)
class Run:
    """One contiguous occupancy of one sign by one body.

    `entry_retrograde` records whether the body backed INTO this sign rather
    than advancing into it, which is the difference between a passage
    beginning and a passage resuming — a distinction the copy must be able to
    make, because "Saturn is back in your 12th" is a different sentence from
    "Saturn enters your 12th".
    """

    body: str
    sign: int          # 0-11, index into positions.SIGNS
    start: date        # first date the body is in this sign (inclusive)
    end: date          # last date the body is in this sign (inclusive)
    entry_retrograde: bool

    @property
    def sign_name(self) -> str:
        return SIGNS[self.sign]

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class Passage:
    """A `Run` read from a particular natal Moon sign: the same sky fact, now
    relative to one reader."""

    body: str
    house: int         # 1-12, counted from the natal Moon sign
    sign: int
    start: date
    end: date
    entry_retrograde: bool
    supportive: bool

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class SadeSatiEpisode:
    """One unbroken stretch of Saturn over the 12th/1st/2nd, with the phase
    runs inside it. See `sade_sati_episodes` for why this is a list of runs
    rather than a start date and a duration."""

    start: date
    end: date
    phases: tuple[Passage, ...]

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def is_full_passage(self) -> bool:
        """True when this episode contains all three phases.

        A short detached episode — Saturn dipping back across a boundary for a
        few months — is NOT a Sade Sati in the sense a reader means, and copy
        that treats it as one would be alarming a person about nothing.
        """
        return {p.house for p in self.phases} == set(SADE_SATI_HOUSES)


def _instant(day: date) -> datetime:
    """The UTC instant at which `day`'s transit state is read: 00:00 IST."""
    return datetime(day.year, day.month, day.day) - _IST_OFFSET


def sign_of(body: str, day: date) -> int:
    """The sidereal sign index (0-11) `body` occupies at 00:00 IST on `day`."""
    if body not in MOVERS:
        raise ValueError(f"{body!r} is not a modelled mover; expected one of {MOVERS}")
    return int(sidereal_positions(_instant(day))[body].longitude // 30)


def is_retrograde(body: str, day: date) -> bool:
    """Whether `body` is in retrograde motion at 00:00 IST on `day`.

    The mean lunar node is retrograde by construction — Rahu and Ketu are
    ALWAYS retrograde and their measured 10-year crossing count is 6 forward-
    less crossings out of 6. So a "Rahu is retrograde" claim carries no
    information and no copy may be keyed on it; the flag exists for Saturn and
    Jupiter, where it is a real, intermittent state.
    """
    return sidereal_positions(_instant(day))[body].retrograde


def house_from_moon(sign: int, moon_sign: int) -> int:
    """The house (1-12) that `sign` occupies counted from `moon_sign`.

    Counting is inclusive and forward through the zodiac, so the Moon sign
    itself is the 1st — the classical convention, and the reason a Moon-sign
    reading needs no ascendant.
    """
    if not 0 <= sign <= 11 or not 0 <= moon_sign <= 11:
        raise ValueError(f"signs are 0-11, got sign={sign} moon_sign={moon_sign}")
    return (sign - moon_sign) % 12 + 1


def sign_runs(body: str, start: date, end: date) -> list[Run]:
    """Contiguous occupancy runs of `body` over [start, end], in date order.

    ONE RUN PER CONTIGUOUS OCCUPANCY — retrograde re-entry into a sign already
    visited produces a SEPARATE run, never an extension of the earlier one and
    never a merge across the gap. That is the whole point: a passage that was
    interrupted is a different fact from one that was not, and the measured
    data is full of them (Jupiter re-crosses 7 of its 12 boundaries within a
    decade).

    The first and last runs are CLIPPED by the window and are therefore not
    known to be complete passages; callers that care must widen the window.
    """
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")

    runs: list[Run] = []
    day = start
    cur_sign = sign_of(body, day)
    cur_start = day
    cur_retro = is_retrograde(body, day)

    while day < end:
        day += timedelta(days=1)
        s = sign_of(body, day)
        if s != cur_sign:
            runs.append(Run(body, cur_sign, cur_start, day - timedelta(days=1), cur_retro))
            # Backing into a sign (retrograde on the crossing day) is recorded
            # on the run being ENTERED, which is where the copy needs it.
            cur_retro = is_retrograde(body, day)
            cur_sign, cur_start = s, day
    runs.append(Run(body, cur_sign, cur_start, end, cur_retro))
    return runs


def passages(moon_sign: int, start: date, end: date,
             bodies: tuple[str, ...] = INDEPENDENT_MOVERS) -> list[Passage]:
    """Every slow-mover passage over [start, end], read from `moon_sign`.

    Ordered by (start, body) so the result is stable and two runs of the same
    window are byte-identical — the determinism property every composition
    system in this repo holds.
    """
    out: list[Passage] = []
    for body in bodies:
        for run in sign_runs(body, start, end):
            house = house_from_moon(run.sign, moon_sign)
            out.append(
                Passage(
                    body=body,
                    house=house,
                    sign=run.sign,
                    start=run.start,
                    end=run.end,
                    entry_retrograde=run.entry_retrograde,
                    supportive=house in SUPPORTIVE_HOUSES[body],
                )
            )
    return sorted(out, key=lambda p: (p.start, p.body))


def active_passages(moon_sign: int, on: date,
                    bodies: tuple[str, ...] = INDEPENDENT_MOVERS) -> list[Passage]:
    """The passages standing on one date — the reading's `standing` movement.

    The window is widened by four years on each side before the runs are cut,
    so a passage that began before `on` reports its true start rather than the
    window's edge. Four years clears Saturn's longest measured single-sign
    occupancy with room to spare.
    """
    lo, hi = on - timedelta(days=4 * 366), on + timedelta(days=4 * 366)
    return [p for p in passages(moon_sign, lo, hi, bodies) if p.start <= on <= p.end]


def phase_of(start: date, end: date, on: date) -> str:
    """Where inside a passage `on` falls: `early`, `middle` or `late`.

    THIS IS THE ONLY WITHIN-PASSAGE VARIATION THE DATA SUPPORTS. A passage's
    house does not change for a median of 88 days, so without a position claim
    a reader who opens the screen in month one and month five sees the same
    sentence. Thirds are exact and computed from the real run length — not
    from a nominal duration — so a 22-day interrupted passage and an 800-day
    one are both described honestly.
    """
    if not start <= on <= end:
        raise ValueError(f"{on} is outside the passage {start}..{end}")
    span = (end - start).days + 1
    elapsed = (on - start).days
    third = elapsed * 3 // span
    return ("early", "middle", "late")[min(third, 2)]


def sade_sati_episodes(moon_sign: int, start: date, end: date) -> list[SadeSatiEpisode]:
    """Saturn over the 12th/1st/2nd from `moon_sign`, as EPISODES OF RUNS.

    THE HIGHEST-LIABILITY COMPUTATION IN THE PRODUCT, and the reason it is
    modelled this way rather than as a start date plus 7.5 years:

    * **Episodes detach.** Measured for Moon in Sagittarius, the main episode
      ends 2022-04-28 — and Saturn returns for a further 189 days from
      2022-07-12 to 2023-01-17. An app that published "your Sade Sati ended in
      April 2022" would be wrong, and wrong in the direction that destroys
      trust: it told someone a hard thing was over and it was not.
    * **Phases recur.** The classical 12th → 1st → 2nd progression is not
      monotone in real sky. Moon in Virgo measures SEVEN phase runs in one
      episode (12, 1, 12, 1, 2, 1, 2) because Saturn retrogrades back across
      each boundary. Copy keyed on "you are now in the setting phase" must be
      able to say it a second time without contradicting itself.
    * **Short episodes are not Sade Sati.** A 73-day dip across a boundary
      (Moon in Pisces, 2022-04-29 to 2022-07-11) satisfies the naive predicate
      and is not the thing anyone means by the word. `is_full_passage`
      separates them, and no copy that names the seven-and-a-half years may be
      selected for an episode that is not one.

    Episodes are separated by any gap at all; adjacent phase runs (Saturn
    moving 12th → 1st with no day outside) stay in one episode. The window is
    used as given — an episode touching an edge is clipped, and callers that
    need true bounds must widen it, exactly as `sign_runs` documents.
    """
    wanted = {(moon_sign - 1) % 12: 12, moon_sign: 1, (moon_sign + 1) % 12: 2}

    phase_runs: list[Passage] = []
    for run in sign_runs("Saturn", start, end):
        house = wanted.get(run.sign)
        if house is None:
            continue
        phase_runs.append(
            Passage(
                body="Saturn",
                house=house,
                sign=run.sign,
                start=run.start,
                end=run.end,
                entry_retrograde=run.entry_retrograde,
                supportive=house in SUPPORTIVE_HOUSES["Saturn"],
            )
        )

    episodes: list[SadeSatiEpisode] = []
    bucket: list[Passage] = []
    for p in phase_runs:
        if bucket and (p.start - bucket[-1].end).days > 1:
            episodes.append(SadeSatiEpisode(bucket[0].start, bucket[-1].end, tuple(bucket)))
            bucket = []
        bucket.append(p)
    if bucket:
        episodes.append(SadeSatiEpisode(bucket[0].start, bucket[-1].end, tuple(bucket)))
    return episodes


def dhaiya_runs(moon_sign: int, start: date, end: date) -> list[Passage]:
    """Saturn over the 4th or the 8th from `moon_sign` — the ~2.5-year dhaiya.

    Same run semantics as everything else here: contiguous occupancies, never
    merged across a retrograde exit. Returned as `Passage` so it carries the
    house, which is what distinguishes the 4th from the 8th — a distinction
    the copy needs and the market conflates.
    """
    runs = []
    for run in sign_runs("Saturn", start, end):
        house = house_from_moon(run.sign, moon_sign)
        if house in DHAIYA_HOUSES:
            runs.append(
                Passage(
                    body="Saturn",
                    house=house,
                    sign=run.sign,
                    start=run.start,
                    end=run.end,
                    entry_retrograde=run.entry_retrograde,
                    supportive=house in SUPPORTIVE_HOUSES["Saturn"],
                )
            )
    return runs


#: The movers that VOTE on the weather. Saturn and Jupiter only — and the
#: exclusion of Rahu is a measurement, not a preference.
#:
#: Measured, 12 signs x 6 years, monthly samples, counting movers in
#: supportive houses:
#:
#:     Saturn + Jupiter, unanimous   demanding 43.5% / mixed 46.4% / supported 10.1%
#:     + Rahu,           unanimous   supported collapses to 1.8%  → dead copy
#:     + Rahu,           majority    `mixed` disappears entirely (3 is odd)
#:
#: Adding a third voter destroys the classification either way: unanimity makes
#: `supported` unreachable, and majority makes `mixed` unreachable. That is the
#: `even`-class lesson from the weekly taxonomy arriving a second time — copy
#: no real sky can select is copy that should not be authored — so the third
#: voter is cut instead. Rahu/Ketu still RENDERS as a standing passage; it just
#: does not vote.
WEATHER_MOVERS = ("Saturn", "Jupiter")


def weather(active: list[Passage]) -> str:
    """`supported` | `mixed` | `demanding` — the one claim no single passage
    carries, and therefore the only genuinely second-order feature a transit
    reading has.

    This is a COUNT over `WEATHER_MOVERS`, not a synthesis of them. The product
    has no aspect computation and no yoga logic, so it cannot say what
    Saturn-in-the-12th "means together with" Jupiter-in-the-5th, and authoring
    pair copy would be inventing a claim the maths does not support. Counting
    how many movers stand in supportive houses is a fact about the set that is
    true of no member of it, and it is all the concurrency the data will
    honestly bear.
    """
    voters = [p for p in active if p.body in WEATHER_MOVERS]
    missing = set(WEATHER_MOVERS) - {p.body for p in voters}
    if missing:
        raise ValueError(f"weather needs a passage for each of {WEATHER_MOVERS}; missing {missing}")
    good = sum(1 for p in voters if p.supportive)
    if good == len(voters):
        return "supported"
    if good == 0:
        return "demanding"
    return "mixed"
