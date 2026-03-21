# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the game (Windows — python/python3 aliases are broken; use full Anaconda path)
$env:USERPROFILE\anaconda3\python.exe run_gui.py

# Generate a map from CLI (no GUI)
$env:USERPROFILE\anaconda3\python.exe main.py --seed 42 --systems 15

# Run unit tests (headless model/logic tests — hand-maintained)
~/anaconda3/python.exe scripts/unit_tests.py

# Run smoke tests (auto-generated import + game-state checks)
~/anaconda3/python.exe scripts/smoke_tests.py

# Run linter
~/anaconda3/python.exe -m ruff check src/ --config ruff.toml

# Build standalone .exe (Windows, requires PyInstaller)
build.bat
```

All commands must be run from `UniversalAssemblers/` as the working directory. Maps are written to `maps/` relative to there.

## Architecture

See `docs/ARCHITECTURE.md` for full detail.

| File / module | Purpose |
|---|---|
| `src/gui/app.py` | `App` — pygame window, `"menu"` / `"galaxy"` / `"system"` state machine, toast dispatch |
| `src/gui/game_view.py` | `GameView` — three-pane system view (NavPanel, MapPanel, EntitiesPanel) |
| `src/gui/{tech,energy,queue,entity}_view.py` | Modal overlays — activate/deactivate protocol, ESC priority, hit-rect pattern |
| `src/gui/{widgets,constants}.py` | Shared UI helpers — Button, ScrollableList, colours, font cache |
| `src/game_state.py` | `GameState` — discovery, `EntityRoster`, `TechState`, `BotTaskList` |
| `src/simulation.py` | `SimulationEngine` — bios, power plants, research, ships, bot tasks |
| `src/generator.py` | `MapGenerator` — deterministic procedural galaxy (seed → same result always) |
| `src/models/` | Data models: `celestial`, `resource`, `entity`, `tech` |

## Commit convention

Git log is the primary context recovery mechanism. Every session that implements something **must** end with a descriptive commit using `/commit-impl`.

```
<type>(<scope>): <what was done — ≤ 72 chars>

Why: <one phrase or sentence>
What: <2-3 tight bullets>
Next: <what comes after>

Files: <key files changed>
```

Types: `feat`, `fix`, `refactor`, `test`, `chore`
Scope: `entity-view`, `tech-tree`, `game-state`, `simulation`, `overlay`, `hooks`, etc.

When spawning a subagent, include a `## Context handoff` block with: recent commit, just implemented, task, and return format expected.

New machine setup: see `docs/SETUP.md`.

## Context recovery (fresh window or new session)

1. Read `CLAUDE.md` — active rules and architecture table
2. Run `git log --oneline -10` — what has been done recently
3. Run `git show HEAD --stat` — what the last session changed
4. Read `TODO.md` — what remains

## After implementing features

After writing or modifying any logic in `src/models/`, `src/game_state.py`, `src/generator.py`, or `src/simulation.py`, **spawn the test-updater agent**:

```
Use the Agent tool with subagent_type "test-updater". Tell it which files were changed and what was implemented. It will add assertions to scripts/unit_tests.py, run the tests, and report lint findings.
```

Do not spawn the agent for GUI-only changes (`src/gui/`) — GUI code is not testable headlessly.

Before committing: run `~/anaconda3/python.exe -c "from src.gui.app import App"` to confirm imports resolve (catches build failures in ~1 s instead of after PyInstaller's 60–120 s run).

The linter also runs automatically as a PostToolUse hook on every `src/` edit — check hook output for `[lint]` lines.

## Key design rules

See `docs/GAME_DESIGN.md` for the full list. Key points: orbital structures = squares on map; probe required before system details visible; power plants: solar/wind/bios renewable, others consume finite resources.

## Implementation status

See `TODO.md` for remaining work. Implemented history is in `git log`.
