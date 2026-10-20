"""Golden tests: the chart file's KP section (reshape E.3, engine/kp.py).

Strongest evidence first:

  * EXTERNAL: AstroSage's KP page for Golden-1 (astrosage_kp_golden_1.json —
    the owner's 1-page KP PDF and page 44 of the 56-page Vedic report, both
    printed 2026-10-20) and its 434 KP pratyantar dates
    (astrosage_dasha_tables.json "kp", pages 45–48). Every lord, every cusp
    sub-sub lord, the ruling planets, both significator lists and all 76 KP
    antar dates are compared exactly; degrees within the arc AstroSage's own
    ephemeris sits from Swiss (README > "Chart file vs AstroSage").
  * The KP New formula against AstroSage's printed values on three dates.
  * CLASSICAL RULES restated independently: the 249-sub table's spans, the
    four significator levels on a hand-built chart.

ONE KNOWN DEVIATION, reported not tuned: Mercury. Swiss puts it 13″ BEFORE
cusp 2 (house 1); AstroSage's Mercury sits 30″ further on (its ephemeris —
the same +33″ the Lahiri page shows) and lands 19″ PAST cusp 2 (house 2).
That one house moves Mercury's significators (ours add house 1) and house
1's list (ours add Mercury). Placed in AstroSage's house 2, the same code
reproduces AstroSage's 21 significator rows exactly — the method agrees.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime

import pytest
import swisseph as swe

from engine.ephemeris import _ensure_init
from engine.kp import (
    KP_NEW_1900,
    VP285_LAHIRI_GAP,
    kp_facts,
    kp_lords,
    kp_new_ayanamsa,
    placidus_house,
    significators,
)
from engine.positions import BODIES
from engine.vimshottari import (
    ABBR,
    DASHA_YEARS,
    calendar_children,
    calendar_dasha,
    calendar_gap,
    calendar_mahas,
)

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
BIRTH = datetime(1989, 9, 23, 4, 47)
THANE = (19 + 11 / 60, 72 + 58 / 60)
AS_OF = date(2026, 10, 20)
SHORT = {"SU": "Sun", "MO": "Moon", "MA": "Mars", "ME": "Mercury", "JU": "Jupiter",
         "VE": "Venus", "SA": "Saturn", "RA": "Rahu", "KE": "Ketu"}
FROM_ABBR = {v: k for k, v in ABBR.items()}


def _load(name: str) -> dict:
    with open(os.path.join(GOLDEN_DIR, name)) as f:
        return json.load(f)


AS = _load("astrosage_kp_golden_1.json")


def _deg(dms: str) -> float:
    d, m, s = (int(x) for x in dms.split("-"))
    return d + m / 60 + s / 3600


def _arcsec(a: float, b: float) -> float:
    d = (a - b) % 360
    return min(d, 360 - d) * 3600


@pytest.fixture(scope="module")
def kp() -> dict:
    return kp_facts(BIRTH, "Asia/Kolkata", *THANE, AS_OF)


# ── The KP zodiac ───────────────────────────────────────────────────────────
def test_kp_new_formula_reproduces_astrosage_printed_values():
    """AstroSage's printed KP New, to the second: Golden-1's birth (the PDF)
    and the two values AstroSage's calculator gave on public record
    (indiadivine.org thread, 2008). One 1900 constant, Newcomb precession."""
    for jd, printed in (
        (swe.julday(1989, 9, 22, 23 + 17 / 60), "023-37-23"),
        (swe.julday(2000, 2, 1, 0), "023-46-04"),
        (swe.julday(2008, 10, 5, 6.5), "023-53-19"),
    ):
        assert _arcsec(kp_new_ayanamsa(jd), _deg(printed)) < 1.0, printed
    assert abs(KP_NEW_1900 - (22 + 22 / 60 + 12.54 / 3600)) < 1e-12


def test_vp285_gap_is_constant_over_supported_years():
    """The KP zodiac rides on VP285 the way AstroSage's does: KP New plus the
    VP285 − plain-Lahiri gap, which Swiss holds at 23.0″ ± 0.05″, 1900–2100."""
    _ensure_init()
    for year in range(1900, 2101, 10):
        jd = swe.julday(year, 1, 1, 0)
        swe.set_sid_mode(swe.SIDM_LAHIRI_VP285, 0, 0)
        vp = swe.get_ayanamsa_ut(jd)
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        plain = swe.get_ayanamsa_ut(jd)
        assert abs((vp - plain) - VP285_LAHIRI_GAP) * 3600 < 0.05, year


def test_kp_positions_sit_the_astrosage_gap_from_the_lahiri_chart(kp):
    """AstroSage's KP page is its Lahiri page moved by 5′23″ (all 9 grahas and
    the lagna, printed seconds). Ours moves by the KP New ↔ plain-Lahiri gap,
    5′26″ at this birth — within 3″ of AstroSage's."""
    from engine.chart_file import natal_facts
    natal = natal_facts(BIRTH, "Asia/Kolkata", *THANE)
    for body in BODIES:
        moved = _arcsec(kp["planets"][body]["longitude"], natal["planets"][body]["longitude"])
        assert abs(moved - 323) < 3.5, body


# ── Lords: the 249-sub table, restated ──────────────────────────────────────
def test_sub_lords_follow_the_vimshottari_proportions():
    """Each nakshatra's 13°20′ splits into 9 subs from the star lord, sized by
    dasha years/120; each sub into 9 sub-subs the same way. Walk Ashwini
    (Ketu's star) edge to edge; a sub's first sub-sub is its own lord."""
    order = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    at = 0.0
    for lord in order:
        span = 800 * DASHA_YEARS[lord] / 120          # arc-minutes
        got = kp_lords((at + 0.01) / 60)        # just inside the sub: its first sub-sub
        assert (got["star_lord"], got["sub_lord"], got["sub_sub_lord"]) == ("Ketu", lord, lord)
        at += span
    assert math.isclose(at, 800)
    # Golden-1's lagna (AstroSage): Leo, Magha, sub Mercury, sub-sub Venus.
    got = kp_lords(_deg("131-54-05"))
    assert [got[k] for k in ("sign_lord", "star_lord", "sub_lord", "sub_sub_lord")] == [
        "Sun", "Ketu", "Mercury", "Venus"]


def test_placidus_house_is_cusp_to_next_cusp():
    cusps = [(10 + 30 * i) % 360 for i in range(12)]
    assert placidus_house(10, cusps) == 1
    assert placidus_house(9.9999, cusps) == 12
    assert placidus_house(355, cusps) == 12
    assert placidus_house(41, cusps) == 2


def test_four_significator_levels_on_a_hand_built_chart():
    """A planet's A/B/C/D and a house's A/B/C/D, built from the definitions."""
    planets = {b: {"house": 12, "star_lord": "Ketu"} for b in BODIES}
    planets["Sun"] = {"house": 1, "star_lord": "Moon"}
    planets["Moon"] = {"house": 4, "star_lord": "Sun"}
    lords = ["Sun", "Mercury", "Venus", "Moon", "Mars", "Jupiter",
             "Saturn", "Saturn", "Jupiter", "Mars", "Venus", "Mercury"]
    pw, hw = significators(planets, lords)
    assert pw["Sun"] == {"a": [4], "b": [1], "c": [4], "d": [1]}
    assert pw["Moon"] == {"a": [1], "b": [4], "c": [1], "d": [4]}
    assert pw["Rahu"] == {"a": [12], "b": [12], "c": [], "d": []}
    assert hw["1"] == {"a": ["Moon"], "b": ["Sun"], "c": ["Moon"], "d": ["Sun"]}
    assert hw["4"] == {"a": ["Sun"], "b": ["Moon"], "c": ["Sun"], "d": ["Moon"]}
    assert hw["2"] == {"a": [], "b": [], "c": [], "d": ["Mercury"]}


# ── Golden-1 vs AstroSage's KP page ─────────────────────────────────────────
def test_golden_ayanamsa(kp):
    assert _arcsec(kp["kp_new"], _deg(AS["ayanamsa"]["value"])) < 1.0
    assert _arcsec(kp["ayanamsa"], kp["kp_new"]) == pytest.approx(23.0, abs=1e-6)


def test_golden_cusps(kp):
    """All 12 cusps: sign, star, sub AND sub-sub lord exact; degrees within
    16″ (AstroSage's intermediate Placidus cusps; the lagna is 2.9″, the MC
    0.4″)."""
    for i, (ours, theirs) in enumerate(zip(kp["cusps"], AS["cusps"], strict=True)):
        assert [ABBR[ours[k]] for k in ("sign_lord", "star_lord", "sub_lord", "sub_sub_lord")] == [
            theirs[k] for k in ("sign_lord", "star_lord", "sub_lord", "sub_sub_lord")], i + 1
        assert _arcsec(ours["longitude"], _deg(theirs["degree"])) < 16, i + 1
    assert _arcsec(kp["cusps"][0]["longitude"], _deg(AS["cusps"][0]["degree"])) < 3
    assert _arcsec(kp["cusps"][9]["longitude"], _deg(AS["cusps"][9]["degree"])) < 1


# AstroSage's planets sit off Swiss by its own ephemeris — the Lahiri page's
# residuals, unchanged by the KP move (README): ″, ours − AstroSage.
PLANET_ARC = {"Sun": 61, "Moon": 6, "Mars": 110, "Mercury": 31, "Jupiter": 53,
              "Venus": 55, "Saturn": 5, "Rahu": 8, "Ketu": 8}


def test_golden_planets(kp):
    """Sign, star, sub and sub-sub lord exact for all nine; degrees within
    AstroSage's per-planet ephemeris residual."""
    for body, theirs in AS["planets"].items():
        ours = kp["planets"][body]
        assert [ABBR[ours[k]] for k in ("sign_lord", "star_lord", "sub_lord", "sub_sub_lord")] == [
            theirs[k] for k in ("sign_lord", "star_lord", "sub_lord", "sub_sub_lord")], body
        assert _arcsec(ours["longitude"], _deg(theirs["degree"])) < PLANET_ARC[body], body


def _astrosage_houses() -> dict[str, int]:
    """AstroSage's Placidus house per planet, from ITS cusps and degrees."""
    cusps = [_deg(c["degree"]) for c in AS["cusps"]]
    return {b: placidus_house(_deg(p["degree"]), cusps) for b, p in AS["planets"].items()}


def test_golden_houses_and_the_mercury_deviation(kp):
    theirs = _astrosage_houses()
    ours = {b: kp["planets"][b]["house"] for b in BODIES}
    assert {b for b in BODIES if ours[b] != theirs[b]} == {"Mercury"}
    assert (ours["Mercury"], theirs["Mercury"]) == (1, 2)
    assert kp["planets"]["Mercury"]["cusp_edge_arcsec"] < 15     # 13″ before cusp 2


def _unions(pw: dict, hw: dict) -> tuple[dict, dict]:
    p = {b: sorted(set(lv["a"] + lv["b"] + lv["c"] + lv["d"])) for b, lv in pw.items()}
    h = {k: [b for b in BODIES if b in set(lv["a"] + lv["b"] + lv["c"] + lv["d"])]
         for k, lv in hw.items()}
    return p, h


def test_golden_significators(kp):
    """AstroSage's two lists are the unions of the four levels. Ours match
    every row but the two Mercury's house moves; with Mercury in AstroSage's
    house the same code gives all 21 rows."""
    want_p = AS["planet_signification"]
    want_h = {k: [SHORT[s] for s in v] for k, v in AS["significators_of_houses"].items()}
    p, h = _unions(kp["significators"]["planets"], kp["significators"]["houses"])
    assert {b for b in p if p[b] != want_p[b]} == {"Mercury"}
    assert {k for k in h if h[k] != want_h[k]} == {"1"}
    assert p["Mercury"] == [1, 2, 11, 12] and h["1"] == ["Sun", "Mars", "Mercury", "Rahu"]

    planets = {b: dict(kp["planets"][b]) for b in BODIES}
    planets["Mercury"]["house"] = 2
    pw, hw = significators(planets, [c["sign_lord"] for c in kp["cusps"]])
    assert _unions(pw, hw) == (want_p, want_h)


def test_golden_ruling_planets(kp):
    r, theirs = kp["ruling"], AS["ruling_planets"]
    assert ABBR[r["day_lord"]] == theirs["day_lord"] and r["vara"] == "Shukrawara"
    for part in ("lagna", "moon"):
        assert {k: ABBR[v] for k, v in r[part].items()} == theirs[part]


def _year(yy: int, near: int) -> int:
    return min((c + yy for c in (1900, 2000, 2100)), key=lambda y: abs(y - near))


def test_golden_kp_dasha(kp):
    """Every KP maha and antar date AstroSage printed — exact. The header's
    'RAH 3 Y 10 M 24 D' is the Lahiri balance AstroSage copied onto the KP
    page; its KP table ends Rahu on 3/7/93, i.e. 3 Y 9 M 10 D."""
    d = kp["dasha"]
    assert (d["lord"], d["balance"]["years"], d["balance"]["months"], d["balance"]["days"]) == (
        "Rahu", 3, 9, 10)
    for ours, theirs in zip(d["mahas"], AS["kp_dasha"], strict=True):
        assert ABBR[ours["lord"]] == theirs["lord"]
        e = date.fromisoformat(ours["end"])
        assert (e.day, e.month, e.year % 100) == tuple(theirs["end"])
        shown = [a for a in theirs["antar"] if a["end"] is not None]
        assert [ABBR[a["lord"]] for a in ours["antar"]] == [a["lord"] for a in shown]
        for a, t in zip(ours["antar"], shown, strict=True):
            end = date.fromisoformat(a["end"])
            assert end == date(_year(t["end"][2], end.year), t["end"][1], t["end"][0]), a


def test_golden_kp_pratyantars_within_a_day(kp):
    """The 434 KP pratyantar ends (not printed in the file) sit within one
    calendar day: our KP Moon is 5.5″ from AstroSage's (18 hours of dasha
    time). Measured: 228/434 exact."""
    cal = calendar_dasha(kp["planets"]["Moon"]["longitude"], BIRTH.date())
    ends = {}
    for m in calendar_mahas(cal):
        for a in calendar_children(m):
            for p in calendar_children(a):
                ends[(ABBR[m.lord], ABBR[a.lord], ABBR[p.lord])] = cal.date_at(p.end)
    rows = _load("astrosage_dasha_tables.json")["kp"]
    exact = 0
    for r in rows:
        got = ends[tuple(r["path"])]
        want = date(_year(r["date"][2], got.year), r["date"][1], r["date"][0])
        gap = calendar_gap(got, want)
        assert gap <= 1, r
        exact += gap == 0
    assert (len(rows), exact) == (434, 228)


def test_golden_kp_pratyantar_blocks_against_astrosage(kp):
    """The two KP pratyantar blocks the chart file prints (the running KP
    antar and the next). Their edges are AstroSage's KP antar dates exactly;
    inside, 8 of the 18 ends are AstroSage's printed dates and 10 fall one
    day earlier — the 5.5″ KP Moon gap above. Reported, not tuned."""
    d = kp["dasha"]
    printed = {tuple(r["path"]): r["date"] for r in _load("astrosage_dasha_tables.json")["kp"]}
    gaps = []
    for which, lords in (("current", ("Saturn", "Jupiter")), ("next", ("Mercury", "Mercury"))):
        b = d["pratyantar"][which]
        m = d["mahas"][b["maha"]]
        a = m["antar"][b["antar"]]
        assert (m["lord"], a["lord"]) == lords
        assert (b["rows"][0]["start"], b["rows"][-1]["end"]) == (a["start"], a["end"])
        for r in b["rows"]:
            got = date.fromisoformat(r["end"])
            t = printed[(ABBR[m["lord"]], ABBR[a["lord"]], ABBR[r["lord"]])]
            gaps.append((got - date(_year(t[2], got.year), t[1], t[0])).days)
    assert (gaps.count(0), gaps.count(-1), len(gaps)) == (8, 10, 18)
    cur = d["pratyantar"]["current"]["rows"][d["running"]["pratyantar"]]
    assert (cur["lord"], cur["start"], cur["end"]) == ("Mercury", "2026-09-17", "2027-01-26")


def test_running_kp_period_on_the_as_of_date(kp):
    """Engine-pinned: on 2026-10-20 Golden-1 runs Saturn / Jupiter (KP)."""
    d = kp["dasha"]
    m = d["mahas"][d["running"]["maha"]]
    assert (m["lord"], m["antar"][d["running"]["antar"]]["lord"]) == ("Saturn", "Jupiter")
    assert FROM_ABBR["SAT"] == "Saturn"
