"""
Game logger — thin wrapper around stdlib logging.

Usage in other modules:
    from src.logger import get_logger, log_snapshot

    log = get_logger("ua.simulation")
    log.info("Something happened")

Call setup() once at process start (run_gui.py). If setup() is never called
(headless unit tests), stdlib logging silently discards all records.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state import GameState

_SETUP_DONE = False


def setup(debug: bool = False) -> None:
    """Configure the root 'ua' logger with a rotating session log file.

    Must be called once before App() in run_gui.py. Safe to call multiple
    times (subsequent calls are no-ops).
    """
    global _SETUP_DONE
    if _SETUP_DONE:
        return
    _SETUP_DONE = True

    os.makedirs("logs", exist_ok=True)

    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join("logs", f"session_{session_ts}.log")

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger("ua")
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root.addHandler(handler)
    # Do not propagate to the stdlib root logger (avoids console spam).
    root.propagate = False

    root.info("=== SESSION START  file=%s  debug=%s ===", log_path, debug)


def get_logger(name: str = "ua") -> logging.Logger:
    """Return a logger under the 'ua' hierarchy.

    Safe to call before setup() — records are silently discarded until a
    handler is attached (which is what headless unit tests need).
    """
    return logging.getLogger(name)


def log_snapshot(gs: "GameState", reason: str = "") -> None:
    """Log a structured game-state snapshot at INFO level.

    Captures year, tech state, entity counts, active task counts, and the
    last 10 ledger messages. Designed to be readable by Claude when
    diagnosing bugs or planning features.

    Safe to call with gs=None (returns immediately).
    """
    if gs is None:
        return

    log = get_logger("ua.snapshot")

    # --- entity counts by (category, type_value) ---
    entity_counts: dict[tuple[str, str], int] = {}
    try:
        for inst in gs.entity_roster.all():
            key = (inst.category, inst.type_value)
            entity_counts[key] = entity_counts.get(key, 0) + inst.count
    except Exception:
        entity_counts = {}

    entity_lines = "\n".join(
        f"    {cat}/{tv}: {cnt}"
        for (cat, tv), cnt in sorted(entity_counts.items())
    ) or "    (none)"

    # --- tech ---
    tech_done = sorted(gs.tech.researched) if gs.tech else []
    tech_progress = {
        k: round(v, 1)
        for k, v in (gs.tech._progress.items() if gs.tech else {})
        if v > 0
    }

    # --- task counts ---
    try:
        bot_task_count = len(gs.bot_tasks.all_keys())
    except Exception:
        bot_task_count = "?"
    try:
        factory_task_count = len(gs.factory_tasks.all_keys())
    except Exception:
        factory_task_count = "?"
    try:
        shipyard_task_count = len(gs.shipyard_tasks.all_keys())
    except Exception:
        shipyard_task_count = "?"

    # --- ledger tail (newest-first, already ordered that way in _ledger) ---
    ledger_lines = ""
    try:
        tail = gs._ledger[:10]
        if tail:
            ledger_lines = "\n".join(f"    {e.message}" for e in tail)
        else:
            ledger_lines = "    (empty)"
    except Exception:
        ledger_lines = "    (unavailable)"

    # --- galaxy info ---
    galaxy_name = "(none)"
    system_count = 0
    try:
        if gs.galaxy:
            galaxy_name = gs.galaxy.name
            system_count = len(gs.galaxy.solar_systems)
    except Exception:
        pass

    snapshot = (
        f"\n=== SNAPSHOT [{reason}] ===\n"
        f"  year          : {gs.in_game_years:.2f}\n"
        f"  galaxy        : {galaxy_name}  ({system_count} systems)\n"
        f"  tech_done     : {tech_done}\n"
        f"  tech_progress : {tech_progress}\n"
        f"  bot_tasks     : {bot_task_count} active\n"
        f"  factory_tasks : {factory_task_count} active\n"
        f"  shipyard_tasks: {shipyard_task_count} active\n"
        f"  entities:\n{entity_lines}\n"
        f"  ledger_tail (newest first):\n{ledger_lines}\n"
        f"=========================="
    )
    log.info(snapshot)
