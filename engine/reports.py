"""Period-report composition. v1: the WEEKLY report.

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

The answer is three-layered: shape is data-driven (a rising week genuinely
should not read like a flat one), variant rotation uses mutually coprime prime
periods (11/7/5, none sharing a factor with 52), and anchors name real dates and
real areas that differ every single time regardless of which cells were drawn.
"""

from __future__ import annotations

from datetime import date, timedelta

from .daily import build_daily_sky
from .scoring import guidance_for_nakshatra
from .vimshottari import NAKSHATRAS

WEEK_DAYS = 7

#: Variant-list lengths, one per movement. Mutually coprime primes, and none
#: shares a factor with 52 (weeks per year) — so no movement can lock to the
#: calendar and no two movements can advance in step. lcm = 385 weeks.
OPENING_VARIANTS = 11
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


def load_report_content_from_json(path=None) -> dict:
    """The report corpus dict (key_type → key → payload) from the seed file."""
    import json
    from pathlib import Path

    from .content import REPORT_SEED_PATH

    data = json.loads(Path(path or REPORT_SEED_PATH).read_text())
    return {kt: data[kt] for kt in ("shape", "turn", "standing", "close")}


def load_report_content_from_db(conn, version: str) -> dict:
    """The report corpus for `version` from the report_content table."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key_type, key, payload FROM report_content WHERE version = %s",
            (version,),
        )
        rows = cur.fetchall()
    if not rows:
        raise SystemExit(f"no report_content rows for version {version!r}; run db/migrate.py")
    out: dict[str, dict] = {}
    for key_type, key, payload in rows:
        out.setdefault(key_type, {})[key] = payload
    return out
