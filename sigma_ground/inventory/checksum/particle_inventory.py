"""Full Standard Model particle inventory for a structure.

Every Standard Model field is counted and its mass contribution computed
by math — nothing omitted, nothing rounded away.  Gluon mass is 0.0 kg
(gauge invariance), sea quark masses are computed from PDG bare masses,
heavy quarks/leptons/bosons are explicitly set to 0 × (their mass).

Walks the resolved structure tree. Each node's resolved_mass_kg is
already set by the resolver — no proportional allocation here.

All 19 Standard Model fundamental particles are always present in the output,
even when their count is zero.
"""

from __future__ import annotations

from sigma_ground.inventory.checksum._walker_utils import molecule_ratios
from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.models.particle import Proton, Neutron
from sigma_ground.inventory.models.quark import Quark


def _empty_accum() -> dict:
    return {
        "protons": 0.0,
        "neutrons": 0.0,
        "electrons": 0.0,
        "atoms": 0.0,
        "molecules": 0.0,
        "bonds_single": 0.0,
        "bonds_double": 0.0,
        "bonds_triple": 0.0,
        "bonds_aromatic": 0.0,
        "bonds_ionic": 0.0,
        "bonds_metallic": 0.0,
        "bonds_hydrogen": 0.0,
        "bonds_van_der_waals": 0.0,
    }


_BOND_TYPE_MAP = {
    "single": "bonds_single",
    "double": "bonds_double",
    "triple": "bonds_triple",
    "aromatic": "bonds_aromatic",
    "ionic": "bonds_ionic",
    "metallic": "bonds_metallic",
    "hydrogen": "bonds_hydrogen",
    "van_der_waals": "bonds_van_der_waals",
}


def _walk(structure, acc: dict) -> None:
    """Recursive walk that accumulates counts into acc."""
    mass = structure.resolved_mass_kg

    if structure.molecules and mass > 0:
        unique = structure.unique_molecules
        ratios = molecule_ratios(structure)

        for mol, ratio in zip(unique, ratios):
            mw = mol.molecular_weight
            if mw <= 0:
                continue
            mass_portion = mass * ratio
            moles = mass_portion / (mw * 1e-3)
            mol_count = moles * CONSTANTS.N_A

            acc["molecules"] += mol_count

            for bond in mol.bonds:
                key = _BOND_TYPE_MAP.get(bond.bond_type, "bonds_single")
                acc[key] += mol_count

            for atom in mol.atoms:
                z = atom.atomic_number
                n = atom.mass_number - z
                acc["atoms"] += mol_count
                acc["protons"] += mol_count * z
                acc["neutrons"] += mol_count * n
                acc["electrons"] += mol_count * z

    for child in structure.children:
        child_acc = _empty_accum()
        _walk(child, child_acc)
        for k in acc:
            acc[k] += child_acc[k] * child.count


def compute_particle_inventory(structure) -> dict:
    """Compute the full Standard Model particle inventory for a structure.

    Every field is explicitly computed by math — nothing omitted.
    If a particle count is zero, its mass is computed as 0 × (particle mass).
    Gluons: 8 per nucleon, rest_mass = 0.0 kg (gauge invariance).
    Sea quarks: 6 per nucleon (uū + dd̄ + ss̄), bare masses from PDG.

    Returns a flat dict with counts and mass contributions for all 19
    fundamental particle types, plus composite counts (atoms, molecules)
    and bond counts by type.
    """
    stated = structure.resolved_mass_kg or 0.0
    acc = _empty_accum()
    _walk(structure, acc)

    p_count = acc["protons"]
    n_count = acc["neutrons"]
    e_count = acc["electrons"]
    nucleons = p_count + n_count

    # Valence quarks: 3 per nucleon (uud for proton, udd for neutron)
    up_quarks = 2 * p_count + n_count
    down_quarks = p_count + 2 * n_count

    # Sea quarks: 6 per nucleon (3 virtual quark-antiquark pairs)
    # Each nucleon contains uū + dd̄ + ss̄ pairs
    sea_up = 1 * nucleons          # one up from each uū pair
    sea_anti_up = 1 * nucleons     # one anti-up
    sea_down = 1 * nucleons        # one down from each dd̄ pair
    sea_anti_down = 1 * nucleons   # one anti-down
    sea_strange = 1 * nucleons     # one strange from each ss̄ pair
    sea_anti_strange = 1 * nucleons  # one anti-strange
    sea_quarks_total = 6 * nucleons

    # Gluons: 8 per nucleon (SU(3) color octet)
    gluons = 8 * nucleons

    # Composite masses
    proton_mass = p_count * CONSTANTS.m_p
    neutron_mass = n_count * CONSTANTS.m_n
    electron_mass = e_count * CONSTANTS.m_e

    # Valence quark bare masses (MS-bar, PDG 2024)
    up_mass = up_quarks * CONSTANTS.m_up_kg
    down_mass = down_quarks * CONSTANTS.m_down_kg

    # Sea quark bare masses — every flavor computed individually
    m_up_kg = CONSTANTS.m_up_mev * CONSTANTS.MeV_to_kg
    m_down_kg = CONSTANTS.m_down_mev * CONSTANTS.MeV_to_kg
    m_strange_mev = 93.4  # PDG 2024, MS-bar
    m_strange_kg = m_strange_mev * CONSTANTS.MeV_to_kg
    # Anti-quarks have identical mass (CPT theorem)
    sea_up_mass = sea_up * m_up_kg
    sea_anti_up_mass = sea_anti_up * m_up_kg         # CPT: m(ū) = m(u)
    sea_down_mass = sea_down * m_down_kg
    sea_anti_down_mass = sea_anti_down * m_down_kg   # CPT: m(d̄) = m(d)
    sea_strange_mass = sea_strange * m_strange_kg
    sea_anti_strange_mass = sea_anti_strange * m_strange_kg  # CPT: m(s̄) = m(s)
    sea_quarks_total_mass = (
        sea_up_mass + sea_anti_up_mass
        + sea_down_mass + sea_anti_down_mass
        + sea_strange_mass + sea_anti_strange_mass
    )

    # Gluon rest mass — 0.0 kg per gluon (QCD gauge invariance)
    gluon_mass_each = 0.0  # kg, by gauge invariance
    gluon_mass = gluons * gluon_mass_each

    # Heavy quarks: 0 in cold baryonic matter, but mass computed as 0 × m
    charm_count = 0
    bottom_count = 0
    top_count = 0
    m_charm_kg = CONSTANTS.m_charm_mev * CONSTANTS.MeV_to_kg
    m_bottom_kg = CONSTANTS.m_bottom_mev * CONSTANTS.MeV_to_kg
    m_top_kg = CONSTANTS.m_top_mev * CONSTANTS.MeV_to_kg
    charm_mass = charm_count * m_charm_kg
    bottom_mass = bottom_count * m_bottom_kg
    top_mass = top_count * m_top_kg

    # Heavy leptons: 0 in cold baryonic matter
    muon_count = 0
    tau_count = 0
    muon_mass = muon_count * CONSTANTS.m_muon
    tau_mass = tau_count * CONSTANTS.m_tau

    # Neutrinos: 0 stable constituents (mass upper bound ~0.1 eV/c²)
    nu_e_count = 0
    nu_mu_count = 0
    nu_tau_count = 0
    m_nu_upper_kg = 0.1 * CONSTANTS.e / CONSTANTS.c_squared  # 0.1 eV/c² upper bound
    nu_e_mass = nu_e_count * m_nu_upper_kg
    nu_mu_mass = nu_mu_count * m_nu_upper_kg
    nu_tau_mass = nu_tau_count * m_nu_upper_kg

    # Gauge bosons (excluding gluons): 0 stable constituents
    photon_count = 0
    w_count = 0
    z_count = 0
    higgs_count = 0
    photon_mass = photon_count * 0.0              # massless (gauge invariance)
    w_mass = w_count * CONSTANTS.m_W
    z_mass = z_count * CONSTANTS.m_Z
    higgs_mass = higgs_count * CONSTANTS.m_higgs

    def _pct(m: float) -> float:
        return (m / stated * 100.0) if stated > 0 else 0.0

    bonds_total = sum(
        acc[k] for k in acc if k.startswith("bonds_")
    )

    return {
        "structure_name": structure.name,
        "stated_mass_kg": stated,

        # ── Composite particles ──
        "protons": p_count,
        "protons_mass_kg": proton_mass,
        "protons_mass_percent": _pct(proton_mass),

        "neutrons": n_count,
        "neutrons_mass_kg": neutron_mass,
        "neutrons_mass_percent": _pct(neutron_mass),

        "electrons": e_count,
        "electrons_mass_kg": electron_mass,
        "electrons_mass_percent": _pct(electron_mass),

        # ── Valence quarks ──
        "up_quarks": up_quarks,
        "up_quarks_mass_kg": up_mass,
        "up_quarks_mass_percent": _pct(up_mass),

        "down_quarks": down_quarks,
        "down_quarks_mass_kg": down_mass,
        "down_quarks_mass_percent": _pct(down_mass),

        # ── Sea quarks (virtual pairs, individually computed) ──
        "sea_quarks": sea_quarks_total,
        "sea_quarks_mass_kg": sea_quarks_total_mass,
        "sea_quarks_mass_percent": _pct(sea_quarks_total_mass),
        "sea_up": sea_up,
        "sea_up_mass_kg": sea_up_mass,
        "sea_anti_up": sea_anti_up,
        "sea_anti_up_mass_kg": sea_anti_up_mass,
        "sea_down": sea_down,
        "sea_down_mass_kg": sea_down_mass,
        "sea_anti_down": sea_anti_down,
        "sea_anti_down_mass_kg": sea_anti_down_mass,
        "sea_strange": sea_strange,
        "sea_strange_mass_kg": sea_strange_mass,
        "sea_anti_strange": sea_anti_strange,
        "sea_anti_strange_mass_kg": sea_anti_strange_mass,

        # ── Gluons (massless gauge bosons, counted and summed) ──
        "gluons": gluons,
        "gluons_mass_kg": gluon_mass,
        "gluons_mass_percent": _pct(gluon_mass),
        "gluon_mass_each_kg": gluon_mass_each,

        # ── Strange quarks (all sea — no valence strange in cold baryonic matter) ──
        "strange_quarks": sea_strange + sea_anti_strange,
        "strange_quarks_mass_kg": sea_strange_mass + sea_anti_strange_mass,
        "strange_quarks_mass_percent": _pct(sea_strange_mass + sea_anti_strange_mass),

        # ── Heavy quarks (0 × mass, computed) ──
        "charm_quarks": charm_count,
        "charm_quarks_mass_kg": charm_mass,
        "bottom_quarks": bottom_count,
        "bottom_quarks_mass_kg": bottom_mass,
        "top_quarks": top_count,
        "top_quarks_mass_kg": top_mass,

        # ── Heavy leptons (0 × mass, computed) ──
        "muons": muon_count,
        "muons_mass_kg": muon_mass,
        "taus": tau_count,
        "taus_mass_kg": tau_mass,

        # ── Neutrinos (0 × upper bound mass, computed) ──
        "electron_neutrinos": nu_e_count,
        "electron_neutrinos_mass_kg": nu_e_mass,
        "muon_neutrinos": nu_mu_count,
        "muon_neutrinos_mass_kg": nu_mu_mass,
        "tau_neutrinos": nu_tau_count,
        "tau_neutrinos_mass_kg": nu_tau_mass,

        # ── Gauge bosons (0 × mass, computed) ──
        "photons": photon_count,
        "photons_mass_kg": photon_mass,
        "w_bosons": w_count,
        "w_bosons_mass_kg": w_mass,
        "z_bosons": z_count,
        "z_bosons_mass_kg": z_mass,
        "higgs_bosons": higgs_count,
        "higgs_bosons_mass_kg": higgs_mass,

        # ── Composites ──
        "atoms": acc["atoms"],
        "molecules": acc["molecules"],

        "bonds_total": bonds_total,
        "bonds_single": acc["bonds_single"],
        "bonds_double": acc["bonds_double"],
        "bonds_triple": acc["bonds_triple"],
        "bonds_aromatic": acc["bonds_aromatic"],
        "bonds_ionic": acc["bonds_ionic"],
        "bonds_metallic": acc["bonds_metallic"],
        "bonds_hydrogen": acc["bonds_hydrogen"],
        "bonds_van_der_waals": acc["bonds_van_der_waals"],

        # ── Totals ──
        "total_fundamental_fermions": up_quarks + down_quarks + e_count + sea_quarks_total,
        "total_gauge_bosons": gluons + photon_count + w_count + z_count + higgs_count,
        "total_all_particles": (
            up_quarks + down_quarks + e_count
            + sea_quarks_total + gluons
            + charm_count + bottom_count + top_count
            + muon_count + tau_count
            + nu_e_count + nu_mu_count + nu_tau_count
            + photon_count + w_count + z_count + higgs_count
        ),

        "standard_model_note": (
            "Complete Standard Model particle inventory. Every field computed by math. "
            "Heavy quarks (c, b, t): 0 × (PDG mass) = 0.0 kg — not stable in cold matter. "
            "Heavy leptons (μ, τ): 0 × (PDG mass) = 0.0 kg — not stable. "
            "Neutrinos (νe, νμ, ντ): 0 × (0.1 eV/c² upper bound) = 0.0 kg. "
            "Gauge bosons (γ, W±, Z⁰, H⁰): 0 × (mass) = 0.0 kg — not stable constituents. "
            "Gluons: 8 per nucleon × 0.0 kg = 0.0 kg — massless by gauge invariance. "
            "Sea quarks: 6 per nucleon (uū + dd̄ + ss̄), bare masses summed from PDG values. "
            "Sea quark mass-energy is already inside QCD binding energy — tracked separately."
        ),
    }
