"""Behavioral computations for atoms.

Returns intrinsic/operable dict and environment resolution for Atom entities.
All physics values come from the entity itself (ElementDB, IsotopeDB) and CONSTANTS.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sigma_ground.inventory.core.constants import CONSTANTS

if TYPE_CHECKING:
    from sigma_ground.inventory.models.atom import Atom

_ATOM_VALID_KEYS = {"energy_ev", "temperature_k", "electric_field_vm", "magnetic_field_t"}


def compute_atom_behaviors(atom: Atom) -> dict:
    """Compute behaviors for an atom."""
    from sigma_ground.inventory.behaviors import extract_fields

    intrinsic_fields, operable_fields = extract_fields(atom)

    children = {
        "protons": len(atom.protons),
        "neutrons": len(atom.neutrons),
        "electrons": len(atom.electrons),
    }

    return {
        "entity_type": "atom",
        "symbol": atom.symbol,
        "name": atom.name,
        "atomic_number": atom.atomic_number,
        "mass_number": atom.mass_number,
        "intrinsic": intrinsic_fields,
        "operable": operable_fields,
        "children": children,
    }


def _ionization_energy_for_state(atom: Atom, charge_state: int) -> float | None:
    """Return the ionization energy to go from charge_state to charge_state+1."""
    attr = f"ionization_energy_{charge_state + 1}"
    return getattr(atom, attr, None)


def resolve_atom_env(atom: Atom, env: dict, mode: str = "delta") -> dict:
    """Apply environment values to an atom and return updated behaviors."""
    bad_keys = set(env) - _ATOM_VALID_KEYS
    if bad_keys:
        raise ValueError(
            f"Invalid atom environment keys: {bad_keys}. "
            f"Valid keys: {sorted(_ATOM_VALID_KEYS)}"
        )

    applied: list[dict] = []

    if "energy_ev" in env:
        E = env["energy_ev"]
        old_charge = atom.charge_state
        ie = _ionization_energy_for_state(atom, old_charge)
        if mode == "delta" and E > 0 and ie is not None and E >= ie:
            atom.charge_state = old_charge + 1
            if atom.electrons:
                atom.electrons.pop()
            applied.append({
                "key": "energy_ev", "mode": mode, "value": E,
                "consequence": (
                    f"ionized: charge_state {old_charge} -> {atom.charge_state}, "
                    f"removed outermost electron (IE={ie:.3f} eV, excess={E - ie:.3f} eV)"
                ),
            })
        else:
            applied.append({
                "key": "energy_ev", "mode": mode, "value": E,
                "consequence": (
                    f"below ionization threshold (IE={ie} eV), "
                    f"energy absorbed into electronic excitation"
                ) if ie is not None else "no ionization data available",
            })

    if "temperature_k" in env:
        T = env["temperature_k"]
        ie1 = atom.ionization_energy_1
        if ie1 and T > 0:
            boltzmann = math.exp(-ie1 * CONSTANTS.e / (CONSTANTS.k_B * T))
        else:
            boltzmann = 0.0
        applied.append({
            "key": "temperature_k", "mode": mode, "value": T,
            "consequence": (
                f"thermal ionization probability ~ {boltzmann:.6e} "
                f"(Boltzmann factor at T={T:.0f} K, IE1={ie1} eV)"
            ),
        })

    if "electric_field_vm" in env:
        F = env["electric_field_vm"]
        r = atom.atomic_radius
        if r is not None:
            alpha = 4.0 * math.pi * CONSTANTS.epsilon_0 * (r * 1e-12) ** 3
            delta_E_J = -0.5 * alpha * F ** 2
            delta_E_eV = delta_E_J / CONSTANTS.e
        else:
            delta_E_eV = 0.0
        applied.append({
            "key": "electric_field_vm", "mode": mode, "value": F,
            "consequence": f"Stark shift: {delta_E_eV:.6e} eV",
        })

    if "magnetic_field_t" in env:
        B = env["magnetic_field_t"]
        nuc_mu = atom.nuclear_magnetic_moment
        if nuc_mu is not None:
            nuclear_split_J = abs(nuc_mu) * 5.0508e-27 * abs(B)
        else:
            nuclear_split_J = 0.0
        electron_split_J = CONSTANTS.mu_B * abs(B)
        applied.append({
            "key": "magnetic_field_t", "mode": mode, "value": B,
            "consequence": (
                f"Zeeman: electronic splitting {electron_split_J:.3e} J, "
                f"nuclear splitting {nuclear_split_J:.3e} J"
            ),
        })

    result = compute_atom_behaviors(atom)
    result["applied"] = applied
    return result
