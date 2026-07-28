"""Gates on the seeded advertising configuration.

The whole safety argument for Block 2A rests on one claim: **ads are off unless
a human turned them on**. That claim has exactly one place it can first be
broken — this seed file — and CI has no database, so this is where it gets
checked.

These tests are written to FALSIFY the claim rather than to describe the file.
Each one names a specific way the default could drift open, and fails on it:

  * a placement shipped enabled
  * the master switch shipped enabled
  * a placement present in the catalogue but absent from the seed (or the
    reverse — a placement seeded that no client knows about)
  * a cap, cooldown or warm-up that is negative, fractional or non-numeric
  * a rewarded unlock declared as anything other than session-scoped, which is
    Block 1's binding constraint (an unlock is not an entitlement)

A default that has never been seen to hold is not a proven default.
"""

from __future__ import annotations

import json

import pytest

from engine.content import AD_CONFIG_SEED_PATH

SEED = json.loads(AD_CONFIG_SEED_PATH.read_text())
PLACEMENTS: dict[str, dict] = SEED["placements"]

#: The catalogue, restated here rather than derived from the seed, so that this
#: file is an INDEPENDENT statement of what must exist. Deriving the expectation
#: from the thing under test would make the test pass for any seed at all —
#: including one with a placement quietly dropped.
EXPECTED: dict[str, str] = {
    "reports_unlock": "rewarded",
    "compat_detail_unlock": "rewarded",
    "muhurat_result_unlock": "rewarded",
    "dasha_detail_unlock": "rewarded",
    "calendar_list": "native",
    "timeline_list": "native",
    "placements_list": "native",
    "knowledge_list": "native",
    "deep_screen_bottom": "banner",
    "section_transition": "interstitial",
    "cold_start": "app_open",
}

NUMERIC_FIELDS = ("daily_cap", "cooldown_seconds", "min_sessions")


def test_seed_declares_its_own_version():
    assert SEED["version"] == AD_CONFIG_SEED_PATH.stem


def test_every_placement_ships_disabled():
    """THE gate. `is False`, not falsy — 0, '' and None must all fail here."""
    hot = [k for k, p in PLACEMENTS.items() if p.get("enabled") is not False]
    assert hot == [], (
        f"these placements ship ENABLED: {sorted(hot)}. Every placement seeds "
        "disabled so that no build can serve an ad before someone deliberately "
        "turns it on in the admin panel."
    )


def test_master_switch_ships_disabled():
    """Belt and braces: even if a placement leaked open, the master holds."""
    assert SEED["master"]["enabled"] is False, (
        "the master switch ships ENABLED. It is the one toggle that must be a "
        "deliberate act — it is the response to an AdMob policy flag."
    )


def test_the_catalogue_is_exactly_the_eleven_placements():
    assert set(PLACEMENTS) == set(EXPECTED), (
        f"seeded placements {sorted(PLACEMENTS)} != catalogue {sorted(EXPECTED)}"
    )


@pytest.mark.parametrize("key,fmt", sorted(EXPECTED.items()))
def test_each_placement_carries_its_declared_format(key, fmt):
    assert PLACEMENTS[key]["format"] == fmt


@pytest.mark.parametrize("key", sorted(EXPECTED))
@pytest.mark.parametrize("field", NUMERIC_FIELDS)
def test_numeric_fields_are_non_negative_integers(key, field):
    """`bool` is an `int` in Python, so it is excluded explicitly — otherwise
    `"daily_cap": true` would pass this check and reach the database as 1."""
    value = PLACEMENTS[key][field]
    assert isinstance(value, int) and not isinstance(value, bool), (
        f"{key}.{field} is {value!r}, which is not an integer"
    )
    assert value >= 0, f"{key}.{field} is negative"


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_every_placement_has_a_usable_starting_cap(key):
    """daily_cap 0 means SERVE NOTHING (aura-api/src/ads.ts enforces it), so a
    placement seeded at 0 would be a dead toggle: switched on in the panel,
    still serving nothing, with no error to explain why. The starting numbers
    are inert while disabled — they exist precisely so that enabling a
    placement is never the same as uncapping it."""
    assert PLACEMENTS[key]["daily_cap"] > 0, (
        f"{key} seeds daily_cap 0, which the Worker reads as 'serve nothing'. "
        "Enabling it in the panel would then do nothing and look like a bug."
    )


@pytest.mark.parametrize(
    "key", sorted(k for k, f in EXPECTED.items() if f == "rewarded")
)
def test_rewarded_unlocks_are_declared_session_scoped(key):
    """Block 1's binding constraint, carried in the config rather than left to
    a screen to remember: a rewarded unlock is SESSION-SCOPED. An unlock that
    persists is an entitlement, and PHASE_1.md removed the entitlement path at
    its call sites specifically so that no seam remains for one to reappear
    under another name."""
    assert PLACEMENTS[key]["params"]["unlock_scope"] == "session", (
        f"{key} does not declare unlock_scope 'session'. A persisted unlock is "
        "an entitlement — that is a product decision, not a config default."
    )


def test_about_records_the_disabled_posture():
    """The seed says what it is, so a reader of the file learns the rule without
    having to reconstruct it from eleven `false`s."""
    note = SEED["_about"]["note"].lower()
    assert "disabled" in note and "daily_cap 0" in SEED["_about"]["note"]
