"""Quality gate for db/seed/dasha_content_v1.json — the dasha content library.

Locks the structural contract (9 maha entries, all 81 ordered maha-antar pairs,
required fields, chip counts) and the voice hard-rules: no fatalism, no
fear-selling, no death/illness/divorce predictions. The wording itself is
subject to astrologer review; this test only guards the invariants that must
survive any rewording.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "db" / "seed" / "dasha_content_v1.json"

LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

# Vocabulary the voice rules ban outright: fatalism, fear-selling, and
# death/illness/divorce prediction. Matched as whole words, case-insensitive.
BANNED_WORDS = [
    "death",
    "die",
    "dying",
    "disease",
    "illness",
    "cancer",
    "divorce",
    "widow",
    "curse",
    "cursed",
    "doom",
    "doomed",
    "destroyed",
    "destruction",
    "ruin",
    "ruined",
    "disaster",
    "tragedy",
    "inauspicious",
    "malefic",
]
BANNED_RE = re.compile(r"\b(" + "|".join(BANNED_WORDS) + r")\b", re.IGNORECASE)


def _load() -> dict:
    return json.loads(SEED_PATH.read_text())


def _all_text(data: dict) -> list[tuple[str, str]]:
    """Every user-visible string in the library as (where, text) pairs."""
    out: list[tuple[str, str]] = []
    for lord, entry in data["maha"].items():
        out.append((f"maha/{lord}/title", entry["title"]))
        out.append((f"maha/{lord}/essence", entry["essence"]))
        for chip in entry["favours"]:
            out.append((f"maha/{lord}/favours", chip))
        for chip in entry["watch"]:
            out.append((f"maha/{lord}/watch", chip))
    for key, entry in data["maha_antar"].items():
        out.append((f"maha_antar/{key}/line", entry["line"]))
        out.append((f"maha_antar/{key}/now", entry["now"]))
    return out


def test_version() -> None:
    assert _load()["version"] == "dasha_content_v1"


def test_maha_entries_complete() -> None:
    maha = _load()["maha"]
    assert sorted(maha) == sorted(LORDS)
    for lord, entry in maha.items():
        assert set(entry) == {"title", "essence", "favours", "watch"}, lord
        # Title is a plain-language era name, never the bare planet name.
        assert entry["title"].strip() and entry["title"] != lord
        # Essence is 2-3 sentences of real substance.
        sentences = [s for s in re.split(r"[.!?]", entry["essence"]) if s.strip()]
        assert 2 <= len(sentences) <= 3, lord
        assert 3 <= len(entry["favours"]) <= 4, lord
        assert 2 <= len(entry["watch"]) <= 3, lord
        for chip in entry["favours"] + entry["watch"]:
            assert chip.strip()


def test_maha_antar_pairs_complete() -> None:
    pairs = _load()["maha_antar"]
    expected = {f"{m}-{a}" for m in LORDS for a in LORDS}
    assert set(pairs) == expected  # all 81 ordered pairs, incl. same-planet
    assert len(pairs) == 81
    for key, entry in pairs.items():
        assert set(entry) == {"line", "now"}, key
        assert entry["line"].strip(), key
        assert entry["now"].strip(), key


def test_no_banned_vocabulary() -> None:
    for where, text in _all_text(_load()):
        match = BANNED_RE.search(text)
        assert match is None, f"banned word {match.group(0)!r} in {where}: {text!r}"
