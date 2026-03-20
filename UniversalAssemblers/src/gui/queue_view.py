"""Queue View — active constructions and task queues.

Accessible via the QUEUE button in the taskbar.
Filterable by system; defaults to the currently viewed system when opened.
Right-click or ESC to close.
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TASKBAR_H, HEADER_H, PADDING,
    C_BG, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_SEP, C_BTN, C_BTN_TXT,
    font,
)
from .widgets import draw_separator, Button

_SECTION_H   = 28   # section heading row height
_GROUP_ROW_H = 20   # location / bot-type grouping row height
_TASK_ROW_H  = 28   # individual task row height
_FILTER_H    = 24
_FILTER_W    = 110
_BAR_W       = 80   # progress bar width


class QueueView:
    """Full-window construction & task queue overlay."""

    def __init__(self, app) -> None:
        self.app       = app
        self.is_active = False

        self._rect = pygame.Rect(0, TASKBAR_H, WINDOW_WIDTH, WINDOW_HEIGHT - TASKBAR_H)

        self._close_btn = Button(
            (self._rect.right - 100, self._rect.y + 8, 90, 26),
            "✕  CLOSE",
            callback=self._close,
            font_size=11,
        )

        self._scroll_y:      int                              = 0
        self._content_h:     int                              = 0
        self._filter_system: str | None                       = None
        self._filter_btns:   list[tuple[pygame.Rect, str | None]] = []

    # ------------------------------------------------------------------
    # Activation

    def activate(self) -> None:
        self.is_active    = True
        self._scroll_y    = 0
        self._filter_btns = []
        sys_ = self.app.selected_system
        self._filter_system = sys_.id if sys_ else None

    def deactivate(self) -> None:
        self.is_active = False

    def _close(self) -> None:
        self.deactivate()

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._close_btn.handle_event(event)

            if event.type == pygame.MOUSEWHEEL:
                visible_h  = self._rect.height - HEADER_H - _FILTER_H - 16
                max_scroll = max(0, self._content_h - visible_h)
                self._scroll_y = max(0, min(max_scroll,
                                            self._scroll_y - event.y * _TASK_ROW_H))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for rect, sys_id in self._filter_btns:
                        if rect.collidepoint(event.pos):
                            self._filter_system = sys_id
                            self._scroll_y = 0
                            break
                elif event.button == 3:
                    self.deactivate()

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, C_BG, self._rect)
        pygame.draw.rect(surface, C_BORDER, self._rect, width=1)

        # Header bar
        hdr_r = pygame.Rect(self._rect.x, self._rect.y, self._rect.width, HEADER_H)
        pygame.draw.rect(surface, C_HEADER, hdr_r)
        hdr_s = font(14, bold=True).render("QUEUE — CONSTRUCTIONS & TASKS", True, C_ACCENT)
        surface.blit(hdr_s, (self._rect.x + PADDING, self._rect.y + 5))
        self._close_btn.draw(surface)

        # Filter tabs
        self._filter_btns = []
        fx = self._rect.x + PADDING
        fy = self._rect.y + HEADER_H + 4
        tabs: list[tuple[str, str | None]] = [("All", None)]
        gs     = self.app.game_state
        galaxy = self.app.galaxy
        if gs and galaxy:
            from ..game_state import DiscoveryState
            for sys_ in galaxy.solar_systems:
                if gs.get_state(sys_.id) in (DiscoveryState.DISCOVERED,
                                              DiscoveryState.COLONIZED):
                    tabs.append((sys_.name[:12], sys_.id))
        for label, sys_id in tabs:
            tb_r = pygame.Rect(fx, fy, _FILTER_W, _FILTER_H)
            sel  = self._filter_system == sys_id
            pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, tb_r, border_radius=3)
            tb_s = font(10, bold=True).render(
                label, True, (0, 0, 0) if sel else C_BTN_TXT
            )
            surface.blit(tb_s, tb_s.get_rect(center=tb_r.center))
            self._filter_btns.append((tb_r, sys_id))
            fx += _FILTER_W + 4
            if fx + _FILTER_W > self._rect.right - PADDING:
                fx = self._rect.x + PADDING
                fy += _FILTER_H + 4

        content_y_start = self._rect.y + HEADER_H + _FILTER_H + 12
        content_rect = pygame.Rect(
            self._rect.x, content_y_start,
            self._rect.width, self._rect.height - (content_y_start - self._rect.y),
        )

        old_clip = surface.get_clip()
        surface.set_clip(content_rect)

        cy      = content_y_start - self._scroll_y
        cx      = self._rect.x + PADDING
        total_h = 0
        any_tasks = False

        if not gs or not galaxy:
            surface.set_clip(old_clip)
            return

        # ── Bot Tasks ──────────────────────────────────────────────────
        bot_section_drawn = False
        for loc_id, bot_type in gs.bot_tasks.all_keys():
            tasks = gs.bot_tasks.get(loc_id, bot_type)
            if not tasks:
                continue
            if self._filter_system and self._loc_to_sys(loc_id) != self._filter_system:
                continue
            any_tasks = True
            if not bot_section_drawn:
                cy, total_h = self._section_hdr(
                    surface, cx, cy, total_h, content_rect,
                    "BOT TASKS", (100, 200, 255),
                )
                bot_section_drawn = True
            loc_name  = self._loc_name(loc_id)
            bot_label = bot_type.replace("_", " ").title()
            cy, total_h = self._group_hdr(
                surface, cx, cy, total_h, content_rect,
                f"  {loc_name}  ›  {bot_label}",
            )
            for task in tasks:
                cy, total_h = self._bot_row(
                    surface, cx, cy, total_h, content_rect, task
                )

        # ── Factory Tasks ──────────────────────────────────────────────
        factory_section_drawn = False
        for loc_id in gs.factory_tasks.all_keys():
            tasks = gs.factory_tasks.get(loc_id)
            if not tasks:
                continue
            if self._filter_system and self._loc_to_sys(loc_id) != self._filter_system:
                continue
            any_tasks = True
            if not factory_section_drawn:
                cy, total_h = self._section_hdr(
                    surface, cx, cy, total_h, content_rect,
                    "FACTORY TASKS", (255, 200, 60),
                )
                factory_section_drawn = True
            cy, total_h = self._group_hdr(
                surface, cx, cy, total_h, content_rect,
                f"  {self._loc_name(loc_id)}",
            )
            for task in tasks:
                cy, total_h = self._factory_row(
                    surface, cx, cy, total_h, content_rect, task
                )

        # ── Shipyard Queue ─────────────────────────────────────────────
        shipyard_section_drawn = False
        for loc_id in gs.shipyard_tasks.all_keys():
            tasks = gs.shipyard_tasks.get(loc_id)
            if not tasks:
                continue
            if self._filter_system and self._loc_to_sys(loc_id) != self._filter_system:
                continue
            any_tasks = True
            if not shipyard_section_drawn:
                cy, total_h = self._section_hdr(
                    surface, cx, cy, total_h, content_rect,
                    "SHIPYARD QUEUE", (180, 130, 255),
                )
                shipyard_section_drawn = True
            cy, total_h = self._group_hdr(
                surface, cx, cy, total_h, content_rect,
                f"  {self._loc_name(loc_id)}",
            )
            for task in tasks:
                cy, total_h = self._shipyard_row(
                    surface, cx, cy, total_h, content_rect, task
                )

        if not any_tasks:
            msg = "No active tasks for the selected filter."
            no_s = font(13).render(msg, True, C_TEXT_DIM)
            surface.blit(no_s, no_s.get_rect(center=(self._rect.centerx,
                                                       content_y_start + 60)))

        self._content_h = total_h

        # Scrollbar
        visible_h = content_rect.height
        if self._content_h > visible_h:
            sb_w    = 6
            sb_x    = self._rect.right - sb_w - 2
            thumb_h = max(20, int(visible_h * visible_h / self._content_h))
            max_sc  = max(1, self._content_h - visible_h)
            thumb_y = content_y_start + int((visible_h - thumb_h) * self._scroll_y / max_sc)
            pygame.draw.rect(surface, (30, 50, 80),
                             pygame.Rect(sb_x, content_y_start, sb_w, visible_h),
                             border_radius=3)
            pygame.draw.rect(surface, (80, 120, 180),
                             pygame.Rect(sb_x, thumb_y, sb_w, thumb_h),
                             border_radius=3)

        surface.set_clip(old_clip)

    # ------------------------------------------------------------------
    # Row helpers — always advance cy/total_h; draw only if in clip rect

    def _section_hdr(
        self, surface, cx, cy, total_h, clip_rect, title, color
    ) -> tuple[int, int]:
        h = _SECTION_H
        if cy >= clip_rect.y - h and cy < clip_rect.bottom:
            draw_separator(surface, cx, cy + h - 3, clip_rect.right - PADDING)
            surface.blit(font(11, bold=True).render(title, True, color), (cx, cy + 5))
        cy += h
        total_h += h
        return cy, total_h

    def _group_hdr(
        self, surface, cx, cy, total_h, clip_rect, label
    ) -> tuple[int, int]:
        h = _GROUP_ROW_H
        if cy >= clip_rect.y - h and cy < clip_rect.bottom:
            surface.blit(font(10).render(label, True, C_TEXT_DIM), (cx + 4, cy + 3))
        cy += h
        total_h += h
        return cy, total_h

    def _bot_row(
        self, surface, cx, cy, total_h, clip_rect, task
    ) -> tuple[int, int]:
        h = _TASK_ROW_H + 2
        if cy >= clip_rect.y - _TASK_ROW_H and cy < clip_rect.bottom:
            row_w = self._rect.width - PADDING * 2 - 8
            row_r = pygame.Rect(cx + 8, cy, row_w, _TASK_ROW_H)
            pygame.draw.rect(surface, (15, 25, 50), row_r, border_radius=2)

            if task.task_type == "mine":
                label = f"Mine  {(task.resource or '').replace('_', ' ').title()}"
            elif task.task_type == "build":
                label = f"Build  {(task.entity_type or '').replace('_', ' ').title()}"
            elif task.task_type == "transport":
                label = f"Transport  {(task.resource or '').replace('_', ' ').title()}"
            else:
                label = task.task_type.title()

            text_col = C_TEXT_DIM if task.complete else C_TEXT
            surface.blit(font(11).render(label, True, text_col), (row_r.x + 6, cy + 7))

            # Progress bar
            bx = cx + 270
            if task.target_amount > 0:
                if task.task_type == "build":
                    frac    = min(1.0, task.built_count / task.target_amount)
                    pg_txt  = f"{task.built_count}/{task.target_amount}"
                else:
                    frac    = min(1.0, task.progress / task.target_amount)
                    pg_txt  = f"{int(task.progress)}/{task.target_amount}"
                pygame.draw.rect(surface, (30, 50, 80), pygame.Rect(bx, cy + 10, _BAR_W, 7))
                if frac > 0:
                    pygame.draw.rect(surface, C_ACCENT,
                                     pygame.Rect(bx, cy + 10, int(_BAR_W * frac), 7))
                surface.blit(font(9).render(pg_txt, True, C_TEXT_DIM),
                             (bx + _BAR_W + 4, cy + 9))

            # Allocation %
            alloc_s = font(10).render(f"{task.allocation}%", True, C_ACCENT)
            surface.blit(alloc_s, (row_r.right - alloc_s.get_width() - 8, cy + 7))

            # Status badge
            if task.complete:
                st_s = font(9, bold=True).render("DONE",   True, (80, 200, 80))
            else:
                st_s = font(9, bold=True).render("ACTIVE", True, (80, 160, 255))
            surface.blit(st_s, (row_r.right - st_s.get_width() - 52, cy + 7))

        cy += h
        total_h += h
        return cy, total_h

    def _factory_row(
        self, surface, cx, cy, total_h, clip_rect, task
    ) -> tuple[int, int]:
        h = _TASK_ROW_H + 2
        if cy >= clip_rect.y - _TASK_ROW_H and cy < clip_rect.bottom:
            row_w = self._rect.width - PADDING * 2 - 8
            row_r = pygame.Rect(cx + 8, cy, row_w, _TASK_ROW_H)
            pygame.draw.rect(surface, (15, 25, 50), row_r, border_radius=2)

            label    = f"Produce  {task.recipe_id.replace('_', ' ').title()}"
            text_col = C_TEXT_DIM if task.complete else C_TEXT
            surface.blit(font(11).render(label, True, text_col), (row_r.x + 6, cy + 7))

            bx = cx + 270
            if task.target_amount > 0:
                frac = min(1.0, task.produced / task.target_amount)
                pygame.draw.rect(surface, (30, 50, 80), pygame.Rect(bx, cy + 10, _BAR_W, 7))
                if frac > 0:
                    pygame.draw.rect(surface, (255, 200, 60),
                                     pygame.Rect(bx, cy + 10, int(_BAR_W * frac), 7))
                surface.blit(
                    font(9).render(f"{task.produced:.0f}/{task.target_amount:.0f}",
                                   True, C_TEXT_DIM),
                    (bx + _BAR_W + 4, cy + 9),
                )
            else:
                surface.blit(font(9).render("continuous", True, C_TEXT_DIM), (bx, cy + 10))

            alloc_s = font(10).render(f"{task.allocation}%", True, (255, 200, 60))
            surface.blit(alloc_s, (row_r.right - alloc_s.get_width() - 8, cy + 7))

        cy += h
        total_h += h
        return cy, total_h

    def _shipyard_row(
        self, surface, cx, cy, total_h, clip_rect, task
    ) -> tuple[int, int]:
        h = _TASK_ROW_H + 2
        if cy >= clip_rect.y - _TASK_ROW_H and cy < clip_rect.bottom:
            row_w = self._rect.width - PADDING * 2 - 8
            row_r = pygame.Rect(cx + 8, cy, row_w, _TASK_ROW_H)
            pygame.draw.rect(surface, (15, 25, 50), row_r, border_radius=2)

            label    = f"Build  {task.ship_type.replace('_', ' ').title()}"
            text_col = C_TEXT_DIM if task.complete else C_TEXT
            surface.blit(font(11).render(label, True, text_col), (row_r.x + 6, cy + 7))

            bx   = cx + 270
            frac = min(1.0, task.built_count / max(1, task.target_count))
            pygame.draw.rect(surface, (30, 50, 80), pygame.Rect(bx, cy + 10, _BAR_W, 7))
            if frac > 0:
                pygame.draw.rect(surface, (180, 130, 255),
                                 pygame.Rect(bx, cy + 10, int(_BAR_W * frac), 7))
            pg_txt = f"{task.built_count}/{task.target_count}"
            surface.blit(font(9).render(pg_txt, True, C_TEXT_DIM),
                         (bx + _BAR_W + 4, cy + 9))
            # Per-ship build progress fraction
            if task.progress > 0 and not task.complete:
                pct_s = font(9).render(f"  ({task.progress * 100:.0f}%)",
                                       True, (180, 130, 255))
                pg_w  = font(9).size(pg_txt)[0]
                surface.blit(pct_s, (bx + _BAR_W + 4 + pg_w, cy + 9))

        cy += h
        total_h += h
        return cy, total_h

    # ------------------------------------------------------------------
    # Location resolution helpers

    def _loc_to_sys(self, location_id: str) -> str | None:
        galaxy = self.app.galaxy
        if not galaxy:
            return None
        for sys_ in galaxy.solar_systems:
            if sys_.id == location_id:
                return sys_.id
            for body in sys_.orbital_bodies:
                if body.id == location_id:
                    return sys_.id
                for moon in body.moons:
                    if moon.id == location_id:
                        return sys_.id
        return None

    def _loc_name(self, location_id: str) -> str:
        galaxy = self.app.galaxy
        if not galaxy:
            return location_id
        for sys_ in galaxy.solar_systems:
            if sys_.id == location_id:
                return f"{sys_.name} (Orbital)"
            for body in sys_.orbital_bodies:
                if body.id == location_id:
                    return body.name
                for moon in body.moons:
                    if moon.id == location_id:
                        return moon.name
        return location_id
