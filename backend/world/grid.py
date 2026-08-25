"""Warehouse grid environment for multi-robot simulation."""

from typing import Dict, List, Tuple


class WarehouseGrid:
    """2D grid environment representing a warehouse with obstacles and agents."""

    def __init__(
        self,
        width: int,
        height: int,
        obstacles: List[Tuple[int, int]] | None = None
    ) -> None:
        """Initialize the warehouse grid.

        Args:
            width: Grid width in cells.
            height: Grid height in cells.
            obstacles: List of (x, y) tuples representing obstacle coordinates.
        """
        self.width = width
        self.height = height
        self.obstacles = set(obstacles) if obstacles else set()
        self._agents: Dict[str, Tuple[int, int]] = {}

    def is_valid_coord(self, x: int, y: int) -> bool:
        """Check if a coordinate is within bounds and not an obstacle.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if coordinate is valid, False otherwise.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return (x, y) not in self.obstacles

    def update_agent(self, agent_id: str, x: int, y: int) -> None:
        """Add or update an agent's position.

        Args:
            agent_id: Unique identifier for the agent.
            x: X coordinate.
            y: Y coordinate.

        Raises:
            ValueError: If the coordinate is invalid.
        """
        if not self.is_valid_coord(x, y):
            raise ValueError(f"Invalid coordinate ({x}, {y}) for agent {agent_id}")
        self._agents[agent_id] = (x, y)

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the grid.

        Args:
            agent_id: Unique identifier for the agent.
        """
        self._agents.pop(agent_id, None)

    def get_agent_position(self, agent_id: str) -> Tuple[int, int] | None:
        """Get an agent's current position.

        Args:
            agent_id: Unique identifier for the agent.

        Returns:
            (x, y) tuple if agent exists, None otherwise.
        """
        return self._agents.get(agent_id)

    def get_state(self) -> dict:
        """Return the current grid state as a dictionary.

        Returns:
            Dictionary containing width, height, obstacles, and agent positions.
        """
        return {
            "width": self.width,
            "height": self.height,
            "obstacles": list(self.obstacles),
            "agents": {agent_id: pos for agent_id, pos in self._agents.items()}
        }