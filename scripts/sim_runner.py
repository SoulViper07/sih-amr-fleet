import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
#!/usr/bin/env python3
"""Simulation runner for multi-robot warehouse simulation demo."""

import time
import json
import logging
import threading
import random
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

if TYPE_CHECKING:
    from backend.world.grid import WarehouseGrid
    from backend.agents.amr import AMRAgent

from backend.world.grid import WarehouseGrid
from backend.agents.amr import AMRAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BROKER = "localhost"
PORT = 1883
GRID_SIZE = (20, 20)

# Warehouse config matching backend
WAREHOUSE_CONFIG = {
    "grid_size": [20, 20],
    "racks": {
        "rack_1": [(x, y) for x in range(2, 5) for y in range(4, 16)],
        "rack_2": [(x, y) for x in range(8, 11) for y in range(4, 16)],
        "rack_3": [(x, y) for x in range(14, 17) for y in range(4, 16)],
    },
    "charging_stations": [(0, 0), (6, 0), (12, 0), (19, 0)],
    "workstations": [(0, 19), (9, 19), (19, 19)],
}

OBSTACLES = []
for rack_coords in WAREHOUSE_CONFIG["racks"].values():
    OBSTACLES.extend(rack_coords)

OBSTACLES_SET = set(OBSTACLES)

# Valid spawn positions (charging stations + workstations)
SPAWN_POSITIONS = [
    (0, 0),   # charging
    (6, 0),   # charging
    (12, 0),  # charging
    (19, 0),  # charging
    (0, 19),  # workstation
    (9, 19),  # workstation
    (19, 19), # workstation
]

# All valid positions (not in obstacles)
VALID_POSITIONS = [(x, y) for x in range(GRID_SIZE[0]) for y in range(GRID_SIZE[1]) if (x, y) not in OBSTACLES_SET]


class Coordinator:
    """Coordinates the simulation by publishing clock ticks and collecting telemetry."""

    def __init__(self) -> None:
        self.client = mqtt.Client(client_id="coordinator", clean_session=True)
        self.client.on_message = self._on_message
        self.live_positions: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.agent_goals: dict[str, tuple[int, int] | None] = {}
        self.agent_arrival_time: dict[str, int] = {}

    def connect(self) -> None:
        """Connect to MQTT broker and subscribe to telemetry."""
        self.client.connect(BROKER, PORT, keepalive=60)
        self.client.subscribe("fleet/telemetry", qos=1)
        self.client.loop_start()
        logger.info("Coordinator connected and subscribed to fleet/telemetry")

    def disconnect(self) -> None:
        """Disconnect from broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        """Store incoming telemetry."""
        try:
            payload = json.loads(msg.payload.decode())
            agent_id = payload.get("agent_id")
            if agent_id:
                with self._lock:
                    self.live_positions[agent_id] = payload
        except json.JSONDecodeError:
            pass

    def publish_clock(self, t: int) -> None:
        """Publish a clock tick."""
        self.client.publish("fleet/clock", json.dumps({"time": t}), qos=1)

    def get_positions(self) -> dict[str, dict]:
        """Get a copy of current positions."""
        with self._lock:
            return dict(self.live_positions)

    def assign_random_goal(self, agent_id: str, current_pos: tuple[int, int]) -> tuple[int, int]:
        """Assign a random valid goal position."""
        # Filter out current position and obstacles
        possible_goals = [pos for pos in VALID_POSITIONS if pos != current_pos]
        if not possible_goals:
            return current_pos
        return random.choice(possible_goals)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Multi-Robot Warehouse Simulation (20x20, 6 AMRs)")
    logger.info("=" * 60)

    # Create grid
    grid = WarehouseGrid(width=GRID_SIZE[0], height=GRID_SIZE[1], obstacles=OBSTACLES)
    logger.info(f"Grid created: {GRID_SIZE[0]}x{GRID_SIZE[1]} with {len(OBSTACLES)} obstacles (racks)")

    # Create 6 agents starting at charging stations and workstations
    agents = []
    for i in range(6):
        agent_id = f"AMR-{i+1}"
        start_pos = SPAWN_POSITIONS[i % len(SPAWN_POSITIONS)]
        priority = 6 - i  # Different priorities
        agent = AMRAgent(
            agent_id=agent_id,
            start_pos=start_pos,
            grid_size=GRID_SIZE,
            obstacles=OBSTACLES_SET,
            priority=priority,
        )
        agents.append(agent)

    # Connect agents
    logger.info("Connecting agents to broker...")
    for agent in agents:
        agent.connect(BROKER, PORT)

    # Create coordinator
    coordinator = Coordinator()
    coordinator.connect()

    # Wait for connections to establish
    time.sleep(1)

    # Initial random goals for all agents
    logger.info("Assigning initial random goals...")
    for agent in agents:
        goal = coordinator.assign_random_goal(agent.agent_id, agent.current_pos)
        agent.plan_to_goal(goal[0], goal[1])
        coordinator.agent_goals[agent.agent_id] = goal

    # Wait for intents to propagate
    time.sleep(1)

    logger.info("Starting continuous simulation loop (t=0 to 300)")
    logger.info("Agents will continuously pick new random targets")
    logger.info("-" * 60)

    # Simulation loop (longer for continuous operation)
    for t in range(301):
        coordinator.publish_clock(t)
        time.sleep(0.5)

        positions = coordinator.get_positions()
        
        # Check for agents that reached their goal and assign new ones
        for agent in agents:
            if agent.status == "DEAD":
                continue
                
            pos_data = positions.get(agent.agent_id)
            if not pos_data:
                continue
                
            current_pos = (pos_data["x"], pos_data["y"])
            goal = coordinator.agent_goals.get(agent.agent_id)
            
            if goal and current_pos == goal:
                # Check if we've been at this goal for 2 seconds (4 ticks at 0.5s each)
                arrival_time = coordinator.agent_arrival_time.get(agent.agent_id)
                if arrival_time is None:
                    coordinator.agent_arrival_time[agent.agent_id] = t
                elif t - arrival_time >= 4:  # 2 seconds = 4 ticks
                    # Assign new random goal
                    new_goal = coordinator.assign_random_goal(agent.agent_id, current_pos)
                    agent.plan_to_goal(new_goal[0], new_goal[1])
                    coordinator.agent_goals[agent.agent_id] = new_goal
                    coordinator.agent_arrival_time[agent.agent_id] = None
                    logger.info(f"Agent {agent.agent_id}: Reached goal, new target ({new_goal[0]}, {new_goal[1]})")
            elif goal and current_pos != goal:
                # Reset arrival time if not at goal
                coordinator.agent_arrival_time[agent.agent_id] = None

        pos_str = ", ".join(
            f"{aid}: ({p['x']}, {p['y']}) bat={p.get('battery', 'N/A')} pri={p.get('priority', 'N/A')} st={p.get('status', 'ACTIVE')}"
            for aid, p in positions.items()
        )
        logger.info(f"t={t:3d} | {pos_str}")

    logger.info("-" * 60)
    logger.info("Simulation complete")

    # Cleanup
    for agent in agents:
        agent.disconnect()
    coordinator.disconnect()


if __name__ == "__main__":
    main()