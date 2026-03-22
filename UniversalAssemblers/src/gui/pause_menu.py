"""
Pause-menu dim overlay.

Activated by pressing ESC while in galaxy or system view.  Draws a translucent
full-screen dimmer and a centred panel with four buttons.  EXIT GAME opens an
inline sub-menu.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from . import constants as _c
from .constants import (
    C_ACCENT, C_BORDER, C_BTN, C_BTN_HOV, C_BTN_TXT, C_PANEL, C_TEXT_DIM, font,
)
from .widgets import Button

if TYPE_CHECKING:
    pass  # App imported at runtime


_PANEL_W = 320
_PANEL_H = 460
_BTN_W   = 260
_BTN_H   = 48
_BTN_GAP = 12

_RESOLUTIONS = [
    ("1280 × 800",   1280,  800),
    ("1280 × 960",   1280,  960),
    ("1600 × 900",   1600,  900),
    ("1920 × 1080",  1920, 1080),
    ("2560 × 1440",  2560, 1440),
]


def _make_button(label: str, panel_rect: pygame.Rect, row: int, cb) -> Button:
    """Helper: create a centred button inside the panel at the given row."""
    x = panel_rect.x + (_PANEL_W - _BTN_W) // 2
    y = panel_rect.y + 80 + row * (_BTN_H + _BTN_GAP)
    return Button((x, y, _BTN_W, _BTN_H), label, callback=cb, font_size=16)


class PauseMenu:

    def __init__(self, app) -> None:
        self.app = app
        self.is_active: bool       = False
        self._sub_active: bool     = False
        self._settings_active: bool = False

        # Panel geometry (centred on screen)
        px = (_c.WINDOW_WIDTH  - _PANEL_W) // 2
        py = (_c.WINDOW_HEIGHT - _PANEL_H) // 2
        self._panel_rect = pygame.Rect(px, py, _PANEL_W, _PANEL_H)

        # Pre-build button lists (callbacks reference self so lambdas are fine)
        self._main_buttons: list[Button] = [
            _make_button("RESUME",    self._panel_rect, 0, self._resume),
            _make_button("SAVE GAME", self._panel_rect, 1, self._save),
            _make_button("LOAD GAME", self._panel_rect, 2, self._load),
            _make_button("SETTINGS",  self._panel_rect, 3, self._open_settings_sub),
            _make_button("EXIT GAME", self._panel_rect, 4, self._open_exit_sub),
        ]
        self._sub_buttons: list[Button] = [
            _make_button("EXIT TO MENU",    self._panel_rect, 0, self._exit_to_menu),
            _make_button("EXIT TO DESKTOP", self._panel_rect, 1, self._exit_to_desktop),
            _make_button("◀  BACK",         self._panel_rect, 2, self._close_exit_sub),
        ]
        self._settings_buttons: list[Button] = [
            _make_button(label, self._panel_rect, i, self._make_res_callback(w, h))
            for i, (label, w, h) in enumerate(_RESOLUTIONS)
        ] + [_make_button("◀  BACK", self._panel_rect, len(_RESOLUTIONS), self._close_settings_sub)]

        # Reusable dim overlay surface
        self._dim = pygame.Surface((_c.WINDOW_WIDTH, _c.WINDOW_HEIGHT), pygame.SRCALPHA)
        self._dim.fill((5, 5, 20, 180))

    # ------------------------------------------------------------------
    # Activation

    def activate(self) -> None:
        self.is_active      = True
        self._sub_active    = False
        self._settings_active = False

    # ------------------------------------------------------------------
    # Button callbacks

    def _resume(self) -> None:
        self.app.resume_game()

    def _save(self) -> None:
        self.app.save_game()

    def _load(self) -> None:
        self.app.load_game()

    def _open_exit_sub(self) -> None:
        self._sub_active = True

    def _open_settings_sub(self) -> None:
        self._settings_active = True

    def _close_settings_sub(self) -> None:
        self._settings_active = False

    def _make_res_callback(self, w: int, h: int):
        def _cb():
            self.app.change_resolution(w, h)
            self._settings_active = False
        return _cb

    def _exit_to_menu(self) -> None:
        self.app.exit_to_menu()

    def _exit_to_desktop(self) -> None:
        self.app.quit()

    def _close_exit_sub(self) -> None:
        self._sub_active = False

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        # ESC is handled by App.run() for both open and close; only route
        # mouse/button events here so the menu doesn't close itself the same
        # frame it was opened.
        if self._settings_active:
            buttons = self._settings_buttons
        elif self._sub_active:
            buttons = self._sub_buttons
        else:
            buttons = self._main_buttons
        for event in events:
            for btn in buttons:
                btn.handle_event(event)

    # ------------------------------------------------------------------
    # Drawing

    def draw(self, surface: pygame.Surface) -> None:
        # 1. Dim overlay
        surface.blit(self._dim, (0, 0))

        # 2. Centre panel
        pygame.draw.rect(surface, C_PANEL, self._panel_rect, border_radius=8)
        pygame.draw.rect(surface, C_BORDER, self._panel_rect, width=2, border_radius=8)

        # 3. "PAUSED" title
        title = font(22, bold=True).render("PAUSED", True, C_ACCENT)
        tx = self._panel_rect.x + (_PANEL_W - title.get_width()) // 2
        ty = self._panel_rect.y + 28
        surface.blit(title, (tx, ty))

        # Subtle divider under title
        div_y = ty + title.get_height() + 12
        pygame.draw.line(
            surface, C_BORDER,
            (self._panel_rect.x + 20, div_y),
            (self._panel_rect.right - 20, div_y),
        )

        # 4. Buttons
        if self._settings_active:
            lbl = font(14, bold=True).render("RESOLUTION", True, C_ACCENT)
            surface.blit(lbl, lbl.get_rect(center=(self._panel_rect.centerx, self._panel_rect.y + 56)))
            cur = font(11).render(
                f"Current: {_c.WINDOW_WIDTH} × {_c.WINDOW_HEIGHT}", True, C_TEXT_DIM
            )
            surface.blit(cur, cur.get_rect(center=(self._panel_rect.centerx, self._panel_rect.y + 74)))
            for btn in self._settings_buttons:
                btn.draw(surface)
        elif self._sub_active:
            for btn in self._sub_buttons:
                btn.draw(surface)
        else:
            for btn in self._main_buttons:
                btn.draw(surface)
