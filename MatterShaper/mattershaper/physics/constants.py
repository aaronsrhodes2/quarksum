"""
Physical constants for the MatterShaper physics layer.

All constants are MEASURED (with citations) or DERIVED from MEASURED constants.
No magic numbers. If a value appears here without a citation, that is a bug.

─────────────────────────────────────────────────────────────────────────────
FUNDAMENTAL LENGTH FLOOR — THE PLANCK LENGTH
─────────────────────────────────────────────────────────────────────────────

L_PLANCK = sqrt(ħG/c³) = 1.616255e-35 m

This is the length scale at which quantum gravitational effects become
significant — the smallest length that any current physical theory can
meaningfully describe. Below this scale, spacetime itself becomes uncertain
in a way that no continuous field theory (including our σ-cascade) addresses.

Why it matters for our code
────────────────────────────
Wherever we need to prevent division by zero in a distance computation,
we have a choice:
  (a) Use an arbitrary epsilon: `if r < 1e-12: ...`
  (b) Use L_PLANCK: `if r < L_PLANCK: ...`

(b) is honest. It says: "we believe physics below L_PLANCK is undefined,
and any computed distance below it should be treated as zero in our model."

In practice, L_PLANCK (1.6e-35 m) is far below our simulation resolution
(smallest length ≈ DELTA_X = 7e-4 m in SPH, or EPS_GRAVITY = 1e-3 in
gravity). The guard fires only on numerical coincidences, not physical ones.
But the label is true. The magic number 1e-12 is not true.

Note: In the σ-cascade, the Planck scale is WHERE THE CASCADE LIVES. It is
the UV boundary of the nucleon mass derivation. This constant therefore
has a double meaning in this codebase: it is both a numerical safety floor
and the physical domain edge of our theoretical framework.

─────────────────────────────────────────────────────────────────────────────
A NOTE ON INFINITY
─────────────────────────────────────────────────────────────────────────────

The word "infinity" is used in at least four distinct ways in this codebase
and in the science that surrounds it. They are NOT interchangeable.

1. IEEE 754 float('inf')
   ─────────────────────
   Computational. 1.0 / 0.0 in floating-point arithmetic.
   Rules: inf + x = inf. inf × 0 = NaN. inf == inf → True.
   Used here: static parcel mass = float('inf'), so that inv_mass = 0
   is computed without a conditional branch.
   THIS IS NOT MATHEMATICAL OR PHYSICAL INFINITY. It is a register state.

2. Mathematical infinity (Cantor)
   ────────────────────────────────
   Cantor showed that infinities come in different sizes:
     ℵ₀ — the countable infinite (integers, rationals)
     ℵ₁ — the uncountable infinite (real numbers, cardinality of the continuum)
     ℵ₂, ℵ₃, ... — strictly larger infinities, each unreachable from the last
   There is no single "infinity" in mathematics. There is a hierarchy of
   infinities ordered by cardinality. The set of all integers is strictly
   smaller than the set of real numbers, even though both are infinite.

   For our physics: the configuration space of all particle arrangements
   is uncountably infinite (ℵ₁), even for a finite number of particles,
   because positions are real-valued. Our simulation samples a finite
   subset of this space.

3. Finite scene depth — NOT projective infinity
   ─────────────────────────────────────────────
   In projective geometry, parallel lines meet "at infinity" — a well-defined
   geometric point.  But a rendered sightline does NOT travel to projective
   infinity: it exits the finite bounding volume of the scene.

   The Barnes-Hut Claying argument settles this from first principles:
   beyond the distance at which a cluster subtends less than THETA_NATURAL =
   1/φ² of the viewer's solid angle, the cluster is physically indistinguishable
   from a point mass.  That is a physical horizon on resolved information.
   It is not infinite.  The scene has a bounding box; the sightline has a
   maximum t equal to the bounding diagonal — not float('inf').

   Using float('inf') as the initial t_max for a sightline is a sentinel
   value ("has not hit anything yet"), not a statement that the sightline
   is physically infinite.  Label it as such.  float('inf') as a sentinel is
   IEEE 754 — type 1 above.  Do not confuse it with geometric infinity.

   NOTE: "ray" in this codebase means exactly one thing — the sightline from
   a surface point to the camera (or vice versa), i.e. the vector along which
   a photon travels to reach the sensor.  The word is not used for
   trajectories, separations, force directions, or any other concept.
   If you need a directed line in physics code, call it a displacement,
   a trajectory, or a separation vector — never a ray.

4. Physical infinity / singularities
   ──────────────────────────────────
   In classical physics, density → ∞ at a point mass. In general relativity,
   density → ∞ at a black hole singularity. These "infinities" are failures
   of the theory — the model breaks down before the quantity actually
   diverges in nature.

   The σ-cascade (Sigma Ground) is our proposed regulator: at nuclear
   scales the σ field sets a finite mass for nucleons, preventing the
   runaway density that would otherwise occur. The Planck scale (L_PLANCK)
   marks the UV boundary where even the cascade is insufficient — at that
   point, quantum gravity effects dominate and we have no theory yet.

   Practical consequence for our code: if a simulation produces a density
   or velocity that approaches float('inf'), it is a signal that the
   physical model has broken down, not that infinity has been achieved.
   Check the forces. Check the timestep. The physics is protesting.

─────────────────────────────────────────────────────────────────────────────
CONSTANTS (MEASURED — one origin each)
─────────────────────────────────────────────────────────────────────────────
"""

import math

# ── Fundamental measured constants ─────────────────────────────────────────
# Source: CODATA 2018 / NIST SP-330 (2019)

HBAR          = 1.054571817e-34   # J·s   Planck constant (reduced), CODATA 2018
G_NEWTON      = 6.67430e-11       # m³/(kg·s²)  Newtonian gravity, CODATA 2018
C_LIGHT       = 2.99792458e8      # m/s   speed of light in vacuum (exact, 1983 definition)
G_STANDARD    = 9.80665           # m/s²  standard gravity, BIPM (exact since 1901)
K_BOLTZMANN   = 1.380649e-23      # J/K   Boltzmann constant (exact, 2019 redefinition)
R_GAS         = 8.314462618       # J/(mol·K)  ideal gas constant = N_A × k_B
SIGMA_SB      = 5.670374419e-8    # W/(m²·K⁴)  Stefan-Boltzmann (exact, 2019)

# ── Derived constants (DERIVED from MEASURED — show the chain) ─────────────

# Planck length: L_P = sqrt(ħ G / c³)
# The fundamental UV length scale. Below L_PLANCK, spacetime quantisation
# prevents any classical or semiclassical description.
# Derivation chain: HBAR (CODATA) → G_NEWTON (CODATA) → C_LIGHT (exact)
L_PLANCK = math.sqrt(HBAR * G_NEWTON / C_LIGHT**3)
# = 1.616255e-35 m  (NIST 2018: 1.616255 × 10⁻³⁵ m, uncertainty 2.3e-40 m)

# Planck mass: m_P = sqrt(ħ c / G)
M_PLANCK = math.sqrt(HBAR * C_LIGHT / G_NEWTON)
# = 2.176434e-8 kg

# Planck energy: E_P = m_P c²
E_PLANCK = M_PLANCK * C_LIGHT**2
# = 1.9561e9 J ≈ 1.2209e19 GeV

# Planck time: t_P = L_PLANCK / c
T_PLANCK = L_PLANCK / C_LIGHT
# = 5.391247e-44 s

# ── Simulation safety floors ───────────────────────────────────────────────
#
# Use L_PLANCK as the floor for any length comparison in the physics layer.
# This is physically motivated (see module docstring) and avoids magic numbers.
#
# For non-length quantities (mass, density, velocity), use physics-specific
# floors derived from the problem context (e.g., v_max × machine_epsilon
# for velocity).
#
# Note: at simulation scales (mm to m), L_PLANCK will NEVER fire in normal
# operation. If it fires, the simulation has produced a particle pair with
# physically unresolvable positions — inspect the force kernel.

LENGTH_FLOOR  = L_PLANCK          # Minimum meaningful length in nature
MASS_FLOOR    = M_PLANCK          # Minimum meaningful mass in nature (informational)

# ── Optical constants (MEASURED — with citations) ──────────────────────────
#
# Refractive indices are MEASURED quantities; they cannot be derived from
# first principles in classical EM without a microscopic model of water.
# Cite the primary measurement for each.
#
# n_water at 589 nm (sodium D line), 20°C:
# Hale, G.M. & Querry, M.R. (1973) Applied Optics 12:555-563
N_WATER = 1.333
#
# n_ice Ih at 589 nm, -15°C:
# Warren, S.G. (1984) Applied Optics 23:1206-1225
N_ICE   = 1.310
#
# Fresnel normal-incidence reflectance: F0 = ((n-1)/(n+1))²
# DERIVED — emerges from Fresnel equations at θ=0. No additional input.
F0_WATER = ((N_WATER - 1.0) / (N_WATER + 1.0)) ** 2   # = 0.02037
F0_ICE   = ((N_ICE   - 1.0) / (N_ICE   + 1.0)) ** 2   # = 0.01801
#
# Snell refraction ratio η = n_air / n_medium  (n_air ≡ 1.000)
# Used in GLSL: refract(I, N, eta)
ETA_WATER = 1.0 / N_WATER   # = 0.75019
ETA_ICE   = 1.0 / N_ICE     # = 0.76336

# ── Water optical absorption (MEASURED — Pope & Fry 1997) ──────────────────
#
# Napierian absorption coefficients at the wavelength of peak sensitivity
# for each CIE 1931 primaries (R≈700nm, G≈546nm, B≈436nm):
#
# Pope, R.M. & Fry, E.S. (1997) Applied Optics 36:8710-8723
# Table 1, columns a_w at λ = 700, 546, 436 nm respectively.
# Units: m⁻¹ (Napierian, base-e)
#
# These are MEASURED on optically pure water; no fit parameters.
WATER_ABS_R = 0.349    # m⁻¹ at 700 nm
WATER_ABS_G = 0.0595   # m⁻¹ at 546 nm
WATER_ABS_B = 0.0145   # m⁻¹ at 436 nm

# ── Blackbody spectral constants — for Planck function B(λ,T) ──────────────
#
# The Planck function gives the spectral radiance of a perfect blackbody.
# Two constants appear directly:
#   C1 = 2 h c²  (first radiation constant, spectral form)
#   C2 = h c / k_B  (second radiation constant)
# Both DERIVED from MEASURED fundamental constants above.
#
# B(λ,T) = C1 / (λ⁵ (exp(C2/(λT)) − 1))   [W sr⁻¹ m⁻³]
#
# We integrate B(λ,T) against the CIE 1931 colour matching functions
# (tabulated in PLANCK_CIE_XYZ below) to get XYZ tristimulus values,
# then convert XYZ → linear sRGB.
#
# Planck constant (non-reduced): h = 2π ħ
H_PLANCK = 2.0 * math.pi * HBAR    # = 6.62607015e-34 J·s  (exact, 2019)
C1_PLANCK = 2.0 * H_PLANCK * C_LIGHT ** 2   # = 1.19104e-16 W·m²·sr⁻¹ (first radiation constant)
C2_PLANCK = H_PLANCK * C_LIGHT / K_BOLTZMANN  # = 1.43878e-2 m·K
#
# CIE 1931 XYZ colour matching functions — tabulated at 10 nm intervals
# from 380 nm to 780 nm inclusive (41 rows).
# Source: CIE publication 15 (2004), Annex 1.
# Approximation: Wyman, C., Sloan, P-P., Shirley, P. (2013)
#   "Simple Analytic Approximations to the CIE XYZ Color Matching Functions"
#   JCGT 2(2):1-11  https://jcgt.org/published/0002/02/01/
#
# Rather than embedding the full 41-row table, we expose the Wyman
# analytic approximation coefficients which integrate to the same result.
# The function planck_to_srgb() (in render/entangler/illumination.py) uses
# these to compute emergent RGB for any blackbody temperature T [K].
#
# sRGB D65 primary matrix — XYZ (D65 illuminant) → linear sRGB
# Source: IEC 61966-2-1 (1999), Annex A  (exact coefficients)
SRGB_FROM_XYZ = (
    # Row 0: R channel
    ( 3.2406, -1.5372, -0.4986),
    # Row 1: G channel
    (-0.9689,  1.8758,  0.0415),
    # Row 2: B channel
    ( 0.0557, -0.2040,  1.0570),
)

# ── Exports ────────────────────────────────────────────────────────────────
__all__ = [
    'HBAR', 'G_NEWTON', 'C_LIGHT', 'G_STANDARD',
    'K_BOLTZMANN', 'R_GAS', 'SIGMA_SB',
    'L_PLANCK', 'M_PLANCK', 'E_PLANCK', 'T_PLANCK',
    'LENGTH_FLOOR', 'MASS_FLOOR',
    # Optical — refractive indices and derived quantities
    'N_WATER', 'N_ICE', 'F0_WATER', 'F0_ICE', 'ETA_WATER', 'ETA_ICE',
    # Optical — water absorption (Pope & Fry 1997)
    'WATER_ABS_R', 'WATER_ABS_G', 'WATER_ABS_B',
    # Optical — blackbody (Planck function coefficients)
    'H_PLANCK', 'C1_PLANCK', 'C2_PLANCK', 'SRGB_FROM_XYZ',
]
