---
description: Add The Defect character, cards, and relics
---

# GSD Workflow: The Defect Implementation

This workflow covers the addition of The Defect to the sts_lightspeed engine.

## Prerequisites

- [ ] `gsd_mechanics.md` completed (Orbs and Focus supported).

## Steps

1. **Character Definition**: Expand `CharacterClasses.h` and initialize The Defect's starting deck and HP in `Player.cpp`.
2. **Card Enums**: Add The Defect's cards to `CardId` enum in `Cards.h`.
3. **Card Logic Implementation**: Implement card effects in `CardFactory` or `ActionQueue`. Pay special attention to:
   - Orb Channeling (Zap, Dualcast, Glacier)
   - Focus changing (Defragment, Biased Cognition)
   - Power generation (Creative AI, Hello World)
4. **Relics**: Add Defect-specific relics (Cracked Core, Inserter, etc.) to `Relics.h`.
5. **Testing**: Run fixed simulations evaluating The Defect's starting deck.
