"""Time-Space A* algorithm for multi-robot path planning with dynamic obstacle avoidance."""

from __future__ import annotations

import heapq
from typing import TypeAlias

Coord: TypeAlias = tuple[int, int]
State: TypeAlias = tuple[int, int, int]


def time_space_astar(
    start: Coord,
    goal: Coord,
    grid_width: int,
    grid_height: int,
    static_obstacles: set[Coord],
    dynamic_reservations: dict[int, set[Coord]],
    max_time: int = 100,
    max_iterations: int = 5000,
) -> list[State] | None:
    """Find a time-space path from start to goal avoiding static and dynamic obstacles.

    Args:
        start: Starting (x, y) coordinate.
        goal: Goal (x, y) coordinate.
        grid_width: Width of the grid.
        grid_height: Height of the grid.
        static_obstacles: Set of (x, y) coordinates that are permanently blocked.
        dynamic_reservations: Mapping of time step -> set of reserved (x, y) coordinates.
        max_time: Maximum time steps to search before giving up.
        max_iterations: Safety circuit breaker to prevent search state explosion.

    Returns:
        List of (x, y, t) states representing the path, or None if no path found.
    """
    start_x, start_y = start
    goal_x, goal_y = goal

    # Early exit if start or goal is invalid
    if not (0 <= start_x < grid_width and 0 <= start_y < grid_height):
        return None
    if not (0 <= goal_x < grid_width and 0 <= goal_y < grid_height):
        return None
    if start in static_obstacles or goal in static_obstacles:
        return None
    if start in dynamic_reservations.get(0, set()):
        return None

    # If already at goal, return immediate path
    if start == goal:
        return [(start_x, start_y, 0)]

    # Movement directions: (dx, dy) for Up, Down, Left, Right, Wait
    moves = [(0, 1), (0, -1), (-1, 0), (1, 0), (0, 0)]

    def heuristic(x: int, y: int) -> int:
        """Manhattan distance heuristic."""
        return abs(x - goal_x) + abs(y - goal_y)

    def is_valid_move(
        curr_x: int,
        curr_y: int,
        next_x: int,
        next_y: int,
        t: int,
    ) -> bool:
        """Check if move from (curr_x, curr_y) at time t to (next_x, next_y) at t+1 is valid."""
        next_t = t + 1

        # Time limit check
        if next_t > max_time:
            return False

        # Bounds check
        if not (0 <= next_x < grid_width and 0 <= next_y < grid_height):
            return False

        # Static obstacle check
        if (next_x, next_y) in static_obstacles:
            return False

        # Vertex collision check at next time step
        if (next_x, next_y) in dynamic_reservations.get(next_t, set()):
            return False

        # Edge/Swap collision check
        # If another agent occupies next position at time t AND current position at time t+1,
        # they would be swapping positions (crossing the same edge in opposite directions)
        if (next_x, next_y) in dynamic_reservations.get(t, set()):
            if (curr_x, curr_y) in dynamic_reservations.get(next_t, set()):
                return False

        return True

    # Priority queue: (f_score, g_score, x, y, t)
    open_set: list[tuple[int, int, int, int, int]] = []
    start_h = heuristic(start_x, start_y)
    heapq.heappush(open_set, (start_h, 0, start_x, start_y, 0))

    # Track visited states and their g-scores for pruning
    g_scores: dict[State, int] = {(start_x, start_y, 0): 0}
    # Track parents for path reconstruction
    parents: dict[State, State | None] = {(start_x, start_y, 0): None}

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