"""Panchang — the five limbs of the Hindu day, plus sunrise/sunset.

For a civil date at a location this computes: sunrise/sunset, tithi, nakshatra,
yoga, karana (each with solved start/end times — crossings are *root-found* on
the relevant angle, never sampled), vaar (weekday) and the moon phase.

Conventions (established against the DrikPanchang golden set, Pune —
see tests/golden/drik_panchang.json and README):

* **Sunrise/sunset = upper limb + atmospheric refraction** (the standard
  astronomical convention). The Hindu-udaya flavour (disc centre, no
  refraction) is ~4 minutes off DrikPanchang; centre+refraction ~1.5 min off;
  upper-limb+refraction matches within ±1 minute on all golden dates.
* Tithi = (Moon − Sun) elongation / 12° — ayanamsa-independent.
* Nakshatra = sidereal Moon / 13°20'. **Panchang defaults to plain Lahiri**
  (DRIKPANCHANG_AYANAMSA): DrikPanchang provably uses it (yoga ends match to
  ±0.8 min; the VP285 flavour that AstroSage's dasha uses drifts ~+0.7 min).
* Yoga = (sidereal Sun + sidereal Moon) / 13°20'.
* Karana = half-tithi (6°), with the four fixed karanas at the cycle edges.

A day's listing window is [sunrise, next sunrise): the element prevailing at
sunrise is listed first, then every element that *starts* before next sunrise.
Kshaya/adhika cases fall out naturally (a window may contain 0, 1 or 2 ends of
the same element type).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

import swisseph as swe

from .ephemeris import DRIKPANCHANG_AYANAMSA, IST, julday_utc, set_ayanamsa
from .timezones import local_to_utc, resolve_tz
from .vimshottari import NAKSHATRA_ARC, NAKSHATRAS

# ── Names ───────────────────────────────────────────────────────────────────
TITHI_NAMES = (
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi",
)  # position 15 is Purnima, 30 is Amavasya — handled in tithi_name()

YOGA_NAMES = (
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti",
)

# Rotating seven karanas (cycle positions 2–57) and the four fixed ones.
KARANA_ROTATING = ("Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti")

VAAR_NAMES = (  # indexed by Python weekday(): Monday=0 … Sunday=6
    "Somawara", "Mangalawara", "Budhawara", "Guruwara", "Shukrawara",
    "Shaniwara", "Raviwara",
)

TITHI_ARC = 12.0
KARANA_ARC = 6.0
YOGA_ARC = NAKSHATRA_ARC  # 13°20'


def tithi_name(index: int) -> str:
    """Name for tithi index 0–29 (0 = Shukla Pratipada … 29 = Amavasya)."""
    if index == 14:
        return "Purnima"
    if index == 29:
        return "Amavasya"
    return TITHI_NAMES[index % 15]


def karana_name(index: int) -> str:
    """Name for karana index 0–59 (0 = Kimstughna, 57–59 the fixed three)."""
    if index == 0:
        return "Kimstughna"
    if index >= 57:
        return ("Shakuni", "Chatushpada", "Naga")[index - 57]
    return KARANA_ROTATING[(index - 1) % 7]


# ── Angle functions (all monotonically increasing mod 360) ──────────────────
_FLG = swe.FLG_SWIEPH


def _tropical(jd: float, body: int) -> float:
    return swe.calc_ut(jd, body, _FLG)[0][0] % 360


def _elongation(jd: float) -> float:
    """Moon − Sun elongation (tithi/karana driver); ayanamsa-independent."""
    return (_tropical(jd, swe.MOON) - _tropical(jd, swe.SUN)) % 360


def _sidereal_moon(jd: float) -> float:
    return swe.calc_ut(jd, swe.MOON, _FLG | swe.FLG_SIDEREAL)[0][0] % 360


def _yoga_sum(jd: float) -> float:
    moon = swe.calc_ut(jd, swe.MOON, _FLG | swe.FLG_SIDEREAL)[0][0]
    sun = swe.calc_ut(jd, swe.SUN, _FLG | swe.FLG_SIDEREAL)[0][0]
    return (moon + sun) % 360


# Approximate advance rates (deg/day) for bracketing the root search.
_RATE = {"tithi": 12.2, "nakshatra": 13.2, "yoga": 14.6}


def _cross_after(angle_fn, target: float, jd0: float, rate: float) -> float:
    """First jd > jd0 where angle_fn (increasing mod 360) crosses `target`."""
    togo = (target - angle_fn(jd0)) % 360
    if togo < 1e-9:
        togo = 360.0
    lo = jd0 + togo / rate * 0.6           # conservative bracket
    hi = jd0 + togo / rate * 1.6 + 0.05

    def signed(jd: float) -> float:
        return ((angle_fn(jd) - target + 180) % 360) - 180

    while signed(lo) > 0:                   # walk back if bracket overshot
        lo -= 0.1
    while signed(hi) < 0:
        hi += 0.1
    for _ in range(60):                     # bisect to well under a second
        mid = (lo + hi) / 2
        if signed(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _cross_before(angle_fn, target: float, jd0: float, rate: float) -> float:
    """Last jd < jd0 where angle_fn crossed `target` (element start time)."""
    gone = (angle_fn(jd0) - target) % 360
    approx = jd0 - gone / rate
    return _cross_after(angle_fn, target, approx - 0.2, rate)


# ── Sunrise / sunset ────────────────────────────────────────────────────────
def _rise_set(jd_start: float, lat: float, lon: float, *, rise: bool) -> float:
    """Next sunrise/sunset (JD UT) after jd_start; upper limb + refraction."""
    flag = swe.CALC_RISE if rise else swe.CALC_SET
    res, times = swe.rise_trans(jd_start, swe.SUN, flag, (lon, lat, 0.0))
    if res != 0:
        raise ValueError("Sun does not rise/set here (polar latitude?)")
    return times[0]


def _jd_to_local(jd: float, tz: tzinfo) -> datetime:
    y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
    utc = datetime(y, m, d, tzinfo=UTC) + timedelta(hours=h)
    return utc.astimezone(tz).replace(tzinfo=None, microsecond=0)


# ── Result types ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Element:
    """One tithi / nakshatra / yoga / karana spell with solved boundaries."""

    name: str
    index: int
    start: datetime  # local
    end: datetime    # local

    def __str__(self) -> str:
        return f"{self.name} upto {self.end:%I:%M %p, %b %d}"


@dataclass(frozen=True)
class Panchang:
    date: date
    location: tuple[float, float]  # lat, lon
    vaar: str                      # Sanskrit weekday name
    weekday: str                   # English
    sunrise: datetime
    sunset: datetime
    next_sunrise: datetime
    tithi: tuple[Element, ...]
    nakshatra: tuple[Element, ...]
    yoga: tuple[Element, ...]
    karana: tuple[Element, ...]
    paksha: str                    # "Shukla" | "Krishna"
    phase_fraction: float          # elongation/360 at sunrise
    waxing: bool


def _elements(
    angle_fn, arc: float, name_fn, rate: float,
    jd_sunrise: float, jd_next_sunrise: float, tz: tzinfo,
) -> tuple[Element, ...]:
    """Prevailing element at sunrise + all that start before next sunrise."""
    total = int(round(360 / arc))
    idx = int(angle_fn(jd_sunrise) // arc)
    jd_start = _cross_before(angle_fn, idx * arc, jd_sunrise, rate)
    out: list[Element] = []
    while jd_start < jd_next_sunrise:
        jd_end = _cross_after(angle_fn, ((idx + 1) % total) * arc, jd_start, rate)
        out.append(
            Element(name_fn(idx), idx, _jd_to_local(jd_start, tz), _jd_to_local(jd_end, tz))
        )
        idx = (idx + 1) % total
        jd_start = jd_end
    return tuple(out)


def compute_panchang(
    day: date,
    lat: float,
    lon: float,
    *,
    tz: tzinfo = IST,
    ayanamsa: str = DRIKPANCHANG_AYANAMSA,
) -> Panchang:
    """Full panchang for the sunrise-day of `day` at (lat, lon)."""
    set_ayanamsa(ayanamsa)

    local_midnight = datetime.combine(day, time()).replace(tzinfo=tz)
    jd_midnight = julday_utc(local_midnight)
    jd_sunrise = _rise_set(jd_midnight, lat, lon, rise=True)
    jd_sunset = _rise_set(jd_sunrise, lat, lon, rise=False)
    jd_next_sunrise = _rise_set(jd_sunrise + 0.01, lat, lon, rise=True)

    tithi = _elements(
        _elongation, TITHI_ARC, tithi_name, _RATE["tithi"],
        jd_sunrise, jd_next_sunrise, tz,
    )
    nakshatra = _elements(
        _sidereal_moon, NAKSHATRA_ARC, lambda i: NAKSHATRAS[i], _RATE["nakshatra"],
        jd_sunrise, jd_next_sunrise, tz,
    )
    yoga = _elements(
        _yoga_sum, YOGA_ARC, lambda i: YOGA_NAMES[i], _RATE["yoga"],
        jd_sunrise, jd_next_sunrise, tz,
    )
    karana = _elements(
        _elongation, KARANA_ARC, karana_name, _RATE["tithi"],
        jd_sunrise, jd_next_sunrise, tz,
    )

    elong = _elongation(jd_sunrise)
    return Panchang(
        date=day,
        location=(lat, lon),
        vaar=VAAR_NAMES[day.weekday()],
        weekday=day.strftime("%A"),
        sunrise=_jd_to_local(jd_sunrise, tz),
        sunset=_jd_to_local(jd_sunset, tz),
        next_sunrise=_jd_to_local(jd_next_sunrise, tz),
        tithi=tithi,
        nakshatra=nakshatra,
        yoga=yoga,
        karana=karana,
        paksha="Shukla" if elong < 180 else "Krishna",
        phase_fraction=elong / 360,
        waxing=elong < 180,
    )


# ── Panchang AT AN INSTANT (the chart file's birth panchang) ────────────────
# compute_panchang above lists a DAY's elements with solved boundaries. A birth
# needs the other question: which tithi / nakshatra / yoga / karana prevailed
# AT one instant. That is a pure read of the same angle functions — no root
# finding — so it is exact wherever the angles are, and the only judgement
# call is the zodiac, which is the CALLER'S: the chart file passes the chart's
# own lahiri_vp285 so the birth nakshatra here can never disagree with the
# Moon's nakshatra in the planet table (the ~23″ flavour gap to plain Lahiri
# would otherwise split them for a Moon within ~1 minute of birth time of a
# boundary). Tithi and karana are ayanamsa-free; yoga and nakshatra are not.

@dataclass(frozen=True)
class InstantPanchang:
    """The five limbs (minus vara, which needs a place) at one instant."""

    tithi_index: int        # 0–29: 0 = Shukla Pratipada … 14 Purnima … 29 Amavasya
    tithi: str
    paksha: str             # "Shukla" | "Krishna"
    nakshatra_index: int    # 0–26
    nakshatra: str
    pada: int               # 1–4
    yoga_index: int         # 0–26
    yoga: str
    karana_index: int       # 0–59
    karana: str
    elongation: float       # Moon − Sun, degrees — the tithi/karana driver
    yoga_sum: float         # sidereal Sun + Moon, degrees (mod 360)
    moon_longitude: float   # sidereal Moon, degrees


def panchang_at(when_utc: datetime, *, ayanamsa: str = DRIKPANCHANG_AYANAMSA) -> InstantPanchang:
    """Tithi, nakshatra (+pada), yoga and karana prevailing at `when_utc`.

    Indices use floor(angle / arc) — written with math.floor, not `//`, so the
    Worker's Math.floor port takes the identical branch at every non-boundary
    angle (Python's float `//` is fmod-based and can differ at an exact edge).
    """
    set_ayanamsa(ayanamsa)
    jd = julday_utc(when_utc)
    elong = _elongation(jd)
    ysum = _yoga_sum(jd)
    moon = _sidereal_moon(jd)

    tithi = math.floor(elong / TITHI_ARC) % 30
    karana = math.floor(elong / KARANA_ARC) % 60
    yoga = math.floor(ysum / YOGA_ARC) % 27
    nak = math.floor(moon / NAKSHATRA_ARC) % 27
    pada = math.floor((moon - nak * NAKSHATRA_ARC) / (NAKSHATRA_ARC / 4)) + 1
    return InstantPanchang(
        tithi_index=tithi,
        tithi=tithi_name(tithi),
        paksha="Shukla" if tithi < 15 else "Krishna",
        nakshatra_index=nak,
        nakshatra=NAKSHATRAS[nak],
        pada=min(pada, 4),
        yoga_index=yoga,
        yoga=YOGA_NAMES[yoga],
        karana_index=karana,
        karana=karana_name(karana),
        elongation=elong,
        yoga_sum=ysum,
        moon_longitude=moon,
    )


@dataclass(frozen=True)
class Vara:
    """The Vedic weekday of an instant: it runs sunrise to sunrise."""

    vara: str                     # Sanskrit name of the Vedic weekday
    weekday: str                  # its English name
    civil_weekday: str            # the calendar weekday of the local date
    sunrise: datetime | None      # local sunrise on the civil date; None = none
    before_sunrise: bool          # True → the vara is the PREVIOUS civil day's


def vara_at(local: datetime, tz_spec: str, lat: float, lon: float) -> Vara:
    """Vara for a local wall-clock instant at a place.

    A Hindu day begins at sunrise, so a birth at 04:47 on a Saturday, before
    that morning's sunrise, is born on Friday's vara (Shukrawara) — the
    calendar weekday and the vara differ. Sunrise here is compute_panchang's
    (upper limb + refraction, ±1 min of DrikPanchang). If the Sun does not
    rise on that civil date (polar day/night) the vara falls back to the civil
    weekday and `sunrise` is None — stated, never invented.
    """
    tz = resolve_tz(tz_spec)
    day = local.date()
    civil = day.strftime("%A")
    jd_birth = julday_utc(local_to_utc(local, tz_spec))
    jd_midnight = julday_utc(datetime.combine(day, time()).replace(tzinfo=tz))
    try:
        jd_rise = _rise_set(jd_midnight, lat, lon, rise=True)
    except ValueError:
        jd_rise = None
    sunrise = _jd_to_local(jd_rise, tz) if jd_rise is not None else None
    if sunrise is None or sunrise.date() != day:
        return Vara(VAAR_NAMES[day.weekday()], civil, civil, None, False)
    before = jd_birth < jd_rise
    vara_day = day - timedelta(days=1) if before else day
    return Vara(VAAR_NAMES[vara_day.weekday()], vara_day.strftime("%A"), civil, sunrise, before)
