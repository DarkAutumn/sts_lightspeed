"""Phase 9.x.5 regression: BattleContext::chooseNightmareCard.

NIGHTMARE is a Silent power: "Choose a card in your hand. Add 2 copies
of that card into your hand next turn." Cost 3, exhausts.

Prior to Phase 9.x.5 the C++ method was declared but never defined, so
the binding was missing and the gym dispatcher truncated the episode
when a CARD_SELECT screen with task=NIGHTMARE was reached.

These tests exercise the full path:
  - the binding exists and is callable;
  - playing NIGHTMARE opens a CARD_SELECT screen with task=NIGHTMARE(14);
  - calling choose_nightmare_card() resolves the screen;
  - after the next monster turn the player draws + receives 2 copies of
    the chosen card.
"""

from __future__ import annotations

import pytest

import slaythespire as sts


CARD_SELECT_TASK_NIGHTMARE = 14
INPUT_PLAYER_NORMAL = sts.InputState.PLAYER_NORMAL
INPUT_CARD_SELECT = sts.InputState.CARD_SELECT


def _build_silent_nightmare_gc() -> sts.GameContext:
    """Construct a Silent GameContext with a stripped-down deck of
    {NIGHTMARE, NEUTRALIZE x4} so the opening combat hand is
    deterministic AND so the post-NIGHTMARE assertion can strictly
    distinguish injected copies from natural-redraw copies.

    Setup rationale: deck has only 4 NEUTRALIZEs total. After the
    NIGHTMARE play + end-turn cycle, the 4 NEUTRALIZEs reshuffle and
    we draw at most 4 of them. NIGHTMARE injects 2 more on top, so a
    next-turn hand with > 4 NEUTRALIZEs proves the injection ran.
    Without the injection the hand would contain exactly 4.
    """
    gc = sts.GameContext(sts.CharacterClass.SILENT, 1, 0)

    # Strip Silent's starter deck (Strike x5, Defend x5, Survivor,
    # Neutralize) so we know exactly what gets drawn.
    while len(gc.deck) > 0:
        gc.remove_card(0)

    gc.obtain_card(sts.Card(sts.CardId.NIGHTMARE))
    for _ in range(4):
        gc.obtain_card(sts.Card(sts.CardId.NEUTRALIZE))
    return gc


def _find_card_in_hand(bc, target_id) -> int:
    for idx, c in enumerate(bc.cards.hand):
        if c.id == target_id:
            return idx
    return -1


def test_choose_nightmare_card_binding_exists():
    """The binding must be present after Phase 9.x.5."""
    bc = sts.BattleContext()
    assert hasattr(bc, "choose_nightmare_card"), (
        "Phase 9.x.5: choose_nightmare_card binding should be exposed"
    )


def test_nightmare_full_lifecycle():
    """Play NIGHTMARE, choose NEUTRALIZE, end turn, assert >4 copies of
    NEUTRALIZE in the next-turn hand (the deck only contains 4
    NEUTRALIZEs, so any count above 4 proves the injection ran)."""
    gc = _build_silent_nightmare_gc()
    bc = sts.BattleContext()
    # Use a single Cultist so the opening turn is survivable (Cultist
    # turn 1 = INCANTATION = ritual stack, no damage).
    bc.init(gc, sts.MonsterEncounter.CULTIST)

    nightmare_idx = _find_card_in_hand(bc, sts.CardId.NIGHTMARE)
    assert nightmare_idx >= 0, "NIGHTMARE should be in opening hand"

    # Silent starts with 3 energy; NIGHTMARE costs 3.
    assert bc.player.energy >= 3
    bc.play_card(nightmare_idx, 0)

    assert bc.input_state == INPUT_CARD_SELECT, (
        f"playing NIGHTMARE should open CARD_SELECT, got "
        f"input_state={bc.input_state}"
    )
    csi = bc.get_card_select_info()
    assert csi["task"] == CARD_SELECT_TASK_NIGHTMARE
    assert csi["pick_count"] == 1

    target_idx = _find_card_in_hand(bc, sts.CardId.NEUTRALIZE)
    assert target_idx >= 0, "expected NEUTRALIZE somewhere in hand"

    bc.choose_nightmare_card(target_idx)
    assert bc.input_state == INPUT_PLAYER_NORMAL, (
        f"after choose_nightmare_card, expected PLAYER_NORMAL, got "
        f"input_state={bc.input_state}"
    )

    bc.end_turn()

    # After end_turn(), monster turn resolves and the next player turn
    # starts. The deck only has 4 NEUTRALIZEs, so any count > 4 in the
    # new hand proves the NIGHTMARE injection ran on top of the natural
    # redraw.
    if bc.is_over:
        pytest.skip(
            "battle ended before NIGHTMARE injection observable"
        )

    neutralize_copies = sum(
        1 for c in bc.cards.hand if c.id == sts.CardId.NEUTRALIZE
    )
    assert neutralize_copies > 4, (
        f"NIGHTMARE should add 2 NEUTRALIZE copies on top of the "
        f"natural-redraw 4; expected >4, got {neutralize_copies}"
    )


def test_choose_nightmare_card_bounds_guard():
    """Out-of-range hand_idx should be a no-op, not a crash."""
    gc = _build_silent_nightmare_gc()
    bc = sts.BattleContext()
    bc.init(gc, sts.MonsterEncounter.CULTIST)

    nightmare_idx = _find_card_in_hand(bc, sts.CardId.NIGHTMARE)
    assert nightmare_idx >= 0
    bc.play_card(nightmare_idx, 0)
    assert bc.input_state == INPUT_CARD_SELECT

    # Negative and overrun indices must not crash.
    bc.choose_nightmare_card(-1)
    bc.choose_nightmare_card(99)
    assert bc.input_state == INPUT_CARD_SELECT, (
        "out-of-range hand_idx should be a no-op (still on CARD_SELECT)"
    )
