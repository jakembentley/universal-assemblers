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

### State machine (`src/gui/app.py` → `App`)
The `App` class owns the pygame window and drives a three-state machine:
- `"menu"` — `MainMenu`
- `"galaxy"` — `GalaxyView` (fog-of-war map of all systems)
- `"system"` — `GameView` (three-pane in-system interface)

`App.run()` processes events globally first (ESC, spacebar, speed badge click), then dispatches to the active view. The pause menu (`PauseMenu`) is an overlay rendered on top of galaxy/system views; its ESC handling lives **only** in `App.run()` — not in `PauseMenu.handle_events()`.

### Three-pane system view (`src/gui/game_view.py`)
`GameView` composes three panels:
- **`NavPanel`** (left) — scrollable lists of solar systems and celestial bodies; selected-body stat block
- **`MapPanel`** (right-top) — animated orbital map; supports system view and planet-zoom (double-click planet with moons); click-to-select bodies, right-click to go back
- **`EntitiesPanel`** (bottom) — three-column roster (Structures | Bots | Ships) with counts read live from `GameState.entity_roster`

### Data models (`src/models/`)
- `celestial.py` — `Galaxy → SolarSystem → Star / CelestialBody / Moon`; all support `to_dict()` / `from_dict()` for JSON save/load
- `resource.py` — `Resource` dataclass: minerals, rare_minerals, ice, gas, **bios** (renewable biological feedstock), energy_output
- `entity.py` — `StructureType`, `MegastructureType`, `BotType`, `ShipType`, `BioType` enums; `PowerPlantSpec` / `POWER_PLANT_SPECS` (solar, wind, bios, fossil, nuclear, cold fusion, dark matter); `STARTING_ENTITIES` manifest (4 structures on home planet + 3 ships in home system)
- `tech.py` — `TechNode` dataclass + `TECH_TREE` dict (13 nodes across construction / energy / military / propulsion / special branches); `can_research(tech_id, researched_set)` helper

### GameState (`src/game_state.py`)
Three concerns in one class:
1. **Discovery** — `DiscoveryState` per system (`UNKNOWN → DETECTED → DISCOVERED → COLONIZED`); k=3 adjacency graph drives fog propagation
2. **Entity roster** — `EntityRoster` holds `EntityInstance` stacks (category, type_value, location_id, count); initialised from `STARTING_ENTITIES` in `new_game()`; `roster.total(cat, type_val)` for panel counts
3. **Tech state** — `TechState` tracks `researched: set[str]` and in-progress research points; `can_research()` checks prerequisites; `add_progress()` completes a tech when cost is met

### Procedural generation (`src/generator.py` → `MapGenerator`)
All randomness flows through `self.rng = random.Random(seed)` for full determinism. Calling `MapGenerator(seed=N).generate()` always produces the same galaxy. Star types are weighted by Harvard class rarity; planet subtypes are weighted by orbital radius.

### Shared UI helpers (`src/gui/widgets.py`, `src/gui/constants.py`)
- `Button`, `ScrollableList`, `draw_panel`, `draw_separator` live in `widgets.py`
- All colours, layout constants, and the `font()` cache helper live in `constants.py`
- Do not re-define `draw_separator` locally in other modules — import from `widgets`

### Taskbar (`src/gui/taskbar.py`)
Top bar with four navigation buttons: GALAXY MAP, TECH TREE, ENERGY, QUEUE. Buttons call `app.open_*_view()` / `app._go_galaxy()`. Center label shows breadcrumb ("System > Body") auto-shortened by removing redundant system prefix from body name. Right 280px reserved for game clock overlay.

### Overlay views (`src/gui/tech_view.py`, `energy_view.py`, `queue_view.py`, `entity_view.py`)
All modal overlays share a common protocol:
- `activate()` / `deactivate()` / `is_active: bool` flag
- Registered in `App.__init__`; opened via `app.open_*_view()` methods
- **Mutually exclusive** — opening one deactivates all others (enforced in `App`)
- ESC close priority (highest first): `queue_view` → `energy_view` → `tech_view` → `entity_view` → `pause_menu`
- Rendering order in `App.run()`: base view → tech → energy → queue → tooltip (always last)
- Scroll via `surface.set_clip(content_rect)` + y-offset; do NOT use nested surfaces

### Hit-rect event pattern
Complex views accumulate clickable rectangles during `draw()` instead of recomputing geometry in `handle_events()`:

```python
self._hit_rects: list[tuple[pygame.Rect, str, object]] = []
# In draw():        self._hit_rects.append((rect, action_id, payload))
# In handle_events(): for rect, action, data in self._hit_rects: if rect.collidepoint(pos): ...
```

Do not recompute layout geometry inside event handlers — always use `_hit_rects` populated by `draw()`.

### Toast notifications (`src/gui/app.py`)
Simulation events (`tech_complete`, `entity_built`, `ship_arrived`, `resource_depleted`) are pushed to `game_state.event_queue` by simulation code and dequeued by `App.run()` each tick. Each event renders a fade-out toast in the top-right corner. Do not emit toasts directly from simulation code — push to the queue and let `App` dispatch.

## Commit convention (plan → implement → test flow)

Git log is the primary context recovery mechanism for this project. Every session that implements something **must** end with a descriptive commit using `/commit-impl` (or matching the format manually). The Stop hook auto-commits as a safety net but its messages have minimal context.

### Commit message format

```
<type>(<scope>): <what was done — ≤ 72 chars>

Why: <reason / user story>
What: <2–5 bullet points of key changes>
State: <"X done. Next: Y"> — where in the plan we are

Files: <key files changed>
```

Types: `feat`, `fix`, `refactor`, `test`, `chore`
Scope: `entity-view`, `tech-tree`, `game-state`, `simulation`, `overlay`, `hooks`, etc.

### Agent handoff protocol

When spawning a subagent, always include a `## Context handoff` block in the prompt:

```
## Context handoff
Recent commit: <git log -1 --oneline output>
Just implemented: <1-2 sentences>
Your task: <what the agent should do>
Return: <what you need back — format and content>
```

Agents return a structured `## <agent-name> result` block. Consume it directly — do not re-read files the agent already processed.

### New machine setup

The hook commands in `.claude/settings.json` require an absolute path to the project on the current machine. This path is **not** committed — it lives in `scripts/local.env.sh` (gitignored).

When starting on a new machine:
1. Create `scripts/local.env.sh` with the correct path for that machine:
   ```bash
   #!/usr/bin/env bash
   UA_PROJECT_DIR="/c/Users/<username>/path/to/UniversalAssemblers"
   # UA_PYTHON="/path/to/python.exe"  # uncomment if auto-detection fails
   ```
2. Update every hook command path in `.claude/settings.json` to match `UA_PROJECT_DIR`.
   There are four commands — all follow the pattern `bash <UA_PROJECT_DIR>/scripts/<script>.sh`.
3. Verify hooks are working by editing any `src/` file and checking that `[smoke]` and `[lint]` output appears.

`env.sh` sources `local.env.sh` automatically (if present) and applies `UA_PYTHON` if set. All other paths in the hook scripts are derived dynamically from the script's own location and require no manual changes.

### Context recovery (fresh window or new session)

To rebuild context when starting fresh:
1. Read `CLAUDE.md` — architecture, patterns, current implementation status
2. Run `git log --oneline -10` — what has been done recently
3. Run `git show HEAD --stat` — what the last session changed
4. Check `Not yet implemented` section — what remains

## After implementing features

After writing or modifying any logic in `src/models/`, `src/game_state.py`, `src/generator.py`, or `src/simulation.py`, **spawn the test-updater agent**:

```
Use the Agent tool with subagent_type "test-updater". Tell it which files were changed and what was implemented. It will add assertions to scripts/unit_tests.py, run the tests, and report lint findings.
```

Do not spawn the agent for GUI-only changes (`src/gui/`) — GUI code is not testable headlessly.

The linter also runs automatically as a PostToolUse hook on every `src/` edit — check hook output for `[lint]` lines.

## Key design rules (from game spec)

- **Orbital structures** are rendered as **squares** (⬡) on the system map; planets/moons as circles
- A single square represents all structures orbiting a star; clicking it opens the structure menu
- Players cannot enter or see details of any system until visited by a Probe
- Tech tree nodes require all prerequisites researched before unlocking; multiple Research Arrays can work on different adjacent nodes simultaneously
- Research Arrays contribute to the global tech pool (not per-system)
- Power plants: solar, wind, bios are renewable; fossil fuels, nuclear, cold fusion consume finite resources
- Megastructures (`MegastructureType`) are a separate category from standard structures — different entity view, different rendering rules; Dyson Sphere alters star visual and decays planets
- Drop Ships path to a target system+body; on arrival they convert into 1 Constructor bot + 1 Miner bot
- Bios entities (primitive / uplifted) are engine-managed; uplifted types can damage player entities

## Implementation status

**Implemented:**
- Procedural galaxy generation, all data models, fog-of-war discovery
- Full entity type enums including `MegastructureType` and `BioType`
- Full tech tree data model with prerequisites and branch metadata
- `EntityRoster` + `TechState` in `GameState`; roster initialised from `STARTING_ENTITIES` on new game
- `EntitiesPanel` reads live counts from `entity_roster`
- `bios` resource field visible in nav panel stats
- Entity view UI (`entity_view.py`) — per-category views for structures, bots, ships, bios; task/recipe/ship forms; power plant toggles; extractor refine mode; ship dispatch with system/body selector and ETA
- Tech tree UI (`tech_view.py`) — full overlay with node cards by branch, research assignment, progress bars
- Global task queue UI (`queue_view.py`) — overlay showing bot tasks, factory tasks, shipyard queues; filterable by system
- Energy overview (`energy_view.py`) — per-body production/consumption balance; offline plant warnings
- Taskbar (`taskbar.py`) — top nav bar; breadcrumb label; game clock
- Toast notification system in `App` — fade-out toasts for simulation events

**Not yet implemented:**
- Orbital structure square icon on system map
- Megastructure special rendering (Dyson Sphere star/planet decay)
- Drop Ship pathfinding and impact conversion
- Probe exploration gating (system bodies hidden until visited)
- Bios entity simulation
- Resource consumption simulation (power plants burning gas/ice/rare minerals)
- Save/load of entity roster and tech state
