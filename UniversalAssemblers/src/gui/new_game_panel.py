"""
New Game settings panel.

Shown before starting a new game; lets the player configure galaxy generation
parameters before calling app.launch_game(settings_dict).
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT,
    C_BG, C_PANEL, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM,
    C_ACCENT, C_BTN, C_BTN_HOV, C_BTN_TXT, C_SELECTED, C_WARN,
    PADDING, font,
)
from .widgets import Button, TextInput, draw_separator


# ---------------------------------------------------------------------------
# Option selector widget (row of clickable label buttons)
# ---------------------------------------------------------------------------

class _Selector:
    """Row of mutually-exclusive option buttons."""

    def __init__(self, options: list[str], default: str) -> None:
        self.options = options
        self.selected = default
        self._rects: list[tuple[pygame.Rect, str]] = []

    def layout(self, x: int, y: int, btn_w: int = 90, btn_h: int = 28, gap: int = 6) -> int:
        """Lay out buttons starting at (x, y). Returns total width used."""
        self._rects = []
        cx = x
        for opt in self.options:
            r = pygame.Rect(cx, y, btn_w, btn_h)
            self._rects.append((r, opt))
            cx += btn_w + gap
        return cx - x

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for r, opt in self._rects:
                if r.collidepoint(event.pos):
                    self.selected = opt
                    return

    def draw(self, surface: pygame.Surface) -> None:
        for r, opt in self._rects:
            sel = opt == self.selected
            bg = C_ACCENT if sel else C_BTN
            hov = r.collidepoint(pygame.mouse.get_pos())
            if not sel and hov:
                bg = C_BTN_HOV
            pygame.draw.rect(surface, bg, r, border_radius=4)
            pygame.draw.rect(surface, C_BORDER, r, 1, border_radius=4)
            lbl = font(12, bold=sel).render(opt, True, (0, 0, 0) if sel else C_BTN_TXT)
            surface.blit(lbl, lbl.get_rect(center=r.center))


# ---------------------------------------------------------------------------
# NewGamePanel
# ---------------------------------------------------------------------------

class NewGamePanel:
    """Full-screen panel for game generation settings."""

    _PANEL_W = 620
    _PANEL_H = 520

    def __init__(self, app) -> None:
        self.app = app

        px = (WINDOW_WIDTH  - self._PANEL_W) // 2
        py = (WINDOW_HEIGHT - self._PANEL_H) // 2
        self._panel_rect = pygame.Rect(px, py, self._PANEL_W, self._PANEL_H)

        # Galaxy Name text input
        name_rect = pygame.Rect(px + 160, py + 60, 300, 26)
        self._name_input = TextInput(name_rect, "Unnamed Sector", font_size=13, max_length=40)
        self._name_input.active = True

        # System Count selector
        self._sys_count = _Selector(["8", "12", "18", "24", "32"], "12")

        # Resource Density
        self._res_density = _Selector(["Low", "Normal", "High", "Rich"], "Normal")

        # Bio Uplift
        self._bio_uplift = _Selector(["Rare", "Normal", "Common"], "Normal")

        # Body Mix
        self._body_mix = _Selector(["Balanced", "Rocky", "Gas-Heavy", "Ice-Rich"], "Balanced")

        # Warp Clusters +/-
        self._warp_clusters = 1
        self._warp_dec_rect = pygame.Rect(0, 0, 28, 28)
        self._warp_inc_rect = pygame.Rect(0, 0, 28, 28)

        # Buttons
        self._start_btn = Button(
            (px + self._PANEL_W // 2 - 90, py + self._PANEL_H - 60, 170, 36),
            "START GAME",
            callback=self._on_start,
            font_size=14,
        )
        self._back_btn = Button(
            (px + PADDING, py + self._PANEL_H - 60, 90, 36),
            "BACK",
            callback=self._on_back,
            font_size=13,
        )

        # Layout selectors
        col_x = px + 160
        row_y = py + 100

        self._sys_count.layout(col_x, row_y, btn_w=68, btn_h=26, gap=5)
        row_y += 44

        self._res_density.layout(col_x, row_y, btn_w=80, btn_h=26, gap=5)
        row_y += 44

        self._bio_uplift.layout(col_x, row_y, btn_w=90, btn_h=26, gap=5)
        row_y += 44

        self._body_mix.layout(col_x, row_y, btn_w=90, btn_h=26, gap=5)
        row_y += 44

        # Warp clusters row — position +/- buttons
        self._warp_row_y = row_y
        self._warp_dec_rect = pygame.Rect(col_x, row_y, 28, 26)
        self._warp_inc_rect = pygame.Rect(col_x + 80, row_y, 28, 26)

    # ------------------------------------------------------------------
    # Callbacks

    def _on_start(self) -> None:
        settings = {
            "galaxy_name":       self._name_input.text.strip() or "Unnamed Sector",
            "num_solar_systems": int(self._sys_count.selected),
            "resource_density":  self._res_density.selected.lower(),
            "bio_uplift_rate":   self._bio_uplift.selected.lower(),
            "body_distribution": self._body_mix.selected.lower().replace("-", "_").replace(" ", "_"),
            "warp_clusters":     self._warp_clusters,
        }
        self.app.launch_game(settings)

    def _on_back(self) -> None:
        self.app.state = "menu"

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._on_back()
                return

            self._name_input.handle_event(event)
            self._sys_count.handle_event(event)
            self._res_density.handle_event(event)
            self._bio_uplift.handle_event(event)
            self._body_mix.handle_event(event)
            self._start_btn.handle_event(event)
            self._back_btn.handle_event(event)

            # Warp clusters +/-
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._warp_dec_rect.collidepoint(event.pos):
                    self._warp_clusters = max(0, self._warp_clusters - 1)
                elif self._warp_inc_rect.collidepoint(event.pos):
                    self._warp_clusters = min(3, self._warp_clusters + 1)

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        # Dim background
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 10, 200))
        surface.blit(overlay, (0, 0))

        # Panel background
        px, py = self._panel_rect.x, self._panel_rect.y
        pygame.draw.rect(surface, C_PANEL, self._panel_rect, border_radius=8)
        pygame.draw.rect(surface, C_BORDER, self._panel_rect, 2, border_radius=8)

        # Title bar
        hdr = pygame.Rect(px, py, self._PANEL_W, 46)
        pygame.draw.rect(surface, C_HEADER, hdr, border_top_left_radius=8, border_top_right_radius=8)
        title = font(18, bold=True).render("NEW GAME SETTINGS", True, C_ACCENT)
        surface.blit(title, title.get_rect(centerx=self._panel_rect.centerx, y=py + 10))

        # Rows
        lbl_x = px + PADDING + 10
        row_y = py + 60

        def _row_label(text: str, y: int) -> None:
            s = font(13).render(text, True, C_TEXT_DIM)
            surface.blit(s, (lbl_x, y + 5))

        # Galaxy Name
        _row_label("Galaxy Name:", row_y)
        self._name_input.draw(surface)
        row_y += 44

        # System Count
        _row_label("System Count:", row_y)
        self._sys_count.draw(surface)
        row_y += 44

        # Resource Density
        _row_label("Resource Density:", row_y)
        self._res_density.draw(surface)
        row_y += 44

        # Bio Uplift
        _row_label("Bio Uplift:", row_y)
        self._bio_uplift.draw(surface)
        row_y += 44

        # Body Mix
        _row_label("Body Mix:", row_y)
        self._body_mix.draw(surface)
        row_y += 44

        # Warp Clusters
        _row_label("Warp Clusters:", row_y)
        col_x = px + 160

        pygame.draw.rect(surface, C_BTN, self._warp_dec_rect, border_radius=4)
        pygame.draw.rect(surface, C_BTN, self._warp_inc_rect, border_radius=4)
        surface.blit(font(14, bold=True).render("−", True, C_BTN_TXT),
                     font(14, bold=True).render("−", True, C_BTN_TXT).get_rect(center=self._warp_dec_rect.center))
        surface.blit(font(14, bold=True).render("+", True, C_BTN_TXT),
                     font(14, bold=True).render("+", True, C_BTN_TXT).get_rect(center=self._warp_inc_rect.center))

        val_s = font(14, bold=True).render(str(self._warp_clusters), True, C_SELECTED)
        surface.blit(val_s, val_s.get_rect(centerx=col_x + 54, centery=self._warp_dec_rect.centery))

        warp_note = font(11).render("(isolated systems requiring Warp Drive)", True, C_TEXT_DIM)
        surface.blit(warp_note, (col_x + 120, row_y + 6))

        # Buttons
        self._start_btn.draw(surface)
        self._back_btn.draw(surface)
