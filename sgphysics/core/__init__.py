"""
sgphysics.core — SSBM σ-field physics.

Re-exports key SSBM physics from local_library for use via the sgphysics
namespace.

  sigma_field    — σ(r) computation, scale transition, σ-cascade
  entanglement   — Quantum entanglement fraction η, photon events
  cosmology      — Hubble expansion, dark energy, dark matter budget
"""

# Lazy imports — local_library must be on sys.path
try:
    from local_library.sigma_field   import *  # noqa: F401,F403
except ImportError:
    pass

try:
    from local_library.entanglement  import *  # noqa: F401,F403
except ImportError:
    pass
