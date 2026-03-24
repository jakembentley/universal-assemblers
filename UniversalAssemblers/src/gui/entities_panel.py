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
    ("extractor",                "Extractor",          "⬡"),
    ("factory",                  "Factory",            "⬡"),
    ("power_plant_solar",        "Solar Plant",        "⬡"),
    ("power_plant_wind",         "Wind Plant",         "⬡"),
    ("power_plant_bios",         "Bio Plant",          "⬡"),
    ("power_plant_fossil",       "Fossil Plant",       "⬡"),
    ("power_plant_nuclear",      "Nuclear Plant",      "⬡"),
    ("power_plant_cold_fusion",  "Cold Fusion",        "⬡"),
    ("power_plant_dark_matter",  "Dark Matter",        "⬡"),
    ("research_array",           "Research Array",     "⬡"),
    ("replicator",               "Replicator",         "⬡"),
    ("shipyard",                 "Shipyard",           "⬡"),
    ("storage_hub",              "Storage Hub",        "⬡"),
]

_BOT_TYPES: list[tuple[str, str, str]] = [
    ("logistic_bot", "Logistic Bot", "◈"),
    ("harvester",    "Harvester",    "◈"),
    ("miner",        "Miner Bot",    "◈"),
    ("constructor",  "Constructor",  "◈"),
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
            if event.type == pygame.MOUSEMOTION:
                if self.rect.collidepoint(event.pos):
                    hit = next(
                        ((cat, tv) for r, cat, tv in self._hit_rects
                         if r.collidepoint(event.pos)),
                        None,
                    )
                    if hit:
                        cat, tv = hit
                        lines = self._build_entity_tooltip(cat, tv)
                        self.app.tooltip.set_hover(f"ent:{tv}", lines, event.pos)
                    else:
                        self.app.tooltip.clear_hover()
                else:
                    self.app.tooltip.clear_hover()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, category, type_val in self._hit_rects:
                    if rect.collidepoint(event.pos):
                        sys    = self.app.selected_system
                        sys_id = sys.id if sys else None
                        body_id = self.app.selected_body_id
                        if category == "bot" and body_id is None:
                            self.app.show_toast("Select a planet first")
                            return
                        if category == "ship":
                            body_id = None
                            # Open entity view at the system where ships actually are.
                            # Prefer the currently selected system; fall back to the
                            # first system that has at least one of this ship type.
                            gs = self.app.game_state
                            if gs:
                                if not any(
                                    i.type_value == type_val and i.category == "ship"
                                    for i in gs.entity_roster.at(sys_id or "")
                                ):
                                    for inst in gs.entity_roster.by_category("ship"):
                                        if inst.type_value == type_val:
                                            sys_id = inst.location_id
                                            break
                        self.app.open_entity_view(category, type_val, sys_id, body_id)
                        return

    def draw(self, surface: pygame.Surface) -> None:
        content = draw_panel(surface, self.rect, "Player Entities")
        roster  = (
            self.app.game_state.entity_roster
            if self.app.game_state else None
        )

        sys     = self.app.selected_system
        sys_id  = sys.id if sys else None
        body_id = self.app.selected_body_id

        self._hit_rects = []
        mouse_pos = pygame.mouse.get_pos()
        col_w = content.width // len(_COLUMNS)
        row_h = ROW_H - 2

        for ci, (title, category, types, accent) in enumerate(_COLUMNS):
            cx = content.x + ci * col_w
            cy = content.y

            # Column total (global) and at-location count
            col_total = (
                sum(roster.total(category, tv) for tv, _, _ in types)
                if roster else 0
            )
            # Location used for "here" count
            if category == "ship":
                here_loc = sys_id
            else:
                here_loc = body_id or sys_id
            col_here = (
                sum(
                    sum(i.count for i in roster.at(here_loc or "")
                        if i.category == category and i.type_value == tv)
                    for tv, _, _ in types
                )
                if roster and here_loc else 0
            )
            header_txt = f"{title.upper()}  ({col_here} here / {col_total} total)"
            header = font(11, bold=True).render(header_txt, True, accent)
            surface.blit(header, (cx + PADDING, cy + 4))

            draw_separator(surface, cx + PADDING, cy + 22, cx + col_w - PADDING)

            if ci > 0:
                pygame.draw.line(surface, C_SEP, (cx, content.y), (cx, content.bottom), 1)

            row_y = cy + 26
            for type_val, name, icon in types:
                if row_y + row_h > content.bottom:
                    break

                # "here" count at current location; global total for dim/bright logic
                here_count = (
                    sum(i.count for i in roster.at(here_loc or "")
                        if i.category == category and i.type_value == type_val)
                    if roster and here_loc else 0
                )
                total_count = roster.total(category, type_val) if roster else 0

                row_rect = pygame.Rect(cx + 1, row_y, col_w - 2, row_h)
                self._hit_rects.append((row_rect, category, type_val))

                if row_rect.collidepoint(mouse_pos) and total_count > 0:
                    pygame.draw.rect(surface, C_HOVER, row_rect, border_radius=2)

                icon_surf = font(12).render(icon, True, accent)
                name_surf = font(12).render(
                    name, True, C_TEXT_DIM if total_count == 0 else C_TEXT
                )
                # Show "here / total" when they differ; otherwise just the here count
                if total_count > here_count and total_count > 0:
                    count_txt = f"{here_count}/{total_count}"
                    count_col = C_TEXT_DIM if here_count == 0 else C_SELECTED
                else:
                    count_txt = str(here_count)
                    count_col = C_SELECTED if here_count > 0 else C_TEXT_DIM
                count_surf = font(11, bold=True).render(count_txt, True, count_col)

                surface.blit(icon_surf,  (cx + PADDING, row_y))
                surface.blit(name_surf,  (cx + PADDING + 16, row_y))
                surface.blit(count_surf, (cx + col_w - PADDING - count_surf.get_width(), row_y))

                row_y += row_h

    # ------------------------------------------------------------------
    # Tooltip helper

    _ENTITY_DESCS: dict[str, str] = {
        "extractor":                 "Mines raw minerals, ice and gas from deposits.",
        "factory":                   "Manufactures electronics, alloys and components.",
        "power_plant_solar":         "Generates clean energy from stellar radiation.",
        "power_plant_wind":          "Generates energy from atmospheric winds.",
        "power_plant_bios":          "Burns biological material for energy.",
        "power_plant_fossil":        "Burns fossil fuels; resource depletes over time.",
        "power_plant_nuclear":       "Splits atomic nuclei for abundant power.",
        "power_plant_cold_fusion":   "Fusion at ambient temperatures — no fuel consumed.",
        "power_plant_dark_matter":   "Harnesses exotic dark matter interactions.",
        "research_array":            "Generates research points for tech unlocks.",
        "replicator":                "Autonomously self-replicates new structures.",
        "shipyard":                  "Constructs and launches spacecraft.",
        "storage_hub":               "Stores accumulated resources on-site.",
        "miner":                     "Extracts minerals, ice and gas from surface.",
        "constructor":               "Builds structures and other entities on order.",
        "logistic_bot":              "Transports resources between bodies.",
        "harvester":                 "Harvests biological resources.",
        "probe":                     "Explores and reveals unknown star systems.",
        "drop_ship":                 "Delivers constructor + miner bots to a target.",
        "mining_vessel":             "Extracts resources from remote bodies.",
        "transport":                 "Ferries resources between star systems.",
        "warship":                   "Combat vessel for hostile encounters.",
    }

    def _build_entity_tooltip(
        self, category: str, type_val: str
    ) -> list[tuple[str, tuple]]:
        from .constants import C_ACCENT, C_TEXT_DIM, C_WARN
        gs      = self.app.game_state
        sys_    = self.app.selected_system
        body_id = self.app.selected_body_id

        name = type_val.replace("_", " ").title()
        # Use the display name from the column registry if available
        for _, cat, types, _ in _COLUMNS:
            if cat == category:
                for tv, n, _ in types:
                    if tv == type_val:
                        name = n
                        break

        lines: list[tuple[str, tuple]] = []
        lines.append((name, C_ACCENT))

        desc = self._ENTITY_DESCS.get(type_val)
        if desc:
            lines.append((desc, C_TEXT_DIM))

        if gs:
            total = gs.entity_roster.total(category, type_val)
            if category == "ship":
                here_loc = sys_.id if sys_ else None
            else:
                here_loc = body_id or (sys_.id if sys_ else None)
            here = (
                sum(i.count for i in gs.entity_roster.at(here_loc or "")
                    if i.category == category and i.type_value == type_val)
                if here_loc else 0
            )
            lines.append((f"Here: {here}   Total: {total}", C_TEXT_DIM))

            # Energy consumption
            from ..models.entity import ENERGY_CONSUMPTION
            ec = ENERGY_CONSUMPTION.get(type_val, 0.0)
            if ec > 0:
                lines.append((f"Energy: -{ec:.0f} / yr", C_WARN))

        return lines
