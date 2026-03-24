"""
sgphysics.celestial — Celestial mechanics and N-body integration.

Re-exports the N-body engine and celestial body definitions from
local_library for use via the sgphysics namespace.

  NBodySystem    — Forest-Ruth FR4 N-body integrator
  CelestialBody  — Body with mass, position, velocity, SRP params
  solar_system   — Pre-built 26-body solar system (DE440-compatible)
"""

try:
    from local_library.interface.nbody import (
        NBodySystem,
        CelestialBody,
    )
    __all__ = ['NBodySystem', 'CelestialBody']
except ImportError:
    __all__ = []
