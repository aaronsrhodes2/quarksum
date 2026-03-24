"""
sgphysics.inventory — Particle inventory and mass closure.

Re-exports the quarksum particle inventory tools for use via the
sgphysics namespace.

  resolve_material  — Material → molecules → atoms → quarks
  mass_closure      — Verify books balance (quarksum)
"""

try:
    from quarksum import resolve_material, mass_closure  # noqa: F401
    __all__ = ['resolve_material', 'mass_closure']
except ImportError:
    __all__ = []
