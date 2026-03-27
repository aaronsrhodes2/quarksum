"""Structure-to-Quark checksum: bare-quark mass reconstruction.

Reconstructs mass from bare quark + electron rest masses.
The resulting mass defect is ~-99% because QCD confinement energy
accounts for the vast majority of nucleon mass.
"""

from __future__ import annotations

from sigma_ground.inventory.checksum.particle_count import count_particles_in_structure
from sigma_ground.inventory.core.constants import CONSTANTS


_GALAXY_MASS_KG = 1e42
_COSMIC_BARYONIC_FRACTION = 0.049


def _baryonic_note(stated_mass_kg: float) -> str:
    """Contextual note on baryonic matter fraction at this scale."""
    if stated_mass_kg >= _GALAXY_MASS_KG:
        return (
            f"At this scale ({stated_mass_kg:.2g} kg), baryonic matter represents "
            f"~5% of the total mass-energy budget. The remaining ~95% is dark matter "
            f"(~27%) and dark energy (~68%). This checksum covers only the baryonic component."
        )
    return (
        f"This structure's mass ({stated_mass_kg:.2g} kg) is 100% baryonic — every "
        f"gram is accounted for by quarks and leptons. Dark matter and dark energy "
        f"become relevant only at galactic scales (>10⁴² kg); at cosmic scales, "
        f"baryonic matter is ~5% of the total mass-energy budget."
    )


def compute_stoq_checksum(root) -> dict:
    """Compute the quark-level StructureToQuarkChecksum for a root structure.

    Returns a dict with the full checksum payload.
    """
    stated_mass = root.resolved_mass_kg or 0.0

    grand_layer_mass, grand_p, grand_n, grand_e = count_particles_in_structure(
        root, stated_mass=stated_mass,
    )

    grand_up = 2.0 * grand_p + grand_n
    grand_down = grand_p + 2.0 * grand_n

    per_child: list[dict] = []
    for child in root.children:
        if child.children:
            child_mass = child.resolved_mass_kg
            d_mass, d_p, d_n, d_e = count_particles_in_structure(
                child, stated_mass=child_mass,
            )
            child_p = d_p * child.count
            child_n = d_n * child.count
            child_e = d_e * child.count
            child_up = 2.0 * child_p + child_n
            child_down = child_p + 2.0 * child_n
            child_recon = (
                child_up * CONSTANTS.m_up_kg
                + child_down * CONSTANTS.m_down_kg
                + child_e * CONSTANTS.m_e
            )
            child_total = child_mass * child.count
            child_defect = child_recon - child_total
            child_defect_pct = (child_defect / child_total * 100.0) if child_total > 0 else 0.0

            per_child.append({
                "name": child.name,
                "stated_mass_kg": child_total,
                "total_protons": child_p,
                "total_neutrons": child_n,
                "total_electrons": child_e,
                "total_up_quarks": child_up,
                "total_down_quarks": child_down,
                "reconstructed_mass_kg": child_recon,
                "mass_defect_kg": child_defect,
                "mass_defect_percent": child_defect_pct,
            })

    reconstructed = (
        grand_up * CONSTANTS.m_up_kg
        + grand_down * CONSTANTS.m_down_kg
        + grand_e * CONSTANTS.m_e
    )
    defect = reconstructed - stated_mass
    defect_pct = (defect / stated_mass * 100.0) if stated_mass > 0 else 0.0

    n_children = len(per_child)
    n_molecules = _count_unique_molecules(root)

    note = (
        f"Quark-level mass checksum: {grand_p:.4g} protons, "
        f"{grand_n:.4g} neutrons, {grand_e:.4g} electrons. "
        f"Mass defect {defect_pct:+.2f}%. "
        f"~99% mass defect is expected: bare quark rest masses are ~1% of nucleon mass. "
        f"The remaining 99% is QCD confinement energy (see /quark-chain for full reconstruction)."
    )

    return {
        "structure_name": root.name,
        "stated_mass_kg": stated_mass,
        "scope_summary": {
            "bodies": n_children,
            "materials": n_molecules,
            "nucleons": {
                "protons": grand_p,
                "neutrons": grand_n,
            },
            "quarks": {
                "up": grand_up,
                "down": grand_down,
            },
            "electrons": grand_e,
        },
        "reconstructed_mass_kg": reconstructed,
        "mass_defect_kg": defect,
        "mass_defect_percent": defect_pct,
        "per_body": per_child,
        "note": note,
        "baryonic_note": _baryonic_note(stated_mass),
    }


def _count_unique_molecules(structure) -> int:
    """Count unique molecules across the whole tree."""
    count = len(structure.unique_molecules)
    for child in structure.children:
        count += _count_unique_molecules(child)
    return count
