"""Interface to real Slay the Spire game via CommunicationMod.

This works with the communication_bridge.py script. Setup:

1. Configure CommunicationMod to run the bridge:
   command=python /path/to/tests/integration/harness/communication_bridge.py --state-dir /tmp/sts_bridge

2. The test runner connects to the bridge via files in the state directory.

Multi-Project Coordination:
    The controller acquires an exclusive lock on connect() to prevent
    multiple projects from using the bridge simultaneously. The lock
    is automatically released on disconnect() or when the process exits.

    from harness.game_controller import GameController

    # Lock is acquired on connect, released on disconnect
    with GameController(project_name="my_test") as game:
        state = game.get_state()  # Exclusive access guaranteed
"""
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from .bridge_lock import bridge_lock, get_lock_info, LockInfo, BridgeLockedError


class CommunicationModError(Exception):
    """Exception raised for CommunicationMod communication errors."""
    pass


class BridgeInUseError(CommunicationModError):
    """Raised when bridge is locked by another process."""
    def __init__(self, lock_info: Optional[LockInfo]):
        self.lock_info = lock_info
        if lock_info:
            message = (
                f"Bridge is locked by '{lock_info.project}' (PID {lock_info.pid})\n\n"
                f"Options:\n"
                f"  1. Wait for the current process to finish\n"
                f"  2. Kill the process: kill {lock_info.pid}\n"
                f"  3. Force remove lock: rm /tmp/sts_bridge/.coordinator/lock"
            )
        else:
            message = "Bridge is locked by another process"
        super().__init__(message)


class GameController:
    """Interface to real Slay the Spire via CommunicationMod bridge.

    The bridge script (communication_bridge.py) runs as a subprocess of
    CommunicationMod and communicates via files.
    """

    def __init__(
        self,
        state_dir: str = "/tmp/sts_bridge",
        config_path: Optional[str] = None,
        timeout: float = 30.0,
        project_name: Optional[str] = None,
        lock_timeout: Optional[float] = None
    ):
        """Initialize the game controller.

        Args:
            state_dir: Directory for bridge communication files.
            config_path: Ignored (kept for backwards compatibility).
            timeout: Timeout for waiting on game state/commands.
            project_name: Name of the project for lock identification.
                         If None, lock is only acquired on connect().
            lock_timeout: Maximum seconds to wait for lock (None = wait forever).
        """
        self.state_dir = Path(state_dir)
        self.timeout = timeout
        self.project_name = project_name or "unknown"
        self.lock_timeout = lock_timeout

        # Bridge communication files
        self.state_file = self.state_dir / 'game_state.json'
        self.command_file = self.state_dir / 'command.txt'
        self.ready_file = self.state_dir / 'bridge_ready.txt'

        self._connected = False
        self._last_state: Optional[Dict[str, Any]] = None
        self._lock_context = None
        self._lock_info: Optional[LockInfo] = None
        self._recording_name: Optional[str] = None

    def is_connected(self) -> bool:
        """Check if bridge is ready."""
        return self.ready_file.exists()

    def connect(self) -> bool:
        """Wait for bridge to be ready and acquire exclusive lock.

        The lock ensures only one project can use the bridge at a time.
        Lock is automatically released on disconnect() or process exit.

        Returns:
            True if connection successful.

        Raises:
            CommunicationModError: If bridge not ready within timeout.
            BridgeInUseError: If bridge is locked by another process.
            TimeoutError: If lock cannot be acquired within lock_timeout.
        """
        # First, acquire the lock to ensure exclusive access
        try:
            self._lock_context = bridge_lock(self.project_name, timeout=self.lock_timeout)
            self._lock_info = self._lock_context.__enter__()
            print(f"Acquired bridge lock for '{self.project_name}' (PID {self._lock_info.pid})")
        except TimeoutError as e:
            # Check who holds the lock
            info = get_lock_info()
            raise BridgeInUseError(info) from e

        print(f"Waiting for CommunicationMod bridge at {self.state_dir}...")

        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if self.ready_file.exists():
                self._connected = True
                print("Connected to CommunicationMod bridge")
                return True
            time.sleep(0.1)

        # Failed to connect - release lock
        self._release_lock()

        raise CommunicationModError(
            f"CommunicationMod bridge not ready after {self.timeout}s.\n"
            f"Expected bridge marker at: {self.ready_file}\n\n"
            f"To set up CommunicationMod:\n"
            f"1. Install ModTheSpire: https://github.com/kiooeht/ModTheSpire\n"
            f"2. Install CommunicationMod: https://github.com/ForgottenArbiter/CommunicationMod\n"
            f"3. Edit ~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties:\n"
            f"   command=python {Path(__file__).parent / 'communication_bridge.py'} --state-dir {self.state_dir}\n"
            f"4. Launch Slay the Spire through ModTheSpire\n"
        )

    def disconnect(self):
        """Disconnect from CommunicationMod bridge and release lock."""
        self._connected = False
        self._release_lock()

    def _release_lock(self):
        """Release the bridge lock if held."""
        if self._lock_context:
            try:
                self._lock_context.__exit__(None, None, None)
            except Exception:
                pass
            self._lock_context = None
            self._lock_info = None

    def get_lock_info(self) -> Optional[LockInfo]:
        """Get information about the current lock.

        Returns:
            LockInfo if this controller holds the lock, None otherwise.
        """
        return self._lock_info

    def _wait_for_state_update(self, timeout: Optional[float] = None) -> bool:
        """Wait for the state file to be updated by the bridge.

        Returns:
            True if state was updated, False on timeout.
        """
        if timeout is None:
            timeout = self.timeout

        # Get current modification time
        try:
            old_mtime = self.state_file.stat().st_mtime
        except FileNotFoundError:
            old_mtime = 0

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                new_mtime = self.state_file.stat().st_mtime
                if new_mtime > old_mtime:
                    return True
            except FileNotFoundError:
                pass
            time.sleep(0.05)

        return False

    def get_state(self) -> Dict[str, Any]:
        """Read current game state from bridge.

        Returns:
            Dictionary containing game state with nested game_state flattened.
        """
        if not self._connected:
            raise CommunicationModError("Not connected to CommunicationMod bridge")

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            self._last_state = state

            # Flatten the nested game_state for comparison with simulator
            # CommunicationMod returns: {"available_commands": [...], "game_state": {...}}
            # We want to merge game_state to top level for comparison
            if 'game_state' in state:
                flattened = state.copy()
                flattened.update(state['game_state'])
                return flattened
            return state
        except FileNotFoundError:
            raise CommunicationModError(
                f"State file not found: {self.state_file}\n"
                f"Ensure CommunicationMod is running with the bridge script."
            )
        except json.JSONDecodeError as e:
            raise CommunicationModError(f"Invalid state JSON: {e}")

    def send_command(self, command: str):
        """Send a command to CommunicationMod via the bridge.

        Args:
            command: Command string to send.
        """
        if not self._connected:
            raise CommunicationModError("Not connected to CommunicationMod bridge")

        # Write command to file for bridge to pick up
        with open(self.command_file, 'w') as f:
            f.write(command + '\n')

        # Wait a moment for command to be processed
        time.sleep(0.1)

    def get_seed(self) -> int:
        """Extract seed from game state with proper int64 conversion.

        Returns:
            Signed 64-bit integer seed value.
        """
        # Import here to avoid circular imports
        import sys
        from pathlib import Path
        tests_path = Path(__file__).parent.parent.parent / 'tests' / 'integration' / 'harness'
        if str(tests_path) not in sys.path:
            sys.path.insert(0, str(tests_path))
        from seed_synchronizer import SeedSynchronizer

        state = self.get_state()
        game_state = state.get('game_state', {})
        raw_seed = game_state.get('seed', 0)
        return SeedSynchronizer.convert_seed_to_int64(raw_seed)

    def start_recording(self, name: str, description: str = "") -> None:
        """Start recording gameplay.

        The recording captures game states as they are received from
        CommunicationMod. Call stop_recording() to save the recording.

        Args:
            name: Name for this recording (used as filename).
            description: Optional description of the recording.
        """
        cmd = f"record {name}"
        if description:
            cmd += f" {description}"
        self.send_command(cmd)
        self._recording_name = name

    def stop_recording(self) -> Optional[str]:
        """Stop recording and return recording name.

        Returns:
            Name of the recording that was stopped, or None if not recording.
        """
        if self._recording_name:
            self.send_command("stop_record")
            name = self._recording_name
            self._recording_name = None
            return name
        return None

    def is_recording(self) -> bool:
        """Check if currently recording.

        Returns:
            True if recording is active.
        """
        return self._recording_name is not None

    def get_combat_state(self) -> Optional[Dict[str, Any]]:
        """Get current combat state if in combat.

        Returns:
            Combat state dictionary or None if not in combat.
        """
        state = self.get_state()
        game_state = state.get('game_state', {})
        return game_state.get('combat_state')

    def play_card(self, card_index: int, target_index: int = -1):
        """Send 'play <idx> [target]' command.

        Args:
            card_index: Index of card in hand to play.
            target_index: Target monster index (-1 for auto-target/untargeted).
        """
        if target_index >= 0:
            command = f"play {card_index} {target_index}"
        else:
            command = f"play {card_index}"
        self.send_command(command)

    def end_turn(self):
        """Send 'end' command to end current turn."""
        self.send_command("end")

    def start_game(self, character: str, ascension: int = 0,
                   seed: Optional[int] = None,
                   timeout: float = 10.0) -> Dict[str, Any]:
        """Start a new run on the live game.

        CommunicationMod's `start <className> <ascensionLevel> [seed]`
        command leaves the game in the Neow event with available_commands
        of `[choose, key, click, wait, state]`.

        Args:
            character: Character class name as accepted by CommunicationMod
                       (IRONCLAD, SILENT, DEFECT, WATCHER).
            ascension: Ascension level (0-20).
            seed: Optional integer seed. If provided, sent as a positional
                  argument; CommunicationMod's SeedHelper interprets the
                  string however it interprets it. Pass `None` to let the
                  game pick a fresh random seed.
            timeout: Seconds to wait for the live game to confirm it's in
                     the new run.

        Returns:
            The first game-state dictionary observed after the start command
            takes effect (room_phase=EVENT, screen_name=NONE, floor=0).

        Raises:
            CommunicationModError: If the game does not enter a run within
                                   `timeout` seconds.
        """
        if not self._connected:
            raise CommunicationModError("Not connected to CommunicationMod bridge")

        char = character.upper().strip()
        cmd = f"start {char} {int(ascension)}"
        if seed is not None:
            cmd += f" {int(seed)}"

        # CommunicationMod's `start` is only valid at the main menu — when
        # in-game it is rejected (`Invalid command: start. Possible commands:
        # [...]`). And there's no programmatic abandon (no `abandon`
        # command, no ESCAPE key — see CommandExecutor.getKeycode in
        # CommunicationMod.jar). So we have three cases:
        #
        #   A) Live game is at the main menu (in_game=False). Send `start`.
        #   B) Live game is at a brand-new Neow event (floor 0, EVENT,
        #      Talk-only options). Adopt the existing run as if we'd
        #      started it ourselves. This is the auto-recovery path that
        #      kicks in if the harness crashed mid-`start_game` or if the
        #      previous scenario invocation aborted between `start` and
        #      its first step.
        #   C) Anything else (in_game=True, NOT a fresh Neow). Refuse loudly
        #      so we never silently divert into a half-run state.
        try:
            current = self.get_state()
        except Exception:
            current = {}

        if current.get('in_game') is True:
            gs = current.get('game_state') or {}
            ss = gs.get('screen_state') or {}
            event_id = (ss.get('event_id') or '').lower()
            ss_screen_name = (ss.get('screen_name') or '').lower()

            # Predicate: BRAND-NEW Neow event, never interacted with.
            #
            #   - At floor 0 in an EVENT room.
            #   - The event is Neow (event_id starts with "neow").
            #   - The Neow event has not yet entered its bonus-pick or
            #     card-pick sub-screens (those report ss['screen_name']
            #     of "card_reward" / "boss_reward" / etc., or transition
            #     to a screen_name other than "EVENT").
            #   - Character matches the requested character.
            #   - Ascension matches the requested ascension.
            #
            # All five must hold; otherwise we'd be adopting a run whose
            # state has already diverged from the (character, ascension,
            # seed) the simulator is about to be initialised with.
            requested_char_upper = (character or '').upper()
            live_char_upper = (gs.get('class') or gs.get('character')
                               or '').upper()
            live_asc = gs.get('ascension_level',
                              gs.get('ascension', None))

            is_fresh_neow = (
                gs.get('floor') == 0
                and gs.get('room_phase') == 'EVENT'
                and event_id.startswith('neow')
                and ss_screen_name in ('', 'event', 'none')
                and (not requested_char_upper
                     or not live_char_upper
                     or live_char_upper == requested_char_upper)
                and (live_asc is None or int(live_asc) == int(ascension))
            )
            if is_fresh_neow:
                print(f"  [start_game] live game already at fresh Neow event "
                      f"(seed={gs.get('seed')!r}, char={live_char_upper}, "
                      f"asc={live_asc}); adopting existing run "
                      f"instead of sending `{cmd}`")
                # Flatten and return current state — caller will read the
                # seed from it and seed the simulator the same way as if
                # we had just started the run.
                flat = current.copy()
                flat.update(gs)
                self._last_state = flat
                return flat
            raise CommunicationModError(
                f"Cannot send `start`: live game is in a run "
                f"(in_game=True, floor={gs.get('floor')}, "
                f"room_phase={gs.get('room_phase')}, "
                f"event_id={event_id!r}, char={live_char_upper!r}, "
                f"asc={live_asc!r}, requested char={requested_char_upper!r}, "
                f"requested asc={ascension!r}). CommunicationMod has no "
                f"programmatic `abandon` command and no ESCAPE key, so the "
                f"harness will not blindly send `start` (which would error "
                f"and leave the run in place). Please return to the main "
                f"menu (ESC → Abandon Run → Confirm) and retry."
            )

        if 'start' not in (current.get('available_commands') or []):
            raise CommunicationModError(
                f"Cannot send `start`: it is not in the live game's "
                f"available_commands "
                f"({current.get('available_commands')!r}). Please "
                f"return to the main menu and retry."
            )

        # Mark the previous mtime so we can detect a real state update
        # rather than just the bridge re-touching the file.
        try:
            old_mtime = self.state_file.stat().st_mtime
        except FileNotFoundError:
            old_mtime = 0

        self.send_command(cmd)

        # Wait until the game reports it's in a run AND has produced a new
        # state-file write, OR until we time out.
        start_time = time.time()
        last_state: Dict[str, Any] = {}
        while time.time() - start_time < timeout:
            try:
                new_mtime = self.state_file.stat().st_mtime
                if new_mtime > old_mtime:
                    with open(self.state_file, 'r') as f:
                        last_state = json.load(f)
                    if last_state.get('in_game') and last_state.get('game_state'):
                        gs = last_state['game_state']
                        # Flatten for caller convenience.
                        flat = last_state.copy()
                        flat.update(gs)
                        self._last_state = flat
                        return flat
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(0.05)

        raise CommunicationModError(
            f"Game did not enter a run within {timeout}s after `{cmd}`. "
            f"Last observed state keys: {list(last_state.keys())}"
        )

    def wait_for_state(self, predicate, timeout: float = 5.0,
                       poll_interval: float = 0.05) -> Optional[Dict[str, Any]]:
        """Poll the bridge state file until `predicate(state)` is true.

        Args:
            predicate: Callable that takes a flattened state dict and
                       returns True when the wait condition is satisfied.
            timeout:   Maximum seconds to wait.
            poll_interval: How often to re-read the state file.

        Returns:
            The first state dict for which the predicate was true, or
            None if the timeout expired.
        """
        if not self._connected:
            raise CommunicationModError("Not connected to CommunicationMod bridge")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                state = self.get_state()
                if predicate(state):
                    return state
            except CommunicationModError:
                pass
            time.sleep(poll_interval)
        return None

    def choose_option(self, option_index: int):
        """Send choice command for events/rewards.

        Args:
            option_index: Index of option to choose.
        """
        self.send_command(f"choose {option_index}")

    def use_potion(self, slot: int, target_index: int = -1):
        """Use a potion.

        Args:
            slot: Potion slot index (0-2 typically).
            target_index: Target for targeted potions (-1 for untargeted).
        """
        if target_index >= 0:
            command = f"potion use {slot} {target_index}"
        else:
            command = f"potion use {slot}"
        self.send_command(command)

    def discard_potion(self, slot: int):
        """Discard a potion.

        Args:
            slot: Potion slot index to discard.
        """
        self.send_command(f"potion discard {slot}")

    def wait(self, frames: int = 1):
        """Wait for specified number of frames.

        Args:
            frames: Number of game frames to wait.
        """
        self.send_command(f"wait {frames}")

    def press_key(self, key: str):
        """Simulate a key press.

        Args:
            key: Key to press (e.g., 'space', 'escape').
        """
        self.send_command(f"key {key}")

    def get_player_hp(self) -> tuple[int, int]:
        """Get current and max HP.

        Returns:
            Tuple of (current_hp, max_hp).
        """
        state = self.get_state()
        game_state = state.get('game_state', {})
        return (game_state.get('current_hp', 0), game_state.get('max_hp', 0))

    def get_gold(self) -> int:
        """Get current gold amount.

        Returns:
            Current gold.
        """
        state = self.get_state()
        game_state = state.get('game_state', {})
        return game_state.get('gold', 0)

    def get_floor(self) -> int:
        """Get current floor number.

        Returns:
            Current floor (1-55+).
        """
        state = self.get_state()
        game_state = state.get('game_state', {})
        return game_state.get('floor', 1)

    def get_act(self) -> int:
        """Get current act number.

        Returns:
            Current act (1-4).
        """
        state = self.get_state()
        game_state = state.get('game_state', {})
        return game_state.get('act', 1)

    def get_hand(self) -> List[Dict[str, Any]]:
        """Get list of cards in hand.

        Returns:
            List of card dictionaries.
        """
        combat = self.get_combat_state()
        if combat:
            return combat.get('hand', [])
        return []

    def get_monsters(self) -> List[Dict[str, Any]]:
        """Get list of monsters in combat.

        Returns:
            List of monster dictionaries with hp, block, intent, etc.
        """
        combat = self.get_combat_state()
        if combat:
            return combat.get('monsters', [])
        return []

    def is_in_combat(self) -> bool:
        """Check if currently in combat.

        Returns:
            True if in combat, False otherwise.
        """
        state = self.get_state()
        game_state = state.get('game_state', {})
        room_phase = game_state.get('room_phase', '')
        return room_phase == 'COMBAT'

    def get_screen_state(self) -> str:
        """Get current screen state.

        Returns:
            Screen state string (e.g., 'combat', 'reward', 'map', 'event').
        """
        state = self.get_state()
        game_state = state.get('game_state', {})
        screen_type = game_state.get('screen_type', 'unknown')
        screen_name = game_state.get('screen_name', '')
        room_phase = game_state.get('room_phase', '')

        if room_phase == 'COMBAT':
            return 'combat'
        elif screen_type == 'NONE':
            return 'game'
        else:
            return screen_name.lower() if screen_name else screen_type.lower()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False
