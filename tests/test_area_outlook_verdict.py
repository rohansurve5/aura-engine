"""Why there is no per-area PERIOD OUTLOOK — the measurement, pinned.

docs/REPORTS.md § the audit gave career / finance / business a "reframe or
defer" verdict: without an ascendant they cannot be house readings, but they
might survive as honest per-area period outlooks built on the six daily life-
area scores the app already ships. This module measures that reframing. It
does not survive, and for a sharper reason than yearly's.

THE STRUCTURAL FACT, from engine/scoring.py:

    score(area, date) = clamp(base(natal, date) + weekday_area_mod[wd][area])
    energy(date)      = clamp(base(natal, date) + weekday_energy_mod[wd])

`base` is the tara/paksha term and is IDENTICAL for all six areas — it is the
energy series the weekly and monthly reports already publish. The only area-
dependent term is a 7-periodic constant from a fixed table, the same for every
user, every month, forever. An area score therefore carries no information
that (energy, weekday) does not already carry — measured below at 100.00%,
not approximately.

The verdict is CUT (as period outlooks; the daily area lines and the Block 6
Life hub are untouched). These tests are the evidence. If one starts failing,
the cut is worth revisiting — that is the point of pinning it rather than
writing it down in prose only.
"""

from __future__ import annotations

import statistics
from calendar import monthrange
from collections import Counter
from datetime import date
from functools import lru_cache

import pytest

import engine.reports as R
from engine.scoring import guidance_for_nakshatra, load_rules_from_json

RULES = load_rules_from_json()
AREAS = RULES["areas"]["order"]
LABELS = RULES["areas"]["labels"]
AREA_MOD = RULES["weekday_area_mod"]
ENERGY_MOD = RULES["weekday_energy_mod"]

#: The app's live window, wide enough that a monthly cadence has 24 issues to
#: repeat across and every natal star is sampled.
NATALS = range(27)
FIRST_YEAR = 2026
N_MONTHS = 24


@pytest.fixture(autouse=True, scope="module")
def _cached_sky():
    """Memoise the ephemeris across the module — ~730 distinct dates, each pure
    and safe to cache, instead of a fresh Swiss Ephemeris call per natal."""
    original = R.build_daily_sky
    R.build_daily_sky = lru_cache(maxsize=None)(original)
    yield
    R.build_daily_sky = original


def _months():
    for i in range(N_MONTHS):
        y, m = FIRST_YEAR + (i // 12), (i % 12) + 1
        yield y, m, [date(y, m, d) for d in range(1, monthrange(y, m)[1] + 1)]


def _row(natal: int, d: date) -> tuple[tuple[int, ...], int, str]:
    sky = R.build_daily_sky(d)
    g = guidance_for_nakshatra(natal, sky, RULES)
    return (
        tuple(g["scores"][LABELS[a]] for a in AREAS),
        g["energy"],
        str(sky["weekday_index"]),
    )


def _month_means(natal: int, days: list[date]) -> tuple[float, ...]:
    rows = [_row(natal, d) for d in days]
    return tuple(
        statistics.mean(r[0][i] for r in rows) for i in range(len(AREAS))
    )


def test_an_area_score_is_fully_determined_by_energy_and_weekday():
    """The kill shot: an area score carries ZERO independent information.

    Predicting each area's score from nothing but the published energy and the
    weekday — inverting the shared `base` out of energy and re-applying the
    area's own weekday constant — reproduces it EXACTLY, 100.00% of the time
    over 27 natals x 12 months x 6 areas. Not "highly correlated": identical.

    An outlook composed from these scores can therefore make no claim that the
    energy series plus a lookup table does not already make, and the energy
    series is what the weekly and monthly reports are built on.
    """
    exact = total = 0
    for natal in NATALS:
        for _, _, days in list(_months())[:12]:
            for d in days:
                scores, energy, wd = _row(natal, d)
                for i, a in enumerate(AREAS):
                    predicted = max(0, min(100, energy - ENERGY_MOD[wd] + AREA_MOD[wd][a]))
                    total += 1
                    exact += predicted == scores[i]
    assert total > 50_000, total
    assert exact == total, (
        f"only {exact}/{total} area scores are determined by (energy, weekday) — "
        "an area has gained an independent input, so the CUT is worth revisiting"
    )


def test_the_only_area_specific_term_is_a_seven_periodic_constant():
    """`weekday_area_mod` is a fixed 7 x 6 table: it does not depend on the
    natal star, the date, the tara, or the paksha.

    That is what makes the previous test's 100% structural rather than a
    coincidence of this sample — and it is the same aliasing artefact that
    already killed week-over-week trajectory and recurring-weekday patterns at
    month scale (docs/REPORTS.md § the monthly report). An area outlook over a
    period is that artefact promoted to the headline.
    """
    assert sorted(AREA_MOD) == [str(i) for i in range(7)]
    for wd, table in AREA_MOD.items():
        assert sorted(table) == sorted(AREAS), wd
        assert all(isinstance(v, int) for v in table.values()), wd


def test_every_area_tracks_the_energy_series_the_reports_already_publish():
    """Within a month, each area's daily series correlates > 0.97 with energy,
    and its monthly mean correlates > 0.98 with the energy mean across 24
    months. "Career is rising this month" is "your energy is rising this
    month" with one word swapped."""
    daily_min = monthly_min = 1.0
    for natal in list(NATALS)[:9]:
        area_means = {i: [] for i in range(len(AREAS))}
        energy_means = []
        for _, _, days in _months():
            rows = [_row(natal, d) for d in days]
            energy = [r[1] for r in rows]
            energy_means.append(statistics.mean(energy))
            for i in range(len(AREAS)):
                series = [r[0][i] for r in rows]
                area_means[i].append(statistics.mean(series))
                daily_min = min(daily_min, statistics.correlation(series, energy))
        for i in range(len(AREAS)):
            monthly_min = min(
                monthly_min, statistics.correlation(area_means[i], energy_means)
            )
    assert daily_min > 0.97, daily_min
    assert monthly_min > 0.98, monthly_min


def test_which_area_leads_the_month_is_the_same_answer_for_almost_everyone():
    """"Standing" is the one genuinely second-order area feature — and at month
    scale it is mechanical Barnum.

    Across 27 natals x 24 months = 648 months, only TWO of the six areas ever
    lead, and one of them leads 94% of the time. Every user is told the same
    thing in the same month, and very nearly the same thing in every month.

    This is docs/REPORTS.md § 6.3's Rahu-retrograde finding in another key: a
    claim that is true in almost every reading ever composed is not a reading.
    """
    leaders = Counter()
    for natal in NATALS:
        for _, _, days in _months():
            means = _month_means(natal, days)
            leaders[AREAS[max(range(len(AREAS)), key=lambda i: means[i])]] += 1
    total = sum(leaders.values())
    assert total == 27 * N_MONTHS
    assert len(leaders) <= 2, dict(leaders)
    assert leaders.most_common(1)[0][1] / total > 0.90, dict(leaders)


def test_consecutive_monthly_outlooks_would_repeat_their_headline():
    """Same test as transit's § 6.2 and yearly's § 7.3, one cadence over: does
    the state outlive the report that would describe it?

    Taking an outlook's headline as (leading area, per-area score band), 63% of
    consecutive month pairs are IDENTICAL. A subscriber on a monthly cadence
    reads the same outlook twice running, most of the time — and rotation
    cannot rescue that, because rotating the words while the claim stands still
    is decorative variety, which § 3 rejects by name.
    """
    bands = RULES["score_bands"]["thresholds"]

    def band_of(v: float) -> str:
        for name in RULES["score_bands"]["order"][:-1]:
            if v >= bands[name]:
                return name
        return RULES["score_bands"]["order"][-1]

    repeats = pairs = 0
    for natal in NATALS:
        previous = None
        for _, _, days in _months():
            means = _month_means(natal, days)
            leader = AREAS[max(range(len(AREAS)), key=lambda i: means[i])]
            headline = (leader, tuple(band_of(round(v)) for v in means))
            if previous is not None:
                pairs += 1
                repeats += headline == previous
            previous = headline
    assert repeats / pairs > 0.55, f"{repeats}/{pairs}"


def test_two_of_the_four_reframed_reports_have_no_input_at_all():
    """Career maps to the `career` score and finance to `money`, but BUSINESS
    and MARRIAGE have no scored area behind them at all.

    `love` is not marriage — conflating them is exactly the reputational
    liability § 2 cut marriage for. So the reframe could at most cover two of
    the four, and those two are the ones the measurement above empties.
    """
    assert "career" in AREAS
    assert "money" in AREAS
    assert "business" not in AREAS
    assert "marriage" not in AREAS
