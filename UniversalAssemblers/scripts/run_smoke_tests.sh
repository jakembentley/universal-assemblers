#!/usr/bin/env bash
# run_smoke_tests.sh — PostToolUse hook
#
# Runs after Edit/Write tool calls. Reads tool input from stdin to check
# if a src/ Python file was modified, then runs scripts/smoke_tests.py and
# reports pass/fail.  Always exits 0 (PostToolUse hooks cannot block).

REPO="/c/Users/Admin/code"
PROJECT="UniversalAssemblers"
PYTHON="/c/Users/Admin/anaconda3/python.exe"
TESTS="$REPO/$PROJECT/scripts/smoke_tests.py"

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

# Only run for .py files under src/
case "$FILE_PATH" in
    *.py) ;;
    *) exit 0 ;;
esac
echo "$FILE_PATH" | grep -q "${PROJECT}/src" || exit 0

# ── 2. Bail if smoke_tests.py doesn't exist yet ──────────────────────────────
if [ ! -f "$TESTS" ]; then
    echo "[smoke] smoke_tests.py not found — skipping."
    exit 0
fi

# ── 3. Run tests ─────────────────────────────────────────────────────────────
cd "$REPO/$PROJECT" || exit 0

OUTPUT=$("$PYTHON" "$TESTS" 2>&1)
CODE=$?

if [ $CODE -eq 0 ]; then
    echo "[smoke] PASS — $OUTPUT"
else
    echo "[smoke] FAIL"
    echo "$OUTPUT"
fi

exit 0
