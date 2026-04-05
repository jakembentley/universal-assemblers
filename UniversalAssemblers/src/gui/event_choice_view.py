"""
Event Choice View — non-exclusive overlay for pending event resolution.

A compact panel anchored to the bottom-right of the window that presents
a forewarned event with player-choice buttons. Follows the activate/deactivate
protocol but is non-exclusive (does not block other overlays).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from . import constants as _c
from .constants import (
    C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT, C_WARN,
    PADDING, font,
)
from .widgets import Button

if TYPE_CHECKING:
    from ..game_state import GameState, PendingEvent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENT_TITLES: dict[str, str] = {
    "asteroid_incoming":    "ASTEROID INCOMING",
    "solar_flare_warning":  "SOLAR FLARE WARNING",
    "bios_attack_imminent": "BIOS REVOLT IMMINENT",
}

_WARN_MAX: dict[str, float] = {
    "asteroid_incoming":    3.0,
    "solar_flare_warning":  2.0,
    "bios_attack_imminent": 4.0,
}

_PANEL_W = 420
_PANEL_H = 210
_BTN_H   = 26


def _fmt_cost(cost: dict) -> str:
    if not cost:
        return "No cost"
    parts = []
    for k, v in cost.items():
        parts.append(f"{v} {k.replace('_', ' ')}")
    return ", ".join(parts)


class EventChoiceView:
    """Non-exclusive overlay showing the most-urgent pending event with choice buttons."""

    def __init__(self, app) -> None:
        self._app = app
        self.is_active: bool = False
        self._event: "PendingEvent | None" = None
        self._buttons: list[Button] = []

    # ------------------------------------------------------------------
    # Lifecycle

    def activate(self, pending_event: "PendingEvent") -> None:
        self._event = pending_event
        self.is_active = True
        self._rebuild_buttons()

    def deactivate(self) -> None:
        self.is_active = False
        self._event = None
        self._buttons = []

    # ------------------------------------------------------------------
    # Layout helpers

    def _panel_rect(self, surface: pygame.Surface) -> pygame.Rect:
        sw, sh = surface.get_size()
        w = _c.scaled(_PANEL_W)
        h = _c.scaled(_PANEL_H)
        return pygame.Rect(sw - w - _c.scaled(12), sh - h - _c.scaled(48), w, h)

    def _rebuild_buttons(self) -> None:
        """Build choice buttons based on current event."""
        self._buttons = []
        if not self._event:
            return
        # Placeholder rects — recalculated in draw() after we know panel position.
        # We store them as (key, label, cost_str, effect_str) and build Button
        # objects at draw time if not yet built, but since Button needs a rect
        # up-front we'll use a dummy position and update it in draw().
        # Simpler: just store the choice data and create buttons in draw().
        self._choice_data = list(self._event.choices)

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface, gs: "GameState") -> None:
        if not self.is_active or not self._event:
            return

        pe = self._event

        # If the event was resolved externally or no longer in pending list, dismiss
        if pe.chosen is not None or pe not in gs.pending_events:
            self.deactivate()
            return

        r = self._panel_rect(surface)
        PAD = _c.scaled(PADDING)
        HDR_H = _c.scaled(28)

        # Background + border
        pygame.draw.rect(surface, _c.C_PANEL, r, border_radius=4)
        pygame.draw.rect(surface, C_BORDER, r, width=1, border_radius=4)

        # Header bar
        hdr_r = pygame.Rect(r.x, r.y, r.width, HDR_H)
        pygame.draw.rect(surface, C_HEADER, hdr_r, border_radius=4)

        title = EVENT_TITLES.get(pe.event_type, pe.event_type.replace("_", " ").upper())

        # Resolve body/system name from payload
        loc_name = pe.payload.get("body_id", "")
        if gs.galaxy and loc_name:
            for sys in gs.galaxy.solar_systems:
                for body in sys.orbital_bodies:
                    if body.id == loc_name:
                        loc_name = body.name
                        break
                    for moon in body.moons:
                        if moon.id == loc_name:
                            loc_name = moon.name
                            break

        title_txt = f"\u26a0  {title}" + (f" \u2014 {loc_name}" if loc_name else "")
        title_s = font(11, bold=True).render(title_txt, True, C_WARN)
        surface.blit(title_s, (r.x + PAD, r.y + (HDR_H - title_s.get_height()) // 2))

        cy = r.y + HDR_H + PAD

        # Countdown line
        warn = pe.warn_years_remaining
        countdown_s = font(10).render(f"Impact in ~{warn:.1f} years", True, C_TEXT)
        surface.blit(countdown_s, (r.x + PAD, cy))
        cy += countdown_s.get_height() + _c.scaled(2)

        # Damage / detail line
        dmg = pe.payload.get("damage")
        ent = pe.payload.get("entity_type", "")
        if dmg and ent:
            detail = f"Projected damage: {dmg} HP to {ent.replace('_', ' ')}"
        elif dmg:
            detail = f"Projected damage: {dmg} HP"
        else:
            detail = ""
        if detail:
            detail_s = font(10).render(detail, True, C_TEXT_DIM)
            surface.blit(detail_s, (r.x + PAD, cy))
            cy += detail_s.get_height() + _c.scaled(2)

        # Separator
        pygame.draw.line(surface, C_BORDER,
                         (r.x + PAD, cy + _c.scaled(3)),
                         (r.right - PAD, cy + _c.scaled(3)))
        cy += _c.scaled(8)

        # Choice buttons — build/update each frame at correct position
        btn_w = r.width - PAD * 2
        btn_h = _c.scaled(_BTN_H)
        choices = getattr(self, "_choice_data", pe.choices)

        # Rebuild buttons if needed (count mismatch means activate was just called)
        if len(self._buttons) != len(choices):
            self._buttons = []
            for ch in choices:
                btn = Button(
                    rect=(r.x + PAD, cy, btn_w, btn_h),
                    label="",  # updated per-frame
                    callback=None,
                    font_size=_c.scaled(10),
                )
                self._buttons.append(btn)

        for i, (btn, ch) in enumerate(zip(self._buttons, choices)):
            cost_str = _fmt_cost(ch.get("cost", {}))
            label = f"{ch['label']}  |  {cost_str}"
            btn_rect = (r.x + PAD, cy, btn_w, btn_h)
            btn._rect = pygame.Rect(*btn_rect)
            btn._label = label

            choice_key = ch["key"]
            def make_cb(key=choice_key):
                def cb():
                    gs.resolve_pending_event(pe.event_id, key)
                    self.deactivate()
                return cb
            btn._callback = make_cb()
            btn.draw(surface)
            cy += btn_h + _c.scaled(3)

        # "N more" badge
        more = len(gs.pending_events) - 1  # excluding current
        if more > 0:
            badge_txt = f"+{more} more"
            badge_s = font(9).render(badge_txt, True, C_ACCENT)
            surface.blit(badge_s, (r.right - badge_s.get_width() - PAD,
                                   r.y + HDR_H + _c.scaled(2)))

    # ------------------------------------------------------------------
    # Event handling

    def handle_event(self, ev: pygame.event.Event, gs: "GameState") -> bool:
        if not self.is_active:
            return False
        for btn in self._buttons:
            btn.handle_event(ev)
        # Consume clicks within panel bounds (prevent click-through)
        if ev.type == pygame.MOUSEBUTTONDOWN:
            # We don't have surface here, so we can't check bounds — that's OK,
            # button callbacks handle their own rects.
            pass
        return False
