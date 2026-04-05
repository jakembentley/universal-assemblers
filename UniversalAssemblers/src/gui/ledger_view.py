"""Ledger View — scrollable log of entity actions and random events.

Accessible via the LEDGER button in the taskbar.
Filter by category: ALL / ENTITY ACTIONS / RANDOM EVENTS.
Right-click or ESC to close.
"""
from __future__ import annotations

import pygame
from . import constants as _c
from .constants import (
    C_BG, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_BTN, C_BTN_TXT,
)
from .widgets import Button
from ..models.ledger import CATEGORY_ENTITY, CATEGORY_RANDOM

_BADGE_COLOR_ENTITY = (60, 160, 255)
_BADGE_COLOR_RANDOM = (160, 60, 200)
_ROW_BG_A = (10, 18, 40)
_ROW_BG_B = (14, 24, 52)

_FILTER_TABS: list[tuple[str, str | None]] = [
    ("ALL", None),
    ("ENTITY ACTIONS", CATEGORY_ENTITY),
    ("RANDOM EVENTS",  CATEGORY_RANDOM),
]


class LedgerView:
    """Full-window game action ledger overlay."""

    def __init__(self, app) -> None:
        self.app       = app
        self.is_active = False

        self._row_h       = _c.scaled(26)
        self._filter_h    = _c.scaled(28)
        self._filter_w    = _c.scaled(150)
        self._timestamp_w = _c.scaled(64)
        self._badge_w     = _c.scaled(38)
        self._scrollbar_w = _c.scaled(6)

        self._rect = pygame.Rect(0, _c.TASKBAR_H, _c.WINDOW_WIDTH, _c.WINDOW_HEIGHT - _c.TASKBAR_H)

        self._close_btn = Button(
            (self._rect.right - _c.scaled(100), self._rect.y + _c.scaled(8),
             _c.scaled(90), _c.scaled(26)),
            "✕  CLOSE",
            callback=self._close,
            font_size=_c.scaled(11),
        )

        self._scroll_y:   int                               = 0
        self._content_h:  int                               = 0
        self._filter:     str | None                        = None  # preserved across opens
        self._filter_btns: list[tuple[pygame.Rect, str | None]] = []

    # ------------------------------------------------------------------
    # Activation

    def activate(self) -> None:
        self.is_active = True
        self._scroll_y = 0     # reset scroll; keep _filter

    def deactivate(self) -> None:
        self.is_active = False

    def _close(self) -> None:
        self.deactivate()

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            self._close_btn.handle_event(event)

            if event.type == pygame.MOUSEWHEEL:
                visible_h  = self._rect.height - _c.HEADER_H - self._filter_h - 16
                max_scroll = max(0, self._content_h - visible_h)
                self._scroll_y = max(0, min(max_scroll,
                                            self._scroll_y - event.y * self._row_h))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for rect, cat in self._filter_btns:
                        if rect.collidepoint(event.pos):
                            self._filter    = cat
                            self._scroll_y  = 0
                            break
                elif event.button == 3:
                    self.deactivate()

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        if not self.is_active:
            return

        # Background + border
        pygame.draw.rect(surface, C_BG, self._rect)
        pygame.draw.rect(surface, C_BORDER, self._rect, width=1)

        # Header bar
        hdr_r = pygame.Rect(self._rect.x, self._rect.y, self._rect.width, _c.HEADER_H)
        pygame.draw.rect(surface, C_HEADER, hdr_r)
        hdr_s = _c.font_scaled(14, bold=True).render("GAME ACTION LEDGER", True, C_ACCENT)
        surface.blit(hdr_s, (self._rect.x + _c.PADDING, self._rect.y + 5))
        self._close_btn.draw(surface)

        # Filter tabs
        self._filter_btns = []
        fx = self._rect.x + _c.PADDING
        fy = self._rect.y + _c.HEADER_H + 4
        for label, cat in _FILTER_TABS:
            tb_r = pygame.Rect(fx, fy, self._filter_w, self._filter_h - 4)
            sel  = self._filter == cat
            pygame.draw.rect(surface, C_ACCENT if sel else C_BTN, tb_r, border_radius=3)
            tb_s = _c.font_scaled(10, bold=True).render(label, True, (0, 0, 0) if sel else C_BTN_TXT)
            surface.blit(tb_s, tb_s.get_rect(center=tb_r.center))
            self._filter_btns.append((tb_r, cat))
            fx += self._filter_w + 6

        # Content clip region
        content_y_start = self._rect.y + _c.HEADER_H + self._filter_h + 8
        content_rect = pygame.Rect(
            self._rect.x, content_y_start,
            self._rect.width, self._rect.height - (content_y_start - self._rect.y),
        )

        old_clip = surface.get_clip()
        surface.set_clip(content_rect)

        gs      = self.app.game_state
        entries = gs.get_ledger(filter_category=self._filter) if gs else []

        if not entries:
            surface.set_clip(old_clip)
            no_s = _c.font_scaled(13).render("No events recorded yet.", True, C_TEXT_DIM)
            surface.blit(no_s, no_s.get_rect(center=(self._rect.centerx,
                                                       content_y_start + 60)))
            return

        cx        = self._rect.x
        row_w     = self._rect.width - self._scrollbar_w - 2
        cy        = content_y_start - self._scroll_y
        total_h   = 0
        msg_x     = cx + _c.PADDING + self._timestamp_w + self._badge_w + 8
        msg_max_w = row_w - _c.PADDING - self._timestamp_w - self._badge_w - 16

        for i, entry in enumerate(entries):
            # Virtual culling — still advance cy
            if cy + self._row_h < content_rect.y:
                cy      += self._row_h
                total_h += self._row_h
                continue
            if cy > content_rect.bottom:
                total_h += self._row_h * (len(entries) - i)
                break

            # Zebra-stripe row background
            row_r = pygame.Rect(cx, cy, row_w, self._row_h)
            pygame.draw.rect(surface, _ROW_BG_A if i % 2 == 0 else _ROW_BG_B, row_r)

            # Timestamp — right-aligned in self._timestamp_w
            ts_s  = _c.font_scaled(9).render(f"Yr {entry.tick_year:.1f}", True, C_TEXT_DIM)
            ts_x  = cx + _c.PADDING + self._timestamp_w - ts_s.get_width()
            surface.blit(ts_s, (ts_x, cy + (self._row_h - ts_s.get_height()) // 2))

            # Category badge pill
            badge_color = _BADGE_COLOR_ENTITY if entry.category == CATEGORY_ENTITY else _BADGE_COLOR_RANDOM
            badge_label = "ENT" if entry.category == CATEGORY_ENTITY else "RND"
            badge_r     = pygame.Rect(
                cx + _c.PADDING + self._timestamp_w + 4, cy + 4,
                self._badge_w - 4, self._row_h - 8,
            )
            pygame.draw.rect(surface, badge_color, badge_r, border_radius=3)
            badge_s = _c.font_scaled(8, bold=True).render(badge_label, True, (255, 255, 255))
            surface.blit(badge_s, badge_s.get_rect(center=badge_r.center))

            # Message text — truncate if too wide
            msg_font = _c.font_scaled(11)
            msg      = entry.message
            msg_s    = msg_font.render(msg, True, entry.color)
            if msg_s.get_width() > msg_max_w:
                # Trim to fit
                while msg and msg_font.size(msg + "…")[0] > msg_max_w:
                    msg = msg[:-1]
                msg   = msg + "…"
                msg_s = msg_font.render(msg, True, entry.color)
            surface.blit(msg_s, (msg_x, cy + (self._row_h - msg_s.get_height()) // 2))

            cy      += self._row_h
            total_h += self._row_h

            # Cause-effect sub-line
            cause_id = getattr(entry, "cause_event_id", None)
            if cause_id and gs:
                cause_entry = next(
                    (e for e in gs._ledger
                     if getattr(e, "event_id", None) == cause_id),
                    None,
                )
                if cause_entry and cy > content_rect.y and cy < content_rect.bottom:
                    dim_col = tuple(max(0, c // 2) for c in cause_entry.color)
                    cause_msg = f"\u21b3 caused by: {cause_entry.message}"
                    cause_s = _c.font_scaled(9).render(cause_msg, True, dim_col)
                    sub_x = msg_x + _c.scaled(12)
                    sub_h = cause_s.get_height() + _c.scaled(2)
                    surface.blit(cause_s, (sub_x, cy))
                    cy      += sub_h
                    total_h += sub_h

        self._content_h = total_h

        # Scrollbar
        visible_h = content_rect.height
        if self._content_h > visible_h:
            sb_x    = self._rect.right - self._scrollbar_w - 2
            thumb_h = max(20, int(visible_h * visible_h / self._content_h))
            max_sc  = max(1, self._content_h - visible_h)
            thumb_y = content_y_start + int((visible_h - thumb_h) * self._scroll_y / max_sc)
            pygame.draw.rect(surface, (30, 50, 80),
                             pygame.Rect(sb_x, content_y_start, self._scrollbar_w, visible_h),
                             border_radius=3)
            pygame.draw.rect(surface, (80, 120, 180),
                             pygame.Rect(sb_x, thumb_y, self._scrollbar_w, thumb_h),
                             border_radius=3)

        surface.set_clip(old_clip)
