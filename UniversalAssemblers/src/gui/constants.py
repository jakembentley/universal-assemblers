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
# Layout
# ---------------------------------------------------------------------------
NAV_W   = 340                            # left panel width
ENT_H   = 190                            # bottom entities panel height
TOP_H   = WINDOW_HEIGHT - ENT_H         # height of the two top panels
MAP_X   = NAV_W                          # map panel x origin
MAP_W   = WINDOW_WIDTH - NAV_W          # map panel width

HEADER_H = 26                            # panel title bar height
ROW_H    = 22                            # list row height
PADDING  = 8

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
