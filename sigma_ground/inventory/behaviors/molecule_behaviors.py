"""Behavioral computations for molecules.

Returns intrinsic/operable dict and environment resolution for Molecule entities.
All physics values come from the entity itself (MaterialDB bond data) and CONSTANTS.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sigma_ground.inventory.core.constants import CONSTANTS

if TYPE_CHECKING:
    from sigma_ground.inventory.models.molecule import Molecule

_MOLECULE_VALID_KEYS = {"energy_ev", "temperature_k", "pressure_pa", "electric_field_vm"}


def _bond_summary(molecule: Molecule) -> dict:
    """Summarize bond properties from the molecule's own bond list."""
    if not molecule.bonds:
        return {"count": 0, "weakest_bond_ev": None, "total_dissociation_ev": 0.0}

    energies = [
        b.dissociation_energy for b in molecule.bonds
        if b.dissociation_energy is not None
    ]
    return {
        "count": len(molecule.bonds),
        "weakest_bond_ev": min(energies) if energies else None,
        "strongest_bond_ev": max(energies) if energies else None,
        "total_dissociation_ev": sum(energies),
    }


def compute_molecule_behaviors(molecule: Molecule) -> dict:
    """Compute behaviors for a molecule."""
    from sigma_ground.inventory.behaviors import extract_fields

    intrinsic_fields, operable_fields = extract_fields(molecule)

    children = {
        "atoms": len(molecule.atoms),
        "bonds": len(molecule.bonds),
    }

    return {
        "entity_type": "molecule",
        "formula": molecule.formula,
        "intrinsic": intrinsic_fields,
        "operable": operable_fields,
        "children": children,
        "bond_summary": _bond_summary(molecule),
    }


def resolve_molecule_env(molecule: Molecule, env: dict, mode: str = "delta") -> dict:
    """Apply environment values to a molecule and return updated behaviors."""
    bad_keys = set(env) - _MOLECULE_VALID_KEYS
    if bad_keys:
        raise ValueError(
            f"Invalid molecule environment keys: {bad_keys}. "
            f"Valid keys: {sorted(_MOLECULE_VALID_KEYS)}"
        )

    applied: list[dict] = []

    if "energy_ev" in env:
        E = env["energy_ev"]
        if mode == "delta" and E > 0 and molecule.bonds:
            candidates = [
                b for b in molecule.bonds
                if b.dissociation_energy is not None and E >= b.dissociation_energy
            ]
            if candidates:
                weakest = min(candidates, key=lambda b: b.dissociation_energy)
                molecule.bonds.remove(weakest)
                applied.append({
                    "key": "energy_ev", "mode": mode, "value": E,
                    "consequence": (
                        f"bond broken: {weakest.bond_type} "
                        f"(D_e={weakest.dissociation_energy:.2f} eV, "
                        f"excess={E - weakest.dissociation_energy:.2f} eV)"
                    ),
                })
            else:
                applied.append({
                    "key": "energy_ev", "mode": mode, "value": E,
                    "consequence": "below all bond dissociation thresholds",
                })
        else:
            applied.append({
                "key": "energy_ev", "mode": mode, "value": E,
                "consequence": "energy applied (update mode or non-positive delta)",
            })

    if "temperature_k" in env:
        T = env["temperature_k"]
        kT_J = CONSTANTS.k_B * abs(T)
        for bond in molecule.bonds:
            if bond.dissociation_energy is None:
                continue
            D_e_J = bond.dissociation_energy * CONSTANTS.e
            r_e = bond.reference_length
            # Morse parameter: a = sqrt(k_eff / (2 * D_e))
            # k_eff approximated from bond order: ~500 N/m per bond order
            k_eff = 500.0 * bond.bond_order if bond.bond_order > 0 else 500.0
            a = math.sqrt(k_eff / (2.0 * D_e_J)) if D_e_J > 0 else 1.0
            # Thermal displacement: <x^2> ~ kT / k_eff => x_rms ~ sqrt(kT/k_eff)
            x_rms_m = math.sqrt(kT_J / k_eff) if k_eff > 0 else 0.0
            x_rms_angstrom = x_rms_m * 1e10
            if mode == "delta":
                bond.length = bond.length + x_rms_angstrom
            else:
                bond.length = r_e + x_rms_angstrom
        applied.append({
            "key": "temperature_k", "mode": mode, "value": T,
            "consequence": f"thermal vibration at T={abs(T):.0f} K (kT={kT_J:.3e} J)",
        })

    if "pressure_pa" in env:
        P = env["pressure_pa"]
        for bond in molecule.bonds:
            k_eff = 500.0 * bond.bond_order if bond.bond_order > 0 else 500.0
            # Bulk modulus ~ k_eff / r_e (order-of-magnitude)
            r_e_m = bond.reference_length * 1e-10
            K = k_eff / r_e_m if r_e_m > 0 else 1e11
            dr_over_r = -P / (3.0 * K)
            if mode == "update":
                bond.length = bond.reference_length * (1.0 + dr_over_r)
            else:
                bond.length = bond.length * (1.0 + dr_over_r)
        applied.append({
            "key": "pressure_pa", "mode": mode, "value": P,
            "consequence": f"pressure {'applied' if mode == 'update' else 'adjusted'} at {P:.3e} Pa",
        })

    if "electric_field_vm" in env:
        F = env["electric_field_vm"]
        total_polarizability = 0.0
        for atom in molecule.atoms:
            r = atom.atomic_radius
            if r is not None:
                alpha = 4.0 * math.pi * CONSTANTS.epsilon_0 * (r * 1e-12) ** 3
                total_polarizability += alpha
        induced_dipole = total_polarizability * F
        applied.append({
            "key": "electric_field_vm", "mode": mode, "value": F,
            "consequence": (
                f"induced dipole moment: {induced_dipole:.3e} C*m "
                f"(molecular polarizability: {total_polarizability:.3e} C^2*s^2/(kg*m^3))"
            ),
        })

    result = compute_molecule_behaviors(molecule)
    result["applied"] = applied
    return result
