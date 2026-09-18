"""AMR Agent for multi-robot warehouse simulation with Time-Space A* path planning."""

import json
import logging
import os
import random
import requests
import time
import uuid
from typing import TYPE_CHECKING, Any

import paho.mqtt.client as mqtt

if TYPE_CHECKING:
    from backend.algorithms.time_space_astar import State

from backend.algorithms.time_space_astar import time_space_astar
from backend.metrics import FleetMetricsCollector, get_collector

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
        metrics_collector: FleetMetricsCollector | None = None,
        task_provider: Any = None,
        step_interval: float = 0.45,
    ) -> None:
        """Initialize the AMR agent.

        Args:
            agent_id: Unique identifier for this agent.
            start_pos: Starting (x, y) coordinate.
            grid_size: Tuple (width, height) of the warehouse grid. Default (30, 30).
            obstacles: Set of (x, y) coordinates representing permanent obstacles.
            priority: Priority level (higher number = higher priority). Default 1.
            metrics_collector: FleetMetricsCollector instance. Default singleton.
            task_provider: Optional callable returning pending tasks.
            step_interval: Minimum real-time interval between physical moves in seconds. Default 0.45.
        """
        self.agent_id = agent_id
        self.metrics_collector = metrics_collector if metrics_collector is not None else get_collector()
        self.task_provider = task_provider
        self.step_interval = step_interval
        self._backend_available: bool | None = None
        self.active_task: dict | None = None
        self.task_start_time: float = 0.0
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
        self.CHARGING_STATIONS = [(0, 0), (0, 29), (29, 0), (29, 29), (14, 0), (14, 29)]
        self.status = "DOCKED" if self.current_pos in self.CHARGING_STATIONS else "ACTIVE"
        self.last_sabotage_check = 0.0
        self.yield_cooldown = 0.0
        self.last_replan_time = 0.0
        self.last_move_time = 0.0
        self.yield_ticks = 0

        # Heartbeat & Fault-Tolerance tracking
        self.peer_last_seen_tick: dict[str, int] = {}
        self._crashed: bool = False
        self.tasks_failed: int = 0

        # Edge-AI bidding state
        self.bid_cost: float | None = None
        self.pending_task: dict | None = None
        self.bid_broadcast_time: int | None = None
        self.intended_next_pos: tuple[int, int] | None = None

        # MQTT client setup
        self.client = mqtt.Client(client_id=f"{agent_id}_{uuid.uuid4().hex[:8]}", clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    @property
    def position(self) -> tuple[int, int]:
        """Return the current (x, y) coordinates of the agent."""
        return self.current_pos

    @position.setter
    def position(self, pos: tuple[int, int]) -> None:
        self.current_pos = pos

    @property
    def path(self) -> list:
        """Return current path buffer."""
        return self.current_path

    @path.setter
    def path(self, val: list) -> None:
        self.current_path = list(val)

    @property
    def target(self) -> tuple[int, int] | None:
        """Return current target/goal coordinate."""
        return self.current_goal

    @target.setter
    def target(self, val: tuple[int, int] | None) -> None:
        self.current_goal = val
        self.goal = val

    def connect(self, broker: str = "broker.emqx.io", port: int = 1883) -> None:
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
            client.subscribe("amr/+/heartbeat", qos=1)
            client.subscribe(f"fleet/dispatch/{self.agent_id}", qos=1)
            client.subscribe(f"amr/{self.agent_id}/sabotage", qos=1)
            client.subscribe(f"fleet/sabotage/{self.agent_id}", qos=1)
            client.subscribe("fleet/sabotage", qos=1)

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

        if (
            topic == f"amr/{self.agent_id}/sabotage"
            or topic == f"fleet/sabotage/{self.agent_id}"
            or topic == "fleet/sabotage"
            or (topic.startswith("amr/") and topic.endswith("/sabotage"))
        ):
            self._handle_sabotage(payload)
            return

        if topic == "fleet/intents":
            self._handle_intent(payload)
        elif topic == "fleet/telemetry":
            self._handle_telemetry(payload)
        elif topic == "fleet/clock":
            self._handle_clock(payload)
        elif topic == "fleet/bids":
            self._handle_bid(payload)
        elif topic.startswith("amr/") and topic.endswith("/heartbeat"):
            self._handle_heartbeat(payload)
        elif topic.startswith("fleet/dispatch/"):
            self._handle_dispatch(payload)

    def _handle_sabotage(self, payload: dict | None = None) -> None:
        """Handle sabotage / kill command from MQTT message."""
        if payload and payload.get("agent_id") and payload.get("agent_id") != self.agent_id:
            return
        self.kill()

    def sabotage(self) -> None:
        """Permanently sabotage and deactivate the AMR."""
        self.kill()

    def kill(self) -> None:
        """Enforce strict, permanent agent deactivation upon sabotage or kill command."""
        self.status = "DEAD"
        self._crashed = True
        self.current_path = []
        self.current_goal = None
        self.goal = None
        self.intended_next_pos = None

        # If holding an active task, mark it unassigned/failed so CNP can salvage it
        if self.active_task is not None:
            task = self.active_task
            task["claimed"] = False
            task["claimed_by"] = None
            task["status"] = "PENDING"
            task["state"] = "PENDING"
            self.metrics_collector.record_task_failed()
            self.tasks_failed += 1
            self.active_task = None

        # Clear any pending task bidding state
        if self.pending_task is not None:
            self.pending_task["claimed"] = False
            self.pending_task["claimed_by"] = None
            self.pending_task["status"] = "PENDING"
            self.pending_task["state"] = "PENDING"
            self.pending_task = None
            self.bid_cost = None
            self.bid_broadcast_time = None

        # Immediately publish terminal DEAD telemetry to inform peers and frontend
        try:
            terminal_telemetry = {
                "agent_id": self.agent_id,
                "x": self.current_pos[0],
                "y": self.current_pos[1],
                "time": self.local_time,
                "battery": round(self.battery, 1),
                "priority": self.priority,
                "status": "DEAD",
                "intended_next_pos": None,
                "next_pos": self.current_pos,
            }
            self.client.publish("fleet/telemetry", json.dumps(terminal_telemetry), qos=1)
        except Exception:
            pass

        logger.warning(f"Agent '{self.agent_id}' permanently deactivated (status=DEAD, _crashed=True)")

    def _handle_telemetry(self, payload: dict) -> None:
        """Track live position and intent of peer robots."""
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
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

        status = payload.get("status", "DOCKED")
        if sender_id in self.peer_positions and self.peer_positions[sender_id].get("status") == "OFFLINE" and status != "OFFLINE":
            status = "OFFLINE"

        self.peer_positions[sender_id] = {
            "pos": (x, y),
            "next_pos": next_pos,
            "intended_next_pos": next_pos,
            "priority": payload.get("priority", 1),
            "status": status,
        }

    def _handle_heartbeat(self, payload: dict) -> None:
        """Track heartbeat and vitality of peer robots."""
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
        sender_id = payload.get("agent_id")
        if not sender_id or sender_id == self.agent_id:
            return
        tick = payload.get("tick")
        if tick is not None:
            self.peer_last_seen_tick[sender_id] = tick

        pos = payload.get("position")
        status = payload.get("status", "ACTIVE")
        if pos is not None and isinstance(pos, (list, tuple)) and len(pos) >= 2:
            pos_tuple = (int(pos[0]), int(pos[1]))
            if sender_id in self.peer_positions:
                self.peer_positions[sender_id]["pos"] = pos_tuple
                if self.peer_positions[sender_id].get("status") != "OFFLINE":
                    self.peer_positions[sender_id]["status"] = status
            else:
                self.peer_positions[sender_id] = {
                    "pos": pos_tuple,
                    "next_pos": pos_tuple,
                    "intended_next_pos": pos_tuple,
                    "priority": 1,
                    "status": status,
                }

    def _handle_intent(self, payload: dict) -> None:
        """Process peer robot's path intent and update dynamic reservations.

        Args:
            payload: JSON payload containing sender_id, path, and priority.
        """
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
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
                        self.plan_to_goal(*self.current_goal, is_replan=True, reason="conflict")

    def _handle_bid(self, payload: dict) -> None:
        """Process peer robot's bid for a task.

        Args:
            payload: JSON payload containing sender_id, task, bid_cost, and priority.
        """
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
        sender_id = payload.get("sender_id")
        task = payload.get("task")
        sender_bid_cost = payload.get("bid_cost")
        sender_priority = payload.get("priority", 1)

        if sender_id == self.agent_id:
            return  # Ignore own bids

        # If we're bidding on the same task, compare bid costs
        same_task = False
        if self.pending_task and task:
            if self.pending_task.get("id") and task.get("id"):
                same_task = (self.pending_task["id"] == task["id"])
            else:
                same_task = (self.pending_task.get("x") == task.get("x") and self.pending_task.get("y") == task.get("y"))

        if same_task and self.bid_cost is not None and sender_bid_cost is not None:
            # Lower bid cost wins (lower is better)
            other_wins = False
            if sender_bid_cost < self.bid_cost:
                other_wins = True
            elif sender_bid_cost == self.bid_cost:
                if sender_priority > self.priority:
                    other_wins = True
                elif sender_priority == self.priority and sender_id < self.agent_id:
                    other_wins = True

            if other_wins:
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

    def publish_heartbeat(self, tick: int | None = None) -> None:
        """Publish heartbeat payload to amr/{agent_id}/heartbeat."""
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
        current_tick = self.local_time if tick is None else tick
        payload = {
            "agent_id": self.agent_id,
            "tick": current_tick,
            "position": self.position,
            "status": self.status,
        }
        try:
            self.client.publish(f"amr/{self.agent_id}/heartbeat", json.dumps(payload), qos=1)
        except Exception:
            pass

    def check_peer_vitality(self, current_tick: int, threshold: int = 5) -> list[str]:
        """Identify any known peer where (current_tick - peer_last_seen_tick[peer_id]) >= threshold.

        Marks peer as status = 'OFFLINE' and locks the failed peer's last known coordinate (x, y)
        as a permanent obstacle in local Time-Space A* search space and dynamic reservation tables
        across all future time steps.

        Returns:
            List of newly identified offline peer agent IDs.
        """
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return []
        newly_offline = []
        for peer_id, last_tick in list(self.peer_last_seen_tick.items()):
            if peer_id == self.agent_id:
                continue
            peer_info = self.peer_positions.get(peer_id, {})
            if peer_info.get("status") == "OFFLINE":
                continue

            if (current_tick - last_tick) >= threshold:
                if peer_id not in self.peer_positions:
                    self.peer_positions[peer_id] = {"status": "OFFLINE", "priority": 1}
                else:
                    self.peer_positions[peer_id]["status"] = "OFFLINE"

                pos = self.peer_positions[peer_id].get("pos")
                if pos is not None:
                    # Fail-safe spatial isolation: Lock stranded robot's position as obstacle
                    self.dynamic_obstacles.add(pos)
                    # Dynamic reservation tables across all future time steps
                    start_t = min(self.local_time, current_tick)
                    for t in range(start_t, start_t + 101):
                        if t not in self.dynamic_reservations:
                            self.dynamic_reservations[t] = set()
                        self.dynamic_reservations[t].add(pos)

                    # If current path intersects with the stranded robot, force immediate replan
                    if any((node[0], node[1]) == pos for node in self.current_path):
                        goal_to_use = self.current_goal or self.goal
                        if goal_to_use:
                            self.plan_to_goal(*goal_to_use, is_replan=True, reason="conflict")

                newly_offline.append(peer_id)
                logger.warning(
                    f"Agent '{self.agent_id}': Peer '{peer_id}' detected OFFLINE at tick {current_tick} "
                    f"(last heartbeat: tick {last_tick}, threshold: {threshold})"
                )
        return newly_offline

    def simulate_silent_crash(self) -> None:
        """Abruptly halt MQTT publishing and disconnect without sending a shutdown message."""
        self._crashed = True
        self.status = "OFFLINE"
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        logger.warning(f"Agent '{self.agent_id}' experienced a silent crash at pos {self.current_pos}")

    def step(self, tick: int | None = None) -> None:
        """Process simulation tick: broadcast heartbeat, check vitality, update bidding and position."""
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
        if tick is not None:
            self.local_time = tick

        # Broadcast heartbeat on each simulation tick
        self.publish_heartbeat(self.local_time)

        # Check peer vitality
        self.check_peer_vitality(self.local_time, threshold=5)

        # Run tick processing
        self._process_tick()

    def _handle_clock(self, payload: dict) -> None:
        """Process global clock tick, handle bidding, and update position along current path.

        Args:
            payload: JSON payload containing current simulation time.
        """
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
        tick = payload.get("time", self.local_time)
        self.step(tick)

    def _process_tick(self) -> None:
        """Internal routine executing bidding, movement, charging, and telemetry for the current tick."""
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
        current_time = time.time()

        # Sabotage check - only poll if explicitly enabled via environment variable
        if os.getenv("ENABLE_SABOTAGE_POLL", "0") == "1" and self._backend_available is not False and (current_time - self.last_sabotage_check > 2.0):
            self.last_sabotage_check = current_time
            try:
                res = requests.get("http://localhost:8000/api/sabotage/status", timeout=0.2)
                if self.agent_id in res.json().get("sabotaged", []):
                    self.kill()
                    return
                self._backend_available = True
            except Exception:
                self._backend_available = False

        # Handle yield cooldown - if cooldown expired, resume status
        if self.status == "YIELDING" and current_time >= self.yield_cooldown:
            if self.goal or self.current_goal:
                self.status = "RUNNING"
            else:
                self.status = "DOCKED" if self.current_pos in self.CHARGING_STATIONS else "ACTIVE"

        # Check if we won the bid (wait 1 tick after broadcasting)
        if (
            self.status not in ["DEAD", "OFFLINE"]
            and not getattr(self, "_crashed", False)
            and self.status in ["DOCKED", "ACTIVE"]
            and self.pending_task
            and self.bid_broadcast_time is not None 
            and self.local_time > self.bid_broadcast_time
        ):
            task = self.pending_task
            if not task.get("claimed", False) or task.get("claimed_by") == self.agent_id:
                task["claimed"] = True
                task["claimed_by"] = self.agent_id
                self.status = "RUNNING"
                self.active_task = task
                self.task_start_time = time.time()
                self.current_goal = (task["x"], task["y"])
                self.goal = (task["x"], task["y"])
                
                self.plan_to_goal(task["x"], task["y"], is_replan=False, reason="task_assignment")
            
            self.pending_task = None
            self.bid_cost = None
            self.bid_broadcast_time = None

        # Edge-AI Bidding Logic: Poll for tasks when DOCKED or ACTIVE (only if not currently bidding)
        if (
            self.status not in ["DEAD", "OFFLINE"]
            and not getattr(self, "_crashed", False)
            and self.status in ["DOCKED", "ACTIVE"]
            and self.pending_task is None
        ):
            tasks = []
            if self.task_provider is not None:
                try:
                    tasks = self.task_provider()
                except Exception:
                    tasks = []
            elif self._backend_available is not False:
                try:
                    res = requests.get("http://localhost:8000/api/tasks", timeout=0.2)
                    tasks = res.json().get("tasks", [])
                    self._backend_available = True
                except Exception:
                    self._backend_available = False

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

        prev_pos = self.current_pos
        current_real_time = time.time()

        if self.status in ["RUNNING", "YIELDING"] and self.current_path:
            # INDUSTRIAL GOVERNOR: Never process a step faster than step_interval of REAL time, ignoring tick bursts
            if current_real_time - self.last_move_time >= self.step_interval:
                self.last_move_time = current_real_time
                
                next_node = self.current_path[0]
                next_pos = (next_node[0], next_node[1])
                
                conflict = False
                blocking_peer_id = None
                
                for peer_id, peer_data in self.peer_positions.items():
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
                    self.metrics_collector.record_reactive_stop()
                    self.status = "YIELDING"
                    self.yield_ticks += 1
                    # Randomized backoff to shatter livelock symmetry (3 to 6 ticks)
                    if self.yield_ticks > random.randint(3, 6) and blocking_peer_id and blocking_peer_id in self.peer_positions:
                        self.metrics_collector.record_deadlock(resolved=False)
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
                        replan_success = False
                        if self.current_goal:
                            replan_success = self.plan_to_goal(*self.current_goal, is_replan=True, reason="deadlock")
                        
                        # 3. Cleanup temporary walls
                        for w in walls_added:
                            self.dynamic_obstacles.discard(w)
                            
                        self.yield_ticks = 0
                        self.last_replan_time = time.time()
                        if replan_success:
                            self.metrics_collector.record_deadlock(resolved=True)
                else:
                    self.status = "RUNNING"
                    self.yield_ticks = 0
                    self.current_path.pop(0)  # Consume the step
                    self.current_pos = next_pos
                    
        # Strict Docking Cleanup
        if self.status in ["RUNNING", "YIELDING"] and not self.current_path:
            if self.current_goal and self.current_pos == self.current_goal:
                if self.active_task is not None:
                    created_at = self.active_task.get("created_at", self.task_start_time)
                    duration = max(0.001, time.time() - created_at)
                    self.metrics_collector.record_task_completed(duration)
                    self.active_task = None

                # Only DOCKED if on a charging station
                if self.current_pos in self.CHARGING_STATIONS:
                    self.status = "DOCKED"
                else:
                    self.status = "ACTIVE"
                self.current_goal = None
                self.goal = None
                self.current_path = []

        if self.current_path:
            self.intended_next_pos = (self.current_path[0][0], self.current_path[0][1])
        else:
            self.intended_next_pos = None

        # 1. Hyper-charge ONLY if physically sitting on a Charging Station and DOCKED
        if self.status == "DOCKED" and self.current_pos in self.CHARGING_STATIONS:
            self.battery = min(100.0, self.battery + 5.0)
        else:
            # 2. Normal drain while working or moving
            self.battery = max(0.0, self.battery - 0.1)
            
            if self.battery == 0:
                self.kill()
                return
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
                if self.active_task is not None:
                    self.metrics_collector.record_task_failed()
                    self.active_task = None
                self.plan_to_goal(*nearest_dock, is_replan=False, reason="charging")

        # Auto-recovery: Force replan if stuck midway
        if self.status != "DEAD" and self.current_goal and not self.current_path:
            # Auto-recovery: Only force replan if we haven't just tried in the last 2 seconds
            if time.time() - getattr(self, "last_replan_time", 0) > 2.0:
                self.plan_to_goal(*self.current_goal, is_replan=True, reason="conflict")
                self.last_replan_time = time.time()

        # Record agent state tick distribution
        self.metrics_collector.record_agent_tick(self.agent_id, self.status)

        # Publish telemetry with status, intended next position, and next_pos
        self.publish_telemetry()

    def publish_telemetry(self) -> None:
        """Publish telemetry with status, intended next position, and next_pos."""
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
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
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return
        x = payload.get("x")
        y = payload.get("y")
        if x is None or y is None:
            return

        if self.status != "DEAD":
            self.status = "RUNNING"

        task_id = payload.get("task_id", f"task_{uuid.uuid4().hex[:6]}")
        self.active_task = {
            "id": task_id,
            "x": x,
            "y": y,
            "created_at": time.time(),
        }
        self.task_start_time = time.time()

        self.plan_to_goal(x, y, is_replan=False, reason="dispatch")

    def plan_to_goal(
        self,
        goal_x: int,
        goal_y: int,
        is_replan: bool = False,
        reason: str | None = None,
    ) -> bool:
        """Plan a path to the goal using Time-Space A* and broadcast intent.

        Args:
            goal_x: Goal X coordinate.
            goal_y: Goal Y coordinate.
            is_replan: Whether this plan call is a replan.
            reason: Reason for replanning ("conflict", "deadlock", etc.).

        Returns:
            True if path found, False otherwise.
        """
        if self.status in ["DEAD", "OFFLINE"] or getattr(self, "_crashed", False):
            return False

        if self.status in ["DOCKED", "IDLE", "ACTIVE"]:
            self.status = "RUNNING"

        self.last_replan_time = time.time()
        self.current_goal = (goal_x, goal_y)
        self.goal = (goal_x, goal_y)
        start_x, start_y = self.current_pos

        # Combine static obstacles with dynamic obstacles (dead robots, yielded spots) and solid peers
        solid_peers = {data["pos"] for data in self.peer_positions.values() if data.get("status") in ["DEAD", "DOCKED", "OFFLINE"] and "pos" in data}
        all_obstacles = self.obstacles | self.dynamic_obstacles | solid_peers

        # Plan path starting from current local time with performance timing
        t_start = time.perf_counter()
        path = time_space_astar(
            start=(start_x, start_y),
            goal=(goal_x, goal_y),
            grid_width=self.grid_size[0],
            grid_height=self.grid_size[1],
            static_obstacles=all_obstacles,
            dynamic_reservations=self.dynamic_reservations,
            max_time=self.local_time + 100,  # Reasonable horizon
            conflict_callback=self.metrics_collector.record_proactive_avoidance,
        )
        duration_ms = (time.perf_counter() - t_start) * 1000.0
        self.metrics_collector.record_planning_step(
            duration_ms=duration_ms,
            is_replan=is_replan,
            reason=reason,
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

        self.status = "RUNNING"

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