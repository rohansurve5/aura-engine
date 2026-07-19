"""Vimshottari Dasha computation from the natal Moon.

Everything here derives from one input: the Moon's sidereal longitude at birth.
That fixes the birth nakshatra, its lord, and the *balance* of the first
maha-dasha; the rest of the 120-year cycle unfolds mechanically.

Two year-length conventions are implemented (see `YearMode`) because which one
a given software uses is only decidable against a known-good table:

* ``solar`` — 1 dasha-year = 365.25 real days, added as actual calendar days.
  This is what AstroSage's Vimshottari table matches (the "astrosage_compat"
  mode) and is the default.
* ``savana`` — the traditional 360-day year. Kept for comparison.

Date arithmetic uses a single *nominal timeline*: the birth maha-dasha is placed
as if it had run from its virtual start (birth − elapsed), so every sub-period
that ended before birth falls out naturally as "elapsed" — exactly the
``00/00/00`` rows AstroSage prints.
"""

from __future__ import annotations

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
