"""
Tutorial overlay panel.

Displayed in the bottom-left corner of the game screen when tutorial mode
is active.  Shows the current step title, body text, NEXT button, and a
SKIP TUTORIAL link.
"""
from __future__ import annotations

import pygame
from . import constants as _c
from .constants import (
    C_PANEL, C_BORDER, C_ACCENT, C_TEXT, C_TEXT_DIM, C_BTN, C_BTN_TXT,
    PADDING, font,
)
from ..tutorial import STEPS


_PANEL_W  = 360
_PANEL_H  = 230
_MARGIN_X = 12
_MARGIN_Y = 12


class TutorialOverlay:
    """Draws the tutorial step card and handles NEXT / SKIP clicks."""

    def __init__(self, app) -> None:
        self.app = app
        self._next_r: pygame.Rect | None = None
        self._skip_r: pygame.Rect | None = None

    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        tm = self.app.tutorial
        if not tm.enabled or tm.complete:
            return
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self._next_r and self._next_r.collidepoint(pos):
                    tm.next_step()
                    return
                if self._skip_r and self._skip_r.collidepoint(pos):
                    tm.skip()
                    return

    def draw(self, surface: pygame.Surface) -> None:
        tm = self.app.tutorial
        step = tm.current_step
        if step is None:
            return

        # Panel anchored bottom-left
        sx = _MARGIN_X
        sy = _c.WINDOW_HEIGHT - _PANEL_H - _c.TASKBAR_H - _MARGIN_Y

        panel = pygame.Rect(sx, sy, _PANEL_W, _PANEL_H)
        panel_surf = pygame.Surface((_PANEL_W, _PANEL_H), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (8, 16, 36, 220), panel_surf.get_rect(), border_radius=6)
        surface.blit(panel_surf, (sx, sy))
        pygame.draw.rect(surface, C_ACCENT, panel, 1, border_radius=6)

        # Step counter badge
        total   = len(STEPS)
        badge   = font(10, bold=True).render(
            f"TUTORIAL  {tm.step_idx + 1}/{total}", True, C_ACCENT
        )
        surface.blit(badge, (sx + PADDING, sy + 6))

        # Title
        title_s = font(13, bold=True).render(step.title, True, (200, 230, 255))
        surface.blit(title_s, (sx + PADDING, sy + 22))

        # Body (word-wrap at ~48 chars)
        bx = sx + PADDING
        by = sy + 40
        body_bottom = sy + _PANEL_H - 38
        clip_prev = surface.get_clip()
        surface.set_clip(pygame.Rect(sx, sy + 40, _PANEL_W, _PANEL_H - 78))
        for raw_line in step.body.split("\n"):
            words = raw_line.split()
            if not words:
                by += 14
                continue
            line = ""
            for word in words:
                test = (line + " " + word).strip()
                if font(11).size(test)[0] <= _PANEL_W - PADDING * 2:
                    line = test
                else:
                    if line:
                        surface.blit(font(11).render(line, True, C_TEXT_DIM), (bx, by))
                        by += 14
                    line = word
            if line:
                surface.blit(font(11).render(line, True, C_TEXT_DIM), (bx, by))
                by += 14
        surface.set_clip(clip_prev)

        # NEXT button
        next_label = "FINISH" if tm.step_idx >= len(STEPS) - 1 else "NEXT  ▶"
        next_r = pygame.Rect(sx + _PANEL_W - 90, sy + _PANEL_H - 34, 80, 26)
        mouse  = pygame.mouse.get_pos()
        nb_col = (0, 100, 60) if next_r.collidepoint(mouse) else (0, 80, 50)
        pygame.draw.rect(surface, nb_col, next_r, border_radius=4)
        pygame.draw.rect(surface, C_ACCENT, next_r, 1, border_radius=4)
        nl = font(12, bold=True).render(next_label, True, (180, 255, 200))
        surface.blit(nl, nl.get_rect(center=next_r.center))
        self._next_r = next_r

        # SKIP TUTORIAL link
        skip_s = font(10).render("skip tutorial", True, (80, 100, 120))
        skip_r = pygame.Rect(sx + PADDING, sy + _PANEL_H - 28, skip_s.get_width(), 18)
        if skip_r.collidepoint(mouse):
            skip_s = font(10).render("skip tutorial", True, (160, 180, 200))
        surface.blit(skip_s, (skip_r.x, skip_r.y))
        self._skip_r = skip_r
