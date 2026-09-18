"""Time-Space A* algorithm for multi-robot path planning with dynamic obstacle avoidance."""

from __future__ import annotations

import heapq
from typing import Callable, TypeAlias

Coord: TypeAlias = tuple[int, int]
State: TypeAlias = tuple[int, int, int]


def time_space_astar(
    start: Coord,
    goal: Coord,
    grid_width: int,
    grid_height: int,
    static_obstacles: set[Coord],
    dynamic_reservations: dict[int, set[Coord]] | set[State],
    max_time: int | None = None,
    max_iterations: int = 5000,
    conflict_callback: Callable[[], None] | None = None,
    start_time: int = 0,
) -> list[State] | None:
    """Find a time-space path from start to goal avoiding static and dynamic obstacles.

    Args:
        start: Starting (x, y) coordinate.
        goal: Goal (x, y) coordinate.
        grid_width: Width of the grid.
        grid_height: Height of the grid.
        static_obstacles: Set of (x, y) coordinates that are permanently blocked.
        dynamic_reservations: Mapping of time step -> set of reserved (x, y) coordinates, or flat set of (x, y, t).
        max_time: Maximum time steps to search before giving up.
        max_iterations: Safety circuit breaker to prevent search state explosion.
        conflict_callback: Callback triggered when dynamic reservations force a detour or wait.
        start_time: Starting simulation time/tick (default 0).

    Returns:
        List of (x, y, t) states representing the path, or None if no path found.
    """
    start_x, start_y = start
    goal_x, goal_y = goal

    # Cap search horizon to prevent state explosion
    max_horizon = 60
    effective_max_time = start_time + max_horizon
    if max_time is not None:
        effective_max_time = min(max_time, start_time + max_horizon)

    # Prune past reservations and build an ultra-fast O(1) lookup set of (x, y, t) tuples
    if isinstance(dynamic_reservations, set):
        res_set: set[State] = {
            (x, y, t)
            for (x, y, t) in dynamic_reservations
            if t >= start_time and t <= effective_max_time + 1
        }
    elif isinstance(dynamic_reservations, dict):
        res_set = {
            (x, y, t)
            for t, coords in dynamic_reservations.items()
            if t >= start_time and t <= effective_max_time + 1
            for (x, y) in coords
        }
    else:
        res_set = set()

    # Early exit if start or goal is invalid
    if not (0 <= start_x < grid_width and 0 <= start_y < grid_height):
        return None
    if not (0 <= goal_x < grid_width and 0 <= goal_y < grid_height):
        return None
    if start in static_obstacles or goal in static_obstacles:
        return None
    if (start_x, start_y, start_time) in res_set:
        return None

    # If already at goal, return immediate path
    if start == goal:
        return [(start_x, start_y, start_time)]

    # Movement directions: (dx, dy) for Up, Down, Left, Right, Wait
    moves = [(0, 1), (0, -1), (-1, 0), (1, 0), (0, 0)]

    def heuristic(x: int, y: int) -> int:
        """Manhattan distance heuristic."""
        return abs(x - goal_x) + abs(y - goal_y)

    had_dynamic_conflict = False

    def is_valid_move(
        curr_x: int,
        curr_y: int,
        next_x: int,
        next_y: int,
        t: int,
    ) -> bool:
        nonlocal had_dynamic_conflict
        next_t = t + 1

        # Time limit check
        if next_t > effective_max_time:
            return False

        # Bounds check
        if not (0 <= next_x < grid_width and 0 <= next_y < grid_height):
            return False

        # Static obstacle check
        if (next_x, next_y) in static_obstacles:
            return False

        # Vertex collision check at next time step: O(1) tuple set lookup
        if (next_x, next_y, next_t) in res_set:
            had_dynamic_conflict = True
            return False

        # Edge/Swap collision check: O(1) tuple set lookups
        if (next_x, next_y, t) in res_set and (curr_x, curr_y, next_t) in res_set:
            had_dynamic_conflict = True
            return False

        return True

    # Priority queue: (f_score, g_score, x, y, t)
    open_set: list[tuple[int, int, int, int, int]] = []
    start_h = heuristic(start_x, start_y)
    heapq.heappush(open_set, (start_h, 0, start_x, start_y, start_time))

    # Track visited states and their g-scores for pruning
    g_scores: dict[State, int] = {(start_x, start_y, start_time): 0}
    # Track parents for path reconstruction
    parents: dict[State, State | None] = {(start_x, start_y, start_time): None}

    iterations = 0
    while open_set:
        iterations += 1
        if iterations > max_iterations:
            print(f"[TimeSpaceA*] Circuit breaker triggered! Iterations exceeded {max_iterations}. Aborting search.")
            return None

        f_score, g_score, x, y, t = heapq.heappop(open_set)

        current_state = (x, y, t)

        # Skip if we've found a better path to this state
        if g_scores.get(current_state, float("inf")) < g_score:
            continue

        # Check if reached goal
        if (x, y) == goal:
            # Reconstruct path
            path: list[State] = []
            state: State | None = current_state
            while state is not None:
                path.append(state)
                state = parents[state]
            path.reverse()

            # Record proactive conflict exactly ONCE per path planning request
            if conflict_callback is not None and had_dynamic_conflict:
                nominal_dist = abs(goal_x - start_x) + abs(goal_y - start_y)
                path_duration = path[-1][2] - path[0][2]
                has_wait_step = any(
                    path[i][0] == path[i + 1][0] and path[i][1] == path[i + 1][1]
                    for i in range(len(path) - 1)
                )
                if path_duration > nominal_dist or has_wait_step:
                    conflict_callback()

            return path

        # Expand neighbors
        for dx, dy in moves:
            next_x, next_y = x + dx, y + dy
            next_t = t + 1

            if not is_valid_move(x, y, next_x, next_y, t):
                continue

            next_state = (next_x, next_y, next_t)
            tentative_g = g_score + 1

            # Skip if we've already found a better or equal path to this state
            if tentative_g >= g_scores.get(next_state, float("inf")):
                continue

            g_scores[next_state] = tentative_g
            parents[next_state] = current_state
            h = heuristic(next_x, next_y)
            heapq.heappush(open_set, (tentative_g + h, tentative_g, next_x, next_y, next_t))

    return None