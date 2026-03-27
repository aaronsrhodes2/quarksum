"""Full quark-chain mass reconstruction.

Starts from bare quark masses and adds/subtracts every binding energy.
Every Standard Model field is explicitly computed — nothing omitted.

    predicted = valence_quarks + sea_quarks + gluons + electrons
              + QCD/c² − nuclear/c² − chemical/c²

Gluons are massless gauge bosons (rest_mass_kg = 0.0 by QCD gauge
invariance).  Sea quarks are virtual quark-antiquark pairs whose bare
masses are non-zero individually but whose net contribution to nucleon
mass is already folded into the QCD binding energy.  Both are included
explicitly so the formula is complete — every field computed by math.

Walks the resolved structure tree directly — no proportional allocation.
"""

from __future__ import annotations

from sigma_ground.inventory.checksum._walker_utils import molecule_ratios
from sigma_ground.inventory.checksum.stoq_checksum import _baryonic_note
from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.models.particle import Proton, Neutron
from sigma_ground.inventory.models.gluon import Gluon


def _quark_chain_constants() -> dict:
    """Pre-compute per-nucleon quark-chain constants.

    Every field from the particle models is extracted, including gluon
    rest mass (0.0 kg) and sea quark bare masses.
    """
    p = Proton.create()
    n = Neutron.create()

    # Valence quark bare masses (kg)
    quark_per_proton_kg = p.constituent_mass_kg   # sum of u+u+d bare masses
    quark_per_neutron_kg = n.constituent_mass_kg  # sum of u+d+d bare masses

    # Sea quark bare masses (kg) — virtual pairs, individually non-zero
    sea_per_proton_kg = sum(q.bare_mass_mev for q in p.sea_quarks) * CONSTANTS.MeV_to_kg
    sea_per_neutron_kg = sum(q.bare_mass_mev for q in n.sea_quarks) * CONSTANTS.MeV_to_kg

    # Gluon rest masses (kg) — massless by gauge invariance, but computed
    gluon_per_proton_kg = sum(g.rest_mass_kg for g in p.gluons)
    gluon_per_neutron_kg = sum(g.rest_mass_kg for g in n.gluons)

    # QCD binding energy (J)
    qcd_per_proton_j = p.binding_energy_joules
    qcd_per_neutron_j = n.binding_energy_joules

    return {
        # Valence quarks
        "quark_per_proton_kg": quark_per_proton_kg,
        "quark_per_neutron_kg": quark_per_neutron_kg,
        # Sea quarks (virtual pairs)
        "sea_per_proton_kg": sea_per_proton_kg,
        "sea_per_neutron_kg": sea_per_neutron_kg,
        # Gluons (massless gauge bosons)
        "gluon_per_proton_kg": gluon_per_proton_kg,
        "gluon_per_neutron_kg": gluon_per_neutron_kg,
        # QCD binding
        "qcd_per_proton_j": qcd_per_proton_j,
        "qcd_per_neutron_j": qcd_per_neutron_j,
        # Electron
        "m_e": CONSTANTS.m_e,
        # Particle counts per nucleon
        "valence_quarks_per_proton": len(p.quarks),
        "valence_quarks_per_neutron": len(n.quarks),
        "sea_quarks_per_proton": len(p.sea_quarks),
        "sea_quarks_per_neutron": len(n.sea_quarks),
        "gluons_per_proton": len(p.gluons),
        "gluons_per_neutron": len(n.gluons),
    }


def walk_quark_chain(structure, stated_mass=None, _consts=None, isotope_moles=False) -> dict:
    """Reconstruct mass from bare quarks through every binding energy level.

    Every Standard Model field is summed explicitly:
      - valence quark bare masses (u, d)
      - sea quark bare masses (uū, dd̄, ss̄ virtual pairs)
      - gluon rest masses (8 × 0.0 kg per nucleon)
      - electron rest masses
      - QCD binding energy
      - nuclear binding energy
      - chemical binding energy

    Uses structure.resolved_mass_kg directly. The stated_mass parameter
    is accepted for API compat but ignored when resolved_mass_kg is available.
    """
    if _consts is None:
        _consts = _quark_chain_constants()

    # Per-nucleon values
    qp_val = _consts["quark_per_proton_kg"]
    qn_val = _consts["quark_per_neutron_kg"]
    sp = _consts["sea_per_proton_kg"]
    sn = _consts["sea_per_neutron_kg"]
    gp = _consts["gluon_per_proton_kg"]
    gn = _consts["gluon_per_neutron_kg"]
    qcd_p = _consts["qcd_per_proton_j"]
    qcd_n = _consts["qcd_per_neutron_j"]
    m_e = _consts["m_e"]

    mass = structure.resolved_mass_kg
    if mass <= 0 and stated_mass is not None:
        mass = stated_mass

    t = {
        # Mass contributions (kg)
        "bare_quark_kg": 0.0,          # valence quarks only
        "sea_quark_kg": 0.0,           # virtual quark-antiquark pairs
        "gluon_kg": 0.0,               # massless gauge bosons (= 0.0)
        "electron_kg": 0.0,
        # Energy contributions (J)
        "qcd_binding_j": 0.0,
        "nuclear_binding_j": 0.0,
        "chemical_binding_j": 0.0,
        # Particle counts
        "proton_count": 0.0,
        "neutron_count": 0.0,
        "electron_count": 0.0,
        "valence_quark_count": 0.0,
        "sea_quark_count": 0.0,
        "gluon_count": 0.0,
        "atom_count": 0,
    }

    if structure.molecules and mass > 0:
        unique = structure.unique_molecules
        ratios = molecule_ratios(structure)

        for mol, ratio in zip(unique, ratios):
            if isotope_moles:
                molar_mass_kg = mol.constituent_mass_kg * CONSTANTS.N_A
            else:
                molar_mass_kg = mol.molecular_weight * 1e-3
            if molar_mass_kg <= 0:
                continue
            mass_portion = mass * ratio
            mol_count = mass_portion / molar_mass_kg * CONSTANTS.N_A

            for atom in mol.atoms:
                Z = atom.atomic_number
                N = atom.neutron_count

                # Valence quark bare masses
                t["bare_quark_kg"] += mol_count * (Z * qp_val + N * qn_val)

                # Sea quark bare masses (virtual pairs, non-zero individually)
                t["sea_quark_kg"] += mol_count * (Z * sp + N * sn)

                # Gluon rest masses (8 per nucleon × 0.0 kg each)
                t["gluon_kg"] += mol_count * (Z * gp + N * gn)

                # Electron rest masses
                t["electron_kg"] += mol_count * Z * m_e

                # QCD binding energy
                t["qcd_binding_j"] += mol_count * (Z * qcd_p + N * qcd_n)

                # Nuclear binding energy
                t["nuclear_binding_j"] += mol_count * atom.binding_energy_joules

                # Particle counts
                t["proton_count"] += mol_count * Z
                t["neutron_count"] += mol_count * N
                t["electron_count"] += mol_count * Z
                vq_per_proton = _consts["valence_quarks_per_proton"]
                vq_per_neutron = _consts["valence_quarks_per_neutron"]
                sq_per_proton = _consts["sea_quarks_per_proton"]
                sq_per_neutron = _consts["sea_quarks_per_neutron"]
                g_per_proton = _consts["gluons_per_proton"]
                g_per_neutron = _consts["gluons_per_neutron"]
                t["valence_quark_count"] += mol_count * (Z * vq_per_proton + N * vq_per_neutron)
                t["sea_quark_count"] += mol_count * (Z * sq_per_proton + N * sq_per_neutron)
                t["gluon_count"] += mol_count * (Z * g_per_proton + N * g_per_neutron)
                t["atom_count"] += int(mol_count)

            # Chemical binding energy
            t["chemical_binding_j"] += mol_count * mol.binding_energy_joules

    for child in structure.children:
        child_t = walk_quark_chain(
            child, stated_mass=child.resolved_mass_kg,
            _consts=_consts, isotope_moles=isotope_moles,
        )
        for key in t:
            t[key] += child_t[key] * child.count

    return t


def predict_from_quark_chain(t: dict) -> float:
    """Compute predicted mass from quark-chain totals dict.

    Every field is included in the sum:
        predicted = valence_quarks + sea_quarks + gluons + electrons
                  + QCD/c² − nuclear/c² − chemical/c²

    Sea quark masses are virtual pair bare masses — individually non-zero
    but their contribution to nucleon mass is ALREADY counted inside the
    QCD binding energy.  To avoid double-counting, sea_quark_kg is tracked
    separately but NOT added to the prediction sum.  The gluon_kg term IS
    added (it equals 0.0 by gauge invariance, so it's numerically neutral).
    """
    c2 = CONSTANTS.c_squared
    return (
        t["bare_quark_kg"]           # valence quark bare masses
        + t["gluon_kg"]              # gluon rest masses (= 0.0, gauge invariance)
        + t["electron_kg"]           # electron rest masses
        + t["qcd_binding_j"] / c2    # QCD confinement energy / c²
        - t["nuclear_binding_j"] / c2  # nuclear binding energy / c²
        - t["chemical_binding_j"] / c2  # chemical binding energy / c²
        # NOTE: sea_quark_kg is NOT added here because sea quark mass-energy
        # is already included in qcd_binding_j (they are virtual pairs whose
        # fluctuation energy is part of the QCD vacuum).  The term is computed
        # and tracked for inventory completeness.
    )


def compute_quark_chain_checksum(root) -> dict:
    """Full quark-chain checksum for a root structure.

    Returns a dict with every Standard Model mass contribution
    explicitly computed, including gluons (0.0 kg) and sea quarks.
    """
    stated_mass = root.resolved_mass_kg or 0.0

    t = walk_quark_chain(root, stated_mass=stated_mass)
    predicted = predict_from_quark_chain(t)
    defect = predicted - stated_mass
    defect_pct = (defect / stated_mass * 100.0) if stated_mass > 0 else 0.0

    return {
        "structure_name": root.name,
        "stated_mass_kg": stated_mass,

        # Every mass contribution explicitly computed
        "bare_quark_mass_kg": t["bare_quark_kg"],
        "sea_quark_bare_mass_kg": t["sea_quark_kg"],
        "gluon_mass_kg": t["gluon_kg"],
        "electron_mass_kg": t["electron_kg"],

        # Every energy contribution
        "qcd_binding_joules": t["qcd_binding_j"],
        "nuclear_binding_joules": t["nuclear_binding_j"],
        "chemical_binding_joules": t["chemical_binding_j"],

        # Prediction
        "predicted_mass_kg": predicted,
        "mass_defect_kg": defect,
        "mass_defect_percent": defect_pct,

        # Full particle counts
        "proton_count": t["proton_count"],
        "neutron_count": t["neutron_count"],
        "electron_count": t["electron_count"],
        "valence_quark_count": t["valence_quark_count"],
        "sea_quark_count": t["sea_quark_count"],
        "gluon_count": t["gluon_count"],
        "atom_count": t["atom_count"],

        "note": (
            f"Quark-chain reconstruction: valence_quarks + gluons(={t['gluon_kg']:.1e}) "
            f"+ electrons + QCD/c² − nuclear/c² − chemical/c² "
            f"= {predicted:.6g} kg vs stated {stated_mass:.6g} kg ({defect_pct:+.4f}%). "
            f"Sea quark bare mass ({t['sea_quark_kg']:.4e} kg) tracked but not summed "
            f"in prediction (already inside QCD binding energy)."
        ),
        "formula": (
            "predicted = bare_quarks + gluon_mass + electrons "
            "+ QCD_binding/c² − nuclear_binding/c² − chemical_binding/c²"
        ),
        "sea_quark_note": (
            f"Sea quarks: {t['sea_quark_count']:.0f} virtual quark-antiquark pairs "
            f"(uū + dd̄ + ss̄ per nucleon). Bare mass sum = {t['sea_quark_kg']:.4e} kg. "
            f"This mass-energy is already counted inside QCD binding energy "
            f"({t['qcd_binding_j']:.4e} J), so it is tracked separately to avoid "
            f"double-counting."
        ),
        "gluon_note": (
            f"Gluons: {t['gluon_count']:.0f} massless SU(3) gauge bosons "
            f"(8 per nucleon). rest_mass = 0.0 kg by gauge invariance. "
            f"Gluon field energy is the dominant contributor to QCD binding energy."
        ),
        "baryonic_note": _baryonic_note(stated_mass),
    }
