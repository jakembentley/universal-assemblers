"""
Map generator for Universal Assemblers.

Call MapGenerator(seed=...).generate() to produce a Galaxy, then
MapGenerator.save(galaxy, path) to write it to a JSON file.

Seeded determinism: all randomness flows through self.rng (random.Random
initialised with the seed), so the same seed always produces the same map.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from typing import List, Optional

from .models.celestial import (
    BodyType,
    CelestialBody,
    Galaxy,
    Moon,
    PlanetSubtype,
    SolarSystem,
    Star,
    StarType,
)
from .models.resource import Resource


# ---------------------------------------------------------------------------
# Name-generation vocabulary
# ---------------------------------------------------------------------------

_SYSTEM_PREFIXES = [
    "Aegis", "Altair", "Antares", "Aquila", "Arcturus", "Auriga",
    "Carina", "Cassini", "Centauri", "Corvus", "Cygnus", "Dorado",
    "Draco", "Eridani", "Fornax", "Gemini", "Hydra", "Kepler",
    "Lacerta", "Lyra", "Meridian", "Naos", "Norma", "Ophiuchi",
    "Orion", "Perseus", "Phecda", "Proxima", "Puppis", "Rigel",
    "Serpens", "Sirius", "Tau", "Tucana", "Vega", "Volans", "Vulpecula",
]

_SYSTEM_SUFFIXES = [
    "Alpha", "Beta", "Delta", "Epsilon", "Gamma", "Major", "Minor",
    "Nova", "Omega", "Prime", "Rex", "Sigma", "Theta", "Ultra", "Zeta",
]

_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
          "XI", "XII", "XIII", "XIV", "XV"]

_MOON_LABELS = list("abcdefghijklmnopqrstuvwxyz")


# ---------------------------------------------------------------------------
# Star type parameters
# ---------------------------------------------------------------------------

# (min_mass, max_mass) relative to Sol
_STAR_MASS = {
    StarType.O_TYPE: (16.0, 150.0),
    StarType.B_TYPE: (2.0, 16.0),
    StarType.A_TYPE: (1.4, 2.1),
    StarType.F_TYPE: (1.04, 1.4),
    StarType.G_TYPE: (0.8, 1.04),
    StarType.K_TYPE: (0.45, 0.8),
    StarType.M_TYPE: (0.08, 0.45),
}

# Weighted probabilities for each star type (rarer = lower weight)
_STAR_WEIGHTS = {
    StarType.O_TYPE: 1,
    StarType.B_TYPE: 3,
    StarType.A_TYPE: 6,
    StarType.F_TYPE: 10,
    StarType.G_TYPE: 15,
    StarType.K_TYPE: 25,
    StarType.M_TYPE: 40,
}

# Approximate bolometric luminosity scale (watts) for energy_output
_STAR_LUMINOSITY_BASE = {
    StarType.O_TYPE: 1e31,
    StarType.B_TYPE: 1e29,
    StarType.A_TYPE: 1e28,
    StarType.F_TYPE: 5e26,
    StarType.G_TYPE: 3.8e26,
    StarType.K_TYPE: 8e25,
    StarType.M_TYPE: 5e23,
}


# ---------------------------------------------------------------------------
# MapGenerator
# ---------------------------------------------------------------------------

class MapGenerator:
    """
    Procedural map generator for Universal Assemblers.

    Parameters
    ----------
    seed : int or None
        RNG seed.  None generates a random seed automatically.
    num_solar_systems : int
        How many stellar systems to place in the map (N).
    min_bodies_per_system / max_bodies_per_system : int
        Bounds on total orbital bodies per system (K range).
    max_moons_per_planet : int
        Hard cap on moons for any single planet or exoplanet.
    galaxy_name : str
        Display name for the sector / galaxy.
    galaxy_radius_ly : float
        Half-width of the square region used for system placement (light-years).
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        num_solar_systems: int = 10,
        min_bodies_per_system: int = 5,
        max_bodies_per_system: int = 25,
        max_moons_per_planet: int = 8,
        galaxy_name: str = "Unnamed Sector",
        galaxy_radius_ly: float = 500.0,
    ) -> None:
        self.seed = seed if seed is not None else random.randint(0, 2**32 - 1)
        self.rng = random.Random(self.seed)

        self.num_solar_systems = num_solar_systems
        self.min_bodies = min_bodies_per_system
        self.max_bodies = max_bodies_per_system
        self.max_moons = max_moons_per_planet
        self.galaxy_name = galaxy_name
        self.galaxy_radius = galaxy_radius_ly

        # Internal planet counter per system — reset for each system
        self._planet_ordinal: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> Galaxy:
        """Generate and return a complete Galaxy object."""
        systems = [
            self._generate_solar_system(i)
            for i in range(self.num_solar_systems)
        ]
        return Galaxy(
            seed=self.seed,
            name=self.galaxy_name,
            generated_at=datetime.now(timezone.utc).isoformat(),
            parameters={
                "num_solar_systems": self.num_solar_systems,
                "min_bodies_per_system": self.min_bodies,
                "max_bodies_per_system": self.max_bodies,
                "max_moons_per_planet": self.max_moons,
                "galaxy_radius_ly": self.galaxy_radius,
            },
            solar_systems=systems,
        )

    @staticmethod
    def save(galaxy: Galaxy, output_path: str) -> str:
        """Serialise *galaxy* to JSON at *output_path* and return the path."""
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(galaxy.to_dict(), fh, indent=2)
        return output_path

    # ------------------------------------------------------------------
    # Solar-system generation
    # ------------------------------------------------------------------

    def _generate_solar_system(self, sys_index: int) -> SolarSystem:
        self._planet_ordinal = 0  # reset ordinal for planet naming
        sys_id = f"sys_{sys_index:04d}"
        name = self._system_name()

        position = {
            "x": round(self.rng.uniform(-self.galaxy_radius, self.galaxy_radius), 2),
            "y": round(self.rng.uniform(-self.galaxy_radius, self.galaxy_radius), 2),
        }

        star = self._generate_star(sys_id, name)

        # Decide how many of each body type we want
        total = self.rng.randint(self.min_bodies, self.max_bodies)
        counts = self._split_body_counts(total)

        orbital_bodies: List[CelestialBody] = []
        body_seq = 0

        # Planets — placed at increasing orbital radii from the star
        planet_radii = sorted(
            self.rng.uniform(0.15, 35.0) for _ in range(counts["planets"])
        )
        for radius in planet_radii:
            body = self._generate_planet(sys_id, name, body_seq, radius)
            orbital_bodies.append(body)
            body_seq += 1

        # Exoplanets — wide, cold orbits beyond the main system
        for _ in range(counts["exoplanets"]):
            radius = self.rng.uniform(40.0, 250.0)
            body = self._generate_exoplanet(sys_id, name, body_seq, radius)
            orbital_bodies.append(body)
            body_seq += 1

        # Comets — highly elliptical, represented by a large orbital radius
        for i in range(counts["comets"]):
            radius = self.rng.uniform(5.0, 120.0)
            body = self._generate_comet(sys_id, name, body_seq, i)
            orbital_bodies.append(body)
            body_seq += 1

        # Asteroids — clustered in the inner-to-mid system belt
        for i in range(counts["asteroids"]):
            radius = self.rng.uniform(1.5, 12.0)
            body = self._generate_asteroid(sys_id, name, body_seq, radius, i)
            orbital_bodies.append(body)
            body_seq += 1

        return SolarSystem(
            id=sys_id,
            name=name,
            position=position,
            star=star,
            orbital_bodies=orbital_bodies,
        )

    def _split_body_counts(self, total: int) -> dict:
        """
        Distribute *total* bodies into type buckets.
        Ratios are jittered per-system so each system feels distinct.
        """
        planet_frac = self.rng.uniform(0.20, 0.40)
        exo_frac = self.rng.uniform(0.00, 0.08)
        comet_frac = self.rng.uniform(0.10, 0.25)

        planets = max(1, round(total * planet_frac))
        exoplanets = round(total * exo_frac)
        comets = round(total * comet_frac)
        asteroids = max(0, total - planets - exoplanets - comets)

        return {
            "planets": planets,
            "exoplanets": exoplanets,
            "comets": comets,
            "asteroids": asteroids,
        }

    # ------------------------------------------------------------------
    # Star generation
    # ------------------------------------------------------------------

    def _generate_star(self, sys_id: str, system_name: str) -> Star:
        star_types = list(_STAR_WEIGHTS.keys())
        weights = [_STAR_WEIGHTS[t] for t in star_types]
        star_type: StarType = self.rng.choices(star_types, weights=weights, k=1)[0]

        lo, hi = _STAR_MASS[star_type]
        mass = round(self.rng.uniform(lo, hi), 4)

        lum_base = _STAR_LUMINOSITY_BASE[star_type]
        energy_output = round(lum_base * self.rng.uniform(0.75, 1.25), 4)

        resources = Resource(
            gas=round(self.rng.uniform(5e6, 5e9), 2),
            energy_output=energy_output,
        )

        return Star(
            id=f"{sys_id}_star",
            name=f"{system_name} Star",
            star_type=star_type,
            mass=mass,
            resources=resources,
        )

    # ------------------------------------------------------------------
    # Orbital body generation
    # ------------------------------------------------------------------

    def _generate_planet(
        self, sys_id: str, system_name: str, seq: int, orbital_radius: float
    ) -> CelestialBody:
        subtype = self._pick_planet_subtype(orbital_radius)
        name = self._planet_name(system_name)
        body_id = f"{sys_id}_body_{seq:03d}"

        size = self._planet_size(subtype)
        resources = self._planet_resources(subtype, orbital_radius)
        moons = self._generate_moons(body_id, name, subtype)

        return CelestialBody(
            id=body_id,
            name=name,
            body_type=BodyType.PLANET,
            size=size,
            orbital_radius=round(orbital_radius, 4),
            resources=resources,
            subtype=subtype.value,
            moons=moons,
        )

    def _generate_exoplanet(
        self, sys_id: str, system_name: str, seq: int, orbital_radius: float
    ) -> CelestialBody:
        """
        Exoplanets in this game are rogue / captured planets at extreme orbits.
        They are always cold and mineral-dense.
        """
        ep_index = seq  # sequential label
        name = f"{system_name} EP-{ep_index + 1}"
        body_id = f"{sys_id}_body_{seq:03d}"

        # Exoplanets skew toward ice-giant and super-earth subtypes
        subtype = self.rng.choices(
            [PlanetSubtype.ICE_GIANT, PlanetSubtype.SUPER_EARTH, PlanetSubtype.TERRESTRIAL],
            weights=[50, 30, 20],
        )[0]

        size = self._planet_size(subtype)
        resources = Resource(
            minerals=round(self.rng.uniform(500, 8000), 2),
            rare_minerals=round(self.rng.uniform(50, 1200), 2),
            ice=round(self.rng.uniform(2000, 30000), 2),
            gas=round(self.rng.uniform(100, 8000), 2),
        )
        num_moons = self.rng.randint(0, min(3, self.max_moons))
        moons = [self._generate_moon(body_id, name, i) for i in range(num_moons)]

        return CelestialBody(
            id=body_id,
            name=name,
            body_type=BodyType.EXOPLANET,
            size=size,
            orbital_radius=round(orbital_radius, 4),
            resources=resources,
            subtype=subtype.value,
            moons=moons,
        )

    def _generate_comet(
        self, sys_id: str, system_name: str, seq: int, comet_index: int
    ) -> CelestialBody:
        orbital_radius = self.rng.uniform(5.0, 120.0)
        return CelestialBody(
            id=f"{sys_id}_body_{seq:03d}",
            name=f"{system_name} Comet-{comet_index + 1}",
            body_type=BodyType.COMET,
            size=round(self.rng.uniform(0.001, 0.025), 5),
            orbital_radius=round(orbital_radius, 4),
            resources=Resource(
                minerals=round(self.rng.uniform(10, 250), 2),
                rare_minerals=round(self.rng.uniform(0, 30), 2),
                ice=round(self.rng.uniform(400, 6000), 2),
                gas=round(self.rng.uniform(10, 600), 2),
            ),
            # Comets never have moons
        )

    def _generate_asteroid(
        self,
        sys_id: str,
        system_name: str,
        seq: int,
        orbital_radius: float,
        asteroid_index: int,
    ) -> CelestialBody:
        # Give each asteroid a unique numeric designation within the system
        designation = self.rng.randint(1000, 9999)
        return CelestialBody(
            id=f"{sys_id}_body_{seq:03d}",
            name=f"{system_name} A-{designation}",
            body_type=BodyType.ASTEROID,
            size=round(self.rng.uniform(0.0001, 0.06), 5),
            orbital_radius=round(orbital_radius, 4),
            resources=Resource(
                minerals=round(self.rng.uniform(50, 2500), 2),
                rare_minerals=round(self.rng.uniform(0, 120), 2),
                ice=round(self.rng.uniform(0, 80), 2),
            ),
            # Asteroids never have moons
        )

    # ------------------------------------------------------------------
    # Moon generation
    # ------------------------------------------------------------------

    def _generate_moons(
        self, parent_id: str, parent_name: str, subtype: PlanetSubtype
    ) -> List[Moon]:
        num = self._moon_count(subtype)
        return [self._generate_moon(parent_id, parent_name, i) for i in range(num)]

    def _generate_moon(self, parent_id: str, parent_name: str, index: int) -> Moon:
        label    = _MOON_LABELS[index] if index < len(_MOON_LABELS) else str(index)
        bios_val = round(self.rng.uniform(2, 30), 2) if self.rng.random() < 0.05 else 0.0
        return Moon(
            id=f"{parent_id}_moon_{index}",
            name=f"{parent_name}-{label}",
            size=round(self.rng.uniform(0.005, 0.35), 4),
            resources=Resource(
                minerals=round(self.rng.uniform(80, 3500), 2),
                rare_minerals=round(self.rng.uniform(0, 200), 2),
                ice=round(self.rng.uniform(0, 800), 2),
                gas=round(self.rng.uniform(0, 60), 2),
                bios=bios_val,
            ),
        )

    def _moon_count(self, subtype: PlanetSubtype) -> int:
        """Gas giants get more moons; small rocky worlds get fewer."""
        cap = self.max_moons
        if subtype == PlanetSubtype.GAS_GIANT:
            return self.rng.randint(0, cap)
        if subtype == PlanetSubtype.HOT_JUPITER:
            return self.rng.randint(0, min(4, cap))   # tidal forces limit moons
        if subtype == PlanetSubtype.ICE_GIANT:
            return self.rng.randint(0, max(1, cap // 2))
        if subtype == PlanetSubtype.SUPER_EARTH:
            return self.rng.randint(0, min(3, cap))
        # TERRESTRIAL
        return self.rng.randint(0, min(2, cap))

    # ------------------------------------------------------------------
    # Helper: planet stats
    # ------------------------------------------------------------------

    def _pick_planet_subtype(self, orbital_radius: float) -> PlanetSubtype:
        """
        Subtype probabilities shift with distance from the star:
          - hot_jupiter  dominates very close orbits
          - terrestrial / super_earth peaks in the habitable zone
          - gas_giant / ice_giant dominates beyond the snow line (~3 AU)
        """
        if orbital_radius < 0.5:
            choices = [PlanetSubtype.HOT_JUPITER, PlanetSubtype.TERRESTRIAL, PlanetSubtype.SUPER_EARTH]
            weights = [55, 30, 15]
        elif orbital_radius < 1.5:
            choices = [PlanetSubtype.TERRESTRIAL, PlanetSubtype.SUPER_EARTH, PlanetSubtype.GAS_GIANT, PlanetSubtype.HOT_JUPITER]
            weights = [45, 30, 15, 10]
        elif orbital_radius < 3.0:
            choices = [PlanetSubtype.TERRESTRIAL, PlanetSubtype.SUPER_EARTH, PlanetSubtype.GAS_GIANT, PlanetSubtype.ICE_GIANT]
            weights = [30, 25, 30, 15]
        else:
            choices = [PlanetSubtype.GAS_GIANT, PlanetSubtype.ICE_GIANT, PlanetSubtype.SUPER_EARTH, PlanetSubtype.TERRESTRIAL]
            weights = [40, 40, 12, 8]

        return self.rng.choices(choices, weights=weights, k=1)[0]

    def _planet_size(self, subtype: PlanetSubtype) -> float:
        ranges = {
            PlanetSubtype.TERRESTRIAL:  (0.40, 1.20),
            PlanetSubtype.SUPER_EARTH:  (1.20, 2.50),
            PlanetSubtype.GAS_GIANT:    (3.00, 12.00),
            PlanetSubtype.ICE_GIANT:    (2.00, 5.00),
            PlanetSubtype.HOT_JUPITER:  (8.00, 16.00),
        }
        lo, hi = ranges[subtype]
        return round(self.rng.uniform(lo, hi), 4)

    def _planet_resources(self, subtype: PlanetSubtype, orbital_radius: float) -> Resource:
        cold = orbital_radius > 3.0  # beyond approximate snow line

        if subtype in (PlanetSubtype.GAS_GIANT, PlanetSubtype.HOT_JUPITER):
            return Resource(
                minerals=round(self.rng.uniform(0, 150), 2),
                rare_minerals=round(self.rng.uniform(0, 15), 2),
                ice=round(self.rng.uniform(0, 600) if cold else 0, 2),
                gas=round(self.rng.uniform(50000, 2000000), 2),
            )
        if subtype == PlanetSubtype.ICE_GIANT:
            return Resource(
                minerals=round(self.rng.uniform(100, 1500), 2),
                rare_minerals=round(self.rng.uniform(10, 150), 2),
                ice=round(self.rng.uniform(8000, 80000), 2),
                gas=round(self.rng.uniform(2000, 80000), 2),
            )
        if subtype == PlanetSubtype.SUPER_EARTH:
            bios_val = round(self.rng.uniform(5, 80), 2) if self.rng.random() < 0.15 else 0.0
            return Resource(
                minerals=round(self.rng.uniform(3000, 20000), 2),
                rare_minerals=round(self.rng.uniform(50, 800), 2),
                ice=round(self.rng.uniform(0, 2000) if cold else 0, 2),
                gas=round(self.rng.uniform(0, 500), 2),
                bios=bios_val,
            )
        # TERRESTRIAL — higher bios chance in the habitable zone (0.5–2.5 AU)
        in_hab_zone = 0.5 <= orbital_radius <= 2.5
        bios_chance = 0.40 if in_hab_zone else 0.10
        bios_val    = round(self.rng.uniform(20, 200), 2) if self.rng.random() < bios_chance else 0.0
        return Resource(
            minerals=round(self.rng.uniform(500, 8000), 2),
            rare_minerals=round(self.rng.uniform(5, 300), 2),
            ice=round(self.rng.uniform(0, 800) if cold else 0, 2),
            gas=round(self.rng.uniform(0, 150), 2),
            bios=bios_val,
        )

    # ------------------------------------------------------------------
    # Name generation
    # ------------------------------------------------------------------

    def _system_name(self) -> str:
        prefix = self.rng.choice(_SYSTEM_PREFIXES)
        suffix = self.rng.choice(_SYSTEM_SUFFIXES)
        return f"{prefix} {suffix}"

    def _planet_name(self, system_name: str) -> str:
        numeral = _ROMAN[self._planet_ordinal] if self._planet_ordinal < len(_ROMAN) else str(self._planet_ordinal + 1)
        self._planet_ordinal += 1
        return f"{system_name} {numeral}"
