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
    "logistic_bot": "Logistic Bot",
    "harvester":    "Harvester Bot",
    "miner":        "Miner Bot",
    "constructor":  "Constructor Bot",
}

_SHIP_NAMES: dict[str, str] = {
    "probe":         "Probe",
    "drop_ship":     "Drop Ship",
    "mining_vessel": "Mining Vessel",
    "transport":     "Transport",
    "warship":       "Warship",
}

_TASK_TYPE_LABELS: dict[str, str] = {
    "mine":      "Mine",
    "build":     "Build",
    "transport": "Transport",
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
    "miner":        ["mine"],
    "harvester":    ["mine"],
    "constructor":  ["build"],
    "logistic_bot": ["transport"],
}

# Buildable entity types for constructor tasks (no tech requirement)
_BUILD_STRUCTURES_BASE = [
    "extractor", "factory", "research_array",
    "power_plant_solar", "power_plant_wind", "power_plant_bios",
    "power_plant_fossil", "power_plant_nuclear", "shipyard", "storage_hub",
]
_BUILD_BOTS = ["miner", "constructor", "logistic_bot", "harvester"]
_BUILD_SHIPS = ["probe", "drop_ship"]


def _get_buildable_structures(gs) -> list[str]:
    """Return structures buildable given current tech state."""
    from ..models.entity import POWER_PLANT_SPECS, StructureType
    researched = gs.tech.researched if gs else set()
    result = list(_BUILD_STRUCTURES_BASE)
    # Add tech-gated structures whose prerequisite is now researched
    gated = {
        "power_plant_cold_fusion": "cold_fusion",
        "power_plant_dark_matter": "dark_matter",
        "replicator": "self_replication",
    }
    for st, tech_id in gated.items():
        if tech_id in researched:
            result.append(st)
    return result


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
        self._bot_scroll:    int = 0
        self._struct_scroll: int = 0
        self._ship_scroll:   int = 0
        # Hit rects populated each draw: (rect, action, data)
        self._hit_rects: list[tuple[pygame.Rect, str, object]] = []

        # --- Ship send-to UI state ---
        self._send_mode:      bool       = False
        self._send_system_id: str | None = None
        self._send_body_id:   str | None = None   # body-level docking target (mining/transport)
        self._fuel_warning:   bool       = False

        # --- Logistic bot transport UI state ---
        self._transport_target_body: str | None = None

        # Scrollable lists for system and body selectors
        sys_sel_rect = pygame.Rect(
            self._rect.x + PADDING,
            self._rect.y + HEADER_H + 160,
            self._rect.width - PADDING * 2,
            180,
        )
        self._sys_list = ScrollableList(sys_sel_rect, "Select Destination System",
                                        on_select=self._on_send_system_select)
        body_sel_rect = pygame.Rect(
            self._rect.x + PADDING,
            self._rect.y + HEADER_H + 160,
            self._rect.width - PADDING * 2,
            140,
        )
        self._body_list = ScrollableList(body_sel_rect, "Select Docking Body",
                                         on_select=self._on_send_body_select)

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
        self._add_task_mode  = False
        self._bot_scroll     = 0
        self._struct_scroll  = 0
        self._ship_scroll    = 0
        # Default task type based on bot capabilities
        allowed = _BOT_ALLOWED_TASKS.get(type_value, ["mine"])
        self._add_task_type = allowed[0]
        self._send_mode              = False
        self._send_system_id         = None
        self._send_body_id           = None
        self._fuel_warning           = False
        self._transport_target_body  = None
        self._hit_rects              = []

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
                    from ..simulation import SHIP_SPEEDS
                    dx = s.position["x"] - home_pos["x"]
                    dy = s.position["y"] - home_pos["y"]
                    dist = math.hypot(dx, dy)
                    spd = SHIP_SPEEDS.get(self._type_value, 0.25)
                    eta_years = 1.0 / spd
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
            # All other ships: any discovered/colonized system; show ETA
            from ..simulation import SHIP_SPEEDS
            spd = SHIP_SPEEDS.get(self._type_value, 0.25)
            eta_years = 1.0 / spd
            home_pos = None
            if self._system_id:
                for s in galaxy.solar_systems:
                    if s.id == self._system_id:
                        home_pos = s.position
                        break
            items = []
            for s in galaxy.solar_systems:
                if s.id == self._system_id:
                    continue
                if gs.get_state(s.id) not in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED):
                    continue
                dist_str = ""
                if home_pos:
                    dx = s.position["x"] - home_pos["x"]
                    dy = s.position["y"] - home_pos["y"]
                    dist = math.hypot(dx, dy)
                    dist_str = f" [{dist:.0f} ly | ~{eta_years:.0f}yr]"
                items.append((f"{s.name}{dist_str}", s.id, None))
        self._sys_list.set_items(items)

    def _on_send_system_select(self, sys_id: str) -> None:
        # Ignore warp-only pseudo-IDs
        if sys_id.startswith("_warp_"):
            return
        self._send_system_id = sys_id
        self._send_body_id   = None
        # For mining_vessel and transport, rebuild body picker for chosen system
        if self._type_value in ("mining_vessel", "transport"):
            self._rebuild_body_list(sys_id)

    def _on_send_body_select(self, body_id: str) -> None:
        self._send_body_id = body_id

    def _rebuild_body_list(self, sys_id: str) -> None:
        """Populate the body selector with landable bodies in sys_id."""
        galaxy = self.app.galaxy
        if not galaxy:
            return
        from ..models.celestial import BodyType
        target_sys = next((s for s in galaxy.solar_systems if s.id == sys_id), None)
        if not target_sys:
            return

        items: list[tuple[str, str, tuple | None]] = []
        for body in target_sys.orbital_bodies:
            if body.body_type == BodyType.STAR:
                continue
            icon = {
                BodyType.ASTEROID: "⬡ Asteroid",
                BodyType.COMET:    "☄ Comet",
                BodyType.PLANET:   "◉ Planet",
                BodyType.EXOPLANET: "◉ Exoplanet",
            }.get(body.body_type, "◉ Body")
            # Mining vessels prefer asteroids; highlight them
            is_asteroid = body.body_type == BodyType.ASTEROID
            col = (200, 220, 160) if (is_asteroid and self._type_value == "mining_vessel") else None
            # Show key resources
            res = getattr(body, "resources", None)
            res_str = ""
            if res:
                parts = []
                if getattr(res, "minerals", 0) > 0:
                    parts.append(f"M:{res.minerals:.0f}")
                if getattr(res, "rare_minerals", 0) > 0:
                    parts.append(f"R:{res.rare_minerals:.0f}")
                if getattr(res, "ice", 0) > 0:
                    parts.append(f"I:{res.ice:.0f}")
                if parts:
                    res_str = "  " + "  ".join(parts)
            label = f"{icon}: {body.name}{res_str}"
            items.append((label, body.id, col))
            # Also add moons as docking targets for transports
            if self._type_value == "transport":
                for moon in body.moons:
                    moon_res = getattr(moon, "resources", None)
                    m_res_str = ""
                    if moon_res:
                        parts = []
                        if getattr(moon_res, "minerals", 0) > 0:
                            parts.append(f"M:{moon_res.minerals:.0f}")
                        if getattr(moon_res, "ice", 0) > 0:
                            parts.append(f"I:{moon_res.ice:.0f}")
                        if parts:
                            m_res_str = "  " + "  ".join(parts)
                    items.append((f"  ↳ Moon: {moon.name}{m_res_str}", moon.id, (140, 160, 180)))
        self._body_list.set_items(items)

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._close_btn.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if self._rect.collidepoint(event.pos):
                    self._close()
                    return

            if event.type == pygame.MOUSEWHEEL and self._rect.collidepoint(pygame.mouse.get_pos()):
                if self._category == "bot":
                    gs = self.app.game_state
                    loc = self._body_id or self._system_id or ""
                    task_count = len(gs.bot_tasks.get(loc, self._type_value)) if gs else 0
                    visible = max(1, (self._rect.height - 150) // 46)
                    max_scroll = max(0, task_count - visible)
                    self._bot_scroll = max(0, min(max_scroll, self._bot_scroll - event.y))
                elif self._category == "structure":
                    self._struct_scroll = max(0, self._struct_scroll - event.y * ROW_H)
                elif self._category == "ship":
                    self._ship_scroll = max(0, self._ship_scroll - event.y * ROW_H)

            if self._category == "bot":
                self._handle_bot_events(event)
            elif self._category == "structure":
                self._handle_structure_events(event)
            elif self._category == "ship":
                self._sys_list.handle_event(event)
                if self._send_system_id and self._type_value in ("mining_vessel", "transport"):
                    self._body_list.handle_event(event)
                self._handle_ship_events(event)

    def _handle_structure_events(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        pos = event.pos
        gs = self.app.game_state
        if not gs:
            return
        for rect, action, data in self._hit_rects:
            if rect.collidepoint(pos):
                if action == "toggle_power_plant":
                    key = f"{self._body_id or self._system_id}:{self._type_value}"
                    gs.power_plant_active[key] = not gs.power_plant_active.get(key, True)
                elif action == "toggle_refine":
                    loc = self._body_id or self._system_id or ""
                    gs.extractor_refine_mode[loc] = not gs.extractor_refine_mode.get(loc, False)
                elif action == "factory_alloc_dec":
                    task_id, loc = data
                    gs.factory_tasks.adjust_allocation(loc, task_id, -10)
                elif action == "factory_alloc_inc":
                    task_id, loc = data
                    gs.factory_tasks.adjust_allocation(loc, task_id, +10)
                elif action == "factory_remove":
                    task_id, loc = data
                    gs.factory_tasks.remove(loc, task_id)
                elif action == "toggle_factory_form":
                    self._add_task_mode = not self._add_task_mode
                elif action == "set_res":
                    self._add_task_res = str(data)
                elif action == "dec_amount":
                    self._add_task_amount = max(0, self._add_task_amount - 100)
                elif action == "inc_amount":
                    self._add_task_amount = min(99999, self._add_task_amount + 100)
                elif action == "confirm_factory_task":
                    from ..game_state import FactoryTask
                    loc_id = str(data)
                    valid_recipes = ["alloys", "electronics", "fuel_cells", "components"]
                    recipe = self._add_task_res if self._add_task_res in valid_recipes else "alloys"
                    gs.factory_tasks.add(loc_id, FactoryTask(
                        recipe_id=recipe,
                        target_amount=float(self._add_task_amount) if self._add_task_amount > 0 else 0.0,
                        allocation=25,
                    ))
                    self._add_task_mode = False
                elif action == "toggle_shipyard_form":
                    self._add_task_mode = not self._add_task_mode
                elif action == "confirm_shipyard_task":
                    from ..game_state import ShipyardTask
                    loc_id = str(data)
                    count = max(1, self._add_task_amount // 100)
                    valid_ships = ["probe", "drop_ship", "mining_vessel", "transport", "warship"]
                    ship = self._add_task_res if self._add_task_res in valid_ships else "probe"
                    gs.shipyard_tasks.add(loc_id, ShipyardTask(
                        ship_type=ship,
                        target_count=count,
                    ))
                    self._add_task_mode = False
                elif action == "shipyard_remove":
                    task_id, loc = data
                    gs.shipyard_tasks.remove(loc, task_id)
                return

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

        elif action == "set_transport_target":
            self._transport_target_body = str(data)

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
            elif self._add_task_type == "transport":
                task = BotTask(
                    task_type="transport",
                    resource=self._add_task_res,
                    entity_type=None,
                    target_amount=self._add_task_amount,
                    target_location=self._transport_target_body,
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
            self._transport_target_body = None

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
                    self._send_system_id = None
                    self._send_body_id   = None
                    if self._send_mode:
                        self._rebuild_sys_list()
                elif action == "dispatch_ship":
                    self._dispatch_ship()
                elif action == "cancel_order":
                    gs = self.app.game_state
                    if gs:
                        loc = self._system_id or ""
                        gs.order_queue.dequeue(loc, self._type_value)
                return

    def _dispatch_ship(self) -> None:
        if not self._send_system_id:
            return
        gs = self.app.game_state
        galaxy = self.app.galaxy
        if not gs or not galaxy:
            return
        loc = self._system_id or ""
        count = sum(
            i.count for i in gs.entity_roster.at(loc)
            if i.category == "ship" and i.type_value == self._type_value
        )
        if count == 0:
            return

        # Fuel cell check
        from ..models.entity import SHIP_FUEL_COSTS
        fuel_cost = SHIP_FUEL_COSTS.get(self._type_value, 0.0)
        if fuel_cost > 0:
            home_sys = next((s for s in galaxy.solar_systems if s.id == self._system_id), None)
            if home_sys:
                fueled = False
                for body in home_sys.orbital_bodies:
                    if body.resources.fuel_cells >= fuel_cost:
                        body.resources.fuel_cells -= fuel_cost
                        fueled = True
                        break
                    if not fueled:
                        for moon in body.moons:
                            if moon.resources.fuel_cells >= fuel_cost:
                                moon.resources.fuel_cells -= fuel_cost
                                fueled = True
                                break
                    if fueled:
                        break
                if not fueled:
                    self._fuel_warning = True
                    return
        self._fuel_warning = False

        # Determine target body
        target_sys = next(
            (s for s in galaxy.solar_systems if s.id == self._send_system_id), None
        )
        if self._type_value in ("mining_vessel", "transport") and self._send_body_id:
            # Player explicitly chose a body — use it
            target_body_id: str | None = self._send_body_id
        elif self._type_value == "drop_ship":
            # Drop ship converts on a planet surface — first orbital body
            target_body_id = (
                target_sys.orbital_bodies[0].id
                if target_sys and target_sys.orbital_bodies else None
            )
        else:
            target_body_id = None

        from ..simulation import ShipOrder, SHIP_SPEEDS
        speed = SHIP_SPEEDS.get(self._type_value, 0.25)
        # Compute BFS waypoints for multi-hop visual path
        waypoints: list[str] = []
        if loc and self._send_system_id and loc != self._send_system_id:
            waypoints = gs.shortest_path(loc, self._send_system_id)
        order = ShipOrder(
            order_type="travel",
            target_system_id=self._send_system_id,
            target_body_id=target_body_id,
            travel_speed=speed,
            waypoints=waypoints,
        )
        gs.order_queue.enqueue(loc, self._type_value, order)
        self._send_mode      = False
        self._send_system_id = None
        self._send_body_id   = None
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

    def _draw_structure(self, surface: pygame.Surface, cx: int, cy_in: int) -> int:
        from ..models.entity import POWER_PLANT_SPECS, StructureType, REFINE_RECIPES

        # Apply scroll via clip offset
        content_top = cy_in
        cy = cy_in - self._struct_scroll

        def txt(label: str, value: str, vcol=C_TEXT) -> None:
            nonlocal cy
            if cy >= content_top - ROW_H and cy < self._rect.bottom:
                l = font(12).render(label, True, C_TEXT_DIM)
                v = font(12, bold=True).render(value, True, vcol)
                surface.blit(l, (cx, cy))
                surface.blit(v, (self._rect.right - v.get_width() - PADDING * 2, cy))
            cy += ROW_H

        gs = self.app.game_state
        loc = self._body_id or self._system_id
        txt("Location", loc or "—", C_TEXT_DIM)

        # Power plant details
        try:
            st = StructureType(self._type_value)
        except ValueError:
            st = None
        if st and st in POWER_PLANT_SPECS:
            spec = POWER_PLANT_SPECS[st]
            # Active / Inactive toggle
            flag_key = f"{loc}:{self._type_value}"
            is_active = gs.power_plant_active.get(flag_key, True) if gs else True
            cy += 4
            if cy >= content_top - 30 and cy < self._rect.bottom:
                tog_r = pygame.Rect(cx, cy, 110, 24)
                tog_col = (0, 120, 60) if is_active else (80, 30, 30)
                pygame.draw.rect(surface, tog_col, tog_r, border_radius=4)
                tog_lbl = font(11, bold=True).render(
                    "● ACTIVE" if is_active else "○ INACTIVE", True,
                    (100, 255, 140) if is_active else (200, 80, 80)
                )
                surface.blit(tog_lbl, tog_lbl.get_rect(center=tog_r.center))
                self._hit_rects.append((tog_r, "toggle_power_plant", None))
            cy += 30
            cy += 4
            if cy >= content_top - 18 and cy < self._rect.bottom:
                draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
                lbl = font(11, bold=True).render("POWER PLANT", True, C_ACCENT)
                surface.blit(lbl, (cx, cy + 3))
            cy += 18
            count = self._count_at_location()
            txt("Total output/yr", f"{spec.base_output * count:,.0f}" if is_active else "0 (inactive)", C_WARN)
            txt("Per unit/yr", f"{spec.base_output:,.0f}", C_TEXT_DIM)
            txt("Renewable", "Yes" if spec.renewable else "No",
                (80, 200, 100) if spec.renewable else C_WARN)
            if spec.input_resource:
                txt("Consumes", spec.input_resource.replace("_", " ").title(), C_WARN)
                txt("Rate (per unit/yr)", f"{spec.input_rate:.1f}")
            # Show modifier
            from ..models.entity import compute_power_modifier
            mod = compute_power_modifier(gs, loc or "", self._type_value) if gs else 1.0
            mod_col = (80, 220, 100) if mod >= 1.0 else (255, 180, 80)
            if cy >= content_top - ROW_H and cy < self._rect.bottom:
                mod_s = font(11).render(f"Env modifier: {mod:.2f}×", True, mod_col)
                surface.blit(mod_s, (cx, cy))
            cy += ROW_H

        # Extractor refine mode toggle
        if self._type_value == "extractor":
            cy += 4
            refine_on = gs.extractor_refine_mode.get(loc or "", False) if gs else False
            if cy >= content_top - 30 and cy < self._rect.bottom:
                ref_r = pygame.Rect(cx, cy, 140, 24)
                ref_col = (20, 80, 120) if refine_on else (40, 40, 60)
                pygame.draw.rect(surface, ref_col, ref_r, border_radius=4)
                ref_lbl = font(11, bold=True).render(
                    "⚗ REFINE: ON" if refine_on else "⚗ REFINE: OFF",
                    True, (100, 200, 255) if refine_on else C_TEXT_DIM
                )
                surface.blit(ref_lbl, ref_lbl.get_rect(center=ref_r.center))
                self._hit_rects.append((ref_r, "toggle_refine", None))
            cy += 30
            if refine_on:
                cy += 4
                if cy >= content_top - 18 and cy < self._rect.bottom:
                    draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
                    lbl = font(11, bold=True).render("REFINE RECIPES (active)", True, C_ACCENT)
                    surface.blit(lbl, (cx, cy + 3))
                cy += 18
                for out_res, (costs, rate) in REFINE_RECIPES.items():
                    cost_str = " + ".join(f"{v:.0f} {k.replace('_',' ')}" for k, v in costs.items())
                    txt(f"→ {out_res.replace('_',' ').title()}/extractor/yr",
                        f"{rate:.0f}  (costs: {cost_str})", (100, 220, 255))

        # Research Array note
        if self._type_value == "research_array":
            cy += 4
            if cy >= content_top - 18 and cy < self._rect.bottom:
                draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
                lbl = font(11, bold=True).render("RESEARCH", True, C_ACCENT)
                surface.blit(lbl, (cx, cy + 3))
            cy += 18
            if cy >= content_top - ROW_H and cy < self._rect.bottom:
                note = font(12).render("Contributes 1 pt/yr to each in-progress tech.", True, C_TEXT_DIM)
                surface.blit(note, (cx, cy))
            cy += ROW_H
            if cy >= content_top - ROW_H and cy < self._rect.bottom:
                note2 = font(12).render("Use the TECH TREE button above to assign research.", True, C_TEXT_DIM)
                surface.blit(note2, (cx, cy))
            cy += ROW_H

        # Factory production queue
        if self._type_value == "factory" and gs:
            tasks = gs.factory_tasks.get(loc or "")
            total_alloc = gs.factory_tasks.total_allocation(loc or "")
            cy += 4
            if cy < self._rect.bottom:
                draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
                fh = font(11, bold=True).render("PRODUCTION", True, C_ACCENT)
                surface.blit(fh, (cx, cy + 3))
            cy += 18
            alloc_s = font(11).render(f"Capacity used: {total_alloc}%", True, C_TEXT_DIM)
            if cy < self._rect.bottom:
                surface.blit(alloc_s, (cx, cy))
            cy += 14
            for task in tasks:
                if cy + 40 > self._rect.bottom - 60:
                    break
                tr = pygame.Rect(cx, cy, self._rect.width - PADDING * 3, 38)
                pygame.draw.rect(surface, (18, 30, 60), tr, border_radius=3)
                pygame.draw.rect(surface, C_BORDER, tr, width=1, border_radius=3)
                desc = task.recipe_id.replace("_", " ").title()
                if task.target_amount > 0:
                    prog_str = f"{task.produced:.0f}/{task.target_amount:.0f}"
                    prog_frac = min(1.0, task.produced / max(1, task.target_amount))
                else:
                    prog_str = f"{task.produced:.0f} (cont.)"
                    prog_frac = 1.0
                surface.blit(font(12, bold=True).render(desc, True, C_TEXT), (cx + 6, cy + 4))
                surface.blit(font(11).render(prog_str, True, C_TEXT_DIM), (cx + 6, cy + 22))
                pygame.draw.rect(surface, (30, 50, 80), pygame.Rect(cx + 6, cy + 32, 180, 4))
                if prog_frac > 0:
                    pygame.draw.rect(surface, (80, 200, 255), pygame.Rect(cx + 6, cy + 32, int(180 * prog_frac), 4))
                # Allocation controls
                ax = tr.right - 110
                dec_r = pygame.Rect(ax, cy + 8, 22, 22)
                inc_r = pygame.Rect(ax + 50, cy + 8, 22, 22)
                alloc_s2 = font(12, bold=True).render(f"{task.allocation}%", True, C_SELECTED)
                pygame.draw.rect(surface, C_BTN, dec_r, border_radius=3)
                pygame.draw.rect(surface, C_BTN, inc_r, border_radius=3)
                surface.blit(font(13, bold=True).render("−", True, C_BTN_TXT), (dec_r.x + 5, dec_r.y + 2))
                surface.blit(font(13, bold=True).render("+", True, C_BTN_TXT), (inc_r.x + 5, inc_r.y + 2))
                surface.blit(alloc_s2, (ax + 26, cy + 10))
                self._hit_rects.append((dec_r, "factory_alloc_dec", (task.task_id, loc or "")))
                self._hit_rects.append((inc_r, "factory_alloc_inc", (task.task_id, loc or "")))
                rm_r = pygame.Rect(tr.right - 26, cy + 8, 22, 22)
                pygame.draw.rect(surface, (80, 20, 20), rm_r, border_radius=3)
                surface.blit(font(12, bold=True).render("✕", True, (255, 100, 100)), (rm_r.x + 4, rm_r.y + 2))
                self._hit_rects.append((rm_r, "factory_remove", (task.task_id, loc or "")))
                cy += 44
            # Add recipe button
            add_r = pygame.Rect(cx, cy + 4, 140, 26)
            pygame.draw.rect(surface, C_BTN_HOV if self._add_task_mode else C_BTN, add_r, border_radius=4)
            btn_txt = "▼  ADD RECIPE" if not self._add_task_mode else "▲  CANCEL"
            btn_surf = font(12, bold=True).render(btn_txt, True, C_BTN_TXT)
            surface.blit(btn_surf, btn_surf.get_rect(center=add_r.center))
            self._hit_rects.append((add_r, "toggle_factory_form", loc or ""))
            cy += 36
            if self._add_task_mode:
                cy = self._draw_factory_form(surface, cx, cy, loc or "")

        # Shipyard build queue
        if self._type_value == "shipyard" and gs:
            # Fuel Depot section
            cy += 4
            if cy < self._rect.bottom:
                draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
                fd_lbl = font(11, bold=True).render("FUEL DEPOT", True, (255, 200, 80))
                surface.blit(fd_lbl, (cx, cy + 3))
            cy += 18
            # Show available fuel_cells at this body
            fuel_avail = 0.0
            if gs.galaxy and loc:
                for sys in gs.galaxy.solar_systems:
                    for body in sys.orbital_bodies:
                        if body.id == loc:
                            fuel_avail = body.resources.fuel_cells
                        for moon in body.moons:
                            if moon.id == loc:
                                fuel_avail = moon.resources.fuel_cells
            fa_s = font(11).render(f"Available: {fuel_avail:.1f} fuel_cells", True, C_TEXT)
            if cy < self._rect.bottom:
                surface.blit(fa_s, (cx, cy))
            cy += 16
            from ..models.entity import SHIP_FUEL_COSTS
            for stype, fcost in SHIP_FUEL_COSTS.items():
                if cy >= self._rect.bottom:
                    break
                fc_row = font(10).render(
                    f"  {stype.replace('_',' ').title()}: {fcost:.0f} fuel_cells",
                    True, C_TEXT_DIM
                )
                surface.blit(fc_row, (cx, cy))
                cy += 14
            cy += 4

            tasks = gs.shipyard_tasks.get(loc or "")
            cy += 4
            if cy < self._rect.bottom:
                draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
                sh_lbl = font(11, bold=True).render("BUILD QUEUE", True, C_ACCENT)
                surface.blit(sh_lbl, (cx, cy + 3))
            cy += 18
            for task in tasks:
                if cy + 38 > self._rect.bottom - 60:
                    break
                tr = pygame.Rect(cx, cy, self._rect.width - PADDING * 3, 36)
                pygame.draw.rect(surface, (18, 30, 60), tr, border_radius=3)
                pygame.draw.rect(surface, C_BORDER, tr, width=1, border_radius=3)
                name = task.ship_type.replace("_", " ").title()
                surface.blit(font(12, bold=True).render(name, True, C_TEXT), (cx + 6, cy + 4))
                prog_str = f"{task.built_count}/{task.target_count}  (+{task.progress:.0%})"
                surface.blit(font(11).render(prog_str, True, C_TEXT_DIM), (cx + 6, cy + 22))
                rm_r = pygame.Rect(tr.right - 26, cy + 7, 22, 22)
                pygame.draw.rect(surface, (80, 20, 20), rm_r, border_radius=3)
                surface.blit(font(12, bold=True).render("✕", True, (255, 100, 100)), (rm_r.x + 4, rm_r.y + 2))
                self._hit_rects.append((rm_r, "shipyard_remove", (task.task_id, loc or "")))
                cy += 40
            # Add ship button
            add_r = pygame.Rect(cx, cy + 4, 140, 26)
            pygame.draw.rect(surface, C_BTN_HOV if self._add_task_mode else C_BTN, add_r, border_radius=4)
            btn_lbl_s = font(12, bold=True).render(
                "▼  BUILD SHIP" if not self._add_task_mode else "▲  CANCEL", True, C_BTN_TXT
            )
            surface.blit(btn_lbl_s, btn_lbl_s.get_rect(center=add_r.center))
            self._hit_rects.append((add_r, "toggle_shipyard_form", loc or ""))
            cy += 36
            if self._add_task_mode:
                cy = self._draw_shipyard_form(surface, cx, cy, loc or "")

        # Incoming build queue for this structure type
        if gs:
            queue_tasks = []
            for (loc_id, bot_type) in gs.bot_tasks.all_keys():
                for t in gs.bot_tasks.get(loc_id, bot_type):
                    if t.task_type == "build" and t.entity_type == self._type_value:
                        queue_tasks.append(t)
            if queue_tasks:
                cy += 4
                if cy >= content_top - 18 and cy < self._rect.bottom:
                    draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
                    q_lbl = font(11, bold=True).render("BUILD QUEUE", True, C_ACCENT)
                    surface.blit(q_lbl, (cx, cy + 3))
                cy += 18
                for qt in queue_tasks:
                    txt("Queued", f"{qt.built_count}/{qt.target_amount}  ({qt.allocation}% alloc)",
                        (80, 200, 100))

        # Clamp scroll to content
        content_h = cy + self._struct_scroll - content_top
        max_scroll = max(0, content_h - (self._rect.bottom - content_top - 10))
        self._struct_scroll = min(self._struct_scroll, max_scroll)

        return cy_in + max(0, cy - cy_in + self._struct_scroll)

    def _draw_factory_form(self, surface: pygame.Surface, cx: int, cy: int, loc: str) -> int:
        from ..models.entity import FACTORY_RECIPES
        from ..game_state import FactoryTask
        gs = self.app.game_state
        if not gs:
            return cy

        recipes = list(FACTORY_RECIPES.keys())
        # Gate components on advanced_manufacturing
        if not gs.tech.is_researched("advanced_manufacturing"):
            recipes = [r for r in recipes if r != "components"]

        form_r = pygame.Rect(cx, cy, self._rect.width - PADDING * 3,
                             26 + len(recipes) * 26 + 62)
        pygame.draw.rect(surface, (15, 25, 50), form_r, border_radius=4)
        pygame.draw.rect(surface, C_BORDER, form_r, width=1, border_radius=4)
        fy = cy + 8
        fx = cx + 8

        # Recipe selector
        for i, rid in enumerate(recipes):
            rr = pygame.Rect(fx, fy + i * 26, form_r.width - 20, 22)
            sel = self._add_task_res == rid
            pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, rr, border_radius=3)
            inputs, rate, out_field = FACTORY_RECIPES[rid]
            cost_parts = " + ".join(f"{v:.0f} {k.replace('_',' ')}" for k, v in inputs.items())
            label = f"{rid.replace('_',' ').title()}  ({rate:.0f}/factory/yr)  <- {cost_parts}"
            surface.blit(
                font(10, bold=True).render(label, True, (0, 0, 0) if sel else C_BTN_TXT),
                (rr.x + 4, rr.y + 4),
            )
            self._hit_rects.append((rr, "set_res", rid))
        fy += len(recipes) * 26 + 6

        # Amount row
        dec_r = pygame.Rect(fx, fy, 26, 22)
        inc_r = pygame.Rect(fx + 90, fy, 26, 22)
        pygame.draw.rect(surface, C_BTN, dec_r, border_radius=3)
        pygame.draw.rect(surface, C_BTN, inc_r, border_radius=3)
        surface.blit(font(13, bold=True).render("-", True, C_BTN_TXT), (dec_r.x + 7, dec_r.y + 2))
        surface.blit(font(13, bold=True).render("+", True, C_BTN_TXT), (inc_r.x + 7, inc_r.y + 2))
        amt_lbl = font(12, bold=True).render(str(self._add_task_amount), True, C_SELECTED)
        surface.blit(amt_lbl, (fx + 34, fy + 3))
        surface.blit(font(11).render("units (0=unlimited)", True, C_TEXT_DIM), (fx + 120, fy + 4))
        self._hit_rects.append((dec_r, "dec_amount", None))
        self._hit_rects.append((inc_r, "inc_amount", None))
        fy += 30

        conf_r = pygame.Rect(fx, fy, 110, 24)
        pygame.draw.rect(surface, (0, 120, 80), conf_r, border_radius=4)
        conf_s = font(12, bold=True).render("ASSIGN", True, (200, 255, 220))
        surface.blit(conf_s, conf_s.get_rect(center=conf_r.center))
        self._hit_rects.append((conf_r, "confirm_factory_task", loc))

        return fy + 32

    def _draw_shipyard_form(self, surface: pygame.Surface, cx: int, cy: int, loc: str) -> int:
        from ..models.entity import SHIPYARD_BUILD_RATES, BUILD_COSTS
        from ..game_state import ShipyardTask
        gs = self.app.game_state
        if not gs:
            return cy

        ships = list(SHIPYARD_BUILD_RATES.keys())
        if not gs.tech.is_researched("atomic_warships"):
            ships = [s for s in ships if s != "warship"]

        form_r = pygame.Rect(cx, cy, self._rect.width - PADDING * 3,
                             26 + len(ships) * 26 + 62)
        pygame.draw.rect(surface, (15, 25, 50), form_r, border_radius=4)
        pygame.draw.rect(surface, C_BORDER, form_r, width=1, border_radius=4)
        fy = cy + 8
        fx = cx + 8

        for i, stype in enumerate(ships):
            sr = pygame.Rect(fx, fy + i * 26, form_r.width - 20, 22)
            sel = self._add_task_res == stype
            pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, sr, border_radius=3)
            build_t = SHIPYARD_BUILD_RATES[stype]
            cost = BUILD_COSTS.get(stype, {})
            cost_str = " + ".join(f"{v:.0f} {k.replace('_',' ')}" for k, v in cost.items())
            label = f"{stype.replace('_',' ').title()}  ({build_t:.1f} yr/ship)  <- {cost_str}"
            surface.blit(
                font(10, bold=True).render(label, True, (0, 0, 0) if sel else C_BTN_TXT),
                (sr.x + 4, sr.y + 4),
            )
            self._hit_rects.append((sr, "set_res", stype))
        fy += len(ships) * 26 + 6

        dec_r = pygame.Rect(fx, fy, 26, 22)
        inc_r = pygame.Rect(fx + 90, fy, 26, 22)
        pygame.draw.rect(surface, C_BTN, dec_r, border_radius=3)
        pygame.draw.rect(surface, C_BTN, inc_r, border_radius=3)
        surface.blit(font(13, bold=True).render("-", True, C_BTN_TXT), (dec_r.x + 7, dec_r.y + 2))
        surface.blit(font(13, bold=True).render("+", True, C_BTN_TXT), (inc_r.x + 7, inc_r.y + 2))
        count = max(1, self._add_task_amount // 100)
        surface.blit(font(12, bold=True).render(str(count), True, C_SELECTED), (fx + 34, fy + 3))
        surface.blit(font(11).render("ships to build", True, C_TEXT_DIM), (fx + 120, fy + 4))
        self._hit_rects.append((dec_r, "dec_amount", None))
        self._hit_rects.append((inc_r, "inc_amount", None))
        fy += 30

        conf_r = pygame.Rect(fx, fy, 110, 24)
        pygame.draw.rect(surface, (0, 80, 160), conf_r, border_radius=4)
        conf_s = font(12, bold=True).render("QUEUE BUILD", True, (200, 230, 255))
        surface.blit(conf_s, conf_s.get_rect(center=conf_r.center))
        self._hit_rects.append((conf_r, "confirm_shipyard_task", loc))

        return fy + 32

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

            visible_tasks = max(1, (self._rect.bottom - cy - 90) // 46)
            total_tasks = len(tasks)
            max_scroll = max(0, total_tasks - visible_tasks)
            self._bot_scroll = max(0, min(max_scroll, self._bot_scroll))
            visible = tasks[self._bot_scroll: self._bot_scroll + visible_tasks]

            # Scrollbar
            if total_tasks > visible_tasks:
                sb_x = self._rect.right - PADDING - 4
                sb_h = visible_tasks * 46
                sb_y = cy
                thumb_h = max(16, int(sb_h * visible_tasks / total_tasks))
                thumb_y = sb_y + int((sb_h - thumb_h) * self._bot_scroll / max_scroll)
                pygame.draw.rect(surface, (30, 50, 80),
                                 pygame.Rect(sb_x, sb_y, 4, sb_h), border_radius=2)
                pygame.draw.rect(surface, (80, 120, 180),
                                 pygame.Rect(sb_x, thumb_y, 4, thumb_h), border_radius=2)

            for task in visible:
                task_r = pygame.Rect(cx, cy, self._rect.width - PADDING * 3, 40)
                pygame.draw.rect(surface, (18, 30, 60), task_r, border_radius=3)
                pygame.draw.rect(surface, C_BORDER, task_r, width=1, border_radius=3)

                # Task description
                if task.task_type == "mine":
                    desc = f"MINE  {task.resource or '?'}"
                    progress_frac = min(1.0, task.progress / max(1, task.target_amount))
                    prog_str = f"{task.progress:,.0f} / {task.target_amount:,.0f}"
                elif task.task_type == "transport":
                    dest_name = task.target_location or "?"
                    if self.app.galaxy and task.target_location:
                        for sys in self.app.galaxy.solar_systems:
                            for body in sys.orbital_bodies:
                                if body.id == task.target_location:
                                    dest_name = body.name
                                for moon in body.moons:
                                    if moon.id == task.target_location:
                                        dest_name = moon.name
                    desc = f"TRANSPORT  {task.resource or '?'} → {dest_name}"
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
        if self._add_task_type == "transport":
            # destination body selector: label + up to 4 rows of 2 bodies each
            form_h += 22   # label
            sys_obj = self.app.selected_system
            body_count = 0
            if sys_obj:
                current_loc = self._body_id or self._system_id or ""
                for body in sys_obj.orbital_bodies:
                    if body.id != current_loc:
                        body_count += 1
                    body_count += sum(1 for moon in body.moons if moon.id != current_loc)
            form_h += ((body_count + 1) // 2) * 24 + 4
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
            all_types = [("mine", "Mine"), ("build", "Build"), ("transport", "Transport")]
            for i, (ttype, tlabel) in enumerate(
                t for t in all_types if t[0] in allowed_types
            ):
                tr = pygame.Rect(fx + i * 90, fy, 82, 22)
                sel = self._add_task_type == ttype
                pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, tr, border_radius=3)
                lbl = font(11, bold=True).render(tlabel, True, (0, 0, 0) if sel else C_BTN_TXT)
                surface.blit(lbl, lbl.get_rect(center=tr.center))
                self._hit_rects.append((tr, "set_task_type", ttype))
            fy += 30

        # Resource / entity type selector
        if self._add_task_type == "mine" or self._add_task_type == "transport":
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

            # For transport: show destination body selector
            if self._add_task_type == "transport":
                dest_lbl = font(11, bold=True).render("Destination:", True, C_TEXT_DIM)
                surface.blit(dest_lbl, (fx, fy))
                fy += 18
                # Get bodies in current system, excluding current location
                dest_bodies: list[tuple[str, str]] = []
                current_loc = self._body_id or self._system_id or ""
                sys_obj = self.app.selected_system
                if sys_obj:
                    for body in sys_obj.orbital_bodies:
                        if body.id != current_loc:
                            dest_bodies.append((body.name, body.id))
                        for moon in body.moons:
                            if moon.id != current_loc:
                                dest_bodies.append((f"↳ {moon.name}", moon.id))
                for i, (bname, bid) in enumerate(dest_bodies):
                    br = pygame.Rect(fx + (i % 2) * 140, fy + (i // 2) * 24, 132, 20)
                    sel = self._transport_target_body == bid
                    pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, br, border_radius=3)
                    blbl = font(9, bold=True).render(
                        bname[:16], True, (0, 0, 0) if sel else C_BTN_TXT
                    )
                    surface.blit(blbl, blbl.get_rect(center=br.center))
                    self._hit_rects.append((br, "set_transport_target", bid))
                rows = (len(dest_bodies) + 1) // 2
                fy += rows * 24 + 4
        else:
            # Show structures then bots in a grid
            gs = self.app.game_state
            buildables = _get_buildable_structures(gs) + _BUILD_BOTS + _BUILD_SHIPS
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
        target = self._add_task_amount if self._add_task_type in ("mine", "transport") else max(1, self._add_task_amount // 100)
        amt_s = font(12, bold=True).render(str(target), True, C_SELECTED)
        surface.blit(amt_s, (fx + 34, fy + 3))
        unit_lbl = "units" if self._add_task_type in ("mine", "transport") else "units to build"
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

    def _draw_ship(self, surface: pygame.Surface, cx: int, cy_in: int) -> int:
        from ..simulation import SHIP_SPEEDS
        gs = self.app.game_state
        if not gs:
            return cy_in

        loc = self._system_id or ""
        content_top = cy_in
        cy = cy_in - self._ship_scroll

        def txt(label: str, value: str, vcol=C_TEXT) -> None:
            nonlocal cy
            if cy >= content_top - ROW_H and cy < self._rect.bottom:
                l = font(12).render(label, True, C_TEXT_DIM)
                v = font(12, bold=True).render(value, True, vcol)
                surface.blit(l, (cx, cy))
                surface.blit(v, (self._rect.right - v.get_width() - PADDING * 2, cy))
            cy += ROW_H

        count = self._count_at_location()
        txt("In system", str(count))

        # Ship role / stats
        _SHIP_ROLES = {
            "probe":         "Recon — scouts new systems",
            "drop_ship":     "Colony — deploys Constructor + Miner on arrival",
            "mining_vessel": "Extraction — docks at bodies to mine resources",
            "transport":     "Cargo — ferries resources between colonies",
            "warship":       "Combat — system defence and projection",
        }
        _SHIP_SPEED_LABELS = {
            "probe": "Fast", "transport": "Medium",
            "mining_vessel": "Medium", "drop_ship": "Slow", "warship": "Very Slow",
        }
        role = _SHIP_ROLES.get(self._type_value, "")
        spd  = SHIP_SPEEDS.get(self._type_value, 0.25)
        spd_lbl = _SHIP_SPEED_LABELS.get(self._type_value, f"{spd:.0%}/yr")
        if cy >= content_top - ROW_H and cy < self._rect.bottom:
            rs = font(11).render(role, True, C_TEXT_DIM)
            surface.blit(rs, (cx, cy))
        cy += ROW_H - 4
        txt("Speed", f"{spd_lbl}  ({spd:.0%}/yr)", C_TEXT_DIM)

        # Travel queue
        orders = gs.order_queue.get_all(loc, self._type_value)
        cy += 4
        if cy < self._rect.bottom:
            draw_separator(surface, cx, cy, self._rect.right - PADDING * 2)
            qlbl = font(11, bold=True).render("TRAVEL QUEUE", True, C_ACCENT)
            surface.blit(qlbl, (cx, cy + 3))
        cy += 18

        if orders:
            galaxy = self.app.galaxy
            for i, order in enumerate(orders[:5]):
                dest_str = order.target_system_id or "?"
                if galaxy:
                    sys_obj = next(
                        (s for s in galaxy.solar_systems if s.id == dest_str), None
                    )
                    if sys_obj:
                        dest_str = sys_obj.name
                # Show body docking target if present
                if order.target_body_id and order.target_body_id != order.target_system_id:
                    dest_str += "  (body)"
                prog_str = f"{order.progress:.0%}"
                eta_frac = 1.0 - order.progress
                eta_yr = eta_frac / max(order.travel_speed, 0.01)
                row_col = C_ACCENT if i == 0 else C_TEXT_DIM
                if cy >= content_top - ROW_H and cy < self._rect.bottom:
                    row_s = font(12).render(
                        f"{'▶' if i == 0 else '◦'}  {dest_str}  —  {prog_str}"
                        f"  (~{eta_yr:.1f}yr)",
                        True, row_col,
                    )
                    surface.blit(row_s, (cx + 6, cy))
                    pbar_w = min(200, self._rect.width - PADDING * 4 - 30)
                    pygame.draw.rect(surface, (30, 50, 80),
                                     pygame.Rect(cx + 6, cy + 16, pbar_w, 4))
                    pygame.draw.rect(surface, C_ACCENT,
                                     pygame.Rect(cx + 6, cy + 16,
                                                 int(pbar_w * order.progress), 4))
                    # Cancel button for the first (active) order
                    if i == 0:
                        cx_btn = cx + 6 + pbar_w + 6
                        cncl_r = pygame.Rect(cx_btn, cy + 10, 22, 22)
                        pygame.draw.rect(surface, (80, 20, 20), cncl_r, border_radius=3)
                        surface.blit(
                            font(11, bold=True).render("✕", True, (255, 100, 100)),
                            (cncl_r.x + 4, cncl_r.y + 3),
                        )
                        self._hit_rects.append((cncl_r, "cancel_order", None))
                cy += 26
        else:
            if cy < self._rect.bottom:
                no_ord = font(12).render("No orders queued.", True, C_TEXT_DIM)
                surface.blit(no_ord, (cx, cy))
            cy += ROW_H

        # Dispatch panel — available for ALL ship types when ships are present
        if count > 0:
            cy += 8
            # Fuel cost info
            from ..models.entity import SHIP_FUEL_COSTS
            fuel_cost = SHIP_FUEL_COSTS.get(self._type_value, 0.0)
            if fuel_cost > 0:
                fc_s = font(11).render(f"⛽ Cost: {fuel_cost:.0f} fuel_cells per dispatch",
                                       True, C_TEXT_DIM)
                surface.blit(fc_s, (cx, cy))
                cy += 16
            # Fuel warning
            if self._fuel_warning and not self._send_mode:
                fw_s = font(11, bold=True).render(
                    "⚠ Insufficient fuel_cells for dispatch", True, C_WARN
                )
                surface.blit(fw_s, (cx, cy))
                cy += 16
            send_btn_r = pygame.Rect(cx, cy, 170, 28)
            pygame.draw.rect(surface, C_BTN_HOV if self._send_mode else C_BTN,
                             send_btn_r, border_radius=4)
            send_lbl = font(12, bold=True).render(
                "▼  DISPATCH SHIP" if not self._send_mode else "▲  CANCEL",
                True, C_BTN_TXT,
            )
            surface.blit(send_lbl, send_lbl.get_rect(center=send_btn_r.center))
            self._hit_rects.append((send_btn_r, "toggle_send", None))
            cy += 36

            if self._send_mode:
                # Step 1 — System selector
                avail_h = max(80, min(180, self._rect.bottom - cy - 60))
                self._sys_list.rect = pygame.Rect(cx, cy, self._rect.width - PADDING * 2, avail_h)
                self._sys_list.draw(surface)
                cy += avail_h + 6

                # Step 2 — Body selector (mining_vessel / transport only)
                if self._send_system_id and self._type_value in ("mining_vessel", "transport"):
                    galaxy = self.app.galaxy
                    dest_name = self._send_system_id
                    if galaxy:
                        sys_obj = next(
                            (s for s in galaxy.solar_systems if s.id == self._send_system_id), None
                        )
                        if sys_obj:
                            dest_name = sys_obj.name
                    if cy < self._rect.bottom:
                        hint_col = (180, 220, 160) if self._type_value == "mining_vessel" \
                                   else (180, 200, 255)
                        hl = font(11, bold=True).render(
                            f"Select docking body in {dest_name}:", True, hint_col
                        )
                        surface.blit(hl, (cx, cy))
                    cy += 16
                    body_h = max(60, min(140, self._rect.bottom - cy - 40))
                    self._body_list.rect = pygame.Rect(cx, cy, self._rect.width - PADDING * 2, body_h)
                    self._body_list.draw(surface)
                    cy += body_h + 6

                # Dispatch button — show when system chosen (body optional for transport/mining)
                if self._send_system_id:
                    # For mining_vessel/transport: require body selection OR allow system-level
                    needs_body = self._type_value in ("mining_vessel", "transport")
                    has_body   = bool(self._send_body_id)
                    can_dispatch = not needs_body or has_body

                    galaxy = self.app.galaxy
                    dest_name = self._send_system_id
                    body_name = ""
                    if galaxy:
                        sys_obj = next(
                            (s for s in galaxy.solar_systems if s.id == self._send_system_id), None
                        )
                        if sys_obj:
                            dest_name = sys_obj.name
                        if self._send_body_id and galaxy:
                            for sys in galaxy.solar_systems:
                                for body in sys.orbital_bodies:
                                    if body.id == self._send_body_id:
                                        body_name = f" → {body.name}"
                                    for moon in body.moons:
                                        if moon.id == self._send_body_id:
                                            body_name = f" → {moon.name}"

                    disp_col = (0, 120, 60) if can_dispatch else (40, 60, 80)
                    disp_btn_r = pygame.Rect(cx, cy, self._rect.width - PADDING * 3, 28)
                    pygame.draw.rect(surface, disp_col, disp_btn_r, border_radius=4)
                    disp_lbl = font(12, bold=True).render(
                        f"DISPATCH → {dest_name}{body_name}",
                        True, (200, 255, 220) if can_dispatch else C_TEXT_DIM,
                    )
                    surface.blit(disp_lbl, disp_lbl.get_rect(center=disp_btn_r.center))
                    if can_dispatch:
                        self._hit_rects.append((disp_btn_r, "dispatch_ship", None))
                    cy += 36

        # Clamp ship scroll
        content_h = cy + self._ship_scroll - content_top
        max_scroll = max(0, content_h - (self._rect.bottom - content_top - 10))
        self._ship_scroll = min(self._ship_scroll, max_scroll)

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
