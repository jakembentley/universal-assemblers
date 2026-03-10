"""Reusable pygame UI widgets."""
from __future__ import annotations

import pygame
from .constants import (
    C_BORDER, C_BTN, C_BTN_HOV, C_BTN_TXT, C_HEADER, C_HOVER,
    C_PANEL, C_ACCENT, C_TEXT, C_TEXT_DIM, C_SELECTED, C_SEP,
    C_SCROLLBAR, HEADER_H, PADDING, ROW_H, font,
)


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------

class Button:
    def __init__(
        self,
        rect: tuple | pygame.Rect,
        label: str,
        callback=None,
        font_size: int = 16,
        bold: bool = True,
    ) -> None:
        self.rect     = pygame.Rect(rect)
        self.label    = label
        self.callback = callback
        self._font_size = font_size
        self._bold    = bold
        self._hovered = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.callback:
                self.callback()

    def draw(self, surface: pygame.Surface) -> None:
        bg = C_BTN_HOV if self._hovered else C_BTN
        pygame.draw.rect(surface, bg, self.rect, border_radius=5)
        pygame.draw.rect(surface, C_BORDER, self.rect, width=1, border_radius=5)
        label_surf = font(self._font_size, self._bold).render(self.label, True, C_BTN_TXT)
        surface.blit(label_surf, label_surf.get_rect(center=self.rect.center))


# ---------------------------------------------------------------------------
# Panel header helper
# ---------------------------------------------------------------------------

def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    title: str | None = None,
) -> pygame.Rect:
    """Draw a dark panel with optional title bar.  Returns the content rect."""
    pygame.draw.rect(surface, C_PANEL, rect)
    pygame.draw.rect(surface, C_BORDER, rect, width=1)
    if title:
        hdr = pygame.Rect(rect.x, rect.y, rect.width, HEADER_H)
        pygame.draw.rect(surface, C_HEADER, hdr)
        surf = font(12, bold=True).render(title.upper(), True, C_ACCENT)
        surface.blit(surf, (rect.x + PADDING, rect.y + (HEADER_H - surf.get_height()) // 2))
        return pygame.Rect(rect.x + 1, rect.y + HEADER_H, rect.width - 2, rect.height - HEADER_H - 1)
    return pygame.Rect(rect.x + 1, rect.y + 1, rect.width - 2, rect.height - 2)


# ---------------------------------------------------------------------------
# ScrollableList
# ---------------------------------------------------------------------------

class ScrollableList:
    """
    Renders a list of (label, id, color) items in a clipped rect.
    Supports mouse-wheel scrolling and click-to-select.
    color is optional per-item; falls back to C_TEXT_DIM / C_TEXT.
    """

    def __init__(
        self,
        rect: pygame.Rect,
        title: str,
        on_select=None,
    ) -> None:
        self.rect      = rect
        self.title     = title
        self.on_select = on_select

        self._items: list[tuple[str, str, tuple | None]] = []   # (label, id, color)
        self._scroll   = 0
        self._selected_id: str | None = None
        self._hovered_idx = -1

        self._content_rect = draw_panel(pygame.Surface((1, 1)), rect, title)
        # recalculate properly at draw time

    def set_items(self, items: list[tuple[str, str, tuple | None]]) -> None:
        self._items  = items
        self._scroll = 0

    def set_selected(self, item_id: str | None) -> None:
        self._selected_id = item_id

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.rect.collidepoint(pygame.mouse.get_pos()):
            return

        if event.type == pygame.MOUSEMOTION:
            rel_y = event.pos[1] - (self.rect.y + HEADER_H)
            self._hovered_idx = rel_y // ROW_H + self._scroll if rel_y >= 0 else -1

        elif event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, min(
                len(self._items) - self._visible_rows(),
                self._scroll - event.y,
            ))

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                rel_y = event.pos[1] - (self.rect.y + HEADER_H)
                if rel_y >= 0:
                    idx = rel_y // ROW_H + self._scroll
                    if 0 <= idx < len(self._items):
                        _, item_id, _ = self._items[idx]
                        self._selected_id = item_id
                        if self.on_select:
                            self.on_select(item_id)

    def _visible_rows(self) -> int:
        return (self.rect.height - HEADER_H) // ROW_H

    def draw(self, surface: pygame.Surface) -> None:
        content = draw_panel(surface, self.rect, self.title)

        # Clip to content area
        old_clip = surface.get_clip()
        surface.set_clip(content)

        visible = self._visible_rows()
        for i in range(visible):
            idx = i + self._scroll
            if idx >= len(self._items):
                break
            label, item_id, color = self._items[idx]
            row_y = content.y + i * ROW_H

            is_sel   = item_id == self._selected_id
            is_hover = idx == self._hovered_idx

            if is_sel:
                bg_rect = pygame.Rect(content.x, row_y, content.width, ROW_H)
                pygame.draw.rect(surface, C_HOVER, bg_rect)
                sel_surf = font(11).render("▶", True, C_SELECTED)
                surface.blit(sel_surf, (content.x + 2, row_y + (ROW_H - sel_surf.get_height()) // 2))
            elif is_hover:
                bg_rect = pygame.Rect(content.x, row_y, content.width, ROW_H)
                pygame.draw.rect(surface, (20, 45, 85), bg_rect)

            text_color = (color if color else (C_TEXT if is_sel else C_TEXT_DIM))
            txt_surf = font(13).render(label, True, text_color)
            surface.blit(txt_surf, (content.x + 18, row_y + (ROW_H - txt_surf.get_height()) // 2))

        # Scrollbar
        total = len(self._items)
        if total > visible and total > 0:
            bar_h     = max(20, int(content.height * visible / total))
            bar_y     = content.y + int(content.height * self._scroll / total)
            bar_rect  = pygame.Rect(content.right - 5, bar_y, 4, bar_h)
            pygame.draw.rect(surface, C_SCROLLBAR, bar_rect, border_radius=2)

        surface.set_clip(old_clip)


# ---------------------------------------------------------------------------
# Separator
# ---------------------------------------------------------------------------

def draw_separator(surface: pygame.Surface, x1: int, y: int, x2: int) -> None:
    pygame.draw.line(surface, C_SEP, (x1, y), (x2, y))


# ---------------------------------------------------------------------------
# TextInput
# ---------------------------------------------------------------------------

class TextInput:
    """Single-line text input box with horizontal scroll. Call handle_event() while active."""
    def __init__(self, rect, initial_text="", font_size=13, max_length=60):
        self.rect = pygame.Rect(rect)
        self.text = initial_text
        self.active = False
        self._cursor = len(initial_text)
        self._font_size = font_size
        self.max_length = max_length
        self._blink_t = 0
        self._scroll_x = 0   # horizontal pixel offset so cursor stays visible

    def _clamp_scroll(self, f: pygame.font.Font) -> None:
        visible_w = self.rect.width - 8
        cursor_px = f.size(self.text[:self._cursor])[0]
        # scroll right if cursor beyond right edge
        if cursor_px - self._scroll_x > visible_w:
            self._scroll_x = cursor_px - visible_w
        # scroll left if cursor before left edge
        if cursor_px - self._scroll_x < 0:
            self._scroll_x = max(0, cursor_px - 10)
        # don't scroll past end of text
        text_w = f.size(self.text)[0]
        self._scroll_x = max(0, min(self._scroll_x, max(0, text_w - visible_w)))

    def handle_event(self, event):
        if not self.active:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.active = self.rect.collidepoint(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self._cursor > 0:
                    self.text = self.text[:self._cursor-1] + self.text[self._cursor:]
                    self._cursor -= 1
            elif event.key == pygame.K_DELETE:
                self.text = self.text[:self._cursor] + self.text[self._cursor+1:]
            elif event.key == pygame.K_LEFT:
                self._cursor = max(0, self._cursor - 1)
            elif event.key == pygame.K_RIGHT:
                self._cursor = min(len(self.text), self._cursor + 1)
            elif event.key == pygame.K_HOME:
                self._cursor = 0
            elif event.key == pygame.K_END:
                self._cursor = len(self.text)
            elif event.unicode and event.unicode.isprintable() and len(self.text) < self.max_length:
                self.text = self.text[:self._cursor] + event.unicode + self.text[self._cursor:]
                self._cursor += 1

    def draw(self, surface):
        from .constants import C_ACCENT, C_TEXT, C_BTN, C_BORDER
        bg = (18, 35, 75) if self.active else (13, 13, 32)
        pygame.draw.rect(surface, bg, self.rect, border_radius=3)
        border_col = C_ACCENT if self.active else C_BORDER
        pygame.draw.rect(surface, border_col, self.rect, 1, border_radius=3)
        f = font(self._font_size)
        self._clamp_scroll(f)
        text_surf = f.render(self.text, True, C_TEXT)
        old_clip = surface.get_clip()
        clip_rect = pygame.Rect(self.rect.x + 3, self.rect.y + 2,
                                self.rect.width - 6, self.rect.height - 4)
        surface.set_clip(clip_rect)
        tx = self.rect.x + 4 - self._scroll_x
        surface.blit(text_surf, (tx, self.rect.centery - text_surf.get_height() // 2))
        if self.active:
            self._blink_t = (self._blink_t + 1) % 60
            if self._blink_t < 30:
                cursor_px = self.rect.x + 4 + f.size(self.text[:self._cursor])[0] - self._scroll_x
                cursor_px = max(self.rect.x + 4, min(cursor_px, self.rect.right - 4))
                pygame.draw.line(surface, C_ACCENT,
                                 (cursor_px, self.rect.y + 3),
                                 (cursor_px, self.rect.bottom - 3), 1)
        surface.set_clip(old_clip)
