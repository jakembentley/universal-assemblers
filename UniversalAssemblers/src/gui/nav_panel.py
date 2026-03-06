"""
Left navigation panel.

Layout (top to bottom, within NAV_W x TOP_H):
  ┌──────────────────────┐
  │  SOLAR SYSTEMS list  │  ~30 % of height
  ├──────────────────────┤
  │  BODIES list         │  ~35 % of height
  ├──────────────────────┤
  │  SELECTED BODY STATS │  ~35 % of height
  └──────────────────────┘
"""
from __future__ import annotations

import pygame
from .constants import (
    NAV_W, TOP_H, HEADER_H, ROW_H, PADDING,
    C_PANEL, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_SELECTED, C_HOVER, C_SEP, C_WARN, BODY_COLORS, STAR_COLORS,
    font,
)
from .widgets import ScrollableList, draw_panel, draw_separator


_SYS_H   = int(TOP_H * 0.28)
_BODY_H  = int(TOP_H * 0.37)
_STAT_H  = TOP_H - _SYS_H - _BODY_H


class NavPanel:

    def __init__(self, app) -> None:
        self.app = app

        sys_rect   = pygame.Rect(0, 0,      NAV_W, _SYS_H)
        body_rect  = pygame.Rect(0, _SYS_H, NAV_W, _BODY_H)
        self.stat_rect = pygame.Rect(0, _SYS_H + _BODY_H, NAV_W, _STAT_H)

        self._sys_list  = ScrollableList(sys_rect,  "Solar Systems", on_select=self._on_system_select)
        self._body_list = ScrollableList(body_rect, "Celestial Bodies", on_select=self._on_body_select)

        self._rebuild_systems()
        self._rebuild_bodies()

    # ------------------------------------------------------------------
    # Callbacks

    def _on_system_select(self, sys_id: str) -> None:
        galaxy = self.app.galaxy
        if not galaxy:
            return
        self.app.close_entity_view()
        idx = next((i for i, s in enumerate(galaxy.solar_systems) if s.id == sys_id), 0)
        self.app.select_system(idx)

    def _on_body_select(self, body_id: str) -> None:
        self.app.close_entity_view()
        self.app.select_body(body_id)

    # ------------------------------------------------------------------
    # State rebuild helpers

    def _rebuild_systems(self) -> None:
        galaxy = self.app.galaxy
        if not galaxy:
            self._sys_list.set_items([])
            return
        items = [
            (s.name, s.id, STAR_COLORS.get(s.star.star_type.value))
            for s in galaxy.solar_systems
        ]
        self._sys_list.set_items(items)
        sys = self.app.selected_system
        if sys:
            self._sys_list.set_selected(sys.id)

    def _rebuild_bodies(self) -> None:
        system = self.app.selected_system
        if not system:
            self._body_list.set_items([])
            return

        gs         = self.app.game_state
        bio_state  = gs.bio_state  if gs else None
        roster     = gs.entity_roster if gs else None

        def _indicators(body_id: str) -> str:
            parts = []
            if bio_state and bio_state.get(body_id):
                pop = bio_state.get(body_id)
                from ..simulation import BioType
                parts.append("U" if pop.bio_type == BioType.UPLIFTED else "b")
            if roster:
                n = sum(i.count for i in roster.at(body_id))
                if n:
                    parts.append(f"[{n}]")
            return (" " + " ".join(parts)) if parts else ""

        items: list[tuple[str, str, tuple | None]] = []

        star_col = STAR_COLORS.get(system.star.star_type.value, (255, 220, 80))
        items.append((f"★ {system.star.name}", system.star.id, star_col))

        for body in system.orbital_bodies:
            btype   = body.body_type.value
            subtype = body.subtype or btype
            color   = BODY_COLORS.get(subtype, BODY_COLORS.get(btype))
            short   = body.name.replace(system.name + " ", "")

            if btype == "planet":
                prefix = "◉"
            elif btype == "exoplanet":
                prefix = "◎"
            elif btype == "comet":
                prefix = "☄"
            elif btype == "asteroid":
                prefix = "·"
            else:
                prefix = "○"

            ind = _indicators(body.id)
            items.append((f"{prefix} {short}{ind}", body.id, color))

            for moon in body.moons:
                moon_short = moon.name.replace(body.name + "-", "")
                mind = _indicators(moon.id)
                items.append((f"  ◦ {moon_short}{mind}", moon.id, BODY_COLORS["moon"]))

        self._body_list.set_items(items)
        self._body_list.set_selected(self.app.selected_body_id)

    # ------------------------------------------------------------------
    # Public update hooks

    def on_system_changed(self) -> None:
        self._rebuild_systems()
        self._rebuild_bodies()

    def on_body_changed(self) -> None:
        self._body_list.set_selected(self.app.selected_body_id)

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._sys_list.handle_event(event)
            self._body_list.handle_event(event)

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        # Rebuild body list each frame so entity/bio indicators stay current
        self._rebuild_bodies()
        self._sys_list.draw(surface)
        self._body_list.draw(surface)
        self._draw_stats(surface)

    def _draw_stats(self, surface: pygame.Surface) -> None:
        rect = self.stat_rect
        content = draw_panel(surface, rect, "Selected Body")

        body_id = self.app.selected_body_id
        system  = self.app.selected_system

        if not system or not body_id:
            msg = font(12).render("No body selected.", True, C_TEXT_DIM)
            surface.blit(msg, (content.x + PADDING, content.y + PADDING))
            return

        x = content.x + PADDING
        y = content.y + 6

        def txt(label: str, value: str, label_col=C_TEXT_DIM, value_col=C_TEXT) -> None:
            nonlocal y
            lbl  = font(12).render(label, True, label_col)
            val  = font(12, bold=True).render(value, True, value_col)
            surface.blit(lbl, (x, y))
            surface.blit(val, (content.right - val.get_width() - PADDING, y))
            y += ROW_H - 2

        def section(title: str) -> None:
            nonlocal y
            y += 4
            draw_separator(surface, x, y, content.right - PADDING)
            s = font(11, bold=True).render(title, True, C_ACCENT)
            surface.blit(s, (x, y + 3))
            y += 18

        # Clip overflow
        old_clip = surface.get_clip()
        surface.set_clip(content)

        # --- Star ---
        if body_id == system.star.id:
            star = system.star
            sc   = STAR_COLORS.get(star.star_type.value, (255, 220, 80))
            name = font(13, bold=True).render(star.name, True, sc)
            surface.blit(name, (x, y)); y += 20
            txt("Class",  star.star_type.value, value_col=sc)
            txt("Mass",   f"{star.mass:.3f} M☉")
            section("Resources")
            res = star.resources
            txt("Gas",    f"{res.gas:,.0f}")
            txt("Energy", f"{res.energy_output:.2e}", value_col=C_WARN)

        else:
            # Orbital body or moon
            body = None
            moon = None
            for ob in system.orbital_bodies:
                if ob.id == body_id:
                    body = ob; break
                for m in ob.moons:
                    if m.id == body_id:
                        body = ob; moon = m; break
                if body:
                    break

            if moon:
                mc   = BODY_COLORS["moon"]
                name = font(13, bold=True).render(moon.name, True, mc)
                surface.blit(name, (x, y)); y += 20
                txt("Type",   "Moon")
                txt("Parent", body.name.replace(system.name + " ", ""), value_col=C_TEXT_DIM)
                txt("Size",   f"{moon.size:.3f} R⊕")
                section("Resources")
                res = moon.resources
                txt("Minerals",      f"{res.minerals:,.1f}")
                txt("Rare minerals", f"{res.rare_minerals:,.1f}", value_col=C_SELECTED)
                txt("Ice",           f"{res.ice:,.1f}")
                txt("Gas",           f"{res.gas:,.1f}")
                if res.bios:
                    txt("Bios",      f"{res.bios:,.1f}", value_col=(80, 200, 100))
                # Bio population
                gs = self.app.game_state
                if gs:
                    pop = gs.bio_state.get(moon.id)
                    if pop:
                        section("Bio Population")
                        from ..simulation import BioType as _BT
                        txt("Type",       pop.bio_type.value.capitalize())
                        txt("Population", f"{pop.population:,.0f}",
                            value_col=(255, 80, 80) if pop.bio_type == _BT.UPLIFTED else (80, 200, 100))
                        txt("Aggression", f"{pop.aggression:.0%}",
                            value_col=C_WARN if pop.aggression > 0.65 else C_TEXT)

            elif body:
                btype  = body.body_type.value
                subtype = body.subtype or btype
                bc     = BODY_COLORS.get(subtype, BODY_COLORS.get(btype, C_TEXT))
                short  = body.name.replace(system.name + " ", "")
                name   = font(13, bold=True).render(body.name, True, bc)
                surface.blit(name, (x, y)); y += 20
                txt("Type",   btype.capitalize())
                if body.subtype:
                    txt("Class", body.subtype.replace("_", " ").title(), value_col=bc)
                txt("Orbit",  f"{body.orbital_radius:.2f} AU")
                txt("Size",   f"{body.size:.3f} R⊕")
                if body.moons:
                    txt("Moons", str(len(body.moons)), value_col=C_ACCENT)
                section("Resources")
                res = body.resources
                txt("Minerals",      f"{res.minerals:,.1f}")
                txt("Rare minerals", f"{res.rare_minerals:,.1f}", value_col=C_SELECTED)
                txt("Ice",           f"{res.ice:,.1f}")
                txt("Gas",           f"{res.gas:,.1f}")
                if res.bios:
                    txt("Bios",      f"{res.bios:,.1f}", value_col=(80, 200, 100))
                if res.energy_output:
                    txt("Energy",    f"{res.energy_output:.2e}", value_col=C_WARN)
                # Bio population
                gs = self.app.game_state
                if gs:
                    pop = gs.bio_state.get(body.id)
                    if pop:
                        section("Bio Population")
                        from ..simulation import BioType as _BT
                        txt("Type",       pop.bio_type.value.capitalize())
                        txt("Population", f"{pop.population:,.0f}",
                            value_col=(255, 80, 80) if pop.bio_type == _BT.UPLIFTED else (80, 200, 100))
                        txt("Aggression", f"{pop.aggression:.0%}",
                            value_col=C_WARN if pop.aggression > 0.65 else C_TEXT)
                        txt("Growth",     f"{pop.growth_rate:.1%}/yr")

        surface.set_clip(old_clip)

