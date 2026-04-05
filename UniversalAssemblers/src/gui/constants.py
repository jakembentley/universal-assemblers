"""
Layout constants, colours, and font helpers for the Universal Assemblers GUI.
All sizes are in pixels.  Fonts are lazily cached after pygame.init().
"""
from __future__ import annotations
import pygame

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 800
FPS           = 60
TITLE         = "Universal Assemblers"

# ---------------------------------------------------------------------------
# Scale infrastructure
# ---------------------------------------------------------------------------
BASE_HEIGHT = 1080
UI_SCALE    = 1.0   # updated by set_ui_scale() on init and resolution change


def scaled(n: int) -> int:
    """Scale a pixel value by UI_SCALE, minimum 1."""
    return max(1, int(n * UI_SCALE))


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
NAV_W     = scaled(340)                    # left panel width
ENT_H     = scaled(190)                    # bottom entities panel height
TASKBAR_H = scaled(36)                     # top taskbar height
TOP_H     = WINDOW_HEIGHT - ENT_H - TASKBAR_H  # height of the two main view panels
MAP_X     = NAV_W                          # map panel x origin
MAP_W     = WINDOW_WIDTH - NAV_W          # map panel width

HEADER_H    = scaled(26)                   # panel title bar height
ROW_H       = scaled(22)                   # list row height
PADDING     = scaled(8)
RES_STRIP_H = scaled(160)                  # global resources strip height

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
C_BG        = (  8,   8,  20)
C_PANEL     = ( 13,  13,  32)
C_BORDER    = ( 35,  70, 120)
C_HEADER    = ( 18,  35,  75)
C_TEXT      = (200, 220, 255)
C_TEXT_DIM  = ( 90, 120, 160)
C_ACCENT    = (  0, 200, 255)
C_SELECTED  = (255, 200,  30)
C_HOVER     = ( 30,  70, 120)
C_SEP       = ( 28,  55,  95)
C_BTN       = ( 22,  52, 105)
C_BTN_HOV   = ( 45,  95, 170)
C_BTN_TXT   = (180, 220, 255)
C_SCROLLBAR = ( 40,  70, 120)
C_WARN      = (255, 160,  40)

# Celestial body colours
STAR_COLORS: dict[str, tuple] = {
    "O-type": (160, 185, 255),
    "B-type": (190, 210, 255),
    "A-type": (245, 245, 255),
    "F-type": (255, 245, 200),
    "G-type": (255, 220,  80),
    "K-type": (255, 160,  40),
    "M-type": (220,  75,  20),
}

BODY_COLORS: dict[str, tuple] = {
    "terrestrial":  ( 70, 145, 205),
    "super_earth":  ( 75, 185, 105),
    "gas_giant":    (225, 185, 100),
    "ice_giant":    (140, 205, 255),
    "hot_jupiter":  (225,  80,  40),
    "exoplanet":    (165,  80, 225),
    "comet":        (200, 240, 255),
    "asteroid":     (130, 120, 110),
    "moon":         (170, 170, 185),
    "star":         (255, 220,  80),
}

# ---------------------------------------------------------------------------
# Font cache
# ---------------------------------------------------------------------------
_font_cache: dict[tuple, pygame.font.Font] = {}

def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        # Prefer a monospace font for the sci-fi terminal aesthetic
        for name in ("Consolas", "Courier New", "monospace"):
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                _font_cache[key] = f
                break
            except Exception:
                continue
        else:
            _font_cache[key] = pygame.font.Font(None, size + 4)
    return _font_cache[key]


def font_scaled(size: int, bold: bool = False) -> pygame.font.Font:
    """Return a font scaled by UI_SCALE, minimum size 8."""
    return font(max(8, scaled(size)), bold)


def set_ui_scale(screen_height: int) -> None:
    """Recompute all layout globals for the given screen height.
    Must be called before any view is constructed or rebuilt.
    """
    import sys
    _mod = sys.modules[__name__]
    _mod.UI_SCALE   = screen_height / BASE_HEIGHT
    _mod.NAV_W      = scaled(340)
    _mod.ENT_H      = scaled(190)
    _mod.TASKBAR_H  = scaled(36)
    _mod.HEADER_H   = scaled(26)
    _mod.ROW_H      = scaled(22)
    _mod.PADDING    = scaled(8)
    _mod.RES_STRIP_H = scaled(160)
    _mod.TOP_H      = screen_height - _mod.ENT_H - _mod.TASKBAR_H
    _mod.MAP_W      = _mod.WINDOW_WIDTH - _mod.NAV_W
    _mod.MAP_X      = _mod.NAV_W
    _font_cache.clear()
