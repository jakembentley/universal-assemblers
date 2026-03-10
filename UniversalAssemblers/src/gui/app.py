"""
Main application class.  Owns the pygame window and the top-level state
machine (main_menu → galaxy → system).
"""
from __future__ import annotations

import json
import os
import sys

import pygame

from .constants import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, TITLE
from .main_menu import MainMenu
from .game_view import GameView
from .galaxy_view import GalaxyView
from .game_clock import GameClock
from .pause_menu import PauseMenu
from .entity_view import EntityView
from .tech_view import TechView
from .new_game_panel import NewGamePanel
from ..generator import MapGenerator
from ..models.celestial import Galaxy
from ..game_state import GameState


class App:

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock  = pygame.time.Clock()

        self.state: str = "menu"   # "menu" | "galaxy" | "system"

        self.galaxy: Galaxy | None         = None
        self.game_state: GameState | None  = None
        self._selected_system_idx: int     = 0
        self.selected_body_id: str | None  = None

        self.main_menu: MainMenu   = MainMenu(self)
        self.galaxy_view: GalaxyView | None = None
        self.game_view:   GameView  | None  = None

        self.game_clock     = GameClock()
        self.pause_menu     = PauseMenu(self)
        self.entity_view    = EntityView(self)
        self.tech_view      = TechView(self)
        self.new_game_panel = NewGamePanel(self)

    # ------------------------------------------------------------------
    # Galaxy / selection accessors

    @property
    def selected_system(self):
        if self.galaxy and 0 <= self._selected_system_idx < len(self.galaxy.solar_systems):
            return self.galaxy.solar_systems[self._selected_system_idx]
        return None

    def select_system(self, idx: int) -> None:
        self._selected_system_idx = idx
        self.selected_body_id     = None
        if self.game_view:
            self.game_view.on_system_changed()

    def select_body(self, body_id: str) -> None:
        self.selected_body_id = body_id
        if self.game_view:
            self.game_view.on_body_changed()

    # ------------------------------------------------------------------
    # Navigation

    def enter_system(self, system_id: str) -> None:
        """Transition from galaxy map into a specific solar system view."""
        if not self.galaxy:
            return
        idx = next(
            (i for i, s in enumerate(self.galaxy.solar_systems) if s.id == system_id),
            None,
        )
        if idx is None:
            return
        self._selected_system_idx = idx
        self.selected_body_id     = None
        if self.game_view is None:
            self.game_view = GameView(self)
        else:
            self.game_view.on_system_changed()
        self.state = "system"

    def back_to_galaxy(self) -> None:
        self.entity_view.deactivate()
        self.state = "galaxy"

    # ------------------------------------------------------------------
    # Pause / resume

    def resume_game(self) -> None:
        self.pause_menu.is_active = False
        self.game_clock.unpause()

    def open_entity_view(
        self,
        category: str,
        type_value: str,
        system_id: str | None = None,
        body_id: str | None = None,
    ) -> None:
        self.tech_view.deactivate()
        self.entity_view.activate(category, type_value, system_id, body_id)

    def close_entity_view(self) -> None:
        self.entity_view.deactivate()

    def open_tech_view(self) -> None:
        self.entity_view.deactivate()
        self.tech_view.activate()

    def close_tech_view(self) -> None:
        self.tech_view.deactivate()

    # ------------------------------------------------------------------
    # Menu actions

    def start_new_game(self) -> None:
        """Open the new game settings panel instead of starting directly."""
        self.new_game_panel = NewGamePanel(self)
        self.state = "new_game_settings"

    def launch_game(self, settings: dict) -> None:
        """Called by NewGamePanel when START is clicked."""
        gen = MapGenerator(
            num_solar_systems=settings.get("num_solar_systems", 12),
            galaxy_name=settings.get("galaxy_name", "Unnamed Sector"),
            resource_density=settings.get("resource_density", "normal"),
            bio_uplift_rate=settings.get("bio_uplift_rate", "normal"),
            body_distribution=settings.get("body_distribution", "balanced"),
            warp_clusters=settings.get("warp_clusters", 1),
        )
        self.galaxy = gen.generate()
        import os
        os.makedirs("maps", exist_ok=True)
        MapGenerator.save(self.galaxy, "maps/autosave.json")
        self._selected_system_idx = 0
        self.selected_body_id     = None

        self.game_state  = GameState.new_game(self.galaxy, home_idx=0)
        self.galaxy_view = GalaxyView(self)
        self.game_view   = None       # lazily created on first enter_system
        self.game_clock  = GameClock()
        self.state       = "galaxy"

    def save_game(self) -> None:
        if not self.galaxy or not self.game_state:
            return
        os.makedirs("maps", exist_ok=True)
        MapGenerator.save(self.galaxy, "maps/quicksave_galaxy.json")
        gs_data = self.game_state.to_dict()
        gs_data["galaxy_file"] = "maps/quicksave_galaxy.json"
        with open("maps/quicksave.json", "w", encoding="utf-8") as fh:
            json.dump(gs_data, fh, indent=2)
        print("[save_game] Saved to maps/quicksave.json + quicksave_galaxy.json")

    def load_game(self) -> None:
        path = self._open_file_dialog()
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)

            if data.get("version") == 1:
                # Full save: load galaxy from companion file
                galaxy_file = data.get("galaxy_file", "")
                if not os.path.isabs(galaxy_file):
                    # Resolve relative to the save file's directory
                    galaxy_file = os.path.join(os.path.dirname(path), galaxy_file)
                if not os.path.exists(galaxy_file):
                    raise FileNotFoundError(f"Galaxy file not found: {galaxy_file}")
                with open(galaxy_file, encoding="utf-8") as fh:
                    galaxy_data = json.load(fh)
                self.galaxy     = Galaxy.from_dict(galaxy_data)
                self.game_state = GameState.from_dict(data, self.galaxy)
            else:
                # Legacy: galaxy-only JSON
                self.galaxy     = Galaxy.from_dict(data)
                self.game_state = GameState.new_game(self.galaxy, home_idx=0)

        except Exception as exc:
            print(f"[load_game] Failed to load '{path}': {exc}")
            return

        self._selected_system_idx   = 0
        self.selected_body_id       = None
        self.galaxy_view            = GalaxyView(self)
        self.game_view              = None
        self.game_clock             = GameClock()
        self.pause_menu.is_active   = False
        self.pause_menu._sub_active = False
        self.state                  = "galaxy"

    def exit_to_menu(self) -> None:
        self.pause_menu.is_active   = False
        self.pause_menu._sub_active = False
        self.game_clock = GameClock()
        self.state = "menu"

    @staticmethod
    def _open_file_dialog() -> str | None:
        """Use tkinter (stdlib) to show a native file picker."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Load Map File",
                filetypes=[("Map JSON", "*.json"), ("All files", "*.*")],
                initialdir="maps",
            )
            root.destroy()
            return path or None
        except Exception as exc:
            print(f"[file dialog] {exc}")
            return None

    def quit(self) -> None:
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------
    # Main loop

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS)
            events = pygame.event.get()

            # Global events (always processed)
            for event in events:
                if event.type == pygame.QUIT:
                    self.quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.tech_view.is_active:
                            self.close_tech_view()
                        elif self.entity_view.is_active:
                            self.close_entity_view()
                        elif self.pause_menu.is_active:
                            self.resume_game()
                        elif self.state == "new_game_settings":
                            self.state = "menu"
                        elif self.state in ("galaxy", "system"):
                            self.pause_menu.activate()
                            self.game_clock.save_and_pause()
                    if event.key == pygame.K_SPACE:
                        if self.state in ("galaxy", "system") and not self.pause_menu.is_active:
                            self.game_clock.toggle_pause()
                    if event.key == pygame.K_t:
                        if self.state in ("galaxy", "system") and not self.pause_menu.is_active:
                            if self.tech_view.is_active:
                                self.close_tech_view()
                            else:
                                self.open_tech_view()
                self.game_clock.handle_event(event)   # speed badge click

            # Clock + simulation update
            if self.state in ("galaxy", "system") and not self.pause_menu.is_active:
                self.game_clock.update(dt)
                if self.game_state and self.game_clock.current_speed > 0:
                    from .game_clock import GameClock
                    dt_years = dt * GameClock.YEAR_PER_MS_AT_1X * self.game_clock.current_speed
                    self.game_state.tick(dt_years)

            # View draw + events (gated behind pause menu)
            if self.state == "menu":
                self.main_menu.handle_events(events)
                self.main_menu.draw(self.screen)
            elif self.state == "new_game_settings":
                self.screen.fill((8, 8, 20))
                self.new_game_panel.handle_events(events)
                self.new_game_panel.draw(self.screen)
            elif self.state == "galaxy" and self.galaxy_view:
                if not self.pause_menu.is_active and not self.tech_view.is_active:
                    self.galaxy_view.handle_events(events)
                self.galaxy_view.draw(self.screen)
            elif self.state == "system" and self.game_view:
                if not self.pause_menu.is_active and not self.tech_view.is_active:
                    self.game_view.handle_events(events)
                self.game_view.draw(self.screen)

            # Overlay clock + pause menu
            if self.state != "menu":
                self.game_clock.draw(self.screen)
            if self.pause_menu.is_active:
                self.pause_menu.handle_events(events)
                self.pause_menu.draw(self.screen)

            # Tech tree overlay (above pause menu so it can be opened anytime)
            if self.tech_view.is_active:
                self.tech_view.handle_events(events)
                self.tech_view.draw(self.screen)

            pygame.display.flip()
