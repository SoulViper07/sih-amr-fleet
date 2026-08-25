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
GRID_SIZE = (20, 20)
OBSTACLES = [(5, 5), (5, 6), (5, 7), (10, 10), (11, 10), (12, 10), (13, 10), (15, 15)]


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
    logger.info("Starting Multi-Robot Warehouse Simulation (20x20, 4 AMRs)")
    logger.info("=" * 60)

    # Create grid (20x20 with static obstacles)
    grid = WarehouseGrid(width=GRID_SIZE[0], height=GRID_SIZE[1], obstacles=OBSTACLES)
    logger.info(f"Grid created: {GRID_SIZE[0]}x{GRID_SIZE[1]} with {len(OBSTACLES)} obstacles")

    # Create agents with different priorities
    agent1 = AMRAgent(
        agent_id="AMR-1",
        start_pos=(0, 0),
        grid_size=GRID_SIZE,
        obstacles=set(OBSTACLES),
        priority=4,
    )
    agent2 = AMRAgent(
        agent_id="AMR-2",
        start_pos=(19, 0),
        grid_size=GRID_SIZE,
        obstacles=set(OBSTACLES),
        priority=3,
    )
    agent3 = AMRAgent(
        agent_id="AMR-3",
        start_pos=(0, 19),
        grid_size=GRID_SIZE,
        obstacles=set(OBSTACLES),
        priority=2,
    )
    agent4 = AMRAgent(
        agent_id="AMR-4",
        start_pos=(19, 19),
        grid_size=GRID_SIZE,
        obstacles=set(OBSTACLES),
        priority=1,
    )

    agents = [agent1, agent2, agent3, agent4]

    # Connect agents
    logger.info("Connecting agents to broker...")
    for agent in agents:
        agent.connect(BROKER, PORT)

    # Create coordinator
    coordinator = Coordinator()
    coordinator.connect()

    # Wait for connections to establish
    time.sleep(1)

    # Plan paths (cross the grid)
    logger.info("Planning paths...")
    agent1.plan_to_goal(19, 19)  # Bottom-left to top-right
    agent2.plan_to_goal(0, 19)   # Bottom-right to top-left
    agent3.plan_to_goal(19, 0)   # Top-left to bottom-right
    agent4.plan_to_goal(0, 0)    # Top-right to bottom-left

    # Wait for intents to propagate
    time.sleep(1)

    logger.info("Starting simulation loop (t=0 to 30)")
    logger.info("Watch for collision avoidance and priority-based yielding")
    logger.info("-" * 60)

    # Simulation loop (longer for 20x20 grid)
    for t in range(31):
        coordinator.publish_clock(t)
        time.sleep(0.5)

        positions = coordinator.get_positions()
        pos_str = ", ".join(
            f"{aid}: ({p['x']}, {p['y']}) bat={p.get('battery', 'N/A')} pri={p.get('priority', 'N/A')}"
            for aid, p in positions.items()
        )
        logger.info(f"t={t:2d} | {pos_str}")

    logger.info("-" * 60)
    logger.info("Simulation complete")

    # Cleanup
    for agent in agents:
        agent.disconnect()
    coordinator.disconnect()


if __name__ == "__main__":
    main()