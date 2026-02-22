"""Combat journal for detailed combat event logging.

Records card plays, enemy actions, damage/block calculations,
and turn-by-turn state snapshots during combat.
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, TextIO


@dataclass
class CardPlay:
    """Record of a card being played."""
    timestamp: str
    card_name: str
    card_index: int
    target_index: int
    energy_cost: int
    damage_dealt: int = 0
    block_gained: int = 0
    effects: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_log_line(self) -> str:
        """Format as human-readable log line."""
        parts = [f"[{self.timestamp}] Played {self.card_name} (idx={self.card_index})"]
        if self.target_index >= 0:
            parts.append(f"-> target {self.target_index}")
        if self.damage_dealt > 0:
            parts.append(f"dmg={self.damage_dealt}")
        if self.block_gained > 0:
            parts.append(f"blk={self.block_gained}")
        if self.effects:
            parts.append(f"effects=[{', '.join(self.effects)}]")
        return " | ".join(parts)


@dataclass
class EnemyAction:
    """Record of an enemy action/intent."""
    timestamp: str
    monster_index: int
    monster_name: str
    intent_type: str  # ATTACK, DEFEND, BUFF, DEBUFF, UNKNOWN, SLEEP
    intent_damage: int = 0
    actual_damage: int = 0
    target: str = "player"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_log_line(self) -> str:
        """Format as human-readable log line."""
        parts = [f"[{self.timestamp}] Enemy {self.monster_index} ({self.monster_name})"]
        parts.append(f"intent={self.intent_type}")
        if self.intent_damage > 0:
            parts.append(f"dmg={self.intent_damage}")
        if self.actual_damage > 0:
            parts.append(f"actual={self.actual_damage}")
        return " | ".join(parts)


@dataclass
class CombatTurn:
    """State snapshot and events for a single combat turn."""
    turn_number: int
    player_hp_before: int
    player_hp_after: int
    player_block: int
    energy_start: int
    energy_end: int
    cards_played: List[CardPlay] = field(default_factory=list)
    enemy_actions: List[EnemyAction] = field(default_factory=list)
    cards_drawn: List[str] = field(default_factory=list)
    monsters_state: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'turn_number': self.turn_number,
            'player_hp_before': self.player_hp_before,
            'player_hp_after': self.player_hp_after,
            'player_block': self.player_block,
            'energy_start': self.energy_start,
            'energy_end': self.energy_end,
            'cards_played': [cp.to_dict() for cp in self.cards_played],
            'enemy_actions': [ea.to_dict() for ea in self.enemy_actions],
            'cards_drawn': self.cards_drawn,
            'monsters_state': self.monsters_state
        }

    def to_log_lines(self) -> List[str]:
        """Format as human-readable log lines."""
        lines = []
        lines.append(f"")
        lines.append(f"{'='*60}")
        lines.append(f"TURN {self.turn_number}")
        lines.append(f"{'='*60}")
        lines.append(f"Player: HP {self.player_hp_before} -> {self.player_hp_after}, Block: {self.player_block}")
        lines.append(f"Energy: {self.energy_start} -> {self.energy_end}")

        if self.cards_drawn:
            lines.append(f"Cards drawn: {', '.join(self.cards_drawn)}")

        if self.cards_played:
            lines.append(f"")
            lines.append(f"Cards played:")
            for cp in self.cards_played:
                lines.append(f"  {cp.to_log_line()}")

        if self.enemy_actions:
            lines.append(f"")
            lines.append(f"Enemy actions:")
            for ea in self.enemy_actions:
                lines.append(f"  {ea.to_log_line()}")

        lines.append(f"")
        return lines


@dataclass
class CombatLog:
    """Complete combat log aggregating all turns and events."""
    combat_id: str
    seed: int
    floor: int
    start_time: str
    end_time: Optional[str] = None
    turns: List[CombatTurn] = field(default_factory=list)
    result: str = "ongoing"  # ongoing, victory, defeat
    enemies: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'combat_id': self.combat_id,
            'seed': self.seed,
            'floor': self.floor,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'turns': [t.to_dict() for t in self.turns],
            'result': self.result,
            'enemies': self.enemies
        }


class CombatJournal:
    """Tracks combat events in detail and writes to log files.

    Maintains an append-only combat log file and tracks turn-by-turn
    state for detailed discrepancy analysis.
    """

    def __init__(self, output_path: Path):
        """Initialize the combat journal.

        Args:
            output_path: Path to the combat.log file.
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        self._current_combat: Optional[CombatLog] = None
        self._current_turn: Optional[CombatTurn] = None
        self._last_monster_states: List[Dict[str, Any]] = []
        self._file_handle: Optional[TextIO] = None
        self._combat_count = 0

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def _write_line(self, line: str):
        """Append a line to the log file."""
        if self._file_handle is None:
            self._file_handle = open(self.output_path, 'a', encoding='utf-8')
        self._file_handle.write(line + '\n')
        self._file_handle.flush()

    def start_combat(self, state: Dict[str, Any]) -> str:
        """Start a new combat and initialize tracking.

        Args:
            state: Current game state containing combat info.

        Returns:
            Combat ID for this combat.
        """
        self._combat_count += 1
        combat_id = f"combat_{self._combat_count}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Extract combat info from state
        combat_state = state.get('combat_state', {})
        seed = state.get('seed', 0)
        floor = state.get('floor', 0)

        # Get enemy names
        enemies = []
        for monster in combat_state.get('monsters', []):
            name = monster.get('name', monster.get('id', 'unknown'))
            enemies.append(name)

        self._current_combat = CombatLog(
            combat_id=combat_id,
            seed=seed,
            floor=floor,
            start_time=datetime.now().isoformat(),
            enemies=enemies
        )

        # Store initial monster states
        self._last_monster_states = combat_state.get('monsters', [])

        # Write combat header
        self._write_line("")
        self._write_line("=" * 70)
        self._write_line(f"COMBAT START: {combat_id}")
        self._write_line(f"Time: {self._current_combat.start_time}")
        self._write_line(f"Floor: {floor}, Seed: {seed}")
        self._write_line(f"Enemies: {', '.join(enemies)}")
        self._write_line("=" * 70)

        return combat_id

    def start_turn(self, state: Dict[str, Any]):
        """Start a new turn.

        Args:
            state: Current game state.
        """
        if self._current_combat is None:
            return

        combat_state = state.get('combat_state', {})
        turn_num = combat_state.get('turn', len(self._current_combat.turns) + 1)

        # Get player state
        player = combat_state.get('player', {})
        player_hp = player.get('cur_hp', player.get('hp', state.get('cur_hp', 0)))
        player_block = player.get('block', 0)
        energy = player.get('energy', state.get('energy', 3))

        # Get hand for cards drawn
        hand = combat_state.get('hand', [])
        cards_drawn = [c.get('name', c.get('id', 'unknown')) for c in hand]

        self._current_turn = CombatTurn(
            turn_number=turn_num,
            player_hp_before=player_hp,
            player_hp_after=player_hp,
            player_block=player_block,
            energy_start=energy,
            energy_end=energy,
            cards_drawn=cards_drawn,
            monsters_state=combat_state.get('monsters', [])
        )

        # Store monster states for tracking
        self._last_monster_states = combat_state.get('monsters', [])

        self._write_line(f"[{self._get_timestamp()}] Turn {turn_num} started")

    def record_card_play(
        self,
        card_name: str,
        card_index: int,
        target_index: int = -1,
        energy_cost: int = 0,
        damage_dealt: int = 0,
        block_gained: int = 0,
        effects: Optional[List[str]] = None
    ):
        """Record a card being played.

        Args:
            card_name: Name of the card.
            card_index: Index in hand.
            target_index: Target monster index (-1 for none).
            energy_cost: Energy cost of the card.
            damage_dealt: Damage dealt by this card.
            block_gained: Block gained from this card.
            effects: List of additional effects.
        """
        if self._current_turn is None:
            return

        card_play = CardPlay(
            timestamp=self._get_timestamp(),
            card_name=card_name,
            card_index=card_index,
            target_index=target_index,
            energy_cost=energy_cost,
            damage_dealt=damage_dealt,
            block_gained=block_gained,
            effects=effects or []
        )

        self._current_turn.cards_played.append(card_play)
        self._write_line(f"  {card_play.to_log_line()}")

    def record_enemy_action(
        self,
        monster_index: int,
        monster_name: str,
        intent_type: str,
        intent_damage: int = 0,
        actual_damage: int = 0
    ):
        """Record an enemy action/intent.

        Args:
            monster_index: Index of the monster.
            monster_name: Name of the monster.
            intent_type: Type of intent (ATTACK, DEFEND, etc.).
            intent_damage: Intended damage (from intent).
            actual_damage: Actual damage dealt.
        """
        if self._current_turn is None:
            return

        action = EnemyAction(
            timestamp=self._get_timestamp(),
            monster_index=monster_index,
            monster_name=monster_name,
            intent_type=intent_type,
            intent_damage=intent_damage,
            actual_damage=actual_damage
        )

        self._current_turn.enemy_actions.append(action)
        self._write_line(f"  {action.to_log_line()}")

    def update_turn_state(self, state: Dict[str, Any]):
        """Update the current turn state from game state.

        Detects changes in monster HP, player HP/block, etc.

        Args:
            state: Current game state.
        """
        if self._current_turn is None or self._current_combat is None:
            return

        combat_state = state.get('combat_state', {})
        player = combat_state.get('player', {})

        # Update player state
        self._current_turn.player_hp_after = player.get('cur_hp', player.get('hp', 0))
        self._current_turn.player_block = player.get('block', 0)
        self._current_turn.energy_end = player.get('energy', 0)

        # Check for monster changes (damage dealt, intents)
        current_monsters = combat_state.get('monsters', [])
        for i, monster in enumerate(current_monsters):
            if i < len(self._last_monster_states):
                old_monster = self._last_monster_states[i]

                # Check for HP change (damage dealt)
                old_hp = old_monster.get('cur_hp', old_monster.get('hp', 0))
                new_hp = monster.get('cur_hp', monster.get('hp', 0))
                if new_hp < old_hp:
                    # Damage was dealt - find which card caused it
                    damage = old_hp - new_hp
                    if self._current_turn.cards_played:
                        last_card = self._current_turn.cards_played[-1]
                        last_card.damage_dealt += damage

                # Check for intent change
                old_intent = old_monster.get('intent', {})
                new_intent = monster.get('intent', {})
                if old_intent != new_intent:
                    self.record_enemy_action(
                        monster_index=i,
                        monster_name=monster.get('name', monster.get('id', 'unknown')),
                        intent_type=new_intent.get('type', 'UNKNOWN'),
                        intent_damage=new_intent.get('damage', 0)
                    )

        self._last_monster_states = current_monsters

    def end_turn(self, state: Dict[str, Any]):
        """End the current turn and record it.

        Args:
            state: Current game state at end of turn.
        """
        if self._current_turn is None or self._current_combat is None:
            return

        # Final state update
        self.update_turn_state(state)

        # Add turn to combat log
        self._current_combat.turns.append(self._current_turn)

        # Write turn summary
        for line in self._current_turn.to_log_lines():
            self._write_line(line)

        self._current_turn = None

    def end_combat(self, state: Dict[str, Any], result: str = "unknown"):
        """End the current combat.

        Args:
            state: Final game state.
            result: Combat result (victory, defeat, flee).
        """
        if self._current_combat is None:
            return

        self._current_combat.end_time = datetime.now().isoformat()
        self._current_combat.result = result

        # Write combat summary
        self._write_line("")
        self._write_line("=" * 70)
        self._write_line(f"COMBAT END: {self._current_combat.combat_id}")
        self._write_line(f"Result: {result}")
        self._write_line(f"Turns: {len(self._current_combat.turns)}")
        self._write_line(f"Duration: {self._current_combat.start_time} -> {self._current_combat.end_time}")
        self._write_line("=" * 70)
        self._write_line("")

        self._current_combat = None
        self._current_turn = None

    def get_summary(self) -> str:
        """Get a summary of all combats in this session.

        Returns:
            Markdown-formatted summary string.
        """
        lines = []
        lines.append("## Combat Journal Summary")
        lines.append("")

        # This would need to track all combats, for now just report current
        if self._current_combat:
            lines.append(f"Current combat: {self._current_combat.combat_id}")
            lines.append(f"Turns: {len(self._current_combat.turns)}")

        return "\n".join(lines)

    def close(self):
        """Close the journal and flush any pending data."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
