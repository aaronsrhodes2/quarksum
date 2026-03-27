"""Count protons, neutrons, and electrons in a structure.

Walks the resolved structure tree. Each node's resolved_mass_kg is
already set by the resolver — no proportional allocation here.
"""

from __future__ import annotations

from sigma_ground.inventory.checksum._walker_utils import molecule_ratios
from sigma_ground.inventory.core.constants import CONSTANTS


def count_particles_in_structure(
    structure, stated_mass: float | None = None,
) -> tuple[float, float, float, float]:
    """Walk a structure tree and count protons, neutrons, electrons.

    Uses structure.resolved_mass_kg (set by the resolver).
    The stated_mass parameter is accepted for API compat but ignored
    when resolved_mass_kg is available.

    Returns (sum_mass_used_kg, total_protons, total_neutrons, total_electrons).
    """
    mass = structure.resolved_mass_kg
    if mass <= 0 and stated_mass is not None:
        mass = stated_mass

    total_p = 0.0
    total_n = 0.0
    total_e = 0.0
    sum_used = 0.0

    if structure.molecules and mass > 0:
        unique = structure.unique_molecules
        ratios = molecule_ratios(structure)

        sum_used += mass
        for mol, ratio in zip(unique, ratios):
            mw = mol.molecular_weight
            if mw <= 0:
                continue
            mass_portion = mass * ratio
            moles = mass_portion / (mw * 1e-3)
            mol_count = moles * CONSTANTS.N_A

            for atom in mol.atoms:
                z = atom.atomic_number
                a = atom.mass_number
                total_p += mol_count * z
                total_n += mol_count * (a - z)
                total_e += mol_count * z

    for child in structure.children:
        child_mass = child.resolved_mass_kg
        _, d_p, d_n, d_e = count_particles_in_structure(child, stated_mass=child_mass)
        total_p += d_p * child.count
        total_n += d_n * child.count
        total_e += d_e * child.count
        sum_used += child_mass * child.count

    return sum_used, total_p, total_n, total_e
