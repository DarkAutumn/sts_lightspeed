# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.0.0] - 2026-02-21

### Added

#### Watcher Character
- **BLESSING card**: New 0-cost SKILL that grants 3(4) energy and exhausts (PURPLE, SPECIAL rarity)
- Watcher stance system: NEUTRAL, CALM, WRATH, DIVINITY with full transition effects
- Scry mechanic with `ScryAction` for draw pile manipulation
- Retain mechanic for end-of-turn card retention
- 20+ Watcher-specific status effects (MANTRA, MENTAL_FORTRESS, NIRVANA, RUSHDOWN, etc.)

#### Watcher Relics
- PURE_WATER: Start combat with a Miracle card in hand
- DAMARU: Gain 1 Mantra at the start of each turn
- ANCHOR: Start combat with 10 Block
- VAJRA: Start combat with 1 Strength
- VIOLET_LOTUS: Gain 1 energy when exiting Wrath to enter Calm
- HOLY_WATER: Watcher-specific potion that adds Miracles to hand

### Fixed

#### Card Implementations
- **PRAY**: Now correctly creates a BLESSING card and adds it to the draw pile (previously did nothing)
- **MEDITATE**: Now gains 3(4) Mantra and allows retrieving a card from discard pile to hand (previously only gained 1(2) Mantra)
- **RAGNAROK**: Now deals 5(7) damage 5(6) times to random enemies and adds 1 Smite to hand (previously dealt total damage split among enemies and added 3 Smite to draw pile)
- **FOREIGN_INFLUENCE**: Now uses Discovery mechanism for random attack selection (previously added fixed STRIKE_RED to draw pile)

### Changed

- `cardBaseDamage` array size increased from `[2][371]` to `[2][372]` to accommodate BLESSING card
- MEDITATE card selection handler implemented in BattleSimulator
- BLESSING card exposed in Python bindings

### Verified

- Mantra → Divinity auto-trigger at 10+ Mantra (working in BuffPlayer template)
- Stance transition effects (CALM exit energy, DIVINITY enter energy, MENTAL_FORTRESS block, RUSHDOWN draw)
- All Watcher relic effects at combat start and during play

---

## Historical Notes

### Character Implementation Order
1. Ironclad (base implementation)
2. Silent (expanded character mechanics)
3. Defect (orb system, focus mechanics)
4. Watcher (stance system, scry, retain)

### Key Systems
- **Card System**: 370+ cards across all characters
- **Combat System**: Full action queue, monster AI, status effects
- **Relic System**: 150+ relics with various triggers
- **Potion System**: All potions implemented
- **Map/Event System**: Full act progression

---

[Unreleased]: https://github.com/username/sts_lightspeed/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/username/sts_lightspeed/releases/tag/v1.0.0
