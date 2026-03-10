"""
Taskbar — horizontal bar at the very top of the system view.

Layout (left → right):
  [ ◀ GALAXY MAP ]  |  System Name  ›  Body Name  |  ... (clock drawn on top by App)
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, TASKBAR_H,
    C_BG, C_BORDER, C_ACCENT, C_TEXT, C_TEXT_DIM, font,
)
from .widgets import Button

_CLOCK_RESERVE = 280   # pixels on the right reserved for the GameClock overlay


class TaskBar:

    def __init__(self, app) -> None:
        self.app  = app
        self.rect = pygame.Rect(0, 0, WINDOW_WIDTH, TASKBAR_H)

        self._back_btn = Button(
            rect=(8, 4, 130, TASKBAR_H - 8),
            label="◀ GALAXY MAP",
            callback=app.back_to_galaxy,
            font_size=12,
            bold=True,
        )

    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._back_btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        # Background
        pygame.draw.rect(surface, (10, 12, 30), self.rect)
        pygame.draw.line(
            surface, C_BORDER,
            (0, TASKBAR_H - 1), (WINDOW_WIDTH, TASKBAR_H - 1),
        )

        self._back_btn.draw(surface)

        # Centre: current system / body breadcrumb
        label_text = self._build_label()
        if label_text:
            # Centre between the back button and the clock reserve
            usable_cx = (WINDOW_WIDTH - _CLOCK_RESERVE + 148) // 2
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
                parts.append(f"★ {sys.star.name}")
            else:
                for body in sys.orbital_bodies:
                    if body.id == body_id:
                        parts.append(body.name.replace(sys.name + " ", ""))
                        break
                    for moon in body.moons:
                        if moon.id == body_id:
                            parts.append(moon.name)
                            break
        return "  ›  ".join(parts)
