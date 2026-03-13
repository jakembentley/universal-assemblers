"""
Taskbar — horizontal bar at the very top of the system view.

Layout (left -> right):
  [ < GALAXY MAP ]  [ TECH TREE ]  |  System Name > Body Name  |  [clock area right]

The game clock (YEAR + speed badge) is rendered separately by App and occupies
the top-right corner.  This bar handles everything to the left of the clock.
"""
from __future__ import annotations

import pygame
from . import constants as _c
from .constants import (
    TASKBAR_H,
    C_BORDER, C_ACCENT, font,
)
from .widgets import Button

_CLOCK_RESERVE = 280   # pixels on the right reserved for the GameClock overlay


class TaskBar:

    def __init__(self, app) -> None:
        self.app = app

        bw, bh = 120, 26
        by = (TASKBAR_H - bh) // 2

        self._galaxy_btn = Button(
            (8, by, bw, bh),
            "<<  GALAXY MAP",
            callback=self._go_galaxy,
            font_size=11,
        )
        self._tech_btn = Button(
            (8 + bw + 8, by, 110, bh),
            "TECH TREE",
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
        W = _c.WINDOW_WIDTH
        bar = pygame.Rect(0, 0, W, TASKBAR_H)
        pygame.draw.rect(surface, (10, 10, 28), bar)
        pygame.draw.line(surface, C_BORDER, (0, TASKBAR_H - 1), (W, TASKBAR_H - 1))

        self._galaxy_btn.draw(surface)
        self._tech_btn.draw(surface)

        # Centre: current system / body breadcrumb
        label_text = self._build_label()
        if label_text:
            btn_right = 8 + 120 + 8 + 110 + 16
            usable_cx = btn_right + (W - _CLOCK_RESERVE - btn_right) // 2
            lbl = font(13, bold=True).render(label_text, True, C_ACCENT)
            surface.blit(lbl, lbl.get_rect(center=(usable_cx, TASKBAR_H // 2)))

    # ------------------------------------------------------------------

    def _build_label(self) -> str:
        sys = self.app.selected_system
        if not sys:
            return ""
        parts = [sys.name]
        body_id = self.app.selected_body_id
        if body_id:
            if body_id == sys.star.id:
                parts.append(sys.star.name)
            else:
                for body in sys.orbital_bodies:
                    if body.id == body_id:
                        parts.append(body.name.replace(sys.name + " ", ""))
                        break
                    for moon in body.moons:
                        if moon.id == body_id:
                            parts.append(moon.name)
                            break
        return "  >  ".join(parts)
