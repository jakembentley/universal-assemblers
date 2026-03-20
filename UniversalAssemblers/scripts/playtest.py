"""
Universal Assemblers — Automated Playtest Driver.

Drives the game through key states programmatically, takes screenshots at each
step, runs compliance checks against GAME_DESIGN.md, and writes a JSON report.

Usage (from UniversalAssemblers/):
    ~/anaconda3/python.exe scripts/playtest.py
    ~/anaconda3/python.exe scripts/playtest.py --offscreen   # headless / CI
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

# ---------------------------------------------------------------------------
# SDL driver setup — must happen before any pygame import
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Universal Assemblers playtest driver")
parser.add_argument("--offscreen", action="store_true",
                    help="Use SDL offscreen driver (no window; headless/CI)")
args, _ = parser.parse_known_args()

if args.offscreen:
    os.environ["SDL_VIDEODRIVER"] = "offscreen"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR   = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_DIR)
os.chdir(REPO_DIR)   # ensure relative paths (maps/, etc.) resolve correctly

# ---------------------------------------------------------------------------
# Imports (after path + SDL env setup)
# ---------------------------------------------------------------------------
import pygame  # noqa: E402

from src.gui.app import App  # noqa: E402
from src.models.tech import TECH_TREE  # noqa: E402
from src.models.entity import (  # noqa: E402
    STARTING_ENTITIES, StructureType, BotType, ShipType,
    MegastructureType, BioType, POWER_PLANT_SPECS,
)
from src.game_state import DiscoveryState  # noqa: E402

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(REPO_DIR, "playtest_output")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Report accumulators
# ---------------------------------------------------------------------------
screenshots: list[dict] = []
checks:      list[dict] = []
failures:    list[dict] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def render_frame(app: App) -> None:
    """Render one complete frame of the current app state to app.screen."""
    app.screen.fill((8, 8, 20))

    if app.state == "menu":
        app.main_menu.draw(app.screen)

    elif app.state == "new_game_settings":
        app.new_game_panel.draw(app.screen)

    elif app.state == "galaxy" and app.galaxy_view:
        app.galaxy_view.draw(app.screen)
        app.game_clock.draw(app.screen)

    elif app.state == "system" and app.game_view:
        app.game_view.draw(app.screen)
        app.game_clock.draw(app.screen)
        # Overlays (same order as App.run)
        if app.tech_view.is_active:
            app.tech_view.draw(app.screen)
        if app.energy_view.is_active:
            app.energy_view.draw(app.screen)
        if app.queue_view.is_active:
            app.queue_view.draw(app.screen)
        if app.entity_view.is_active:
            app.entity_view.draw(app.screen)

    pygame.display.flip()


def take_screenshot(app: App, slug: str, label: str) -> str:
    """Render a frame, save it as PNG, record in the screenshots list."""
    render_frame(app)
    path = os.path.join(OUT_DIR, f"{slug}.png")
    pygame.image.save(app.screen, path)
    screenshots.append({"name": slug, "path": path, "label": label})
    print(f"  [screenshot] {slug}.png — {label}")
    return path


def check(name: str, passed: bool, detail: str = "") -> None:
    """Record a boolean compliance check."""
    entry = {"check": name, "passed": passed, "detail": detail}
    checks.append(entry)
    if not passed:
        failures.append(entry)
    status = "PASS" if passed else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"  [{status}] {name}{suffix}")


# ---------------------------------------------------------------------------
# Main playtest sequence
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("  Universal Assemblers — Automated Playtest")
    print("=" * 60)

    app = App()

    # -----------------------------------------------------------------------
    # 1. Main menu
    # -----------------------------------------------------------------------
    print("\n[1] Main Menu")
    check("state_is_menu",    app.state == "menu",         f"state={app.state}")
    check("main_menu_exists", app.main_menu is not None)
    take_screenshot(app, "01_main_menu", "Main Menu")

    # -----------------------------------------------------------------------
    # 2. Launch game
    # -----------------------------------------------------------------------
    print("\n[2] Launching New Game")
    settings = {
        "num_solar_systems":  8,
        "galaxy_name":        "Playtest Sector",
        "resource_density":   "normal",
        "bio_uplift_rate":    "normal",
        "body_distribution":  "balanced",
        "warp_clusters":      1,
    }
    app.launch_game(settings)
    check("state_is_galaxy",      app.state == "galaxy",     f"state={app.state}")
    check("galaxy_exists",        app.galaxy is not None)
    check("game_state_exists",    app.game_state is not None)
    if app.galaxy:
        n = len(app.galaxy.solar_systems)
        check("galaxy_has_systems", n > 0, f"count={n}")
    take_screenshot(app, "02_galaxy_view", "Galaxy View")

    # -----------------------------------------------------------------------
    # 3. Starting entity roster (spec from §5 of GAME_DESIGN.md)
    # -----------------------------------------------------------------------
    print("\n[3] Starting Entity Roster (GAME_DESIGN §5)")
    gs = app.game_state
    check("starting_extractor",       gs.entity_roster.total("structure", "extractor")           >= 1)
    check("starting_factory",         gs.entity_roster.total("structure", "factory")             == 1)
    check("starting_solar_plant",     gs.entity_roster.total("structure", "power_plant_solar")   >= 1)
    check("starting_research_array",  gs.entity_roster.total("structure", "research_array")      == 1)
    check("starting_probe",           gs.entity_roster.total("ship",      "probe")               == 1)
    check("starting_drop_ship",       gs.entity_roster.total("ship",      "drop_ship")           == 1)
    check("starting_mining_vessel",   gs.entity_roster.total("ship",      "mining_vessel")       == 1)

    # -----------------------------------------------------------------------
    # 4. Tech tree completeness (spec from §3 of GAME_DESIGN.md)
    # -----------------------------------------------------------------------
    print("\n[4] Tech Tree (GAME_DESIGN §3)")
    check("tech_tree_min_13_nodes",        len(TECH_TREE) >= 13,                  f"nodes={len(TECH_TREE)}")
    check("tech_structure_modules",        "structure_modules"        in TECH_TREE)
    check("tech_orbital_power",            "orbital_power"            in TECH_TREE)
    check("tech_multi_component",          "multi_component_structures" in TECH_TREE)
    check("tech_refinery_efficiency",      "refinery_efficiency"      in TECH_TREE)
    check("tech_self_replication",         "self_replication"         in TECH_TREE)
    check("tech_cold_fusion",              "cold_fusion"              in TECH_TREE)
    check("tech_dark_matter",              "dark_matter"              in TECH_TREE)
    check("tech_swarm_bots",               "swarm_bots"               in TECH_TREE)
    check("tech_atomic_warships",          "atomic_warships"          in TECH_TREE)
    check("tech_doom_machine",             "doom_machine"             in TECH_TREE)
    check("tech_solar_sails",              "solar_sails"              in TECH_TREE)
    check("tech_space_folding",            "space_folding"            in TECH_TREE)
    check("tech_wormhole_drive",           "wormhole_drive"           in TECH_TREE)

    # Prerequisite wiring spot-checks
    swarm_node  = TECH_TREE.get("swarm_bots")
    doom_node   = TECH_TREE.get("doom_machine")
    dm_node     = TECH_TREE.get("dark_matter")
    check("swarm_bots_prereqs_correct",
          swarm_node is not None and
          "multi_component_structures" in (swarm_node.prerequisites or []) and
          "self_replication"           in (swarm_node.prerequisites or []),
          str(getattr(swarm_node, "prerequisites", None)))
    check("doom_machine_prereqs_correct",
          doom_node is not None and
          "atomic_warships" in (doom_node.prerequisites or []) and
          "swarm_bots"      in (doom_node.prerequisites or []),
          str(getattr(doom_node, "prerequisites", None)))
    check("dark_matter_prereqs_correct",
          dm_node is not None and
          "cold_fusion"   in (dm_node.prerequisites or []) and
          "space_folding" in (dm_node.prerequisites or []),
          str(getattr(dm_node, "prerequisites", None)))

    # -----------------------------------------------------------------------
    # 5. Power plant specs — renewable vs finite (GAME_DESIGN §1 Resources)
    # -----------------------------------------------------------------------
    print("\n[5] Power Plant Specs (GAME_DESIGN §2.1)")
    RENEWABLE_TYPES = {
        StructureType.POWER_PLANT_SOLAR,
        StructureType.POWER_PLANT_WIND,
        StructureType.POWER_PLANT_BIOS,
        StructureType.POWER_PLANT_DARK_MATTER,
    }
    FINITE_TYPES = {
        StructureType.POWER_PLANT_FOSSIL,
        StructureType.POWER_PLANT_NUCLEAR,
        StructureType.POWER_PLANT_COLD_FUSION,
    }
    for st in RENEWABLE_TYPES:
        spec = POWER_PLANT_SPECS.get(st)
        check(f"renewable_{st.value}", spec is not None and spec.renewable is True,
              f"spec={spec}")
    for st in FINITE_TYPES:
        spec = POWER_PLANT_SPECS.get(st)
        check(f"finite_{st.value}", spec is not None and spec.renewable is False,
              f"spec={spec}")

    # -----------------------------------------------------------------------
    # 6. Entity type enums (GAME_DESIGN §2)
    # -----------------------------------------------------------------------
    print("\n[6] Entity Type Enums (GAME_DESIGN §2)")
    # Megastructures
    check("mega_dyson_sphere",    hasattr(MegastructureType, "DYSON_SPHERE"))
    check("mega_space_elevator",  hasattr(MegastructureType, "SPACE_ELEVATOR"))
    check("mega_disc_world",      hasattr(MegastructureType, "DISC_WORLD"))
    check("mega_halogate",        hasattr(MegastructureType, "HALOGATE"))
    check("mega_doom_machine",    hasattr(MegastructureType, "DOOM_MACHINE"))
    # Ships
    check("ship_probe",           hasattr(ShipType, "PROBE"))
    check("ship_drop_ship",       hasattr(ShipType, "DROP_SHIP"))
    check("ship_mining_vessel",   hasattr(ShipType, "MINING_VESSEL"))
    check("ship_transport",       hasattr(ShipType, "TRANSPORT"))
    check("ship_warship",         hasattr(ShipType, "WARSHIP"))
    # Bots
    check("bot_constructor",      hasattr(BotType, "CONSTRUCTOR"))
    check("bot_harvester",        hasattr(BotType, "HARVESTER"))
    check("bot_miner",            hasattr(BotType, "MINER"))
    # Bios
    check("bio_primitive",        hasattr(BioType, "PRIMITIVE"))
    check("bio_uplifted",         hasattr(BioType, "UPLIFTED"))

    # -----------------------------------------------------------------------
    # 7. Discovery / fog-of-war
    # -----------------------------------------------------------------------
    print("\n[7] Discovery States (GAME_DESIGN §4)")
    if app.galaxy:
        home_sys = app.galaxy.solar_systems[0]
        disc = gs.get_state(home_sys.id)
        check("home_system_colonized", disc == DiscoveryState.COLONIZED,
              f"state={disc}")
        non_home = [s for s in app.galaxy.solar_systems if s.id != home_sys.id]
        if non_home:
            other_disc = gs.get_state(non_home[0].id)
            check("other_system_not_colonized",
                  other_disc != DiscoveryState.COLONIZED,
                  f"state={other_disc}")

    # -----------------------------------------------------------------------
    # 8. Enter home system → system view
    # -----------------------------------------------------------------------
    print("\n[8] System View (GAME_DESIGN §4 GUI)")
    if app.galaxy:
        home_id = app.galaxy.solar_systems[0].id
        app.enter_system(home_id)
        check("state_is_system", app.state == "system", f"state={app.state}")
        check("game_view_created", app.game_view is not None)
        take_screenshot(app, "03_system_view", "System View — Home System")

    # -----------------------------------------------------------------------
    # 9. Tech tree overlay
    # -----------------------------------------------------------------------
    print("\n[9] Tech Tree Overlay (GAME_DESIGN §4 GUI)")
    app.open_tech_view()
    check("tech_view_active",                    app.tech_view.is_active)
    check("entity_view_off_when_tech_active",    not app.entity_view.is_active)
    check("energy_view_off_when_tech_active",    not app.energy_view.is_active)
    check("queue_view_off_when_tech_active",     not app.queue_view.is_active)
    take_screenshot(app, "04_tech_view", "Tech Tree Overlay")
    app.close_tech_view()

    # -----------------------------------------------------------------------
    # 10. Energy overview overlay
    # -----------------------------------------------------------------------
    print("\n[10] Energy Overview Overlay")
    app.open_energy_view()
    check("energy_view_active",                  app.energy_view.is_active)
    check("tech_view_off_when_energy_active",     not app.tech_view.is_active)
    take_screenshot(app, "05_energy_view", "Energy Overview")
    app.close_energy_view()

    # -----------------------------------------------------------------------
    # 11. Queue overlay
    # -----------------------------------------------------------------------
    print("\n[11] Task Queue Overlay")
    app.open_queue_view()
    check("queue_view_active",                   app.queue_view.is_active)
    check("energy_view_off_when_queue_active",   not app.energy_view.is_active)
    take_screenshot(app, "06_queue_view", "Task Queue Overlay")
    app.close_queue_view()

    # -----------------------------------------------------------------------
    # 12. Entity view — structures
    # -----------------------------------------------------------------------
    print("\n[12] Entity View — Structures (GAME_DESIGN §4 GUI)")
    if app.game_state and app.galaxy:
        home = app.galaxy.solar_systems[0]
        # Find the body where the factory is
        home_body_id: str | None = None
        for inst in app.game_state.entity_roster._instances:
            if inst.type_value == "factory":
                home_body_id = inst.location_id
                break
        if home_body_id:
            app.open_entity_view("structure", "factory",
                                 system_id=home.id, body_id=home_body_id)
            check("entity_view_active_structure",            app.entity_view.is_active)
            check("tech_view_off_when_entity_active",        not app.tech_view.is_active)
            take_screenshot(app, "07_entity_view_factory", "Entity View — Factory")
            app.close_entity_view()

            # Solar power plant
            app.open_entity_view("structure", "power_plant_solar",
                                 system_id=home.id, body_id=home_body_id)
            check("entity_view_active_solar_plant",          app.entity_view.is_active)
            take_screenshot(app, "08_entity_view_solar", "Entity View — Solar Power Plant")
            app.close_entity_view()

            # Research array
            app.open_entity_view("structure", "research_array",
                                 system_id=home.id, body_id=home_body_id)
            take_screenshot(app, "09_entity_view_research", "Entity View — Research Array")
            app.close_entity_view()

    # -----------------------------------------------------------------------
    # 13. Entity view — ship
    # -----------------------------------------------------------------------
    print("\n[13] Entity View — Ships")
    if app.game_state and app.galaxy:
        home = app.galaxy.solar_systems[0]
        probe_loc: str | None = None
        for inst in app.game_state.entity_roster._instances:
            if inst.type_value == "probe":
                probe_loc = inst.location_id
                break
        if probe_loc:
            app.open_entity_view("ship", "probe",
                                 system_id=home.id, body_id=probe_loc)
            check("entity_view_active_ship",                 app.entity_view.is_active)
            take_screenshot(app, "10_entity_view_probe", "Entity View — Probe")
            app.close_entity_view()

    # -----------------------------------------------------------------------
    # 14. Overlay mutual-exclusion invariant
    # -----------------------------------------------------------------------
    print("\n[14] Overlay Mutual-Exclusion Invariant")
    app.open_tech_view()
    check("only_tech_active_1",    app.tech_view.is_active)
    check("energy_inactive_1",     not app.energy_view.is_active)
    app.open_energy_view()
    check("energy_active_after",   app.energy_view.is_active,  "energy should be active")
    check("tech_inactive_after",   not app.tech_view.is_active, "tech should be deactivated")
    app.open_queue_view()
    check("queue_active_after",    app.queue_view.is_active)
    check("energy_inactive_2",     not app.energy_view.is_active)
    app.close_queue_view()
    check("all_overlays_closed",
          not (app.tech_view.is_active or app.energy_view.is_active
               or app.queue_view.is_active or app.entity_view.is_active))

    # -----------------------------------------------------------------------
    # 15. TechState initial conditions
    # -----------------------------------------------------------------------
    print("\n[15] TechState Initial Conditions")
    tech_state = app.game_state.tech
    check("tech_state_exists",         tech_state is not None)
    check("nothing_researched_at_start",
          len(tech_state.researched) == 0,
          f"researched={tech_state.researched}")

    # -----------------------------------------------------------------------
    # Cleanup + report
    # -----------------------------------------------------------------------
    pygame.quit()

    passed = sum(1 for c in checks if c["passed"])
    total  = len(checks)
    report = {
        "summary": {
            "total_checks": total,
            "passed":       passed,
            "failed":       total - passed,
            "pass_rate":    f"{100 * passed // total}%" if total else "0%",
        },
        "screenshots": screenshots,
        "checks":      checks,
        "failures":    failures,
    }
    report_path = os.path.join(OUT_DIR, "playtest_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{total} checks passed  ({report['summary']['pass_rate']})")
    if failures:
        print(f"  Failures ({len(failures)}):")
        for f_entry in failures:
            print(f"    ✗ {f_entry['check']}: {f_entry['detail']}")
    print(f"  Screenshots : {OUT_DIR}/")
    print(f"  Report      : {report_path}")
    print("=" * 60)

    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        try:
            pygame.quit()
        except Exception:
            pass
        sys.exit(2)
