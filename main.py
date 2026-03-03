#!/usr/bin/env python3
"""
Universal Assemblers — Map Generator CLI

Usage examples:

    # Fully random map, 10 systems, saved to maps/
    python main.py

    # Reproducible map from a specific seed
    python main.py --seed 42

    # Larger map with custom parameters
    python main.py --seed 1337 --systems 25 --min-bodies 8 --max-bodies 40 --max-moons 12

    # Save to a specific path
    python main.py --seed 99 --output my_campaign/sector_1.json
"""

import argparse
import os
from datetime import datetime, timezone

from src.generator import MapGenerator


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="universal-assemblers",
        description="Generate a Universal Assemblers galaxy map.",
    )
    p.add_argument(
        "--seed", type=int, default=None,
        help="RNG seed for deterministic generation. Omit for a random seed.",
    )
    p.add_argument(
        "--systems", type=int, default=10, metavar="N",
        help="Number of solar systems to generate (default: 10).",
    )
    p.add_argument(
        "--min-bodies", type=int, default=5, metavar="K_MIN",
        help="Minimum orbital bodies per system (default: 5).",
    )
    p.add_argument(
        "--max-bodies", type=int, default=25, metavar="K_MAX",
        help="Maximum orbital bodies per system (default: 25).",
    )
    p.add_argument(
        "--max-moons", type=int, default=8, metavar="M",
        help="Maximum moons per planet (default: 8).",
    )
    p.add_argument(
        "--name", type=str, default="Unnamed Sector",
        help='Galaxy / sector name (default: "Unnamed Sector").',
    )
    p.add_argument(
        "--output", type=str, default=None,
        help=(
            "Output file path. Defaults to maps/map_<seed>_<timestamp>.json."
        ),
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    gen = MapGenerator(
        seed=args.seed,
        num_solar_systems=args.systems,
        min_bodies_per_system=args.min_bodies,
        max_bodies_per_system=args.max_bodies,
        max_moons_per_planet=args.max_moons,
        galaxy_name=args.name,
    )

    print(f"Generating map...")
    print(f"  Seed         : {gen.seed}")
    print(f"  Solar systems: {gen.num_solar_systems}")
    print(f"  Bodies/system: {gen.min_bodies}–{gen.max_bodies}")
    print(f"  Max moons    : {gen.max_moons}")
    print()

    galaxy = gen.generate()

    # Determine output path
    if args.output is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join("maps", f"map_{gen.seed}_{timestamp}.json")
    else:
        output_path = args.output

    saved_to = MapGenerator.save(galaxy, output_path)

    # Print summary
    print(f"Galaxy: {galaxy.name}")
    print(f"  Solar systems  : {len(galaxy.solar_systems)}")
    print(f"  Orbital bodies : {galaxy.total_bodies}")
    print(f"  Moons          : {galaxy.total_moons}")
    print()

    # Per-system breakdown
    header = f"  {'System':<28} {'Star':>8}  {'Pl':>3} {'EP':>3} {'Co':>3} {'As':>4} {'Mo':>4}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for s in galaxy.solar_systems:
        print(
            f"  {s.name:<28} {s.star.star_type.value:>8}  "
            f"{s.num_planets:>3} {s.num_exoplanets:>3} "
            f"{s.num_comets:>3} {s.num_asteroids:>4} {s.num_moons:>4}"
        )

    print()
    print(f"Map saved to: {saved_to}")


if __name__ == "__main__":
    main()
