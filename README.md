# Universal Assemblers

A single-player game where you play as an AI assembling von Neumann machines to colonize space.

## Project Status

Early development — map generation prototype.

## Map Generator

Procedurally generates a galaxy map from a seed. The map captures the full
nested structure of the game world:

```
Galaxy
└── SolarSystem  (N systems)
    ├── Star            — with gas reserves and energy output
    └── CelestialBody[] (K bodies per system)
        ├── Planet      — terrestrial / super-earth / gas giant / ice giant / hot jupiter
        │   └── Moon[]  — up to M moons, each with their own resources
        ├── Exoplanet   — rogue / captured planet at wide orbits; may have moons
        ├── Comet       — ice-rich, high orbital radius
        └── Asteroid    — mineral-dense, inner belt
```

Each object carries a `resources` block:

| Field           | Description                                      |
|-----------------|--------------------------------------------------|
| `minerals`      | Common metal ores — primary construction feed    |
| `rare_minerals` | Exotic compounds — advanced manufacturing        |
| `ice`           | Water ice — propellant, hydrogen, life support   |
| `gas`           | Hydrogen / helium — fuel, atmospheric processing |
| `energy_output` | Continuous flux (stellar luminosity, geothermal) |

Map files are saved as JSON under `maps/`.

## Requirements

- Python 3.8+ (no third-party dependencies)

## Usage

```bash
# Random seed, 10 systems
python main.py

# Reproducible map
python main.py --seed 42

# Larger map with custom parameters
python main.py --seed 1337 --systems 25 --min-bodies 8 --max-bodies 40 --max-moons 12

# Named sector saved to a specific path
python main.py --seed 99 --name "Kepler Expanse" --output saves/sector_1.json
```

### CLI flags

| Flag            | Default          | Description                          |
|-----------------|------------------|--------------------------------------|
| `--seed`        | random           | RNG seed for deterministic maps      |
| `--systems`     | `10`             | Number of solar systems (N)          |
| `--min-bodies`  | `5`              | Min orbital bodies per system        |
| `--max-bodies`  | `25`             | Max orbital bodies per system (K)    |
| `--max-moons`   | `8`              | Max moons per planet                 |
| `--name`        | `Unnamed Sector` | Galaxy / sector display name         |
| `--output`      | auto             | Output JSON path                     |

## Project Structure

```
universal-assemblers/
├── main.py               # CLI entry point
├── src/
│   ├── generator.py      # MapGenerator — all procedural logic
│   └── models/
│       ├── resource.py   # Resource dataclass
│       └── celestial.py  # Moon, CelestialBody, Star, SolarSystem, Galaxy
└── maps/                 # Generated map files (gitignored)
```
