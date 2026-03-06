"""
GameState — discovery tracking, entity roster, tech state, and simulation.

DiscoveryState controls what the player can see and interact with.
EntityRoster tracks every entity instance and its location.
TechState tracks which technologies have been researched.
BioState + SimulationEngine handle non-player bio populations.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.celestial import Galaxy


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class DiscoveryState(Enum):
    UNKNOWN    = 0   # not rendered at all
    DETECTED   = 1   # adjacent to a known system; faint blip + "???"
    DISCOVERED = 2   # player has clicked to scan; full name/type revealed
    COLONIZED  = 3   # home system; brightest rendering + player ring


# ---------------------------------------------------------------------------
# Entity roster
# ---------------------------------------------------------------------------

@dataclass
class EntityInstance:
    """One stack of identical entities at a single location."""
    category: str    # "structure" | "bot" | "ship" | "bio"
    type_value: str  # e.g. "factory", "probe", "worker"
    location_id: str # system_id (ships/orbital) or body_id (surface structures/bots)
    count: int = 1


class EntityRoster:
    """Tracks all player entity instances across the galaxy."""

    def __init__(self) -> None:
        self._instances: list[EntityInstance] = []

    def add(self, category: str, type_value: str, location_id: str, count: int = 1) -> None:
        """Add count entities; merges into existing stack if same key."""
        for inst in self._instances:
            if (inst.category == category
                    and inst.type_value == type_value
                    and inst.location_id == location_id):
                inst.count += count
                return
        self._instances.append(EntityInstance(category, type_value, location_id, count))

    def remove(self, category: str, type_value: str, location_id: str, count: int = 1) -> bool:
        """Remove count entities. Returns False if insufficient."""
        for inst in self._instances:
            if (inst.category == category
                    and inst.type_value == type_value
                    and inst.location_id == location_id):
                if inst.count < count:
                    return False
                inst.count -= count
                if inst.count == 0:
                    self._instances.remove(inst)
                return True
        return False

    def total(self, category: str, type_value: str) -> int:
        """Total count of a specific entity type across all locations."""
        return sum(
            i.count for i in self._instances
            if i.category == category and i.type_value == type_value
        )

    def at(self, location_id: str) -> list[EntityInstance]:
        """All entity stacks at a given location."""
        return [i for i in self._instances if i.location_id == location_id]

    def by_category(self, category: str) -> list[EntityInstance]:
        """All stacks of a given category."""
        return [i for i in self._instances if i.category == category]

    def all(self) -> list[EntityInstance]:
        return list(self._instances)


# ---------------------------------------------------------------------------
# Tech state
# ---------------------------------------------------------------------------

class TechState:
    """Tracks researched technologies and in-progress research."""

    def __init__(self) -> None:
        self.researched: set[str] = set()
        # tech_id → accumulated research points
        self._progress: dict[str, float] = {}

    def can_research(self, tech_id: str) -> bool:
        """True if all prerequisites are satisfied and tech not already done."""
        from .models.tech import can_research as _can_research
        if tech_id in self.researched:
            return False
        return _can_research(tech_id, self.researched)

    def start_research(self, tech_id: str) -> bool:
        """Begin researching tech_id. Returns False if not unlockable."""
        if not self.can_research(tech_id):
            return False
        if tech_id not in self._progress:
            self._progress[tech_id] = 0.0
        return True

    def add_progress(self, tech_id: str, amount: float) -> bool:
        """Add research points. Returns True if the tech just completed."""
        from .models.tech import TECH_TREE
        if tech_id not in self._progress:
            return False
        self._progress[tech_id] += amount
        node = TECH_TREE.get(tech_id)
        if node and self._progress[tech_id] >= node.research_cost:
            self.researched.add(tech_id)
            del self._progress[tech_id]
            return True
        return False

    def progress_fraction(self, tech_id: str) -> float:
        """Return 0.0–1.0 completion fraction; 1.0 if already researched."""
        from .models.tech import TECH_TREE
        if tech_id in self.researched:
            return 1.0
        if tech_id not in self._progress:
            return 0.0
        node = TECH_TREE.get(tech_id)
        if not node or node.research_cost == 0:
            return 0.0
        return min(self._progress[tech_id] / node.research_cost, 1.0)

    def is_researched(self, tech_id: str) -> bool:
        return tech_id in self.researched

    def in_progress_ids(self) -> list[str]:
        return list(self._progress.keys())


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------

class GameState:
    """Tracks discovery, entity roster, tech state, and non-player simulation."""

    def __init__(self) -> None:
        from .simulation import BioState, SimulationEngine
        self.galaxy = None
        self._states: dict[str, DiscoveryState] = {}
        self.adjacency: dict[str, list[str]] = {}
        self.entity_roster: EntityRoster = EntityRoster()
        self.tech: TechState = TechState()
        self.bio_state: BioState = BioState()
        self.sim_engine: SimulationEngine = SimulationEngine(self)
        self._sim_events: list = []   # most-recent tick's events, for UI polling

    # ------------------------------------------------------------------
    # Factory

    @classmethod
    def new_game(cls, galaxy: "Galaxy", home_idx: int = 0) -> "GameState":
        from .models.entity import STARTING_ENTITIES

        gs = cls()
        gs.galaxy    = galaxy
        gs.adjacency = cls._build_adjacency(galaxy, k=3)

        # Discovery states
        for sys in galaxy.solar_systems:
            gs._states[sys.id] = DiscoveryState.UNKNOWN
        home = galaxy.solar_systems[home_idx]
        gs._states[home.id] = DiscoveryState.COLONIZED
        for nb_id in gs.adjacency.get(home.id, []):
            if gs._states[nb_id] == DiscoveryState.UNKNOWN:
                gs._states[nb_id] = DiscoveryState.DETECTED

        # Entity roster — resolve "home_body" / "home_system" location tokens
        home_system_id = home.id
        home_body_id   = (
            home.orbital_bodies[0].id if home.orbital_bodies else home.id
        )
        for cat, type_val, loc_token, count in STARTING_ENTITIES:
            loc_id = home_system_id if loc_token == "home_system" else home_body_id
            gs.entity_roster.add(cat, type_val, loc_id, count)

        # Bio populations — seed from bios resource values on all bodies
        gs._init_bio_state()

        # Build sim engine now that galaxy and bio_state are populated
        from .simulation import SimulationEngine
        gs.sim_engine = SimulationEngine(gs)

        return gs

    def _init_bio_state(self) -> None:
        """Scan every body in the galaxy and spawn BioPopulations where bios > 0."""
        from .simulation import make_bio_population
        if not self.galaxy:
            return
        rng = random.Random(self.galaxy.seed ^ 0xB10B1AB)
        for sys in self.galaxy.solar_systems:
            for body in sys.orbital_bodies:
                if body.resources.bios > 0:
                    self.bio_state.add(
                        make_bio_population(body.id, sys.id, body.resources.bios, rng)
                    )
                for moon in body.moons:
                    if moon.resources.bios > 0:
                        self.bio_state.add(
                            make_bio_population(moon.id, sys.id, moon.resources.bios, rng)
                        )

    # ------------------------------------------------------------------
    # Simulation tick

    def tick(self, dt_years: float) -> None:
        """Advance the non-player simulation. Called every game frame when unpaused."""
        self._sim_events = self.sim_engine.tick(dt_years)

    def pop_sim_events(self) -> list:
        """Return and clear the most-recent sim events (for UI notification)."""
        events = list(self._sim_events)
        self._sim_events = []
        return events

    # ------------------------------------------------------------------
    # Adjacency

    @staticmethod
    def _build_adjacency(galaxy: "Galaxy", k: int = 3) -> dict[str, list[str]]:
        systems = galaxy.solar_systems
        adj: dict[str, list[str]] = {s.id: [] for s in systems}
        for i, sys_a in enumerate(systems):
            ax, ay = sys_a.position["x"], sys_a.position["y"]
            distances = []
            for j, sys_b in enumerate(systems):
                if i == j:
                    continue
                bx, by = sys_b.position["x"], sys_b.position["y"]
                distances.append((math.hypot(bx - ax, by - ay), sys_b.id))
            distances.sort()
            for _, nb_id in distances[:k]:
                if nb_id not in adj[sys_a.id]:
                    adj[sys_a.id].append(nb_id)
                if sys_a.id not in adj[nb_id]:
                    adj[nb_id].append(sys_a.id)
        return adj

    # ------------------------------------------------------------------
    # Discovery accessors / mutations

    def get_state(self, system_id: str) -> DiscoveryState:
        return self._states.get(system_id, DiscoveryState.UNKNOWN)

    def can_enter(self, system_id: str) -> bool:
        return self._states.get(system_id, DiscoveryState.UNKNOWN) in (
            DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED
        )

    def discover_system(self, system_id: str) -> None:
        current = self._states.get(system_id, DiscoveryState.UNKNOWN)
        if current in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
            return
        self._states[system_id] = DiscoveryState.DISCOVERED
        for nb_id in self.adjacency.get(system_id, []):
            if self._states.get(nb_id, DiscoveryState.UNKNOWN) == DiscoveryState.UNKNOWN:
                self._states[nb_id] = DiscoveryState.DETECTED

    def discovered_count(self) -> int:
        return sum(
            1 for s in self._states.values()
            if s in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED)
        )
