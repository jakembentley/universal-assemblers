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
from . import constants as _c
from .constants import C_BORDER

_DELAY_MS = 420   # ms before the tooltip appears


class Tooltip:

    def __init__(self) -> None:
        self._hover_id:    object                  = None
        self._hover_since: int                     = 0
        self._lines:       list[tuple[str, tuple]] = []
        self._pos:         tuple[int, int]         = (0, 0)
        self.hit_rect:     "pygame.Rect | None"    = None

    @property
    def hover_id(self) -> object:
        return self._hover_id

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

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Return True if *pos* falls on the currently-visible tooltip."""
        return self.hit_rect is not None and self.hit_rect.collidepoint(pos)

    def draw(self, surface: pygame.Surface) -> None:
        self.hit_rect = None
        now = pygame.time.get_ticks()
        if not self._hover_id or not self._lines:
            return
        if now - self._hover_since < _DELAY_MS:
            return

        _pad    = _c.scaled(8)
        _line_h = _c.scaled(18)
        _max_w  = _c.scaled(300)

        rendered = [_c.font_scaled(11).render(text, True, color) for text, color in self._lines]
        if not rendered:
            return

        w = min(_max_w, max(s.get_width() for s in rendered) + _pad * 2)
        h = len(rendered) * _line_h + _pad * 2

        mx, my = self._pos
        tx = mx + _c.scaled(16)
        ty = my + _c.scaled(16)
        if tx + w > _c.WINDOW_WIDTH - 4:
            tx = mx - w - _c.scaled(8)
        if ty + h > _c.WINDOW_HEIGHT - 4:
            ty = my - h - _c.scaled(8)

        self.hit_rect = pygame.Rect(tx, ty, w, h)

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((6, 10, 26, 225))
        surface.blit(bg, (tx, ty))
        pygame.draw.rect(surface, C_BORDER, pygame.Rect(tx, ty, w, h), 1)

        for i, surf in enumerate(rendered):
            surface.blit(surf, (tx + _pad, ty + _pad + i * _line_h))
