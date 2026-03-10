"""
Non-player element simulation engine.

SimulationEngine.tick(dt_years) is called once per game frame (while unpaused)
via GameState.tick().  It returns a list of SimEvents that the UI can surface
as log entries or notifications.

Simulated systems
-----------------
Bio populations (BioPopulation):
  • Logistic population growth toward a per-body carrying capacity
  • Primitive populations can spontaneously uplift at high density
  • Uplifted populations with high aggression fire attack events against
    any player entities sharing their body
  • Populations that exceed their spread_threshold can colonise adjacent
    bodies within the same solar system

Ship orders (ShipOrder / OrderQueue):
  • Probe  — travels to a target system; discovers it on arrival
  • Drop Ship — travels to a target body; converts to Constructor + Miner bot
  • Mining Vessel — travels to a body; extracts resources each tick while there
  All ship travel uses system-position distances (light-years) and per-type speeds.

All randomness flows through self._rng, seeded from the galaxy seed, so
simulation behaviour is deterministic for a given save (within a session).
"""
from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_state import GameState

from .models.entity import BioType


# ---------------------------------------------------------------------------
# Ship orders
# ---------------------------------------------------------------------------

# Travel speed in light-years per simulated year at base (1×) tech level
SHIP_SPEEDS: dict[str, float] = {
    "probe":         50.0,
    "drop_ship":     30.0,
    "mining_vessel": 25.0,
    "transport":     20.0,
    "warship":       40.0,
}


@dataclass
class ShipOrder:
    """
    A single ship-unit dispatched on a mission.

    origin_system_id   -- system the ship departed from
    origin_location_id -- specific body or system id where the unit was taken from
    target_system_id   -- destination system
    target_body_id     -- destination body (None for probe/fleet orders)
    distance_ly        -- total journey distance in light-years
    progress_ly        -- accumulated travel distance so far
    order_id           -- unique identifier (auto-generated)
    """
    ship_type:          str
    order_type:         str           # "explore" | "deploy" | "mine" | "patrol"
    origin_system_id:   str
    origin_location_id: str
    target_system_id:   str
    target_body_id:     str | None
    distance_ly:        float
    progress_ly:        float = 0.0
    order_id:           str   = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def fraction(self) -> float:
        if self.distance_ly <= 0:
            return 1.0
        return min(self.progress_ly / self.distance_ly, 1.0)

    @property
    def complete(self) -> bool:
        return self.progress_ly >= self.distance_ly

    @property
    def eta_years(self) -> float:
        """Estimated years remaining at current ship speed."""
        remaining = max(0.0, self.distance_ly - self.progress_ly)
        speed = SHIP_SPEEDS.get(self.ship_type, 30.0)
        return remaining / speed if speed > 0 else float("inf")


class OrderQueue:
    """Tracks all active ship orders across the galaxy."""

    def __init__(self) -> None:
        self._orders: list[ShipOrder] = []

    def add(self, order: ShipOrder) -> None:
        self._orders.append(order)

    def remove(self, order: ShipOrder) -> None:
        try:
            self._orders.remove(order)
        except ValueError:
            pass

    def active(self) -> list[ShipOrder]:
        return list(self._orders)

    def for_type(self, ship_type: str) -> list[ShipOrder]:
        return [o for o in self._orders if o.ship_type == ship_type]

    def for_origin(self, system_id: str) -> list[ShipOrder]:
        return [o for o in self._orders if o.origin_system_id == system_id]

    def count(self) -> int:
        return len(self._orders)


def system_distance(galaxy, sys_a_id: str, sys_b_id: str) -> float:
    """Return the light-year distance between two systems in the galaxy."""
    a = next((s for s in galaxy.solar_systems if s.id == sys_a_id), None)
    b = next((s for s in galaxy.solar_systems if s.id == sys_b_id), None)
    if not a or not b:
        return float("inf")
    return math.hypot(
        b.position["x"] - a.position["x"],
        b.position["y"] - a.position["y"],
    )


# ---------------------------------------------------------------------------
# Simulation events
# ---------------------------------------------------------------------------

@dataclass
class SimEvent:
    """
    A discrete simulation event to be surfaced to the UI.

    kind    -- "bio_attack" | "bio_spread" | "bio_extinct" | "bio_uplift"
    body_id -- the body where the event occurred
    system_id
    detail  -- human-readable description
    """
    kind: str
    body_id: str
    system_id: str
    detail: str


# ---------------------------------------------------------------------------
# Bio population data
# ---------------------------------------------------------------------------

@dataclass
class BioPopulation:
    """
    A biological population resident on a single celestial body.

    population       -- Abstract units (1 = tiny colony, 1 000 = thriving world)
    growth_rate      -- Logistic rate constant per year (e.g. 0.08 = 8 %/yr at low density)
    aggression       -- 0.0 – 1.0; uplifted bios attack player entities above threshold
    spread_threshold -- Population at which they can seed an adjacent body
    capacity         -- Carrying capacity; population asymptotes toward this value
    """
    body_id:          str
    system_id:        str
    bio_type:         BioType
    population:       float
    growth_rate:      float
    aggression:       float
    spread_threshold: float
    capacity:         float


# ---------------------------------------------------------------------------
# Bio state container
# ---------------------------------------------------------------------------

@dataclass
class BioState:
    """All active bio populations across the galaxy, keyed by body_id."""

    populations: dict[str, BioPopulation] = field(default_factory=dict)

    def add(self, pop: BioPopulation) -> None:
        self.populations[pop.body_id] = pop

    def get(self, body_id: str) -> BioPopulation | None:
        return self.populations.get(body_id)

    def remove(self, body_id: str) -> None:
        self.populations.pop(body_id, None)

    def all(self) -> list[BioPopulation]:
        return list(self.populations.values())

    def count(self) -> int:
        return len(self.populations)

    def count_by_type(self, bio_type: BioType) -> int:
        return sum(1 for p in self.populations.values() if p.bio_type == bio_type)


# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

_ATTACK_THRESHOLD      = 0.65   # aggression above this → attack events
_UPLIFT_POP_THRESHOLD  = 800.0  # min population for uplift roll
_UPLIFT_CHANCE_PER_YR  = 0.002  # base probability of uplift per simulated year
_SPREAD_MAX_CHANCE     = 0.05   # cap on per-tick spread probability
_ATTACK_ROLL_RATE      = 0.20   # expected attack events per simulated year (Poisson proxy)
_EXTINCT_THRESHOLD     = 0.5    # population below this → extinct


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

class SimulationEngine:
    """
    Advances the non-player simulation by dt_years each call.

    Typical call site::

        events = game_state.sim_engine.tick(dt_years)

    The engine holds a lazy-built cache of body→system and system→bodies
    mappings so spreading checks are O(1) per population per tick.
    """

    def __init__(self, game_state: "GameState") -> None:
        self.gs   = game_state
        seed      = game_state.galaxy.seed if game_state.galaxy else 0
        self._rng = random.Random(seed ^ 0xB10B1AB)

        # Lazy lookup tables
        self._body_to_system: dict[str, str]        = {}
        self._system_bodies:  dict[str, list[str]]  = {}
        self._lookup_built    = False

    # ------------------------------------------------------------------
    # Public API

    # Bot mining/build rates (per bot per year at 100 % allocation)
    _MINE_RATES: dict[str, float]  = {"miner": 10.0, "harvester": 15.0, "worker": 5.0}
    _BUILD_RATES: dict[str, dict]  = {
        "constructor": {"structure": 1.0, "bot": 2.0},
        "worker":      {"structure": 0.5, "bot": 1.0},
    }
    _STRUCTURE_TYPES: frozenset[str] = frozenset({
        "extractor", "factory",
        "power_plant_solar", "power_plant_wind", "power_plant_bios",
        "power_plant_fossil", "power_plant_nuclear",
        "power_plant_cold_fusion", "power_plant_dark_matter",
        "research_array", "replicator", "shipyard", "storage_hub",
    })

    def tick(self, dt_years: float) -> list[SimEvent]:
        """Advance all simulated populations, ship orders, and bot tasks by dt_years."""
        if dt_years <= 0:
            return []

        self._ensure_lookup()
        events: list[SimEvent] = []

        # Bio populations
        for pop in list(self.gs.bio_state.populations.values()):
            events += self._tick_population(pop, dt_years)
        if self.gs.bio_state.populations:
            events += self._tick_spreading()

        # Ship orders
        events += self._tick_orders(dt_years)

        # Bot tasks
        events += self._tick_bot_tasks(dt_years)

        return events

    # ------------------------------------------------------------------
    # Ship order ticking

    def _tick_orders(self, dt_years: float) -> list[SimEvent]:
        events: list[SimEvent] = []
        for order in list(self.gs.order_queue.active()):
            speed = SHIP_SPEEDS.get(order.ship_type, 30.0)
            order.progress_ly += speed * dt_years
            if order.complete:
                events += self._complete_order(order)
                self.gs.order_queue.remove(order)
        return events

    def _complete_order(self, order: ShipOrder) -> list[SimEvent]:
        gs = self.gs
        tgt_sys  = order.target_system_id
        tgt_body = order.target_body_id

        # Resolve target system name for readable events
        sys_name = tgt_sys
        if gs.galaxy:
            s = next((x for x in gs.galaxy.solar_systems if x.id == tgt_sys), None)
            if s:
                sys_name = s.name
        body_name = tgt_body or sys_name

        if order.ship_type == "probe":
            gs.discover_system(tgt_sys)
            gs.entity_roster.add("ship", "probe", tgt_sys, 1)
            return [SimEvent(
                kind="probe_arrived",
                body_id=tgt_sys,
                system_id=tgt_sys,
                detail=f"Probe reached {sys_name} — system discovered.",
            )]

        if order.ship_type == "drop_ship":
            dest = tgt_body or tgt_sys
            gs.entity_roster.add("bot", "constructor", dest, 1)
            gs.entity_roster.add("bot", "miner",       dest, 1)
            return [SimEvent(
                kind="drop_ship_landed",
                body_id=dest,
                system_id=tgt_sys,
                detail=f"Drop Ship landed at {body_name}. Deployed Constructor + Miner bots.",
            )]

        if order.ship_type == "mining_vessel":
            dest = tgt_body or tgt_sys
            gs.entity_roster.add("ship", "mining_vessel", dest, 1)
            return [SimEvent(
                kind="mining_vessel_arrived",
                body_id=dest,
                system_id=tgt_sys,
                detail=f"Mining Vessel arrived at {body_name} and began operations.",
            )]

        return []

    # ------------------------------------------------------------------
    # Per-population update

    def _tick_population(self, pop: BioPopulation, dt_years: float) -> list[SimEvent]:
        events: list[SimEvent] = []

        # Logistic growth: dP/dt = r·P·(1 − P/K)
        dP = (
            pop.growth_rate
            * pop.population
            * (1.0 - pop.population / pop.capacity)
            * dt_years
        )
        pop.population = max(0.0, min(pop.capacity, pop.population + dP))

        # Extinction check
        if pop.population < _EXTINCT_THRESHOLD:
            self.gs.bio_state.remove(pop.body_id)
            events.append(SimEvent(
                kind="bio_extinct",
                body_id=pop.body_id,
                system_id=pop.system_id,
                detail=f"Bio population on {pop.body_id} went extinct.",
            ))
            return events

        # Primitive → Uplifted spontaneous transition
        if (
            pop.bio_type == BioType.PRIMITIVE
            and pop.population >= _UPLIFT_POP_THRESHOLD
            and self._rng.random() < _UPLIFT_CHANCE_PER_YR * dt_years
        ):
            pop.bio_type   = BioType.UPLIFTED
            pop.aggression = min(1.0, pop.aggression + self._rng.uniform(0.25, 0.45))
            events.append(SimEvent(
                kind="bio_uplift",
                body_id=pop.body_id,
                system_id=pop.system_id,
                detail=f"Primitive bios on {pop.body_id} became Uplifted.",
            ))

        # Uplifted aggression → attack player entities
        if pop.bio_type == BioType.UPLIFTED and pop.aggression > _ATTACK_THRESHOLD:
            player_entities = self.gs.entity_roster.at(pop.body_id)
            if player_entities and self._rng.random() < _ATTACK_ROLL_RATE * dt_years:
                events.append(SimEvent(
                    kind="bio_attack",
                    body_id=pop.body_id,
                    system_id=pop.system_id,
                    detail=(
                        f"Uplifted bios are attacking player entities on {pop.body_id}. "
                        f"({len(player_entities)} entity stack(s) at risk)"
                    ),
                ))

        return events

    # ------------------------------------------------------------------
    # Spreading

    def _tick_spreading(self) -> list[SimEvent]:
        events: list[SimEvent] = []

        for pop in list(self.gs.bio_state.populations.values()):
            if pop.population < pop.spread_threshold:
                continue

            # Candidate bodies: same system, unoccupied
            candidates = [
                bid
                for bid in self._system_bodies.get(pop.system_id, [])
                if bid != pop.body_id
                and bid not in self.gs.bio_state.populations
            ]
            if not candidates:
                continue

            # Spread probability scales with how far above threshold we are
            excess    = pop.population / pop.spread_threshold
            p_spread  = min(_SPREAD_MAX_CHANCE, 0.008 * excess)
            if self._rng.random() > p_spread:
                continue

            target = self._rng.choice(candidates)
            seed_pop = BioPopulation(
                body_id=target,
                system_id=pop.system_id,
                bio_type=pop.bio_type,
                population=max(1.0, pop.population * 0.01),
                growth_rate=pop.growth_rate * self._rng.uniform(0.7, 1.1),
                aggression=min(1.0, pop.aggression * self._rng.uniform(0.8, 1.2)),
                spread_threshold=pop.spread_threshold,
                capacity=pop.capacity  * self._rng.uniform(0.4, 1.3),
            )
            self.gs.bio_state.add(seed_pop)
            events.append(SimEvent(
                kind="bio_spread",
                body_id=target,
                system_id=pop.system_id,
                detail=f"Bios spread from {pop.body_id} to {target}.",
            ))

        return events

    # ------------------------------------------------------------------
    # Bot task ticking

    def _tick_bot_tasks(self, dt_years: float) -> list[SimEvent]:
        events: list[SimEvent] = []
        gs = self.gs
        bt = gs.bot_tasks

        # Iterate over every location+bot_type pair that has assigned tasks
        for loc_id, bot_type in bt.all_keys():
            tasks = bt.get(loc_id, bot_type)
            if not tasks:
                continue

            # Count bots of this type at this location
            bot_count = sum(
                i.count for i in gs.entity_roster.at(loc_id)
                if i.category == "bot" and i.type_value == bot_type
            )
            if bot_count <= 0:
                continue

            for task in list(tasks):
                if task.complete:
                    continue
                alloc_frac = task.allocation / 100.0

                if task.task_type == "mine":
                    rate = self._MINE_RATES.get(bot_type, 0.0)
                    task.progress += rate * alloc_frac * bot_count * dt_years
                    if task.progress >= task.target_amount:
                        task.progress = float(task.target_amount)
                        sys_id = self._body_to_system.get(loc_id, loc_id)
                        events.append(SimEvent(
                            kind="mining_task_complete",
                            body_id=loc_id,
                            system_id=sys_id,
                            detail=(
                                f"Mining task complete: {task.target_amount} "
                                f"{task.resource or 'resource'} extracted at {loc_id}."
                            ),
                        ))

                elif task.task_type == "build" and task.entity_type:
                    cat = (
                        "structure" if task.entity_type in self._STRUCTURE_TYPES
                        else "bot"
                    )
                    rates = self._BUILD_RATES.get(bot_type, {})
                    rate  = rates.get(cat, 0.0)
                    task.progress += rate * alloc_frac * bot_count * dt_years
                    # Complete one entity each time progress passes 1.0
                    while task.progress >= 1.0 and task.built_count < task.target_amount:
                        task.built_count += 1
                        task.progress    -= 1.0
                        gs.entity_roster.add(cat, task.entity_type, loc_id, 1)
                        sys_id = self._body_to_system.get(loc_id, loc_id)
                        events.append(SimEvent(
                            kind="build_task_progress",
                            body_id=loc_id,
                            system_id=sys_id,
                            detail=(
                                f"Built {task.entity_type} at {loc_id} "
                                f"({task.built_count}/{task.target_amount})."
                            ),
                        ))

        return events

    # ------------------------------------------------------------------
    # Lookup cache

    def _ensure_lookup(self) -> None:
        if self._lookup_built or not self.gs.galaxy:
            return
        for sys in self.gs.galaxy.solar_systems:
            bodies: list[str] = []
            for body in sys.orbital_bodies:
                self._body_to_system[body.id] = sys.id
                bodies.append(body.id)
                for moon in body.moons:
                    self._body_to_system[moon.id] = sys.id
                    bodies.append(moon.id)
            self._system_bodies[sys.id] = bodies
        self._lookup_built = True


# ---------------------------------------------------------------------------
# Factory: build a BioPopulation from a body's bios resource value
# ---------------------------------------------------------------------------

def make_bio_population(
    body_id: str,
    system_id: str,
    bios_value: float,
    rng: random.Random,
) -> BioPopulation:
    """
    Derive a BioPopulation from a body's bios resource quantity.

    bios_value acts as a proxy for biological richness:
      •  0–50  → sparse primitive life
      • 50–150 → established primitive colony, small chance of uplifted
      • 150+   → rich ecosystem, higher chance of uplifted, faster growth
    """
    # Bio type
    uplift_chance = 0.05 if bios_value < 50 else (0.15 if bios_value < 150 else 0.30)
    bio_type = BioType.UPLIFTED if rng.random() < uplift_chance else BioType.PRIMITIVE

    # Scale stats with bios_value
    richness    = min(bios_value / 200.0, 1.0)   # 0–1 normalised
    population  = rng.uniform(10.0, 50.0) + richness * 500.0
    growth_rate = rng.uniform(0.04, 0.06) + richness * 0.04
    capacity    = rng.uniform(500.0, 1500.0) + richness * 3000.0

    if bio_type == BioType.UPLIFTED:
        aggression = rng.uniform(0.45, 0.85)
    else:
        aggression = rng.uniform(0.0, 0.25)

    spread_threshold = capacity * rng.uniform(0.55, 0.75)

    return BioPopulation(
        body_id=body_id,
        system_id=system_id,
        bio_type=bio_type,
        population=population,
        growth_rate=growth_rate,
        aggression=aggression,
        spread_threshold=spread_threshold,
        capacity=capacity,
    )
