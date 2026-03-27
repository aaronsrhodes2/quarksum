"""
sgphysics.constants — Unified physical constants for sigma-ground-physics.

Re-exports everything from sigma_ground.field.constants (the authoritative source)
and adds any additional constants needed by the sgphysics dynamics layer.

All constants are MEASURED (with citations) or DERIVED from MEASURED constants.
No magic numbers.
"""

# ── Re-export from the authoritative source ──────────────────────────────────
from sigma_ground.field.constants import (
    # SSBM parameters
    XI,
    LAMBDA_QCD_MEV,
    GAMMA,
    SIGMA_CONV,

    # Physical constants
    G,
    C,
    HBAR,

    # Nucleon mass decomposition
    M_UP_MEV,
    M_DOWN_MEV,
    PROTON_BARE_MEV,
    PROTON_TOTAL_MEV,
    PROTON_QCD_MEV,
    NEUTRON_BARE_MEV,
    NEUTRON_TOTAL_MEV,
    NEUTRON_QCD_MEV,
    PROTON_QCD_FRACTION,
    NEUTRON_QCD_FRACTION,
    M_ELECTRON_MEV,

    # Coulomb energy
    E_CHARGE,
    EPS_0,
    R0_FM,
    KE_E2_MEV_FM,
    A_C_MEV,

    # Entanglement
    ETA,

    # Nuclear matter
    N0_FM3,
    E_SAT_MEV,
    K_SAT_MEV,
    J_SYM_MEV,

    # Cosmological
    H0,
    M_HUBBLE_KG,
    M_PLANCK_KG,
    L_PLANCK,
    M_SUN_KG,
    L_SUN_W,
    AU_M,
    YEAR_S,
)

# ── Additional constants for dynamics layer ───────────────────────────────────

# Planck length — also defined in vec.py locally to avoid circular imports,
# but the canonical derivation lives here.
# L_PLANCK = sqrt(ħG/c³) = 1.616255e-35 m  (re-exported above from local_library)

__all__ = [
    'XI', 'LAMBDA_QCD_MEV', 'GAMMA', 'SIGMA_CONV',
    'G', 'C', 'HBAR',
    'M_UP_MEV', 'M_DOWN_MEV',
    'PROTON_BARE_MEV', 'PROTON_TOTAL_MEV', 'PROTON_QCD_MEV',
    'NEUTRON_BARE_MEV', 'NEUTRON_TOTAL_MEV', 'NEUTRON_QCD_MEV',
    'PROTON_QCD_FRACTION', 'NEUTRON_QCD_FRACTION',
    'M_ELECTRON_MEV',
    'E_CHARGE', 'EPS_0', 'R0_FM', 'KE_E2_MEV_FM', 'A_C_MEV',
    'ETA',
    'N0_FM3', 'E_SAT_MEV', 'K_SAT_MEV', 'J_SYM_MEV',
    'H0', 'M_HUBBLE_KG', 'M_PLANCK_KG', 'L_PLANCK',
    'M_SUN_KG', 'L_SUN_W', 'AU_M', 'YEAR_S',
]
