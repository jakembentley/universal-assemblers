# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the game (Windows — python/python3 aliases are broken; use full Anaconda path)
/c/Users/Admin/anaconda3/python.exe run_gui.py

# Generate a map from CLI (no GUI)
/c/Users/Admin/anaconda3/python.exe main.py --seed 42 --systems 15

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

**Not yet implemented:**
- Entity view UI (click entity → dedicated view)
- Bot task list / percentage-allocation UI
- Ship task queue UI
- Tech tree UI (node browser, research assignment, progress display)
- Orbital structure square icon on system map
- Megastructure special rendering (Dyson Sphere star/planet decay)
- Drop Ship pathfinding and impact conversion
- Probe exploration gating (system bodies hidden until visited)
- Bios entity simulation
- Resource consumption simulation (power plants burning gas/ice/rare minerals)
- Save/load of entity roster and tech state
