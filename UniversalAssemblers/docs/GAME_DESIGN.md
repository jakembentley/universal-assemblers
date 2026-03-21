# Key Design Rules (from game spec)

- **Orbital structures** are rendered as **squares** (⬡) on the system map; planets/moons as circles
- A single square represents all structures orbiting a star; clicking it opens the structure menu
- Players cannot enter or see details of any system until visited by a Probe
- Tech tree nodes require all prerequisites researched before unlocking; multiple Research Arrays can work on different adjacent nodes simultaneously
- Research Arrays contribute to the global tech pool (not per-system)
- Power plants: solar, wind, bios are renewable; fossil fuels, nuclear, cold fusion consume finite resources
- Megastructures (`MegastructureType`) are a separate category from standard structures — different entity view, different rendering rules; Dyson Sphere alters star visual and decays planets
- Drop Ships path to a target system+body; on arrival they convert into 1 Constructor bot + 1 Miner bot
- Bios entities (primitive / uplifted) are engine-managed; uplifted types can damage player entities
