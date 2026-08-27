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

    # Create 6 agents strictly at docked coordinates (y=0 charging bays)
    agents = []
    for i in range(6):
        agent_id = f"AMR-{i+1}"
        start_pos = DOCKED_POSITIONS[i]
        priority = 6 - i  # Different priorities (AMR-1 highest)
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

    logger.info("Starting continuous simulation loop (infinite production mode)")
    logger.info("Agents will bid on tasks via Edge-AI Contract Net Protocol")
    logger.info("-" * 60)

    # Simulation loop (infinite runtime for production demo)
    t = 0
    try:
        while True:
            coordinator.publish_clock(t)
            t += 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")

    logger.info("-" * 60)
    logger.info("Simulation complete")

    # Cleanup
    for agent in agents:
        agent.disconnect()
    coordinator.disconnect()


if __name__ == "__main__":
    main()