from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .resource import Resource


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BodyType(str, Enum):
    """Top-level classification of every object in the galaxy map."""
    STAR = "star"
    PLANET = "planet"
    EXOPLANET = "exoplanet"   # Rogue / captured planet drifting at wide orbits
    COMET = "comet"
    ASTEROID = "asteroid"
    MOON = "moon"


class StarType(str, Enum):
    """Harvard spectral classification used to drive stat generation."""
    O_TYPE = "O-type"   # Blue supergiant  — rare, luminous, short-lived
    B_TYPE = "B-type"   # Blue-white giant
    A_TYPE = "A-type"   # White
    F_TYPE = "F-type"   # Yellow-white
    G_TYPE = "G-type"   # Yellow (Sol analogue)
    K_TYPE = "K-type"   # Orange dwarf
    M_TYPE = "M-type"   # Red dwarf       — most common


class PlanetSubtype(str, Enum):
    """Geological / atmospheric classification for planets and exoplanets."""
    TERRESTRIAL = "terrestrial"     # Rocky, solid surface
    SUPER_EARTH = "super_earth"     # Large rocky world
    GAS_GIANT = "gas_giant"         # Jupiter / Saturn analogue
    ICE_GIANT = "ice_giant"         # Uranus / Neptune analogue
    HOT_JUPITER = "hot_jupiter"     # Gas giant in a very close orbit


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Moon:
    """
    A natural satellite orbiting a planet or exoplanet.

    Moons can carry mineral and ice deposits but never have their own moons.
    """
    id: str
    name: str
    size: float                          # Relative diameter (Earth = 1.0)
    resources: Resource = field(default_factory=Resource)
    body_type: BodyType = field(default=BodyType.MOON, init=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "body_type": self.body_type.value,
            "size": round(self.size, 4),
            "resources": self.resources.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Moon":
        return cls(
            id=d["id"],
            name=d["name"],
            size=d["size"],
            resources=Resource.from_dict(d["resources"]),
        )


@dataclass
class CelestialBody:
    """
    Any non-stellar orbital body: planet, exoplanet, comet, or asteroid.

    Planets and exoplanets may host a list of Moon children.
    Comets and asteroids never have moons.

    orbital_radius -- Semi-major axis in AU (1 AU = Earth–Sun distance).
    size           -- Relative diameter (Earth = 1.0).
    subtype        -- Populated for PLANET and EXOPLANET; None otherwise.
    """
    id: str
    name: str
    body_type: BodyType
    size: float
    orbital_radius: float
    resources: Resource = field(default_factory=Resource)
    subtype: Optional[str] = None
    moons: List[Moon] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "name": self.name,
            "body_type": self.body_type.value,
            "size": round(self.size, 4),
            "orbital_radius": round(self.orbital_radius, 4),
            "resources": self.resources.to_dict(),
            "moons": [m.to_dict() for m in self.moons],
        }
        if self.subtype is not None:
            d["subtype"] = self.subtype
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CelestialBody":
        return cls(
            id=d["id"],
            name=d["name"],
            body_type=BodyType(d["body_type"]),
            size=d["size"],
            orbital_radius=d["orbital_radius"],
            resources=Resource.from_dict(d["resources"]),
            subtype=d.get("subtype"),
            moons=[Moon.from_dict(m) for m in d.get("moons", [])],
        )


@dataclass
class Star:
    """
    The central stellar body of a solar system.

    Stars carry a massive gas reservoir and radiate energy_output continuously.
    They have no orbital_radius (they sit at the system origin).

    mass      -- Stellar mass relative to Sol (1.0 = our Sun).
    star_type -- Harvard spectral class.
    """
    id: str
    name: str
    star_type: StarType
    mass: float
    resources: Resource = field(default_factory=Resource)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "body_type": BodyType.STAR.value,
            "star_type": self.star_type.value,
            "mass": round(self.mass, 4),
            "resources": self.resources.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Star":
        return cls(
            id=d["id"],
            name=d["name"],
            star_type=StarType(d["star_type"]),
            mass=d["mass"],
            resources=Resource.from_dict(d["resources"]),
        )


@dataclass
class SolarSystem:
    """
    A stellar system containing one star and its collection of orbital bodies.

    position  -- Galactic (x, y) coordinates in light-years from the map origin.
    warp_only -- True if this system requires a Warp Drive to reach; not connected
                 to the main adjacency graph.
    """
    id: str
    name: str
    position: dict           # {"x": float, "y": float}
    star: Star
    orbital_bodies: List[CelestialBody] = field(default_factory=list)
    warp_only: bool = False

    # Convenience counts (populated after generation for fast reads)
    @property
    def num_planets(self) -> int:
        return sum(1 for b in self.orbital_bodies if b.body_type == BodyType.PLANET)

    @property
    def num_exoplanets(self) -> int:
        return sum(1 for b in self.orbital_bodies if b.body_type == BodyType.EXOPLANET)

    @property
    def num_comets(self) -> int:
        return sum(1 for b in self.orbital_bodies if b.body_type == BodyType.COMET)

    @property
    def num_asteroids(self) -> int:
        return sum(1 for b in self.orbital_bodies if b.body_type == BodyType.ASTEROID)

    @property
    def num_moons(self) -> int:
        return sum(len(b.moons) for b in self.orbital_bodies)

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "name": self.name,
            "position": self.position,
            "star": self.star.to_dict(),
            "body_counts": {
                "planets": self.num_planets,
                "exoplanets": self.num_exoplanets,
                "comets": self.num_comets,
                "asteroids": self.num_asteroids,
                "moons": self.num_moons,
            },
            "orbital_bodies": [b.to_dict() for b in self.orbital_bodies],
        }
        if self.warp_only:
            d["warp_only"] = True
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SolarSystem":
        return cls(
            id=d["id"],
            name=d["name"],
            position=d["position"],
            star=Star.from_dict(d["star"]),
            orbital_bodies=[CelestialBody.from_dict(b) for b in d.get("orbital_bodies", [])],
            warp_only=d.get("warp_only", False),
        )


@dataclass
class Galaxy:
    """
    The root map object.  Serialised directly to the map JSON file.

    seed       -- The RNG seed used; supply the same seed to reproduce the map.
    parameters -- Generation knobs recorded for reference and re-generation.
    """
    seed: int
    name: str
    generated_at: str
    parameters: dict
    solar_systems: List[SolarSystem] = field(default_factory=list)

    # Aggregate stats
    @property
    def total_bodies(self) -> int:
        return sum(len(s.orbital_bodies) for s in self.solar_systems)

    @property
    def total_moons(self) -> int:
        return sum(s.num_moons for s in self.solar_systems)

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "name": self.name,
            "generated_at": self.generated_at,
            "parameters": self.parameters,
            "summary": {
                "solar_systems": len(self.solar_systems),
                "total_orbital_bodies": self.total_bodies,
                "total_moons": self.total_moons,
            },
            "solar_systems": [s.to_dict() for s in self.solar_systems],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Galaxy":
        return cls(
            seed=d["seed"],
            name=d["name"],
            generated_at=d["generated_at"],
            parameters=d["parameters"],
            solar_systems=[SolarSystem.from_dict(s) for s in d.get("solar_systems", [])],
        )
