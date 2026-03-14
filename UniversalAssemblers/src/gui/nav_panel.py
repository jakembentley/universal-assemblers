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
from . import constants as _c
from .constants import (
    NAV_W, TASKBAR_H, HEADER_H, ROW_H, PADDING,
    C_PANEL, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_SELECTED, C_HOVER, C_SEP, C_WARN, C_SCROLLBAR, BODY_COLORS, STAR_COLORS,
    font,
)
from .widgets import ScrollableList, draw_panel, draw_separator, TextInput
from ..game_state import DiscoveryState


class NavPanel:

    def __init__(self, app) -> None:
        self.app = app

        _top_h  = _c.TOP_H
        _SYS_H  = int(_top_h * 0.28)
        _BODY_H = int(_top_h * 0.37)
        _STAT_H = _top_h - _SYS_H - _BODY_H

        sys_rect   = pygame.Rect(0, TASKBAR_H,                       NAV_W, _SYS_H)
        body_rect  = pygame.Rect(0, TASKBAR_H + _SYS_H,             NAV_W, _BODY_H)
        self.stat_rect = pygame.Rect(0, TASKBAR_H + _SYS_H + _BODY_H, NAV_W, _STAT_H)

        self._stat_scroll: int   = 0
        self._stat_content_h: int = 300  # updated each draw pass

        self._sys_list  = ScrollableList(sys_rect,  "Solar Systems", on_select=self._on_system_select)
        self._body_list = ScrollableList(body_rect, "Celestial Bodies", on_select=self._on_body_select)

        # Name-editing state
        self._name_input: TextInput | None = None
        self._editing_body: object | None = None
        self._edit_icon_rect: pygame.Rect | None = None

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
        gs = self.app.game_state
        items = []
        for s in galaxy.solar_systems:
            if gs:
                state = gs.get_state(s.id)
                if state not in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                    continue
            items.append((s.name, s.id, STAR_COLORS.get(s.star.star_type.value)))
        self._sys_list.set_items(items)
        sys = self.app.selected_system
        if sys:
            self._sys_list.set_selected(sys.id)

    def _rebuild_bodies(self) -> None:
        system = self.app.selected_system
        if not system:
            self._body_list.set_items([])
            return

        gs = self.app.game_state

        # Gate body list on probe status
        if gs and not gs.is_probed(system.id):
            self._body_list.set_items([
                ("  ⚠  Send a Probe to reveal", "_probe_hint", C_WARN),
            ])
            return

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
        self._stat_scroll = 0

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            # If name input is active, route all events to it
            if self._name_input is not None:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        # Commit the name change
                        if self._editing_body is not None and self._name_input.text.strip():
                            self._editing_body.name = self._name_input.text.strip()
                        self._name_input = None
                        self._editing_body = None
                        continue
                    elif event.key == pygame.K_ESCAPE:
                        # Cancel
                        self._name_input = None
                        self._editing_body = None
                        continue
                self._name_input.handle_event(event)
                continue

            # Check for edit icon click
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and self._edit_icon_rect is not None
                    and self._edit_icon_rect.collidepoint(event.pos)):
                # Start editing the currently selected body's name
                body_id = self.app.selected_body_id
                system  = self.app.selected_system
                if body_id and system:
                    edit_obj = None
                    if body_id == system.star.id:
                        edit_obj = system.star
                    else:
                        for ob in system.orbital_bodies:
                            if ob.id == body_id:
                                edit_obj = ob
                                break
                            for m in ob.moons:
                                if m.id == body_id:
                                    edit_obj = m
                                    break
                            if edit_obj:
                                break
                    if edit_obj is not None:
                        # Full-width input that sits at the top of the stat panel
                        input_rect = pygame.Rect(
                            self.stat_rect.x + PADDING,
                            self.stat_rect.y + PADDING,
                            self.stat_rect.width - PADDING * 2,
                            26,
                        )
                        self._name_input = TextInput(input_rect, edit_obj.name, font_size=12)
                        self._name_input.active = True
                        self._editing_body = edit_obj
                continue

            if event.type == pygame.MOUSEWHEEL:
                if self.stat_rect.collidepoint(pygame.mouse.get_pos()):
                    visible_h = self.stat_rect.height - HEADER_H
                    max_scroll = max(0, self._stat_content_h - visible_h)
                    self._stat_scroll = max(0, min(max_scroll,
                                                   self._stat_scroll - event.y * ROW_H))
                    continue

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
        # Draw active name input if present
        if self._name_input is not None:
            self._name_input.draw(surface)

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
        _content_top = content.y + 6
        y = _content_top - self._stat_scroll

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
            surface.blit(name, (x, y))
            # Edit icon
            icon_x = x + name.get_width() + 6
            icon_surf = font(12).render("✎", True, C_TEXT_DIM)
            surface.blit(icon_surf, (icon_x, y))
            self._edit_icon_rect = pygame.Rect(icon_x, y, icon_surf.get_width() + 4, icon_surf.get_height())
            y += 20
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
                surface.blit(name, (x, y))
                icon_x = x + name.get_width() + 6
                icon_surf = font(12).render("✎", True, C_TEXT_DIM)
                surface.blit(icon_surf, (icon_x, y))
                self._edit_icon_rect = pygame.Rect(icon_x, y, icon_surf.get_width() + 4, icon_surf.get_height())
                y += 20
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
                surface.blit(name, (x, y))
                icon_x = x + name.get_width() + 6
                icon_surf = font(12).render("✎", True, C_TEXT_DIM)
                surface.blit(icon_surf, (icon_x, y))
                self._edit_icon_rect = pygame.Rect(icon_x, y, icon_surf.get_width() + 4, icon_surf.get_height())
                y += 20
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
                # Power balance
                gs = self.app.game_state
                if gs:
                    from ..models.entity import compute_energy_balance
                    prod, cons = compute_energy_balance(gs, body.id)
                    if prod > 0 or cons > 0:
                        surplus = prod - cons
                        pcol = (80, 220, 100) if surplus >= 0 else (255, 80, 80)
                        txt("Power",
                            f"+{prod:,.0f} / -{cons:,.0f}  ({surplus:+.0f})",
                            value_col=pcol)
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

        # Record total content height for scroll clamping
        self._stat_content_h = max(1, y + self._stat_scroll - _content_top)

        # Scrollbar
        visible_h = content.height
        if self._stat_content_h > visible_h:
            bar_h = max(20, int(visible_h * visible_h / self._stat_content_h))
            max_scroll = self._stat_content_h - visible_h
            bar_y = content.y + int((visible_h - bar_h) * self._stat_scroll / max_scroll)
            pygame.draw.rect(surface, C_SCROLLBAR,
                             pygame.Rect(content.right - 5, bar_y, 4, bar_h),
                             border_radius=2)

        surface.set_clip(old_clip)

