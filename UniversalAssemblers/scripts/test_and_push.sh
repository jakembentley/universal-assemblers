#!/usr/bin/env bash
# test_and_push.sh
#
# Called by the Claude Code Stop hook.
# 1. Checks whether any changes exist under UniversalAssemblers/
# 2. Runs a Python smoke test from the project directory
# 3. If tests pass: stages only UniversalAssemblers/ source files, commits, and pushes
#
# Never stages build/, dist/, __pycache__, or binary files.

REPO="/c/Users/Admin/CODE"
PROJECT="UniversalAssemblers"
PYTHON="/c/Users/Admin/anaconda3/python.exe"

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

# ── 2. Smoke test (run from project dir so 'src' is importable) ───────────────
echo "[hook] Changes detected in ${PROJECT}/ — running smoke test..."

cd "$REPO/$PROJECT" || exit 1

"$PYTHON" -c "
from src.models.entity import StructureType, MegastructureType, BioType, STARTING_ENTITIES
from src.models.tech import TECH_TREE, can_research
from src.models.resource import Resource
from src.game_state import GameState
from src.generator import MapGenerator

gen = MapGenerator(seed=1, num_solar_systems=3)
gs  = GameState.new_game(gen.generate())
assert gs.entity_roster.total('structure', 'factory') == 1, 'factory missing'
assert gs.entity_roster.total('ship', 'probe') == 1,       'probe missing'
assert len(TECH_TREE) > 0,                                  'tech tree empty'
print('Smoke test passed.')
"

if [ $? -ne 0 ]; then
  echo "[hook] Smoke test FAILED — aborting push."
  exit 1
fi

# ── 3. Stage source files only, commit, push ─────────────────────────────────
cd "$REPO" || exit 1

# Add only tracked source paths — never build artifacts or binaries
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
