"""Aura Calculation Engine — verifiable Vedic astrology calculations.

Public surface:

    from engine import positions_from_ist, compute_dasha

Everything is deterministic and covered by golden tests against a known-good
AstroSage chart (see ``tests/``).
"""

from __future__ import annotations

from .choghadiya import (
    Window,
    day_choghadiya,
    gulika_kaal,
    night_choghadiya,
    rahu_kaal,
    yamaganda_kaal,
)
from .daily import CANONICAL_LOCATION, build_daily_sky
from .ephemeris import (
    ASTROSAGE_AYANAMSA,
    AYANAMSAS,
    DEFAULT_AYANAMSA,
    DRIKPANCHANG_AYANAMSA,
)
from .panchang import Element, Panchang, compute_panchang
from .positions import (
    BODIES,
    Position,
    ayanamsa_at,
    positions_from_ist,
    sidereal_positions,
)
from .scoring import (
    SCORE_RULES_VERSION,
    all_guidance,
    guidance_for_nakshatra,
    load_rules_from_db,
    load_rules_from_json,
    tara_of,
)
from .vimshottari import (
    Balance,
    DashaResult,
    Nakshatra,
    Period,
    RoundedMaha,
    compute_dasha,
    format_astrosage,
    nakshatra_of,
    rounded_table,
)

__all__ = [
    "ASTROSAGE_AYANAMSA",
    "AYANAMSAS",
    "DEFAULT_AYANAMSA",
    "DRIKPANCHANG_AYANAMSA",
    "CANONICAL_LOCATION",
    "SCORE_RULES_VERSION",
    "build_daily_sky",
    "all_guidance",
    "guidance_for_nakshatra",
    "load_rules_from_db",
    "load_rules_from_json",
    "tara_of",
    "BODIES",
    "Element",
    "Panchang",
    "Window",
    "compute_panchang",
    "day_choghadiya",
    "night_choghadiya",
    "rahu_kaal",
    "gulika_kaal",
    "yamaganda_kaal",
    "Position",
    "ayanamsa_at",
    "positions_from_ist",
    "sidereal_positions",
    "Balance",
    "DashaResult",
    "Nakshatra",
    "Period",
    "RoundedMaha",
    "compute_dasha",
    "format_astrosage",
    "nakshatra_of",
    "rounded_table",
]

__version__ = "0.1.0"
