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


# ─── GameState.shortest_path ──────────────────────────────────────────────────
section("GameState.shortest_path")

from src.simulation import ShipOrder, OrderQueue

gs_sp = _fresh_gs()
all_sys_ids = [s.id for s in gs_sp.galaxy.solar_systems]
home_sp = all_sys_ids[0]

try:
    path = gs_sp.shortest_path(home_sp, home_sp)
    assert path == [home_sp], f"same-node path should be [node], got {path}"
    ok("shortest_path(a, a) returns [a]")
except AssertionError as e:
    fail("shortest_path same node", str(e))

try:
    neighbors = gs_sp.adjacency.get(home_sp, [])
    if neighbors:
        neighbor = neighbors[0]
        path = gs_sp.shortest_path(home_sp, neighbor)
        assert len(path) == 2, f"adjacent path length should be 2, got {len(path)}"
        assert path[0] == home_sp, "path should start at home"
        assert path[1] == neighbor, "path should end at neighbor"
        ok("shortest_path to adjacent system returns 2-element list")
    else:
        ok("shortest_path adjacent skipped (home has no neighbors in tiny galaxy)")
except AssertionError as e:
    fail("shortest_path adjacent", str(e))

try:
    # Find a system reachable from home (may be 2+ hops in a larger galaxy)
    far_id = None
    for sid in all_sys_ids:
        if sid != home_sp:
            far_id = sid
            break
    if far_id:
        path = gs_sp.shortest_path(home_sp, far_id)
        assert path[0] == home_sp, "path must start at home"
        assert path[-1] == far_id, "path must end at far system"
        ok("shortest_path first/last elements are correct")
    else:
        ok("shortest_path far-system skipped (single-system galaxy)")
except AssertionError as e:
    fail("shortest_path start/end", str(e))

try:
    if far_id:
        path = gs_sp.shortest_path(home_sp, far_id)
        valid_ids = {s.id for s in gs_sp.galaxy.solar_systems}
        assert all(sid in valid_ids for sid in path), \
            f"path contains unknown system IDs: {[sid for sid in path if sid not in valid_ids]}"
        ok("shortest_path contains only valid system IDs")
    else:
        ok("shortest_path valid IDs skipped (single-system galaxy)")
except AssertionError as e:
    fail("shortest_path valid IDs", str(e))


# ─── GameState.check_victory (technology) ─────────────────────────────────────
section("GameState.check_victory (technology)")

from src.models.tech import TECH_TREE

gs_cv = _fresh_gs()

try:
    result = gs_cv.check_victory()
    assert result is None, f"fresh game should return None from check_victory, got {result!r}"
    ok("check_victory returns None on fresh game")
except AssertionError as e:
    fail("check_victory fresh game", str(e))

try:
    # Manually mark all tech nodes as researched
    gs_cv.tech.researched = set(TECH_TREE.keys())
    result = gs_cv.check_victory()
    assert result == "technology", \
        f"all techs researched should return 'technology', got {result!r}"
    ok("check_victory returns 'technology' when all techs researched")
except AssertionError as e:
    fail("check_victory technology", str(e))


# ─── GameState.check_victory (domination) ─────────────────────────────────────
section("GameState.check_victory (domination)")

from src.game_state import DiscoveryState

# Use a galaxy large enough to have >= 3 discovered systems
from src.generator import MapGenerator as _MG
_gen_dom = _MG(seed=7, num_solar_systems=6)
gs_dom = GameState.new_game(_gen_dom.generate())

try:
    # Discover all systems so discovered_count >= 3
    for sol in gs_dom.galaxy.solar_systems:
        gs_dom._states[sol.id] = DiscoveryState.DISCOVERED
    # Mark home as COLONIZED so it counts too
    home_dom = gs_dom.galaxy.solar_systems[0].id
    gs_dom._states[home_dom] = DiscoveryState.COLONIZED

    discovered_systems = [
        s for s in gs_dom.galaxy.solar_systems
        if gs_dom._states.get(s.id) in (DiscoveryState.DISCOVERED, DiscoveryState.COLONIZED)
    ]
    needed = max(1, int(len(discovered_systems) * 0.6) + 1)

    # Place structures on bodies in enough systems to exceed 60% threshold
    placed = 0
    for sol in discovered_systems:
        if placed >= needed:
            break
        if sol.orbital_bodies:
            body = sol.orbital_bodies[0]
            gs_dom.entity_roster.add("structure", "factory", body.id, 1)
            placed += 1

    result = gs_dom.check_victory()
    assert result == "domination", \
        f"domination should trigger when entities in >=60% systems, got {result!r}"
    ok("check_victory returns 'domination' with entities in 60%+ of systems")
except AssertionError as e:
    fail("check_victory domination", str(e))


# ─── GameState serialization round-trip (order_queue) ─────────────────────────
section("GameState serialization round-trip (order_queue)")

gs_rt = _fresh_gs()
home_rt = gs_rt.galaxy.solar_systems[0].id

try:
    waypoints_data = [home_rt, "sys_far"]
    order = ShipOrder(
        order_type="travel",
        target_system_id="sys_far",
        travel_speed=0.5,
        progress=0.25,
        waypoints=waypoints_data,
        current_waypoint_idx=1,
    )
    gs_rt.order_queue.enqueue(home_rt, "probe", order)

    saved = gs_rt.to_dict()
    gs_rt2 = GameState.from_dict(saved, gs_rt.galaxy)

    restored_order = gs_rt2.order_queue.peek(home_rt, "probe")
    assert restored_order is not None, "order should survive serialization round-trip"
    ok("ShipOrder survives to_dict/from_dict round-trip")
except AssertionError as e:
    fail("order_queue round-trip presence", str(e))
except Exception as e:
    fail("order_queue round-trip", str(e))

try:
    restored_order2 = gs_rt2.order_queue.peek(home_rt, "probe")
    assert restored_order2 is not None, "need restored order for waypoints check"
    assert restored_order2.waypoints == waypoints_data, \
        f"waypoints should survive round-trip, got {restored_order2.waypoints!r}"
    ok("ShipOrder.waypoints field survives round-trip")
except AssertionError as e:
    fail("order_queue waypoints round-trip", str(e))

try:
    restored_order3 = gs_rt2.order_queue.peek(home_rt, "probe")
    assert restored_order3 is not None, "need restored order for waypoint_idx check"
    assert restored_order3.current_waypoint_idx == 1, \
        f"current_waypoint_idx should be 1, got {restored_order3.current_waypoint_idx}"
    ok("ShipOrder.current_waypoint_idx survives round-trip")
except AssertionError as e:
    fail("order_queue current_waypoint_idx round-trip", str(e))


# ─── SimulationEngine._tick_bios returns list ─────────────────────────────────
section("SimulationEngine._tick_bios returns list")

gs_bio = _fresh_gs()

try:
    result = gs_bio.sim_engine._tick_bios(1.0)
    assert isinstance(result, list), \
        f"_tick_bios should return a list, got {type(result).__name__}"
    ok("_tick_bios returns a list")
except AssertionError as e:
    fail("_tick_bios return type", str(e))

try:
    result2 = gs_bio.sim_engine._tick_bios(0.0)
    assert isinstance(result2, list), "_tick_bios(0.0) should return a list"
    ok("_tick_bios(0.0) returns a list")
except AssertionError as e:
    fail("_tick_bios zero dt", str(e))


# ─── ShipOrder waypoints ───────────────────────────────────────────────────────
section("ShipOrder waypoints")

try:
    so = ShipOrder(
        target_system_id="sys_abc",
        waypoints=["sys_home", "sys_mid", "sys_abc"],
        current_waypoint_idx=0,
    )
    assert so.waypoints == ["sys_home", "sys_mid", "sys_abc"], "waypoints not stored correctly"
    assert so.current_waypoint_idx == 0, "current_waypoint_idx should be 0"
    ok("ShipOrder stores waypoints and current_waypoint_idx")
except AssertionError as e:
    fail("ShipOrder waypoints field", str(e))

try:
    oq_test = OrderQueue()
    oq_test.enqueue("loc_a", "probe", so)
    d = oq_test.to_dict()
    oq_test2 = OrderQueue.from_dict(d)
    restored_so = oq_test2.peek("loc_a", "probe")
    assert restored_so is not None, "order should be present after from_dict"
    assert restored_so.waypoints == ["sys_home", "sys_mid", "sys_abc"], \
        f"waypoints should survive OrderQueue serialization, got {restored_so.waypoints!r}"
    assert restored_so.current_waypoint_idx == 0, \
        f"current_waypoint_idx should be 0, got {restored_so.current_waypoint_idx}"
    ok("ShipOrder with waypoints survives OrderQueue serialization")
except AssertionError as e:
    fail("ShipOrder waypoints serialization", str(e))


# ─── GameState.apply_damage / health_fraction ────────────────────────────────
section("GameState.apply_damage / health_fraction")

from src.simulation import BioPopulation, BioState
from src.models.entity import BioType

gs_dmg = _fresh_gs()
# Place a stack of 2 factories at a test body for damage tests
_dmg_body = "test_body_dmg"
gs_dmg.entity_roster.add("structure", "factory", _dmg_body, 2)

# Undamaged entity → health_fraction 1.0
try:
    hf = gs_dmg.health_fraction(_dmg_body, "structure", "factory")
    assert hf == 1.0, f"undamaged health_fraction should be 1.0, got {hf}"
    ok("health_fraction on undamaged entity returns 1.0")
except AssertionError as e:
    fail("health_fraction undamaged", str(e))

# apply_damage with amount < 100 → returns False, health_fraction < 1.0
try:
    destroyed = gs_dmg.apply_damage(_dmg_body, "structure", "factory", 50)
    assert not destroyed, "damage < 100 should return False (not destroyed)"
    hf = gs_dmg.health_fraction(_dmg_body, "structure", "factory")
    assert hf < 1.0, f"health_fraction should be < 1.0 after partial damage, got {hf}"
    ok("apply_damage(<100) returns False, health_fraction < 1.0")
except AssertionError as e:
    fail("apply_damage partial", str(e))

# apply_damage with amount = 100 → returns True (one unit destroyed), count decremented
try:
    gs_dmg2 = _fresh_gs()
    gs_dmg2.entity_roster.add("structure", "factory", _dmg_body, 1)
    pre_count = gs_dmg2.entity_roster.total("structure", "factory")
    destroyed2 = gs_dmg2.apply_damage(_dmg_body, "structure", "factory", 100)
    post_count = gs_dmg2.entity_roster.total("structure", "factory")
    assert destroyed2, "damage = 100 should return True (entity destroyed)"
    assert post_count == pre_count - 1, \
        f"entity count should decrement by 1, was {pre_count}, now {post_count}"
    ok("apply_damage(100) returns True, entity count decremented")
except AssertionError as e:
    fail("apply_damage(100) destroys entity", str(e))

# apply_damage on non-existent entity → returns False gracefully
try:
    result = gs_dmg.apply_damage("nonexistent_body", "structure", "factory", 50)
    assert result is False, f"apply_damage on non-existent entity should return False, got {result}"
    ok("apply_damage on non-existent entity returns False gracefully")
except AssertionError as e:
    fail("apply_damage non-existent entity", str(e))
except Exception as e:
    fail("apply_damage non-existent entity (exception)", str(e))

# Cumulative damage: two calls of 60 each → entity destroyed after second call
try:
    gs_dmg3 = _fresh_gs()
    _dmg_body3 = "test_body_cumul"
    gs_dmg3.entity_roster.add("structure", "factory", _dmg_body3, 1)
    r1 = gs_dmg3.apply_damage(_dmg_body3, "structure", "factory", 60)
    assert not r1, "first 60-damage call should NOT destroy the entity"
    r2 = gs_dmg3.apply_damage(_dmg_body3, "structure", "factory", 60)
    assert r2, "second 60-damage call (total 120) should destroy the entity"
    # Check count at the specific body (not global total, which may include starting entities)
    at_body = [i for i in gs_dmg3.entity_roster.at(_dmg_body3)
               if i.category == "structure" and i.type_value == "factory"]
    assert len(at_body) == 0, \
        "factory stack at test body should be empty after cumulative destruction"
    ok("cumulative damage (60 + 60) destroys entity on second call")
except AssertionError as e:
    fail("cumulative damage", str(e))


# ─── SimulationEngine._tick_bios events ──────────────────────────────────────
section("SimulationEngine._tick_bios events")

# Test: uplifted bio with aggression=1.0 + player entities at same body → attack event
try:
    gs_bio2 = _fresh_gs()
    _bio_body = "bio_attack_body"
    gs_bio2.entity_roster.add("structure", "extractor", _bio_body, 2)
    # Inject an uplifted bio at that body with max aggression and large population
    atk_pop = BioPopulation(
        body_id=_bio_body,
        system_id="any_sys",
        bio_type=BioType.UPLIFTED,
        population=5000.0,
        aggression=1.0,
        growth_rate=0.01,
    )
    gs_bio2.bio_state.add(atk_pop)
    # Run many ticks to ensure the probabilistic attack fires
    found_attack = False
    for _ in range(200):
        evs = gs_bio2.sim_engine._tick_bios(1.0)
        if any(e.get("type") in ("bios_entity_damaged", "bios_entity_destroyed")
               for e in evs):
            found_attack = True
            break
    assert found_attack, \
        "uplifted bio (aggression=1.0, pop=5000) should produce attack events within 200 ticks"
    ok("uplifted bio with aggression=1.0 generates attack events")
except AssertionError as e:
    fail("_tick_bios uplifted attack", str(e))

# Test: primitive bio + ≥3 structures → mutation event can be generated
try:
    gs_bio3 = _fresh_gs()
    _mut_body = "mutation_test_body"
    # Place 3 structures at the body
    gs_bio3.entity_roster.add("structure", "factory", _mut_body, 3)
    # Inject a primitive bio with high aggression (doesn't affect mutation, but set for clarity)
    mut_pop = BioPopulation(
        body_id=_mut_body,
        system_id="any_sys",
        bio_type=BioType.PRIMITIVE,
        population=1000.0,
        aggression=0.8,
        growth_rate=0.01,
    )
    gs_bio3.bio_state.add(mut_pop)
    # Run many ticks looking for a mutation event
    found_mutation = False
    for _ in range(5000):
        evs = gs_bio3.sim_engine._tick_bios(1.0)
        if any(e.get("type") == "bios_mutation" for e in evs):
            found_mutation = True
            break
    assert found_mutation, \
        "primitive bio near 3+ structures should eventually trigger bios_mutation event"
    ok("primitive bio near 3+ structures generates bios_mutation event")
except AssertionError as e:
    fail("_tick_bios mutation", str(e))


# ─── GameState serialization round-trip (entity_damage + bio_state) ───────────
section("GameState serialization round-trip (entity_damage + bio_state)")

# entity_damage round-trip
try:
    gs_rt2 = _fresh_gs()
    _rt_body = "rt_test_body"
    gs_rt2.entity_roster.add("structure", "factory", _rt_body, 2)
    gs_rt2.apply_damage(_rt_body, "structure", "factory", 45)
    pre_dmg = dict(gs_rt2.entity_damage)

    saved_d = gs_rt2.to_dict()
    gs_rt2_loaded = GameState.from_dict(saved_d, gs_rt2.galaxy)

    assert gs_rt2_loaded.entity_damage == pre_dmg, \
        f"entity_damage should survive round-trip: expected {pre_dmg}, got {gs_rt2_loaded.entity_damage}"
    ok("entity_damage survives to_dict/from_dict round-trip")
except AssertionError as e:
    fail("entity_damage round-trip", str(e))
except Exception as e:
    fail("entity_damage round-trip (exception)", str(e))

# bio_state round-trip: bio_type, population, aggression preserved
try:
    gs_rt3 = _fresh_gs()
    _rt_bio_body = "rt_bio_body"
    _rt_sys = gs_rt3.galaxy.solar_systems[0].id
    rt_bio_pop = BioPopulation(
        body_id=_rt_bio_body,
        system_id=_rt_sys,
        bio_type=BioType.UPLIFTED,
        population=999.0,
        aggression=0.77,
        growth_rate=0.03,
    )
    gs_rt3.bio_state.add(rt_bio_pop)

    saved_d3 = gs_rt3.to_dict()
    gs_rt3_loaded = GameState.from_dict(saved_d3, gs_rt3.galaxy)

    restored_pop = gs_rt3_loaded.bio_state.get(_rt_bio_body)
    assert restored_pop is not None, "bio population should exist after round-trip"
    assert restored_pop.bio_type == BioType.UPLIFTED, \
        f"bio_type should be UPLIFTED, got {restored_pop.bio_type}"
    assert abs(restored_pop.population - 999.0) < 1.0, \
        f"population should be ~999.0, got {restored_pop.population}"
    assert abs(restored_pop.aggression - 0.77) < 0.001, \
        f"aggression should be 0.77, got {restored_pop.aggression}"
    ok("bio_state (bio_type, population, aggression) survives to_dict/from_dict round-trip")
except AssertionError as e:
    fail("bio_state round-trip", str(e))
except Exception as e:
    fail("bio_state round-trip (exception)", str(e))


# ─── EntityRoster + TechState + in_game_years save/load round-trip ───────────
section("EntityRoster / TechState / in_game_years save/load round-trip")

# entity_roster: multiple stacks at different locations survive round-trip
try:
    gs_er = _fresh_gs()
    gs_er.entity_roster.add("structure", "factory", "body_a", 3)
    gs_er.entity_roster.add("bot", "miner", "body_a", 2)
    gs_er.entity_roster.add("ship", "probe", "sys_x", 1)

    d_er = gs_er.to_dict()
    gs_er2 = GameState.from_dict(d_er, gs_er.galaxy)

    assert gs_er2.entity_roster.total("structure", "factory") >= 3, \
        "factory count should survive round-trip"
    at_a = {(i.category, i.type_value, i.count) for i in gs_er2.entity_roster.at("body_a")}
    assert ("structure", "factory", 3) in at_a, "factory stack at body_a should survive"
    assert ("bot", "miner", 2) in at_a, "miner stack at body_a should survive"
    probe_at_sys = gs_er2.entity_roster.at("sys_x")
    assert any(i.type_value == "probe" and i.count == 1 for i in probe_at_sys), \
        "probe at sys_x should survive round-trip"
    ok("entity_roster (multi-stack, multi-location) survives save/load round-trip")
except AssertionError as e:
    fail("entity_roster round-trip", str(e))
except Exception as e:
    fail("entity_roster round-trip (exception)", str(e))

# tech state: researched set and in-progress research survive round-trip
try:
    gs_tech = _fresh_gs()
    # Complete structure_modules (no prereqs), partially research energy_efficiency (also no prereqs)
    cost_sm = TECH_TREE["structure_modules"].research_cost
    gs_tech.tech.start_research("structure_modules")
    gs_tech.tech.add_progress("structure_modules", cost_sm)  # fully complete
    gs_tech.tech.start_research("energy_efficiency")
    gs_tech.tech.add_progress("energy_efficiency", 5.0)       # partial progress

    d_tech = gs_tech.to_dict()
    gs_tech2 = GameState.from_dict(d_tech, gs_tech.galaxy)

    assert "structure_modules" in gs_tech2.tech.researched, \
        "completed tech should be in researched set after round-trip"
    assert "energy_efficiency" not in gs_tech2.tech.researched, \
        "partial tech should not be in researched set"
    frac = gs_tech2.tech.progress_fraction("energy_efficiency")
    assert frac > 0.0, f"in-progress tech fraction should be > 0, got {frac}"
    ok("TechState (researched + in-progress) survives save/load round-trip")
except AssertionError as e:
    fail("TechState round-trip", str(e))
except Exception as e:
    fail("TechState round-trip (exception)", str(e))

# in_game_years persists across save/load
try:
    gs_yr = _fresh_gs()
    gs_yr.in_game_years = 42.5
    d_yr = gs_yr.to_dict()
    gs_yr2 = GameState.from_dict(d_yr, gs_yr.galaxy)
    assert abs(gs_yr2.in_game_years - 42.5) < 0.001, \
        f"in_game_years should be 42.5, got {gs_yr2.in_game_years}"
    ok("in_game_years survives save/load round-trip")
except AssertionError as e:
    fail("in_game_years round-trip", str(e))
except Exception as e:
    fail("in_game_years round-trip (exception)", str(e))


# ─── _tick_ships multi-hop waypoint travel ────────────────────────────────────
section("_tick_ships multi-hop waypoint travel")

from src.simulation import SimulationEngine

# Helper: build a minimal GameState with no galaxy but with order_queue + entity_roster
def _gs_for_ships():
    """Minimal GameState-like object good enough for _tick_ships."""
    gs = _fresh_gs()
    return gs

# Test 1: drop ship with 3-waypoint path [A, B, C], first leg completes → moves to B, not converted
try:
    gs_mh1 = _gs_for_ships()
    sys_a = "sys_A"
    sys_b = "sys_B"
    sys_c = "sys_C"
    # Place a drop ship at sys_A
    gs_mh1.entity_roster.add("ship", "drop_ship", sys_a, 1)
    order_mh1 = ShipOrder(
        order_type="travel",
        target_system_id=sys_c,
        target_body_id=None,
        travel_speed=1.0,   # speed=1.0 means one full tick (dt=1.0) completes one leg
        progress=0.0,
        waypoints=[sys_a, sys_b, sys_c],
        current_waypoint_idx=0,
    )
    gs_mh1.order_queue.enqueue(sys_a, "drop_ship", order_mh1)

    # Tick with dt=1.0 → first leg completes
    evs = gs_mh1.sim_engine._tick_ships(1.0)

    # Ship should now be at sys_B
    at_b = [i for i in gs_mh1.entity_roster.at(sys_b)
            if i.category == "ship" and i.type_value == "drop_ship"]
    assert len(at_b) == 1 and at_b[0].count == 1, \
        f"drop ship should be at sys_B after first leg, got {at_b}"
    ok("drop ship moves to mid-waypoint (B) after first leg completes")
except AssertionError as e:
    fail("drop ship first leg -> moves to B", str(e))
except Exception as e:
    fail("drop ship first leg -> moves to B (exception)", str(e))

try:
    # Ship must NOT still be at sys_A
    at_a_after = [i for i in gs_mh1.entity_roster.at(sys_a)
                  if i.category == "ship" and i.type_value == "drop_ship"]
    assert len(at_a_after) == 0, \
        f"drop ship should have left sys_A, but found {at_a_after}"
    ok("drop ship no longer at source (A) after first leg")
except AssertionError as e:
    fail("drop ship leaves A after first leg", str(e))
except Exception as e:
    fail("drop ship leaves A after first leg (exception)", str(e))

try:
    # No drop_ship_arrived event yet (not on final leg)
    arrived_evs = [e for e in evs if e.get("type") == "drop_ship_arrived"]
    assert len(arrived_evs) == 0, \
        f"drop_ship_arrived should NOT be emitted after first leg, got {arrived_evs}"
    ok("no drop_ship_arrived event after first leg")
except AssertionError as e:
    fail("no premature drop_ship_arrived event", str(e))
except Exception as e:
    fail("no premature drop_ship_arrived event (exception)", str(e))

try:
    # No constructor/miner at dest yet
    at_c_bots = [i for i in gs_mh1.entity_roster.at(sys_c)
                 if i.category == "bot"]
    assert len(at_c_bots) == 0, \
        f"no bots should be at sys_C yet, got {at_c_bots}"
    ok("no bots spawned at final destination after first leg")
except AssertionError as e:
    fail("no premature bot spawn", str(e))
except Exception as e:
    fail("no premature bot spawn (exception)", str(e))

try:
    # Order must be re-keyed at sys_B with current_waypoint_idx=1
    order_at_b = gs_mh1.order_queue.peek(sys_b, "drop_ship")
    assert order_at_b is not None, "order should be re-keyed at sys_B"
    assert order_at_b.current_waypoint_idx == 1, \
        f"current_waypoint_idx should be 1 after advancing, got {order_at_b.current_waypoint_idx}"
    assert order_at_b.progress == 0.0, \
        f"progress should be reset to 0.0, got {order_at_b.progress}"
    ok("order re-keyed at B with current_waypoint_idx=1 and progress reset")
except AssertionError as e:
    fail("order re-keyed at B", str(e))
except Exception as e:
    fail("order re-keyed at B (exception)", str(e))

# Test 2: second leg completes → drop ship converts at sys_C
try:
    # Continue the same gs_mh1 from test 1 — ship is now at sys_B with idx=1
    evs2 = gs_mh1.sim_engine._tick_ships(1.0)

    # Constructor and Miner should appear at target_body_id or target_system_id (sys_C)
    at_c_constructor = [i for i in gs_mh1.entity_roster.at(sys_c)
                        if i.category == "bot" and i.type_value == "constructor"]
    at_c_miner = [i for i in gs_mh1.entity_roster.at(sys_c)
                  if i.category == "bot" and i.type_value == "miner"]
    assert len(at_c_constructor) == 1 and at_c_constructor[0].count == 1, \
        f"constructor should be at sys_C, got {at_c_constructor}"
    assert len(at_c_miner) == 1 and at_c_miner[0].count == 1, \
        f"miner should be at sys_C, got {at_c_miner}"
    ok("drop ship converts to constructor + miner at final destination (C)")
except AssertionError as e:
    fail("drop ship conversion at final destination", str(e))
except Exception as e:
    fail("drop ship conversion at final destination (exception)", str(e))

try:
    arrived_evs2 = [e for e in evs2 if e.get("type") == "drop_ship_arrived"]
    assert len(arrived_evs2) == 1, \
        f"exactly one drop_ship_arrived event expected, got {arrived_evs2}"
    assert arrived_evs2[0]["destination"] == sys_c, \
        f"event destination should be sys_C, got {arrived_evs2[0]['destination']}"
    ok("drop_ship_arrived event emitted on final leg with correct destination")
except AssertionError as e:
    fail("drop_ship_arrived event on final leg", str(e))
except Exception as e:
    fail("drop_ship_arrived event on final leg (exception)", str(e))

try:
    # Drop ship removed from sys_B on conversion
    at_b_after = [i for i in gs_mh1.entity_roster.at(sys_b)
                  if i.category == "ship" and i.type_value == "drop_ship"]
    assert len(at_b_after) == 0, \
        f"drop ship should be gone from sys_B after conversion, got {at_b_after}"
    ok("drop ship removed from intermediate system (B) after conversion")
except AssertionError as e:
    fail("drop ship removed from B after conversion", str(e))
except Exception as e:
    fail("drop ship removed from B after conversion (exception)", str(e))

# Test 3: drop ship with single-hop waypoints=[A, B] → arrives and converts immediately in one tick
try:
    gs_mh3 = _gs_for_ships()
    s_home = "sys_home3"
    s_dest = "sys_dest3"
    gs_mh3.entity_roster.add("ship", "drop_ship", s_home, 1)
    order_mh3 = ShipOrder(
        order_type="travel",
        target_system_id=s_dest,
        target_body_id=None,
        travel_speed=1.0,
        progress=0.0,
        waypoints=[s_home, s_dest],
        current_waypoint_idx=0,
    )
    gs_mh3.order_queue.enqueue(s_home, "drop_ship", order_mh3)

    evs3 = gs_mh3.sim_engine._tick_ships(1.0)

    # Should convert immediately — constructor + miner at dest
    at_dest_con = [i for i in gs_mh3.entity_roster.at(s_dest)
                   if i.category == "bot" and i.type_value == "constructor"]
    at_dest_min = [i for i in gs_mh3.entity_roster.at(s_dest)
                   if i.category == "bot" and i.type_value == "miner"]
    assert len(at_dest_con) == 1 and at_dest_con[0].count == 1, \
        f"constructor should be at dest, got {at_dest_con}"
    assert len(at_dest_min) == 1 and at_dest_min[0].count == 1, \
        f"miner should be at dest, got {at_dest_min}"
    ok("single-hop drop ship converts immediately on arrival (one tick)")
except AssertionError as e:
    fail("single-hop drop ship immediate conversion", str(e))
except Exception as e:
    fail("single-hop drop ship immediate conversion (exception)", str(e))

try:
    arrived3 = [e for e in evs3 if e.get("type") == "drop_ship_arrived"]
    assert len(arrived3) == 1, \
        f"exactly one drop_ship_arrived event for single-hop, got {arrived3}"
    ok("single-hop drop ship emits drop_ship_arrived event")
except AssertionError as e:
    fail("single-hop drop_ship_arrived event", str(e))
except Exception as e:
    fail("single-hop drop_ship_arrived event (exception)", str(e))

try:
    # Ship removed from source on single-hop conversion
    at_home3 = [i for i in gs_mh3.entity_roster.at(s_home)
                if i.category == "ship" and i.type_value == "drop_ship"]
    assert len(at_home3) == 0, \
        f"drop ship should be gone from source after single-hop arrival, got {at_home3}"
    ok("drop ship removed from source after single-hop arrival")
except AssertionError as e:
    fail("drop ship removed from source (single-hop)", str(e))
except Exception as e:
    fail("drop ship removed from source (single-hop) (exception)", str(e))


# ─── _tick_power_plants: bios consumption + fossil auto-deactivation ──────────
section("_tick_power_plants: bios / fossil consumption")

from src.models.resource import Resource
from src.models.entity import POWER_PLANT_SPECS, StructureType, compute_power_modifier


def _home_body(gs):
    """Return the CelestialBody for the home system's first orbital body."""
    return gs.galaxy.solar_systems[0].orbital_bodies[0]


# Test 1 — bio plant consumes bios resource each tick
try:
    gs_bpp = _fresh_gs()
    hb1 = _home_body(gs_bpp)
    hb1.resources.bios = 100.0
    gs_bpp.entity_roster.add("structure", "power_plant_bios", hb1.id, 1)
    pre_bios = hb1.resources.bios
    gs_bpp.sim_engine._tick_power_plants(1.0)
    post_bios = hb1.resources.bios
    assert post_bios < pre_bios, \
        f"bios should have been consumed; was {pre_bios}, now {post_bios}"
    ok("bio plant consumes bios resource each tick")
except AssertionError as e:
    fail("bio plant consumes bios", str(e))
except Exception as e:
    fail("bio plant consumes bios (exception)", str(e))

# Test 2 — bio plant DOES auto-deactivate when bios depletes (spec.renewable=False)
# The bio plant is renewable=False so it follows the same deactivation logic as fossil;
# population regenerates bios over time, allowing the plant to be reactivated externally.
try:
    gs_bnd = _fresh_gs()
    hb2 = _home_body(gs_bnd)
    hb2.resources.bios = 0.5                               # tiny — will deplete in 1 tick
    # Remove any bio pop so regen doesn't replenish bios during this tick
    gs_bnd.bio_state.remove(hb2.id)
    gs_bnd.entity_roster.add("structure", "power_plant_bios", hb2.id, 1)
    flag_key_bios = f"{hb2.id}:power_plant_bios"
    gs_bnd.sim_engine._tick_power_plants(1.0)
    still_active = gs_bnd.power_plant_active.get(flag_key_bios, True)
    assert not still_active, \
        "bio plant should auto-deactivate when bios depletes (renewable=False)"
    ok("bio plant auto-deactivates when bios depletes (renewable=False)")
except AssertionError as e:
    fail("bio plant auto-deactivate on bios depletion", str(e))
except Exception as e:
    fail("bio plant auto-deactivate on bios depletion (exception)", str(e))

# Test 3 — fossil plant auto-deactivates when gas runs to 0
try:
    gs_foss = _fresh_gs()
    hb3 = _home_body(gs_foss)
    hb3.resources.gas = 0.5                                # will deplete in 1 tick (rate=10/yr)
    gs_foss.entity_roster.add("structure", "power_plant_fossil", hb3.id, 1)
    flag_key_foss = f"{hb3.id}:power_plant_fossil"
    gs_foss.sim_engine._tick_power_plants(1.0)
    still_active_foss = gs_foss.power_plant_active.get(flag_key_foss, True)
    assert not still_active_foss, \
        "fossil plant should auto-deactivate when gas runs to 0"
    ok("fossil plant auto-deactivates when gas depleted")
except AssertionError as e:
    fail("fossil plant auto-deactivate", str(e))
except Exception as e:
    fail("fossil plant auto-deactivate (exception)", str(e))


# ─── _tick_bios: bios resource regeneration ───────────────────────────────────
section("_tick_bios: bios regeneration from bio population")

try:
    gs_bregen = _fresh_gs()
    hb4 = _home_body(gs_bregen)
    hb4.resources.bios = 0.0                               # start at zero

    regen_pop = BioPopulation(
        body_id=hb4.id,
        system_id=gs_bregen.galaxy.solar_systems[0].id,
        bio_type=BioType.PRIMITIVE,
        population=500.0,
        aggression=0.1,
        growth_rate=0.01,
    )
    gs_bregen.bio_state.add(regen_pop)
    gs_bregen.sim_engine._tick_bios(1.0)
    bios_after = hb4.resources.bios
    assert bios_after > 0.0, \
        f"bios should be > 0 after _tick_bios with living population, got {bios_after}"
    ok(f"_tick_bios regenerates bios on body with bio population (got {bios_after:.2f})")
except AssertionError as e:
    fail("_tick_bios bios regeneration", str(e))
except Exception as e:
    fail("_tick_bios bios regeneration (exception)", str(e))


# ─── compute_power_modifier: bio plant scales with bios stockpile ─────────────
section("compute_power_modifier: bio plant bios scaling")

try:
    gs_cpm = _fresh_gs()
    hb5 = _home_body(gs_cpm)
    hb5.resources.bios = 10.0                              # below 50 → throttled
    mod_low = compute_power_modifier(gs_cpm, hb5.id, "power_plant_bios")
    assert mod_low < 1.0, \
        f"bio modifier should be < 1.0 when bios=10, got {mod_low}"
    ok(f"compute_power_modifier < 1.0 when bios < 50 (got {mod_low:.3f})")
except AssertionError as e:
    fail("compute_power_modifier bio low bios", str(e))
except Exception as e:
    fail("compute_power_modifier bio low bios (exception)", str(e))

try:
    gs_cpm2 = _fresh_gs()
    hb6 = _home_body(gs_cpm2)
    hb6.resources.bios = 50.0                              # at threshold → full output
    mod_full = compute_power_modifier(gs_cpm2, hb6.id, "power_plant_bios")
    # No energy_efficiency researched → research_bonus = 1.0
    assert abs(mod_full - 1.0) < 0.001, \
        f"bio modifier should be ~1.0 when bios=50 (no research), got {mod_full}"
    ok(f"compute_power_modifier ~1.0 when bios >= 50, no research (got {mod_full:.3f})")
except AssertionError as e:
    fail("compute_power_modifier bio full bios", str(e))
except Exception as e:
    fail("compute_power_modifier bio full bios (exception)", str(e))

try:
    gs_cpm3 = _fresh_gs()
    hb7 = _home_body(gs_cpm3)
    hb7.resources.bios = 0.0                               # zero bios → zero output
    mod_zero = compute_power_modifier(gs_cpm3, hb7.id, "power_plant_bios")
    assert mod_zero == 0.0, \
        f"bio modifier should be 0.0 when bios=0, got {mod_zero}"
    ok(f"compute_power_modifier = 0.0 when bios = 0 (got {mod_zero:.3f})")
except AssertionError as e:
    fail("compute_power_modifier bio zero bios", str(e))
except Exception as e:
    fail("compute_power_modifier bio zero bios (exception)", str(e))


# ─── BioPopulation.initial_bios save/load round-trip ─────────────────────────
section("BioPopulation.initial_bios save/load round-trip")

try:
    gs_ibrt = _fresh_gs()
    _ibrt_body = "ibrt_test_body"
    _ibrt_sys = gs_ibrt.galaxy.solar_systems[0].id
    ibrt_pop = BioPopulation(
        body_id=_ibrt_body,
        system_id=_ibrt_sys,
        bio_type=BioType.PRIMITIVE,
        population=200.0,
        aggression=0.3,
        growth_rate=0.02,
        initial_bios=50.0,
    )
    gs_ibrt.bio_state.add(ibrt_pop)

    saved_ibrt = gs_ibrt.to_dict()
    gs_ibrt2 = GameState.from_dict(saved_ibrt, gs_ibrt.galaxy)

    restored_ibrt = gs_ibrt2.bio_state.get(_ibrt_body)
    assert restored_ibrt is not None, "population should survive round-trip"
    assert abs(restored_ibrt.initial_bios - 50.0) < 0.001, \
        f"initial_bios should be 50.0, got {restored_ibrt.initial_bios}"
    ok("initial_bios=50.0 survives to_dict/from_dict round-trip")
except AssertionError as e:
    fail("initial_bios round-trip", str(e))
except Exception as e:
    fail("initial_bios round-trip (exception)", str(e))


# ─── BioPopulation.tick: capacity scaling ────────────────────────────────────
section("BioPopulation.tick: capacity scaling")

# Full bios → full capacity → population should grow when below carrying cap
try:
    pop_full = BioPopulation(
        body_id="cap_test_body",
        system_id="any_sys",
        bio_type=BioType.PRIMITIVE,
        population=100.0,
        aggression=0.1,
        growth_rate=0.05,
        capacity=10000.0,
        initial_bios=100.0,
    )
    pop_before = pop_full.population
    # effective_capacity = capacity * (current_bios / initial_bios) = 10000 * 1.0 = 10000
    pop_full.tick(1.0, effective_capacity=10000.0)
    assert pop_full.population > pop_before, \
        f"population should grow when below full capacity; before={pop_before}, after={pop_full.population}"
    ok("BioPopulation grows when bios=initial_bios (full effective capacity)")
except AssertionError as e:
    fail("capacity scaling full bios", str(e))
except Exception as e:
    fail("capacity scaling full bios (exception)", str(e))

# Depleted bios → reduced capacity → population > effective capacity → should decrease
try:
    pop_dep = BioPopulation(
        body_id="cap_dep_body",
        system_id="any_sys",
        bio_type=BioType.PRIMITIVE,
        population=5000.0,
        aggression=0.1,
        growth_rate=0.05,
        capacity=10000.0,
        initial_bios=100.0,
    )
    # effective_capacity = 500 (5% of 10000 — simulating 5% bios remaining)
    # population=5000 > effective_capacity=500 → dN negative → population decreases
    pop_before_dep = pop_dep.population
    pop_dep.tick(1.0, effective_capacity=500.0)
    assert pop_dep.population < pop_before_dep, \
        f"population should decline when > effective_capacity; before={pop_before_dep}, after={pop_dep.population}"
    ok("BioPopulation declines when population > reduced effective capacity (depleted bios)")
except AssertionError as e:
    fail("capacity scaling depleted bios", str(e))
except Exception as e:
    fail("capacity scaling depleted bios (exception)", str(e))


# ─── _tick_bios: primitive regen vs uplifted no-regen ────────────────────────
section("_tick_bios: primitive regen vs uplifted no-regen")

# Primitive regen: bios resource should increase after one tick
try:
    gs_preg = _fresh_gs()
    hb_preg = _home_body(gs_preg)
    hb_preg.resources.bios = 10.0
    preg_pop = BioPopulation(
        body_id=hb_preg.id,
        system_id=gs_preg.galaxy.solar_systems[0].id,
        bio_type=BioType.PRIMITIVE,
        population=1000.0,
        aggression=0.1,
        growth_rate=0.01,
        initial_bios=50.0,
    )
    # Remove any existing bio pop at this body first
    gs_preg.bio_state.remove(hb_preg.id)
    gs_preg.bio_state.add(preg_pop)
    bios_before = hb_preg.resources.bios
    gs_preg.sim_engine._tick_bios(1.0)
    bios_after = hb_preg.resources.bios
    assert bios_after > bios_before, \
        f"primitive population should regenerate bios; before={bios_before}, after={bios_after}"
    ok(f"primitive population regenerates bios resource (before={bios_before:.1f}, after={bios_after:.3f})")
except AssertionError as e:
    fail("primitive bios regen", str(e))
except Exception as e:
    fail("primitive bios regen (exception)", str(e))

# Uplifted no-regen: bios should NOT increase (stays same or decreases with plant consumption)
try:
    gs_unoreg = _fresh_gs()
    hb_unoreg = _home_body(gs_unoreg)
    hb_unoreg.resources.bios = 10.0
    unoreg_pop = BioPopulation(
        body_id=hb_unoreg.id,
        system_id=gs_unoreg.galaxy.solar_systems[0].id,
        bio_type=BioType.UPLIFTED,
        population=1000.0,
        aggression=0.1,
        growth_rate=0.01,
        initial_bios=50.0,
    )
    gs_unoreg.bio_state.remove(hb_unoreg.id)
    gs_unoreg.bio_state.add(unoreg_pop)
    bios_before_u = hb_unoreg.resources.bios
    gs_unoreg.sim_engine._tick_bios(1.0)
    bios_after_u = hb_unoreg.resources.bios
    # Uplifted population should NOT add bios; value stays the same (no power plant here)
    assert bios_after_u == bios_before_u, \
        f"uplifted population should NOT regenerate bios; before={bios_before_u}, after={bios_after_u}"
    ok("uplifted population does not regenerate bios resource")
except AssertionError as e:
    fail("uplifted no bios regen", str(e))
except Exception as e:
    fail("uplifted no bios regen (exception)", str(e))


# ─── _tick_bios: extinction event ────────────────────────────────────────────
section("_tick_bios: extinction event and BioState.remove()")

# Extinction: bios=0 + population<=2 + initial_bios > 0 → bios_extinction event + pop removed
try:
    gs_ext = _fresh_gs()
    hb_ext = _home_body(gs_ext)
    hb_ext.resources.bios = 0.0
    ext_pop = BioPopulation(
        body_id=hb_ext.id,
        system_id=gs_ext.galaxy.solar_systems[0].id,
        bio_type=BioType.PRIMITIVE,
        population=1.5,   # <= 2.0 threshold
        aggression=0.1,
        growth_rate=0.01,
        initial_bios=50.0,  # > 0 required for extinction check
    )
    gs_ext.bio_state.remove(hb_ext.id)
    gs_ext.bio_state.add(ext_pop)
    evs_ext = gs_ext.sim_engine._tick_bios(1.0)
    ext_evs = [e for e in evs_ext if e.get("type") == "bios_extinction"]
    assert len(ext_evs) >= 1, \
        f"bios_extinction event should be emitted when bios=0 and pop<=2; events={evs_ext}"
    assert ext_evs[0].get("body_id") == hb_ext.id, \
        f"event body_id should match; got {ext_evs[0].get('body_id')}"
    assert gs_ext.bio_state.get(hb_ext.id) is None, \
        "population should be removed from bio_state after extinction"
    ok("bios_extinction event emitted and population removed when bios=0 and pop<=2")
except AssertionError as e:
    fail("bios_extinction event", str(e))
except Exception as e:
    fail("bios_extinction event (exception)", str(e))

# BioState.remove() removes a population by body_id
try:
    bs_test = BioState()
    rm_pop = BioPopulation(
        body_id="rm_test_body",
        system_id="rm_sys",
        bio_type=BioType.PRIMITIVE,
        population=100.0,
        aggression=0.1,
        growth_rate=0.02,
    )
    bs_test.add(rm_pop)
    assert bs_test.get("rm_test_body") is not None, "population should exist before remove()"
    bs_test.remove("rm_test_body")
    assert bs_test.get("rm_test_body") is None, "population should be None after remove()"
    ok("BioState.remove() removes population by body_id")
except AssertionError as e:
    fail("BioState.remove()", str(e))
except Exception as e:
    fail("BioState.remove() (exception)", str(e))

# BioState.remove() is idempotent (removing non-existent key does not raise)
try:
    bs_test2 = BioState()
    bs_test2.remove("nonexistent_body")   # should not raise
    ok("BioState.remove() is idempotent for non-existent body_id")
except Exception as e:
    fail("BioState.remove() idempotent", str(e))


# ─── _tick_power_plants: bios consumption (detailed) ─────────────────────────
section("_tick_power_plants: bio plant consumes bios (renewable=False)")

# Bio plant (power_plant_bios) has renewable=False → consumes bios resource each tick
try:
    gs_bpdet = _fresh_gs()
    hb_bpdet = _home_body(gs_bpdet)
    hb_bpdet.resources.bios = 100.0
    # Remove any existing bio pop to avoid regen masking consumption
    gs_bpdet.bio_state.remove(hb_bpdet.id)
    gs_bpdet.entity_roster.add("structure", "power_plant_bios", hb_bpdet.id, 1)
    bios_pre = hb_bpdet.resources.bios
    gs_bpdet.sim_engine._tick_power_plants(1.0)
    bios_post = hb_bpdet.resources.bios
    assert bios_post < bios_pre, \
        f"bio plant should consume bios (renewable=False); before={bios_pre}, after={bios_post}"
    ok(f"power_plant_bios consumes bios resource (before={bios_pre:.1f}, after={bios_post:.1f})")
except AssertionError as e:
    fail("bio plant bios consumption detail", str(e))
except Exception as e:
    fail("bio plant bios consumption detail (exception)", str(e))


# ─── Summary ─────────────────────────────────────────────────────────────────
print(f"\n{'-'*50}")
print(f"Unit tests: {_passed} passed, {_failed} failed")
if _failed > 0:
    sys.exit(1)
print("All unit tests OK.")
