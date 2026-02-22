#!/usr/bin/env python3
"""Interactive diff logger for sts_lightspeed.

Monitors real Slay the Spire game via CommunicationMod, syncs with simulator,
and logs all discrepancies with detailed reports.
"""
import json
import signal
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, TextIO

# Add paths for imports
_project_root = Path(__file__).parent.parent.parent
_integration_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_integration_dir))

from harness.game_controller import GameController, CommunicationModError
from harness.state_comparator import StateComparator, Discrepancy, DiscrepancySeverity, ComparisonResult
from harness.combat_journal import CombatJournal
from harness.discrepancy_reporter import DiscrepancyReporter, DiscrepancyRecord


@dataclass
class DiffEvent:
    """Represents a logged event during the session."""
    event_id: str
    timestamp: str
    event_type: str  # "state_change", "combat_action", "discrepancy", "session_start", "session_end"
    game_state_before: Optional[Dict[str, Any]] = None
    game_state_after: Optional[Dict[str, Any]] = None
    sim_state: Optional[Dict[str, Any]] = None
    discrepancies: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_jsonl(self) -> str:
        """Convert to JSON Lines format."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class SessionConfig:
    """Configuration for a logging session."""
    output_dir: Path
    session_id: str
    seed: int
    character: str
    ascension: int
    mode: str  # "full", "watch", "verify"
    interval: float
    verbose: bool
    state_dir: str = "/tmp/sts_bridge"

    def to_dict(self) -> dict:
        return {
            'output_dir': str(self.output_dir),
            'session_id': self.session_id,
            'seed': self.seed,
            'character': self.character,
            'ascension': self.ascension,
            'mode': self.mode,
            'interval': self.interval,
            'verbose': self.verbose,
            'state_dir': self.state_dir
        }


@dataclass
class SessionStats:
    """Statistics for a logging session."""
    start_time: str = ""
    end_time: str = ""
    total_events: int = 0
    total_actions: int = 0
    state_changes: int = 0
    critical_discrepancies: int = 0
    major_discrepancies: int = 0
    minor_discrepancies: int = 0
    combats_tracked: int = 0
    floors_visited: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class DiffLogger:
    """Main diff logger that coordinates game monitoring and discrepancy reporting.

    This class:
    - Connects to the real game via CommunicationMod
    - Initializes the simulator with the same seed
    - Monitors game state changes
    - Compares game and simulator states
    - Logs all discrepancies to files
    """

    def __init__(self, config: SessionConfig):
        """Initialize the diff logger.

        Args:
            config: Session configuration.
        """
        self.config = config
        self.stats = SessionStats()

        # Controllers (imported conditionally)
        self.game: Optional[GameController] = None
        self.sim = None  # SimulatorController
        self.comparator = StateComparator()
        self.combat_journal: Optional[CombatJournal] = None
        self.reporter: Optional[DiscrepancyReporter] = None

        # State tracking
        self._last_game_state: Optional[Dict[str, Any]] = None
        self._last_sim_state: Optional[Dict[str, Any]] = None
        self._in_combat: bool = False
        self._current_floor: int = 0
        self._action_history: List[Dict[str, Any]] = []

        # File handles
        self._events_file: Optional[TextIO] = None
        self._event_count = 0

        # Runtime state
        self._running = False
        self._initialized = False

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().isoformat()

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        self._event_count += 1
        return f"evt_{self._event_count:06d}_{uuid.uuid4().hex[:8]}"

    def _log(self, message: str, level: str = "INFO"):
        """Log a message to console."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = f"[{timestamp}] [{level}]"

        if self.config.verbose or level in ("WARNING", "ERROR", "CRITICAL"):
            print(f"{prefix} {message}")

    def _setup_session_directory(self):
        """Create the session output directory structure."""
        # Create main session directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.config.output_dir / "discrepancies").mkdir(exist_ok=True)

        # Write session config
        config_path = self.config.output_dir / "session_config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)

        # Create/update latest symlink
        results_dir = self.config.output_dir.parent
        latest_link = results_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(self.config.output_dir)

        self._log(f"Session directory: {self.config.output_dir}")

    def _open_events_file(self):
        """Open the events JSONL file for appending."""
        events_path = self.config.output_dir / "events.jsonl"
        self._events_file = open(events_path, 'a', encoding='utf-8')

    def _close_events_file(self):
        """Close the events file."""
        if self._events_file:
            self._events_file.close()
            self._events_file = None

    def _write_event(self, event: DiffEvent):
        """Write an event to the JSONL file."""
        if self._events_file:
            self._events_file.write(event.to_jsonl() + '\n')
            self._events_file.flush()

    def start(self) -> bool:
        """Start the logging session.

        Connects to the game, initializes the simulator,
        and sets up all logging components.

        Returns:
            True if startup successful, False otherwise.
        """
        self._log("Starting diff logger session...")

        # Setup directories
        self._setup_session_directory()

        # Open events file
        self._open_events_file()

        # Record session start
        self.stats.start_time = self._get_timestamp()
        start_event = DiffEvent(
            event_id=self._generate_event_id(),
            timestamp=self.stats.start_time,
            event_type="session_start",
            metadata={'config': self.config.to_dict()}
        )
        self._write_event(start_event)

        # Initialize combat journal
        combat_log_path = self.config.output_dir / "combat.log"
        self.combat_journal = CombatJournal(combat_log_path)

        # Initialize discrepancy reporter
        self.reporter = DiscrepancyReporter(
            self.config.output_dir / "discrepancies",
            self.config.to_dict()
        )

        # Connect to game
        self._log("Connecting to game...")
        try:
            self.game = GameController(
                state_dir=self.config.state_dir,
                project_name=f"diff_logger_{self.config.session_id}"
            )
            self.game.connect()
            self._log("Connected to game successfully")
        except CommunicationModError as e:
            self._log(f"Failed to connect to game: {e}", level="ERROR")
            return False

        # Get initial state
        try:
            initial_state = self.game.get_state()
            self._last_game_state = initial_state

            # Extract seed if not provided
            if self.config.seed == 0:
                raw_seed = initial_state.get('seed', 0)
                if raw_seed > 0x7FFFFFFFFFFFFFFF:
                    self.config.seed = raw_seed - 0x10000000000000000
                else:
                    self.config.seed = raw_seed
                self._log(f"Auto-detected seed: {self.config.seed}")

            # Extract character if not provided
            if self.config.character == "AUTO":
                self.config.character = initial_state.get('character', 'IRONCLAD').upper()
                self._log(f"Auto-detected character: {self.config.character}")

        except Exception as e:
            self._log(f"Error reading initial game state: {e}", level="ERROR")
            return False

        # Initialize simulator (unless in watch mode)
        if self.config.mode != "watch":
            self._log("Initializing simulator...")
            try:
                from harness.simulator_controller import SimulatorController
                self.sim = SimulatorController()
                self.sim.setup_game(
                    self.config.seed,
                    self.config.character,
                    self.config.ascension
                )
                self._log(f"Simulator initialized: seed={self.config.seed}, char={self.config.character}")
            except ImportError:
                self._log("Simulator not available, running in watch mode", level="WARNING")
                self.config.mode = "watch"
                self.sim = None
            except Exception as e:
                self._log(f"Failed to initialize simulator: {e}", level="WARNING")
                self.sim = None
                self.config.mode = "watch"

        self._initialized = True
        self._log("Session started successfully")
        return True

    def _process_state_change(self, new_state: Dict[str, Any]):
        """Process a game state change.

        Args:
            new_state: The new game state.
        """
        old_state = self._last_game_state

        # Create event
        event = DiffEvent(
            event_id=self._generate_event_id(),
            timestamp=self._get_timestamp(),
            event_type="state_change",
            game_state_before=old_state,
            game_state_after=new_state,
            metadata={
                'floor': new_state.get('floor', 0),
                'screen_state': new_state.get('screen_state', new_state.get('room_phase', 'unknown'))
            }
        )

        # Detect changes
        floor = new_state.get('floor', 0)
        if floor != self._current_floor:
            self._log(f"Floor changed: {self._current_floor} -> {floor}")
            self._current_floor = floor
            self.stats.floors_visited += 1
            event.metadata['floor_change'] = True

        # Check combat state
        in_combat = new_state.get('room_phase', '') == 'COMBAT'
        if in_combat and not self._in_combat:
            self._log("Combat started")
            self.stats.combats_tracked += 1
            if self.combat_journal:
                self.combat_journal.start_combat(new_state)
            event.metadata['combat_start'] = True
        elif not in_combat and self._in_combat:
            self._log("Combat ended")
            if self.combat_journal:
                self.combat_journal.end_combat(new_state, "victory")
            event.metadata['combat_end'] = True
        self._in_combat = in_combat

        # Update combat journal if in combat
        if in_combat and self.combat_journal:
            self._update_combat_journal(old_state, new_state)

        # Compare with simulator if available
        if self.sim and self.config.mode in ("full", "verify"):
            discrepancies = self._compare_states(new_state)
            if discrepancies:
                event.discrepancies = [
                    {
                        'field': d.field,
                        'game_value': d.game_value,
                        'sim_value': d.sim_value,
                        'severity': d.severity.value,
                        'message': d.message
                    }
                    for d in discrepancies
                ]

                # Update stats
                for d in discrepancies:
                    if d.severity == DiscrepancySeverity.CRITICAL:
                        self.stats.critical_discrepancies += 1
                    elif d.severity == DiscrepancySeverity.MAJOR:
                        self.stats.major_discrepancies += 1
                    else:
                        self.stats.minor_discrepancies += 1

                # Report discrepancies
                for d in discrepancies:
                    self._report_discrepancy(d, old_state, new_state)

        # Write event
        self._write_event(event)
        self.stats.state_changes += 1
        self._last_game_state = new_state

    def _update_combat_journal(self, old_state: Optional[Dict], new_state: Dict):
        """Update combat journal with state changes.

        Args:
            old_state: Previous game state.
            new_state: Current game state.
        """
        if not self.combat_journal:
            return

        old_combat = old_state.get('combat_state', {}) if old_state else {}
        new_combat = new_state.get('combat_state', {})

        # Detect turn changes
        old_turn = old_combat.get('turn', 0)
        new_turn = new_combat.get('turn', 0)

        if new_turn > old_turn:
            # New turn started
            if old_turn > 0:
                self.combat_journal.end_turn(old_state)
            self.combat_journal.start_turn(new_state)

        # Detect card plays (hand size decrease)
        old_hand = old_combat.get('hand', [])
        new_hand = new_combat.get('hand', [])

        if len(old_hand) > len(new_hand) and old_turn == new_turn:
            # Find which card was played
            old_cards = {c.get('id', c.get('name', '')) for c in old_hand}
            new_cards = {c.get('id', c.get('name', '')) for c in new_hand}
            played = old_cards - new_cards

            if played:
                # Find the card index
                for i, c in enumerate(old_hand):
                    if c.get('id', c.get('name', '')) in played:
                        self.combat_journal.record_card_play(
                            card_name=c.get('name', c.get('id', 'unknown')),
                            card_index=i,
                            target_index=-1,  # Unknown
                            energy_cost=c.get('cost', 0)
                        )
                        break

        # Update turn state
        self.combat_journal.update_turn_state(new_state)

    def _compare_states(self, game_state: Dict[str, Any]) -> List[Discrepancy]:
        """Compare game state with simulator state.

        Args:
            game_state: Current game state.

        Returns:
            List of discrepancies found.
        """
        if not self.sim:
            return []

        try:
            sim_state = self.sim.get_state()
            self._last_sim_state = sim_state

            result = self.comparator.compare(game_state, sim_state)

            if not result.match:
                for d in result.discrepancies:
                    self._log(
                        f"Discrepancy [{d.severity.value.upper()}]: {d.field} - "
                        f"game={d.game_value}, sim={d.sim_value}",
                        level=d.severity.value.upper()
                    )

            return result.discrepancies

        except Exception as e:
            self._log(f"Error comparing states: {e}", level="ERROR")
            return []

    def _report_discrepancy(
        self,
        discrepancy: Discrepancy,
        game_state_before: Optional[Dict],
        game_state_after: Dict
    ):
        """Report a discrepancy to the reporter.

        Args:
            discrepancy: The discrepancy to report.
            game_state_before: State before the change.
            game_state_after: State after the change.
        """
        if not self.reporter:
            return

        record = self.reporter.record(
            field=discrepancy.field,
            game_value=discrepancy.game_value,
            sim_value=discrepancy.sim_value,
            severity=discrepancy.severity.value,
            message=discrepancy.message,
            game_state_before=game_state_before,
            game_state_after=game_state_after,
            sim_state=self._last_sim_state,
            action_history=self._action_history[-50:]  # Last 50 actions
        )

        self._log(f"Discrepancy recorded: {record.record_id}")

    def run(self):
        """Run the main monitoring loop.

        Continuously polls the game for state changes and processes them.
        """
        if not self._initialized:
            self._log("Logger not initialized. Call start() first.", level="ERROR")
            return

        self._running = True
        self._log(f"\nStarting monitoring (mode={self.config.mode}, interval={self.config.interval}s)")
        self._log("Play the game normally. Press Ctrl+C to stop.\n")

        try:
            while self._running:
                self.sync_step()
                time.sleep(self.config.interval)

        except KeyboardInterrupt:
            self._log("\nStopping diff logger...")
        finally:
            self._running = False

    def sync_step(self) -> Optional[DiffEvent]:
        """Perform a single sync step.

        Reads current game state and processes any changes.

        Returns:
            DiffEvent if something happened, None otherwise.
        """
        if not self.game:
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
            self._process_state_change(game_state)
            self.stats.total_events += 1

        except Exception as e:
            self._log(f"Error in sync step: {e}", level="ERROR")

        return None

    def stop(self):
        """Stop the logging session and generate final reports."""
        self._log("Stopping session...")

        self._running = False

        # Record session end
        self.stats.end_time = self._get_timestamp()
        end_event = DiffEvent(
            event_id=self._generate_event_id(),
            timestamp=self.stats.end_time,
            event_type="session_end",
            metadata={'stats': self.stats.to_dict()}
        )
        self._write_event(end_event)

        # Close combat journal
        if self.combat_journal:
            self.combat_journal.close()

        # Generate session summary
        if self.reporter:
            summary = self.reporter.generate_session_summary(
                self.stats.to_dict(),
                self.stats.start_time,
                self.stats.end_time,
                self.config.to_dict()
            )
            summary_path = self.config.output_dir / "summary.md"
            with open(summary_path, 'w') as f:
                f.write(summary)

        # Close files
        self._close_events_file()

        # Disconnect from game
        if self.game:
            self.game.disconnect()

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print a summary of the session to console."""
        print("\n" + "=" * 60)
        print("DIFF LOGGER SESSION SUMMARY")
        print("=" * 60)
        print(f"Session ID: {self.config.session_id}")
        print(f"Duration: {self.stats.start_time} to {self.stats.end_time}")
        print(f"Mode: {self.config.mode}")
        print()
        print(f"Events logged: {self.stats.total_events}")
        print(f"State changes: {self.stats.state_changes}")
        print(f"Combats tracked: {self.stats.combats_tracked}")
        print(f"Floors visited: {self.stats.floors_visited}")
        print()
        print(f"Critical discrepancies: {self.stats.critical_discrepancies}")
        print(f"Major discrepancies: {self.stats.major_discrepancies}")
        print(f"Minor discrepancies: {self.stats.minor_discrepancies}")
        print()
        print(f"Output directory: {self.config.output_dir}")
        print("=" * 60)

    def get_stats(self) -> SessionStats:
        """Get current session statistics.

        Returns:
            Session stats.
        """
        return self.stats

    def has_critical_discrepancies(self) -> bool:
        """Check if any critical discrepancies were found.

        Returns:
            True if critical discrepancies exist.
        """
        return self.stats.critical_discrepancies > 0


def create_session_config(
    output_base_dir: str = "integration/results",
    seed: int = 0,
    character: str = "AUTO",
    ascension: int = 0,
    mode: str = "full",
    interval: float = 0.1,
    verbose: bool = False,
    state_dir: str = "/tmp/sts_bridge"
) -> SessionConfig:
    """Create a session configuration with auto-generated session ID.

    Args:
        output_base_dir: Base directory for session output.
        seed: Game seed (0 for auto-detect).
        character: Character class ("AUTO" for auto-detect).
        ascension: Ascension level.
        mode: Sync mode (full, watch, verify).
        interval: Polling interval in seconds.
        verbose: Enable verbose output.
        state_dir: Bridge state directory.

    Returns:
        SessionConfig instance.
    """
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_base_dir) / "sessions" / f"session_{session_id}"

    return SessionConfig(
        output_dir=output_dir,
        session_id=session_id,
        seed=seed,
        character=character,
        ascension=ascension,
        mode=mode,
        interval=interval,
        verbose=verbose,
        state_dir=state_dir
    )
