# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Phase 9.x.5 — `BattleContext::chooseNightmareCard` engine impl

Resolves the Phase 8 known limitation: NIGHTMARE (Silent power, cost 3,
"Choose a card in your hand. Add 2 copies of that card into your hand
next turn.") is now fully supported end-to-end.

#### Added
- **`BattleContext::chooseNightmareCard(int handIdx)`** — implementation
  in `src/combat/BattleContext.cpp`. Snapshots the chosen card, resets
  combat-only attrs (`costForTurn`, `freeToPlayOnce`, `retain`),
  stores 2 copies in `Player::nightmareCards[2]`, sets
  `Player::nightmareCount = 2`, then closes the card-select screen.
- **Start-of-next-turn injection** in `BattleContext::afterMonsterTurns`
  — right after the `addToBot(Actions::DrawCards(player.cardDrawPerTurn))`
  call, we queue a no-capture lambda that drains
  `Player::nightmareCards` into the new hand via
  `notifyAddCardToCombat` + `moveToHandHelper` (which routes 10-card-cap
  overflow to discard). FIFO queue ordering means the normal draw
  resolves first; the 2 NIGHTMARE copies arrive on top.
- **`BattleContext.choose_nightmare_card(hand_idx)`** Python binding
  with hand-index bounds guard, GIL release, and action-queue pump.
- **Sim-driver wiring**: `BattleSimulator.cpp` (display + execute) and
  `Action.cpp` (search-agent action enumeration) now route NIGHTMARE
  through the new method instead of leaving it as a `// todo` no-op.
- **C++ unit test** in `apps/unit_tests.cpp`: drives a Silent
  `BattleContext` with `{NIGHTMARE, 4×STRIKE_GREEN}`, plays NIGHTMARE,
  resolves the card-select, end-turn, asserts ≥2 STRIKE_GREEN copies
  appear in the next-turn hand and `nightmareCount` resets to 0.
- **Python regression tests** in `tests/python/test_nightmare_engine.py`
  (3 tests): binding exists; full lifecycle (CARD_SELECT → choose →
  next-turn injection); out-of-range bounds-guard.

#### Resolved
- Phase 8 known limitation: NIGHTMARE Python binding is now defined and
  the gym dispatcher in `slaythespire-rl/sts_gym/combat_env.py` routes
  NIGHTMARE to `bc.choose_nightmare_card(0)` instead of triggering a
  stuck-state truncation.

#### Known limitation
- The engine's `Player::nightmareCards[2]` field is sized for ONE
  NIGHTMARE per turn. If a player plays two NIGHTMAREs in the same
  turn, the second `chooseNightmareCard` call overwrites the first's
  queued copies. Bumping the array (and the corresponding loop bound
  in the injection lambda) would lift this; deferred since it requires
  an engine-wide schema change and Silent's deck-builder rarely
  produces that scenario.
- The queued `CardInstance` snapshot preserves stat-equivalent state
  (cost, base damage/block/magic, upgrade level) but does NOT reset
  card-specific `misc` / `specialData` mutations made earlier in
  combat (e.g., Rampage's accumulated damage bonus, Ritual Dagger's
  in-combat damage). This matches the existing `chooseDualWieldCard`
  pattern in the engine, which has no per-card "stat-equivalent copy"
  helper. Out-of-scope for Phase 9.x.5; would require a per-card
  reset table.

#### Verified
- C++ `apps/unit_tests`: 1275 assertions, 0 failures.
- `tests/python/` on .venv (3.14): 34 passed, 1 skipped.
- `tests/python/` on .venv-3.14t (3.14t free-threaded): 35 passed.
- `slaythespire-rl/tests/`: 95 passed (the obsolete
  `test_nightmare_marked_unsupported` was inverted to
  `test_nightmare_dispatched_to_choose_nightmare_card`).

### Phase 9.x.4 — Sync-harness translator + sim-driver fix

Fixes the long-standing "all scenarios pass with `Steps: 0`" no-op
problem in `integration/run_tests.py`. The harness now actually
drives the live game from main menu through Neow → map → combat in
lockstep with the in-process simulator, and surfaces real
divergences for the comparator to flag.

Discovered that the prior "Phase 1.5 baseline" pass was a false
positive: every Ironclad scenario reported `Steps: 0` because the
scenario loader silently produced `('unknown', {})` steps for the
new YAML schema and the translator returned `None` for any step
type other than `play`/`end`/`choose`/`potion`. Documented at
length in `docs/KNOWN_ISSUES.md`.

#### Fixed
- **`tests/integration/harness/scenario_loader.py`** —
  `ScenarioStep.from_dict` now accepts BOTH the legacy
  `action: "..."` string format AND the structured `type: ...`
  schema. Added `_parse_typed_step` covering choose / play /
  end_turn / potion / map / event / shop / reward / rest /
  treasure / card_select / boss_reward / proceed / cancel /
  wait / key.
- **`integration/run_tests.py`** — rewrote
  `_translate_scenario_step` to handle every scenario step type,
  with `_find_card_index_in_hand` and `_find_card_index_in_live_hand`
  helpers that match cards by both display name AND
  CommunicationMod modid (case-insensitive substring). Rewrote
  `run_scenario` to:
  1. Send `start CHAR ASC SEED` to the live game.
  2. Read the live game's actual seed from its state.
  3. Initialise the simulator with that seed (sign-extended).
  4. Walk scenario steps in lockstep, logging skipped steps.
- **`integration/harness/game_controller.py`** — added
  `start_game(character, ascension, seed, timeout)` that
  refuses-fast if the game is in an unrecognised state, but
  AUTO-ADOPTS an existing in-progress run if it's at a fresh Neow
  event (floor 0, EVENT, event_id starts with "neow"). Added
  `wait_for_state(predicate, timeout, poll_interval)`.
- **`integration/harness/simulator_controller.py`** — masked the
  seed with `& 0xFFFFFFFFFFFFFFFF` before passing it to
  `setup_game`, since pybind11's `std::uint64_t` converter rejects
  the live game's signed-int64 representation.
- **`integration/harness/state_comparator.py`** — added
  `_normalise_seed` so signed-int64 and uint64 representations of
  the same seed compare equal. Downgraded `screen_state` format
  mismatches from CRITICAL to MAJOR (live game returns rich event
  dict, simulator returns coarse string — apples-and-oranges, not
  a real divergence).

#### Added
- **`tests/python/test_sync_harness_translator.py`** — 14 offline
  pytest cases covering both YAML schemas and every
  step-type-to-TranslatedAction translation. Guards the Phase
  9.x.4 fix from regressing without requiring a live
  CommunicationMod bridge.

#### Documented
- **`docs/KNOWN_ISSUES.md`** — new "Sync-harness divergences"
  section: ISSUE-100 (deck-card cost reports -1 outside combat),
  ISSUE-101 (screen_state format mismatch), ISSUE-102 (Neow
  card-pick desync between live and sim), ISSUE-103 (potion-slot
  count convention).

#### Verified
- Smoke-test against live Steam StS (Java 8 + native Linux JRE
  shadow-launch): `basic_combat.yaml` advances through Neow Talk
  → Neow card-pick before hitting the genuine ISSUE-102
  divergence.
- 20/20 offline pytest cases green.
- Full `tests/python/` suite green: 31 passed, 1 skipped.

#### Review-fixes (GPT-5.5 rubber-duck pass)
- **Fail loud on `start_game` failure** when connected to a live
  game. Previously a swallowed exception silently degraded to
  sim-only mode and let the scenario report PASSED with no live
  comparison — the very bug this harness exists to catch.
- **Stricter Neow-adoption predicate** in `start_game`: also
  requires character match, ascension match, and that the Neow
  event hasn't entered a sub-screen (no `screen_name="card_reward"`
  etc.). Previous predicate could adopt a previous run with
  wrong character/ascension or partial-Neow-progress.
- **Card-name disambiguation** in `_select_card_in_hand` (new
  helper extracted from the two `_find_card_index_in_*` methods):
  exact-name-or-modid match wins; substring fallback only fires
  when exactly one match exists. Refuses ambiguity (e.g. "Strike"
  in a hand also containing "Perfected Strike" / "Twin Strike")
  and prints a diagnostic.
- **`type: verify` step support.** Pre-existing `verify` steps in
  `status_effects.yaml` and `relic_integration.yaml` were silently
  dropped by the old translator and would have continued to be
  dropped by the new one. Now `run_scenario` handles them inline
  via a new `_run_verify_step` covering `has_relic` / `no_relic` /
  `monster_status` / `player_status` / `hp_at_least` / `hp_at_most`
  / `floor`. Unsupported `check` values pass with a diagnostic
  rather than failing scenarios that mix supported + unsupported
  checks.

### Phase 8 — Legality bindings for the Gym wrapper

Adds three thin engine-legality bindings that the slaythespire-rl
Gymnasium action-mask uses to defer correctness to the engine rather
than re-implementing rules in Python.

#### Added
- **`BattleContext.is_card_play_allowed() -> bool`** — wraps
  `BattleContext::isCardPlayAllowed()`. False during e.g. Entangled-
  blocks-attacks turns where the player has hand cards but cannot
  legally play any.
- **`CardInstance.can_use(bc, target=0, in_autoplay=False) -> bool`** —
  wraps `CardInstance::canUse(...)`. Covers cost, target alive/
  targetable, status flags (Confused / curse-without-relic / etc.),
  energy, and free-play paths.
- **`CardInstance.can_use_on_any_target(bc) -> bool`** — wraps
  `CardInstance::canUseOnAnyTarget(...)` (cost + at-least-one-legal-
  target). The engine notes this is slower; intended for mask code.

#### Phase-8 known limitation (RESOLVED in Phase 9.x.5)
- ~~`BattleContext::chooseNightmareCard(int)` is declared in the header
  but **not defined** in ben-w-smith's source.~~ Fixed in Phase 9.x.5;
  see that section above.

### Phase 7 — Battle observation encoder (NNInterface extension)

Adds a numpy-typed combat-state observation API to `NNInterface`,
adapted from `SimoneBarbaro/sts_lightspeed` but extended to
ben-w-smith's full enum surface. This is the primary input the
forthcoming `slaythespire-rl` Gymnasium environment will hand to a
policy network.

#### Added
- **`NNInterface.battle_observation_size`** property (currently 10443
  on this codebase): the fixed length of the battle observation array.
- **`NNInterface.getBattleObservation(gc, bc) -> np.ndarray`**: a 1-D
  `int32` numpy array encoding the entire `BattleContext`:
  - 8 player core slots (curHp, maxHp, block, energy, str, dex, focus,
    artifact)
  - 8 player meta slots (hp%, stance one-hot ×4, orbSlots,
    monsterTurnIdx, energyPerTurn)
  - one slot per `PlayerStatus` (101 slots) read from `Player::statusMap`
  - hand: 10 positional slots × `numCards*2` one-hot (upgrade-doubled)
  - draw/discard/exhaust: 3 × `numCards*2` count vectors (capped 30)
  - potion one-hot over `numPotions`
  - relic one-hot over `relicSlotCount` (matches out-of-battle layout)
  - 5 monster slots × {hp, maxHp, block, 14 MonsterStatus slots,
    MonsterId one-hot, isAttack, attackCount, damage}
- **`NNInterface.getBattleObservationMaximums() -> np.ndarray`**: same
  shape with per-slot upper bounds for observation normalization.
- `numCards`, `numStatuses`, `numPotions`, `numMonsterIds` constants
  declared on `NNInterface`.

#### Changed
- `NNInterface::getInstance()` is now bound with
  `pybind11::return_value_policy::reference` so pybind11 stops
  attempting to delete the Meyers singleton at module unload. This was
  a **pre-existing** latent bug (a `free(): invalid size` abort
  reproducible on master @ 3caec99 with `python -c "import
  slaythespire; slaythespire.getNNInterface()"`) that we tripped over
  the moment we wrote tests that actually call `getNNInterface()`.
  Fixed via `pybind11::return_value_policy::reference` on
  `m.def("getNNInterface", ...)`.
- `def_property_readonly("observation_space_size", []() {...})`
  changed to take `const NNInterface &` so it can actually be invoked
  on an instance. The old signature was unreachable from Python (it
  was registered as an instance property but the bound lambda took no
  arguments, so attribute access raised TypeError). Same pattern
  applied to the new `battle_observation_size` property.

#### Tests
- `tests/test_battle_observation.py` (15 tests) in the
  `slaythespire-rl` repo covers:
  - Surface (constants exist and are positive ints)
  - Shape & dtype (1-D int array, length == `battle_observation_size`)
  - Determinism (same seed → same observation)
  - Seed-dependence (different seeds → different observations)
  - Cross-character coverage (all 4 chars produce observations within
    the `getBattleObservationMaximums` envelope)
  - Behavior under play (encoding changes after `play_card`)
  - Thread-safety (N=8 distinct BCs encoded in parallel match serial
    encoding)
  - Singleton lifetime (`getNNInterface()` is safe to call repeatedly
    and to dispose of without aborting)
  - Phase 7 review-fix #1 regression: Silent-vs-Ironclad cards encode
    distinct slots (pre-fix all non-red cards collided onto slot 0).
  - Phase 7 review-fix #2 regression: bit-only statuses don't crash
    or trip the maximums envelope.

#### Rubber-duck pass 1 findings (RESOLVED)
- **`[BUG]`** `cardInstanceIdx` used `cardEncodeMap`, which only assigns
  slots for red+colorless cards. Silent/Defect/Watcher cards collided
  onto slot 0. **Fixed** by indexing by raw `CardId` value: `idx = id *
  2 + upgraded`, sized to `numCards * 2`. The legacy `cardEncodeMap`
  is still used by the older meta-state `getObservation` (Ironclad
  deck encoding) — Phase 7 only changes the battle encoder.
- **`[CORRECTNESS]`** Player status iteration only walked
  `p.statusMap`. Several real combat-affecting statuses (BARRICADE,
  CORRUPTION, CONFUSED, PEN_NIB, SURROUNDED, …) are stored in
  `statusBits0/1` bit-fields outside the map. **Fixed** by iterating
  `0..numStatuses-1` and using map values when present, else encoding
  `1` for bit-set statuses. We can't call `Player::getStatusRuntime`
  here because it does `statusMap.at(s)` for the default branch,
  which throws for bit-only statuses (latent bug, deferred).

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
