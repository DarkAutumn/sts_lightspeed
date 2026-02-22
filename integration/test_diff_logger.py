#!/usr/bin/env python3
"""Tests for the diff logger components."""
import json
import os
import sys
import tempfile
import shutil
import unittest
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Add paths for imports - handle both direct run and package import
_project_root = Path(__file__).parent.parent
_integration_dir = Path(__file__).parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_integration_dir) not in sys.path:
    sys.path.insert(0, str(_integration_dir))

from harness.combat_journal import (
    CombatJournal, CombatTurn, CardPlay, EnemyAction, CombatLog
)
from harness.discrepancy_reporter import (
    DiscrepancyReporter, DiscrepancyRecord
)
from harness.diff_logger import (
    DiffEvent, SessionConfig, SessionStats, create_session_config
)


class TestCombatJournal(unittest.TestCase):
    """Tests for CombatJournal."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = Path(self.temp_dir) / "combat.log"
        self.journal = CombatJournal(self.log_path)

    def tearDown(self):
        """Clean up test fixtures."""
        self.journal.close()
        shutil.rmtree(self.temp_dir)

    def test_start_combat_creates_log_file(self):
        """Test that starting combat creates the log file."""
        state = {
            'seed': 12345,
            'floor': 5,
            'combat_state': {
                'turn': 1,
                'monsters': [{'name': 'Cultist', 'cur_hp': 50}]
            }
        }
        combat_id = self.journal.start_combat(state)

        self.assertTrue(self.log_path.exists())
        self.assertIn('combat_', combat_id)
        self.assertIsNotNone(self.journal._current_combat)

    def test_record_card_play(self):
        """Test recording a card play."""
        self.journal.start_combat({'seed': 1, 'floor': 1, 'combat_state': {'turn': 1, 'monsters': []}})
        self.journal.start_turn({'combat_state': {'turn': 1, 'player': {'cur_hp': 80, 'energy': 3}, 'hand': []}})

        self.journal.record_card_play(
            card_name='Strike',
            card_index=0,
            target_index=0,
            energy_cost=1,
            damage_dealt=6
        )

        self.assertEqual(len(self.journal._current_turn.cards_played), 1)
        self.assertEqual(self.journal._current_turn.cards_played[0].card_name, 'Strike')

    def test_record_enemy_action(self):
        """Test recording an enemy action."""
        self.journal.start_combat({'seed': 1, 'floor': 1, 'combat_state': {'turn': 1, 'monsters': []}})
        self.journal.start_turn({'combat_state': {'turn': 1, 'player': {'cur_hp': 80}}})

        self.journal.record_enemy_action(
            monster_index=0,
            monster_name='Cultist',
            intent_type='ATTACK',
            intent_damage=6
        )

        self.assertEqual(len(self.journal._current_turn.enemy_actions), 1)
        self.assertEqual(self.journal._current_turn.enemy_actions[0].intent_type, 'ATTACK')

    def test_end_turn_records_state(self):
        """Test that ending a turn records it properly."""
        self.journal.start_combat({'seed': 1, 'floor': 1, 'combat_state': {'turn': 1, 'monsters': []}})
        self.journal.start_turn({'combat_state': {'turn': 1, 'player': {'cur_hp': 80, 'energy': 3}, 'hand': []}})
        self.journal.end_turn({'combat_state': {'turn': 2, 'player': {'cur_hp': 75, 'energy': 0}}})

        self.assertEqual(len(self.journal._current_combat.turns), 1)

    def test_end_combat_sets_result(self):
        """Test ending combat."""
        self.journal.start_combat({'seed': 1, 'floor': 1, 'combat_state': {'turn': 1, 'monsters': []}})
        combat = self.journal._current_combat
        self.journal.end_combat({}, 'victory')

        # After end_combat, _current_combat is set to None, but we saved reference
        self.assertEqual(combat.result, 'victory')
        self.assertIsNotNone(combat.end_time)

    def test_card_play_to_log_line(self):
        """Test CardPlay log line formatting."""
        card = CardPlay(
            timestamp="12:00:00.000",
            card_name="Strike",
            card_index=0,
            target_index=1,
            energy_cost=1,
            damage_dealt=9,
            block_gained=0
        )
        line = card.to_log_line()

        self.assertIn('Strike', line)
        self.assertIn('target 1', line)
        self.assertIn('dmg=9', line)

    def test_enemy_action_to_log_line(self):
        """Test EnemyAction log line formatting."""
        action = EnemyAction(
            timestamp="12:00:00.000",
            monster_index=0,
            monster_name="Cultist",
            intent_type="ATTACK",
            intent_damage=6
        )
        line = action.to_log_line()

        self.assertIn('Cultist', line)
        self.assertIn('ATTACK', line)
        self.assertIn('dmg=6', line)


class TestDiscrepancyReporter(unittest.TestCase):
    """Tests for DiscrepancyReporter."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "discrepancies"
        self.reporter = DiscrepancyReporter(
            self.output_dir,
            session_config={'seed': 12345, 'character': 'IRONCLAD', 'ascension': 0}
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_record_creates_files(self):
        """Test that recording a discrepancy creates all files."""
        record = self.reporter.record(
            field='player.cur_hp',
            game_value=75,
            sim_value=70,
            severity='critical',
            message='HP mismatch'
        )

        # Check JSON file
        json_path = self.output_dir / f"{record.record_id}.json"
        self.assertTrue(json_path.exists())

        # Check Markdown file
        md_path = self.output_dir / f"{record.record_id}.md"
        self.assertTrue(md_path.exists())

        # Check reproduction script
        script_path = self.output_dir / f"{record.record_id}_reproduce.py"
        self.assertTrue(script_path.exists())

    def test_categorize_field(self):
        """Test field categorization."""
        self.assertEqual(self.reporter.categorize('monster[0].cur_hp'), 'monster')
        self.assertEqual(self.reporter.categorize('card.Strike'), 'card')
        self.assertEqual(self.reporter.categorize('hand.count'), 'card')
        self.assertEqual(self.reporter.categorize('relics.BurningBlood'), 'relic')
        self.assertEqual(self.reporter.categorize('player.cur_hp'), 'combat')
        self.assertEqual(self.reporter.categorize('floor'), 'progression')
        self.assertEqual(self.reporter.categorize('gold'), 'gold')
        self.assertEqual(self.reporter.categorize('unknown_field'), 'unknown')

    def test_generate_session_summary(self):
        """Test session summary generation."""
        # Record a discrepancy
        self.reporter.record(
            field='player.cur_hp',
            game_value=75,
            sim_value=70,
            severity='critical',
            message='HP mismatch'
        )

        stats = {
            'total_events': 10,
            'total_actions': 5,
            'critical_discrepancies': 1,
            'major_discrepancies': 0,
            'minor_discrepancies': 0
        }
        config = {
            'session_id': 'test_session',
            'seed': 12345,
            'character': 'IRONCLAD',
            'ascension': 0,
            'mode': 'full',
            'interval': 0.1
        }

        summary = self.reporter.generate_session_summary(
            stats, '2026-01-01T00:00:00', '2026-01-01T00:01:00', config
        )

        self.assertIn('test_session', summary)
        self.assertIn('IRONCLAD', summary)
        self.assertIn('10', summary)  # total_events
        self.assertIn('ISSUES FOUND', summary)

    def test_reproduction_script_content(self):
        """Test that reproduction script has correct content."""
        record = self.reporter.record(
            field='player.cur_hp',
            game_value=75,
            sim_value=70,
            severity='critical',
            message='HP mismatch',
            action_history=[
                {'command': 'play 0 0'},
                {'command': 'end'}
            ]
        )

        script_path = self.output_dir / f"{record.record_id}_reproduce.py"
        with open(script_path) as f:
            script = f.read()

        self.assertIn('#!/usr/bin/env python3', script)
        self.assertIn('SEED = 12345', script)
        self.assertIn("CHARACTER = 'IRONCLAD'", script)
        self.assertIn('play 0 0', script)

    def test_get_records_by_severity(self):
        """Test filtering records by severity."""
        self.reporter.record(field='a', game_value=1, sim_value=2, severity='critical', message='m1')
        self.reporter.record(field='b', game_value=1, sim_value=2, severity='major', message='m2')
        self.reporter.record(field='c', game_value=1, sim_value=2, severity='critical', message='m3')

        critical = self.reporter.get_records_by_severity('critical')
        self.assertEqual(len(critical), 2)

        major = self.reporter.get_records_by_severity('major')
        self.assertEqual(len(major), 1)


class TestDiffLoggerDataClasses(unittest.TestCase):
    """Tests for diff logger data classes."""

    def test_diff_event_to_dict(self):
        """Test DiffEvent serialization."""
        event = DiffEvent(
            event_id='evt_001',
            timestamp='2026-01-01T00:00:00',
            event_type='state_change',
            game_state_before={'hp': 80},
            game_state_after={'hp': 75},
            sim_state={'hp': 70},
            discrepancies=[],
            metadata={'floor': 5}
        )

        d = event.to_dict()
        self.assertEqual(d['event_id'], 'evt_001')
        self.assertEqual(d['event_type'], 'state_change')
        self.assertEqual(d['metadata']['floor'], 5)

    def test_diff_event_to_jsonl(self):
        """Test DiffEvent JSONL output."""
        event = DiffEvent(
            event_id='evt_001',
            timestamp='2026-01-01T00:00:00',
            event_type='test',
            metadata={'key': 'value'}
        )

        jsonl = event.to_jsonl()
        parsed = json.loads(jsonl)

        self.assertEqual(parsed['event_id'], 'evt_001')

    def test_session_config_to_dict(self):
        """Test SessionConfig serialization."""
        config = SessionConfig(
            output_dir=Path('/tmp/test'),
            session_id='test_session',
            seed=12345,
            character='IRONCLAD',
            ascension=10,
            mode='full',
            interval=0.1,
            verbose=True
        )

        d = config.to_dict()

        self.assertEqual(d['session_id'], 'test_session')
        self.assertEqual(d['output_dir'], '/tmp/test')
        self.assertEqual(d['seed'], 12345)

    def test_session_stats_to_dict(self):
        """Test SessionStats serialization."""
        stats = SessionStats(
            start_time='2026-01-01T00:00:00',
            end_time='2026-01-01T00:01:00',
            total_events=10,
            critical_discrepancies=2
        )

        d = stats.to_dict()

        self.assertEqual(d['total_events'], 10)
        self.assertEqual(d['critical_discrepancies'], 2)

    def test_create_session_config(self):
        """Test session config factory function."""
        config = create_session_config(
            output_base_dir='/tmp/results',
            seed=999,
            character='SILENT',
            ascension=5,
            mode='watch',
            interval=0.2,
            verbose=True
        )

        self.assertEqual(config.seed, 999)
        self.assertEqual(config.character, 'SILENT')
        self.assertEqual(config.ascension, 5)
        self.assertEqual(config.mode, 'watch')
        self.assertEqual(config.interval, 0.2)
        self.assertTrue(config.verbose)
        # Session ID is a timestamp like YYYYMMDD_HHMMSS
        self.assertTrue(len(config.session_id) >= 15)  # At least 15 chars for timestamp
        self.assertIn('_', config.session_id)  # Has underscore separator


class TestCombatTurn(unittest.TestCase):
    """Tests for CombatTurn dataclass."""

    def test_to_dict(self):
        """Test CombatTurn serialization."""
        turn = CombatTurn(
            turn_number=1,
            player_hp_before=80,
            player_hp_after=75,
            player_block=5,
            energy_start=3,
            energy_end=0,
            cards_played=[CardPlay(
                timestamp="12:00:00",
                card_name="Strike",
                card_index=0,
                target_index=0,
                energy_cost=1
            )],
            cards_drawn=['Strike', 'Defend']
        )

        d = turn.to_dict()

        self.assertEqual(d['turn_number'], 1)
        self.assertEqual(d['player_hp_before'], 80)
        self.assertEqual(len(d['cards_played']), 1)
        self.assertEqual(d['cards_drawn'], ['Strike', 'Defend'])

    def test_to_log_lines(self):
        """Test CombatTurn log line generation."""
        turn = CombatTurn(
            turn_number=1,
            player_hp_before=80,
            player_hp_after=75,
            player_block=5,
            energy_start=3,
            energy_end=0,
            cards_played=[],
            cards_drawn=['Strike']
        )

        lines = turn.to_log_lines()

        self.assertTrue(any('TURN 1' in line for line in lines))
        self.assertTrue(any('80 -> 75' in line for line in lines))


class TestDiscrepancyRecord(unittest.TestCase):
    """Tests for DiscrepancyRecord dataclass."""

    def test_to_dict(self):
        """Test DiscrepancyRecord serialization."""
        record = DiscrepancyRecord(
            record_id='disc_001',
            timestamp='2026-01-01T00:00:00',
            field='player.cur_hp',
            game_value=75,
            sim_value=70,
            severity='critical',
            message='HP mismatch',
            category='combat',
            tags=['hp', 'combat']
        )

        d = record.to_dict()

        self.assertEqual(d['record_id'], 'disc_001')
        self.assertEqual(d['field'], 'player.cur_hp')
        self.assertEqual(d['severity'], 'critical')
        self.assertEqual(d['category'], 'combat')


if __name__ == '__main__':
    unittest.main(verbosity=2)
