"""
Tech tree browser overlay.

Covers the full window (below the taskbar) and shows all 13 tech nodes
grouped by branch.  Each node shows:
  - Name, description, prerequisites
  - Status: LOCKED / AVAILABLE / IN PROGRESS (with progress bar) / RESEARCHED
  - [Research] button if available and not already in progress

Activated by pressing T or clicking the TECH TREE button in the taskbar.
"""
from __future__ import annotations

import pygame
from .constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TASKBAR_H, HEADER_H, ROW_H, PADDING,
    C_BG, C_PANEL, C_BORDER, C_HEADER, C_TEXT, C_TEXT_DIM, C_ACCENT,
    C_SELECTED, C_HOVER, C_WARN, C_SEP, C_BTN, C_BTN_HOV, C_BTN_TXT,
    font,
)
from .widgets import draw_panel, draw_separator, Button
from ..models.tech import TECH_TREE, TechNode


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

_BRANCH_ORDER = ["construction", "energy", "military", "propulsion", "special"]
_BRANCH_COLORS: dict[str, tuple] = {
    "construction": (100, 200, 255),
    "energy":       (255, 210, 80),
    "military":     (255, 100, 100),
    "propulsion":   (180, 255, 180),
    "special":      (220, 140, 255),
}

# Node card dimensions
_CARD_W = 230
_CARD_H = 110
_CARD_GAP = 12
_COL_X_START = PADDING + 60   # first column x


class TechView:

    def __init__(self, app) -> None:
        self.app       = app
        self.is_active = False

        self._rect = pygame.Rect(0, TASKBAR_H, WINDOW_WIDTH, WINDOW_HEIGHT - TASKBAR_H)

        self._close_btn = Button(
            (self._rect.right - 100, self._rect.y + 8, 90, 26),
            "✕  CLOSE",
            callback=self._close,
            font_size=11,
        )

        # Scroll offset (pixels from top of content)
        self._scroll_y: int = 0
        self._content_h: int = 0          # computed during draw
        self._max_scroll: int = 0

        # Hit rects for "Research" buttons: (rect, tech_id)
        self._research_btns: list[tuple[pygame.Rect, str]] = []

        # Hover state
        self._hovered_tech: str | None = None

    # ------------------------------------------------------------------

    def activate(self) -> None:
        self.is_active = True
        self._scroll_y = 0

    def deactivate(self) -> None:
        self.is_active = False

    def _close(self) -> None:
        self.deactivate()

    # ------------------------------------------------------------------
    # Events

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        mouse_pos = pygame.mouse.get_pos()
        self._hovered_tech = None
        for event in events:
            self._close_btn.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self._close()
                return

            if event.type == pygame.MOUSEWHEEL:
                self._scroll_y = max(0, min(self._max_scroll,
                                            self._scroll_y - event.y * 30))

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, tech_id in self._research_btns:
                    if rect.collidepoint(event.pos):
                        self._start_research(tech_id)
                        return

    def _start_research(self, tech_id: str) -> None:
        gs = self.app.game_state
        if not gs:
            return
        gs.tech.start_research(tech_id)

    # ------------------------------------------------------------------
    # Draw

    def draw(self, surface: pygame.Surface) -> None:
        self._research_btns = []

        # Semi-transparent overlay background
        bg = pygame.Surface((self._rect.width, self._rect.height), pygame.SRCALPHA)
        bg.fill((5, 8, 20, 235))
        surface.blit(bg, self._rect.topleft)
        pygame.draw.rect(surface, C_BORDER, self._rect, width=1)

        # Header bar
        hdr_r = pygame.Rect(self._rect.x, self._rect.y, self._rect.width, HEADER_H + 4)
        pygame.draw.rect(surface, C_HEADER, hdr_r)
        t = font(14, bold=True).render("TECHNOLOGY TREE", True, C_ACCENT)
        surface.blit(t, (self._rect.x + PADDING, self._rect.y + 7))
        self._close_btn.draw(surface)

        gs = self.app.game_state
        if not gs:
            nm = font(13).render("No game in progress.", True, C_TEXT_DIM)
            surface.blit(nm, (self._rect.x + PADDING, self._rect.y + HEADER_H + 20))
            return

        # Research summary line
        researched_count = len(gs.tech.researched)
        total_count      = len(TECH_TREE)
        in_prog          = gs.tech.in_progress_ids()
        array_count      = gs.entity_roster.total("structure", "research_array")
        sum_s = font(12).render(
            f"Researched: {researched_count}/{total_count}   "
            f"In progress: {len(in_prog)}   "
            f"Research Arrays: {array_count}",
            True, C_TEXT_DIM,
        )
        surface.blit(sum_s, (self._rect.x + PADDING, self._rect.y + HEADER_H + 8))

        content_y_start = self._rect.y + HEADER_H + 30

        # Clip content area (scrollable)
        clip_rect = pygame.Rect(
            self._rect.x, content_y_start,
            self._rect.width, self._rect.height - HEADER_H - 30,
        )
        old_clip = surface.get_clip()
        surface.set_clip(clip_rect)

        self._draw_tech_cards(surface, gs, content_y_start - self._scroll_y)

        surface.set_clip(old_clip)

        # Scrollbar
        if self._max_scroll > 0:
            sb_x    = self._rect.right - 8
            sb_h    = clip_rect.height
            thumb_h = max(30, int(sb_h * clip_rect.height / (self._content_h + 1)))
            thumb_y = content_y_start + int(
                (sb_h - thumb_h) * self._scroll_y / max(1, self._max_scroll)
            )
            pygame.draw.rect(surface, (40, 70, 120),
                             pygame.Rect(sb_x, content_y_start, 6, sb_h), border_radius=3)
            pygame.draw.rect(surface, C_ACCENT,
                             pygame.Rect(sb_x, thumb_y, 6, thumb_h), border_radius=3)

    def _draw_tech_cards(
        self, surface: pygame.Surface, gs, base_y: int
    ) -> None:
        """Lay out tech cards in branch columns."""
        branches = {b: [] for b in _BRANCH_ORDER}
        for tech_id, node in TECH_TREE.items():
            branch = node.branch if node.branch in branches else "special"
            branches[branch].append((tech_id, node))

        num_cols    = len(_BRANCH_ORDER)
        col_w       = (self._rect.width - PADDING * 2) // num_cols
        max_col_h   = 0

        for ci, branch in enumerate(_BRANCH_ORDER):
            col_x   = self._rect.x + PADDING + ci * col_w
            card_y  = base_y + 10

            # Branch header
            bh_s = font(11, bold=True).render(branch.upper(), True,
                                              _BRANCH_COLORS.get(branch, C_ACCENT))
            surface.blit(bh_s, (col_x + (_CARD_W - bh_s.get_width()) // 2, card_y))
            card_y += 22

            for tech_id, node in sorted(branches[branch],
                                        key=lambda x: len(x[1].prerequisites)):
                card_y = self._draw_card(surface, gs, tech_id, node,
                                         col_x, card_y, _CARD_W)
                card_y += _CARD_GAP

            col_h = card_y - base_y
            if col_h > max_col_h:
                max_col_h = col_h

        self._content_h = max_col_h
        visible_h       = self._rect.height - HEADER_H - 30
        self._max_scroll = max(0, self._content_h - visible_h)

    def _draw_card(
        self,
        surface: pygame.Surface,
        gs,
        tech_id: str,
        node: TechNode,
        cx: int,
        cy: int,
        w: int,
    ) -> int:
        """Draw one tech node card; returns the y below it."""
        # Determine status
        is_researched  = gs.tech.is_researched(tech_id)
        is_in_progress = tech_id in gs.tech.in_progress_ids()
        can_research   = gs.tech.can_research(tech_id)

        if is_researched:
            border_col = (80, 200, 100)
            bg_col     = (12, 35, 18)
            status_txt = "RESEARCHED"
            status_col = (80, 200, 100)
        elif is_in_progress:
            border_col = C_WARN
            bg_col     = (35, 28, 12)
            status_txt = "IN PROGRESS"
            status_col = C_WARN
        elif can_research:
            border_col = C_ACCENT
            bg_col     = (12, 20, 40)
            status_txt = "AVAILABLE"
            status_col = C_ACCENT
        else:
            border_col = (35, 45, 70)
            bg_col     = (10, 12, 22)
            status_txt = "LOCKED"
            status_col = C_TEXT_DIM

        card_r = pygame.Rect(cx, cy, w, _CARD_H)
        pygame.draw.rect(surface, bg_col,     card_r, border_radius=5)
        pygame.draw.rect(surface, border_col, card_r, width=1, border_radius=5)

        tx = cx + 8
        ty = cy + 6

        # Node name
        name_s = font(12, bold=True).render(node.name, True, C_TEXT)
        surface.blit(name_s, (tx, ty))
        ty += 17

        # Status badge
        st_s = font(10, bold=True).render(status_txt, True, status_col)
        surface.blit(st_s, (tx, ty))
        ty += 14

        # Description (truncated to fit)
        desc = node.description
        max_chars = (w - 16) // 6
        if len(desc) > max_chars:
            desc = desc[:max_chars - 1] + "…"
        desc_s = font(10).render(desc, True, C_TEXT_DIM)
        surface.blit(desc_s, (tx, ty))
        ty += 14

        # Prerequisites
        if node.prerequisites:
            prereqs = ", ".join(
                TECH_TREE[p].name if p in TECH_TREE else p
                for p in node.prerequisites
            )
            pr_text = f"Req: {prereqs}"
            if len(pr_text) > max_chars:
                pr_text = pr_text[:max_chars - 1] + "…"
            pr_s = font(10).render(pr_text, True, (120, 120, 160))
            surface.blit(pr_s, (tx, ty))
        ty += 13

        # Progress bar (in-progress or researched)
        if is_in_progress:
            frac = gs.tech.progress_fraction(tech_id)
            pbar_w = w - 16
            pygame.draw.rect(surface, (30, 50, 80),
                             pygame.Rect(tx, ty, pbar_w, 6), border_radius=3)
            pygame.draw.rect(surface, C_WARN,
                             pygame.Rect(tx, ty, int(pbar_w * frac), 6), border_radius=3)
            pct_s = font(10).render(f"{frac:.0%}", True, C_WARN)
            surface.blit(pct_s, (tx + pbar_w - pct_s.get_width(), ty - 14))
            ty += 10
        elif is_researched:
            frac_bar_w = w - 16
            pygame.draw.rect(surface, (80, 200, 100),
                             pygame.Rect(tx, ty, frac_bar_w, 4), border_radius=2)
            ty += 8

        # Research button (available and not yet started)
        if can_research and not is_in_progress:
            btn_r = pygame.Rect(cx + w - 88, cy + _CARD_H - 26, 80, 20)
            pygame.draw.rect(surface, C_BTN_HOV, btn_r, border_radius=3)
            btn_s = font(10, bold=True).render("RESEARCH", True, C_BTN_TXT)
            surface.blit(btn_s, btn_s.get_rect(center=btn_r.center))
            self._research_btns.append((btn_r, tech_id))

        return cy + _CARD_H
