"""Tech tree for Universal Assemblers.

Each TechNode defines prerequisites, what it unlocks, and how much research
it costs.  TECH_TREE is the authoritative registry keyed by tech_id string.

Usage:
    from src.models.tech import TECH_TREE, can_research

    researched = {"refinery_efficiency"}
    if can_research("self_replication", researched):
        ...
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TechNode:
    id: str
    name: str
    description: str
    prerequisites: list[str]   # tech_ids that must be researched first
    unlocks: list[str]         # entity type values or feature flags this enables
    research_cost: float       # research-units required to complete
    branch: str                # "construction" | "energy" | "military" | "propulsion" | "special"


# ---------------------------------------------------------------------------
# Full tech tree
# ---------------------------------------------------------------------------

TECH_TREE: dict[str, TechNode] = {

    # -----------------------------------------------------------------------
    # Construction branch
    # -----------------------------------------------------------------------

    "structure_modules": TechNode(
        id="structure_modules",
        name="Structure Modules",
        description=(
            "Standardised modular components that snap together, enabling "
            "multi-part and orbital structures."
        ),
        prerequisites=[],
        unlocks=["multi_component_structures", "orbital_power"],
        research_cost=200.0,
        branch="construction",
    ),

    "multi_component_structures": TechNode(
        id="multi_component_structures",
        name="Multi-Component Structures",
        description=(
            "Large structures assembled from multiple modules with a "
            "dedicated modular entity view."
        ),
        prerequisites=["structure_modules"],
        unlocks=["modular_entity_view"],
        research_cost=400.0,
        branch="construction",
    ),

    "orbital_power": TechNode(
        id="orbital_power",
        name="Orbital Power Plants",
        description=(
            "Enables construction of power plants, research arrays, and "
            "shipyards in orbit around stars and on moons."
        ),
        prerequisites=["structure_modules"],
        unlocks=["orbital_placement"],
        research_cost=350.0,
        branch="construction",
    ),

    "swarm_bots": TechNode(
        id="swarm_bots",
        name="Swarm Bots",
        description=(
            "Megastructure construction using a continuous stream of "
            "Constructor bots.  Requires Self Replication for bot supply."
        ),
        prerequisites=["multi_component_structures", "self_replication"],
        unlocks=["dyson_sphere", "space_elevator", "disc_world", "halogate"],
        research_cost=1000.0,
        branch="construction",
    ),

    # -----------------------------------------------------------------------
    # Energy / production branch
    # -----------------------------------------------------------------------

    "refinery_efficiency": TechNode(
        id="refinery_efficiency",
        name="Refinery Efficiency",
        description="Optimised refinery processes reduce construction resource costs.",
        prerequisites=[],
        unlocks=["construction_cost_reduction"],
        research_cost=150.0,
        branch="energy",
    ),

    "self_replication": TechNode(
        id="self_replication",
        name="Self Replication",
        description=(
            "Enables the Replicator structure, which can autonomously "
            "reproduce basic components using local materials."
        ),
        prerequisites=["refinery_efficiency"],
        unlocks=["replicator"],
        research_cost=600.0,
        branch="energy",
    ),

    "cold_fusion": TechNode(
        id="cold_fusion",
        name="Cold Fusion",
        description="Low-temperature fusion reactions using water ice as feedstock.",
        prerequisites=["refinery_efficiency"],
        unlocks=["power_plant_cold_fusion"],
        research_cost=800.0,
        branch="energy",
    ),

    "dark_matter": TechNode(
        id="dark_matter",
        name="Dark Matter Containment",
        description=(
            "Harness dark matter as an effectively limitless power source. "
            "No resource consumption required."
        ),
        prerequisites=["cold_fusion", "space_folding"],
        unlocks=["power_plant_dark_matter"],
        research_cost=2000.0,
        branch="special",
    ),

    # -----------------------------------------------------------------------
    # Military branch
    # -----------------------------------------------------------------------

    "atomic_warships": TechNode(
        id="atomic_warships",
        name="Atomic Warships",
        description=(
            "Nuclear-drive warships capable of offensive and defensive "
            "combat operations."
        ),
        prerequisites=[],
        unlocks=["warship"],
        research_cost=500.0,
        branch="military",
    ),

    "doom_machine": TechNode(
        id="doom_machine",
        name="Doom Machine",
        description=(
            "A self-sustaining weapons megastructure of terrifying scale. "
            "Requires both Atomic Warships and Swarm Bots."
        ),
        prerequisites=["atomic_warships", "swarm_bots"],
        unlocks=["doom_machine_entity"],
        research_cost=2000.0,
        branch="military",
    ),

    # -----------------------------------------------------------------------
    # Propulsion branch
    # -----------------------------------------------------------------------

    "solar_sails": TechNode(
        id="solar_sails",
        name="Solar Sails",
        description="Light-pressure propulsion increases standard ship travel speed.",
        prerequisites=[],
        unlocks=["ship_speed_bonus"],
        research_cost=200.0,
        branch="propulsion",
    ),

    "space_folding": TechNode(
        id="space_folding",
        name="Space Folding",
        description=(
            "Metric compression drives that dramatically extend ship "
            "travel range between systems."
        ),
        prerequisites=["solar_sails"],
        unlocks=["ship_range_bonus"],
        research_cost=600.0,
        branch="propulsion",
    ),

    "wormhole_drive": TechNode(
        id="wormhole_drive",
        name="Wormhole Drive",
        description=(
            "Unstable wormhole generators that enable near-instantaneous "
            "travel — destination is not guaranteed."
        ),
        prerequisites=["space_folding"],
        unlocks=["wormhole_travel"],
        research_cost=1500.0,
        branch="special",
    ),

    "energy_efficiency": TechNode(
        id="energy_efficiency",
        name="Energy Efficiency",
        description="Advanced materials and superconducting grids boost all power plant output by 25%.",
        prerequisites=[],
        unlocks=["power_efficiency_bonus"],
        research_cost=250.0,
        branch="energy",
    ),

    "advanced_manufacturing": TechNode(
        id="advanced_manufacturing",
        name="Advanced Manufacturing",
        description="Factory automation enables production of composite components from alloys and electronics.",
        prerequisites=["refinery_efficiency"],
        unlocks=["components_production"],
        research_cost=400.0,
        branch="energy",
    ),

    "asteroid_mining": TechNode(
        id="asteroid_mining",
        name="Asteroid Mining",
        description="Equips Mining Vessels with drilling rigs and micro-thrusters for high-yield asteroid extraction.",
        prerequisites=["solar_sails"],
        unlocks=["asteroid_mining_enabled"],
        research_cost=350.0,
        branch="propulsion",
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def can_research(tech_id: str, researched: set[str]) -> bool:
    """Return True if all prerequisites for tech_id are in researched."""
    node = TECH_TREE.get(tech_id)
    if node is None:
        return False
    return all(p in researched for p in node.prerequisites)


def unlocked_by(feature: str) -> list[str]:
    """Return tech_ids whose unlocks list contains feature."""
    return [tid for tid, node in TECH_TREE.items() if feature in node.unlocks]
