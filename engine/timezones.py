"""Timezone specs: fixed UTC offsets and IANA zone ids, resolved at an instant.

Two spec forms are accepted everywhere a timezone is configured:

  "+05:30" / "-08:00"   a FIXED offset. Means exactly that offset, always, for
                        every date. Historical DST is deliberately NOT applied.
  "Asia/Kolkata"        an IANA zone id. The offset is resolved AT THE GIVEN
                        INSTANT from the tz database, so a 1943 Calcutta birth
                        correctly resolves to +06:30 (India's war-time DST,
                        1942-09-01 → 1945-10-15) while a 1990 one is +05:30.

The two forms are kept distinct on purpose. "+05:30" is the legacy contract of
the natal cross-validation goldens and of `daily_sky.location`, and it must keep
meaning what it has always meant — see README "Known deviations". IANA is a new
input class, never a reinterpretation of an existing one.

The Worker mirrors this module in TypeScript (aura-api/src/natal.ts, via
Intl.DateTimeFormat). Both sides are cross-validated on the same golden set.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")


def is_fixed_offset(spec: str) -> bool:
    """True if `spec` is a fixed "+HH:MM"/"-HH:MM" offset rather than a zone id."""
    return _OFFSET_RE.match(spec) is not None


def resolve_tz(spec: str) -> tzinfo:
    """A tzinfo for `spec`, which may be "+HH:MM"/"-HH:MM" or an IANA zone id.

    Raises ValueError on anything unrecognised — callers must NOT fall back to a
    guess, because a silently-wrong timezone is a silently-wrong chart.
    """
    m = _OFFSET_RE.match(spec)
    if m is not None:
        sign = -1 if m.group(1) == "-" else 1
        minutes = sign * (int(m.group(2)) * 60 + int(m.group(3)))
        return timezone(timedelta(minutes=minutes), name=spec)
    try:
        return ZoneInfo(spec)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unrecognised timezone spec: {spec!r}") from exc


def offset_minutes_at(spec: str, local_naive: datetime) -> int:
    """Minutes east of UTC in `spec` at the wall-clock instant `local_naive`."""
    off = local_naive.replace(tzinfo=resolve_tz(spec)).utcoffset()
    assert off is not None  # both branches of resolve_tz always supply one
    return int(off.total_seconds() // 60)


def local_to_utc(local_naive: datetime, spec: str) -> datetime:
    """Interpret a naive wall-clock datetime in `spec` and return aware UTC.

    For an IANA spec the offset is taken at that wall-clock instant, so births
    inside a historical DST window get the DST offset. Ambiguous times (the
    repeated hour at a fall-back transition) resolve to the FIRST occurrence —
    Python's `fold=0` default. The Worker matches this by preferring the larger
    candidate offset, which yields the same earlier instant; the golden case
    `1945-10-14 23:30 Asia/Kolkata` pins the agreement.
    """
    return local_naive.replace(tzinfo=resolve_tz(spec)).astimezone(UTC)
