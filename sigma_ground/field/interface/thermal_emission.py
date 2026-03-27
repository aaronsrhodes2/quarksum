"""
Thermal emission optics — Planck spectral radiance × Kirchhoff emissivity.

At high temperature, materials emit thermal radiation. The emitted spectrum is
the blackbody Planck function B(λ,T) modulated by the material's emissivity ε(λ).

Physics chain:
  T → B(λ,T) = 2hc²/λ⁵ / (exp(hc/λkT) − 1)   (FIRST_PRINCIPLES: Planck's law)
  optical constants n+ik → R(λ) = Fresnel reflectance
  ε(λ) = 1 − R(λ)                              (FIRST_PRINCIPLES: Kirchhoff's law)
  L(λ,T) = ε(λ) × B(λ,T)                       (FIRST_PRINCIPLES: emission law)
  Sample L at R/G/B → normalize → visible chromaticity

Kirchhoff's law of thermal radiation (1859):
  A body in thermal equilibrium emits as much as it absorbs at each wavelength.
  A good absorber is a good emitter: ε(λ) = α(λ) = 1 − R(λ) for an opaque
  flat surface (FIRST_PRINCIPLES, from thermodynamic equilibrium).

Temperature regimes and visible colour:
  < 700K (below Draper point): emission entirely in IR → no visible glow
  ~800K (Draper point, ~525°C): faint deep red glow becomes visible
  ~1000K: dull red-orange (forge glow)
  ~2000K: orange (molten metal)
  ~3000K: warm white (tungsten filament bulb)
  ~6000K: white (solar surface temperature)
  ~10000K: bluish-white

Emissivity source:
  Metals: ε(λ) = 1 − R(λ) using MEASURED n+ik from optics.py MEASURED_NK.
  Blackbody: ε(λ) = 1 (perfect absorber/emitter).

σ-dependence: NONE — all EM.
  Planck's law: quantum electrodynamics (photon statistics) → σ-INVARIANT.
  Optical constants n+ik: EM → σ-INVARIANT.
  Kirchhoff emissivity: ε = 1−R → EM → σ-INVARIANT.
  Colour: EM → σ-INVARIANT.

Origin tags:
  - Planck spectral radiance: FIRST_PRINCIPLES (Planck 1900, exact QM)
  - Kirchhoff emissivity ε = 1−R: FIRST_PRINCIPLES (thermodynamic equilibrium)
  - Metal optical constants n+ik: MEASURED (Palik 1985; Johnson & Christy 1972)
    (imported from optics.py MEASURED_NK)
  - Fresnel equation: FIRST_PRINCIPLES (Maxwell boundary conditions)
  - Draper point (~700K): MEASURED (Draper 1847, empirical onset of visible glow)

□σ = −ξR   (all quantities here: EM, σ-invariant)
"""

import math
from .optics import MEASURED_NK, _fresnel_r

# ── Fundamental constants (exact, 2019 SI definition) ─────────────────────
_H_PLANCK   = 6.62607015e-34    # J·s (exact)
_C_LIGHT    = 2.99792458e8      # m/s (exact)
_K_BOLTZMANN = 1.380649e-23     # J/K (exact)
_HC         = _H_PLANCK * _C_LIGHT   # 1.98644568×10⁻²⁵ J·m

# ── Visible wavelength sampling (CIE 1931 cone peaks) ─────────────────────
_LAMBDA_R_M  = 650e-9   # L-cone peak
_LAMBDA_G_M  = 550e-9   # M-cone peak
_LAMBDA_B_M  = 450e-9   # S-cone peak

# ── Draper point — empirical onset of visible thermal glow ────────────────
# Below this temperature, thermal emission is entirely in IR.
# Draper (1847): iron becomes faintly visible red at ~798K = 525°C.
# We use 700K as a conservative threshold for rendering purposes.
# MEASURED origin: Draper (1847); commonly cited as the "Draper point".
_DRAPER_POINT_K = 700.0

# ── Supported material keys ───────────────────────────────────────────────
# Maps key → emissivity source.
# 'blackbody' → ε = 1 (perfect emitter)
# metals → ε = 1 − R(λ) using MEASURED_NK from optics.py

THERMAL_EMISSION_MATERIALS = frozenset(
    ['blackbody'] + list(MEASURED_NK.keys())
)


# ── Planck spectral radiance ──────────────────────────────────────────────

def planck_spectral_radiance(lam_m: float, T: float) -> float:
    """Spectral radiance of a blackbody at temperature T.

    FIRST_PRINCIPLES (Planck 1900; exact quantum statistical mechanics):
      B(λ,T) = 2hc² / λ⁵ × 1 / (exp(hc/λkT) − 1)

    Physical meaning:
      The equilibrium radiation density emitted per unit area, per unit
      solid angle, per unit wavelength interval, by a perfect blackbody.

    Parameters
    ----------
    lam_m : float
        Wavelength in metres.
    T : float
        Temperature in Kelvin.

    Returns
    -------
    float
        Spectral radiance in W / (m² · sr · m).
        Returns 0.0 for T ≤ 0 or lam_m ≤ 0.
    """
    if T <= 0 or lam_m <= 0:
        return 0.0
    x = _HC / (lam_m * _K_BOLTZMANN * T)
    if x > 700.0:
        # exp(700) overflows double precision; Wien regime → B ≈ 0 for practical purposes
        return 0.0
    try:
        prefactor = 2.0 * _HC * _C_LIGHT / (lam_m**5)
        return prefactor / (math.exp(x) - 1.0)
    except (OverflowError, ZeroDivisionError):
        return 0.0


# ── Kirchhoff emissivity ──────────────────────────────────────────────────

def emissivity(material_key: str, lam_m: float) -> float:
    """Spectral emissivity ε(λ) for a material at wavelength lam_m.

    FIRST_PRINCIPLES (Kirchhoff 1859):
      For a flat opaque surface in thermal equilibrium:
        ε(λ) = α(λ) = 1 − R(λ)
      where R(λ) = Fresnel normal-incidence reflectance.

    Sources:
      'blackbody' → ε = 1 (exact, by definition)
      metals → ε = 1 − Fresnel(n, k)  [MEASURED n+ik from Palik / JC72]

    Parameters
    ----------
    material_key : str
        One of THERMAL_EMISSION_MATERIALS.
    lam_m : float
        Wavelength in metres.

    Returns
    -------
    float
        Emissivity ∈ (0, 1].
    """
    if material_key == 'blackbody':
        return 1.0

    # Find closest wavelength in the measured n+ik table for this material
    nk_table = MEASURED_NK[material_key]
    closest_lam = min(nk_table.keys(), key=lambda lam: abs(lam - lam_m))
    n, k = nk_table[closest_lam]
    R = _fresnel_r(n, k)
    return max(0.0, min(1.0, 1.0 - R))


# ── Visible glow threshold ────────────────────────────────────────────────

def is_visibly_glowing(T: float) -> bool:
    """Whether the thermal emission at temperature T is visible to the human eye.

    Below the Draper point (~700K), thermal emission is entirely in the
    infrared and is invisible. Above it, the Wien tail of the Planck function
    extends into the visible red, producing a faint glow.

    Threshold: 700K (MEASURED: Draper 1847, empirical).

    Parameters
    ----------
    T : float
        Temperature in Kelvin.

    Returns
    -------
    bool
        True if visibly glowing.
    """
    return T >= _DRAPER_POINT_K


# ── Visible emission colour ───────────────────────────────────────────────

def thermal_emission_rgb(material_key: str, T: float = 300.0):
    """Normalised visible chromaticity of thermal emission at temperature T.

    Pipeline:
      1. Compute L(λ,T) = ε(λ) × B(λ,T) at λ = 650nm, 550nm, 450nm.
      2. If T < _DRAPER_POINT_K or all channels ≈ 0: return (0, 0, 0).
      3. Normalise so max(L_r, L_g, L_b) = 1.0 → chromaticity.

    The normalised output gives the hue and relative saturation of the
    thermal glow, suitable for use as Material.color in MatterShaper.
    Absolute intensity scales with T⁴ (Stefan-Boltzmann) but the renderer
    handles intensity separately.

    σ-dependence: NONE — Planck + Kirchhoff + Fresnel are all EM.
    σ-INVARIANT.

    Parameters
    ----------
    material_key : str
        One of THERMAL_EMISSION_MATERIALS.
    T : float
        Temperature in Kelvin.

    Returns
    -------
    tuple of float
        (r, g, b) normalised chromaticity ∈ [0, 1].
        Returns (0, 0, 0) for T below the Draper point.
    """
    if not is_visibly_glowing(T):
        return (0.0, 0.0, 0.0)

    L_r = emissivity(material_key, _LAMBDA_R_M) * planck_spectral_radiance(_LAMBDA_R_M, T)
    L_g = emissivity(material_key, _LAMBDA_G_M) * planck_spectral_radiance(_LAMBDA_G_M, T)
    L_b = emissivity(material_key, _LAMBDA_B_M) * planck_spectral_radiance(_LAMBDA_B_M, T)

    L_max = max(L_r, L_g, L_b)
    if L_max <= 0.0:
        return (0.0, 0.0, 0.0)

    return (
        max(0.0, min(1.0, L_r / L_max)),
        max(0.0, min(1.0, L_g / L_max)),
        max(0.0, min(1.0, L_b / L_max)),
    )


# ── Diagnostic report ─────────────────────────────────────────────────────

def thermal_emission_report(material_key: str, T: float = 300.0) -> dict:
    """Full diagnostic report for thermal emission properties.

    Returns detailed provenance-tagged fields for debugging and inspection.

    σ-INVARIANT: all quantities are EM.

    Parameters
    ----------
    material_key : str
        Material key.
    T : float
        Temperature in Kelvin.

    Returns
    -------
    dict
        Diagnostic fields with origin tags.
    """
    B_r = planck_spectral_radiance(_LAMBDA_R_M, T)
    B_g = planck_spectral_radiance(_LAMBDA_G_M, T)
    B_b = planck_spectral_radiance(_LAMBDA_B_M, T)

    e_r = emissivity(material_key, _LAMBDA_R_M)
    e_g = emissivity(material_key, _LAMBDA_G_M)
    e_b = emissivity(material_key, _LAMBDA_B_M)

    r, g, b = thermal_emission_rgb(material_key, T)

    # Wien displacement: λ_max × T = b_Wien
    _WIEN_B = 2.897771955e-3   # m·K
    lam_peak_nm = (_WIEN_B / T * 1e9) if T > 0 else float('inf')

    origin = (
        "B(λ,T): FIRST_PRINCIPLES (Planck 1900 — exact quantum statistical mechanics: "
        "B = 2hc²/λ⁵ × 1/(exp(hc/λkT)−1)). "
        "ε(λ) = 1−R(λ): FIRST_PRINCIPLES (Kirchhoff 1859 — thermodynamic equilibrium). "
        "R(λ): FIRST_PRINCIPLES Fresnel + MEASURED n+ik (Palik 1985; Johnson & Christy 1972). "
        "Draper point threshold (~700K): MEASURED (Draper 1847). "
        "σ-INVARIANT: Planck is QED (photon statistics); n+ik and Fresnel are EM. "
        "□σ = −ξR."
    )

    return {
        'material'           : material_key,
        'T_K'                : T,
        'is_glowing'         : is_visibly_glowing(T),
        'wien_peak_nm'       : lam_peak_nm,
        'planck_650nm'       : B_r,
        'planck_550nm'       : B_g,
        'planck_450nm'       : B_b,
        'emissivity_650nm'   : e_r,
        'emissivity_550nm'   : e_g,
        'emissivity_450nm'   : e_b,
        'emission_650nm'     : e_r * B_r,
        'emission_550nm'     : e_g * B_g,
        'emission_450nm'     : e_b * B_b,
        'rgb_tuple'          : (r, g, b),
        'origin'             : origin,
    }
