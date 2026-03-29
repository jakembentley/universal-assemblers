#!/usr/bin/env python3
"""
Universal Assemblers — GUI entry point.

Usage:
    python run_gui.py [--debug]
"""
import argparse
import traceback

from src import logger as _logger
from src.gui.app import App


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="universal-assemblers")
    p.add_argument(
        "--debug", action="store_true",
        help="Enable DEBUG-level logging to logs/session_*.log",
    )
    return p


if __name__ == "__main__":
    args = _build_parser().parse_args()
    _logger.setup(debug=args.debug)
    _log = _logger.get_logger("ua.main")

    try:
        App().run()
    except SystemExit:
        raise  # normal quit() path — do not log
    except Exception:
        _log.error("Unhandled exception in main loop:\n%s", traceback.format_exc())
        raise
