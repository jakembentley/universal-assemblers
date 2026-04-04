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
from .constants import C_BORDER, C_ACCENT, font
from .widgets import Button


class TaskBar:

    def __init__(self, app) -> None:
        self.app = app

        bw  = _c.scaled(120)
        bh  = _c.scaled(26)
        gap = _c.scaled(8)
        by  = (_c.TASKBAR_H - bh) // 2

        x = gap
        self._galaxy_btn = Button(
            (x, by, bw, bh),
            "<<  GALAXY MAP",
            callback=self._go_galaxy,
            font_size=_c.scaled(11),
        )
        x += bw + gap
        self._tech_btn = Button(
            (x, by, _c.scaled(110), bh),
            "TECH TREE",
            callback=self._open_tech,
            font_size=_c.scaled(11),
        )
        x += _c.scaled(110) + gap
        self._energy_btn = Button(
            (x, by, _c.scaled(90), bh),
            "⚡ ENERGY",
            callback=self._open_energy,
            font_size=_c.scaled(11),
        )
        x += _c.scaled(90) + gap
        self._queue_btn = Button(
            (x, by, _c.scaled(90), bh),
            "≡ QUEUE",
            callback=self._open_queue,
            font_size=_c.scaled(11),
        )
        x += _c.scaled(90) + gap
        self._ledger_btn = Button(
            (x, by, _c.scaled(90), bh),
            "≡ LEDGER",
            callback=self._open_ledger,
            font_size=_c.scaled(11),
        )
        x += _c.scaled(90) + gap
        self._help_btn = Button(
            (x, by, _c.scaled(70), bh),
            "? HELP",
            callback=self._open_help,
            font_size=_c.scaled(11),
        )
        # Store the right edge of buttons for breadcrumb centering
        self._btn_right = x + _c.scaled(70) + gap

    # ------------------------------------------------------------------

    def _go_galaxy(self) -> None:
        if self.app.state == "system":
            self.app.back_to_galaxy()

    def _open_tech(self) -> None:
        self.app.open_tech_view()

    def _open_energy(self) -> None:
        self.app.open_energy_view()

    def _open_queue(self) -> None:
        self.app.open_queue_view()

    def _open_ledger(self) -> None:
        self.app.open_ledger_view()

    def _open_help(self) -> None:
        self.app.open_help_view()

    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._galaxy_btn.handle_event(event)
            self._tech_btn.handle_event(event)
            self._energy_btn.handle_event(event)
            self._queue_btn.handle_event(event)
            self._ledger_btn.handle_event(event)
            self._help_btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        W = _c.WINDOW_WIDTH
        bar = pygame.Rect(0, 0, W, _c.TASKBAR_H)
        pygame.draw.rect(surface, (10, 10, 28), bar)
        pygame.draw.line(surface, C_BORDER, (0, _c.TASKBAR_H - 1), (W, _c.TASKBAR_H - 1))

        self._galaxy_btn.draw(surface)
        self._tech_btn.draw(surface)
        self._energy_btn.draw(surface)
        self._queue_btn.draw(surface)
        self._ledger_btn.draw(surface)
        self._help_btn.draw(surface)

        # Centre: current system / body breadcrumb
        label_text = self._build_label()
        if label_text:
            clock_reserve = _c.scaled(280)
            usable_cx = self._btn_right + (W - clock_reserve - self._btn_right) // 2
            lbl = font(_c.scaled(13), bold=True).render(label_text, True, C_ACCENT)
            surface.blit(lbl, lbl.get_rect(center=(usable_cx, _c.TASKBAR_H // 2)))

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
