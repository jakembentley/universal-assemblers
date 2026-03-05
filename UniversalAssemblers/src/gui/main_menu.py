"""Main menu screen with animated star field background."""
from __future__ import annotations

import random
import math
import time

import pygame
from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, C_BG, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_SELECTED, font,
)
from .widgets import Button


class MainMenu:
    """Draws the main menu and dispatches button actions to the App."""

    _NUM_STARS    = 220
    _NUM_NEBULA   = 6

    def __init__(self, app) -> None:
        self.app = app
        rng = random.Random(0xDEADBEEF)

        # Static star field
        self._stars = [
            (
                rng.randint(0, WINDOW_WIDTH),
                rng.randint(0, WINDOW_HEIGHT),
                rng.uniform(0.4, 1.0),           # brightness
                rng.randint(1, 2),               # radius
                rng.uniform(0.2, 1.2),           # twinkle speed
                rng.uniform(0, math.pi * 2),     # twinkle phase
            )
            for _ in range(self._NUM_STARS)
        ]

        # Nebula blobs (coloured circles with low alpha)
        self._nebulas = [
            (
                rng.randint(50, WINDOW_WIDTH - 50),
                rng.randint(50, WINDOW_HEIGHT - 50),
                rng.randint(80, 200),
                (rng.randint(20, 80), rng.randint(20, 80), rng.randint(80, 160), 18),
            )
            for _ in range(self._NUM_NEBULA)
        ]
        self._nebula_surf = self._build_nebula_surf()

        bw, bh = 300, 52
        cx      = WINDOW_WIDTH // 2

        self._buttons = [
            Button(
                (cx - bw // 2, 370, bw, bh),
                "NEW GAME",
                callback=self.app.start_new_game,
                font_size=18,
            ),
            Button(
                (cx - bw // 2, 440, bw, bh),
                "LOAD GAME",
                callback=self.app.load_game,
                font_size=18,
            ),
            Button(
                (cx - bw // 2, 510, bw, bh),
                "EXIT",
                callback=self.app.quit,
                font_size=18,
            ),
        ]

    # ------------------------------------------------------------------

    def _build_nebula_surf(self) -> pygame.Surface:
        surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        for x, y, r, color in self._nebulas:
            # Soft glow by drawing concentric circles with decreasing alpha
            for dr in range(r, 0, -8):
                alpha = int(color[3] * (1 - dr / r) + 4)
                c = (*color[:3], min(alpha, 40))
                pygame.draw.circle(surf, c, (x, y), dr)
        return surf

    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            for btn in self._buttons:
                btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C_BG)
        surface.blit(self._nebula_surf, (0, 0))
        self._draw_stars(surface)
        self._draw_title(surface)
        for btn in self._buttons:
            btn.draw(surface)
        self._draw_footer(surface)

    def _draw_stars(self, surface: pygame.Surface) -> None:
        t = time.time()
        for x, y, brightness, r, speed, phase in self._stars:
            twinkle = 0.6 + 0.4 * math.sin(t * speed + phase)
            v = int(brightness * twinkle * 255)
            col = (v, v, min(255, int(v * 1.1)))
            pygame.draw.circle(surface, col, (x, y), r)

    def _draw_title(self, surface: pygame.Surface) -> None:
        # Main title
        title_font = font(52, bold=True)
        title_surf = title_font.render("UNIVERSAL ASSEMBLERS", True, C_ACCENT)
        tx = WINDOW_WIDTH // 2 - title_surf.get_width() // 2
        # Subtle glow behind title
        glow_surf = title_font.render("UNIVERSAL ASSEMBLERS", True, (0, 60, 90))
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            surface.blit(glow_surf, (tx + dx, 155 + dy))
        surface.blit(title_surf, (tx, 155))

        # Subtitle
        sub = font(16).render("Colonize the galaxy.  Become the swarm.", True, C_TEXT_DIM)
        surface.blit(sub, (WINDOW_WIDTH // 2 - sub.get_width() // 2, 225))

        # Decorative rule
        rule_y = 268
        mid    = WINDOW_WIDTH // 2
        pygame.draw.line(surface, (0, 80, 130), (mid - 280, rule_y), (mid - 20, rule_y), 1)
        diamond = font(13).render("◆", True, C_ACCENT)
        surface.blit(diamond, (mid - diamond.get_width() // 2, rule_y - diamond.get_height() // 2))
        pygame.draw.line(surface, (0, 80, 130), (mid + 20, rule_y), (mid + 280, rule_y), 1)

    def _draw_footer(self, surface: pygame.Surface) -> None:
        foot = font(11).render(
            "v0.1.0  —  github.com/jakembentley/universal-assemblers",
            True, (40, 60, 100),
        )
        surface.blit(foot, (WINDOW_WIDTH // 2 - foot.get_width() // 2, WINDOW_HEIGHT - 28))
