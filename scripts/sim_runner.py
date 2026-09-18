#!/usr/bin/env python3
"""Simulation runner for multi-robot warehouse simulation and benchmark scenarios."""

import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import json
import logging
import os
import random
import threading
import time
import uuid
from typing import TYPE_CHECKING, Any

import paho.mqtt.client as mqtt
import requests

if TYPE_CHECKING:
    from backend.world.grid import WarehouseGrid
    from backend.agents.amr import AMRAgent

from backend.agents.amr import AMRAgent
from backend.metrics import FleetMetricsCollector, get_collector
from backend.world.grid import WarehouseGrid
from scripts.scenarios import ScenarioConfig, ScenarioManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", 1883))
GRID_SIZE = (30, 30)

# Warehouse config matching backend
WAREHOUSE_CONFIG = {
    "grid_size": [30, 30],
    "racks": {
        "rack_1": [(x, y) for x in range(4, 6) for y in range(6, 25)],
        "rack_2": [(x, y) for x in range(10, 12) for y in range(6, 25)],
        "rack_3": [(x, y) for x in range(16, 18) for y in range(6, 25)],
        "rack_4": [(x, y) for x in range(22, 24) for y in range(6, 25)],
    },
    "charging_stations": [(0, 0), (0, 29), (29, 0), (29, 29), (14, 0), (14, 29)],
    "workstations": [(2, 29), (14, 29), (27, 29)],
}

OBSTACLES = []
for rack_coords in WAREHOUSE_CONFIG["racks"].values():
    OBSTACLES.extend(rack_coords)

OBSTACLES_SET = set(OBSTACLES)

# Valid spawn positions (charging stations + workstations)
SPAWN_POSITIONS = [
    (0, 0),
    (0, 29),
    (29, 0),
    (29, 29),
    (14, 0),
    (14, 29),
    (2, 29),
    (27, 29),
]

# Docked positions for 6 AMRs (distributed charging stations)
DOCKED_POSITIONS = [
    (0, 0),
    (0, 29),
    (29, 0),
    (29, 29),
    (14, 0),
    (14, 29),
]

# All valid positions (not in obstacles)
VALID_POSITIONS = [(x, y) for x in range(GRID_SIZE[0]) for y in range(GRID_SIZE[1]) if (x, y) not in OBSTACLES_SET]


class Coordinator:
    """Coordinates the simulation by publishing clock ticks, injecting tasks, and collecting telemetry."""

    def __init__(
        self,
        metrics_collector: FleetMetricsCollector | None = None,
        valid_positions: list[tuple[int, int]] | None = None,
    ) -> None:
        self.collector = metrics_collector if metrics_collector is not None else get_collector()
        self.valid_positions = valid_positions if valid_positions is not None else VALID_POSITIONS
        self.client = mqtt.Client(client_id=f"coordinator_{uuid.uuid4().hex[:8]}", clean_session=True)
        self.client.on_message = self._on_message
        self.live_positions: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.agent_goals: dict[str, tuple[int, int] | None] = {}
        self.agent_arrival_time: dict[str, int] = {}
        self.pending_tasks: list[dict] = []
        self._agent_ticks: dict[str, int] = {}
        self.agent_last_seen_tick: dict[str, int] = {}
        self.offline_agents: set[str] = set()
        self._backend_available: bool | None = None

    def connect(self) -> None:
        """Connect to MQTT broker and subscribe to telemetry, bids, and heartbeats."""
        self.client.connect(BROKER, PORT, keepalive=60)
        self.client.subscribe("fleet/telemetry", qos=1)
        self.client.subscribe("fleet/bids", qos=1)
        self.client.subscribe("amr/+/heartbeat", qos=1)
        self.client.loop_start()
        logger.info("Coordinator connected and subscribed to fleet/telemetry, fleet/bids, and amr/+/heartbeat")

    def disconnect(self) -> None:
        """Disconnect from broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        """Store incoming telemetry, track contract net protocol bids, and record heartbeat ticks."""
        try:
            payload = json.loads(msg.payload.decode())
            if msg.topic == "fleet/telemetry":
                agent_id = payload.get("agent_id")
                if agent_id:
                    with self._lock:
                        self.live_positions[agent_id] = payload
                        tick_time = payload.get("time")
                        if tick_time is not None:
                            self._agent_ticks[agent_id] = tick_time
            elif msg.topic == "fleet/bids":
                sender_id = payload.get("sender_id")
                task_data = payload.get("task", {})
                task_id = task_data.get("id", "unknown")
                bid_cost = payload.get("bid_cost")
                logger.info(f"CNP Bid: Agent {sender_id} placed bid {bid_cost} for task {task_id}")
            elif msg.topic.startswith("amr/") and msg.topic.endswith("/heartbeat"):
                agent_id = payload.get("agent_id")
                tick = payload.get("tick")
                if agent_id and tick is not None:
                    with self._lock:
                        self.agent_last_seen_tick[agent_id] = tick
                        self._agent_ticks[agent_id] = tick
                        if agent_id in self.live_positions and payload.get("status"):
                            self.live_positions[agent_id]["status"] = payload["status"]
        except json.JSONDecodeError:
            pass

    def check_agent_vitality(self, current_tick: int, threshold: int = 5) -> list[str]:
        """Detect agents that have missed heartbeats for >= threshold ticks."""
        newly_offline = []
        with self._lock:
            for agent_id, last_tick in list(self.agent_last_seen_tick.items()):
                if agent_id not in self.offline_agents and (current_tick - last_tick) >= threshold:
                    self.offline_agents.add(agent_id)
                    newly_offline.append(agent_id)
                    if agent_id in self.live_positions:
                        self.live_positions[agent_id]["status"] = "OFFLINE"
        return newly_offline

    def dispatch_agent(
        self,
        agent_id: str,
        target: tuple[int, int],
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch a specific agent directly to target coordinates."""
        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:6]}"
        now = time.time()
        self.collector.record_task_created()
        payload = {"x": target[0], "y": target[1], "task_id": task_id, "created_at": now}
        self.client.publish(f"fleet/dispatch/{agent_id}", json.dumps(payload), qos=1)
        logger.info(f"Dispatched {agent_id} to {target} (task: {task_id})")
        return payload

    def inject_task(self, target: tuple[int, int] | None = None) -> dict:
        """Inject a warehouse task for AMR agents to bid on."""
        if target is None:
            target = random.choice(self.valid_positions)

        task_id = f"task_{uuid.uuid4().hex[:6]}"
        now = time.time()
        task = {
            "id": task_id,
            "x": target[0],
            "y": target[1],
            "created_at": now,
            "claimed": False,
        }

        self.collector.record_task_created()
        with self._lock:
            self.pending_tasks.append(task)

        # Broadcast or post task to FastAPI backend if explicitly enabled
        if os.getenv("ENABLE_BACKEND_HTTP", "0") == "1" and self._backend_available is not False:
            try:
                requests.post(
                    "http://localhost:8000/api/tasks",
                    json={"x": target[0], "y": target[1]},
                    timeout=0.2,
                )
                self._backend_available = True
            except Exception:
                self._backend_available = False

        logger.info(f"Task {task_id} injected at {target}")
        return task

    def get_pending_tasks(self) -> list[dict]:
        """Return unclaimed tasks for local bidding fallback."""
        with self._lock:
            return [t for t in self.pending_tasks if not t.get("claimed", False)]

    def publish_clock(self, t: int) -> None:
        """Publish a clock tick and sync metrics."""
        self.collector.record_clock_tick()
        self.client.publish("fleet/clock", json.dumps({"time": t}), qos=1)
        # Periodically publish metrics snapshot over MQTT
        if t % 2 == 0:
            self.client.publish(
                "fleet/metrics",
                json.dumps(self.collector.get_snapshot()),
                qos=1,
            )

    def wait_for_agents(self, t: int, expected_agents: set[str], timeout: float = 0.05) -> None:
        """Wait until all expected agents have processed tick t or timeout expires."""
        if not expected_agents:
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if all(self._agent_ticks.get(a, -1) >= t for a in expected_agents):
                    return
            time.sleep(0.001)

    def get_positions(self) -> dict[str, dict]:
        """Get a copy of current positions."""
        with self._lock:
            return dict(self.live_positions)

    def assign_random_goal(self, agent_id: str, current_pos: tuple[int, int]) -> tuple[int, int]:
        """Assign a random valid goal position."""
        possible_goals = [pos for pos in self.valid_positions if pos != current_pos]
        if not possible_goals:
            return current_pos
        return random.choice(possible_goals)


def main(
    max_ticks: int | None = None,
    tick_delay: float = 0.5,
    scenario: str = "normal",
    export_metrics: str | None = None,
    collector: FleetMetricsCollector | None = None,
) -> dict[str, Any]:
    """Execute multi-agent AMR simulation for the given scenario configuration.

    Args:
        max_ticks: Optional maximum ticks to run (defaults to scenario max_ticks if set, or indefinite for normal).
        tick_delay: Delay between ticks in seconds (0 for headless max-speed mode).
        scenario: Name of registered benchmark scenario ("normal", "high_traffic", "corridor_conflict", "deadlock_livelock").
        export_metrics: Optional file path to export final metrics snapshot as JSON.
        collector: Optional metrics collector instance (defaults to global singleton).

    Returns:
        Dictionary snapshot of final metrics.
    """
    scenario_cfg = ScenarioManager.get_scenario(scenario)

    if max_ticks is None and scenario != "normal":
        max_ticks = scenario_cfg.max_ticks

    logger.info("=" * 60)
    logger.info(f"Starting Multi-Robot Scenario: {scenario_cfg.name}")
    logger.info(f"Description: {scenario_cfg.description}")
    logger.info(
        f"Grid: {scenario_cfg.grid_size[0]}x{scenario_cfg.grid_size[1]} | "
        f"Robots: {len(scenario_cfg.initial_robot_positions)} | "
        f"Max Ticks: {max_ticks}"
    )
    logger.info("=" * 60)

    # Create grid
    grid_size = scenario_cfg.grid_size
    obstacles = scenario_cfg.get_obstacles()
    obstacles_set = scenario_cfg.get_obstacles_set()
    grid = WarehouseGrid(width=grid_size[0], height=grid_size[1], obstacles=obstacles)
    logger.info(f"Grid created: {grid_size[0]}x{grid_size[1]} with {len(obstacles)} obstacles")

    # Create coordinator with shared metrics collector
    coordinator = Coordinator(
        metrics_collector=collector,
        valid_positions=scenario_cfg.get_valid_positions(),
    )
    coordinator.connect()

    # Step interval governor: allow tick-speed movement when tick_delay == 0
    step_interval = 0.0 if tick_delay == 0 else min(0.45, tick_delay)

    # Create agents according to scenario configuration
    agents: list[AMRAgent] = []
    for agent_id, start_pos in scenario_cfg.initial_robot_positions.items():
        priority = scenario_cfg.initial_robot_priorities.get(agent_id, 1)
        agent = AMRAgent(
            agent_id=agent_id,
            start_pos=start_pos,
            grid_size=grid_size,
            obstacles=obstacles_set,
            priority=priority,
            metrics_collector=coordinator.collector,
            task_provider=coordinator.get_pending_tasks,
            step_interval=step_interval,
        )
        agents.append(agent)

    # Connect agents to broker
    logger.info("Connecting agents to broker...")
    for agent in agents:
        agent.connect(BROKER, PORT)
    time.sleep(0.05)  # Allow MQTT subscriptions to establish

    # Publish initial telemetry and heartbeats so peer robots register start coordinates and vitality
    for agent in agents:
        agent.publish_telemetry()
        agent.publish_heartbeat(0)
        coordinator.agent_last_seen_tick[agent.agent_id] = 0
    time.sleep(0.05)  # Allow initial broadcast to be processed

    expected_agent_ids = {agent.agent_id for agent in agents}

    logger.info("Starting simulation loop")
    logger.info("-" * 60)

    # If normal scenario with no scripted tasks, inject initial task
    if scenario == "normal" and not scenario_cfg.scripted_tasks:
        coordinator.inject_task()

    # Simulation loop
    t = 0
    try:
        while True:
            if max_ticks is not None and t >= max_ticks:
                logger.info(f"Reached max ticks ({max_ticks}), terminating simulation loop")
                break

            # 0. Check scripted failure events for this tick
            failures_to_trigger = []
            if hasattr(scenario_cfg, "get_failures_for_tick"):
                failures_to_trigger = scenario_cfg.get_failures_for_tick(t)
            elif scenario == "robot_failure" and t == 20:
                failures_to_trigger = [{"tick": 20, "agent_id": "AMR-2"}]

            for fail_spec in failures_to_trigger:
                fail_id = fail_spec.get("agent_id")
                for ag in agents:
                    if ag.agent_id == fail_id and not ag._crashed:
                        logger.warning(f"[Fault-Tolerance] Simulating silent crash for {fail_id} at tick {t}")
                        ag.simulate_silent_crash()
                        expected_agent_ids.discard(fail_id)

            # 1. Process scripted tasks for this tick
            for task_spec in scenario_cfg.get_tasks_for_tick(t):
                agent_id = task_spec.get("agent_id")
                target = task_spec.get("target")
                if target is None and "x" in task_spec and "y" in task_spec:
                    target = (task_spec["x"], task_spec["y"])

                if agent_id and target:
                    coordinator.dispatch_agent(agent_id, target)
                elif target:
                    coordinator.inject_task(target=target)
                else:
                    coordinator.inject_task()

            # 2. Dynamic task injection for normal / high_traffic
            if scenario_cfg.dynamic_task_interval is not None:
                if t > 0 and t % scenario_cfg.dynamic_task_interval == 0:
                    unclaimed = coordinator.get_pending_tasks()
                    if scenario == "high_traffic" or len(unclaimed) < 3:
                        coordinator.inject_task()

            # 3. Publish clock tick and sync
            coordinator.publish_clock(t)

            coordinator.wait_for_agents(t, expected_agent_ids, timeout=0.05)
            if tick_delay > 0:
                time.sleep(tick_delay)

            # 4. Check peer vitality across all agents (peers tracking peers)
            for ag in agents:
                if not ag._crashed:
                    ag.check_peer_vitality(t, threshold=5)

            # 5. Coordinator vitality check & task salvage
            newly_offline = coordinator.check_agent_vitality(t, threshold=5)
            for off_id in newly_offline:
                expected_agent_ids.discard(off_id)
                for ag in agents:
                    if ag.agent_id == off_id:
                        if ag.active_task is not None:
                            incomplete_task = ag.active_task
                            ag.active_task = None
                            ag.tasks_failed += 1
                            coordinator.collector.record_silent_failure()
                            coordinator.collector.record_task_reassigned()
                            incomplete_task["claimed"] = False
                            incomplete_task["state"] = "PENDING"
                            incomplete_task["status"] = "PENDING"
                            with coordinator._lock:
                                if incomplete_task not in coordinator.pending_tasks:
                                    coordinator.pending_tasks.append(incomplete_task)
                            logger.info(
                                f"Task {incomplete_task.get('id')} salvaged from failed agent {off_id} "
                                f"and returned to pending_tasks as PENDING"
                            )

                        coordinator.client.publish(
                            "fleet/telemetry",
                            json.dumps({
                                "agent_id": off_id,
                                "status": "OFFLINE",
                                "x": ag.current_pos[0],
                                "y": ag.current_pos[1],
                                "time": t,
                            }),
                            qos=1,
                        )

            t += 1
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")

    logger.info("-" * 60)
    logger.info("Simulation complete")
    final_snapshot = coordinator.collector.get_snapshot()
    logger.info(f"Final Fleet Metrics Snapshot:\n{json.dumps(final_snapshot, indent=2)}")

    if export_metrics:
        export_path = Path(export_metrics)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(final_snapshot, f, indent=2)
        logger.info(f"Exported metrics snapshot to {export_metrics}")

    # Cleanup
    for agent in agents:
        agent.disconnect()
    coordinator.disconnect()

    return final_snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Robot Warehouse Simulation Runner")
    parser.add_argument(
        "--scenario",
        type=str,
        choices=ScenarioManager.list_scenarios(),
        default="normal",
        help="Evaluation scenario to execute (default: normal)",
    )
    parser.add_argument("--max-ticks", type=int, default=None, help="Maximum number of ticks to run")
    parser.add_argument("--tick-delay", type=float, default=0.5, help="Delay between ticks in seconds (default: 0.5)")
    parser.add_argument("--export-metrics", type=str, default=None, help="Filepath to export final JSON metrics snapshot")
    args = parser.parse_args()
    main(
        max_ticks=args.max_ticks,
        tick_delay=args.tick_delay,
        scenario=args.scenario,
        export_metrics=args.export_metrics,
    )