"""
Main application class.  Owns the pygame window and the top-level state
machine (main_menu → galaxy → system).
"""
from __future__ import annotations

import json
import os
import sys
from collections import deque

import pygame

from .constants import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, TITLE
from .main_menu import MainMenu
from .game_view import GameView
from .galaxy_view import GalaxyView
from .game_clock import GameClock
from .pause_menu import PauseMenu
from .entity_view import EntityView
from .tech_view import TechView
from .energy_view import EnergyView
from .queue_view import QueueView
from .tooltip import Tooltip
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
        self.energy_view    = EnergyView(self)
        self.queue_view     = QueueView(self)
        self.tooltip        = Tooltip()
        self.new_game_panel = NewGamePanel(self)

        # Toast notifications: each entry is (message, expiry_ms, color)
        self._notifications: deque = deque(maxlen=5)
        self._victory_state: str | None = None   # set when a victory condition triggers

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
        self.energy_view.deactivate()
        self.queue_view.deactivate()
        self.entity_view.activate(category, type_value, system_id, body_id)

    def close_entity_view(self) -> None:
        self.entity_view.deactivate()

    def open_tech_view(self) -> None:
        self.entity_view.deactivate()
        self.energy_view.deactivate()
        self.queue_view.deactivate()
        self.tech_view.activate()

    def close_tech_view(self) -> None:
        self.tech_view.deactivate()

    def open_energy_view(self) -> None:
        self.entity_view.deactivate()
        self.tech_view.deactivate()
        self.queue_view.deactivate()
        self.energy_view.activate()

    def close_energy_view(self) -> None:
        self.energy_view.deactivate()

    def open_queue_view(self) -> None:
        self.entity_view.deactivate()
        self.tech_view.deactivate()
        self.energy_view.deactivate()
        self.queue_view.activate()

    def close_queue_view(self) -> None:
        self.queue_view.deactivate()

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

    def save_game(self, slot: int = -1) -> None:
        """Save game. slot=-1 → quicksave, slot=0-2 → autosave ring buffer."""
        if not self.galaxy or not self.game_state:
            return
        os.makedirs("maps", exist_ok=True)
        from ..generator import MapGenerator as _MG
        if slot == -1:
            galaxy_file = "maps/quicksave_galaxy.json"
            save_file   = "maps/quicksave.json"
        else:
            galaxy_file = f"maps/autosave_{slot}_galaxy.json"
            save_file   = f"maps/autosave_{slot}.json"
        _MG.save(self.galaxy, galaxy_file)
        gs_data = self.game_state.to_dict()
        gs_data["galaxy_file"] = galaxy_file
        with open(save_file, "w", encoding="utf-8") as fh:
            json.dump(gs_data, fh, indent=2)

    def _quickload(self) -> None:
        path = "maps/quicksave.json"
        if not os.path.exists(path):
            now = pygame.time.get_ticks()
            self._notifications.append(("No quicksave found", now + 3000, (255, 80, 80)))
            return
        self._load_from_path(path)

    def _autosave(self) -> None:
        """Rolling 3-slot autosave ring buffer."""
        slot_path = "maps/autosave_slot.txt"
        try:
            slot = int(open(slot_path).read().strip()) if os.path.exists(slot_path) else 0
        except Exception:
            slot = 0
        slot = slot % 3
        self.save_game(slot=slot)
        with open(slot_path, "w") as fh:
            fh.write(str((slot + 1) % 3))

    def load_game(self) -> None:
        path = self._open_file_dialog()
        if not path:
            return
        self._load_from_path(path)

    def _load_from_path(self, path: str) -> None:
        """Load a save file from a given path (used by load_game and quickload)."""
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)

            if "galaxy_file" in data:
                # Full save: load galaxy from companion file
                galaxy_file = data.get("galaxy_file", "")
                if not os.path.isabs(galaxy_file):
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
        self._victory_state         = None
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

    def change_resolution(self, w: int, h: int) -> None:
        """Apply a new window resolution and rebuild all geometry-dependent views."""
        from . import constants as _c
        _c.WINDOW_WIDTH  = w
        _c.WINDOW_HEIGHT = h
        _c.TOP_H = h - _c.ENT_H - _c.TASKBAR_H
        _c.MAP_W = w - _c.NAV_W
        self.screen = pygame.display.set_mode((w, h))
        # Rebuild views that cache resolution-dependent geometry
        self.pause_menu  = PauseMenu(self)
        self.entity_view = EntityView(self)
        self.tech_view   = TechView(self)
        self.energy_view = EnergyView(self)
        self.queue_view  = QueueView(self)
        if self.galaxy_view:
            self.galaxy_view = GalaxyView(self)
        if self.game_view:
            self.game_view = GameView(self)

    def quit(self) -> None:
        if self.galaxy and self.game_state:
            self._autosave()
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------
    # Toast notifications

    def _location_name(self, body_id: "str | None", system_id: "str | None") -> str:
        """Resolve a body_id or system_id to a human-readable name."""
        if body_id and self.galaxy:
            for sys in self.galaxy.solar_systems:
                for body in sys.orbital_bodies:
                    if body.id == body_id:
                        return body.name
                    for moon in body.moons:
                        if moon.id == body_id:
                            return moon.name
        if system_id and self.galaxy:
            sys_obj = next(
                (s for s in self.galaxy.solar_systems if s.id == system_id), None
            )
            if sys_obj:
                return sys_obj.name
        return body_id or system_id or "?"

    def _process_sim_events(self) -> None:
        if not self.game_state:
            return
        now = pygame.time.get_ticks()
        TTL = 6000   # ms
        from ..models.tech import TECH_TREE
        for ev in self.game_state.pop_sim_events():
            etype = ev.get("type", "")
            if etype == "tech_complete":
                tid = ev.get("tech_id", "")
                name = TECH_TREE[tid].name if tid in TECH_TREE else tid
                msg = f"TECH UNLOCKED: {name}"
                col = (80, 220, 120)
            elif etype == "entity_built":
                ent = (ev.get("entity_type") or "").replace("_", " ").title()
                msg = f"BUILT: {ent}"
                col = (80, 200, 255)
            elif etype in ("drop_ship_arrived", "probe_arrived", "ship_arrived"):
                dest = ev.get("destination") or ev.get("system_id") or "?"
                if self.galaxy:
                    sys_obj = next((s for s in self.galaxy.solar_systems if s.id == dest), None)
                    if sys_obj:
                        dest = sys_obj.name
                if etype == "drop_ship_arrived":
                    label = "Drop Ship"
                elif etype == "probe_arrived":
                    label = "Probe"
                else:
                    label = (ev.get("ship_type") or "Ship").replace("_", " ").title()
                label = label  # keep for f-string below
                msg = f"{label} arrived: {dest}"
                col = (255, 200, 80)
            elif etype == "resource_depleted":
                res = (ev.get("resource") or "").replace("_", " ").title()
                msg = f"RESOURCE DEPLETED: {res}"
                col = (255, 80, 80)
            elif etype == "resource_depleted_plant":
                plant_type = (ev.get("plant_type") or "").replace("_", " ").title()
                loc_id = ev.get("location_id") or "?"
                # Try to get a friendly name for the location
                loc_name = loc_id
                if self.galaxy:
                    for sys in self.galaxy.solar_systems:
                        for body in sys.orbital_bodies:
                            if body.id == loc_id:
                                loc_name = body.name
                            for moon in body.moons:
                                if moon.id == loc_id:
                                    loc_name = moon.name
                msg = f"⚡ {plant_type} offline — fuel depleted at {loc_name}"
                col = (255, 160, 40)
            elif etype in ("bios_entity_damaged", "bios_entity_destroyed"):
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                ent = (ev.get("entity_type") or "entity").replace("_", " ").title()
                verb = "destroyed" if etype == "bios_entity_destroyed" else "damaged"
                msg = f"BIOS ATTACK: {ent} {verb} at {loc}"
                col = (255, 60, 60)
            elif etype == "bios_mutation":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                msg = f"BIOS MUTATED to Uplifted at {loc}"
                col = (255, 120, 40)
            elif etype == "bios_extinction":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                btype = (ev.get("bio_type") or "bio").title()
                msg = f"BIOS EXTINCT: {btype} population lost at {loc}"
                col = (180, 80, 200)
            elif etype in ("solar_flare_damaged", "solar_flare_destroyed"):
                loc = self._location_name(None, ev.get("system_id"))
                ent = (ev.get("entity_type") or "ship").replace("_", " ").title()
                verb = "destroyed" if etype == "solar_flare_destroyed" else "damaged"
                msg = f"SOLAR FLARE: {ent} {verb} in {loc}"
                col = (255, 140, 0)
            elif etype == "asteroid_impact":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                ent = (ev.get("entity_type") or "structure").replace("_", " ").title()
                destroyed = ev.get("destroyed", False)
                msg = f"ASTEROID IMPACT: {ent} {'destroyed' if destroyed else 'damaged'} at {loc}"
                col = (255, 80, 80)
            elif etype == "factory_malfunction":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                destroyed = ev.get("destroyed", False)
                msg = f"FACTORY MALFUNCTION at {loc}" + (" — destroyed!" if destroyed else "")
                col = (255, 160, 40)
            elif etype == "power_surge":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                ent = (ev.get("entity_type") or "power plant").replace("_", " ").title()
                destroyed = ev.get("destroyed", False)
                msg = f"POWER SURGE: {ent} {'destroyed' if destroyed else 'damaged'} at {loc}"
                col = (255, 160, 40)
            elif etype == "vein_discovery":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                res = (ev.get("resource") or "minerals").replace("_", " ").title()
                amt = ev.get("amount", 0)
                msg = f"VEIN FOUND: +{amt} {res} at {loc}"
                col = (80, 220, 120)
            elif etype == "bio_population_boom":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                btype = (ev.get("bio_type") or "bio").title()
                msg = f"BIO BOOM: {btype} population surge at {loc}"
                col = (160, 100, 255)
            elif etype == "bio_aggression_spike":
                loc = self._location_name(ev.get("body_id"), ev.get("system_id"))
                new_agg = ev.get("new_aggression", 0.0)
                msg = f"BIO AGGRESSION SPIKE at {loc}: {int(new_agg * 100)}%"
                col = (255, 100, 40)
            elif etype == "research_breakthrough":
                from ..models.tech import TECH_TREE
                tid  = ev.get("tech_id", "")
                name = TECH_TREE[tid].name if tid in TECH_TREE else tid
                if ev.get("tech_completed"):
                    msg = f"BREAKTHROUGH: {name} completed!"
                    col = (80, 220, 120)
                else:
                    msg = f"RESEARCH BREAKTHROUGH: {name} advanced"
                    col = (100, 180, 255)
            elif etype == "victory":
                vtype = ev.get("victory_type", "unknown")
                self._victory_state = vtype
                continue
            else:
                continue
            self._notifications.append((msg, now + TTL, col))

    def _draw_notifications(self, surface: pygame.Surface) -> None:
        if not self._notifications:
            return
        from .constants import font as _font, WINDOW_WIDTH
        from .game_clock import GameClock
        clock_h = GameClock.CLOCK_H if hasattr(GameClock, "CLOCK_H") else 32
        now = pygame.time.get_ticks()
        # Prune expired
        while self._notifications and self._notifications[0][1] <= now:
            self._notifications.popleft()
        x = WINDOW_WIDTH - 10
        y = clock_h + 8
        TTL = 6000
        for msg, expiry, col in reversed(list(self._notifications)):
            remaining = expiry - now
            alpha = min(255, int(255 * remaining / max(1, min(TTL, 1500))))
            pad = 6
            surf = _font(12, bold=True).render(msg, True, col)
            w = surf.get_width() + pad * 2
            h = surf.get_height() + pad * 2
            bg = pygame.Surface((w, h), pygame.SRCALPHA)
            bg.fill((10, 10, 30, min(200, alpha)))
            surface.blit(bg, (x - w, y))
            surf.set_alpha(alpha)
            surface.blit(surf, (x - w + pad, y + pad))
            pygame.draw.rect(surface, (*col, alpha), pygame.Rect(x - w, y, w, h), 1)
            y += h + 4

    def _draw_victory_overlay(self, surface: pygame.Surface) -> None:
        """Full-screen victory overlay shown when a win condition triggers."""
        from .constants import font as _font, WINDOW_WIDTH, WINDOW_HEIGHT
        # Dim background
        dim = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        surface.blit(dim, (0, 0))

        cx = WINDOW_WIDTH  // 2
        cy = WINDOW_HEIGHT // 2

        _VICTORY_LABELS = {
            "domination":  ("DOMINATION VICTORY",  "You have colonised 60% of the known galaxy."),
            "construction": ("CONSTRUCTION VICTORY", "The Doom Machine is complete."),
            "technology":  ("TECHNOLOGY VICTORY",   "All technologies have been researched."),
        }
        title_txt, sub_txt = _VICTORY_LABELS.get(
            self._victory_state or "",
            ("VICTORY", "You have won!")
        )

        # Title
        title_s = _font(36, bold=True).render(title_txt, True, (255, 220, 80))
        surface.blit(title_s, title_s.get_rect(center=(cx, cy - 60)))

        # Subtitle
        sub_s = _font(18).render(sub_txt, True, (200, 200, 220))
        surface.blit(sub_s, sub_s.get_rect(center=(cx, cy - 15)))

        # Buttons
        cont_r = pygame.Rect(cx - 175, cy + 30, 150, 42)
        new_r  = pygame.Rect(cx + 25,  cy + 30, 150, 42)
        pygame.draw.rect(surface, (40, 100, 60), cont_r, border_radius=6)
        pygame.draw.rect(surface, (80, 30, 30),  new_r,  border_radius=6)
        pygame.draw.rect(surface, (100, 180, 120), cont_r, width=2, border_radius=6)
        pygame.draw.rect(surface, (180, 80,  80),  new_r,  width=2, border_radius=6)
        cont_lbl = _font(14, bold=True).render("CONTINUE", True, (200, 255, 220))
        new_lbl  = _font(14, bold=True).render("NEW GAME",  True, (255, 180, 180))
        surface.blit(cont_lbl, cont_lbl.get_rect(center=cont_r.center))
        surface.blit(new_lbl,  new_lbl.get_rect(center=new_r.center))

        # Handle click
        for event in pygame.event.peek([pygame.MOUSEBUTTONDOWN]):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if cont_r.collidepoint(event.pos):
                    self._victory_state = None
                    pygame.event.clear([pygame.MOUSEBUTTONDOWN])
                elif new_r.collidepoint(event.pos):
                    self._victory_state = None
                    self.exit_to_menu()
                    pygame.event.clear([pygame.MOUSEBUTTONDOWN])

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
                        if self.queue_view.is_active:
                            self.close_queue_view()
                        elif self.energy_view.is_active:
                            self.close_energy_view()
                        elif self.tech_view.is_active:
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
                    if event.key == pygame.K_F5:
                        if self.state in ("galaxy", "system") and self.game_state:
                            self.save_game()
                            now = pygame.time.get_ticks()
                            self._notifications.append(("GAME SAVED  [F5]", now + 3000, (80, 220, 120)))
                    if event.key == pygame.K_F9:
                        if self.state in ("galaxy", "system"):
                            self._quickload()
                self.game_clock.handle_event(event)   # speed badge click

            # Clock + simulation update
            if self.state in ("galaxy", "system") and not self.pause_menu.is_active:
                self.game_clock.update(dt)
                if self.game_state and self.game_clock.current_speed > 0:
                    from .game_clock import GameClock
                    dt_years = dt * GameClock.YEAR_PER_MS_AT_1X * self.game_clock.current_speed
                    self.game_state.tick(dt_years)
                    self._process_sim_events()

            # View draw + events (gated behind pause menu)
            if self.state == "menu":
                self.main_menu.handle_events(events)
                self.main_menu.draw(self.screen)
            elif self.state == "new_game_settings":
                self.screen.fill((8, 8, 20))
                self.new_game_panel.handle_events(events)
                self.new_game_panel.draw(self.screen)
            elif self.state == "galaxy" and self.galaxy_view:
                overlays_active = (self.pause_menu.is_active or self.tech_view.is_active
                                   or self.energy_view.is_active or self.queue_view.is_active)
                if not overlays_active:
                    self.galaxy_view.handle_events(events)
                self.galaxy_view.draw(self.screen)
            elif self.state == "system" and self.game_view:
                overlays_active = (self.pause_menu.is_active or self.tech_view.is_active
                                   or self.energy_view.is_active or self.queue_view.is_active)
                if not overlays_active:
                    self.game_view.handle_events(events)
                self.game_view.draw(self.screen)

            # Overlay clock + pause menu
            if self.state != "menu":
                self.game_clock.draw(self.screen)
                self._draw_notifications(self.screen)
            if self.pause_menu.is_active:
                self.pause_menu.handle_events(events)
                self.pause_menu.draw(self.screen)

            # Tech tree overlay (above pause menu so it can be opened anytime)
            if self.tech_view.is_active:
                self.tech_view.handle_events(events)
                self.tech_view.draw(self.screen)

            # Energy overview overlay
            if self.energy_view.is_active:
                self.energy_view.handle_events(events)
                self.energy_view.draw(self.screen)

            # Queue overlay
            if self.queue_view.is_active:
                self.queue_view.handle_events(events)
                self.queue_view.draw(self.screen)

            # Tooltip — drawn last so it appears above everything
            self.tooltip.draw(self.screen)

            # Victory overlay
            if self._victory_state:
                self._draw_victory_overlay(self.screen)

            pygame.display.flip()
