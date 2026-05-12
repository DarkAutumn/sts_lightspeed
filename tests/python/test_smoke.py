"""Phase 2 smoke test: minimal imports + GameContext sanity.

These tests must keep passing through every later phase. They are the
absolute floor — if these break, nothing else works.
"""
from __future__ import annotations

import pytest


def test_module_imports():
    import sts_lightspeed as sts
    assert hasattr(sts, "GameContext")
    assert hasattr(sts, "BattleContext")
    assert hasattr(sts, "CharacterClass")
    assert hasattr(sts, "CardId")
    assert sts.__version__ == "0.2.0"


def test_compiled_module_directly():
    import slaythespire
    assert hasattr(slaythespire, "GameContext")


def test_character_enum_has_all_four():
    import sts_lightspeed as sts
    names = {c.name for c in sts.CharacterClass.__members__.values()} if hasattr(sts.CharacterClass, "__members__") else None
    # Older pybind enums don't expose __members__; fall back to dir().
    if names is None:
        names = {a for a in dir(sts.CharacterClass) if a.isupper()}
    expected = {"IRONCLAD", "SILENT", "DEFECT", "WATCHER"}
    assert expected.issubset(names), f"missing: {expected - names}"


def test_ironclad_starter_deck_has_10_cards():
    import sts_lightspeed as sts
    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 12345, 0)
    # Ironclad starter: 5 Strike, 4 Defend, 1 Bash, 1 AscendersBane(=11 only on A1)
    # On ascension 0 the deck is 10 cards.
    assert len(gc.deck) == 10, f"expected 10 starter cards, got {len(gc.deck)}"


def test_seed_helper_roundtrip():
    import sts_lightspeed as sts
    s = sts.get_seed_long("ABCDE")
    s2 = sts.get_seed_str(s)
    assert s2 == "ABCDE"
