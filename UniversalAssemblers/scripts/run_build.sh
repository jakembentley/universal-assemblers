#!/usr/bin/env bash
# run_build.sh — Stop hook
#
# Runs PyInstaller after each session if any src/ Python files changed
# since the last successful build.  Skips the build if nothing changed.

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

SPEC="$PROJECT_DIR/UniversalAssemblers.spec"
STAMP="$PROJECT_DIR/build/.last_build_stamp"

cd "$PROJECT_DIR" || exit 1

# ── 1. Check for Python source changes since last build ──────────────────────
CHANGED_SRC=$(
  find src/ -name "*.py" -newer "$STAMP" 2>/dev/null | head -1
)

if [ -z "$CHANGED_SRC" ] && [ -f "$STAMP" ]; then
  echo "[build] No src/ changes since last build — skipping PyInstaller."
  exit 0
fi

# ── 2. Bail if PyInstaller not found ────────────────────────────────────────
if [ ! -f "$PYINSTALLER" ] && ! command -v pyinstaller &>/dev/null; then
  echo "[build] PyInstaller not found — skipping build (install with: pip install pyinstaller)."
  exit 0
fi

echo "[build] Source changes detected — running PyInstaller..."

# ── 3. Run PyInstaller ────────────────────────────────────────────────────────
"$PYINSTALLER" "$SPEC" --noconfirm 2>&1
BUILD_CODE=$?

if [ $BUILD_CODE -eq 0 ]; then
  mkdir -p "$(dirname "$STAMP")"
  touch "$STAMP"
  echo "[build] Build successful — dist/UniversalAssemblers.exe updated."
else
  echo "[build] Build FAILED (exit $BUILD_CODE). Check output above."
fi

exit $BUILD_CODE
