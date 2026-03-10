"""
Entity detail view — renders inline in the map panel area.

Layout: location-aware header  ▸  info card  ▸  category section
Right-click or NavPanel selection returns to map view.

Structure  : power plant I/O stats (or generic info) + research-array tech state
Bot        : task allocation percentage bars with +/− controls
Ship
  probe         : active orders (progress bars) + system dispatch list
  drop_ship     : active orders + two-step deploy UI (system → body → confirm)
  mining_vessel : active orders + target-body selector
  others        : available tasks stub
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame
from .constants import (
    NAV_W, MAP_W, TOP_H, TASKBAR_H, HEADER_H, PADDING, ROW_H,
    C_BG, C_PANEL, C_BORDER, C_ACCENT, C_TEXT, C_TEXT_DIM,
    C_BTN, C_BTN_HOV, C_BTN_TXT, C_SELECTED, C_SEP, C_WARN, C_HOVER, font,
)
from .widgets import draw_panel, draw_separator, Button
from ..models.entity import POWER_PLANT_SPECS, StructureType
from ..simulation import ShipOrder, SHIP_SPEEDS, system_distance


_MAP_RECT = pygame.Rect(NAV_W, TASKBAR_H, MAP_W, TOP_H)

_TYPE_NAMES: dict[str, str] = {
    "extractor":               "Extractor",
    "factory":                 "Factory",
    "power_plant_solar":       "Solar Plant",
    "power_plant_wind":        "Wind Plant",
    "power_plant_bios":        "Bio Plant",
    "power_plant_fossil":      "Fossil Plant",
    "power_plant_nuclear":     "Nuclear Plant",
    "power_plant_cold_fusion": "Cold Fusion Plant",
    "power_plant_dark_matter": "Dark Matter Plant",
    "research_array":          "Research Array",
    "replicator":              "Replicator",
    "shipyard":                "Shipyard",
    "storage_hub":             "Storage Hub",
    "worker":                  "Worker Bot",
    "harvester":               "Harvester Bot",
    "miner":                   "Miner Bot",
    "constructor":             "Constructor Bot",
    "probe":                   "Probe",
    "drop_ship":               "Drop Ship",
    "mining_vessel":           "Mining Vessel",
    "transport":               "Transport",
    "warship":                 "Warship",
}

_BOT_TASKS: dict[str, list[str]] = {
    "worker":      ["Construction", "Maintenance", "Idle"],
    "harvester":   ["Harvesting", "Idle"],
    "miner":       ["Mining", "Idle"],
    "constructor": ["Construction", "Idle"],
}

_SHIP_TASKS: dict[str, list[str]] = {
    "transport": ["Transport Resources", "Transport Entities"],
    "warship":   ["Patrol", "Attack", "Defend"],
}

# Bot task picker options
_MINE_RESOURCES: list[tuple[str, str]] = [
    ("minerals",      "Minerals"),
    ("rare_minerals", "Rare Min."),
    ("ice",           "Ice"),
    ("gas",           "Gas"),
    ("bios",          "Bios"),
]
_BUILD_STRUCTURES: list[tuple[str, str]] = [
    ("extractor",           "Extractor"),
    ("factory",             "Factory"),
    ("power_plant_solar",   "Solar Plant"),
    ("power_plant_wind",    "Wind Plant"),
    ("power_plant_bios",    "Bio Plant"),
    ("power_plant_fossil",  "Fossil Plant"),
    ("power_plant_nuclear", "Nuclear Plant"),
    ("research_array",      "Research Array"),
    ("replicator",          "Replicator"),
    ("shipyard",            "Shipyard"),
    ("storage_hub",         "Storage Hub"),
]
_BUILD_BOTS: list[tuple[str, str]] = [
    ("worker",      "Worker"),
    ("harvester",   "Harvester"),
    ("miner",       "Miner"),
    ("constructor", "Constructor"),
]

_C_TASK_MINE  = (60, 160, 220)    # blue — mining tasks
_C_TASK_BUILD = (120, 200, 120)   # green — build tasks

_C_DISPATCH  = (60, 180, 100)    # green confirm button
_C_CANCEL    = (180, 70,  60)    # red cancel button
_C_PROGRESS  = (0, 160, 220)     # in-flight progress bar


# ---------------------------------------------------------------------------
# Deploy UI state for Drop Ship / Mining Vessel
# ---------------------------------------------------------------------------

@dataclass
class _DeployState:
    step:        int      = 0    # 0=idle  1=pick system  2=pick body  3=confirm
    sys_id:      str | None = None
    body_id:     str | None = None
    sys_name:    str      = ""
    body_name:   str      = ""
    scroll_off:  int      = 0    # scroll offset for the list


# ---------------------------------------------------------------------------
# EntityView
# ---------------------------------------------------------------------------

class EntityView:

    def __init__(self, app) -> None:
        self.app        = app
        self.is_active  = False
        self.category:   str | None = None
        self.type_value: str | None = None
        self.system_id:  str | None = None   # system context when opened
        self.body_id:    str | None = None   # body context (None for ships)

        # Bot task buttons (registered each draw)
        self._task_buttons: list[tuple[pygame.Rect, str, int]]  = []   # legacy (unused)
        self._bot_task_rects: list[tuple[pygame.Rect, str, str]] = []  # (rect, task_id, action)
        self._bot_picker_btns: list[tuple[pygame.Rect, str]]     = []  # (rect, resource_key)
        self._bot_target_btns: list[tuple[pygame.Rect, int]]     = []  # (rect, delta)
        self._bot_add_btn:    pygame.Rect | None = None
        self._bot_add_confirm: pygame.Rect | None = None
        self._bot_add_cancel:  pygame.Rect | None = None
        # Add-task picker state
        self._bot_add_mode:     bool       = False
        self._bot_add_resource: str | None = None
        self._bot_add_target:   int        = 100

        # Ship dispatch / deploy state
        self._deploy:        _DeployState = _DeployState()
        self._dispatch_btns: list[tuple[pygame.Rect, str]]     = []  # (rect, system_id)
        self._body_btns:     list[tuple[pygame.Rect, str, str]]= []  # (rect, body_id, body_name)
        self._confirm_btn:   pygame.Rect | None = None
        self._cancel_btn:    pygame.Rect | None = None

    # ------------------------------------------------------------------
    # Lifecycle

    def activate(
        self,
        category:   str,
        type_value: str,
        system_id:  str | None = None,
        body_id:    str | None = None,
    ) -> None:
        self.category   = category
        self.type_value = type_value
        self.system_id  = system_id
        self.body_id    = body_id
        self.is_active  = True
        self._task_buttons   = []
        self._bot_task_rects = []
        self._bot_picker_btns = []
        self._bot_target_btns = []
        self._bot_add_btn     = None
        self._bot_add_confirm = None
        self._bot_add_cancel  = None
        self._bot_add_mode     = False
        self._bot_add_resource = None
        self._bot_add_target   = 100
        self._dispatch_btns  = []
        self._body_btns      = []
        self._confirm_btn    = None
        self._cancel_btn     = None
        self._deploy         = _DeployState()

    def deactivate(self) -> None:
        self.is_active  = False
        self.category   = None
        self.type_value = None
        self._deploy    = _DeployState()

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if _MAP_RECT.collidepoint(event.pos):
                    self.deactivate()
                    return

            if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
                continue

            pos = event.pos

            # Bot task management (alloc +/−, remove)
            for rect, task_id, action in self._bot_task_rects:
                if rect.collidepoint(pos):
                    gs = self.app.game_state
                    if gs and self.type_value:
                        loc = self.body_id or self.system_id or ""
                        if action == "remove":
                            gs.bot_tasks.remove(loc, self.type_value, task_id)
                        elif action.startswith("alloc"):
                            delta = int(action.split(":")[1])
                            gs.bot_tasks.adjust_allocation(loc, self.type_value, task_id, delta)
                    return

            # Bot add-task picker
            for rect, value in self._bot_picker_btns:
                if rect.collidepoint(pos):
                    self._bot_add_resource = value
                    return

            # Bot add-task target amount +/−
            for rect, delta in self._bot_target_btns:
                if rect.collidepoint(pos):
                    self._bot_add_target = max(1, self._bot_add_target + delta)
                    return

            # Bot add-task confirm
            if self._bot_add_confirm and self._bot_add_confirm.collidepoint(pos):
                self._do_add_bot_task()
                return

            # Bot add-task cancel / add button
            if self._bot_add_cancel and self._bot_add_cancel.collidepoint(pos):
                self._bot_add_mode     = False
                self._bot_add_resource = None
                self._bot_add_target   = 100
                return
            if self._bot_add_btn and self._bot_add_btn.collidepoint(pos):
                self._bot_add_mode = True
                return

            # System dispatch / step-1 select (probe dispatches immediately;
            # drop_ship / mining_vessel advance to body/confirm step)
            for rect, sys_id in self._dispatch_btns:
                if rect.collidepoint(pos):
                    if self.type_value == "probe":
                        self._dispatch_probe(sys_id)
                    else:
                        sys_obj = None
                        if self.app.galaxy:
                            sys_obj = next(
                                (s for s in self.app.galaxy.solar_systems if s.id == sys_id),
                                None,
                            )
                        self._deploy.sys_id   = sys_id
                        self._deploy.sys_name = sys_obj.name if sys_obj else sys_id
                        # Drop ship needs body selection; mining vessel goes straight to confirm
                        self._deploy.step = 2 if self.type_value == "drop_ship" else 3
                    return

            # Drop ship / mining vessel body buttons
            for rect, body_id, body_name in self._body_btns:
                if rect.collidepoint(pos):
                    self._deploy.body_id   = body_id
                    self._deploy.body_name = body_name
                    self._deploy.step      = 3
                    return

            # Cancel button
            if self._cancel_btn and self._cancel_btn.collidepoint(pos):
                self._deploy = _DeployState()
                return

            # Confirm button
            if self._confirm_btn and self._confirm_btn.collidepoint(pos):
                self._confirm_dispatch()
                return

    # ------------------------------------------------------------------
    # Bot task logic

    def _do_add_bot_task(self) -> None:
        from ..game_state import BotTask
        gs = self.app.game_state
        if not gs or not self._bot_add_resource or not self.type_value:
            return
        loc_id = self.body_id or self.system_id
        if not loc_id:
            return
        bot_type  = self.type_value
        is_build  = bot_type in ("constructor", "worker")
        task_type = "build" if is_build else "mine"
        task = BotTask(
            task_type=task_type,
            resource=None if is_build else self._bot_add_resource,
            entity_type=self._bot_add_resource if is_build else None,
            target_amount=self._bot_add_target,
            allocation=10,
        )
        gs.bot_tasks.add(loc_id, bot_type, task)
        self._bot_add_mode     = False
        self._bot_add_resource = None
        self._bot_add_target   = 100

    # ------------------------------------------------------------------
    # Ship dispatch logic

    def _dispatch_probe(self, target_sys_id: str) -> None:
        gs = self.app.game_state
        if not gs or not self.system_id:
            return
        loc = self.system_id
        if gs.entity_roster.total("ship", "probe") < 1:
            return
        # Deduct one probe from this system (or globally if not found here)
        at_loc = sum(
            i.count for i in gs.entity_roster.at(loc)
            if i.type_value == "probe"
        )
        if at_loc < 1:
            return
        gs.entity_roster.remove("ship", "probe", loc, 1)
        dist = system_distance(gs.galaxy, loc, target_sys_id)
        order = ShipOrder(
            ship_type="probe",
            order_type="explore",
            origin_system_id=loc,
            origin_location_id=loc,
            target_system_id=target_sys_id,
            target_body_id=None,
            distance_ly=dist,
        )
        gs.order_queue.add(order)

    def _confirm_dispatch(self) -> None:
        gs = self.app.game_state
        if not gs or not self.system_id or not self._deploy.sys_id:
            return
        ship = self.type_value
        loc  = self.system_id
        at_loc = sum(
            i.count for i in gs.entity_roster.at(loc)
            if i.type_value == ship
        )
        if at_loc < 1:
            return
        gs.entity_roster.remove("ship", ship, loc, 1)
        dist = system_distance(gs.galaxy, loc, self._deploy.sys_id)
        order = ShipOrder(
            ship_type=ship,
            order_type="deploy" if ship == "drop_ship" else "mine",
            origin_system_id=loc,
            origin_location_id=loc,
            target_system_id=self._deploy.sys_id,
            target_body_id=self._deploy.body_id,
            distance_ly=dist,
        )
        gs.order_queue.add(order)
        self._deploy = _DeployState()

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        content = draw_panel(surface, _MAP_RECT, self._build_title())

        # Right-click hint (top-right of header area)
        hint = font(10).render("Right-click to return to map", True, C_TEXT_DIM)
        surface.blit(hint, (_MAP_RECT.right - hint.get_width() - PADDING, _MAP_RECT.y + 8))

        y = self._draw_info_card(surface, content)
        draw_separator(surface, content.x + PADDING, y, content.right - PADDING)
        y += 8

        # Clip content to panel
        old_clip = surface.get_clip()
        surface.set_clip(content.inflate(0, 0))

        if self.category == "structure":
            self._draw_structure(surface, content, y)
        elif self.category == "bot":
            self._draw_bot(surface, content, y)
        elif self.category == "ship":
            self._draw_ship(surface, content, y)

        surface.set_clip(old_clip)

    # ------------------------------------------------------------------
    # Title / header

    def _build_title(self) -> str:
        name = _TYPE_NAMES.get(self.type_value or "", self.type_value or "")
        if not self.app.galaxy or not self.system_id:
            return name
        sys = next(
            (s for s in self.app.galaxy.solar_systems if s.id == self.system_id),
            None,
        )
        sys_name = sys.name if sys else self.system_id

        if self.body_id and sys:
            # Find the body name
            for body in sys.orbital_bodies:
                if body.id == self.body_id:
                    return f"{name}  ·  {body.name},  {sys_name}"
                for moon in body.moons:
                    if moon.id == self.body_id:
                        return f"{name}  ·  {moon.name},  {sys_name}"
        return f"{name}  ·  {sys_name}"

    def _draw_info_card(self, surface: pygame.Surface, content: pygame.Rect) -> int:
        """Draw the category / count row. Returns the y position after the card."""
        gs     = self.app.game_state
        roster = gs.entity_roster if gs else None

        # Location-scoped count
        loc_id  = self.body_id or self.system_id
        if roster and loc_id:
            here  = sum(
                i.count for i in roster.at(loc_id)
                if i.type_value == self.type_value
            )
        else:
            here = 0
        total = roster.total(self.category or "", self.type_value or "") if roster else 0

        y = content.y + 4
        surface.blit(
            font(11).render(f"Category : {(self.category or '').capitalize()}", True, C_TEXT_DIM),
            (content.x + PADDING, y),
        )
        y += ROW_H
        here_str  = f"Here: {here}"
        total_str = f"Total: {total}"
        surface.blit(font(11).render(here_str,  True, C_ACCENT),   (content.x + PADDING, y))
        surface.blit(font(11).render(total_str, True, C_TEXT_DIM), (content.x + PADDING + 110, y))
        y += ROW_H + 4
        return y

    # ------------------------------------------------------------------
    # Structure section

    def _draw_structure(
        self, surface: pygame.Surface, content: pygame.Rect, y: int
    ) -> None:
        if self.type_value == "research_array":
            self._draw_research_array(surface, content, y)
            return

        try:
            st   = StructureType(self.type_value)
            spec = POWER_PLANT_SPECS.get(st)
        except ValueError:
            spec = None

        gs     = self.app.game_state
        roster = gs.entity_roster if gs else None
        loc_id = self.body_id or self.system_id
        count  = sum(
            i.count for i in (roster.at(loc_id) if roster and loc_id else [])
            if i.type_value == self.type_value
        )

        if spec:
            surface.blit(
                font(12, bold=True).render("Power Plant", True, C_ACCENT),
                (content.x + PADDING, y),
            )
            y += ROW_H + 4
            total_out = spec.base_output * count
            rows = [
                ("Output/plant",  f"{spec.base_output:.0f} EU/yr"),
                ("Active plants", str(count)),
                ("Total output",  f"{total_out:.0f} EU/yr"),
                ("Renewable",     "Yes" if spec.renewable else "No"),
            ]
            if spec.input_resource:
                rows += [
                    ("Consumes",    spec.input_resource),
                    ("Rate/plant",  f"{spec.input_rate:.0f} units/yr"),
                    ("Total rate",  f"{spec.input_rate * count:.0f} units/yr"),
                ]
            if spec.unlocked_by:
                rows.append(("Tech required", spec.unlocked_by))

            for label, value in rows:
                ls = font(11).render(f"{label:<14}:", True, C_TEXT_DIM)
                vs = font(11).render(value, True, C_TEXT)
                surface.blit(ls, (content.x + PADDING, y))
                surface.blit(vs, (content.x + PADDING + ls.get_width() + 6, y))
                y += ROW_H

            if not spec.renewable:
                y += 4
                warn = font(10).render(
                    f"⚠  Non-renewable — requires {spec.input_resource} deposits.",
                    True, C_WARN,
                )
                surface.blit(warn, (content.x + PADDING, y))
        else:
            surface.blit(
                font(11).render("No detailed stats for this structure.", True, C_TEXT_DIM),
                (content.x + PADDING, y),
            )

    def _draw_research_array(
        self, surface: pygame.Surface, content: pygame.Rect, y: int
    ) -> None:
        from ..models.tech import TECH_TREE

        surface.blit(
            font(12, bold=True).render("Research Array", True, C_ACCENT),
            (content.x + PADDING, y),
        )
        y += ROW_H + 4

        tech = self.app.game_state.tech if self.app.game_state else None
        in_progress = tech.in_progress_ids() if tech else []

        # In Progress
        surface.blit(font(11, bold=True).render("In Progress", True, C_TEXT), (content.x + PADDING, y))
        y += ROW_H
        bar_w = content.width - PADDING * 2 - 120
        if in_progress:
            for tid in in_progress:
                node = TECH_TREE.get(tid)
                frac = tech.progress_fraction(tid) if tech else 0.0
                name = node.name if node else tid
                surface.blit(font(11).render(name, True, C_TEXT), (content.x + PADDING, y))
                bx = content.x + PADDING + 200
                pygame.draw.rect(surface, C_BTN, pygame.Rect(bx, y + 4, bar_w, ROW_H - 6), border_radius=3)
                if frac > 0:
                    pygame.draw.rect(surface, C_ACCENT, pygame.Rect(bx, y + 4, int(bar_w * frac), ROW_H - 6), border_radius=3)
                surface.blit(font(11, bold=True).render(f"{int(frac*100)}%", True, C_SELECTED), (bx + bar_w + 6, y + 2))
                y += ROW_H + 2
        else:
            surface.blit(font(11).render("None active.", True, C_TEXT_DIM), (content.x + PADDING + 8, y))
            y += ROW_H

        y += 4; draw_separator(surface, content.x + PADDING, y, content.right - PADDING); y += 8

        # Completed
        researched = tech.researched if tech else set()
        surface.blit(font(11, bold=True).render("Completed", True, C_TEXT), (content.x + PADDING, y)); y += ROW_H
        if researched:
            col_w = content.width // 2
            for i, tid in enumerate(sorted(researched)):
                node = TECH_TREE.get(tid)
                name = node.name if node else tid
                cx   = content.x + PADDING + (i % 2) * col_w
                surface.blit(font(10).render(f"✓  {name}", True, (80, 200, 120)), (cx, y))
                if i % 2 == 1:
                    y += ROW_H
            if len(researched) % 2 == 1:
                y += ROW_H
        else:
            surface.blit(font(11).render("None yet.", True, C_TEXT_DIM), (content.x + PADDING + 8, y)); y += ROW_H

        y += 4; draw_separator(surface, content.x + PADDING, y, content.right - PADDING); y += 8

        # Available
        surface.blit(font(11, bold=True).render("Available to Research", True, C_TEXT), (content.x + PADDING, y)); y += ROW_H
        available = [
            tid for tid in TECH_TREE
            if tech and tech.can_research(tid) and tid not in in_progress
        ]
        if available:
            for tid in available:
                node = TECH_TREE.get(tid)
                name = node.name if node else tid
                cost = f"{node.research_cost:.0f} pts" if node else ""
                surface.blit(font(11).render(f"◉  {name}  ({cost})", True, C_TEXT), (content.x + PADDING + 8, y))
                y += ROW_H
                if y + ROW_H > content.bottom - ROW_H:
                    break
        else:
            surface.blit(font(11).render("None — check prerequisites.", True, C_TEXT_DIM), (content.x + PADDING + 8, y))

        # Count note at bottom
        gs    = self.app.game_state
        count = gs.entity_roster.total("structure", "research_array") if gs else 0
        note  = font(10).render(
            f"{count} Research Array{'s' if count != 1 else ''} — each can work on a separate tech simultaneously.",
            True, C_TEXT_DIM,
        )
        surface.blit(note, (content.x + PADDING, content.bottom - ROW_H - 4))

    # ------------------------------------------------------------------
    # Bot section

    def _draw_bot(self, surface: pygame.Surface, content: pygame.Rect, y: int) -> None:
        self._bot_task_rects  = []
        self._bot_picker_btns = []
        self._bot_target_btns = []
        self._bot_add_btn     = None
        self._bot_add_confirm = None
        self._bot_add_cancel  = None

        gs       = self.app.game_state
        bot_type = self.type_value or ""
        loc_id   = self.body_id or self.system_id or ""

        # Bot count at location
        bot_count = sum(
            i.count for i in (gs.entity_roster.at(loc_id) if gs else [])
            if i.category == "bot" and i.type_value == bot_type
        )
        is_builder = bot_type in ("constructor", "worker")

        # Header: task type label
        lbl = "Build Tasks" if is_builder else "Mining Tasks"
        surface.blit(
            font(12, bold=True).render(lbl, True, C_ACCENT),
            (content.x + PADDING, y),
        )
        cnt_txt = font(11).render(f"  ({bot_count} bot{'s' if bot_count != 1 else ''} here)", True, C_TEXT_DIM)
        surface.blit(cnt_txt, (content.x + PADDING + 120, y + 2))
        y += ROW_H + 2

        tasks = gs.bot_tasks.get(loc_id, bot_type) if gs else []

        if not tasks:
            surface.blit(
                font(11).render("No tasks assigned.", True, C_TEXT_DIM),
                (content.x + PADDING + 8, y + 2),
            )
            y += ROW_H
        else:
            bar_w      = content.width - PADDING * 2 - 200
            alloc_bar_w = 80
            mouse      = pygame.mouse.get_pos()
            for task in tasks:
                if y + ROW_H + 4 > content.bottom - 70:
                    break
                c = _C_TASK_BUILD if is_builder else _C_TASK_MINE

                # Task name
                if task.task_type == "mine":
                    name = f"Mine  {task.resource or '?'}"
                elif task.entity_type:
                    name = f"Build  {_TYPE_NAMES.get(task.entity_type, task.entity_type)}"
                else:
                    name = "Build"
                surface.blit(font(11).render(name, True, c), (content.x + PADDING, y + 2))

                # Allocation bar (small)
                abx = content.x + PADDING + 180
                pygame.draw.rect(surface, C_BTN, pygame.Rect(abx, y + 6, alloc_bar_w, ROW_H - 10), border_radius=2)
                fw = int(alloc_bar_w * task.allocation / 100)
                if fw:
                    pygame.draw.rect(surface, c, pygame.Rect(abx, y + 6, fw, ROW_H - 10), border_radius=2)
                surface.blit(
                    font(10, bold=True).render(f"{task.allocation}%", True, C_SELECTED),
                    (abx + alloc_bar_w + 4, y + 4),
                )

                # Progress display
                if task.task_type == "mine":
                    prog_str = f"{task.progress:.0f}/{task.target_amount}"
                else:
                    prog_str = f"{task.built_count}/{task.target_amount} built"
                surface.blit(font(10).render(prog_str, True, C_TEXT_DIM), (abx + alloc_bar_w + 44, y + 4))

                # − / + / ✕ buttons
                bx_ctrl = content.right - PADDING - 62
                minus_r = pygame.Rect(bx_ctrl,      y + 3, 18, ROW_H - 6)
                plus_r  = pygame.Rect(bx_ctrl + 22, y + 3, 18, ROW_H - 6)
                rem_r   = pygame.Rect(bx_ctrl + 44, y + 3, 18, ROW_H - 6)
                for btn_r, lbl_ch in ((minus_r, "−"), (plus_r, "+"), (rem_r, "✕")):
                    bg = C_BTN_HOV if btn_r.collidepoint(mouse) else C_BTN
                    pygame.draw.rect(surface, bg, btn_r, border_radius=3)
                    ch = font(10, bold=True).render(lbl_ch, True, C_BTN_TXT)
                    surface.blit(ch, ch.get_rect(center=btn_r.center))
                self._bot_task_rects.append((minus_r, task.task_id, "alloc:-10"))
                self._bot_task_rects.append((plus_r,  task.task_id, "alloc:+10"))
                self._bot_task_rects.append((rem_r,   task.task_id, "remove"))

                y += ROW_H + 4

        # Idle % display
        used_alloc = sum(t.allocation for t in tasks)
        idle_pct   = max(0, 100 - used_alloc)
        draw_separator(surface, content.x + PADDING, y, content.right - PADDING)
        y += 6
        surface.blit(
            font(11).render(f"Idle: {idle_pct}%  (allocated: {used_alloc}%)", True, C_TEXT_DIM),
            (content.x + PADDING, y),
        )
        y += ROW_H + 4
        draw_separator(surface, content.x + PADDING, y, content.right - PADDING)
        y += 8

        # Add Task section
        if self._bot_add_mode:
            self._draw_bot_add_picker(surface, content, y, is_builder)
        else:
            add_r = pygame.Rect(content.x + PADDING, y, 140, 24)
            mouse = pygame.mouse.get_pos()
            bg = C_BTN_HOV if add_r.collidepoint(mouse) else C_BTN
            pygame.draw.rect(surface, bg, add_r, border_radius=4)
            lbl_text = "+ Add Build Task" if is_builder else "+ Add Mining Task"
            surface.blit(font(11).render(lbl_text, True, C_BTN_TXT), (add_r.x + 8, add_r.y + 4))
            self._bot_add_btn = add_r

    def _draw_bot_add_picker(
        self, surface: pygame.Surface, content: pygame.Rect, y: int, is_builder: bool
    ) -> None:
        options = (_BUILD_STRUCTURES + _BUILD_BOTS) if is_builder else _MINE_RESOURCES
        lbl_hdr = "Select what to build:" if is_builder else "Select resource to mine:"
        surface.blit(font(11, bold=True).render(lbl_hdr, True, C_TEXT), (content.x + PADDING, y))
        y += ROW_H + 2

        mouse = pygame.mouse.get_pos()
        btn_w = 110
        btn_h = 22
        cols  = max(1, (content.width - PADDING * 2) // (btn_w + 4))
        col   = 0
        row_y = y
        for key, display in options:
            if row_y + btn_h > content.bottom - 60:
                break
            bx = content.x + PADDING + col * (btn_w + 4)
            btn_r = pygame.Rect(bx, row_y, btn_w, btn_h)
            selected = self._bot_add_resource == key
            bg = C_ACCENT if selected else (C_BTN_HOV if btn_r.collidepoint(mouse) else C_BTN)
            pygame.draw.rect(surface, bg, btn_r, border_radius=3)
            txt_c = (0, 0, 0) if selected else C_BTN_TXT
            surf  = font(10).render(display, True, txt_c)
            surface.blit(surf, surf.get_rect(center=btn_r.center))
            self._bot_picker_btns.append((btn_r, key))
            col += 1
            if col >= cols:
                col    = 0
                row_y += btn_h + 3

        y = row_y + btn_h + 8

        # Target amount row
        surface.blit(font(11).render("Target amount:", True, C_TEXT_DIM), (content.x + PADDING, y + 3))
        minus_r = pygame.Rect(content.x + PADDING + 130, y, 22, 22)
        plus_r  = pygame.Rect(content.x + PADDING + 186, y, 22, 22)
        for btn_r, lbl_ch, delta in ((minus_r, "−", -10), (plus_r, "+", +10)):
            bg = C_BTN_HOV if btn_r.collidepoint(mouse) else C_BTN
            pygame.draw.rect(surface, bg, btn_r, border_radius=3)
            ch_surf = font(11, bold=True).render(lbl_ch, True, C_BTN_TXT)
            surface.blit(ch_surf, ch_surf.get_rect(center=btn_r.center))
            self._bot_target_btns.append((btn_r, delta))
        surface.blit(
            font(12, bold=True).render(str(self._bot_add_target), True, C_SELECTED),
            (content.x + PADDING + 156, y + 2),
        )
        y += 30

        # Confirm / Cancel
        conf_r = pygame.Rect(content.x + PADDING, y, 90, 24)
        can_r  = pygame.Rect(content.x + PADDING + 100, y, 70, 24)
        can_draw = self._bot_add_resource is not None
        bg_conf = _C_DISPATCH if can_draw else (40, 60, 40)
        pygame.draw.rect(surface, bg_conf, conf_r, border_radius=4)
        pygame.draw.rect(surface, C_BTN_HOV, can_r, border_radius=4)
        surface.blit(font(11).render("Assign", True, C_BTN_TXT), (conf_r.x + 8, conf_r.y + 4))
        surface.blit(font(11).render("Cancel", True, C_BTN_TXT), (can_r.x + 8,  can_r.y + 4))
        if can_draw:
            self._bot_add_confirm = conf_r
        self._bot_add_cancel = can_r

    # ------------------------------------------------------------------
    # Ship section

    def _draw_ship(self, surface: pygame.Surface, content: pygame.Rect, y: int) -> None:
        tv = self.type_value or ""
        if tv == "probe":
            self._draw_probe(surface, content, y)
        elif tv == "drop_ship":
            self._draw_drop_ship(surface, content, y)
        elif tv == "mining_vessel":
            self._draw_mining_vessel(surface, content, y)
        else:
            self._draw_ship_generic(surface, content, y)

    # -- Probe --

    def _draw_probe(self, surface: pygame.Surface, content: pygame.Rect, y: int) -> None:
        self._dispatch_btns = []
        gs = self.app.game_state

        # Active orders
        surface.blit(font(12, bold=True).render("Probes In Transit", True, C_ACCENT), (content.x + PADDING, y))
        y += ROW_H + 2
        orders = [
            o for o in (gs.order_queue.active() if gs else [])
            if o.ship_type == "probe"
        ]
        if orders:
            bar_w = content.width - PADDING * 2 - 180
            for o in orders:
                sys_name = self._sys_name(o.target_system_id)
                label    = f"→ {sys_name}"
                eta_str  = f"ETA {o.eta_years:.1f} yr"
                surface.blit(font(11).render(label,   True, C_TEXT),     (content.x + PADDING, y))
                surface.blit(font(11).render(eta_str, True, C_TEXT_DIM), (content.x + PADDING + 200, y))
                bx = content.x + PADDING + 310
                pygame.draw.rect(surface, C_BTN, pygame.Rect(bx, y + 4, bar_w, ROW_H - 6), border_radius=3)
                fw = int(bar_w * o.fraction)
                if fw:
                    pygame.draw.rect(surface, _C_PROGRESS, pygame.Rect(bx, y + 4, fw, ROW_H - 6), border_radius=3)
                surface.blit(font(10).render(f"{int(o.fraction*100)}%", True, C_SELECTED), (bx + bar_w + 6, y + 4))
                y += ROW_H + 2
        else:
            surface.blit(font(11).render("No probes in transit.", True, C_TEXT_DIM), (content.x + PADDING + 8, y))
            y += ROW_H

        y += 6; draw_separator(surface, content.x + PADDING, y, content.right - PADDING); y += 8

        # Dispatch list
        surface.blit(font(12, bold=True).render("Send Probe to System", True, C_ACCENT), (content.x + PADDING, y))
        y += ROW_H + 2

        here = self._count_here("ship", "probe")
        if here < 1:
            surface.blit(font(11).render("No probes available at this location.", True, C_WARN), (content.x + PADDING + 8, y))
            return

        surface.blit(
            font(11).render(f"Available here: {here}  — click a system to dispatch", True, C_TEXT_DIM),
            (content.x + PADDING + 8, y),
        )
        y += ROW_H + 2

        if not gs or not gs.galaxy or not self.system_id:
            return

        from ..game_state import DiscoveryState
        col_w = content.width // 2

        for i, sys in enumerate(gs.galaxy.solar_systems):
            if y + ROW_H > content.bottom - PADDING:
                break
            if sys.id == self.system_id:
                continue
            state = gs.get_state(sys.id)
            dist  = system_distance(gs.galaxy, self.system_id, sys.id)
            speed = SHIP_SPEEDS["probe"]

            col = C_TEXT
            if state in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                state_str = "explored"
            elif state == DiscoveryState.DETECTED:
                state_str = "detected"
                col = C_TEXT_DIM
            else:
                state_str = "unknown"
                col = (60, 70, 90)

            already_en_route = any(
                o.target_system_id == sys.id and o.ship_type == "probe"
                for o in gs.order_queue.active()
            )
            label = f"{'→' if already_en_route else '◉'}  {sys.name}  ({dist:.0f} ly  ·  {dist/speed:.1f} yr)"

            btn_r = pygame.Rect(content.x + PADDING + 8, y, content.width - PADDING * 2 - 16, ROW_H)
            mouse = pygame.mouse.get_pos()
            if btn_r.collidepoint(mouse) and not already_en_route and col != (60, 70, 90):
                pygame.draw.rect(surface, C_HOVER, btn_r, border_radius=2)

            surface.blit(font(11).render(label, True, col), (btn_r.x + 4, y + 2))
            surface.blit(font(10).render(state_str, True, C_TEXT_DIM), (btn_r.right - 80, y + 4))

            if not already_en_route and state != DiscoveryState.UNKNOWN:
                self._dispatch_btns.append((btn_r, sys.id))

            y += ROW_H + 1

    # -- Drop Ship --

    def _draw_drop_ship(self, surface: pygame.Surface, content: pygame.Rect, y: int) -> None:
        self._body_btns  = []
        self._cancel_btn = None
        self._confirm_btn = None
        gs = self.app.game_state

        # Active orders
        surface.blit(font(12, bold=True).render("Drop Ships In Transit", True, C_ACCENT), (content.x + PADDING, y))
        y += ROW_H + 2
        orders = [o for o in (gs.order_queue.active() if gs else []) if o.ship_type == "drop_ship"]
        if orders:
            for o in orders:
                sys_name  = self._sys_name(o.target_system_id)
                body_name = o.target_body_id or sys_name
                label    = f"→ {body_name} in {sys_name}"
                eta_str  = f"ETA {o.eta_years:.1f} yr"
                bar_w    = content.width - PADDING * 2 - 320
                surface.blit(font(11).render(label,   True, C_TEXT),     (content.x + PADDING, y))
                surface.blit(font(11).render(eta_str, True, C_TEXT_DIM), (content.x + PADDING + 250, y))
                bx = content.x + PADDING + 340
                pygame.draw.rect(surface, C_BTN, pygame.Rect(bx, y + 4, bar_w, ROW_H - 6), border_radius=3)
                fw = int(bar_w * o.fraction)
                if fw:
                    pygame.draw.rect(surface, _C_DISPATCH, pygame.Rect(bx, y + 4, fw, ROW_H - 6), border_radius=3)
                y += ROW_H + 2
        else:
            surface.blit(font(11).render("No drop ships in transit.", True, C_TEXT_DIM), (content.x + PADDING + 8, y))
            y += ROW_H

        y += 6; draw_separator(surface, content.x + PADDING, y, content.right - PADDING); y += 8

        here = self._count_here("ship", "drop_ship")
        surface.blit(font(12, bold=True).render("Deploy Drop Ship", True, C_ACCENT), (content.x + PADDING, y))
        y += ROW_H + 2

        if here < 1:
            surface.blit(font(11).render("No drop ships available at this location.", True, C_WARN), (content.x + PADDING + 8, y))
            return

        d = self._deploy
        from ..game_state import DiscoveryState

        if d.step == 0:
            surface.blit(font(11).render("Select a destination system:", True, C_TEXT_DIM), (content.x + PADDING + 8, y))
            y += ROW_H + 4
            if gs and gs.galaxy:
                for sys in gs.galaxy.solar_systems:
                    if y + ROW_H > content.bottom - PADDING:
                        break
                    state = gs.get_state(sys.id)
                    if state not in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                        continue
                    dist  = system_distance(gs.galaxy, self.system_id or "", sys.id)
                    speed = SHIP_SPEEDS["drop_ship"]
                    label = f"◉  {sys.name}  ({dist:.0f} ly  ·  {dist/speed:.1f} yr)"
                    btn_r = pygame.Rect(content.x + PADDING + 8, y, content.width - PADDING * 2 - 16, ROW_H)
                    if btn_r.collidepoint(pygame.mouse.get_pos()):
                        pygame.draw.rect(surface, C_HOVER, btn_r, border_radius=2)
                    surface.blit(font(11).render(label, True, C_TEXT), (btn_r.x + 4, y + 2))
                    self._dispatch_btns.append((btn_r, sys.id))
                    y += ROW_H + 1

        elif d.step == 2:
            # Pick body
            surface.blit(
                font(11).render(f"System: {d.sys_name}  — select a body:", True, C_TEXT_DIM),
                (content.x + PADDING + 8, y),
            )
            y += ROW_H + 4
            if gs and gs.galaxy:
                sys = next((s for s in gs.galaxy.solar_systems if s.id == d.sys_id), None)
                if sys:
                    for body in sys.orbital_bodies:
                        if y + ROW_H > content.bottom - PADDING * 4:
                            break
                        label = f"◉  {body.name}  ({body.subtype or body.body_type.value})"
                        btn_r = pygame.Rect(content.x + PADDING + 8, y, content.width - PADDING * 2 - 16, ROW_H)
                        if btn_r.collidepoint(pygame.mouse.get_pos()):
                            pygame.draw.rect(surface, C_HOVER, btn_r, border_radius=2)
                        surface.blit(font(11).render(label, True, C_TEXT), (btn_r.x + 4, y + 2))
                        self._body_btns.append((btn_r, body.id, body.name))
                        y += ROW_H + 1

            can_r = pygame.Rect(content.x + PADDING, content.bottom - 32, 90, 24)
            pygame.draw.rect(surface, C_BTN_HOV, can_r, border_radius=4)
            surface.blit(font(11).render("Cancel", True, C_BTN_TXT), (can_r.x + 8, can_r.y + 4))
            self._cancel_btn = can_r

        elif d.step == 3:
            # Confirm
            surface.blit(
                font(11).render(f"Deploy to:  {d.body_name}  in  {d.sys_name}", True, C_TEXT),
                (content.x + PADDING + 8, y),
            )
            y += ROW_H + 4
            surface.blit(
                font(10).render(
                    "On arrival the drop ship will be destroyed and deploy 1 Constructor + 1 Miner bot.",
                    True, C_TEXT_DIM,
                ),
                (content.x + PADDING + 8, y),
            )
            y += ROW_H + 12

            conf_r = pygame.Rect(content.x + PADDING + 8, y, 110, 26)
            can_r  = pygame.Rect(content.x + PADDING + 130, y, 90, 26)
            pygame.draw.rect(surface, _C_DISPATCH, conf_r, border_radius=4)
            pygame.draw.rect(surface, C_BTN_HOV,  can_r,  border_radius=4)
            surface.blit(font(11).render("Confirm", True, C_BTN_TXT), (conf_r.x + 8, conf_r.y + 5))
            surface.blit(font(11).render("Cancel",  True, C_BTN_TXT), (can_r.x  + 8, can_r.y  + 5))
            self._confirm_btn = conf_r
            self._cancel_btn  = can_r

    # -- Mining Vessel --

    def _draw_mining_vessel(self, surface: pygame.Surface, content: pygame.Rect, y: int) -> None:
        self._dispatch_btns = []
        self._body_btns     = []
        self._confirm_btn   = None
        self._cancel_btn    = None
        gs = self.app.game_state

        surface.blit(font(12, bold=True).render("Mining Vessels In Transit", True, C_ACCENT), (content.x + PADDING, y))
        y += ROW_H + 2
        orders = [o for o in (gs.order_queue.active() if gs else []) if o.ship_type == "mining_vessel"]
        if orders:
            for o in orders:
                label   = f"→ {self._sys_name(o.target_system_id)}"
                eta_str = f"ETA {o.eta_years:.1f} yr"
                bar_w   = content.width - PADDING * 2 - 280
                surface.blit(font(11).render(label,   True, C_TEXT),     (content.x + PADDING, y))
                surface.blit(font(11).render(eta_str, True, C_TEXT_DIM), (content.x + PADDING + 180, y))
                bx = content.x + PADDING + 270
                pygame.draw.rect(surface, C_BTN, pygame.Rect(bx, y + 4, bar_w, ROW_H - 6), border_radius=3)
                fw = int(bar_w * o.fraction)
                if fw:
                    pygame.draw.rect(surface, C_SELECTED, pygame.Rect(bx, y + 4, fw, ROW_H - 6), border_radius=3)
                y += ROW_H + 2
        else:
            surface.blit(font(11).render("No mining vessels in transit.", True, C_TEXT_DIM), (content.x + PADDING + 8, y))
            y += ROW_H

        y += 6; draw_separator(surface, content.x + PADDING, y, content.right - PADDING); y += 8

        here = self._count_here("ship", "mining_vessel")
        surface.blit(font(12, bold=True).render("Dispatch Mining Vessel", True, C_ACCENT), (content.x + PADDING, y))
        y += ROW_H + 2

        if here < 1:
            surface.blit(font(11).render("No mining vessels available here.", True, C_WARN), (content.x + PADDING + 8, y))
            return

        d = self._deploy
        if d.step == 0:
            surface.blit(font(11).render("Select destination system:", True, C_TEXT_DIM), (content.x + PADDING + 8, y))
            y += ROW_H + 4
            from ..game_state import DiscoveryState
            if gs and gs.galaxy:
                for sys in gs.galaxy.solar_systems:
                    if y + ROW_H > content.bottom - PADDING:
                        break
                    state = gs.get_state(sys.id)
                    if state not in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                        continue
                    dist  = system_distance(gs.galaxy, self.system_id or "", sys.id)
                    speed = SHIP_SPEEDS["mining_vessel"]
                    label = f"◉  {sys.name}  ({dist:.0f} ly  ·  {dist/speed:.1f} yr)"
                    btn_r = pygame.Rect(content.x + PADDING + 8, y, content.width - PADDING * 2 - 16, ROW_H)
                    if btn_r.collidepoint(pygame.mouse.get_pos()):
                        pygame.draw.rect(surface, C_HOVER, btn_r, border_radius=2)
                    surface.blit(font(11).render(label, True, C_TEXT), (btn_r.x + 4, y + 2))
                    self._dispatch_btns.append((btn_r, sys.id))
                    y += ROW_H + 1

        elif d.step == 3:
            surface.blit(
                font(11).render(f"Dispatch to:  {d.sys_name}", True, C_TEXT),
                (content.x + PADDING + 8, y),
            )
            y += ROW_H + 12
            conf_r = pygame.Rect(content.x + PADDING + 8, y, 110, 26)
            can_r  = pygame.Rect(content.x + PADDING + 130, y, 90, 26)
            pygame.draw.rect(surface, _C_DISPATCH, conf_r, border_radius=4)
            pygame.draw.rect(surface, C_BTN_HOV,  can_r,  border_radius=4)
            surface.blit(font(11).render("Confirm", True, C_BTN_TXT), (conf_r.x + 8, conf_r.y + 5))
            surface.blit(font(11).render("Cancel",  True, C_BTN_TXT), (can_r.x  + 8, can_r.y  + 5))
            self._confirm_btn = conf_r
            self._cancel_btn  = can_r

    # -- Generic ship --

    def _draw_ship_generic(self, surface: pygame.Surface, content: pygame.Rect, y: int) -> None:
        surface.blit(font(12, bold=True).render("Available Tasks", True, C_ACCENT), (content.x + PADDING, y))
        y += ROW_H + 4
        tasks = _SHIP_TASKS.get(self.type_value or "", [])
        for task in tasks:
            surface.blit(font(11).render(f"▷  {task}", True, C_TEXT), (content.x + PADDING, y))
            y += ROW_H
        if not tasks:
            surface.blit(font(11).render("No tasks defined.", True, C_TEXT_DIM), (content.x + PADDING, y))
            y += ROW_H
        y += 12
        surface.blit(font(11).render("Task queue: not yet implemented.", True, C_TEXT_DIM), (content.x + PADDING, y))

    # ------------------------------------------------------------------
    # Helpers

    def _count_here(self, category: str, type_value: str) -> int:
        gs = self.app.game_state
        if not gs:
            return 0
        loc = self.body_id or self.system_id
        if not loc:
            return 0
        return sum(
            i.count for i in gs.entity_roster.at(loc)
            if i.category == category and i.type_value == type_value
        )

    def _sys_name(self, sys_id: str) -> str:
        if self.app.galaxy:
            s = next((x for x in self.app.galaxy.solar_systems if x.id == sys_id), None)
            if s:
                return s.name
        return sys_id
