"""Ashtakoota (Guna Milan) compatibility and Mangal (Kuja) Dosha.

This module is the *math* for Block 4 compatibility. It is deliberately narrow:
it turns two people's Moon placements (and, for Mangal Dosha, one full natal
chart) into the classical eight-koota tally and the Mangal flags — and nothing
else. The descriptive, agency-preserving *voice* layer is `describe_match`
below; it is small and band-neutral, and it is gated exactly like every other
corpus in this repo (see `tests/test_compatibility_gates_falsify.py`).

WHAT IS EXACT, AND WHY THIS IS NOT A CROSS-VALIDATED COMPUTATION
----------------------------------------------------------------
Unlike `positions`/`vimshottari`/`chart`, nothing here is an *independent
numerical computation* to be cross-validated against a reference site's
ephemeris. Every koota is a **deterministic table lookup** keyed off two exact,
already-cross-validated quantities:

* the **Moon nakshatra** (index 0-26) — exact, gates every aura-api deploy via
  `crossval_natal.py`; and
* the **Moon rashi** (sign 0-11) — likewise exact.

So the *inputs* are proven to the dasha/natal standard. The *tables* are
classical constants (Brihat Parashara Hora Shastra; B. V. Raman, *Muhurtha*);
the golden test pins their encodings and the full per-koota breakdown for a
spread of couples. What CANNOT be "proven correct" the way an ephemeris can is
the choice of table where **the tradition itself disagrees** — the parihar
(cancellation) rules, the Graha Maitri fractional scheme, the Vashya matrix,
the Yoni intermediate values. Those are documented as divergences in
`docs/COMPATIBILITY.md`, not smoothed over. The parts that actually drive a
"warning" — Nadi dosha (0/8), Bhakoot dosha (0/7), the Yoni sworn-enemy pole
(0/4) — are the *unambiguous* ones; the contested fractions live in the low
koota weights (Vashya 2, the Graha Maitri middle).

Birth time: the koota math needs **no** birth time — the Moon nakshatra/rashi
are what the product already has (with the documented noon-assumption caveat
when a birth time is unknown). Mangal Dosha's lagna form DOES need a birth time
(it counts Mars's house from the ascendant); its Moon/Venus forms do not. See
`mangal_dosha`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .chart import Chart
from .vimshottari import nakshatra_of

# ── Sign lords (rashi adhipati) ─────────────────────────────────────────────
SIGN_LORDS = (
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
)

# ── Varna (koota 1, max 1) — from Moon RASHI ────────────────────────────────
# Rank Brahmin 4 > Kshatriya 3 > Vaishya 2 > Shudra 1. The classical rule is
# directional and gendered: 1 point iff the *groom's* varna >= the *bride's*.
# The gender asymmetry is itself a product-honesty problem — see docs.
_VARNA_RANK = {"Brahmin": 4, "Kshatriya": 3, "Vaishya": 2, "Shudra": 1}
# sign index 0..11 -> varna
VARNA_BY_SIGN = (
    "Kshatriya",  # Aries
    "Vaishya",    # Taurus
    "Shudra",     # Gemini
    "Brahmin",    # Cancer
    "Kshatriya",  # Leo
    "Vaishya",    # Virgo
    "Shudra",     # Libra
    "Brahmin",    # Scorpio
    "Kshatriya",  # Sagittarius
    "Vaishya",    # Capricorn
    "Shudra",     # Aquarius
    "Brahmin",    # Pisces
)

# ── Vashya (koota 2, max 2) — from Moon RASHI ───────────────────────────────
# The five vashya groups. NOTE (divergence): the classical membership splits
# Sagittarius and Capricorn at the half-sign, which is degree-dependent. We use
# the whole-sign majority convention (Sagittarius -> human's group per Raman's
# "first half", Capricorn -> quadruped) and flag the split in docs. Vashya is
# worth only 2 points, so this low-stakes divergence never moves a dosha.
_CHATUSHPADA, _MANAVA, _JALACHARA, _VANACHARA, _KEETA = (
    "Chatushpada", "Manava", "Jalachara", "Vanachara", "Keeta",
)
VASHYA_GROUP_BY_SIGN = (
    _CHATUSHPADA,  # Aries
    _CHATUSHPADA,  # Taurus
    _MANAVA,       # Gemini
    _JALACHARA,    # Cancer
    _VANACHARA,    # Leo
    _MANAVA,       # Virgo
    _MANAVA,       # Libra
    _KEETA,        # Scorpio
    _MANAVA,       # Sagittarius (first-half convention)
    _CHATUSHPADA,  # Capricorn (first-half convention)
    _MANAVA,       # Aquarius
    _JALACHARA,    # Pisces
)
# Points[groom_group][bride_group]; asymmetric by tradition (magnetic control).
# Source: the widely published 5x5 vashya matrix (Steve Hora; freehoroscopes).
_VASHYA_POINTS = {
    _CHATUSHPADA: {_CHATUSHPADA: 2, _MANAVA: 1, _JALACHARA: 1, _VANACHARA: 1.5, _KEETA: 1},
    _MANAVA:      {_CHATUSHPADA: 1, _MANAVA: 2, _JALACHARA: 1.5, _VANACHARA: 0, _KEETA: 1},
    _JALACHARA:   {_CHATUSHPADA: 1, _MANAVA: 1.5, _JALACHARA: 2, _VANACHARA: 1, _KEETA: 1},
    _VANACHARA:   {_CHATUSHPADA: 0, _MANAVA: 0, _JALACHARA: 0, _VANACHARA: 2, _KEETA: 0},
    _KEETA:       {_CHATUSHPADA: 1, _MANAVA: 1, _JALACHARA: 1, _VANACHARA: 0, _KEETA: 2},
}

# ── Tara / Dina (koota 3, max 3) — from Moon NAKSHATRA ───────────────────────
# Count from one star to the other, take remainder mod 9. Remainders 3, 5, 7
# (Vipat, Pratyak, Naidhana) are inauspicious. Both directions auspicious -> 3,
# one -> 1.5, neither -> 0.
_TARA_BAD_REMAINDERS = {3, 5, 7}

# ── Yoni (koota 4, max 4) — from Moon NAKSHATRA ──────────────────────────────
# One of 14 animal yonis per nakshatra (B. V. Raman). The intermediate values
# (1/2/3) of the 14x14 matrix vary a little across sources; the two poles that
# matter — same animal (4) and the seven sworn-enemy pairs (0) — are stable
# everywhere. We encode friend=3 / neutral=2 / enemy=1 from Raman's groupings
# and document the middle as a soft spot.
(HORSE, ELEPHANT, SHEEP, SERPENT, DOG, CAT, RAT, COW, BUFFALO, TIGER, DEER,
 MONKEY, MONGOOSE, LION) = range(14)
YONI_BY_NAK = (
    HORSE,     # 0 Ashwini
    ELEPHANT,  # 1 Bharani
    SHEEP,     # 2 Krittika
    SERPENT,   # 3 Rohini
    SERPENT,   # 4 Mrigashira
    DOG,       # 5 Ardra
    CAT,       # 6 Punarvasu
    SHEEP,     # 7 Pushya
    CAT,       # 8 Ashlesha
    RAT,       # 9 Magha
    RAT,       # 10 Purva Phalguni
    COW,       # 11 Uttara Phalguni
    BUFFALO,   # 12 Hasta
    TIGER,     # 13 Chitra
    BUFFALO,   # 14 Swati
    TIGER,     # 15 Vishakha
    DEER,      # 16 Anuradha
    DEER,      # 17 Jyeshtha
    DOG,       # 18 Mula
    MONKEY,    # 19 Purva Ashadha
    MONGOOSE,  # 20 Uttara Ashadha
    MONKEY,    # 21 Shravana
    LION,      # 22 Dhanishta
    HORSE,     # 23 Shatabhisha
    LION,      # 24 Purva Bhadrapada
    COW,       # 25 Uttara Bhadrapada
    ELEPHANT,  # 26 Revati
)
YONI_NAMES = (
    "Horse", "Elephant", "Sheep", "Serpent", "Dog", "Cat", "Rat", "Cow",
    "Buffalo", "Tiger", "Deer", "Monkey", "Mongoose", "Lion",
)
# The seven canonical sworn-enemy pairs -> 0 points (bitter enmity).
_YONI_SWORN_ENEMIES = frozenset(
    frozenset(p) for p in (
        (COW, TIGER), (ELEPHANT, LION), (HORSE, BUFFALO), (CAT, RAT),
        (SERPENT, MONGOOSE), (DOG, DEER), (MONKEY, SHEEP),
    )
)
# Ordinary (non-sworn) enemy pairs -> 1 point; friendly pairs -> 3; else 2.
# Raman's groupings; documented as the soft middle.
_YONI_ENEMIES = frozenset(
    frozenset(p) for p in (
        (HORSE, ELEPHANT), (SHEEP, MONKEY), (DOG, CAT), (SERPENT, RAT),
        (TIGER, DEER), (COW, LION), (BUFFALO, MONGOOSE),
    )
)
_YONI_FRIENDS = frozenset(
    frozenset(p) for p in (
        (HORSE, SHEEP), (ELEPHANT, DEER), (COW, BUFFALO), (SERPENT, DEER),
        (CAT, DOG), (RAT, MONKEY), (LION, HORSE),
    )
)

# ── Graha Maitri (koota 5, max 5) — from Moon RASHI lords ────────────────────
# Naisargika (natural) friendship, Parashara. Each planet -> {friends, enemies};
# everything else neutral.
_NAISARGIKA = {
    "Sun":     ({"Moon", "Mars", "Jupiter"}, {"Venus", "Saturn"}),
    "Moon":    ({"Sun", "Mercury"}, set()),
    "Mars":    ({"Sun", "Moon", "Jupiter"}, {"Mercury"}),
    "Mercury": ({"Sun", "Venus"}, {"Moon"}),
    "Jupiter": ({"Sun", "Moon", "Mars"}, {"Mercury", "Venus"}),
    "Venus":   ({"Mercury", "Saturn"}, {"Sun", "Moon"}),
    "Saturn":  ({"Mercury", "Venus"}, {"Sun", "Moon", "Mars"}),
}


def _relation(of: str, to: str) -> str:
    """`of`'s natural view of `to`: 'friend' | 'neutral' | 'enemy'."""
    if of == to:
        return "friend"
    friends, enemies = _NAISARGIKA[of]
    if to in friends:
        return "friend"
    if to in enemies:
        return "enemy"
    return "neutral"


# Combined two-way relationship -> points. The 0/5 poles are stable; the middle
# fractions are a documented divergence (schemes vary 0.5/1/3/4). We use the
# common Prokerala/Raman-style table.
_GRAHA_MAITRI_POINTS = {
    ("friend", "friend"): 5.0,
    ("friend", "neutral"): 4.0,
    ("neutral", "friend"): 4.0,
    ("neutral", "neutral"): 3.0,
    ("friend", "enemy"): 1.0,
    ("enemy", "friend"): 1.0,
    ("neutral", "enemy"): 0.5,
    ("enemy", "neutral"): 0.5,
    ("enemy", "enemy"): 0.0,
}

# ── Gana (koota 6, max 6) — from Moon NAKSHATRA ──────────────────────────────
_DEVA, _MANUSHYA, _RAKSHASA = "Deva", "Manushya", "Rakshasa"
GANA_BY_NAK = (
    _DEVA,      # 0 Ashwini
    _MANUSHYA,  # 1 Bharani
    _RAKSHASA,  # 2 Krittika
    _MANUSHYA,  # 3 Rohini
    _DEVA,      # 4 Mrigashira
    _MANUSHYA,  # 5 Ardra
    _DEVA,      # 6 Punarvasu
    _DEVA,      # 7 Pushya
    _RAKSHASA,  # 8 Ashlesha
    _RAKSHASA,  # 9 Magha
    _MANUSHYA,  # 10 Purva Phalguni
    _MANUSHYA,  # 11 Uttara Phalguni
    _DEVA,      # 12 Hasta
    _RAKSHASA,  # 13 Chitra
    _DEVA,      # 14 Swati
    _RAKSHASA,  # 15 Vishakha
    _DEVA,      # 16 Anuradha
    _RAKSHASA,  # 17 Jyeshtha
    _RAKSHASA,  # 18 Mula
    _MANUSHYA,  # 19 Purva Ashadha
    _MANUSHYA,  # 20 Uttara Ashadha
    _DEVA,      # 21 Shravana
    _RAKSHASA,  # 22 Dhanishta
    _RAKSHASA,  # 23 Shatabhisha
    _MANUSHYA,  # 24 Purva Bhadrapada
    _MANUSHYA,  # 25 Uttara Bhadrapada
    _DEVA,      # 26 Revati
)
# Points[groom_gana][bride_gana]; asymmetric (Deva groom + Rakshasa bride 1;
# Rakshasa groom + Deva bride 0 — the classical asymmetry).
_GANA_POINTS = {
    _DEVA:     {_DEVA: 6, _MANUSHYA: 5, _RAKSHASA: 1},
    _MANUSHYA: {_DEVA: 5, _MANUSHYA: 6, _RAKSHASA: 0},
    _RAKSHASA: {_DEVA: 0, _MANUSHYA: 0, _RAKSHASA: 6},
}

# ── Bhakoot / Rashi (koota 7, max 7) — from Moon RASHI ───────────────────────
# 0 points for the mutual counts 6/8 (shad-ashtaka), 5/9 (nava-pancham) and
# 2/12 (dwir-dwadash); else 7.
_BHAKOOT_DOSHA_COUNTS = frozenset({(2, 12), (5, 9), (6, 8)})

# ── Nadi (koota 8, max 8) — from Moon NAKSHATRA ─────────────────────────────
_AADI, _MADHYA, _ANTYA = "Aadi", "Madhya", "Antya"
NADI_BY_NAK = (
    _AADI,    # 0 Ashwini
    _MADHYA,  # 1 Bharani
    _ANTYA,   # 2 Krittika
    _ANTYA,   # 3 Rohini
    _MADHYA,  # 4 Mrigashira
    _AADI,    # 5 Ardra
    _AADI,    # 6 Punarvasu
    _MADHYA,  # 7 Pushya
    _ANTYA,   # 8 Ashlesha
    _ANTYA,   # 9 Magha
    _MADHYA,  # 10 Purva Phalguni
    _AADI,    # 11 Uttara Phalguni
    _AADI,    # 12 Hasta
    _MADHYA,  # 13 Chitra
    _ANTYA,   # 14 Swati
    _ANTYA,   # 15 Vishakha
    _MADHYA,  # 16 Anuradha
    _AADI,    # 17 Jyeshtha
    _AADI,    # 18 Mula
    _MADHYA,  # 19 Purva Ashadha
    _ANTYA,   # 20 Uttara Ashadha
    _ANTYA,   # 21 Shravana
    _MADHYA,  # 22 Dhanishta
    _AADI,    # 23 Shatabhisha
    _AADI,    # 24 Purva Bhadrapada
    _MADHYA,  # 25 Uttara Bhadrapada
    _ANTYA,   # 26 Revati
)

# The customary "workable match" line. It is a CONVENTION, not a verdict — see
# describe_match and docs.
CUSTOMARY_THRESHOLD = 18


# ═══════════════════════════════════════════════════════════════════════════
# Result types
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class KootaScore:
    """One koota's result: what it scored, out of what, and the raw facts."""

    name: str
    got: float
    maximum: float
    detail: str            # the descriptive fact ("Deva / Manushya"), never a verdict
    is_dosha: bool = False  # a recognised classical "dosha" (0 on a high-weight koota)


@dataclass(frozen=True)
class AshtakootaResult:
    kootas: tuple[KootaScore, ...]
    total: float
    maximum: float = 36.0

    @property
    def doshas(self) -> tuple[KootaScore, ...]:
        return tuple(k for k in self.kootas if k.is_dosha)

    def by_name(self, name: str) -> KootaScore:
        return next(k for k in self.kootas if k.name == name)


@dataclass(frozen=True)
class Person:
    """The minimum a person contributes to guna milan: their natal Moon."""

    moon_longitude: float

    @property
    def nakshatra_index(self) -> int:
        return nakshatra_of(self.moon_longitude).index

    @property
    def sign_index(self) -> int:
        return int(self.moon_longitude % 360 // 30)


# ═══════════════════════════════════════════════════════════════════════════
# The eight kootas — each a pure function of the two Moon placements
# ═══════════════════════════════════════════════════════════════════════════
def _count(from_sign: int, to_sign: int) -> int:
    """1-based count from `from_sign` to `to_sign` inclusive (1..12)."""
    return (to_sign - from_sign) % 12 + 1


def varna(groom: Person, bride: Person) -> KootaScore:
    g, b = VARNA_BY_SIGN[groom.sign_index], VARNA_BY_SIGN[bride.sign_index]
    got = 1.0 if _VARNA_RANK[g] >= _VARNA_RANK[b] else 0.0
    return KootaScore("Varna", got, 1.0, f"{g} / {b}")


def vashya(groom: Person, bride: Person) -> KootaScore:
    g, b = VASHYA_GROUP_BY_SIGN[groom.sign_index], VASHYA_GROUP_BY_SIGN[bride.sign_index]
    got = float(_VASHYA_POINTS[g][b])
    return KootaScore("Vashya", got, 2.0, f"{g} / {b}")


def _tara_ok(from_nak: int, to_nak: int) -> bool:
    rem = ((to_nak - from_nak) % 27 + 1) % 9
    return rem not in _TARA_BAD_REMAINDERS


def tara(groom: Person, bride: Person) -> KootaScore:
    a = _tara_ok(groom.nakshatra_index, bride.nakshatra_index)
    b = _tara_ok(bride.nakshatra_index, groom.nakshatra_index)
    got = 3.0 if (a and b) else 1.5 if (a or b) else 0.0
    return KootaScore("Tara", got, 3.0, f"{'ok' if a else 'bad'} / {'ok' if b else 'bad'}")


def _yoni_points(ya: int, yb: int) -> float:
    if ya == yb:
        return 4.0
    pair = frozenset((ya, yb))
    if pair in _YONI_SWORN_ENEMIES:
        return 0.0
    if pair in _YONI_ENEMIES:
        return 1.0
    if pair in _YONI_FRIENDS:
        return 3.0
    return 2.0


def yoni(groom: Person, bride: Person) -> KootaScore:
    ya, yb = YONI_BY_NAK[groom.nakshatra_index], YONI_BY_NAK[bride.nakshatra_index]
    got = _yoni_points(ya, yb)
    return KootaScore(
        "Yoni", got, 4.0, f"{YONI_NAMES[ya]} / {YONI_NAMES[yb]}",
        is_dosha=(got == 0.0),
    )


def graha_maitri(groom: Person, bride: Person) -> KootaScore:
    lg, lb = SIGN_LORDS[groom.sign_index], SIGN_LORDS[bride.sign_index]
    if lg == lb:
        return KootaScore("Graha Maitri", 5.0, 5.0, f"{lg} / {lb} (same lord)")
    got = _GRAHA_MAITRI_POINTS[(_relation(lg, lb), _relation(lb, lg))]
    return KootaScore("Graha Maitri", got, 5.0, f"{lg} / {lb}")


def gana(groom: Person, bride: Person) -> KootaScore:
    g, b = GANA_BY_NAK[groom.nakshatra_index], GANA_BY_NAK[bride.nakshatra_index]
    got = float(_GANA_POINTS[g][b])
    return KootaScore("Gana", got, 6.0, f"{g} / {b}")


def bhakoot(groom: Person, bride: Person) -> KootaScore:
    counts = (
        _count(groom.sign_index, bride.sign_index),
        _count(bride.sign_index, groom.sign_index),
    )
    dosha = tuple(sorted(counts)) in _BHAKOOT_DOSHA_COUNTS
    got = 0.0 if dosha else 7.0
    detail = f"{counts[0]}/{counts[1]} apart"
    return KootaScore("Bhakoot", got, 7.0, detail, is_dosha=dosha)


def nadi(groom: Person, bride: Person) -> KootaScore:
    g, b = NADI_BY_NAK[groom.nakshatra_index], NADI_BY_NAK[bride.nakshatra_index]
    same = g == b
    return KootaScore(
        "Nadi", 0.0 if same else 8.0, 8.0, f"{g} / {b}", is_dosha=same,
    )


_KOOTAS = (varna, vashya, tara, yoni, graha_maitri, gana, bhakoot, nadi)


def guna_milan(groom: Person, bride: Person) -> AshtakootaResult:
    """The eight-koota tally. `groom`/`bride` name the two DIRECTIONAL roles the
    tradition uses (several kootas are asymmetric); the names carry no judgement
    and the caller may assign them either way — see docs on the gender problem.
    """
    scores = tuple(k(groom, bride) for k in _KOOTAS)
    total = sum(s.got for s in scores)
    return AshtakootaResult(scores, total)


# ═══════════════════════════════════════════════════════════════════════════
# Nadi & Bhakoot parihar (cancellation) — the divergence zone, made explicit
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Parihar:
    """A classical cancellation that MAY apply to a dosha. We surface it as a
    fact ('a recognised exception applies'); we never let it silently zero a
    warning, and we never invent exceptions the sources do not agree on."""

    dosha: str
    applies: bool
    reason: str


def nadi_parihar(groom: Person, bride: Person) -> Parihar:
    """The two well-agreed Nadi exceptions (BPHS-lineage, shared by AstroSage &
    DrikPanchang): same rashi + different nakshatra, or same nakshatra +
    different pada. We deliberately DO NOT encode the contested "same nakshatra-
    lord" exception. Only meaningful when Nadi dosha is present."""
    ga, ba = groom.nakshatra_index, bride.nakshatra_index
    if NADI_BY_NAK[ga] != NADI_BY_NAK[ba]:
        return Parihar("Nadi", False, "no Nadi dosha")
    n_g, n_b = nakshatra_of(groom.moon_longitude), nakshatra_of(bride.moon_longitude)
    if groom.sign_index == bride.sign_index and ga != ba:
        return Parihar("Nadi", True, "same rashi, different nakshatra")
    if ga == ba and n_g.pada != n_b.pada:
        return Parihar("Nadi", True, "same nakshatra, different pada")
    return Parihar("Nadi", False, "same Nadi, no recognised exception")


def bhakoot_parihar(groom: Person, bride: Person) -> Parihar:
    """The well-agreed Bhakoot exception: the two rashi lords are the same
    planet or mutual natural friends. Only meaningful when Bhakoot dosha is
    present."""
    counts = tuple(sorted((
        _count(groom.sign_index, bride.sign_index),
        _count(bride.sign_index, groom.sign_index),
    )))
    if counts not in _BHAKOOT_DOSHA_COUNTS:
        return Parihar("Bhakoot", False, "no Bhakoot dosha")
    lg, lb = SIGN_LORDS[groom.sign_index], SIGN_LORDS[bride.sign_index]
    if lg == lb:
        return Parihar("Bhakoot", True, "same rashi lord")
    if _relation(lg, lb) == "friend" and _relation(lb, lg) == "friend":
        return Parihar("Bhakoot", True, "rashi lords are mutual friends")
    return Parihar("Bhakoot", False, "Bhakoot dosha, no recognised exception")


# ═══════════════════════════════════════════════════════════════════════════
# Mangal (Kuja / Manglik) Dosha — the biggest fear-selling vector, stated as fact
# ═══════════════════════════════════════════════════════════════════════════
# The houses (from a reference point) in which Mars is said to cause the dosha.
# The 1/2/4/7/8/12 set is the inclusive North-Indian convention; the 2nd house
# is the contested member (South-Indian sets often drop it). We report BOTH the
# strict (1/4/7/8/12) and inclusive (adds 2) counts so the divergence is visible.
_MANGAL_HOUSES_STRICT = frozenset({1, 4, 7, 8, 12})
_MANGAL_HOUSES_INCLUSIVE = _MANGAL_HOUSES_STRICT | {2}


@dataclass(frozen=True)
class MangalReferencePoint:
    """Mars's house counted from one reference (lagna / Moon / Venus) and
    whether that lands in the dosha set — strict and inclusive."""

    reference: str            # "lagna" | "Moon" | "Venus"
    house: int                # 1..12
    strict: bool              # Mars in {1,4,7,8,12}
    inclusive: bool           # adds the contested 2nd house


@dataclass(frozen=True)
class MangalAssessment:
    """The raw Mangal facts. `points` is one entry per available reference; the
    lagna reference is present only when a birth time gave a chart. This is a
    DESCRIPTION of a placement, never a verdict on marriageability — see docs."""

    points: tuple[MangalReferencePoint, ...]
    cancellations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def flagged_strict(self) -> bool:
        return any(p.strict for p in self.points)

    @property
    def flagged_inclusive(self) -> bool:
        return any(p.inclusive for p in self.points)


def _house_from(sign_of_mars: int, reference_sign: int) -> int:
    return (sign_of_mars - reference_sign) % 12 + 1


def mangal_dosha(chart: Chart) -> MangalAssessment:
    """Mangal Dosha facts from a full natal chart (needs a birth time — the
    lagna reference is house-of-Mars-from-the-ascendant). We also count from the
    Moon and from Venus (the other two classical reference points, neither of
    which needs a birth time), so the assessment degrades honestly: without a
    chart, use `mangal_dosha_from_moon`."""
    mars_sign = int(chart.placements["Mars"].position.longitude // 30)
    moon_sign = int(chart.placements["Moon"].position.longitude // 30)
    venus_sign = int(chart.placements["Venus"].position.longitude // 30)
    asc_sign = chart.ascendant.sign_index

    pts = []
    for ref, ref_sign in (("lagna", asc_sign), ("Moon", moon_sign), ("Venus", venus_sign)):
        h = _house_from(mars_sign, ref_sign)
        pts.append(MangalReferencePoint(
            ref, h, h in _MANGAL_HOUSES_STRICT, h in _MANGAL_HOUSES_INCLUSIVE,
        ))
    return MangalAssessment(tuple(pts))


def mangal_dosha_from_moon(person: Person, venus_sign: int | None = None) -> MangalAssessment:
    """The no-birth-time Mangal path: count Mars's house from the Moon (and from
    Venus if its sign is supplied) — never from a fabricated lagna. Requires the
    person's Mars sign, so callers pass a `Person` carrying it via a chart; when
    only the Moon is known this returns an EMPTY assessment (honest: the lagna
    form is unavailable, and Moon-form needs Mars's sign, which needs a full
    chart anyway). Kept as the explicit honest-degradation entry point."""
    return MangalAssessment(())


# ═══════════════════════════════════════════════════════════════════════════
# The voice layer — band-neutral, agency-preserving, and gated
# ═══════════════════════════════════════════════════════════════════════════
# Every string the product may show is drawn from here so the gate battery in
# tests/test_compatibility_gates_falsify.py can read and mutate the same corpus
# the code ships. Band lines are deliberately close in length and identical in
# stance across high/low — the anti-fear-selling symmetry (transit gate pattern).
# Nothing here decrees a relationship; the low band says so out loud.
DESCRIPTORS: dict[str, dict[str, str]] = {
    "band": {
        "high": (
            "A high traditional tally: most of the eight koota markers line up. "
            "Read it as encouragement rather than a guarantee, and keep talking."
        ),
        "mid": (
            "A middling traditional tally: some koota markers line up and some do "
            "not. It sketches tendencies rather than outcomes, so weigh it lightly."
        ),
        "low": (
            "A low traditional tally: fewer of the eight koota markers line up. "
            "It is one tradition's count rather than a verdict, and many close "
            "bonds score low here."
        ),
    },
    "dosha": {
        # Each names the marker as one tradition's, keeps the reader's agency, and
        # never predicts an outcome. A recognised exception, when present, is
        # appended by describe_match — it is surfaced, never used to hide the fact.
        "Nadi": (
            "Nadi: both charts share the same nadi in this tradition, which some "
            "readers weigh for health and children. It is a marker to discuss, "
            "not a barrier, and traditional exceptions can set it aside."
        ),
        "Bhakoot": (
            "Bhakoot: the moon signs sit in a count this tradition reads for "
            "household rhythm. Treat it as a note for conversation rather than a "
            "ruling, and traditional exceptions can set it aside."
        ),
        "Yoni": (
            "Yoni: the two nakshatra animals are read as a mismatched pair in this "
            "tradition. It speaks to pace and temperament, not fate, and it is one "
            "signal among the eight rather than the last word."
        ),
        "Mangal": (
            "Mangal: Mars sits in one of the houses this tradition marks, counted "
            "from your chart. It is a widely discussed marker, not a ruling on "
            "anyone's future, and several traditional conditions set it aside."
        ),
    },
}

# Words that turn a description into a decree. The reader keeps agency: we
# describe markers, we never rule on a relationship or a person's marriageability.
VERDICT_WORDS = frozenset({
    "incompatible", "unmarriageable", "doomed", "cursed", "inauspicious",
    "forbidden", "rejected", "unfit", "avoid", "reject", "cancel the match",
    "should not marry", "must not marry", "will fail", "will divorce",
    "will suffer", "manglik problem", "guaranteed", "never marry",
})


def _band(total: float) -> str:
    return "high" if total >= 28 else "low" if total < CUSTOMARY_THRESHOLD else "mid"


def describe_match(
    groom: Person,
    bride: Person,
    *,
    mangal: MangalAssessment | None = None,
) -> dict:
    """Turn a tally into the band-neutral, agency-preserving lines the product
    may show. Returns the numeric breakdown PLUS the descriptive lines — the
    number is always shown with the honest caveat, never as a bare verdict."""
    result = guna_milan(groom, bride)
    lines = [DESCRIPTORS["band"][_band(result.total)]]

    parihar = {"Nadi": nadi_parihar(groom, bride), "Bhakoot": bhakoot_parihar(groom, bride)}
    for k in result.doshas:
        base = DESCRIPTORS["dosha"][k.name]
        if k.name in parihar and parihar[k.name].applies:
            base += f" Here a recognised exception applies: {parihar[k.name].reason}."
        lines.append(base)
    if mangal is not None and mangal.flagged_strict:
        lines.append(DESCRIPTORS["dosha"]["Mangal"])

    return {
        "total": result.total,
        "maximum": result.maximum,
        "threshold": CUSTOMARY_THRESHOLD,
        "kootas": [
            {"name": k.name, "got": k.got, "max": k.maximum, "detail": k.detail}
            for k in result.kootas
        ],
        "lines": lines,
    }
