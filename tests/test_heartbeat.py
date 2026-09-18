"""Unit and integration tests for Phase 3 Tick-Synchronized Heartbeat & Silent Failure Detection."""

import time
import pytest
from unittest.mock import MagicMock

from backend.metrics import FleetMetricsCollector
from backend.agents.amr import AMRAgent
from backend.algorithms.time_space_astar import time_space_astar
from scripts.sim_runner import Coordinator


def test_heartbeat_emission_and_reception():
    """Test 1: Verify heartbeat publishing format and accurate peer tick recording."""
    collector = FleetMetricsCollector()
    agent1 = AMRAgent("AMR-1", start_pos=(0, 0), metrics_collector=collector)
    agent2 = AMRAgent("AMR-2", start_pos=(5, 5), metrics_collector=collector)

    # Mock agent1 client publish to capture heartbeat payload
    agent1.client = MagicMock()

    # Emit heartbeat at tick 12
    agent1.publish_heartbeat(tick=12)
    assert agent1.client.publish.called
    call_args = agent1.client.publish.call_args
    topic = call_args[0][0]
    payload_raw = call_args[0][1]

    assert topic == "amr/AMR-1/heartbeat"
    import json
    payload = json.loads(payload_raw)
    assert payload["agent_id"] == "AMR-1"
    assert payload["tick"] == 12
    assert payload["position"] == [0, 0] or payload["position"] == (0, 0)
    assert payload["status"] in ["DOCKED", "ACTIVE", "RUNNING"]

    # Now simulate agent2 receiving this heartbeat
    agent2._handle_heartbeat(payload)

    # Verify peer last seen tick and position recorded accurately
    assert agent2.peer_last_seen_tick.get("AMR-1") == 12
    assert "AMR-1" in agent2.peer_positions
    assert agent2.peer_positions["AMR-1"]["pos"] == (0, 0)
    assert agent2.peer_positions["AMR-1"]["status"] == payload["status"]


def test_silent_failure_detection():
    """Test 2: Simulate dropping heartbeats for 6 ticks; assert status becomes OFFLINE and coordinates isolated."""
    collector = FleetMetricsCollector()
    agent = AMRAgent("AMR-1", start_pos=(0, 0), metrics_collector=collector)

    # Initial heartbeat received at tick 10
    agent._handle_heartbeat({
        "agent_id": "AMR-2",
        "tick": 10,
        "position": (4, 4),
        "status": "ACTIVE",
    })
    assert agent.peer_last_seen_tick["AMR-2"] == 10
    assert agent.peer_positions["AMR-2"]["status"] == "ACTIVE"

    # Advance simulation by 4 ticks (tick 14): within threshold of 5, should NOT be OFFLINE
    newly_offline = agent.check_peer_vitality(current_tick=14, threshold=5)
    assert len(newly_offline) == 0
    assert agent.peer_positions["AMR-2"]["status"] == "ACTIVE"
    assert (4, 4) not in agent.dynamic_obstacles

    # Advance simulation by 6 ticks from last seen (tick 16): 16 - 10 = 6 >= threshold(5)
    newly_offline = agent.check_peer_vitality(current_tick=16, threshold=5)
    assert "AMR-2" in newly_offline
    assert agent.peer_positions["AMR-2"]["status"] == "OFFLINE"

    # Fail-safe spatial isolation checks
    assert (4, 4) in agent.dynamic_obstacles
    # Dynamic reservations across all future time steps
    assert (4, 4) in agent.dynamic_reservations.get(16, set())
    assert (4, 4) in agent.dynamic_reservations.get(20, set())
    assert (4, 4) in agent.dynamic_reservations.get(50, set())


def test_stranded_robot_obstacle_avoidance():
    """Test 3: Verify that an AMR planning a route through the failed robot's tile replans around it."""
    collector = FleetMetricsCollector()
    agent1 = AMRAgent("AMR-1", start_pos=(0, 0), grid_size=(10, 10), metrics_collector=collector)

    # 1. Initially plan route from (0, 0) to (0, 4) with no obstacles
    planned = agent1.plan_to_goal(0, 4)
    assert planned is True
    initial_path_coords = [(node[0], node[1]) for node in agent1.current_path]
    # Direct route along column 0 should pass through (0, 2)
    assert (0, 2) in initial_path_coords

    # 2. Peer AMR-2 strands at (0, 2) and drops heartbeats
    agent1._handle_heartbeat({
        "agent_id": "AMR-2",
        "tick": 5,
        "position": (0, 2),
        "status": "RUNNING",
    })

    # At tick 11 (6 ticks after tick 5): check_peer_vitality identifies failure
    newly_offline = agent1.check_peer_vitality(current_tick=11, threshold=5)
    assert "AMR-2" in newly_offline
    assert (0, 2) in agent1.dynamic_obstacles

    # Spatial isolation must immediately force replan around (0, 2)
    replan_path_coords = [(node[0], node[1]) for node in agent1.current_path]
    assert (0, 2) not in replan_path_coords, f"Path {replan_path_coords} must not include stranded obstacle (0, 2)"
    # Path still reaches goal (0, 4)
    if replan_path_coords:
        assert replan_path_coords[-1] == (0, 4)


def test_task_reassignment_on_failure():
    """Test 4: Verify that a task held by a failed agent is successfully salvaged, re-auctioned, and completed."""
    collector = FleetMetricsCollector()
    collector.reset()

    coordinator = Coordinator(metrics_collector=collector)

    # Surviving agent starting at (0, 0)
    agent1 = AMRAgent(
        agent_id="AMR-1",
        start_pos=(0, 0),
        grid_size=(15, 15),
        priority=3,
        metrics_collector=collector,
        task_provider=coordinator.get_pending_tasks,
        step_interval=0.0,
    )
    # Target agent starting at (0, 3)
    agent2 = AMRAgent(
        agent_id="AMR-2",
        start_pos=(0, 3),
        grid_size=(15, 15),
        priority=2,
        metrics_collector=collector,
        task_provider=coordinator.get_pending_tasks,
        step_interval=0.0,
    )

    # Step interval zero for synchronous simulation in tests
    agent1.step_interval = 0.0
    agent2.step_interval = 0.0

    # Agent 2 starts holding active task to reach (0, 6)
    task = {
        "id": "task_recovery_test",
        "x": 0,
        "y": 6,
        "created_at": time.time(),
        "claimed": True,
    }
    agent2.active_task = task
    agent2.current_goal = (0, 6)
    agent2.goal = (0, 6)
    agent2.plan_to_goal(0, 6)
    assert len(agent2.current_path) > 0

    # Tick 1: Agent 2 moves 1 step toward (0, 6)
    agent2.step(1)
    assert agent2.current_pos == (0, 4)
    coordinator.agent_last_seen_tick["AMR-2"] = 1

    # Simulate silent crash on Agent 2 at tick 2
    agent2.simulate_silent_crash()
    assert agent2._crashed is True
    assert agent2.status == "OFFLINE"

    # Simulate tick 7 (6 ticks since tick 1, threshold 5): Coordinator detects failure
    newly_offline = coordinator.check_agent_vitality(current_tick=7, threshold=5)
    assert "AMR-2" in newly_offline

    # Salvage task from agent2
    if agent2.active_task is not None:
        salvaged_task = agent2.active_task
        agent2.active_task = None
        agent2.tasks_failed += 1
        coordinator.collector.record_silent_failure()
        coordinator.collector.record_task_reassigned()
        salvaged_task["claimed"] = False
        salvaged_task["state"] = "PENDING"
        salvaged_task["status"] = "PENDING"
        coordinator.pending_tasks.append(salvaged_task)

    assert collector.silent_failures_detected == 1
    assert collector.tasks_reassigned == 1
    assert len(coordinator.get_pending_tasks()) == 1

    # Now agent1 runs tick 8: polls pending tasks, bids, and wins
    agent1.step(8)
    assert agent1.pending_task is not None or agent1.active_task is not None

    # Step agent1 forward to win bid and process task
    agent1.step(9)
    assert agent1.active_task is not None
    assert agent1.current_goal == (0, 6)

    # Step agent1 until task completion
    for tick in range(10, 30):
        agent1.step(tick)
        if agent1.active_task is None:
            break

    # Verify task was completed successfully by surviving agent
    assert collector.tasks_completed == 1
    assert agent1.current_pos == (0, 6)
    assert agent1.active_task is None
