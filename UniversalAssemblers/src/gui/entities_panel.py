"""
Bottom panel: player entities.

Three columns — Structures | Bots | Ships — with counts read live from
GameState.entity_roster.  Each column lists every known entity type; a
count of 0 is shown dimly for types not yet built.  Clicking a row opens
the entity detail view.
"""
from __future__ import annotations

import pygame
from . import constants as _c
from .constants import (
    ENT_H, TASKBAR_H, HEADER_H, PADDING, ROW_H,
    C_PANEL, C_BORDER, C_HEADER, C_ACCENT, C_TEXT, C_TEXT_DIM,
    C_SEP, C_SELECTED, C_HOVER, font,
)
from .widgets import draw_panel, draw_separator


# ---------------------------------------------------------------------------
# Entity type registry: (type_value, display_name, icon)
# Order controls display order in each column.
# ---------------------------------------------------------------------------

_STRUCTURE_TYPES: list[tuple[str, str, str]] = [
    ("extractor",           "Extractor",       "⬡"),
    ("factory",             "Factory",         "⬡"),
    ("power_plant_solar",   "Solar Plant",     "⬡"),
    ("power_plant_wind",    "Wind Plant",      "⬡"),
    ("power_plant_bios",    "Bio Plant",       "⬡"),
    ("power_plant_fossil",  "Fossil Plant",    "⬡"),
    ("power_plant_nuclear", "Nuclear Plant",   "⬡"),
    ("research_array",      "Research Array",  "⬡"),
    ("replicator",          "Replicator",      "⬡"),
    ("shipyard",            "Shipyard",        "⬡"),
    ("storage_hub",         "Storage Hub",     "⬡"),
]

_BOT_TYPES: list[tuple[str, str, str]] = [
    ("worker",      "Worker Bot",  "◈"),
    ("harvester",   "Harvester",   "◈"),
    ("miner",       "Miner Bot",   "◈"),
    ("constructor", "Constructor", "◈"),
]

_SHIP_TYPES: list[tuple[str, str, str]] = [
    ("probe",         "Probe",       "▷"),
    ("drop_ship",     "Drop Ship",   "▷"),
    ("mining_vessel", "Miner",       "▷"),
    ("transport",     "Transport",   "▷"),
    ("warship",       "Warship",     "▷"),
]

# (column_title, category_key, type_list, accent_colour)
_COLUMNS: list[tuple[str, str, list, tuple]] = [
    ("Structures", "structure", _STRUCTURE_TYPES, C_ACCENT),
    ("Bots",       "bot",       _BOT_TYPES,       (130, 200, 130)),
    ("Ships",      "ship",      _SHIP_TYPES,       (200, 160, 255)),
]


class EntitiesPanel:

    def __init__(self, app) -> None:
        self.app  = app
        self.rect = pygame.Rect(0, _c.TOP_H + TASKBAR_H, _c.WINDOW_WIDTH, ENT_H)
        # Hit rects populated each draw(): (rect, category, type_val)
        self._hit_rects: list[tuple[pygame.Rect, str, str]] = []

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, category, type_val in self._hit_rects:
                    if rect.collidepoint(event.pos):
                        sys   = self.app.selected_system
                        sys_id  = sys.id if sys else None
                        body_id = self.app.selected_body_id
                        # Ships live at system level; structures/bots at body level
                        if category == "ship":
                            body_id = None
                        self.app.open_entity_view(category, type_val, sys_id, body_id)
                        return

    def draw(self, surface: pygame.Surface) -> None:
        content = draw_panel(surface, self.rect, "Player Entities")
        roster  = (
            self.app.game_state.entity_roster
            if self.app.game_state else None
        )

        self._hit_rects = []
        mouse_pos = pygame.mouse.get_pos()
        col_w = content.width // len(_COLUMNS)
        row_h = ROW_H - 2

        for ci, (title, category, types, accent) in enumerate(_COLUMNS):
            cx = content.x + ci * col_w
            cy = content.y

            # Column total
            col_total = (
                sum(roster.total(category, tv) for tv, _, _ in types)
                if roster else 0
            )
            header = font(12, bold=True).render(
                f"{title.upper()}  ({col_total})", True, accent
            )
            surface.blit(header, (cx + PADDING, cy + 4))

            draw_separator(surface, cx + PADDING, cy + 22, cx + col_w - PADDING)

            if ci > 0:
                pygame.draw.line(surface, C_SEP, (cx, content.y), (cx, content.bottom), 1)

            row_y = cy + 26
            for type_val, name, icon in types:
                if row_y + row_h > content.bottom:
                    break

                count = roster.total(category, type_val) if roster else 0

                row_rect = pygame.Rect(cx + 1, row_y, col_w - 2, row_h)
                self._hit_rects.append((row_rect, category, type_val))

                # Hover highlight
                if row_rect.collidepoint(mouse_pos):
                    pygame.draw.rect(surface, C_HOVER, row_rect, border_radius=2)

                icon_surf  = font(12).render(icon, True, accent)
                name_surf  = font(12).render(name, True, C_TEXT_DIM if count == 0 else C_TEXT)
                count_surf = font(12, bold=True).render(
                    str(count), True, C_SELECTED if count > 0 else C_TEXT_DIM
                )

                surface.blit(icon_surf,  (cx + PADDING, row_y))
                surface.blit(name_surf,  (cx + PADDING + 16, row_y))
                surface.blit(count_surf, (cx + col_w - PADDING - count_surf.get_width(), row_y))

                row_y += row_h
