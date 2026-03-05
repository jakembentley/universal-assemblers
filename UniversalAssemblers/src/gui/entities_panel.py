"""
Bottom panel: player entities.

Three columns — Structures | Bots | Ships — with counts read live from
GameState.entity_roster.  Each column lists every known entity type; a
count of 0 is shown dimly for types not yet built.
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, ENT_H, TOP_H, HEADER_H, PADDING, ROW_H,
    C_PANEL, C_BORDER, C_HEADER, C_ACCENT, C_TEXT, C_TEXT_DIM,
    C_SEP, C_SELECTED, font,
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
        self.rect = pygame.Rect(0, TOP_H, WINDOW_WIDTH, ENT_H)

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        pass  # entity click → entity view (not yet implemented)

    def draw(self, surface: pygame.Surface) -> None:
        content = draw_panel(surface, self.rect, "Player Entities")
        roster  = (
            self.app.game_state.entity_roster
            if self.app.game_state else None
        )

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

                icon_surf  = font(12).render(icon, True, accent)
                name_surf  = font(12).render(name, True, C_TEXT_DIM if count == 0 else C_TEXT)
                count_surf = font(12, bold=True).render(
                    str(count), True, C_SELECTED if count > 0 else C_TEXT_DIM
                )

                surface.blit(icon_surf,  (cx + PADDING, row_y))
                surface.blit(name_surf,  (cx + PADDING + 16, row_y))
                surface.blit(count_surf, (cx + col_w - PADDING - count_surf.get_width(), row_y))

                row_y += row_h
