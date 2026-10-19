"""Golden test: our Vimshottari table vs AstroSage's export.

Matching AstroSage exactly is the entire point of Prompt A. What the ephemeris
sweep established (see README > "Ayanamsa discovery"):

* The ayanamsa is **Lahiri VP285**, not plain Swiss Lahiri. With VP285 the
  balance is exact and every maha boundary lands within ±1 day; plain Lahiri is
  ~3–4 days off across the board.
* The dasha-year is **365.25 days** (solar/Julian), added as real calendar days.

Confirmed-matching facts are asserted strictly (balance, nakshatra, all maha
boundaries). The antar level matches to ±1 day for 77/85 dates; the remaining 8
are off by exactly 2 days. That gap is reported via
`test_antar_strict_one_day_is_the_open_question` (xfail) rather than fudged.

Its cause is now pinned (reshape B review, `test_astrosage_dasha_is_a_360_day_calendar`):
AstroSage does not count dasha time in real days. It lays a 360-day year of
twelve 30-day months onto the calendar as if every month had 30 days, so a
date never reads 31, and a "29/30 February" rolls into March. One model with
one free constant reproduces all 942 Lahiri dates AstroSage printed for this
chart (432 of them to the hour) and all 434 of its KP dates. Adopted for the
chart file (reshape B decisions, 2026-10-20) as `calendar_dasha`, whose own
tests close this file; compute_dasha keeps 365.25 real days for /v1/dasha,
the live app's route, unchanged.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta
from fractions import Fraction

import pytest

from engine.ephemeris import ASTROSAGE_AYANAMSA
from engine.positions import positions_from_ist
from engine.vimshottari import (
    ABBR,
    calendar_children,
    calendar_dasha,
    calendar_date,
    calendar_day,
    calendar_gap,
    calendar_mahas,
    compute_dasha,
    rounded_table,
)

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
    "cascading rounding): AstroSage counts dasha time on a 360-day calendar of "
    "30-day months, compute_dasha (/v1/dasha) on 365.25 real days — the chart "
    "file uses that calendar (calendar_dasha; 76/76 exact, tests below) — see "
    "test_astrosage_dasha_is_a_360_day_calendar and README > Known deviations",
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


# ── Why: AstroSage's dasha calendar (reshape B review) ──────────────────────
# Not the engine's arithmetic — a model of AstroSage's, fitted to its own
# printed dates, so the cause of the xfail above is a tested fact and not a
# guess. Positions on AstroSage's dasha timeline are LABELS in a calendar of
# 30-day months: serial = 360·year + 30·(month − 1) + (day − 1) + hour/24.
# Every boundary is epoch + (cumulative dasha years) × 360 in that serial;
# turning a label back into a date, a day past the real month's length rolls
# into the next month (February always as 28 days, leap years included).
TABLES = None
_YEARS = {"KET": 7, "VEN": 20, "SUN": 6, "MON": 10, "MAR": 7, "RAH": 18,
          "JUP": 16, "SAT": 19, "MER": 17}
_SEQ = ["KET", "VEN", "SUN", "MON", "MAR", "RAH", "JUP", "SAT", "MER"]
_MONTH_LEN = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _tables() -> dict:
    global TABLES
    if TABLES is None:
        path = os.path.join(os.path.dirname(__file__), "golden", "astrosage_dasha_tables.json")
        with open(path) as f:
            TABLES = json.load(f)
    return TABLES


def _cumulative_years() -> dict[tuple, Fraction]:
    """End of every maha/antar/pratyantar/sookshma, in dasha years from the
    virtual start of the birth (Rahu) maha — exact fractions."""
    order = lambda lord: _SEQ[_SEQ.index(lord):] + _SEQ[:_SEQ.index(lord)]  # noqa: E731
    ends, t = {}, Fraction(0)
    for m in order("RAH"):
        at = t
        for a in order(m):
            la = Fraction(_YEARS[m] * _YEARS[a], 120)
            pt = at
            for p in order(a):
                lp = la * _YEARS[p] / 120
                st = pt
                for x in order(p):
                    st += lp * _YEARS[x] / 120
                    ends[(m, a, p, x)] = st
                pt += lp
                ends[(m, a, p)] = pt
            at += la
            ends[(m, a)] = at
        t += _YEARS[m]
    return ends


def _serial(d: int, mo: int, y: int, h: float = 0.0) -> float:
    return y * 360 + (mo - 1) * 30 + (d - 1) + h / 24


def _label(s: float) -> tuple[int, int, int, float]:
    y = math.floor(s / 360)
    r = s - y * 360
    mo = math.floor(r / 30) + 1
    r -= (mo - 1) * 30
    d, h = math.floor(r) + 1, (r - math.floor(r)) * 24
    if d > _MONTH_LEN[mo - 1]:
        d, mo = d - _MONTH_LEN[mo - 1], mo + 1
        if mo == 13:
            mo, y = 1, y + 1
    return d, mo, y, h


def _year4(path: tuple, y2: int, ends: dict) -> int:
    near = 1975 + float(ends[path])   # this chart's timeline starts in 1975
    return min((c + y2 for c in (1900, 2000, 2100)), key=lambda y: abs(y - near))


def _fit(obs: list, ends: dict) -> tuple[float, float]:
    """The epoch interval every observation allows (hour-level ones bound it
    to the hour, dates to the day). 1–2 March may be a rolled 29/30 Feb label,
    so those are scored but not used to fit."""
    lo, hi = -math.inf, math.inf
    for path, d, mo, y, h in obs:
        if mo == 3 and d <= 2:
            continue
        c = float(ends[path]) * 360
        width = 1 / 24 if h is not None else 1.0
        base = _serial(d, mo, y, h or 0.0)
        lo, hi = max(lo, base - c), min(hi, base + width - c)
    return lo, hi


def _misses(obs: list, ends: dict, epoch: float) -> list:
    out = []
    for path, d, mo, y, h in obs:
        pd, pm, py, ph = _label(epoch + float(ends[path]) * 360)
        if (pd, pm, py) != (d, mo, y) or (h is not None and int(ph) != h):
            out.append((path, (d, mo, y, h), (pd, pm, py, round(ph, 2))))
    return out


def test_astrosage_dasha_is_a_360_day_calendar():
    """Every Lahiri dasha date AstroSage printed for the golden chart — the
    PDF's 76 antar ends, the docx's 434 pratyantar ends and 432 sookshma ends
    to the hour — follows the 30-day-month model from ONE epoch, fitted here
    to a window under a minute wide. The engine's 365.25-day arithmetic, by
    contrast, gets 42/76 antar ends exact (2 off by two days)."""
    t, ends = _tables(), _cumulative_years()
    obs = []
    for maha, rows in t["antar"].items():
        for lord, v in rows:
            if v is not None:
                obs.append(((maha, lord), v[0], v[1], _year4((maha, lord), v[2], ends), None))
    for b in t["blocks"]:
        for lord, v in b["rows"]:
            if v is not None:
                obs.append((tuple(b["label"] + [lord]), v[0], v[1], v[2], v[3]))
    assert len(obs) == 942 and sum(o[4] is not None for o in obs) == 432
    lo, hi = _fit(obs, ends)
    assert 0 < (hi - lo) * 24 * 60 < 1.0          # one epoch, pinned to < 1 minute
    assert _misses(obs, ends, (lo + hi) / 2) == []
    # The birth (23 Sep 1989) lands on the timeline at its DAY LABEL, its 04:47
    # dropped: that is the anchor under which the epoch implies AstroSage's own
    # printed Moon (Gemini 17-06-43) — 17-06-42.9.
    f = (_serial(23, 9, 1989) + 1 - (lo + hi) / 2) / (18 * 360)
    moon = 66 + 2 / 3 + f * 40 / 3
    assert abs(moon - (60 + 17 + 6 / 60 + 43 / 3600)) * 3600 < 0.5


def test_astrosage_kp_dasha_follows_the_same_calendar():
    """Same report, KP ayanamsa (a different Moon): 434 more dates, one epoch,
    zero misses — and that epoch implies the KP Moon AstroSage prints
    (077-12-06) under the same day-label anchor."""
    t, ends = _tables(), _cumulative_years()
    obs = [(tuple(r["path"]), r["date"][0], r["date"][1],
            _year4(tuple(r["path"]), r["date"][2], ends), None) for r in t["kp"]]
    assert len(obs) == 434
    lo, hi = _fit(obs, ends)
    assert hi > lo and _misses(obs, ends, (lo + hi) / 2) == []
    for epoch in (lo, hi):
        f = (_serial(23, 9, 1989) + 1 - epoch) / (18 * 360)
        moon = 66 + 2 / 3 + f * 40 / 3
        assert abs(moon - (77 + 12 / 60 + 6 / 3600)) * 3600 < 1.0


# ── The production calendar: vimshottari.calendar_dasha ────────────────────
# What the chart file prints, held to the model above and to AstroSage's dates.
def _production_ends(moon: float) -> dict[tuple, tuple[int, int, int]]:
    cal = calendar_dasha(moon, BIRTH.date())
    ends = {}

    def walk(p, path):
        d = cal.date_at(p.end)
        ends[path] = (d.day, d.month, d.year)
        if len(path) < 4:
            for c in calendar_children(p):
                walk(c, (*path, ABBR[c.lord]))

    for m in calendar_mahas(cal):
        walk(m, (ABBR[m.lord],))
    return ends


def _astrosage_dates() -> list[tuple[tuple, tuple[int, int, int]]]:
    t, cum = _tables(), _cumulative_years()
    out = [((maha, lord), (v[0], v[1], _year4((maha, lord), v[2], cum)))
           for maha, rows in t["antar"].items() for lord, v in rows if v is not None]
    out += [((*b["label"], lord), tuple(v[:3])) for b in t["blocks"]
            for lord, v in b["rows"] if v is not None]
    return out


def _implied_moon() -> float:
    """The Moon AstroSage's 942 dates imply under the model (17-06-42.9)."""
    t, cum = _tables(), _cumulative_years()
    obs = [((maha, lord), v[0], v[1], _year4((maha, lord), v[2], cum), None)
           for maha, rows in t["antar"].items() for lord, v in rows if v is not None]
    obs += [(tuple(b["label"] + [lord]), v[0], v[1], v[2], v[3])
            for b in t["blocks"] for lord, v in b["rows"] if v is not None]
    lo, hi = _fit(obs, cum)
    f = (_serial(23, 9, 1989) + 1 - (lo + hi) / 2) / (18 * 360)
    return 66 + 2 / 3 + f * 40 / 3


def test_calendar_rolls_february_and_never_prints_a_31st():
    feb28 = calendar_day(date(2004, 2, 28))
    assert [calendar_date(feb28 + i).isoformat() for i in range(4)] == [
        "2004-02-28", "2004-03-01", "2004-03-02", "2004-03-01"]  # AstroSage: 29/2 → 1/3/04
    assert calendar_day(date(1990, 1, 31)) == calendar_day(date(1990, 2, 1))
    assert calendar_gap(date(2048, 2, 28), date(2048, 3, 1)) == 1   # 28 vs rolled 29 Feb
    for n in range(360 * 1989, 360 * 2110):
        d = calendar_date(n)
        assert d.day <= 30
        if not (d.month == 3 and d.day <= 2):
            assert calendar_day(d) == n


def test_production_calendar_reproduces_every_astrosage_date():
    """Fed the Moon AstroSage's dates imply, calendar_dasha — the chart file's
    code, not the model — gives all 942 printed dates (sookshma to the day)."""
    ends = _production_ends(_implied_moon())
    dates = _astrosage_dates()
    assert len(dates) == 942
    assert [(p, want, ends[p]) for p, want in dates if ends[p] != want] == []


def test_production_calendar_with_our_moon():
    """With the engine's own Moon (2.4″ past AstroSage's — its ephemeris, README)
    every antar end is still exact; the shorter periods move by at most two
    calendar days. Measured: pratyantar 298/434 exact, sookshma 293/432."""
    from engine.chart_file import natal_facts
    natal = natal_facts(BIRTH, "Asia/Kolkata", 19 + 11 / 60, 72 + 58 / 60)
    moon = natal["planets"]["Moon"]["longitude"]
    ends = _production_ends(moon)
    exact = {2: 0, 3: 0, 4: 0}
    for path, want in _astrosage_dates():
        got = ends[path]
        gap = calendar_gap(date(*got[::-1]), date(*want[::-1]))
        assert gap <= 2, (path, want, got)
        exact[len(path)] += gap == 0
    assert exact == {2: 76, 3: 298, 4: 293}

