"""
Developer Debug HUD Overlay.

A compact, toggleable panel (F12) anchored to the bottom-right of the window
that shows live runtime state: FPS, tick counter, in-game year, power balance,
and a scrollable log of the last 30 simulation events.

Follows the activate()/deactivate() protocol used by all other overlays.
"""
from __future__ import annotations

import pygame
from . import constants as _c
from .constants import (
    C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    HEADER_H, PADDING, font,
)
from .widgets import Button


class DebugView:
    """Developer debug HUD overlay (F12 to toggle)."""

    def __init__(self, app) -> None:
        self.app = app
        self.is_active = False
        self._scroll_y: int = 0

        self._panel_w  = _c.scaled(420)
        self._panel_h  = _c.scaled(360)
        self._margin   = _c.scaled(8)

        # Anchor panel from bottom-right
        sw, sh = app.screen.get_size()
        px = sw - self._panel_w - self._margin
        py = sh - self._panel_h - self._margin
        self._panel_rect = pygame.Rect(px, py, self._panel_w, self._panel_h)

        self._close_btn = Button(
            (self._panel_rect.right - _c.scaled(80), self._panel_rect.y + _c.scaled(4),
             _c.scaled(72), _c.scaled(22)),
            "✕  CLOSE",
            callback=self.deactivate,
            font_size=int(_c.scaled(10)),
        )

    # ------------------------------------------------------------------
    # Activation protocol

    def activate(self) -> None:
        self.is_active = True
        self._scroll_y = 0
        try:
            from src.logger import get_logger
            get_logger("ua.debug").info("[debug_view] activated")
        except Exception:
            pass

    def deactivate(self) -> None:
        self.is_active = False

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._close_btn.handle_event(event)
            if event.type == pygame.MOUSEWHEEL:
                if self._panel_rect.collidepoint(pygame.mouse.get_pos()):
                    self._scroll_y = max(0, self._scroll_y - event.y * 14)

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        sw, sh = surface.get_size()
        px = sw - self._panel_w - self._margin
        py = sh - self._panel_h - self._margin
        self._panel_rect = pygame.Rect(px, py, self._panel_w, self._panel_h)
        self._close_btn.rect = pygame.Rect(
            self._panel_rect.right - _c.scaled(80),
            self._panel_rect.y + _c.scaled(4),
            _c.scaled(72),
            _c.scaled(22),
        )
        r = self._panel_rect

        # Panel background
        bg = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
        bg.fill((5, 8, 20, 230))
        surface.blit(bg, r.topleft)
        pygame.draw.rect(surface, C_BORDER, r, width=1)

        # --- Header ---
        hdr_r = pygame.Rect(r.x, r.y, r.width, HEADER_H)
        pygame.draw.rect(surface, C_HEADER, hdr_r)
        hdr_s = font(12, bold=True).render("DEBUG HUD   [F12 to close]", True, C_ACCENT)
        surface.blit(hdr_s, (r.x + PADDING, r.y + 5))
        self._close_btn.draw(surface)

        cy = r.y + HEADER_H + 6

        # --- Performance strip ---
        gs = self.app.game_state
        if gs:
            fps = int(self.app.clock.get_fps())
            perf_txt = f"FPS: {fps}   TICK: {gs.tick_count}   YEAR: {gs.in_game_years:.2f}"
        else:
            perf_txt = "FPS: ---   TICK: ---   YEAR: ---"
        perf_s = font(11, bold=True).render(perf_txt, True, C_TEXT)
        surface.blit(perf_s, (r.x + PADDING, cy))
        cy += 18

        # Separator
        pygame.draw.line(surface, C_BORDER, (r.x + PADDING, cy), (r.right - PADDING, cy))
        cy += 4

        # --- Power balance strip ---
        if gs:
            total_prod, total_cons = self._compute_power(gs)
            net = total_prod - total_cons
            net_col = (80, 220, 100) if net >= 0 else (255, 80, 80)
            pwr_txt = f"Power  Prod: +{total_prod:,.0f}   Cons: -{total_cons:,.0f}   Net: {net:+,.0f}"
            pwr_s = font(11).render(pwr_txt, True, net_col)
        else:
            pwr_s = font(11).render("Power: no game active", True, C_TEXT_DIM)
        surface.blit(pwr_s, (r.x + PADDING, cy))
        cy += 18

        # Separator
        pygame.draw.line(surface, C_BORDER, (r.x + PADDING, cy), (r.right - PADDING, cy))
        cy += 6

        # --- Sim-event log header ---
        log_lbl = font(10, bold=True).render("SIM EVENTS (last 30):", True, C_TEXT_DIM)
        surface.blit(log_lbl, (r.x + PADDING, cy))
        cy += 16

        # --- Scrollable event log ---
        log_rect = pygame.Rect(r.x + PADDING, cy, r.width - PADDING * 2, r.bottom - cy - 4)
        old_clip = surface.get_clip()
        surface.set_clip(log_rect)

        entries = gs.debug_event_log if gs else []
        line_h = 14
        draw_y = log_rect.y - self._scroll_y
        for entry in entries:
            if draw_y + line_h >= log_rect.y and draw_y < log_rect.bottom:
                # Truncate to fit panel width
                max_chars = (log_rect.width - 4) // 6
                txt = entry if len(entry) <= max_chars else entry[:max_chars - 1] + "…"
                entry_s = font(10).render(txt, True, C_TEXT_DIM)
                surface.blit(entry_s, (log_rect.x + 2, draw_y))
            draw_y += line_h

        surface.set_clip(old_clip)

        # Scrollbar
        content_h = len(entries) * line_h
        visible_h = log_rect.height
        if content_h > visible_h:
            # Clamp scroll
            max_scroll = content_h - visible_h
            self._scroll_y = min(self._scroll_y, max_scroll)
            sb_x = r.right - 6
            sb_h = visible_h
            thumb_h = max(20, int(sb_h * visible_h / content_h))
            thumb_y = log_rect.y + int((sb_h - thumb_h) * self._scroll_y / max(1, max_scroll))
            pygame.draw.rect(surface, (30, 50, 80),
                             pygame.Rect(sb_x, log_rect.y, 5, sb_h), border_radius=2)
            pygame.draw.rect(surface, C_ACCENT,
                             pygame.Rect(sb_x, thumb_y, 5, thumb_h), border_radius=2)

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _compute_power(gs) -> tuple[float, float]:
        """Return (total_prod, total_cons) across all entity roster entries."""
        try:
            from ..models.entity import compute_energy_balance
        except Exception:
            return 0.0, 0.0

        if not gs.galaxy:
            return 0.0, 0.0

        total_prod = 0.0
        total_cons = 0.0
        for sys in gs.galaxy.solar_systems:
            from ..game_state import DiscoveryState
            if gs.get_state(sys.id) not in (
                DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED
            ):
                continue
            for body in sys.orbital_bodies:
                p, c = compute_energy_balance(gs, body.id)
                total_prod += p
                total_cons += c
                for moon in body.moons:
                    p2, c2 = compute_energy_balance(gs, moon.id)
                    total_prod += p2
                    total_cons += c2

        return total_prod, total_cons
