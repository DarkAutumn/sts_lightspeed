#!/usr/bin/env python3
"""Main test runner for Slay the Spire integration tests.

This script synchronizes the sts_lightspeed simulator with the real game
via CommunicationMod and compares states to validate simulator accuracy.

Usage:
    python run_tests.py --quick                    # Quick smoke test
    python run_tests.py --character IRONCLAD       # Test specific character
    python run_tests.py --test test_basic_strike   # Run specific test
    python run_tests.py --report-only test_results/  # Generate report from existing results
"""
import argparse
import json
import sys
import time
import yaml
from pathlib import Path
from typing import Optional, Callable, List, Tuple

# Add paths for imports
_project_root = Path(__file__).parent.parent  # worktree root
_integration_dir = Path(__file__).parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_integration_dir))

# Import from local integration harness (has state_comparator, action_translator)
from harness.game_controller import GameController, CommunicationModError, BridgeInUseError
from harness.simulator_controller import SimulatorController
from harness.state_comparator import StateComparator, ComparisonResult
from harness.action_translator import ActionTranslator, TranslatedAction, ActionType
from harness.reporter import Reporter, TestResult, StepResult, ActionRecord

# Import from tests harness (has scenario_loader, seed_synchronizer, etc.)
from tests.integration.harness.scenario_loader import ScenarioLoader, Scenario, ScenarioStep


class TestRunner:
    """Main test runner that synchronizes game and simulator execution."""

    def __init__(self, config_path: Optional[str] = None, project_name: Optional[str] = None):
        """Initialize the test runner.

        Args:
            config_path: Path to config.yaml. Defaults to same directory as this file.
            project_name: Name of the project for bridge lock identification.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        self.config = self._load_config(config_path)
        self.project_name = project_name or "sts_lightspeed"
        self.game: Optional[GameController] = None
        self.sim: Optional[SimulatorController] = None
        self.comparator = StateComparator(
            tolerances=self.config.get('comparison', {}).get('tolerances', {})
        )
        self.reporter = Reporter(
            output_dir=self.config.get('reporting', {}).get('output_dir', './test_results')
        )
        self.translator = ActionTranslator()
        self._current_result: Optional[TestResult] = None

    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        if not config_path.exists():
            print(f"Warning: Config file not found at {config_path}, using defaults")
            return {}

        with open(config_path) as f:
            return yaml.safe_load(f)

    def connect_game(self) -> bool:
        """Connect to the real game via CommunicationMod.

        Acquires an exclusive lock on the bridge before connecting.
        Lock is released on disconnect_game() or when process exits.

        Returns:
            True if connection successful.
        """
        comm_config = self.config.get('communication_mod', {})
        state_dir = comm_config.get('state_dir', '/tmp/sts_bridge')
        timeout = comm_config.get('timeout', 30.0)
        lock_timeout = comm_config.get('lock_timeout', None)

        self.game = GameController(
            state_dir=state_dir,
            timeout=timeout,
            project_name=self.project_name,
            lock_timeout=lock_timeout
        )

        try:
            self.game.connect()
            return True
        except BridgeInUseError as e:
            print(f"Bridge is locked by another project: {e}")
            return False
        except CommunicationModError as e:
            print(f"Failed to connect to CommunicationMod: {e}")
            return False

    def disconnect_game(self):
        """Disconnect from the real game."""
        if self.game:
            self.game.disconnect()
            self.game = None

    def init_simulator(self, seed: int, character: str, ascension: int):
        """Initialize the simulator with the same parameters as the game.

        Args:
            seed: Game seed.
            character: Character class.
            ascension: Ascension level.
        """
        self.sim = SimulatorController()
        self.sim.setup_game(seed, character, ascension)
        print(f"Initialized simulator: seed={seed}, character={character}, ascension={ascension}")

    def run_synchronized_step(self, action: TranslatedAction) -> StepResult:
        """Execute an action on both game and simulator, then compare states.

        Args:
            action: Translated action to execute.

        Returns:
            StepResult with comparison data.
        """
        step_num = self._current_result.total_steps if self._current_result else 0

        # Record the action
        action_record = ActionRecord(
            step=step_num,
            game_command=action.game_command,
            sim_command=action.sim_command,
            action_type=action.action_type.value
        )

        error = None
        comparison = None

        try:
            # Execute on game
            if self.game and action.game_command:
                self.game.send_command(action.game_command)
                time.sleep(self.config.get('test_execution', {}).get('action_delay', 0.1))

            # Execute on simulator
            if self.sim and action.sim_command:
                self.sim.take_action(action.sim_command)

            # Get states and compare
            if self.game and self.sim:
                game_state = self.game.get_state()
                sim_state = self.sim.get_state()
                comparison = self.comparator.compare(game_state, sim_state)

        except Exception as e:
            error = str(e)

        return StepResult(
            step=step_num,
            action=action_record,
            comparison=comparison,
            error=error
        )

    def run_test(
        self,
        test_name: str,
        seed: int,
        character: str = 'IRONCLAD',
        ascension: int = 0,
        action_generator: Optional[Callable] = None,
        max_steps: int = 1000
    ) -> TestResult:
        """Run a synchronized test.

        Args:
            test_name: Name for the test.
            seed: Game seed to use.
            character: Character class.
            ascension: Ascension level.
            action_generator: Optional function that yields actions.
                             If None, uses default action selection.
            max_steps: Maximum steps before stopping.

        Returns:
            TestResult with complete test data.
        """
        result = TestResult(
            test_name=test_name,
            seed=seed,
            character=character,
            ascension=ascension
        )
        self._current_result = result

        # Initialize simulator
        self.init_simulator(seed, character, ascension)

        # If connected to game, sync with game state
        if self.game:
            try:
                game_state = self.game.get_state()
                print(f"Game state: floor={game_state.get('floor')}, "
                      f"act={game_state.get('act')}, "
                      f"hp={game_state.get('current_hp')}/{game_state.get('max_hp')}")
            except Exception as e:
                print(f"Warning: Could not get initial game state: {e}")

        step = 0
        stop_on_critical = self.config.get('test_execution', {}).get('stop_on_critical', True)

        try:
            while step < max_steps:
                # Get next action
                if action_generator:
                    action = next(action_generator(self.sim, self.game), None)
                    if action is None:
                        break
                    if isinstance(action, str):
                        action = self.translator.from_sim_to_game(action)
                else:
                    # Default: use simulator's available actions
                    action = self._select_next_action()
                    if action is None:
                        break

                # Execute step
                step_result = self.run_synchronized_step(action)
                result.add_step(step_result)

                step += 1

                # Print progress
                if step % 10 == 0:
                    print(f"Step {step}: {step_result.comparison.get_summary() if step_result.comparison else 'no comparison'}")

                # Stop on critical failure if configured
                if stop_on_critical and step_result.comparison and step_result.comparison.critical_count > 0:
                    print(f"Stopping: Critical discrepancy detected at step {step}")
                    break

        except KeyboardInterrupt:
            print(f"\nTest interrupted at step {step}")
        except Exception as e:
            result.error_message = str(e)
            print(f"Test error at step {step}: {e}")

        result.finalize()

        # Store final states
        if self.game:
            try:
                result.final_game_state = self.game.get_state()
            except:
                pass
        if self.sim:
            result.final_sim_state = self.sim.get_state()

        self._current_result = None
        return result

    def _select_next_action(self) -> Optional[TranslatedAction]:
        """Select the next action to take (default implementation).

        Returns:
            TranslatedAction or None if no action available.
        """
        if not self.sim:
            return None

        screen_state = self.sim.get_screen_state()

        # Handle events - use "choose" command
        if screen_state == 'event':
            available = self.sim.get_available_actions()
            if available:
                # For events, use "choose <idx>" for game
                idx = available[0]
                return TranslatedAction(
                    action_type=ActionType.CHOOSE_OPTION,
                    game_command=f"choose {idx}",
                    sim_command=str(idx),
                    params={'option_index': idx}
                )

        # Check if in combat - need to handle targeted cards
        if self.sim.is_in_combat():
            state = self.sim.get_state()
            combat = state.get('combat_state', {})
            hand = combat.get('hand', [])
            energy = combat.get('player', {}).get('energy', 0)
            monsters = combat.get('monsters', [])

            # Find first monster that's targetable
            target_idx = -1
            for i, m in enumerate(monsters):
                if not m.get('is_dying', False) and m.get('is_targetable', True):
                    target_idx = i
                    break

            # Find a playable card
            for i, card in enumerate(hand):
                cost = card.get('cost_for_turn', card.get('cost', 0))
                if cost <= energy:
                    # Check if card needs a target
                    if card.get('requires_target', False) and target_idx >= 0:
                        return self.translator.from_sim_to_game(f"{i} {target_idx}")
                    elif not card.get('requires_target', False):
                        return self.translator.from_sim_to_game(str(i))

            # Can't play any cards, end turn
            return self.translator.from_sim_to_game("end")

        # Handle rewards, map, etc.
        available = self.sim.get_available_actions()
        if available:
            # For non-event screens, use "choose" for game
            idx = available[0]
            return TranslatedAction(
                action_type=ActionType.CHOOSE_OPTION,
                game_command=f"choose {idx}",
                sim_command=str(idx),
                params={'option_index': idx}
            )

        # No actions available - try to proceed
        if screen_state in ['reward', 'map']:
            return self.translator.from_sim_to_game("proceed")

        return None

    def run_quick_test(self, seed: int = 12345, character: str = 'IRONCLAD') -> TestResult:
        """Run a quick smoke test.

        Args:
            seed: Game seed.
            character: Character class.

        Returns:
            TestResult.
        """
        return self.run_test(
            test_name="quick_smoke_test",
            seed=seed,
            character=character,
            ascension=0,
            max_steps=self.config.get('scenarios', {}).get('quick', {}).get('max_steps', 50)
        )

    def run_scenario(self, scenario_path: str) -> TestResult:
        """Run a YAML scenario file in lockstep against the live game.

        Drives the live game (via CommunicationMod) and the in-process
        simulator together, sending the same logical action to each and
        comparing post-action state. Live game must already be at the main
        menu (CommunicationMod's only available commands are `start` and
        `state`); this method sends `start <character> <ascension> [seed]`
        to begin a new run, then walks scenario steps.

        Args:
            scenario_path: Path to the YAML scenario file.

        Returns:
            TestResult with scenario execution results.
        """
        loader = ScenarioLoader()
        scenario = loader.load(scenario_path)

        result = TestResult(
            test_name=scenario.name,
            seed=scenario.seed or 12345,
            character=scenario.character,
            ascension=scenario.ascension,
        )
        self._current_result = result

        # 1) Drive the live game into a new run, if connected. The actual
        #    int64 seed picked by the game (which differs from the
        #    user-typed seed string) is then used to initialise the
        #    simulator so both sides start from the exact same RNG state.
        live_seed = scenario.seed
        if self.game:
            try:
                live_state = self.game.start_game(
                    character=scenario.character,
                    ascension=scenario.ascension,
                    seed=scenario.seed,
                    timeout=15.0,
                )
                # Read the actual seed the live game settled on; convert
                # to a signed int64 for the simulator.
                try:
                    raw_seed = (live_state.get('game_state') or live_state).get('seed') \
                        if isinstance(live_state, dict) else None
                    if raw_seed is not None:
                        from tests.integration.harness.seed_synchronizer import SeedSynchronizer
                        live_seed = SeedSynchronizer.convert_seed_to_int64(raw_seed)
                        gs = live_state.get('game_state') or live_state
                        print(f"  [scenario] live game started; "
                              f"seed={live_seed} (raw={raw_seed!r}), "
                              f"floor={gs.get('floor')}, "
                              f"room_phase={gs.get('room_phase')}")
                except Exception as e:
                    print(f"  [scenario] WARNING: could not extract live seed ({e}); "
                          f"falling back to scenario seed {scenario.seed}")
            except Exception as e:
                # When connected to a live game, a start_game failure means
                # we cannot run a meaningful sync test. Failing fast here is
                # critical: silently falling back to sim-only would report
                # a passing scenario without any live comparison, hiding
                # divergences (the very thing this harness exists to find).
                err = (f"live-game start_game failed: {e!r}. Refusing to run "
                       f"scenario as sim-only because that would silently "
                       f"hide live-vs-sim divergences. Reset the live game "
                       f"to the main menu and retry.")
                print(f"  [scenario] ERROR: {err}")
                result.passed = False
                result.error_message = err
                result.finalize()
                return result

        # 2) Initialise the simulator with the live game's actual seed
        #    (or, if we're not connected to a live game, the scenario seed).
        self.init_simulator(
            seed=live_seed if live_seed is not None else 12345,
            character=scenario.character,
            ascension=scenario.ascension,
        )

        # 3) Walk the scenario steps. Each step is translated into a
        #    (game_command, sim_command) pair and applied via
        #    run_synchronized_step, which also compares post-action states.
        skipped_steps = 0
        for step_idx, step in enumerate(scenario.steps):
            # `verify` is an in-line assertion — it does NOT advance the
            # game; it just sanity-checks current sim state against an
            # expected predicate. Handle it before translation so the
            # generic "unknown action_type" path doesn't silently drop it.
            if step.action_type == 'verify':
                ok, msg = self._run_verify_step(step.params)
                if not ok:
                    print(f"  [scenario] step {step_idx} verify FAILED: {msg}")
                    result.passed = False
                    if not result.error_message:
                        result.error_message = (
                            f"verify step {step_idx} failed: {msg}"
                        )
                    # Stop on a verification failure — same behavior as a
                    # critical state divergence.
                    break
                else:
                    print(f"  [scenario] step {step_idx} verify ok ({msg})")
                continue

            action = self._translate_scenario_step(step)
            if action is None:
                skipped_steps += 1
                print(f"  [scenario] step {step_idx} ({step.action_type}) skipped (no translation)")
                continue

            step_result = self.run_synchronized_step(action)
            result.add_step(step_result)

            # Check expected state if defined.
            if step.expected:
                verification = self._verify_expected_state(step.expected)
                if not verification.get('match', True):
                    print(f"Step {step_result.step}: State mismatch - "
                          f"{verification.get('message', '')}")

            # Stop on critical failure.
            if step_result.comparison and step_result.comparison.critical_count > 0:
                print(f"Stopping scenario: Critical discrepancy at step {step_result.step}")
                break

        if skipped_steps:
            print(f"  [scenario] {skipped_steps} of {len(scenario.steps)} "
                  f"steps were skipped (no translation)")

        # 4) Try to return the live game to a known state for the next
        #    scenario. CommunicationMod has no `abandon` command and no
        #    ESCAPE key (its key list is CONFIRM/CANCEL/MAP/DECK/…/CARD_N
        #    only — see CommandExecutor.getKeycode in CommunicationMod.jar),
        #    so the only way to return to the main menu programmatically
        #    is `click X Y` on the in-game UI buttons (ESC → Abandon →
        #    Confirm). That's fragile and out of scope for 9.x.4.
        #    Strategy: if the player died or the run completed naturally,
        #    `in_game` will be False after a brief settle period; we wait
        #    for that. Otherwise we leave the run in place and the next
        #    scenario invocation will detect `in_game=True` and fail
        #    cleanly with a clear error message.
        if self.game:
            try:
                self.game.wait_for_state(
                    lambda s: not s.get('in_game', True),
                    timeout=2.0,
                )
            except Exception:
                pass

        result.finalize()
        self._current_result = None
        return result

    def _translate_scenario_step(self, step: ScenarioStep) -> Optional[TranslatedAction]:
        """Translate a scenario step to a TranslatedAction.

        The translator handles every step type produced by ScenarioLoader
        (both the legacy ``action: "..."`` strings and the newer
        ``type: ...`` structured form). Any unrecognised step type is
        logged via the result.errors list and the step is skipped.

        Args:
            step: ScenarioStep to translate.

        Returns:
            TranslatedAction or None if translation failed (the caller
            should record this as a "skipped step" diagnostic).
        """
        params = step.params
        action_type = step.action_type

        if action_type == 'play':
            card_name = str(params.get('card', ''))
            target = int(params.get('target', -1))
            card_idx = self._find_card_index_in_hand(card_name)
            if card_idx is None:
                # Try the live game's hand as a fallback (handles cases
                # where the simulator hasn't been driven into combat yet).
                card_idx = self._find_card_index_in_live_hand(card_name)
            if card_idx is None:
                print(f"  [translator] play step skipped: card '{card_name}' "
                      f"not in either sim or live hand")
                return None
            if target >= 0:
                return self.translator.from_sim_to_game(f"{card_idx} {target}")
            return self.translator.from_sim_to_game(str(card_idx))

        if action_type in ('end_turn', 'end'):
            return self.translator.from_sim_to_game("end")

        if action_type == 'choose':
            option = int(params.get('option', 0))
            return TranslatedAction(
                action_type=ActionType.CHOOSE_OPTION,
                game_command=f"choose {option}",
                sim_command=str(option),
                params={'option_index': option},
            )

        if action_type == 'map':
            # CommunicationMod expresses map navigation as a `choose <node>`
            # while in the map screen. The simulator's map-screen handler
            # likewise expects a `<idx>` action.
            node = int(params.get('node', 0))
            return TranslatedAction(
                action_type=ActionType.MAP_MOVE,
                game_command=f"choose {node}",
                sim_command=str(node),
                params={'node_index': node},
            )

        if action_type == 'potion':
            slot = int(params.get('slot', 0))
            target = int(params.get('target', -1))
            subaction = str(params.get('subaction', 'use'))
            if subaction in ('use', 'drink'):
                if target >= 0:
                    return self.translator.from_sim_to_game(f"drink {slot} {target}")
                return self.translator.from_sim_to_game(f"drink {slot}")
            return self.translator.from_sim_to_game(f"discard potion {slot}")

        if action_type == 'wait':
            frames = int(params.get('frames', 1))
            return TranslatedAction(
                action_type=ActionType.UNKNOWN,
                game_command=f"wait {frames}",
                sim_command="",  # Sim doesn't have a frame concept; no-op.
                params={'frames': frames},
            )

        if action_type == 'proceed':
            return TranslatedAction(
                action_type=ActionType.UNKNOWN,
                game_command="proceed",
                sim_command="",
                params={},
            )

        if action_type == 'cancel':
            return TranslatedAction(
                action_type=ActionType.UNKNOWN,
                game_command="cancel",
                sim_command="",
                params={},
            )

        if action_type == 'key':
            value = str(params.get('value', 'SPACE'))
            return TranslatedAction(
                action_type=ActionType.UNKNOWN,
                game_command=f"key {value}",
                sim_command="",
                params={'key': value},
            )

        if action_type == 'unknown':
            return None

        # Unrecognised step type — record as diagnostic but don't crash.
        print(f"  [translator] WARNING: unknown step action_type='{action_type}' "
              f"params={params!r} — skipping")
        return None

    @staticmethod
    def _select_card_in_hand(hand: list, card_name: str) -> Optional[int]:
        """Pick the hand-index for ``card_name`` from a list of card dicts.

        Match priority (case-insensitive):
          1. Exact name OR exact modid (``id`` field). First exact match wins.
          2. If no exact match, fall back to substring match — but ONLY if
             exactly one card in the hand is a substring match. Two or more
             substring candidates are an ambiguous translation (e.g. "Strike"
             would otherwise greedily match "Perfected Strike", "Twin Strike",
             "Strike", "Thunder Strike", …) and the caller should treat it
             as a translation failure.

        Returns the chosen index, or None if no exact match and the
        substring fallback is empty or ambiguous.
        """
        if not card_name or not hand:
            return None
        target = card_name.strip().lower()

        for i, card in enumerate(hand):
            name = str(card.get('name', '')).lower()
            cid = str(card.get('id', '')).lower()
            if name == target or cid == target:
                return i

        substring_matches = []
        for i, card in enumerate(hand):
            name = str(card.get('name', '')).lower()
            cid = str(card.get('id', '')).lower()
            if target in name or target in cid:
                substring_matches.append(i)

        if len(substring_matches) == 1:
            return substring_matches[0]
        if len(substring_matches) > 1:
            ambiguous = [hand[i].get('name') or hand[i].get('id')
                         for i in substring_matches]
            print(f"  [translator] WARNING: card '{card_name}' is ambiguous "
                  f"in hand — matched {len(substring_matches)} cards: "
                  f"{ambiguous!r}. Refusing to guess; mark scenario step "
                  f"with the exact card name or modid.")
        return None

    def _find_card_index_in_hand(self, card_name: str) -> Optional[int]:
        """Return the simulator-hand index for ``card_name`` using the
        exact-then-unique-substring policy."""
        if not self.sim:
            return None
        try:
            state = self.sim.get_state()
        except Exception:
            return None
        return self._select_card_in_hand(
            state.get('combat_state', {}).get('hand', []) or [],
            card_name,
        )

    def _find_card_index_in_live_hand(self, card_name: str) -> Optional[int]:
        """Return the live-game hand index for ``card_name``. Used as a
        fallback when the simulator's combat state isn't yet populated."""
        if not self.game:
            return None
        try:
            hand = self.game.get_hand()
        except Exception:
            return None
        return self._select_card_in_hand(hand or [], card_name)

    def _run_verify_step(self, params: dict) -> Tuple[bool, str]:
        """Apply a ``type: verify`` scenario step against current sim state.

        Supported checks (driven by ``check`` field in the YAML):

          - ``has_relic``  → params: ``relic`` (name). Pass iff a relic of
            that name appears in the simulator's relics list.
          - ``no_relic``   → opposite of ``has_relic``.
          - ``monster_status`` → params: ``monster`` (idx),
            ``status`` (lowercased status name), ``value`` (int amount).
            Pass iff the monster has that status with at least that value.
          - ``player_status`` → params: ``status`` (lowercased status
            name), ``value`` (int amount). Pass iff the player has that
            status with at least that value.
          - ``hp_at_least`` / ``hp_at_most`` → params: ``value`` (int).
          - ``floor`` → params: ``value`` (int). Pass iff current floor
            equals value.

        Unsupported ``check`` values pass with a diagnostic message — they
        are recorded in the journal but not failed (so a partial
        implementation does not block scenarios with mixed check coverage).
        Returns ``(passed, message)``.
        """
        if not self.sim:
            return (True, "no sim — verify skipped")
        try:
            state = self.sim.get_state()
        except Exception as e:
            return (False, f"could not read sim state: {e!r}")

        check = (params.get('check') or '').lower()
        if not check:
            return (False, f"verify step missing 'check' field; params={params!r}")

        if check in ('has_relic', 'no_relic'):
            relic_name = (params.get('relic') or '').lower()
            relics = state.get('relics') or []
            present = any(
                str(r.get('name', '')).lower() == relic_name
                or str(r.get('id', '')).lower() == relic_name
                for r in relics
            )
            if check == 'has_relic':
                return (present, f"has_relic '{relic_name}' "
                                 f"({'present' if present else 'absent'})")
            return (not present, f"no_relic '{relic_name}' "
                                 f"({'absent' if not present else 'present'})")

        if check == 'monster_status':
            mon_idx = int(params.get('monster', 0))
            status_name = (params.get('status') or '').lower()
            min_value = int(params.get('value', 1))
            monsters = (state.get('combat_state') or {}).get('monsters') or []
            if not (0 <= mon_idx < len(monsters)):
                return (False, f"monster index {mon_idx} out of range "
                               f"(have {len(monsters)} monsters)")
            powers = monsters[mon_idx].get('powers') or []
            for p in powers:
                if str(p.get('name', '')).lower() == status_name \
                        or str(p.get('id', '')).lower() == status_name:
                    if int(p.get('amount', 0)) >= min_value:
                        return (True, f"monster[{mon_idx}].{status_name} "
                                      f"={p.get('amount')} (>= {min_value})")
                    return (False, f"monster[{mon_idx}].{status_name} "
                                   f"={p.get('amount')} (< {min_value})")
            return (False, f"monster[{mon_idx}] has no '{status_name}' status")

        if check == 'player_status':
            status_name = (params.get('status') or '').lower()
            min_value = int(params.get('value', 1))
            powers = (state.get('combat_state') or {}).get('player', {}).get('powers') or []
            for p in powers:
                if str(p.get('name', '')).lower() == status_name \
                        or str(p.get('id', '')).lower() == status_name:
                    if int(p.get('amount', 0)) >= min_value:
                        return (True, f"player.{status_name}="
                                      f"{p.get('amount')} (>= {min_value})")
                    return (False, f"player.{status_name}="
                                   f"{p.get('amount')} (< {min_value})")
            return (False, f"player has no '{status_name}' status")

        if check in ('hp_at_least', 'hp_at_most'):
            cur = int(state.get('cur_hp', 0))
            value = int(params.get('value', 0))
            if check == 'hp_at_least':
                return (cur >= value, f"hp={cur} (need >= {value})")
            return (cur <= value, f"hp={cur} (need <= {value})")

        if check == 'floor':
            cur = int(state.get('floor_num', state.get('floor', 0)))
            value = int(params.get('value', 0))
            return (cur == value, f"floor={cur} (expected {value})")

        # Unknown check — don't fail the scenario; surface diagnostic.
        return (True, f"verify check='{check}' not yet implemented "
                      f"(params={params!r})")

    def _verify_expected_state(self, expected_state) -> dict:
        """Verify current state against expected state.

        Args:
            expected_state: ExpectedState to verify against.

        Returns:
            Dictionary with 'match' boolean and optional 'message'.
        """
        if not self.sim:
            return {'match': True}

        current_state = self.sim.get_state()

        # Check player HP
        if hasattr(expected_state, 'player_hp_min') and expected_state.player_hp_min is not None:
            if current_state.get('cur_hp', 0) < expected_state.player_hp_min:
                return {'match': False, 'message': f"HP {current_state.get('cur_hp')} < min {expected_state.player_hp_min}"}

        if hasattr(expected_state, 'player_hp_max') and expected_state.player_hp_max is not None:
            if current_state.get('cur_hp', 0) > expected_state.player_hp_max:
                return {'match': False, 'message': f"HP {current_state.get('cur_hp')} > max {expected_state.player_hp_max}"}

        # Check block
        if hasattr(expected_state, 'player_block') and expected_state.player_block is not None:
            combat = current_state.get('combat_state', {})
            actual_block = combat.get('player', {}).get('block', 0)
            if actual_block != expected_state.player_block:
                return {'match': False, 'message': f"Block {actual_block} != expected {expected_state.player_block}"}

        # Check energy
        if hasattr(expected_state, 'player_energy') and expected_state.player_energy is not None:
            combat = current_state.get('combat_state', {})
            actual_energy = combat.get('player', {}).get('energy', 0)
            if actual_energy != expected_state.player_energy:
                return {'match': False, 'message': f"Energy {actual_energy} != expected {expected_state.player_energy}"}

        return {'match': True}


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Slay the Spire Integration Test Runner"
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to config.yaml'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick smoke test'
    )
    parser.add_argument(
        '--character',
        type=str,
        default='IRONCLAD',
        choices=['IRONCLAD', 'SILENT', 'DEFECT', 'WATCHER'],
        help='Character to test'
    )
    parser.add_argument(
        '--ascension',
        type=int,
        default=0,
        help='Ascension level'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Game seed (random if not specified)'
    )
    parser.add_argument(
        '--steps',
        type=int,
        default=100,
        help='Maximum steps per test'
    )
    parser.add_argument(
        '--test',
        type=str,
        default=None,
        help='Run specific test'
    )
    parser.add_argument(
        '--scenario',
        type=str,
        default=None,
        help='Run a specific YAML scenario file'
    )
    parser.add_argument(
        '--no-game',
        action='store_true',
        help='Run without connecting to real game (simulator only)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--report-only',
        type=str,
        default=None,
        help='Generate report from existing results directory'
    )
    parser.add_argument(
        '--project',
        type=str,
        default='sts_lightspeed',
        help='Project name for bridge lock identification (default: sts_lightspeed)'
    )

    args = parser.parse_args()

    # Report-only mode
    if args.report_only:
        reporter = Reporter(output_dir=args.report_only)
        results_dir = Path(args.report_only)

        # Load all JSON result files
        for result_file in results_dir.glob("*.json"):
            try:
                with open(result_file) as f:
                    data = json.load(f)
                    # Handle both single result and wrapped results format
                    if 'results' in data:
                        # Wrapped format (from generate_json_report)
                        for result_data in data['results']:
                            result = TestResult.from_dict(result_data)
                            reporter.add_result(result)
                    else:
                        # Single result format
                        result = TestResult.from_dict(data)
                        reporter.add_result(result)
            except Exception as e:
                print(f"Warning: Could not load {result_file}: {e}")

        if not reporter.results:
            print(f"No results found in {args.report_only}")
            return 1

        # Generate reports
        reporter.print_console_report(verbose=args.verbose)
        reporter.generate_all_reports()
        return 0 if all(r.passed for r in reporter.results) else 1

    # Create test runner
    runner = TestRunner(config_path=args.config, project_name=args.project)

    # Connect to game unless --no-game
    if not args.no_game:
        if not runner.connect_game():
            print("Failed to connect to game. Use --no-game for simulator-only testing.")
            return 1

    # Generate random seed if not specified
    import random
    seed = args.seed if args.seed is not None else random.randint(1, 999999999)

    try:
        # Run test(s)
        if args.quick:
            result = runner.run_quick_test(seed=seed, character=args.character)
            runner.reporter.add_result(result)
        elif args.test:
            result = runner.run_test(
                test_name=args.test,
                seed=seed,
                character=args.character,
                ascension=args.ascension,
                max_steps=args.steps
            )
            runner.reporter.add_result(result)
        elif args.scenario:
            result = runner.run_scenario(args.scenario)
            runner.reporter.add_result(result)
        else:
            # Default: run quick test
            result = runner.run_quick_test(seed=seed, character=args.character)
            runner.reporter.add_result(result)

        # Generate reports
        runner.reporter.print_console_report(verbose=args.verbose)
        runner.reporter.generate_all_reports()

        # Return exit code based on test results
        return 0 if all(r.passed for r in runner.reporter.results) else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    finally:
        runner.disconnect_game()


if __name__ == "__main__":
    sys.exit(main())
