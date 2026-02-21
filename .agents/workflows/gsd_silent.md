---
description: Add The Silent character, cards, and relics
---

# GSD Workflow: The Silent Implementation

This workflow covers the addition of The Silent to the sts_lightspeed engine.

## Prerequisites

- [ ] `gsd_mechanics.md` completed (Poison, Shivs, Discard hooks supported).

## Steps

1. **Character Definition**: Expand `CharacterClasses.h` and initialize The Silent's starting deck and HP in `Player.cpp`.
2. **Card Enums**: Add The Silent's cards to `CardId` enum in `Cards.h`.
3. **Card Logic Implementation**: Implement card effects in `CardFactory` or `ActionQueue`. Pay special attention to:
   - Discard synergys (Tactician, Reflex)
   - Shiv generation (Blade Dance, Cloak and Dagger)
   - Poison application (Bouncing Flask, Catalyst)
4. **Relics**: Add Silent-specific relics (Ring of the Snake, Snecko Skull, etc.) to `Relics.h` and implement their hooks.
5. **Testing**: Run fixed simulations evaluating The Silent's starting deck.
