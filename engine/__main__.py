"""Command-line interface for the Aura Calculation Engine.

    python -m engine dasha --dob 23/09/1989 --time 04:47 --lat 19.99 --lon 73.79
    python -m engine positions --dob 23/09/1989 --time 04:47
    python -m engine panchang --date 2026-07-18 --lat 18.5204 --lon 73.8567

`dasha` prints the maha + antar table in the same layout as AstroSage's export
so charts can be eyeballed side by side (Lahiri VP285 — the flavour proven to
match AstroSage). `panchang` prints a DrikPanchang-style day card (plain
Lahiri — the flavour proven to match DrikPanchang). See README.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from .choghadiya import (
    day_choghadiya,
    gulika_kaal,
    night_choghadiya,
    rahu_kaal,
    yamaganda_kaal,
)
from .ephemeris import ASTROSAGE_AYANAMSA, AYANAMSAS, DRIKPANCHANG_AYANAMSA
from .panchang import compute_panchang
from .positions import positions_from_ist
from .vimshottari import YEAR_MODES, compute_dasha, format_astrosage


def _parse_birth(dob: str, time: str) -> datetime:
    """Parse dd/mm/yyyy + HH:MM (IST wall-clock) into a naive datetime."""
    try:
        d, m, y = (int(x) for x in dob.split("/"))
        hh, mm = (int(x) for x in time.split(":"))
    except ValueError:
        raise SystemExit(f"could not parse --dob {dob!r} --time {time!r} "
                         "(expected dd/mm/yyyy and HH:MM)") from None
    return datetime(y, m, d, hh, mm)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dob", required=True, help="birth date, dd/mm/yyyy (IST)")
    p.add_argument("--time", required=True, help="birth time, HH:MM (24h, IST)")
    p.add_argument("--lat", type=float, default=None,
                   help="birth latitude (optional; dasha is location-independent)")
    p.add_argument("--lon", type=float, default=None, help="birth longitude (optional)")
    p.add_argument("--ayanamsa", default=ASTROSAGE_AYANAMSA, choices=sorted(AYANAMSAS),
                   help=f"sidereal mode (default: {ASTROSAGE_AYANAMSA})")
    p.add_argument("--true-node", action="store_true", help="use true lunar node")


def cmd_dasha(args: argparse.Namespace) -> int:
    birth = _parse_birth(args.dob, args.time)
    moon = positions_from_ist(
        birth, lat=args.lat, lon=args.lon,
        ayanamsa=args.ayanamsa, true_node=args.true_node,
    )["Moon"].longitude
    result = compute_dasha(moon, birth, year_mode=args.year_mode, levels=2, cycles=2)
    print(format_astrosage(
        result, birth, blocks=args.blocks, astrosage_rounding=args.astrosage_rounding,
    ))
    print(f"\n# ayanamsa={args.ayanamsa}  year_mode={args.year_mode}  "
          f"nakshatra={result.nakshatra.name} pada {result.nakshatra.pada} "
          f"(lord {result.nakshatra.lord})")
    if args.ayanamsa != ASTROSAGE_AYANAMSA:
        print(f"# note: {args.ayanamsa!r} may not match AstroSage; "
              f"use --ayanamsa {ASTROSAGE_AYANAMSA} for parity")
    return 0


def cmd_positions(args: argparse.Namespace) -> int:
    birth = _parse_birth(args.dob, args.time)
    pos = positions_from_ist(
        birth, lat=args.lat, lon=args.lon,
        ayanamsa=args.ayanamsa, true_node=args.true_node,
    )
    print(f"Sidereal positions ({args.ayanamsa}) for {args.dob} {args.time} IST")
    print("-" * 40)
    for name in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
                 "Saturn", "Rahu", "Ketu"):
        print(pos[name])
    return 0


def cmd_panchang(args: argparse.Namespace) -> int:
    try:
        day = date.fromisoformat(args.date)
    except ValueError:
        raise SystemExit(f"could not parse --date {args.date!r} (expected YYYY-MM-DD)") from None
    p = compute_panchang(day, args.lat, args.lon, ayanamsa=args.ayanamsa)

    def fmt(dt_: datetime) -> str:
        suffix = f", {dt_:%b %d}" if dt_.date() != day else ""
        return f"{dt_:%I:%M %p}{suffix}"

    w = 66
    print("=" * w)
    print(f"  Panchang — {day:%A, %B %d, %Y}   ({args.lat:.4f}, {args.lon:.4f})")
    print("=" * w)
    print(f"  Sunrise  {p.sunrise:%I:%M %p}    Sunset  {p.sunset:%I:%M %p}    "
          f"{p.vaar} | {p.paksha} Paksha")
    print("-" * w)
    for label, elems in (
        ("Tithi", p.tithi), ("Nakshatra", p.nakshatra),
        ("Yoga", p.yoga), ("Karana", p.karana),
    ):
        parts = [f"{e.name} upto {fmt(e.end)}" for e in elems]
        print(f"  {label:10} " + "; ".join(parts))
    print("-" * w)
    for kaal in (rahu_kaal, gulika_kaal, yamaganda_kaal):
        k = kaal(p.sunrise, p.sunset)
        print(f"  {k.name:12} {k.start:%I:%M %p} to {k.end:%I:%M %p}")
    print("-" * w)
    print("  Day Choghadiya" + " " * 18 + "Night Choghadiya")
    night = night_choghadiya(p.sunset, p.next_sunrise)
    for d_slot, n_slot in zip(day_choghadiya(p.sunrise, p.sunset), night, strict=False):
        print(f"  {d_slot!s:30}  {n_slot!s}")
    print("=" * w)
    print(f"  # ayanamsa={args.ayanamsa}  moon phase={p.phase_fraction:.1%} "
          f"{'waxing' if p.waxing else 'waning'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m engine", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("dasha", help="print the Vimshottari maha+antar table")
    _add_common(d)
    d.add_argument("--year-mode", default="solar", choices=sorted(YEAR_MODES),
                   help="dasha-year length (default: solar = 365.25 days)")
    d.add_argument("--blocks", type=int, default=10, help="maha blocks to print")
    d.add_argument("--astrosage-rounding", action="store_true",
                   help="cascading day-rounded dates (closer to AstroSage's "
                        "table; see README > Known deviations)")
    d.set_defaults(func=cmd_dasha)

    p = sub.add_parser("positions", help="print sidereal graha longitudes")
    _add_common(p)
    p.set_defaults(func=cmd_positions)

    pc = sub.add_parser("panchang", help="print a DrikPanchang-style day card")
    pc.add_argument("--date", required=True, help="civil date, YYYY-MM-DD (local)")
    pc.add_argument("--lat", type=float, required=True, help="latitude")
    pc.add_argument("--lon", type=float, required=True, help="longitude")
    pc.add_argument("--ayanamsa", default=DRIKPANCHANG_AYANAMSA,
                    choices=sorted(AYANAMSAS),
                    help=f"sidereal mode (default: {DRIKPANCHANG_AYANAMSA} — "
                         "matches DrikPanchang)")
    pc.set_defaults(func=cmd_panchang)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
