# Universal Assemblers — Game Design Document

## 1. Core Concepts

### Entities
Entities are game elements that can interact with resource locations or other entities. Three control categories:
- **Player-controlled** — directly commanded by the player
- **Sim-controlled** — run by the computer simulation (AI factions, neutral actors)
- **Passive / engine-handled** — managed automatically by the game engine (e.g., Bios)

### Resources
| Resource | Renewable | Notes |
|---|---|---|
| Minerals | No | Common construction material; mined from surfaces |
| Rare Minerals | No | Advanced manufacturing; nuclear fuel feedstock |
| Ice | No | Propellant, life support, cold fusion feedstock |
| Gas | No | Fuel, atmospherics; fossil fuel feedstock |
| Bios | Yes | Biological feedstock; grows back slowly on suitable bodies |
| Energy Output | Yes | Radiated by stars; captured by solar/wind power plants |

---

## 2. Entity Types

### 2.1 Structures
Stationary entities. Exist on a celestial body surface or in orbit (space structures). Two categories:
- **Standard Structures** — majority of structures; grouped under a single ⬡ icon on the system map when orbital
- **Megastructures** — special instances with unique rules and visual effects; not grouped under the standard square

#### Standard Structures
| Structure | Location | Tech Required | Notes |
|---|---|---|---|
| Extractor | Surface | — (starter) | Mines minerals, rare minerals, ice, gas |
| Factory | Surface | — (starter) | Produces components and sub-assemblies |
| Power Plant (Solar) | Surface / Orbital* | — (starter) | Renewable; no consumption |
| Power Plant (Wind) | Surface | — | Renewable; terrestrial planets only |
| Power Plant (Bios) | Surface | — | Renewable; consumes bios |
| Power Plant (Fossil Fuel) | Surface | — | Finite; consumes gas |
| Power Plant (Nuclear) | Surface | — | Finite; consumes rare minerals |
| Power Plant (Cold Fusion) | Surface / Orbital* | `cold_fusion` | Finite; consumes ice |
| Power Plant (Dark Matter) | Surface / Orbital* | `dark_matter` | Renewable; no consumption |
| Research Array | Surface / Orbital* | — (starter) | Contributes to global tech pool |
| Replicator | Surface | `self_replication` | Self-replicates basic components |
| Shipyard | Surface / Orbital* | — | Constructs and launches ships |
| Storage Hub | Surface | — | Increases resource storage capacity |

*Orbital placement requires `orbital_power` tech

#### Megastructures
Require `swarm_bots` tech and a continuous stream of Constructor bots during assembly. Special visual rules apply — they are **never** nested under the standard orbital square.

| Megastructure | Tech Required | Special Rules |
|---|---|---|
| Dyson Sphere | `swarm_bots` | Alters star visual; slowly decays nearby planets |
| Space Elevator | `swarm_bots` | Reduces launch costs from parent body |
| Disc World | `swarm_bots` | Massive habitable ring megastructure |
| Halogate | `swarm_bots` | Enables fast system-to-system transit |
| Doom Machine | `doom_machine` (+ `swarm_bots`) | Offensive/destructive weapons platform |

Megastructures use a **modular entity view** (assembly progress + module slots) distinct from other entity views.

---

### 2.2 Bots
Mobile ground/orbital entities carrying out tasks autonomously.

| Bot | Notes |
|---|---|
| Worker Bot | General labour: construction assist, logistics |
| Harvester | Resource extraction from surface deposits |
| Constructor | Structure construction and repair |

**Bot Entity View**
- Task list for all bots at the selected location (planet or system)
- Player sets a percentage allocation across available tasks
- Player can add new tasks to the bot order queue

---

### 2.3 Ships
Mobile inter-system entities.

| Ship | Tech Required | Notes |
|---|---|---|
| Probe | — (starter) | Explores systems; required before system details are visible |
| Drop Ship | — (starter) | Paths to target system + planet; on impact converts into 1 Constructor + 1 Miner bot |
| Mining Vessel | — (starter) | Extracts resources from asteroids and remote bodies |
| Transport | — | Bulk resource and personnel ferry |
| Warship | `atomic_warships` | Combat vessel |

**Drop Ship behaviour**: player selects a target system (must be explored) and a target celestial body. The ship travels there autonomously. On arrival/impact it is destroyed and replaced by one Constructor bot + one Miner bot at that location.

**Ship Entity View**: similar structure to Bot view — task queue + percentage allocation — but with ship-specific task types (travel, escort, mine, patrol, intercept, etc.).

---

### 2.4 Bios
A special entity category that moves freely. Managed by the game engine (not player-controlled).

| Sub-type | Behaviour |
|---|---|
| Primitive | Passive; can be observed and interacted with by the player |
| Uplifted | Active; can damage player entities; can be interacted with by the player |

Bios require their own entity view (observation / interaction panel).

---

## 3. Tech Tree

All Research Arrays contribute their output to the global research pool. A player can direct different arrays toward **different adjacent unlocked nodes simultaneously**. A node cannot be started until all its prerequisites are fully researched.

### Branch: Construction
```
Structure Modules
  └─► Multi-Component Structures
        └─► Swarm Bots ◄── (also requires: Self Replication)
              └─► Dyson Sphere, Space Elevator, Disc World, Halogate

Structure Modules
  └─► Orbital Power Plants  (enables orbital placement of power/research/shipyard)
```

### Branch: Energy / Production
```
Refinery Efficiency  (reduces construction costs)
  └─► Self Replication  → unlocks Replicator structure
  └─► Cold Fusion       → unlocks Cold Fusion Power Plant

Cold Fusion + Space Folding
  └─► Dark Matter       → unlocks Dark Matter Power Plant
```

### Branch: Military
```
Atomic Warships  → unlocks Warship
  └─► Doom Machine  (also requires: Swarm Bots)
```

### Branch: Propulsion
```
Solar Sails  (ship speed bonus)
  └─► Space Folding  (ship range bonus)
        └─► Wormhole Drive  (special: destination is randomised)
```

### Full Node Reference
| Tech ID | Name | Prerequisites | Unlocks |
|---|---|---|---|
| `structure_modules` | Structure Modules | — | Multi-Component Structures, Orbital Power Plants |
| `multi_component_structures` | Multi-Component Structures | `structure_modules` | Swarm Bots path |
| `orbital_power` | Orbital Power Plants | `structure_modules` | Orbital placement for power/research/shipyard |
| `refinery_efficiency` | Refinery Efficiency | — | Self Replication path, cost reduction |
| `self_replication` | Self Replication | `refinery_efficiency` | Replicator structure |
| `cold_fusion` | Cold Fusion | `refinery_efficiency` | Cold Fusion Power Plant |
| `dark_matter` | Dark Matter Containment | `cold_fusion` + `space_folding` | Dark Matter Power Plant |
| `swarm_bots` | Swarm Bots | `multi_component_structures` + `self_replication` | All megastructures |
| `atomic_warships` | Atomic Warships | — | Warship |
| `doom_machine` | Doom Machine | `atomic_warships` + `swarm_bots` | Doom Machine megastructure |
| `solar_sails` | Solar Sails | — | Ship speed bonus |
| `space_folding` | Space Folding | `solar_sails` | Ship range bonus |
| `wormhole_drive` | Wormhole Drive | `space_folding` | Random-destination FTL |

---

## 4. GUI / UI Rules

### System Map
- Structures **on a planet or moon** are displayed via the body's own icon
- All structures **orbiting a star** are represented by a single ⬡ square — clicking opens the **Orbital Structure Menu** listing all structures at that location
- Megastructures alter the system map visually and are not nested under the square icon
- A Dyson Sphere gradually changes the star's rendered size/colour and slowly shrinks nearby planet icons

### Entity Views
Clicking an entity in the bottom panel or on the map switches to that entity's dedicated view, localised to the currently selected system or body.

| Entity | View |
|---|---|
| Standard Structure | Info panel: resource I/O rates, output level |
| Modular / Megastructure | Assembly progress bar, module slots |
| Bot | Task list + percentage-allocation sliders + add-task button |
| Ship | Task queue + available task types |
| Bio | Observation / interaction panel |

### Galaxy Map
Clicking the entity section in galaxy map view shows a **summary of all player entities** across the entire galaxy (totals by type, grouped by system).

### Exploration Gating
A system's contents (bodies, resources, entity details) are hidden until a Probe visits. Unvisited systems appear as dim ??? blips.

### Tech Tree Gating
A tech cannot begin research until all prerequisites are fully researched. The Research Array assignment UI should grey out locked nodes.

---

## 5. Starting State
At game initialisation the player controls one system (home, COLONIZED) containing:

**On the home planet (home_body):**
- 1× Extractor
- 1× Factory
- 1× Power Plant (Solar)
- 1× Research Array

**In the home system:**
- 1× Probe
- 1× Drop Ship
- 1× Mining Vessel

---

## 6. Implementation Status

### Implemented
- Procedural galaxy generation (seeded, deterministic)
- Galaxy / SolarSystem / CelestialBody / Moon / Resource data models
- Fog-of-war discovery states (Unknown → Detected → Discovered → Colonized)
- Main menu, galaxy map view, three-pane system view
- Entity type enums (StructureType, BotType, ShipType, MegastructureType, BioType)
- Power plant spec data (solar, wind, bios, fossil, nuclear, cold fusion, dark matter)
- Full tech tree data model (TechNode, TECH_TREE, prerequisite helpers)
- EntityRoster in GameState (initialised from STARTING_ENTITIES on new game)
- TechState in GameState (tracks researched set, in-progress research)
- EntitiesPanel reads live counts from GameState entity roster

### Not Yet Implemented
- Entity view UI (clicking entity → dedicated view panel)
- Bot task list / percentage-allocation UI
- Ship task queue UI
- Megastructure special rendering (Dyson Sphere star/planet decay)
- Orbital structure square icon on system map (single ⬡ for all orbital structures)
- Drop Ship pathfinding and impact conversion (→ Constructor + Miner bot)
- Tech tree UI (node browser, research assignment, progress display)
- Resource consumption simulation (power plants burning gas / ice / rare minerals)
- Probe exploration gating (system bodies hidden until Probe visits)
- Bios entity simulation
- Save / load of entity roster and tech state
- Wind / bios resource generation in the map generator
