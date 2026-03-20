"""
Universal Assemblers — Headless Simulation Playtest.

Pure Python, zero pygame/SDL. Runs SimulationEngine.tick() for N ticks,
checks invariants each tick, and writes a structured JSON report.

Usage (from UniversalAssemblers/):
    ~/anaconda3/python.exe scripts/sim_playtest.py
    ~/anaconda3/python.exe scripts/sim_playtest.py --seed 42 --systems 10 --ticks 200
    ~/anaconda3/python.exe scripts/sim_playtest.py --out playtest_output/my_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from collections import defaultdict

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR   = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_DIR)
os.chdir(REPO_DIR)

from src.generator import MapGenerator      # noqa: E402
from src.game_state import GameState        # noqa: E402
from src.simulation import SimulationEngine # noqa: E402


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Headless simulation playtest")
    p.add_argument("--seed",    type=int,   default=42,    help="Galaxy seed")
    p.add_argument("--systems", type=int,   default=10,    help="Number of solar systems")
    p.add_argument("--ticks",   type=int,   default=200,   help="Simulation ticks to run")
    p.add_argument("--dt",      type=float, default=0.05,  help="dt per tick in game-years")
    p.add_argument("--out",     type=str,   default=None,  help="Output JSON path")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Report state
# ---------------------------------------------------------------------------

invariant_violations: list[dict] = []
events_by_type:       dict[str, int] = defaultdict(int)
notable_events:       list[dict] = []
missing_mechanics:    list[str] = []


def record_violation(tick: int, rule: str, **kwargs) -> None:
    entry = {"tick": tick, "rule": rule, **kwargs}
    invariant_violations.append(entry)
    print(f"  [VIOLATION] tick={tick} rule={rule} {kwargs}")


# ---------------------------------------------------------------------------
# Invariant checker
# ---------------------------------------------------------------------------

def _all_bodies(gs: GameState):
    """Yield every body (planet, moon) in the galaxy."""
    if not gs.galaxy:
        return
    for sys in gs.galaxy.solar_systems:
        for body in sys.orbital_bodies:
            yield body
            for moon in body.moons:
                yield moon


def _all_body_ids(gs: GameState) -> set[str]:
    return {b.id for b in _all_bodies(gs)}


def check_invariants(gs: GameState, tick: int, events: list) -> None:
    valid_body_ids = _all_body_ids(gs)
    valid_system_ids = {s.id for s in gs.galaxy.solar_systems} if gs.galaxy else set()

    # 1. No resource amount < 0 on any body
    for body in _all_bodies(gs):
        r = body.resources
        for attr in ("minerals", "rare_minerals", "ice", "gas", "bios",
                     "electronics", "alloys", "fuel_cells"):
            val = getattr(r, attr, 0.0)
            if val < -1e-6:
                record_violation(tick, "resource_negative",
                                 body_id=body.id, resource=attr, value=round(val, 4))

    # 2. No entity count < 0 in entity_roster
    for inst in gs.entity_roster.all():
        if inst.count < 0:
            record_violation(tick, "entity_count_negative",
                             category=inst.category, type_value=inst.type_value,
                             location_id=inst.location_id, count=inst.count)

    # 3. Ship orders progress in [0.0, 1.0]
    for loc_id, ship_type in gs.order_queue.all_keys():
        for order in gs.order_queue.get_all(loc_id, ship_type):
            if not (0.0 <= order.progress <= 1.0 + 1e-6):
                record_violation(tick, "ship_progress_out_of_range",
                                 location_id=loc_id, ship_type=ship_type,
                                 progress=round(order.progress, 4))

    # 4. Bio populations ≥ 0
    for pop in gs.bio_state.all():
        if pop.population < 0:
            record_violation(tick, "bio_population_negative",
                             body_id=pop.body_id, population=round(pop.population, 4))

    # 5. Tech progress fractions in [0.0, 1.0]
    for node_id in gs.tech.in_progress_ids():
        progress = gs.tech.progress_fraction(node_id)
        if not (0.0 <= progress <= 1.0 + 1e-6):
            record_violation(tick, "tech_progress_out_of_range",
                             node_id=node_id, progress=round(progress, 4))

    # 6. Events reference valid body/system IDs
    for evt in events:
        for key in ("body_id", "location_id"):
            val = evt.get(key)
            if val and val not in valid_body_ids and val not in valid_system_ids:
                record_violation(tick, "event_invalid_id",
                                 event_type=evt.get("type"), key=key, value=val)
        for key in ("system_id",):
            val = evt.get(key)
            if val and val not in valid_system_ids:
                record_violation(tick, "event_invalid_system_id",
                                 event_type=evt.get("type"), key=key, value=val)


# ---------------------------------------------------------------------------
# Final state snapshot
# ---------------------------------------------------------------------------

def build_final_state(gs: GameState, ticks: int, dt: float) -> dict:
    entities: dict[str, dict[str, int]] = {}
    for inst in gs.entity_roster.all():
        cat = entities.setdefault(inst.category, {})
        cat[inst.type_value] = cat.get(inst.type_value, 0) + inst.count

    return {
        "game_years":         round(gs.in_game_years, 4),
        "entities":           entities,
        "tech_researched":    list(gs.tech.researched),
        "systems_discovered": sum(
            1 for s in gs.galaxy.solar_systems
            if gs.get_state(s.id).value != "unknown"
        ) if gs.galaxy else 0,
        "bio_populations":    len(gs.bio_state.all()),
    }


# ---------------------------------------------------------------------------
# Missing-mechanics heuristics
# ---------------------------------------------------------------------------

def check_missing_mechanics(gs: GameState, seen_event_types: set[str], ticks: int) -> None:
    # Miners present but no vein_discovery events
    miner_count = (
        gs.entity_roster.total("bot", "miner") +
        gs.entity_roster.total("ship", "mining_vessel")
    )
    if miner_count > 0 and "vein_discovery" not in seen_event_types:
        missing_mechanics.append("no vein_discovery despite miners/mining_vessels present")

    # Bio populations present for long enough but no bios_mutation events
    if len(gs.bio_state.all()) > 0 and ticks >= 50 and "bios_mutation" not in seen_event_types:
        missing_mechanics.append("no bios_mutation after 50+ ticks with bio populations present")

    # Victory check: if all tech prereqs for a win condition could be met
    # but no victory event — note it as a potential gap (soft flag only)
    if "victory" not in seen_event_types:
        missing_mechanics.append("no victory event after full run (may be expected if prerequisites unmet)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    out_dir = os.path.join(REPO_DIR, "playtest_output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = args.out or os.path.join(out_dir, "sim_report.json")

    print("=" * 60)
    print("  Universal Assemblers — Headless Sim Playtest")
    print(f"  seed={args.seed}  systems={args.systems}  ticks={args.ticks}  dt={args.dt}")
    print("=" * 60)

    # Build galaxy + game state
    print("\n[setup] Generating galaxy…")
    gen = MapGenerator(seed=args.seed, num_solar_systems=args.systems)
    galaxy = gen.generate()
    gs  = GameState.new_game(galaxy)
    engine = gs.sim_engine   # already initialised by new_game()
    print(f"  Systems: {len(galaxy.solar_systems)}")
    print(f"  Bio pops: {len(gs.bio_state.all())}")

    seen_event_types: set[str] = set()

    print(f"\n[run] Ticking {args.ticks} × dt={args.dt} yr…")
    for tick in range(args.ticks):
        gs.tick(args.dt)
        events = gs.pop_sim_events()

        for evt in events:
            t = evt.get("type", "unknown")
            events_by_type[t] += 1
            seen_event_types.add(t)
            # Notable: rare or significant events
            if t in ("victory", "bios_extinction", "bios_uplift", "system_discovered"):
                notable_events.append({"tick": tick, **evt})

        check_invariants(gs, tick, events)

        if (tick + 1) % 50 == 0:
            print(f"  tick {tick + 1}/{args.ticks}  game_yr={gs.in_game_years:.2f}"
                  f"  violations={len(invariant_violations)}")

    check_missing_mechanics(gs, seen_event_types, args.ticks)
    final_state = build_final_state(gs, args.ticks, args.dt)

    # Compose report
    report = {
        "run": {
            "seed":       args.seed,
            "systems":    args.systems,
            "ticks":      args.ticks,
            "dt":         args.dt,
            "game_years": round(args.ticks * args.dt, 4),
        },
        "invariant_violations": invariant_violations,
        "events_summary": {
            "by_type": dict(events_by_type),
            "total":   sum(events_by_type.values()),
        },
        "notable_events":   notable_events,
        "missing_mechanics": missing_mechanics,
        "final_state":      final_state,
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    # Summary
    print("\n" + "=" * 60)
    viol_count = len(invariant_violations)
    print(f"  Invariant violations : {viol_count}")
    print(f"  Event types seen     : {sorted(seen_event_types)}")
    print(f"  Missing mechanics    : {len(missing_mechanics)}")
    print(f"  Game years simulated : {final_state['game_years']:.2f}")
    print(f"  Report               : {out_path}")
    print("=" * 60)

    return 0 if viol_count == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
