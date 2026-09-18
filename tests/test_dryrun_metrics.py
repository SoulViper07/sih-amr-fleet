"""Dry-run verification test for sim_runner and GET /api/metrics endpoint."""

import pytest
from fastapi.testclient import TestClient

from backend.api import app, collector as api_collector
from backend.metrics import get_collector
from scripts.sim_runner import main


def test_standalone_sim_runner_100_ticks():
    """Run standalone simulation for 100 ticks and verify non-zero, mathematically consistent metrics."""
    collector = get_collector()
    collector.reset()

    # Run simulation for 100 ticks at 0.01s tick delay
    main(max_ticks=100, tick_delay=0.01)

    snap = collector.get_snapshot()

    # 1. Verification of Non-zero metrics
    assert snap["total_ticks"] == 100
    assert snap["tasks_created"] > 0
    assert snap["total_path_plans"] > 0
    assert snap["total_planning_time_ms"] > 0.0
    assert snap["avg_planning_time_ms"] > 0.0
    assert snap["max_planning_time_ms"] > 0.0
    assert snap["active_agent_ticks"] > 0
    assert snap["fleet_utilization"] > 0.0

    # 2. Verification of Mathematical consistency
    assert snap["tasks_created"] >= snap["tasks_completed"] + snap["tasks_failed"]
    assert snap["total_path_plans"] >= snap["total_replans"]
    assert snap["total_replans"] >= snap["replans_due_to_conflict"] + snap["replans_due_to_deadlock"]
    assert snap["deadlocks_detected"] >= snap["deadlocks_resolved"]

    expected_utilization = round(
        (snap["active_agent_ticks"] / (snap["total_ticks"] * 6)) * 100.0, 2
    )
    assert snap["fleet_utilization"] == expected_utilization

    # 3. Verify GET /api/metrics returns valid JSON with non-zero metrics
    client = TestClient(app)
    response = client.get("/api/metrics")

    assert response.status_code == 200
    api_data = response.json()

    assert api_data["total_ticks"] == 100
    assert api_data["tasks_created"] > 0
    assert api_data["total_path_plans"] > 0
    assert api_data["fleet_utilization"] > 0.0
    assert api_data["avg_planning_time_ms"] > 0.0
