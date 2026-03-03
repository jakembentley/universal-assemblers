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
    energy_output: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)
