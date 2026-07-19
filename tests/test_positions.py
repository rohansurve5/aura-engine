"""Sanity + invariants for sidereal positions.

These are not golden-matched against AstroSage's planet table (that doc wasn't
provided), so they assert structural correctness and the one value the dasha
depends on: the natal Moon.
"""

from __future__ import annotations

from engine.ephemeris import ASTROSAGE_AYANAMSA
from engine.positions import BODIES, positions_from_ist

from .conftest import BIRTH


def test_all_bodies_present():
    pos = positions_from_ist(BIRTH, ayanamsa=ASTROSAGE_AYANAMSA)
    assert set(pos) == set(BODIES)


def test_longitudes_in_range():
    pos = positions_from_ist(BIRTH, ayanamsa=ASTROSAGE_AYANAMSA)
    for p in pos.values():
        assert 0.0 <= p.longitude < 360.0


def test_ketu_opposes_rahu():
    pos = positions_from_ist(BIRTH, ayanamsa=ASTROSAGE_AYANAMSA)
    diff = (pos["Ketu"].longitude - pos["Rahu"].longitude) % 360
    assert abs(diff - 180.0) < 1e-6


def test_nodes_are_retrograde():
    # The mean lunar node always moves backwards.
    pos = positions_from_ist(BIRTH, ayanamsa=ASTROSAGE_AYANAMSA)
    assert pos["Rahu"].retrograde
    assert pos["Ketu"].retrograde


def test_moon_matches_birth_chart():
    # Ardra, pada 4 → Rahu-lorded → drives the RAHU balance.
    moon = positions_from_ist(BIRTH, ayanamsa=ASTROSAGE_AYANAMSA)["Moon"]
    assert 77.0 < moon.longitude < 77.2
    assert moon.sign == "Gemini"


def test_location_independent():
    # Geocentric longitudes must not depend on lat/lon.
    a = positions_from_ist(BIRTH, ayanamsa=ASTROSAGE_AYANAMSA)
    b = positions_from_ist(BIRTH, lat=19.99, lon=73.79, ayanamsa=ASTROSAGE_AYANAMSA)
    for name in BODIES:
        assert a[name].longitude == b[name].longitude
