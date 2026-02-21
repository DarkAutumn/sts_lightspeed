#!/usr/bin/env python3
"""Interactive sync mode for real-time game-simulator state comparison.

This script monitors the real Slay the Spire game (via CommunicationMod),
extracts actions, applies them to the simulator, and reports discrepancies
in real-time.

Usage:
    # Start the interactive sync (requires game already running)
    python interactive_sync.py

    # Start with specific seed
    python interactive_sync.py --seed 12345

    # Run in watch mode (just observe, don't replay to sim)
    python interactive_sync.py --watch

The workflow:
1. Connect to game via CommunicationMod
2. Read game state and extract seed
3. Initialize simulator with same seed
4. Watch for game state changes
5. Extract actions from state changes
6. Apply same actions to simulator
7. Compare states and report discrepancies
"""
import argparse
import json
import sys
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum

# Add paths for imports
_project_root = Path(__file__).parent.parent.parent
_integration_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_integration_dir))

from harness.game_controller import GameController, CommunicationModError
from harness.simulator_controller import SimulatorController
from harness.state_comparator import StateComparator, Discrepancy, DiscrepancySeverity
from harness.action_translator import ActionTranslator, TranslatedAction, ActionType


class SyncMode(Enum):
    """Sync operation modes."""
    FULL = "full"           # Full sync: replay all actions to simulator
    WATCH = "watch"         # Watch mode: only observe, don't replay
    VERIFY = "verify"       # Verify mode: compare states but don't replay


@dataclass
class SyncEvent:
    """Represents a sync event."""
    timestamp: str
    event_type: str
    data: Dict[str, Any]
    discrepancies: List[Discrepancy] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data,
            'discrepancies': [
                {
                    'field': d.field,
                    'game_value': d.game_value,
                    'sim_value': d.sim_value,
                    'severity': d.severity.value,
                    'message': d.message
                }
                for d in self.discrepancies
            ]
        }


class InteractiveSync:
    """Real-time synchronization between game and simulator.

    This class monitors the game for state changes, extracts actions,
    applies them to the simulator, and reports any discrepancies.
    """

    def __init__(
        self,
        state_dir: str = "/tmp/sts_bridge",
        mode: SyncMode = SyncMode.FULL,
        verbose: bool = False,
        alert_callback: Optional[Callable[[SyncEvent], None]] = None
    ):
        """Initialize the interactive sync.

        Args:
            state_dir: Directory for bridge communication.
            mode: Sync mode (FULL, WATCH, or VERIFY).
            verbose: Enable verbose output.
            alert_callback: Optional callback for discrepancy alerts.
        """
        self.state_dir = state_dir
        self.mode = mode
        self.verbose = verbose
        self.alert_callback = alert_callback

        self.game: Optional[GameController] = None
        self.sim: Optional[SimulatorController] = None
        self.comparator = StateComparator()
        self.translator = ActionTranslator()

        self._last_game_state: Optional[Dict[str, Any]] = None
        self._last_sim_state: Optional[Dict[str, Any]] = None
        self._last_action: Optional[str] = None
        self._synced = False
        self._running = False
        self._events: List[SyncEvent] = []

        # Stats
        self.stats = {
            'total_actions': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'critical_discrepancies': 0,
            'major_discrepancies': 0,
            'minor_discrepancies': 0,
        }

    def connect(self) -> bool:
        """Connect to the game via CommunicationMod.

        Returns:
            True if connection successful.
        """
        print("Connecting to CommunicationMod bridge...")
        self.game = GameController(state_dir=self.state_dir)

        try:
            self.game.connect()
            print("Connected to game successfully!")
            return True
        except CommunicationModError as e:
            print(f"Failed to connect: {e}")
            return False

    def initialize_simulator(self, seed: Optional[int] = None,
                            character: str = 'IRONCLAD',
                            ascension: int = 0) -> bool:
        """Initialize the simulator with the same seed as the game.

        Args:
            seed: Optional seed to use. If None, extracts from game.
            character: Character class.
            ascension: Ascension level.

        Returns:
            True if initialization successful.
        """
        if seed is None:
            # Extract seed from game
            if self.game is None:
                print("Error: Not connected to game")
                return False

            try:
                game_state = self.game.get_state()
                # Get seed from game state
                game_state_inner = game_state.get('game_state', game_state)
                raw_seed = game_state_inner.get('seed', 0)

                # Handle int64 conversion
                if raw_seed > 0x7FFFFFFFFFFFFFFF:
                    seed = raw_seed - 0x10000000000000000
                else:
                    seed = raw_seed

                # Get character from game if available
                char_str = game_state_inner.get('character', character)
                if char_str:
                    character = char_str.upper()

                print(f"Extracted from game: seed={seed}, character={character}")

            except Exception as e:
                print(f"Error extracting seed from game: {e}")
                return False

        try:
            self.sim = SimulatorController()
            self.sim.setup_game(seed, character, ascension)
            print(f"Simulator initialized: seed={seed}, character={character}, ascension={ascension}")
            self._synced = True
            return True
        except Exception as e:
            print(f"Failed to initialize simulator: {e}")
            return False

    def _log(self, message: str, level: str = "INFO"):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = f"[{timestamp}] [{level}]"
        print(f"{prefix} {message}")

    def _create_event(self, event_type: str, data: Dict[str, Any],
                     discrepancies: List[Discrepancy] = None) -> SyncEvent:
        """Create and store a sync event."""
        event = SyncEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            data=data,
            discrepancies=discrepancies or []
        )
        self._events.append(event)

        if self.alert_callback and event.discrepancies:
            self.alert_callback(event)

        return event

    def _detect_action_from_state_change(
        self,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any]
    ) -> Optional[str]:
        """Detect what action occurred based on state change.

        This is a heuristic approach to detect actions from state diffs.
        For more accurate detection, we would need access to CommunicationMod's
        command log or action history.

        Args:
            old_state: Previous game state.
            new_state: Current game state.

        Returns:
            Detected action string or None.
        """
        if old_state is None or new_state is None:
            return None

        old_combat = old_state.get('combat_state', {})
        new_combat = new_state.get('combat_state', {})

        # Check for turn change (end turn was pressed)
        old_turn = old_combat.get('turn', 0)
        new_turn = new_combat.get('turn', 0)
        if new_turn > old_turn:
            return "end"

        # Check for hand size decrease (card was played)
        old_hand = old_combat.get('hand', [])
        new_hand = new_combat.get('hand', [])
        if len(old_hand) > len(new_hand):
            # Try to identify which card was played
            # This is a simplified heuristic
            return "play"  # We don't know exact index

        # Check for screen state change
        old_screen = old_state.get('screen_state', old_state.get('room_phase', ''))
        new_screen = new_state.get('screen_state', new_state.get('room_phase', ''))
        if old_screen != new_screen:
            return "choose"  # Some choice was made

        # Check for HP changes in monsters (damage was dealt)
        old_monsters = old_combat.get('monsters', [])
        new_monsters = new_combat.get('monsters', [])
        if len(old_monsters) == len(new_monsters):
            for om, nm in zip(old_monsters, new_monsters):
                if om.get('cur_hp', 0) != nm.get('cur_hp', 0):
                    # Monster HP changed - likely a card was played
                    return "play"

        return None

    def _compare_and_report(self, game_state: Dict[str, Any],
                           sim_state: Dict[str, Any]) -> List[Discrepancy]:
        """Compare states and report discrepancies.

        Args:
            game_state: Current game state.
            sim_state: Current simulator state.

        Returns:
            List of discrepancies found.
        """
        result = self.comparator.compare(game_state, sim_state)

        if not result.match:
            # Update stats
            self.stats['critical_discrepancies'] += result.critical_count
            self.stats['major_discrepancies'] += result.major_count
            self.stats['minor_discrepancy'] += result.minor_count

            # Print discrepancy summary
            for disc in result.discrepancies:
                severity_str = disc.severity.value.upper()
                self._log(
                    f"Discrepancy [{severity_str}]: {disc.field} - "
                    f"game={disc.game_value}, sim={disc.sim_value}",
                    level=severity_str
                )

        return result.discrepancies

    def sync_step(self) -> Optional[SyncEvent]:
        """Perform a single sync step.

        Reads current game state, compares with simulator, and optionally
        replays actions.

        Returns:
            SyncEvent if something happened, None otherwise.
        """
        if self.game is None:
            return None

        try:
            # Get current game state
            game_state = self.game.get_state()

            # Check if state changed
            if self._last_game_state is not None:
                if game_state == self._last_game_state:
                    # No change
                    return None

            # State changed - process it
            self._log(f"State changed", level="DEBUG")

            # Detect action if possible
            detected_action = self._detect_action_from_state_change(
                self._last_game_state, game_state
            )

            # If we have a simulator and detected an action, replay it
            if self.sim and detected_action and self.mode == SyncMode.FULL:
                try:
                    # Translate and apply action
                    translated = self.translator.from_game_to_sim(detected_action)
                    if translated.sim_command:
                        self.sim.take_action(translated.sim_command)
                        self.stats['total_actions'] += 1
                        self._log(f"Applied to simulator: {translated.sim_command}")
                except Exception as e:
                    self._log(f"Error applying action to simulator: {e}", level="ERROR")

            # Compare states if we have both
            discrepancies = []
            if self.sim:
                sim_state = self.sim.get_state()
                discrepancies = self._compare_and_report(game_state, sim_state)
                self._last_sim_state = sim_state

            # Update last state
            self._last_game_state = game_state

            # Create event
            return self._create_event(
                event_type="state_change",
                data={
                    'detected_action': detected_action,
                    'game_screen': game_state.get('screen_state', 'unknown'),
                    'game_floor': game_state.get('floor', 0),
                },
                discrepancies=discrepancies
            )

        except Exception as e:
            self._log(f"Error in sync step: {e}", level="ERROR")
            return None

    def run(self, interval: float = 0.1, max_events: int = 10000):
        """Run the interactive sync loop.

        Args:
            interval: Polling interval in seconds.
            max_events: Maximum number of events to process before stopping.
        """
        if not self._synced and self.mode != SyncMode.WATCH:
            print("Warning: Simulator not synced. Running in watch mode.")
            self.mode = SyncMode.WATCH

        self._running = True
        print(f"\nStarting interactive sync (mode={self.mode.value})")
        print("Play the game normally. Press Ctrl+C to stop.\n")

        try:
            while self._running and len(self._events) < max_events:
                self.sync_step()
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nStopping interactive sync...")
        finally:
            self._running = False
            self._print_summary()

    def _print_summary(self):
        """Print a summary of the sync session."""
        print("\n" + "=" * 60)
        print("SYNC SESSION SUMMARY")
        print("=" * 60)
        print(f"Total events: {len(self._events)}")
        print(f"Total actions: {self.stats['total_actions']}")
        print(f"Successful syncs: {self.stats['successful_syncs']}")
        print(f"Failed syncs: {self.stats['failed_syncs']}")
        print(f"Critical discrepancies: {self.stats['critical_discrepancies']}")
        print(f"Major discrepancies: {self.stats['major_discrepancies']}")
        print(f"Minor discrepancies: {self.stats['minor_discrepancies']}")
        print("=" * 60)

    def stop(self):
        """Stop the sync loop."""
        self._running = False

    def get_events(self) -> List[SyncEvent]:
        """Get all recorded events."""
        return self._events

    def export_events(self, filepath: str):
        """Export events to JSON file.

        Args:
            filepath: Path to save the events.
        """
        data = {
            'summary': self.stats,
            'events': [e.to_dict() for e in self._events]
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Exported {len(self._events)} events to {filepath}")


def alert_handler(event: SyncEvent):
    """Default alert handler for discrepancies.

    This can be customized or replaced with more sophisticated alerts
    (desktop notifications, webhooks, etc.)
    """
    for disc in event.discrepancies:
        if disc.severity == DiscrepancySeverity.CRITICAL:
            print(f"\n{'!' * 60}")
            print(f"CRITICAL DISCREPANCY DETECTED!")
            print(f"Field: {disc.field}")
            print(f"Game: {disc.game_value}")
            print(f"Simulator: {disc.sim_value}")
            print(f"{'!' * 60}\n")


def main():
    """Main entry point for interactive sync."""
    parser = argparse.ArgumentParser(
        description="Interactive sync between Slay the Spire and simulator"
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Game seed (extracted from game if not specified)'
    )
    parser.add_argument(
        '--character',
        type=str,
        default='IRONCLAD',
        choices=['IRONCLAD', 'SILENT', 'DEFECT', 'WATCHER'],
        help='Character class'
    )
    parser.add_argument(
        '--ascension',
        type=int,
        default=0,
        help='Ascension level'
    )
    parser.add_argument(
        '--mode',
        type=str,
        default='full',
        choices=['full', 'watch', 'verify'],
        help='Sync mode: full (replay actions), watch (observe only), verify (compare only)'
    )
    parser.add_argument(
        '--state-dir',
        type=str,
        default='/tmp/sts_bridge',
        help='Bridge state directory'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=0.1,
        help='Polling interval in seconds'
    )
    parser.add_argument(
        '--export',
        type=str,
        default=None,
        help='Export events to JSON file on exit'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Create sync instance
    mode_map = {
        'full': SyncMode.FULL,
        'watch': SyncMode.WATCH,
        'verify': SyncMode.VERIFY,
    }

    sync = InteractiveSync(
        state_dir=args.state_dir,
        mode=mode_map[args.mode],
        verbose=args.verbose,
        alert_callback=alert_handler
    )

    # Connect to game
    if not sync.connect():
        print("Failed to connect to game. Make sure CommunicationMod is running.")
        return 1

    # Initialize simulator (unless in watch mode)
    if args.mode != 'watch':
        if not sync.initialize_simulator(
            seed=args.seed,
            character=args.character,
            ascension=args.ascension
        ):
            print("Failed to initialize simulator. Continuing in watch mode.")
            sync.mode = SyncMode.WATCH

    # Run sync loop
    sync.run(interval=args.interval)

    # Export if requested
    if args.export:
        sync.export_events(args.export)

    # Return exit code based on discrepancies
    if sync.stats['critical_discrepancies'] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
