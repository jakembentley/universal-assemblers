"""Ledger — persistent record of entity actions and random events visible to the player."""
from __future__ import annotations

from dataclasses import dataclass

CATEGORY_ENTITY = "entity"
CATEGORY_RANDOM = "random"

_ENTITY_TYPES = frozenset({
    "drop_ship_arrived", "probe_arrived", "ship_arrived",
    "entity_built", "ship_built",
    "tech_complete", "resource_depleted", "resource_depleted_plant",
})


@dataclass
class LedgerEntry:
    tick_year:  float        # gs.in_game_years at emission time
    category:   str          # CATEGORY_ENTITY or CATEGORY_RANDOM
    event_type: str          # raw ev["type"] string
    message:    str          # pre-formatted human-readable string
    color:      tuple        # RGB display color
    system_id:  str | None   # None → always visible (global player events)


def _resolve_location(ev: dict, body_env: dict, galaxy) -> tuple[str | None, str]:
    """Return (system_id, human_readable_location_name) for an event dict."""
    body_id   = ev.get("body_id")
    system_id = ev.get("system_id")

    # Resolve system_id from body_id if missing
    if not system_id and body_id and body_env:
        system_id = body_env.get(body_id, {}).get("system_id")

    # Resolve human-readable location name
    if body_id and galaxy:
        for sys in galaxy.solar_systems:
            for body in sys.orbital_bodies:
                if body.id == body_id:
                    return system_id, body.name
                for moon in body.moons:
                    if moon.id == body_id:
                        return system_id, moon.name
    if system_id and galaxy:
        sys_obj = next((s for s in galaxy.solar_systems if s.id == system_id), None)
        if sys_obj:
            return system_id, sys_obj.name

    return system_id, body_id or system_id or "?"


def format_ledger_event(
    ev: dict, body_env: dict, galaxy
) -> tuple[str, tuple, str, str | None] | None:
    """Convert a raw sim event dict into (message, color, category, system_id).

    Returns None if the event should not appear in the ledger (e.g. victory).
    """
    from .tech import TECH_TREE

    etype = ev.get("type", "")

    if etype == "victory":
        return None

    system_id_default, loc = _resolve_location(ev, body_env, galaxy)

    if etype == "tech_complete":
        tid  = ev.get("tech_id", "")
        name = TECH_TREE[tid].name if tid in TECH_TREE else tid
        return (f"TECH UNLOCKED: {name}", (80, 220, 120), CATEGORY_ENTITY, None)

    if etype == "entity_built":
        ent = (ev.get("entity_type") or "").replace("_", " ").title()
        return (f"BUILT: {ent}", (80, 200, 255), CATEGORY_ENTITY, None)

    if etype in ("drop_ship_arrived", "probe_arrived", "ship_arrived"):
        dest_id = ev.get("destination") or ev.get("system_id") or "?"
        dest    = dest_id
        if galaxy:
            sys_obj = next((s for s in galaxy.solar_systems if s.id == dest_id), None)
            if sys_obj:
                dest = sys_obj.name
        if etype == "drop_ship_arrived":
            label = "Drop Ship"
        elif etype == "probe_arrived":
            label = "Probe"
        else:
            label = (ev.get("ship_type") or "Ship").replace("_", " ").title()
        dest_sys_id = ev.get("destination") or ev.get("system_id")
        return (f"{label} arrived: {dest}", (255, 200, 80), CATEGORY_ENTITY, dest_sys_id)

    if etype == "resource_depleted":
        res = (ev.get("resource") or "").replace("_", " ").title()
        return (f"RESOURCE DEPLETED: {res}", (255, 80, 80), CATEGORY_ENTITY, system_id_default)

    if etype == "resource_depleted_plant":
        plant_type = (ev.get("plant_type") or "").replace("_", " ").title()
        loc_id     = ev.get("location_id") or "?"
        # Resolve loc_id name from body_env / galaxy
        loc_name = loc_id
        if galaxy:
            for sys in galaxy.solar_systems:
                for body in sys.orbital_bodies:
                    if body.id == loc_id:
                        loc_name = body.name
                    for moon in body.moons:
                        if moon.id == loc_id:
                            loc_name = moon.name
        sys_id = body_env.get(loc_id, {}).get("system_id") if body_env else None
        return (
            f"{plant_type} offline — fuel depleted at {loc_name}",
            (255, 160, 40), CATEGORY_ENTITY, sys_id,
        )

    if etype in ("bios_entity_damaged", "bios_entity_destroyed"):
        ent  = (ev.get("entity_type") or "entity").replace("_", " ").title()
        verb = "destroyed" if etype == "bios_entity_destroyed" else "damaged"
        return (
            f"BIOS ATTACK: {ent} {verb} at {loc}",
            (255, 60, 60), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "bios_mutation":
        return (
            f"BIOS MUTATED to Uplifted at {loc}",
            (255, 120, 40), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "bios_extinction":
        btype = (ev.get("bio_type") or "bio").title()
        return (
            f"BIOS EXTINCT: {btype} population lost at {loc}",
            (180, 80, 200), CATEGORY_RANDOM, system_id_default,
        )

    if etype in ("solar_flare_damaged", "solar_flare_destroyed"):
        ent  = (ev.get("entity_type") or "ship").replace("_", " ").title()
        verb = "destroyed" if etype == "solar_flare_destroyed" else "damaged"
        return (
            f"SOLAR FLARE: {ent} {verb} in {loc}",
            (255, 140, 0), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "asteroid_impact":
        ent       = (ev.get("entity_type") or "structure").replace("_", " ").title()
        destroyed = ev.get("destroyed", False)
        return (
            f"ASTEROID IMPACT: {ent} {'destroyed' if destroyed else 'damaged'} at {loc}",
            (255, 80, 80), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "factory_malfunction":
        destroyed = ev.get("destroyed", False)
        suffix    = " — destroyed!" if destroyed else ""
        return (
            f"FACTORY MALFUNCTION at {loc}{suffix}",
            (255, 160, 40), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "power_surge":
        ent       = (ev.get("entity_type") or "power plant").replace("_", " ").title()
        destroyed = ev.get("destroyed", False)
        return (
            f"POWER SURGE: {ent} {'destroyed' if destroyed else 'damaged'} at {loc}",
            (255, 160, 40), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "vein_discovery":
        res = (ev.get("resource") or "minerals").replace("_", " ").title()
        amt = ev.get("amount", 0)
        return (
            f"VEIN FOUND: +{amt} {res} at {loc}",
            (80, 220, 120), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "bio_population_boom":
        btype = (ev.get("bio_type") or "bio").title()
        return (
            f"BIO BOOM: {btype} population surge at {loc}",
            (160, 100, 255), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "bio_aggression_spike":
        new_agg = ev.get("new_aggression", 0.0)
        return (
            f"BIO AGGRESSION SPIKE at {loc}: {int(new_agg * 100)}%",
            (255, 100, 40), CATEGORY_RANDOM, system_id_default,
        )

    if etype == "research_breakthrough":
        tid  = ev.get("tech_id", "")
        name = TECH_TREE[tid].name if tid in TECH_TREE else tid
        if ev.get("tech_completed"):
            return (f"BREAKTHROUGH: {name} completed!", (80, 220, 120), CATEGORY_RANDOM, None)
        return (
            f"RESEARCH BREAKTHROUGH: {name} advanced",
            (100, 180, 255), CATEGORY_RANDOM, None,
        )

    if etype == "ship_built":
        ship = (ev.get("ship_type") or "ship").replace("_", " ").title()
        return (f"SHIP BUILT: {ship}", (80, 200, 255), CATEGORY_ENTITY, system_id_default)

    # Unknown event type — skip silently
    return None
