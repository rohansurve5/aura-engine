"""Shared fixtures + golden-comparison helpers for the engine tests."""

from __future__ import annotations

import json
import os
from datetime import date, datetime

import pytest

from engine.ephemeris import ASTROSAGE_AYANAMSA
from engine.positions import positions_from_ist
from engine.vimshottari import DashaResult, compute_dasha

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "astrosage_dasha.json")

# Rohan's birth data (IST). Place/coordinates were not provided; Vimshottari
# depends only on the geocentric Moon, which is location-independent.
BIRTH = datetime(1989, 9, 23, 4, 47)


@pytest.fixture(scope="session")
def golden() -> dict:
    with open(GOLDEN) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def moon_longitude() -> float:
    return positions_from_ist(BIRTH, ayanamsa=ASTROSAGE_AYANAMSA)["Moon"].longitude


@pytest.fixture(scope="session")
def result(moon_longitude: float) -> DashaResult:
    return compute_dasha(moon_longitude, BIRTH, year_mode="solar", levels=3, cycles=2)


def as_date(iso: str) -> date:
    return date.fromisoformat(iso)


def antar_deltas(result: DashaResult, golden: dict) -> list[tuple[str, str, str, int]]:
    """(maha, antar, golden_end, delta_days) for every post-birth antar date."""
    rows: list[tuple[str, str, str, int]] = []
    for gi, gm in enumerate(golden["maha"]):
        maha = result.mahas[gi]
        for ai, ga in enumerate(gm["antar"]):
            if ga["end"] is None:
                continue
            delta = (maha.children[ai].end.date() - as_date(ga["end"])).days
            rows.append((gm["lord"], ga["lord"], ga["end"], delta))
    return rows
