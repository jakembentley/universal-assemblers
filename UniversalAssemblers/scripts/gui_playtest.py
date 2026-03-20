"""
Universal Assemblers — GUI Event-Injection Playtest.

Drives the App via direct method calls (same as scripts/playtest.py) and
supplements with pixel-region assertions.  Because App.run() is a blocking
loop, we replicate one-frame rendering via a local render_frame() helper.

In headless mode (default) the SDL "dummy" driver is used; pixel assertions
are automatically skipped because dummy renders no real pixels.

Usage (from UniversalAssemblers/):
    ~/anaconda3/python.exe scripts/gui_playtest.py          # headless (default)
    ~/anaconda3/python.exe scripts/gui_playtest.py --window # real window (debug)
    ~/anaconda3/python.exe scripts/gui_playtest.py --out playtest_output/gui_report.json
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
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--window", action="store_true",
                     help="Show real window (enables pixel assertions)")
_parser.add_argument("--out", type=str, default=None)
_args, _ = _parser.parse_known_args()

_HEADLESS = not _args.window
if _HEADLESS:
    # "dummy" is always available on all platforms; surfaces are valid but
    # contain no real pixel content — pixel assertions are skipped.
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR   = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_DIR)
os.chdir(REPO_DIR)

import pygame  # noqa: E402

from src.gui.app import App  # noqa: E402

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(REPO_DIR, "playtest_output")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Report state
# ---------------------------------------------------------------------------
checks:  list[dict] = []
errors:  list[str]  = []


def record_pass(name: str, detail: str = "") -> None:
    checks.append({"name": name, "passed": True, "detail": detail})
    suffix = f" ({detail})" if detail else ""
    print(f"  [PASS] {name}{suffix}")


def record_fail(name: str, error: str = "") -> None:
    checks.append({"name": name, "passed": False, "error": error})
    suffix = f": {error}" if error else ""
    print(f"  [FAIL] {name}{suffix}")


# ---------------------------------------------------------------------------
# One-frame rendering helper (mirrors App.run() draw section)
# ---------------------------------------------------------------------------

def render_frame(app: App) -> None:
    """Draw one complete frame without blocking."""
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
        if app.tech_view.is_active:
            app.tech_view.draw(app.screen)
        if app.energy_view.is_active:
            app.energy_view.draw(app.screen)
        if app.queue_view.is_active:
            app.queue_view.draw(app.screen)
        if app.entity_view.is_active:
            app.entity_view.draw(app.screen)

    pygame.display.flip()


# ---------------------------------------------------------------------------
# Pixel assertion helpers
# ---------------------------------------------------------------------------

def assert_region_not_blank(surface: pygame.Surface, rect: pygame.Rect, label: str) -> bool:
    """Return True if region has non-zero pixels.

    Always returns True in headless/dummy mode (pixels are meaningless there).
    """
    if _HEADLESS:
        return True
    arr = pygame.surfarray.array3d(surface)
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    x = max(0, x); y = max(0, y)
    w = min(w, arr.shape[0] - x)
    h = min(h, arr.shape[1] - y)
    if w <= 0 or h <= 0:
        return False
    return bool(arr[x:x + w, y:y + h].max() > 0)


def pixel_check(name: str, surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Record a pass/fail pixel assertion, skipping in headless mode."""
    if _HEADLESS:
        record_pass(name, "skipped (headless)")
        return
    if assert_region_not_blank(surface, rect, name):
        record_pass(name)
    else:
        record_fail(name, f"region {rect} is entirely black")


# ---------------------------------------------------------------------------
# Simulate ESC key processing (mirrors App.run() ESC branch)
# ---------------------------------------------------------------------------

def process_esc(app: App) -> None:
    """Simulate pressing ESC: closes the topmost overlay or pauses the game."""
    if app.queue_view.is_active:
        app.close_queue_view()
    elif app.energy_view.is_active:
        app.close_energy_view()
    elif app.tech_view.is_active:
        app.close_tech_view()
    elif app.entity_view.is_active:
        app.close_entity_view()
    elif app.state in ("galaxy", "system"):
        # Would open pause menu — not testing that here, just note transition
        pass
    render_frame(app)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_initial_state(app: App) -> None:
    print("\n[1] Initial state")
    render_frame(app)
    if app.state == "menu":
        record_pass("initial_state_is_menu")
    else:
        record_fail("initial_state_is_menu", f"state={app.state}")

    if app.main_menu is not None:
        record_pass("main_menu_exists")
    else:
        record_fail("main_menu_exists")


def test_launch_game(app: App) -> None:
    print("\n[2] Launch game")
    settings = {
        "num_solar_systems":  6,
        "galaxy_name":        "GUI Playtest",
        "resource_density":   "normal",
        "bio_uplift_rate":    "normal",
        "body_distribution":  "balanced",
        "warp_clusters":      1,
    }
    app.launch_game(settings)
    render_frame(app)

    if app.state == "galaxy":
        record_pass("launch_game_reaches_galaxy")
    else:
        record_fail("launch_game_reaches_galaxy", f"state={app.state}")

    if app.game_state is not None:
        record_pass("game_state_created")
    else:
        record_fail("game_state_created", "game_state is None")

    if app.galaxy is not None and len(app.galaxy.solar_systems) > 0:
        record_pass("galaxy_has_systems", f"count={len(app.galaxy.solar_systems)}")
    else:
        record_fail("galaxy_has_systems", "no solar systems")

    # Pixel: galaxy map center should render something
    if app.screen:
        w, h = app.screen.get_size()
        pixel_check("galaxy_view_renders", app.screen,
                    pygame.Rect(w // 3, h // 3, w // 3, h // 3))


def test_enter_home_system(app: App) -> None:
    print("\n[3] Enter home system")
    if not app.galaxy:
        record_fail("enter_home_system", "no galaxy")
        return

    home_id = app.galaxy.solar_systems[0].id
    app.enter_system(home_id)
    render_frame(app)

    if app.state == "system":
        record_pass("enter_home_system")
    else:
        record_fail("enter_home_system", f"state={app.state}")

    if app.game_view is not None:
        record_pass("game_view_created")
    else:
        record_fail("game_view_created", "game_view is None")

    if app.screen:
        w, h = app.screen.get_size()
        pixel_check("system_view_renders", app.screen,
                    pygame.Rect(w // 4, h // 4, w // 2, h // 2))


def test_tech_overlay(app: App) -> None:
    print("\n[4] Tech overlay")
    app.open_tech_view()
    render_frame(app)

    if app.tech_view.is_active:
        record_pass("tech_overlay_opens")
    else:
        record_fail("tech_overlay_opens", "tech_view.is_active is False")

    if not app.energy_view.is_active and not app.queue_view.is_active:
        record_pass("tech_overlay_mutual_exclusion")
    else:
        record_fail("tech_overlay_mutual_exclusion",
                    f"energy={app.energy_view.is_active} queue={app.queue_view.is_active}")

    if app.screen:
        w, h = app.screen.get_size()
        pixel_check("tech_overlay_renders", app.screen,
                    pygame.Rect(w // 6, h // 6, 2 * w // 3, 2 * h // 3))

    # ESC should close it
    process_esc(app)
    if not app.tech_view.is_active:
        record_pass("esc_closes_tech_overlay")
    else:
        record_fail("esc_closes_tech_overlay", "tech_view still active after ESC")


def test_energy_overlay(app: App) -> None:
    print("\n[5] Energy overlay")
    app.open_energy_view()
    render_frame(app)

    if app.energy_view.is_active:
        record_pass("energy_overlay_opens")
    else:
        record_fail("energy_overlay_opens", "energy_view.is_active is False")

    if not app.tech_view.is_active:
        record_pass("energy_overlay_mutual_exclusion")
    else:
        record_fail("energy_overlay_mutual_exclusion", "tech_view still active")

    if app.screen:
        w, h = app.screen.get_size()
        pixel_check("energy_overlay_renders", app.screen,
                    pygame.Rect(w // 6, h // 6, 2 * w // 3, 2 * h // 3))

    process_esc(app)
    if not app.energy_view.is_active:
        record_pass("esc_closes_energy_overlay")
    else:
        record_fail("esc_closes_energy_overlay", "energy_view still active after ESC")


def test_queue_overlay(app: App) -> None:
    print("\n[6] Queue overlay")
    app.open_queue_view()
    render_frame(app)

    if app.queue_view.is_active:
        record_pass("queue_overlay_opens")
    else:
        record_fail("queue_overlay_opens", "queue_view.is_active is False")

    process_esc(app)
    if not app.queue_view.is_active:
        record_pass("esc_closes_queue_overlay")
    else:
        record_fail("esc_closes_queue_overlay", "queue_view still active after ESC")


def test_overlay_mutual_exclusion(app: App) -> None:
    print("\n[7] Overlay mutual exclusion")
    app.open_tech_view()
    render_frame(app)
    app.open_energy_view()
    render_frame(app)

    if app.energy_view.is_active and not app.tech_view.is_active:
        record_pass("energy_deactivates_tech")
    else:
        record_fail("energy_deactivates_tech",
                    f"energy={app.energy_view.is_active} tech={app.tech_view.is_active}")

    app.open_queue_view()
    render_frame(app)
    if app.queue_view.is_active and not app.energy_view.is_active:
        record_pass("queue_deactivates_energy")
    else:
        record_fail("queue_deactivates_energy",
                    f"queue={app.queue_view.is_active} energy={app.energy_view.is_active}")

    app.close_queue_view()
    render_frame(app)
    if not any([app.tech_view.is_active, app.energy_view.is_active,
                app.queue_view.is_active, app.entity_view.is_active]):
        record_pass("all_overlays_closed")
    else:
        record_fail("all_overlays_closed", "at least one overlay still active")


def test_entity_views(app: App) -> None:
    print("\n[8] Entity views")
    if not (app.game_state and app.galaxy):
        record_fail("entity_view_test", "no game state or galaxy")
        return

    home = app.galaxy.solar_systems[0]
    home_body_id: str | None = None
    for inst in app.game_state.entity_roster._instances:
        if inst.type_value == "factory":
            home_body_id = inst.location_id
            break

    if not home_body_id:
        record_fail("entity_view_factory", "factory not found in roster")
        return

    app.open_entity_view("structure", "factory",
                         system_id=home.id, body_id=home_body_id)
    render_frame(app)

    if app.entity_view.is_active:
        record_pass("entity_view_factory_opens")
    else:
        record_fail("entity_view_factory_opens", "entity_view not active")

    if not app.tech_view.is_active and not app.energy_view.is_active:
        record_pass("entity_view_mutual_exclusion")
    else:
        record_fail("entity_view_mutual_exclusion", "another overlay still active")

    process_esc(app)
    if not app.entity_view.is_active:
        record_pass("esc_closes_entity_view")
    else:
        record_fail("esc_closes_entity_view", "entity_view still active after ESC")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    out_path = _args.out or os.path.join(OUT_DIR, "gui_report.json")
    mode = "windowed" if not _HEADLESS else "headless (dummy driver)"

    print("=" * 60)
    print("  Universal Assemblers — GUI Event-Injection Playtest")
    print(f"  Mode: {mode}")
    print("=" * 60)

    app = App()
    render_frame(app)

    test_initial_state(app)
    test_launch_game(app)
    test_enter_home_system(app)
    test_tech_overlay(app)
    test_energy_overlay(app)
    test_queue_overlay(app)
    test_overlay_mutual_exclusion(app)
    test_entity_views(app)

    pygame.quit()

    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed

    report = {
        "mode":    mode,
        "checks":  checks,
        "passed":  passed,
        "failed":  failed,
        "errors":  errors,
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{len(checks)} passed")
    if failed:
        print(f"  Failures ({failed}):")
        for c in checks:
            if not c["passed"]:
                print(f"    ✗ {c['name']}: {c.get('error', '')}")
    print(f"  Report: {out_path}")
    print("=" * 60)

    return 0 if failed == 0 else 1


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
