"""
Energy Overview overlay.

Full-window panel (below taskbar) showing energy production/consumption
for every body in the galaxy that has any power plants or consumers.

Activated via App.open_energy_view() / taskbar "⚡ ENERGY" button.
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TASKBAR_H, HEADER_H, ROW_H, PADDING,
    C_PANEL, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_SELECTED, C_HOVER, C_WARN, C_SEP, C_BTN, C_BTN_HOV, C_BTN_TXT,
    C_BG,
    font,
)
from .widgets import draw_panel, draw_separator, Button

_BODY_ROW_H   = 28
_SUBROW_H     = 20
_FILTER_BTN_H = 24
_FILTER_BTN_W = 110


class EnergyView:
    """Full-window energy overview overlay."""

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

        self._scroll_y:   int       = 0
        self._content_h:  int       = 0
        self._filter_system: str | None = None   # None = All
        # list of (rect, sys_id_or_None) for filter tabs
        self._filter_btns: list[tuple[pygame.Rect, str | None]] = []

    # ------------------------------------------------------------------
    # Activation

    def activate(self) -> None:
        self.is_active       = True
        self._scroll_y       = 0
        self._filter_system  = None
        self._filter_btns    = []

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
                visible_h = self._rect.height - HEADER_H - _FILTER_BTN_H - 16
                max_scroll = max(0, self._content_h - visible_h)
                self._scroll_y = max(0, min(max_scroll, self._scroll_y - event.y * _BODY_ROW_H))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, sys_id in self._filter_btns:
                    if rect.collidepoint(event.pos):
                        self._filter_system = sys_id
                        self._scroll_y = 0
                        break

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        # Background
        pygame.draw.rect(surface, C_BG, self._rect)
        pygame.draw.rect(surface, C_BORDER, self._rect, width=1)

        # Header bar
        hdr_r = pygame.Rect(self._rect.x, self._rect.y, self._rect.width, HEADER_H)
        pygame.draw.rect(surface, C_HEADER, hdr_r)
        hdr_s = font(14, bold=True).render("⚡ ENERGY OVERVIEW", True, C_ACCENT)
        surface.blit(hdr_s, (self._rect.x + PADDING, self._rect.y + 5))
        self._close_btn.draw(surface)

        # Filter tabs
        self._filter_btns = []
        fx = self._rect.x + PADDING
        fy = self._rect.y + HEADER_H + 4
        tabs: list[tuple[str, str | None]] = [("All", None)]
        gs = self.app.game_state
        galaxy = self.app.galaxy
        if gs and galaxy:
            from ..game_state import DiscoveryState
            for sys in galaxy.solar_systems:
                if gs.get_state(sys.id) in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                    tabs.append((sys.name[:12], sys.id))
        for label, sys_id in tabs:
            tb_r = pygame.Rect(fx, fy, _FILTER_BTN_W, _FILTER_BTN_H)
            sel = self._filter_system == sys_id
            pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, tb_r, border_radius=3)
            tb_s = font(10, bold=True).render(label, True, (0, 0, 0) if sel else C_BTN_TXT)
            surface.blit(tb_s, tb_s.get_rect(center=tb_r.center))
            self._filter_btns.append((tb_r, sys_id))
            fx += _FILTER_BTN_W + 4
            if fx + _FILTER_BTN_W > self._rect.right - PADDING:
                fx = self._rect.x + PADDING
                fy += _FILTER_BTN_H + 4

        content_y_start = self._rect.y + HEADER_H + _FILTER_BTN_H + 12
        content_rect = pygame.Rect(
            self._rect.x, content_y_start,
            self._rect.width, self._rect.height - (content_y_start - self._rect.y)
        )

        # Set clip for scrollable content
        old_clip = surface.get_clip()
        surface.set_clip(content_rect)

        cy = content_y_start - self._scroll_y
        cx = self._rect.x + PADDING

        if not gs or not galaxy:
            surface.set_clip(old_clip)
            return

        from ..models.entity import (
            compute_energy_balance, POWER_PLANT_SPECS, StructureType,
            compute_power_modifier,
        )

        total_content_h = 0

        # Gather systems to display
        systems_to_show = []
        for sys in galaxy.solar_systems:
            if self._filter_system is not None and sys.id != self._filter_system:
                continue
            from ..game_state import DiscoveryState
            if gs.get_state(sys.id) not in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                continue
            systems_to_show.append(sys)

        for sys in systems_to_show:
            # Collect all bodies with energy activity
            active_bodies = []
            all_bodies = []
            for body in sys.orbital_bodies:
                all_bodies.append(body)
                for moon in body.moons:
                    all_bodies.append(moon)

            sys_total_prod = 0.0
            sys_total_cons = 0.0
            body_rows: list[tuple] = []   # (body, prod, cons, offline_plants, subrows_h)

            for body in all_bodies:
                prod, cons = compute_energy_balance(gs, body.id)
                sys_total_prod += prod
                sys_total_cons += cons
                if prod == 0.0 and cons == 0.0:
                    continue

                # Find offline plants
                offline_plants: list[str] = []
                for struct_type, spec in POWER_PLANT_SPECS.items():
                    flag_key = f"{body.id}:{struct_type.value}"
                    if not gs.power_plant_active.get(flag_key, True):
                        # Check if there's actually such a plant here
                        has_plant = any(
                            i.type_value == struct_type.value
                            for i in gs.entity_roster.at(body.id)
                            if i.category == "structure"
                        )
                        if has_plant:
                            offline_plants.append(struct_type.value)

                subrow_count = len(offline_plants)
                total_row_h = _BODY_ROW_H + subrow_count * _SUBROW_H
                body_rows.append((body, prod, cons, offline_plants, total_row_h))

            if not body_rows:
                continue

            # System summary header
            sys_net = sys_total_prod - sys_total_cons
            sys_col = (80, 220, 100) if sys_net >= 0 else (255, 80, 80)
            if cy >= content_y_start - 20 and cy < content_rect.bottom:
                draw_separator(surface, cx, cy, self._rect.right - PADDING)
                sys_lbl = font(11, bold=True).render(
                    f"SYSTEM: {sys.name}   Prod: +{sys_total_prod:,.0f}   "
                    f"Cons: -{sys_total_cons:,.0f}   Net: {sys_net:+,.0f}",
                    True, sys_col,
                )
                surface.blit(sys_lbl, (cx, cy + 2))
            cy += 18
            total_content_h += 18

            for body, prod, cons, offline_plants, row_h in body_rows:
                throttle = min(1.0, prod / max(cons, 1e-9)) if cons > 0 else 1.0
                net = prod - cons
                row_col = (80, 220, 100) if net >= 0 else (255, 80, 80)
                throttle_pct = int(throttle * 100)
                throttle_col = C_ACCENT if throttle >= 1.0 else C_WARN

                if cy >= content_y_start - _BODY_ROW_H and cy < content_rect.bottom:
                    # Body row
                    row_r = pygame.Rect(cx, cy, self._rect.width - PADDING * 2, _BODY_ROW_H)
                    pygame.draw.rect(surface, (15, 25, 50), row_r, border_radius=2)

                    body_name_s = font(11, bold=True).render(
                        f"● {body.name}", True, C_TEXT
                    )
                    surface.blit(body_name_s, (cx + 6, cy + 6))

                    # Energy stats right-aligned
                    stats_s = font(10).render(
                        f"Prod: +{prod:,.0f}  |  Cons: -{cons:,.0f}  |  Net: {net:+,.0f}",
                        True, C_TEXT_DIM,
                    )
                    surface.blit(stats_s, (cx + 180, cy + 6))

                    thr_s = font(10, bold=True).render(
                        f"Throttle: {throttle_pct}%", True, throttle_col
                    )
                    surface.blit(thr_s, (self._rect.right - PADDING - thr_s.get_width() - 4, cy + 6))

                    # Net color bar
                    bar_w = max(0, min(80, int(80 * min(throttle, 1.0))))
                    pygame.draw.rect(surface, (30, 50, 80), pygame.Rect(cx + 6, cy + 22, 80, 4))
                    if bar_w > 0:
                        pygame.draw.rect(surface, row_col, pygame.Rect(cx + 6, cy + 22, bar_w, 4))

                cy += _BODY_ROW_H

                # Offline plant sub-rows
                for plant_tv in offline_plants:
                    if cy >= content_y_start - _SUBROW_H and cy < content_rect.bottom:
                        warn_s = font(10).render(
                            f"  ⚠ {plant_tv.replace('_',' ').title()} OFFLINE (fuel depleted)",
                            True, (220, 80, 80),
                        )
                        surface.blit(warn_s, (cx + 16, cy + 2))
                    cy += _SUBROW_H

                total_content_h += row_h

            cy += 4
            total_content_h += 4

        self._content_h = total_content_h

        # Scrollbar
        visible_h = content_rect.height
        if self._content_h > visible_h:
            sb_w   = 6
            sb_x   = self._rect.right - sb_w - 2
            sb_y   = content_y_start
            sb_h   = visible_h
            thumb_h = max(20, int(sb_h * visible_h / self._content_h))
            max_scroll = max(1, self._content_h - visible_h)
            thumb_y = sb_y + int((sb_h - thumb_h) * self._scroll_y / max_scroll)
            pygame.draw.rect(surface, (30, 50, 80), pygame.Rect(sb_x, sb_y, sb_w, sb_h), border_radius=3)
            pygame.draw.rect(surface, (80, 120, 180), pygame.Rect(sb_x, thumb_y, sb_w, thumb_h), border_radius=3)

        surface.set_clip(old_clip)
