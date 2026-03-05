"""
In-game year clock.

Draws a pill-shaped HUD in the top-right corner showing the current year and
a clickable speed badge.  Spacebar pauses/unpauses; clicking the badge cycles
through 1×, 5× and 10× speeds.
"""
from __future__ import annotations

import pygame
from .constants import WINDOW_WIDTH, C_ACCENT, C_BTN_TXT, C_TEXT_DIM, font


class GameClock:
    SPEEDS: list[int] = [1, 5, 10]
    YEAR_PER_MS_AT_1X: float = 0.1 / 1000   # 0.1 yr / real-second at 1×

    # HUD geometry
    _RECT = pygame.Rect(WINDOW_WIDTH - 275, 8, 265, 34)

    def __init__(self) -> None:
        self.year: float = 0.0
        self._speed_idx: int = 0
        self._paused: bool = False
        self._badge_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)  # set in draw

    # ------------------------------------------------------------------
    # Time management

    def update(self, dt_ms: int) -> None:
        """Advance the year counter if not paused."""
        if not self._paused:
            self.year += dt_ms * self.YEAR_PER_MS_AT_1X * self.SPEEDS[self._speed_idx]

    def toggle_pause(self) -> None:
        """Spacebar: flip pause state."""
        self._paused = not self._paused

    def cycle_speed(self) -> None:
        """Click on the speed badge: 1× → 5× → 10× → 1×."""
        self._speed_idx = (self._speed_idx + 1) % len(self.SPEEDS)
        self._paused = False   # cycling speed un-pauses

    def save_and_pause(self) -> None:
        """Called when the pause menu is opened (ESC key)."""
        self._paused = True

    def unpause(self) -> None:
        """Called when the pause menu is closed (Resume)."""
        self._paused = False

    # ------------------------------------------------------------------
    # Properties / helpers

    @property
    def current_speed(self) -> int:
        return 0 if self._paused else self.SPEEDS[self._speed_idx]

    @property
    def is_paused(self) -> bool:
        return self._paused

    def speed_label(self) -> str:
        if self._paused:
            return "PAUSED"
        return f"{self.SPEEDS[self._speed_idx]}×"

    # ------------------------------------------------------------------
    # Event handling

    def handle_event(self, event: pygame.event.Event) -> None:
        """Detect a left-click on the speed badge."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._badge_rect.collidepoint(event.pos):
                self.cycle_speed()

    # ------------------------------------------------------------------
    # Drawing

    def draw(self, surface: pygame.Surface) -> None:
        rect = self._RECT

        # Semi-transparent dark pill background
        bg = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        bg.fill((5, 10, 28, 200))
        pygame.draw.rect(bg, (30, 60, 110, 180), bg.get_rect(), width=1, border_radius=8)
        surface.blit(bg, rect.topleft)

        # Year text  (e.g. "YEAR  4 217")
        year_int = int(self.year)
        year_str = f"{year_int:,}".replace(",", " ")   # thousands separator → space
        year_text = f"YEAR  {year_str}"
        year_surf = font(15, bold=True).render(year_text, True, C_ACCENT)
        surface.blit(year_surf, (rect.x + 10, rect.y + (rect.height - year_surf.get_height()) // 2))

        # Speed badge  ("[1×]", "[PAUSED]")
        badge_text = f"[{self.speed_label()}]"
        badge_surf = font(14, bold=True).render(badge_text, True, C_BTN_TXT)
        bx = rect.right - badge_surf.get_width() - 10
        by = rect.y + (rect.height - badge_surf.get_height()) // 2
        self._badge_rect = pygame.Rect(bx - 4, rect.y + 2, badge_surf.get_width() + 8, rect.height - 4)

        # Badge highlight on hover
        mouse = pygame.mouse.get_pos()
        if self._badge_rect.collidepoint(mouse):
            hl = pygame.Surface(self._badge_rect.size, pygame.SRCALPHA)
            hl.fill((60, 100, 180, 80))
            surface.blit(hl, self._badge_rect.topleft)

        surface.blit(badge_surf, (bx, by))
