"""Does 'personal muhurat' carry a per-user signal, or is it day-quality relabelled?

The A2 paywall REMOVED "Personal muhurat" as not computable without houses. A3
built the ascendant + houses. This script answers, with numbers and the same
discipline as sensitivity_ascendant.py / measure_a5_scores.py, two questions:

  §2.1  How many candidate windows does a purpose search actually return per
        day? (If nearly every hour qualifies it is decorative; if almost none,
        useless.) Distribution over a realistic (place, day) grid.

  §2.2  THE NUMBER. Does the USER's chart meaningfully change WHICH windows are
        returned / how they rank — or are two users at the same place/day given
        the same list? Measured three ways:
          (a) day-quality muhurat (no birth time): the qualifying window list is
              a pure function of (place, day). Confirmed identical across users.
          (b) + tarabala/chandrabala (the classical PERSONAL factors that need
              no birth time): these are DAY-CONSTANT, so they add equally to
              every window in a day and cannot re-rank the windows. Measured:
              fraction of user-pairs whose within-day ORDER differs.
          (c) + lagna-house-from-natal (needs a birth time; the A3 unlock): the
              rising sign at a window, counted as a Whole-Sign house from the
              user's natal lagna, VARIES within the day and differs by user.
              Measured: fraction of user-pairs whose TOP window / ordered list
              differs, under a range of weightings so the verdict is not an
              artefact of one weight.

Deterministic: seeded RNG, no wall-clock reads. India/IST only (the launch
market; wall clock = instant, no DST) — the non-IST window accuracy is already
gated by scripts/crossval_window.py. Re-run:
    uv run python scripts/measure_muhurat.py
"""

from __future__ import annotations

import os
import statistics
import sys
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

import swisseph as swe

from engine.chart import ascendant_sidereal, compute_chart
from engine.choghadiya import (
    day_choghadiya,
    gulika_kaal,
    night_choghadiya,
    rahu_kaal,
    yamaganda_kaal,
)
from engine.ephemeris import IST
from engine.muhurat import (  # the shipped constants — single source of truth
    CHOG_RANK,
    GOOD_LAGNA_HOUSE,
    LAGNA_CLASS_FIT,
    PURPOSES,
)
from engine.positions import sidereal_positions
from engine.timezones import local_to_utc
from engine.vimshottari import nakshatra_of

SEED = 285
ENGINE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Personal, birth-time-free: tarabala (day Moon nakshatra from natal nakshatra)
# and chandrabala (day Moon rashi from natal rashi). Both are DAY-CONSTANT — the
# measurement below proves they cannot re-rank within-day windows.
GOOD_TARA = {2, 4, 6, 8, 9}          # 1-indexed favourable taras
GOOD_CHANDRA = {1, 3, 6, 7, 10, 11}  # favourable Moon-from-Moon houses (1-idx)

CITIES = [
    ("Mumbai", 19.0760, 72.8777), ("Delhi", 28.6139, 77.2090),
    ("Bangalore", 12.9716, 77.5946), ("Kolkata", 22.5626, 88.3630),
    ("Chennai", 13.0878, 80.2785), ("Jaipur", 26.9124, 75.7873),
]
BIRTH_CITIES = CITIES  # synthetic births drawn from the same set


def _rise_set(jd_start: float, lat: float, lon: float, *, rise: bool) -> float:
    flag = swe.CALC_RISE if rise else swe.CALC_SET
    res, times = swe.rise_trans(jd_start, swe.SUN, flag, (lon, lat, 0.0))
    if res != 0:
        raise ValueError("no rise/set")
    return times[0]


def _jd_to_ist_naive(jd: float) -> datetime:
    y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
    utc = datetime(y, m, d, tzinfo=UTC) + timedelta(hours=h)
    return utc.astimezone(IST).replace(tzinfo=None, microsecond=0)


def day_windows(day: date, lat: float, lon: float) -> list[tuple[str, int]]:
    """The 16 choghadiya slots for (day, place), each as (name, lagna_sign at
    its midpoint), with the three kaals marked by blanking their day slot name
    to 'KAAL' so it never qualifies. Impersonal: pure function of (day, place)."""
    midnight = datetime.combine(day, time()).replace(tzinfo=IST)
    jd_mid = swe.julday(*midnight.astimezone(UTC).timetuple()[:3],
                        midnight.astimezone(UTC).hour + midnight.astimezone(UTC).minute / 60)
    jd_rise = _rise_set(jd_mid, lat, lon, rise=True)
    jd_set = _rise_set(jd_rise, lat, lon, rise=False)
    jd_next = _rise_set(jd_set, lat, lon, rise=True)
    rise, sset, nxt = (_jd_to_ist_naive(j) for j in (jd_rise, jd_set, jd_next))

    day_slots = day_choghadiya(rise, sset)
    night_slots = night_choghadiya(sset, nxt)
    # Kaals occupy exact day-part boundaries == day choghadiya slots. Blank them.
    kaal_starts = {
        rahu_kaal(rise, sset).start,
        gulika_kaal(rise, sset).start,
        yamaganda_kaal(rise, sset).start,
    }
    out: list[tuple[str, int]] = []
    for w in day_slots + night_slots:
        name = "KAAL" if w.start in kaal_starts else w.name
        mid = w.start + (w.end - w.start) / 2
        asc = ascendant_sidereal(local_to_utc(mid, "+05:30"), lat, lon)
        out.append((name, asc.sign_index))
    return out


def qualifying(windows: list[tuple[str, int]], purpose: str) -> list[int]:
    """Indices of windows whose choghadiya is in the purpose's favoured set."""
    favoured = PURPOSES[purpose]
    return [i for i, (name, _) in enumerate(windows) if name in favoured]


def score(windows, idx, purpose, user, *, w_tara, w_lagna):
    """A per-window score. Impersonal terms + optional personal terms. `user` is
    (natal_nak_index, natal_moon_sign, natal_asc_sign, day_tara, day_chandra)."""
    name, lagna_sign = windows[idx]
    s = CHOG_RANK.get(name, 0)
    if lagna_sign in LAGNA_CLASS_FIT[purpose]:
        s += 1                                   # impersonal lagna-class fit
    # Personal but DAY-CONSTANT (adds equally to every window this day):
    _, _, natal_asc, day_tara, day_chandra = user
    s += w_tara * ((day_tara in GOOD_TARA) + (day_chandra in GOOD_CHANDRA))
    # Personal AND within-day-varying (needs birth time): lagna house from natal.
    house = (lagna_sign - natal_asc) % 12 + 1
    s += w_lagna * (house in GOOD_LAGNA_HOUSE)
    return s


def ranked(windows, quals, purpose, user, *, w_tara, w_lagna):
    """Qualifying window indices, best-first; impersonal stable tie-break (start
    order) so any reordering is a real personal effect, not tie noise."""
    return sorted(
        quals,
        key=lambda i: (-score(windows, i, purpose, user, w_tara=w_tara, w_lagna=w_lagna), i),
    )


def main() -> None:
    import random

    swe.set_ephe_path(os.path.join(ENGINE_ROOT, "ephe"))
    rng = random.Random(SEED)

    start = date(2026, 7, 21)
    n_days = 90
    days = [start + timedelta(days=i) for i in range(n_days)]

    # ── Synthetic user population: natal (nak idx, moon sign, asc sign) ──────
    n_users = 300
    bstart = datetime(1970, 1, 1)
    bspan = int((datetime(2006, 12, 31, 23, 59) - bstart).total_seconds() // 60)
    users_natal = []
    for _ in range(n_users):
        when = bstart + timedelta(minutes=rng.randrange(bspan + 1))
        _, lat, lon = rng.choice(BIRTH_CITIES)
        c = compute_chart(local_to_utc(when, "+05:30"), lat, lon)
        moon_lon = c.placements["Moon"].position.longitude
        users_natal.append(
            (nakshatra_of(moon_lon).index, int(moon_lon // 30), c.ascendant.sign_index)
        )

    # ── Per-day sky: transit Moon nakshatra + rashi at 00:00 IST boundary ────
    day_sky = {}
    for d in days:
        inst = datetime.combine(d, time()).replace(tzinfo=IST).astimezone(UTC).replace(tzinfo=None)
        moon = sidereal_positions(inst)["Moon"].longitude
        day_sky[d] = (nakshatra_of(moon).index, int(moon // 30))

    def user_row(natal, d):
        nak, msign, asc = natal
        day_nak, day_msign = day_sky[d]
        tara = (day_nak - nak) % 9 + 1            # 1..9 tarabala
        chandra = (day_msign - msign) % 12 + 1    # 1..12 chandrabala house
        return (nak, msign, asc, tara, chandra)

    # ── Precompute the impersonal 16-window vector for each (city, day) ──────
    grid = {}
    for cname, lat, lon in CITIES:
        for d in days:
            grid[(cname, d)] = day_windows(d, lat, lon)

    # ═══ §2.1  Candidate-window distribution ═══════════════════════════════
    print(f"cities={len(CITIES)} days={n_days} ({start}..{days[-1]}) "
          f"users={n_users}\n")
    print("§2.1  qualifying windows per day (of 16 choghadiya slots; kaals removed)")
    daytime_slots = 8
    for purpose in PURPOSES:
        counts = [len(qualifying(grid[k], purpose)) for k in grid]
        day_counts = [  # how many of the qualifying fall in the 8 DAY slots
            sum(1 for i in qualifying(grid[k], purpose) if i < 8) for k in grid
        ]
        hist = Counter(counts)
        frac_daytime = statistics.mean(day_counts) / daytime_slots
        print(f"  {purpose:9} mean {statistics.mean(counts):4.1f}/16  "
              f"min {min(counts)} max {max(counts)}  "
              f"daytime coverage {frac_daytime:5.1%}  "
              f"hist={dict(sorted(hist.items()))}")

    # ═══ §2.2  Personalisation ═════════════════════════════════════════════
    print("\n§2.2  does the USER's chart change the returned/ranked windows?")

    # (a) day-quality muhurat: the qualifying LIST is a pure function of place+day
    #     → identical for every user, by construction. Confirm and state it.
    print("  (a) no birth time — qualifying window list is (place, day) only, "
          "identical for all users: TRUE by construction.")

    # (b) + tarabala/chandrabala (day-constant): can they re-rank within a day?
    #     Compare two random users' ORDER on the same (place, day), w_lagna=0.
    pairs = 20_000
    keys = list(grid)
    diff_order_b = 0
    for _ in range(pairs):
        k = rng.choice(keys)
        d = k[1]
        purpose = rng.choice(list(PURPOSES))
        quals = qualifying(grid[k], purpose)
        if len(quals) < 2:
            continue
        ua = user_row(users_natal[rng.randrange(n_users)], d)
        ub = user_row(users_natal[rng.randrange(n_users)], d)
        ra = ranked(grid[k], quals, purpose, ua, w_tara=3, w_lagna=0)
        rb = ranked(grid[k], quals, purpose, ub, w_tara=3, w_lagna=0)
        diff_order_b += ra != rb
    print(f"  (b) + tarabala/chandrabala (no birth time, day-constant): "
          f"within-day order differs on {diff_order_b}/{pairs} user-pairs "
          f"= {diff_order_b / pairs:.2%}")

    # (c) + lagna-house-from-natal (birth time): the only within-day-varying
    #     personal term. Sweep its weight; report top-window and full-order
    #     disagreement across random user pairs at the same (place, day).
    print("  (c) + lagna-house-from-natal (birth time). Sweep weight w_lagna "
          "(choghadiya rank spans 0-4; tara term fixed at 3):")
    for w_lagna in (1, 2, 4):
        diff_top = diff_list = considered = 0
        for _ in range(pairs):
            k = rng.choice(keys)
            d = k[1]
            purpose = rng.choice(list(PURPOSES))
            quals = qualifying(grid[k], purpose)
            if len(quals) < 2:
                continue
            considered += 1
            ua = user_row(users_natal[rng.randrange(n_users)], d)
            ub = user_row(users_natal[rng.randrange(n_users)], d)
            ra = ranked(grid[k], quals, purpose, ua, w_tara=3, w_lagna=w_lagna)
            rb = ranked(grid[k], quals, purpose, ub, w_tara=3, w_lagna=w_lagna)
            diff_top += ra[0] != rb[0]
            diff_list += ra != rb
        print(f"      w_lagna={w_lagna}: top window differs "
              f"{diff_top / considered:.1%}, full order differs "
              f"{diff_list / considered:.1%}  (n={considered})")

    # (c') UPPER BOUND: lagna-house ALONE decides the ranking (choghadiya off).
    #      Shows the most personalisation the birth-time term can ever inject.
    diff_top = considered = 0
    for _ in range(pairs):
        k = rng.choice(keys)
        d = k[1]
        purpose = rng.choice(list(PURPOSES))
        quals = qualifying(grid[k], purpose)
        if len(quals) < 2:
            continue
        considered += 1
        ua = user_row(users_natal[rng.randrange(n_users)], d)
        ub = user_row(users_natal[rng.randrange(n_users)], d)
        # w_lagna huge, choghadiya negligible → lagna-house dominates.
        ra = ranked(grid[k], quals, purpose, ua, w_tara=0, w_lagna=100)
        rb = ranked(grid[k], quals, purpose, ub, w_tara=0, w_lagna=100)
        diff_top += ra[0] != rb[0]
    print(f"  (c') upper bound — lagna-house alone decides: top window differs "
          f"{diff_top / considered:.1%} of user-pairs (n={considered})")

    # (c'') THE ALTITUDE. The within-day term depends ONLY on natal lagna SIGN
    #       (tara/chandra are day-constant), so two users sharing a lagna sign
    #       get an identical ranking. Personal muhurat is therefore a 12-WAY
    #       (lagna-sign) personalisation — the exact altitude the A5 area scores
    #       ship at — NOT a per-individual reading. Quantify it like A5 did:
    #       distinct top-windows / distinct orders across the 12 lagna signs.
    def ranking_for_lagna(windows, quals, purpose, asc_sign, w_lagna):
        fake = (0, 0, asc_sign, 0, 0)  # tara/chandra neutral → w_tara irrelevant
        return tuple(ranked(windows, quals, purpose, fake, w_tara=0, w_lagna=w_lagna))

    # same-lagna-sign users are identical by construction — assert it once.
    k0 = keys[0]
    d0 = k0[1]
    q0 = qualifying(grid[k0], "start")
    while len(q0) < 2:
        k0 = rng.choice(keys)
        d0 = k0[1]
        q0 = qualifying(grid[k0], "start")
    same_sign_users = [user_row(n, d0) for n in users_natal if n[2] == users_natal[0][2]]
    orders = {tuple(ranked(grid[k0], q0, "start", u, w_tara=0, w_lagna=2))
              for u in same_sign_users}
    print(f"\n  (c'') users sharing a natal lagna sign ({len(same_sign_users)} of them) "
          f"→ {len(orders)} distinct within-day ranking (should be 1): "
          f"{'CONFIRMED 12-way' if len(orders) == 1 else 'NOT lagna-only'}")

    dtop, dord, samples = [], [], 0
    for k in keys:
        d = k[1]
        for purpose in PURPOSES:
            quals = qualifying(grid[k], purpose)
            if len(quals) < 2:
                continue
            samples += 1
            tops, ords = set(), set()
            for asc_sign in range(12):
                r = ranking_for_lagna(grid[k], quals, purpose, asc_sign, w_lagna=2)
                tops.add(r[0])
                ords.add(r)
            dtop.append(len(tops))
            dord.append(len(ords))
    print(f"  (c'') across the 12 lagna signs, per (place,day,purpose) with >=2 "
          f"windows (n={samples}): mean {statistics.mean(dtop):.1f} distinct top "
          f"windows (max {max(dtop)}), mean {statistics.mean(dord):.1f} distinct "
          f"orders (max {max(dord)}).")

    # ── The day-level go/no-go IS personal — but it is the EXISTING energy ──
    #    score, not a per-window muhurat. Quantify so the recommendation is fair.
    flips = trials = 0
    for _ in range(pairs):
        d = rng.choice(days)
        ua = user_row(users_natal[rng.randrange(n_users)], d)
        ub = user_row(users_natal[rng.randrange(n_users)], d)
        good_a = (ua[3] in GOOD_TARA) and (ua[4] in GOOD_CHANDRA)
        good_b = (ub[3] in GOOD_TARA) and (ub[4] in GOOD_CHANDRA)
        trials += 1
        flips += good_a != good_b
    print(f"\n  day-level personal go/no-go (tarabala+chandrabala) differs on "
          f"{flips / trials:.1%} of user-pairs — REAL, but this is the existing "
          f"daily energy score, not a per-window timing.")


if __name__ == "__main__":
    main()
