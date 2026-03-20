"""Floating tooltip rendered near the mouse cursor.

Usage (any view that has access to app):
    # While something is hovered:
    app.tooltip.set_hover(unique_id, lines, mouse_pos)
    # When nothing is hovered:
    app.tooltip.clear_hover()

`lines` is a list of (text: str, color: tuple) pairs.
`unique_id` can be any hashable — used to detect hover-target changes and
reset the delay timer.
"""
from __future__ import annotations

import pygame
from .constants import C_BORDER, font

_DELAY_MS = 420   # ms before the tooltip appears
_PAD      = 8
_LINE_H   = 18
_MAX_W    = 300


class Tooltip:

    def __init__(self) -> None:
        self._hover_id:    object                  = None
        self._hover_since: int                     = 0
        self._lines:       list[tuple[str, tuple]] = []
        self._pos:         tuple[int, int]         = (0, 0)

    # ------------------------------------------------------------------

    def set_hover(
        self,
        hover_id: object,
        lines: list[tuple[str, tuple]],
        pos: tuple[int, int],
    ) -> None:
        """Register the currently hovered target.  Call every frame while hovering."""
        now = pygame.time.get_ticks()
        if hover_id != self._hover_id:
            self._hover_id    = hover_id
            self._hover_since = now
        self._lines = lines
        self._pos   = pos

    def clear_hover(self) -> None:
        self._hover_id = None
        self._lines    = []

    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        if not self._hover_id or not self._lines:
            return
        if now - self._hover_since < _DELAY_MS:
            return

        rendered = [font(11).render(text, True, color) for text, color in self._lines]
        if not rendered:
            return

        w = min(_MAX_W, max(s.get_width() for s in rendered) + _PAD * 2)
        h = len(rendered) * _LINE_H + _PAD * 2

        from .constants import WINDOW_WIDTH, WINDOW_HEIGHT
        mx, my = self._pos
        tx = mx + 16
        ty = my + 16
        if tx + w > WINDOW_WIDTH - 4:
            tx = mx - w - 8
        if ty + h > WINDOW_HEIGHT - 4:
            ty = my - h - 8

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((6, 10, 26, 225))
        surface.blit(bg, (tx, ty))
        pygame.draw.rect(surface, C_BORDER, pygame.Rect(tx, ty, w, h), 1)

        for i, surf in enumerate(rendered):
            surface.blit(surf, (tx + _PAD, ty + _PAD + i * _LINE_H))
