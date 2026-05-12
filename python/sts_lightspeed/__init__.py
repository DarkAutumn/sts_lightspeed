"""sts_lightspeed — Python API for the C++ Slay the Spire simulator.

This is a thin re-export wrapper around the compiled `slaythespire`
extension module so that downstream code can `import sts_lightspeed` and
get a stable, documented surface area.

# Surface area

## Stable (relied on by `slaythespire-rl`)

- ``sts_lightspeed.CharacterClass`` — enum of playable characters.
- ``sts_lightspeed.GameContext`` — top-level run state (overworld, deck,
  relics, gold). Construct with ``GameContext(character, seed, ascension)``.
- ``sts_lightspeed.BattleContext`` — combat state. Created from a
  ``GameContext`` plus an encounter.
- ``sts_lightspeed.Player`` / ``sts_lightspeed.Monster`` /
  ``sts_lightspeed.MonsterGroup`` — observable game objects.
- ``sts_lightspeed.CardId`` / ``sts_lightspeed.RelicId`` /
  ``sts_lightspeed.MonsterId`` — constant enums.
- ``sts_lightspeed.CardInstance`` / ``sts_lightspeed.CardManager``.
- ``sts_lightspeed.play_card(bc, hand_idx, target_idx)``,
  ``sts_lightspeed.potion(bc, action, slot, target)``.
- ``sts_lightspeed.SeedHelper`` (`get_seed_str`, `get_seed_long`).
- ``sts_lightspeed.NNInterface`` — observation encoder (412 floats).

## Unstable / internal (do not depend on)

- ``sts_lightspeed.ConsoleSimulator``
- ``sts_lightspeed.Agent`` (legacy ScumSearchAgent2 wrapper)
- ``sts_lightspeed.SpireMap``
- ``sts_lightspeed.play()`` (REPL)

The full set of `BattleContext` mutators (``choose_*``, ``end_turn``,
``drink_potion``, ``play_card``, ``clone_with_fresh_rng``, ``get_state``)
is added in Phase 6 by porting jdc5549's binding work.

# Versioning

This is `sts_lightspeed 0.2.0`. Backward-compat breaks will bump the
minor version until 1.0; until then **assume nothing is stable** beyond
what is exported from this `__init__.py`.
"""

from __future__ import annotations

# Re-export everything from the compiled extension.
from slaythespire import *  # noqa: F401,F403
import slaythespire as _ext  # noqa: F401

__all__ = [name for name in dir(_ext) if not name.startswith("_")]
__version__ = "0.2.0"
