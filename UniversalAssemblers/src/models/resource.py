from dataclasses import dataclass, asdict


@dataclass
class Resource:
    """
    Quantities of harvestable materials on a celestial body.
    All values are in arbitrary game units (AU-res).

    minerals       -- Common metal ores; primary construction material.
    rare_minerals  -- Rare earths and exotic compounds; advanced manufacturing.
    ice            -- Water ice; propellant, life support, and hydrogen feedstock.
    gas            -- Hydrogen, helium, and volatile gases; fuel and atmospherics.
    energy_output  -- Continuous energy flux (solar luminosity, geothermal, etc.).
    """
    minerals: float = 0.0
    rare_minerals: float = 0.0
    ice: float = 0.0
    gas: float = 0.0
    bios: float = 0.0        # biological feedstock; renewable on suitable bodies
    energy_output: float = 0.0
    # Manufactured resources (produced by extractors in refine mode)
    electronics: float = 0.0  # from minerals + rare_minerals
    alloys: float = 0.0        # from minerals
    fuel_cells: float = 0.0    # from gas + ice

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Resource":
        return cls(
            minerals=d.get("minerals", 0.0),
            rare_minerals=d.get("rare_minerals", 0.0),
            ice=d.get("ice", 0.0),
            gas=d.get("gas", 0.0),
            bios=d.get("bios", 0.0),
            energy_output=d.get("energy_output", 0.0),
            electronics=d.get("electronics", 0.0),
            alloys=d.get("alloys", 0.0),
            fuel_cells=d.get("fuel_cells", 0.0),
        )
