"""AMR Agent for multi-robot warehouse simulation with Time-Space A* path planning."""

import json
import logging
import random
import requests
import time
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

if TYPE_CHECKING:
    from backend.algorithms.time_space_astar import State

from backend.algorithms.time_space_astar import time_space_astar

logger = logging.getLogger(__name__)


class AMRAgent:
    """Autonomous Mobile Robot agent with decentralized path planning, collision avoidance, and Edge-AI task bidding."""

    def __init__(
        self,
        agent_id: str,
        start_pos: tuple[int, int],
        grid_size: tuple[int, int] = (30, 30),
        obstacles: set[tuple[int, int]] | None = None,
        priority: int = 1,
    ) -> None:
        """Initialize the AMR agent.

        Args:
            agent_id: Unique identifier for this agent.
            start_pos: Starting (x, y) coordinate.
            grid_size: Tuple (width, height) of the warehouse grid. Default (30, 30).
            obstacles: Set of (x, y) coordinates representing permanent obstacles.
            priority: Priority level (higher number = higher priority). Default 1.
        """
        self.agent_id = agent_id
        self.current_pos = start_pos
        self.current_path: list[State] = []
        self.dynamic_reservations: dict[int, set[tuple[int, int]]] = {}
        self.peer_positions: dict[str, dict] = {}
        self.local_time = 0
        self.grid_size = grid_size
        self.obstacles = obstacles if obstacles is not None else set()
        self.dynamic_obstacles: set[tuple[int, int]] = set()
        self.priority = priority
        self.goal: tuple[int, int] | None = None
        self.current_goal: tuple[int, int] | None = None
        self.battery = 100.0
        self.status = "DOCKED"  # Start docked at charging bay
        self.last_sabotage_check = 0.0
        self.yield_cooldown = 0.0
        self.last_replan_time = 0.0
        self.last_move_time = 0.0
        self.yield_ticks = 0
        self.CHARGING_STATIONS = [(0, 0), (0, 29), (29, 0), (29, 29), (14, 0), (14, 29)]

        # Edge-AI bidding state
        self.bid_cost: float | None = None
        self.pending_task: dict | None = None
        self.bid_broadcast_time: int | None = None
        self.intended_next_pos: tuple[int, int] | None = None

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
        except Exception:
            raise

    def disconnect(self) -> None:
        """Disconnect from MQTT broker and stop network loop."""
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
        """Callback for when the client connects to the broker."""
        if rc == 0:
            client.subscribe("fleet/intents", qos=1)
            client.subscribe("fleet/clock", qos=1)
            client.subscribe("fleet/bids", qos=1)
            client.subscribe("fleet/telemetry", qos=1)
            client.subscribe(f"fleet/dispatch/{self.agent_id}", qos=1)

    def _on_disconnect(self, client: mqtt.Client, userdata: object, rc: int) -> None:
        """Callback for when the client disconnects from the broker."""
        pass

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
        except json.JSONDecodeError:
            return

        if topic == "fleet/intents":
            self._handle_intent(payload)
        elif topic == "fleet/telemetry":
            self._handle_telemetry(payload)
        elif topic == "fleet/clock":
            self._handle_clock(payload)
        elif topic == "fleet/bids":
            self._handle_bid(payload)
        elif topic.startswith("fleet/dispatch/"):
            self._handle_dispatch(payload)

    def _handle_telemetry(self, payload: dict) -> None:
        """Track live position and intent of peer robots."""
        sender_id = payload.get("agent_id")
        if not sender_id or sender_id == self.agent_id:
            return
        x = payload.get("x")
        y = payload.get("y")
        if x is None or y is None:
            return

        inp = payload.get("next_pos") or payload.get("intended_next_pos")
        next_pos = (x, y)
        if isinstance(inp, (list, tuple)) and len(inp) >= 2:
            next_pos = (inp[0], inp[1])

        self.peer_positions[sender_id] = {
            "pos": (x, y),
            "next_pos": next_pos,
            "intended_next_pos": next_pos,
            "priority": payload.get("priority", 1),
            "status": payload.get("status", "DOCKED"),
        }

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

        # Track peer position and intended next position from path
        if path and isinstance(path, list):
            first_node = path[0]
            if isinstance(first_node, (list, tuple)) and len(first_node) >= 2:
                curr_pos = (first_node[0], first_node[1])
                next_p = None
                if len(path) > 1 and isinstance(path[1], (list, tuple)) and len(path[1]) >= 2:
                    next_p = (path[1][0], path[1][1])
                if sender_id in self.peer_positions:
                    self.peer_positions[sender_id]["pos"] = curr_pos
                    if next_p:
                        self.peer_positions[sender_id]["intended_next_pos"] = next_p
                    self.peer_positions[sender_id]["priority"] = sender_priority
                    self.peer_positions[sender_id]["status"] = sender_status
                else:
                    self.peer_positions[sender_id] = {
                        "pos": curr_pos,
                        "intended_next_pos": next_p,
                        "priority": sender_priority,
                        "status": sender_status,
                    }

        # If sender is DEAD, treat their position as a dynamic obstacle
        if sender_status == "DEAD":
            if path:
                last_node = path[-1]
                if isinstance(last_node, (list, tuple)) and len(last_node) >= 2:
                    dead_x, dead_y = last_node[0], last_node[1]
                    self.dynamic_obstacles.add((dead_x, dead_y))

        if not isinstance(path, list):
            return

        peer_path: list[State] = []
        for node in path:
            if not isinstance(node, (list, tuple)) or len(node) != 3:
                continue
            x, y, t = node
            peer_path.append((x, y, t))
            if t not in self.dynamic_reservations:
                self.dynamic_reservations[t] = set()
            self.dynamic_reservations[t].add((x, y))

        # Check for conflicts with our current path
        if self._check_conflict(peer_path):
            should_yield = False
            if self.priority < sender_priority:
                should_yield = True
            elif self.priority == sender_priority and self.agent_id > sender_id:
                should_yield = True

            if should_yield:
                current_time = time.time()
                if current_time >= self.yield_cooldown:
                    self.yield_cooldown = current_time + 3.0
                    self.status = "YIELDING"
                    
                    if path:
                        first_node = path[0]
                        if isinstance(first_node, (list, tuple)) and len(first_node) >= 2:
                            other_x, other_y = first_node[0], first_node[1]
                            self.dynamic_obstacles.add((other_x, other_y))
                    
                    if self.current_goal and (current_time - self.last_replan_time > 1.0):
                        self.plan_to_goal(*self.current_goal)

    def _handle_bid(self, payload: dict) -> None:
        """Process peer robot's bid for a task.

        Args:
            payload: JSON payload containing sender_id, task, bid_cost, and priority.
        """
        sender_id = payload.get("sender_id")
        task = payload.get("task")
        sender_bid_cost = payload.get("bid_cost")
        sender_priority = payload.get("priority", 1)

        if sender_id == self.agent_id:
            return  # Ignore own bids

        # If we're bidding on the same task, compare bid costs
        if (self.pending_task and task and 
            self.pending_task.get("x") == task.get("x") and 
            self.pending_task.get("y") == task.get("y") and
            self.bid_cost is not None and sender_bid_cost is not None):
            
            # Lower bid cost wins (lower is better)
            if sender_bid_cost < self.bid_cost or (sender_bid_cost == self.bid_cost and sender_priority > self.priority):
                self.pending_task = None
                self.bid_cost = None
                self.bid_broadcast_time = None

    def _check_conflict(self, peer_path: list[State]) -> bool:
        """Check for vertex collision between peer path and our current path.

        Args:
            peer_path: List of (x, y, t) tuples from another agent.

        Returns:
            True if vertex collision detected at t >= local_time, False otherwise.
        """
        if not self.current_path:
            return False

        our_future: dict[int, tuple[int, int]] = {}
        for x, y, t in self.current_path:
            if t >= self.local_time:
                our_future[t] = (x, y)

        for x, y, t in peer_path:
            if t >= self.local_time and t in our_future:
                if our_future[t] == (x, y):
                    return True  # Vertex collision
        return False

    def _handle_clock(self, payload: dict) -> None:
        """Process global clock tick, handle bidding, and update position along current path.

        Args:
            payload: JSON payload containing current simulation time.
        """
        self.local_time = payload.get("time", self.local_time)
        current_time = time.time()

        # Throttled sabotage check - only poll every 2 seconds to prevent blocking
        if current_time - self.last_sabotage_check > 2.0:
            self.last_sabotage_check = current_time
            try:
                res = requests.get("http://localhost:8000/api/sabotage/status", timeout=0.5)
                if self.agent_id in res.json().get("sabotaged", []):
                    self.status = "DEAD"
            except Exception:
                pass

        # Handle yield cooldown - if cooldown expired, resume status
        if self.status == "YIELDING" and current_time >= self.yield_cooldown:
            if self.goal or self.current_goal:
                self.status = "MOVING"
            else:
                self.status = "DOCKED"

        # Edge-AI Bidding Logic: Poll for tasks when DOCKED
        if self.status == "DOCKED":
            try:
                res = requests.get("http://localhost:8000/api/tasks", timeout=0.5)
                tasks = res.json().get("tasks", [])
                for task in tasks:
                    if not task.get("claimed", False):
                        # Calculate bid cost: Manhattan distance + battery penalty
                        distance = abs(self.current_pos[0] - task["x"]) + abs(self.current_pos[1] - task["y"])
                        battery_penalty = (100 - self.battery) * 0.1
                        self.bid_cost = distance + battery_penalty
                        self.pending_task = task
                        self.bid_broadcast_time = self.local_time
                        
                        bid_payload = {
                            "sender_id": self.agent_id,
                            "task": task,
                            "bid_cost": self.bid_cost,
                            "priority": self.priority,
                        }
                        self.client.publish("fleet/bids", json.dumps(bid_payload), qos=1)
                        break  # Only bid on one task at a time
            except Exception:
                pass

        # Check if we won the bid (wait 1 tick after broadcasting)
        if (self.status == "DOCKED" and self.pending_task and self.bid_broadcast_time is not None 
            and self.local_time > self.bid_broadcast_time):
            self.status = "MOVING"
            task = self.pending_task
            self.current_goal = (task["x"], task["y"])
            self.goal = (task["x"], task["y"])
            
            self.plan_to_goal(task["x"], task["y"])
            
            self.pending_task = None
            self.bid_cost = None
            self.bid_broadcast_time = None

        prev_pos = self.current_pos
        current_real_time = time.time()

        if self.status in ["MOVING", "YIELDING"] and self.current_path:
            # INDUSTRIAL GOVERNOR: Never process a step faster than 0.45s of REAL time, ignoring tick bursts
            if current_real_time - self.last_move_time >= 0.45:
                self.last_move_time = current_real_time
                
                next_node = self.current_path[0]
                next_pos = (next_node[0], next_node[1])
                
                conflict = False
                blocking_peer_id = None
                
                for peer_id, peer_data in self.peer_positions.items():
                    if peer_data.get("status") not in ["DEAD", "IDLE"]:
                        peer_curr = peer_data.get("pos")
                        # Read peer's intent (default to current pos if not broadcasting yet)
                        peer_next = peer_data.get("next_pos", peer_curr)
                        
                        # 1. Solid Matter Check (Tile is currently occupied)
                        if next_pos == peer_curr:
                            conflict = True
                            blocking_peer_id = peer_id
                            break  # Cannot step into occupied tile, regardless of priority
                            
                        # 2. Vertex Intersection Check (We both want the exact same empty tile)
                        elif next_pos == peer_next and next_pos != self.current_pos:
                            peer_pri = peer_data.get("priority", 1)
                            # Tie-breaker: Lower priority bot yields the empty tile
                            if self.priority < peer_pri or (self.priority == peer_pri and self.agent_id > peer_id):
                                conflict = True
                                blocking_peer_id = peer_id
                                break
                
                if conflict:
                    self.status = "YIELDING"
                    self.yield_ticks += 1
                    # Randomized backoff to shatter livelock symmetry (3 to 6 ticks)
                    if self.yield_ticks > random.randint(3, 6) and blocking_peer_id and blocking_peer_id in self.peer_positions:
                        blocker_data = self.peer_positions[blocking_peer_id]
                        blocker_pos = blocker_data.get("pos")
                        blocker_next = blocker_data.get("next_pos", blocker_pos)
                        
                        # 1. Flag both the VIP bot's current AND next intended tile as solid brick walls
                        walls_added = []
                        if blocker_pos:
                            self.dynamic_obstacles.add(blocker_pos)
                            walls_added.append(blocker_pos)
                        if blocker_next and blocker_next != blocker_pos:
                            self.dynamic_obstacles.add(blocker_next)
                            walls_added.append(blocker_next)
                        
                        # 2. Force replan with a much wider detour
                        if self.current_goal:
                            self.plan_to_goal(*self.current_goal)
                        
                        # 3. Cleanup temporary walls
                        for w in walls_added:
                            self.dynamic_obstacles.discard(w)
                            
                        self.yield_ticks = 0
                        self.last_replan_time = time.time()
                else:
                    self.status = "MOVING"
                    self.yield_ticks = 0
                    self.current_path.pop(0)  # Consume the step
                    self.current_pos = next_pos
                    
        # Strict Docking Cleanup
        if self.status in ["MOVING", "YIELDING"] and not self.current_path:
            if self.current_goal and self.current_pos == self.current_goal:
                self.status = "DOCKED"
                self.current_goal = None
                self.goal = None
                self.current_path = []

        if self.current_path:
            self.intended_next_pos = (self.current_path[0][0], self.current_path[0][1])
        else:
            self.intended_next_pos = None

        # 1. Hyper-charge ONLY if physically sitting on a Charging Station
        if self.status in ["DOCKED", "IDLE"] and self.current_pos in self.CHARGING_STATIONS:
            self.battery = min(100.0, self.battery + 5.0)
        else:
            # 2. Normal drain while working or moving
            self.battery = max(0.0, self.battery - 0.1)
            
            if self.battery == 0:
                self.status = "DEAD"
            # 3. Autonomous Return-to-Base at 20%
            elif self.battery <= 20.0 and self.current_goal not in self.CHARGING_STATIONS:
                # Find docks not currently occupied by resting peers
                available_docks = [
                    dock for dock in self.CHARGING_STATIONS 
                    if not any(p.get("pos") == dock and p.get("status") in ["DOCKED", "IDLE"] for peer_id, p in self.peer_positions.items())
                ]
                if not available_docks:
                    available_docks = self.CHARGING_STATIONS  # Fallback
                
                # Calculate nearest dock using Manhattan distance
                nearest_dock = min(available_docks, key=lambda d: abs(d[0] - self.current_pos[0]) + abs(d[1] - self.current_pos[1]))
                
                # Abort current task and route to charger
                self.plan_to_goal(*nearest_dock)

        # Auto-recovery: Force replan if stuck midway
        if self.status != "DEAD" and self.current_goal and not self.current_path:
            # Auto-recovery: Only force replan if we haven't just tried in the last 2 seconds
            if time.time() - getattr(self, "last_replan_time", 0) > 2.0:
                self.plan_to_goal(*self.current_goal)
                self.last_replan_time = time.time()

        # Publish telemetry with status, intended next position, and next_pos
        next_step_pos = (self.current_path[0][0], self.current_path[0][1]) if self.current_path else self.current_pos
        telemetry = {
            "agent_id": self.agent_id,
            "x": self.current_pos[0],
            "y": self.current_pos[1],
            "time": self.local_time,
            "battery": round(self.battery, 1),
            "priority": self.priority,
            "status": self.status,
            "intended_next_pos": self.intended_next_pos,
            "next_pos": next_step_pos,
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
            return

        if self.status != "DEAD":
            self.status = "MOVING"

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

        if self.status in ["DOCKED", "IDLE"]:
            self.status = "MOVING"

        self.last_replan_time = time.time()
        self.current_goal = (goal_x, goal_y)
        self.goal = (goal_x, goal_y)
        start_x, start_y = self.current_pos

        # Combine static obstacles with dynamic obstacles (dead robots, yielded spots) and docked peers
        docked_obstacles = {data["pos"] for data in self.peer_positions.values() if data.get("status") in ["DOCKED", "IDLE"]}
        all_obstacles = self.obstacles | self.dynamic_obstacles | docked_obstacles

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
            self.current_path = []
            self.status = "YIELDING"
            self.yield_cooldown = time.time() + 2.0
            return False

        adjusted_path = [(x, y, t + self.local_time) for x, y, t in path]
        if len(adjusted_path) > 1 and (adjusted_path[0][0], adjusted_path[0][1]) == self.current_pos:
            self.current_path = list(adjusted_path[1:])
        else:
            self.current_path = list(adjusted_path)

        self.status = "MOVING"

        # Broadcast intent to fleet
        intent = {
            "sender_id": self.agent_id,
            "path": adjusted_path,
            "timestamp": self.local_time,
            "priority": self.priority,
            "status": self.status,
        }
        self.client.publish("fleet/intents", json.dumps(intent), qos=1, retain=False)
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