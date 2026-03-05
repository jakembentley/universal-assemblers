"""
Bottom panel: player entities (stub data).

Divided into three columns: Structures | Bots | Ships.
All counts are zero for now; this panel is wired up and ready for live data.
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, ENT_H, TOP_H, HEADER_H, PADDING, ROW_H,
    C_PANEL, C_BORDER, C_HEADER, C_ACCENT, C_TEXT, C_TEXT_DIM,
    C_SEP, C_SELECTED, C_WARN, font,
)
from .widgets import draw_panel, draw_separator


# Stub entity definitions: (display_name, icon, count)
_STRUCTURES = [
    ("Extractor",    "⬡", 0),
    ("Smelter",      "⬡", 0),
    ("Factory",      "⬡", 0),
    ("Shipyard",     "⬡", 0),
    ("Power Plant",  "⬡", 0),
    ("Storage Hub",  "⬡", 0),
]

_BOTS = [
    ("Worker Bot",    "◈", 0),
    ("Constructor",   "◈", 0),
    ("Scout Drone",   "◈", 0),
    ("Soldier Bot",   "◈", 0),
    ("Harvester",     "◈", 0),
]

_SHIPS = [
    ("Probe",         "▷", 0),
    ("Transport",     "▷", 0),
    ("Constructor",   "▷", 0),
    ("Warship",       "▷", 0),
]

_COLUMNS = [
    ("Structures", _STRUCTURES, C_ACCENT),
    ("Bots",       _BOTS,       (130, 200, 130)),
    ("Ships",      _SHIPS,      (200, 160, 255)),
]


class EntitiesPanel:

    def __init__(self, app) -> None:
        self.app  = app
        self.rect = pygame.Rect(0, TOP_H, WINDOW_WIDTH, ENT_H)

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        pass   # placeholder — will forward clicks when entities have actions

    def draw(self, surface: pygame.Surface) -> None:
        content = draw_panel(surface, self.rect, "Player Entities")

        col_w   = content.width // len(_COLUMNS)
        row_h   = ROW_H - 2

        for ci, (title, items, accent) in enumerate(_COLUMNS):
            cx = content.x + ci * col_w
            cy = content.y

            # Column header
            total  = sum(v for _, _, v in items)
            header = font(12, bold=True).render(
                f"{title.upper()}  ({total})", True, accent
            )
            surface.blit(header, (cx + PADDING, cy + 4))

            # Separator under column header
            draw_separator(surface, cx + PADDING, cy + 22, cx + col_w - PADDING)

            # Vertical divider between columns
            if ci > 0:
                pygame.draw.line(surface, C_SEP, (cx, content.y), (cx, content.bottom), 1)

            # Rows
            row_y = cy + 26
            for name, icon, count in items:
                if row_y + row_h > content.bottom:
                    break

                icon_surf  = font(12).render(icon, True, accent)
                name_surf  = font(12).render(name, True, C_TEXT_DIM)
                count_surf = font(12, bold=True).render(
                    str(count), True, C_SELECTED if count > 0 else C_TEXT_DIM
                )

                surface.blit(icon_surf,  (cx + PADDING, row_y))
                surface.blit(name_surf,  (cx + PADDING + 16, row_y))
                surface.blit(count_surf, (cx + col_w - PADDING - count_surf.get_width(), row_y))

                row_y += row_h

        # Stub notice
        note = font(10).render(
            "[stub — entity model not yet implemented]", True, (40, 60, 90)
        )
        surface.blit(
            note,
            (content.right - note.get_width() - PADDING, content.bottom - note.get_height() - 4),
        )
