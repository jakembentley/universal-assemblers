"""
Simulation engine for Universal Assemblers.

BioType          -- re-exported for compatibility with nav_panel / other imports
BioPopulation    -- a living bio population on a specific body
BioState         -- all bio populations keyed by body_id
ShipOrder        -- a pending travel order for a ship stack
OrderQueue       -- ship order queues keyed by (location_id, ship_type)
SimulationEngine -- per-tick update; called from GameState.tick()
make_bio_population -- factory function seeded from bios resource value
"""
from __future__ import annotations

import random
import uuid as _uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models.entity import BioType          # re-export so nav_panel can do:
                                            #   from ..simulation import BioType

if TYPE_CHECKING:
    from .game_state import GameState


# ---------------------------------------------------------------------------
# Bio population
# ---------------------------------------------------------------------------

@dataclass
class BioPopulation:
    body_id:     str
    system_id:   str
    bio_type:    BioType
    population:  float          # headcount; fractional for simulation precision
    aggression:  float          # 0.0–1.0 threat level
    growth_rate: float          # annual fractional growth (e.g. 0.03 = 3 %/yr)
    capacity:    float = 0.0    # logistic carrying capacity; set by __post_init__

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            self.capacity = self.population * 20.0

    def tick(self, dt_years: float) -> None:
        """Logistic growth: dN/dt = r·N·(1 - N/K)."""
        r = self.growth_rate
        K = self.capacity
        N = self.population
        dN = r * N * (1 - N / K) * dt_years
        self.population = max(1.0, N + dN)


class BioState:
    """All bio populations keyed by body_id."""

    def __init__(self) -> None:
        self._pops: dict[str, BioPopulation] = {}

    def add(self, pop: BioPopulation) -> None:
        self._pops[pop.body_id] = pop

    def get(self, body_id: str) -> BioPopulation | None:
        return self._pops.get(body_id)

    def all(self) -> list[BioPopulation]:
        return list(self._pops.values())


def make_bio_population(
    body_id: str,
    system_id: str,
    bios_resource: float,
    rng: random.Random,
    uplift_multiplier: float = 1.0,
) -> BioPopulation:
    """Seed a bio population from a body's bios resource value."""
    uplift_chance = min(0.15 * uplift_multiplier, 1.0)
    bio_type    = BioType.UPLIFTED if rng.random() < uplift_chance else BioType.PRIMITIVE
    aggression  = rng.uniform(0.05, 0.95)
    growth_rate = rng.uniform(0.005, 0.08)
    population  = bios_resource * rng.uniform(50, 200)
    return BioPopulation(
        body_id=body_id,
        system_id=system_id,
        bio_type=bio_type,
        population=population,
        aggression=aggression,
        growth_rate=growth_rate,
    )


# ---------------------------------------------------------------------------
# Ship orders
# ---------------------------------------------------------------------------

@dataclass
class ShipOrder:
    """One pending travel order for a ship stack."""
    order_id:         str         = field(default_factory=lambda: _uuid.uuid4().hex[:8])
    order_type:       str         = "travel"        # "travel"
    target_system_id: str | None  = None
    target_body_id:   str | None  = None
    travel_speed:     float       = 0.25            # fraction of journey per in-game year
    progress:         float       = 0.0             # 0.0 → 1.0; 1.0 = arrived


class OrderQueue:
    """Ship orders keyed by (location_id, ship_type)."""

    def __init__(self) -> None:
        self._orders: dict[str, list[ShipOrder]] = {}

    @staticmethod
    def _key(location_id: str, ship_type: str) -> str:
        return f"{location_id}:{ship_type}"

    def enqueue(self, location_id: str, ship_type: str, order: ShipOrder) -> None:
        k = self._key(location_id, ship_type)
        if k not in self._orders:
            self._orders[k] = []
        self._orders[k].append(order)

    def peek(self, location_id: str, ship_type: str) -> ShipOrder | None:
        queue = self._orders.get(self._key(location_id, ship_type), [])
        return queue[0] if queue else None

    def dequeue(self, location_id: str, ship_type: str) -> ShipOrder | None:
        k = self._key(location_id, ship_type)
        queue = self._orders.get(k, [])
        return queue.pop(0) if queue else None

    def get_all(self, location_id: str, ship_type: str) -> list[ShipOrder]:
        return list(self._orders.get(self._key(location_id, ship_type), []))

    def all_keys(self) -> list[tuple[str, str]]:
        result = []
        for k in self._orders:
            loc, stype = k.rsplit(":", 1)
            result.append((loc, stype))
        return result


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

_MINE_RATES: dict[str, float] = {
    "miner":     10.0,   # resource-units / yr / bot at 100% allocation
    "harvester": 15.0,
    "worker":     5.0,
}

_BUILD_RATES: dict[str, float] = {
    "constructor": 1.0,  # entities / yr / bot at 100% allocation
    "worker":      0.5,
}

# All structure type_values that constructors can place
_STRUCTURE_TYPES: frozenset[str] = frozenset({
    "extractor", "factory", "research_array", "shipyard", "storage_hub",
    "replicator", "power_plant_solar", "power_plant_wind", "power_plant_bios",
    "power_plant_fossil", "power_plant_nuclear", "power_plant_cold_fusion",
    "power_plant_dark_matter",
})


class SimulationEngine:
    """Per-tick game simulation: bios growth, resource consumption, ships, bots."""

    def __init__(self, gs: "GameState") -> None:
        self.gs = gs

    def tick(self, dt_years: float) -> list:
        """Run one sim step. Returns event dicts for UI notification."""
        events: list = []
        self._tick_bios(dt_years)
        events.extend(self._tick_power_plants(dt_years))
        events.extend(self._tick_research(dt_years))
        events.extend(self._tick_ships(dt_years))
        events.extend(self._tick_bot_tasks(dt_years))
        return events

    # ------------------------------------------------------------------

    def _tick_bios(self, dt_years: float) -> None:
        for pop in self.gs.bio_state.all():
            pop.tick(dt_years)

    def _tick_power_plants(self, dt_years: float) -> list:
        from .models.entity import POWER_PLANT_SPECS
        events: list = []
        roster = self.gs.entity_roster
        galaxy = self.gs.galaxy
        if not galaxy:
            return events

        # Build body_id → body lookup for resource access
        body_map: dict[str, object] = {}
        for sys in galaxy.solar_systems:
            for body in sys.orbital_bodies:
                body_map[body.id] = body
                for moon in body.moons:
                    body_map[moon.id] = moon

        for struct_type, spec in POWER_PLANT_SPECS.items():
            if spec.renewable or not spec.input_resource:
                continue
            for inst in roster.by_category("structure"):
                if inst.type_value != struct_type.value:
                    continue
                body = body_map.get(inst.location_id)
                if not body:
                    continue
                res = body.resources
                current = getattr(res, spec.input_resource, 0.0)
                consumed = spec.input_rate * inst.count * dt_years
                new_val = max(0.0, current - consumed)
                setattr(res, spec.input_resource, new_val)
                if current > 0 and new_val == 0.0:
                    events.append({
                        "type": "resource_depleted",
                        "resource": spec.input_resource,
                        "location_id": inst.location_id,
                    })
        return events

    def _tick_research(self, dt_years: float) -> list:
        """Each Research Array contributes 1 pt/yr distributed across in-progress techs."""
        events: list = []
        roster = self.gs.entity_roster
        array_count = roster.total("structure", "research_array")
        if array_count == 0:
            return events
        tech = self.gs.tech
        in_progress = tech.in_progress_ids()
        if not in_progress:
            return events
        pts_per_tech = (array_count * dt_years) / len(in_progress)
        for tech_id in in_progress:
            completed = tech.add_progress(tech_id, pts_per_tech)
            if completed:
                events.append({"type": "tech_complete", "tech_id": tech_id})
        return events

    def _tick_ships(self, dt_years: float) -> list:
        """Advance ship travel; convert Drop Ships on arrival; probe systems."""
        events: list = []
        oq     = self.gs.order_queue
        roster = self.gs.entity_roster

        for loc_id, ship_type in list(oq.all_keys()):
            order = oq.peek(loc_id, ship_type)
            if not order or order.order_type != "travel":
                continue
            order.progress = min(1.0, order.progress + order.travel_speed * dt_years)
            if order.progress < 1.0:
                continue

            # Arrived
            oq.dequeue(loc_id, ship_type)

            if ship_type == "drop_ship":
                roster.remove("ship", "drop_ship", loc_id, 1)
                dest = order.target_body_id or order.target_system_id or loc_id
                roster.add("bot", "constructor", dest, 1)
                roster.add("bot", "miner", dest, 1)
                # Discover & probe the destination system
                if order.target_system_id:
                    self.gs.discover_system(order.target_system_id)
                    self.gs.probed_systems.add(order.target_system_id)
                events.append({
                    "type": "drop_ship_arrived",
                    "destination": dest,
                    "source": loc_id,
                })

            elif ship_type == "probe":
                roster.remove("ship", "probe", loc_id, 1)
                if order.target_system_id:
                    self.gs.discover_system(order.target_system_id)
                    self.gs.probed_systems.add(order.target_system_id)
                    events.append({
                        "type": "probe_arrived",
                        "system_id": order.target_system_id,
                    })

        return events

    def _tick_bot_tasks(self, dt_years: float) -> list:
        """Advance bot task progress; deduct build costs from body resources."""
        from .models.entity import BUILD_COSTS
        events: list = []
        gs     = self.gs
        galaxy = gs.galaxy
        if not galaxy:
            return events

        # Build body_id → body lookup
        body_map: dict[str, object] = {}
        for sys in galaxy.solar_systems:
            for body in sys.orbital_bodies:
                body_map[body.id] = body
                for moon in body.moons:
                    body_map[moon.id] = moon

        for loc_id, bot_type in list(gs.bot_tasks.all_keys()):
            tasks     = gs.bot_tasks.get(loc_id, bot_type)
            bot_count = gs.entity_roster.total("bot", bot_type)
            if bot_count == 0:
                continue
            body = body_map.get(loc_id)

            completed_ids: list[str] = []
            for task in tasks:
                if task.complete:
                    completed_ids.append(task.task_id)
                    continue

                alloc_frac     = task.allocation / 100.0
                effective_bots = bot_count * alloc_frac

                if task.task_type == "mine":
                    rate  = _MINE_RATES.get(bot_type, 5.0)
                    mined = rate * effective_bots * dt_years
                    if body:
                        res       = body.resources  # type: ignore[attr-defined]
                        available = getattr(res, task.resource or "", 0.0)
                        actual    = min(mined, available)
                        if actual > 0:
                            setattr(res, task.resource, available - actual)
                            task.progress += actual
                    else:
                        task.progress += mined

                elif task.task_type == "build":
                    rate           = _BUILD_RATES.get(bot_type, 0.25)
                    task.progress += rate * effective_bots * dt_years

                    # Complete whole units while progress >= 1.0
                    cost = BUILD_COSTS.get(task.entity_type or "", {})
                    while task.progress >= 1.0 and task.built_count < task.target_amount:
                        # Check and deduct resource cost
                        if cost and body:
                            res = body.resources  # type: ignore[attr-defined]
                            if not all(
                                getattr(res, r, 0.0) >= amt for r, amt in cost.items()
                            ):
                                # Stall — not enough resources
                                task.progress = min(task.progress, 0.9999)
                                break
                            for r, amt in cost.items():
                                setattr(res, r, max(0.0, getattr(res, r, 0.0) - amt))

                        task.progress    -= 1.0
                        task.built_count += 1
                        cat = "structure" if task.entity_type in _STRUCTURE_TYPES else "bot"
                        gs.entity_roster.add(cat, task.entity_type or "", loc_id, 1)
                        events.append({
                            "type":        "entity_built",
                            "entity_type": task.entity_type,
                            "location":    loc_id,
                        })

                if task.complete:
                    completed_ids.append(task.task_id)

            for tid in completed_ids:
                gs.bot_tasks.remove(loc_id, bot_type, tid)

        return events
