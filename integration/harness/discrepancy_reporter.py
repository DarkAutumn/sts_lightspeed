"""Discrepancy reporter for generating detailed bug reports.

Creates structured reports from discrepancies detected during
interactive sync sessions, including replication scripts.
"""
import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class DiscrepancyRecord:
    """Record of a single discrepancy with full context."""
    record_id: str
    timestamp: str
    field: str
    game_value: Any
    sim_value: Any
    severity: str
    message: str
    game_state_before: Dict[str, Any] = field(default_factory=dict)
    game_state_after: Dict[str, Any] = field(default_factory=dict)
    sim_state: Dict[str, Any] = field(default_factory=dict)
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    category: str = "unknown"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class DiscrepancyReporter:
    """Generates and manages discrepancy reports.

    Writes individual discrepancy reports and session summaries,
    including Python scripts for reproduction.
    """

    def __init__(self, output_dir: Path, session_config: Optional[Dict[str, Any]] = None):
        """Initialize the reporter.

        Args:
            output_dir: Directory to write reports.
            session_config: Optional session configuration for context.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_config = session_config or {}
        self._records: List[DiscrepancyRecord] = []
        self._record_count = 0

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().isoformat()

    def _generate_id(self) -> str:
        """Generate a unique record ID."""
        self._record_count += 1
        return f"disc_{self._record_count:04d}_{uuid.uuid4().hex[:8]}"

    def categorize(self, field: str) -> str:
        """Categorize a discrepancy based on the field name.

        Args:
            field: Field name from discrepancy.

        Returns:
            Category string.
        """
        field_lower = field.lower()

        if 'monster' in field_lower:
            return 'monster'
        elif 'card' in field_lower or 'hand' in field_lower or 'deck' in field_lower:
            return 'card'
        elif 'relic' in field_lower:
            return 'relic'
        elif 'combat' in field_lower or 'hp' in field_lower or 'block' in field_lower:
            return 'combat'
        elif 'event' in field_lower:
            return 'event'
        elif 'potion' in field_lower:
            return 'potion'
        elif 'energy' in field_lower:
            return 'energy'
        elif 'floor' in field_lower or 'act' in field_lower:
            return 'progression'
        elif 'gold' in field_lower:
            return 'gold'
        else:
            return 'unknown'

    def record(
        self,
        field: str,
        game_value: Any,
        sim_value: Any,
        severity: str,
        message: str,
        game_state_before: Optional[Dict[str, Any]] = None,
        game_state_after: Optional[Dict[str, Any]] = None,
        sim_state: Optional[Dict[str, Any]] = None,
        action_history: Optional[List[Dict[str, Any]]] = None
    ) -> DiscrepancyRecord:
        """Record a discrepancy and write it to file.

        Args:
            field: Field name where discrepancy was found.
            game_value: Value from the game.
            sim_value: Value from the simulator.
            severity: Severity level (critical, major, minor).
            message: Description of the discrepancy.
            game_state_before: Game state before the change.
            game_state_after: Game state after the change.
            sim_state: Current simulator state.
            action_history: List of actions leading to this point.

        Returns:
            The created DiscrepancyRecord.
        """
        record = DiscrepancyRecord(
            record_id=self._generate_id(),
            timestamp=self._get_timestamp(),
            field=field,
            game_value=game_value,
            sim_value=sim_value,
            severity=severity,
            message=message,
            game_state_before=game_state_before or {},
            game_state_after=game_state_after or {},
            sim_state=sim_state or {},
            action_history=action_history or [],
            category=self.categorize(field)
        )

        self._records.append(record)
        self._write_record(record)

        return record

    def _write_record(self, record: DiscrepancyRecord) -> Path:
        """Write a discrepancy record to files.

        Args:
            record: The record to write.

        Returns:
            Path to the markdown report file.
        """
        # Write JSON
        json_path = self.output_dir / f"{record.record_id}.json"
        with open(json_path, 'w') as f:
            json.dump(record.to_dict(), f, indent=2, default=str)

        # Write Markdown
        md_path = self.output_dir / f"{record.record_id}.md"
        with open(md_path, 'w') as f:
            f.write(self._generate_markdown_report(record))

        # Write replication script
        script_path = self.output_dir / f"{record.record_id}_reproduce.py"
        with open(script_path, 'w') as f:
            f.write(self.generate_replication_script(record))

        return md_path

    def _generate_markdown_report(self, record: DiscrepancyRecord) -> str:
        """Generate a markdown report for a discrepancy.

        Args:
            record: The discrepancy record.

        Returns:
            Markdown-formatted string.
        """
        lines = []

        # Header
        lines.append(f"# Discrepancy Report: {record.record_id}")
        lines.append("")
        lines.append(f"**Timestamp**: {record.timestamp}")
        lines.append(f"**Severity**: {record.severity.upper()}")
        lines.append(f"**Category**: {record.category}")
        lines.append(f"**Field**: `{record.field}`")
        lines.append("")

        # Discrepancy details
        lines.append("## Discrepancy")
        lines.append("")
        lines.append(f"| Property | Value |")
        lines.append(f"|----------|-------|")
        lines.append(f"| **Game Value** | `{record.game_value}` |")
        lines.append(f"| **Sim Value** | `{record.sim_value}` |")
        lines.append(f"| **Message** | {record.message} |")
        lines.append("")

        # Session context
        if self.session_config:
            lines.append("## Session Context")
            lines.append("")
            lines.append(f"- **Seed**: {self.session_config.get('seed', 'unknown')}")
            lines.append(f"- **Character**: {self.session_config.get('character', 'unknown')}")
            lines.append(f"- **Ascension**: {self.session_config.get('ascension', 0)}")
            lines.append("")

        # Game state before
        if record.game_state_before:
            lines.append("## Game State (Before)")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(record.game_state_before, indent=2, default=str)[:2000])
            lines.append("```")
            lines.append("")

        # Game state after
        if record.game_state_after:
            lines.append("## Game State (After)")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(record.game_state_after, indent=2, default=str)[:2000])
            lines.append("```")
            lines.append("")

        # Action history
        if record.action_history:
            lines.append("## Action History")
            lines.append("")
            lines.append("| Step | Action |")
            lines.append("|------|--------|")
            for i, action in enumerate(record.action_history[-20:]):  # Last 20
                action_str = action.get('action', action.get('command', str(action)))
                lines.append(f"| {i+1} | `{action_str}` |")
            lines.append("")

        # Reproduction
        lines.append("## Reproduction")
        lines.append("")
        lines.append(f"See `{record.record_id}_reproduce.py` for a script to reproduce this discrepancy.")
        lines.append("")

        # Tags
        if record.tags:
            lines.append("## Tags")
            lines.append("")
            lines.append(", ".join(f"`{t}`" for t in record.tags))
            lines.append("")

        return "\n".join(lines)

    def generate_replication_script(self, record: DiscrepancyRecord) -> str:
        """Generate a Python script to reproduce the discrepancy.

        Args:
            record: The discrepancy record.

        Returns:
            Python script as a string.
        """
        seed = self.session_config.get('seed', 12345)
        character = self.session_config.get('character', 'IRONCLAD')
        ascension = self.session_config.get('ascension', 0)

        lines = []
        lines.append('#!/usr/bin/env python3')
        lines.append(f'"""Reproduction script for discrepancy: {record.record_id}')
        lines.append('')
        lines.append(f'Field: {record.field}')
        lines.append(f'Severity: {record.severity}')
        lines.append(f'Message: {record.message}')
        lines.append('"""')
        lines.append('')
        lines.append('import sys')
        lines.append('from pathlib import Path')
        lines.append('')
        lines.append('# Add paths for imports')
        lines.append('_project_root = Path(__file__).parent.parent.parent.parent')
        lines.append('sys.path.insert(0, str(_project_root))')
        lines.append('')
        lines.append('from harness.simulator_controller import SimulatorController')
        lines.append('from harness.state_comparator import StateComparator')
        lines.append('')
        lines.append(f'SEED = {seed}')
        lines.append(f"CHARACTER = '{character}'")
        lines.append(f'ASCENSION = {ascension}')
        lines.append('')
        lines.append('')
        lines.append('def setup_simulator():')
        lines.append('    """Initialize the simulator with the session configuration."""')
        lines.append('    sim = SimulatorController()')
        lines.append('    sim.setup_game(SEED, CHARACTER, ASCENSION)')
        lines.append('    return sim')
        lines.append('')
        lines.append('')
        lines.append('def execute_actions(sim, actions):')
        lines.append('    """Execute a list of actions on the simulator."""')
        lines.append('    for action in actions:')
        lines.append('        cmd = action.get("sim_command", action.get("command", ""))')
        lines.append('        if cmd:')
        lines.append('            print(f"Executing: {cmd}")')
        lines.append('            sim.take_action(cmd)')
        lines.append('')
        lines.append('')
        lines.append('def verify_discrepancy(sim):')
        lines.append('    """Verify the discrepancy still exists."""')
        lines.append('    state = sim.get_state()')
        lines.append(f'    expected_field = "{record.field}"')
        lines.append(f'    expected_value = {repr(record.game_value)}')
        lines.append('')
        lines.append('    # Navigate to the field in the state')
        lines.append('    parts = expected_field.split(".")')
        lines.append('    current = state')
        lines.append('    for part in parts:')
        lines.append('        if part.endswith("]"):')
        lines.append('            # Handle array index')
        lines.append('            name, idx = part[:-1].split("[" )')
        lines.append('            current = current.get(name, [])[int(idx)]')
        lines.append('        else:')
        lines.append('            current = current.get(part)')
        lines.append('')
        lines.append('    actual_value = current')
        lines.append('')
        lines.append('    if actual_value == expected_value:')
        lines.append(f'        print("SUCCESS: Field {{expected_field}} has expected value {{expected_value}}")')
        lines.append('        return True')
        lines.append('    else:')
        lines.append(f'        print("DISCREPANCY: Field {{expected_field}}")')
        lines.append(f'        print(f"  Expected: {{expected_value}}")')
        lines.append(f'        print(f"  Actual: {{actual_value}}")')
        lines.append('        return False')
        lines.append('')
        lines.append('')
        lines.append('def main():')
        lines.append('    """Main reproduction routine."""')
        lines.append('    print("Setting up simulator...")')
        lines.append('    sim = setup_simulator()')
        lines.append('')
        lines.append('    # Actions from history')
        lines.append('    actions = [')

        # Add actions from history
        for action in record.action_history:
            cmd = action.get('sim_command', action.get('command', ''))
            if cmd:
                lines.append(f'        {{"command": "{cmd}"}},')

        lines.append('    ]')
        lines.append('')
        lines.append('    print(f"Executing {{len(actions)}} actions...")')
        lines.append('    execute_actions(sim, actions)')
        lines.append('')
        lines.append('    print("Verifying discrepancy...")')
        lines.append('    result = verify_discrepancy(sim)')
        lines.append('')
        lines.append('    if result:')
        lines.append('        print("Discrepancy appears to be fixed!")')
        lines.append('        return 0')
        lines.append('    else:')
        lines.append('        print("Discrepancy still exists.")')
        lines.append('        return 1')
        lines.append('')
        lines.append('')
        lines.append('if __name__ == "__main__":')
        lines.append('    sys.exit(main())')
        lines.append('')

        return "\n".join(lines)

    def generate_session_summary(
        self,
        stats: Dict[str, Any],
        start_time: str,
        end_time: str,
        config: Dict[str, Any]
    ) -> str:
        """Generate a markdown summary of the entire session.

        Args:
            stats: Session statistics.
            start_time: Session start timestamp.
            end_time: Session end timestamp.
            config: Session configuration.

        Returns:
            Markdown-formatted summary string.
        """
        lines = []

        # Header
        lines.append("# Diff Logger Session Summary")
        lines.append("")
        lines.append(f"**Session ID**: {config.get('session_id', 'unknown')}")
        lines.append(f"**Start Time**: {start_time}")
        lines.append(f"**End Time**: {end_time}")
        lines.append("")

        # Configuration
        lines.append("## Configuration")
        lines.append("")
        lines.append(f"- **Seed**: {config.get('seed', 'auto-detected')}")
        lines.append(f"- **Character**: {config.get('character', 'unknown')}")
        lines.append(f"- **Ascension**: {config.get('ascension', 0)}")
        lines.append(f"- **Mode**: {config.get('mode', 'unknown')}")
        lines.append(f"- **Interval**: {config.get('interval', 0.1)}s")
        lines.append("")

        # Statistics
        lines.append("## Statistics")
        lines.append("")
        lines.append(f"- **Total Events**: {stats.get('total_events', 0)}")
        lines.append(f"- **Total Actions**: {stats.get('total_actions', 0)}")
        lines.append(f"- **Critical Discrepancies**: {stats.get('critical_discrepancies', 0)}")
        lines.append(f"- **Major Discrepancies**: {stats.get('major_discrepancies', 0)}")
        lines.append(f"- **Minor Discrepancies**: {stats.get('minor_discrepancies', 0)}")
        lines.append("")

        # Discrepancy summary
        if self._records:
            lines.append("## Discrepancies")
            lines.append("")

            # Group by category
            by_category: Dict[str, List[DiscrepancyRecord]] = {}
            for r in self._records:
                cat = r.category
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(r)

            for cat, records in sorted(by_category.items()):
                lines.append(f"### {cat.title()} ({len(records)})")
                lines.append("")
                lines.append("| ID | Field | Severity | Message |")
                lines.append("|----|-------|----------|---------|")
                for r in records:
                    msg_short = r.message[:50] + "..." if len(r.message) > 50 else r.message
                    lines.append(f"| [{r.record_id}](discrepancies/{r.record_id}.md) | `{r.field}` | {r.severity} | {msg_short} |")
                lines.append("")

        # Files generated
        lines.append("## Generated Files")
        lines.append("")
        lines.append(f"- `events.jsonl` - Complete event log")
        lines.append(f"- `combat.log` - Combat journal")
        lines.append(f"- `discrepancies/` - Individual discrepancy reports")
        lines.append(f"- `summary.md` - This file")
        lines.append("")

        # Result
        critical = stats.get('critical_discrepancies', 0)
        if critical > 0:
            lines.append("## Result: ISSUES FOUND")
            lines.append("")
            lines.append(f"Found {critical} critical discrepancies that need investigation.")
        else:
            lines.append("## Result: NO CRITICAL ISSUES")
            lines.append("")
            lines.append("No critical discrepancies found during this session.")

        return "\n".join(lines)

    def get_records(self) -> List[DiscrepancyRecord]:
        """Get all recorded discrepancies.

        Returns:
            List of all discrepancy records.
        """
        return self._records.copy()

    def get_records_by_severity(self, severity: str) -> List[DiscrepancyRecord]:
        """Get records filtered by severity.

        Args:
            severity: Severity level to filter by.

        Returns:
            List of matching records.
        """
        return [r for r in self._records if r.severity == severity]

    def get_records_by_category(self, category: str) -> List[DiscrepancyRecord]:
        """Get records filtered by category.

        Args:
            category: Category to filter by.

        Returns:
            List of matching records.
        """
        return [r for r in self._records if r.category == category]

    def clear(self):
        """Clear all stored records."""
        self._records.clear()
        self._record_count = 0
