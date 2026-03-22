---
name: write-unit-test
description: Guide for writing unit tests in the Universal Assemblers codebase. Use when adding new assertions to scripts/unit_tests.py.
---

# Writing unit tests for Universal Assemblers

## Test file: `scripts/unit_tests.py`

This file is the persistent, hand-maintained unit test suite. It is **not** auto-generated.

`scripts/smoke_tests.py` IS auto-generated — never edit it.

## Test style

Tests use a lightweight pass/fail reporter defined at the top of `unit_tests.py`:

```python
def ok(label: str) -> None:   ...  # increments _passed
def fail(label: str, msg: str) -> None:  ...  # increments _failed
def section(title: str) -> None:  ...  # prints a section header
```

Each test assertion follows this pattern:

```python
try:
    # arrange
    roster = EntityRoster()
    roster.add(EntityInstance("bot", "miner", "sys_0/body_0", 3))

    # act + assert
    assert roster.total("bot", "miner") == 3, "count should match what was added"
    ok("roster total matches added count")
except AssertionError as e:
    fail("roster total matches added count", str(e))
except Exception as e:
    fail("roster total matches added count", f"unexpected exception: {e}")
```

## What to test

**Do test** (headless, model/logic layer):
- `src/game_state.py` — `EntityRoster`, `TechState`, `DiscoveryState`, `GameState.new_game()`
- `src/models/tech.py` — `can_research()`, `TECH_TREE` structure
- `src/models/entity.py` — enum values, `STARTING_ENTITIES`, `POWER_PLANT_SPECS`
- `src/models/celestial.py` — `to_dict()` / `from_dict()` round-trips
- `src/generator.py` — determinism, system counts
- `src/simulation.py` — tick logic, energy balance calculations

**Do NOT test** (require display or are too stateful):
- Any class in `src/gui/` — pygame rendering requires a display
- `App`, `GameView`, `MapPanel`, overlay views — these need pygame initialized

## Key import pattern

All test files start with:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

Then import from `src.*` directly.

## Fresh GameState helper

Use `_fresh_gs()` if it's already defined in the file, or create a local helper:

```python
def _fresh_gs():
    gen = MapGenerator(seed=1, num_solar_systems=3)
    return GameState.new_game(gen.generate())
```

Always use a small `num_solar_systems` (3-5) to keep tests fast.

## Section placement

Add a new section at the **end** of the file, just before the `── Summary ──` block:

```python
section("YourNewFeature")

try:
    ...
    ok("descriptive label")
except AssertionError as e:
    fail("descriptive label", str(e))
```

## Good test labels

Labels should read like a sentence fragment describing the invariant:
- `"factory starts with count 1"` ✓
- `"test1"` ✗
- `"advanced_construction locked without prereqs"` ✓
- `"prereq check"` ✗

## Running tests

```bash
cd ~/universal-assemblers/UniversalAssemblers && ~/anaconda3/python.exe scripts/unit_tests.py 2>&1
```
