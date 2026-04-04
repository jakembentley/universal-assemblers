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
        """Remap an action to a new key, clearing any existing binding for that key."""
        for other_action, other_key in list(self._keys.items()):
            if other_action != action and other_key == key_const:
                del self._keys[other_action]
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
                try:
                    key_const = pygame.key.key_code(key_name)
                except ValueError:
                    continue
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
        kb: dict[str, str] = {}
        for action, key_const in self._keys.items():
            kb[action] = pygame.key.name(key_const)
        data["keybindings"] = kb
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
