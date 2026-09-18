"""Scenario test suite for repeatable evaluation benchmarks in AMR fleet simulation."""

import json
from pathlib import Path
import pytest

from backend.metrics import FleetMetricsCollector
from backend.world.grid import WarehouseGrid
from scripts.scenarios import ScenarioManager
from scripts.sim_runner import main


def test_scenario_initialization():
    """Verify that all 5 registered scenarios initialize with valid configurations and bounds."""
    scenario_names = ["normal", "high_traffic", "corridor_conflict", "deadlock_livelock", "robot_failure"]

    for name in scenario_names:
        cfg = ScenarioManager.get_scenario(name)
        assert cfg.name == name
        assert len(cfg.description) > 0

        w, h = cfg.grid_size
        assert w > 0 and h > 0

        obstacles = cfg.get_obstacles()
        obs_set = cfg.get_obstacles_set()
        assert len(obstacles) == len(obs_set), f"Duplicate obstacles detected in scenario '{name}'"

        # Check all obstacles are strictly within grid bounds
        for ox, oy in obstacles:
            assert 0 <= ox < w and 0 <= oy < h, f"Obstacle ({ox}, {oy}) out of bounds in scenario '{name}'"

        # Check all robot positions are valid within bounds and non-colliding with static obstacles
        assert len(cfg.initial_robot_positions) > 0
        for agent_id, (rx, ry) in cfg.initial_robot_positions.items():
            assert 0 <= rx < w and 0 <= ry < h, f"Robot '{agent_id}' at ({rx}, {ry}) out of bounds in '{name}'"
            assert (rx, ry) not in obs_set, f"Robot '{agent_id}' spawned on an obstacle at ({rx}, {ry}) in '{name}'"
            priority = cfg.initial_robot_priorities.get(agent_id)
            assert priority is not None and priority > 0, f"Robot '{agent_id}' missing positive priority in '{name}'"

        # Check all scripted tasks are valid within bounds and non-obstacle
        for task in cfg.scripted_tasks:
            target = task.get("target") or (task.get("x"), task.get("y"))
            if target:
                tx, ty = target
                assert 0 <= tx < w and 0 <= ty < h, f"Task target ({tx}, {ty}) out of bounds in '{name}'"
                assert (tx, ty) not in obs_set, f"Task target on obstacle at ({tx}, {ty}) in '{name}'"

        # Verify WarehouseGrid instantiates cleanly without exceptions
        grid = WarehouseGrid(width=w, height=h, obstacles=obstacles)
        assert grid.width == w
        assert grid.height == h


def test_corridor_conflict_60_ticks():
    """Run corridor_conflict scenario for 60 ticks and assert proactive avoidance or reactive stops."""
    collector = FleetMetricsCollector()
    collector.reset()

    snap = main(
        max_ticks=60,
        tick_delay=0.01,
        scenario="corridor_conflict",
        collector=collector,
    )

    assert snap["total_ticks"] == 60
    assert snap["total_path_plans"] > 0
    # Assertion requirement: proactive_conflicts_avoided > 0 OR reactive_stops_triggered > 0
    assert (
        snap["proactive_conflicts_avoided"] > 0 or snap["reactive_stops_triggered"] > 0
    ), f"Expected conflict resolution in corridor_conflict! Got: {snap}"


def test_deadlock_livelock_100_ticks():
    """Run deadlock_livelock scenario for 100 ticks and assert backoff and detour replanning execute without grid lockups."""
    collector = FleetMetricsCollector()
    collector.reset()

    snap = main(
        max_ticks=100,
        tick_delay=0.01,
        scenario="deadlock_livelock",
        collector=collector,
    )

    assert snap["total_ticks"] == 100
    assert snap["total_path_plans"] > 0
    assert snap["reactive_stops_triggered"] > 0, "Expected reactive stops in deadlock scenario"
    assert snap["deadlocks_detected"] > 0, "Expected deadlock detection to trigger after backoff threshold"
    assert (
        snap["deadlocks_resolved"] > 0 or snap["replans_due_to_deadlock"] > 0
    ), "Expected deadlock resolution or detour replanning to clear obstruction"


def test_high_traffic_scenario_saturation():
    """Run high_traffic scenario for 30 ticks and verify rapid task injection and high fleet activity."""
    collector = FleetMetricsCollector()
    collector.reset()

    snap = main(
        max_ticks=30,
        tick_delay=0.01,
        scenario="high_traffic",
        collector=collector,
    )

    assert snap["total_ticks"] == 30
    assert snap["tasks_created"] >= 15, "Expected frequent task injection in high_traffic scenario"
    assert snap["total_path_plans"] > 0
    assert snap["active_agent_ticks"] > 0


def test_export_metrics_flag(tmp_path: Path):
    """Verify --export-metrics writes the snapshot JSON file matching collector output."""
    collector = FleetMetricsCollector()
    collector.reset()

    export_file = tmp_path / "metrics_export.json"

    snap = main(
        max_ticks=20,
        tick_delay=0.01,
        scenario="corridor_conflict",
        export_metrics=str(export_file),
        collector=collector,
    )

    assert export_file.exists(), "Exported metrics file does not exist"
    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_ticks"] == 20
    assert data["tasks_created"] == snap["tasks_created"]
    assert data["total_path_plans"] == snap["total_path_plans"]


def test_robot_failure_scenario():
    """Run robot_failure scenario for 60 ticks; assert silent failure detection and task reassignment."""
    collector = FleetMetricsCollector()
    collector.reset()

    snap = main(
        max_ticks=60,
        tick_delay=0.01,
        scenario="robot_failure",
        collector=collector,
    )

    assert snap["total_ticks"] == 60
    assert snap["silent_failures_detected"] >= 1, f"Expected silent failure detected, got {snap}"
    assert snap["tasks_reassigned"] >= 1, f"Expected task reassignment, got {snap}"
    assert snap["tasks_completed"] >= 1, f"Expected completed tasks, got {snap}"
