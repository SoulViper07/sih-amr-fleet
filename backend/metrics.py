"""Fleet Performance Metrics Collector for decentralized multi-agent AMR warehouse simulation."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class FleetMetricsCollector:
    """Thread-safe singleton metrics collector tracking task, algorithmic, safety, and efficiency metrics.

    Maintains strictly O(1) constant memory footprint using running accumulators and counters.
    """

    _instance: FleetMetricsCollector | None = None
    _singleton_lock = threading.Lock()

    def __init__(self, num_agents: int = 6) -> None:
        """Initialize the metrics collector."""
        self._lock = threading.Lock()
        self.num_agents = num_agents
        self._known_agents: set[str] = set()

        # Task Metrics
        self.tasks_created: int = 0
        self.tasks_completed: int = 0
        self.tasks_failed: int = 0
        self.total_task_duration_seconds: float = 0.0

        # Path Planning & Algorithmic Metrics
        self.total_path_plans: int = 0
        self.total_planning_time_ms: float = 0.0
        self.max_planning_time_ms: float = 0.0
        self.total_replans: int = 0
        self.replans_due_to_conflict: int = 0
        self.replans_due_to_deadlock: int = 0

        # Safety & Conflict Metrics
        self.proactive_conflicts_avoided: int = 0
        self.reactive_stops_triggered: int = 0
        self.deadlocks_detected: int = 0
        self.deadlocks_resolved: int = 0

        # Fault-Tolerance & Resilience Metrics
        self.silent_failures_detected: int = 0
        self.tasks_reassigned: int = 0

        # Fleet Efficiency Metrics
        self.total_ticks: int = 0
        self.active_agent_ticks: int = 0
        self.idle_agent_ticks: int = 0
        self.charging_agent_ticks: int = 0

    @classmethod
    def get_instance(cls, num_agents: int = 6) -> FleetMetricsCollector:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls(num_agents=num_agents)
        return cls._instance

    def record_task_created(self) -> None:
        """Record the creation/injection of a new task."""
        with self._lock:
            self.tasks_created += 1

    def record_task_completed(self, duration: float) -> None:
        """Record task completion with end-to-end duration in seconds."""
        with self._lock:
            self.tasks_completed += 1
            self.total_task_duration_seconds += max(0.0, float(duration))

    def record_task_failed(self) -> None:
        """Record task failure."""
        with self._lock:
            self.tasks_failed += 1

    def record_planning_step(
        self,
        duration_ms: float,
        is_replan: bool = False,
        reason: str | None = None,
    ) -> None:
        """Record a Time-Space A* path planning execution."""
        with self._lock:
            self.total_path_plans += 1
            dur = max(0.0, float(duration_ms))
            self.total_planning_time_ms += dur
            if dur > self.max_planning_time_ms:
                self.max_planning_time_ms = dur

            if is_replan:
                self.total_replans += 1
                if reason == "conflict":
                    self.replans_due_to_conflict += 1
                elif reason == "deadlock":
                    self.replans_due_to_deadlock += 1

    def record_proactive_avoidance(self) -> None:
        """Record proactive conflict avoidance in Time-Space A* search."""
        with self._lock:
            self.proactive_conflicts_avoided += 1

    @property
    def proactive_conflicts(self) -> int:
        """Alias for proactive_conflicts_avoided."""
        return self.proactive_conflicts_avoided

    @proactive_conflicts.setter
    def proactive_conflicts(self, val: int) -> None:
        with self._lock:
            self.proactive_conflicts_avoided = val

    def record_reactive_stop(self) -> None:
        """Record reactive stop/yield triggered by Layer 2 collision check."""
        with self._lock:
            self.reactive_stops_triggered += 1

    def record_deadlock(self, resolved: bool = False) -> None:
        """Record deadlock detection or successful resolution."""
        with self._lock:
            if resolved:
                self.deadlocks_resolved += 1
            else:
                self.deadlocks_detected += 1

    def record_silent_failure(self) -> None:
        """Record a detected silent agent crash / heartbeat timeout."""
        with self._lock:
            self.silent_failures_detected += 1

    def record_task_reassigned(self) -> None:
        """Record a task salvaged from a failed agent and reassigned to CNP bidding."""
        with self._lock:
            self.tasks_reassigned += 1

    def record_clock_tick(self) -> None:
        """Record a global simulation clock tick."""
        with self._lock:
            self.total_ticks += 1

    def record_agent_tick(self, agent_id: str, state: str) -> None:
        """Record an agent's state for the current tick."""
        with self._lock:
            self._known_agents.add(agent_id)
            normalized = state.upper() if state else "IDLE"
            if normalized in ("RUNNING", "YIELDING", "MOVING"):
                self.active_agent_ticks += 1
            elif normalized in ("DOCKED", "CHARGING"):
                self.charging_agent_ticks += 1
            else:
                self.idle_agent_ticks += 1

    def update_from_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Update metrics from an external snapshot dictionary (e.g. via MQTT sync)."""
        with self._lock:
            for key in (
                "tasks_created",
                "tasks_completed",
                "tasks_failed",
                "total_task_duration_seconds",
                "total_path_plans",
                "total_planning_time_ms",
                "max_planning_time_ms",
                "total_replans",
                "replans_due_to_conflict",
                "replans_due_to_deadlock",
                "proactive_conflicts_avoided",
                "reactive_stops_triggered",
                "deadlocks_detected",
                "deadlocks_resolved",
                "silent_failures_detected",
                "tasks_reassigned",
                "total_ticks",
                "active_agent_ticks",
                "idle_agent_ticks",
                "charging_agent_ticks",
            ):
                if key in snapshot:
                    val = snapshot[key]
                    current_val = getattr(self, key)
                    if isinstance(current_val, float):
                        setattr(self, key, max(current_val, float(val)))
                    elif isinstance(current_val, int):
                        setattr(self, key, max(current_val, int(val)))

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        with self._lock:
            self._known_agents.clear()
            self.tasks_created = 0
            self.tasks_completed = 0
            self.tasks_failed = 0
            self.total_task_duration_seconds = 0.0
            self.total_path_plans = 0
            self.total_planning_time_ms = 0.0
            self.max_planning_time_ms = 0.0
            self.total_replans = 0
            self.replans_due_to_conflict = 0
            self.replans_due_to_deadlock = 0
            self.proactive_conflicts_avoided = 0
            self.reactive_stops_triggered = 0
            self.deadlocks_detected = 0
            self.deadlocks_resolved = 0
            self.silent_failures_detected = 0
            self.tasks_reassigned = 0
            self.total_ticks = 0
            self.active_agent_ticks = 0
            self.idle_agent_ticks = 0
            self.charging_agent_ticks = 0

    def get_snapshot(self) -> dict[str, Any]:
        """Return snapshot dictionary of all computed metrics."""
        with self._lock:
            total_finished = self.tasks_completed + self.tasks_failed
            if total_finished > 0:
                task_success_rate = round((self.tasks_completed / total_finished) * 100.0, 2)
            else:
                task_success_rate = 0.0

            avg_task_completion_time = (
                round(self.total_task_duration_seconds / self.tasks_completed, 2)
                if self.tasks_completed > 0
                else 0.0
            )

            avg_planning_time = (
                round(self.total_planning_time_ms / self.total_path_plans, 2)
                if self.total_path_plans > 0
                else 0.0
            )

            agent_count = len(self._known_agents) if self._known_agents else self.num_agents
            total_possible_agent_ticks = self.total_ticks * max(1, agent_count)
            fleet_utilization = (
                round((self.active_agent_ticks / total_possible_agent_ticks) * 100.0, 2)
                if total_possible_agent_ticks > 0
                else 0.0
            )

            return {
                "tasks_created": self.tasks_created,
                "tasks_completed": self.tasks_completed,
                "tasks_failed": self.tasks_failed,
                "task_success_rate": task_success_rate,
                "total_task_duration_seconds": round(self.total_task_duration_seconds, 2),
                "avg_task_completion_time_seconds": avg_task_completion_time,
                "total_path_plans": self.total_path_plans,
                "total_planning_time_ms": round(self.total_planning_time_ms, 2),
                "avg_planning_time_ms": avg_planning_time,
                "max_planning_time_ms": round(self.max_planning_time_ms, 2),
                "total_replans": self.total_replans,
                "replans_due_to_conflict": self.replans_due_to_conflict,
                "replans_due_to_deadlock": self.replans_due_to_deadlock,
                "proactive_conflicts_avoided": self.proactive_conflicts_avoided,
                "reactive_stops_triggered": self.reactive_stops_triggered,
                "deadlocks_detected": self.deadlocks_detected,
                "deadlocks_resolved": self.deadlocks_resolved,
                "silent_failures_detected": self.silent_failures_detected,
                "tasks_reassigned": self.tasks_reassigned,
                "total_ticks": self.total_ticks,
                "active_agent_ticks": self.active_agent_ticks,
                "idle_agent_ticks": self.idle_agent_ticks,
                "charging_agent_ticks": self.charging_agent_ticks,
                "fleet_utilization": fleet_utilization,
            }


def get_collector() -> FleetMetricsCollector:
    """Convenience getter for singleton FleetMetricsCollector."""
    return FleetMetricsCollector.get_instance()
