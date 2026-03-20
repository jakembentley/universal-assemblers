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
import uuid as _uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.celestial import Galaxy


# ---------------------------------------------------------------------------
# Bot tasks
# ---------------------------------------------------------------------------

@dataclass
class BotTask:
    """One assigned task for a bot type at a location."""
    task_type:       str           # "mine" | "build" | "transport"
    resource:        str | None    # mine/transport: "minerals"|"rare_minerals"|"ice"|"gas"|"bios"
    entity_type:     str | None    # build: entity type_value (e.g. "factory", "miner")
    target_amount:   int           # units to mine/transport OR entities to build
    progress:        float = 0.0   # accumulated progress (units extracted / build fraction)
    built_count:     int   = 0     # for build tasks: how many entities completed so far
    allocation:      int   = 10    # 0–100 % of bot time devoted to this task
    task_id:         str   = field(default_factory=lambda: _uuid.uuid4().hex[:8])
    target_location: str | None = None  # transport: destination body_id

    @property
    def complete(self) -> bool:
        if self.task_type == "mine":
            return self.progress >= self.target_amount
        if self.task_type == "transport":
            return self.progress >= self.target_amount
        return self.built_count >= self.target_amount


class BotTaskList:
    """All bot tasks keyed by (location_id, bot_type)."""

    def __init__(self) -> None:
        self._tasks: dict[str, list[BotTask]] = {}

    @staticmethod
    def _key(location_id: str, bot_type: str) -> str:
        return f"{location_id}:{bot_type}"

    def get(self, location_id: str, bot_type: str) -> list[BotTask]:
        return self._tasks.get(self._key(location_id, bot_type), [])

    def add(self, location_id: str, bot_type: str, task: BotTask) -> None:
        k = self._key(location_id, bot_type)
        if k not in self._tasks:
            self._tasks[k] = []
        self._tasks[k].append(task)

    def remove(self, location_id: str, bot_type: str, task_id: str) -> None:
        k = self._key(location_id, bot_type)
        self._tasks[k] = [t for t in self._tasks.get(k, []) if t.task_id != task_id]

    def adjust_allocation(
        self, location_id: str, bot_type: str, task_id: str, delta: int
    ) -> None:
        """Change a task's allocation; does not exceed total of 100%."""
        tasks = self.get(location_id, bot_type)
        task  = next((t for t in tasks if t.task_id == task_id), None)
        if not task:
            return
        used = sum(t.allocation for t in tasks if t.task_id != task_id)
        max_alloc = max(0, 100 - used)
        task.allocation = max(0, min(max_alloc, task.allocation + delta))

    def total_allocation(self, location_id: str, bot_type: str) -> int:
        return sum(t.allocation for t in self.get(location_id, bot_type))

    def all_keys(self) -> list[tuple[str, str]]:
        """Return all (location_id, bot_type) pairs that have tasks."""
        result = []
        for k in self._tasks:
            loc, btype = k.rsplit(":", 1)
            result.append((loc, btype))
        return result

    def to_dict(self) -> dict:
        result = {}
        for k, tasks in self._tasks.items():
            result[k] = [
                {
                    "task_type":       t.task_type,
                    "resource":        t.resource,
                    "entity_type":     t.entity_type,
                    "target_amount":   t.target_amount,
                    "progress":        t.progress,
                    "built_count":     t.built_count,
                    "allocation":      t.allocation,
                    "task_id":         t.task_id,
                    "target_location": t.target_location,
                }
                for t in tasks
            ]
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "BotTaskList":
        import uuid as _u
        btl = cls()
        for k, tasks in d.items():
            loc, btype = k.rsplit(":", 1)
            for td in tasks:
                btl.add(loc, btype, BotTask(
                    task_type=td["task_type"],
                    resource=td.get("resource"),
                    entity_type=td.get("entity_type"),
                    target_amount=td.get("target_amount", 0),
                    progress=td.get("progress", 0.0),
                    built_count=td.get("built_count", 0),
                    allocation=td.get("allocation", 10),
                    task_id=td.get("task_id", _u.uuid4().hex[:8]),
                    target_location=td.get("target_location"),
                ))
        return btl


# ---------------------------------------------------------------------------
# Factory tasks
# ---------------------------------------------------------------------------

@dataclass
class FactoryTask:
    """One production run assigned to factories at a location."""
    recipe_id:     str    # key into FACTORY_RECIPES
    target_amount: float  # units to produce (0 = unlimited/continuous)
    allocation:    int   = 25    # 0–100 % of factory throughput
    produced:      float = 0.0
    task_id:       str   = field(default_factory=lambda: _uuid.uuid4().hex[:8])

    @property
    def complete(self) -> bool:
        return self.target_amount > 0 and self.produced >= self.target_amount


class FactoryTaskList:
    """Factory production tasks keyed by location_id."""

    def __init__(self) -> None:
        self._tasks: dict[str, list[FactoryTask]] = {}

    def get(self, location_id: str) -> list[FactoryTask]:
        return self._tasks.get(location_id, [])

    def add(self, location_id: str, task: FactoryTask) -> None:
        if location_id not in self._tasks:
            self._tasks[location_id] = []
        self._tasks[location_id].append(task)

    def remove(self, location_id: str, task_id: str) -> None:
        self._tasks[location_id] = [
            t for t in self._tasks.get(location_id, []) if t.task_id != task_id
        ]

    def adjust_allocation(self, location_id: str, task_id: str, delta: int) -> None:
        tasks = self.get(location_id)
        task = next((t for t in tasks if t.task_id == task_id), None)
        if not task:
            return
        used = sum(t.allocation for t in tasks if t.task_id != task_id)
        task.allocation = max(0, min(max(0, 100 - used), task.allocation + delta))

    def total_allocation(self, location_id: str) -> int:
        return sum(t.allocation for t in self.get(location_id))

    def all_keys(self) -> list[str]:
        return list(self._tasks.keys())

    def to_dict(self) -> dict:
        return {
            loc: [
                {"recipe_id": t.recipe_id, "target_amount": t.target_amount,
                 "allocation": t.allocation, "produced": t.produced, "task_id": t.task_id}
                for t in tasks
            ]
            for loc, tasks in self._tasks.items()
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FactoryTaskList":
        import uuid as _u
        ftl = cls()
        for loc, tasks in d.items():
            for td in tasks:
                ftl.add(loc, FactoryTask(
                    recipe_id=td["recipe_id"],
                    target_amount=td["target_amount"],
                    allocation=td.get("allocation", 25),
                    produced=td.get("produced", 0.0),
                    task_id=td.get("task_id", _u.uuid4().hex[:8]),
                ))
        return ftl


# ---------------------------------------------------------------------------
# Shipyard tasks
# ---------------------------------------------------------------------------

@dataclass
class ShipyardTask:
    """One ship production run assigned to a shipyard location."""
    ship_type:    str
    target_count: int
    built_count:  int   = 0
    progress:     float = 0.0
    task_id:      str   = field(default_factory=lambda: _uuid.uuid4().hex[:8])

    @property
    def complete(self) -> bool:
        return self.built_count >= self.target_count


class ShipyardTaskList:
    """Shipyard build queues keyed by location_id."""

    def __init__(self) -> None:
        self._tasks: dict[str, list[ShipyardTask]] = {}

    def get(self, location_id: str) -> list[ShipyardTask]:
        return self._tasks.get(location_id, [])

    def add(self, location_id: str, task: ShipyardTask) -> None:
        if location_id not in self._tasks:
            self._tasks[location_id] = []
        self._tasks[location_id].append(task)

    def remove(self, location_id: str, task_id: str) -> None:
        self._tasks[location_id] = [
            t for t in self._tasks.get(location_id, []) if t.task_id != task_id
        ]

    def all_keys(self) -> list[str]:
        return list(self._tasks.keys())

    def to_dict(self) -> dict:
        return {
            loc: [
                {"ship_type": t.ship_type, "target_count": t.target_count,
                 "built_count": t.built_count, "progress": t.progress, "task_id": t.task_id}
                for t in tasks
            ]
            for loc, tasks in self._tasks.items()
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShipyardTaskList":
        import uuid as _u
        stl = cls()
        for loc, tasks in d.items():
            for td in tasks:
                stl.add(loc, ShipyardTask(
                    ship_type=td["ship_type"],
                    target_count=td["target_count"],
                    built_count=td.get("built_count", 0),
                    progress=td.get("progress", 0.0),
                    task_id=td.get("task_id", _u.uuid4().hex[:8]),
                ))
        return stl


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
    type_value: str  # e.g. "factory", "probe", "logistic_bot"
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

    def to_dict(self) -> dict:
        return {
            "instances": [
                {
                    "category":    i.category,
                    "type_value":  i.type_value,
                    "location_id": i.location_id,
                    "count":       i.count,
                }
                for i in self._instances
            ]
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EntityRoster":
        er = cls()
        for inst in d.get("instances", []):
            er.add(
                inst["category"],
                inst["type_value"],
                inst["location_id"],
                inst.get("count", 1),
            )
        return er


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

    def to_dict(self) -> dict:
        return {
            "researched": list(self.researched),
            "progress":   dict(self._progress),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TechState":
        ts = cls()
        ts.researched = set(d.get("researched", []))
        ts._progress  = dict(d.get("progress", {}))
        return ts


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------

class GameState:
    """Tracks discovery, entity roster, tech state, and non-player simulation."""

    def __init__(self) -> None:
        from .simulation import BioState, SimulationEngine, OrderQueue
        self.galaxy = None
        self._states: dict[str, DiscoveryState] = {}
        self.adjacency: dict[str, list[str]] = {}
        self.entity_roster: EntityRoster = EntityRoster()
        self.tech: TechState = TechState()
        self.bio_state: BioState = BioState()
        self.bot_tasks: BotTaskList = BotTaskList()
        self.order_queue: OrderQueue = OrderQueue()
        self.sim_engine: SimulationEngine = SimulationEngine(self)
        self._sim_events: list = []   # most-recent tick's events, for UI polling
        self.probed_systems: set[str] = set()   # systems a probe has visited
        # power_plant_active: key = f"{body_id}:{type_value}", default True
        self.power_plant_active: dict[str, bool] = {}
        # extractor_refine_mode: key = body_id, default False
        self.extractor_refine_mode: dict[str, bool] = {}
        # entity_damage: key = f"{location_id}:{category}:{type_value}", value = accumulated dmg pts
        self.entity_damage: dict[str, int] = {}
        self.factory_tasks:  FactoryTaskList  = FactoryTaskList()
        self.shipyard_tasks: ShipyardTaskList = ShipyardTaskList()
        # body_env cache: body_id → {orbital_radius, subtype, star_luminosity}
        self.body_env: dict[str, dict] = {}
        self._victory_declared: bool = False
        self.in_game_years: float = 0.0

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
        # Pick the best terrestrial/super_earth planet in the habitable zone (0.5–2.5 AU)
        from .models.celestial import BodyType, PlanetSubtype
        best_body = None
        for body in home.orbital_bodies:
            if body.body_type == BodyType.PLANET and body.subtype in (
                PlanetSubtype.TERRESTRIAL.value, PlanetSubtype.SUPER_EARTH.value
            ) and 0.5 <= body.orbital_radius <= 2.5:
                if best_body is None or body.resources.bios > best_body.resources.bios:
                    best_body = body
        if best_body is None:
            # Fall back to any terrestrial/super_earth planet
            for body in home.orbital_bodies:
                if body.body_type == BodyType.PLANET and body.subtype in (
                    PlanetSubtype.TERRESTRIAL.value, PlanetSubtype.SUPER_EARTH.value
                ):
                    best_body = body
                    break
        if best_body is None and home.orbital_bodies:
            best_body = home.orbital_bodies[0]
        home_body_id = best_body.id if best_body else home.id
        for cat, type_val, loc_token, count in STARTING_ENTITIES:
            loc_id = home_system_id if loc_token == "home_system" else home_body_id
            gs.entity_roster.add(cat, type_val, loc_id, count)

        # Home system starts probed (player has full visibility there)
        gs.probed_systems = {home.id}

        # Bio populations — seed from bios resource values on all bodies
        gs._init_bio_state()

        # Build sim engine now that galaxy and bio_state are populated
        from .simulation import SimulationEngine
        gs.sim_engine = SimulationEngine(gs)
        gs._rebuild_body_env()

        return gs

    def _init_bio_state(self) -> None:
        """Scan every body in the galaxy and spawn BioPopulations where bios > 0."""
        from .simulation import make_bio_population
        if not self.galaxy:
            return
        rng = random.Random(self.galaxy.seed ^ 0xB10B1AB)
        bio_uplift_mult = self.galaxy.parameters.get("bio_uplift_mult", 1.0)
        for sys in self.galaxy.solar_systems:
            for body in sys.orbital_bodies:
                if body.resources.bios > 0:
                    self.bio_state.add(
                        make_bio_population(body.id, sys.id, body.resources.bios, rng,
                                            uplift_multiplier=bio_uplift_mult)
                    )
                for moon in body.moons:
                    if moon.resources.bios > 0:
                        self.bio_state.add(
                            make_bio_population(moon.id, sys.id, moon.resources.bios, rng,
                                                uplift_multiplier=bio_uplift_mult)
                        )

    def _rebuild_body_env(self) -> None:
        """Cache orbital + atmospheric environment data for all bodies."""
        if not self.galaxy:
            return
        self.body_env = {}
        for sys in self.galaxy.solar_systems:
            star_lum = sys.star.resources.energy_output
            for body in sys.orbital_bodies:
                self.body_env[body.id] = {
                    "orbital_radius": body.orbital_radius,
                    "subtype": getattr(body, "subtype", "") or "",
                    "star_luminosity": star_lum,
                    "body_type": body.body_type.value,
                    "system_id": sys.id,
                }
                for moon in body.moons:
                    self.body_env[moon.id] = {
                        "orbital_radius": body.orbital_radius,  # moon inherits planet's orbit
                        "subtype": "moon",
                        "star_luminosity": star_lum,
                        "body_type": "moon",
                        "system_id": sys.id,
                    }

    # ------------------------------------------------------------------
    # Simulation tick

    def tick(self, dt_years: float) -> None:
        """Advance the non-player simulation. Called every game frame when unpaused."""
        self.in_game_years += dt_years
        self._sim_events = self.sim_engine.tick(dt_years)

    def pop_sim_events(self) -> list:
        """Return and clear the most-recent sim events (for UI notification)."""
        events = list(self._sim_events)
        self._sim_events = []
        return events

    # ------------------------------------------------------------------
    # Entity damage

    _HP_PER_ENTITY: int = 100  # damage points to destroy one unit of any entity type

    def _damage_key(self, location_id: str, category: str, type_value: str) -> str:
        return f"{location_id}:{category}:{type_value}"

    def apply_damage(
        self, location_id: str, category: str, type_value: str, amount: int
    ) -> bool:
        """Apply damage to an entity stack. Returns True if at least one unit was destroyed."""
        key = self._damage_key(location_id, category, type_value)
        self.entity_damage[key] = self.entity_damage.get(key, 0) + amount
        destroyed = False
        while self.entity_damage.get(key, 0) >= self._HP_PER_ENTITY:
            removed = self.entity_roster.remove(category, type_value, location_id, 1)
            if not removed:
                self.entity_damage.pop(key, None)
                break
            self.entity_damage[key] -= self._HP_PER_ENTITY
            destroyed = True
            if self.entity_damage.get(key, 0) <= 0:
                self.entity_damage.pop(key, None)
                break
        return destroyed

    def health_fraction(
        self, location_id: str, category: str, type_value: str
    ) -> float:
        """Return 0.0–1.0 health of the top unit in the stack (1.0 = undamaged)."""
        key = self._damage_key(location_id, category, type_value)
        dmg = self.entity_damage.get(key, 0)
        if dmg == 0:
            return 1.0
        return max(0.0, 1.0 - (dmg % self._HP_PER_ENTITY) / self._HP_PER_ENTITY)

    # ------------------------------------------------------------------
    # Adjacency

    @staticmethod
    def _build_adjacency(galaxy: "Galaxy", k: int = 3) -> dict[str, list[str]]:
        systems = galaxy.solar_systems
        adj: dict[str, list[str]] = {s.id: [] for s in systems}
        # Warp-only systems get empty adjacency lists and are excluded from main graph
        for i, sys_a in enumerate(systems):
            if sys_a.warp_only:
                continue
            ax, ay = sys_a.position["x"], sys_a.position["y"]
            distances = []
            for j, sys_b in enumerate(systems):
                if i == j or sys_b.warp_only:
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

    def is_probed(self, system_id: str) -> bool:
        return system_id in self.probed_systems

    def shortest_path(self, from_id: str, to_id: str) -> list[str]:
        """BFS shortest path between two system IDs using adjacency graph.
        Returns list of system IDs (inclusive of start and end)."""
        if from_id == to_id:
            return [from_id]
        visited: set[str] = {from_id}
        queue: list[list[str]] = [[from_id]]
        while queue:
            path = queue.pop(0)
            for neighbor in self.adjacency.get(path[-1], []):
                if neighbor == to_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return [from_id, to_id]  # Fallback: direct connection if not found

    def check_victory(self) -> str | None:
        """Check win conditions each tick. Returns victory type or None."""
        from .models.tech import TECH_TREE
        # Technology: all tech nodes researched
        if len(self.tech.researched) >= len(TECH_TREE):
            return "technology"
        # Construction: doom_machine entity built
        if self.entity_roster.total("structure", "doom_machine") > 0:
            return "construction"
        # Domination: player entities in ≥ 60% of discovered systems
        if self.galaxy:
            discovered = [
                s for s in self.galaxy.solar_systems
                if self._states.get(s.id) in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED)
            ]
            if len(discovered) >= 3:
                colonized_count = 0
                for sys in discovered:
                    has_entities = False
                    all_bodies = list(sys.orbital_bodies)
                    for body in sys.orbital_bodies:
                        all_bodies.extend(body.moons)
                    for b in all_bodies:
                        if any(
                            i.category in ("structure", "bot")
                            for i in self.entity_roster.at(b.id)
                        ):
                            has_entities = True
                            break
                    if has_entities:
                        colonized_count += 1
                if colonized_count >= len(discovered) * 0.6:
                    return "domination"
        return None

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict:
        from .simulation import BioPopulation as _BP  # noqa: F401
        return {
            "version": 2,
            "discovery_states":     {k: v.value for k, v in self._states.items()},
            "probed_systems":       list(self.probed_systems),
            "entity_roster":        self.entity_roster.to_dict(),
            "tech":                 self.tech.to_dict(),
            "power_plant_active":   dict(self.power_plant_active),
            "extractor_refine_mode": dict(self.extractor_refine_mode),
            "entity_damage":        dict(self.entity_damage),
            "factory_tasks":        self.factory_tasks.to_dict(),
            "shipyard_tasks":       self.shipyard_tasks.to_dict(),
            "bot_tasks":            self.bot_tasks.to_dict(),
            "order_queue":          self.order_queue.to_dict(),
            "bio_state": [
                {
                    "body_id":     p.body_id,
                    "system_id":   p.system_id,
                    "bio_type":    p.bio_type.value,
                    "population":  p.population,
                    "aggression":  p.aggression,
                    "growth_rate": p.growth_rate,
                    "capacity":    p.capacity,
                }
                for p in self.bio_state.all()
            ],
        }

    @classmethod
    def from_dict(cls, d: dict, galaxy: "Galaxy") -> "GameState":
        gs = cls()
        gs.galaxy    = galaxy
        gs.adjacency = cls._build_adjacency(galaxy, k=3)

        for sys_id, state_val in d.get("discovery_states", {}).items():
            gs._states[sys_id] = DiscoveryState(state_val)

        gs.probed_systems        = set(d.get("probed_systems", []))
        gs.entity_roster         = EntityRoster.from_dict(d.get("entity_roster", {}))
        gs.tech                  = TechState.from_dict(d.get("tech", {}))
        gs.power_plant_active    = dict(d.get("power_plant_active", {}))
        gs.extractor_refine_mode = dict(d.get("extractor_refine_mode", {}))
        gs.entity_damage         = dict(d.get("entity_damage", {}))
        gs.factory_tasks  = FactoryTaskList.from_dict(d.get("factory_tasks", {}))
        gs.shipyard_tasks = ShipyardTaskList.from_dict(d.get("shipyard_tasks", {}))
        gs.bot_tasks      = BotTaskList.from_dict(d.get("bot_tasks", {}))
        from .simulation import OrderQueue
        gs.order_queue = OrderQueue.from_dict(d.get("order_queue", {}))

        # Bio state: restore serialised populations if present, else regenerate from scratch
        if "bio_state" in d:
            from .simulation import BioState, BioPopulation
            from .models.entity import BioType as _BioType
            gs.bio_state = BioState()
            for pd in d["bio_state"]:
                pop = BioPopulation(
                    body_id=pd["body_id"],
                    system_id=pd["system_id"],
                    bio_type=_BioType(pd["bio_type"]),
                    population=pd["population"],
                    aggression=pd["aggression"],
                    growth_rate=pd["growth_rate"],
                    capacity=pd.get("capacity", 0.0),
                )
                gs.bio_state.add(pop)
        else:
            gs._init_bio_state()

        from .simulation import SimulationEngine
        gs.sim_engine = SimulationEngine(gs)
        gs._rebuild_body_env()

        return gs
