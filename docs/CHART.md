# Birth chart — the Worker port & its gate (Block 8 §2/§3)

`engine/chart.py` has computed the full sidereal chart since A3 (ascendant,
Whole Sign houses, nine graha placements — see [ASCENDANT.md](ASCENDANT.md)).
Block 8 ports that chart into the Worker so the app can display it, gates the
port against Swiss Ephemeris, exposes it at `/v1/chart`, and stores it on the
device profile. This document records the port's three from-scratch decisions,
the cross-validation and its tolerances, and the arctic-circle boundary the
gate discovered. No chart SCREENS are built here — that is the next task.

## What the Worker computes (`aura-api/src/chart.ts`)

For a birth instant (UTC) at a place below the polar circle:

* **Ascendant** — reused verbatim from `src/ascendant.ts` (the A5 port already
  gated by `crossval_ascendant.py`); the chart does not re-derive the lagna.
* **12 Whole Sign house cusps** — `house_signs[i] = SIGNS[(asc_sign + i) % 12]`,
  the same rotation the engine ships. House 1 is always the ascendant's sign.
* **Nine grahas**, each in a sidereal sign, a Whole Sign house
  (`((planet_sign − asc_sign) mod 12) + 1`), and a direction.

Placidus cusps / MC and KP are **not** ported — they are undefined above 66° and
serve KP only, which is out of scope (ASCENDANT.md § houses). Whole Sign is the
product chart.

### Decision 1 — Rahu/Ketu from a mean lunar node built from scratch

astronomy-engine provides only the TRUE node, but the engine (and AstroSage's
Vimshottari) use the MEAN node. So `chart.ts` computes the mean longitude of the
ascending node Ω on the mean ecliptic of date directly:

    Ω = 125.0445479 − 1934.1362891·T + 0.0020754·T² + T³/467441 − T⁴/60616000

(T = Julian centuries of TT from J2000). **Source:** Meeus, *Astronomical
Algorithms* 2nd ed., eq. 47.7 — the standard IAU/ELP mean-element series that
Swiss Ephemeris' `swe.MEAN_NODE` also evaluates. Sidereal Rahu = `norm360(Ω −
ayanamsaVp285)`; Ketu = Rahu + 180°; both always retrograde (the node regresses
at ≈ 0.053°/day). This was the piece most likely to diverge silently, so it was
cross-checked against the engine FIRST: the crossval measures **max node Δ well
within the 1′ gate** (the whole asc+9-graha set peaks at **19.27″**).

### Decision 2 — retrogradity by finite difference, with a stated station policy

Direction is the sign of the apparent sidereal speed, estimated by a central
difference of the sidereal longitude over ±1 h. That window differences a smooth
analytic series (no sampling jitter) and carries the ayanamsa rate exactly as
Swiss' sidereal speed does, so its sign matches Swiss everywhere except within
the station window. A planet whose speed is within **STATION_EPS = 0.02°/day**
of zero is stationing — within a few hours of the turn its direct/retrograde
state is genuinely ambiguous. That is surfaced as `near_station` in the payload
(never asserted as certain), the way the ascendant surfaces `near_boundary`; and
if the engine and Worker ever disagree on the retrograde bit inside that band,
the crossval records a **station-boundary case** rather than adjudicating it.

### Decision 3 — the arctic-circle boundary (measured)

The closed-form ascendant agrees with Swiss to **≤ 15″ up to 66.5°**, then jumps
~180° at 67° (it selects the descending root). This is physical, not a bug: above
the arctic/antarctic circle the ecliptic goes circumpolar and the ascending
horizon intersection is no longer unique. It is the **same latitude at which the
engine already publishes no Placidus cusps** (`_PLACIDUS_LAT_LIMIT = 66.0`) —
both fail for one reason. So the chart is defined for **|lat| < 66.0** and
`/v1/chart` refuses above it (`chart: null` + reason), never a wrong lagna. The
`crossval_chart.py` world panel therefore tops out at Anchorage (61.2°N, clean);
Tromsø (69.6°N) is the refused example, asserted by `chart.test.ts`.

## The gate (`aura-engine/scripts/crossval_chart.py`)

1,001 births — 945 India (population-weighted over the 20 largest cities) + 50
world (high latitude below the circle, southern hemisphere, DST zones, +05:45) +
**5 seeded genuine near-station births** (one per slow mover, found by scanning
the engine's own speed for a sign change and bisecting to the turn, so the
station machinery is exercised rather than merely coded) + the 1943 war-time-DST
Kolkata birth. Every birth is resolved by BOTH the engine (`compute_chart`,
lahiri_vp285 — source of truth) and the exact Worker TypeScript (via
`aura-api/scripts/chart-batch.ts`, no reimplementation).

**Covers every quantity a screen displays:** ascendant longitude & sign, each
graha's longitude, sign & Whole Sign house, the 12 house cusps, and retrogradity.

**Tolerances, defended.** Longitude ≤ **1 arc-minute** on the ascendant and all
nine grahas (measured max 19.27″ ≈ 1.3 s of birth time — the same bar natal,
dasha and ascendant hold to). Sign, house and direction agree 100% except:

* a **sign-ingress boundary** — a body both sides place within 1′ of the same
  ingress (1′ ≈ 4 s of birth time), where the sign is genuinely contested; and
* a **station boundary** — both sides within STATION_EPS of zero speed.

Contested cases are flagged in the golden and asserted AS contested by
`test/chart.crossval.test.ts` (still near the ingress / still near the station),
never adjudicated. The last run: **1001/1001 clean, 1 sign-ingress boundary, 1
station boundary, 238 near-station placements exercised.** The gate is blocking
in aura-api CI and predeploy.

## Exposure (`aura-api` `/v1/chart`)

A **separate endpoint, not an extension of `/v1/natal`** — decided on the zone=
lesson. `/v1/natal` already returns an `ascendant` block for a `?…&lat&lon&time`
request and is cached `immutable, 1y`; folding the chart into that same response
would change the shape of already-cached URLs, so POPs would serve the
ascendant-only body for up to a year while cold POPs served the chart. A new URL
is a new cache namespace by construction, and `/v1/natal` stays byte-identical
for every existing caller (its 5 crossvals regenerate sha256-identical).

**Birth time required** — no time ⇒ `chart: null` with a reason, never a noon
lagna. **Arctic refusal** as above. Cached `immutable, 1y` (birth data never
changes); `r=` is the same rollback lever `/v1/natal` documents.

**Egress:** the app now calls `/v1/chart`, so `privacy_egress_test.dart` gains a
`/v1/chart` manifest row and `legal/privacy.html` gains a `/v1/chart` clause —
and the old "Aura does not calculate a full birth chart" sentence, now false,
was rewritten in the same change (the drift class that gate exists to catch).

## Storage (`Aura` app)

`UserProfile.chart` (a `NatalChart`) is persisted alongside the flat ascendant
fields, resolved by `ApiClient.fetchChart`, backfilled in the background off the
same on-open path that re-fires the natal lookup, and cleared as one unit with a
re-resolved birth (`clearChart`, matching `clearAscendant`/`clearNatalMoonSign`)
so a fresh ascendant never pairs with a stale chart. Absent (never wrong) on
profiles saved before the field existed and whenever the birth time is unknown.

## Re-running

    uv run python scripts/crossval_chart.py      # regenerates the golden
    cd ../aura-api && npm test                    # replays it + the endpoint contract
