import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
#!/usr/bin/env python3
"""Simulation runner for multi-robot warehouse path planning demo."""

import time
import json
import logging
import threading
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
GRID_WIDTH = 10
GRID_HEIGHT = 10


class Coordinator:
    """Coordinates the simulation by publishing clock ticks and collecting telemetry."""

    def __init__(self) -> None:
        self.client = mqtt.Client(client_id="coordinator", clean_session=True)
        self.client.on_message = self._on_message
        self.live_positions: dict[str, dict] = {}
        self._lock = threading.Lock()

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


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Multi-Robot Warehouse Simulation")
    logger.info("=" * 60)

    # Create grid (10x10, no static obstacles)
    grid = WarehouseGrid(width=GRID_WIDTH, height=GRID_HEIGHT, obstacles=[])
    logger.info(f"Grid created: {GRID_WIDTH}x{GRID_HEIGHT}")

    # Create agents
    agent1 = AMRAgent(
        agent_id="AMR-1",
        start_pos=(0, 5),
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        static_obstacles=grid.obstacles,
    )
    agent2 = AMRAgent(
        agent_id="AMR-2",
        start_pos=(5, 0),
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        static_obstacles=grid.obstacles,
    )

    # Connect agents
    logger.info("Connecting agents to broker...")
    agent1.connect(BROKER, PORT)
    agent2.connect(BROKER, PORT)

    # Create coordinator
    coordinator = Coordinator()
    coordinator.connect()

    # Wait for connections to establish
    time.sleep(1)

    # Plan paths
    logger.info("Planning paths...")
    agent1.plan_to_goal(9, 5)  # Left to right across row 5
    agent2.plan_to_goal(5, 9)  # Top to bottom down column 5

    # Wait for intents to propagate
    time.sleep(1)

    logger.info("Starting simulation loop (t=0 to 15)")
    logger.info("Watch for collision avoidance at intersection (5, 5)")
    logger.info("-" * 60)

    # Simulation loop
    for t in range(16):
        coordinator.publish_clock(t)
        time.sleep(0.5)

        positions = coordinator.get_positions()
        pos_str = ", ".join(
            f"{aid}: ({p['x']}, {p['y']})" for aid, p in positions.items()
        )
        logger.info(f"t={t:2d} | {pos_str}")

    logger.info("-" * 60)
    logger.info("Simulation complete")

    # Cleanup
    agent1.disconnect()
    agent2.disconnect()
    coordinator.disconnect()


if __name__ == "__main__":
    main()