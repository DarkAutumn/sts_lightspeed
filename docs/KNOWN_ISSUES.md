# Known Issues

This document tracks known bugs and limitations in the simulator that need investigation or fixes.

## Combat Bugs

### ISSUE-001: Dual Wield + Ritual Dagger Interaction
**Location:** `src/combat/BattleContext.cpp:4725`
**Severity:** Medium
**Status:** Open

**Description:**
When using Dual Wield on Ritual Dagger, the behavior is inconsistent:
- When there is no choice on which card to pick, the first one will change the card in the deck
- When there IS a choice on which card to pick, neither will change the card in the deck

**Expected Behavior:**
Dual Wield copies should consistently update the original card's stats when the copy is played.

**Notes:**
This may affect other cards with "on play" deck modifications.

---

### ISSUE-002: Exhume Card Selection Edge Case
**Location:** `src/combat/Actions.cpp:852`
**Severity:** Low
**Status:** Open

**Description:**
The Exhume action has a bug where the selected card cannot be Exhume itself. While this is intentional logic, there may be edge cases where the exhaust pile contains only Exhume cards or where the selection logic fails.

**Expected Behavior:**
Exhume should gracefully handle cases where no valid cards exist in the exhaust pile.

**Notes:**
Current workaround: Returns early if exhaust pile is empty or hand is full.

---

### ISSUE-003: Intangible Status vs Potion Damage
**Location:** `src/combat/Monster.cpp:477`
**Severity:** Low
**Status:** Open

**Description:**
The INTANGIBLE status check in `Monster::damage()` may not correctly handle potion damage. INTANGIBLE reduces all damage to 1, but potion damage mechanics might differ from the game.

**Expected Behavior:**
Verify that potion damage interacts with INTANGIBLE the same way as in the original game.

**Notes:**
Needs testing with Fire Potion, Explosion Potion, etc. against monsters with INTANGIBLE.

---

## Disabled Features

The following features are intentionally disabled pending implementation:

| Feature | Location | Constant |
|---------|----------|----------|
| Colosseum Event | `include/game/GameContext.h` | `disableColosseum` |
| Match and Keep | `include/game/GameContext.h` | `disableMatchAndKeep` |
| Prismatic Shard | `include/game/GameContext.h` | `disablePrismaticShard` |

---

## Build Issues

### Pre-existing Compilation Errors
Several pre-existing compilation errors exist in the codebase (not introduced by recent changes):

1. `BattleContext.cpp:2483` - `isEscaping` should be called as function
2. `BattleContext.cpp:2546` - `PS::EQUIV` doesn't exist (should be different status)
3. `BattleContext.cpp:2681` - `CardSelectInfo` constructor signature mismatch
4. `BattleContext.cpp:2682` - `InputState::SELECT_CARDS_HAND` doesn't exist
5. `BattleContext.cpp:2755` - `getCardFromPool` signature mismatch
6. `BattleContext.cpp:3253` - `PS::HEATSINK` should be `PS::HEATSINKS`

---

## Sync-harness divergences (Phase 9.x.4 baseline)

Filed during the Phase 9.x.4 harness fix. These are real, reproducible
divergences observed when running the live game (CommunicationMod /
Steam StS) and the in-process simulator side-by-side via
`integration/run_tests.py --scenario …`.

### ISSUE-100: Deck-card `cost` reports `-1` for cards outside combat
**Location:** `integration/harness/simulator_controller.py:_get_deck_state`
(reads `card.cost` via the slaythespire pybind11 bindings)
**Severity:** Medium
**Status:** Open
**First seen:** Phase 9.x.4 baseline run, scenario
`integration/scenarios/ironclad/basic_combat.yaml`, step 0

**Description:**
Every card in `gc.deck` reports `cost == -1` from the simulator's
binding, while the live game reports the actual base cost (Bash=2,
Defend=1, Strike=1). The harness comparator currently flags this as a
MAJOR `deck.<CARD>.costs` mismatch on every scenario.

**Expected:**
Base cost should match the live game's reported cost.

**Hypothesis:**
The `Card` value type used in `gc.deck` may not be initialised with a
cost when the card is sitting in the deck (cost is filled in by
`CardInstance` at combat-init time). Either the binding should fill it
in from the static card data, or the harness should read base cost
from a different field.

**Workaround until fixed:**
Comparator currently downgrades to MAJOR (not CRITICAL) so it does not
abort scenarios; the divergence is logged once per card in every
scenario.

---

### ISSUE-101: Live game's `screen_state` is a rich dict, sim's is a coarse string
**Location:** `integration/harness/simulator_controller.py:_get_state`
+ `state_comparator.py:_compare_fields`
**Severity:** Low
**Status:** Workaround in place

**Description:**
CommunicationMod returns `screen_state` as a nested dictionary with
event/screen-specific detail (event_id, body_text, options[],
choice_list, …). The simulator returns a single screen-name string
(`'reward'`, `'event'`, `'combat'`, …). They are never `==`-equal.

**Workaround in place:**
`_compare_fields` now special-cases `screen_state`: it downgrades any
mismatch to MAJOR (not CRITICAL) so scenarios are not aborted on
format-only divergence. Real per-screen verification is delegated to
the per-domain comparators (combat, deck, monsters, …).

**Future fix:**
Promote each side to a normalised representation:
`{'kind': 'event'|'reward'|'combat'|…, 'detail': {...}}`. Then re-enable
strict comparison.

---

### ISSUE-102: Neow card-pick advances live deck by 1, sim deck unchanged
**Location:** Sim's Neow handling vs CommunicationMod's
**Severity:** High (blocks lockstep past Neow until resolved)
**Status:** Open
**First seen:** `basic_combat.yaml` step 1

**Description:**
After the harness sends `choose 0` at the Neow card-reward sub-screen,
the live game's deck grows from 10 → 11 cards (the picked Neow card is
added to the deck). The simulator's deck stays at 10. This indicates
that the simulator is not surfacing the Neow card-pick sub-screen via
the same logical action sequence — likely the sim's `take_action("0")`
in its `'reward'` screen is selecting a different option than the live
game's `choose 0` in its Neow card-pick selection.

**Hypothesis:**
The sim's `setup_game` puts you immediately into a Neow-rewards-style
screen with a different action layout than CommunicationMod's
`Neow Event` → `[Talk]` → `Neow Event` → 4 reward options →
card-select sub-screen. The sequence of `choose <N>` indices does not
align.

**Workaround / next step:**
Phase 9.x.4 documents this as a known limitation. The proper fix is to
add a "sim-driver" component that, instead of blindly mirroring scenario
indices, observes the live game's screen sequence and drives the sim
through the equivalent logical actions. Tracked as a follow-up subtask
of Phase 9.x.4.

---

### ISSUE-103: Live game has 3 potion slots reported, sim has 0
**Location:** `simulator_controller.py:_get_potions_state`
**Severity:** Low
**Status:** Open

**Description:**
The live game reports 3 `Potion Slot` entries (empty slots), the sim
reports 0. `potions.count: game=3, sim=0` flagged as MINOR.

**Hypothesis:**
The sim's `_get_potions_state` filters out `INVALID` potions; live game
does not. They're both correct — just different conventions. Either
make the sim include empty slots or make the comparator subtract empty
slots from the live count before comparing.

---


## Coverage Gaps

See the project audit for detailed test coverage gaps:
- Characters: Only Ironclad (25%)
- Cards: ~2% tested
- Relics: 0% tested
- Events: 0% tested
- Ascension: 0% tested

---

*Last updated: 2026-05-12 (Phase 9.x.4 — added sync-harness divergence section)*
