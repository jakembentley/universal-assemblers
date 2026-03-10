"""
Entity detail view — replaces the map panel when an entity row is clicked.

Activated via App.open_entity_view(category, type_value, system_id, body_id).
Deactivated via App.close_entity_view() or ESC key.

Panel layout (right side: NAV_W → WINDOW_WIDTH, TASKBAR_H → TOP_H+TASKBAR_H):

  ┌─────────────────────────────────────────────────────────────┐
  │  TITLE:  <EntityName>   [count]   [X CLOSE]                 │
  ├─────────────────────────────────────────────────────────────┤
  │                                                             │
  │  Content area (differs per category / type)                 │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘

Categories:
  "structure" — power output, resource I/O, count at location
  "bot"       — task list with allocation controls and add-task panel
  "ship"      — travel order queue, send-to system selector
  "bio"       — bio population stats
"""
from __future__ import annotations

import pygame
from .constants import (
    NAV_W, MAP_W, TOP_H, TASKBAR_H, HEADER_H, ROW_H, PADDING,
    C_PANEL, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_SELECTED, C_HOVER, C_WARN, C_SEP, C_BTN, C_BTN_HOV, C_BTN_TXT,
    font,
)
from .widgets import draw_panel, draw_separator, Button, ScrollableList


# ---------------------------------------------------------------------------
# Display metadata
# ---------------------------------------------------------------------------

_STRUCTURE_NAMES: dict[str, str] = {
    "extractor":             "Extractor",
    "factory":               "Factory",
    "power_plant_solar":     "Solar Farm",
    "power_plant_wind":      "Wind Farm",
    "power_plant_bios":      "Bio Plant",
    "power_plant_fossil":    "Fossil Fuel Plant",
    "power_plant_nuclear":   "Nuclear Plant",
    "power_plant_cold_fusion": "Cold Fusion Plant",
    "power_plant_dark_matter": "Dark Matter Plant",
    "research_array":        "Research Array",
    "replicator":            "Replicator",
    "shipyard":              "Shipyard",
    "storage_hub":           "Storage Hub",
}

_BOT_NAMES: dict[str, str] = {
    "worker":      "Worker Bot",
    "harvester":   "Harvester Bot",
    "miner":       "Miner Bot",
    "constructor": "Constructor Bot",
}

_SHIP_NAMES: dict[str, str] = {
    "probe":         "Probe",
    "drop_ship":     "Drop Ship",
    "mining_vessel": "Mining Vessel",
    "transport":     "Transport",
    "warship":       "Warship",
}

_TASK_TYPE_LABELS: dict[str, str] = {
    "mine":  "Mine",
    "build": "Build",
}

_MINE_RESOURCES = ["minerals", "rare_minerals", "ice", "gas", "bios"]
_MINE_RES_LABELS = {
    "minerals":      "Minerals",
    "rare_minerals": "Rare Minerals",
    "ice":           "Ice",
    "gas":           "Gas",
    "bios":          "Bios",
}

# Which task types each bot type is allowed to add
_BOT_ALLOWED_TASKS: dict[str, list[str]] = {
    "miner":       ["mine"],
    "harvester":   ["mine"],
    "constructor": ["build"],
    "worker":      ["mine", "build"],
}

# Buildable entity types for constructor tasks
_BUILD_STRUCTURES = [
    "extractor", "factory", "research_array",
    "power_plant_solar", "power_plant_wind", "power_plant_fossil",
    "power_plant_nuclear", "shipyard", "storage_hub",
]
_BUILD_BOTS = ["miner", "constructor", "worker", "harvester"]


class EntityView:
    """Overlay that replaces the map panel to show entity details."""

    def __init__(self, app) -> None:
        self.app      = app
        self.is_active = False

        self._category:    str        = ""
        self._type_value:  str        = ""
        self._system_id:   str | None = None
        self._body_id:     str | None = None

        self._rect = pygame.Rect(NAV_W, TASKBAR_H, MAP_W, TOP_H)

        self._close_btn = Button(
            (self._rect.right - 90, self._rect.y + 4, 82, HEADER_H - 6),
            "✕  CLOSE",
            callback=self._close,
            font_size=11,
        )

        # --- Bot task UI state ---
        self._add_task_mode:   bool       = False   # True when the add-task form is visible
        self._add_task_type:   str        = "mine"  # "mine" | "build"
        self._add_task_res:    str        = "minerals"
        self._add_task_amount: int        = 100
        # Hit rects populated each draw: (rect, action, data)
        self._hit_rects: list[tuple[pygame.Rect, str, object]] = []

        # --- Ship send-to UI state ---
        self._send_mode:      bool       = False
        self._send_system_id: str | None = None

        # Scrollable list for system selector
        sys_sel_rect = pygame.Rect(
            self._rect.x + PADDING,
            self._rect.y + HEADER_H + 160,
            self._rect.width - PADDING * 2,
            TOP_H - HEADER_H - 170,
        )
        self._sys_list = ScrollableList(sys_sel_rect, "Select Destination System",
                                        on_select=self._on_send_system_select)

    # ------------------------------------------------------------------
    # Activation

    def activate(
        self,
        category:   str,
        type_value: str,
        system_id:  str | None = None,
        body_id:    str | None = None,
    ) -> None:
        self.is_active    = True
        self._category    = category
        self._type_value  = type_value
        self._system_id   = system_id
        self._body_id     = body_id
        self._add_task_mode = False
        # Default task type based on bot capabilities
        allowed = _BOT_ALLOWED_TASKS.get(type_value, ["mine"])
        self._add_task_type = allowed[0]
        self._send_mode     = False
        self._send_system_id = None
        self._hit_rects      = []

        if category == "ship":
            self._rebuild_sys_list()

    def deactivate(self) -> None:
        self.is_active = False

    def _close(self) -> None:
        self.deactivate()

    # ------------------------------------------------------------------
    # Internal helpers

    def _entity_name(self) -> str:
        if self._category == "structure":
            return _STRUCTURE_NAMES.get(self._type_value, self._type_value)
        if self._category == "bot":
            return _BOT_NAMES.get(self._type_value, self._type_value)
        if self._category == "ship":
            return _SHIP_NAMES.get(self._type_value, self._type_value)
        return self._type_value.replace("_", " ").title()

    def _count_at_location(self) -> int:
        gs = self.app.game_state
        if not gs:
            return 0
        loc = self._body_id or self._system_id
        if not loc:
            return gs.entity_roster.total(self._category, self._type_value)
        return sum(
            i.count for i in gs.entity_roster.at(loc)
            if i.category == self._category and i.type_value == self._type_value
        )

    def _rebuild_sys_list(self) -> None:
        gs = self.app.game_state
        galaxy = self.app.galaxy
        if not gs or not galaxy:
            return
        from ..game_state import DiscoveryState
        import math

        # For probes: only show adjacent systems
        if self._type_value == "probe" and self._system_id:
            adjacent_ids = set(gs.adjacency.get(self._system_id, []))
            items = []
            home_pos = None
            for s in galaxy.solar_systems:
                if s.id == self._system_id:
                    home_pos = s.position
                    break

            for s in galaxy.solar_systems:
                if s.id == self._system_id:
                    continue
                if s.id not in adjacent_ids:
                    continue
                # Calculate distance + ETA
                dist_str = ""
                if home_pos:
                    dx = s.position["x"] - home_pos["x"]
                    dy = s.position["y"] - home_pos["y"]
                    dist = math.hypot(dx, dy)
                    eta_years = 1.0 / 0.25  # travel_speed = 0.25 fraction/year → 4 years
                    dist_str = f" [{dist:.0f} ly | ~{eta_years:.0f}yr]"

                if s.warp_only:
                    label = f"{s.name}{dist_str}  [Warp Drive required]"
                    items.append((label, f"_warp_{s.id}", (100, 60, 140)))
                else:
                    state = gs.get_state(s.id)
                    color = None
                    if state not in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                        color = (90, 120, 160)
                    items.append((f"{s.name}{dist_str}", s.id, color))
        else:
            # Drop ships and other ships: all discovered/colonized systems
            items = [
                (s.name, s.id, None)
                for s in galaxy.solar_systems
                if gs.get_state(s.id) in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED)
                   and s.id != self._system_id
            ]
        self._sys_list.set_items(items)

    def _on_send_system_select(self, sys_id: str) -> None:
        # Ignore warp-only pseudo-IDs
        if sys_id.startswith("_warp_"):
            return
        self._send_system_id = sys_id

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._close_btn.handle_event(event)

            if self._category == "bot":
                self._handle_bot_events(event)
            elif self._category == "ship":
                self._sys_list.handle_event(event)
                self._handle_ship_events(event)

    def _handle_bot_events(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        pos = event.pos
        for rect, action, data in self._hit_rects:
            if rect.collidepoint(pos):
                self._dispatch_bot_action(action, data)
                return

    def _dispatch_bot_action(self, action: str, data: object) -> None:
        gs = self.app.game_state
        if not gs:
            return
        loc = self._body_id or self._system_id or ""

        if action == "toggle_add_task":
            self._add_task_mode = not self._add_task_mode

        elif action == "set_task_type":
            allowed = _BOT_ALLOWED_TASKS.get(self._type_value, ["mine"])
            if str(data) in allowed:
                self._add_task_type = str(data)

        elif action == "set_res":
            self._add_task_res = str(data)

        elif action == "inc_amount":
            self._add_task_amount = min(99999, self._add_task_amount + 100)

        elif action == "dec_amount":
            self._add_task_amount = max(100, self._add_task_amount - 100)

        elif action == "confirm_add_task":
            from ..game_state import BotTask
            # Validate: only allow task types this bot can perform
            allowed = _BOT_ALLOWED_TASKS.get(self._type_value, ["mine"])
            if self._add_task_type not in allowed:
                return
            if self._add_task_type == "mine":
                task = BotTask(
                    task_type="mine",
                    resource=self._add_task_res,
                    entity_type=None,
                    target_amount=self._add_task_amount,
                )
            else:
                task = BotTask(
                    task_type="build",
                    resource=None,
                    entity_type=self._add_task_res,
                    target_amount=max(1, self._add_task_amount // 100),
                )
            gs.bot_tasks.add(loc, self._type_value, task)
            self._add_task_mode = False

        elif action == "remove_task":
            task_id = str(data)
            gs.bot_tasks.remove(loc, self._type_value, task_id)

        elif action == "alloc_inc":
            task_id, _ = data  # type: ignore
            gs.bot_tasks.adjust_allocation(loc, self._type_value, str(task_id), +10)

        elif action == "alloc_dec":
            task_id, _ = data  # type: ignore
            gs.bot_tasks.adjust_allocation(loc, self._type_value, str(task_id), -10)

    def _handle_ship_events(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        pos = event.pos
        for rect, action, data in self._hit_rects:
            if rect.collidepoint(pos):
                if action == "toggle_send":
                    self._send_mode = not self._send_mode
                    if self._send_mode:
                        self._rebuild_sys_list()
                elif action == "dispatch_ship":
                    self._dispatch_ship()
                return

    def _dispatch_ship(self) -> None:
        if not self._send_system_id:
            return
        gs = self.app.game_state
        galaxy = self.app.galaxy
        if not gs or not galaxy:
            return
        count = gs.entity_roster.total(self._category, self._type_value)
        if count == 0:
            return
        # Find first body in target system
        target_sys = next(
            (s for s in galaxy.solar_systems if s.id == self._send_system_id), None
        )
        target_body_id = (
            target_sys.orbital_bodies[0].id if target_sys and target_sys.orbital_bodies
            else None
        )
        from ..simulation import ShipOrder
        order = ShipOrder(
            order_type="travel",
            target_system_id=self._send_system_id,
            target_body_id=target_body_id,
        )
        loc = self._system_id or ""
        gs.order_queue.enqueue(loc, self._type_value, order)
        self._send_mode = False
        self._send_system_id = None
        self.deactivate()

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        self._hit_rects = []
        content = draw_panel(surface, self._rect, None)

        # Title bar
        hdr = pygame.Rect(self._rect.x, self._rect.y, self._rect.width, HEADER_H)
        pygame.draw.rect(surface, C_HEADER, hdr)
        name = self._entity_name()
        count = self._count_at_location()
        title_surf = font(13, bold=True).render(
            f"{name.upper()}  ×{count}", True, C_ACCENT
        )
        surface.blit(title_surf, (self._rect.x + PADDING, self._rect.y + 6))
        self._close_btn.draw(surface)

        draw_separator(surface, self._rect.x + PADDING, self._rect.y + HEADER_H,
                       self._rect.right - PADDING)

        # Content
        cx = self._rect.x + PADDING
        cy = self._rect.y + HEADER_H + 10

        old_clip = surface.get_clip()
        surface.set_clip(pygame.Rect(
            self._rect.x, self._rect.y + HEADER_H,
            self._rect.width, self._rect.height - HEADER_H,
        ))

        if self._category == "structure":
            cy = self._draw_structure(surface, cx, cy)
        elif self._category == "bot":
            cy = self._draw_bot(surface, cx, cy)
        elif self._category == "ship":
            cy = self._draw_ship(surface, cx, cy)
        elif self._category == "bio":
            cy = self._draw_bio(surface, cx, cy)

        surface.set_clip(old_clip)

    # ------------------------------------------------------------------
    # Structure panel

    def _draw_structure(self, surface: pygame.Surface, cx: int, cy: int) -> int:
        from ..models.entity import POWER_PLANT_SPECS, StructureType

        def txt(label: str, value: str, vcol=C_TEXT) -> None:
            nonlocal cy
            l = font(12).render(label, True, C_TEXT_DIM)
            v = font(12, bold=True).render(value, True, vcol)
            surface.blit(l, (cx, cy))
            surface.blit(v, (self._rect.right - v.get_width() - PADDING * 2, cy))
            cy += ROW_H

        loc = self._body_id or self._system_id
        txt("Location", loc or "—", C_TEXT_DIM)

        # Power plant details
        try:
            st = StructureType(self._type_value)
        except ValueError:
            st = None
        if st and st in POWER_PLANT_SPECS:
            spec = POWER_PLANT_SPECS[st]
            cy += 8
            sep_y = cy
            draw_separator(surface, cx, sep_y, self._rect.right - PADDING * 2)
            lbl = font(11, bold=True).render("POWER PLANT", True, C_ACCENT)
            surface.blit(lbl, (cx, sep_y + 3))
            cy += 18
            txt("Output (per unit/yr)", f"{spec.base_output:,.0f}", C_WARN)
            txt("Renewable", "Yes" if spec.renewable else "No",
                (80, 200, 100) if spec.renewable else C_WARN)
            if spec.input_resource:
                txt("Consumes", spec.input_resource.replace("_", " ").title(), C_WARN)
                txt("Rate (per unit/yr)", f"{spec.input_rate:.1f}")

        # Research Array note
        if self._type_value == "research_array":
            cy += 8
            draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
            lbl = font(11, bold=True).render("RESEARCH", True, C_ACCENT)
            surface.blit(lbl, (cx, cy + 3))
            cy += 18
            note = font(12).render("Contributes 1 pt/yr to each in-progress tech.", True, C_TEXT_DIM)
            surface.blit(note, (cx, cy))
            cy += ROW_H
            note2 = font(12).render("Use the TECH TREE button above to assign research.", True, C_TEXT_DIM)
            surface.blit(note2, (cx, cy))
            cy += ROW_H

        return cy

    # ------------------------------------------------------------------
    # Bot panel

    def _draw_bot(self, surface: pygame.Surface, cx: int, cy: int) -> int:
        gs = self.app.game_state
        if not gs:
            return cy

        loc = self._body_id or self._system_id or ""
        tasks = gs.bot_tasks.get(loc, self._type_value)
        total_alloc = gs.bot_tasks.total_allocation(loc, self._type_value)

        # Total allocation label + bar (drawn within the visible clip area)
        alloc_lbl = font(11).render(f"Total allocation: {total_alloc}%", True, C_TEXT_DIM)
        surface.blit(alloc_lbl, (cx, cy))
        cy += 14
        bar_w = self._rect.width - PADDING * 4
        bar_r = pygame.Rect(cx, cy, bar_w, 10)
        pygame.draw.rect(surface, (30, 50, 80), bar_r, border_radius=3)
        fill_w = int(bar_w * total_alloc / 100)
        col = (80, 200, 100) if total_alloc <= 100 else (255, 80, 80)
        if fill_w > 0:
            pygame.draw.rect(surface, col, pygame.Rect(cx, cy, fill_w, 10), border_radius=3)
        cy += 18

        # Task rows
        if tasks:
            draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
            th = font(11, bold=True).render("TASKS", True, C_ACCENT)
            surface.blit(th, (cx, cy + 3))
            cy += 18

            for task in tasks:
                if cy + 42 > self._rect.bottom - 80:
                    break
                task_r = pygame.Rect(cx, cy, self._rect.width - PADDING * 3, 40)
                pygame.draw.rect(surface, (18, 30, 60), task_r, border_radius=3)
                pygame.draw.rect(surface, C_BORDER, task_r, width=1, border_radius=3)

                # Task description
                if task.task_type == "mine":
                    desc = f"MINE  {task.resource or '?'}"
                    progress_frac = min(1.0, task.progress / max(1, task.target_amount))
                    prog_str = f"{task.progress:,.0f} / {task.target_amount:,.0f}"
                else:
                    desc = f"BUILD  {(task.entity_type or '?').replace('_', ' ').title()}"
                    progress_frac = min(1.0, task.built_count / max(1, task.target_amount))
                    prog_str = f"{task.built_count} / {task.target_amount}"

                desc_s = font(12, bold=True).render(desc.upper(), True, C_TEXT)
                prog_s = font(11).render(prog_str, True, C_TEXT_DIM)
                surface.blit(desc_s, (cx + 6, cy + 4))
                surface.blit(prog_s, (cx + 6, cy + 22))

                # Progress bar
                pbar_x = cx + 6
                pbar_y = cy + 34
                pbar_w = 200
                pygame.draw.rect(surface, (30, 50, 80),
                                 pygame.Rect(pbar_x, pbar_y, pbar_w, 5))
                if progress_frac > 0:
                    pygame.draw.rect(surface, C_ACCENT,
                                     pygame.Rect(pbar_x, pbar_y, int(pbar_w * progress_frac), 5))

                # Allocation controls
                alloc_x = task_r.right - 120
                alloc_s = font(12, bold=True).render(f"{task.allocation}%", True, C_SELECTED)
                surface.blit(alloc_s, (alloc_x + 24, cy + 10))

                dec_r = pygame.Rect(alloc_x, cy + 8, 22, 22)
                inc_r = pygame.Rect(alloc_x + 56, cy + 8, 22, 22)
                pygame.draw.rect(surface, C_BTN, dec_r, border_radius=3)
                pygame.draw.rect(surface, C_BTN, inc_r, border_radius=3)
                surface.blit(font(13, bold=True).render("−", True, C_BTN_TXT),
                             (dec_r.x + 5, dec_r.y + 2))
                surface.blit(font(13, bold=True).render("+", True, C_BTN_TXT),
                             (inc_r.x + 5, inc_r.y + 2))
                self._hit_rects.append((dec_r, "alloc_dec", (task.task_id, task)))
                self._hit_rects.append((inc_r, "alloc_inc", (task.task_id, task)))

                # Remove button
                rm_r = pygame.Rect(task_r.right - 26, cy + 8, 22, 22)
                pygame.draw.rect(surface, (80, 20, 20), rm_r, border_radius=3)
                surface.blit(font(12, bold=True).render("✕", True, (255, 100, 100)),
                             (rm_r.x + 4, rm_r.y + 2))
                self._hit_rects.append((rm_r, "remove_task", task.task_id))

                cy += 46
        else:
            no_tasks = font(12).render("No tasks assigned.", True, C_TEXT_DIM)
            surface.blit(no_tasks, (cx, cy + 8))
            cy += ROW_H + 8

        # + Add task button
        add_btn_r = pygame.Rect(cx, cy + 4, 130, 26)
        pygame.draw.rect(surface, C_BTN_HOV if self._add_task_mode else C_BTN,
                         add_btn_r, border_radius=4)
        add_lbl = font(12, bold=True).render(
            "▼  ADD TASK" if not self._add_task_mode else "▲  CANCEL",
            True, C_BTN_TXT
        )
        surface.blit(add_lbl, add_lbl.get_rect(center=add_btn_r.center))
        self._hit_rects.append((add_btn_r, "toggle_add_task", None))
        cy += 36

        if self._add_task_mode:
            cy = self._draw_add_task_form(surface, cx, cy)

        return cy

    def _draw_add_task_form(self, surface: pygame.Surface, cx: int, cy: int) -> int:
        from ..models.entity import BUILD_COSTS

        allowed_types = _BOT_ALLOWED_TASKS.get(self._type_value, ["mine"])

        # Estimate form height
        form_h = 8
        if len(allowed_types) > 1:
            form_h += 30   # task type toggle row
        form_h += 60       # resource / entity grid (2 rows max)
        form_h += 30       # amount row
        if self._add_task_type == "build":
            form_h += 20   # cost line
        form_h += 34       # confirm button + padding

        form_r = pygame.Rect(cx, cy, self._rect.width - PADDING * 3, form_h)
        pygame.draw.rect(surface, (15, 25, 50), form_r, border_radius=4)
        pygame.draw.rect(surface, C_BORDER, form_r, width=1, border_radius=4)

        fx = cx + 8
        fy = cy + 8

        # Task type toggle — only shown if the bot can do more than one type
        if len(allowed_types) > 1:
            all_types = [("mine", "Mine"), ("build", "Build")]
            for i, (ttype, tlabel) in enumerate(
                (t for t in all_types if t[0] in allowed_types)
            ):
                tr = pygame.Rect(fx + i * 80, fy, 72, 22)
                sel = self._add_task_type == ttype
                pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, tr, border_radius=3)
                lbl = font(11, bold=True).render(tlabel, True, (0, 0, 0) if sel else C_BTN_TXT)
                surface.blit(lbl, lbl.get_rect(center=tr.center))
                self._hit_rects.append((tr, "set_task_type", ttype))
            fy += 30

        # Resource / entity type selector
        if self._add_task_type == "mine":
            for i, res in enumerate(_MINE_RESOURCES):
                rr = pygame.Rect(fx + (i % 3) * 90, fy + (i // 3) * 26, 82, 22)
                sel = self._add_task_res == res
                pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, rr, border_radius=3)
                rlbl = font(10, bold=True).render(
                    _MINE_RES_LABELS[res], True, (0, 0, 0) if sel else C_BTN_TXT
                )
                surface.blit(rlbl, rlbl.get_rect(center=rr.center))
                self._hit_rects.append((rr, "set_res", res))
            fy += ((len(_MINE_RESOURCES) - 1) // 3 + 1) * 26 + 4
        else:
            # Show structures then bots in a grid
            buildables = _BUILD_STRUCTURES + _BUILD_BOTS
            for i, etype in enumerate(buildables):
                er = pygame.Rect(fx + (i % 3) * 95, fy + (i // 3) * 26, 88, 22)
                sel = self._add_task_res == etype
                pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, er, border_radius=3)
                elbl = font(9, bold=True).render(
                    etype.replace("_", " ").title(), True, (0, 0, 0) if sel else C_BTN_TXT
                )
                surface.blit(elbl, elbl.get_rect(center=er.center))
                self._hit_rects.append((er, "set_res", etype))
            fy += ((len(buildables) - 1) // 3 + 1) * 26 + 4

        # Amount row
        dec_r = pygame.Rect(fx, fy, 26, 22)
        inc_r = pygame.Rect(fx + 90, fy, 26, 22)
        pygame.draw.rect(surface, C_BTN, dec_r, border_radius=3)
        pygame.draw.rect(surface, C_BTN, inc_r, border_radius=3)
        surface.blit(font(13, bold=True).render("−", True, C_BTN_TXT), (dec_r.x + 7, dec_r.y + 2))
        surface.blit(font(13, bold=True).render("+", True, C_BTN_TXT), (inc_r.x + 7, inc_r.y + 2))
        target = self._add_task_amount if self._add_task_type == "mine" else max(1, self._add_task_amount // 100)
        amt_s = font(12, bold=True).render(str(target), True, C_SELECTED)
        surface.blit(amt_s, (fx + 34, fy + 3))
        unit_lbl = "units" if self._add_task_type == "mine" else "units to build"
        amt_lbl = font(11).render(unit_lbl, True, C_TEXT_DIM)
        surface.blit(amt_lbl, (fx + 120, fy + 4))
        self._hit_rects.append((dec_r, "dec_amount", None))
        self._hit_rects.append((inc_r, "inc_amount", None))
        fy += 28

        # Resource cost preview for build tasks
        if self._add_task_type == "build":
            cost = BUILD_COSTS.get(self._add_task_res, {})
            if cost:
                cost_parts = [f"{v:.0f} {k.replace('_', ' ')}" for k, v in cost.items()]
                cost_str = "Cost/unit: " + " + ".join(cost_parts)
            else:
                cost_str = "Cost/unit: free"
            cost_surf = font(10).render(cost_str, True, C_WARN)
            surface.blit(cost_surf, (fx, fy))
            fy += 18

        # Confirm button
        conf_r = pygame.Rect(fx, fy, 100, 24)
        pygame.draw.rect(surface, (0, 120, 80), conf_r, border_radius=4)
        conf_lbl = font(12, bold=True).render("CONFIRM", True, (200, 255, 220))
        surface.blit(conf_lbl, conf_lbl.get_rect(center=conf_r.center))
        self._hit_rects.append((conf_r, "confirm_add_task", None))

        return fy + 32

    # ------------------------------------------------------------------
    # Ship panel

    def _draw_ship(self, surface: pygame.Surface, cx: int, cy: int) -> int:
        gs = self.app.game_state
        if not gs:
            return cy

        loc = self._system_id or ""

        def txt(label: str, value: str, vcol=C_TEXT) -> None:
            nonlocal cy
            l = font(12).render(label, True, C_TEXT_DIM)
            v = font(12, bold=True).render(value, True, vcol)
            surface.blit(l, (cx, cy))
            surface.blit(v, (self._rect.right - v.get_width() - PADDING * 2, cy))
            cy += ROW_H

        count = self._count_at_location()
        txt("In system", str(count))

        # Travel queue
        orders = gs.order_queue.get_all(loc, self._type_value)
        cy += 8
        draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
        qlbl = font(11, bold=True).render("TRAVEL QUEUE", True, C_ACCENT)
        surface.blit(qlbl, (cx, cy + 3))
        cy += 18

        if orders:
            for order in orders[:5]:
                dest_str = order.target_system_id or "?"
                prog_str = f"{order.progress:.0%}"
                galaxy = self.app.galaxy
                if galaxy:
                    sys_obj = next(
                        (s for s in galaxy.solar_systems if s.id == dest_str), None
                    )
                    if sys_obj:
                        dest_str = sys_obj.name
                row_s = font(12).render(
                    f"▶  {dest_str}  —  {prog_str} complete", True, C_TEXT
                )
                surface.blit(row_s, (cx + 6, cy))
                pbar_w = min(200, self._rect.width - PADDING * 4)
                pygame.draw.rect(surface, (30, 50, 80),
                                 pygame.Rect(cx + 6, cy + 16, pbar_w, 4))
                pygame.draw.rect(surface, C_ACCENT,
                                 pygame.Rect(cx + 6, cy + 16, int(pbar_w * order.progress), 4))
                cy += 26
        else:
            no_ord = font(12).render("No orders queued.", True, C_TEXT_DIM)
            surface.blit(no_ord, (cx, cy))
            cy += ROW_H

        # Drop Ship / Probe dispatch
        if self._type_value in ("drop_ship", "probe") and count > 0:
            cy += 8
            send_btn_r = pygame.Rect(cx, cy, 160, 28)
            pygame.draw.rect(surface, C_BTN_HOV if self._send_mode else C_BTN,
                             send_btn_r, border_radius=4)
            send_lbl = font(12, bold=True).render(
                "▼  SEND SHIP" if not self._send_mode else "▲  CANCEL SEND",
                True, C_BTN_TXT,
            )
            surface.blit(send_lbl, send_lbl.get_rect(center=send_btn_r.center))
            self._hit_rects.append((send_btn_r, "toggle_send", None))
            cy += 36

            if self._send_mode:
                self._sys_list.rect = pygame.Rect(
                    cx, cy,
                    self._rect.width - PADDING * 2,
                    min(200, self._rect.bottom - cy - 50),
                )
                self._sys_list.draw(surface)
                cy += self._sys_list.rect.height + 8

                if self._send_system_id:
                    disp_btn_r = pygame.Rect(cx, cy, 140, 28)
                    pygame.draw.rect(surface, (0, 110, 180), disp_btn_r, border_radius=4)
                    galaxy = self.app.galaxy
                    dest_name = self._send_system_id
                    if galaxy:
                        sys_obj = next(
                            (s for s in galaxy.solar_systems
                             if s.id == self._send_system_id), None
                        )
                        if sys_obj:
                            dest_name = sys_obj.name
                    disp_lbl = font(12, bold=True).render(
                        f"DISPATCH → {dest_name}", True, (200, 240, 255)
                    )
                    surface.blit(disp_lbl, disp_lbl.get_rect(center=disp_btn_r.center))
                    self._hit_rects.append((disp_btn_r, "dispatch_ship", None))
                    cy += 36

        return cy

    # ------------------------------------------------------------------
    # Bio panel

    def _draw_bio(self, surface: pygame.Surface, cx: int, cy: int) -> int:
        gs = self.app.game_state
        if not gs:
            return cy
        loc = self._body_id or ""
        pop = gs.bio_state.get(loc) if loc else None
        if not pop:
            msg = font(12).render("No bio population here.", True, C_TEXT_DIM)
            surface.blit(msg, (cx, cy))
            return cy + ROW_H

        def txt(label: str, value: str, vcol=C_TEXT) -> None:
            nonlocal cy
            l = font(12).render(label, True, C_TEXT_DIM)
            v = font(12, bold=True).render(value, True, vcol)
            surface.blit(l, (cx, cy))
            surface.blit(v, (self._rect.right - v.get_width() - PADDING * 2, cy))
            cy += ROW_H

        txt("Type",        pop.bio_type.value.capitalize())
        txt("Population",  f"{pop.population:,.0f}",
            (255, 80, 80) if pop.bio_type.value == "uplifted" else (80, 200, 100))
        txt("Aggression",  f"{pop.aggression:.0%}",
            C_WARN if pop.aggression > 0.65 else C_TEXT)
        txt("Growth rate", f"{pop.growth_rate:.1%}/yr")
        return cy
