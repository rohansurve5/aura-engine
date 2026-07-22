"""Muhurat — auspicious timing selection, and its honest personalisation limit.

This composes the pieces the engine already owns — panchang sunrise/sunset,
`engine.choghadiya` (the 16 slots + the three kaals, both already
DrikPanchang-verified and engine-vs-Worker cross-validated), and the A3
ascendant — into a *ranked* list of candidate windows for a purpose.

The central, measured finding (scripts/measure_muhurat.py, recorded in
docs/MUHURAT.md) shapes the whole design:

  * The candidate WINDOW LIST is a pure function of (place, day, purpose) —
    choghadiya + kaal + the rising-sign class. **Identical for every user.**
    This is "auspicious timings for your day and place", NOT personal.
  * The classical PERSONAL factors that need no birth time — tarabala and
    chandrabala — are DAY-CONSTANT, so they add equally to every window and
    provably cannot re-rank them (measured 0%). They are the existing daily
    energy score, not a per-window timing.
  * The ONLY factor that personalises WHICH window ranks best is the rising
    sign at the window taken as a Whole-Sign house from the user's natal lagna
    — which needs a birth time (A3). It genuinely re-ranks (top window differs
    on 40-62% of user pairs) but keys ONLY on the natal lagna SIGN: it is a
    12-WAY personalisation, the same altitude the A5 area scores ship at, NOT a
    per-individual reading. Two users sharing a lagna sign get the same list.

So `rank_windows` takes `natal_lagna_sign` and reports honestly: absent it, the
result is flagged impersonal; present, it is flagged `personal_12way`. There is
no third mode — a noon-lagna personalisation is never fabricated (the
docs/ASCENDANT.md rule).

The voice layer (DESCRIPTORS + the gate constants) is the §3 anti-fear-selling
surface: a kaal is reported as a period the tradition sets aside, WITHOUT ever
implying harm from acting in it. tests/test_muhurat_gates_falsify.py mutates
this exact corpus and calls the real gates, exactly as the compatibility and
transit batteries do.

Engine + gates only — no Worker port, no Neon seed, no UI (the choghadiya port
already exists in aura-api/src/window.ts and is gated by crossval_window.py).
Binding condition mirroring A3/compatibility: if a *ranked, personalised*
muhurat ever becomes app-visible, it must ship the lagna via the already-gated
ascendant port and a golden-parity gate over the ranking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from .choghadiya import (
    day_choghadiya,
    gulika_kaal,
    night_choghadiya,
    rahu_kaal,
    yamaganda_kaal,
)

# ── The purpose model — classical choghadiya associations only ──────────────
# Choghadiya→purpose is well-defined and agrees across B.V. Raman, DrikPanchang
# and Prokerala. Purpose-specific NAKSHATRA menus vary wildly between traditions
# (Muhurta Chintamani vs regional almanacs), so they are deliberately CUT — an
# arbitrary single answer would be false precision (the task's §1 instruction).
PURPOSES: dict[str, frozenset[str]] = {
    "start":    frozenset({"Amrit", "Shubh", "Labh"}),           # any new undertaking
    "business": frozenset({"Labh", "Amrit", "Shubh"}),           # gain-seeking, purchase
    "travel":   frozenset({"Chal", "Amrit", "Shubh", "Labh"}),   # Chal = movement
    "ceremony": frozenset({"Shubh", "Amrit"}),                   # puja, auspicious rite
}

# Within-set preference so a stable ranking exists (impersonal: day + place).
CHOG_RANK = {"Amrit": 3, "Shubh": 2, "Labh": 2, "Chal": 1}

# Rising-sign class → purpose fit. Chara/Sthira/Dvisvabhava (movable/fixed/dual)
# is the one lagna rule classical electional broadly agrees on. Impersonal — the
# same sign rises for everyone at a place/instant. 0=Aries .. 11=Pisces.
MOVABLE = frozenset({0, 3, 6, 9})     # Aries Cancer Libra Capricorn
FIXED = frozenset({1, 4, 7, 10})      # Taurus Leo Scorpio Aquarius
DUAL = frozenset({2, 5, 8, 11})       # Gemini Virgo Sagittarius Pisces
LAGNA_CLASS_FIT = {
    "start": FIXED, "business": FIXED, "ceremony": FIXED, "travel": MOVABLE,
}

# The birth-time-gated personal term: the window's rising sign as a Whole-Sign
# house from the user's natal lagna. Kendras (1/4/7/10) + trikonas (5/9) are the
# electional sweet spots ("elect a moment whose lagna is a kendra/trikona from
# the native"). This is the ONLY term that keys on the user AND varies within a
# day — hence the whole personalisation, and hence the birth-time gate.
GOOD_LAGNA_HOUSE = frozenset({1, 4, 5, 7, 9, 10})


@dataclass(frozen=True)
class Candidate:
    """One ranked auspicious window."""

    name: str                 # choghadiya name (Amrit/Shubh/Labh/Chal)
    start: datetime
    end: datetime
    lagna_sign: int           # rising sign at the window midpoint (0-11)
    score: int
    personal: bool            # did the lagna house term contribute to the score?


def _lagna_house(lagna_sign: int, natal_lagna_sign: int) -> int:
    """The window's rising sign as a Whole-Sign house (1-12) from the native."""
    return (lagna_sign - natal_lagna_sign) % 12 + 1


def score_window(
    name: str, lagna_sign: int, purpose: str, natal_lagna_sign: int | None
) -> int:
    """Impersonal choghadiya + lagna-class score, plus the birth-time lagna-house
    term when a natal lagna is given. NB: tarabala/chandrabala are intentionally
    absent — they are day-constant and cannot re-rank windows (measured 0%)."""
    s = CHOG_RANK.get(name, 0)
    if lagna_sign in LAGNA_CLASS_FIT[purpose]:
        s += 1
    if natal_lagna_sign is not None:
        if _lagna_house(lagna_sign, natal_lagna_sign) in GOOD_LAGNA_HOUSE:
            s += 2
    return s


def rank_windows(
    windows: list[tuple[str, datetime, datetime, int]],
    kaal_starts: set[datetime],
    purpose: str,
    *,
    natal_lagna_sign: int | None = None,
) -> dict:
    """Rank candidate windows for a purpose. `windows` is the 16 choghadiya slots
    as (name, start, end, lagna_sign); `kaal_starts` the start instants of the
    three kaals (their day slots are excluded). Ephemeris-free and pure so the
    ranking is unit-testable without Swiss Ephemeris.

    Returns the ranked candidates AND an honest `personalisation` label:
      * 'impersonal'    — no birth time; identical for every user at place/day;
      * 'personal_12way'— birth time; re-ranked by natal lagna SIGN (12 classes).
    """
    if purpose not in PURPOSES:
        raise ValueError(f"unknown purpose {purpose!r}; one of {sorted(PURPOSES)}")
    favoured = PURPOSES[purpose]
    cands: list[Candidate] = []
    for name, start, end, lagna_sign in windows:
        if start in kaal_starts or name not in favoured:
            continue
        s = score_window(name, lagna_sign, purpose, natal_lagna_sign)
        personal = (
            natal_lagna_sign is not None
            and _lagna_house(lagna_sign, natal_lagna_sign) in GOOD_LAGNA_HOUSE
        )
        cands.append(Candidate(name, start, end, lagna_sign, s, personal))
    # Best score first; impersonal stable tie-break on start time so any
    # reordering is a real personal effect, never tie noise.
    cands.sort(key=lambda c: (-c.score, c.start))
    return {
        "purpose": purpose,
        "personalisation": "personal_12way" if natal_lagna_sign is not None else "impersonal",
        "candidates": cands,
    }


def _windows_for(
    day: date, lat: float, lon: float, tz: tzinfo
) -> tuple[list[tuple[str, datetime, datetime, int]], set[datetime]]:
    """Build the 16 choghadiya slots (each with its midpoint rising sign) and the
    kaal start instants for (day, place). Imports Swiss Ephemeris lazily so the
    pure ranking layer above stays importable without it."""
    import swisseph as swe

    from .chart import ascendant_sidereal
    from .ephemeris import IST
    from .timezones import local_to_utc

    def _rise_set(jd0: float, *, rise: bool) -> float:
        flag = swe.CALC_RISE if rise else swe.CALC_SET
        res, times = swe.rise_trans(jd0, swe.SUN, flag, (lon, lat, 0.0))
        if res != 0:
            raise ValueError("Sun does not rise/set here (polar latitude?)")
        return times[0]

    from datetime import UTC

    def _to_local(jd: float) -> datetime:
        y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
        utc = datetime(y, m, d, tzinfo=UTC) + timedelta(hours=h)
        return utc.astimezone(tz).replace(tzinfo=None, microsecond=0)

    midnight = datetime.combine(day, time()).replace(tzinfo=tz).astimezone(UTC)
    jd_mid = swe.julday(midnight.year, midnight.month, midnight.day,
                        midnight.hour + midnight.minute / 60)
    jd_rise = _rise_set(jd_mid, rise=True)
    jd_set = _rise_set(jd_rise, rise=False)
    jd_next = _rise_set(jd_set, rise=True)
    rise, sset, nxt = _to_local(jd_rise), _to_local(jd_set), _to_local(jd_next)

    slots = day_choghadiya(rise, sset) + night_choghadiya(sset, nxt)
    kaal_starts = {
        rahu_kaal(rise, sset).start,
        gulika_kaal(rise, sset).start,
        yamaganda_kaal(rise, sset).start,
    }
    # NB: this offset trick is IST-safe (no DST); non-IST callers should route
    # through the fixed-offset method scripts/crossval_window.py documents.
    offset = "+05:30" if tz is IST else None
    windows = []
    for w in slots:
        mid = w.start + (w.end - w.start) / 2
        if offset:
            when_utc = local_to_utc(mid, offset)
        else:
            when_utc = mid.replace(tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
        asc = ascendant_sidereal(when_utc, lat, lon)
        windows.append((w.name, w.start, w.end, asc.sign_index))
    return windows, kaal_starts


def auspicious_timings(
    day: date, lat: float, lon: float, purpose: str, *,
    natal_lagna_sign: int | None = None, tz: tzinfo | None = None,
) -> dict:
    """The ephemeris entrypoint: ranked auspicious windows for (day, place,
    purpose). IST by default (the launch market). See rank_windows for the honest
    personalisation contract."""
    from .ephemeris import IST

    windows, kaal_starts = _windows_for(day, lat, lon, tz or IST)
    return rank_windows(windows, kaal_starts, purpose, natal_lagna_sign=natal_lagna_sign)


# ═══════════════════════════════════════════════════════════════════════════
# The voice layer — §3: report a BAD window WITHOUT implying consequences
# ═══════════════════════════════════════════════════════════════════════════
# Rahu kaal is the single most weaponised timing in this market — used to make
# people afraid to act. Every string the product may show lives here so the gate
# battery can mutate the exact corpus the code ships. The inauspicious lines
# name a period the tradition sets aside; they NEVER state or imply an outcome,
# and (the symmetry gate) they never read heavier than the auspicious ones.
DESCRIPTORS: dict[str, dict[str, str]] = {
    "band": {
        # Same stance, matched weight — the auspicious/inauspicious symmetry.
        "auspicious": (
            "An auspicious window in this tradition: the choghadiya is a "
            "favourable one for your purpose. A supportive time to begin, in one "
            "tradition's reckoning rather than a promise."
        ),
        "inauspicious": (
            "A window this tradition sets aside for the purpose: the choghadiya "
            "is a less favourable one here. It is one tradition's timing rather "
            "than a rule, and many good things happen in these hours too."
        ),
    },
    "kaal": {
        # Named, framed, agentive, outcome-free. The rahu line in particular must
        # never imply harm from acting during it.
        "Rahu Kaal": (
            "Rahu Kaal: a period many traditions set aside for beginnings, "
            "counted from sunrise by the weekday. It is a customary pause, not a "
            "warning of harm, and plenty is done in these hours every day."
        ),
        "Gulika Kaal": (
            "Gulika Kaal: another weekday-counted period the tradition treats as "
            "less favourable for starts. A note to weigh, not a rule to fear."
        ),
        "Yamaganda": (
            "Yamaganda: a weekday-counted period some traditions set aside for "
            "new work. It is a customary preference, never a prediction."
        ),
    },
    "personalisation": {
        # The honesty line the paywall/reading must carry, per mode.
        "impersonal": (
            "These are auspicious timings for your day and place — the same for "
            "everyone here today. Add your birth time to see the windows that "
            "suit your own rising sign."
        ),
        "personal_12way": (
            "These windows are ranked for your rising sign — timings whose "
            "moment favours your own chart, in one tradition's reckoning."
        ),
    },
}

# Words that turn a timing note into a decree of harm. We describe periods the
# tradition sets aside; we never say a person will suffer for acting in one.
VERDICT_WORDS = frozenset({
    "cursed", "doomed", "disaster", "catastrophe", "forbidden", "banned",
    "dangerous hour", "evil hour", "will fail", "will suffer", "will go wrong",
    "brings misfortune", "invites disaster", "never begin", "must not", "ruined",
})

# Outcome promises built from ordinary words — the fatalism a vocabulary scan
# misses ("acting now leads to loss", "harms the venture"). The §3 signature.
# The transitive-verb branch requires an OBJECT so the corpus's own defusing
# clause ("not a warning of harm") — the noun, in a negation — is not a false
# positive; only harm asserted ON something ("harms the venture") is caught.
OUTCOME = re.compile(
    r"\b(?:harms?|damages?|ruins?|destroys?|hurts?|wrecks?)\s+"
    r"(?:the|a|an|any|your|it|this|every)\b"
    r"|\b(?:leads?|results?)\s+(?:to|in)\b"
    r"|\b(?:ends? in|dooms?|prevents?"
    r"|brings? (?:loss|failure|misfortune|ruin|trouble)"
    r"|causes? (?:loss|failure|harm|ruin))\b"
    r"|\bwill (?:suffer|fail|break|collapse|go wrong)\b"
)

# Framing + agency the kaal/inauspicious lines must keep (the fatalism gate).
FRAME = re.compile(r"\btradition")
AGENCY = re.compile(
    r"not a warning|not a rule|not a prediction|customary|rather than a|"
    r"weigh, not|plenty is done|many good things|set aside"
)


def describe_band(name: str) -> str:
    return DESCRIPTORS["band"][name]


def describe_kaal(name: str) -> str:
    return DESCRIPTORS["kaal"][name]


def describe_timings(result: dict) -> dict:
    """Attach the band-neutral, non-consequence voice to a ranking. The reading
    always carries the honest personalisation line for its mode."""
    lines = [DESCRIPTORS["personalisation"][result["personalisation"]]]
    if result["candidates"]:
        lines.append(DESCRIPTORS["band"]["auspicious"])
    return {**result, "lines": lines}
