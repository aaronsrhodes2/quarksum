"""SGConstants -- SSBM-patched physics constants.

Drop-in replacement for astropy.constants and scipy.constants.
All values sourced from sigma_ground.field.constants (CODATA measured) or
DE440/JPL (gravitational parameters).

Usage
-----
    # Before: astropy (CODATA 2014, less precise GM)
    import astropy.constants as const
    G   = const.G.value          # 6.674e-11 m³ kg⁻¹ s⁻²
    GM  = const.GM_sun.value     # 1.32712440018e20 m³/s²

    # After: SSBM (CODATA 2018 + DE440, more precise)
    from sigma_ground.field.interface.adapters.constants import SGConstants
    G   = SGConstants.G          # 6.67430e-11 m³ kg⁻¹ s⁻²
    GM  = SGConstants.GM_sun     # 1.327124400419e20 m³/s²

External library compatibility
-------------------------------
    sg_patch_astropy()  -- injects SGConstants values into astropy.constants
    sg_patch_scipy()    -- makes scipy.constants.G match SSBM value

    These are NON-DESTRUCTIVE: the original values are saved as
    astropy.constants.G_original, etc.
"""

from __future__ import annotations

import math
from typing import Any

from sigma_ground.field.constants import (
    G, C, HBAR, M_SUN_KG, YEAR_S, H0,
    M_PLANCK_KG, L_PLANCK,
)
from sigma_ground.field.interface.orbital import ANCHOR_GM


class SGConstants:
    """SSBM-ground physics constants.

    All attributes mirror the naming of astropy.constants for easy migration.
    sg_ prefixed aliases are also provided.
    """

    # ── Fundamental (CODATA 2018, from sigma_ground.field.constants) ──────────
    G    = G          # 6.67430e-11 m³ kg⁻¹ s⁻²   (gravitational constant)
    c    = C          # 2.99792458e8 m/s             (speed of light, exact)
    hbar = HBAR       # 1.054571817e-34 J·s          (reduced Planck)
    h    = HBAR * 2 * math.pi                        # Planck constant

    # ── Derived (from G, c above -- no magic numbers) ────────────────────
    M_Planck = M_PLANCK_KG    # Planck mass    √(ℏc/G)
    L_Planck = L_PLANCK       # Planck length  ℏ/(M_Planck c)

    # ── Astrophysical (DE440-measured, from sigma_ground.field.interface.orbital) ─
    # All GM in m³/s² (= km³/s² × 1e9)
    GM_sun     = ANCHOR_GM["Sun"]     * 1e9  # 1.3271244004193938e+20 m³/s²
    GM_earth   = ANCHOR_GM["Earth"]   * 1e9  # 3.9860043543600e+14 m³/s²
    GM_mars    = ANCHOR_GM["Mars"]    * 1e9
    GM_jupiter = ANCHOR_GM["Jupiter"] * 1e9
    GM_saturn  = ANCHOR_GM["Saturn"]  * 1e9
    GM_uranus  = ANCHOR_GM["Uranus"]  * 1e9
    GM_neptune = ANCHOR_GM["Neptune"] * 1e9

    # Solar mass from GM_sun / G (more precise than direct measurement)
    M_sun  = ANCHOR_GM["Sun"] * 1e9 / G   # kg
    M_earth= ANCHOR_GM["Earth"] * 1e9 / G # kg

    # ── Time / distance ───────────────────────────────────────────────────
    yr        = YEAR_S              # Julian year, s (IAU exact)
    au        = 1.495978707e11      # 1 AU in metres (IAU 2012, exact by definition)
    pc        = 3.085677581e16      # 1 parsec in metres  (= AU / tan(1 arcsec))
    ly        = C * YEAR_S          # 1 light-year in metres (derived from c, yr)

    # ── Cosmological ─────────────────────────────────────────────────────
    H0        = H0                  # Hubble constant s⁻¹  (Planck 2018: 67.4 km/s/Mpc)

    # ── sg_ aliases (for callers using the sg_ prefix convention) ────────
    sg_G       = G
    sg_c       = C
    sg_GM_sun  = ANCHOR_GM["Sun"] * 1e9
    sg_M_sun   = ANCHOR_GM["Sun"] * 1e9 / G
    sg_au      = 1.495978707e11

    # ── Comparison: astropy CODATA 2014 values (for reference only) ──────
    # These show the delta between CODATA 2014 and DE440 + CODATA 2018.
    # Do NOT use these in calculations -- kept for cross-checks only.
    _astropy_G        = 6.67408e-11     # astropy default (CODATA 2014)
    _astropy_GM_sun   = 1.32712440018e20  # astropy default (older TDB estimate)
    _astropy_GM_earth = 3.986004418e14    # astropy default

    @classmethod
    def delta_GM_sun_ppm(cls) -> float:
        """Parts-per-million difference between DE440 and astropy GM_sun."""
        return 1e6 * abs(cls.GM_sun - cls._astropy_GM_sun) / cls._astropy_GM_sun

    @classmethod
    def all_gm(cls) -> dict[str, float]:
        """All DE440 GM values in m³/s²."""
        return {k: v * 1e9 for k, v in ANCHOR_GM.items()}


# ── Optional library patching ─────────────────────────────────────────────

def sg_patch_astropy() -> dict[str, Any]:
    """Inject SSBM values into astropy.constants (non-destructive).

    Saves originals as <name>_original so they can be restored.
    Returns a dict of {name: (original, patched)} for logging.

    Call once at application startup, before any astropy imports that
    consume the constants.

    Raises ImportError if astropy is not installed.
    """
    import astropy.constants as aconst

    patched: dict[str, Any] = {}

    def _patch(name: str, sg_value: float, unit: str) -> None:
        import astropy.constants
        orig = getattr(aconst, name, None)
        if orig is not None and not hasattr(aconst, f"{name}_original"):
            setattr(aconst, f"{name}_original", orig)
        try:
            import astropy.units as u
            new_const = astropy.constants.Constant(
                abbrev=name, name=f"sg_{name}",
                value=sg_value, unit=unit,
                uncertainty=0.0, reference="SSBM/DE440",
                system="si",
            )
            setattr(astropy.constants, name, new_const)
            patched[name] = (orig, new_const)
        except Exception:
            pass  # astropy version incompatibility -- skip silently

    _patch("G",       SGConstants.G,       "m3 / (kg s2)")
    _patch("GM_sun",  SGConstants.GM_sun,  "m3 / s2")
    _patch("M_sun",   SGConstants.M_sun,   "kg")
    return patched


def sg_patch_scipy() -> dict[str, Any]:
    """Inject SSBM G into scipy.constants (non-destructive).

    Raises ImportError if scipy is not installed.
    """
    import scipy.constants as sc
    patched: dict[str, Any] = {}

    if not hasattr(sc, "G_original"):
        sc.G_original = sc.G  # type: ignore[attr-defined]
    sc.G = SGConstants.G      # type: ignore[attr-defined]
    patched["G"] = (sc.G_original, SGConstants.G)
    return patched
