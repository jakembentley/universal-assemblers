"""
Right-side orbital map panel.

Two view modes:
  • "system"  — star at centre, all orbital bodies shown with orbit rings.
  • "planet"  — selected planet at centre, its moons shown orbiting.

Click a body to select it.  Double-click a planet to zoom into planet mode.
Click the back button (or double-click empty space) to return to system mode.
"""
from __future__ import annotations

import math
import time
import random

import pygame
from . import constants as _c
from .constants import (
    NAV_W, TASKBAR_H, HEADER_H, PADDING,
    C_BG, C_PANEL, C_BORDER, C_HEADER, C_ACCENT, C_TEXT, C_TEXT_DIM,
    C_SELECTED, C_HOVER, C_BTN, C_BTN_HOV, C_BTN_TXT,
    STAR_COLORS, BODY_COLORS, font,
)
from .widgets import draw_panel, Button


_ORBIT_COLOR   = (22, 45, 80)
_ORBIT_SEL     = (50, 100, 160)
_GLOW_STEPS    = 5


class MapPanel:

    def __init__(self, app) -> None:
        self.app  = app
        self.rect = pygame.Rect(NAV_W, TASKBAR_H, _c.MAP_W, _c.TOP_H)

        self._mode = "system"    # "system" | "planet"
        self._zoom_body_id: str | None = None

        # Stable per-body angles (seed from body id hash)
        self._body_angles: dict[str, float] = {}

        # Click detection cache: body_id -> (screen_x, screen_y, click_r)
        self._hit_targets: list[tuple[str, int, int, int]] = []

        # Double-click detection
        self._last_click_time  = 0.0
        self._last_click_id: str | None = None

        # Back button (only visible in planet mode)
        self._back_btn = Button(
            (self.rect.x + PADDING, self.rect.y + HEADER_H + PADDING, 90, 26),
            "◀  SYSTEM",
            callback=self._go_back,
            font_size=12,
        )

        # Pre-bake a star field for this panel only
        rng = random.Random(0xCAFEBABE)
        self._bg_stars = [
            (
                rng.randint(NAV_W, NAV_W + _c.MAP_W),
                rng.randint(TASKBAR_H, TASKBAR_H + _c.TOP_H),
                rng.randint(1, 2),
                rng.uniform(0.3, 1.0),
            )
            for _ in range(180)
        ]

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if not self.rect.collidepoint(pygame.mouse.get_pos()):
                if event.type not in (pygame.MOUSEBUTTONDOWN,):
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and not self.rect.collidepoint(event.pos):
                    continue

            if self._mode == "planet":
                self._back_btn.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.rect.collidepoint(event.pos):
                    self._handle_click(event.pos)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if self.rect.collidepoint(event.pos):
                    if self._mode == "planet":
                        self._go_back()          # planet view → system view
                    else:
                        self.app.back_to_galaxy()  # system view → galaxy map

    def _handle_click(self, pos: tuple[int, int]) -> None:
        hit_id = self._find_hit(pos)
        if hit_id is None:
            return

        # Orbital structure square click
        if hit_id.endswith("_orbital_struct"):
            system = self.app.selected_system
            if system:
                self.app.open_entity_view("structure", "extractor", system.id, None)
            return

        now = time.time()
        double = (hit_id == self._last_click_id and now - self._last_click_time < 0.35)
        self._last_click_time = now
        self._last_click_id   = hit_id

        self.app.select_body(hit_id)

        if double:
            system = self.app.selected_system
            if system:
                # Find if it's a planet with moons — zoom in
                for body in system.orbital_bodies:
                    if body.id == hit_id and body.moons:
                        self._mode = "planet"
                        self._zoom_body_id = hit_id
                        return

    def _find_hit(self, pos: tuple[int, int]) -> str | None:
        best_id   = None
        best_dist = float("inf")
        for body_id, bx, by, cr in self._hit_targets:
            d = math.hypot(pos[0] - bx, pos[1] - by)
            if d <= cr and d < best_dist:
                best_dist = d
                best_id   = body_id
        return best_id

    def _go_back(self) -> None:
        self._mode = "system"
        self._zoom_body_id = None

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, C_PANEL, self.rect)
        self._draw_bg_stars(surface)

        system = self.app.selected_system
        if not system:
            self._draw_placeholder(surface)
        elif self._mode == "planet" and self._zoom_body_id:
            planet = next(
                (b for b in system.orbital_bodies if b.id == self._zoom_body_id), None
            )
            if planet and planet.moons:
                self._draw_planet_view(surface, system, planet)
            else:
                self._mode = "system"
                self._draw_system_view(surface, system)
        else:
            self._draw_system_view(surface, system)

        pygame.draw.rect(surface, (30, 60, 110), self.rect, width=1)

    def _draw_bg_stars(self, surface: pygame.Surface) -> None:
        for x, y, r, b in self._bg_stars:
            v = int(b * 160)
            pygame.draw.circle(surface, (v, v, min(255, int(v * 1.15))), (x, y), r)

    def _draw_placeholder(self, surface: pygame.Surface) -> None:
        msg = font(16).render("No galaxy loaded.", True, C_TEXT_DIM)
        cx  = self.rect.centerx
        cy  = self.rect.centery
        surface.blit(msg, msg.get_rect(center=(cx, cy)))

    # ------------------------------------------------------------------
    # System view

    def _draw_system_view(self, surface: pygame.Surface, system) -> None:
        self._hit_targets = []
        cx = self.rect.centerx
        cy = self.rect.centery

        t = time.time() * 0.5   # global time, halved for slower orbits

        # Scale: fit the 5 AU zone comfortably, compress outer orbits
        max_r_px = min(MAP_W, TOP_H) * 0.44

        gs = self.app.game_state
        is_probed = gs.is_probed(system.id) if gs else False

        # Show probe-required overlay if unprobed
        if not is_probed:
            self._draw_probe_required(surface, system)
            return

        # 1. Orbit rings (draw before bodies)
        for body in system.orbital_bodies:
            r_px = self._au_to_px(body.orbital_radius, max_r_px)
            color = _ORBIT_SEL if body.id == self.app.selected_body_id else _ORBIT_COLOR
            pygame.draw.circle(surface, color, (cx, cy), int(r_px), 1)

        # 2. Star
        star      = system.star
        star_col  = STAR_COLORS.get(star.star_type.value, (255, 220, 80))
        star_r    = max(10, min(22, int(star.mass * 9)))
        self._draw_glow(surface, cx, cy, star_r + 12, star_col, steps=6)
        pygame.draw.circle(surface, star_col, (cx, cy), star_r)
        self._hit_targets.append((star.id, cx, cy, star_r + 6))

        # Highlight ring if star selected
        if self.app.selected_body_id == star.id:
            pygame.draw.circle(surface, C_SELECTED, (cx, cy), star_r + 5, 2)

        # 3. Orbital structure icon (square) near the star
        if gs:
            orbital_structs = [
                i for i in gs.entity_roster.at(system.id)
                if i.category == "structure"
            ]
            if orbital_structs:
                struct_total = sum(i.count for i in orbital_structs)
                sq_x = cx + star_r + 14
                sq_y = cy - 8
                sq_r = pygame.Rect(sq_x, sq_y, 16, 16)
                pygame.draw.rect(surface, (0, 60, 100), sq_r)
                pygame.draw.rect(surface, C_ACCENT, sq_r, width=1)
                sq_lbl = font(9, bold=True).render(str(struct_total), True, C_ACCENT)
                surface.blit(sq_lbl, sq_lbl.get_rect(center=sq_r.center))
                self._hit_targets.append((system.id + "_orbital_struct",
                                          sq_r.centerx, sq_r.centery, 12))

        # 4. Orbital bodies
        for body in system.orbital_bodies:
            r_px   = self._au_to_px(body.orbital_radius, max_r_px)
            angle  = self._orbit_angle(body.id, body.orbital_radius, t)
            bx     = int(cx + math.cos(angle) * r_px)
            by     = int(cy + math.sin(angle) * r_px)

            col, vis_r = self._body_visuals(body)
            selected   = body.id == self.app.selected_body_id

            if selected:
                pygame.draw.circle(surface, C_SELECTED, (bx, by), vis_r + 4, 2)
            if body.body_type.value in ("planet", "exoplanet") and vis_r >= 4:
                self._draw_glow(surface, bx, by, vis_r + 4, col, steps=3)

            pygame.draw.circle(surface, col, (bx, by), max(2, vis_r))
            self._hit_targets.append((body.id, bx, by, max(vis_r + 3, 8)))

        # 5. Ships animated in orbit
        self._draw_ships(surface, system, cx, cy, max_r_px, t)

        # 6. Labels for selected body
        self._draw_system_label(surface, system)

    def _draw_probe_required(self, surface: pygame.Surface, system) -> None:
        """Show a message when the system has not been probed yet."""
        star     = system.star
        star_col = STAR_COLORS.get(star.star_type.value, (255, 220, 80))
        cx, cy   = self.rect.centerx, self.rect.centery

        # Dim star silhouette
        self._draw_glow(surface, cx, cy, 40, star_col, steps=4)
        pygame.draw.circle(surface, tuple(c // 3 for c in star_col), (cx, cy), 14)

        msg1 = font(15, bold=True).render("SYSTEM UNPROBED", True, C_ACCENT)
        msg2 = font(12).render(
            "Send a Probe or Drop Ship here to reveal body details.",
            True, C_TEXT_DIM,
        )
        surface.blit(msg1, msg1.get_rect(center=(cx, cy + 50)))
        surface.blit(msg2, msg2.get_rect(center=(cx, cy + 72)))

    def _draw_system_label(self, surface: pygame.Surface, system) -> None:
        """System name + star type in top-right corner of map panel."""
        name_surf = font(14, bold=True).render(system.name, True, C_ACCENT)
        type_surf = font(12).render(system.star.star_type.value, True, C_TEXT_DIM)
        rx = self.rect.right - PADDING
        ry = self.rect.y + HEADER_H + PADDING
        surface.blit(name_surf, (rx - name_surf.get_width(), ry))
        surface.blit(type_surf, (rx - type_surf.get_width(), ry + 20))

        # Body count line
        counts = (
            f"{system.num_planets}pl  "
            f"{system.num_exoplanets}ep  "
            f"{system.num_comets}co  "
            f"{system.num_asteroids}ast"
        )
        ct_surf = font(11).render(counts, True, C_TEXT_DIM)
        surface.blit(ct_surf, (rx - ct_surf.get_width(), ry + 38))

    # ------------------------------------------------------------------
    # Planet / moon zoom view

    def _draw_planet_view(self, surface: pygame.Surface, system, planet) -> None:
        self._hit_targets = []
        cx = self.rect.centerx
        cy = self.rect.centery
        t  = time.time() * 0.5

        max_r_px = min(MAP_W, TOP_H) * 0.38

        # Orbit rings for moons
        for i, moon in enumerate(planet.moons):
            moon_r_au = (i + 1) * 0.06   # synthetic spacing for display
            r_px = self._au_to_px(moon_r_au, max_r_px, scale_max=0.5)
            pygame.draw.circle(surface, _ORBIT_COLOR, (cx, cy), int(r_px), 1)

        # Planet at centre
        col, vis_r = self._body_visuals(planet)
        vis_r = max(vis_r, 14)
        self._draw_glow(surface, cx, cy, vis_r + 8, col, steps=4)
        pygame.draw.circle(surface, col, (cx, cy), vis_r)
        self._hit_targets.append((planet.id, cx, cy, vis_r + 6))
        if self.app.selected_body_id == planet.id:
            pygame.draw.circle(surface, C_SELECTED, (cx, cy), vis_r + 5, 2)

        # Moons
        for i, moon in enumerate(planet.moons):
            moon_r_au = (i + 1) * 0.06
            r_px  = self._au_to_px(moon_r_au, max_r_px, scale_max=0.5)
            speed = 0.08 / (moon_r_au ** 0.5)
            phase = (hash(moon.id) % 628) / 100.0
            angle = t * speed + phase
            mx    = int(cx + math.cos(angle) * r_px)
            my    = int(cy + math.sin(angle) * r_px)

            moon_col  = BODY_COLORS["moon"]
            moon_vis_r = max(3, int(moon.size * 6))
            selected  = moon.id == self.app.selected_body_id

            if selected:
                pygame.draw.circle(surface, C_SELECTED, (mx, my), moon_vis_r + 4, 2)
            pygame.draw.circle(surface, moon_col, (mx, my), moon_vis_r)
            self._hit_targets.append((moon.id, mx, my, moon_vis_r + 6))

        # Label
        name_surf = font(14, bold=True).render(planet.name, True, col)
        type_surf = font(12).render(
            f"{planet.subtype or planet.body_type.value}  •  {len(planet.moons)} moons",
            True, C_TEXT_DIM,
        )
        rx = self.rect.right - PADDING
        ry = self.rect.y + HEADER_H + PADDING
        surface.blit(name_surf, (rx - name_surf.get_width(), ry + 34))
        surface.blit(type_surf, (rx - type_surf.get_width(), ry + 54))

        # Back button
        self._back_btn.draw(surface)

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _au_to_px(au: float, max_r_px: float, scale_max: float = 1.0) -> float:
        """Logarithmic AU → pixel mapping so outer orbits don't disappear."""
        return math.log(au + 1) / math.log(41) * max_r_px * scale_max

    def _orbit_angle(self, body_id: str, au: float, t: float) -> float:
        if body_id not in self._body_angles:
            self._body_angles[body_id] = (hash(body_id) % 628) / 100.0
        speed = 0.025 / max(au, 0.05) ** 0.5
        return t * speed + self._body_angles[body_id]

    @staticmethod
    def _body_visuals(body) -> tuple[tuple, int]:
        btype  = body.body_type.value
        if btype == "planet":
            col = BODY_COLORS.get(body.subtype or "", (100, 160, 220))
            r   = max(4, min(13, int(getattr(body, "size", 4))))
        elif btype == "exoplanet":
            col = BODY_COLORS["exoplanet"]
            r   = max(4, min(9, int(getattr(body, "size", 3))))
        elif btype == "comet":
            col = BODY_COLORS["comet"]
            r   = 3
        elif btype == "asteroid":
            col = BODY_COLORS["asteroid"]
            r   = 2
        else:
            col = BODY_COLORS.get(btype, (160, 160, 180))
            r   = 4
        return col, r

    @staticmethod
    def _draw_glow(
        surface: pygame.Surface,
        cx: int, cy: int,
        max_r: int,
        color: tuple,
        steps: int = _GLOW_STEPS,
    ) -> None:
        for i in range(steps, 0, -1):
            r     = int(max_r * i / steps)
            alpha = int(30 * (1 - i / steps) + 5)
            gs    = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*color[:3], alpha), (r, r), r)
            surface.blit(gs, (cx - r, cy - r), special_flags=pygame.BLEND_RGBA_ADD)

    # ------------------------------------------------------------------
    # Ship animation

    _SHIP_COLORS: dict = {
        "probe":         (0, 220, 255),
        "drop_ship":     (255, 180, 60),
        "mining_vessel": (220, 200, 80),
        "transport":     (140, 220, 140),
        "warship":       (255, 80,  80),
    }
    _SHIP_COLOR_DEFAULT = (180, 180, 220)

    def _draw_ships(
        self,
        surface: pygame.Surface,
        system,
        cx: int, cy: int,
        max_r_px: float,
        t: float,
    ) -> None:
        gs = self.app.game_state
        if not gs:
            return

        # Ships stationed at system level orbit close to the star
        sys_ships = [i for i in gs.entity_roster.at(system.id) if i.category == "ship"]
        for idx, inst in enumerate(sys_ships):
            base_r = 36 + idx * 16
            speed  = 0.9 / (base_r / 30) ** 0.5
            phase  = (hash(inst.type_value + "sys") % 628) / 100.0
            col    = self._SHIP_COLORS.get(inst.type_value, self._SHIP_COLOR_DEFAULT)
            for k in range(min(inst.count, 3)):
                angle = t * 2 * speed + phase + k * 0.45
                sx = int(cx + math.cos(angle) * base_r)
                sy = int(cy + math.sin(angle) * base_r)
                self._draw_ship_icon(surface, sx, sy, angle + math.pi / 2, col)

        # Ships at body level orbit just outside their body
        for body in system.orbital_bodies:
            body_r_px   = self._au_to_px(body.orbital_radius, max_r_px)
            body_angle  = self._orbit_angle(body.id, body.orbital_radius, t)
            bx = int(cx + math.cos(body_angle) * body_r_px)
            by = int(cy + math.sin(body_angle) * body_r_px)

            body_ships = [i for i in gs.entity_roster.at(body.id) if i.category == "ship"]
            for idx, inst in enumerate(body_ships):
                orbit_r = 16 + idx * 10
                speed   = 1.2
                phase   = (hash(inst.type_value + body.id) % 628) / 100.0
                col     = self._SHIP_COLORS.get(inst.type_value, self._SHIP_COLOR_DEFAULT)
                for k in range(min(inst.count, 3)):
                    angle = t * 2 * speed + phase + k * 0.5
                    sx = int(bx + math.cos(angle) * orbit_r)
                    sy = int(by + math.sin(angle) * orbit_r)
                    self._draw_ship_icon(surface, sx, sy, angle + math.pi / 2, col)

    @staticmethod
    def _draw_ship_icon(
        surface: pygame.Surface,
        x: int, y: int,
        heading: float,
        color: tuple,
        size: int = 4,
    ) -> None:
        tip   = (int(x + math.cos(heading) * size * 2),
                 int(y + math.sin(heading) * size * 2))
        left  = (int(x + math.cos(heading + 2.3) * size),
                 int(y + math.sin(heading + 2.3) * size))
        right = (int(x + math.cos(heading - 2.3) * size),
                 int(y + math.sin(heading - 2.3) * size))
        pygame.draw.polygon(surface, color, [tip, left, right])

    # ------------------------------------------------------------------

    def on_system_changed(self) -> None:
        self._mode = "system"
        self._zoom_body_id = None
        self._body_angles  = {}
