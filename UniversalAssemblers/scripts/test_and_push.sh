#!/usr/bin/env bash
# test_and_push.sh — Stop hook
#
# 1. Checks whether any changes exist under the project directory
# 2. Runs Python smoke tests
# 3. Stages only source files, commits, and pushes

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

TESTS="$PROJECT_DIR/scripts/smoke_tests.py"

cd "$REPO" || exit 1

# ── 1. Check for changes scoped to the project ───────────────────────────────
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

# ── 2. Smoke tests ────────────────────────────────────────────────────────────
echo "[hook] Changes detected in ${PROJECT}/ — running smoke tests..."

cd "$PROJECT_DIR" || exit 1

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

# ── 3. Build validation — verify all key src/ imports load cleanly ───────────
echo "[hook] Checking imports..."
cd "$PROJECT_DIR" || exit 1
IMPORT_OUTPUT=$(
  "$PYTHON" -c "
from src.gui.app import App
from src.simulation import SimulationEngine
from src.game_state import GameState
from src.generator import MapGenerator
from src.models.entity import POWER_PLANT_SPECS, BUILD_COSTS
from src.models.tech import TECH_TREE
print('All imports OK')
" 2>&1
)
IMPORT_CODE=$?
if [ $IMPORT_CODE -ne 0 ]; then
  echo "[hook] Import check FAILED — build.bat would break. Aborting push."
  echo "$IMPORT_OUTPUT"
  exit 1
fi
echo "[hook] $IMPORT_OUTPUT"

cd "$REPO" || exit 1

# ── 4. Stage source files only, commit, push ─────────────────────────────────
cd "$REPO" || exit 1

git add "${PROJECT}/" \
  ':!*/__pycache__' \
  ':!*/build/'      \
  ':!*/dist/'       \
  ':!*.exe'         \
  ':!*.pkg'         \
  ':!*.pyz'         \
  ':!*.pyc'

if git diff --cached --quiet; then
  echo "[hook] Nothing new to commit."
  exit 0
fi

TIMESTAMP=$(date +"%Y-%m-%d %H:%M")

# Build an informative body: list changed src/ files and the diff stat summary
CHANGED_SRC=$(git diff --cached --name-only | grep "^${PROJECT}/src/" | sed "s|${PROJECT}/src/||" | sort | tr '\n' ' ')
STAT_SUMMARY=$(git diff --cached --stat | tail -1 | sed 's/^ *//')

BODY=""
[ -n "$CHANGED_SRC" ] && BODY="src: ${CHANGED_SRC}"$'\n'
[ -n "$STAT_SUMMARY" ] && BODY="${BODY}${STAT_SUMMARY}"

if [ -n "$BODY" ]; then
  git commit -m "auto: ${PROJECT} @ ${TIMESTAMP}" -m "$BODY"
else
  git commit -m "auto: ${PROJECT} @ ${TIMESTAMP}"
fi

git push origin master

echo "[hook] Changes pushed to GitHub."
