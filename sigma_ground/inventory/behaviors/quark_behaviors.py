"""QCD behavioral computations for individual quarks.

Computes all closed-form quantum behaviors for a given quark:
  - Color charge transitions via gluon exchange (SU(3) group theory)
  - Cornell confinement potential V(r)
  - Running coupling constant alpha_s(Q) (one-loop, asymptotic freedom)
  - CKM weak-decay coupling matrix (PDG 2024)
  - Color entanglement (baryon/meson singlet states, von Neumann entropy)

All formulas from PDG 2024 and standard QCD references.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sigma_ground.inventory.models.quark import Quark

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALPHA_S_MZ = 0.1179          # PDG 2024 world average at M_Z
_M_Z_GEV = 91.1876            # Z boson mass (GeV)
_STRING_TENSION = 0.18         # GeV^2 (Cornell potential string tension)
_ALPHA_S_HADRONIC = 0.39       # alpha_s at ~1 GeV hadronic scale
_FM_TO_GEV_INV = 5.068        # 1 fm = 5.068 GeV^-1
_QCD_SCALE_MEV = 217           # Lambda_QCD approximate (MeV)

# Flavor mass thresholds for nf counting (GeV)
_M_CHARM_GEV = 1.27
_M_BOTTOM_GEV = 4.18
_M_TOP_GEV = 172.5

# CKM matrix magnitudes |V_ij| — PDG 2024
# Rows: up-type (u, c, t); Columns: down-type (d, s, b)
_CKM = [
    [0.97373, 0.2245, 0.00382],   # up
    [0.221,   0.987,  0.0410],    # charm
    [0.0080,  0.0388, 1.013],     # top
]
_UP_TYPE = ("up", "charm", "top")
_DOWN_TYPE = ("down", "strange", "bottom")

# Color algebra
_COLORS = ("red", "green", "blue")
_ANTI_MAP = {"red": "anti-red", "green": "anti-green", "blue": "anti-blue",
             "anti-red": "red", "anti-green": "green", "anti-blue": "blue"}

# Gell-Mann lambda_3 diagonal eigenvalues (r, g, b)
_LAMBDA3 = {"red": 1.0, "green": -1.0, "blue": 0.0}
# Gell-Mann lambda_8 diagonal eigenvalues (r, g, b)
_LAMBDA8 = {"red": 1.0, "green": 1.0, "blue": -2.0}

# Off-diagonal gluon states: (color_carried, anticolor_carried)
# When a quark of color C emits gluon (C, anti-X), quark becomes X
_OFF_DIAGONAL_GLUONS = [
    ("red", "anti-blue"),
    ("red", "anti-green"),
    ("blue", "anti-red"),
    ("blue", "anti-green"),
    ("green", "anti-red"),
    ("green", "anti-blue"),
]

# Pretty labels for gluon states
_ANTI_LABEL = {
    "anti-red": "r\u0304", "anti-green": "g\u0304", "anti-blue": "b\u0304",
}
_COLOR_LABEL = {"red": "r", "green": "g", "blue": "b"}


# ---------------------------------------------------------------------------
# Color transitions
# ---------------------------------------------------------------------------

def _strip_anti(anticolor: str) -> str:
    """anti-blue -> blue"""
    return anticolor.replace("anti-", "")


def _color_transitions(color: str) -> dict:
    """Compute all gluon-mediated color transitions for a quark of given color."""
    emissions = []
    absorptions = []

    for g_color, g_anti in _OFF_DIAGONAL_GLUONS:
        target = _strip_anti(g_anti)
        # Emission: quark color must match gluon's color charge
        if g_color == color:
            label = _COLOR_LABEL.get(g_color, g_color) + _ANTI_LABEL.get(g_anti, g_anti)
            emissions.append({"gluon": label, "result_color": target})

        # Absorption: quark color must match partner of gluon's anticolor
        if target == color:
            label = _COLOR_LABEL.get(g_color, g_color) + _ANTI_LABEL.get(g_anti, g_anti)
            absorptions.append({"gluon": label, "from_color": g_color})

    diag = {
        "gluon_7": _LAMBDA3.get(color, 0.0) / math.sqrt(2),
        "gluon_8": _LAMBDA8.get(color, 0.0) / math.sqrt(6),
    }

    return {
        "emissions": emissions,
        "absorptions": absorptions,
        "diagonal_couplings": diag,
    }


# ---------------------------------------------------------------------------
# Cornell confinement potential
# ---------------------------------------------------------------------------

_CORNELL_DISTANCES_FM = [0.1, 0.2, 0.5, 1.0, 1.5, 2.0]


def _cornell_potential(r_fm: float) -> float:
    """V(r) = -4*alpha_s/(3*r) + k*r  in GeV, with r in fm."""
    r_gev_inv = r_fm * _FM_TO_GEV_INV
    coulomb = -4.0 * _ALPHA_S_HADRONIC / (3.0 * r_gev_inv)
    linear = _STRING_TENSION * r_gev_inv
    return coulomb + linear


def _confinement_section() -> dict:
    return {
        "string_tension_gev2": _STRING_TENSION,
        "qcd_scale_mev": _QCD_SCALE_MEV,
        "cornell_potential": [
            {"r_fm": r, "V_gev": round(_cornell_potential(r), 6)}
            for r in _CORNELL_DISTANCES_FM
        ],
        "note": (
            "The Cornell potential V(r) = -4\u03b1s/(3r) + kr shows two regimes: "
            "at short distances the Coulomb-like term dominates (asymptotic freedom), "
            "while at long distances the linear term grows without bound (confinement). "
            "No free quarks can exist — pulling quarks apart creates new quark-antiquark "
            "pairs from the vacuum before separation is achieved."
        ),
    }


# ---------------------------------------------------------------------------
# Running coupling constant (one-loop)
# ---------------------------------------------------------------------------

def _active_flavors(Q_gev: float) -> int:
    if Q_gev < _M_CHARM_GEV:
        return 3
    if Q_gev < _M_BOTTOM_GEV:
        return 4
    if Q_gev < _M_TOP_GEV:
        return 5
    return 6


def _lambda_qcd_squared(nf: int) -> float:
    """Derive Lambda_QCD^2 from alpha_s(M_Z) = 0.1179 at nf=5, then match at thresholds."""
    # At M_Z with nf=5: alpha_s = 12*pi / ((33-2*nf)*ln(M_Z^2/Lambda^2))
    # Solve for Lambda^2: Lambda^2 = M_Z^2 * exp(-12*pi / ((33-2*nf)*alpha_s))
    beta0_5 = 33 - 2 * 5  # = 23
    ln_ratio_5 = 12.0 * math.pi / (beta0_5 * _ALPHA_S_MZ)
    lambda2_nf5 = _M_Z_GEV ** 2 * math.exp(-ln_ratio_5)

    if nf == 5:
        return lambda2_nf5

    # Continuous matching at flavor thresholds
    # At threshold mu, alpha_s is continuous, so:
    # Lambda_{nf-1}^2 = mu^2 * (Lambda_{nf}^2 / mu^2)^(beta0_nf / beta0_{nf-1})
    if nf == 4:
        mu2 = _M_BOTTOM_GEV ** 2
        ratio = lambda2_nf5 / mu2
        beta0_4 = 33 - 2 * 4  # = 25
        return mu2 * ratio ** (beta0_5 / beta0_4)

    if nf == 3:
        lambda2_4 = _lambda_qcd_squared(4)
        mu2 = _M_CHARM_GEV ** 2
        ratio = lambda2_4 / mu2
        beta0_3 = 33 - 2 * 3  # = 27
        beta0_4 = 33 - 2 * 4
        return mu2 * ratio ** (beta0_4 / beta0_3)

    if nf == 6:
        mu2 = _M_TOP_GEV ** 2
        ratio = lambda2_nf5 / mu2
        beta0_6 = 33 - 2 * 6  # = 21
        return mu2 * ratio ** (beta0_5 / beta0_6)

    return lambda2_nf5


def _alpha_s(Q_gev: float) -> float:
    """One-loop running coupling alpha_s(Q)."""
    nf = _active_flavors(Q_gev)
    beta0 = 33 - 2 * nf
    lambda2 = _lambda_qcd_squared(nf)
    q2 = Q_gev ** 2
    if q2 <= lambda2:
        return float("inf")
    return 12.0 * math.pi / (beta0 * math.log(q2 / lambda2))


_ALPHA_S_SCALES = [1.0, 2.0, 5.0, 10.0, 91.2, 1000.0]


def _asymptotic_freedom_section() -> dict:
    return {
        "alpha_s": [
            {
                "Q_gev": q,
                "nf": _active_flavors(q),
                "alpha_s": round(_alpha_s(q), 6),
            }
            for q in _ALPHA_S_SCALES
        ],
        "alpha_s_at_mz": _ALPHA_S_MZ,
        "note": (
            "The strong coupling \u03b1s runs with energy scale Q: it is large "
            "at low energies (confinement) and small at high energies (asymptotic "
            "freedom). This is the defining property of QCD — quarks behave as "
            "nearly free particles in high-energy collisions but are permanently "
            "confined inside hadrons at low energies. One-loop formula: "
            "\u03b1s(Q) = 12\u03c0 / ((33\u22122nf) \u00b7 ln(Q\u00b2/\u039b\u00b2))."
        ),
    }


# ---------------------------------------------------------------------------
# CKM couplings
# ---------------------------------------------------------------------------

def _ckm_couplings(flavor: str) -> dict:
    """Return weak-decay transition probabilities for the given quark flavor."""
    clean = flavor.replace("anti-", "").replace("anti_", "")

    if clean in _UP_TYPE:
        row = _UP_TYPE.index(clean)
        transitions = [
            {
                "to": _DOWN_TYPE[col],
                "Vij": _CKM[row][col],
                "probability": round(_CKM[row][col] ** 2, 6),
            }
            for col in range(3)
        ]
    elif clean in _DOWN_TYPE:
        col = _DOWN_TYPE.index(clean)
        transitions = [
            {
                "to": _UP_TYPE[row],
                "Vij": _CKM[row][col],
                "probability": round(_CKM[row][col] ** 2, 6),
            }
            for row in range(3)
        ]
    else:
        transitions = []

    is_anti = "anti" in flavor
    return {
        "transitions": transitions,
        "note": (
            f"CKM matrix elements for {flavor} quark. "
            f"{'Antiquarks use the complex conjugate (same magnitudes). ' if is_anti else ''}"
            "Transition probability = |Vij|^2. The CKM matrix is unitary: "
            "each row and column sums to ~1. Off-diagonal elements enable "
            "flavor-changing weak decays (e.g. top -> bottom + W+)."
        ),
    }


# ---------------------------------------------------------------------------
# Entanglement
# ---------------------------------------------------------------------------

_BARYON_SINGLET = (
    "|\u03c8\u27e9 = (\u2009|rgb\u27e9 \u2212 |rbg\u27e9 "
    "+ |gbr\u27e9 \u2212 |grb\u27e9 "
    "+ |brg\u27e9 \u2212 |bgr\u27e9\u2009) / \u221a6"
)
_MESON_SINGLET = (
    "|\u03c8\u27e9 = (\u2009|r\u0305r\u27e9 + |g\u0305g\u27e9 + |b\u0305b\u27e9\u2009) / \u221a3"
)
_VON_NEUMANN_ENTROPY = math.log(3)  # maximally entangled in 3-dim color space


def _entanglement_section() -> dict:
    return {
        "baryon_singlet": _BARYON_SINGLET,
        "meson_singlet": _MESON_SINGLET,
        "von_neumann_entropy": _VON_NEUMANN_ENTROPY,
        "note": (
            "Quarks inside a hadron form a color-singlet state — they are "
            "maximally entangled in color space. In a baryon (3 quarks), the "
            "antisymmetric combination \u03b5_{ijk}|c_i c_j c_k\u27e9/\u221a6 "
            "ensures color neutrality. Tracing over any two quarks yields a "
            "completely mixed reduced state \u03c1 = I/3, giving von Neumann "
            "entropy S = ln(3) \u2248 1.099 — the maximum for a 3-dimensional "
            "system. This entanglement has been experimentally confirmed at "
            "RHIC and the LHC."
        ),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_quark_behaviors(quark: Quark) -> dict:
    """Compute all QCD behaviors for a given quark.

    Returns a dict with two top-level keys:
      ``intrinsic`` — read-only properties and computed behaviors fixed by nature
      ``operable``  — mutable state with physical mechanisms for change
    """
    from sigma_ground.inventory.behaviors import extract_fields

    intrinsic_fields, operable_fields = extract_fields(quark)

    color = quark.color_charge
    if color.startswith("anti-"):
        color = color.replace("anti-", "")

    intrinsic_fields["confinement"] = _confinement_section()
    intrinsic_fields["asymptotic_freedom"] = _asymptotic_freedom_section()
    intrinsic_fields["ckm_couplings"] = _ckm_couplings(quark.flavor)
    intrinsic_fields["entanglement"] = _entanglement_section()

    operable_fields["color_charge"]["mechanism"] = "gluon exchange"
    operable_fields["color_charge"]["transitions"] = _color_transitions(color)

    operable_fields["spin_projection"]["mechanism"] = "external magnetic field"

    return {
        "entity_type": "quark",
        "flavor": quark.flavor,
        "color": quark.color_charge,
        "generation": quark.generation,
        "bare_mass_mev": quark.bare_mass_mev,
        "constituent_mass_mev": quark.constituent_mass_mev,
        "intrinsic": intrinsic_fields,
        "operable": operable_fields,
    }


# ---------------------------------------------------------------------------
# Environment resolution
# ---------------------------------------------------------------------------

_QUARK_VALID_KEYS = {"energy_gev", "magnetic_field_t", "color_field"}

# Gluon label → (emitter_color, result_color)
_GLUON_LABEL_MAP: dict[str, tuple[str, str]] = {}
for _gc, _ga in _OFF_DIAGONAL_GLUONS:
    _label = _COLOR_LABEL.get(_gc, _gc) + _ANTI_LABEL.get(_ga, _ga)
    _GLUON_LABEL_MAP[_label] = (_gc, _strip_anti(_ga))


def resolve_quark_env(quark: Quark, env: dict, mode: str = "delta") -> dict:
    """Apply environment values to a quark and return updated behaviors.

    Parameters
    ----------
    quark : Quark
        The quark to mutate.
    env : dict
        Environment keys. Valid: ``energy_gev``, ``magnetic_field_t``,
        ``color_field`` (update mode only).
    mode : str
        ``"delta"`` for relative adjustment, ``"update"`` for absolute replacement.
    """
    bad_keys = set(env) - _QUARK_VALID_KEYS
    if bad_keys:
        raise ValueError(
            f"Invalid quark environment keys: {bad_keys}. "
            f"Valid keys: {sorted(_QUARK_VALID_KEYS)}"
        )

    applied: list[dict] = []

    if "color_field" in env:
        if mode == "delta":
            raise ValueError("color_field is categorical; use mode='update'")
        gluon_label = env["color_field"]
        if gluon_label not in _GLUON_LABEL_MAP:
            raise ValueError(
                f"Unknown gluon label: '{gluon_label}'. "
                f"Valid: {sorted(_GLUON_LABEL_MAP)}"
            )
        emitter_color, result_color = _GLUON_LABEL_MAP[gluon_label]
        old_color = quark.color_charge
        if old_color != emitter_color:
            raise ValueError(
                f"Gluon {gluon_label} requires color '{emitter_color}', "
                f"but quark has '{old_color}'"
            )
        quark.color_charge = result_color
        applied.append({
            "key": "color_field", "mode": mode, "value": gluon_label,
            "consequence": f"color_charge: {old_color} -> {result_color}",
        })

    if "energy_gev" in env:
        Q = env["energy_gev"]
        if mode == "delta":
            Q = abs(Q)
        applied.append({
            "key": "energy_gev", "mode": mode, "value": Q,
            "consequence": (
                f"alpha_s({Q:.1f} GeV) = {_alpha_s(Q):.6f}, "
                f"nf = {_active_flavors(Q)}"
            ),
        })

    if "magnetic_field_t" in env:
        from sigma_ground.inventory.core.constants import CONSTANTS
        B = env["magnetic_field_t"]
        if mode == "delta":
            B_total = B
        else:
            B_total = B
        omega = abs(quark.charge) * CONSTANTS.e * abs(B_total) / (
            quark.bare_mass_mev * CONSTANTS.MeV_to_kg
        )
        old_spin = quark.spin_projection
        quark.spin_projection = -old_spin
        applied.append({
            "key": "magnetic_field_t", "mode": mode, "value": B,
            "consequence": (
                f"spin_projection: {old_spin} -> {quark.spin_projection} "
                f"(Larmor omega={omega:.3e} rad/s)"
            ),
        })

    result = compute_quark_behaviors(quark)
    result["applied"] = applied
    return result
