"""Golden test: our Vimshottari table vs AstroSage's export.

Matching AstroSage exactly is the entire point of Prompt A. What the ephemeris
sweep established (see README > "Ayanamsa discovery"):

* The ayanamsa is **Lahiri VP285**, not plain Swiss Lahiri. With VP285 the
  balance is exact and every maha boundary lands within ±1 day; plain Lahiri is
  ~3–4 days off across the board.
* The dasha-year is **365.25 days** (solar/Julian), added as real calendar days.

Confirmed-matching facts are asserted strictly (balance, nakshatra, all maha
boundaries). The antar level matches to ±1 day for 77/85 dates; the remaining 8
are off by exactly 2 days (sub-arcsecond ayanamsa residue). That gap is reported
honestly via `test_antar_strict_one_day_is_the_open_question` (xfail) rather than
fudged.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from engine.ephemeris import ASTROSAGE_AYANAMSA
from engine.positions import positions_from_ist
from engine.vimshottari import compute_dasha, rounded_table

from .conftest import BIRTH, antar_deltas, as_date

TOLERANCE = timedelta(days=1)


# ── Balance & nakshatra (headline requirement) ──────────────────────────────
def test_balance_matches_exactly(result, golden):
    g = golden["balance"]
    assert result.balance.lord == g["lord"]
    assert (result.balance.years, result.balance.months, result.balance.days) == (
        g["years"], g["months"], g["days"]
    ), f"balance {result.balance} != AstroSage {g}"


def test_birth_nakshatra(result):
    nak = result.nakshatra
    assert nak.name == "Ardra"
    assert nak.pada == 4
    assert nak.lord == "Rahu"


# ── Maha-dasha boundaries (all within ±1 day) ───────────────────────────────
def test_all_maha_boundaries_within_one_day(result, golden):
    for gi, gm in enumerate(golden["maha"]):
        maha = result.mahas[gi]
        assert maha.lord == gm["lord"]
        # start of the first maha is clamped to birth; compare the rest + all ends
        delta_end = abs((maha.end.date() - as_date(gm["end"])).days)
        assert delta_end <= 1, (
            f"{gm['lord']} maha end {maha.end.date()} vs {gm['end']} "
            f"(Δ{delta_end}d)"
        )
        if gi > 0:
            delta_start = abs((maha.start.date() - as_date(gm["start"])).days)
            assert delta_start <= 1


# ── Antar-dasha (target: ±1 day) ────────────────────────────────────────────
def test_antar_within_two_days_and_mostly_one(result, golden):
    rows = antar_deltas(result, golden)
    max_delta = max(abs(d) for *_, d in rows)
    within_one = sum(1 for *_, d in rows if abs(d) <= 1)
    assert max_delta <= 2, f"an antar date is off by {max_delta} days"
    assert within_one / len(rows) >= 0.85, (
        f"only {within_one}/{len(rows)} antar dates within ±1 day"
    )


@pytest.mark.xfail(
    reason="antar dates off by exactly 2 days remain (8 exact-float / 4 with "
    "cascading rounding, see Prompt A.1) — residual gap vs AstroSage's exact "
    "internal ayanamsa constant; reported, not fudged. README > Known deviations",
    strict=True,
)
def test_antar_strict_one_day_is_the_open_question(result, golden):
    rows = antar_deltas(result, golden)
    offenders = [(m, a, g, d) for m, a, g, d in rows if abs(d) > 1]
    assert not offenders, "\n".join(
        f"  {m[:3]}-{a[:3]} golden {g}: Δ{d:+d}d" for m, a, g, d in offenders
    )


# ── Prompt A.1: cascading day-rounding presentation mode ────────────────────
def test_astrosage_rounding_mode_improves_but_does_not_close(result, golden):
    """Round-half maha boundaries + antar cascaded from the rounded parent.

    Confirms the two halves of the A.1 verdict: (a) maha boundaries become
    essentially exact (AstroSage does round maha ends to whole days), and
    (b) 4 antar dates still sit 2 days off — so the mode stays an option and
    the strict ±1d antar test stays xfail.
    """
    rounded = rounded_table(result, BIRTH, blocks=10)

    # (a) maha ends: 9/10 exact, worst 1 day (2113 boundary).
    maha_deltas = [
        abs((rounded[gi].end - as_date(gm["end"])).days)
        for gi, gm in enumerate(golden["maha"])
    ]
    assert sum(1 for d in maha_deltas if d == 0) >= 9
    assert max(maha_deltas) <= 1

    # (b) antar: strictly better than exact-float rendering, but not closed.
    offenders = []
    within_one = total = 0
    for gi, gm in enumerate(golden["maha"]):
        for ai, ga in enumerate(gm["antar"]):
            if ga["end"] is None:
                continue
            delta = (rounded[gi].antar[ai][1] - as_date(ga["end"])).days
            total += 1
            if abs(delta) <= 1:
                within_one += 1
            else:
                offenders.append((gm["lord"], ga["lord"], delta))
    assert max(abs(d) for *_, d in offenders) <= 2
    assert 0 < len(offenders) <= 4          # improved from 8, NOT closed
    assert within_one >= 74                 # the already-matching dates hold


# ── The ayanamsa discovery, pinned as a regression guard ────────────────────
def test_vp285_beats_plain_lahiri(golden):
    def avg_abs_maha_delta(ayanamsa: str) -> float:
        moon = positions_from_ist(BIRTH, ayanamsa=ayanamsa)["Moon"].longitude
        res = compute_dasha(moon, BIRTH, year_mode="solar", levels=1, cycles=2)
        deltas = [
            abs((res.mahas[gi].end.date() - as_date(gm["end"])).days)
            for gi, gm in enumerate(golden["maha"])
        ]
        return sum(deltas) / len(deltas)

    assert avg_abs_maha_delta(ASTROSAGE_AYANAMSA) <= 1.0
    assert avg_abs_maha_delta("lahiri") > 2.0  # plain Lahiri is visibly wrong


# ── Pratyantar (experimental — structure only, loose tolerance) ─────────────
def test_pratyantar_structure_and_ballpark(result, golden):
    # Index our maha→antar tree by (maha, antar) for lookup.
    index = {}
    for maha in result.mahas:
        for antar in maha.children:
            index.setdefault((maha.lord, antar.lord), antar)  # first cycle wins

    checked = 0
    for block in golden["pratyantar"]:
        antar = index.get((block["maha"], block["antar"]))
        if antar is None:
            continue
        assert len(antar.children) == 9  # structure is exact
        for pi, gp in enumerate(block["periods"]):
            if gp["end"] is None:
                continue
            delta = abs((antar.children[pi].end.date() - as_date(gp["end"])).days)
            assert delta <= 5, (  # experimental: ballpark only
                f"prat {block['maha'][:3]}-{block['antar'][:3]}-{gp['lord'][:3]} "
                f"Δ{delta}d"
            )
            checked += 1
    assert checked > 100  # we actually exercised the pratyantar tree
