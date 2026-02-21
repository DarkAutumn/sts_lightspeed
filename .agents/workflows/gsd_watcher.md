---
description: Add The Watcher character, cards, and relics
---

# GSD Workflow: The Watcher Implementation

This workflow covers the addition of The Watcher to the sts_lightspeed engine.

## Prerequisites

- [ ] `gsd_mechanics.md` completed (Stances, Scry, Retain, Mantra supported).

## Steps

1. **Character Definition**: Expand `CharacterClasses.h` and initialize The Watcher's starting deck and HP in `Player.cpp`.
2. **Card Enums**: Add The Watcher's cards to `CardId` enum in `Cards.h`.
3. **Card Logic Implementation**: Implement card effects in `CardFactory` or `ActionQueue`. Pay special attention to:
   - Stance dancing (Eruption, Vigilance, Empty Fist)
   - Scry mechanics (Cut Through Fate, Third Eye)
   - Retain mechanics (Establishment, Meditate)
4. **Relics**: Add Watcher-specific relics (Pure Water, Violet Lotus, etc.) to `Relics.h`.
5. **Testing**: Run fixed simulations evaluating The Watcher's starting deck.
