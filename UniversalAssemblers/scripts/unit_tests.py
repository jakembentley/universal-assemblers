"""
Unit tests for Universal Assemblers model/logic layer.

Unlike smoke_tests.py (which is auto-generated), this file is maintained by hand
and extended by the test-updater agent when new features are implemented.

Run:
    ~/anaconda3/python.exe scripts/unit_tests.py

Exit 0 = all passed.  Exit 1 = failure with message.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_passed = 0
_failed = 0

def ok(label: str) -> None:
    global _passed
    _passed += 1
    print(f"  PASS  {label}")

def fail(label: str, msg: str) -> None:
    global _failed
    _failed += 1
    print(f"  FAIL  {label}: {msg}")

def section(title: str) -> None:
    print(f"\n-- {title} --")


# ─── Helpers ─────────────────────────────────────────────────────────────────

from src.game_state import GameState
from src.generator import MapGenerator

def _fresh_gs():
    gen = MapGenerator(seed=1, num_solar_systems=3)
    return GameState.new_game(gen.generate())


# ─── TechState ───────────────────────────────────────────────────────────────
section("TechState")

from src.models.tech import TECH_TREE, can_research

# structure_modules has no prerequisites — should be available immediately
try:
    assert can_research("structure_modules", set()), \
        "structure_modules should be available with no prereqs"
    ok("structure_modules available immediately")
except AssertionError as e:
    fail("structure_modules available check", str(e))

# multi_component_structures requires structure_modules
try:
    assert not can_research("multi_component_structures", set()), \
        "multi_component_structures should be locked without structure_modules"
    ok("multi_component_structures locked without prereqs")
except AssertionError as e:
    fail("multi_component_structures prereq check", str(e))

try:
    assert can_research("multi_component_structures", {"structure_modules"}), \
        "multi_component_structures should unlock after structure_modules"
    ok("multi_component_structures unlocks after prereq")
except AssertionError as e:
    fail("multi_component_structures unlock check", str(e))

# Unknown tech ID should return False
try:
    assert not can_research("nonexistent_tech", set()), \
        "unknown tech_id should return False"
    ok("unknown tech_id returns False")
except AssertionError as e:
    fail("unknown tech_id check", str(e))

# TechState on new game
gs = _fresh_gs()
try:
    assert gs.tech is not None, "TechState should exist"
    ok("TechState exists on new game")
except AssertionError as e:
    fail("TechState existence", str(e))

try:
    assert len(gs.tech.researched) == 0, "No techs researched at game start"
    ok("no techs pre-researched at start")
except AssertionError as e:
    fail("TechState initial state", str(e))

# TechState.start_research / add_progress
gs2 = _fresh_gs()
try:
    started = gs2.tech.start_research("structure_modules")
    assert started, "start_research should return True for available tech"
    ok("start_research returns True for available tech")
except AssertionError as e:
    fail("start_research available", str(e))

try:
    started_again = gs2.tech.start_research("structure_modules")
    assert started_again, "calling start_research twice is idempotent"
    ok("start_research is idempotent")
except AssertionError as e:
    fail("start_research idempotent", str(e))

try:
    cost = TECH_TREE["structure_modules"].research_cost
    completed = gs2.tech.add_progress("structure_modules", cost)
    assert completed, "add_progress should return True when cost met"
    assert "structure_modules" in gs2.tech.researched, "tech should be in researched set"
    ok("add_progress completes tech at full cost")
except AssertionError as e:
    fail("add_progress completion", str(e))

try:
    assert not gs2.tech.can_research("structure_modules"), \
        "already-researched tech should return False from can_research"
    ok("can_research returns False for already-researched tech")
except AssertionError as e:
    fail("can_research already researched", str(e))

try:
    frac = gs2.tech.progress_fraction("structure_modules")
    assert frac == 1.0, f"researched tech progress should be 1.0, got {frac}"
    ok("progress_fraction is 1.0 for researched tech")
except AssertionError as e:
    fail("progress_fraction completed", str(e))


# ─── EntityRoster ─────────────────────────────────────────────────────────────
section("EntityRoster")

from src.game_state import EntityRoster
from src.models.entity import StructureType, BotType, ShipType

roster = EntityRoster()
try:
    roster.add("structure", StructureType.FACTORY.value, "sys_0/body_0", 1)
    assert roster.total("structure", StructureType.FACTORY.value) == 1
    ok("add and total single entity")
except Exception as e:
    fail("add and total single entity", str(e))

try:
    roster.add("structure", StructureType.FACTORY.value, "sys_0/body_0", 2)
    assert roster.total("structure", StructureType.FACTORY.value) == 3, \
        "second add to same location should accumulate"
    ok("accumulates count on same location")
except Exception as e:
    fail("accumulate count same location", str(e))

try:
    roster.add("structure", StructureType.FACTORY.value, "sys_1/body_0", 5)
    assert roster.total("structure", StructureType.FACTORY.value) == 8, \
        "total should sum across all locations"
    ok("total sums across multiple locations")
except Exception as e:
    fail("total across locations", str(e))

try:
    assert roster.total("structure", StructureType.RESEARCH_ARRAY.value) == 0
    ok("total returns 0 for absent entity type")
except Exception as e:
    fail("total absent entity", str(e))

try:
    assert roster.total("bot", BotType.MINER.value) == 0
    ok("total returns 0 across different category")
except Exception as e:
    fail("total cross-category", str(e))

# remove
try:
    removed = roster.remove("structure", StructureType.FACTORY.value, "sys_0/body_0", 1)
    assert removed, "remove should return True when entity exists"
    assert roster.total("structure", StructureType.FACTORY.value) == 7
    ok("remove decrements count")
except Exception as e:
    fail("remove decrements count", str(e))

try:
    over_remove = roster.remove("structure", StructureType.FACTORY.value, "sys_0/body_0", 999)
    assert not over_remove, "remove should return False when count insufficient"
    ok("remove returns False for insufficient count")
except Exception as e:
    fail("remove insufficient count", str(e))

# by_category and at
try:
    by_cat = roster.by_category("structure")
    assert all(i.category == "structure" for i in by_cat)
    ok("by_category returns only matching category")
except Exception as e:
    fail("by_category", str(e))

try:
    at_loc = roster.at("sys_0/body_0")
    assert all(i.location_id == "sys_0/body_0" for i in at_loc)
    ok("at returns only matching location")
except Exception as e:
    fail("at location filter", str(e))


# ─── MapGenerator determinism ─────────────────────────────────────────────────
section("MapGenerator determinism")

try:
    g1 = MapGenerator(seed=42, num_solar_systems=5).generate()
    g2 = MapGenerator(seed=42, num_solar_systems=5).generate()
    names1 = sorted(s.name for s in g1.solar_systems)
    names2 = sorted(s.name for s in g2.solar_systems)
    assert names1 == names2, "Same seed should produce same system names"
    ok("same seed produces same galaxy")
except AssertionError as e:
    fail("determinism same seed", str(e))

try:
    g3 = MapGenerator(seed=99, num_solar_systems=5).generate()
    names3 = sorted(s.name for s in g3.solar_systems)
    assert names1 != names3, "Different seeds should produce different galaxies"
    ok("different seed produces different galaxy")
except AssertionError as e:
    fail("determinism different seed", str(e))

try:
    g4 = MapGenerator(seed=42, num_solar_systems=5).generate()
    # Generator may add bonus/warp-only systems; count is at least the requested number
    assert len(g4.solar_systems) >= 5, \
        f"expected >= 5 systems, got {len(g4.solar_systems)}"
    ok(f"generator produces >= requested system count (got {len(g4.solar_systems)})")
except AssertionError as e:
    fail("system count", str(e))


# ─── DiscoveryState ───────────────────────────────────────────────────────────
section("DiscoveryState")

from src.game_state import DiscoveryState

gs3 = _fresh_gs()
home_id = gs3.galaxy.solar_systems[0].id  # home_idx=0 by default in new_game()

try:
    lvl = gs3.get_state(home_id)
    assert lvl == DiscoveryState.COLONIZED, \
        f"Home system should start COLONIZED, got {lvl}"
    ok("home system starts COLONIZED")
except AssertionError as e:
    fail("home system discovery level", str(e))

try:
    all_ids = [s.id for s in gs3.galaxy.solar_systems]
    non_home = [sid for sid in all_ids if sid != home_id]
    if non_home:
        lvl = gs3.get_state(non_home[0])
        assert lvl in (DiscoveryState.UNKNOWN, DiscoveryState.DETECTED), \
            f"Non-home system should start UNKNOWN or DETECTED, got {lvl}"
        ok("non-home system starts UNKNOWN or DETECTED")
except AssertionError as e:
    fail("non-home system discovery level", str(e))

try:
    assert gs3.can_enter(home_id), "home system should be enterable"
    ok("home system is enterable")
except AssertionError as e:
    fail("home system enterable", str(e))

try:
    discovered = gs3.discovered_count()
    assert discovered >= 1, "at least home system should be discovered"
    ok(f"discovered_count >= 1 (got {discovered})")
except AssertionError as e:
    fail("discovered_count", str(e))

# discover_system propagates DETECTED to neighbors
try:
    non_home2 = [s.id for s in gs3.galaxy.solar_systems if s.id != home_id]
    # find an UNKNOWN system
    unknown_ids = [sid for sid in non_home2 if gs3.get_state(sid) == DiscoveryState.UNKNOWN]
    if unknown_ids:
        target = unknown_ids[0]
        gs3.discover_system(target)
        assert gs3.get_state(target) == DiscoveryState.DISCOVERED, \
            "discover_system should set state to DISCOVERED"
        ok("discover_system sets state to DISCOVERED")
    else:
        ok("discover_system propagation skipped (no UNKNOWN systems in 3-system galaxy)")
except AssertionError as e:
    fail("discover_system", str(e))


# ─── TECH_TREE completeness ───────────────────────────────────────────────────
section("TECH_TREE structure")

try:
    assert len(TECH_TREE) >= 13, f"Expected >= 13 nodes, got {len(TECH_TREE)}"
    ok(f"TECH_TREE has {len(TECH_TREE)} nodes")
except AssertionError as e:
    fail("TECH_TREE size", str(e))

try:
    for tech_id, node in TECH_TREE.items():
        for prereq in node.prerequisites:
            assert prereq in TECH_TREE, \
                f"{tech_id} has unknown prereq '{prereq}'"
    ok("all prerequisites reference valid tech IDs")
except AssertionError as e:
    fail("prerequisite references valid", str(e))

try:
    branches = {node.branch for node in TECH_TREE.values()}
    assert len(branches) >= 3, f"Expected >= 3 branches, got {branches}"
    ok(f"TECH_TREE has {len(branches)} branches: {sorted(branches)}")
except AssertionError as e:
    fail("TECH_TREE branches", str(e))

try:
    root_nodes = [tid for tid, node in TECH_TREE.items() if not node.prerequisites]
    assert len(root_nodes) >= 2, \
        f"Expected >= 2 root nodes (no prereqs), got {root_nodes}"
    ok(f"{len(root_nodes)} root nodes available immediately")
except AssertionError as e:
    fail("TECH_TREE root nodes", str(e))


# ─── Summary ─────────────────────────────────────────────────────────────────
print(f"\n{'-'*50}")
print(f"Unit tests: {_passed} passed, {_failed} failed")
if _failed > 0:
    sys.exit(1)
print("All unit tests OK.")
