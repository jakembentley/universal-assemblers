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
    body_id:      str
    system_id:    str
    bio_type:     BioType
    population:   float          # headcount; fractional for simulation precision
    aggression:   float          # 0.0–1.0 threat level
    growth_rate:  float          # annual fractional growth (e.g. 0.03 = 3 %/yr)
    capacity:     float = 0.0    # base logistic carrying capacity; set by __post_init__
    initial_bios: float = 0.0    # bios resource on this body at seeding time

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            self.capacity = self.population * 20.0

    def tick(self, dt_years: float, effective_capacity: float | None = None) -> None:
        """Logistic growth: dN/dt = r·N·(1 - N/K).

        effective_capacity overrides self.capacity when bios availability has
        reduced the carrying capacity below its base value.
        """
        r = self.growth_rate
        K = max(1.0, effective_capacity if effective_capacity is not None else self.capacity)
        N = self.population
        dN = r * N * (1 - N / K) * dt_years
        self.population = max(1.0, N + dN)


# How many bios resource units a population regenerates per individual per year.
# Primitive populations produce biological material; uplifted ones consume/destroy it.
_BIOS_REGEN_PER_POP: float = 0.001


class BioState:
    """All bio populations keyed by body_id."""

    def __init__(self) -> None:
        self._pops: dict[str, BioPopulation] = {}

    def add(self, pop: BioPopulation) -> None:
        self._pops[pop.body_id] = pop

    def get(self, body_id: str) -> BioPopulation | None:
        return self._pops.get(body_id)

    def remove(self, body_id: str) -> None:
        self._pops.pop(body_id, None)

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
        initial_bios=bios_resource,
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
    waypoints: list = field(default_factory=list)  # system_id sequence for multi-hop travel
    current_waypoint_idx: int = 0                  # which leg we're currently on


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

    def to_dict(self) -> dict:
        result = {}
        for k, orders in self._orders.items():
            result[k] = [
                {
                    "order_id":            o.order_id,
                    "order_type":          o.order_type,
                    "target_system_id":    o.target_system_id,
                    "target_body_id":      o.target_body_id,
                    "travel_speed":        o.travel_speed,
                    "progress":            o.progress,
                    "waypoints":           list(o.waypoints),
                    "current_waypoint_idx": o.current_waypoint_idx,
                }
                for o in orders
            ]
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "OrderQueue":
        oq = cls()
        for k, orders in d.items():
            loc, stype = k.rsplit(":", 1)
            for od in orders:
                order = ShipOrder(
                    order_id=od.get("order_id", ""),
                    order_type=od.get("order_type", "travel"),
                    target_system_id=od.get("target_system_id"),
                    target_body_id=od.get("target_body_id"),
                    travel_speed=od.get("travel_speed", 0.25),
                    progress=od.get("progress", 0.0),
                    waypoints=od.get("waypoints", []),
                    current_waypoint_idx=od.get("current_waypoint_idx", 0),
                )
                oq.enqueue(loc, stype, order)
        return oq

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

_REPAIR_RATE = 20  # HP restored per logistic bot per year at 100% allocation

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
        seed = gs.galaxy.seed ^ 0xDEADF00D if gs.galaxy else 0xDEADF00D
        self.rng = random.Random(seed)

    def tick(self, dt_years: float) -> list:
        """Run one sim step. Returns event dicts for UI notification."""
        events: list = []
        events.extend(self._tick_bios(dt_years))
        events.extend(self._tick_random_events(dt_years))
        events.extend(self._tick_power_plants(dt_years))
        events.extend(self._tick_research(dt_years))
        events.extend(self._tick_ships(dt_years))
        events.extend(self._tick_bot_tasks(dt_years))
        self._tick_extractors(dt_years)
        events.extend(self._tick_factories(dt_years))
        events.extend(self._tick_shipyards(dt_years))

        # Victory check
        if not self.gs._victory_declared:
            v = self.gs.check_victory()
            if v:
                self.gs._victory_declared = True
                events.append({"type": "victory", "victory_type": v})

        return events

    # ------------------------------------------------------------------

    def _tick_bios(self, dt_years: float) -> list:
        """Bio population growth, spread, mutation, attacks, and bios resource feedback."""
        events: list = []
        galaxy = self.gs.galaxy
        rng = self.rng

        # Build body-to-system map, system-body lists, and body object map
        body_to_system: dict[str, str] = {}
        body_map: dict[str, object] = {}
        system_bodies: dict[str, list] = {}
        if galaxy:
            for sys in galaxy.solar_systems:
                bodies: list = []
                for body in sys.orbital_bodies:
                    bodies.append(body)
                    body_to_system[body.id] = sys.id
                    body_map[body.id] = body
                    for moon in body.moons:
                        bodies.append(moon)
                        body_to_system[moon.id] = sys.id
                        body_map[moon.id] = moon
                system_bodies[sys.id] = bodies

        extinct_ids: list[str] = []

        for pop in self.gs.bio_state.all():
            body = body_map.get(pop.body_id)
            current_bios = getattr(getattr(body, "resources", None), "bios", 0.0) if body else 0.0

            # --- Capacity scaling based on available bios resource ---
            # When bios has been depleted below its seeded level the ecosystem
            # supports fewer individuals; carrying capacity shrinks proportionally.
            if pop.initial_bios > 0:
                bios_fraction = min(1.0, current_bios / pop.initial_bios)
                effective_capacity = max(1.0, pop.capacity * bios_fraction)
            else:
                effective_capacity = pop.capacity

            pop.tick(dt_years, effective_capacity)

            # --- Primitive populations regenerate bios resource ---
            # Primitive populations maintain the biological substrate; uplifted
            # populations consume/degrade the environment (no regen).
            if pop.bio_type == BioType.PRIMITIVE and body is not None:
                regen = pop.population * _BIOS_REGEN_PER_POP * dt_years
                bios_cap = (pop.initial_bios * 2.0) if pop.initial_bios > 0 else 500.0
                res = body.resources  # type: ignore[attr-defined]
                res.bios = min(bios_cap, res.bios + regen)

            # --- Extinction: bios depleted and population critically low ---
            if current_bios <= 0 and pop.population <= 2.0 and pop.initial_bios > 0:
                extinct_ids.append(pop.body_id)
                events.append({
                    "type":      "bios_extinction",
                    "body_id":   pop.body_id,
                    "system_id": body_to_system.get(pop.body_id, ""),
                    "bio_type":  pop.bio_type.value,
                })
                continue

            # --- Spread: when population > 70% capacity, small chance to seed nearby body ---
            if pop.population > 0.7 * pop.capacity:
                if rng.random() < 0.005 * dt_years:
                    sys_id = body_to_system.get(pop.body_id)
                    if sys_id and sys_id in system_bodies:
                        candidates = [
                            b for b in system_bodies[sys_id]
                            if b.id != pop.body_id
                            and not self.gs.bio_state.get(b.id)
                            and getattr(getattr(b, "resources", None), "bios", 0) > 0
                        ]
                        if candidates:
                            target = rng.choice(candidates)
                            seed_bios = getattr(
                                getattr(target, "resources", None), "bios", 0.0
                            )
                            seed_pop = BioPopulation(
                                body_id=target.id,
                                system_id=sys_id,
                                bio_type=pop.bio_type,
                                population=max(1.0, pop.population * 0.02),
                                aggression=pop.aggression,
                                growth_rate=pop.growth_rate,
                                initial_bios=seed_bios,
                            )
                            self.gs.bio_state.add(seed_pop)

            # --- Mutation: primitive bios near heavy player construction can become uplifted ---
            if pop.bio_type == BioType.PRIMITIVE:
                structure_count = sum(
                    i.count for i in self.gs.entity_roster.at(pop.body_id)
                    if i.category == "structure"
                )
                if structure_count >= 3:
                    mutation_chance = 0.002 * (structure_count / 3.0) * dt_years
                    if rng.random() < mutation_chance:
                        pop.bio_type = BioType.UPLIFTED
                        pop.aggression = min(1.0, pop.aggression + rng.uniform(0.1, 0.3))
                        events.append({
                            "type":      "bios_mutation",
                            "body_id":   pop.body_id,
                            "system_id": body_to_system.get(pop.body_id, ""),
                        })

            # --- Attacks: uplifted bios with aggression > 0.5 can damage any entity type ---
            if pop.bio_type == BioType.UPLIFTED and pop.aggression > 0.5:
                damage_chance = pop.aggression * 0.08 * dt_years
                if rng.random() < damage_chance:
                    all_entities = self.gs.entity_roster.at(pop.body_id)
                    target = self._pick_bio_attack_target(all_entities, rng)
                    if target:
                        dmg = int(rng.randint(10, 30) * min(2.0, pop.population / 1000.0))
                        dmg = max(10, dmg)
                        destroyed = self.gs.apply_damage(
                            pop.body_id, target.category, target.type_value, dmg
                        )
                        ev_type = "bios_entity_destroyed" if destroyed else "bios_entity_damaged"
                        events.append({
                            "type":        ev_type,
                            "body_id":     pop.body_id,
                            "system_id":   body_to_system.get(pop.body_id, ""),
                            "entity_cat":  target.category,
                            "entity_type": target.type_value,
                            "damage":      dmg,
                        })

        for body_id in extinct_ids:
            self.gs.bio_state.remove(body_id)

        return events

    def _pick_bio_attack_target(self, entities: list, rng: random.Random) -> "object | None":
        """Pick the highest-priority attackable entity from a location's roster."""
        for priority_cat, priority_type in [
            ("structure", "extractor"),
            ("structure", "factory"),
            ("structure", "shipyard"),
            ("structure", "research_array"),
            ("structure", None),
            ("bot",       None),
            ("ship",      None),
        ]:
            candidates = [
                i for i in entities
                if i.category == priority_cat
                and (priority_type is None or i.type_value == priority_type)
                and i.count > 0
            ]
            if candidates:
                return rng.choice(candidates)
        return None

    def _tick_random_events(self, dt_years: float) -> list:
        """Roll random events across all player-occupied bodies and systems."""
        events: list = []
        galaxy = self.gs.galaxy
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

        # Collect occupied locations
        occupied_body_ids: set[str] = set()
        occupied_system_ids: set[str] = set()
        for inst in self.gs.entity_roster.all():
            if inst.category in ("structure", "bot"):
                occupied_body_ids.add(inst.location_id)
            elif inst.category == "ship":
                occupied_system_ids.add(inst.location_id)

        # System-level events (solar flares)
        for sys_id in occupied_system_ids:
            ev = self._roll_system_event(sys_id, body_to_system, dt_years)
            if ev:
                events.append(ev)

        # Body-level events (one per body per tick max)
        for body_id in occupied_body_ids:
            body = body_map.get(body_id)
            if not body:
                continue
            ev = self._roll_body_event(body_id, body, body_to_system, dt_years)
            if ev:
                events.append(ev)

        return events

    def _roll_system_event(
        self, sys_id: str, body_to_system: dict, dt_years: float
    ) -> "dict | None":
        """Roll one system-level random event (solar flares, etc.)."""
        rng = self.rng
        roster = self.gs.entity_roster

        ships_here = [i for i in roster.at(sys_id) if i.category == "ship" and i.count > 0]
        if ships_here and rng.random() < 0.08 * dt_years:
            target = rng.choice(ships_here)
            dmg = rng.randint(20, 50)
            destroyed = self.gs.apply_damage(sys_id, "ship", target.type_value, dmg)
            ev_type = "solar_flare_destroyed" if destroyed else "solar_flare_damaged"
            return {
                "type":        ev_type,
                "system_id":   sys_id,
                "entity_cat":  "ship",
                "entity_type": target.type_value,
                "damage":      dmg,
            }
        return None

    def _roll_body_event(
        self, body_id: str, body: object, body_to_system: dict, dt_years: float
    ) -> "dict | None":
        """Roll one body-level random event. Returns first triggered event or None."""
        rng = self.rng
        gs = self.gs
        roster = gs.entity_roster
        sys_id = body_to_system.get(body_id, "")

        entities_here = roster.at(body_id)
        structures    = [i for i in entities_here if i.category == "structure" and i.count > 0]
        factories     = [i for i in structures if i.type_value == "factory"]
        power_plants  = [i for i in structures if i.type_value.startswith("power_plant")]
        extractors    = [i for i in structures if i.type_value == "extractor"]
        research      = [i for i in structures if i.type_value == "research_array"]
        bio_pop       = gs.bio_state.get(body_id)
        uplifted_bio  = bio_pop if (bio_pop and bio_pop.bio_type == BioType.UPLIFTED) else None

        # Asteroid impact
        if structures and rng.random() < 0.04 * dt_years:
            target = rng.choice(structures)
            destroyed = gs.apply_damage(body_id, "structure", target.type_value, 100)
            return {
                "type":        "asteroid_impact",
                "body_id":     body_id,
                "system_id":   sys_id,
                "entity_type": target.type_value,
                "destroyed":   destroyed,
            }

        # Factory malfunction
        if factories and rng.random() < 0.06 * dt_years:
            dmg = rng.randint(15, 40)
            destroyed = gs.apply_damage(body_id, "structure", "factory", dmg)
            return {
                "type":      "factory_malfunction",
                "body_id":   body_id,
                "system_id": sys_id,
                "damage":    dmg,
                "destroyed": destroyed,
            }

        # Power surge
        if power_plants and rng.random() < 0.05 * dt_years:
            target = rng.choice(power_plants)
            dmg = rng.randint(20, 50)
            destroyed = gs.apply_damage(body_id, "structure", target.type_value, dmg)
            return {
                "type":        "power_surge",
                "body_id":     body_id,
                "system_id":   sys_id,
                "entity_type": target.type_value,
                "damage":      dmg,
                "destroyed":   destroyed,
            }

        # Vein discovery (rare minerals)
        if extractors and rng.random() < 0.02 * dt_years:
            amount = rng.uniform(50, 200)
            body.resources.rare_minerals += amount  # type: ignore[attr-defined]
            return {
                "type":      "vein_discovery",
                "body_id":   body_id,
                "system_id": sys_id,
                "resource":  "rare_minerals",
                "amount":    round(amount),
            }

        # Vein discovery (minerals)
        if extractors and rng.random() < 0.04 * dt_years:
            amount = rng.uniform(200, 800)
            body.resources.minerals += amount  # type: ignore[attr-defined]
            return {
                "type":      "vein_discovery",
                "body_id":   body_id,
                "system_id": sys_id,
                "resource":  "minerals",
                "amount":    round(amount),
            }

        # Bio aggression spike
        if uplifted_bio and rng.random() < 0.06 * dt_years:
            uplifted_bio.aggression = min(1.0, uplifted_bio.aggression + rng.uniform(0.05, 0.25))
            return {
                "type":          "bio_aggression_spike",
                "body_id":       body_id,
                "system_id":     sys_id,
                "new_aggression": round(uplifted_bio.aggression, 2),
            }

        # Bio population boom
        if bio_pop and rng.random() < 0.07 * dt_years:
            bio_pop.population = min(bio_pop.capacity, bio_pop.population * rng.uniform(1.2, 2.0))
            return {
                "type":           "bio_population_boom",
                "body_id":        body_id,
                "system_id":      sys_id,
                "bio_type":       bio_pop.bio_type.value,
                "new_population": int(bio_pop.population),
            }

        # Research breakthrough
        if research and rng.random() < 0.03 * dt_years:
            in_prog = gs.tech.in_progress_ids()
            if in_prog:
                tech_id   = rng.choice(in_prog)
                bonus_pts = rng.uniform(1.0, 3.0) * len(research)
                completed = gs.tech.add_progress(tech_id, bonus_pts)
                ev: dict = {
                    "type":      "research_breakthrough",
                    "body_id":   body_id,
                    "system_id": sys_id,
                    "tech_id":   tech_id,
                }
                if completed:
                    ev["tech_completed"] = True
                return ev

        return None

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
            if not spec.input_resource:          # solar, wind, dark_matter: no fuel consumed
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
                    events.append({
                        "type": "resource_depleted",
                        "resource": spec.input_resource,
                        "location_id": inst.location_id,
                    })
                    if not spec.renewable:
                        # Non-renewable: auto-deactivate; renewable (bio) throttles via modifier
                        self.gs.power_plant_active[flag_key] = False
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
        """Advance ship travel hop-by-hop; convert Drop Ships on arrival; probe systems."""
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

            # Current leg complete — check if more waypoint hops remain
            waypoints = order.waypoints
            if waypoints and order.current_waypoint_idx + 1 < len(waypoints) - 1:
                next_idx    = order.current_waypoint_idx + 1
                next_sys_id = waypoints[next_idx]
                roster.remove("ship", ship_type, loc_id, 1)
                roster.add("ship", ship_type, next_sys_id, 1)
                oq.dequeue(loc_id, ship_type)
                order.progress             = 0.0
                order.current_waypoint_idx = next_idx
                oq.enqueue(next_sys_id, ship_type, order)
                # Passing through a system reveals it
                self.gs.discover_system(next_sys_id)
                continue

            # Final leg complete — arrived at destination
            oq.dequeue(loc_id, ship_type)

            if ship_type == "drop_ship":
                roster.remove("ship", "drop_ship", loc_id, 1)
                dest = order.target_body_id or order.target_system_id or loc_id
                roster.add("bot", "constructor", dest, 1)
                roster.add("bot", "miner", dest, 1)
                # Discover and probe the destination system
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
                    # Only harvesters can harvest bios; miners are blocked
                    if task.resource == "bios" and bot_type != "harvester":
                        continue
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

                elif task.task_type == "repair":
                    repair_amount = int(_REPAIR_RATE * effective_bots * throttle * dt_years)
                    target_cat = task.resource  # "structure" | "bot" | "ship"

                    if target_cat == "ship":
                        # Ships live at system_id; bot must be at a body with a shipyard
                        has_shipyard = any(
                            i.type_value == "shipyard" and i.category == "structure"
                            for i in gs.entity_roster.at(loc_id)
                        )
                        if not has_shipyard:
                            continue
                        heal_loc = body_to_system.get(loc_id)
                    else:
                        heal_loc = loc_id

                    if heal_loc and repair_amount > 0:
                        # Find most-damaged entity of the target category at heal_loc
                        best_key = None
                        best_dmg = 0
                        for key, dmg in gs.entity_damage.items():
                            parts = key.split(":")
                            if len(parts) == 3 and parts[0] == heal_loc and parts[1] == target_cat and dmg > best_dmg:
                                best_key = parts
                                best_dmg = dmg
                        if best_key:
                            gs.repair_damage(best_key[0], best_key[1], best_key[2], repair_amount)
                            if repair_amount >= 10:
                                events.append({"type": "entity_repaired", "location": loc_id, "category": target_cat})

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
