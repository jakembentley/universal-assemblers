"""Entity type enumerations, power-plant specs, and starting entity manifest."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Structure types
# ---------------------------------------------------------------------------

class StructureType(str, Enum):
    # --- Starter structures ---
    EXTRACTOR               = "extractor"
    FACTORY                 = "factory"
    POWER_PLANT_SOLAR       = "power_plant_solar"
    RESEARCH_ARRAY          = "research_array"
    # --- Buildable (no tech gate) ---
    POWER_PLANT_WIND        = "power_plant_wind"
    POWER_PLANT_BIOS        = "power_plant_bios"
    POWER_PLANT_FOSSIL      = "power_plant_fossil"
    POWER_PLANT_NUCLEAR     = "power_plant_nuclear"
    SHIPYARD                = "shipyard"
    STORAGE_HUB             = "storage_hub"
    # --- Tech-gated ---
    POWER_PLANT_COLD_FUSION = "power_plant_cold_fusion"   # cold_fusion
    POWER_PLANT_DARK_MATTER = "power_plant_dark_matter"   # dark_matter
    REPLICATOR              = "replicator"                # self_replication


# ---------------------------------------------------------------------------
# Megastructure types (separate category — special rules apply)
# ---------------------------------------------------------------------------

class MegastructureType(str, Enum):
    DYSON_SPHERE    = "dyson_sphere"     # swarm_bots; alters star visual, decays planets
    SPACE_ELEVATOR  = "space_elevator"   # swarm_bots; reduces launch cost
    DISC_WORLD      = "disc_world"       # swarm_bots; massive habitable megastructure
    HALOGATE        = "halogate"         # swarm_bots; fast system-to-system transit
    DOOM_MACHINE    = "doom_machine"     # doom_machine tech; offensive weapons platform


# ---------------------------------------------------------------------------
# Bot types
# ---------------------------------------------------------------------------

class BotType(str, Enum):
    LOGISTIC_BOT = "logistic_bot"
    HARVESTER    = "harvester"
    MINER        = "miner"
    CONSTRUCTOR  = "constructor"


# ---------------------------------------------------------------------------
# Ship types
# ---------------------------------------------------------------------------

class ShipType(str, Enum):
    # --- Starter ships ---
    PROBE         = "probe"
    DROP_SHIP     = "drop_ship"      # on arrival converts to Constructor + Miner bot
    MINING_VESSEL = "mining_vessel"
    # --- Buildable ---
    TRANSPORT     = "transport"
    WARSHIP       = "warship"        # atomic_warships tech


# ---------------------------------------------------------------------------
# Bio types (engine-managed, not player-controlled)
# ---------------------------------------------------------------------------

class BioType(str, Enum):
    PRIMITIVE = "primitive"   # passive; can be interacted with
    UPLIFTED  = "uplifted"    # active; can damage player entities; can be interacted with


# ---------------------------------------------------------------------------
# Power plant specifications
# ---------------------------------------------------------------------------

@dataclass
class PowerPlantSpec:
    name: str
    base_output: float           # energy-units/yr per plant @ 100% throttle
    renewable: bool              # True if no resource is consumed
    input_resource: str | None   # Resource field name consumed ("gas", "rare_minerals", etc.)
    input_rate: float            # resource-units/yr per plant @ 100%
    requires_resource: str | None  # resource field that must be > 0 on the body
    color: tuple                 # RGB for bar chart
    unlocked_by: str | None      # tech_id, or None for starter plants


POWER_PLANT_SPECS: dict[StructureType, PowerPlantSpec] = {

    StructureType.POWER_PLANT_SOLAR: PowerPlantSpec(
        name="Solar Farm",
        base_output=50.0,
        renewable=True,
        input_resource=None,
        input_rate=0.0,
        requires_resource=None,
        color=(255, 220, 80),
        unlocked_by=None,
    ),

    StructureType.POWER_PLANT_WIND: PowerPlantSpec(
        name="Wind Farm",
        base_output=40.0,
        renewable=True,
        input_resource=None,
        input_rate=0.0,
        requires_resource=None,       # terrestrial atmosphere check handled by game rules
        color=(180, 230, 255),
        unlocked_by=None,
    ),

    StructureType.POWER_PLANT_BIOS: PowerPlantSpec(
        name="Bio Plant",
        base_output=60.0,
        renewable=True,
        input_resource="bios",
        input_rate=8.0,
        requires_resource="bios",
        color=(80, 200, 100),
        unlocked_by=None,
    ),

    StructureType.POWER_PLANT_FOSSIL: PowerPlantSpec(
        name="Fossil Fuel Plant",
        base_output=80.0,
        renewable=False,
        input_resource="gas",
        input_rate=10.0,
        requires_resource="gas",
        color=(180, 140, 80),
        unlocked_by=None,
    ),

    StructureType.POWER_PLANT_NUCLEAR: PowerPlantSpec(
        name="Nuclear Plant",
        base_output=150.0,
        renewable=False,
        input_resource="rare_minerals",
        input_rate=5.0,
        requires_resource="rare_minerals",
        color=(100, 220, 120),
        unlocked_by=None,
    ),

    StructureType.POWER_PLANT_COLD_FUSION: PowerPlantSpec(
        name="Cold Fusion Plant",
        base_output=300.0,
        renewable=False,
        input_resource="ice",
        input_rate=3.0,
        requires_resource="ice",
        color=(100, 200, 255),
        unlocked_by="cold_fusion",
    ),

    StructureType.POWER_PLANT_DARK_MATTER: PowerPlantSpec(
        name="Dark Matter Plant",
        base_output=1000.0,
        renewable=True,
        input_resource=None,
        input_rate=0.0,
        requires_resource=None,
        color=(200, 100, 255),
        unlocked_by="dark_matter",
    ),
}

POWER_PLANT_TYPES: list[StructureType] = list(POWER_PLANT_SPECS.keys())


# ---------------------------------------------------------------------------
# Build costs
# ---------------------------------------------------------------------------
# Maps entity type_value → {resource_field: amount_per_unit}
# Constructors deduct these from the body's resources each time one unit is built.

BUILD_COSTS: dict[str, dict[str, float]] = {
    # Structures
    "extractor":               {"minerals": 50,  "rare_minerals": 10},
    "factory":                 {"minerals": 100, "rare_minerals": 20},
    "research_array":          {"minerals": 80,  "rare_minerals": 30},
    "power_plant_solar":       {"minerals": 40,  "rare_minerals": 5},
    "power_plant_wind":        {"minerals": 40,  "rare_minerals": 5},
    "power_plant_bios":        {"minerals": 60,  "rare_minerals": 10},
    "power_plant_fossil":      {"minerals": 80,  "rare_minerals": 15},
    "power_plant_nuclear":     {"minerals": 120, "rare_minerals": 40},
    "power_plant_cold_fusion": {"minerals": 200, "rare_minerals": 80},
    "power_plant_dark_matter": {"minerals": 500, "rare_minerals": 200},
    "shipyard":                {"minerals": 200, "rare_minerals": 50},
    "storage_hub":             {"minerals": 60,  "rare_minerals": 10},
    "replicator":              {"minerals": 300, "rare_minerals": 100},
    # Ships
    "probe":                   {"minerals": 40,  "rare_minerals": 15},
    "drop_ship":               {"minerals": 80,  "rare_minerals": 20},
    # Bots
    "miner":                   {"minerals": 20,  "rare_minerals": 5},
    "constructor":             {"minerals": 20,  "rare_minerals": 5},
    "logistic_bot":            {"minerals": 15,  "rare_minerals": 2},
    "harvester":               {"minerals": 25,  "rare_minerals": 5},
}


# ---------------------------------------------------------------------------
# Energy consumption
# ---------------------------------------------------------------------------
# Maps entity type_value → energy-units/yr consumed per unit

ENERGY_CONSUMPTION: dict[str, float] = {
    "extractor":               20.0,
    "factory":                 25.0,
    "research_array":          30.0,
    "shipyard":                40.0,
    "storage_hub":             10.0,
    "replicator":              60.0,
    "miner":                    5.0,
    "constructor":              5.0,
    "logistic_bot":             3.0,
    "harvester":                4.0,
}


def compute_power_modifier(gs, body_id: str, plant_type_value: str) -> float:
    """
    Return an environment + research multiplier for a power plant's output.
    Solar: inverse-square orbital distance, star luminosity.
    Wind: atmospheric density by body subtype.
    Bios: scales with available bios resource.
    Research: energy_efficiency tech +25%.
    All others: research bonus only.
    """
    env = gs.body_env.get(body_id, {})
    orbital_radius  = env.get("orbital_radius", 1.0)
    subtype         = env.get("subtype", "")
    star_lum        = env.get("star_luminosity", 3.8e26)
    research_bonus  = 1.25 if "energy_efficiency" in gs.tech.researched else 1.0

    if plant_type_value == "power_plant_solar":
        ref_lum = 3.8e26  # G-type Sun
        lum_factor = min(3.0, (star_lum / ref_lum) ** 0.5)
        dist_factor = lum_factor / max(0.05, orbital_radius ** 2)
        return min(5.0, max(0.05, dist_factor)) * research_bonus

    if plant_type_value == "power_plant_wind":
        atm = {"gas_giant": 2.5, "hot_jupiter": 3.0, "terrestrial": 1.0,
               "super_earth": 1.2, "ice_giant": 0.6}.get(subtype, 0.2)
        return atm * research_bonus

    if plant_type_value == "power_plant_bios":
        # Need bios resource — look it up from roster/body
        # Without galaxy access here we return a neutral 1.0; caller may override
        return research_bonus

    # Fossil, nuclear, cold fusion, dark matter — stable, just research
    return research_bonus


def compute_energy_balance(gs, body_id: str) -> tuple[float, float]:
    """Return (production, consumption) energy-units/yr for a body."""
    roster = gs.entity_roster
    production = 0.0
    consumption = 0.0
    for inst in roster.at(body_id):
        if inst.category == "structure":
            try:
                st = StructureType(inst.type_value)
                if st in POWER_PLANT_SPECS:
                    flag_key = f"{body_id}:{inst.type_value}"
                    if gs.power_plant_active.get(flag_key, True):
                        modifier = compute_power_modifier(gs, body_id, inst.type_value)
                        production += POWER_PLANT_SPECS[st].base_output * inst.count * modifier
            except ValueError:
                pass
            cons = ENERGY_CONSUMPTION.get(inst.type_value, 0.0)
            consumption += cons * inst.count
        elif inst.category == "bot":
            consumption += ENERGY_CONSUMPTION.get(inst.type_value, 0.0) * inst.count
    return production, consumption


# ---------------------------------------------------------------------------
# Manufactured resource refine recipes
# ---------------------------------------------------------------------------
# Maps output_resource → (input_costs_per_unit, output_per_extractor_per_yr)

REFINE_RECIPES: dict[str, tuple[dict[str, float], float]] = {
    "electronics": ({"minerals": 20.0, "rare_minerals": 10.0}, 5.0),
    "alloys":      ({"minerals": 30.0},                        8.0),
    "fuel_cells":  ({"gas": 20.0, "ice": 10.0},               5.0),
}


# ---------------------------------------------------------------------------
# Factory recipes
# ---------------------------------------------------------------------------
# Maps recipe_id → (input_costs_per_output_unit, output_per_factory_per_yr, output_resource_field)

FACTORY_RECIPES: dict[str, tuple[dict[str, float], float, str]] = {
    # recipe_id: (inputs, output_rate/factory/yr, output_resource_field)
    "alloys":       ({"minerals":       30.0},                     12.0, "alloys"),
    "electronics":  ({"minerals":       20.0, "rare_minerals": 8.0}, 10.0, "electronics"),
    "fuel_cells":   ({"gas":            20.0, "ice":         10.0},  8.0, "fuel_cells"),
    "components":   ({"alloys":          6.0, "electronics":  4.0},  3.0, "components"),
}

# ---------------------------------------------------------------------------
# Ship fuel costs
# ---------------------------------------------------------------------------
# fuel_cells consumed per dispatch

SHIP_FUEL_COSTS: dict[str, float] = {
    "probe":          2.0,
    "drop_ship":      8.0,
    "mining_vessel":  5.0,
    "transport":      6.0,
    "warship":        10.0,
}


# ---------------------------------------------------------------------------
# Shipyard build rates
# ---------------------------------------------------------------------------
# Maps ship_type → build_time_years_per_ship_per_shipyard

SHIPYARD_BUILD_RATES: dict[str, float] = {
    "probe":         1.0,   # 1 yr per shipyard
    "drop_ship":     2.0,
    "mining_vessel": 2.5,
    "transport":     3.0,
    "warship":       5.0,
}


# ---------------------------------------------------------------------------
# Starting entity manifest
# ---------------------------------------------------------------------------
# (category, type_value, location, count)
# location: "home_body" = first planet in home system
#           "home_system" = home system id

STARTING_ENTITIES: list[tuple[str, str, str, int]] = [
    # Structures on the starting planet
    ("structure", "extractor",         "home_body",   1),
    ("structure", "factory",           "home_body",   1),
    ("structure", "power_plant_solar", "home_body",   1),
    ("structure", "research_array",    "home_body",   1),
    ("structure", "power_plant_wind",  "home_body",   1),
    # Bots on the starting planet
    ("bot",       "miner",             "home_body",   1),
    ("bot",       "constructor",       "home_body",   1),
    # Ships in the home system
    ("ship",      "probe",             "home_system", 1),
    ("ship",      "drop_ship",         "home_system", 1),
    ("ship",      "mining_vessel",     "home_system", 1),
]
