"""Entity type enumerations, power-plant specs, and starting entity manifest."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StructureType(str, Enum):
    EXTRACTOR              = "extractor"
    REPLICATOR             = "replicator"
    POWER_PLANT_SOLAR      = "power_plant_solar"
    POWER_PLANT_FOSSIL     = "power_plant_fossil"
    POWER_PLANT_NUCLEAR    = "power_plant_nuclear"
    POWER_PLANT_COLD_FUSION = "power_plant_cold_fusion"
    POWER_PLANT_DARK_MATTER = "power_plant_dark_matter"
    RESEARCH_ARRAY         = "research_array"


class BotType(str, Enum):
    WORKER      = "worker"
    HARVESTER   = "harvester"
    CONSTRUCTOR = "constructor"


class ShipType(str, Enum):
    PROBE            = "probe"
    CONSTRUCTOR_SHIP = "constructor_ship"
    MINING_VESSEL    = "mining_vessel"


@dataclass
class PowerPlantSpec:
    name: str
    base_output: float          # energy-units/yr per plant @ 100% throttle
    input_resource: str | None  # "gas" | "rare_minerals" | "ice" | None
    input_rate: float           # resource-units/yr per plant @ 100%
    requires_resource: str | None  # resource field that must be > 0 on body
    color: tuple                # RGB for bar chart
    unlocked_by: str | None     # tech_id or None (starter plants)


POWER_PLANT_SPECS: dict[StructureType, PowerPlantSpec] = {
    StructureType.POWER_PLANT_SOLAR: PowerPlantSpec(
        name="Solar Farm",
        base_output=50.0,
        input_resource=None,
        input_rate=0.0,
        requires_resource=None,
        color=(255, 220, 80),
        unlocked_by=None,
    ),
    StructureType.POWER_PLANT_FOSSIL: PowerPlantSpec(
        name="Fossil Fuel Plant",
        base_output=80.0,
        input_resource="gas",
        input_rate=10.0,
        requires_resource="gas",
        color=(180, 140, 80),
        unlocked_by=None,
    ),
    StructureType.POWER_PLANT_NUCLEAR: PowerPlantSpec(
        name="Nuclear Plant",
        base_output=150.0,
        input_resource="rare_minerals",
        input_rate=5.0,
        requires_resource="rare_minerals",
        color=(100, 220, 120),
        unlocked_by=None,
    ),
    StructureType.POWER_PLANT_COLD_FUSION: PowerPlantSpec(
        name="Cold Fusion Plant",
        base_output=300.0,
        input_resource="ice",
        input_rate=3.0,
        requires_resource="ice",
        color=(100, 200, 255),
        unlocked_by="cold_fusion",
    ),
    StructureType.POWER_PLANT_DARK_MATTER: PowerPlantSpec(
        name="Dark Matter Plant",
        base_output=1000.0,
        input_resource=None,
        input_rate=0.0,
        requires_resource=None,
        color=(200, 100, 255),
        unlocked_by="dark_matter",
    ),
}

POWER_PLANT_TYPES: list[StructureType] = [
    StructureType.POWER_PLANT_SOLAR,
    StructureType.POWER_PLANT_FOSSIL,
    StructureType.POWER_PLANT_NUCLEAR,
    StructureType.POWER_PLANT_COLD_FUSION,
    StructureType.POWER_PLANT_DARK_MATTER,
]

# Starting entity manifest: (category, type_value, location, count)
# "location" is "home_body" or "home_system" (resolved at init time)
STARTING_ENTITIES: list[tuple[str, str, str, int]] = [
    ("structure", "extractor",           "home_body",   2),
    ("structure", "replicator",          "home_body",   1),
    ("structure", "power_plant_solar",   "home_body",   3),
    ("structure", "research_array",      "home_body",   1),
    ("bot",       "worker",              "home_body",   5),
    ("bot",       "harvester",           "home_body",   3),
    ("bot",       "constructor",         "home_body",   2),
    ("ship",      "probe",               "home_system", 2),
    ("ship",      "constructor_ship",    "home_system", 1),
    ("ship",      "mining_vessel",       "home_system", 1),
]
