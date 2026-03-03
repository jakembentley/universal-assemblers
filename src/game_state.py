"""
GameState — discovery tracking and adjacency graph for the galaxy map.

DiscoveryState controls what the player can see and interact with.
The adjacency graph (K-nearest neighbours) drives fog-of-war propagation.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.celestial import Galaxy


class DiscoveryState(Enum):
    UNKNOWN    = 0   # not rendered at all
    DETECTED   = 1   # adjacent to a known system; faint blip + "???"
    DISCOVERED = 2   # player has clicked to scan; full name/type revealed
    COLONIZED  = 3   # home system; brightest rendering + player ring


class GameState:
    """Tracks per-system discovery state and the adjacency graph."""

    def __init__(self) -> None:
        self.galaxy = None
        # system_id → DiscoveryState
        self._states: dict[str, DiscoveryState] = {}
        # system_id → [neighbour_ids]
        self.adjacency: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Factory

    @classmethod
    def new_game(cls, galaxy: "Galaxy", home_idx: int = 0) -> "GameState":
        gs = cls()
        gs.galaxy = galaxy
        gs.adjacency = cls._build_adjacency(galaxy, k=3)

        # All systems start UNKNOWN
        for sys in galaxy.solar_systems:
            gs._states[sys.id] = DiscoveryState.UNKNOWN

        # Home system → COLONIZED
        home = galaxy.solar_systems[home_idx]
        gs._states[home.id] = DiscoveryState.COLONIZED

        # Neighbours of home → DETECTED
        for nb_id in gs.adjacency.get(home.id, []):
            if gs._states[nb_id] == DiscoveryState.UNKNOWN:
                gs._states[nb_id] = DiscoveryState.DETECTED

        return gs

    # ------------------------------------------------------------------
    # Adjacency

    @staticmethod
    def _build_adjacency(galaxy: "Galaxy", k: int = 3) -> dict[str, list[str]]:
        """Connect each system to its k nearest neighbours (bidirectional)."""
        systems = galaxy.solar_systems
        adj: dict[str, list[str]] = {s.id: [] for s in systems}

        for i, sys_a in enumerate(systems):
            ax, ay = sys_a.position["x"], sys_a.position["y"]
            # Compute distances to every other system
            distances = []
            for j, sys_b in enumerate(systems):
                if i == j:
                    continue
                bx, by = sys_b.position["x"], sys_b.position["y"]
                d = math.hypot(bx - ax, by - ay)
                distances.append((d, sys_b.id))
            distances.sort()
            # Take k nearest
            for _, nb_id in distances[:k]:
                if nb_id not in adj[sys_a.id]:
                    adj[sys_a.id].append(nb_id)
                if sys_a.id not in adj[nb_id]:
                    adj[nb_id].append(sys_a.id)

        return adj

    # ------------------------------------------------------------------
    # Accessors

    def get_state(self, system_id: str) -> DiscoveryState:
        return self._states.get(system_id, DiscoveryState.UNKNOWN)

    def can_enter(self, system_id: str) -> bool:
        return self._states.get(system_id, DiscoveryState.UNKNOWN) in (
            DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED
        )

    # ------------------------------------------------------------------
    # Mutations

    def discover_system(self, system_id: str) -> None:
        """Mark system as DISCOVERED; reveal UNKNOWN neighbours as DETECTED."""
        current = self._states.get(system_id, DiscoveryState.UNKNOWN)
        if current in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
            return  # already known
        self._states[system_id] = DiscoveryState.DISCOVERED
        for nb_id in self.adjacency.get(system_id, []):
            if self._states.get(nb_id, DiscoveryState.UNKNOWN) == DiscoveryState.UNKNOWN:
                self._states[nb_id] = DiscoveryState.DETECTED

    # ------------------------------------------------------------------
    # Stats

    def discovered_count(self) -> int:
        return sum(
            1 for s in self._states.values()
            if s in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED)
        )
