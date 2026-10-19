"""Vimshottari Dasha computation from the natal Moon.

Everything here derives from one input: the Moon's sidereal longitude at birth.
That fixes the birth nakshatra, its lord, and the *balance* of the first
maha-dasha; the rest of the 120-year cycle unfolds mechanically.

Two year-length conventions are implemented (see `YearMode`) because which one
a given software uses is only decidable against a known-good table:

* ``solar`` — 1 dasha-year = 365.25 real days, added as actual calendar days.
  The default; it drives /v1/dasha and matches AstroSage's tables to ±2 days.
* ``savana`` — the traditional 360-day year. Kept for comparison.

AstroSage's own dates are neither: they are labels on a calendar of 30-day
months (``calendar_dasha``, below), which the chart file uses.

Date arithmetic uses a single *nominal timeline*: the birth maha-dasha is placed
as if it had run from its virtual start (birth − elapsed), so every sub-period
that ended before birth falls out naturally as "elapsed" — exactly the
``00/00/00`` rows AstroSage prints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# ── Constants ───────────────────────────────────────────────────────────────
NAKSHATRA_ARC = 13 + 20 / 60  # 13°20' = 800'
TOTAL_NAKSHATRAS = 27
CYCLE_YEARS = 120

# Vimshottari lord order and each lord's maha-dasha length (years).
LORD_SEQUENCE = ("Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury")
DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
assert sum(DASHA_YEARS.values()) == CYCLE_YEARS

# Three-letter tokens matching the AstroSage document (for CLI / golden parity).
ABBR = {
    "Ketu": "KET", "Venus": "VEN", "Sun": "SUN", "Moon": "MON", "Mars": "MAR",
    "Rahu": "RAH", "Jupiter": "JUP", "Saturn": "SAT", "Mercury": "MER",
}

NAKSHATRAS = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
)

# Year-length modes: name -> days per dasha-year.
YEAR_MODES = {"solar": 365.25, "savana": 360.0}
DEFAULT_YEAR_MODE = "solar"


# ── Nakshatra ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Nakshatra:
    index: int          # 0–26
    name: str
    pada: int           # 1–4
    lord: str
    fraction_elapsed: float  # 0–1 through the nakshatra


def nakshatra_of(moon_longitude: float) -> Nakshatra:
    """Resolve the birth nakshatra, pada and lord from the Moon's longitude."""
    lon = moon_longitude % 360
    index = int(lon // NAKSHATRA_ARC)
    within = lon - index * NAKSHATRA_ARC
    pada = int(within // (NAKSHATRA_ARC / 4)) + 1
    lord = LORD_SEQUENCE[index % 9]
    return Nakshatra(index, NAKSHATRAS[index], pada, lord, within / NAKSHATRA_ARC)


def _order_from(lord: str) -> list[str]:
    """The 9 lords in Vimshottari order, rotated to start at `lord`."""
    start = LORD_SEQUENCE.index(lord)
    return [LORD_SEQUENCE[(start + i) % 9] for i in range(9)]


# ── Period tree ─────────────────────────────────────────────────────────────
@dataclass
class Period:
    """A dasha at any level (maha / antar / pratyantar)."""

    lord: str
    level: int                 # 1=maha, 2=antar, 3=pratyantar
    start: datetime
    end: datetime
    years: float               # nominal duration in dasha-years
    elapsed: bool              # ended at/before birth (AstroSage "00/00/00")
    children: list[Period] = field(default_factory=list)

    @property
    def abbr(self) -> str:
        return ABBR[self.lord]


@dataclass
class DashaResult:
    nakshatra: Nakshatra
    balance: Balance
    mahas: list[Period]
    year_mode: str
    year_days: float


@dataclass(frozen=True)
class Balance:
    """Remaining span of the birth maha-dasha, as AstroSage prints it."""

    lord: str
    years: int
    months: int
    days: int
    total_days: float

    def __str__(self) -> str:
        return f"{self.lord.upper()} {self.years} Y {self.months} M {self.days} D"


def _decompose(total_days: float, year_days: float) -> tuple[int, int, int]:
    """Split a day count into Y/M/D using the same convention as the year mode."""
    month_days = year_days / 12
    years = int(total_days // year_days)
    rem = total_days - years * year_days
    months = int(rem // month_days)
    rem -= months * month_days
    return years, months, round(rem)


def _build_children(
    lord: str,
    parent_start: datetime,
    parent_years: float,
    level: int,
    birth: datetime,
    year_days: float,
    max_level: int,
) -> list[Period]:
    """Sub-periods of a period: sequence starts at `lord`, durations ∝ lord years."""
    periods: list[Period] = []
    cursor = parent_start
    for sub in _order_from(lord):
        sub_years = parent_years * DASHA_YEARS[sub] / CYCLE_YEARS
        start = cursor
        end = start + timedelta(days=sub_years * year_days)
        node = Period(sub, level, start, end, sub_years, end <= birth)
        if level < max_level:
            node.children = _build_children(
                sub, start, sub_years, level + 1, birth, year_days, max_level
            )
        periods.append(node)
        cursor = end
    return periods


def compute_dasha(
    moon_longitude: float,
    birth_local: datetime,
    *,
    year_mode: str = DEFAULT_YEAR_MODE,
    levels: int = 3,
    cycles: int = 2,
) -> DashaResult:
    """Full Vimshottari table from the natal Moon.

    `birth_local` is the wall-clock birth datetime (its calendar dates are what
    the output dates are expressed in). `levels`: 1=maha, 2=+antar, 3=+prat.
    `cycles`: how many 120-year cycles of maha-dashas to emit.
    """
    if year_mode not in YEAR_MODES:
        raise ValueError(f"year_mode must be one of {sorted(YEAR_MODES)}")
    year_days = YEAR_MODES[year_mode]

    nak = nakshatra_of(moon_longitude)
    lord_years = DASHA_YEARS[nak.lord]

    balance_years = (1 - nak.fraction_elapsed) * lord_years
    balance_days = balance_years * year_days
    by, bm, bd = _decompose(balance_days, year_days)
    balance = Balance(nak.lord, by, bm, bd, balance_days)

    # Virtual start of the birth maha, so pre-birth sub-periods read as elapsed.
    elapsed_days = nak.fraction_elapsed * lord_years * year_days
    nominal_start = birth_local - timedelta(days=elapsed_days)

    mahas: list[Period] = []
    cursor = nominal_start
    for mlord in _order_from(nak.lord) * cycles:
        m_years = DASHA_YEARS[mlord]
        start = cursor
        end = start + timedelta(days=m_years * year_days)
        node = Period(mlord, 1, start, end, m_years, end <= birth_local)
        if levels >= 2:
            node.children = _build_children(
                mlord, start, m_years, 2, birth_local, year_days, levels
            )
        mahas.append(node)
        cursor = end

    return DashaResult(nak, balance, mahas, year_mode, year_days)


# ── AstroSage rounding mode (presentation layer — Prompt A.1) ───────────────
# Hypothesis tested: AstroSage's antar dates come from *cascading* day-rounding
# (antar boundaries derived from the day-rounded parent maha boundary, then
# themselves rounded). Verdict against the golden chart:
#   * maha level: round-half makes 9/10 boundaries EXACT (vs ±1d for exact
#     floats) — AstroSage clearly rounds maha boundaries to whole days.
#   * antar level: offenders drop 8 → 4, but 4 dates remain off by exactly
#     2 days — the hypothesis does NOT fully close the gap.
# Therefore this stays an *option* (`astrosage_rounding=True`), not the
# default; internal float datetimes remain the canonical representation.
# The cause of the remaining 2-day gaps was found in the reshape B review:
# AstroSage places dasha time on a 360-day calendar of 30-day months (every
# month treated as 30 days long), not on 365.25 real days — pinned by
# tests/test_vimshottari.py::test_astrosage_dasha_is_a_360_day_calendar —
# and the chart file now uses that calendar (calendar_dasha, below).
# See README > "Known deviations".


def _round_day(d: datetime) -> date:
    """Round a datetime to the nearest whole calendar day (round-half-up)."""
    return (d + timedelta(hours=12)).date()


@dataclass(frozen=True)
class RoundedMaha:
    """Day-rounded presentation of one maha block (dates, not datetimes)."""

    lord: str
    start: date
    end: date
    antar: tuple[tuple[str, date], ...]  # (lord, day-rounded end) in order


def rounded_table(result: DashaResult, birth: datetime, *, blocks: int = 10) -> list[RoundedMaha]:
    """Cascading day-rounded maha+antar dates (AstroSage-style presentation).

    Maha boundaries are rounded to whole days first; each antar chain is then
    re-derived from its *rounded* parent start (at midnight) using the exact
    float durations, and finally rounded itself. Pure presentation — the
    `Period` tree in `result` keeps exact float datetimes.
    """
    out: list[RoundedMaha] = []
    for maha in result.mahas[:blocks]:
        start_day = _round_day(maha.start)
        end_day = _round_day(maha.end)
        base = datetime.combine(start_day, datetime.min.time())
        antar: list[tuple[str, date]] = []
        cum = 0.0
        for sub in maha.children:
            cum += sub.years * result.year_days
            antar.append((sub.lord, _round_day(base + timedelta(days=cum))))
        out.append(RoundedMaha(maha.lord, start_day, end_day, tuple(antar)))
    return out


# ── AstroSage's dasha calendar (the chart file's dates) ────────────────────
# AstroSage does not lay dasha time on real days. Its dates are LABELS on a
# calendar of twelve 30-day months: day number = 360·year + 30·(month − 1) +
# (day − 1), every boundary = epoch + (cumulative dasha years) × 360, and a
# label is printed as the date it names — except that 29 and 30 February roll
# into 1 and 2 March (February always counts 28 days, leap years included), so
# no date is ever the 31st. The birth sits at the START OF THE DAY AFTER its
# date label, its clock time dropped; the Moon still decides the balance.
# Fitted to, and reproducing, all 942 Lahiri dates (76 antar, 434 pratyantar,
# 432 sookshma to the hour) and 434 KP dates AstroSage printed for the golden
# chart — tests/test_vimshottari.py — and adopted for the chart file in the
# reshape B decisions (2026-10-20). compute_dasha (365.25 real days) still
# drives /v1/dasha for the live app, unchanged.
#
# Lengths are whole numbers of 1/120³ year (maha 120³·L, antar 120²·L·L′, …),
# so a parent's last child ends on exactly the parent's end, at every level.
CALENDAR_UNITS_PER_YEAR = 120 ** 3
CALENDAR_UNITS_PER_DAY = CALENDAR_UNITS_PER_YEAR // 360  # 4800


def calendar_day(d: date) -> int:
    """A real date's day number on the 30-day-month calendar (a 31st shares
    the next month's 1st)."""
    return d.year * 360 + (d.month - 1) * 30 + (d.day - 1)


def calendar_date(day: int) -> date:
    """The date AstroSage prints for a day number: 29/30 February → 1/2 March."""
    year, rem = divmod(day, 360)
    month, d = rem // 30 + 1, rem % 30 + 1
    if month == 2 and d > 28:
        month, d = 3, d - 28
    return date(year, month, d)


def calendar_labels(d: date) -> tuple[int, ...]:
    """Every day number that prints as `d`: 1/2 March may be a rolled 29/30 Feb."""
    n = calendar_day(d)
    return (n, n - 2) if d.month == 3 and d.day <= 2 else (n,)


def calendar_gap(a: date, b: date) -> int:
    """Days apart on the dasha calendar (the closest reading of each)."""
    return min(abs(x - y) for x in calendar_labels(a) for y in calendar_labels(b))


@dataclass(frozen=True)
class CalendarDasha:
    """The birth's dasha timeline on AstroSage's calendar. Positions on it are
    integer UNITS (1/120³ dasha-year) from the virtual start of the birth maha."""

    nakshatra: Nakshatra
    balance: Balance       # birth date → the birth maha's printed end, as Y/M/D
                           # of 360/30 days; total_days = the exact remainder
    epoch: float           # calendar day number (fractional) of unit 0

    def date_at(self, units: int) -> date:
        return calendar_date(math.floor(self.epoch + units / CALENDAR_UNITS_PER_DAY))


@dataclass(frozen=True)
class CalendarPeriod:
    """One period in units: [start, end) on the CalendarDasha timeline."""

    lord: str
    start: int
    end: int


def calendar_dasha(moon_longitude: float, birth_day: date) -> CalendarDasha:
    """Place the birth on AstroSage's dasha calendar (see the section note).

    The balance is the whole label days from the birth date to the birth
    maha's printed end, so birth date + balance = that end, always — the golden
    chart's 3Y 10M 24D (AstroSage's own) is 23.3 days of remainder plus the
    birth day. A balance rounded on its own could say a day less than the
    table under it."""
    nak = nakshatra_of(moon_longitude)
    lord_days = DASHA_YEARS[nak.lord] * 360
    epoch = calendar_day(birth_day) + 1 - nak.fraction_elapsed * lord_days
    days = math.floor(epoch + lord_days) - calendar_day(birth_day)
    by, rem = divmod(days, 360)
    bm, bd = divmod(rem, 30)
    balance = Balance(nak.lord, by, bm, bd, (1 - nak.fraction_elapsed) * lord_days)
    return CalendarDasha(nak, balance, epoch)


def calendar_mahas(cal: CalendarDasha, count: int = 9) -> list[CalendarPeriod]:
    """`count` mahas from the birth maha's virtual start (unit 0)."""
    out, at = [], 0
    for i in range(count):
        lord = LORD_SEQUENCE[(LORD_SEQUENCE.index(cal.nakshatra.lord) + i) % 9]
        length = DASHA_YEARS[lord] * CALENDAR_UNITS_PER_YEAR
        out.append(CalendarPeriod(lord, at, at + length))
        at += length
    return out


def calendar_children(parent: CalendarPeriod) -> list[CalendarPeriod]:
    """The 9 sub-periods of a period, from its own lord, tiling it exactly."""
    length = parent.end - parent.start
    out, at = [], parent.start
    for lord in _order_from(parent.lord):
        step = length * DASHA_YEARS[lord] // CYCLE_YEARS
        out.append(CalendarPeriod(lord, at, at + step))
        at += step
    assert at == parent.end, "a sub-period length is not a whole number of units"
    return out


# ── AstroSage-style rendering (for eyeball comparison) ──────────────────────
def _fmt_date(d: datetime, birth: datetime) -> str:
    """`d/ m/yy` like the AstroSage doc; dates at/before birth read 00/00/00."""
    if d <= birth:
        return "00/00/00"
    yy = d.year % 100
    return f"{d.day}/{d.month:>2}/{yy:02d}"


def _fmt_day(d: date, birth: date) -> str:
    if d <= birth:
        return "00/00/00"
    return f"{d.day}/{d.month:>2}/{d.year % 100:02d}"


def format_astrosage(
    result: DashaResult,
    birth: datetime,
    *,
    blocks: int = 10,
    astrosage_rounding: bool = False,
) -> str:
    """Render the maha + antar table in the same layout as the reference doc.

    With `astrosage_rounding=True`, dates go through `rounded_table()` (the
    cascading day-rounding presentation) instead of truncating exact floats.
    """
    lines = ["Vimshottari Dasha", f"Balance Of Dasha : {result.balance}", "------------"]
    if astrosage_rounding:
        birth_day = birth.date()
        for maha in rounded_table(result, birth, blocks=blocks):
            lines.append(f"{ABBR[maha.lord]} -{DASHA_YEARS[maha.lord]} Years")
            lines.append("-------------")
            start = birth_day if maha.start <= birth_day else maha.start
            lines.append(_fmt_day(start, birth_day - timedelta(days=1)))
            lines.append(_fmt_day(maha.end, birth_day - timedelta(days=1)))
            lines.append("-------------")
            for lord, end in maha.antar:
                lines.append(f"{ABBR[lord]} {_fmt_day(end, birth_day)}")
            lines.append("------------")
        return "\n".join(lines)
    for maha in result.mahas[:blocks]:
        lines.append(f"{maha.abbr} -{DASHA_YEARS[maha.lord]} Years")
        lines.append("-------------")
        start = birth if maha.start <= birth else maha.start
        lines.append(_fmt_date(start, birth - timedelta(days=1)))
        lines.append(_fmt_date(maha.end, birth - timedelta(days=1)))
        lines.append("-------------")
        for antar in maha.children:
            lines.append(f"{antar.abbr} {_fmt_date(antar.end, birth)}")
        lines.append("------------")
    return "\n".join(lines)
