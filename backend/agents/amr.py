"""AMR Agent for multi-robot warehouse simulation with Time-Space A* path planning."""

import json
import logging
import requests
import time
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

if TYPE_CHECKING:
    from backend.algorithms.time_space_astar import State

from backend.algorithms.time_space_astar import time_space_astar

logger = logging.getLogger(__name__)


class AMRAgent:
    """Autonomous Mobile Robot agent with decentralized path planning and collision avoidance."""

    def __init__(
        self,
        agent_id: str,
        start_pos: tuple[int, int],
        grid_size: tuple[int, int] = (20, 20),
        obstacles: set[tuple[int, int]] | None = None,
        priority: int = 1,
    ) -> None:
        """Initialize the AMR agent.

        Args:
            agent_id: Unique identifier for this agent.
            start_pos: Starting (x, y) coordinate.
            grid_size: Tuple (width, height) of the warehouse grid.
            obstacles: Set of (x, y) coordinates representing permanent obstacles.
            priority: Priority level (higher number = higher priority). Default 1.
        """
        self.agent_id = agent_id
        self.current_pos = start_pos
        self.current_path: list[State] = []
        self.dynamic_reservations: dict[int, set[tuple[int, int]]] = {}
        self.local_time = 0
        self.grid_size = grid_size
        self.obstacles = obstacles if obstacles is not None else set()
        self.dynamic_obstacles: set[tuple[int, int]] = set()
        self.priority = priority
        self.goal: tuple[int, int] | None = None
        self.current_goal: tuple[int, int] | None = None
        self.battery = 100.0
        self.status = "ACTIVE"
        self.last_sabotage_check = 0.0

        # MQTT client setup
        self.client = mqtt.Client(client_id=agent_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def connect(self, broker: str = "localhost", port: int = 1883) -> None:
        """Connect to MQTT broker and start network loop.

        Args:
            broker: MQTT broker hostname or IP.
            port: MQTT broker port.
        """
        try:
            self.client.connect(broker, port, keepalive=60)
            self.client.loop_start()
            logger.info(f"Agent {self.agent_id} connected to {broker}:{port}")
        except Exception as e:
            logger.error(f"Agent {self.agent_id} failed to connect: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from MQTT broker and stop network loop."""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info(f"Agent {self.agent_id} disconnected")

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
        """Callback for when the client connects to the broker."""
        if rc == 0:
            logger.info(f"Agent {self.agent_id} connected successfully")
            # Subscribe to fleet topics
            client.subscribe("fleet/intents", qos=1)
            client.subscribe("fleet/clock", qos=1)
            # Subscribe to dispatch commands for this agent
            client.subscribe(f"fleet/dispatch/{self.agent_id}", qos=1)
        else:
            logger.error(f"Agent {self.agent_id} connection failed with code {rc}")

    def _on_disconnect(self, client: mqtt.Client, userdata: object, rc: int) -> None:
        """Callback for when the client disconnects from the broker."""
        logger.warning(f"Agent {self.agent_id} disconnected with code {rc}")

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming MQTT messages.

        Args:
            client: MQTT client instance.
            userdata: User data (unused).
            msg: Received message.
        """
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError as e:
            logger.error(f"Agent {self.agent_id} failed to parse message: {e}")
            return

        if topic == "fleet/intents":
            self._handle_intent(payload)
        elif topic == "fleet/clock":
            self._handle_clock(payload)
        elif topic.startswith("fleet/dispatch/"):
            self._handle_dispatch(payload)

    def _handle_intent(self, payload: dict) -> None:
        """Process peer robot's path intent and update dynamic reservations.

        Args:
            payload: JSON payload containing sender_id, path, and priority.
        """
        sender_id = payload.get("sender_id")
        path = payload.get("path", [])
        sender_priority = payload.get("priority", 1)
        sender_status = payload.get("status", "ACTIVE")

        if sender_id == self.agent_id:
            return  # Ignore own broadcasts

        # If sender is DEAD, treat their position as a dynamic obstacle
        if sender_status == "DEAD":
            # Get the latest position from the path
            if path:
                last_node = path[-1]
                if isinstance(last_node, list) and len(last_node) >= 2:
                    dead_x, dead_y = last_node[0], last_node[1]
                    self.dynamic_obstacles.add((dead_x, dead_y))
                    logger.warning(f"Agent {self.agent_id}: Added dead agent {sender_id} at ({dead_x}, {dead_y}) as dynamic obstacle")

        if not isinstance(path, list):
            logger.warning(f"Agent {self.agent_id} received invalid path from {sender_id}")
            return

        peer_path: list[State] = []
        for node in path:
            if not isinstance(node, list) or len(node) != 3:
                continue
            x, y, t = node
            peer_path.append((x, y, t))
            if t not in self.dynamic_reservations:
                self.dynamic_reservations[t] = set()
            self.dynamic_reservations[t].add((x, y))

        # Check for conflicts with our current path
        if self._check_conflict(peer_path):
            # Resolve conflict: lower priority yields. If equal, higher agent_id yields.
            if self.priority < sender_priority or (self.priority == sender_priority and self.agent_id > sender_id):
                logger.warning(
                    f"Agent {self.agent_id}: Conflict detected with {sender_id} (priority {sender_priority}). "
                    f"Yielding and replanning."
                )
                if self.current_goal:
                    self.plan_to_goal(*self.current_goal)

    def _check_conflict(self, peer_path: list[State]) -> bool:
        """Check for vertex collision between peer path and our current path.

        Args:
            peer_path: List of (x, y, t) tuples from another agent.

        Returns:
            True if vertex collision detected at t >= local_time, False otherwise.
        """
        if not self.current_path:
            return False

        # Build a set of our future positions for fast lookup
        our_future: dict[int, tuple[int, int]] = {}
        for x, y, t in self.current_path:
            if t >= self.local_time:
                our_future[t] = (x, y)

        # Check peer path against our future positions
        for x, y, t in peer_path:
            if t >= self.local_time and t in our_future:
                if our_future[t] == (x, y):
                    return True  # Vertex collision
        return False

    def _handle_clock(self, payload: dict) -> None:
        """Process global clock tick and update position along current path.

        Args:
            payload: JSON payload containing current simulation time.
        """
        self.local_time = payload.get("time", self.local_time)

        # Throttled sabotage check - only poll every 2 seconds to prevent blocking
        current_time = time.time()
        if current_time - self.last_sabotage_check > 2.0:
            self.last_sabotage_check = current_time
            try:
                res = requests.get("http://localhost:8000/api/sabotage/status", timeout=0.5)
                if self.agent_id in res.json().get("sabotaged", []):
                    self.status = "DEAD"
            except Exception:
                pass

        # Track previous position to detect movement
        prev_pos = self.current_pos

        # If DEAD, stop moving completely but continue broadcasting
        if self.status == "DEAD":
            # Don't advance along path - stay frozen
            pass
        else:
            # Advance along path if current time matches a path node
            for x, y, t in self.current_path:
                if t == self.local_time:
                    self.current_pos = (x, y)
                    break

        # Update battery: moving costs 0.5, idle/yielding costs 0.1
        if self.current_pos != prev_pos:
            self.battery = max(0.0, self.battery - 0.5)
        else:
            self.battery = max(0.0, self.battery - 0.1)

        # Publish telemetry with status
        telemetry = {
            "agent_id": self.agent_id,
            "x": self.current_pos[0],
            "y": self.current_pos[1],
            "time": self.local_time,
            "battery": round(self.battery, 1),
            "priority": self.priority,
            "status": self.status,
        }
        self.client.publish("fleet/telemetry", json.dumps(telemetry), qos=1)

    def _handle_dispatch(self, payload: dict) -> None:
        """Handle dispatch command to navigate to a new target.

        Args:
            payload: JSON payload containing x and y coordinates.
        """
        x = payload.get("x")
        y = payload.get("y")
        if x is None or y is None:
            logger.warning(f"Agent {self.agent_id}: Invalid dispatch payload {payload}")
            return

        logger.info(f"Agent {self.agent_id}: Received dispatch command to ({x}, {y})")
        self.plan_to_goal(x, y)

    def plan_to_goal(self, goal_x: int, goal_y: int) -> bool:
        """Plan a path to the goal using Time-Space A* and broadcast intent.

        Args:
            goal_x: Goal X coordinate.
            goal_y: Goal Y coordinate.

        Returns:
            True if path found, False otherwise.
        """
        if self.status == "DEAD":
            return False

        self.current_goal = (goal_x, goal_y)
        self.goal = (goal_x, goal_y)
        start_x, start_y = self.current_pos

        # Combine static obstacles with dynamic obstacles (dead robots)
        all_obstacles = self.obstacles | self.dynamic_obstacles

        # Plan path starting from current local time
        path = time_space_astar(
            start=(start_x, start_y),
            goal=(goal_x, goal_y),
            grid_width=self.grid_size[0],
            grid_height=self.grid_size[1],
            static_obstacles=all_obstacles,
            dynamic_reservations=self.dynamic_reservations,
            max_time=self.local_time + 100,  # Reasonable horizon
        )

        if path is None:
            logger.warning(f"Agent {self.agent_id}: No path found to ({goal_x}, {goal_y})")
            self.current_path = []
            return False

        # Adjust path times to be absolute (starting from local_time)
        # The planner returns path starting at t=0, so we shift by local_time
        adjusted_path = [(x, y, t + self.local_time) for x, y, t in path]
        self.current_path = adjusted_path

        # Broadcast intent to fleet
        intent = {
            "sender_id": self.agent_id,
            "path": adjusted_path,
            "timestamp": self.local_time,
            "priority": self.priority,
            "status": self.status,
        }
        self.client.publish("fleet/intents", json.dumps(intent), qos=1, retain=False)
        logger.info(f"Agent {self.agent_id}: Path planned to ({goal_x}, {goal_y}), length={len(adjusted_path)}")
        return True

    def get_state(self) -> dict:
        """Return current agent state for debugging/monitoring.

        Returns:
            Dictionary with agent state information.
        """
        return {
            "agent_id": self.agent_id,
            "position": self.current_pos,
            "local_time": self.local_time,
            "goal": self.goal,
            "path_length": len(self.current_path),
            "reservations_count": sum(len(s) for s in self.dynamic_reservations.values()),
            "priority": self.priority,
            "battery": round(self.battery, 1),
            "status": self.status,
        }