#!/usr/bin/env bash
# check_python_path.sh — PreToolUse hook for Bash commands
#
# Warns if a Bash command uses bare `python` or `python3` when those aliases
# resolve to a no-op stub (e.g. the Windows Store stub).  Uses env.sh to
# locate the real Python, so the warning is always accurate for this machine.

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

TOOL_INPUT=$(cat)

COMMAND=$(echo "$TOOL_INPUT" | "$PYTHON" -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null)

# Check for bare python/python3 invocations (not part of a longer path)
if echo "$COMMAND" | grep -qE '(^|[[:space:];|&])(python3?)[[:space:]]'; then
    echo "[hook] WARNING: command uses bare 'python'/'python3' — these may point to a stub, not the real interpreter. Use: $PYTHON" >&2
fi

exit 0
