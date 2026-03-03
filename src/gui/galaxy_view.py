"""
GalaxyView — full-screen galaxy map with fog of war.

Renders all solar systems with per-discovery-state visuals, a dynamic fog
overlay, connection lines between known systems, and a HUD for navigation.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, C_BG, C_ACCENT, C_TEXT, C_TEXT_DIM,
    C_BTN, C_BTN_HOV, C_BTN_TXT, C_BORDER, C_SELECTED, STAR_COLORS, font,
)
from ..game_state import DiscoveryState

if TYPE_CHECKING:
    pass  # App imported at runtime to avoid circular imports

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
TOP_BAR_H    = 50
BOTTOM_BAR_H = 60
MAP_RECT     = pygame.Rect(10, TOP_BAR_H + 5, WINDOW_WIDTH - 20, WINDOW_HEIGHT - TOP_BAR_H - BOTTOM_BAR_H - 10)

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------
_FOG_COLOR       = (5, 5, 20)
_FOG_BASE_ALPHA  = 170
_STAR_FIELD_COUNT = 200
_CLICK_RADIUS    = 14   # px — how close a click must land to a node

_DETECTED_COLOR  = (120, 120, 140)
_LINE_KNOWN      = (50, 90, 140)
_LINE_DETECTED   = (30, 50, 80)


class GalaxyView:

    def __init__(self, app) -> None:
        self.app = app
        self._selected_id: str | None = None
        self._hovered_id:  str | None = None
        self._last_click_id: str | None = None   # for double-click detection
        self._last_click_time: int = 0

        # Pre-bake star field (seeded from galaxy seed for reproducibility)
        self._star_field: list[tuple[int, int, int]] = []  # (x, y, brightness)
        self._screen_pos: dict[str, tuple[int, int]] = {}

        # Enter-system button
        self._btn_rect = pygame.Rect(WINDOW_WIDTH - 170, WINDOW_HEIGHT - BOTTOM_BAR_H + 10, 155, 36)
        self._btn_hovered = False

        # Fog surface (rebuilt when discovery state changes)
        self._fog_dirty = True
        self._fog_surface: pygame.Surface | None = None

        self._init_layout()

    # ------------------------------------------------------------------
    # Layout

    def _init_layout(self) -> None:
        galaxy = self.app.galaxy
        if not galaxy or not galaxy.solar_systems:
            return

        # Bake star field using galaxy seed
        rng = random.Random(galaxy.seed)
        self._star_field = [
            (
                rng.randint(MAP_RECT.left, MAP_RECT.right),
                rng.randint(MAP_RECT.top,  MAP_RECT.bottom),
                rng.randint(30, 110),
            )
            for _ in range(_STAR_FIELD_COUNT)
        ]

        self._compute_layout()

    def _compute_layout(self) -> None:
        """Map galaxy coordinates → screen pixels, centred with 15% padding."""
        systems = self.app.galaxy.solar_systems
        xs = [s.position["x"] for s in systems]
        ys = [s.position["y"] for s in systems]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        span_x = (max_x - min_x) or 1.0
        span_y = (max_y - min_y) or 1.0

        # Add 15% padding on each side
        pad = 0.15
        span_x *= (1 + 2 * pad)
        span_y *= (1 + 2 * pad)
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2

        # Scale preserving aspect ratio
        scale = min(MAP_RECT.width / span_x, MAP_RECT.height / span_y)

        map_cx = MAP_RECT.centerx
        map_cy = MAP_RECT.centery

        self._screen_pos = {}
        for s in systems:
            sx = int(map_cx + (s.position["x"] - cx) * scale)
            sy = int(map_cy + (s.position["y"] - cy) * scale)
            self._screen_pos[s.id] = (sx, sy)

        self._fog_dirty = True

    # ------------------------------------------------------------------
    # Fog

    def _rebuild_fog(self, surface: pygame.Surface) -> None:
        gs = self.app.game_state
        W, H = surface.get_size()
        fog = pygame.Surface((W, H), pygame.SRCALPHA)
        fog.fill((*_FOG_COLOR, _FOG_BASE_ALPHA))

        for sys in self.app.galaxy.solar_systems:
            state = gs.get_state(sys.id)
            pos   = self._screen_pos.get(sys.id)
            if not pos:
                continue

            if state == DiscoveryState.COLONIZED:
                max_r = 160
                for r in range(max_r, 0, -3):
                    alpha = int(_FOG_BASE_ALPHA * (r / max_r) ** 0.7)
                    pygame.draw.circle(fog, (*_FOG_COLOR, alpha), pos, r)

            elif state == DiscoveryState.DISCOVERED:
                max_r = 120
                for r in range(max_r, 0, -3):
                    alpha = int(_FOG_BASE_ALPHA * (r / max_r) ** 0.7)
                    pygame.draw.circle(fog, (*_FOG_COLOR, alpha), pos, r)

            elif state == DiscoveryState.DETECTED:
                max_r = 55
                for r in range(max_r, 0, -3):
                    alpha = int(_FOG_BASE_ALPHA * (r / max_r) ** 1.5)
                    pygame.draw.circle(fog, (*_FOG_COLOR, alpha), pos, r)

        self._fog_surface = fog
        self._fog_dirty   = False

    # ------------------------------------------------------------------
    # Event handling

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        mouse_pos = pygame.mouse.get_pos()
        self._hovered_id = self._node_at(mouse_pos)
        self._btn_hovered = self._btn_rect.collidepoint(mouse_pos)

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.app.state = "menu"

    def _handle_click(self, pos: tuple[int, int]) -> None:
        # Enter-system button
        if self._btn_rect.collidepoint(pos):
            if self._selected_id and self.app.game_state.can_enter(self._selected_id):
                self.app.enter_system(self._selected_id)
            return

        hit_id = self._node_at(pos)
        if hit_id is None:
            return

        gs = self.app.game_state
        state = gs.get_state(hit_id)

        if state == DiscoveryState.DETECTED:
            gs.discover_system(hit_id)
            self._fog_dirty = True
            self._selected_id = hit_id

        elif state in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
            now = pygame.time.get_ticks()
            if hit_id == self._last_click_id and (now - self._last_click_time) < 400:
                # Double-click → enter system
                self.app.enter_system(hit_id)
                return
            self._selected_id = hit_id
            self._last_click_id   = hit_id
            self._last_click_time = now

    def _node_at(self, pos: tuple[int, int]) -> str | None:
        """Return the system_id whose screen position is closest to pos (within click radius)."""
        best_id   = None
        best_dist = _CLICK_RADIUS + 1
        gs = self.app.game_state
        for sys in self.app.galaxy.solar_systems:
            state = gs.get_state(sys.id)
            if state == DiscoveryState.UNKNOWN:
                continue
            sp = self._screen_pos.get(sys.id)
            if sp is None:
                continue
            d = math.hypot(pos[0] - sp[0], pos[1] - sp[1])
            if d <= _CLICK_RADIUS and d < best_dist:
                best_dist = d
                best_id   = sys.id
        return best_id

    # ------------------------------------------------------------------
    # Drawing

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(C_BG)

        # 1. Background star field
        self._draw_star_field(surface)

        # 2. Connection lines (below fog)
        self._draw_connections(surface)

        # 3. Fog overlay
        if self._fog_dirty or self._fog_surface is None:
            self._rebuild_fog(surface)
        surface.blit(self._fog_surface, (0, 0))

        # 4. System nodes + labels (above fog)
        self._draw_nodes(surface)

        # 5. Selected highlight ring
        if self._selected_id:
            sp = self._screen_pos.get(self._selected_id)
            if sp:
                pygame.draw.circle(surface, C_SELECTED, sp, 18, 2)

        # 6. HUD
        self._draw_top_bar(surface)
        self._draw_bottom_bar(surface)

    def _draw_star_field(self, surface: pygame.Surface) -> None:
        for x, y, b in self._star_field:
            surface.set_at((x, y), (b, b, b))

    def _draw_connections(self, surface: pygame.Surface) -> None:
        gs  = self.app.game_state
        adj = self.app.game_state.adjacency
        drawn: set[frozenset] = set()

        for sys in self.app.galaxy.solar_systems:
            a_state = gs.get_state(sys.id)
            if a_state == DiscoveryState.UNKNOWN:
                continue
            sp_a = self._screen_pos.get(sys.id)
            if sp_a is None:
                continue

            for nb_id in adj.get(sys.id, []):
                key = frozenset((sys.id, nb_id))
                if key in drawn:
                    continue
                drawn.add(key)

                b_state = gs.get_state(nb_id)
                if b_state == DiscoveryState.UNKNOWN:
                    continue
                sp_b = self._screen_pos.get(nb_id)
                if sp_b is None:
                    continue

                both_known = (
                    a_state in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED)
                    and b_state in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED)
                )
                color = _LINE_KNOWN if both_known else _LINE_DETECTED

                if both_known:
                    pygame.draw.line(surface, color, sp_a, sp_b, 1)
                else:
                    # Dashed line for detected connections
                    self._draw_dashed_line(surface, color, sp_a, sp_b)

    @staticmethod
    def _draw_dashed_line(
        surface: pygame.Surface,
        color: tuple,
        p1: tuple[int, int],
        p2: tuple[int, int],
        dash: int = 8,
        gap: int = 6,
    ) -> None:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        pos = 0.0
        while pos < length:
            start = (int(p1[0] + ux * pos), int(p1[1] + uy * pos))
            pos   = min(pos + dash, length)
            end   = (int(p1[0] + ux * pos), int(p1[1] + uy * pos))
            pygame.draw.line(surface, color, start, end, 1)
            pos += gap

    def _draw_nodes(self, surface: pygame.Surface) -> None:
        gs      = self.app.game_state
        tick    = pygame.time.get_ticks()
        pulse   = int(128 + 80 * math.sin(tick / 400.0))   # 0–255 pulsing

        for sys in self.app.galaxy.solar_systems:
            state = gs.get_state(sys.id)
            if state == DiscoveryState.UNKNOWN:
                continue

            sp = self._screen_pos.get(sys.id)
            if sp is None:
                continue

            star_color = STAR_COLORS.get(sys.star.star_type.value, (200, 200, 200))

            if state == DiscoveryState.COLONIZED:
                self._draw_glow(surface, sp, star_color, radius=16)
                pygame.draw.circle(surface, star_color, sp, 12)
                self._draw_hex_ring(surface, sp, C_ACCENT, 20)
                label_color = (255, 255, 255)
                label_text  = sys.name

            elif state == DiscoveryState.DISCOVERED:
                self._draw_glow(surface, sp, star_color, radius=11)
                pygame.draw.circle(surface, star_color, sp, 9)
                label_color = C_TEXT
                label_text  = sys.name

            else:  # DETECTED
                col = (*_DETECTED_COLOR, pulse)
                det_surf = pygame.Surface((12, 12), pygame.SRCALPHA)
                pygame.draw.circle(det_surf, col, (6, 6), 4)
                surface.blit(det_surf, (sp[0] - 6, sp[1] - 6))
                label_color = (80, 80, 100)
                label_text  = "???"

            lbl = font(11).render(label_text, True, label_color)
            surface.blit(lbl, (sp[0] - lbl.get_width() // 2, sp[1] + 14))

    @staticmethod
    def _draw_glow(
        surface: pygame.Surface,
        center: tuple[int, int],
        color: tuple,
        radius: int,
    ) -> None:
        glow = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        for r in range(radius * 2, 0, -2):
            alpha = max(0, int(60 * (1 - r / (radius * 2))))
            pygame.draw.circle(glow, (*color, alpha), (radius * 2, radius * 2), r)
        surface.blit(glow, (center[0] - radius * 2, center[1] - radius * 2))

    @staticmethod
    def _draw_hex_ring(
        surface: pygame.Surface,
        center: tuple[int, int],
        color: tuple,
        radius: int,
    ) -> None:
        points = [
            (
                center[0] + int(radius * math.cos(math.radians(60 * i - 30))),
                center[1] + int(radius * math.sin(math.radians(60 * i - 30))),
            )
            for i in range(6)
        ]
        pygame.draw.polygon(surface, color, points, 2)

    def _draw_top_bar(self, surface: pygame.Surface) -> None:
        bar = pygame.Rect(0, 0, WINDOW_WIDTH, TOP_BAR_H)
        pygame.draw.rect(surface, (10, 10, 28), bar)
        pygame.draw.line(surface, C_BORDER, (0, TOP_BAR_H - 1), (WINDOW_WIDTH, TOP_BAR_H - 1))

        galaxy = self.app.galaxy
        gs     = self.app.game_state
        disc   = gs.discovered_count()
        total  = len(galaxy.solar_systems)

        title = font(18, bold=True).render(galaxy.name.upper(), True, C_ACCENT)
        surface.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 8))

        info = font(13).render(
            f"Discovered: {disc}/{total}   Seed: {galaxy.seed}",
            True, C_TEXT_DIM,
        )
        surface.blit(info, (WINDOW_WIDTH // 2 - info.get_width() // 2, 30))

    def _draw_bottom_bar(self, surface: pygame.Surface) -> None:
        bar_y = WINDOW_HEIGHT - BOTTOM_BAR_H
        bar   = pygame.Rect(0, bar_y, WINDOW_WIDTH, BOTTOM_BAR_H)
        pygame.draw.rect(surface, (10, 10, 28), bar)
        pygame.draw.line(surface, C_BORDER, (0, bar_y), (WINDOW_WIDTH, bar_y))

        # Selected system info (left side)
        gs = self.app.game_state
        if self._selected_id:
            sys = next(
                (s for s in self.app.galaxy.solar_systems if s.id == self._selected_id),
                None,
            )
            state = gs.get_state(self._selected_id)
            if sys and state in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                label = (
                    f"SELECTED: {sys.name}  [{sys.star.star_type.value}]"
                    f"  Pl:{sys.num_planets}  Co:{sys.num_comets}  As:{sys.num_asteroids}"
                )
            elif sys and state == DiscoveryState.DETECTED:
                label = "SELECTED: ??? (scan to reveal)"
            else:
                label = "Select a system"
        else:
            label = "Select a system"

        lbl_surf = font(13).render(label, True, C_TEXT)
        surface.blit(lbl_surf, (12, bar_y + (BOTTOM_BAR_H - lbl_surf.get_height()) // 2))

        # Enter-system button (right side)
        can_enter = bool(
            self._selected_id and gs.can_enter(self._selected_id)
        )
        bg    = (C_BTN_HOV if self._btn_hovered and can_enter else
                 C_BTN     if can_enter else
                 (30, 30, 50))
        txt_c = C_BTN_TXT if can_enter else (70, 70, 90)
        pygame.draw.rect(surface, bg, self._btn_rect, border_radius=5)
        pygame.draw.rect(surface, C_BORDER if can_enter else (40, 40, 60),
                         self._btn_rect, width=1, border_radius=5)
        btn_lbl = font(14, bold=True).render("ENTER SYSTEM ▶", True, txt_c)
        surface.blit(btn_lbl, btn_lbl.get_rect(center=self._btn_rect.center))

    # ------------------------------------------------------------------
    # External API

    def mark_fog_dirty(self) -> None:
        self._fog_dirty = True
