"""The WEEKLY/MONTHLY report engine. v1 ships the weekly report.

SCOPE — this module is NOT "all reports". It is the engine for reports that are
RANGE AGGREGATES of daily_guidance rows: weekly today, monthly when its corpus
is authored (report_content key_type rows are discriminated by `report_kind`,
migration 010). A yearly report is deliberately NOT built here — averaging 365
days of a 9-fold tara cycle is statistically empty (docs/REPORTS.md § the
audit), so yearly is a Vimshottari composition over dasha_content, structurally
a sibling of the dasha timeline, not of this engine.

WHAT A REPORT IS (the design question this module answers)
==========================================================

The three composition systems that already exist each have a different unit:

    daily guidance   one DATE      → "what is today like?"
    dasha content    one PERIOD    → "what is this era about?"   (static per lord)
    identity content one PERSON    → "what are you like?"        (static per star)

A report is none of these. It spans a RANGE, and the naive reading — compose
each day, concatenate — produces N readings rather than one report. What makes
it a report is that its claims are about the range *as a whole*, and every such
claim is a SECOND-ORDER feature that is not present in any single day:

    trend      does the span rise, fall, crest, dip, jitter, or sit flat?
    spread     is it a dramatic week or an even one?
    position   WHERE inside the window does the high fall — early, middle, late?
    aggregate  which life-area leads across the whole span, which lags?
    swing      which area MOVES most (often more interesting than which is highest)

None of these can be read off one day's payload. They exist only once you hold
seven days at once, which is precisely why a report is a distinct artefact and
not a longer card.

THE ARC. Range features alone would still be a list — of statistics rather than
of days. A report also needs an *ordering with a beginning, a turn and a close*.
This module composes four movements, always in this order:

    1. SHAPE     what this week IS as a whole              (from trend + spread)
    2. TURN      the moment inside it that changes          (from peak/trough position)
    3. STANDING  which area leads, which lags, which holds  (from aggregate ranking)
    4. CLOSE     what to carry out of it                    (from trend)

plus ANCHORS — specific dated days the reader can act on, carrying the peak and
the trough. Anchors are what make the report checkable: `test_report_anchors.py`
asserts the named peak day really is the highest-energy day in the window, so a
report cannot claim a shape its own data contradicts.

DETERMINISM. Same (week_start, natal_index, rules, content) → byte-identical
report. No now(), no randomness. Variant selection is a pure function of the
epoch week index and the natal index — see `_variant` and docs/REPORTS.md.

NON-REPETITION is a harder problem here than in the daily system, for two
compounding reasons documented in docs/REPORTS.md § determinism:

  * a reader sees only ~52 reports a year, but each is long, so repetition is
    far more visible per sample than in a two-sentence daily card; and
  * aggregates REGRESS TO THE MEAN — the longer the range, the more every span
    averages out to the same middling numbers, so the underlying data really is
    more similar week-to-week than day-to-day.

The answer is three-layered: shape is data-driven (a front-loaded week genuinely
should not read like a scattered one), variant rotation uses mutually coprime
prime periods (17/7/5, none sharing a factor with 52), and anchors name real
dates and real areas that differ every single time regardless of which cells
were drawn.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from .daily import build_daily_sky
from .scoring import guidance_for_nakshatra
from .vimshottari import NAKSHATRAS

WEEK_DAYS = 7

#: Variant-list lengths, one per movement. Mutually coprime primes, and none
#: shares a factor with 52 (weeks per year) — so no movement can lock to the
#: calendar and no two movements can advance in step. lcm = 595 weeks.
#:
#: Openings were 11 and are now 17, closing the reports-#1-and-#12 collision
#: (11 guarantees only 11 distinct consecutive reports). 13 — the obvious next
#: prime — is the one prime that CANNOT work here: 13 divides 52, so a 13-slot
#: rotation advances 52 ≡ 0 (mod 13) across a 52-week year and hands every
#: anniversary week the same opening. 17 is the smallest count above 12 that is
#: coprime with 52, 7 and 5 at once.
OPENING_VARIANTS = 17
TURN_VARIANTS = 7
STANDING_VARIANTS = 5
CLOSE_VARIANTS = 5

#: The six shape classes, in classification precedence order (see `shape_of`).
#:
#: THESE DESCRIBE A RHYTHM, NOT A TREND, AND THAT WAS A CORRECTION.
#:
#: The first draft of this module classified weeks as rising / falling /
#: cresting / dipping / volatile / flat — the vocabulary any human reaches for
#: when asked to describe a span. `test_all_six_shapes_occur_across_a_realistic_span`
#: then failed with `{'volatile', 'cresting'}`: across 26 weeks x 6 natal stars,
#: real sky data produced only two of the six, and four sixths of the corpus was
#: unreachable copy that every distinctness gate still passed.
#:
#: The cause is in the scoring rules, not the classifier. Daily energy is driven
#: by tara, whose nine energies are 55/88/32/78/42/82/30/80/90 — deliberately
#: alternating — and tara advances one step per day as the Moon crosses one
#: nakshatra per day. So the energy series is a SAWTOOTH with a ~50-point
#: day-to-day swing and a weekly spread that measured 48-70 in every week
#: sampled. There is no weekly trend in this data. A report claiming one would
#: be describing an artefact of smoothing, which is exactly the kind of
#: unfalsifiable claim the whole product is positioned against.
#:
#: What IS really there is WHERE the strong days fall. That is a distribution
#: claim rather than a trend claim, it is true of the data, and it is more
#: actionable anyway: "your two best days are Thursday and Friday" is something
#: a reader can put in a calendar, where "the week rises" is not.
SHAPES = ("even", "split", "front", "back", "centre", "scattered")

#: The five turn kinds — where the single best day sits, or (`whiplash`) the
#: fact that the best and worst days are adjacent, which in a sawtooth is both
#: common and genuinely worth warning about.
TURN_KINDS = ("peak_early", "peak_mid", "peak_late", "whiplash", "no_turn")

#: The three roles an area can hold in one week's standing.
ROLES = ("leads", "lags", "steadies")

#: The thirds the week is split into for the distribution test. Deliberately
#: 2/3/2 rather than equal: the middle is where "midweek" actually means
#: something to a reader, and the edges are what they plan around.
FRONT_DAYS = (0, 1)
CENTRE_DAYS = (2, 3, 4)
BACK_DAYS = (5, 6)

#: How many of the week's days count as "strong" for the distribution test.
STRONG_DAYS = 3

# Classification thresholds. Named constants rather than inline numbers: they
# are the entire definition of what each class means, and
# tests/test_report_composition.py pins each at both edges of its boundary.
EVEN_SPREAD = 12       # max-min below this and no day stands out at all
CLUSTER_MIN = 2        # strong days in one third for it to be that third's week


def week_start(day: date) -> date:
    """The Monday of `day`'s ISO week — the canonical start of a weekly report."""
    return day - timedelta(days=day.weekday())


def week_index(monday: date) -> int:
    """A monotone epoch week number. Advances by exactly 1 per week, which is
    what lets the coprime variant periods walk cleanly instead of jumping."""
    return monday.toordinal() // WEEK_DAYS


def _variant(count: int, wk: int, natal_index: int, stride: int, salt: int = 0) -> int:
    """Deterministic variant index.

    `wk * stride` advances every week; `natal_index` de-syncs readers so two
    people never receive the same skeleton in the same week; `salt` de-syncs
    movements from each other. `stride` is coprime with `count` in every call
    site, so consecutive weeks always advance rather than sometimes repeating.
    """
    return (wk * stride + natal_index * 3 + salt) % count


def _mean(values: list[int]) -> float:
    return sum(values) / len(values)


def _round_half_up(x: float) -> int:
    """Round half away from zero for positive x — i.e. JS `Math.round`.

    Deliberately NOT Python's `round()`, which is banker's (half-to-even):
    over a 4-7 day week mean or a 28-31 day month mean an exact .5 is
    reachable, and the two rules disagree there. Every rounded field in a
    report payload goes through this, so the Worker's `Math.round` and the
    engine cannot drift on a tie. Energies are 0-100, so the positive-only
    simplification is safe and is asserted in the composition gates.
    """
    return int(x + 0.5)


def strong_days(energies: list[int]) -> list[int]:
    """Indices of the `STRONG_DAYS` highest-energy days, earliest first.

    Ties break toward the earlier day (`-i` in the sort key), so the result is
    stable and a reader is never told to wait for a later day that scores the
    same as one already available.
    """
    ranked = sorted(range(len(energies)), key=lambda i: (energies[i], -i), reverse=True)
    return sorted(ranked[:STRONG_DAYS])


def shape_of(energies: list[int]) -> str:
    """Classify a week by WHERE its strong days fall — see `SHAPES`.

    Precedence is fixed and each step is a strictly more specific claim than the
    next. `even` is the floor: under `EVEN_SPREAD` no day stands out enough for
    a distribution claim to mean anything, so making one would be inventing
    structure. `split` outranks the single-third classes because "strong at both
    ends" is more specific than "strong at one end" when both are true.
    `scattered` is the honest default — a week whose strong days genuinely do
    not cluster gets told so, rather than being forced into the nearest third.
    """
    if len(energies) != WEEK_DAYS:
        raise ValueError(f"a weekly shape needs {WEEK_DAYS} energies, got {len(energies)}")

    if max(energies) - min(energies) < EVEN_SPREAD:
        return "even"

    strong = set(strong_days(energies))
    front = len(strong & set(FRONT_DAYS))
    centre = len(strong & set(CENTRE_DAYS))
    back = len(strong & set(BACK_DAYS))

    if front >= 1 and back >= 1 and centre == 0:
        return "split"
    if front >= CLUSTER_MIN:
        return "front"
    if back >= CLUSTER_MIN:
        return "back"
    if centre >= CLUSTER_MIN:
        return "centre"
    return "scattered"


def turn_of(energies: list[int], shape: str) -> str:
    """Which `TURN_KINDS` moment this week hinges on.

    An `even` week is the one shape with no turn to report — naming a "pivot" in
    a week whose spread is under twelve points would be inventing drama the data
    does not contain, which is the single easiest way for a report to read as
    generated. `no_turn` exists so that case is authored honestly rather than
    forced into a peak framing.

    `whiplash` outranks the peak positions because when the best and worst days
    are adjacent, THAT is the fact worth telling a reader — it is the practical
    consequence of the sawtooth documented on `SHAPES`, and it changes what they
    should schedule across those two days.
    """
    if shape == "even":
        return "no_turn"
    peak_i = energies.index(max(energies))
    trough_i = energies.index(min(energies))
    if abs(peak_i - trough_i) == 1:
        return "whiplash"
    if peak_i <= 1:
        return "peak_early"
    if peak_i >= 5:
        return "peak_late"
    return "peak_mid"


def area_standing(area_scores: dict[str, list[int]]) -> dict[str, str]:
    """area → role, from the whole week's scores rather than any one day.

    Exactly one area `leads` (highest weekly mean), one `lags` (lowest), and one
    `steadies` (smallest spread across the week, i.e. the area a reader can rely
    on). Ties break on `sorted()` order of the area name so the result is stable
    across runs; the remaining areas carry no role and are not named in the
    report, because a report that mentions all six areas equally has ranked
    nothing and is a list again.
    """
    names = sorted(area_scores)
    means = {a: _mean(area_scores[a]) for a in names}
    spreads = {a: max(area_scores[a]) - min(area_scores[a]) for a in names}

    leads = max(names, key=lambda a: (means[a], -names.index(a)))
    lags = min(names, key=lambda a: (means[a], names.index(a)))
    remaining = [a for a in names if a not in (leads, lags)] or names
    steadies = min(remaining, key=lambda a: (spreads[a], remaining.index(a)))

    out = {leads: "leads", steadies: "steadies"}
    out[lags] = "lags"  # written last: if lags == leads (all-equal week), lags wins
    return out


def build_weekly_report(
    natal_index: int,
    monday: date,
    rules: dict,
    content: dict,
) -> dict:
    """The weekly report payload for one natal nakshatra and one ISO week.

    Pure function of its arguments. `content` is the report corpus as returned
    by `load_report_content_from_json` / `_from_db` — shape → openings, turn →
    lines, '<area>.<role>' → lines, close → lines.
    """
    if monday.weekday() != 0:
        raise ValueError(f"a weekly report must start on a Monday, got {monday}")

    days = [monday + timedelta(days=i) for i in range(WEEK_DAYS)]
    skies = [build_daily_sky(d) for d in days]
    guidance = [guidance_for_nakshatra(natal_index, s, rules) for s in skies]

    energies = [g["energy"] for g in guidance]
    labels = rules["areas"]["labels"]
    order = rules["areas"]["order"]
    area_scores = {a: [g["scores"][labels[a]] for g in guidance] for a in order}

    shape = shape_of(energies)
    turn = turn_of(energies, shape)
    standing = area_standing(area_scores)
    wk = week_index(monday)

    peak_i = energies.index(max(energies))
    trough_i = energies.index(min(energies))

    opening = content["shape"][shape]["openings"][
        _variant(OPENING_VARIANTS, wk, natal_index, stride=1)
    ]
    turn_line = content["turn"][turn]["lines"][
        _variant(TURN_VARIANTS, wk, natal_index, stride=3, salt=1)
    ]
    close_line = content["close"][shape]["lines"][
        _variant(CLOSE_VARIANTS, wk, natal_index, stride=2, salt=2)
    ]

    standing_lines = {}
    for i, area in enumerate(order):
        role = standing.get(area)
        if role is None:
            continue
        cell = content["standing"][f"{area}.{role}"]["lines"]
        standing_lines[labels[area]] = cell[
            _variant(STANDING_VARIANTS, wk, natal_index, stride=2, salt=3 + i)
        ]

    # Anchors carry the report's falsifiable claims: these dates ARE the
    # extremes of `energies`, asserted in tests/test_report_anchors.py. They are
    # also the strongest anti-repetition force in the whole design — two weeks
    # that draw identical cells still name different days and different areas.
    anchors = {
        "peak": {"date": days[peak_i].isoformat(), "weekday": days[peak_i].strftime("%A"),
                 "energy": energies[peak_i]},
        "trough": {"date": days[trough_i].isoformat(), "weekday": days[trough_i].strftime("%A"),
                   "energy": energies[trough_i]},
    }

    return {
        "kind": "weekly",
        "week_start": monday.isoformat(),
        "week_end": days[-1].isoformat(),
        "week_index": wk,
        "nakshatra_index": natal_index,
        "nakshatra": NAKSHATRAS[natal_index],
        "shape": shape,
        "turn": turn,
        "energies": energies,
        "energy_mean": round(_mean(energies)),
        "energy_spread": max(energies) - min(energies),
        "standing": {labels[a]: r for a, r in standing.items()},
        "anchors": anchors,
        "opening": opening,
        "turn_line": turn_line,
        "standing_lines": standing_lines,
        "close": close_line,
    }


# ═════════════════════════════════════════════════════════════════════════════
# THE MONTHLY REPORT — the same engine at month scale, NOT the weekly over 30
# days. docs/REPORTS.md § the monthly report carries the full design; the load-
# bearing decisions are summarised here because the code below enforces them.
#
# WHAT IS SECOND-ORDER AT MONTH SCALE. The weekly report's unit of claim is the
# DAY: where the strong days fall inside seven of them. Running that arithmetic
# over 30 days would produce the same kind of claim over a longer list — a
# longer report, not a different one. The features that exist at month scale
# and at no smaller scale are claims about WEEKS:
#
#     carrier    which week carries the month — the week-level distribution
#     halves     do the month's two halves genuinely differ, and which way
#     hinge      are the best and worst WEEKS adjacent — a mid-month pivot
#     standing   which area leads/lags/steadies across the whole month
#
# Candidates measured on real sky (144 months x 6 natals) and REJECTED:
#
#   * week-over-week TRAJECTORY ("the month rises") — the weekly means of a
#     month are the tara sawtooth aliased through a 7-day window (9 and 7 are
#     coprime, so the phase slides by two days each week). A monotone run of
#     4-5 such means is an artefact of that aliasing, exactly the smoothing
#     artefact the weekly taxonomy already rejected at day scale ("the week
#     rises"). Same trap, one level up; same verdict.
#   * recurring WEEKDAY patterns ("your Thursdays run strong") — real in 46% of
#     sampled months, but each weekday has only 4-5 samples against a 9-day
#     cycle, so the pattern is phase coincidence that a reader will extrapolate
#     to next month, where it will be false. A claim that is true this month
#     and invites a false generalisation fails the falsifiability bar in
#     spirit even when it passes it in letter. Recorded, not authored.
#
# WEEK-GRANULARITY IS ALSO THE CROSS-KIND DIVISION OF LABOUR. A subscriber
# reads the weekly and the monthly in the same sitting (IDENTITY.md §5 is the
# precedent: nakshatra owns what you DO, moon sign owns what you NEED). Here:
#
#     WEEKLY OWNS DAYS. MONTHLY OWNS WEEKS.
#
#     weekly   names dated days, weekday names, day-scale advice
#     monthly  names weeks and month-halves; NEVER names a day or a weekday
#
# tests/test_report_cross_kind.py makes that mechanical: monthly copy may not
# contain a day-scale token, weekly copy may not contain a month-scale token,
# and no weekly/monthly pair in the same movement may share a frame or a
# skeleton. The monthly anchors are WEEKS (their Monday dates), so the two
# reports corroborate instead of repeating: the monthly names the carrier
# week, the weekly for that week names its days.
# ═════════════════════════════════════════════════════════════════════════════

#: Monthly variant-list lengths. THE COPRIMALITY CONSTRAINT IS DERIVED FROM 12,
#: NOT COPIED FROM 52 — a monthly rotation locks to the CALENDAR YEAR, so the
#: cycle to clear is 12 (reports per year), and a count sharing a factor with
#: 12 hands some month-of-year the same cell on a short anniversary cycle.
#:
#: 13 — the one prime that could NOT work at week scale (13 divides 52) — is
#: exactly right here: gcd(13, 12) = 1, and it is the smallest count above 12
#: at all, which matters because a reader sees 12 reports a year and the
#: consecutive-distinct guarantee should outlast a full year. Anniversary
#: months advance 12 ≡ -1 (mod 13) per year, so the same calendar month
#: repeats an opening cell only after 13 years.
#:
#: 13 / 7 / 5 are pairwise coprime and each is coprime with 12, so the full
#: skeleton recurs only every lcm = 455 months (~38 years), and no movement
#: can advance in step with another. Pinned in
#: tests/test_report_monthly_composition.py.
MONTH_OPENING_VARIANTS = 13
MONTH_TURN_VARIANTS = 7
MONTH_STANDING_VARIANTS = 5
MONTH_CLOSE_VARIANTS = 5

#: The five month shapes — WHICH WEEK CARRIES THE MONTH, in classification
#: precedence order. A distribution claim over weeks, exactly as the weekly
#: shape is a distribution claim over days, and for the same reason: measured
#: on real sky there is no month-scale trend, but there really is a strongest
#: week. Distribution measured over 144 real months: core 62%, closing 15%,
#: opening 11%, twin 7%, level 4% — all five reachable, unlike the weekly
#: taxonomy's dead `even` class.
MONTH_SHAPES = ("level", "twin", "opening", "closing", "core")

#: The four month turn kinds — the month's pivot, at week granularity.
#: `hinge` (best and worst weeks adjacent — the month turns hard at one week
#: boundary) outranks the halves comparison for the same reason weekly
#: `whiplash` outranks peak position: adjacency of the extremes is the fact
#: that changes what a reader schedules. Measured: hinge 33%, steady 25%,
#: lifts 23%, settles 19%.
MONTH_TURN_KINDS = ("lifts", "settles", "hinge", "steady")

# Month-scale classification thresholds. DERIVED FROM REAL DATA, not copied
# from the weekly constants: weekly means regress toward the mean, so the
# spread of a month's weekly means (measured min 1.4, median 13.7, max 30.3)
# lives on a completely different scale from the spread of a week's daily
# energies (measured 48-70). Each is pinned at both edges in
# tests/test_report_monthly_composition.py.
LEVEL_SPREAD = 6     # weekly-mean spread below this → no week stands out
TWIN_MARGIN = 2      # top two weeks within this margin → a genuine near-tie
HALF_MARGIN = 4      # half means must differ by this for a lifts/settles claim
FIRST_HALF_LAST_DAY = 15  # calendar halves: days 1-15 vs 16-end

#: An ISO week must hold this many of the month's days to be nameable in the
#: report. A 1-3 day fragment at a month edge still counts toward the halves
#: and the standing (every day of the month is aggregated), but it cannot be
#: the "carrier week" — naming a week on a 2-day sample would be the report
#: inventing a week-level claim from day-level noise. Every calendar month has
#: 4 or 5 qualifying weeks.
QUALIFYING_WEEK_MIN_DAYS = 4


def month_index(year: int, month: int) -> int:
    """A monotone epoch month number — advances by exactly 1 per month,
    including across year boundaries, which is what lets the coprime monthly
    variant periods walk cleanly. The monthly analogue of `week_index`."""
    return year * 12 + (month - 1)


def month_weeks(year: int, month: int) -> list[tuple[date, list[date]]]:
    """The month's qualifying ISO weeks: (monday, in-month days), ordered.

    Weeks are ISO weeks — the same weeks the weekly report is keyed by — so a
    monthly anchor names a week the reader can open a weekly report for. Only
    weeks holding at least `QUALIFYING_WEEK_MIN_DAYS` of the month's days
    qualify; edge fragments belong to a neighbouring month's story.
    """
    n_days = monthrange(year, month)[1]
    by_week: dict[date, list[date]] = {}
    for i in range(n_days):
        d = date(year, month, i + 1)
        by_week.setdefault(week_start(d), []).append(d)
    return [
        (monday, days)
        for monday, days in sorted(by_week.items())
        if len(days) >= QUALIFYING_WEEK_MIN_DAYS
    ]


def _argmax(values: list[float]) -> int:
    """First index of the maximum. Explicit so the tie-break (earliest week)
    is pinned and mirrored exactly by the Worker implementation."""
    best = 0
    for i, v in enumerate(values):
        if v > values[best]:
            best = i
    return best


def _argmin(values: list[float]) -> int:
    worst = 0
    for i, v in enumerate(values):
        if v < values[worst]:
            worst = i
    return worst


def month_shape_of(week_means: list[float]) -> str:
    """Classify a month by WHICH WEEK CARRIES IT — see `MONTH_SHAPES`.

    Precedence mirrors `shape_of`'s logic one level up. `level` is the floor:
    under `LEVEL_SPREAD` no week stands out and a carrier claim would invent
    structure — and unlike the weekly `even`, `level` is REACHABLE on real
    data (4% of sampled months), because weekly means regress toward the mean
    while daily energies saw across their full range. `twin` outranks the
    position classes because "two separated strong weeks" is the more specific
    claim when both are true; a near-tie between ADJACENT weeks is just a wide
    carrier and falls through to its position.
    """
    if len(week_means) < 2:
        raise ValueError(f"a month shape needs at least 2 week means, got {len(week_means)}")

    if max(week_means) - min(week_means) < LEVEL_SPREAD:
        return "level"

    best = _argmax(week_means)
    second = -1
    for i, v in enumerate(week_means):
        if i == best:
            continue
        if second == -1 or v > week_means[second]:
            second = i
    if week_means[best] - week_means[second] <= TWIN_MARGIN and abs(best - second) > 1:
        return "twin"
    if best == 0:
        return "opening"
    if best == len(week_means) - 1:
        return "closing"
    return "core"


def month_turn_of(
    week_means: list[float], first_half_mean: float, second_half_mean: float, shape: str
) -> str:
    """The month's pivot — see `MONTH_TURN_KINDS`.

    A `level` month is the one shape with no pivot to report: its weekly means
    sit within `LEVEL_SPREAD` of each other, so naming a hinge or a directional
    half would be drama the data does not contain — the month-scale version of
    `even` → `no_turn`. `hinge` (best and worst weeks adjacent) outranks the
    halves comparison; `lifts`/`settles` require the halves to differ by
    `HALF_MARGIN`, else the honest answer is `steady`.
    """
    if shape == "level":
        return "steady"
    best = _argmax(week_means)
    worst = _argmin(week_means)
    if abs(best - worst) == 1:
        return "hinge"
    if second_half_mean - first_half_mean >= HALF_MARGIN:
        return "lifts"
    if first_half_mean - second_half_mean >= HALF_MARGIN:
        return "settles"
    return "steady"


def build_monthly_report(
    natal_index: int,
    year: int,
    month: int,
    rules: dict,
    content: dict,
) -> dict:
    """The monthly report payload for one natal nakshatra and one calendar
    month. Pure function of its arguments, like `build_weekly_report`.
    `content` is the MONTHLY corpus (`load_report_content_from_json(
    report_kind="monthly")`).

    The report's claims are at WEEK granularity throughout: the anchors are
    the carrier week and the thin week (as their Monday dates — the same keys
    the weekly report is fetched by), never a single day. That is the
    division of labour with the weekly report, enforced mechanically by
    tests/test_report_cross_kind.py.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")

    n_days = monthrange(year, month)[1]
    days = [date(year, month, i + 1) for i in range(n_days)]
    skies = [build_daily_sky(d) for d in days]
    guidance = [guidance_for_nakshatra(natal_index, s, rules) for s in skies]

    energies = [g["energy"] for g in guidance]
    labels = rules["areas"]["labels"]
    order = rules["areas"]["order"]
    area_scores = {a: [g["scores"][labels[a]] for g in guidance] for a in order}

    weeks = month_weeks(year, month)
    by_day = {d: e for d, e in zip(days, energies, strict=True)}
    week_means = [_mean([by_day[d] for d in ds]) for _, ds in weeks]

    first_half = [e for d, e in zip(days, energies, strict=True) if d.day <= FIRST_HALF_LAST_DAY]
    second_half = [e for d, e in zip(days, energies, strict=True) if d.day > FIRST_HALF_LAST_DAY]
    h1, h2 = _mean(first_half), _mean(second_half)

    shape = month_shape_of(week_means)
    turn = month_turn_of(week_means, h1, h2, shape)
    standing = area_standing(area_scores)
    mi = month_index(year, month)

    carrier_i = _argmax(week_means)
    thin_i = _argmin(week_means)

    opening = content["shape"][shape]["openings"][
        _variant(MONTH_OPENING_VARIANTS, mi, natal_index, stride=1)
    ]
    turn_line = content["turn"][turn]["lines"][
        _variant(MONTH_TURN_VARIANTS, mi, natal_index, stride=3, salt=1)
    ]
    close_line = content["close"][shape]["lines"][
        _variant(MONTH_CLOSE_VARIANTS, mi, natal_index, stride=2, salt=2)
    ]

    standing_lines = {}
    for i, area in enumerate(order):
        role = standing.get(area)
        if role is None:
            continue
        cell = content["standing"][f"{area}.{role}"]["lines"]
        standing_lines[labels[area]] = cell[
            _variant(MONTH_STANDING_VARIANTS, mi, natal_index, stride=2, salt=3 + i)
        ]

    # Anchors are WEEKS. tests/test_report_monthly_composition.py asserts the
    # carrier really is the argmax of the weekly means and the thin week the
    # argmin — the monthly instance of "a report may not contradict its own
    # data". Their Monday dates are the weekly report's own keys, so the two
    # kinds corroborate rather than repeat.
    # `energy_mean` is ROUNDED wherever it is exposed, at every scale, matching
    # the weekly report — which has only ever published an integer. The raw
    # float stays internal: `week_means` above drives classification and the
    # argmax/argmin tie-breaks, so rounding here cannot move a shape, a turn or
    # an anchor. It only stops the payload publishing 70.85714285714286 to a
    # reader, which is a number no report should ever show anyone.
    anchors = {
        "carrier_week": {
            "week_start": weeks[carrier_i][0].isoformat(),
            "energy_mean": _round_half_up(week_means[carrier_i]),
        },
        "thin_week": {
            "week_start": weeks[thin_i][0].isoformat(),
            "energy_mean": _round_half_up(week_means[thin_i]),
        },
    }

    return {
        "kind": "monthly",
        "month": f"{year:04d}-{month:02d}",
        "month_start": days[0].isoformat(),
        "month_end": days[-1].isoformat(),
        "month_index": mi,
        "nakshatra_index": natal_index,
        "nakshatra": NAKSHATRAS[natal_index],
        "shape": shape,
        "turn": turn,
        "weeks": [
            {
                "week_start": monday.isoformat(),
                "days_in_month": len(ds),
                "energy_mean": _round_half_up(mean),
            }
            for (monday, ds), mean in zip(weeks, week_means, strict=True)
        ],
        "energy_mean": _round_half_up(_mean(energies)),
        # ROUNDED, consistent with every other energy figure the payload
        # publishes. These were the one exposed float left in any report, and
        # they leaked the raw mean (69.53333333333333) into a reader-facing
        # field for no gain. As with `energy_mean` and the week means, the
        # rounding is applied only at the boundary: `h1`/`h2` above drive
        # `month_turn_of`'s HALF_MARGIN comparison at full precision, so
        # rounding here cannot move a turn. `_round_half_up` rather than
        # Python's banker's `round()` so the Worker's `Math.round` cannot
        # disagree on an exact .5 — a 15-day and a 13-16 day half both reach
        # one readily.
        "half_means": {"first": _round_half_up(h1), "second": _round_half_up(h2)},
        "standing": {labels[a]: r for a, r in standing.items()},
        "anchors": anchors,
        "opening": opening,
        "turn_line": turn_line,
        "standing_lines": standing_lines,
        "close": close_line,
    }


#: The movements each report_kind is composed of. weekly and monthly share the
#: four movements of a range-aggregate report; transit's are different because
#: its claim is different — a standing configuration rather than a distribution
#: over a range (migration 011 carries the full reasoning). Declared here as
#: one mapping so the loaders, the seeder and the corpus gates cannot disagree
#: about what a kind consists of.
KEY_TYPES: dict[str, tuple[str, ...]] = {
    "weekly": ("shape", "turn", "standing", "close"),
    "monthly": ("shape", "turn", "standing", "close"),
    "transit": ("weather", "passage", "phase", "sade_sati"),
}


def load_report_content_from_json(path=None, report_kind: str = "weekly") -> dict:
    """One report_kind's corpus dict (key_type → key → payload) from the seed
    file. The v2 seed nests corpora by kind so every kind can share one version
    and one activation marker (see migrations 010 and 011)."""
    import json
    from pathlib import Path

    from .content import REPORT_SEED_PATH

    data = json.loads(Path(path or REPORT_SEED_PATH).read_text())
    corpus = data[report_kind]
    return {kt: corpus[kt] for kt in KEY_TYPES[report_kind]}


def load_report_content_from_db(conn, version: str, report_kind: str = "weekly") -> dict:
    """One report_kind's corpus for `version` from the report_content table."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key_type, key, payload FROM report_content "
            "WHERE version = %s AND report_kind = %s",
            (version, report_kind),
        )
        rows = cur.fetchall()
    if not rows:
        raise SystemExit(
            f"no report_content rows for version {version!r} kind {report_kind!r}; "
            "run db/migrate.py"
        )
    out: dict[str, dict] = {}
    for key_type, key, payload in rows:
        out.setdefault(key_type, {})[key] = payload
    return out
