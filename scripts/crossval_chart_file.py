"""Cross-validate the chart file's facts: engine (Swiss) vs Worker (astronomy-engine).

Reshape Phase B. aura-api's POST /v1/chart-file builds the file from
src/chartFacts.ts, a port of engine/chart_file.py (the source of truth). This
script runs BOTH over the same inputs and requires them to agree on every
value the file states:

  natal   ascendant + 9 grahas: longitude ≤ 1′; sign, nakshatra, pada, D9 sign,
          house, D9 house, retrograde, combust, dignity — exact;
          birth panchang (tithi, karana, yoga, nakshatra, pada) and vara —
          exact; sunrise ≤ 90 s
  dasha   identity, balance ±1 day, every maha / antar row ±1 day with the
          same lords, the running maha/antar/pratyantar, both pratyantar
          tables ±1 day — days on AstroSage's dasha calendar (calendar_gap: a
          printed 1/2 March may be a rolled 29/30 February)
          Mangal dosha (houses from lagna and Moon, cancellations, both
          verdicts) — exact
  sky     today's 9 grahas as natal; every Saturn/Jupiter/Rahu ingress in
          365 days — same body, signs, direction, order; instant within the
          time it takes the body to move 40″ (≥ 30 min); Saturn's sign changes
          over the 42-year Saturn-cycle window, same rule (the Worker reads
          them from its generated table, src/saturnTable.ts); and the Saturn
          cycles (Sade Sati, Kantaka, Ashtama) for all 12 Moon signs — state,
          phase, every date exact

"Exact" admits ONE exception, the same boundary-honesty policy every crossval
in this repo uses (crossval_chart.py, crossval_ascendant.py): a value whose
engine input sits within 1′ of the boundary that decides it (a pada edge, a
combustion orb, a dignity degree, a tithi edge, a station, a sunrise, a dasha
day) is a CONTESTED case — recorded and counted, never adjudicated, never a
failure. The Worker test (test/chartFile.crossval.test.ts) applies the
identical rules to the golden this writes.

Inputs: 240 Indian births (population-weighted) + 50 world births + 5 seeded
near-station births (so Mercury/Venus retro-dependent combustion is exercised)
+ the golden chart (Thane) + the four B1 births abroad; each with an as-of
date in 2024–2040 (≥ birth). The endpoint itself takes births in India only;
the world and abroad births exercise the same shared functions. Plus 51 skies
— as-of dates, always India time. Seeded: identical runs produce
byte-identical goldens.

Run:  uv run python scripts/crossval_chart_file.py
Exit: non-zero on ANY uncontested disagreement (do not tune — investigate).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))
sys.path.insert(0, str(ENGINE_ROOT / "scripts"))

from crossval_chart import (  # noqa: E402
    INDIA_CITIES,
    INDIA_WEIGHTS,
    STATION_BODIES,
    STATION_EPS,
    WORLD_CITIES,
    find_station_case,
)

from engine.chart_file import (  # noqa: E402
    EXALTATION,
    MOOLATRIKONA,
    _utc_from_ms,
    combust_orb,
    dasha_facts,
    natal_facts,
    saturn_cycles,
    separation,
    sky_facts,
)
from engine.positions import sidereal_positions  # noqa: E402
from engine.vimshottari import calendar_gap  # noqa: E402

AURA_API = ENGINE_ROOT.parent / "aura-api"
GOLDEN_PATH = AURA_API / "test" / "golden" / "chart_file_crossval.json"

SEED = 20261019
ARC = 1 / 60                      # 1′ in degrees
PADA = 30 / 9                     # every sign/nakshatra/navamsa edge is a pada edge
DAY_MS = 86_400_000
SUNRISE_TOL_S = 90
VARA_CONTEST_S = 120
INGRESS_ARC = 40 / 3600           # degrees of motion the instants may differ by
INGRESS_MIN_TOL_MS = 30 * 60_000

BIRTH_START = datetime(1930, 1, 1)
BIRTH_END = datetime(2025, 12, 31, 23, 59)
AS_OF_START = date(2024, 1, 1)
AS_OF_END = date(2040, 12, 31)

GOLDEN_BIRTH = {"dob": "1989-09-23", "time": "04:47", "zone": "Asia/Kolkata",  # Thane
                "lat": round(19 + 11 / 60, 6), "lon": round(72 + 58 / 60, 6),
                "as_of": "2026-10-19"}
ABROAD = [  # reshape B1's dasha_abroad.json births
    ("1990-07-04", "10:00", "America/New_York", 40.7128, -74.0060),
    ("1985-06-15", "08:30", "Europe/London", 51.5074, -0.1278),
    ("1995-03-10", "14:00", "Asia/Dubai", 25.2048, 55.2708),
    ("1990-01-15", "10:00", "America/New_York", 40.7128, -74.0060),
]


# ── Inputs ──────────────────────────────────────────────────────────────────
def _as_of(rng: random.Random, dob: str) -> str:
    lo = max(AS_OF_START, date.fromisoformat(dob))
    return (lo + timedelta(days=rng.randrange((AS_OF_END - lo).days + 1))).isoformat()


def generate_births() -> list[dict]:
    rng = random.Random(SEED)
    span = int((BIRTH_END - BIRTH_START).total_seconds() // 60)
    births: list[dict] = []

    def add(when: datetime, zone: str, lat: float, lon: float) -> None:
        dob = when.strftime("%Y-%m-%d")
        births.append({"dob": dob, "time": when.strftime("%H:%M"), "zone": zone,
                       "lat": lat, "lon": lon, "as_of": _as_of(rng, dob)})

    for _ in range(240):
        city = rng.choices(INDIA_CITIES, weights=INDIA_WEIGHTS)[0]
        add(BIRTH_START + timedelta(minutes=rng.randrange(span + 1)), "Asia/Kolkata",
            city[1], city[2])
    for i in range(50):
        city = WORLD_CITIES[i % len(WORLD_CITIES)]
        add(BIRTH_START + timedelta(minutes=rng.randrange(span + 1)), city[3], city[1], city[2])
    offset = timedelta(0)
    for body in STATION_BODIES:
        s = find_station_case(body, datetime(2001, 2, 1) + offset)
        offset += timedelta(days=370)
        births.append({k: s[k] for k in ("dob", "time", "zone", "lat", "lon")}
                      | {"as_of": _as_of(rng, s["dob"])})
    births.append(GOLDEN_BIRTH)
    for dob, tm, zone, lat, lon in ABROAD:
        births.append({"dob": dob, "time": tm, "zone": zone, "lat": lat, "lon": lon,
                       "as_of": _as_of(rng, dob)})
    return births


def generate_skies() -> list[dict]:
    rng = random.Random(SEED + 1)
    span = (AS_OF_END - AS_OF_START).days
    skies = [
        {"as_of": "2026-10-19"},
        # Real short sign stays (Swiss, 1900–2100) — the cases an over-stepping
        # ingress walk would miss: Jupiter 24 d in Sagittarius from 2019-03-30,
        # Saturn 8 d in Libra from 2041-01-29, Saturn 27 d from 1993-10-15.
        {"as_of": "2019-01-01"},
        {"as_of": "2040-11-01"},
        {"as_of": "1993-06-01"},
    ]
    for _ in range(47):
        skies.append({"as_of": (AS_OF_START + timedelta(days=rng.randrange(span + 1))).isoformat()})
    return skies


# ── Engine side ─────────────────────────────────────────────────────────────
def engine_birth(b: dict) -> dict:
    local = datetime.strptime(f"{b['dob']} {b['time']}", "%Y-%m-%d %H:%M")
    natal = natal_facts(local, b["zone"], b["lat"], b["lon"])
    dasha = dasha_facts(natal["planets"]["Moon"]["longitude"], local,
                        date.fromisoformat(b["as_of"]))
    return {"natal": natal, "dasha": dasha}


def engine_sky(s: dict) -> dict:
    as_of = date.fromisoformat(s["as_of"])
    sky = sky_facts(as_of)
    # The tolerance an ingress instant gets is set by how fast the body moves
    # there, so the golden carries the engine's speed at each event.
    for e in sky["ingresses"]:
        e["speed"] = sidereal_positions(_utc_from_ms(e["utc_ms"]))[e["body"]].speed
    for c in sky["saturn"]["changes"]:
        c["speed"] = sidereal_positions(_utc_from_ms(c["utc_ms"]))["Saturn"].speed
    sky["cycles"] = [saturn_cycles(moon, sky["saturn"], as_of) for moon in range(12)]
    return sky


def worker(births: list[dict], skies: list[dict]) -> dict:
    proc = subprocess.run(
        ["node", "scripts/chart-file-batch.ts"],
        input=json.dumps({"births": births, "skies": skies}),
        capture_output=True, text=True, cwd=AURA_API, check=True,
    )
    return json.loads(proc.stdout)


# ── The comparison (mirrored verbatim in test/chartFile.crossval.test.ts) ───
def near_multiple(x: float, step: float, tol: float) -> bool:
    r = x % step
    return min(r, step - r) < tol


DIGNITY_EDGES = sorted({e for t in (EXALTATION, MOOLATRIKONA) for _, lo, hi in t.values()
                        for e in (lo, hi)} | {0, 30})


class Tally:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.contested: list[str] = []
        self.checked = 0
        self.worst = {"lon_arcsec": 0.0, "sunrise_s": 0.0, "dasha_days": 0, "ingress_arcsec": 0.0}

    def check(self, tag: str, ok: bool, contested: bool, detail: str) -> None:
        self.checked += 1
        if ok:
            return
        (self.contested if contested else self.fails).append(f"{tag}: {detail}")


def compare_point(t: Tally, tag: str, e: dict, w: dict) -> bool:
    """Longitude ≤ 1′ always; discrete fields exact unless within 1′ of a pada edge."""
    d = separation(e["longitude"], w["longitude"])
    t.worst["lon_arcsec"] = max(t.worst["lon_arcsec"], d * 3600)
    t.check(tag, d <= ARC, False, f"longitude off by {d * 3600:.1f}″")
    edge = near_multiple(e["longitude"], PADA, ARC)
    for k in ("sign_index", "nakshatra_index", "pada", "navamsa_sign_index"):
        t.check(f"{tag}.{k}", e[k] == w[k], edge, f"engine {e[k]} worker {w[k]}")
    return edge


def station(e: dict, w: dict) -> bool:
    return abs(e["speed"]) < STATION_EPS or bool(w.get("near_station"))


def compare_natal(t: Tally, tag: str, e: dict, w: dict) -> None:
    t.check(f"{tag}.utc", e["utc_ms"] == w["utc_ms"], False, f"{e['utc_ms']} vs {w['utc_ms']}")
    t.check(f"{tag}.offset", e["utc_offset_minutes"] == w["utc_offset_minutes"], False, "offset")
    asc_edge = compare_point(t, f"{tag}.asc", e["ascendant"], w["ascendant"])
    sun = e["planets"]["Sun"]["longitude"]
    for body, ep in e["planets"].items():
        wp = w["planets"][body]
        bt = f"{tag}.{body}"
        edge = compare_point(t, bt, ep, wp)
        t.check(f"{bt}.house", ep["house"] == wp["house"], edge or asc_edge, "house")
        t.check(f"{bt}.navamsa_house", ep["navamsa_house"] == wp["navamsa_house"],
                edge or asc_edge, "D9 house")
        stat = station(ep, wp)
        t.check(f"{bt}.retrograde", ep["retrograde"] == wp["retrograde"], stat, "direction")
        orbs = {combust_orb(body, r) for r in ((True, False) if stat else (ep["retrograde"],))}
        orbs.discard(None)
        sep = separation(ep["longitude"], sun)
        t.check(f"{bt}.combust", ep["combust"] == wp["combust"],
                stat or any(abs(sep - o) < 2 * ARC for o in orbs), "combust")
        deg = ep["longitude"] % 30
        t.check(f"{bt}.dignity", ep["dignity"] == wp["dignity"],
                any(abs(deg - x) < ARC for x in DIGNITY_EDGES), "dignity")
    p, q = e["panchang"], w["panchang"]
    t.check(f"{tag}.tithi", p["tithi_index"] == q["tithi_index"],
            near_multiple(p["elongation"], 12, ARC), "tithi")
    t.check(f"{tag}.karana", p["karana_index"] == q["karana_index"],
            near_multiple(p["elongation"], 6, ARC), "karana")
    t.check(f"{tag}.yoga", p["yoga_index"] == q["yoga_index"],
            near_multiple(p["yoga_sum"], 360 / 27, 2 * ARC), "yoga")
    moon_edge = near_multiple(e["planets"]["Moon"]["longitude"], PADA, ARC)
    for k in ("nakshatra_index", "pada"):
        t.check(f"{tag}.panchang.{k}", p[k] == q[k], moon_edge, k)
    # Mangal dosha is sign arithmetic on Mars, Moon, Jupiter and the lagna:
    # contested only if one of those sits within 1′ of a sign edge.
    sign_edge = any(near_multiple(lon, 30, ARC) for lon in (
        e["ascendant"]["longitude"],
        *(e["planets"][b]["longitude"] for b in ("Mars", "Moon", "Jupiter"))))
    t.check(f"{tag}.mangal_dosha", e["mangal_dosha"] == w["mangal_dosha"], sign_edge,
            f"{e['mangal_dosha']} vs {w['mangal_dosha']}")
    v, x = e["vara"], w["vara"]
    if v["sunrise_ms"] is not None and x["sunrise_ms"] is not None:
        ds = abs(v["sunrise_ms"] - x["sunrise_ms"]) / 1000
        t.worst["sunrise_s"] = max(t.worst["sunrise_s"], ds)
        t.check(f"{tag}.sunrise", ds <= SUNRISE_TOL_S, False, f"sunrise off by {ds:.0f}s")
    near_rise = (v["sunrise_ms"] is not None
                 and abs(e["utc_ms"] - v["sunrise_ms"]) < VARA_CONTEST_S * 1000)
    for k in ("vara", "civil_weekday", "before_sunrise"):
        t.check(f"{tag}.vara.{k}", v[k] == x[k], near_rise, f"{v[k]} vs {x[k]}")


def _days(a: str, b: str) -> int:
    return calendar_gap(date.fromisoformat(a), date.fromisoformat(b))


def compare_rows(t: Tally, tag: str, er: list[dict], wr: list[dict], contested: bool) -> None:
    t.check(f"{tag}.count", len(er) == len(wr), contested, f"{len(er)} vs {len(wr)} rows")
    for i, (a, b) in enumerate(zip(er, wr, strict=False)):
        t.check(f"{tag}[{i}].lord", a["lord"] == b["lord"], contested,
                f"{a['lord']} vs {b['lord']}")
        gap = max(_days(a["start"], b["start"]), _days(a["end"], b["end"]))
        t.worst["dasha_days"] = max(t.worst["dasha_days"], gap)
        t.check(f"{tag}[{i}].dates", gap <= 1, False, f"off by {gap} days")


def compare_dasha(t: Tally, tag: str, e: dict, w: dict, moon_lon: float, dob: str,
                  as_of: str) -> None:
    edge = near_multiple(moon_lon, PADA, ARC)
    for k in ("nakshatra_index", "pada", "lord"):
        t.check(f"{tag}.{k}", e[k] == w[k], edge, k)
    db = abs(e["balance"]["total_days"] - w["balance"]["total_days"])
    t.check(f"{tag}.balance", db <= 1, False, f"balance off by {db:.2f} days")
    ymd = [b["years"] * 360 + b["months"] * 30 + b["days"] for b in (e["balance"], w["balance"])]
    t.check(f"{tag}.balance_ymd", abs(ymd[0] - ymd[1]) <= 1, False, f"Y/M/D {ymd}")
    t.check(f"{tag}.mahas", len(e["mahas"]) == len(w["mahas"]) == 9, False, "maha count")
    for i, (a, b) in enumerate(zip(e["mahas"], w["mahas"], strict=False)):
        compare_rows(t, f"{tag}.maha[{i}]", [a], [b], False)
        # A birth-maha antar ending within a day of birth may be dropped on one
        # side only (its rounded end lands on/after the birth day).
        clip = i == 0 and any(_days(r["end"], dob) <= 1 for r in a["antar"])
        compare_rows(t, f"{tag}.maha[{i}].antar", a["antar"], b["antar"], clip)
    bounds = [r[k] for m in e["mahas"] for r in (m, *m["antar"]) for k in ("start", "end")]
    for which in ("current", "next"):
        ep, wp = e["pratyantar"][which], w["pratyantar"][which]
        if ep is not None:
            bounds += [r[k] for r in ep["rows"] for k in ("start", "end")]
    near_edge = any(_days(as_of, b) <= 1 for b in bounds)
    t.check(f"{tag}.running", e["running"] == w["running"], near_edge,
            f"{e['running']} vs {w['running']}")
    for which in ("current", "next"):
        ep, wp = e["pratyantar"][which], w["pratyantar"][which]
        if ep is None or wp is None:
            t.check(f"{tag}.prat.{which}", ep is None and wp is None, near_edge, "presence")
            continue
        same = (ep["maha"], ep["antar"]) == (wp["maha"], wp["antar"])
        t.check(f"{tag}.prat.{which}.which", same, near_edge, "which antar")
        if same:
            compare_rows(t, f"{tag}.prat.{which}", ep["rows"], wp["rows"], False)


def compare_sky(t: Tally, tag: str, e: dict, w: dict) -> None:
    for k in ("as_of", "instant_ms", "window_start_ms"):
        t.check(f"{tag}.{k}", e[k] == w[k], False, f"{e[k]} vs {w[k]}")
    for body, ep in e["planets"].items():
        wp = w["planets"][body]
        compare_point(t, f"{tag}.{body}", ep, wp)
        t.check(f"{tag}.{body}.retrograde", ep["retrograde"] == wp["retrograde"],
                station(ep, wp), "direction")
    ei, wi = e["ingresses"], w["ingresses"]
    end_ms = e["window_start_ms"] + 365 * DAY_MS

    def tol(ev: dict) -> float:
        return max(INGRESS_MIN_TOL_MS, INGRESS_ARC / max(abs(ev["speed"]), 1e-6) * DAY_MS)

    # A crossing within tolerance of either window edge may fall inside on one
    # side only; a station sitting near a boundary can add or drop a dip.
    edgy = any(ev["utc_ms"] - e["window_start_ms"] < tol(ev) or end_ms - ev["utc_ms"] < tol(ev)
               or abs(ev["speed"]) < STATION_EPS for ev in ei)
    key = [(x["body"], x["from_sign_index"], x["to_sign_index"], x["retrograde"]) for x in ei]
    wkey = [(x["body"], x["from_sign_index"], x["to_sign_index"], x["retrograde"]) for x in wi]
    t.check(f"{tag}.ingresses", key == wkey, edgy, f"{key} vs {wkey}")
    if key == wkey:
        for a, b in zip(ei, wi, strict=True):
            dt = abs(a["utc_ms"] - b["utc_ms"])
            arc = dt / DAY_MS * abs(a["speed"]) * 3600
            t.worst["ingress_arcsec"] = max(t.worst["ingress_arcsec"], arc)
            t.check(f"{tag}.ingress.{a['body']}", dt <= tol(a), False,
                    f"{dt / 60000:.1f} min apart ({arc:.1f}″ of motion)")
    compare_saturn(t, tag, e, w)


IST_MS = 330 * 60_000


def compare_saturn(t: Tally, tag: str, e: dict, w: dict) -> None:
    """Saturn's 42-year sign-change list, then the cycles built on it."""
    es, ws = e["saturn"], w["saturn"]
    for k in ("window_start_ms", "window_end_ms"):
        t.check(f"{tag}.saturn.{k}", es[k] == ws[k], False, f"{es[k]} vs {ws[k]}")

    def tol(c: dict) -> float:
        return max(INGRESS_MIN_TOL_MS, INGRESS_ARC / max(abs(c["speed"]), 1e-6) * DAY_MS)

    ec, wc = es["changes"], ws["changes"]
    edgy = any(c["utc_ms"] - es["window_start_ms"] < tol(c)
               or es["window_end_ms"] - c["utc_ms"] < tol(c)
               or abs(c["speed"]) < STATION_EPS for c in ec)
    t.check(f"{tag}.saturn.start_sign", es["start_sign_index"] == ws["start_sign_index"], edgy,
            f"{es['start_sign_index']} vs {ws['start_sign_index']}")
    same = [c["to_sign_index"] for c in ec] == [c["to_sign_index"] for c in wc]
    t.check(f"{tag}.saturn.changes", same, edgy, f"{len(ec)} vs {len(wc)} changes")
    if not same:
        return
    for a, b in zip(ec, wc, strict=True):
        dt = abs(a["utc_ms"] - b["utc_ms"])
        arc = dt / DAY_MS * abs(a["speed"]) * 3600
        t.worst["ingress_arcsec"] = max(t.worst["ingress_arcsec"], arc)
        t.check(f"{tag}.saturn.change", dt <= tol(a), False,
                f"{dt / 60000:.1f} min apart ({arc:.1f}″ of motion)")
    # A cycle date is the IST date of a change, its state is read at 12:00
    # IST: contested if a change sits within tolerance of an IST midnight (its
    # date may flip) or of the as-of noon (the state may flip).
    noon = e["instant_ms"]
    flip = any(min((c["utc_ms"] + IST_MS) % DAY_MS, DAY_MS - (c["utc_ms"] + IST_MS) % DAY_MS)
               < tol(c) or abs(c["utc_ms"] - noon) < tol(c) for c in ec)
    for moon, (a, b) in enumerate(zip(e["cycles"], w["cycles"], strict=True)):
        t.check(f"{tag}.cycles[moon={moon}]", a == b, flip, f"{a} vs {b}")


def main() -> int:
    births, skies = generate_births(), generate_skies()
    print(f"cross-validating {len(births)} births + {len(skies)} skies "
          "(engine Swiss vs Worker astronomy-engine) ...")
    eb = [engine_birth(b) for b in births]
    es = [engine_sky(s) for s in skies]
    w = worker(births, skies)

    t = Tally()
    for i, (b, e, wb) in enumerate(zip(births, eb, w["births"], strict=True)):
        tag = f"birth[{i}] {b['dob']} {b['time']} {b['zone']}"
        if "error" in wb:
            t.fails.append(f"{tag}: worker error {wb['error']}")
            continue
        compare_natal(t, tag, e["natal"], wb["natal"])
        compare_dasha(t, f"{tag}.dasha", e["dasha"], wb["dasha"],
                      e["natal"]["planets"]["Moon"]["longitude"], b["dob"], b["as_of"])
    for i, (s, e, ws) in enumerate(zip(skies, es, w["skies"], strict=True)):
        compare_sky(t, f"sky[{i}] {s['as_of']}", e, ws)

    n_ing = sum(len(s["ingresses"]) for s in es)
    print(f"checked {t.checked} values ({n_ing} ingresses); worst: "
          + ", ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
                      for k, v in t.worst.items()))
    print(f"contested (boundary cases, recorded not adjudicated): {len(t.contested)}")
    for c in t.contested:
        print(f"  ~ {c}")
    if t.fails:
        print(f"\nFAIL — {len(t.fails)} disagreement(s); DO NOT TUNE, investigate:")
        for f in t.fails[:60]:
            print(f"  {f}")
        return 1

    golden = {
        "births": [{"input": b, "expected": e} for b, e in zip(births, eb, strict=True)],
        "skies": [{"input": s, "expected": e} for s, e in zip(skies, es, strict=True)],
    }
    GOLDEN_PATH.write_text(json.dumps(golden, separators=(",", ":")) + "\n")
    print(f"agreement: every uncontested value; golden written: "
          f"{GOLDEN_PATH.relative_to(ENGINE_ROOT.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
