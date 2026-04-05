"""
Objectives View — modal overlay for pending tasks and long-term goals.

Section A: Urgent Tasks — one entry per PendingEvent in gs.pending_events
Section B: Long-term Goals — hardcoded list evaluated against gs each render

Activated by the TASKS button in the taskbar (or via app.open_objectives_view()).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from . import constants as _c
from .constants import (
    C_BG, C_PANEL, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM,
    C_ACCENT, C_WARN, PADDING,
)
from .widgets import Button, draw_panel
from .event_choice_view import EVENT_TITLES, _WARN_MAX

if TYPE_CHECKING:
    from ..game_state import GameState

# ---------------------------------------------------------------------------
# Long-term goals definition
# ---------------------------------------------------------------------------

def _count_dyson_spheres(gs: "GameState") -> int:
    return gs.entity_roster.total("structure", "dyson_sphere")

def _tech_progress(gs: "GameState") -> tuple[int, int]:
    try:
        from ..models.tech import TECH_TREE
        return len(gs.tech.researched), len(TECH_TREE)
    except Exception:
        return 0, 1

def _colonized_progress(gs: "GameState") -> tuple[int, int]:
    try:
        from ..game_state import DiscoveryState
        total    = len(gs._states)
        col = sum(1 for v in gs._states.values()
                  if v in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED))
        return col, total
    except Exception:
        return 0, 1

GOALS: list[dict] = [
    {
        "id":       "dyson_sphere",
        "label":    "Complete Dyson Sphere",
        "check":    lambda gs: _count_dyson_spheres(gs) > 0,
        "progress": lambda gs: (_count_dyson_spheres(gs), 1),
    },
    {
        "id":       "research_all",
        "label":    "Research All Technologies",
        "check":    lambda gs: _tech_progress(gs)[0] >= _tech_progress(gs)[1],
        "progress": _tech_progress,
    },
    {
        "id":       "colonize_all",
        "label":    "Colonize Every System",
        "check":    lambda gs: _colonized_progress(gs)[0] >= _colonized_progress(gs)[1],
        "progress": _colonized_progress,
    },
    {
        "id":       "survive_200",
        "label":    "Survive 200 Years",
        "check":    lambda gs: gs.in_game_years >= 200,
        "progress": lambda gs: (min(int(gs.in_game_years), 200), 200),
    },
]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

_PANEL_W = 520
_PANEL_H = 500
_ROW_H   = 40
_BAR_H   = 8


class ObjectivesView:
    """Full modal overlay — Urgent Tasks + Long-term Goals."""

    def __init__(self, app) -> None:
        self._app = app
        self.is_active: bool = False
        self._scroll_y: int = 0
        self._resolved_goals: set[str] = set()

        self._close_btn: Button | None = None

    # ------------------------------------------------------------------
    # Lifecycle

    def activate(self) -> None:
        self.is_active = True
        self._scroll_y = 0

    def deactivate(self) -> None:
        self.is_active = False

    # ------------------------------------------------------------------
    # Panel rect

    def _rect(self, surface: pygame.Surface) -> pygame.Rect:
        sw, sh = surface.get_size()
        w = _c.scaled(_PANEL_W)
        h = _c.scaled(_PANEL_H)
        x = (sw - w) // 2
        y = _c.scaled(40)  # below taskbar
        return pygame.Rect(x, y, w, min(h, sh - _c.scaled(60)))

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface, gs: "GameState") -> None:
        if not self.is_active:
            return

        r = self._rect(surface)
        PAD = _c.scaled(PADDING)
        HDR_H = _c.scaled(30)
        ROW_H = _c.scaled(_ROW_H)
        BAR_H = _c.scaled(_BAR_H)

        # Background + border
        pygame.draw.rect(surface, _c.C_PANEL, r, border_radius=4)
        pygame.draw.rect(surface, C_BORDER, r, width=1, border_radius=4)

        # Header
        hdr_r = pygame.Rect(r.x, r.y, r.width, HDR_H)
        pygame.draw.rect(surface, C_HEADER, hdr_r, border_radius=4)
        hdr_s = _c.font_scaled(13, bold=True).render("OBJECTIVES", True, C_ACCENT)
        surface.blit(hdr_s, (r.x + PAD, r.y + (HDR_H - hdr_s.get_height()) // 2))

        # Close button
        close_rect = (r.right - _c.scaled(60), r.y + _c.scaled(4),
                      _c.scaled(52), _c.scaled(22))
        if self._close_btn is None:
            self._close_btn = Button(
                rect=close_rect,
                label="CLOSE",
                callback=self.deactivate,
                font_size=_c.scaled(10),
            )
        self._close_btn._rect = pygame.Rect(*close_rect)
        self._close_btn.draw(surface)

        # Clip content area
        content_y = r.y + HDR_H + PAD
        clip_r = pygame.Rect(r.x, content_y, r.width, r.bottom - content_y - PAD)
        surface.set_clip(clip_r)

        cy = content_y - self._scroll_y

        # ---- Section A: Urgent Tasks ----
        sec_s = _c.font_scaled(11, bold=True).render("URGENT TASKS", True, C_WARN)
        surface.blit(sec_s, (r.x + PAD, cy))
        cy += sec_s.get_height() + _c.scaled(4)

        if not gs.pending_events:
            none_s = _c.font_scaled(10).render("No pending threats.", True, C_TEXT_DIM)
            surface.blit(none_s, (r.x + PAD + _c.scaled(8), cy))
            cy += none_s.get_height() + _c.scaled(4)
        else:
            for pe in gs.pending_events:
                row_r = pygame.Rect(r.x + PAD, cy, r.width - PAD * 2, ROW_H)
                pygame.draw.rect(surface, (30, 40, 55), row_r, border_radius=3)
                pygame.draw.rect(surface, C_BORDER, row_r, width=1, border_radius=3)

                title = EVENT_TITLES.get(pe.event_type, pe.event_type.replace("_", " ").upper())
                loc = pe.payload.get("body_id", "")
                if gs.galaxy and loc:
                    for sys in gs.galaxy.solar_systems:
                        for body in sys.orbital_bodies:
                            if body.id == loc:
                                loc = body.name; break
                            for moon in body.moons:
                                if moon.id == loc:
                                    loc = moon.name; break

                lbl_txt = f"\u26a0 {title}" + (f" \u2014 {loc}" if loc else "")
                lbl_s = _c.font_scaled(10, bold=True).render(lbl_txt, True, C_WARN)
                surface.blit(lbl_s, (row_r.x + _c.scaled(4), row_r.y + _c.scaled(3)))

                # Countdown bar
                max_warn = _WARN_MAX.get(pe.event_type, 4.0)
                frac = max(0.0, min(1.0, pe.warn_years_remaining / max_warn))
                bar_bg = pygame.Rect(row_r.x + _c.scaled(4),
                                     row_r.y + ROW_H - BAR_H - _c.scaled(4),
                                     row_r.width - _c.scaled(8), BAR_H)
                bar_fill = pygame.Rect(bar_bg.x, bar_bg.y,
                                       int(bar_bg.width * frac), bar_bg.height)
                bar_col = (
                    (200, 60, 60) if frac < 0.3 else
                    (220, 180, 0) if frac < 0.6 else
                    (60, 180, 60)
                )
                pygame.draw.rect(surface, (20, 30, 40), bar_bg, border_radius=2)
                if bar_fill.width > 0:
                    pygame.draw.rect(surface, bar_col, bar_fill, border_radius=2)
                time_txt = f"{pe.warn_years_remaining:.1f}y remaining"
                time_s = _c.font_scaled(9).render(time_txt, True, C_TEXT_DIM)
                surface.blit(time_s, (bar_bg.right - time_s.get_width() - _c.scaled(2),
                                      bar_bg.y - time_s.get_height()))

                # Click detection for opening EventChoiceView
                if (pygame.mouse.get_pressed()[0]
                        and row_r.collidepoint(pygame.mouse.get_pos())):
                    if hasattr(self._app, "open_event_choice_view"):
                        self._app.open_event_choice_view(pe)

                cy += ROW_H + _c.scaled(4)

        # Separator
        pygame.draw.line(surface, C_BORDER,
                         (r.x + PAD, cy + _c.scaled(2)),
                         (r.right - PAD, cy + _c.scaled(2)))
        cy += _c.scaled(10)

        # ---- Section B: Long-term Goals ----
        goal_s = _c.font_scaled(11, bold=True).render("LONG-TERM GOALS", True, C_ACCENT)
        surface.blit(goal_s, (r.x + PAD, cy))
        cy += goal_s.get_height() + _c.scaled(4)

        for goal in GOALS:
            try:
                done = goal["check"](gs)
                cur, tot = goal["progress"](gs)
            except Exception:
                done, cur, tot = False, 0, 1

            # Award goal once
            if done and goal["id"] not in self._resolved_goals:
                self._resolved_goals.add(goal["id"])
                gs.resolve_goal(goal["id"])

            row_r = pygame.Rect(r.x + PAD, cy, r.width - PAD * 2, ROW_H)
            bg_col = (30, 55, 35) if done else (25, 35, 50)
            pygame.draw.rect(surface, bg_col, row_r, border_radius=3)
            pygame.draw.rect(surface, C_BORDER, row_r, width=1, border_radius=3)

            lbl_col = (80, 220, 100) if done else C_TEXT
            lbl_s = _c.font_scaled(10, bold=True).render(goal["label"], True, lbl_col)
            surface.blit(lbl_s, (row_r.x + _c.scaled(4), row_r.y + _c.scaled(3)))

            if done:
                badge_s = _c.font_scaled(9, bold=True).render("COMPLETE", True, (80, 220, 100))
                surface.blit(badge_s, (row_r.right - badge_s.get_width() - _c.scaled(6),
                                       row_r.y + _c.scaled(3)))

            # Progress bar
            frac = min(1.0, cur / max(tot, 1))
            prog_txt = f"{cur} / {tot}"
            bar_bg = pygame.Rect(row_r.x + _c.scaled(4),
                                 row_r.y + ROW_H - BAR_H - _c.scaled(4),
                                 row_r.width - _c.scaled(8), BAR_H)
            bar_fill = pygame.Rect(bar_bg.x, bar_bg.y,
                                   int(bar_bg.width * frac), bar_bg.height)
            bar_col = (80, 220, 100) if done else (80, 140, 220)
            pygame.draw.rect(surface, (20, 30, 40), bar_bg, border_radius=2)
            if bar_fill.width > 0:
                pygame.draw.rect(surface, bar_col, bar_fill, border_radius=2)
            prog_s = _c.font_scaled(9).render(prog_txt, True, C_TEXT_DIM)
            surface.blit(prog_s, (bar_bg.right - prog_s.get_width() - _c.scaled(2),
                                  bar_bg.y - prog_s.get_height()))

            cy += ROW_H + _c.scaled(4)

        surface.set_clip(None)

        # Scroll arrows (simple — just indicate more content)
        total_content_h = cy - (r.y + HDR_H + PAD) + self._scroll_y
        if total_content_h > clip_r.height:
            arrow_s = _c.font_scaled(10).render("\u25bc scroll", True, C_TEXT_DIM)
            surface.blit(arrow_s, (r.x + PAD, r.bottom - arrow_s.get_height() - _c.scaled(2)))

    # ------------------------------------------------------------------
    # Event handling

    def handle_event(self, ev: pygame.event.Event, gs: "GameState") -> bool:
        if not self.is_active:
            return False

        if self._close_btn:
            self._close_btn.handle_event(ev)

        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.deactivate()
            return True

        if ev.type == pygame.MOUSEWHEEL:
            self._scroll_y = max(0, self._scroll_y - ev.y * _c.scaled(20))
            return True

        return False
