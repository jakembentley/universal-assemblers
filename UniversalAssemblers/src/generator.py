"""
Map generator for Universal Assemblers.

Call MapGenerator(seed=...).generate() to produce a Galaxy, then
MapGenerator.save(galaxy, path) to write it to a JSON file.

Seeded determinism: all randomness flows through self.rng (random.Random
initialised with the seed), so the same seed always produces the same map.
"""

from __future__ import annotations

import json
import math
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

# Style A: Classic — "{Greek_letter} {Constellation}"
_GREEK = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta",
    "Iota", "Kappa", "Lambda", "Mu", "Nu", "Xi", "Pi", "Rho", "Sigma",
    "Tau", "Upsilon", "Phi", "Chi", "Psi", "Omega",
]
_CONSTELLATION = [
    "Andromeda", "Aquila", "Ara", "Auriga", "Bootes", "Cancer", "Canis",
    "Carina", "Cassiopeia", "Centauri", "Cepheus", "Corvus", "Cygni",
    "Dorado", "Draconis", "Eridani", "Geminorum", "Herculis", "Hydrae",
    "Leonis", "Lyrae", "Normae", "Ophiuchi", "Orionis", "Pegasi", "Persei",
    "Phoenicis", "Puppis", "Sagittarii", "Scorpii", "Serpentis", "Tauri",
    "Tucanae", "Ursae", "Velorum", "Virginis", "Volantis",
]

# Style B: Catalog — "{Prefix} {number}"
_CATALOG_PREFIXES = [
    "GJ", "HD", "HIP", "KIC", "LHS", "WISE", "Wolf", "Ross", "Lalande", "Gliese",
]

# Style C: Exotic — "{ExoticWord}{optional_suffix}"
_EXOTIC_NAMES = [
    "Aethos", "Borvath", "Caelum", "Dravex", "Elara", "Feraxis", "Galadris",
    "Halveth", "Iketh", "Jorath", "Kethara", "Lacros", "Maedon", "Naevos",
    "Orveth", "Praxi", "Quellar", "Ranoth", "Solvar", "Thalos", "Urrath",
    "Vethis", "Wyrath", "Xanthos", "Zorvan", "Astherion", "Belcara", "Cruxis",
    "Delvara", "Ethren", "Falmis", "Golveth", "Harkon", "Ithrel", "Jethara",
    "Kelvos", "Loreth",
]
_EXOTIC_SUFFIXES = [
    "", "Prime", "Reach", "Deep", "Station", "Nexus", "Expanse", "Rift",
    "Gate", "Verge", "Edge", "Mark",
]

_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
          "XI", "XII", "XIII", "XIV", "XV"]

# Moon name pool
_MOON_POOL = [
    "Io", "Europa", "Ganymede", "Callisto", "Amalthea", "Phobos", "Deimos",
    "Triton", "Nereid", "Proteus", "Titan", "Rhea", "Dione", "Tethys",
    "Enceladus", "Mimas", "Hyperion", "Ariel", "Umbriel", "Titania", "Oberon",
    "Miranda", "Charon", "Nix", "Hydra", "Kerberos", "Aether", "Nemesis",
    "Shade", "Echo", "Veil", "Drift", "Frost", "Shard", "Wraith", "Cinder",
    "Hollow", "Pale", "Ruin", "Trace", "Flux", "Knell", "Mote", "Sable",
    "Thorn", "Umber", "Vast", "Wane", "Yore", "Zephyr",
]


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

# Resource density multipliers
_RES_MULT = {
    "low":    0.4,
    "normal": 1.0,
    "high":   1.6,
    "rich":   2.5,
}

# Bio uplift multipliers
_BIO_MULT = {
    "rare":   0.3,
    "normal": 1.0,
    "common": 2.5,
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
    resource_density : str
        "low" | "normal" | "high" | "rich" — scales all resource amounts.
    bio_uplift_rate : str
        "rare" | "normal" | "common" — scales bios chance and uplift probability.
    body_distribution : str
        "balanced" | "rocky" | "gas_heavy" | "ice_rich" — skews body type weights.
    warp_clusters : int
        Number of isolated warp-only mini-clusters to add.
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
        resource_density: str = "normal",
        bio_uplift_rate: str = "normal",
        body_distribution: str = "balanced",
        warp_clusters: int = 1,
    ) -> None:
        self.seed = seed if seed is not None else random.randint(0, 2**32 - 1)
        self.rng = random.Random(self.seed)

        self.num_solar_systems = num_solar_systems
        self.min_bodies = min_bodies_per_system
        self.max_bodies = max_bodies_per_system
        self.max_moons = max_moons_per_planet
        self.galaxy_name = galaxy_name
        self.galaxy_radius = galaxy_radius_ly
        self.resource_density = resource_density
        self.bio_uplift_rate = bio_uplift_rate
        self.body_distribution = body_distribution
        self.warp_clusters = warp_clusters

        self._res_mult = _RES_MULT.get(resource_density, 1.0)
        self._bio_mult = _BIO_MULT.get(bio_uplift_rate, 1.0)

        # Internal planet/moon state — reset per system/body
        self._planet_ordinal: int = 0
        self._moon_names_used: set = set()
        self._system_style: str = "classic"  # track current system name style

        # Track used system names for uniqueness
        self._used_system_names: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> Galaxy:
        """Generate and return a complete Galaxy object."""
        # Main cluster systems
        main_systems = [
            self._generate_solar_system(i)
            for i in range(self.num_solar_systems)
        ]

        # Warp-only mini-clusters
        warp_systems: List[SolarSystem] = []
        for cluster_idx in range(self.warp_clusters):
            cluster_size = self.rng.randint(2, 4)
            cluster_systems = self._generate_warp_cluster(
                len(main_systems) + len(warp_systems),
                cluster_size,
            )
            warp_systems.extend(cluster_systems)

        all_systems = main_systems + warp_systems

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
                "resource_density": self.resource_density,
                "bio_uplift_rate": self.bio_uplift_rate,
                "body_distribution": self.body_distribution,
                "warp_clusters": self.warp_clusters,
                "bio_uplift_mult": self._bio_mult,
            },
            solar_systems=all_systems,
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
    # Warp cluster generation
    # ------------------------------------------------------------------

    def _generate_warp_cluster(
        self, start_idx: int, cluster_size: int
    ) -> List[SolarSystem]:
        """Generate a mini-cluster of warp-only systems placed far from main cluster."""
        # Pick a random angle and place far out
        angle = self.rng.uniform(0, 2 * math.pi)
        dist_mult = self.rng.uniform(1.5, 2.5)
        cluster_cx = math.cos(angle) * self.galaxy_radius * dist_mult
        cluster_cy = math.sin(angle) * self.galaxy_radius * dist_mult

        systems = []
        for i in range(cluster_size):
            sys_idx = start_idx + i
            sys_id = f"sys_{sys_idx:04d}"

            self._planet_ordinal = 0
            name = self._unique_system_name()

            # Spread within the mini-cluster
            spread = self.galaxy_radius * 0.08
            pos_x = round(cluster_cx + self.rng.uniform(-spread, spread), 2)
            pos_y = round(cluster_cy + self.rng.uniform(-spread, spread), 2)
            position = {"x": pos_x, "y": pos_y}

            star = self._generate_star(sys_id, name)

            total = self.rng.randint(self.min_bodies, self.max_bodies)
            counts = self._split_body_counts(total)
            orbital_bodies: List[CelestialBody] = []
            body_seq = 0

            planet_radii = sorted(
                self.rng.uniform(0.15, 35.0) for _ in range(counts["planets"])
            )
            for radius in planet_radii:
                body = self._generate_planet(sys_id, name, body_seq, radius)
                orbital_bodies.append(body)
                body_seq += 1

            for _ in range(counts["exoplanets"]):
                radius = self.rng.uniform(40.0, 250.0)
                body = self._generate_exoplanet(sys_id, name, body_seq, radius)
                orbital_bodies.append(body)
                body_seq += 1

            for ci in range(counts["comets"]):
                body = self._generate_comet(sys_id, name, body_seq, ci)
                orbital_bodies.append(body)
                body_seq += 1

            for ai in range(counts["asteroids"]):
                radius = self.rng.uniform(1.5, 12.0)
                body = self._generate_asteroid(sys_id, name, body_seq, radius, ai)
                orbital_bodies.append(body)
                body_seq += 1

            systems.append(SolarSystem(
                id=sys_id,
                name=name,
                position=position,
                star=star,
                orbital_bodies=orbital_bodies,
                warp_only=True,
            ))

        return systems

    # ------------------------------------------------------------------
    # Solar-system generation
    # ------------------------------------------------------------------

    def _generate_solar_system(self, sys_index: int) -> SolarSystem:
        self._planet_ordinal = 0  # reset ordinal for planet naming
        sys_id = f"sys_{sys_index:04d}"
        name = self._unique_system_name()

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
        body_distribution affects the fractions.
        """
        dist = self.body_distribution

        if dist == "rocky":
            planet_frac = self.rng.uniform(0.35, 0.50)
        else:
            planet_frac = self.rng.uniform(0.20, 0.40)

        exo_frac = self.rng.uniform(0.00, 0.08)

        if dist == "ice_rich":
            comet_frac = self.rng.uniform(0.20, 0.35)
        else:
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
        self._moon_names_used = set()
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

        # ice_rich distribution: extra ice multiplier
        ice_mult = 2.0 if self.body_distribution == "ice_rich" else 1.0
        resources = Resource(
            minerals=round(self.rng.uniform(500, 8000) * self._res_mult, 2),
            rare_minerals=round(self.rng.uniform(50, 1200) * self._res_mult, 2),
            ice=round(self.rng.uniform(2000, 30000) * self._res_mult * ice_mult, 2),
            gas=round(self.rng.uniform(100, 8000) * self._res_mult, 2),
        )
        num_moons = self.rng.randint(0, min(3, self.max_moons))
        self._moon_names_used = set()
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
        ice_mult = 2.0 if self.body_distribution == "ice_rich" else 1.0
        return CelestialBody(
            id=f"{sys_id}_body_{seq:03d}",
            name=self._asteroid_name(system_name),
            body_type=BodyType.COMET,
            size=round(self.rng.uniform(0.001, 0.025), 5),
            orbital_radius=round(orbital_radius, 4),
            resources=Resource(
                minerals=round(self.rng.uniform(10, 250) * self._res_mult, 2),
                rare_minerals=round(self.rng.uniform(0, 30) * self._res_mult, 2),
                ice=round(self.rng.uniform(400, 6000) * self._res_mult * ice_mult, 2),
                gas=round(self.rng.uniform(10, 600) * self._res_mult, 2),
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
        return CelestialBody(
            id=f"{sys_id}_body_{seq:03d}",
            name=self._asteroid_name(system_name),
            body_type=BodyType.ASTEROID,
            size=round(self.rng.uniform(0.0001, 0.06), 5),
            orbital_radius=round(orbital_radius, 4),
            resources=Resource(
                minerals=round(self.rng.uniform(50, 2500) * self._res_mult, 2),
                rare_minerals=round(self.rng.uniform(0, 120) * self._res_mult, 2),
                ice=round(self.rng.uniform(0, 80) * self._res_mult, 2),
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
        moon_name = self._pick_moon_name(parent_name)
        bios_chance = 0.05 * self._bio_mult
        bios_val = round(self.rng.uniform(2, 30) * self._res_mult, 2) if self.rng.random() < bios_chance else 0.0
        ice_mult = 2.0 if self.body_distribution == "ice_rich" else 1.0
        return Moon(
            id=f"{parent_id}_moon_{index}",
            name=moon_name,
            size=round(self.rng.uniform(0.005, 0.35), 4),
            resources=Resource(
                minerals=round(self.rng.uniform(80, 3500) * self._res_mult, 2),
                rare_minerals=round(self.rng.uniform(0, 200) * self._res_mult, 2),
                ice=round(self.rng.uniform(0, 800) * self._res_mult * ice_mult, 2),
                gas=round(self.rng.uniform(0, 60) * self._res_mult, 2),
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
        Subtype probabilities shift with distance from the star.
        body_distribution further adjusts the weights.
        """
        dist = self.body_distribution

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

        # Apply distribution modifiers
        if dist == "rocky":
            # Skew towards terrestrial/super_earth
            new_weights = []
            for c, w in zip(choices, weights):
                if c in (PlanetSubtype.TERRESTRIAL, PlanetSubtype.SUPER_EARTH):
                    new_weights.append(int(w * 1.8))
                else:
                    new_weights.append(w)
            weights = new_weights
        elif dist == "gas_heavy":
            # Gas giant / hot_jupiter weights ×1.5
            new_weights = []
            for c, w in zip(choices, weights):
                if c in (PlanetSubtype.GAS_GIANT, PlanetSubtype.HOT_JUPITER):
                    new_weights.append(int(w * 1.5))
                else:
                    new_weights.append(w)
            weights = new_weights
        elif dist == "ice_rich":
            # Ice giant weight ×2
            new_weights = []
            for c, w in zip(choices, weights):
                if c == PlanetSubtype.ICE_GIANT:
                    new_weights.append(int(w * 2))
                else:
                    new_weights.append(w)
            weights = new_weights

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
        ice_mult = 2.0 if self.body_distribution == "ice_rich" else 1.0
        rm = self._res_mult
        bm = self._bio_mult

        if subtype in (PlanetSubtype.GAS_GIANT, PlanetSubtype.HOT_JUPITER):
            return Resource(
                minerals=round(self.rng.uniform(0, 150) * rm, 2),
                rare_minerals=round(self.rng.uniform(0, 15) * rm, 2),
                ice=round((self.rng.uniform(0, 600) if cold else 0) * rm * ice_mult, 2),
                gas=round(self.rng.uniform(50000, 2000000) * rm, 2),
            )
        if subtype == PlanetSubtype.ICE_GIANT:
            return Resource(
                minerals=round(self.rng.uniform(100, 1500) * rm, 2),
                rare_minerals=round(self.rng.uniform(10, 150) * rm, 2),
                ice=round(self.rng.uniform(8000, 80000) * rm * ice_mult, 2),
                gas=round(self.rng.uniform(2000, 80000) * rm, 2),
            )
        if subtype == PlanetSubtype.SUPER_EARTH:
            bios_chance = 0.15 * bm
            bios_val = round(self.rng.uniform(5, 80) * rm, 2) if self.rng.random() < bios_chance else 0.0
            return Resource(
                minerals=round(self.rng.uniform(3000, 20000) * rm, 2),
                rare_minerals=round(self.rng.uniform(50, 800) * rm, 2),
                ice=round((self.rng.uniform(0, 2000) if cold else 0) * rm * ice_mult, 2),
                gas=round(self.rng.uniform(0, 500) * rm, 2),
                bios=bios_val,
            )
        # TERRESTRIAL — higher bios chance in the habitable zone (0.5–2.5 AU)
        in_hab_zone = 0.5 <= orbital_radius <= 2.5
        bios_chance = (0.40 if in_hab_zone else 0.10) * bm
        bios_chance = min(bios_chance, 1.0)
        bios_val = round(self.rng.uniform(20, 200) * rm, 2) if self.rng.random() < bios_chance else 0.0
        return Resource(
            minerals=round(self.rng.uniform(500, 8000) * rm, 2),
            rare_minerals=round(self.rng.uniform(5, 300) * rm, 2),
            ice=round((self.rng.uniform(0, 800) if cold else 0) * rm * ice_mult, 2),
            gas=round(self.rng.uniform(0, 150) * rm, 2),
            bios=bios_val,
        )

    # ------------------------------------------------------------------
    # Name generation
    # ------------------------------------------------------------------

    def _unique_system_name(self) -> str:
        """Generate a unique system name, retrying on collision."""
        for _ in range(20):
            name = self._system_name()
            if name not in self._used_system_names:
                self._used_system_names.add(name)
                return name
        # Fallback: append a number
        base = self._system_name()
        n = 2
        candidate = f"{base}-{n}"
        while candidate in self._used_system_names:
            n += 1
            candidate = f"{base}-{n}"
        self._used_system_names.add(candidate)
        return candidate

    def _system_name(self) -> str:
        style = self.rng.choices(["classic", "catalog", "exotic"], weights=[35, 30, 35])[0]
        self._system_style = style
        if style == "classic":
            greek = self.rng.choice(_GREEK)
            const = self.rng.choice(_CONSTELLATION)
            return f"{greek} {const}"
        elif style == "catalog":
            prefix = self.rng.choice(_CATALOG_PREFIXES)
            number = self.rng.randint(100, 9999)
            return f"{prefix} {number}"
        else:  # exotic
            word = self.rng.choice(_EXOTIC_NAMES)
            suffix = self.rng.choice(_EXOTIC_SUFFIXES)
            return f"{word}{(' ' + suffix) if suffix else ''}"

    def _planet_name(self, system_name: str) -> str:
        """Name a planet based on the current system's naming style."""
        ordinal = self._planet_ordinal
        self._planet_ordinal += 1

        if self._system_style == "catalog":
            # Use lowercase letter for catalog systems
            letters = "bcdefghijklmnopqrstuvwxyz"
            letter = letters[ordinal] if ordinal < len(letters) else str(ordinal + 1)
            # Space for word-based prefixes (Wolf, Ross, Lalande, Gliese),
            # no space for short code prefixes (GJ, HD, HIP, KIC, LHS, WISE)
            parts = system_name.split()
            if len(parts) >= 1 and len(parts[0]) <= 4 and parts[0].isupper():
                return f"{system_name}{letter}"
            else:
                return f"{system_name} {letter}"
        else:
            # Roman numeral for classic and exotic
            numeral = _ROMAN[ordinal] if ordinal < len(_ROMAN) else str(ordinal + 1)
            return f"{system_name} {numeral}"

    def _asteroid_name(self, system_name: str) -> str:
        """Real-style asteroid designation: '(year) Lnnn'"""
        year = self.rng.randint(2140, 2480)
        letter = chr(self.rng.randint(ord('A'), ord('Z')))
        number = self.rng.randint(1, 999)
        return f"({year}) {letter}{number:03d}"

    def _pick_moon_name(self, parent_name: str) -> str:
        """Pick a unique moon name from the pool (per parent body)."""
        available = [n for n in _MOON_POOL if n not in self._moon_names_used]
        if available:
            name = self.rng.choice(available)
            self._moon_names_used.add(name)
            return name
        # Pool exhausted — fall back to parent abbreviation + letter
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        idx = len(self._moon_names_used) - len(_MOON_POOL)
        letter = letters[idx % len(letters)]
        # Abbreviate parent name
        words = parent_name.split()
        abbrev = words[-1][:3].upper() if words else "UNK"
        return f"{abbrev}-{letter}"
