"""
Top taskbar — navigation buttons drawn across the full window width.

The game clock (YEAR + speed badge) is rendered separately by App and occupies
the top-right corner.  This bar handles everything to the left of the clock.
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, TASKBAR_H, C_BORDER, C_PANEL,
    C_BTN, C_BTN_HOV, C_BTN_TXT, C_ACCENT, C_TEXT_DIM, font,
)
from .widgets import Button


class TaskBar:

    def __init__(self, app) -> None:
        self.app = app

        bw, bh = 120, 26
        by = (TASKBAR_H - bh) // 2

        self._galaxy_btn = Button(
            (8, by, bw, bh),
            "◀  GALAXY MAP",
            callback=self._go_galaxy,
            font_size=11,
        )
        self._tech_btn = Button(
            (8 + bw + 8, by, 110, bh),
            "⌬  TECH TREE",
            callback=self._open_tech,
            font_size=11,
        )

    # ------------------------------------------------------------------

    def _go_galaxy(self) -> None:
        if self.app.state == "system":
            self.app.back_to_galaxy()

    def _open_tech(self) -> None:
        self.app.open_tech_view()

    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._galaxy_btn.handle_event(event)
            self._tech_btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        bar = pygame.Rect(0, 0, WINDOW_WIDTH, TASKBAR_H)
        pygame.draw.rect(surface, (10, 10, 28), bar)
        pygame.draw.line(surface, C_BORDER, (0, TASKBAR_H - 1), (WINDOW_WIDTH, TASKBAR_H - 1))
        self._galaxy_btn.draw(surface)
        self._tech_btn.draw(surface)
