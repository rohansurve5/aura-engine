"""Why there is no YEARLY report — the measurement, pinned.

docs/REPORTS.md § the audit reframed yearly away from daily aggregates (a year
of tara sawtooth averages to the same middling number for every user) and onto
Vimshottari, which genuinely varies over years. This module measures whether
that reframing survives contact with the data. It does not.

The verdict is CUT, and these tests are the evidence. If one starts failing,
the cut is worth revisiting — that is the point of pinning it rather than
writing it down in prose only.
"""

from __future__ import annotations

import statistics
from datetime import datetime

from engine.vimshottari import compute_dasha

# A deterministic spread of natals: moon longitude x birth date. No RNG, so the
# numbers in the docstrings below are reproducible byte-for-byte.
NATALS = [
    ((i * 360.0 / 120.0 + 1.37) % 360.0,
     datetime(1960 + (i * 7) % 46, 1 + (i * 5) % 12, 1 + (i * 11) % 28, 6, 30))
    for i in range(120)
]
YEARS = range(2026, 2036)  # the app's live window


def _year_facts(res, year):
    """(antar boundaries in the year, antar periods touching it, maha boundaries)."""
    y0, y1 = datetime(year, 1, 1), datetime(year + 1, 1, 1)
    antars = [c for m in res.mahas for c in m.children]
    touching = [p for p in antars if min(p.end, y1) > max(p.start, y0)]
    bounds = [p for p in antars if y0 < p.start < y1]
    maha_bounds = [m for m in res.mahas if y0 < m.start < y1]
    return bounds, touching, maha_bounds


def _sample():
    rows = []
    for lon, birth in NATALS:
        res = compute_dasha(lon, birth, levels=2, cycles=2)
        for y in YEARS:
            bounds, touching, maha_bounds = _year_facts(res, y)
            if touching:
                rows.append((len(bounds), len(touching), len(maha_bounds)))
    # The vacuous-pass guard the rest of the suite holds to: an empty work-list
    # must have no path to a green. Every ratio below divides by len(rows), so
    # an empty sample would raise — but state the size explicitly anyway, since
    # a shrunken-but-nonempty sample would quietly weaken every threshold.
    assert len(rows) == len(NATALS) * len(YEARS) == 1200, (
        f"sample is {len(rows)} rows, expected 1200 — thresholds below were "
        f"derived on that denominator"
    )
    return rows


# ── The structural kill: N is too small to have a shape ──────────────────────

def test_a_year_holds_too_few_dasha_periods_to_have_a_second_order_feature():
    """THE FINDING THAT CUT THE REPORT.

    docs/REPORTS.md § what a report is defines a report as an artefact whose
    every claim is a SECOND-ORDER feature — distribution, spread, position,
    adjacency — that exists only once you hold N units at once. Weekly holds 7
    days. Monthly holds 4-5 weeks. A yearly report over Vimshottari holds a
    measured mean of ~1.7 antar periods, and exactly one period 41% of the
    time.

    There is no distribution over 1.7 items. Every candidate second-order
    feature collapses to first-order restatement of the one period the reader
    is already in — which the shipped `astro-dasha-current` screen names, and
    `astro-dasha-detail` dates and interprets for every period in the life.

    Measured: mean 1.67 periods/year, 40.9% of years hold exactly one.
    """
    rows = _sample()
    per_year = [touching for _, touching, _ in rows]
    mean_periods = statistics.mean(per_year)
    single = sum(1 for n in per_year if n == 1) / len(per_year)

    assert mean_periods < 2.5, (
        f"mean {mean_periods:.2f} periods/year — if a year ever held enough "
        f"periods to have a distribution, the cut is worth revisiting"
    )
    assert single > 0.30, (
        f"only {single:.1%} of years hold a single period — the 'no shape over "
        f"N=1' argument weakens if this drops"
    )


def test_the_dasha_state_outlives_the_yearly_cadence():
    """The transit failure mode, one cadence up.

    § 6.2 killed the transit REPORT because the state held for a median 89 days
    against a 7-day cadence: a reader would receive a byte-identical payload a
    dozen issues running. The same test at year scale: the median antar period
    runs 404 days against a 365-day cadence, so the state STILL outlives the
    report that would describe it — and 41% of calendar years contain no
    boundary of any kind, making that year's report a verbatim reissue.
    """
    lengths = []
    for lon, birth in NATALS:
        res = compute_dasha(lon, birth, levels=2, cycles=2)
        lengths += [(c.end - c.start).days for m in res.mahas for c in m.children]
    median = statistics.median(lengths)

    assert median > 365, (
        f"median antar {median:.0f}d — a state shorter than the cadence would "
        f"make a yearly report a genuinely new claim each issue"
    )

    rows = _sample()
    static = sum(1 for b, _, mb in rows if not b and not mb) / len(rows)
    assert static > 0.30, f"only {static:.1%} of years are static — see above"


def test_the_maha_almost_never_changes_inside_a_calendar_year():
    """The one claim a yearly report could make that the reader would call
    news — "you enter a new era this year" — is available in 8% of years, and
    it is the single most visible thing on the timeline screen we already ship:
    the bar heights are proportional to period length and the running period is
    marked. Rare AND already delivered."""
    rows = _sample()
    with_maha_change = sum(1 for _, _, mb in rows if mb) / len(rows)
    assert with_maha_change < 0.15, (
        f"{with_maha_change:.1%} of years contain a maha boundary"
    )


def test_the_headline_claim_repeats_year_over_year():
    """A yearly report's headline is (era, dominant sub-period). For 42% of
    consecutive year pairs that tuple is IDENTICAL — the reader's second
    report opens on the same claim as the first. Rotation cannot rescue this
    for the same reason it could not rescue transit: rotating the words while
    the claim stands still is decorative variety, which § determinism rejects
    by name."""
    repeats = pairs = 0
    for lon, birth in NATALS:
        res = compute_dasha(lon, birth, levels=2, cycles=2)
        prev = None
        for y in YEARS:
            y0, y1 = datetime(y, 1, 1), datetime(y + 1, 1, 1)
            spans = []
            for m in res.mahas:
                for c in m.children:
                    s, e = max(c.start, y0), min(c.end, y1)
                    if e > s:
                        spans.append((m.lord, c.lord, (e - s).days))
            if not spans:
                continue
            dominant = max(spans, key=lambda t: t[2])[:2]
            if prev is not None:
                pairs += 1
                repeats += dominant == prev
            prev = dominant

    rate = repeats / pairs
    assert rate > 0.30, (
        f"{rate:.1%} year-over-year repeat rate — a lower rate would mean the "
        f"headline is genuinely new each year"
    )
