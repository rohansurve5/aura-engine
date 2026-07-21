"""Natal chart: sidereal ascendant (lagna), houses, and graha placements.

This is the first module where birth TIME and PLACE are load-bearing: the
ascendant moves ~1° every 4 minutes (a full sign in ~2 hours), so unlike the
geocentric quantities in `engine.positions` it depends on latitude, longitude
and the exact birth instant.

House system — decided here, once:

* We SHIP **Whole Sign** houses (house 1 = the ascendant's whole sign, house
  2 = the next sign, ...). This is the convention of Indian parlour astrology
  and of the references users check us against — the rashi chart on
  AstroSage/DrikPanchang kundlis places grahas in whole signs counted from
  the lagna. It is also defined at every latitude.
* **Placidus cusps** are exposed as `placidus_cusps` because KP astrology
  (post-A3 backlog: cusp sub-lords) requires them and Swiss Ephemeris returns
  them from the same call. They are `None` above the polar circles, where
  Placidus is mathematically undefined (swisseph raises); Whole Sign carries
  on. KP work must also switch `ayanamsa="krishnamurti"` — passing it here is
  supported and produces KP-flavour cusps.

Ayanamsa — `lahiri_vp285` (the library default), because the chart must agree
with the dasha/natal side: a user's lagna nakshatra and their Moon nakshatra
have to come from the SAME zodiac, and the natal/dasha stack is proven against
AstroSage with vp285. The flavour gap to plain `lahiri` (DrikPanchang) is
~23 arcsec at the ascendant — about 1–2 seconds of birth time — far below any
reference site's display precision (golden tests measure both flavours).

Sidereal houses note (the NONUT sibling): planetary sidereal longitudes are
mean-of-date (SEFLG_SIDEREAL forces SEFLG_NONUT — see aura-api/src/natal.ts),
but house cusps come from the APPARENT sidereal time / true equinox and are
then reduced by the same ayanamsa. That asymmetry is Swiss Ephemeris'
convention and matches the reference sites; do not "fix" it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import swisseph as swe

from .ephemeris import DEFAULT_AYANAMSA, julday_utc, set_ayanamsa
from .positions import SIGNS, Position, sidereal_positions
from .timezones import local_to_utc
from .vimshottari import Nakshatra, nakshatra_of

# Above these geographic latitudes Placidus intermediate cusps are undefined
# (the relevant diurnal arcs never intersect the horizon). Swiss raises; we
# publish None and keep the Whole Sign chart. Value = arctic/antarctic circle.
_PLACIDUS_LAT_LIMIT = 66.0


@dataclass(frozen=True)
class Ascendant:
    """The lagna: sidereal longitude of the eastern horizon's ecliptic point."""

    longitude: float          # sidereal, 0–360°

    @property
    def sign_index(self) -> int:
        return int(self.longitude // 30)

    @property
    def sign(self) -> str:
        return SIGNS[self.sign_index]

    @property
    def sign_degrees(self) -> float:
        return self.longitude % 30

    @property
    def nakshatra(self) -> Nakshatra:
        return nakshatra_of(self.longitude)

    def __str__(self) -> str:
        d = self.sign_degrees
        return (
            f"Lagna {int(d):02d}°{int((d - int(d)) * 60):02d}' {self.sign} "
            f"({self.nakshatra.name} pada {self.nakshatra.pada})"
        )


@dataclass(frozen=True)
class Placement:
    """One graha, placed: its Position plus Whole Sign house and nakshatra."""

    position: Position
    house: int                # 1–12, Whole Sign from the lagna

    @property
    def body(self) -> str:
        return self.position.body

    @property
    def sign(self) -> str:
        return self.position.sign

    @property
    def retrograde(self) -> bool:
        return self.position.retrograde

    @property
    def nakshatra(self) -> Nakshatra:
        return nakshatra_of(self.position.longitude)

    def __str__(self) -> str:
        return f"{self.position}  H{self.house}"


@dataclass(frozen=True)
class Chart:
    """A complete sidereal natal chart for one birth instant and place."""

    ascendant: Ascendant
    midheaven: float                        # sidereal MC longitude
    placements: dict[str, Placement]        # Sun..Ketu, traditional order
    house_signs: tuple[str, ...]            # house 1..12 → whole sign
    placidus_cusps: tuple[float, ...] | None  # 12 sidereal cusps; None polar
    ayanamsa: str

    def houses_of(self, *bodies: str) -> tuple[int, ...]:
        return tuple(self.placements[b].house for b in bodies)


def ascendant_sidereal(
    when_utc: datetime,
    lat: float,
    lon: float,
    *,
    ayanamsa: str = DEFAULT_AYANAMSA,
) -> Ascendant:
    """The lagna alone — the cheap path for boundary root-finding and stats.

    Whole Sign ('W') is used purely as the house-system argument; the
    ascendant itself is house-system independent.
    """
    set_ayanamsa(ayanamsa)
    _, ascmc = swe.houses_ex(
        julday_utc(when_utc), lat, lon, b"W", swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    )
    return Ascendant(ascmc[0] % 360)


def compute_chart(
    when_utc: datetime,
    lat: float,
    lon: float,
    *,
    ayanamsa: str = DEFAULT_AYANAMSA,
    true_node: bool = False,
) -> Chart:
    """Full chart at a UTC instant: lagna, houses, all 9 grahas placed."""
    set_ayanamsa(ayanamsa)
    jd = julday_utc(when_utc)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    _, ascmc = swe.houses_ex(jd, lat, lon, b"W", flags)
    asc = Ascendant(ascmc[0] % 360)
    mc = ascmc[1] % 360

    placidus: tuple[float, ...] | None = None
    if abs(lat) < _PLACIDUS_LAT_LIMIT:
        cusps, _ = swe.houses_ex(jd, lat, lon, b"P", flags)
        placidus = tuple(c % 360 for c in cusps)

    positions = sidereal_positions(when_utc, ayanamsa=ayanamsa, true_node=true_node)
    asc_sign = asc.sign_index
    placements = {
        name: Placement(pos, (int(pos.longitude // 30) - asc_sign) % 12 + 1)
        for name, pos in positions.items()
    }
    house_signs = tuple(SIGNS[(asc_sign + i) % 12] for i in range(12))
    return Chart(asc, mc, placements, house_signs, placidus, ayanamsa)


def chart_from_local(
    local_birth: datetime,
    tz_spec: str,
    lat: float,
    lon: float,
    *,
    ayanamsa: str = DEFAULT_AYANAMSA,
    true_node: bool = False,
) -> Chart:
    """Chart from a naive local wall-clock birth time plus a timezone spec.

    `tz_spec` is either "+HH:MM" or an IANA id; IANA resolves the offset AT
    THE BIRTH INSTANT (engine.timezones), so a 1943 Calcutta birth flows
    through war-time DST correctly. There is deliberately NO default zone: a
    silently-wrong timezone is a silently-wrong lagna.
    """
    return compute_chart(
        local_to_utc(local_birth, tz_spec),
        lat,
        lon,
        ayanamsa=ayanamsa,
        true_node=true_node,
    )
