"""
Help / Guide overlay.

Full-window panel (below taskbar) showing a per-entity reference guide.
Opened by clicking an entity tooltip or the '? HELP' taskbar button.

Activated via App.open_help_view(entity_type) / App.close_help_view().
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TASKBAR_H, HEADER_H, PADDING,
    C_PANEL, C_BORDER, C_HEADER, C_BG,
    C_TEXT, C_TEXT_DIM, C_ACCENT, C_SELECTED, C_HOVER,
    C_SEP, C_WARN, C_SCROLLBAR,
    font,
)
from .widgets import Button
from ..models.entity import BUILD_COSTS, ENERGY_CONSUMPTION, POWER_PLANT_SPECS, StructureType


# ---------------------------------------------------------------------------
# Guide data model
# ---------------------------------------------------------------------------

@dataclass
class _GuideEntry:
    name: str
    category: str                       # "structure" | "bot" | "ship"
    full_desc: tuple[str, ...]          # pre-split lines ~55 chars each
    actions: list[str]                  # "What you can do" bullets
    build_cost: dict[str, float] = field(default_factory=dict)
    energy_draw: float = 0.0
    required_tech: str | None = None
    tips: list[str] = field(default_factory=list)


def _e(type_val: str) -> _GuideEntry:
    """Helper: pull build_cost and energy_draw from entity model dicts."""
    return _GuideEntry(
        name="",
        category="",
        full_desc=(),
        actions=[],
        build_cost=BUILD_COSTS.get(type_val, {}),
        energy_draw=ENERGY_CONSUMPTION.get(type_val, 0.0),
    )


_GUIDE_DATA: dict[str, _GuideEntry] = {}

def _build_guide_data() -> dict[str, _GuideEntry]:
    d: dict[str, _GuideEntry] = {}

    # --- Structures ---

    d["extractor"] = _GuideEntry(
        name="Extractor",
        category="structure",
        full_desc=(
            "Drills the surface to harvest raw minerals,",
            "ice and gas from local deposits.",
            "Output scales with deposit richness.",
        ),
        actions=[
            "Click the row to open entity detail view",
            "Assign Miner bots to increase throughput",
            "Place near high-richness deposits for best yield",
        ],
        build_cost=BUILD_COSTS.get("extractor", {}),
        energy_draw=ENERGY_CONSUMPTION.get("extractor", 0.0),
        tips=[
            "Stack multiple Extractors on a rich vein",
            "Pair with a Storage Hub to buffer output",
        ],
    )

    d["factory"] = _GuideEntry(
        name="Factory",
        category="structure",
        full_desc=(
            "Processes raw materials into electronics,",
            "alloys and refined components.",
            "Runs recipes automatically when inputs are stocked.",
        ),
        actions=[
            "Click the row to view active recipes",
            "Ensure upstream Extractors feed raw inputs",
        ],
        build_cost=BUILD_COSTS.get("factory", {}),
        energy_draw=ENERGY_CONSUMPTION.get("factory", 0.0),
        tips=[
            "Factories only produce what recipes allow",
            "Check the Queue overlay to monitor output",
        ],
    )

    d["power_plant_solar"] = _GuideEntry(
        name="Solar Farm",
        category="structure",
        full_desc=(
            "Converts stellar radiation into energy.",
            "Output falls off with orbital distance.",
            "Completely renewable — no fuel required.",
        ),
        actions=[
            "Produces energy passively — no action needed",
            "Build more units to scale capacity",
        ],
        build_cost=BUILD_COSTS.get("power_plant_solar", {}),
        energy_draw=0.0,
        tips=[
            "Less effective in distant or dim star systems",
            "Combine with Wind Farms for diversity",
        ],
    )

    d["power_plant_wind"] = _GuideEntry(
        name="Wind Farm",
        category="structure",
        full_desc=(
            "Harvests kinetic energy from atmospheric winds.",
            "Only effective on bodies with a dense atmosphere.",
            "Fully renewable with no resource cost.",
        ),
        actions=[
            "Produces energy passively — no action needed",
        ],
        build_cost=BUILD_COSTS.get("power_plant_wind", {}),
        energy_draw=0.0,
        tips=[
            "Gas giants and terrestrials have the best winds",
            "Useless on airless moons and asteroids",
        ],
    )

    d["power_plant_bios"] = _GuideEntry(
        name="Bio Plant",
        category="structure",
        full_desc=(
            "Burns harvested biological material for energy.",
            "Requires an active bios supply on the body.",
            "Goes offline automatically when bios run out.",
        ),
        actions=[
            "Assign Harvester bots to replenish bios supply",
            "Monitor bios reserves in the Energy overlay",
        ],
        build_cost=BUILD_COSTS.get("power_plant_bios", {}),
        energy_draw=0.0,
        tips=[
            "Bios regenerates naturally but slowly",
            "Harvesters accelerate the refresh rate",
        ],
    )

    spec_ff = POWER_PLANT_SPECS.get(StructureType.POWER_PLANT_FOSSIL)
    d["power_plant_fossil"] = _GuideEntry(
        name="Fossil Fuel Plant",
        category="structure",
        full_desc=(
            "Burns atmospheric gas for high output.",
            "Gas deposits are finite and will deplete over time.",
            "Requires a body with gas reserves.",
        ),
        actions=[
            "Monitor gas reserves in the Energy overlay",
            "Plan transition to renewable sources early",
        ],
        build_cost=BUILD_COSTS.get("power_plant_fossil", {}),
        energy_draw=0.0,
        tips=[
            f"Consumes ~{spec_ff.input_rate:.0f} gas/yr per plant" if spec_ff else "",
            "Switch to Nuclear or Cold Fusion before gas runs dry",
        ],
    )

    spec_nuc = POWER_PLANT_SPECS.get(StructureType.POWER_PLANT_NUCLEAR)
    d["power_plant_nuclear"] = _GuideEntry(
        name="Nuclear Plant",
        category="structure",
        full_desc=(
            "Fissions rare minerals to produce abundant power.",
            "High output; requires rare mineral reserves.",
            "No tech gate — buildable from the start.",
        ),
        actions=[
            "Ensure rare minerals are being mined",
            "Monitor reserves in the Energy overlay",
        ],
        build_cost=BUILD_COSTS.get("power_plant_nuclear", {}),
        energy_draw=0.0,
        tips=[
            f"Consumes ~{spec_nuc.input_rate:.0f} rare minerals/yr each" if spec_nuc else "",
            "High output — fewer units needed than Solar/Wind",
        ],
    )

    spec_cf = POWER_PLANT_SPECS.get(StructureType.POWER_PLANT_COLD_FUSION)
    d["power_plant_cold_fusion"] = _GuideEntry(
        name="Cold Fusion Plant",
        category="structure",
        full_desc=(
            "Fuses hydrogen at ambient temperature using ice.",
            "Requires the Cold Fusion tech to unlock.",
            f"Outputs {spec_cf.base_output:.0f} energy/yr per plant." if spec_cf else "",
        ),
        actions=[
            "Research Cold Fusion in the Tech Tree first",
            "Ensure ice deposits are present on the body",
        ],
        build_cost=BUILD_COSTS.get("power_plant_cold_fusion", {}),
        energy_draw=0.0,
        required_tech="cold_fusion",
        tips=[
            "Best mid-game power source on icy bodies",
            "Very cost-efficient per unit of energy",
        ],
    )

    spec_dm = POWER_PLANT_SPECS.get(StructureType.POWER_PLANT_DARK_MATTER)
    d["power_plant_dark_matter"] = _GuideEntry(
        name="Dark Matter Plant",
        category="structure",
        full_desc=(
            "Taps exotic dark matter interactions for limitless power.",
            "Requires the Dark Matter tech to unlock.",
            f"Outputs {spec_dm.base_output:.0f} energy/yr — fully renewable." if spec_dm else "",
        ),
        actions=[
            "Research Dark Matter in the Tech Tree first",
            "No fuel monitoring needed — fully autonomous",
        ],
        build_cost=BUILD_COSTS.get("power_plant_dark_matter", {}),
        energy_draw=0.0,
        required_tech="dark_matter",
        tips=[
            "Single best late-game power source",
            "High build cost but zero ongoing fuel cost",
        ],
    )

    d["research_array"] = _GuideEntry(
        name="Research Array",
        category="structure",
        full_desc=(
            "Generates research points passively each year.",
            "Research points unlock new tech tree nodes.",
            "Build more arrays to speed up your tech progress.",
        ),
        actions=[
            "No direct interaction needed — works passively",
            "Open Tech Tree (TECH button) to spend research",
        ],
        build_cost=BUILD_COSTS.get("research_array", {}),
        energy_draw=ENERGY_CONSUMPTION.get("research_array", 0.0),
        tips=[
            "Prioritise research early for a tech advantage",
            "Spreading arrays across multiple colonies compounds output",
        ],
    )

    d["replicator"] = _GuideEntry(
        name="Replicator",
        category="structure",
        full_desc=(
            "Autonomously builds copies of itself and other structures.",
            "Requires the Self-Replication tech to unlock.",
            "Dramatically accelerates large-scale construction.",
        ),
        actions=[
            "Research Self-Replication in the Tech Tree first",
            "Provide ample mineral reserves for replication runs",
        ],
        build_cost=BUILD_COSTS.get("replicator", {}),
        energy_draw=ENERGY_CONSUMPTION.get("replicator", 0.0),
        required_tech="self_replication",
        tips=[
            "Exponential growth — a few Replicators go a long way",
            "Keep energy surplus high; they draw 60 / yr each",
        ],
    )

    d["shipyard"] = _GuideEntry(
        name="Shipyard",
        category="structure",
        full_desc=(
            "Constructs and launches all classes of spacecraft.",
            "Build queues are managed in the Queue overlay.",
            "Only one ship is built at a time per Shipyard.",
        ),
        actions=[
            "Open Queue overlay (QUEUE button) to order ships",
            "Ensure sufficient minerals for chosen ship class",
        ],
        build_cost=BUILD_COSTS.get("shipyard", {}),
        energy_draw=ENERGY_CONSUMPTION.get("shipyard", 0.0),
        tips=[
            "Build a Shipyard early — Probes open new systems",
            "Multiple Shipyards can build in parallel",
        ],
    )

    d["storage_hub"] = _GuideEntry(
        name="Storage Hub",
        category="structure",
        full_desc=(
            "Provides on-site resource storage for a body.",
            "Prevents production from stalling when reserves fill.",
            "Logistic Bots can use hubs as transfer waypoints.",
        ),
        actions=[
            "Build near high-output Extractors",
            "Assign Logistic Bots to move stock between hubs",
        ],
        build_cost=BUILD_COSTS.get("storage_hub", {}),
        energy_draw=ENERGY_CONSUMPTION.get("storage_hub", 0.0),
        tips=[
            "Always build at least one hub per active colony",
            "Full hubs block further production — size appropriately",
        ],
    )

    # --- Bots ---

    d["miner"] = _GuideEntry(
        name="Miner Bot",
        category="bot",
        full_desc=(
            "Extracts minerals, ice and gas from surface deposits.",
            "Operates autonomously once assigned a task.",
            "Output scales with the number of bots on task.",
        ),
        actions=[
            "Click the row to open entity detail view",
            "Adjust task allocation slider to set bot count",
        ],
        build_cost=BUILD_COSTS.get("miner", {}),
        energy_draw=ENERGY_CONSUMPTION.get("miner", 0.0),
        tips=[
            "More bots = faster extraction; diminishing returns above ~10",
            "Pair with Extractors for maximum yield",
        ],
    )

    d["constructor"] = _GuideEntry(
        name="Constructor Bot",
        category="bot",
        full_desc=(
            "Builds structures and other entities on command.",
            "Each active Constructor works one build task at a time.",
            "Drop Ships arrive as one Constructor + one Miner.",
        ),
        actions=[
            "Click the row to open entity detail view",
            "Assign build tasks via the task allocation slider",
        ],
        build_cost=BUILD_COSTS.get("constructor", {}),
        energy_draw=ENERGY_CONSUMPTION.get("constructor", 0.0),
        tips=[
            "Always keep at least one Constructor on standby",
            "Multiple Constructors share a build queue in parallel",
        ],
    )

    d["logistic_bot"] = _GuideEntry(
        name="Logistic Bot",
        category="bot",
        full_desc=(
            "Automates resource transfers between bodies.",
            "Prioritises routes with the highest imbalance.",
            "Requires Storage Hubs at both endpoints.",
        ),
        actions=[
            "Assign to logistic tasks via the task panel",
            "Check the Energy overlay to monitor transfer activity",
        ],
        build_cost=BUILD_COSTS.get("logistic_bot", {}),
        energy_draw=ENERGY_CONSUMPTION.get("logistic_bot", 0.0),
        tips=[
            "Essential for balancing resource flow in a large colony",
            "More bots = faster transfer throughput",
        ],
    )

    d["harvester"] = _GuideEntry(
        name="Harvester Bot",
        category="bot",
        full_desc=(
            "Cultivates and harvests biological resources.",
            "Feeds the Bio Plant and bios-based research.",
            "Only useful on bodies with active bios populations.",
        ),
        actions=[
            "Assign to harvest tasks via the task panel",
            "Pair with Bio Plants to maintain fuel supply",
        ],
        build_cost=BUILD_COSTS.get("harvester", {}),
        energy_draw=ENERGY_CONSUMPTION.get("harvester", 0.0),
        tips=[
            "Over-harvesting damages bio populations; use moderation",
            "Uplifted bios are more productive but more dangerous",
        ],
    )

    # --- Ships ---

    d["probe"] = _GuideEntry(
        name="Probe",
        category="ship",
        full_desc=(
            "Scout vessel that reveals unexplored star systems.",
            "A system must be visited by a Probe before its",
            "details and resources become visible.",
        ),
        actions=[
            "Select the Probe in the entities panel",
            "Choose a target system in the galaxy view",
            "Probe travels automatically; system unlocks on arrival",
        ],
        build_cost=BUILD_COSTS.get("probe", {}),
        energy_draw=0.0,
        tips=[
            "Always launch a Probe toward promising nearby systems",
            "Probe cost is low — build several in parallel",
        ],
    )

    d["drop_ship"] = _GuideEntry(
        name="Drop Ship",
        category="ship",
        full_desc=(
            "Delivers a Constructor Bot and Miner Bot to any body.",
            "On arrival the ship is consumed and both bots",
            "are added to the destination body's roster.",
        ),
        actions=[
            "Queue a Drop Ship in the Shipyard",
            "Set the destination before launch",
        ],
        build_cost=BUILD_COSTS.get("drop_ship", {}),
        energy_draw=0.0,
        tips=[
            "Use Drop Ships to bootstrap a new colony quickly",
            "The two bots it delivers are ready to work immediately",
        ],
    )

    d["mining_vessel"] = _GuideEntry(
        name="Mining Vessel",
        category="ship",
        full_desc=(
            "Heavy-duty ship that extracts resources from",
            "remote bodies and transfers them back to base.",
            "Operates independently once a route is set.",
        ),
        actions=[
            "Assign a source body and destination body",
            "Ship operates its route automatically",
        ],
        build_cost=BUILD_COSTS.get("mining_vessel", {}),
        energy_draw=0.0,
        tips=[
            "Ideal for rich asteroid or comet deposits",
            "More vessels on a route increases transfer rate",
        ],
    )

    d["transport"] = _GuideEntry(
        name="Transport",
        category="ship",
        full_desc=(
            "Cargo vessel for moving resources between star systems.",
            "Faster and higher capacity than Mining Vessels.",
            "Essential for inter-system supply chains.",
        ),
        actions=[
            "Set source and destination systems for the route",
            "Monitor cargo in the Ledger overlay",
        ],
        build_cost=BUILD_COSTS.get("transport", {}),
        energy_draw=0.0,
        tips=[
            "Bulk up Trade routes with multiple Transports",
            "Combine with Storage Hubs at both ends",
        ],
    )

    d["warship"] = _GuideEntry(
        name="Warship",
        category="ship",
        full_desc=(
            "Combat vessel designed for hostile encounters.",
            "Patrols assigned systems and engages hostile entities.",
            "Requires Atomic Warships tech to unlock.",
        ),
        actions=[
            "Research Atomic Warships in the Tech Tree",
            "Assign patrol orders via the entity detail panel",
        ],
        build_cost=BUILD_COSTS.get("warship", {}),
        energy_draw=0.0,
        required_tech="atomic_warships",
        tips=[
            "Uplifted bio populations can damage undefended colonies",
            "Station Warships near valuable contested systems",
        ],
    )

    return d


_GUIDE_DATA = _build_guide_data()

# Ordered keys for sidebar navigation
_STRUCTURE_KEYS = [
    "extractor", "factory",
    "power_plant_solar", "power_plant_wind", "power_plant_bios",
    "power_plant_fossil", "power_plant_nuclear",
    "power_plant_cold_fusion", "power_plant_dark_matter",
    "research_array", "replicator", "shipyard", "storage_hub",
]
_BOT_KEYS  = ["miner", "constructor", "logistic_bot", "harvester"]
_SHIP_KEYS = ["probe", "drop_ship", "mining_vessel", "transport", "warship"]
_ALL_KEYS  = _STRUCTURE_KEYS + _BOT_KEYS + _SHIP_KEYS

_SIDEBAR_W   = 220
_SB_ROW_H    = 22
_SB_CAT_H    = 26
_CONTENT_PAD = 14
_LINE_H      = 20
_SECTION_GAP = 12

_TECH_NAMES: dict[str, str] = {
    "cold_fusion":      "Cold Fusion",
    "dark_matter":      "Dark Matter",
    "self_replication": "Self-Replication",
    "atomic_warships":  "Atomic Warships",
}


# ---------------------------------------------------------------------------
# HelpView
# ---------------------------------------------------------------------------

class HelpView:
    """Full-window help / entity guide overlay."""

    def __init__(self, app) -> None:
        self.app       = app
        self.is_active = False

        self._rect = pygame.Rect(0, TASKBAR_H, WINDOW_WIDTH, WINDOW_HEIGHT - TASKBAR_H)

        self._close_btn = Button(
            (self._rect.right - 100, self._rect.y + 8, 90, 26),
            "\u2715  CLOSE",
            callback=self._close,
            font_size=11,
        )

        self._selected:      str = _ALL_KEYS[0]
        self._scroll_y:      int = 0
        self._sidebar_scroll: int = 0
        self._content_h:     int = 0
        self._sb_h:          int = 0

        # Hit-rects for sidebar rows: (rect, type_val)
        self._sb_rects: list[tuple[pygame.Rect, str]] = []

        # Rects for sidebar and content panes
        _content_x = self._rect.x + _SIDEBAR_W + 1
        _content_y = self._rect.y + HEADER_H
        self._sidebar_rect = pygame.Rect(
            self._rect.x, _content_y, _SIDEBAR_W, self._rect.height - HEADER_H
        )
        self._content_rect = pygame.Rect(
            _content_x, _content_y,
            self._rect.width - _SIDEBAR_W - 1, self._rect.height - HEADER_H,
        )

    # ------------------------------------------------------------------
    # Activation

    def activate(self, entity_type: str | None = None) -> None:
        self.is_active       = True
        self._just_opened    = True
        self._selected       = entity_type if entity_type in _GUIDE_DATA else _ALL_KEYS[0]
        self._scroll_y       = 0
        self._sidebar_scroll = 0

    def deactivate(self) -> None:
        self.is_active = False

    def _close(self) -> None:
        self.deactivate()

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._close_btn.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self._close()
                return

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Ignore the click that opened this overlay (same-frame dismiss guard)
                if self._just_opened:
                    self._just_opened = False
                    continue
                # Outside overlay → close
                if not self._rect.collidepoint(event.pos):
                    self._close()
                    return
                # Sidebar entry click
                for rect, type_val in self._sb_rects:
                    if rect.collidepoint(event.pos):
                        self._selected    = type_val
                        self._scroll_y    = 0
                        break

            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self._sidebar_rect.collidepoint((mx, my)):
                    visible_h   = self._sidebar_rect.height
                    max_scroll  = max(0, self._sb_h - visible_h)
                    self._sidebar_scroll = max(0, min(max_scroll,
                                               self._sidebar_scroll - event.y * _SB_ROW_H))
                elif self._content_rect.collidepoint((mx, my)):
                    visible_h   = self._content_rect.height
                    max_scroll  = max(0, self._content_h - visible_h)
                    self._scroll_y = max(0, min(max_scroll,
                                        self._scroll_y - event.y * _LINE_H))

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._close()
                    return
                # Left/right arrow — cycle entries
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    idx = _ALL_KEYS.index(self._selected) if self._selected in _ALL_KEYS else 0
                    if event.key == pygame.K_LEFT:
                        idx = (idx - 1) % len(_ALL_KEYS)
                    else:
                        idx = (idx + 1) % len(_ALL_KEYS)
                    self._selected    = _ALL_KEYS[idx]
                    self._scroll_y    = 0

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        # Background
        pygame.draw.rect(surface, C_BG, self._rect)
        pygame.draw.rect(surface, C_BORDER, self._rect, width=1)

        # Header bar
        hdr_r = pygame.Rect(self._rect.x, self._rect.y, self._rect.width, HEADER_H)
        pygame.draw.rect(surface, C_HEADER, hdr_r)
        hdr_s = font(14, bold=True).render("? HELP GUIDE", True, C_ACCENT)
        surface.blit(hdr_s, (self._rect.x + PADDING, self._rect.y + 5))
        self._close_btn.draw(surface)

        # Vertical divider between sidebar and content
        pygame.draw.line(
            surface, C_SEP,
            (self._rect.x + _SIDEBAR_W, self._rect.y + HEADER_H),
            (self._rect.x + _SIDEBAR_W, self._rect.bottom),
        )

        self._draw_sidebar(surface)
        self._draw_content(surface)

    def _draw_sidebar(self, surface: pygame.Surface) -> None:
        sr = self._sidebar_rect
        old_clip = surface.get_clip()
        surface.set_clip(sr)

        self._sb_rects = []
        ty = sr.y - self._sidebar_scroll

        sections = [
            ("STRUCTURES", _STRUCTURE_KEYS, C_ACCENT),
            ("BOTS",       _BOT_KEYS,       (100, 220, 150)),
            ("SHIPS",      _SHIP_KEYS,       (120, 190, 255)),
        ]

        for sec_label, keys, sec_col in sections:
            # Category header
            if _SB_CAT_H + ty > sr.y:
                hdr_r = pygame.Rect(sr.x, ty, sr.width, _SB_CAT_H)
                pygame.draw.rect(surface, C_PANEL, hdr_r)
                s = font(11, bold=True).render(sec_label, True, sec_col)
                surface.blit(s, (sr.x + PADDING, ty + (_SB_CAT_H - s.get_height()) // 2))
            ty += _SB_CAT_H

            for key in keys:
                entry = _GUIDE_DATA.get(key)
                if entry is None:
                    ty += _SB_ROW_H
                    continue
                row_r = pygame.Rect(sr.x, ty, sr.width, _SB_ROW_H)
                # Register hit rect with unclipped position for click detection
                self._sb_rects.append((row_r, key))

                if ty + _SB_ROW_H > sr.y and ty < sr.bottom:
                    selected = (key == self._selected)
                    if selected:
                        pygame.draw.rect(surface, C_HOVER, row_r)
                    name_col = C_SELECTED if selected else C_TEXT
                    s = font(11, bold=selected).render(entry.name, True, name_col)
                    surface.blit(s, (sr.x + PADDING + 8, ty + (_SB_ROW_H - s.get_height()) // 2))
                ty += _SB_ROW_H

        self._sb_h = ty + self._sidebar_scroll - sr.y

        # Scrollbar for sidebar
        visible_h = sr.height
        if self._sb_h > visible_h:
            bar_h   = max(20, int(visible_h * visible_h / self._sb_h))
            max_sc  = self._sb_h - visible_h
            bar_y   = sr.y + int((visible_h - bar_h) * self._sidebar_scroll / max_sc)
            pygame.draw.rect(surface, C_SCROLLBAR,
                             pygame.Rect(sr.right - 5, bar_y, 4, bar_h),
                             border_radius=2)

        surface.set_clip(old_clip)

    def _draw_content(self, surface: pygame.Surface) -> None:
        cr = self._content_rect
        old_clip = surface.get_clip()
        surface.set_clip(cr)

        entry = _GUIDE_DATA.get(self._selected)
        if entry is None:
            surface.set_clip(old_clip)
            return

        tx = cr.x + _CONTENT_PAD
        ty = cr.y + _CONTENT_PAD - self._scroll_y
        total_h = _CONTENT_PAD

        def line(text: str, color: tuple, fsize: int = 12, bold: bool = False,
                 indent: int = 0) -> None:
            nonlocal ty, total_h
            if text:
                s = font(fsize, bold=bold).render(text, True, color)
                surface.blit(s, (tx + indent, ty))
            ty     += _LINE_H
            total_h += _LINE_H

        def gap(extra: int = _SECTION_GAP) -> None:
            nonlocal ty, total_h
            ty     += extra
            total_h += extra

        def section_header(text: str) -> None:
            nonlocal ty, total_h
            gap(4)
            line(text, C_TEXT_DIM, fsize=11, bold=True)
            # Underline
            uw = cr.width - _CONTENT_PAD * 2 - 10
            pygame.draw.line(surface, C_SEP, (tx, ty - 2), (tx + uw, ty - 2))
            total_h += 2

        # Entity name
        gap(4)
        line(entry.name, C_ACCENT, fsize=16, bold=True)
        gap(4)

        # Description
        for desc_line in entry.full_desc:
            if desc_line:
                line(desc_line, C_TEXT, fsize=12)

        # What you can do
        if entry.actions:
            section_header("WHAT YOU CAN DO")
            for action in entry.actions:
                line(f"\u00b7 {action}", C_TEXT, fsize=11, indent=8)

        # Build cost
        if entry.build_cost:
            section_header("BUILD COST")
            _NAMES = {"minerals": "Minerals", "rare_minerals": "Rare Minerals",
                      "ice": "Ice", "gas": "Gas", "electronics": "Electronics"}
            for res, amt in entry.build_cost.items():
                line(f"{_NAMES.get(res, res):20s}  {int(amt)}", C_TEXT_DIM, fsize=11, indent=8)

        # Energy draw
        if entry.energy_draw > 0:
            section_header("ENERGY DRAW")
            line(f"\u2212{entry.energy_draw:.0f} energy-units / yr", C_WARN, fsize=11, indent=8)

        # Required tech
        if entry.required_tech:
            section_header("REQUIRED TECH")
            tech_name = _TECH_NAMES.get(entry.required_tech, entry.required_tech)
            line(f"Requires: {tech_name}", C_ACCENT, fsize=11, indent=8)
            line("Open TECH TREE to research this node.", C_TEXT_DIM, fsize=11, indent=8)

        # Tips
        if entry.tips:
            valid_tips = [t for t in entry.tips if t]
            if valid_tips:
                section_header("TIPS")
                for tip in valid_tips:
                    line(f"\u2605 {tip}", C_TEXT_DIM, fsize=11, indent=8)

        gap(16)

        self._content_h = total_h

        surface.set_clip(old_clip)

        # Scrollbar for content
        visible_h = cr.height
        if self._content_h > visible_h:
            bar_h  = max(20, int(visible_h * visible_h / self._content_h))
            max_sc = self._content_h - visible_h
            bar_y  = cr.y + int((visible_h - bar_h) * self._scroll_y / max_sc)
            pygame.draw.rect(surface, C_SCROLLBAR,
                             pygame.Rect(cr.right - 5, bar_y, 4, bar_h),
                             border_radius=2)
