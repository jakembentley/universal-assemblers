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
    WORKER      = "worker"
    HARVESTER   = "harvester"
    MINER       = "miner"
    CONSTRUCTOR = "constructor"


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
    # Bots
    "miner":                   {"minerals": 20,  "rare_minerals": 5},
    "constructor":             {"minerals": 20,  "rare_minerals": 5},
    "worker":                  {"minerals": 15,  "rare_minerals": 2},
    "harvester":               {"minerals": 25,  "rare_minerals": 5},
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
