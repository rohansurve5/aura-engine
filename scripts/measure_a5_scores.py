"""A5 §1 — measure the proposed house/significator area scores BEFORE building.

THE PROPOSED FORMULA (candidate score_rules v4, additive over the v3_2 base):

    h(p)      = ((sign_of(p, day) - asc_sign) mod 12) + 1     # p's transit
                # Whole Sign house counted from the user's natal lagna sign
    T[area]   = sum over p in SIGS[area]:  w[area][p] * G[p][h(p)]
              + sum over all 9 grahas q with h(q) in HOUSES[area]: occ(q, h(q))
    score[a]  = clamp( tara_energy + paksha_mod + weekday_area_mod[wd][a] + T[a] )
    energy    = unchanged (27-row, tara + weekday)

    G[p][h]   = +1 if h in FAV[p], -2 if h in EXTRA_BAD[p], else -1
                (classical gochara favourability, reckoned from the lagna)
    occ(q,h)  = B[q], with malefic B flipped positive in upachaya houses
                {3,6,10,11} ("malefics do well in upachayas")

Sky is sampled at the 00:00 IST day boundary — the same convention
engine/transits.py and measure_gochara_daily.py read by.

MEASUREMENTS (the GO/NO-GO gate for building A5):
  1. A1's own prediction test: exact-vector prediction of the six scores from
     (energy, weekday). v3_2 measured 100% (59,130/59,130). Must collapse.
  2. Area rank order across users on the same day: distinct leaders, distinct
     full rank orders, leader distribution. v3_2: 1 order/day for everyone.
  3. Birth sensitivity on the SCORES: pairs 4 min apart, 2 h apart, same
     instant different city.
  4. Structure disclosure: the additive decomposition score = f(nak,day) +
     g(asc,day) — how many distinct T vectors the 12 ascendants actually take
     per day, and clamp saturation.
  5. Fixed-user leader stability across 90 days (vs Money-leads-94.4%).

Deterministic: seeded RNG, no wall-clock reads.
Run:  uv run python scripts/measure_a5_scores.py
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from engine.chart import ascendant_sidereal
from engine.positions import positions_from_ist
from engine.scoring import load_rules_from_json, tara_of
from engine.timezones import local_to_utc
from engine.vimshottari import nakshatra_of

SEED = 285
N_BIRTHS = 20_000
START_DAY = date(2026, 7, 21)
N_DAYS = 90
BIRTH_START = datetime(1961, 1, 1)
BIRTH_END = datetime(2008, 12, 31, 23, 59)

CITIES = [
    ("Mumbai", 19.0760, 72.8777, 12.4), ("Delhi", 28.6139, 77.2090, 11.0),
    ("Bangalore", 12.9716, 77.5946, 8.4), ("Hyderabad", 17.3850, 78.4867, 6.8),
    ("Ahmedabad", 23.0225, 72.5714, 5.6), ("Chennai", 13.0878, 80.2785, 4.6),
    ("Kolkata", 22.5626, 88.3630, 4.5), ("Surat", 21.1702, 72.8311, 4.5),
    ("Pune", 18.5204, 73.8567, 3.1), ("Jaipur", 26.9124, 75.7873, 3.1),
    ("Lucknow", 26.8467, 80.9462, 2.8), ("Kanpur", 26.4499, 80.3319, 2.8),
    ("Nagpur", 21.1458, 79.0882, 2.4), ("Indore", 22.7196, 75.8577, 1.9),
    ("Thane", 19.2183, 72.9781, 1.8), ("Bhopal", 23.2599, 77.4126, 1.8),
    ("Visakhapatnam", 17.6868, 83.2185, 1.7), ("Patna", 25.5941, 85.1376, 1.7),
    ("Vadodara", 22.3072, 73.1812, 1.7), ("Ghaziabad", 28.6692, 77.4538, 1.6),
]
WEIGHTS = [c[3] for c in CITIES]

BODIES = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")

# ── The candidate v4 tables (these become score_rules v4 if the gate passes) ──
FAV = {
    "Sun": {3, 6, 10, 11},
    "Moon": {1, 3, 6, 7, 10, 11},
    "Mars": {3, 6, 11},
    "Mercury": {2, 4, 6, 8, 10, 11},
    "Jupiter": {2, 5, 7, 9, 11},
    "Venus": {1, 2, 3, 4, 5, 8, 9, 11, 12},
    "Saturn": {3, 6, 11},
    "Rahu": {3, 6, 10, 11},
    "Ketu": {3, 6, 11},
}
EXTRA_BAD = {"Saturn": {1, 8, 12}, "Moon": {8}, "Mars": {8}}
SIGS = {
    "career": {"Saturn": 5, "Sun": 3},
    "money": {"Jupiter": 5, "Venus": 3},
    "love": {"Venus": 5, "Moon": 3},
    "mind": {"Mercury": 6},
    "health": {"Mars": 4, "Sun": 4},
    "mood": {"Moon": 6},
}
HOUSES = {
    "career": {10}, "money": {2, 11}, "love": {7},
    "mind": {5}, "health": {6}, "mood": {4},
}
B_OCC = {
    "Jupiter": 3, "Venus": 2, "Mercury": 1, "Moon": 1,
    "Sun": -1, "Mars": -2, "Saturn": -3, "Rahu": -2, "Ketu": -1,
}
UPACHAYA = {3, 6, 10, 11}

AREAS = ("love", "money", "career", "mind", "health", "mood")


def g_val(planet: str, house: int) -> int:
    if house in FAV[planet]:
        return 1
    if house in EXTRA_BAD.get(planet, ()):
        return -2
    return -1


def t_vector(asc_sign: int, day_signs: dict[str, int]) -> tuple[int, ...]:
    houses = {p: ((day_signs[p] - asc_sign) % 12) + 1 for p in BODIES}
    out = []
    for area in AREAS:
        t = sum(w * g_val(p, houses[p]) for p, w in SIGS[area].items())
        for q in BODIES:
            hq = houses[q]
            if hq in HOUSES[area]:
                b = B_OCC[q]
                if b < 0 and hq in UPACHAYA:
                    b = -b
                t += b
        out.append(t)
    return tuple(out)


def clamp(v: float) -> int:
    return max(0, min(100, int(round(v))))


def main() -> None:
    rng = random.Random(SEED)
    rules = load_rules_from_json()
    order = rules["areas"]["order"]
    assert tuple(order) == AREAS, order

    # ── population: (nak, asc) per birth ─────────────────────────────────────
    print(f"pool: {N_BIRTHS} births 1961-2008, 20 Indian cities (pop-weighted), "
          f"{N_DAYS} days from {START_DAY}")
    span_min = int((BIRTH_END - BIRTH_START).total_seconds() // 60)
    births = []
    for _ in range(N_BIRTHS):
        when = BIRTH_START + timedelta(minutes=rng.randrange(span_min + 1))
        city = rng.choices(CITIES, weights=WEIGHTS)[0]
        births.append((when, city))

    keys = []          # (nak, asc) per birth
    for when, (_, lat, lon, _) in births:
        utc = local_to_utc(when, "+05:30")
        asc = ascendant_sidereal(utc, lat, lon).sign_index
        moon = positions_from_ist(when)["Moon"].longitude
        keys.append((nakshatra_of(moon).index, asc))
    pop = Counter(keys)   # weight per (nak, asc) class

    # ── the sky per day: planet signs + day nakshatra + paksha at 00:00 IST ──
    days = []
    for i in range(N_DAYS):
        d = START_DAY + timedelta(days=i)
        pos = positions_from_ist(datetime(d.year, d.month, d.day))
        signs = {p: int(pos[p].longitude // 30) for p in BODIES}
        moon_lon, sun_lon = pos["Moon"].longitude, pos["Sun"].longitude
        days.append({
            "date": d,
            "wd": str(d.weekday()),
            "signs": signs,
            "day_nak": nakshatra_of(moon_lon).index,
            "waxing": (moon_lon - sun_lon) % 360 < 180,
        })

    # ── score vectors for every (day, nak, asc) class ────────────────────────
    # score = f(nak, day) + g(asc, day), then clamped: compute both halves.
    paksha = rules["paksha"]
    v4 = {}          # (di, nak, asc) -> 6-vector (v4)
    v32 = {}         # (di, nak) -> 6-vector (current)
    energy_of = {}   # (di, nak) -> energy (unchanged in v4)
    for di, day in enumerate(days):
        wd = day["wd"]
        area_mod = rules["weekday_area_mod"][wd]
        e_mod = rules["weekday_energy_mod"][wd]
        p_mod = paksha["waxing" if day["waxing"] else "waning"]
        tvecs = {a: t_vector(a, day["signs"]) for a in range(12)}
        for nak in range(27):
            tara = tara_of(nak, day["day_nak"])
            base = rules["tara"][str(tara)]["energy"] + p_mod
            energy_of[(di, nak)] = clamp(base + e_mod)
            v32[(di, nak)] = tuple(
                clamp(base + area_mod.get(a, 0)) for a in AREAS
            )
            for asc in range(12):
                v4[(di, nak, asc)] = tuple(
                    clamp(base + area_mod.get(a, 0) + t)
                    for a, t in zip(AREAS, tvecs[asc], strict=True)
                )

    n_users_effective = sum(pop.values())
    total_samples = n_users_effective * N_DAYS

    # ── 1. A1's prediction test: (energy, weekday) -> exact six-vector ───────
    def prediction_rate(score_of) -> tuple[int, int]:
        by_key = defaultdict(Counter)
        for di, day in enumerate(days):
            for (nak, asc), w in pop.items():
                key = (energy_of[(di, nak)], day["wd"])
                by_key[key][score_of(di, nak, asc)] += w
        hit = sum(c.most_common(1)[0][1] for c in by_key.values())
        return hit, total_samples

    hit32, tot = prediction_rate(lambda di, nak, asc: v32[(di, nak)])
    hit4, _ = prediction_rate(lambda di, nak, asc: v4[(di, nak, asc)])
    print("\n1. A1 prediction test — six scores predicted exactly from "
          "(energy, weekday):")
    print(f"   v3_2 (current):  {hit32}/{tot} = {hit32 / tot:.1%}")
    print(f"   v4  (proposed):  {hit4}/{tot} = {hit4 / tot:.1%}")

    # also with the ascendant added to the predictor key — how much of the
    # remainder is day-config rather than asc:
    by_key = defaultdict(Counter)
    for di, day in enumerate(days):
        for (nak, asc), w in pop.items():
            by_key[(energy_of[(di, nak)], day["wd"], asc)][v4[(di, nak, asc)]] += w
    hit_asc = sum(c.most_common(1)[0][1] for c in by_key.values())
    print(f"   v4 from (energy, weekday, asc):  {hit_asc / tot:.1%}  "
          f"(remainder = the day's actual planet configuration)")

    # ── 2. rank order across users, per day ──────────────────────────────────
    def rank_of(vec) -> tuple[int, ...]:
        # order areas by (score desc, area-order asc) — scoring.py tie-break
        return tuple(sorted(range(6), key=lambda i: (-vec[i], i)))

    leader_w = Counter()
    dist_leaders, dist_orders = [], []
    for di in range(N_DAYS):
        leaders_today, orders_today = Counter(), set()
        for (nak, asc), w in pop.items():
            r = rank_of(v4[(di, nak, asc)])
            leaders_today[r[0]] += w
            orders_today.add(r)
        for a, w in leaders_today.items():
            leader_w[a] += w
        dist_leaders.append(len(leaders_today))
        dist_orders.append(len(orders_today))
    print("\n2. rank order across users on the same day (v3_2 baseline: "
          "1 order, 1 leader, Money-dominant):")
    print(f"   distinct leaders per day:     mean {sum(dist_leaders) / N_DAYS:.1f} "
          f"(min {min(dist_leaders)}, max {max(dist_leaders)})")
    print(f"   distinct full rank orders/day: mean {sum(dist_orders) / N_DAYS:.1f} "
          f"(min {min(dist_orders)}, max {max(dist_orders)})")
    shares = ", ".join(
        f"{AREAS[a].capitalize()} {leader_w[a] / total_samples:.1%}"
        for a in sorted(leader_w, key=lambda a: -leader_w[a])
    )
    print(f"   leader share of user-days:    {shares}")

    # ── 3. birth sensitivity, measured on the scores ─────────────────────────
    sub = births[:4_000]
    sample_days = rng.sample(range(N_DAYS), 10)

    def key_of(when, lat, lon):
        utc = local_to_utc(when, "+05:30")
        return (
            nakshatra_of(positions_from_ist(when)["Moon"].longitude).index,
            ascendant_sidereal(utc, lat, lon).sign_index,
        )

    def pair_stats(shift: timedelta | None, other_city: bool) -> tuple[float, float]:
        n_diff_vec = n_diff_rank = 0
        n = 0
        for when, (name, lat, lon, _) in sub:
            if other_city:
                oc = rng.choices(CITIES, weights=WEIGHTS)[0]
                while oc[0] == name:
                    oc = rng.choices(CITIES, weights=WEIGHTS)[0]
                k1, k2 = key_of(when, lat, lon), key_of(when, oc[1], oc[2])
            else:
                k1, k2 = key_of(when, lat, lon), key_of(when + shift, lat, lon)
            for di in sample_days:
                a, b = v4[(di, *k1)], v4[(di, *k2)]
                n += 1
                n_diff_vec += a != b
                n_diff_rank += rank_of(a) != rank_of(b)
        return n_diff_vec / n, n_diff_rank / n

    v1, r1 = pair_stats(timedelta(minutes=4), False)
    v2, r2 = pair_stats(timedelta(hours=2), False)
    v3, r3 = pair_stats(None, True)
    print("\n3. birth sensitivity on the six scores (v3_2 baseline: 4 min ~3.7% "
          "boundary-only, 2 h ~8%, city 0.0%):")
    print(f"   births 4 min apart:  scores differ {v1:.1%} of user-days, "
          f"rank order differs {r1:.1%}")
    print(f"   births 2 h apart:    scores differ {v2:.1%}, rank order {r2:.1%}")
    print(f"   same instant, different city: scores differ {v3:.1%}, "
          f"rank order {r3:.1%}")

    # ── 4. structure disclosure ──────────────────────────────────────────────
    tv_distinct = []
    for day in days:
        tv_distinct.append(len({t_vector(a, day["signs"]) for a in range(12)}))
    n_scores = N_DAYS * 27 * 12 * 6
    n_sat = sum(
        (s in (0, 100))
        for vecs in v4.values() for s in vecs
    )
    print("\n4. structure (stated honestly):")
    print("   score = f(nak, day) + g(asc, day) BEFORE clamping — additive by "
          "construction, no nak x asc interaction term.")
    print("   consequence: on one day, users with the same asc sign share a "
          "rank order; the order key is (asc, day), 12-way, not 324-way.")
    print(f"   distinct T vectors across the 12 ascendants: "
          f"mean {sum(tv_distinct) / N_DAYS:.1f}/12 per day "
          f"(min {min(tv_distinct)}, max {max(tv_distinct)})")
    print(f"   clamp saturation: {n_sat / n_scores:.2%} of all area scores "
          f"sit at 0 or 100")

    # ── 5. fixed-user leader stability across the 90 days ───────────────────
    top_share, change_rate = [], []
    for nak, asc in pop:
        leaders = [rank_of(v4[(di, nak, asc)])[0] for di in range(N_DAYS)]
        c = Counter(leaders)
        top_share.append(c.most_common(1)[0][1] / N_DAYS)
        changes = sum(leaders[i] != leaders[i - 1] for i in range(1, N_DAYS))
        change_rate.append(changes / (N_DAYS - 1))
    ts = sum(top_share) / len(top_share)
    cr = sum(change_rate) / len(change_rate)
    print("\n5. fixed user across 90 days (baseline: leader same for everyone, "
          "Money 94.4% of months):")
    print(f"   a user's most common leader holds {ts:.1%} of their days (mean); "
          f"day-to-day leader changes on {cr:.1%} of days")


if __name__ == "__main__":
    main()
