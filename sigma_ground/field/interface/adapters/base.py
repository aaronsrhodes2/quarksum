"""SGPhysicsMixin -- the core sigma-ground adapter primitive.

Any class that inherits this mixin gains sg_ methods backed by SSBM
physics.  External library objects can be wrapped via SGAdapter.

Convention
----------
    sg_<method>     SSBM-patched version of an equivalent external method.
                    Uses DE440-measured GMs, CODATA constants, Forest-Ruth
                    integration, and SSBM EOS densities -- never the
                    external library's own approximations.

Why sg_ not override?
    External library code is NEVER modified.  Patching happens outward:
    callers migrate from lib.method() to sg.method() one call at a time.
    The external library remains available as a fallback and for comparison.

Example
-------
    # Before: astropy physics (CODATA, STP density, RK45 integrator)
    import astropy.constants as const
    GM = const.GM_sun.value

    # After: SSBM physics (DE440, EOS density, Forest-Ruth)
    from sigma_ground.field.interface.adapters import SGConstants
    GM = SGConstants.GM_sun
"""

from __future__ import annotations

import math
from typing import Any


class SGPhysicsMixin:
    """Mixin adding SSBM-physics sg_ methods to any class.

    Inherit alongside any class (including external library classes) to
    add SSBM-patched alternatives.  All sg_ methods are self-contained;
    they do not call super() and do not depend on the mixed-in class.
    """

    # ── gravitational parameters ─────────────────────────────────────────

    def sg_gm(self, body_name: str) -> float:
        """GM in m³/s² from DE440 measurements.

        More precise than CODATA-derived values used in astropy/scipy.
        Source: Folkner et al. (2014), ANCHOR_GM in local_library.interface.orbital.
        """
        from sigma_ground.field.interface.orbital import ANCHOR_GM
        _extra = {
            "Mercury": 22_032.09,
            "Venus":   324_858.59,
            "Uranus":    5_793_950.6103,
            "Neptune":   6_835_099.97,
        }
        km3 = ANCHOR_GM.get(body_name) or _extra.get(body_name)
        if km3 is None:
            raise KeyError(
                f"No DE440 GM for {body_name!r}. "
                f"Available: {list(ANCHOR_GM.keys()) + list(_extra.keys())}"
            )
        return km3 * 1e9  # km³/s² → m³/s²

    def sg_mass(self, body_name: str) -> float:
        """Mass in kg derived from DE440 GM and CODATA G.

        m = GM / G  — both from measured sources, not approximations.
        """
        from sigma_ground.field.constants import G
        return self.sg_gm(body_name) / G

    # ── density ─────────────────────────────────────────────────────────

    def sg_density(self, material_name: str, T_K: float = 293.0,
                   P_Pa: float = 101_325.0) -> float:
        """Density in kg/m³ via local_library element/material database.

        Unlike STP lookups, this uses the actual T and P.
        Flags any STP-only approximation via LOCAL_LIBRARY: approximation.

        Parameters
        ----------
        material_name : element symbol or common name (e.g. 'Fe', 'iron')
        T_K : temperature in Kelvin
        P_Pa : pressure in Pascals
        """
        try:
            from sigma_ground.field.interface.element import MaterialElement
            elem = MaterialElement(material_name)
            return elem.density_kg_m3(T_K=T_K, P_Pa=P_Pa)
        except Exception:
            # LOCAL_LIBRARY: approximation -- EOS not available for this material;
            # falling back to STP density from element table.
            from sigma_ground.field.interface.element import ElementalProperties
            props = ElementalProperties(material_name)
            return props.density_stp_kg_m3

    # ── integration ───────────────────────────────────────────────────────

    def sg_propagate_orbit(
        self,
        bodies: list,
        dt_s: float,
        n_steps: int,
        method: str = "forest_ruth",
        include_gr: bool = True,
    ) -> list:
        """Propagate N bodies using Forest-Ruth (default) or Verlet.

        Drop-in replacement for scipy.integrate orbit propagators, using
        the SSBM 4th-order symplectic integrator.

        Parameters
        ----------
        bodies : list of CelestialBody from sigma_ground.field.interface.nbody
        dt_s   : fixed timestep (seconds) -- do NOT vary; symplecticity requires fixed dt
        n_steps : number of steps
        method  : 'forest_ruth' (4th-order) or 'verlet' (2nd-order)
        include_gr : include 1PN Schwarzschild correction

        Returns
        -------
        list of CelestialBody at t0 + n_steps * dt_s
        """
        from sigma_ground.field.interface.nbody import NBodySystem
        system  = NBodySystem(bodies, include_gr=include_gr)
        step_fn = (system.forest_ruth_step if method == "forest_ruth"
                   else system.step)
        for _ in range(n_steps):
            step_fn(dt_s)
        return system.bodies


class SGAdapter:
    """Wraps any external library object, adding sg_ methods from SGPhysicsMixin.

    The wrapped object is accessible via .lib for non-patched operations;
    all sg_ calls use SSBM physics regardless of what the external library
    would return.

    Parameters
    ----------
    obj : external library object to wrap (astropy Body, jplephem kernel, etc.)

    Example
    -------
        from astropy.coordinates import get_body_barycentric
        from sigma_ground.field.interface.adapters import SGAdapter

        astropy_sun = get_body_barycentric('sun', time)
        wrapped = SGAdapter(astropy_sun)
        wrapped.sg_gm('Sun')          # DE440, not CODATA
        wrapped.lib.xyz               # fall through to astropy
    """

    def __init__(self, obj: Any) -> None:
        self.lib = obj  # unmodified external object

    def __getattr__(self, name: str) -> Any:
        if name.startswith("sg_"):
            raise AttributeError(
                f"SGAdapter has no SSBM method {name!r}. "
                f"Did you mean to add it to SGPhysicsMixin?"
            )
        return getattr(self.lib, name)

    # Inject all SGPhysicsMixin methods
    sg_gm             = SGPhysicsMixin.sg_gm
    sg_mass           = SGPhysicsMixin.sg_mass
    sg_density        = SGPhysicsMixin.sg_density
    sg_propagate_orbit = SGPhysicsMixin.sg_propagate_orbit
