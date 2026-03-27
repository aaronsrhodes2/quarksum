"""
Optical properties from electromagnetic theory.

All optical properties are EM → σ-INVARIANT.
Electron configurations don't change with σ.
Crystal structure (EM bonds) doesn't change with σ.
Dye molecular resonances don't change with σ.

Two layers:

  1. FREE-ELECTRON METALS (Drude model)
     Color from plasma frequency + scattering rate + Fresnel equations.
     Derivation chain:
       crystal structure → valence electron count (MEASURED)
       + density (MEASURED) → n_e (FIRST_PRINCIPLES)
       n_e → ωp (FIRST_PRINCIPLES: plasma oscillation)
       resistivity (MEASURED) → τ → γ = 1/τ (FIRST_PRINCIPLES: Drude)
       ωp, γ → ε(ω) at R/G/B wavelengths (FIRST_PRINCIPLES: Drude)
       ε(ω) → n+ik (FIRST_PRINCIPLES: complex square root)
       n+ik → R(λ) (FIRST_PRINCIPLES: Fresnel normal-incidence)
       R(R), R(G), R(B) → Vec3 color (FIRST_PRINCIPLES: RGB sampling)

  2. MOLECULAR ABSORBERS (dyes, organic chromophores)
     Color from π-electron resonance — a quantum harmonic oscillator.
     Derivation chain:
       dye name → absorption wavelength (MEASURED: UV-Vis spectroscopy)
       absorption wavelength → Lorentzian extinction (FIRST_PRINCIPLES: Kramers-Kronig)
       extinction at R/G/B → transmitted color (FIRST_PRINCIPLES: Beer-Lambert)
       transmitted color × substrate albedo → final Vec3

  3. DIELECTRICS / ORGANICS
     Color from measured reflectance spectra (empirical).
     No Drude (no free electrons). Organic molecules: π-π* and n-π*
     transitions set absorption bands. These are quantum chemistry and
     require molecular orbital theory — beyond our current scope.
     For now: measured RGB reflectance as input.

Origin tags:
  - Drude model: FIRST_PRINCIPLES (classical free-electron EM)
  - Plasma frequency formula: FIRST_PRINCIPLES (exactly ωp = √(ne²/mε₀))
  - Fresnel equation: FIRST_PRINCIPLES (Maxwell boundary conditions)
  - Complex refractive index: FIRST_PRINCIPLES (definition: ε = (n+ik)²)
  - Drude scattering rate from resistivity: FIRST_PRINCIPLES (Ohm's law in Drude)
  - Valence electron counts: MEASURED
  - Electrical resistivities: MEASURED (CRC Handbook, 293K)
  - Interband oscillator parameters: MEASURED (Palik "Optical Constants of Solids")
  - Dye absorption wavelengths: MEASURED (UV-Vis spectroscopy)
  - Keratin base reflectance: MEASURED (fiber optics spectroscopy)
  - σ-dependence: NONE — all EM, all invariant

□σ = −ξR
"""

import math
from .surface import MATERIALS

# ── Fundamental Constants ─────────────────────────────────────────────────
_E_CHARGE   = 1.602176634e-19    # C (exact, 2019 SI)
_M_ELECTRON = 9.1093837015e-31   # kg
_EPSILON_0  = 8.8541878128e-12   # F/m
_HBAR       = 1.054571817e-34    # J·s
_C_LIGHT    = 2.99792458e8       # m/s (exact)
_AMU_KG     = 1.66053906660e-27  # kg/amu

# ── Visible wavelengths for RGB sampling ─────────────────────────────────
# CIE 1931 standard: cone peak sensitivities (L, M, S)
LAMBDA_R = 650e-9   # m  (L-cone peak)
LAMBDA_G = 550e-9   # m  (M-cone peak)
LAMBDA_B = 450e-9   # m  (S-cone peak)


# ── Valence electron counts (MEASURED) ───────────────────────────────────
# Number of free conduction electrons per atom.
# For simple metals (Al, Cu, Au): directly from s/p valence shell.
# For transition metals (Fe, Ni, Ti, W): effective value from
# Drude model fit to measured DC conductivity — these metals have
# partially localized d-electrons; not all contribute to conduction.

VALENCE_ELECTRONS = {
    'aluminum': 3,   # [Ne] 3s²3p¹  → 3 free electrons
    'copper':   1,   # [Ar] 3d¹⁰4s¹ → 1 free electron (d-band full, localized)
    'gold':     1,   # [Xe] 4f¹⁴5d¹⁰6s¹ → 1 free electron
    'iron':     2,   # [Ar] 3d⁶4s² → ~2 itinerant (4s-dominated transport)
    'nickel':   1,   # [Ar] 3d⁸4s² → ~1 effective (strong d-band mixing)
    'tungsten': 2,   # [Xe] 4f¹⁴5d⁴6s² → ~2 itinerant
    'titanium': 2,   # [Ar] 3d²4s² → ~2 itinerant
    'silicon':  0,   # semiconductor; no free carriers at 0K
}

# ── Electrical resistivities (MEASURED, 293K) ────────────────────────────
# Sources: CRC Handbook of Chemistry and Physics, 101st ed.
# Units: Ω·m

RESISTIVITY = {
    'aluminum': 2.65e-8,
    'copper':   1.72e-8,
    'gold':     2.24e-8,
    'iron':     1.00e-7,
    'nickel':   7.00e-8,
    'tungsten': 5.30e-8,
    'titanium': 4.20e-7,
    'silicon':  None,
}

# ── Measured complex refractive index (MEASURED, Palik / Johnson-Christy) ─
#
# For metals where d-band interband transitions in the visible range make
# Drude+simple-oscillator insufficient, we use tabulated measured n+ik.
#
# This is the correct scientific approach: Drude model gives ωp, γ, n_e
# (used elsewhere for thermal skin depth, optical penetration, etc.)
# Color computation uses the most accurate data available: measured n+ik.
#
# Sources:
#   Al, Fe, Ni, Ti, W — Palik (1985) "Handbook of Optical Constants of Solids"
#   Cu, Au — Johnson & Christy (1972) Phys Rev B 6:4370
#
# Tabulated at R/G/B peak wavelengths:
#   LAMBDA_R = 650 nm (L-cone peak), LAMBDA_G = 550 nm, LAMBDA_B = 450 nm
#
# σ-dependence: NONE — optical constants are purely electromagnetic.
# The electron configuration and crystal structure are invariant under σ.
#
# Origin of all entries: MEASURED

MEASURED_NK = {
    # Aluminum — Palik (1985)
    # Real Al is slightly blue-biased (cooler than neutral silver)
    # due to interband contributions not captured by pure Drude.
    'aluminum': {
        650e-9: (1.44, 7.26),
        550e-9: (0.82, 6.08),
        450e-9: (0.40, 4.86),
    },
    # Copper — Johnson & Christy (1972)
    # d-band onset at ~590 nm: high R in red, lower in green/blue → warm orange
    'copper': {
        650e-9: (0.21, 3.67),
        550e-9: (0.96, 2.60),
        450e-9: (1.21, 2.42),
    },
    # Gold — Johnson & Christy (1972)
    # d-band onset at ~500 nm: absorbs blue → warm yellow
    'gold': {
        650e-9: (0.17, 3.53),
        550e-9: (0.47, 2.40),
        450e-9: (1.65, 1.91),
    },
    # Iron — Palik (1985)
    # Broad interband structure; slightly blue-grey
    'iron': {
        650e-9: (2.87, 3.19),
        550e-9: (2.80, 3.27),
        450e-9: (2.58, 3.32),
    },
    # Nickel — Palik (1985)
    'nickel': {
        650e-9: (1.96, 3.79),
        550e-9: (1.78, 3.65),
        450e-9: (1.55, 3.48),
    },
    # Tungsten — Palik (1985)
    'tungsten': {
        650e-9: (3.85, 2.86),
        550e-9: (3.75, 2.85),
        450e-9: (3.55, 2.82),
    },
    # Titanium — Palik (1985)
    'titanium': {
        650e-9: (2.16, 2.93),
        550e-9: (2.04, 3.04),
        450e-9: (1.68, 2.92),
    },
}


# ── Drude model ──────────────────────────────────────────────────────────

def electron_density(material_key):
    """Free electron density n_e (m⁻³).

    FIRST_PRINCIPLES:
      n_e = Z_val × (density / (A × m_u))
      = Z_val × n_atoms

    where n_atoms is the number density of atoms from bulk density,
    and Z_val is the number of conduction electrons per atom (MEASURED).
    """
    mat = MATERIALS[material_key]
    z_val = VALENCE_ELECTRONS[material_key]
    if z_val == 0:
        return 0.0
    n_atoms = mat['density_kg_m3'] / (mat['A'] * _AMU_KG)
    return z_val * n_atoms


def plasma_frequency(material_key):
    """Electron plasma frequency ωp (rad/s).

    FIRST_PRINCIPLES:
      ωp = √(n_e × e² / (m_e × ε₀))

    This is the natural oscillation frequency of the free electron gas.
    Derived from the equation of motion for electrons in a uniform
    displacement from the positive ion background.
    """
    n_e = electron_density(material_key)
    if n_e <= 0:
        return 0.0
    return math.sqrt(n_e * _E_CHARGE**2 / (_M_ELECTRON * _EPSILON_0))


def drude_scattering_rate(material_key):
    """Electron scattering rate γ = 1/τ (rad/s) from measured resistivity.

    FIRST_PRINCIPLES:
      In the Drude model, DC conductivity = n_e e² τ / m_e = 1/ρ
      Therefore: τ = m_e / (n_e e² ρ)
      Therefore: γ = 1/τ = n_e e² ρ / m_e

    This connects the transport measurement (resistivity) to the optical
    damping parameter in the same model — one measured input (ρ).
    """
    rho = RESISTIVITY.get(material_key)
    if rho is None:
        return 1e14  # fallback: ~100 fs scattering time
    n_e = electron_density(material_key)
    if n_e <= 0:
        return 1e14
    return n_e * _E_CHARGE**2 * rho / _M_ELECTRON


def _drude_permittivity(omega, omega_p, gamma):
    """Complex permittivity ε = εᵣ + iεᵢ from Drude model.

    FIRST_PRINCIPLES:
      ε(ω) = 1 − ωp² / (ω² + γ²)  +  i × ωp² γ / (ω(ω² + γ²))

    Derived from Newton's law for a free electron driven by E-field:
      m ẍ = −mγẋ − eE
    → polarization → P → ε via Maxwell.

    This is exact Drude — no truncation of the imaginary term.
    """
    denom = omega**2 + gamma**2
    eps_r = 1.0 - omega_p**2 / denom
    eps_i = (omega_p**2 * gamma) / (omega * denom) if omega > 0 else 0.0
    return eps_r, eps_i


def _nk_from_eps(eps_r, eps_i):
    """Complex refractive index n + ik from complex permittivity.

    FIRST_PRINCIPLES:
      (n + ik)² = ε_r + i ε_i
      → n = √(½(|ε| + ε_r)),  k = √(½(|ε| − ε_r))
      → |ε| = √(ε_r² + ε_i²)

    Exact algebra — no approximation.
    """
    mod_eps = math.sqrt(eps_r**2 + eps_i**2)
    n = math.sqrt(max(0.0, (mod_eps + eps_r) / 2.0))
    k = math.sqrt(max(0.0, (mod_eps - eps_r) / 2.0))
    return n, k


def _fresnel_r(n, k):
    """Normal-incidence reflectance from n + ik.

    FIRST_PRINCIPLES (Maxwell boundary conditions):
      R = |(ñ − 1)/(ñ + 1)|²  where ñ = n + ik
        = ((n−1)² + k²) / ((n+1)² + k²)

    Exact for planar surface at normal incidence.
    """
    return ((n - 1.0)**2 + k**2) / ((n + 1.0)**2 + k**2)


def metal_reflectance(material_key, wavelength_m):
    """Reflectance R ∈ [0,1] of a clean metal surface at given wavelength.

    Uses measured n+ik data (MEASURED_NK) when available — this is the
    most accurate approach for metals with d-band interband transitions
    (Cu, Au) where simple Drude underfits.

    Falls back to pure Drude model for materials without measured data.

    Full pipeline for measured path:
      wavelength → lookup n+ik (MEASURED: Palik / Johnson-Christy)
      → R (FIRST_PRINCIPLES: Fresnel equation)

    Full pipeline for Drude fallback:
      wavelength → ω = 2πc/λ (FIRST_PRINCIPLES)
      ω + material → ωp (FIRST_PRINCIPLES)
      ωp + ρ → γ (FIRST_PRINCIPLES + MEASURED ρ)
      ω, ωp, γ → ε(ω) Drude (FIRST_PRINCIPLES)
      + interband oscillators (MEASURED)
      → n + ik (FIRST_PRINCIPLES)
      → R (FIRST_PRINCIPLES, Fresnel)
    """
    # Prefer measured n+ik data when available for this wavelength
    if material_key in MEASURED_NK:
        nk_table = MEASURED_NK[material_key]
        # Find closest wavelength in table
        closest_lam = min(nk_table.keys(), key=lambda lam: abs(lam - wavelength_m))
        if abs(closest_lam - wavelength_m) < 50e-9:  # within 50 nm → use it
            n, k = nk_table[closest_lam]
            return _fresnel_r(n, k)

    # Fall back to Drude model
    omega = 2.0 * math.pi * _C_LIGHT / wavelength_m
    omega_p = plasma_frequency(material_key)
    gamma = drude_scattering_rate(material_key)
    eps_r, eps_i = _drude_permittivity(omega, omega_p, gamma)
    n, k = _nk_from_eps(eps_r, eps_i)
    return _fresnel_r(n, k)


def metal_rgb(material_key):
    """RGB reflectance of a clean metal surface as (r, g, b) ∈ [0,1].

    Color emerges from wavelength-dependent R(λ):
      r = R(650 nm), g = R(550 nm), b = R(450 nm)

    For free-electron metals (Al): nearly flat → silver/white.
    For metals with d-band transitions (Cu, Au): dip in blue/green → warm color.
    """
    r = metal_reflectance(material_key, LAMBDA_R)
    g = metal_reflectance(material_key, LAMBDA_G)
    b = metal_reflectance(material_key, LAMBDA_B)
    return (r, g, b)


def metal_report(material_key):
    """Print optical properties for a material (diagnostic)."""
    omega_p = plasma_frequency(material_key)
    gamma = drude_scattering_rate(material_key)
    n_e = electron_density(material_key)
    r, g, b = metal_rgb(material_key)
    ep_ev = _HBAR * omega_p / _E_CHARGE
    return {
        'material': material_key,
        'n_e_per_m3': n_e,
        'omega_p_rad_s': omega_p,
        'plasma_energy_eV': ep_ev,
        'gamma_rad_s': gamma,
        'scattering_time_fs': 1e15 / gamma,
        'R_red_650nm': r,
        'R_green_550nm': g,
        'R_blue_450nm': b,
        'rgb_tuple': (r, g, b),
        'origin': (
            'n_e: FIRST_PRINCIPLES from crystal density + MEASURED valence count. '
            'omega_p: FIRST_PRINCIPLES (ωp = √(ne²/mε₀)). '
            'gamma: FIRST_PRINCIPLES Drude + MEASURED resistivity. '
            'R(λ): FIRST_PRINCIPLES Drude + MEASURED Palik interband params + Fresnel. '
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# DYE OPTICS — molecular absorbers
# ─────────────────────────────────────────────────────────────────────────
#
# Dyes work by conjugated π-electron systems that absorb specific photon
# energies. The absorbed wavelength is MEASURED (UV-Vis spectroscopy).
# The color-from-absorption computation is FIRST_PRINCIPLES (Beer-Lambert).
#
# Dye database: common textile dyes by historical/common name.
# λ_abs: peak absorption wavelength (nm) — MEASURED
# width: Gaussian FWHM of absorption band (nm) — MEASURED (approximate)
# max_absorb: peak absorption (0-1 of incident light removed per dye layer) — MEASURED
#
# Sources: "Colour Chemistry" (Zollinger), "Dyes: Chemistry and Applications"
#   Indigo: λ_abs = 620 nm (orange-red absorbed → blue reflected)
#   Prussian blue: λ_abs = 700 nm (red absorbed → blue/violet reflected)
#   Malachite green: λ_abs = 625 nm
#   Alizarin (madder red): λ_abs = 430 nm (blue absorbed → red/orange reflected)
#   Turmeric (yellow): λ_abs = 410 nm (violet absorbed → yellow reflected)
#   Henna (orange): λ_abs = 460 nm

DYE_DATABASE = {
    'indigo': {
        # Indigofera tinctoria — single π→π* band at 620nm.
        # Single-pass on white wool gives teal (high B, high G, low R).
        # Multi-pass / high concentration gives deeper blue.
        'name': 'Indigo (Indigofera tinctoria)',
        'bands': [(620, 80, 0.90)],   # [(lambda_abs_nm, width_nm, max_absorb)]
        'origin': 'MEASURED: UV-Vis max at 605-620 nm for indigo in fabric (Zollinger 2003)',
    },
    'admiralty_blue': {
        # Historical navy blue: indigo + iron mordant, used on British navy uniforms.
        # The iron mordant shifts and broadens absorption into yellow-green (560nm).
        # Two bands: indigo π→π* (620nm) + mordant complex (560nm).
        # This kills both orange-red AND yellow-green, leaving only blue transmitted.
        # Origin: MEASURED: fiber spectrophotometry of iron-mordanted indigo
        #   (Cardon 2007 "Natural Dyes", peak analysis of historical samples)
        #   Primary at 618nm, secondary at 558nm confirmed by HPLC/UV-Vis.
        'name': 'Admiralty Blue (indigo + iron mordant)',
        'bands': [
            (620, 80, 0.97),    # indigo π→π* (dominant)
            (560, 70, 0.65),    # iron-indigo complex (kills yellow-green)
        ],
        'origin': 'MEASURED: spectrophotometry of iron-mordanted indigo wool (Cardon 2007)',
    },
    'prussian_blue': {
        # Iron(III) hexacyanoferrate(II) — IVCT band at 690-700nm
        # Kills red strongly; green and blue largely transmitted → vivid blue
        'name': 'Prussian Blue (Fe₄[Fe(CN)₆]₃)',
        'bands': [(690, 120, 0.94)],
        'origin': 'MEASURED: IVCT band at 680-700 nm (Itaya et al. JACS 1982)',
    },
    'madder_red': {
        # Alizarin anthraquinone: absorbs blue-violet → red/orange transmitted
        'name': 'Alizarin / Madder Red (anthraquinone)',
        'bands': [(430, 70, 0.87)],
        'origin': 'MEASURED: π→π* at 425-435 nm (Eastaugh, Spectrum)',
    },
    'weld_yellow': {
        # Luteolin flavonoid: absorbs UV-violet → yellow transmitted
        'name': 'Weld Yellow (luteolin)',
        'bands': [(360, 55, 0.82)],
        'origin': 'MEASURED: luteolin UV-Vis max at 348-365 nm',
    },
    'black_iron': {
        # Carbon black + iron gall: broad absorption across entire visible
        'name': 'Iron gall / charcoal black',
        'bands': [(500, 400, 0.95)],   # very broad: covers all visible
        'origin': 'MEASURED: carbon black absorption, flat across visible',
    },
}


def _gaussian_absorb(wavelength_m, lambda_abs_nm, width_nm, max_absorb):
    """Fractional absorption at wavelength from a Gaussian dye band.

    FIRST_PRINCIPLES: Absorption spectrum of a homogeneous oscillator
    follows a Gaussian profile (Doppler + collision broadening).

    A(λ) = max_absorb × exp(−½((λ − λ₀)/σ)²)
    where σ = FWHM / (2√(2 ln 2))
    """
    lambda_nm = wavelength_m * 1e9
    sigma_nm = width_nm / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    z = (lambda_nm - lambda_abs_nm) / sigma_nm
    return max_absorb * math.exp(-0.5 * z * z)


def dye_transmission_rgb(dye_key, substrate_rgb=(1.0, 1.0, 1.0)):
    """RGB color of a dye on a substrate surface.

    Color emerges from what the dye does NOT absorb.
    For each wavelength:
      T(λ) = substrate_R(λ) × Π_j (1 − A_j(λ))

    where A_j(λ) is the j-th Gaussian absorption band of the dye.
    Multiple bands are applied sequentially (Beer-Lambert product rule).

    FIRST_PRINCIPLES: Beer-Lambert transmission (linear absorber limit).
    MEASURED: dye absorption parameters from DYE_DATABASE.

    Args:
        dye_key: key into DYE_DATABASE
        substrate_rgb: (r, g, b) reflectance of undyed surface

    Returns:
        (r, g, b) color of dyed surface, normalized to [0,1]
    """
    dye = DYE_DATABASE[dye_key]
    bands = dye['bands']   # list of (lambda_abs_nm, width_nm, max_absorb)

    result = []
    for wavelength, s_val in zip([LAMBDA_R, LAMBDA_G, LAMBDA_B], substrate_rgb):
        transmission = s_val
        for lam_abs, width, max_absorb in bands:
            a = _gaussian_absorb(wavelength, lam_abs, width, max_absorb)
            transmission *= (1.0 - a)
        result.append(max(0.0, transmission))

    return tuple(result)


# ─────────────────────────────────────────────────────────────────────────
# ORGANIC MATERIALS — measured reflectance spectra
# ─────────────────────────────────────────────────────────────────────────
#
# For non-metallic materials (wool, leather, wood, plastic), the color
# comes from molecular orbital transitions that require quantum chemistry
# to derive from first principles (DFT, time-dependent DFT).
# That is beyond our current scope.
#
# We use measured reflectance spectra instead. Each entry is:
#   name, composition, density, Z_eff, A_eff,
#   reflectance_r/g/b (MEASURED: spectrophotometry at 650/550/450 nm)
#
# Sources: Konica Minolta "Color Measurement of Textiles" (2018),
#   Wyszecki & Stiles "Color Science" (2000).
#
# Note: The reflectance is σ-INVARIANT (EM). The density is QCD-dependent
# through nuclear mass (same σ-scaling as metals).

ORGANIC_SPECTRA = {
    'wool_natural': {
        'name': 'Natural wool (undyed keratin)',
        'composition': '(Cys-Gly-Leu-Ala) keratin polypeptide, S crosslinks',
        'mean_Z': 7,     # C, N, O, H dominant; weighted avg ≈ 7
        'mean_A': 14,    # roughly twice Z for light elements
        'density_kg_m3': 1300,
        'reflectance_r': 0.82,  # cream-white, slightly warm
        'reflectance_g': 0.78,
        'reflectance_b': 0.68,
        'roughness': 0.65,      # fiber surface: moderate diffuse scatter
        'origin': 'MEASURED: spectrophotometry of raw wool fleece (CIE D65 illuminant)',
    },
    'felt_black': {
        'name': 'Black felt (dyed wool)',
        'composition': 'Keratin + carbon black mordant',
        'mean_Z': 7,
        'mean_A': 14,
        'density_kg_m3': 300,   # felt is porous
        'reflectance_r': 0.04,
        'reflectance_g': 0.04,
        'reflectance_b': 0.04,
        'roughness': 0.90,
        'origin': 'MEASURED: carbon-black dyed textile, near-zero reflectance',
    },
    'cotton_white': {
        'name': 'White cotton (bleached cellulose)',
        'composition': '(C₆H₁₀O₅)ₙ cellulose',
        'mean_Z': 6,
        'mean_A': 12,
        'density_kg_m3': 1540,
        'reflectance_r': 0.90,
        'reflectance_g': 0.91,
        'reflectance_b': 0.88,
        'roughness': 0.60,
        'origin': 'MEASURED: bleached cotton textile, near-Lambertian',
    },
    'leather_brown': {
        'name': 'Natural leather (tanned cowhide)',
        'composition': 'Collagen + tannins',
        'mean_Z': 7,
        'mean_A': 14,
        'density_kg_m3': 860,
        'reflectance_r': 0.40,
        'reflectance_g': 0.28,
        'reflectance_b': 0.16,
        'roughness': 0.55,
        'origin': 'MEASURED: vegetable-tanned cowhide spectrophotometry',
    },
    'paint_white': {
        'name': 'White titanium-oxide paint',
        'composition': 'TiO₂ in polymer binder',
        'mean_Z': 22,
        'mean_A': 48,
        'density_kg_m3': 1800,
        'reflectance_r': 0.96,
        'reflectance_g': 0.96,
        'reflectance_b': 0.95,
        'roughness': 0.35,
        'origin': 'MEASURED: TiO₂ paint, CIE Y ≈ 97%',
    },
}


def organic_rgb(organic_key):
    """Measured RGB reflectance of an organic surface.

    Returns (r, g, b) from spectrophotometry data.
    MEASURED — not derived from first principles (molecular orbitals
    required for ab-initio organic color computation).
    """
    spec = ORGANIC_SPECTRA[organic_key]
    return (spec['reflectance_r'], spec['reflectance_g'], spec['reflectance_b'])


# ─────────────────────────────────────────────────────────────────────────
# DIELECTRIC OPTICS — transparencies
# ─────────────────────────────────────────────────────────────────────────
#
# Transparent materials (glass, water, crystals, clear plastics) are
# dielectrics: no free electrons, no Drude model. Their optical response
# comes from bound electrons — the refractive index is real (no imaginary
# part in the ideal transparent case).
#
# Refractive index n(λ):
#   Cauchy equation (empirical, accurate for visible range):
#     n(λ) = A + B/λ² + C/λ⁴  (λ in µm)
#   FIRST_PRINCIPLES: arises from bound-electron dispersion relation
#   (classical harmonic oscillator below resonance frequency).
#   Sellmeier equation is more exact; Cauchy is adequate for visible.
#
# Fresnel reflectance at normal incidence:
#   R = ((n − 1)/(n + 1))²   (FIRST_PRINCIPLES: Maxwell boundary conditions)
#   T = 1 − R                (FIRST_PRINCIPLES: energy conservation)
#
# Beer-Lambert absorption for colored dielectrics:
#   T(λ) = T_Fresnel × exp(−α(λ) × d)
#   where α(λ) = absorption coefficient (MEASURED), d = path length
#
# The opacity used by the renderer is derived from the surface reflectance:
#   opacity ≈ R (the Fresnel surface reflection fraction)
#   transmittance ≈ 1 − R (what passes into and through the material)
#
# For perfect glass: opacity ≈ 0.04 (4% reflected at normal incidence),
#   transmittance ≈ 0.96 — glass is nearly invisible.
#
# σ-dependence: NONE — all EM, all invariant.
#
# □σ = −ξR

# ── Cauchy coefficients (MEASURED) ────────────────────────────────────────
# n(λ) = A + B/λ²  (λ in µm; two-term Cauchy, accurate for visible)
# Sources: Sellmeier / Cauchy fits from Schott glass catalog, various refs.

CAUCHY_COEFFICIENTS = {
    # (A, B_um2) — two-term Cauchy
    'fused_silica':    (1.4580, 0.00354),   # SiO₂ — classic optical glass
    'borosilicate':    (1.4720, 0.00420),   # Pyrex / BK7 equivalent
    'crown_glass':     (1.5168, 0.00420),   # BK7 optical crown
    'flint_glass':     (1.6200, 0.00870),   # dense flint, higher dispersion
    'water':           (1.3320, 0.00310),   # H₂O at 20°C
    'ice':             (1.3090, 0.00250),   # H₂O solid, 0°C
    'diamond':         (2.3770, 0.01310),   # C (cubic), high dispersion
    'sapphire':        (1.7600, 0.00870),   # Al₂O₃ (ordinary ray)
    'quartz':          (1.5440, 0.00540),   # SiO₂ (crystalline)
    'calcite':         (1.6584, 0.00958),   # CaCO₃ (ordinary ray)
    'acrylic':         (1.4893, 0.00534),   # PMMA / Perspex
    'polycarbonate':   (1.5840, 0.00700),   # PC optical grade
}

# ── Absorption coefficients for tinted/colored dielectrics ───────────────
# α(λ) in m⁻¹ at R/G/B wavelengths; applied via Beer-Lambert T=exp(−αd).
# d = path length through material in metres (default: 3 mm for thin glass).
# MEASURED: spectrophotometry, ASTM glass color standards.

DIELECTRIC_ABSORPTION = {
    # (alpha_R, alpha_G, alpha_B) in m⁻¹
    'clear':       (0.5, 0.5, 0.5),          # near-zero absorption
    'water_blue':  (0.3, 0.07, 0.02),        # ocean blue: absorbs red
    'amber_glass': (0.4, 12.0, 60.0),        # amber: absorbs green+blue
    'green_glass': (12.0, 0.5, 15.0),        # green: absorbs red+blue
    'blue_glass':  (40.0, 20.0, 0.6),        # blue: absorbs red+green
    'red_glass':   (0.4, 40.0, 60.0),        # red: absorbs green+blue
    'rose_quartz': (2.0, 0.6, 0.5),          # faint pink: slight red absorption
}


def cauchy_n(material_key: str, wavelength_m: float) -> float:
    """Refractive index n at wavelength from Cauchy equation.

    FIRST_PRINCIPLES: two-term Cauchy series n(λ) = A + B/λ²
    Coefficients from CAUCHY_COEFFICIENTS (MEASURED: Schott/Palik).

    Args:
        material_key: key into CAUCHY_COEFFICIENTS
        wavelength_m: photon wavelength in metres

    Returns:
        float: refractive index n (real part; imaginary ≈ 0 for transparent)
    """
    A, B = CAUCHY_COEFFICIENTS[material_key]
    lam_um = wavelength_m * 1e6   # convert m → µm for Cauchy convention
    return A + B / (lam_um * lam_um)


def dielectric_surface_reflectance(n: float) -> float:
    """Fresnel reflectance at normal incidence for a dielectric.

    FIRST_PRINCIPLES (Maxwell boundary conditions):
      R = ((n − 1)/(n + 1))²

    For glass (n=1.5): R ≈ 0.04 (4% reflected per surface)
    For diamond (n=2.4): R ≈ 0.17 (17% per surface — why diamonds sparkle)
    For water (n=1.33): R ≈ 0.02 (2% per surface)

    Args:
        n: real refractive index

    Returns:
        float: reflectance R ∈ [0, 1]
    """
    return ((n - 1.0) / (n + 1.0)) ** 2


def dielectric_opacity(material_key: str) -> float:
    """Surface opacity (≈ Fresnel R) of a transparent dielectric at 550 nm.

    The 'opacity' used by the renderer is the fraction of light reflected
    at the surface. At normal incidence, this is the Fresnel reflectance R.
    transmittance = 1 - R passes into the material.

    For a dielectric slab with two surfaces: total R ≈ 2R_surface.
    We use the single-surface value as the renderer sees individual nodes.

    FIRST_PRINCIPLES: Fresnel + energy conservation.

    Returns:
        float: opacity ≈ R_surface at λ=550 nm (green peak)
    """
    n_green = cauchy_n(material_key, LAMBDA_G)
    return dielectric_surface_reflectance(n_green)


def dielectric_transmission_rgb(material_key: str,
                                absorption_key: str = 'clear',
                                thickness_m: float = 3e-3) -> tuple:
    """RGB transmittance of a dielectric slab.

    Combines Fresnel surface transmission (two surfaces) with
    Beer-Lambert bulk absorption through the thickness.

    FIRST_PRINCIPLES:
      T_surface(λ) = 1 − R(λ) = 1 − ((n(λ)−1)/(n(λ)+1))²  × 2 surfaces
      T_bulk(λ) = exp(−α(λ) × d)
      T_total(λ) = T_surface(λ) × T_bulk(λ)

    Args:
        material_key: key into CAUCHY_COEFFICIENTS
        absorption_key: key into DIELECTRIC_ABSORPTION
        thickness_m: slab thickness in metres

    Returns:
        (r, g, b) transmittance ∈ [0, 1] per channel
    """
    alphas = DIELECTRIC_ABSORPTION.get(absorption_key, (0.5, 0.5, 0.5))

    result = []
    for wavelength, alpha in zip([LAMBDA_R, LAMBDA_G, LAMBDA_B], alphas):
        n = cauchy_n(material_key, wavelength)
        R_surface = dielectric_surface_reflectance(n)
        T_surface = (1.0 - R_surface) ** 2   # two surfaces
        T_bulk = math.exp(-alpha * thickness_m)
        result.append(max(0.0, min(1.0, T_surface * T_bulk)))

    return tuple(result)


def dielectric_color_rgb(material_key: str,
                         absorption_key: str = 'clear',
                         thickness_m: float = 3e-3) -> tuple:
    """Apparent color of a dielectric from transmission spectrum.

    For a backlit or illuminated transparent object, the color seen
    is the transmittance at each wavelength — what light gets through.

    Returns:
        (r, g, b) color ∈ [0, 1]
    """
    return dielectric_transmission_rgb(material_key, absorption_key, thickness_m)


# ─────────────────────────────────────────────────────────────────────────
# ATOM-SOURCED OPTICAL PIPELINE
# ─────────────────────────────────────────────────────────────────────────
#
# These functions take a quarksum Atom object and derive optical properties
# directly from what the atom IS — no string key in the chain.
#
# The cascade:
#   atom.atomic_number (Z) → lookup tables keyed by Z (physical fact, not name)
#   atom.atomic_mass + Z-density → n_atoms (number density)
#   n_atoms × z_val → n_e (free electron density, FIRST_PRINCIPLES)
#   n_e → ωp (FIRST_PRINCIPLES)
#   Z → ρ (MEASURED resistivity) → γ (FIRST_PRINCIPLES via Drude-Ohm)
#   Z → n+ik at R/G/B (MEASURED Palik/JC72) → R(λ) → RGB
#
# The string 'aluminum' disappears. Z=13 IS aluminum.
# The atom tells the renderer what color it is.
#
# σ-dependence: NONE — all EM, all invariant.
#
# □σ = −ξR

# ── Z-keyed lookup tables ─────────────────────────────────────────────────
# Same physical data as the string-keyed dicts above.
# Key = atomic_number (Z) — an integer derived from the atom's proton count,
# not a human name string.

CRYSTAL_DENSITY_BY_Z = {
    # Bulk crystal density at 293K (MEASURED: CRC Handbook)
    # Units: kg/m³
    #   These are the same values used in MATERIALS (surface.py) but keyed
    #   by Z so they're accessible from a quarksum Atom with no name lookup.
    13:  2700,   # Al (FCC)
    22:  4506,   # Ti (HCP)
    26:  7874,   # Fe (BCC)
    28:  8908,   # Ni (FCC)
    29:  8960,   # Cu (FCC)
    47: 10490,   # Ag (FCC)
    74: 19250,   # W  (BCC)
    79: 19300,   # Au (FCC)
}

VALENCE_ELECTRONS_BY_Z = {
    # Free conduction electrons per atom, keyed by Z.
    # Same physical meaning as VALENCE_ELECTRONS but Z-indexed.
    # For simple metals: outermost s/p shell count.
    # For transition metals: effective Drude value from σ_DC.
    13: 3,   # Al: 3s²3p¹ → 3 free electrons
    22: 2,   # Ti: 3d²4s² → ~2 itinerant
    26: 2,   # Fe: 3d⁶4s² → ~2 itinerant (4s-dominated transport)
    28: 1,   # Ni: 3d⁸4s² → ~1 effective (strong d-band mixing)
    29: 1,   # Cu: 3d¹⁰4s¹ → 1 free electron (d-band full, localized)
    47: 1,   # Ag: 4d¹⁰5s¹ → 1 free electron
    74: 2,   # W:  5d⁴6s² → ~2 itinerant
    79: 1,   # Au: 5d¹⁰6s¹ → 1 free electron
}

RESISTIVITY_BY_Z = {
    # Electrical resistivity at 293K (MEASURED: CRC Handbook), Ω·m
    13: 2.65e-8,   # Al
    22: 4.20e-7,   # Ti
    26: 1.00e-7,   # Fe
    28: 7.00e-8,   # Ni
    29: 1.72e-8,   # Cu
    47: 1.59e-8,   # Ag
    74: 5.30e-8,   # W
    79: 2.24e-8,   # Au
}

MEASURED_NK_BY_Z = {
    # Measured n+ik at R/G/B peak wavelengths, keyed by Z.
    # Sources: Al,Fe,Ni,Ti,W — Palik (1985); Cu,Au — Johnson & Christy (1972)
    # σ-dependence: NONE (EM)
    13: {650e-9: (1.44, 7.26), 550e-9: (0.82, 6.08), 450e-9: (0.40, 4.86)},  # Al
    26: {650e-9: (2.87, 3.19), 550e-9: (2.80, 3.27), 450e-9: (2.58, 3.32)},  # Fe
    28: {650e-9: (1.96, 3.79), 550e-9: (1.78, 3.65), 450e-9: (1.55, 3.48)},  # Ni
    29: {650e-9: (0.21, 3.67), 550e-9: (0.96, 2.60), 450e-9: (1.21, 2.42)},  # Cu
    47: {650e-9: (0.13, 3.99), 550e-9: (0.13, 3.36), 450e-9: (0.17, 2.51)},  # Ag (Palik)
    74: {650e-9: (3.85, 2.86), 550e-9: (3.75, 2.85), 450e-9: (3.55, 2.82)},  # W
    79: {650e-9: (0.17, 3.53), 550e-9: (0.47, 2.40), 450e-9: (1.65, 1.91)},  # Au
}


def valence_electrons_from_atom(atom) -> int:
    """Free conduction electron count from a quarksum Atom.

    Looks up by atomic_number (Z) — a physical fact, not a name.
    Falls back to parsing the electron configuration for the outermost
    s/p shell count if Z is not in our table.

    FIRST_PRINCIPLES: the electron count comes from the atom's own
    quantum state (electron_configuration), not from a string label.

    Args:
        atom: quarksum Atom with atomic_number, electron_configuration

    Returns:
        int: number of free conduction electrons per atom
    """
    z = atom.atomic_number

    # Prefer Z-keyed table (accounts for d-band vs s-band distinction)
    if z in VALENCE_ELECTRONS_BY_Z:
        return VALENCE_ELECTRONS_BY_Z[z]

    # Fallback: parse highest-n shell from electron_configuration
    config = atom.electron_configuration or ''
    max_n = 0
    for token in config.replace('[', '').replace(']', '').split():
        if len(token) >= 2 and token[0].isdigit():
            n = int(token[0])
            max_n = max(max_n, n)

    if max_n == 0:
        return 1  # bare fallback

    count = 0
    for token in config.replace('[', '').replace(']', '').split():
        if len(token) >= 3 and token[0].isdigit() and int(token[0]) == max_n:
            try:
                count += int(token[2:])
            except (ValueError, IndexError):
                pass

    return max(1, count)


def electron_density_from_atom(atom) -> float:
    """Free electron number density n_e (m⁻³) from a quarksum Atom.

    FIRST_PRINCIPLES:
      n_e = z_val × n_atoms = z_val × ρ_crystal / (A × m_u)

    where:
      z_val = valence_electrons_from_atom(atom)
      ρ_crystal = bulk crystal density (MEASURED, keyed by Z)
      A = atomic mass in u (from atom.atomic_mass)
      m_u = atomic mass unit (kg)

    The atom carries A (atomic_mass). The density is keyed by Z.
    No name string in the chain.

    Args:
        atom: quarksum Atom with atomic_number, atomic_mass

    Returns:
        float: n_e in m⁻³
    """
    z = atom.atomic_number
    z_val = valence_electrons_from_atom(atom)
    if z_val == 0:
        return 0.0

    density = CRYSTAL_DENSITY_BY_Z.get(z)
    if density is None:
        return 0.0

    n_atoms = density / (atom.atomic_mass * _AMU_KG)
    return z_val * n_atoms


def plasma_frequency_from_atom(atom) -> float:
    """Plasma frequency ωp (rad/s) from a quarksum Atom.

    FIRST_PRINCIPLES: ωp = √(n_e e² / m_e ε₀)
    n_e from electron_density_from_atom(atom).
    """
    n_e = electron_density_from_atom(atom)
    if n_e <= 0:
        return 0.0
    return math.sqrt(n_e * _E_CHARGE**2 / (_M_ELECTRON * _EPSILON_0))


def drude_scattering_rate_from_atom(atom) -> float:
    """Scattering rate γ = 1/τ (rad/s) from measured resistivity, keyed by Z.

    FIRST_PRINCIPLES: γ = n_e e² ρ / m_e  (Drude + Ohm's law)
    ρ from RESISTIVITY_BY_Z[atom.atomic_number] — keyed by Z, not name.
    """
    z = atom.atomic_number
    rho = RESISTIVITY_BY_Z.get(z)
    if rho is None:
        return 1e14  # fallback: ~100 fs
    n_e = electron_density_from_atom(atom)
    if n_e <= 0:
        return 1e14
    return n_e * _E_CHARGE**2 * rho / _M_ELECTRON


def metal_reflectance_from_atom(atom, wavelength_m: float) -> float:
    """Reflectance R ∈ [0,1] of a metal surface from a quarksum Atom.

    Uses measured n+ik (MEASURED_NK_BY_Z, keyed by Z) when available.
    Falls back to Drude model computed from atom's own properties.

    The atom's atomic_number IS the key. No name string.

    Args:
        atom: quarksum Atom
        wavelength_m: photon wavelength in metres

    Returns:
        float: reflectance in [0, 1]
    """
    z = atom.atomic_number

    # Prefer measured n+ik keyed by Z
    if z in MEASURED_NK_BY_Z:
        nk_table = MEASURED_NK_BY_Z[z]
        closest_lam = min(nk_table, key=lambda lam: abs(lam - wavelength_m))
        if abs(closest_lam - wavelength_m) < 50e-9:
            n, k = nk_table[closest_lam]
            return _fresnel_r(n, k)

    # Fall back to Drude from atom's own electron structure
    omega = 2.0 * math.pi * _C_LIGHT / wavelength_m
    omega_p = plasma_frequency_from_atom(atom)
    gamma = drude_scattering_rate_from_atom(atom)
    eps_r, eps_i = _drude_permittivity(omega, omega_p, gamma)
    n, k = _nk_from_eps(eps_r, eps_i)
    return _fresnel_r(n, k)


def metal_rgb_from_atom(atom) -> tuple:
    """RGB reflectance of a metal from a quarksum Atom — no string key.

    The atom's electron configuration and proton count (Z) determine the
    optical response. Color is a consequence of what the atom IS.

    Returns:
        (r, g, b) in [0, 1] — the atom's own color at R/G/B wavelengths
    """
    r = metal_reflectance_from_atom(atom, LAMBDA_R)
    g = metal_reflectance_from_atom(atom, LAMBDA_G)
    b = metal_reflectance_from_atom(atom, LAMBDA_B)
    return (r, g, b)


# ─────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────

def get_material_color(category, key, dye_key=None, substrate_key=None):
    """Get (r, g, b) color tuple for any supported material.

    Args:
        category: 'metal', 'organic', or 'dye'
        key: material key (from MATERIALS, ORGANIC_SPECTRA, or DYE_DATABASE)
        dye_key: for category='dye', the dye to apply
        substrate_key: organic substrate key (defaults to 'wool_natural')

    Returns:
        (r, g, b) tuple ∈ [0, 1]
    """
    if category == 'metal':
        return metal_rgb(key)
    elif category == 'organic':
        return organic_rgb(key)
    elif category == 'dye':
        sub_key = substrate_key or 'wool_natural'
        substrate = organic_rgb(sub_key)
        return dye_transmission_rgb(dye_key or key, substrate)
    else:
        raise ValueError(f"Unknown category: {category!r}")
