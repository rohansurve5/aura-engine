"""Parse the AstroSage Vimshottari .docx into tests/golden/astrosage_dasha.json.

The document has four stacked tables; we capture the two that Prompt A scores
against:

* **maha + antar** — 10 maha blocks, each printing its start/end plus 9
  antar-dasha *end* dates (``00/00/00`` = ended before birth).
* **pratyantar** ("Sub-Sub Periods") — ``MAHA -- ANTAR`` blocks, each with 9
  pratyantar end dates. Marked experimental.

The 4th "Sookshama" (hour-precision) table is intentionally skipped.

Dates print as ``d/ m/yy`` with a 2-digit year. We resolve the century by
walking each section chronologically and keeping dates non-decreasing.

Run:  uv run python scripts/parse_golden.py
"""

from __future__ import annotations

import json
import os
import re
from datetime import date

import docx

HERE = os.path.dirname(__file__)
GOLDEN_DIR = os.path.join(HERE, os.pardir, "tests", "golden")
DOCX = os.path.join(GOLDEN_DIR, "Vimshottari_Dasha.docx")
OUT = os.path.join(GOLDEN_DIR, "astrosage_dasha.json")

BIRTH = date(1989, 9, 23)
NAME = {
    "KET": "Ketu", "VEN": "Venus", "SUN": "Sun", "MON": "Moon", "MAR": "Mars",
    "RAH": "Rahu", "JUP": "Jupiter", "SAT": "Saturn", "MER": "Mercury",
}

_MAHA_HDR = re.compile(r"^([A-Z]{3})\s*-\s*(\d+)\s*Years$")
_ANTAR_HDR = re.compile(r"^([A-Z]{3})\s*--\s*([A-Z]{3})$")
_DATE_ROW = re.compile(r"^([A-Z]{3})\s+(\d{1,2})/\s*(\d{1,2})/\s*(\d{1,2})")
_DATE_ONLY = re.compile(r"^(\d{1,2})/\s*(\d{1,2})/\s*(\d{1,2})")


def _resolve(day: int, month: int, yy: int, prev: date | None) -> date:
    """Pick the century for a 2-digit year that keeps the section monotonic."""
    candidates = sorted(
        date(base + yy, month, day) for base in (1900, 2000, 2100)
    )
    floor = prev or BIRTH
    for c in candidates:
        if c >= floor:
            return c
    return candidates[-1]


def _rows(paras: list[str]) -> list[str]:
    return [p.strip() for p in paras]


def parse() -> dict:
    paras = _rows([p.text for p in docx.Document(DOCX).paragraphs])

    balance = _parse_balance(paras)
    maha = _parse_maha(paras)
    prat = _parse_pratyantar(paras)
    return {
        "source": "AstroSage — Vimshottari Dasha.docx",
        "birth": {
            "date": BIRTH.isoformat(),
            "time": "04:47",
            "tz": "+05:30",
            "note": (
                "Birth place/coordinates were not provided. Vimshottari dasha "
                "depends only on the geocentric Moon longitude, which is "
                "location-independent, so the table is unaffected."
            ),
        },
        "balance": balance,
        "maha": maha,
        "pratyantar": prat,
    }


def _parse_balance(paras: list[str]) -> dict:
    for p in paras:
        m = re.search(r"Balance Of Dasha\s*:\s*([A-Z]+)\s+(\d+)\s*Y\s+(\d+)\s*M\s+(\d+)\s*D", p)
        if m:
            return {
                "lord": m.group(1).capitalize(),
                "years": int(m.group(2)),
                "months": int(m.group(3)),
                "days": int(m.group(4)),
            }
    # The balance also appears as prompt-known ground truth if not a paragraph.
    return {"lord": "Rahu", "years": 3, "months": 10, "days": 24}


def _date_at(paras: list[str], i: int, prev: date | None) -> tuple[date, int]:
    m = _DATE_ONLY.match(paras[i])
    d, mo, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return _resolve(d, mo, yy, prev), i + 1


def _antar_rows(paras: list[str], i: int, block_start: date) -> tuple[list[dict], int]:
    """Read up to 9 'LORD d/m/yy' rows; 00/00/00 -> elapsed (end=None)."""
    rows: list[dict] = []
    prev = block_start
    while i < len(paras) and len(rows) < 9:
        m = _DATE_ROW.match(paras[i])
        if not m:
            break
        lord, d, mo, yy = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if (d, mo, yy) == (0, 0, 0):
            rows.append({"lord": NAME[lord], "end": None})
        else:
            end = _resolve(d, mo, yy, prev)
            prev = end
            rows.append({"lord": NAME[lord], "end": end.isoformat()})
        i += 1
    return rows, i


def _parse_maha(paras: list[str]) -> list[dict]:
    out: list[dict] = []
    prev_end: date | None = None
    i = 0
    while i < len(paras):
        m = _MAHA_HDR.match(paras[i])
        if not m:
            i += 1
            continue
        lord = NAME[m.group(1)]
        # skip separator line, read start + end dates
        i += 1
        while i < len(paras) and not _DATE_ONLY.match(paras[i]):
            i += 1
        start, i = _date_at(paras, i, prev_end)
        end, i = _date_at(paras, i, start)
        prev_end = end
        while i < len(paras) and not _DATE_ROW.match(paras[i]):
            i += 1
        antar, i = _antar_rows(paras, i, start)
        out.append({
            "lord": lord,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "antar": antar,
        })
        # stop after section 1 (10 maha blocks before the pratyantar section)
        if len(out) >= 10:
            break
    return out


def _parse_pratyantar(paras: list[str]) -> list[dict]:
    out: list[dict] = []
    i = 0
    while i < len(paras):
        m = _ANTAR_HDR.match(paras[i])
        if not m:
            i += 1
            continue
        maha, antar = NAME[m.group(1)], NAME[m.group(2)]
        i += 1
        while i < len(paras) and not _DATE_ONLY.match(paras[i]):
            i += 1
        if i >= len(paras):
            break
        start, i = _date_at(paras, i, None)
        end, i = _date_at(paras, i, start)
        while i < len(paras) and not _DATE_ROW.match(paras[i]):
            i += 1
        periods, i = _antar_rows(paras, i, start)
        out.append({
            "maha": maha,
            "antar": antar,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "periods": periods,
        })
    return out


def main() -> None:
    data = parse()
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"wrote {OUT}")
    print(f"  balance: {data['balance']}")
    print(f"  maha blocks: {len(data['maha'])}")
    print(f"  pratyantar blocks: {len(data['pratyantar'])}")


if __name__ == "__main__":
    main()
