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
        x += _c.scaled(70) + gap
        self._tasks_btn = Button(
            (x, by, _c.scaled(80), bh),
            "\u2022 TASKS",
            callback=self._open_tasks,
            font_size=_c.scaled(11),
        )
        # Store the right edge of buttons for breadcrumb centering
        self._btn_right = x + _c.scaled(80) + gap

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

    def _open_tasks(self) -> None:
        self.app.open_objectives_view()

    # ------------------------------------------------------------------

    @staticmethod
    def _threat_color(level: float) -> tuple:
        """Lerp green → yellow → red based on 0.0–1.0 threat level."""
        if level <= 0.5:
            t = level * 2
            return (int(t * 220), 200, int((1 - t) * 0))
        else:
            t = (level - 0.5) * 2
            return (220, int((1 - t) * 180), 0)

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._galaxy_btn.handle_event(event)
            self._tech_btn.handle_event(event)
            self._energy_btn.handle_event(event)
            self._queue_btn.handle_event(event)
            self._ledger_btn.handle_event(event)
            self._help_btn.handle_event(event)
            self._tasks_btn.handle_event(event)

            # Threat meter click handling
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                W = _c.WINDOW_WIDTH
                meter_y = _c.TASKBAR_H
                meter_h = _c.scaled(18)
                if meter_y <= my < meter_y + meter_h:
                    third = W // 3
                    if mx < third:
                        self.app.open_ledger_view()
                    elif mx < third * 2:
                        gs = getattr(self.app, "game_state", None)
                        if gs and gs.pending_events:
                            env_pe = next(
                                (p for p in gs.pending_events
                                 if p.event_type in ("asteroid_incoming", "solar_flare_warning")),
                                None,
                            )
                            if env_pe:
                                self.app.open_event_choice_view(env_pe)
                    else:
                        self.app.open_ledger_view()

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
        self._tasks_btn.draw(surface)

        # Threat meter strip — drawn just below taskbar
        meter_y = _c.TASKBAR_H
        meter_h = _c.scaled(18)
        gs = getattr(self.app, "game_state", None)
        threat = gs.threat_levels if gs else {"bios": 0.0, "environmental": 0.0, "resources": 0.0}
        labels = [("BIOS", "bios"), ("ENVIRON", "environmental"), ("RESOURCES", "resources")]
        bar_total_w = W // 3
        for i, (label, key) in enumerate(labels):
            level  = threat.get(key, 0.0)
            bx     = i * bar_total_w
            bg_r   = pygame.Rect(bx, meter_y, bar_total_w, meter_h)
            fill_w = int(bar_total_w * level)
            col    = self._threat_color(level)
            pygame.draw.rect(surface, (15, 15, 30), bg_r)
            if fill_w > 0:
                pygame.draw.rect(surface, col, pygame.Rect(bx, meter_y, fill_w, meter_h))
            pygame.draw.line(surface, C_BORDER,
                             (bx + bar_total_w - 1, meter_y),
                             (bx + bar_total_w - 1, meter_y + meter_h))
            lbl_s = font(_c.scaled(8), bold=True).render(
                f"{label} {int(level * 100)}%", True, (180, 180, 200)
            )
            surface.blit(lbl_s, (bx + _c.scaled(4), meter_y + (meter_h - lbl_s.get_height()) // 2))
        pygame.draw.line(surface, C_BORDER,
                         (0, meter_y + meter_h),
                         (W, meter_y + meter_h))

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
