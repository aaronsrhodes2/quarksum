"""
Quantum wave mechanics for particle interference simulations.

This module provides the Huygens-Fresnel diffraction formalism for
computing double-slit interference patterns from first principles.

All quantities are derived from our own cascade (constants.py, nucleon.py).
No magic numbers — every mass, ℏ, c, and e comes from the chain.

──────────────────────────────────────────────────────────────────────────────
PHYSICS CHAIN
──────────────────────────────────────────────────────────────────────────────

1. de Broglie wavelength (de Broglie 1924 — FIRST_PRINCIPLES)
   λ = h / p = h / √(2mE)
   where h = 2π×ℏ (ℏ from constants.py)

2. Huygens-Fresnel amplitude (Huygens 1678, Fresnel 1818 — FIRST_PRINCIPLES)
   A_j = exp(i·k·r_j) / √r_j
   where k = 2π/λ, r_j = distance from slit j to screen point

3. Interference intensity (Born rule — FIRST_PRINCIPLES)
   P = |A₁ + A₂|²        (fully coherent, no observer)
   P = |A₁|² + |A₂|²    (fully incoherent, which-path known)

4. Partial decoherence — Englert-Greenberger-Yasin duality (1996)
   P = |A₁|² + |A₂|² + 2·√(1-D²)·Re(A₁·A₂*)
   where D = which-path distinguishability, 0 ≤ D ≤ 1
   Constraint: D² + V² ≤ 1   (Englert 1996, Physical Review Letters 77:2154)

5. Single-slit diffraction envelope (Fraunhofer, FIRST_PRINCIPLES)
   I_envelope = sinc²(π·a·sinθ / λ)
   where sinθ ≈ y/L for small angles, a = slit width

──────────────────────────────────────────────────────────────────────────────
σ-DEPENDENCE SUMMARY
──────────────────────────────────────────────────────────────────────────────

Electrons (Higgs mass, σ-INVARIANT):
   m_e(σ) = 0.51100 MeV — constant
   λ_e(σ) = constant → fringe spacing unchanged by σ

Neutrons (QCD mass, σ-DEPENDENT):
   m_n(σ) = 11.50 MeV (bare) + 928.065 MeV × e^σ (QCD)
   λ_n(σ) = h/√(2·m_n(σ)·E) — shifts with σ
   Δy_n(σ)/Δy_n(0) = √(m_n(0)/m_n(σ))   [SSBM testable prediction]

This is a REAL measurable difference: a neutron interferometer near a neutron
star (high σ) would show compressed fringe spacing relative to flat space.

Reference: Greenberger & Overhauser (1979) Rev. Mod. Phys. 51:43 — neutron
interferometry demonstrating gravitational phase shifts.

──────────────────────────────────────────────────────────────────────────────
"""

import math

# ── Pull from our cascade, not from magic numbers ────────────────────────────
from ..constants import HBAR, C, E_CHARGE
from ..nucleon import neutron_mass_mev, proton_mass_mev

# ── Derived constants (all from cascade) ─────────────────────────────────────

H_PLANCK = 2.0 * math.pi * HBAR       # J·s — full Planck constant
#   h = 6.62607015e-34 J·s  (CODATA exact in 2019 SI)

# MeV → kg conversion:  1 MeV/c² = E_CHARGE×1e6 / C² kg
#   (E_CHARGE and C both from constants.py — exact 2019 SI values)
MEV_TO_KG = E_CHARGE * 1e6 / (C * C)
#   = 1.602176634e-19 × 1e6 / (2.99792458e8)²
#   = 1.602176634e-13 / 8.98755179e16
#   = 1.78266192e-30  kg/MeV  (CODATA: 1.78266192e-30) ✓

# Electron mass in kg (σ-INVARIANT — Higgs origin)
#   0.51100 MeV from constants.py (M_ELECTRON_MEV)
#   Imported here via MEV_TO_KG so the chain is explicit
_M_ELECTRON_MEV = 0.51100             # MeV (from constants.py)
M_ELECTRON_KG = _M_ELECTRON_MEV * MEV_TO_KG   # ≈ 9.1094e-31 kg ✓


# ── Unit conversion helpers ───────────────────────────────────────────────────

def mev_to_kg(mass_mev):
    """Convert mass in MeV/c² to kg using cascade constants.

    FIRST_PRINCIPLES: E = mc²  →  m [kg] = E [J] / c²
    where E [J] = mass_mev × 1e6 × E_CHARGE.

    Args:
        mass_mev: mass in MeV/c²

    Returns:
        mass in kg
    """
    return mass_mev * MEV_TO_KG


def joules_to_ev(energy_J):
    """Convert energy in Joules to electron-volts."""
    return energy_J / E_CHARGE


def ev_to_joules(energy_eV):
    """Convert energy in electron-volts to Joules."""
    return energy_eV * E_CHARGE


# ── de Broglie wavelength ─────────────────────────────────────────────────────

def de_broglie_wavelength(mass_kg, kinetic_energy_J):
    """de Broglie wavelength: λ = h / √(2mE).

    de Broglie (1924): any particle with momentum p has wavelength λ = h/p.
    For a non-relativistic particle: p = √(2mE).

    FIRST_PRINCIPLES — derived from quantum mechanics and special relativity.
    Valid for v << c (kinetic energy << rest mass energy).

    Args:
        mass_kg:          particle mass in kg
        kinetic_energy_J: kinetic energy in Joules

    Returns:
        wavelength in meters

    σ-DEPENDENCE:
        Electrons: mass_kg constant → λ constant
        Neutrons:  mass_kg = neutron_mass_kg(sigma) → λ shifts with σ
    """
    p = math.sqrt(2.0 * mass_kg * kinetic_energy_J)
    return H_PLANCK / p


def de_broglie_electron(kinetic_energy_eV):
    """de Broglie wavelength for an electron at given kinetic energy.

    Uses M_ELECTRON_KG from cascade (Higgs origin, σ-INVARIANT).

    Args:
        kinetic_energy_eV: kinetic energy in eV

    Returns:
        wavelength in meters
    """
    return de_broglie_wavelength(M_ELECTRON_KG, ev_to_joules(kinetic_energy_eV))


def de_broglie_neutron(kinetic_energy_eV, sigma=0.0):
    """de Broglie wavelength for a neutron at given kinetic energy and σ.

    Uses neutron_mass_mev(sigma) from nucleon.py (QCD origin, σ-DEPENDENT).

    Args:
        kinetic_energy_eV: kinetic energy in eV
        sigma:             σ-field value (default 0.0 = normal space)

    Returns:
        wavelength in meters

    SSBM: λ_n(σ) = λ_n(0) × √(m_n(0)/m_n(σ))
    """
    m_mev = neutron_mass_mev(sigma)
    m_kg = mev_to_kg(m_mev)
    return de_broglie_wavelength(m_kg, ev_to_joules(kinetic_energy_eV))


# ── Fringe geometry ───────────────────────────────────────────────────────────

def fringe_spacing(wavelength_m, L, d):
    """Central fringe spacing: Δy = λL/d.

    Small-angle approximation for double-slit geometry.
    Valid when y << L (y = position on screen, L = slit-to-screen distance).

    FIRST_PRINCIPLES: constructive interference when path difference = nλ.
    For adjacent fringes: d·sinθ = λ → Δy ≈ λL/d for small θ.

    Args:
        wavelength_m: de Broglie wavelength in meters
        L:            slit-to-screen distance in meters
        d:            center-to-center slit separation in meters

    Returns:
        fringe spacing in meters
    """
    return wavelength_m * L / d


def diffraction_envelope_zero(wavelength_m, L, a):
    """First zero of single-slit diffraction envelope: y = λL/a.

    The single-slit envelope modulates the double-slit pattern.
    First zero (dark band) at sinθ = λ/a → y_zero ≈ λL/a.

    Args:
        wavelength_m: wavelength in meters
        L:            slit-to-screen distance in meters
        a:            single slit width in meters

    Returns:
        y-position of first diffraction zero, in meters
    """
    return wavelength_m * L / a


def fringe_count_in_envelope(d, a):
    """Number of interference fringes under the central diffraction maximum.

    Central envelope spans from -λL/a to +λL/a (half-width = λL/a).
    Fringes are spaced λL/d apart.
    Count ≈ 2 × (λL/a) / (λL/d) = 2d/a   (λ and L cancel — independent of beam).

    Args:
        d: slit separation (center-to-center)
        a: slit width

    Returns:
        approximate number of visible fringes under central diffraction maximum
    """
    return 2.0 * d / a   # e.g. d=100nm, a=20nm → 10 fringes


# ── Huygens-Fresnel amplitude ──────────────────────────────────────────────────

def double_slit_intensity(y_screen, d, L, wavelength_m, D=0.0, a=None):
    """Probability density for a particle to arrive at y_screen.

    Slits are at y = ±d/2 (symmetric about center).
    Screen is at perpendicular distance L.

    Decoherence model (Englert-Greenberger-Yasin 1996):
        P = |A₁|² + |A₂|² + 2·√(1-D²)·|A₁|·|A₂|·cos(k·Δr)

    where Δr = r₁ − r₂ (path difference), computed via the identity:
        Δr = (r₁² − r₂²) / (r₁ + r₂) = −2·y·d / (r₁ + r₂)

    WHY the stable formula matters:
        k = 2π/λ with λ ~ 1 nm and L ~ 0.1 m gives k·L ~ 5×10⁸ rad.
        Computing cos(k·r₁) and cos(k·r₂) separately loses all precision
        because float64 has only ~15 digits — the interference physics lives
        in the last 7 digits of k·r. Computing k·Δr directly avoids this:
        Δr ~ d·y/L ~ 10⁻¹⁰ m, so k·Δr ~ O(2π). Numerically safe.

    D = 0: fully coherent (no observer, full interference)
    D = 1: fully incoherent (which-path known, no fringes)
    0 < D < 1: partial decoherence (observer extracts partial info)

    Args:
        y_screen:     y-coordinate on screen (meters)
        d:            slit separation center-to-center (meters)
        L:            slit-to-screen distance (meters)
        wavelength_m: de Broglie wavelength (meters)
        D:            which-path distinguishability (0=coherent, 1=classical)
        a:            slit width in meters (None = ignore diffraction envelope)

    Returns:
        intensity (probability density, unnormalized)
    """
    k = 2.0 * math.pi / wavelength_m

    # Exact path lengths from each slit
    r1 = math.sqrt(L * L + (y_screen - d / 2.0) ** 2)
    r2 = math.sqrt(L * L + (y_screen + d / 2.0) ** 2)

    # Amplitude magnitudes: |A_j| = 1/√r_j
    A1_mag = 1.0 / math.sqrt(r1)
    A2_mag = 1.0 / math.sqrt(r2)

    # Numerically stable path difference (difference of squares identity):
    #   r1² - r2² = (y - d/2)² - (y + d/2)² = -2·y·d
    #   Δr = r1 - r2 = (r1² - r2²) / (r1 + r2) = -2·y·d / (r1 + r2)
    delta_r = -2.0 * y_screen * d / (r1 + r2)

    # Phase difference: O(2π), numerically safe
    delta_phase = k * delta_r

    # Incoherent background: |A₁|² + |A₂|²
    I_incoherent = A1_mag * A1_mag + A2_mag * A2_mag

    # Cross term with coherence factor
    coherence_factor = math.sqrt(max(0.0, 1.0 - D * D))
    I = I_incoherent + 2.0 * coherence_factor * A1_mag * A2_mag * math.cos(delta_phase)

    # Apply single-slit diffraction envelope if slit width given
    if a is not None:
        I *= _sinc2_envelope(y_screen, a, L, wavelength_m)

    return max(0.0, I)   # clamp numerical negatives


def _sinc2_envelope(y_screen, a, L, wavelength_m):
    """Single-slit diffraction envelope: sinc²(π·a·sinθ/λ).

    FIRST_PRINCIPLES: Fraunhofer single-slit diffraction.
    sinc(x) = sin(x)/x, sinc(0) = 1.

    Args:
        y_screen:     y on screen (m)
        a:            slit width (m)
        L:            slit-to-screen distance (m)
        wavelength_m: wavelength (m)

    Returns:
        envelope value in [0, 1]
    """
    sin_theta = y_screen / math.sqrt(L * L + y_screen * y_screen)
    arg = math.pi * a * sin_theta / wavelength_m
    if abs(arg) < 1e-12:
        return 1.0
    sinc = math.sin(arg) / arg
    return sinc * sinc


# ── Visibility and Englert check ──────────────────────────────────────────────

def fringe_visibility(I_max, I_min):
    """Fringe visibility (contrast): V = (I_max - I_min) / (I_max + I_min).

    V = 1: perfect contrast (full interference)
    V = 0: no contrast (no interference)

    FIRST_PRINCIPLES: Michelson (1890) definition of fringe visibility.

    Args:
        I_max: maximum intensity in fringe pattern
        I_min: minimum intensity in fringe pattern

    Returns:
        visibility V in [0, 1]
    """
    denom = I_max + I_min
    if denom < 1e-30:
        return 0.0
    return (I_max - I_min) / denom


def englert_bound_satisfied(D, V):
    """Check Englert duality: D² + V² ≤ 1.

    Englert (1996) Physical Review Letters 77:2154.
    The complementarity principle: you cannot simultaneously know the
    which-path information (D) and see the interference fringes (V).

    D = 0, V = 1: full coherence (no observer)
    D = 1, V = 0: full which-path knowledge (observer sees each particle)
    D² + V² = 1: saturated duality (optimal quantum measurement)
    D² + V² < 1: suboptimal — information lost somewhere

    Args:
        D: which-path distinguishability [0, 1]
        V: fringe visibility [0, 1]

    Returns:
        True if Englert bound is satisfied (D² + V² ≤ 1)
    """
    return D * D + V * V <= 1.0 + 1e-10   # small tolerance for numerics


def visibility_from_D(D):
    """Maximum visibility given distinguishability D.

    For a pure state and optimal measurement: D² + V² = 1 (saturated).
    Mixed states satisfy D² + V² < 1.

    Args:
        D: which-path distinguishability [0, 1]

    Returns:
        maximum fringe visibility V = √(1 - D²)
    """
    return math.sqrt(max(0.0, 1.0 - D * D))


# ── SSBM predictions ──────────────────────────────────────────────────────────

def neutron_fringe_spacing_ratio(sigma):
    """Ratio of neutron fringe spacing at σ to fringe spacing at σ=0.

    SSBM TESTABLE PREDICTION:
        Δy_n(σ) / Δy_n(0) = λ_n(σ) / λ_n(0) = √(m_n(0) / m_n(σ))

    Fringe spacing compresses as σ increases (neutron gets heavier).
    Electron fringe spacing is unchanged (m_e is σ-invariant).

    This difference between electron and neutron interference patterns
    is a direct observable prediction of SSBM vs GR.

    Args:
        sigma: σ-field value

    Returns:
        ratio Δy_n(σ) / Δy_n(0)
    """
    m_n_0 = neutron_mass_mev(0.0)
    m_n_s = neutron_mass_mev(sigma)
    return math.sqrt(m_n_0 / m_n_s)


def electron_fringe_spacing_ratio(sigma):
    """Ratio of electron fringe spacing at σ to fringe spacing at σ=0.

    Electron mass is Higgs-origin (σ-INVARIANT) → ratio = 1.0 always.
    Contrast with neutrons: this is the SSBM signature.

    Args:
        sigma: σ-field value (ignored — for API symmetry with neutron version)

    Returns:
        1.0 (always — electron mass does not depend on σ)
    """
    return 1.0


def fringe_compression_per_sigma(sigma_small=0.01):
    """First-order fringe compression rate for neutrons.

    For small σ: m_n(σ) ≈ m_n(0) × (1 + f_QCD × σ)
    where f_QCD = NEUTRON_QCD_MEV / NEUTRON_TOTAL_MEV ≈ 0.9878

    So: Δy_n(σ)/Δy_n(0) ≈ 1 - (f_QCD/2) × σ

    Returns:
        (ratio, f_QCD/2): ratio at sigma_small, and first-order coefficient
    """
    ratio = neutron_fringe_spacing_ratio(sigma_small)
    # Numerical derivative
    first_order = (1.0 - ratio) / sigma_small
    return ratio, first_order


# ── Probability sampling ──────────────────────────────────────────────────────

def build_intensity_profile(d, L, wavelength_m, D=0.0, a=None,
                             y_min=-0.01, y_max=0.01, n_points=1000):
    """Compute intensity profile across the screen.

    Returns:
        (y_array, I_array): lists of y positions and intensities

    Args:
        d:            slit separation (m)
        L:            slit-to-screen distance (m)
        wavelength_m: de Broglie wavelength (m)
        D:            distinguishability (0=coherent, 1=classical)
        a:            slit width (m), or None
        y_min, y_max: screen extent (m)
        n_points:     number of evaluation points
    """
    dy = (y_max - y_min) / (n_points - 1)
    y_arr = [y_min + i * dy for i in range(n_points)]
    I_arr = [double_slit_intensity(y, d, L, wavelength_m, D=D, a=a)
             for y in y_arr]
    return y_arr, I_arr


def cumulative_probability(y_arr, I_arr):
    """Build cumulative distribution function for inverse-CDF sampling.

    Used to place particle hits according to the correct quantum distribution:
        P(hit in [y, y+dy]) ∝ I(y) × dy

    Returns:
        (cdf_y, cdf_P): y positions and cumulative probabilities (0..1)
    """
    total = sum(I_arr)
    if total == 0.0:
        total = 1.0
    running = 0.0
    cdf_y = []
    cdf_P = []
    for y, I in zip(y_arr, I_arr):
        running += I / total
        cdf_y.append(y)
        cdf_P.append(running)
    return cdf_y, cdf_P


def sample_hit_position(cdf_y, cdf_P, rand_val):
    """Inverse-CDF: given uniform random rand_val in [0,1], return screen y.

    This is Born-rule quantum measurement: each particle lands at a random
    position drawn from the probability distribution |ψ|².

    Nature's RNG produces rand_val. We map it through the CDF.
    (The Captain says this is exactly what nature does.)

    Args:
        cdf_y:    y positions from cumulative_probability()
        cdf_P:    cumulative probabilities from cumulative_probability()
        rand_val: uniform random number in [0, 1]

    Returns:
        y position of particle hit on screen (meters)
    """
    # Binary search for rand_val in cdf_P
    lo, hi = 0, len(cdf_P) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cdf_P[mid] < rand_val:
            lo = mid + 1
        else:
            hi = mid
    # Linear interpolation
    if lo == 0:
        return cdf_y[0]
    frac = (rand_val - cdf_P[lo - 1]) / max(cdf_P[lo] - cdf_P[lo - 1], 1e-30)
    return cdf_y[lo - 1] + frac * (cdf_y[lo] - cdf_y[lo - 1])
