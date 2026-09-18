"""Unit and integration tests for FleetMetricsCollector and instrumented AMR simulation."""

import time
import pytest
from fastapi.testclient import TestClient

from backend.metrics import FleetMetricsCollector, get_collector
from backend.algorithms.time_space_astar import time_space_astar
from backend.agents.amr import AMRAgent
from backend.api import app, collector as api_collector


def test_collector_initial_state():
    """Verify collector starts with clean zeroed counters."""
    collector = FleetMetricsCollector()
    snap = collector.get_snapshot()

    assert snap["tasks_created"] == 0
    assert snap["tasks_completed"] == 0
    assert snap["tasks_failed"] == 0
    assert snap["task_success_rate"] == 0.0
    assert snap["total_task_duration_seconds"] == 0.0
    assert snap["avg_task_completion_time_seconds"] == 0.0

    assert snap["total_path_plans"] == 0
    assert snap["total_planning_time_ms"] == 0.0
    assert snap["avg_planning_time_ms"] == 0.0
    assert snap["max_planning_time_ms"] == 0.0
    assert snap["total_replans"] == 0
    assert snap["replans_due_to_conflict"] == 0
    assert snap["replans_due_to_deadlock"] == 0

    assert snap["proactive_conflicts_avoided"] == 0
    assert snap["reactive_stops_triggered"] == 0
    assert snap["deadlocks_detected"] == 0
    assert snap["deadlocks_resolved"] == 0

    assert snap["total_ticks"] == 0
    assert snap["active_agent_ticks"] == 0
    assert snap["idle_agent_ticks"] == 0
    assert snap["charging_agent_ticks"] == 0
    assert snap["fleet_utilization"] == 0.0


def test_collector_task_metrics():
    """Verify task recording, success rate, and duration averages."""
    collector = FleetMetricsCollector()

    collector.record_task_created()
    collector.record_task_created()
    collector.record_task_created()
    assert collector.get_snapshot()["tasks_created"] == 3

    collector.record_task_completed(duration=4.5)
    collector.record_task_completed(duration=5.5)

    snap = collector.get_snapshot()
    assert snap["tasks_completed"] == 2
    assert snap["total_task_duration_seconds"] == 10.0
    assert snap["avg_task_completion_time_seconds"] == 5.0
    assert snap["task_success_rate"] == 100.0

    collector.record_task_failed()
    snap = collector.get_snapshot()
    assert snap["tasks_failed"] == 1
    # 2 completed out of 3 finished = 66.67%
    assert snap["task_success_rate"] == 66.67


def test_collector_planning_metrics():
    """Verify planning step durations, max planning time, and replan counters."""
    collector = FleetMetricsCollector()

    collector.record_planning_step(duration_ms=12.0, is_replan=False)
    collector.record_planning_step(duration_ms=28.0, is_replan=True, reason="conflict")
    collector.record_planning_step(duration_ms=20.0, is_replan=True, reason="deadlock")

    snap = collector.get_snapshot()
    assert snap["total_path_plans"] == 3
    assert snap["total_planning_time_ms"] == 60.0
    assert snap["avg_planning_time_ms"] == 20.0
    assert snap["max_planning_time_ms"] == 28.0
    assert snap["total_replans"] == 2
    assert snap["replans_due_to_conflict"] == 1
    assert snap["replans_due_to_deadlock"] == 1


def test_collector_safety_and_deadlock_metrics():
    """Verify proactive avoidance, reactive stops, and deadlock detection/resolution."""
    collector = FleetMetricsCollector()

    collector.record_proactive_avoidance()
    collector.record_proactive_avoidance()
    collector.record_reactive_stop()
    collector.record_deadlock(resolved=False)
    collector.record_deadlock(resolved=True)

    snap = collector.get_snapshot()
    assert snap["proactive_conflicts_avoided"] == 2
    assert snap["reactive_stops_triggered"] == 1
    assert snap["deadlocks_detected"] == 1
    assert snap["deadlocks_resolved"] == 1


def test_collector_fleet_efficiency():
    """Verify tick accumulation and fleet utilization calculations."""
    collector = FleetMetricsCollector(num_agents=2)

    collector.record_clock_tick()
    collector.record_clock_tick()

    collector.record_agent_tick("AMR-1", "RUNNING")
    collector.record_agent_tick("AMR-2", "DOCKED")
    collector.record_agent_tick("AMR-1", "YIELDING")
    collector.record_agent_tick("AMR-2", "IDLE")

    snap = collector.get_snapshot()
    assert snap["total_ticks"] == 2
    assert snap["active_agent_ticks"] == 2
    assert snap["charging_agent_ticks"] == 1
    assert snap["idle_agent_ticks"] == 1

    # 2 active ticks / (2 ticks * 2 agents = 4 total capacity) = 50.0%
    assert snap["fleet_utilization"] == 50.0


def test_proactive_avoidance_in_time_space_astar():
    """Verify Time-Space A* invokes conflict_callback when dynamic reservations block a move."""
    collector = FleetMetricsCollector()

    # Dynamic reservation blocking (1, 0) at t=1 (vertex collision)
    dynamic_reservations = {1: {(1, 0)}}
    start = (0, 0)
    goal = (2, 0)

    path = time_space_astar(
        start=start,
        goal=goal,
        grid_width=5,
        grid_height=5,
        static_obstacles=set(),
        dynamic_reservations=dynamic_reservations,
        conflict_callback=collector.record_proactive_avoidance,
    )

    assert path is not None
    # Path found, and proactive avoidance was triggered when (1, 0) at t=1 was evaluated
    assert collector.proactive_conflicts_avoided > 0


def test_api_metrics_endpoint():
    """Verify GET /api/metrics returns the metrics snapshot."""
    client = TestClient(app)

    # Record some metrics into the singleton
    api_collector.record_task_created()
    api_collector.record_task_completed(2.5)

    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()

    assert "tasks_created" in data
    assert "tasks_completed" in data
    assert "tasks_failed" in data
    assert "task_success_rate" in data
    assert "fleet_utilization" in data
    assert data["tasks_completed"] >= 1
    assert data["task_success_rate"] > 0


def test_constant_memory_footprint():
    """Verify the collector does not retain unbounded collections."""
    collector = FleetMetricsCollector()

    # Simulate 1000 tasks and plans
    for i in range(1000):
        collector.record_task_created()
        collector.record_task_completed(duration=i * 0.01)
        collector.record_planning_step(duration_ms=1.5, is_replan=(i % 2 == 0))
        collector.record_agent_tick(f"AMR-{i % 6}", "RUNNING")

    snap = collector.get_snapshot()
    assert snap["tasks_created"] == 1000
    assert snap["tasks_completed"] == 1000

    # Ensure no list attributes exist on collector
    for attr_name, attr_val in collector.__dict__.items():
        if not attr_name.startswith("_"):
            assert not isinstance(attr_val, list), f"Attribute {attr_name} must not be a list!"
