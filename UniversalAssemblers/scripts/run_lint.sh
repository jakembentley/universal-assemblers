#!/usr/bin/env bash
# run_lint.sh — PostToolUse hook
#
# Runs after Edit/Write tool calls on src/ Python files.
# Installs ruff on first use if not present, then lints the modified file.
# Always exits 0 (PostToolUse hooks cannot block).

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

# ── 1. Parse file path from stdin JSON ───────────────────────────────────────
TOOL_INPUT=$(cat)
FILE_PATH=$(echo "$TOOL_INPUT" | "$PYTHON" -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null)

# Only lint .py files under src/
case "$FILE_PATH" in
    *.py) ;;
    *) exit 0 ;;
esac
echo "$FILE_PATH" | grep -q "${PROJECT}/src" || exit 0

# ── 2. Ensure ruff is available ───────────────────────────────────────────────
PY_DIR="$(dirname "$PYTHON")"
RUFF="$PY_DIR/Scripts/ruff.exe"
[ -f "$RUFF" ] || RUFF="$PY_DIR/ruff"
[ -f "$RUFF" ] || RUFF="$(command -v ruff 2>/dev/null)"

if [ -z "$RUFF" ] || [ ! -f "$RUFF" ]; then
    echo "[lint] ruff not found — installing..."
    "$PYTHON" -m pip install ruff --quiet 2>&1
    # Re-resolve after install
    RUFF="$PY_DIR/Scripts/ruff.exe"
    [ -f "$RUFF" ] || RUFF="$PY_DIR/ruff"
    [ -f "$RUFF" ] || RUFF="$("$PYTHON" -c "import shutil; print(shutil.which('ruff') or '')" 2>/dev/null)"
    if [ -z "$RUFF" ]; then
        echo "[lint] ruff install failed — skipping lint."
        exit 0
    fi
fi

# ── 3. Run ruff on the modified file ────────────────────────────────────────
cd "$PROJECT_DIR" || exit 0

# Convert Windows absolute path to relative for cleaner output
REL_FILE="${FILE_PATH#$PROJECT_DIR/}"
REL_FILE="${REL_FILE#$PROJECT_DIR\\}"

OUTPUT=$("$RUFF" check "$FILE_PATH" --config "$PROJECT_DIR/ruff.toml" 2>&1)
CODE=$?

if [ $CODE -eq 0 ]; then
    echo "[lint] PASS — $REL_FILE"
else
    echo "[lint] ISSUES in $REL_FILE"
    echo "$OUTPUT"
fi

exit 0
