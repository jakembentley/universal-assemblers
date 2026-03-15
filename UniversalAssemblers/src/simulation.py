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

# Travel speed (fraction of journey completed per in-game year) per ship type.
# Higher = faster.  Probes are recon craft; warships are heavily armoured.
SHIP_SPEEDS: dict[str, float] = {
    "probe":          0.50,
    "mining_vessel":  0.30,
    "transport":      0.25,
    "drop_ship":      0.20,
    "warship":        0.15,
}


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
    "miner":        10.0,   # resource-units / yr / bot at 100% allocation
    "harvester":    15.0,
    "logistic_bot":  5.0,   # fallback rate (primary role is transport)
}

_BUILD_RATES: dict[str, float] = {
    "constructor": 1.0,  # entities / yr / bot at 100% allocation
}

# Ship type_values that constructors can build
_SHIP_TYPES: frozenset[str] = frozenset({
    "probe", "drop_ship", "mining_vessel", "transport", "warship",
})

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
        self._tick_extractors(dt_years)
        events.extend(self._tick_factories(dt_years))
        events.extend(self._tick_shipyards(dt_years))
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
                flag_key = f"{inst.location_id}:{struct_type.value}"
                # Skip if already deactivated
                if not self.gs.power_plant_active.get(flag_key, True):
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
                    # Auto-deactivate the plant
                    self.gs.power_plant_active[flag_key] = False
                    events.append({
                        "type": "resource_depleted",
                        "resource": spec.input_resource,
                        "location_id": inst.location_id,
                    })
                    events.append({
                        "type": "resource_depleted_plant",
                        "location_id": inst.location_id,
                        "plant_type": struct_type.value,
                    })
        return events

    def _tick_research(self, dt_years: float) -> list:
        """Each Research Array contributes 1 pt/yr distributed across in-progress techs."""
        from .models.entity import compute_energy_balance
        events: list = []
        roster = self.gs.entity_roster
        array_count = roster.total("structure", "research_array")
        if array_count == 0:
            return events
        tech = self.gs.tech
        in_progress = tech.in_progress_ids()
        if not in_progress:
            return events

        # Sum throttle across all bodies that have research arrays
        galaxy = self.gs.galaxy
        total_throttled_arrays = 0.0
        if galaxy:
            for sys in galaxy.solar_systems:
                for body in sys.orbital_bodies:
                    cnt = sum(
                        i.count for i in roster.at(body.id)
                        if i.category == "structure" and i.type_value == "research_array"
                    )
                    if cnt:
                        prod, cons = compute_energy_balance(self.gs, body.id)
                        throttle = min(1.0, prod / max(cons, 1.0))
                        total_throttled_arrays += cnt * throttle
                    for moon in body.moons:
                        cnt = sum(
                            i.count for i in roster.at(moon.id)
                            if i.category == "structure" and i.type_value == "research_array"
                        )
                        if cnt:
                            prod, cons = compute_energy_balance(self.gs, moon.id)
                            throttle = min(1.0, prod / max(cons, 1.0))
                            total_throttled_arrays += cnt * throttle
        else:
            total_throttled_arrays = float(array_count)

        pts_per_tech = (total_throttled_arrays * dt_years) / len(in_progress)
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
                dest_sys = order.target_system_id or loc_id
                roster.remove("ship", "probe", loc_id, 1)
                roster.add("ship", "probe", dest_sys, 1)   # probe stays at destination
                if order.target_system_id:
                    self.gs.discover_system(order.target_system_id)
                    self.gs.probed_systems.add(order.target_system_id)
                events.append({
                    "type": "probe_arrived",
                    "system_id": dest_sys,
                })

            else:
                # All other ship types: move to destination, stay in roster.
                # Mining vessels and transports can dock at a specific body;
                # warships operate at system level.
                dest_sys = order.target_system_id or loc_id
                if ship_type in ("mining_vessel", "transport") and order.target_body_id:
                    dest = order.target_body_id
                else:
                    dest = dest_sys
                roster.remove("ship", ship_type, loc_id, 1)
                roster.add("ship", ship_type, dest, 1)
                if order.target_system_id:
                    self.gs.discover_system(order.target_system_id)
                    self.gs.probed_systems.add(order.target_system_id)
                events.append({
                    "type": "ship_arrived",
                    "ship_type": ship_type,
                    "destination": dest,
                    "source": loc_id,
                })

        return events

    def _tick_extractors(self, dt_years: float) -> None:
        """Refine base resources into manufactured goods when extractor refine mode is on."""
        from .models.entity import REFINE_RECIPES, compute_energy_balance
        gs     = self.gs
        galaxy = gs.galaxy
        if not galaxy:
            return
        roster = gs.entity_roster

        body_map: dict[str, object] = {}
        for sys in galaxy.solar_systems:
            for body in sys.orbital_bodies:
                body_map[body.id] = body
                for moon in body.moons:
                    body_map[moon.id] = moon

        for inst in roster.by_category("structure"):
            if inst.type_value != "extractor":
                continue
            if not gs.extractor_refine_mode.get(inst.location_id, False):
                continue
            body = body_map.get(inst.location_id)
            if not body:
                continue
            res = body.resources  # type: ignore[attr-defined]

            # Power throttle
            prod, cons = compute_energy_balance(gs, inst.location_id)
            throttle = min(1.0, prod / max(cons, 1.0)) if cons > 0 else 1.0

            for out_res, (costs, rate_per_extractor) in REFINE_RECIPES.items():
                output_amount = rate_per_extractor * inst.count * throttle * dt_years
                # Check and consume inputs
                if not all(getattr(res, r, 0.0) >= amt * output_amount / rate_per_extractor
                           for r, amt in costs.items()):
                    continue
                for r, amt in costs.items():
                    consumed = amt * output_amount / rate_per_extractor
                    setattr(res, r, max(0.0, getattr(res, r, 0.0) - consumed))
                setattr(res, out_res, getattr(res, out_res, 0.0) + output_amount)

    def _tick_bot_tasks(self, dt_years: float) -> list:
        """Advance bot task progress; deduct build costs from body resources."""
        from .models.entity import BUILD_COSTS, compute_energy_balance
        events: list = []
        gs     = self.gs
        galaxy = gs.galaxy
        if not galaxy:
            return events

        # Build body_id → body lookup + body_id → system_id reverse map
        body_map: dict[str, object] = {}
        body_to_system: dict[str, str] = {}
        for sys in galaxy.solar_systems:
            for body in sys.orbital_bodies:
                body_map[body.id] = body
                body_to_system[body.id] = sys.id
                for moon in body.moons:
                    body_map[moon.id] = moon
                    body_to_system[moon.id] = sys.id

        for loc_id, bot_type in list(gs.bot_tasks.all_keys()):
            tasks     = gs.bot_tasks.get(loc_id, bot_type)
            bot_count = sum(
                i.count for i in gs.entity_roster.at(loc_id)
                if i.category in ("bot", "ship") and i.type_value == bot_type
            )
            if bot_count == 0:
                continue
            body = body_map.get(loc_id)

            # Asteroid mining gate: mining_vessel tasks at asteroids require tech
            if bot_type == "mining_vessel":
                if not gs.tech.is_researched("asteroid_mining"):
                    continue
                # mining_vessel tasks are ship-category

            # Power throttle: reduce effective work rate if power is insufficient
            prod, cons = compute_energy_balance(gs, loc_id)
            throttle = min(1.0, prod / max(cons, 1.0)) if cons > 0 else 1.0

            completed_ids: list[str] = []
            for task in tasks:
                if task.complete:
                    completed_ids.append(task.task_id)
                    continue

                alloc_frac     = task.allocation / 100.0
                effective_bots = bot_count * alloc_frac

                if task.task_type == "mine":
                    rate  = _MINE_RATES.get(bot_type, 5.0)
                    mined = rate * effective_bots * throttle * dt_years
                    if body:
                        res       = body.resources  # type: ignore[attr-defined]
                        available = getattr(res, task.resource or "", 0.0)
                        actual    = min(mined, available)
                        if actual > 0:
                            setattr(res, task.resource, available - actual)
                            task.progress += actual
                    else:
                        task.progress += mined

                elif task.task_type == "transport":
                    # Move resources from loc_id to task.target_location
                    if not task.target_location or not body:
                        continue
                    target_body = body_map.get(task.target_location)
                    if not target_body:
                        continue
                    TRANSPORT_RATE = 50.0  # resource-units/yr per logistic bot at 100%
                    move_amount = TRANSPORT_RATE * effective_bots * throttle * dt_years
                    res_src = body.resources  # type: ignore[attr-defined]
                    res_dst = target_body.resources  # type: ignore[attr-defined]
                    resource = task.resource or "minerals"
                    available = getattr(res_src, resource, 0.0)
                    actual = min(move_amount, available)
                    if actual > 0:
                        setattr(res_src, resource, available - actual)
                        setattr(res_dst, resource, getattr(res_dst, resource, 0.0) + actual)
                        task.progress += actual

                elif task.task_type == "build":
                    rate           = _BUILD_RATES.get(bot_type, 0.25)
                    task.progress += rate * effective_bots * throttle * dt_years

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
                        etype = task.entity_type or ""
                        if etype in _STRUCTURE_TYPES:
                            cat = "structure"
                            add_loc = loc_id
                        elif etype in _SHIP_TYPES:
                            cat = "ship"
                            # Ships land at system level, not body level
                            add_loc = body_to_system.get(loc_id, loc_id)
                        else:
                            cat = "bot"
                            add_loc = loc_id
                        gs.entity_roster.add(cat, etype, add_loc, 1)
                        events.append({
                            "type":        "entity_built",
                            "entity_type": etype,
                            "location":    add_loc,
                        })

                if task.complete:
                    completed_ids.append(task.task_id)

            for tid in completed_ids:
                gs.bot_tasks.remove(loc_id, bot_type, tid)

        return events

    def _tick_factories(self, dt_years: float) -> list:
        """Run factory production recipes."""
        from .models.entity import FACTORY_RECIPES, compute_energy_balance
        events: list = []
        gs     = self.gs
        galaxy = gs.galaxy
        if not galaxy:
            return events

        body_map: dict[str, object] = {}
        for sys in galaxy.solar_systems:
            for body in sys.orbital_bodies:
                body_map[body.id] = body
                for moon in body.moons:
                    body_map[moon.id] = moon

        for loc_id in list(gs.factory_tasks.all_keys()):
            tasks = gs.factory_tasks.get(loc_id)
            factory_count = sum(
                i.count for i in gs.entity_roster.at(loc_id)
                if i.category == "structure" and i.type_value == "factory"
            )
            if factory_count == 0:
                continue
            body = body_map.get(loc_id)
            if not body:
                continue
            res = body.resources  # type: ignore[attr-defined]

            # Power throttle
            prod, cons = compute_energy_balance(gs, loc_id)
            throttle = min(1.0, prod / max(cons, 1.0)) if cons > 0 else 1.0

            completed: list[str] = []
            for task in tasks:
                if task.complete:
                    completed.append(task.task_id)
                    continue
                # Gate: components recipe requires advanced_manufacturing tech
                if task.recipe_id == "components" and not gs.tech.is_researched("advanced_manufacturing"):
                    continue
                recipe = FACTORY_RECIPES.get(task.recipe_id)
                if not recipe:
                    continue
                inputs, rate_per_factory, out_field = recipe
                alloc_frac    = task.allocation / 100.0
                output_amount = rate_per_factory * factory_count * alloc_frac * throttle * dt_years

                # Check inputs
                scale = 1.0
                for r, cost_per_unit in inputs.items():
                    available = getattr(res, r, 0.0)
                    max_from_r = available / max(cost_per_unit, 1e-9)
                    scale = min(scale, max_from_r / max(output_amount, 1e-9))
                scale = max(0.0, min(1.0, scale))
                actual_output = output_amount * scale

                if actual_output > 0:
                    for r, cost_per_unit in inputs.items():
                        consumed = cost_per_unit * actual_output
                        setattr(res, r, max(0.0, getattr(res, r, 0.0) - consumed))
                    setattr(res, out_field, getattr(res, out_field, 0.0) + actual_output)
                    task.produced += actual_output
                    if task.complete:
                        events.append({
                            "type": "factory_complete",
                            "recipe": task.recipe_id,
                            "location": loc_id,
                        })

                if task.complete:
                    completed.append(task.task_id)

            for tid in completed:
                gs.factory_tasks.remove(loc_id, tid)

        return events

    def _tick_shipyards(self, dt_years: float) -> list:
        """Build ships in shipyard queues."""
        from .models.entity import SHIPYARD_BUILD_RATES, BUILD_COSTS, compute_energy_balance
        events: list = []
        gs     = self.gs
        galaxy = gs.galaxy
        if not galaxy:
            return events

        body_map: dict[str, object] = {}
        body_to_system: dict[str, str] = {}
        for sys in galaxy.solar_systems:
            for body in sys.orbital_bodies:
                body_map[body.id] = body
                body_to_system[body.id] = sys.id
                for moon in body.moons:
                    body_map[moon.id] = moon
                    body_to_system[moon.id] = sys.id

        for loc_id in list(gs.shipyard_tasks.all_keys()):
            tasks = gs.shipyard_tasks.get(loc_id)
            shipyard_count = sum(
                i.count for i in gs.entity_roster.at(loc_id)
                if i.category == "structure" and i.type_value == "shipyard"
            )
            if shipyard_count == 0:
                continue
            body = body_map.get(loc_id)
            if not body:
                continue
            res = body.resources  # type: ignore[attr-defined]

            prod, cons = compute_energy_balance(gs, loc_id)
            throttle = min(1.0, prod / max(cons, 1.0)) if cons > 0 else 1.0

            completed: list[str] = []
            for task in tasks:
                if task.complete:
                    completed.append(task.task_id)
                    continue
                # Gate warships behind atomic_warships tech
                if task.ship_type == "warship" and not gs.tech.is_researched("atomic_warships"):
                    continue

                build_time = SHIPYARD_BUILD_RATES.get(task.ship_type, 2.0)
                progress_this_tick = (shipyard_count / build_time) * throttle * dt_years
                task.progress += progress_this_tick

                cost = BUILD_COSTS.get(task.ship_type, {})
                while task.progress >= 1.0 and task.built_count < task.target_count:
                    if cost:
                        if not all(getattr(res, r, 0.0) >= amt for r, amt in cost.items()):
                            task.progress = min(task.progress, 0.9999)
                            break
                        for r, amt in cost.items():
                            setattr(res, r, max(0.0, getattr(res, r, 0.0) - amt))
                    task.progress    -= 1.0
                    task.built_count += 1
                    dest_sys = body_to_system.get(loc_id, loc_id)
                    gs.entity_roster.add("ship", task.ship_type, dest_sys, 1)
                    events.append({
                        "type": "ship_built",
                        "ship_type": task.ship_type,
                        "location": dest_sys,
                    })

                if task.complete:
                    completed.append(task.task_id)

            for tid in completed:
                gs.shipyard_tasks.remove(loc_id, tid)

        return events
