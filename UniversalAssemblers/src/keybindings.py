"""
Keybindings — persists player-configured hotkeys to maps/settings.json.

Usage:
    from src.keybindings import Keybindings
    kb = Keybindings("maps/settings.json")
    if event.key == kb.key("quick_save"):
        ...
    kb.set("quick_save", pygame.K_F6)
    kb.save()
"""
from __future__ import annotations

import json
import os
import pygame


# Default keybindings: action_id -> pygame key constant
_DEFAULTS: dict[str, int] = {
    "toggle_pause": pygame.K_SPACE,
    "quick_save":   pygame.K_F5,
    "quick_load":   pygame.K_F9,
    "debug_view":   pygame.K_F12,
}

# Human-readable action labels (for display in settings menu)
ACTION_LABELS: dict[str, str] = {
    "toggle_pause": "Pause / Resume",
    "quick_save":   "Quick Save",
    "quick_load":   "Quick Load",
    "debug_view":   "Debug HUD",
}


class Keybindings:
    """Manages hotkey mappings with file-backed persistence."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._keys: dict[str, int] = dict(_DEFAULTS)
        self.load()

    # ------------------------------------------------------------------

    def key(self, action: str) -> int:
        """Return the current pygame key constant for an action."""
        return self._keys.get(action, _DEFAULTS.get(action, 0))

    def set(self, action: str, key_const: int) -> None:
        """Remap an action to a new key."""
        self._keys[action] = key_const

    def reset_all(self) -> None:
        self._keys = dict(_DEFAULTS)

    def actions(self) -> list[str]:
        return list(ACTION_LABELS.keys())

    # ------------------------------------------------------------------

    def load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            kb = data.get("keybindings", {})
            for action, key_name in kb.items():
                key_const = getattr(pygame, f"K_{key_name}", None)
                if key_const is not None:
                    self._keys[action] = key_const
        except (json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        # Load existing file so we don't clobber other settings
        data: dict = {}
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        # pygame.key.name() returns e.g. "f5", "space"; strip and upper for K_ lookup
        kb: dict[str, str] = {}
        for action, key_const in self._keys.items():
            name = pygame.key.name(key_const).upper()
            kb[action] = name
        data["keybindings"] = kb
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
