"""Three-pane game interface assembled from NavPanel, MapPanel, EntitiesPanel."""
from __future__ import annotations

import pygame
from .nav_panel      import NavPanel
from .map_panel      import MapPanel
from .entities_panel import EntitiesPanel


class GameView:

    def __init__(self, app) -> None:
        self.app            = app
        self.nav_panel      = NavPanel(app)
        self.map_panel      = MapPanel(app)
        self.entities_panel = EntitiesPanel(app)

    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        self.nav_panel.handle_events(events)
        self.map_panel.handle_events(events)
        self.entities_panel.handle_events(events)

    def draw(self, surface: pygame.Surface) -> None:
        from .constants import C_BG
        surface.fill(C_BG)
        self.nav_panel.draw(surface)
        self.map_panel.draw(surface)
        self.entities_panel.draw(surface)

    # ------------------------------------------------------------------
    # Called by App when game state changes

    def on_system_changed(self) -> None:
        self.map_panel.on_system_changed()
        self.nav_panel.on_system_changed()

    def on_body_changed(self) -> None:
        self.nav_panel.on_body_changed()
