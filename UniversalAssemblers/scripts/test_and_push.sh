#!/usr/bin/env bash
# test_and_push.sh
#
# Called by the Claude Code Stop hook.
# 1. Checks whether any changes exist under UniversalAssemblers/
# 2. Runs the Python smoke tests from the project directory
# 3. Stages only UniversalAssemblers/ source files, commits, and pushes
#
# Build (PyInstaller) is NOT run here — it is slow (~1-3 min) and should
# only be triggered explicitly with `build.bat` when releasing.
#
# Never stages build/, dist/, __pycache__, or binary files.

REPO="/c/Users/Admin/code"
PROJECT="UniversalAssemblers"
PYTHON="/c/Users/Admin/anaconda3/python.exe"
TESTS="$REPO/$PROJECT/scripts/smoke_tests.py"

cd "$REPO" || exit 1

# ── 1. Check for changes scoped to UniversalAssemblers/ ──────────────────────
CHANGED=$(
  {
    git diff --name-only HEAD 2>/dev/null
    git ls-files --others --exclude-standard 2>/dev/null
  } | grep "^${PROJECT}/" \
    | grep -v "/__pycache__/" \
    | grep -v "/build/"       \
    | grep -v "/dist/"        \
    || true
)

if [ -z "$CHANGED" ]; then
  exit 0   # nothing to do
fi

# ── 2. Smoke tests (run from project dir so 'src' is importable) ──────────────
echo "[hook] Changes detected in ${PROJECT}/ — running smoke tests..."

cd "$REPO/$PROJECT" || exit 1

if [ -f "$TESTS" ]; then
  OUTPUT=$("$PYTHON" "$TESTS" 2>&1)
  CODE=$?
  if [ $CODE -ne 0 ]; then
    echo "[hook] Smoke tests FAILED — aborting push."
    echo "$OUTPUT"
    exit 1
  fi
  echo "[hook] $OUTPUT"
else
  # Fallback inline smoke test if scripts/smoke_tests.py hasn't been generated yet
  "$PYTHON" -c "
from src.game_state import GameState
from src.generator import MapGenerator
from src.models.tech import TECH_TREE
gs = GameState.new_game(MapGenerator(seed=1, num_solar_systems=3).generate())
assert gs.entity_roster.total('structure', 'factory') == 1, 'factory missing'
assert gs.entity_roster.total('ship', 'probe') == 1, 'probe missing'
assert len(TECH_TREE) > 0, 'tech tree empty'
print('Fallback smoke test passed.')
"
  if [ $? -ne 0 ]; then
    echo "[hook] Smoke test FAILED — aborting push."
    exit 1
  fi
fi

# ── 3. Stage source files only, commit, push ─────────────────────────────────
cd "$REPO" || exit 1

# Add only source paths — never build artifacts or binaries
git add "${PROJECT}/" \
  ':!*/__pycache__' \
  ':!*/build/'      \
  ':!*/dist/'       \
  ':!*.exe'         \
  ':!*.pkg'         \
  ':!*.pyz'         \
  ':!*.pyc'

# Nothing staged means changes were already committed
if git diff --cached --quiet; then
  echo "[hook] Nothing new to commit."
  exit 0
fi

TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "auto: ${PROJECT} changes @ ${TIMESTAMP}"
git push origin master

echo "[hook] Changes pushed to GitHub."
