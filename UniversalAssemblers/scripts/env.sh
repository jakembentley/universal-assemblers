#!/usr/bin/env bash
# env.sh — shared environment for all hook scripts
#
# Auto-detects Python and PyInstaller across Windows (Anaconda/Miniconda/system)
# and Unix/macOS.  Source this file; do NOT execute it directly.
#
# After sourcing, the following variables are set:
#   PYTHON        — full path to the Python executable
#   PYINSTALLER   — full path to the PyInstaller executable
#   PROJECT_DIR   — absolute path to the UniversalAssemblers project root
#   REPO          — absolute path to the parent repository root
#   PROJECT       — basename of PROJECT_DIR  (= "UniversalAssemblers")

# ── Python detection ─────────────────────────────────────────────────────────
# Prefers Anaconda/Miniconda at standard install locations on Windows, then
# falls back to system python3/python.  Never returns Windows Store stubs.
_ua_find_python() {
    local candidates=(
        "$HOME/anaconda3/python.exe"
        "$HOME/Anaconda3/python.exe"
        "$HOME/miniconda3/python.exe"
        "$HOME/Miniconda3/python.exe"
        "/c/ProgramData/Anaconda3/python.exe"
        "/c/ProgramData/Miniconda3/python.exe"
    )
    for p in "${candidates[@]}"; do
        [ -f "$p" ] && echo "$p" && return 0
    done
    # Unix / macOS fallback
    command -v python3 2>/dev/null && return 0
    command -v python  2>/dev/null && return 0
    echo "python3"   # last resort — will fail loudly if not found
}

# Allow override via environment variable (e.g. CI)
if [ -z "$PYTHON" ]; then
    PYTHON="$(_ua_find_python)"
fi

# ── PyInstaller detection ────────────────────────────────────────────────────
_ua_find_pyinstaller() {
    local py_dir
    py_dir="$(dirname "$PYTHON")"
    local candidates=(
        "$py_dir/Scripts/pyinstaller.exe"   # Windows Anaconda
        "$py_dir/pyinstaller"               # Unix venv
        "$py_dir/../Scripts/pyinstaller.exe"
    )
    for p in "${candidates[@]}"; do
        [ -f "$p" ] && echo "$p" && return 0
    done
    command -v pyinstaller 2>/dev/null && return 0
    echo "pyinstaller"   # last resort
}

if [ -z "$PYINSTALLER" ]; then
    PYINSTALLER="$(_ua_find_pyinstaller)"
fi

# ── Project paths (derived from this file's location) ───────────────────────
_UA_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$_UA_SCRIPTS_DIR/.." && pwd)"
PROJECT="$(basename "$PROJECT_DIR")"
REPO="$(cd "$PROJECT_DIR/.." && pwd)"

# ── Local machine overrides (from scripts/local.env.sh if present) ──────────
_UA_LOCAL="$_UA_SCRIPTS_DIR/local.env.sh"
if [ -f "$_UA_LOCAL" ]; then
    source "$_UA_LOCAL"
    [ -n "$UA_PYTHON" ] && PYTHON="$UA_PYTHON"
fi
