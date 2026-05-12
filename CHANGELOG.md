# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Phase 6 — Full BattleContext Python bindings (jdc5549 port)

Brings the Python module from a thin wrapper around `Agent.playout`
(whole-run scripted by C++) to a complete in-process combat-driver API
suitable for RL gymnasium use. Adapted from the `jdc5549/sts_lightspeed`
fork, but extended to ben-w-smith's superset of `PlayerStatus` /
`CardId` enums so it works for all four characters.

#### Added
- **`sts_lightspeed.InputState` Python enum** mirroring the C++
  `InputState` enum (EXECUTING_ACTIONS, PLAYER_NORMAL, CARD_SELECT,
  CHOOSE_STANCE_ACTION, CHOOSE_DISCARD_CARDS, SCRY, INITIAL_SHUFFLE,
  …) so Python code can dispatch on `bc.input_state` symbolically.
- **`sts_lightspeed.BattleContext` Python class** with:
  - `init(gc)` and `init(gc, encounter)` overloads
  - `execute_actions()`, `resume_actions()`
  - `play_card(hand_idx, target_idx)`, `end_turn()`, `drink_potion(idx, target)`
  - `exit_battle()` for forcing combat termination
  - 14 `choose_*` card-select handlers covering all in-battle card
    selection screens (`choose_armaments`, `choose_discovery`,
    `choose_dual_wield`, `choose_exhaust_one`, `choose_exhume`,
    `choose_forethought`, `choose_headbutt`, `choose_recycle`,
    `choose_warcry`, `choose_discard_to_hand`, `choose_exhaust_many`,
    `choose_gamble`, `choose_codex`, `choose_draw_to_hand`)
  - state accessors: `input_state`, `outcome`, `is_battle_over`,
    `turn`, `ascension`, `floor_num`, `monster_turn_idx`,
    `encounter`, `player`, `monsters`, `cards`
  - **`get_state() -> dict`** returning a structured snapshot: player
    HP / energy / block / strength / dexterity / focus / artifact /
    stance / orb slots / relic bits, full status map (~90 keys
    spanning Ironclad / Silent / Defect / Watcher specific statuses),
    hand / draw / discard / exhaust piles, monster list with intent
    and damage, card-select screen state.
  - **`get_card_select_info()`** wrapping `bc.cardSelectInfo`
  - `get_monster_damage(idx)` and `get_monster_attack_count(idx)` for
    intent prediction.
  - **`clone_with_fresh_rng(seed, reshuffle_draw_pile=False)`**:
    deep-copies the BattleContext and reseeds the 6 RNG streams
    (`aiRng`, `cardRandomRng`, `miscRng`, `monsterHpRng`, `potionRng`,
    `shuffleRng`) from `seed`. Optional `reshuffle_draw_pile=True`
    re-randomises the draw order so search agents can explore the
    counterfactual "what if the next draw were different" branch.
  - RNG counter accessors: `cards_drawn`, `card_random_rng_counter`,
    `ai_rng_counter`, `misc_rng_counter`, `potion_rng_counter`,
    `shuffle_rng_counter` for sync-harness parity checks.
- **GIL release on every step-like binding**
  (`init`, `execute_actions`, `play_card`, `end_turn`, `drink_potion`,
  `exit_battle`, all `choose_*`, `clone_with_fresh_rng`). The Python
  module already declares `mod_gil_not_used()` from Phase 4, so distinct
  BattleContexts can now be driven concurrently from multiple Python
  threads on a free-threaded build.

#### Fixed
- **`ScreenStateInfo::encounter`**: was not default-initialized, so a
  freshly-constructed `GameContext` had `info.encounter` set to
  whatever bytes happened to be at that offset. After `Agent.playout`
  ran, that memory got reused and *new* `GameContext` instances would
  inherit the leftover encounter value, causing
  `BattleContext::init(gc)` (which uses `gc.info.encounter` by
  default) to spawn monsters when called outside a navigated combat.
  Now defaults to `MonsterEncounter::INVALID`.
- **`Player::cc` in `BattleContext::init`**: was never assigned from
  the source `GameContext`. Code paths that read `player.cc`
  (random card / potion generation, the new `get_state()` "character"
  field) saw uninitialised memory — they happened to land on
  `CharacterClass::IRONCLAD` for fresh processes, which masked the
  bug. Now `player.cc = gc.cc` is set explicitly during `init`.

#### Threading contract
- `BattleContext` is **single-owner** per Python thread. The module
  declares `mod_gil_not_used()` and every step-like binding releases
  the GIL, so distinct BC instances may be driven concurrently — but
  driving the **same** BC from two threads is undefined behavior (the
  step methods mutate non-atomic fields). This contract is documented
  on the class docstring and validated by the per-distinct-BC
  thread-safety test in `slaythespire-rl/tests/test_battle_context_bindings.py`.
  Adding an internal mutex was considered and rejected: it would
  defeat the purpose of the free-threaded build for the RL VectorEnv
  use case, where each environment owns exactly one BC.

#### Rubber-duck (GPT-5.5) addenda — Phase 6 pass 1
- **(fix in-scope)** All `choose_*` bindings now set
  `inputState = EXECUTING_ACTIONS` and call `executeActions()` after
  mutating selection state, matching `BattleSimulator::takeAction`'s
  pattern. Previously the binding returned with the BC stuck in
  CARD_SELECT and any queued follow-up actions (e.g. Discovery's draw,
  Armaments' card replacement) silently deferred.
- **(fix in-scope)** Added missing `choose_discard_cards`,
  `choose_scry_cards`, and `choose_setup_card` bindings. These
  `CardSelectTask` states are reachable from regular play (Malaise,
  Scry, Setup); without bindings Python could not progress the
  battle.
- **(fix in-scope)** Extended `get_state()["statuses"]` with the
  Watcher / Defect / misc statuses that jdc5549's original port
  omitted: `BLASPHEMY`, `DEVA_FORM`, `EXTRA_TURN`, `HEATSINKS`,
  `MACHINE_LEARNING`, `MENTAL_FORTRESS`, `NIRVANA`, `RUSHDOWN`,
  `SELF_REPAIR`, `SIMMERING_FURY`, `SPIRIT_SHIELD`, `STORM`,
  `STUDY`, `RETAIN_CARDS`.

#### Rubber-duck (GPT-5.5) addenda — Phase 6 pass 2
- **(fix in-scope)** `choose_discard_cards` binding now sorts indices
  descending before forwarding to `BattleContext::chooseDiscardCards`.
  The C++ method removes hand indices in caller order without
  shift-compensating, so a Python caller passing `[0, 1]` would have
  actually discarded original hand positions 0 and 2 (because removing
  position 0 shifts later cards down by one). The sibling
  `chooseExhaustCards` / `chooseGambleCards` already sort descending
  internally; this binding equalises the contract for the discard
  path without changing C++ semantics for other internal callers.

#### Rubber-duck (GPT-5.5) addenda — Phase 6 pass 3
- **(fix in-scope)** `choose_scry_cards` binding now sorts indices
  ascending before forwarding to `BattleContext::chooseScryCards`.
  The C++ method iterates the index list in reverse and removes at
  `drawPile.size() - 1 - drawIdx`. For ascending input that works
  correctly (largest drawIdx — i.e. deepest card in the visible Scry
  set — is removed first, so subsequent indices stay valid), but for
  unsorted input the first removal shifts the draw pile and the second
  removal hits the wrong card. Sorting ascending in the binding makes
  the Python API order-insensitive.

### Phase 5.5 — Crash fixes discovered during slaythespire-rl golden-seed bringup

These changes make `Agent.playout` complete cleanly on every (character,
seed) tuple in `slaythespire-rl/tests/parity/golden_seeds.json` (4
characters × seeds {1, 42, 1337, 9999, 2025}). Most were stub Actions
or missing dispatch entries left over from earlier merges. See
`slaythespire-rl/docs/KNOWN_ISSUES.md` for detail.

#### Fixed
- **`Actions::PoisonLoseHpAction`**: returned an empty `std::function`
  that crashed (`std::bad_function_call`) when popped from the action
  queue. Now takes a `monsterIdx`, applies poison damage via
  `Monster::damageUnblockedHelper`, and decrements POISON by 1.
  `Monster::applyStartOfTurnPowers` updated to pass `idx`.
- **`Actions::EssenceOfDarkness`**: stub replaced with a real
  implementation that channels `Orb::DARK` per orb slot.
- **`Actions::IncreaseOrbSlots`**: stub replaced with
  `Player::increaseOrbSlots(count)`.
- **`BattleScumSearcher2::enumerateCardSelectActions`**: added cases
  for `DISCARD`, `HOLOGRAM`, `MEDITATE`, `NIGHTMARE`, `RECYCLE`,
  `SETUP`, `SEEK`, and `SCRY`. Previously the default branch fired
  `assert(false)` whenever any Silent / Watcher card-select task
  reached the search agent.
- **`Action::isValidMultiCardSelectAction`**: added `SCRY` case that
  accepts any subset of draw-pile indices.
- **`Monster::addDebuff<MS::SHACKLED>`**: template specialization was
  missing; previously hit `assert(false)` in the default branch when
  Malaise / Piercing Wail (Silent) tried to shackle a monster. Fixed
  by both reducing the target's `strength` by `amount` AND recording
  `amount` in the dedicated `shackled` field; `applyEndOfTurnPowers`
  then restores the strength via `buff<STRENGTH>(shackled)`.
  Convention: `addDebuff<SHACKLED>` is the "apply the debuff"
  primitive (used by player cards through `debuffEnemy<>`, which still
  runs the artifact check first); `buff<SHACKLED>` is the
  recording-only primitive used by monster-internal effects like
  `SHIFTING` that manage the strength delta themselves.
- **`CardId::SHIV`**: was unimplemented in `useAttackCard`. Added a
  base case: 4/6 damage with `PS::ACCURACY` bonus.
- **`PS::FORESIGHT` start-of-turn handler**: previously set
  `InputState::SHUFFLE_DISCARD_TO_DRAW` but nothing transitioned out of
  that state. Now calls `Actions::EmptyDeckShuffle` directly.

#### Changed
- **Stance Potion** (`BattleContext::drinkPotion` case
  `Potion::STANCE_POTION`): previously transitioned to
  `InputState::CHOOSE_STANCE_ACTION`, which is unhandled by both the
  search agent and the Python bindings. Now auto-picks `Stance::CALM`
  via `Actions::ChangeStance(CALM)` so stance enter/exit hooks fire
  (CALM-exit energy, VIOLET_LOTUS, MENTAL_FORTRESS, DIVINITY,
  RUSHDOWN). This is a documented soft-degrade (see
  KNOWN_ISSUES.md); future work will extend the search-action enum to
  expose the stance choice.
- **Unimplemented-card branches** in `useAttackCard` / `useSkillCard` /
  `usePowerCard`: replaced `assert(false)` with
  `throw std::runtime_error(...)`. Calling an unimplemented card now
  raises a clean Python `RuntimeError` instead of aborting the
  process.
- **`ActionQueue::pushBack` / `pushFront`** (debug-only, behind
  `STS_ASSERTS`): now assert `a.actFunc` is non-empty. Catches future
  Action() default-construct mistakes at the push site rather than at
  the much-later pop site.

#### Build
- Added `/build_debug/` to `.gitignore` (used for `-O0 -g3
  -DSTS_ASSERTS=ON` lldb sessions during this phase).

### Added

#### Defect Character - Complete Card Implementation
- **49 Defect cards** fully implemented (all skills and powers)
- **Orb System enhancements**: AMPLIFY status for double/triple orb evokes
- **4 new status effects**: HEATSINKS, MACHINE_LEARNING, SELF_REPAIR, STORM

##### Defect Skills (37 cards)
- Basic Orb Cards: ZAP, DUALCAST, LEAP, COOLHEADED, DARKNESS, GLACIER
- Energy/Draw Cards: TURBO, DOUBLE_ENERGY, OVERCLOCK, SKIM, CHARGE_BATTERY
- Advanced Orb Cards: AMPLIFY, RECURSION, MULTI_CAST, TEMPEST, RAINBOW, CHAOS, FUSION
- Block/Utility Cards: AUTO_SHIELDS, BOOT_SEQUENCE, CHILL, CONSUME, EQUILIBRIUM, FORCE_FIELD, GENETIC_ALGORITHM, REINFORCED_BODY, REPROGRAM, STACK, STEAM_BARRIER, WHITE_NOISE
- Deck Manipulation Cards: AGGREGATE, COLLECT, FISSION, HOLOGRAM, REBOOT, RECYCLE

##### Defect Powers (12 cards)
- DEFRAGMENT, CAPACITOR, BIASED_COGNITION, CREATIVE_AI, ECHO_FORM
- ELECTRODYNAMICS, HEATSINKS, HELLO_WORLD, LOOP, MACHINE_LEARNING
- SELF_REPAIR, STATIC_DISCHARGE, STORM

### Changed

- `Player::evokeOrb()` enhanced to support AMPLIFY status for multi-evoke effects
- `PlayerStatusEffects.h` expanded with 4 new status effect enums

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
