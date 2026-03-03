"""
Main application class.  Owns the pygame window and the top-level state
machine (main_menu  ↔  game).
"""
from __future__ import annotations

import json
import sys

import pygame

from .constants import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, TITLE
from .main_menu import MainMenu
from .game_view import GameView
from ..generator import MapGenerator
from ..models.celestial import Galaxy


class App:

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock  = pygame.time.Clock()

        self.state: str = "menu"   # "menu" | "game"

        self.galaxy: Galaxy | None         = None
        self._selected_system_idx: int     = 0
        self.selected_body_id: str | None  = None

        self.main_menu: MainMenu  = MainMenu(self)
        self.game_view: GameView | None = None

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
    # Menu actions

    def start_new_game(self) -> None:
        gen          = MapGenerator(num_solar_systems=12, galaxy_name="Sector Zero")
        self.galaxy  = gen.generate()
        MapGenerator.save(self.galaxy, "maps/autosave.json")
        self._selected_system_idx = 0
        self.selected_body_id     = None
        self.game_view = GameView(self)
        self.state     = "game"

    def load_game(self) -> None:
        path = self._open_file_dialog()
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.galaxy = Galaxy.from_dict(data)
        except Exception as exc:
            print(f"[load_game] Failed to load '{path}': {exc}")
            return
        self._selected_system_idx = 0
        self.selected_body_id     = None
        self.game_view = GameView(self)
        self.state     = "game"

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
            self.clock.tick(FPS)
            events = pygame.event.get()

            for event in events:
                if event.type == pygame.QUIT:
                    self.quit()
                # ESC from game → back to menu
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.state == "game":
                        self.state = "menu"

            if self.state == "menu":
                self.main_menu.handle_events(events)
                self.main_menu.draw(self.screen)
            elif self.state == "game" and self.game_view:
                self.game_view.handle_events(events)
                self.game_view.draw(self.screen)

            pygame.display.flip()
