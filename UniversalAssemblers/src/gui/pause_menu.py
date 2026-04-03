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


_RESOLUTIONS = [
    ("1280 × 800",   1280,  800),
    ("1280 × 960",   1280,  960),
    ("1600 × 900",   1600,  900),
    ("1920 × 1080",  1920, 1080),
    ("2560 × 1440",  2560, 1440),
]


class PauseMenu:

    def __init__(self, app) -> None:
        self.app = app
        self.is_active: bool       = False
        self._sub_active: bool     = False
        self._settings_active: bool = False

        # Scaled panel dimensions
        panel_w = _c.scaled(320)
        panel_h = _c.scaled(520)   # extra height for display-mode row
        btn_w   = _c.scaled(260)
        btn_h   = _c.scaled(48)
        btn_gap = _c.scaled(12)

        # Panel geometry (centred on screen)
        px = (_c.WINDOW_WIDTH  - panel_w) // 2
        py = (_c.WINDOW_HEIGHT - panel_h) // 2
        self._panel_rect = pygame.Rect(px, py, panel_w, panel_h)

        def _make_button(label: str, row: int, cb) -> Button:
            x = self._panel_rect.x + (panel_w - btn_w) // 2
            y = self._panel_rect.y + _c.scaled(80) + row * (btn_h + btn_gap)
            return Button((x, y, btn_w, btn_h), label, callback=cb,
                          font_size=_c.scaled(16))

        # Pre-build button lists (callbacks reference self so lambdas are fine)
        self._main_buttons: list[Button] = [
            _make_button("RESUME",    0, self._resume),
            _make_button("SAVE GAME", 1, self._save),
            _make_button("LOAD GAME", 2, self._load),
            _make_button("SETTINGS",  3, self._open_settings_sub),
            _make_button("EXIT GAME", 4, self._open_exit_sub),
        ]
        self._sub_buttons: list[Button] = [
            _make_button("EXIT TO MENU",    0, self._exit_to_menu),
            _make_button("EXIT TO DESKTOP", 1, self._exit_to_desktop),
            _make_button("◀  BACK",         2, self._close_exit_sub),
        ]
        self._settings_buttons: list[Button] = [
            _make_button(label, i, self._make_res_callback(w, h))
            for i, (label, w, h) in enumerate(_RESOLUTIONS)
        ] + [_make_button("◀  BACK", len(_RESOLUTIONS), self._close_settings_sub)]

        # Display-mode toggle buttons (Windowed | Borderless | Fullscreen)
        # Placed below the resolution list row
        from .app import DISPLAY_WINDOWED, DISPLAY_BORDERLESS, DISPLAY_FULLSCREEN
        _dm_labels = [
            ("Windowed",   DISPLAY_WINDOWED),
            ("Borderless", DISPLAY_BORDERLESS),
            ("Fullscreen", DISPLAY_FULLSCREEN),
        ]
        dm_btn_w = _c.scaled(82)
        dm_btn_h = _c.scaled(28)
        dm_gap   = _c.scaled(6)
        dm_total = len(_dm_labels) * dm_btn_w + (len(_dm_labels) - 1) * dm_gap
        dm_start_x = self._panel_rect.x + (panel_w - dm_total) // 2
        dm_y = self._panel_rect.y + _c.scaled(80) + (len(_RESOLUTIONS) + 1) * (btn_h + btn_gap) + _c.scaled(8)
        self._dm_btns: list[tuple[pygame.Rect, str]] = []
        for i, (lbl, mode) in enumerate(_dm_labels):
            r = pygame.Rect(dm_start_x + i * (dm_btn_w + dm_gap), dm_y, dm_btn_w, dm_btn_h)
            self._dm_btns.append((r, mode))
        self._dm_labels_map = {mode: lbl for lbl, mode in _dm_labels}

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
        now = pygame.time.get_ticks()
        self.app._notifications.append(("GAME SAVED", now + 3000, (80, 220, 120)))

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
            # Display-mode buttons visible in settings sub-panel
            if self._settings_active and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, mode in self._dm_btns:
                    if rect.collidepoint(event.pos):
                        self.app.change_display_mode(mode)
                        return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self.is_active = False
                return

    # ------------------------------------------------------------------
    # Drawing

    def draw(self, surface: pygame.Surface) -> None:
        # 1. Dim overlay
        surface.blit(self._dim, (0, 0))

        # 2. Centre panel
        pygame.draw.rect(surface, C_PANEL, self._panel_rect, border_radius=8)
        pygame.draw.rect(surface, C_BORDER, self._panel_rect, width=2, border_radius=8)

        # 3. "PAUSED" title
        title = font(_c.scaled(22), bold=True).render("PAUSED", True, C_ACCENT)
        tx = self._panel_rect.x + (self._panel_rect.width - title.get_width()) // 2
        ty = self._panel_rect.y + _c.scaled(28)
        surface.blit(title, (tx, ty))

        # Subtle divider under title
        div_y = ty + title.get_height() + _c.scaled(12)
        pygame.draw.line(
            surface, C_BORDER,
            (self._panel_rect.x + 20, div_y),
            (self._panel_rect.right - 20, div_y),
        )

        # 4. Buttons
        if self._settings_active:
            lbl = font(14, bold=True).render("RESOLUTION", True, C_ACCENT)
            surface.blit(lbl, lbl.get_rect(center=(self._panel_rect.centerx, self._panel_rect.y + _c.scaled(56))))
            cur = font(11).render(
                f"Current: {_c.WINDOW_WIDTH} × {_c.WINDOW_HEIGHT}", True, C_TEXT_DIM
            )
            surface.blit(cur, cur.get_rect(center=(self._panel_rect.centerx, self._panel_rect.y + _c.scaled(74))))
            for btn in self._settings_buttons:
                btn.draw(surface)
            # Display mode row
            dm_lbl = font(11, bold=True).render("DISPLAY MODE", True, C_ACCENT)
            surface.blit(dm_lbl, dm_lbl.get_rect(
                center=(self._panel_rect.centerx, self._dm_btns[0][0].y - _c.scaled(14))
            ))
            from .app import DISPLAY_WINDOWED, DISPLAY_BORDERLESS, DISPLAY_FULLSCREEN
            cur_mode = getattr(self.app, "_display_mode", DISPLAY_WINDOWED)
            mouse_pos = pygame.mouse.get_pos()
            for rect, mode in self._dm_btns:
                active = (mode == cur_mode)
                hov    = rect.collidepoint(mouse_pos) and not active
                bg = C_ACCENT if active else (C_BTN_HOV if hov else C_BTN)
                pygame.draw.rect(surface, bg, rect, border_radius=4)
                pygame.draw.rect(surface, C_BORDER, rect, 1, border_radius=4)
                m_lbl = font(_c.scaled(11), bold=active).render(
                    self._dm_labels_map[mode], True, (0, 0, 0) if active else C_BTN_TXT
                )
                surface.blit(m_lbl, m_lbl.get_rect(center=rect.center))
        elif self._sub_active:
            for btn in self._sub_buttons:
                btn.draw(surface)
        else:
            for btn in self._main_buttons:
                btn.draw(surface)
