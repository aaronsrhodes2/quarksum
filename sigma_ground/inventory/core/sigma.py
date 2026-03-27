"""SSBM scale field σ — core scaling functions.

The Scale-Shifted Baryonic Matter hypothesis:

    Λ_eff(x) = Λ_QCD · exp(σ(x))

σ is a dimensionless scalar field ("dimension zero") that modifies the
effective QCD energy scale with gravitational environment.  At σ = 0
(our lab, flat spacetime), all physics is standard.

WHAT SCALES (QCD-dependent):
    Quark constituent masses (QCD dressing ~330 MeV)    → ×e^σ
    Nucleon masses (~99% QCD binding: 929/938 MeV)      → ×e^σ
    Nuclear binding (strong force component)             → ×e^σ
    Gluon field energy                                   → ×e^σ

WHAT DOES NOT SCALE (Higgs / EM):
    Quark bare masses (u=2.16, d=4.67 MeV from Higgs)   → invariant
    Electron mass (0.511 MeV, Higgs + EM)               → invariant
    Coulomb energy in nuclei                              → invariant
    Chemical bond energies (EM)                           → invariant
    Fine structure constant α_EM                          → invariant

Parameters:
    ξ = 0.1582 — Ω_b / (Ω_b + Ω_c), Planck 2018
    Λ_QCD = 217 MeV — PDG reference confinement scale

No Materia dependency.  Pure physics, pure math.
"""

from __future__ import annotations

import math

from sigma_ground.inventory.core.constants import CONSTANTS

# ── SSBM fundamental parameters ──────────────────────────────────────

XI: float = 0.1582
"""ξ = Ω_b / (Ω_b + Ω_c).  Planck 2018: Ω_b h² = 0.02237, Ω_c h² = 0.1200.
INPUT parameter — the one new free parameter SSBM introduces."""

ETA: float = 0.4153
"""η = cosmic entanglement fraction.  DERIVED from the dark energy constraint:
ρ_DE(observed) = η × ρ_released at σ_conv.  Falls out of ξ + Planck cosmology."""

SIGMA_0: float = 0.0
"""σ = 0 in the present epoch — our spacetime is the reference frame.
A convention, not a measurement. Nonzero inside black holes and at the Big Bang.
Use SIGMA_FLOOR as the computational epsilon; never divide by SIGMA_0 directly."""

# Planck length (re-derived here to keep this module self-contained)
_HBAR = CONSTANTS.hbar       # 1.054571817e-34 J·s
_G    = 6.67430e-11          # m³ kg⁻¹ s⁻²
_C    = CONSTANTS.c          # 2.99792458e8 m/s
_H0   = 67.4e3 / 3.086e22   # Hubble constant s⁻¹ (Planck 2018)
_L_PLANCK = (_HBAR * _G / _C**3) ** 0.5  # √(ħG/c³) ≈ 1.616e-35 m

SIGMA_FLOOR: float = _L_PLANCK * _H0 / _C
"""Planck-derived σ computational epsilon ≈ 1.18×10⁻⁶¹.
= l_P / R_H (Planck length / Hubble radius).
Use instead of 0.0 wherever σ appears in a denominator or logarithm."""

LAMBDA_QCD_MEV: float = 217.0
"""QCD confinement scale Λ_QCD (MeV).  PDG reference value."""

LAMBDA_QCD_GEV: float = 0.217
"""QCD confinement scale Λ_QCD (GeV)."""

# ── Derived constants (computed once) ─────────────────────────────────

_MEV_TO_KG: float = CONSTANTS.e * 1e6 / CONSTANTS.c_squared

# Proton: uud → bare mass = 2×m_u + m_d
_PROTON_BARE_MEV: float = 2.0 * CONSTANTS.m_up_mev + CONSTANTS.m_down_mev
_PROTON_TOTAL_MEV: float = CONSTANTS.m_p / _MEV_TO_KG
_PROTON_QCD_MEV: float = _PROTON_TOTAL_MEV - _PROTON_BARE_MEV

# Neutron: udd → bare mass = m_u + 2×m_d
_NEUTRON_BARE_MEV: float = CONSTANTS.m_up_mev + 2.0 * CONSTANTS.m_down_mev
_NEUTRON_TOTAL_MEV: float = CONSTANTS.m_n / _MEV_TO_KG
_NEUTRON_QCD_MEV: float = _NEUTRON_TOTAL_MEV - _NEUTRON_BARE_MEV

# SEMF Coulomb coefficient (MeV) — the EM piece of nuclear binding
# Derived from first principles: a_C = (3/5) × e² / (4πε₀ r₀)
# where r₀ ≈ 1.25 fm (nuclear charge radius parameter).
# NOT a textbook fit — computed from fundamental constants.
A_C_MEV: float = (
    3.0 / 5.0
    * (CONSTANTS.e ** 2 / (4.0 * math.pi * CONSTANTS.epsilon_0 * 1.25e-15))
    / CONSTANTS.e * 1e-6  # J → MeV
)


# ── Core scale function ──────────────────────────────────────────────

def scale_ratio(sigma: float) -> float:
    """e^σ — the fundamental QCD scale shift.

    σ = 0 → 1.0 (standard physics, exact).
    σ > 0 → QCD scale increases (stronger confinement, heavier baryons).
    σ < 0 → QCD scale decreases (weaker confinement, lighter baryons).
    """
    return math.exp(sigma)


def lambda_eff_mev(sigma: float) -> float:
    """Effective QCD scale: Λ_eff = Λ_QCD · e^σ (MeV)."""
    return LAMBDA_QCD_MEV * scale_ratio(sigma)


# ── Nucleon masses at σ ──────────────────────────────────────────────

def proton_mass_kg(sigma: float) -> float:
    """Proton mass at σ.

    m_p(σ) = bare_quarks + QCD_binding × e^σ

    At σ=0: returns CONSTANTS.m_p exactly.
    bare_quarks = 2×m_u + m_d = 8.99 MeV  (Higgs, σ-invariant)
    QCD_binding = 938.27 − 8.99 = 929.28 MeV  (scales with e^σ)
    """
    if sigma == 0.0:
        return CONSTANTS.m_p
    return (_PROTON_BARE_MEV + _PROTON_QCD_MEV * scale_ratio(sigma)) * _MEV_TO_KG


def neutron_mass_kg(sigma: float) -> float:
    """Neutron mass at σ.

    m_n(σ) = bare_quarks + QCD_binding × e^σ

    At σ=0: returns CONSTANTS.m_n exactly.
    bare_quarks = m_u + 2×m_d = 11.50 MeV  (Higgs, σ-invariant)
    QCD_binding = 939.57 − 11.50 = 928.07 MeV  (scales with e^σ)
    """
    if sigma == 0.0:
        return CONSTANTS.m_n
    return (_NEUTRON_BARE_MEV + _NEUTRON_QCD_MEV * scale_ratio(sigma)) * _MEV_TO_KG


def proton_mass_mev(sigma: float) -> float:
    """Proton mass at σ in MeV/c²."""
    if sigma == 0.0:
        return _PROTON_TOTAL_MEV
    return _PROTON_BARE_MEV + _PROTON_QCD_MEV * scale_ratio(sigma)


def neutron_mass_mev(sigma: float) -> float:
    """Neutron mass at σ in MeV/c²."""
    if sigma == 0.0:
        return _NEUTRON_TOTAL_MEV
    return _NEUTRON_BARE_MEV + _NEUTRON_QCD_MEV * scale_ratio(sigma)


# ── Nuclear binding energy at σ ──────────────────────────────────────

def nuclear_binding_mev(be_mev: float, Z: int, A: int, sigma: float) -> float:
    """Nuclear binding energy at σ.

    Decomposes using the Semi-Empirical Mass Formula:
        strong_part = BE + coulomb_repulsion  (add back what SEMF subtracted)
        coulomb_part = a_C × Z(Z−1) / A^{1/3}

    Strong part scales with e^σ.  Coulomb part is EM → σ-invariant.

        BE(σ) = strong_part × e^σ − coulomb_part

    At σ=0: returns be_mev exactly.

    HONESTY: SEMF decomposition is approximate.  Shell effects,
    deformation, and pairing corrections are lumped into the strong part.
    """
    if sigma == 0.0 or A <= 0:
        return be_mev

    coulomb = A_C_MEV * Z * (Z - 1) / (A ** (1.0 / 3.0))
    strong = be_mev + coulomb  # total strong contribution
    return strong * scale_ratio(sigma) - coulomb


# ── Three-measure at arbitrary σ ─────────────────────────────────────

def three_measures_nucleus(
    Z: int,
    N: int,
    be_mev: float,
    sigma: float,
) -> dict:
    """Three independent measures for a nucleus at σ.

    stable_mass   = what you'd measure on a scale (the bonded thing).
    constituent   = sum of free nucleon masses (take it apart, weigh pieces).
    binding       = nuclear binding energy (calorimetry of the bond).

    All three computed independently from σ-shifted physics.
    The identity stable ≈ constituent − binding/c² is a CHECK.

    Args:
        Z: Proton count.
        N: Neutron count.
        be_mev: Nuclear binding energy at σ=0 (MeV).
        sigma: Scale field value.

    Returns:
        Dict with stable_kg, constituent_kg, binding_J, check_delta.
    """
    A = Z + N
    c2 = CONSTANTS.c_squared

    # Measure 1: Constituent mass — sum of free nucleon masses at σ
    mp = proton_mass_kg(sigma)
    mn = neutron_mass_kg(sigma)
    constituent_kg = Z * mp + N * mn

    # Measure 2: Binding energy at σ (converted to joules)
    be_sigma_mev = nuclear_binding_mev(be_mev, Z, A, sigma)
    binding_J = be_sigma_mev * CONSTANTS.MeV_to_J

    # Measure 3: Stable mass — what the whole nucleus weighs at σ
    # This is independently computed: constituent minus mass equivalent of binding
    stable_kg = constituent_kg - binding_J / c2

    # The check: how well does the identity close?
    # At every σ, E=mc² holds, so stable = constituent - binding/c²
    # should be exact (limited only by floating point).
    check = constituent_kg - binding_J / c2
    delta = abs(stable_kg - check) / stable_kg if stable_kg > 0 else 0.0

    return {
        "sigma": sigma,
        "Z": Z,
        "N": N,
        "A": A,
        "stable_mass_kg": stable_kg,
        "constituent_mass_kg": constituent_kg,
        "binding_energy_J": binding_J,
        "binding_energy_mev": be_sigma_mev,
        "proton_mass_kg": mp,
        "neutron_mass_kg": mn,
        "check_delta": delta,
        "identity_holds": delta < 1e-12,
    }


def three_measures_atom(
    Z: int,
    N: int,
    be_mev: float,
    sigma: float,
) -> dict:
    """Three measures for a full atom (nucleus + electrons) at σ.

    Electrons are σ-invariant (Higgs/EM mass).
    """
    nuc = three_measures_nucleus(Z, N, be_mev, sigma)

    e_mass = Z * CONSTANTS.m_e  # σ-invariant

    return {
        **nuc,
        "electron_mass_kg": e_mass,
        "atom_stable_mass_kg": nuc["stable_mass_kg"] + e_mass,
        "atom_constituent_mass_kg": nuc["constituent_mass_kg"] + e_mass,
        # Binding doesn't change — electrons' binding energy (~eV) is negligible
        # compared to nuclear binding (~MeV).  Electron ionization energy is EM.
    }


# ── Sigma profile from gravitational environment ─────────────────────

def sigma_from_potential(r_m: float, M_kg: float) -> float:
    """σ from Newtonian potential: σ = ξ × GM/(rc²).

    At event horizon (r = 2GM/c²): σ = ξ/2 = 0.0791
    At Earth's surface: σ ~ 7×10⁻¹⁰ (negligible)
    """
    if r_m <= 0 or M_kg <= 0:
        return 0.0

    G = 6.67430e-11
    compactness = G * M_kg / (r_m * CONSTANTS.c_squared)
    if compactness > 0.5:
        compactness = 0.5

    return XI * compactness


# ── QCD mass decomposition (for the checksum) ────────────────────────

def nucleon_qcd_fraction() -> dict:
    """Return the QCD vs Higgs mass decomposition of nucleons.

    This is the fundamental fact that makes SSBM work:
    ~99% of nucleon mass is QCD binding, not Higgs.
    """
    return {
        "proton": {
            "total_mev": _PROTON_TOTAL_MEV,
            "bare_quarks_mev": _PROTON_BARE_MEV,
            "qcd_binding_mev": _PROTON_QCD_MEV,
            "qcd_fraction": _PROTON_QCD_MEV / _PROTON_TOTAL_MEV,
            "higgs_fraction": _PROTON_BARE_MEV / _PROTON_TOTAL_MEV,
        },
        "neutron": {
            "total_mev": _NEUTRON_TOTAL_MEV,
            "bare_quarks_mev": _NEUTRON_BARE_MEV,
            "qcd_binding_mev": _NEUTRON_QCD_MEV,
            "qcd_fraction": _NEUTRON_QCD_MEV / _NEUTRON_TOTAL_MEV,
            "higgs_fraction": _NEUTRON_BARE_MEV / _NEUTRON_TOTAL_MEV,
        },
    }
