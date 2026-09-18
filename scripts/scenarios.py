"""Benchmark evaluation scenarios for multi-agent AMR warehouse simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ScenarioConfig:
    """Configuration dataclass for repeatable benchmark evaluation scenarios.

    Attributes:
        name: Unique scenario identifier (e.g. 'normal', 'corridor_conflict').
        description: Human-readable description of the scenario and its objectives.
        grid_size: Tuple (width, height) specifying grid boundaries.
        obstacle_layout: List of (x, y) coordinates or callable generating obstacle coordinates.
        initial_robot_positions: Mapping of agent_id -> (x, y) starting coordinate.
        initial_robot_priorities: Mapping of agent_id -> priority integer (higher = higher priority).
        scripted_tasks: List of task specifications to inject at specific ticks.
            Format: [{"tick": int, "agent_id": str | None, "target": tuple[int, int] | None, "x": int, "y": int}]
        max_ticks: Recommended simulation duration for this benchmark.
        dynamic_task_interval: Tick interval for continuous dynamic task injection, or None for deterministic-only.
    """

    name: str
    description: str
    grid_size: tuple[int, int]
    obstacle_layout: list[tuple[int, int]] | Callable[[], list[tuple[int, int]]]
    initial_robot_positions: dict[str, tuple[int, int]]
    initial_robot_priorities: dict[str, int]
    scripted_tasks: list[dict[str, Any]] = field(default_factory=list)
    scripted_failures: list[dict[str, Any]] = field(default_factory=list)
    max_ticks: int = 100
    dynamic_task_interval: int | None = None

    def get_obstacles(self) -> list[tuple[int, int]]:
        """Return obstacle coordinates as a concrete list of (x, y) tuples."""
        if callable(self.obstacle_layout):
            return list(self.obstacle_layout())
        return list(self.obstacle_layout)

    def get_obstacles_set(self) -> set[tuple[int, int]]:
        """Return obstacle coordinates as a set for O(1) membership checks."""
        return set(self.get_obstacles())

    def get_valid_positions(self) -> list[tuple[int, int]]:
        """Return all non-obstacle coordinates within grid bounds."""
        obs = self.get_obstacles_set()
        w, h = self.grid_size
        return [(x, y) for x in range(w) for y in range(h) if (x, y) not in obs]

    def get_tasks_for_tick(self, tick: int) -> list[dict[str, Any]]:
        """Retrieve any scripted tasks scheduled to be injected at the specified tick."""
        return [t for t in self.scripted_tasks if t.get("tick") == tick]

    def get_failures_for_tick(self, tick: int) -> list[dict[str, Any]]:
        """Retrieve any scripted failure events scheduled for the specified tick."""
        return [f for f in self.scripted_failures if f.get("tick") == tick]


def _build_standard_racks() -> list[tuple[int, int]]:
    """Generate 152 standard rack obstacles (4 double-column racks of height 19)."""
    obstacles: list[tuple[int, int]] = []
    for rack_x in (4, 5, 10, 11, 16, 17, 22, 23):
        for y in range(6, 25):
            obstacles.append((rack_x, y))
    return obstacles


def _create_normal_scenario() -> ScenarioConfig:
    """Scenario 1: Standard warehouse (30x30, 152 racks, 6 AMRs, continuous random tasks)."""
    return ScenarioConfig(
        name="normal",
        description="Standard warehouse simulation (30x30, 152 racks, 6 AMRs, continuous random task generation)",
        grid_size=(30, 30),
        obstacle_layout=_build_standard_racks,
        initial_robot_positions={
            "AMR-1": (0, 0),
            "AMR-2": (0, 29),
            "AMR-3": (29, 0),
            "AMR-4": (29, 29),
            "AMR-5": (14, 0),
            "AMR-6": (14, 29),
        },
        initial_robot_priorities={
            "AMR-1": 6,
            "AMR-2": 5,
            "AMR-3": 4,
            "AMR-4": 3,
            "AMR-5": 2,
            "AMR-6": 1,
        },
        scripted_tasks=[],
        max_ticks=100,
        dynamic_task_interval=15,
    )


def _create_high_traffic_scenario() -> ScenarioConfig:
    """Scenario 2: High-traffic warehouse (task injection interval = 2 ticks to saturate fleet)."""
    initial_tasks = [
        {"tick": 0, "target": (7, 15)},
        {"tick": 0, "target": (13, 15)},
        {"tick": 0, "target": (19, 15)},
        {"tick": 0, "target": (25, 15)},
    ]
    return ScenarioConfig(
        name="high_traffic",
        description="High-traffic warehouse benchmark with task injection every 2 ticks, saturating all agents simultaneously",
        grid_size=(30, 30),
        obstacle_layout=_build_standard_racks,
        initial_robot_positions={
            "AMR-1": (0, 0),
            "AMR-2": (0, 29),
            "AMR-3": (29, 0),
            "AMR-4": (29, 29),
            "AMR-5": (14, 0),
            "AMR-6": (14, 29),
        },
        initial_robot_priorities={
            "AMR-1": 6,
            "AMR-2": 5,
            "AMR-3": 4,
            "AMR-4": 3,
            "AMR-5": 2,
            "AMR-6": 1,
        },
        scripted_tasks=initial_tasks,
        max_ticks=100,
        dynamic_task_interval=2,
    )


def _build_corridor_obstacles() -> list[tuple[int, int]]:
    """Build narrow 1-cell corridor layout (width 12, height 5) with sidings at (4, 3) and (7, 3)."""
    obstacles: set[tuple[int, int]] = set()
    # Outer bounding walls
    for x in range(12):
        obstacles.add((x, 0))
        obstacles.add((x, 4))
    obstacles.add((0, 2))
    obstacles.add((11, 2))
    # Bottom wall bordering corridor
    for x in range(1, 11):
        obstacles.add((x, 1))
    # Top wall bordering corridor, leaving sidings at (4, 3) and (7, 3)
    for x in range(1, 11):
        if x not in (4, 7):
            obstacles.add((x, 3))
    return sorted(list(obstacles))


def _create_corridor_conflict_scenario() -> ScenarioConfig:
    """Scenario 3: Narrow corridor conflict (length 10 cells, width 1) forcing head-on opposition."""
    return ScenarioConfig(
        name="corridor_conflict",
        description="Narrow corridor confrontation testing Time-Space A* proactive avoidance or Layer 2 reactive stop/yield",
        grid_size=(12, 5),
        obstacle_layout=_build_corridor_obstacles,
        initial_robot_positions={
            "AMR-1": (1, 2),
            "AMR-2": (10, 2),
        },
        initial_robot_priorities={
            "AMR-1": 2,
            "AMR-2": 1,
        },
        scripted_tasks=[
            {"tick": 0, "agent_id": "AMR-1", "target": (10, 2)},
            {"tick": 1, "agent_id": "AMR-2", "target": (1, 2)},
        ],
        max_ticks=80,
        dynamic_task_interval=None,
    )


def _build_deadlock_obstacles() -> list[tuple[int, int]]:
    """Build constrained channel layout (width 10, height 5) with detour bypass bay at row 3 (x=3..6)."""
    obstacles: set[tuple[int, int]] = set()
    # Outer bounding walls
    for x in range(10):
        obstacles.add((x, 0))
        obstacles.add((x, 4))
    for y in range(5):
        obstacles.add((0, y))
        obstacles.add((9, y))
    # Row 1 is a solid barrier
    for x in range(1, 9):
        obstacles.add((x, 1))
    # Row 3 is blocked except for detour bay bypass cells (x in 3..6)
    for x in (1, 2, 7, 8):
        obstacles.add((x, 3))
    return sorted(list(obstacles))


def _create_deadlock_livelock_scenario() -> ScenarioConfig:
    """Scenario 4: Head-on confrontation in channel triggering 3-6 tick backoff and obstacle-masking detour replan."""
    return ScenarioConfig(
        name="deadlock_livelock",
        description="Head-on deadlock confrontation triggering randomized backoff and obstacle-masking detour replanning",
        grid_size=(10, 5),
        obstacle_layout=_build_deadlock_obstacles,
        initial_robot_positions={
            "AMR-1": (4, 2),
            "AMR-2": (5, 2),
        },
        initial_robot_priorities={
            "AMR-1": 2,
            "AMR-2": 1,
        },
        scripted_tasks=[
            {"tick": 0, "agent_id": "AMR-1", "target": (7, 2)},
            {"tick": 0, "agent_id": "AMR-2", "target": (2, 2)},
        ],
        max_ticks=100,
        dynamic_task_interval=None,
    )


def _create_robot_failure_scenario() -> ScenarioConfig:
    """Scenario 5: Fault-tolerance benchmark (30x30, 4 AMRs, silent failure of AMR-2 at tick 20 mid-route)."""
    return ScenarioConfig(
        name="robot_failure",
        description="Fault-tolerance benchmark: AMR-2 silent crash at tick 20 mid-route; peers detect within 5 ticks, isolate stranded AMR, route around obstacle, and complete re-auctioned task",
        grid_size=(30, 30),
        obstacle_layout=_build_standard_racks,
        initial_robot_positions={
            "AMR-1": (0, 0),
            "AMR-2": (0, 29),
            "AMR-3": (29, 0),
            "AMR-4": (29, 29),
        },
        initial_robot_priorities={
            "AMR-1": 4,
            "AMR-2": 3,
            "AMR-3": 2,
            "AMR-4": 1,
        },
        scripted_tasks=[
            {"tick": 0, "agent_id": "AMR-2", "target": (0, 5)},
            {"tick": 0, "agent_id": "AMR-3", "target": (29, 10)},
            {"tick": 0, "agent_id": "AMR-4", "target": (15, 29)},
            {"tick": 32, "target": (0, 20)},
        ],
        scripted_failures=[
            {"tick": 20, "agent_id": "AMR-2"},
        ],
        max_ticks=60,
        dynamic_task_interval=None,
    )


class ScenarioManager:
    """Central registry and manager for evaluation benchmark scenarios."""

    _scenarios: dict[str, ScenarioConfig] = {}

    @classmethod
    def register(cls, config: ScenarioConfig) -> None:
        """Register a scenario configuration."""
        cls._scenarios[config.name] = config

    @classmethod
    def get_scenario(cls, name: str) -> ScenarioConfig:
        """Retrieve a registered scenario by name.

        Args:
            name: Scenario identifier.

        Returns:
            ScenarioConfig instance.

        Raises:
            KeyError: If scenario name is not registered.
        """
        if name not in cls._scenarios:
            available = ", ".join(cls.list_scenarios())
            raise KeyError(f"Unknown scenario '{name}'. Available scenarios: {available}")
        return cls._scenarios[name]

    @classmethod
    def list_scenarios(cls) -> list[str]:
        """Return list of all registered scenario names."""
        return list(cls._scenarios.keys())

    @classmethod
    def reset_registry(cls) -> None:
        """Reset registry and re-register standard scenarios."""
        cls._scenarios.clear()
        cls.register(_create_normal_scenario())
        cls.register(_create_high_traffic_scenario())
        cls.register(_create_corridor_conflict_scenario())
        cls.register(_create_deadlock_livelock_scenario())
        cls.register(_create_robot_failure_scenario())


# Initialize default registry
ScenarioManager.reset_registry()
