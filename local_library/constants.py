"""
SSBM Constants — The measured numbers that define the model,
plus one declared unknown.

Every number here is either measured (from experiment/observation),
derived from measured numbers, or explicitly marked as unknown.
"""

import math

# ── SSBM Parameters ───────────────────────────────────────────────────
# The single new constant: baryon fraction (Planck 2018)
#   Ω_b h² = 0.02237,  Ω_c h² = 0.1200
#   Exact: 0.02237 / (0.02237 + 0.1200) = 0.15716...
#   Canonical SSBM value (used in all publications and tests):
XI = 0.1582

# QCD confinement scale (PDG reference)
LAMBDA_QCD_MEV = 217.0  # MeV

# Spectral index relation: γ = 3 - n_s (Planck 2018: n_s = 0.9649)
GAMMA = 2.035

# Critical σ where nuclear bonds fail
SIGMA_CONV = -math.log(XI)  # ≈ 1.849... but using exact XI

# ── Physical Constants ────────────────────────────────────────────────
G = 6.67430e-11       # m³ kg⁻¹ s⁻²  (gravitational constant)
C = 2.99792458e8      # m/s            (speed of light)
HBAR = 1.054571817e-34  # J·s          (reduced Planck constant)

# ── Nucleon Mass Decomposition (MeV) ─────────────────────────────────
# This is the KEY FACT: ~99% of nucleon mass is QCD binding, not Higgs.

# Quark bare masses (Higgs origin — σ-INVARIANT)
M_UP_MEV = 2.16       # MeV (PDG 2020)
M_DOWN_MEV = 4.67     # MeV (PDG 2020)

# Proton (uud): bare = 2×m_u + m_d
PROTON_BARE_MEV = 2 * M_UP_MEV + M_DOWN_MEV  # = 8.99 MeV
PROTON_TOTAL_MEV = 938.272          # MeV (measured)
PROTON_QCD_MEV = PROTON_TOTAL_MEV - PROTON_BARE_MEV  # = 929.282 MeV

# Neutron (udd): bare = m_u + 2×m_d
NEUTRON_BARE_MEV = M_UP_MEV + 2 * M_DOWN_MEV  # = 11.50 MeV
NEUTRON_TOTAL_MEV = 939.565         # MeV (measured)
NEUTRON_QCD_MEV = NEUTRON_TOTAL_MEV - NEUTRON_BARE_MEV  # = 928.065 MeV

# QCD fractions
PROTON_QCD_FRACTION = PROTON_QCD_MEV / PROTON_TOTAL_MEV   # ≈ 0.9904
NEUTRON_QCD_FRACTION = NEUTRON_QCD_MEV / NEUTRON_TOTAL_MEV  # ≈ 0.9878

# Electron mass (Higgs origin — σ-INVARIANT)
M_ELECTRON_MEV = 0.51100            # MeV

# ── Coulomb Energy (first-principles electrostatics) ─────────────────
# NOT from SEMF. Derived from Coulomb's law integrated over a uniform
# charge sphere:  E_C = (3/5) × ke_e² / r₀ × Z(Z-1) / A^(1/3)
#
# Inputs (all measured):
#   e    = 1.602176634e-19 C    (elementary charge, CODATA exact)
#   ε₀   = 8.854187817e-12 F/m  (vacuum permittivity, CODATA)
#   r₀   = 1.215 fm             (nuclear charge radius, electron scattering — Hofstadter)
#
# ke × e² = e²/(4πε₀) = 1.43996 MeV·fm  (EM coupling constant)
# a_C = (3/5) × 1.43996 / 1.215 = 0.7111 MeV

E_CHARGE = 1.602176634e-19    # C  (elementary charge, exact by 2019 SI)
EPS_0 = 8.854187817e-12       # F/m (vacuum permittivity)
R0_FM = 1.215                 # fm (nuclear charge radius, electron scattering)

# ke × e²  in MeV·fm
_MeV_per_J = 1 / 1.602176634e-13
KE_E2_MEV_FM = E_CHARGE**2 / (4 * math.pi * EPS_0) * _MeV_per_J * 1e15

# Coulomb coefficient — pure electrostatics, no SEMF
A_C_MEV = (3.0 / 5.0) * KE_E2_MEV_FM / R0_FM  # ≈ 0.7111 MeV (σ-INVARIANT)

# ── Entanglement Fraction (η) ─────────────────────────────────────────
# The ratio of particles entangled with at least one other particle
# *somewhere* (it doesn't matter where the partner is).
#
# DERIVED from the dark energy constraint:
#   At σ_conv, QCD binding energy is released. The entangled fraction
#   releases coherently → gluon condensate (w = −1, dark energy).
#   The non-entangled fraction thermalizes → radiation (w = +1/3).
#   Matching ρ_DE(observed) = η × ρ_released gives η = 0.4153.
#
# Bounds:   0 ≤ η ≤ 1
#   η = 0:  no particles entangled (fully classical limit)
#   η = 1:  every particle entangled with at least one other
#
# Physical meaning: inside a hadron, quarks are always entangled
# (color singlet). But η asks about CROSS-HADRON entanglement —
# particles that share quantum correlations with partners in other
# hadrons, other atoms, other galaxies. This includes:
#   - EPR pairs (produced together, flew apart)
#   - Particles from common decay chains
#   - Cosmological correlations from the Big Bang
#   - Any interaction that created entanglement and was never decohered
ETA = 0.4153  # DERIVED — cosmic entanglement fraction (dark energy constraint)

# ── Nuclear Matter (QCD observables) ─────────────────────────────────
# Nuclear saturation density: where attraction and repulsion balance.
# MEASURED from electron scattering on heavy nuclei.
N0_FM3 = 0.16              # fm⁻³ (nuclear saturation density)
E_SAT_MEV = -16.0           # MeV (binding energy per nucleon at saturation)

# Nuclear incompressibility: K = 9n₀² d²(E/A)/dn² at saturation.
# MEASURED from giant monopole resonances in heavy nuclei.
# This is a QCD observable — it's the stiffness of nuclear matter,
# set by the balance of attractive σ-meson and repulsive ω-meson exchange.
# In SSBM: both meson masses scale with Λ_QCD × e^σ, so K(σ) = K₀ × e^σ.
K_SAT_MEV = 230.0           # MeV (nuclear incompressibility)

# Symmetry energy: energy cost of neutron-proton imbalance.
# MEASURED from nuclear mass differences.
J_SYM_MEV = 32.0            # MeV (symmetry energy at saturation)

# ── Cosmological ──────────────────────────────────────────────────────
H0 = 67.4e3 / 3.086e22  # Hubble constant in s⁻¹ (67.4 km/s/Mpc)
M_HUBBLE_KG = C**3 / (2 * G * H0)  # Hubble mass ≈ 9.3e52 kg
M_PLANCK_KG = math.sqrt(HBAR * C / G)  # Planck mass ≈ 2.18e-8 kg
L_PLANCK    = HBAR / (M_PLANCK_KG * C) # Planck length √(ℏG/c³) ≈ 1.616e-35 m
#   The smallest length with physical meaning (below this: quantum gravity).
#   Use as the natural "effectively zero" floor — not a magic number,
#   but the universe's own minimum. Derived from ℏ, G, c above.
M_SUN_KG = 1.989e30    # Solar mass

# Derived time constants
YEAR_S = 365.25 * 86400.0  # Julian year in seconds (exact by IAU definition)
