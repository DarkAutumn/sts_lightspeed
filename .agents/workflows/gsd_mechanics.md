---
description: Implement core mechanics for Defect, Silent, and Watcher
---

# GSD Workflow: Core Mechanics

This workflow covers the implementation of shared base mechanics required by the other 3 characters before their specific cards are added.

## Prerequisites

- [ ] Verify `Player.h` and `BattleContext.h` update for V2.3.4.

## Steps

1. **Orb System Details**: Update `Player` class and `BattleContext` to fully support channeling, evoking, and passive effects of the 4 Orb types (Lightning, Frost, Dark, Plasma).
2. **Stance System Details**: Expand `Stance` system logic to handle `Wrath`, `Calm`, and `Divinity`. Include stance entry/exit triggers (e.g. entering Calm gains no energy, but exiting Calm grants 2 energy).
3. **Status Effects**: Verify and add missing `PlayerStatusEffects.h` and `MonsterStatusEffects.h` for Poison, Focus, Mantra, Scry, Retain, Vigor.
4. **Compile & Test**: Build the project and ensure existing Ironclad simulation doesn't break due to overhead.
