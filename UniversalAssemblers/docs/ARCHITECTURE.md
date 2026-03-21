# Architecture

## State machine (`src/gui/app.py` → `App`)
The `App` class owns the pygame window and drives a three-state machine:
- `"menu"` — `MainMenu`
- `"galaxy"` — `GalaxyView` (fog-of-war map of all systems)
- `"system"` — `GameView` (three-pane in-system interface)

`App.run()` processes events globally first (ESC, spacebar, speed badge click), then dispatches to the active view. The pause menu (`PauseMenu`) is an overlay rendered on top of galaxy/system views; its ESC handling lives **only** in `App.run()` — not in `PauseMenu.handle_events()`.

## Three-pane system view (`src/gui/game_view.py`)
`GameView` composes three panels:
- **`NavPanel`** (left) — scrollable lists of solar systems and celestial bodies; selected-body stat block
- **`MapPanel`** (right-top) — animated orbital map; supports system view and planet-zoom (double-click planet with moons); click-to-select bodies, right-click to go back
- **`EntitiesPanel`** (bottom) — three-column roster (Structures | Bots | Ships) with counts read live from `GameState.entity_roster`

## Data models (`src/models/`)
- `celestial.py` — `Galaxy → SolarSystem → Star / CelestialBody / Moon`; all support `to_dict()` / `from_dict()` for JSON save/load
- `resource.py` — `Resource` dataclass: minerals, rare_minerals, ice, gas, **bios** (renewable biological feedstock), energy_output
- `entity.py` — `StructureType`, `MegastructureType`, `BotType`, `ShipType`, `BioType` enums; `PowerPlantSpec` / `POWER_PLANT_SPECS` (solar, wind, bios, fossil, nuclear, cold fusion, dark matter); `STARTING_ENTITIES` manifest (4 structures on home planet + 3 ships in home system)
- `tech.py` — `TechNode` dataclass + `TECH_TREE` dict (13 nodes across construction / energy / military / propulsion / special branches); `can_research(tech_id, researched_set)` helper

## GameState (`src/game_state.py`)
Three concerns in one class:
1. **Discovery** — `DiscoveryState` per system (`UNKNOWN → DETECTED → DISCOVERED → COLONIZED`); k=3 adjacency graph drives fog propagation
2. **Entity roster** — `EntityRoster` holds `EntityInstance` stacks (category, type_value, location_id, count); initialised from `STARTING_ENTITIES` in `new_game()`; `roster.total(cat, type_val)` for panel counts
3. **Tech state** — `TechState` tracks `researched: set[str]` and in-progress research points; `can_research()` checks prerequisites; `add_progress()` completes a tech when cost is met

## Procedural generation (`src/generator.py` → `MapGenerator`)
All randomness flows through `self.rng = random.Random(seed)` for full determinism. Calling `MapGenerator(seed=N).generate()` always produces the same galaxy. Star types are weighted by Harvard class rarity; planet subtypes are weighted by orbital radius.

## Shared UI helpers (`src/gui/widgets.py`, `src/gui/constants.py`)
- `Button`, `ScrollableList`, `draw_panel`, `draw_separator` live in `widgets.py`
- All colours, layout constants, and the `font()` cache helper live in `constants.py`
- Do not re-define `draw_separator` locally in other modules — import from `widgets`

## Taskbar (`src/gui/taskbar.py`)
Top bar with four navigation buttons: GALAXY MAP, TECH TREE, ENERGY, QUEUE. Buttons call `app.open_*_view()` / `app._go_galaxy()`. Center label shows breadcrumb ("System > Body") auto-shortened by removing redundant system prefix from body name. Right 280px reserved for game clock overlay.

## Overlay views (`src/gui/tech_view.py`, `energy_view.py`, `queue_view.py`, `entity_view.py`)
All modal overlays share a common protocol:
- `activate()` / `deactivate()` / `is_active: bool` flag
- Registered in `App.__init__`; opened via `app.open_*_view()` methods
- **Mutually exclusive** — opening one deactivates all others (enforced in `App`)
- ESC close priority (highest first): `queue_view` → `energy_view` → `tech_view` → `entity_view` → `pause_menu`
- Rendering order in `App.run()`: base view → tech → energy → queue → tooltip (always last)
- Scroll via `surface.set_clip(content_rect)` + y-offset; do NOT use nested surfaces

## Hit-rect event pattern
Complex views accumulate clickable rectangles during `draw()` instead of recomputing geometry in `handle_events()`:

```python
self._hit_rects: list[tuple[pygame.Rect, str, object]] = []
# In draw():        self._hit_rects.append((rect, action_id, payload))
# In handle_events(): for rect, action, data in self._hit_rects: if rect.collidepoint(pos): ...
```

Do not recompute layout geometry inside event handlers — always use `_hit_rects` populated by `draw()`.

## Toast notifications (`src/gui/app.py`)
Simulation events (`tech_complete`, `entity_built`, `ship_arrived`, `resource_depleted`) are pushed to `game_state.event_queue` by simulation code and dequeued by `App.run()` each tick. Each event renders a fade-out toast in the top-right corner. Do not emit toasts directly from simulation code — push to the queue and let `App` dispatch.
