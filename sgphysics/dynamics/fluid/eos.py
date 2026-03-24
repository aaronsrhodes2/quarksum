"""
Equations of state for SPH fluids.

An equation of state (EOS) maps density → pressure. In SPH, the EOS is
evaluated per-particle to compute the pressure force between neighbors.

Tait equation (weakly compressible liquids)
-------------------------------------------
  P = K/γ_tait × ((ρ/ρ₀)^γ_tait - 1)

Where:
  K        = bulk modulus (Pa)           — from material.bulk_modulus_pa
  γ_tait   = 7  (water; Batchelor 1967) — MEASURED, empirical
  ρ₀       = rest density (kg/m³)       — material.density_kg_m3
  ρ        = current density (kg/m³)    — from SPH density sum

For the weakly-compressible SPH (WCSPH) approach, we set the speed of sound
  c_s = sqrt(K / ρ₀)
and choose K large enough that density fluctuations are < 1%.
The Mach number condition: v_max / c_s < 0.1.

FIRST_PRINCIPLES: the Tait equation is the exact large-pressure correction
to the isothermal compressibility for liquids. At small ΔP/K it reduces to
the linear Hooke approximation P ≈ K × (ρ/ρ₀ - 1).

We use the LINEAR form here for simplicity and numerical stability in the
first SPH implementation. The full Tait form is noted for future upgrade.

Reference: Monaghan (1994) J. Comput. Phys. 110:399-406.
           Batchelor (1967) "An Introduction to Fluid Dynamics" §4.2.

Ideal gas EOS
-------------
  P = (ρ / M) × R × T
    = ρ × (R/M) × T
    = ρ × c_s²   where c_s² = γ × R × T / M

For SPH gas simulations (compressible flow), γ = Cp/Cv = 1.4 for air.
FIRST_PRINCIPLES: kinetic theory of ideal gas.

σ-dependence
------------
  ρ₀(σ) = material.density_at_sigma(σ)
  K is EM-based (bond stiffness) → σ-INVARIANT at leading order
  Exception: K(σ) shifts slightly via E_coh(σ) — see mechanical.py.
  For the EOS we use K(σ=0) as a practical approximation.
"""


# ── Tait EOS (linear approximation) ─────────────────────────────────────────

def pressure_tait(rho, rho_0, K, gamma_tait=7):
    """Pressure from Tait equation of state (linearized for stability).

    Linear form: P = K × (ρ/ρ₀ - 1)
    Exact for small density perturbations (weakly compressible).

    For the full power-law Tait, use pressure_tait_full().

    Args:
        rho:        local particle density (kg/m³)
        rho_0:      rest density (kg/m³)
        K:          bulk modulus (Pa)
        gamma_tait: unused in linear form, kept for API consistency.

    Returns:
        Pressure P in Pascals. Negative = tension (allowed for cohesive fluids).

    FIRST_PRINCIPLES (linear Hooke limit of Tait).
    """
    return K * (rho / rho_0 - 1.0)


def pressure_tait_full(rho, rho_0, K, gamma_tait=7):
    """Pressure from the full power-law Tait equation.

    P = (K / γ) × ((ρ/ρ₀)^γ - 1)

    More accurate at large density excursions.
    Less numerically stable near ρ ≈ ρ₀ (stiff system).

    Args:
        rho:        local particle density (kg/m³)
        rho_0:      rest density (kg/m³)
        K:          bulk modulus (Pa). Note: here K acts as the reference
                    pressure B = K/γ in the Tait formulation.
        gamma_tait: Tait exponent. 7 for water (Batchelor 1967).

    Returns:
        Pressure in Pascals.
    """
    return (K / gamma_tait) * ((rho / rho_0) ** gamma_tait - 1.0)


# ── Ideal gas EOS ────────────────────────────────────────────────────────────

def pressure_ideal_gas(rho, T, M_kg_mol=0.02897, gamma=1.4):
    """Pressure from ideal gas law.

    P = ρ × (R/M) × T

    Args:
        rho:       density (kg/m³)
        T:         temperature (K)
        M_kg_mol:  molar mass (kg/mol). Default: dry air (0.02897).
        gamma:     heat capacity ratio Cp/Cv. Default: 1.4 (diatomic air).
                   Used only for c_s computation.

    Returns:
        (P, c_s): pressure in Pa and speed of sound in m/s.

    FIRST_PRINCIPLES: ideal gas law PV = nRT.
    """
    R_GAS = 8.314462618   # J/(mol·K)
    P = rho * (R_GAS / M_kg_mol) * T
    c_s = (gamma * R_GAS * T / M_kg_mol) ** 0.5   # sqrt(γRT/M)
    return P, c_s


# ── Speed of sound in liquid ──────────────────────────────────────────────

def speed_of_sound_liquid(K, rho):
    """Speed of sound in a liquid: c = sqrt(K/ρ).

    FIRST_PRINCIPLES: from the wave equation for a compressible fluid.
    For water at 20°C: c = sqrt(2.2e9 / 998) ≈ 1484 m/s (MEASURED: 1482 m/s).

    Args:
        K:   bulk modulus (Pa)
        rho: density (kg/m³)

    Returns:
        Speed of sound in m/s.
    """
    return (K / rho) ** 0.5
