"""YAML scenario loader for test scenarios.

This module provides functionality to load and manage test scenarios
defined in YAML files. Scenarios define a sequence of actions with
expected outcomes.
"""
import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from .expected_state import ExpectedState, ExpectedStateManager


@dataclass
class ScenarioStep:
    """A single step in a test scenario."""
    action_type: str  # 'play', 'end_turn', 'choose', 'potion', etc.
    params: Dict[str, Any] = field(default_factory=dict)
    expected: Optional[ExpectedState] = None
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict, step_num: int) -> 'ScenarioStep':
        """Create ScenarioStep from dictionary.

        Two YAML schemas are supported:

        Old format (single action string):
            - action: "play Strike 0"
              description: "..."

        New format (typed structured fields):
            - type: play
              card: "Strike"
              target: 0
              description: "..."

        Args:
            data: Dictionary with step data.
            step_num: Step number.

        Returns:
            ScenarioStep instance.
        """
        # Parse expected state once (shared by both schemas).
        expected = None
        if 'expected' in data:
            manager = ExpectedStateManager()
            expected = manager._parse_expected_state(step_num, data['expected'])

        # Schema A: legacy "action: ..." string.
        if 'action' in data and data.get('action'):
            action_type, params = cls._parse_action(data['action'])
            return cls(
                action_type=action_type,
                params=params,
                expected=expected,
                description=data.get('description', ''),
            )

        # Schema B: new "type: ..." structured form.
        action_type, params = cls._parse_typed_step(data)
        return cls(
            action_type=action_type,
            params=params,
            expected=expected,
            description=data.get('description', ''),
        )

    @staticmethod
    def _parse_typed_step(data: dict) -> tuple:
        """Parse a structured step dict (Schema B) into (action_type, params).

        Recognised step types and their fields:
          - choose:        option: <int>
          - play:          card: <name>, target: <int> (optional)
          - end_turn/end:  (no fields)
          - potion:        subaction: use|discard, slot: <int>, target: <int>
          - map:           node: <int>            (a map-node choice; CommunicationMod
                                                    handles map navigation as a `choose`)
          - event:         option: <int>          (alias for choose during events)
          - shop:          option: <int>          (alias for choose during shopping)
          - reward:        option: <int>          (alias for choose during card/relic rewards)
          - rest:          option: <int>          (alias for choose at rest sites)
          - treasure:      option: <int>          (alias for choose at treasure rooms)
          - card_select:   option: <int>          (alias for choose during card_select screens)
          - boss_reward:   option: <int>          (alias for choose at boss-relic rewards)
          - proceed:       (no fields)            (close screen / advance after rewards)
          - cancel:        (no fields)            (back-out of a screen)
          - wait:          frames: <int> (default 1)
          - key:           value: <key-name>      (e.g. SPACE, ESCAPE)
          - unknown:       (any unrecognised type — preserved verbatim for diagnostics)
        """
        raw_type = (data.get('type') or 'unknown').lower()
        params = {}

        # Bag every non-meta field from the YAML into params, so that even
        # unrecognised types preserve their data for downstream tools and
        # diagnostics. The translator can then look at params directly.
        meta_keys = {'type', 'description', 'expected'}
        for key, value in data.items():
            if key in meta_keys:
                continue
            params[key] = value

        # Normalise some aliases.
        if raw_type in ('end_turn', 'end'):
            return ('end_turn', {})
        if raw_type in ('event', 'shop', 'reward', 'rest', 'treasure',
                        'card_select', 'boss_reward'):
            # All of these map to a `choose <option>` on both sides; carry
            # the `option` field through.
            opt = params.get('option', 0)
            return ('choose', {'option': int(opt)})
        if raw_type == 'choose':
            opt = params.get('option', 0)
            return ('choose', {'option': int(opt)})
        if raw_type == 'map':
            # `node: N` for legibility; CommunicationMod handles map nodes as
            # a `choose <node>` command.
            node = params.get('node', params.get('option', 0))
            return ('map', {'node': int(node)})
        if raw_type == 'play':
            return ('play', {
                'card': params.get('card', ''),
                'target': int(params.get('target', -1)),
            })
        if raw_type == 'potion':
            return ('potion', {
                'subaction': params.get('subaction', 'use'),
                'slot': int(params.get('slot', 0)),
                'target': int(params.get('target', -1)),
            })
        if raw_type == 'wait':
            return ('wait', {'frames': int(params.get('frames', 1))})
        if raw_type == 'proceed':
            return ('proceed', {})
        if raw_type == 'cancel':
            return ('cancel', {})
        if raw_type == 'key':
            return ('key', {'value': str(params.get('value', 'SPACE'))})

        # Pass through whatever the YAML said; downstream translator decides
        # what to do (or logs an "unsupported step" diagnostic).
        return (raw_type, params)

    @staticmethod
    def _parse_action(action_str: str) -> tuple:
        """Parse action string into type and params.

        Args:
            action_str: Action string like 'play Strike', 'end', 'choose 0'.

        Returns:
            Tuple of (action_type, params_dict).
        """
        parts = action_str.strip().split(None, 1)
        if not parts:
            return ('unknown', {})

        action_type = parts[0].lower()
        params = {}

        if len(parts) > 1:
            rest = parts[1]

            if action_type == 'play':
                # "play Strike" or "play Strike 0"
                play_parts = rest.split()
                params['card'] = play_parts[0]
                if len(play_parts) > 1:
                    params['target'] = int(play_parts[1])

            elif action_type == 'choose':
                params['option'] = int(rest)

            elif action_type == 'potion':
                # "potion use 0" or "potion discard 0"
                potion_parts = rest.split()
                params['subaction'] = potion_parts[0]
                params['slot'] = int(potion_parts[1]) if len(potion_parts) > 1 else 0
                if len(potion_parts) > 2:
                    params['target'] = int(potion_parts[2])

            elif action_type == 'end':
                params['turn'] = True

            else:
                # Generic: treat rest as value
                params['value'] = rest

        return (action_type, params)


@dataclass
class Scenario:
    """A complete test scenario."""
    name: str
    character: str
    ascension: int
    seed: Optional[int]
    description: str = ""
    tags: List[str] = field(default_factory=list)
    preconditions: Dict[str, Any] = field(default_factory=dict)
    steps: List[ScenarioStep] = field(default_factory=list)
    expected_states: Dict[int, ExpectedState] = field(default_factory=dict)
    source_file: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'character': self.character,
            'ascension': self.ascension,
            'seed': self.seed,
            'description': self.description,
            'tags': self.tags,
            'preconditions': self.preconditions,
            'steps': [
                {
                    'action_type': s.action_type,
                    'params': s.params,
                    'description': s.description
                }
                for s in self.steps
            ]
        }


class ScenarioLoader:
    """Loads and manages test scenarios from YAML files."""

    def __init__(self, scenarios_dir: Optional[str] = None):
        """Initialize the scenario loader.

        Args:
            scenarios_dir: Default directory to search for scenarios.
        """
        self.scenarios_dir = Path(scenarios_dir) if scenarios_dir else None
        self._scenarios: Dict[str, Scenario] = {}

    def load(self, yaml_path: str) -> Scenario:
        """Load a scenario from a YAML file.

        Args:
            yaml_path: Path to the YAML file.

        Returns:
            Loaded Scenario.
        """
        path = Path(yaml_path)

        with open(path) as f:
            data = yaml.safe_load(f)

        scenario = self._parse_scenario(data, str(path))
        self._scenarios[scenario.name] = scenario
        return scenario

    def _parse_scenario(self, data: dict, source_file: str) -> Scenario:
        """Parse scenario from YAML data.

        Args:
            data: Dictionary from YAML.
            source_file: Path to source file.

        Returns:
            Scenario instance.
        """
        # Parse basic info
        name = data.get('name', 'Unnamed Scenario')
        character = data.get('character', 'IRONCLAD')
        ascension = data.get('ascension', 0)
        seed = data.get('seed')
        description = data.get('description', '')
        tags = data.get('tags', [])
        preconditions = data.get('preconditions', {})

        # Parse steps
        steps = []
        steps_data = data.get('steps', [])
        for i, step_data in enumerate(steps_data):
            if isinstance(step_data, str):
                # Simple action string
                step = ScenarioStep.from_dict({'action': step_data}, i)
            else:
                step = ScenarioStep.from_dict(step_data, i)
            steps.append(step)

        # Parse expected states
        expected_states = {}
        expected_states_data = data.get('expected_states', {})
        manager = ExpectedStateManager()

        for key, state_data in expected_states_data.items():
            step_num = manager._parse_step_key(key)
            if step_num is not None:
                expected_states[step_num] = manager._parse_expected_state(
                    step_num, state_data
                )

        return Scenario(
            name=name,
            character=character,
            ascension=ascension,
            seed=seed,
            description=description,
            tags=tags,
            preconditions=preconditions,
            steps=steps,
            expected_states=expected_states,
            source_file=source_file
        )

    def load_all(self, directory: Optional[str] = None) -> List[Scenario]:
        """Load all scenarios from a directory.

        Args:
            directory: Directory to search (uses scenarios_dir if not specified).

        Returns:
            List of loaded Scenarios.
        """
        dir_path = Path(directory) if directory else self.scenarios_dir
        if not dir_path:
            raise ValueError("No directory specified")

        scenarios = []
        for yaml_file in dir_path.rglob('*.yaml'):
            try:
                scenario = self.load(str(yaml_file))
                scenarios.append(scenario)
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")

        return scenarios

    def load_by_character(self, character: str, directory: Optional[str] = None) -> List[Scenario]:
        """Load all scenarios for a specific character.

        Args:
            character: Character class name.
            directory: Directory to search.

        Returns:
            List of Scenarios for the character.
        """
        all_scenarios = self.load_all(directory)
        return [s for s in all_scenarios if s.character.upper() == character.upper()]

    def get_scenario(self, name: str) -> Optional[Scenario]:
        """Get a loaded scenario by name.

        Args:
            name: Scenario name.

        Returns:
            Scenario or None if not found.
        """
        return self._scenarios.get(name)

    def filter_by_tags(self, scenarios: List[Scenario], tags: List[str]) -> List[Scenario]:
        """Filter scenarios by tags.

        Args:
            scenarios: List of scenarios to filter.
            tags: Tags to match (scenario must have ALL tags).

        Returns:
            Filtered list of scenarios.
        """
        if not tags:
            return scenarios

        filtered = []
        for scenario in scenarios:
            if all(tag in scenario.tags for tag in tags):
                filtered.append(scenario)

        return filtered

    def filter_by_preconditions(
        self,
        scenarios: List[Scenario],
        screen_state: Optional[str] = None,
        floor: Optional[int] = None,
        act: Optional[int] = None
    ) -> List[Scenario]:
        """Filter scenarios by preconditions.

        Args:
            scenarios: List of scenarios to filter.
            screen_state: Required screen state.
            floor: Required floor.
            act: Required act.

        Returns:
            Filtered list of scenarios.
        """
        filtered = []
        for scenario in scenarios:
            pre = scenario.preconditions

            if screen_state and pre.get('screen_state') != screen_state:
                continue

            if floor is not None:
                pre_floor = pre.get('floor')
                if isinstance(pre_floor, dict):
                    if not (pre_floor.get('min', 0) <= floor <= pre_floor.get('max', 999)):
                        continue
                elif pre_floor != floor:
                    continue

            if act is not None and pre.get('act') != act:
                continue

            filtered.append(scenario)

        return filtered

    def create_scenario(self, **kwargs) -> Scenario:
        """Create a new scenario programmatically.

        Args:
            **kwargs: Scenario attributes.

        Returns:
            New Scenario instance.
        """
        return Scenario(**kwargs)

    def save_scenario(self, scenario: Scenario, output_path: str):
        """Save a scenario to a YAML file.

        Args:
            scenario: Scenario to save.
            output_path: Output file path.
        """
        data = {
            'name': scenario.name,
            'character': scenario.character,
            'ascension': scenario.ascension,
            'description': scenario.description,
            'tags': scenario.tags,
            'preconditions': scenario.preconditions,
            'steps': []
        }

        if scenario.seed is not None:
            data['seed'] = scenario.seed

        for step in scenario.steps:
            step_data = {
                'action': self._format_action(step.action_type, step.params)
            }
            if step.description:
                step_data['description'] = step.description
            data['steps'].append(step_data)

        with open(output_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @staticmethod
    def _format_action(action_type: str, params: dict) -> str:
        """Format action as string.

        Args:
            action_type: Type of action.
            params: Action parameters.

        Returns:
            Action string.
        """
        if action_type == 'play':
            card = params.get('card', 'Unknown')
            target = params.get('target')
            if target is not None:
                return f"play {card} {target}"
            return f"play {card}"

        elif action_type == 'choose':
            return f"choose {params.get('option', 0)}"

        elif action_type == 'potion':
            subaction = params.get('subaction', 'use')
            slot = params.get('slot', 0)
            target = params.get('target')
            if target is not None:
                return f"potion {subaction} {slot} {target}"
            return f"potion {subaction} {slot}"

        elif action_type == 'end':
            return "end"

        else:
            return f"{action_type} {params.get('value', '')}".strip()


def get_default_scenarios_dir() -> Path:
    """Get the default scenarios directory.

    Returns:
        Path to the scenarios directory.
    """
    return Path(__file__).parent.parent / 'scenarios'
