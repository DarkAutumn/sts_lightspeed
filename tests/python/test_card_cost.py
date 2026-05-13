"""ISSUE-100 regression: sts::Card must expose `.cost` from Python.

Pre-fix, the `Card` value type in `gc.deck` had no `cost` attribute and
the harness fell back to a `-1` stub for every deck card. The fix adds
a `cost` property on the Card binding that delegates to the engine's
static `getEnergyCost(id, upgraded)` lookup. This test guards against
regression.
"""
from __future__ import annotations

import pytest


def test_card_cost_attribute_exists():
    import sts_lightspeed as sts

    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 1, 0)
    assert len(gc.deck) > 0, "Ironclad starter deck is non-empty"
    for card in gc.deck:
        assert hasattr(card, "cost"), (
            "Card must expose `.cost` (ISSUE-100 regression: pre-fix the "
            "binding only exposed cost on CardInstance, not on Card)"
        )


@pytest.mark.parametrize(
    "cc",
    ["IRONCLAD", "SILENT", "DEFECT", "WATCHER"],
)
def test_starter_deck_cards_have_real_cost(cc: str):
    """The pre-fix stub was `card.cost = -1`; assert no deck card
    returns -1 (the engine never assigns -1 to a real card; -1 was
    the harness's `hasattr` fallback)."""
    import sts_lightspeed as sts

    char = getattr(sts.CharacterClass, cc)
    gc = sts.GameContext(char, 12345, 0)
    for card in gc.deck:
        assert card.cost != -1, (
            f"{cc} starter card cost is the -1 stub — binding regression"
        )


def test_ironclad_starter_costs():
    """Pin the Ironclad starter deck costs since they're well known:
    5x Strike (cost 1), 4x Defend (cost 1), 1x Bash (cost 2),
    1x Ascender's Bane (curse, unplayable). Total = 11 cards."""
    import sts_lightspeed as sts

    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 1, 0)
    by_id: dict[str, list[int]] = {}
    for card in gc.deck:
        by_id.setdefault(str(card.id), []).append(card.cost)

    # CardId enum repr varies; look up by the substring of the enum name.
    def find_costs(substring: str) -> list[int]:
        for key, costs in by_id.items():
            if substring in key:
                return costs
        return []

    bash_costs = find_costs("BASH")
    assert bash_costs == [2], f"Bash should be a single cost-2 card; got {bash_costs}"

    # Strikes — there should be 5, all cost 1
    strike_costs = find_costs("STRIKE_RED")
    assert strike_costs == [1] * 5, f"5x Strike cost 1; got {strike_costs}"

    # Defends — there should be 4, all cost 1
    defend_costs = find_costs("DEFEND_RED")
    assert defend_costs == [1] * 4, f"4x Defend cost 1; got {defend_costs}"


def test_upgraded_strike_still_cost_1():
    """Strike+ doesn't get a cost discount; it stays cost 1."""
    import sts_lightspeed as sts

    base = sts.Card(sts.CardId.STRIKE_RED)
    upgraded = sts.Card(sts.CardId.STRIKE_RED)
    upgraded.upgrade()
    assert base.cost == 1
    assert upgraded.cost == 1


def test_bash_upgrade_does_not_change_cost():
    """Bash+ keeps cost 2 — only some Ironclad cards get an upgrade
    discount (e.g. Searing Blow doesn't, Bash doesn't)."""
    import sts_lightspeed as sts

    base = sts.Card(sts.CardId.BASH)
    upgraded = sts.Card(sts.CardId.BASH)
    upgraded.upgrade()
    assert base.cost == 2
    assert upgraded.cost == 2
