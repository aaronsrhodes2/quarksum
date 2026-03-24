"""
QuarkSum default loads — immutable registry of canonical physical systems.

These are the nine default physical systems accessible by name or --menu.
They are defined as NamedTuples (immutable) and stored in a frozen tuple.

Each load has:
  id           — sample file stem (loads quarksum/samples/{id}.json)
  name         — human-readable display name
  message      — greeting printed to stderr when loaded as the default
  radius_m     — characteristic radius in metres (None if not applicable)
                 Used by compute_physics() for geometric quantities:
                 escape velocity, gravitational σ-field, surface area.

Physics/Rendering note:
  The radius_m values here are the physical radii from measurement, not
  from simulation. They are constants, not outputs — they belong in this
  registry and not in the JSON spec (which carries only mass/composition).

All values from IAU, NASA/JPL, NIST, or equivalent authoritative sources.
"""

from __future__ import annotations
from typing import NamedTuple


class DefaultLoad(NamedTuple):
    """Immutable descriptor for one default physical system."""
    id: str
    name: str
    message: str
    radius_m: float | None


# ── Registry ─────────────────────────────────────────────────────────────────
# Ordered from largest to smallest — the natural cosmological zoom.
# This order is used by --menu.

LOADS: tuple[DefaultLoad, ...] = (
    DefaultLoad(
        id="universe",
        name="Our Universe",
        message="We loaded the observable universe. Big place.",
        radius_m=4.4e26,     # Observable universe radius (46.5 Gly comoving)
    ),
    DefaultLoad(
        id="milky_way",
        name="Milky Way Galaxy",
        message="We loaded the Milky Way. You are in it.",
        radius_m=4.73e20,    # ~50 kpc radius (Bland-Hawthorn & Gerhard 2016)
    ),
    DefaultLoad(
        id="sol_solar_system",
        name="Sol Solar System",
        message="We loaded Sol and the solar system. Mind the Oort Cloud.",
        radius_m=1.5e13,     # ~100,000 AU (Oort Cloud outer edge)
    ),
    DefaultLoad(
        id="earth_with_moon",
        name="Earth with Moon",
        message="We loaded the earth and the moon, have fun!",
        radius_m=6.371e6,    # Earth mean radius (IAU 2015: 6371.0 km)
    ),
    DefaultLoad(
        id="iceberg_in_ocean",
        name="Iceberg in Ocean",
        message="We loaded the iceberg. 89% is below the surface.",
        radius_m=150.0,      # ~150 m radius (large tabular iceberg proxy)
    ),
    DefaultLoad(
        id="apple_on_table",
        name="Apple on Table",
        message="We loaded the apple on the table. Newton approves.",
        radius_m=0.038,      # ~38 mm radius (medium apple)
    ),
    DefaultLoad(
        id="bronze_cube",
        name="Bronze Cube",
        message="We loaded the bronze cube. 10 cm on a side, 8.8 kg.",
        radius_m=0.0866,     # sqrt(3)/2 × 0.1 m (circumradius of 10 cm cube)
    ),
    DefaultLoad(
        id="water_molecule",
        name="Water Molecule",
        message="We loaded one water molecule. 10 protons, 8 neutrons, 10 electrons.",
        radius_m=1.52e-10,   # H₂O kinetic radius (van der Waals, ~152 pm)
    ),
    DefaultLoad(
        id="hydrogen_atom",
        name="Hydrogen Atom",
        message="We loaded one hydrogen atom. The simplest thing that exists.",
        radius_m=5.29e-11,   # Bohr radius a₀ = 0.529 Å (NIST CODATA 2018)
    ),
)

# ── Default ───────────────────────────────────────────────────────────────────
DEFAULT_ID: str = "earth_with_moon"

# ── Lookup helpers ────────────────────────────────────────────────────────────

def by_id(load_id: str) -> DefaultLoad | None:
    """Return the DefaultLoad for a given id, or None."""
    for load in LOADS:
        if load.id == load_id:
            return load
    return None


def default_load() -> DefaultLoad:
    """Return the default DefaultLoad (earth_with_moon)."""
    result = by_id(DEFAULT_ID)
    assert result is not None, f"Default id '{DEFAULT_ID}' not found in LOADS"
    return result
