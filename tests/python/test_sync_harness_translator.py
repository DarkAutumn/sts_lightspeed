"""Offline regression tests for the sync-harness translator.

These tests guard the Phase 9.x.4 fix by exercising the parts of the
sync harness that are pure-Python and don't need a live CommunicationMod
bridge:

* ``ScenarioLoader`` accepts both YAML schemas (legacy ``action: "..."``
  string and new ``type: ...`` structured form).
* ``_translate_scenario_step`` produces the expected ``TranslatedAction``
  for every supported step type (``choose``, ``map``, ``play``,
  ``end_turn``, ``potion``, ``wait``, ``proceed``, ``cancel``, ``key``).

Before Phase 9.x.4 every scenario silently translated to ``Steps: 0``
because the loader produced ``action_type='unknown'`` for the new YAML
schema and the translator returned ``None`` for any step type other
than ``choose``/``play``/``end_turn``/``potion``. Both gaps are
covered here.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Wire the integration package onto sys.path so we can import the
# harness modules without a CommunicationMod bridge being live.
#
# IMPORTANT: only add ``integration/`` so the modules are uniformly
# imported as ``harness.*`` and ``run_tests``. Adding ``_REPO_ROOT``
# would let the runner re-import ``integration.harness.action_translator``
# as a second module object, and the resulting two ``ActionType`` enum
# classes would not compare equal.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "integration"))

from harness.action_translator import ActionType, ActionTranslator  # noqa: E402

# ScenarioLoader lives under tests/integration/harness/. Add the
# tests/ directory so it imports as ``integration.harness.scenario_loader``
# matching the rest of the test suite's convention.
sys.path.insert(0, str(_REPO_ROOT / "tests"))
from integration.harness.scenario_loader import (  # noqa: E402
    ScenarioLoader,
    ScenarioStep,
)


# ---------------------------------------------------------------------------
# ScenarioLoader: both YAML schemas
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "scenario.yaml"
    p.write_text(textwrap.dedent(body))
    return p


def test_loader_parses_legacy_action_string_format(tmp_path):
    """The pre-Phase-9.x.4 YAML format used `action: "..."` strings."""
    path = _write(tmp_path, """
        name: "legacy"
        character: IRONCLAD
        ascension: 0
        steps:
          - action: "choose 0"
          - action: "play Strike 0"
          - action: "end"
    """)
    s = ScenarioLoader().load(str(path))
    assert [(st.action_type, st.params) for st in s.steps] == [
        ("choose", {"option": 0}),
        ("play", {"card": "Strike", "target": 0}),
        ("end", {}),
    ]


def test_loader_parses_new_typed_format(tmp_path):
    """The Phase-9.x.4-and-later YAML format uses `type: ...` blocks."""
    path = _write(tmp_path, """
        name: "modern"
        character: IRONCLAD
        ascension: 0
        steps:
          - type: choose
            option: 0
          - type: map
            node: 2
          - type: play
            card: "Strike"
            target: 0
          - type: end_turn
          - type: potion
            subaction: discard
            slot: 1
          - type: wait
            frames: 3
          - type: proceed
          - type: cancel
          - type: key
            value: CONFIRM
    """)
    s = ScenarioLoader().load(str(path))
    types = [st.action_type for st in s.steps]
    assert types == [
        "choose", "map", "play", "end_turn",
        "potion", "wait", "proceed", "cancel", "key",
    ]
    # Spot-check params on a few that previously silently dropped to
    # action_type='unknown'.
    assert s.steps[1].params == {"node": 2}
    assert s.steps[2].params == {"card": "Strike", "target": 0}
    assert s.steps[5].params == {"frames": 3}


def test_loader_aliases_event_shop_reward_to_choose(tmp_path):
    """`type: event/shop/reward/...` are aliases for `type: choose`."""
    path = _write(tmp_path, """
        name: "aliases"
        character: IRONCLAD
        ascension: 0
        steps:
          - type: event
            option: 1
          - type: shop
            option: 2
          - type: reward
            option: 0
          - type: rest
            option: 0
          - type: treasure
            option: 0
          - type: card_select
            option: 3
          - type: boss_reward
            option: 1
    """)
    s = ScenarioLoader().load(str(path))
    # All collapse to 'choose' so the translator (and downstream
    # comparators) treat them uniformly.
    for step in s.steps:
        assert step.action_type == "choose"
        assert isinstance(step.params.get("option"), int)


# ---------------------------------------------------------------------------
# Translator: shape of TranslatedAction per step type
# ---------------------------------------------------------------------------

class _StubGameController:
    """Minimal GameController stand-in: no bridge, no I/O."""

    def __init__(self, hand=None):
        self._hand = hand or []

    def get_hand(self):
        return list(self._hand)


class _StubSimulatorController:
    """Minimal SimulatorController stand-in: no slaythespire required."""

    def __init__(self, hand=None):
        self._hand = hand or []

    def get_state(self):
        return {"combat_state": {"hand": list(self._hand)}}


def _make_runner(monkeypatch, sim_hand=None, live_hand=None):
    """Build a TestRunner without touching the bridge or the C++ sim."""
    # Defer import until after sys.path is wired (test module top did
    # that already). Use the bare ``run_tests`` import — NOT
    # ``integration.run_tests`` — to share the same module object (and
    # therefore the same ActionType enum class) with the runner.
    from run_tests import TestRunner

    runner = TestRunner.__new__(TestRunner)
    runner.config = {}
    runner.project_name = "offline-test"
    runner.translator = ActionTranslator()
    runner.sim = _StubSimulatorController(sim_hand)
    runner.game = _StubGameController(live_hand)
    runner._current_result = None
    runner.comparator = None
    runner.reporter = None
    return runner


def _step(action_type: str, **params) -> ScenarioStep:
    return ScenarioStep(action_type=action_type, params=params)


def test_translator_choose(monkeypatch):
    r = _make_runner(monkeypatch)
    a = r._translate_scenario_step(_step("choose", option=2))
    assert a is not None
    assert a.action_type == ActionType.CHOOSE_OPTION
    assert a.game_command == "choose 2"
    assert a.sim_command == "2"


def test_translator_map(monkeypatch):
    r = _make_runner(monkeypatch)
    a = r._translate_scenario_step(_step("map", node=3))
    assert a is not None
    assert a.action_type == ActionType.MAP_MOVE
    assert a.game_command == "choose 3"
    assert a.sim_command == "3"


def test_translator_end_turn(monkeypatch):
    r = _make_runner(monkeypatch)
    for kind in ("end_turn", "end"):
        a = r._translate_scenario_step(_step(kind))
        assert a is not None
        assert a.action_type == ActionType.END_TURN
        assert a.game_command == "end"
        assert a.sim_command == "end"


def test_translator_play_match_in_sim_hand(monkeypatch):
    sim_hand = [
        {"id": "Defend_R", "name": "Defend"},
        {"id": "Strike_R", "name": "Strike"},
        {"id": "Bash", "name": "Bash"},
    ]
    r = _make_runner(monkeypatch, sim_hand=sim_hand)
    a = r._translate_scenario_step(_step("play", card="Strike", target=0))
    assert a is not None
    assert a.action_type == ActionType.PLAY_CARD
    assert a.game_command == "play 1 0"
    assert a.sim_command == "1 0"


def test_translator_play_falls_back_to_live_hand(monkeypatch):
    """If the sim's hand is empty, the translator must consult the
    live game's hand (so scenarios can run even when the sim hasn't
    yet been driven into combat)."""
    live_hand = [
        {"id": "Strike_R", "name": "Strike"},
        {"id": "Bash", "name": "Bash"},
    ]
    r = _make_runner(monkeypatch, sim_hand=[], live_hand=live_hand)
    a = r._translate_scenario_step(_step("play", card="Bash", target=0))
    assert a is not None
    assert a.game_command == "play 1 0"
    assert a.sim_command == "1 0"


def test_translator_play_returns_none_when_card_absent(monkeypatch):
    """A scenario asking us to play a card neither side knows about is a
    soft failure (translator returns None and the runner records a
    skipped step)."""
    r = _make_runner(monkeypatch, sim_hand=[{"id": "Strike_R", "name": "Strike"}])
    a = r._translate_scenario_step(_step("play", card="Nightmare", target=0))
    assert a is None


def test_translator_play_matches_modid(monkeypatch):
    """Card matching is case-insensitive substring against either the
    display name OR the CommunicationMod modid."""
    sim_hand = [{"id": "Strike_G", "name": "Strike"}]
    r = _make_runner(monkeypatch, sim_hand=sim_hand)
    a = r._translate_scenario_step(_step("play", card="strike_g", target=0))
    assert a is not None
    assert a.game_command == "play 0 0"


def test_translator_play_prefers_exact_match_over_substring(monkeypatch):
    """When 'Strike' matches both 'Strike' and 'Perfected Strike' as
    substrings, the exact match must win."""
    sim_hand = [
        {"id": "PerfectedStrike", "name": "Perfected Strike"},
        {"id": "Strike_R", "name": "Strike"},
        {"id": "TwinStrike", "name": "Twin Strike"},
    ]
    r = _make_runner(monkeypatch, sim_hand=sim_hand)
    a = r._translate_scenario_step(_step("play", card="Strike", target=0))
    assert a is not None
    # Index 1 is the exact "Strike", not 0 ("Perfected Strike") or
    # 2 ("Twin Strike").
    assert a.game_command == "play 1 0"


def test_translator_play_refuses_ambiguous_substring(monkeypatch, capsys):
    """If no exact match and multiple substring matches exist, the
    translator must REFUSE to guess (returns None)."""
    sim_hand = [
        {"id": "PerfectedStrike", "name": "Perfected Strike"},
        {"id": "TwinStrike", "name": "Twin Strike"},
        {"id": "ThunderStrike", "name": "Thunder Strike"},
    ]
    r = _make_runner(monkeypatch, sim_hand=sim_hand)
    a = r._translate_scenario_step(_step("play", card="Strike", target=0))
    assert a is None
    out = capsys.readouterr().out
    assert "ambiguous" in out


def test_translator_potion_use(monkeypatch):
    r = _make_runner(monkeypatch)
    a = r._translate_scenario_step(_step("potion", subaction="use", slot=1, target=0))
    assert a is not None
    assert a.action_type == ActionType.USE_POTION
    assert a.game_command == "potion use 1 0"
    assert a.sim_command == "drink 1 0"


def test_translator_potion_discard(monkeypatch):
    r = _make_runner(monkeypatch)
    a = r._translate_scenario_step(_step("potion", subaction="discard", slot=2))
    assert a is not None
    assert a.action_type == ActionType.DISCARD_POTION
    assert a.game_command == "potion discard 2"


def test_translator_wait_proceed_cancel_key(monkeypatch):
    r = _make_runner(monkeypatch)
    aw = r._translate_scenario_step(_step("wait", frames=5))
    assert aw is not None and aw.game_command == "wait 5" and aw.sim_command == ""

    ap = r._translate_scenario_step(_step("proceed"))
    assert ap is not None and ap.game_command == "proceed" and ap.sim_command == ""

    ac = r._translate_scenario_step(_step("cancel"))
    assert ac is not None and ac.game_command == "cancel" and ac.sim_command == ""

    ak = r._translate_scenario_step(_step("key", value="CONFIRM"))
    assert ak is not None and ak.game_command == "key CONFIRM"


def test_translator_unknown_returns_none(monkeypatch, capsys):
    """Unrecognised step types are a soft failure — None + diagnostic.

    This is the regression guard for the Phase 9.x.4 root cause:
    pre-fix every scenario step landed here (`action_type='unknown'`)
    and silently produced Steps:0.
    """
    r = _make_runner(monkeypatch)
    assert r._translate_scenario_step(_step("nosuchtype", foo=1)) is None
    out = capsys.readouterr().out
    assert "unknown step action_type='nosuchtype'" in out


# ---------------------------------------------------------------------------
# verify steps (handled by run_scenario, not the translator)
# ---------------------------------------------------------------------------

class _StubSimWithRelics:
    def __init__(self, relics):
        self._relics = relics

    def get_state(self):
        return {"relics": [{"name": r} for r in self._relics]}


def test_verify_has_relic(monkeypatch):
    r = _make_runner(monkeypatch)
    r.sim = _StubSimWithRelics(["Burning Blood"])
    ok, msg = r._run_verify_step({"check": "has_relic", "relic": "Burning Blood"})
    assert ok, msg


def test_verify_has_relic_missing(monkeypatch):
    r = _make_runner(monkeypatch)
    r.sim = _StubSimWithRelics([])
    ok, msg = r._run_verify_step({"check": "has_relic", "relic": "Burning Blood"})
    assert not ok and "absent" in msg


def test_verify_unknown_check_passes_with_diagnostic(monkeypatch):
    """Unknown verify checks PASS (don't fail the scenario) but include a
    diagnostic so partial check coverage doesn't block scenarios that mix
    supported and unsupported checks."""
    r = _make_runner(monkeypatch)
    r.sim = _StubSimWithRelics([])
    ok, msg = r._run_verify_step({"check": "weird_check", "value": 1})
    assert ok and "not yet implemented" in msg


def test_verify_no_check_field_fails(monkeypatch):
    r = _make_runner(monkeypatch)
    r.sim = _StubSimWithRelics([])
    ok, msg = r._run_verify_step({"value": 1})
    assert not ok and "missing" in msg
