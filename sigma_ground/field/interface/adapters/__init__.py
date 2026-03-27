"""local_library.interface.adapters -- SSBM physics patch layer.

Wraps external Python physics libraries with SSBM-ground (sg_) alternatives.
External libraries are NEVER modified; sg_ methods sit alongside them.

Public API
----------
    SGConstants       Drop-in for astropy.constants / scipy.constants
    SGAdapter         Generic wrapper: adds sg_ methods to any external object
    SGPhysicsMixin    Mixin: inherit to add sg_ methods to your own classes
    SGEphemeris       Planet positions with 4-tier SSBM fallback
    sg_solve_ivp      Forest-Ruth ODE solver (scipy.integrate.solve_ivp API)
    sg_nbody          N-body convenience wrapper (NBodySystem + FR4)
    sg_odeint         Forest-Ruth odeint (scipy.integrate.odeint API)
    sg_patch_astropy  Inject SSBM constants into astropy (non-destructive)
    sg_patch_scipy    Inject SSBM G into scipy (non-destructive)

Naming convention
-----------------
    sg_<method>     Sigma-ground patched version of an equivalent external call.
                    Uses DE440 GMs, CODATA 2018 constants, FR4 integration.

    SG<Class>       Sigma-ground class -- either wraps an external class or
                    provides a standalone SSBM alternative.

Example
-------
    from sigma_ground.field.interface.adapters import SGConstants, SGEphemeris

    print(SGConstants.GM_sun)           # 1.327e20 m³/s² (DE440, not CODATA)

    eph = SGEphemeris()
    pos = eph.sg_position("Mars", jd=2461000.0)  # (x,y,z) km, ICRF
    print(eph.sg_distance_au("Mars", jd=2461000.0))  # heliocentric AU
"""

from sigma_ground.field.interface.adapters.base       import SGPhysicsMixin, SGAdapter
from sigma_ground.field.interface.adapters.constants  import (
    SGConstants, sg_patch_astropy, sg_patch_scipy,
)
from sigma_ground.field.interface.adapters.ephemeris  import SGEphemeris
from sigma_ground.field.interface.adapters.integrator import (
    sg_solve_ivp, sg_nbody, sg_odeint, SGSolution,
)

__all__ = [
    "SGPhysicsMixin",
    "SGAdapter",
    "SGConstants",
    "SGEphemeris",
    "SGSolution",
    "sg_solve_ivp",
    "sg_nbody",
    "sg_odeint",
    "sg_patch_astropy",
    "sg_patch_scipy",
]
