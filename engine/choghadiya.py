"""Choghadiya windows and the three inauspicious kaals.

Everything here is pure arithmetic on sunrise/sunset — no ephemeris calls.
Day choghadiya = 8 equal splits of sunrise→sunset; night = 8 equal splits of
sunset→next sunrise. Kaal windows (rahu/gulika/yamaganda) are single day-parts
selected by weekday.

Sequences and part-numbers below were verified against the DrikPanchang golden
tables for a Saturday and a Friday (day + night, all 16 slots each) and the
kaal windows across all 10 golden days — see tests/golden/drik_panchang.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# The rotating 7-name cycles. The day's first slot is ruled by the weekday
# (index into the cycle); subsequent slots walk the cycle; slot 8 = slot 1.
DAY_CYCLE = ("Udveg", "Chal", "Labh", "Amrit", "Kaal", "Shubh", "Rog")
NIGHT_CYCLE = ("Shubh", "Amrit", "Chal", "Rog", "Kaal", "Labh", "Udveg")

# First day/night choghadiya per Python weekday (Monday=0 … Sunday=6).
_DAY_FIRST = {0: "Amrit", 1: "Rog", 2: "Labh", 3: "Shubh", 4: "Chal", 5: "Kaal", 6: "Udveg"}
_NIGHT_FIRST = {0: "Chal", 1: "Kaal", 2: "Udveg", 3: "Amrit", 4: "Rog", 5: "Labh", 6: "Shubh"}

# Which of the 8 day-parts (1-based) each kaal occupies, per weekday.
_RAHU_PART = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}
_GULIKA_PART = {0: 6, 1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 7}
_YAMAGANDA_PART = {0: 4, 1: 3, 2: 2, 3: 1, 4: 7, 5: 6, 6: 5}

AUSPICIOUS = {"Amrit", "Shubh", "Labh", "Chal"}  # Chal counts as neutral-good


@dataclass(frozen=True)
class Window:
    """A named time window (choghadiya slot or kaal)."""

    name: str
    start: datetime
    end: datetime

    @property
    def auspicious(self) -> bool:
        return self.name in AUSPICIOUS

    def __str__(self) -> str:
        return f"{self.name:7} {self.start:%I:%M %p} – {self.end:%I:%M %p}"


def _split(start: datetime, end: datetime, names: list[str]) -> list[Window]:
    step = (end - start) / 8
    return [
        Window(names[i], start + step * i, start + step * (i + 1)) for i in range(8)
    ]


def _slot_names(cycle: tuple[str, ...], first: str) -> list[str]:
    i = cycle.index(first)
    names = [cycle[(i + k) % 7] for k in range(7)]
    return names + [names[0]]  # 8th slot repeats the 1st


def day_choghadiya(sunrise: datetime, sunset: datetime) -> list[Window]:
    """The 8 day slots for the civil day `sunrise` falls on."""
    wd = sunrise.date().weekday()
    return _split(sunrise, sunset, _slot_names(DAY_CYCLE, _DAY_FIRST[wd]))


def night_choghadiya(sunset: datetime, next_sunrise: datetime) -> list[Window]:
    """The 8 night slots (sunset → next sunrise), named by the *day's* weekday."""
    wd = sunset.date().weekday()
    return _split(sunset, next_sunrise, _slot_names(NIGHT_CYCLE, _NIGHT_FIRST[wd]))


def _day_part(sunrise: datetime, sunset: datetime, part: int, name: str) -> Window:
    step = (sunset - sunrise) / 8
    start = sunrise + step * (part - 1)
    return Window(name, start, start + step)


def rahu_kaal(sunrise: datetime, sunset: datetime) -> Window:
    return _day_part(sunrise, sunset, _RAHU_PART[sunrise.date().weekday()], "Rahu Kaal")


def gulika_kaal(sunrise: datetime, sunset: datetime) -> Window:
    return _day_part(sunrise, sunset, _GULIKA_PART[sunrise.date().weekday()], "Gulika Kaal")


def yamaganda_kaal(sunrise: datetime, sunset: datetime) -> Window:
    return _day_part(
        sunrise, sunset, _YAMAGANDA_PART[sunrise.date().weekday()], "Yamaganda"
    )
