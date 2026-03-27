"""Top-down material generator (trimmed for QuarkSum pipeline).

Select a material name and generate the complete hierarchy:
Structure -> Molecules -> Atoms -> Particles -> Quarks
"""

from __future__ import annotations

import logging
from uuid import uuid4

from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.data.loader import ElementDB, MaterialDB
from sigma_ground.inventory.models.atom import Atom
from sigma_ground.inventory.models.bond import Bond, BondType
from sigma_ground.inventory.models.molecule import Molecule
from sigma_ground.inventory.models.particle import Electron, Neutron, Proton
from sigma_ground.inventory.models.structure import Structure, MaterialClass

log = logging.getLogger(__name__)

_PARTICLE_SYMBOLS = {"n", "p", "e"}


def _build_particle_atom(symbol: str) -> Atom:
    """Create a synthetic Atom wrapper for a particle-level composition symbol."""
    if symbol == "n":
        return Atom(
            id=str(uuid4()), symbol="n⁰", name="Neutron",
            atomic_number=0, atomic_mass=CONSTANTS.m_n / 1.66053906660e-27,
            electron_configuration="", element_category="nucleon",
            period=0, block="n", mass_number=1, neutron_count=1,
            protons=[], neutrons=[Neutron.create()], electrons=[],
        )
    if symbol == "p":
        return Atom(
            id=str(uuid4()), symbol="p⁺", name="Proton",
            atomic_number=1, atomic_mass=CONSTANTS.m_p / 1.66053906660e-27,
            electron_configuration="", element_category="nucleon",
            period=0, block="n", mass_number=1, neutron_count=0,
            protons=[Proton.create()], neutrons=[], electrons=[],
        )
    if symbol == "e":
        return Atom(
            id=str(uuid4()), symbol="e⁻", name="Electron",
            atomic_number=0, atomic_mass=CONSTANTS.m_e / 1.66053906660e-27,
            electron_configuration="", element_category="lepton",
            period=0, block="l", mass_number=0, neutron_count=0,
            protons=[], neutrons=[], electrons=[Electron.create()],
        )
    raise ValueError(f"Unknown particle symbol: '{symbol}'")


_BOND_TYPE_MAP = {
    "single": BondType.SINGLE,
    "double": BondType.DOUBLE,
    "triple": BondType.TRIPLE,
    "aromatic": BondType.AROMATIC,
    "ionic": BondType.IONIC,
    "metallic": BondType.METALLIC,
    "hydrogen": BondType.HYDROGEN,
    "van_der_waals": BondType.VAN_DER_WAALS,
}

_MATERIAL_CLASS_MAP = {
    "metal": MaterialClass.METAL,
    "semimetal": MaterialClass.SEMIMETAL,
    "semiconductor": MaterialClass.SEMICONDUCTOR,
    "insulator": MaterialClass.INSULATOR,
    "molecular": MaterialClass.MOLECULAR,
    "molecular_solid": MaterialClass.MOLECULAR,
    "ionic": MaterialClass.IONIC,
    "network_covalent": MaterialClass.NETWORK_COVALENT,
    "noble_gas": MaterialClass.NOBLE_GAS,
    "liquid": MaterialClass.MOLECULAR,
    "gas": MaterialClass.MOLECULAR,
}


class MaterialGenerator:
    """Generates a fully populated Structure from a material name."""

    def __init__(self) -> None:
        self._elements = ElementDB.get()
        self._materials = MaterialDB.get()

    def generate(self, material_name: str) -> Structure:
        """Build a complete Structure with molecular/atomic/particle/quark tree."""
        mat = self._materials.by_name(material_name)

        mat_class_str = mat.get("material_class", "")
        mat_class = _MATERIAL_CLASS_MAP.get(mat_class_str, MaterialClass.MOLECULAR)

        composition = mat.get("molecular_composition", [])
        if not composition:
            return Structure(
                name=mat["name"],
                formula=mat["formula"],
                material_class=mat_class.value,
                molecules=[],
                crystal_structure=mat.get("crystal_structure", "none"),
                standard_density=mat.get("density", 0.0),
                permittivity_override=mat.get("relative_permittivity", 1.0),
            )

        molecule = self._build_molecule(mat)

        return Structure(
            name=mat["name"],
            formula=mat["formula"],
            material_class=mat_class.value,
            molecules=[molecule],
            crystal_structure=mat.get("crystal_structure", "amorphous"),
            standard_density=mat.get("density", 0.0),
            standard_melting_point=mat.get("melting_point"),
            standard_boiling_point=mat.get("boiling_point"),
            band_gap=mat.get("band_gap"),
        )

    def generate_mixed(self, material_ratios: list[tuple[str, float]]) -> Structure:
        """Build a Structure from multiple materials with ratios."""
        if len(material_ratios) == 1:
            return self.generate(material_ratios[0][0])

        all_molecules: list[Molecule] = []
        primary_mat = self._materials.by_name(material_ratios[0][0])

        for mat_name, _ratio in material_ratios:
            mat = self._materials.by_name(mat_name)
            if not mat.get("molecular_composition"):
                continue
            mol = self._build_molecule(mat)
            all_molecules.append(mol)

        names = " + ".join(f"{n}({r*100:.0f}%)" for n, r in material_ratios)
        formulas = "-".join(n for n, _ in material_ratios)
        mat_class = _MATERIAL_CLASS_MAP.get(
            primary_mat.get("material_class", ""), MaterialClass.MOLECULAR
        )

        return Structure(
            name=names,
            formula=formulas,
            material_class=mat_class.value,
            molecules=all_molecules,
            crystal_structure=primary_mat.get("crystal_structure", "amorphous"),
            standard_density=primary_mat.get("density", 0.0),
            standard_melting_point=primary_mat.get("melting_point"),
            standard_boiling_point=primary_mat.get("boiling_point"),
            band_gap=primary_mat.get("band_gap"),
        )

    def _build_molecule(self, mat: dict) -> Molecule:
        composition = mat.get("molecular_composition", [])
        bond_info = mat.get("bond_info", [])

        atoms: list[Atom] = []
        atom_index_map: dict[str, list[Atom]] = {}

        for entry in composition:
            symbol = entry["symbol"]
            count = entry.get("count", 1)

            for _ in range(count):
                if symbol in _PARTICLE_SYMBOLS:
                    atom = _build_particle_atom(symbol)
                else:
                    element_data = self._elements.by_symbol(symbol)
                    atom = Atom.create(element_data)
                atoms.append(atom)
                atom_index_map.setdefault(symbol, []).append(atom)

        bonds = self._build_bonds(atom_index_map, bond_info)
        mw = sum(a.atomic_mass for a in atoms)

        return Molecule.create(
            formula=mat["formula"],
            atoms=atoms,
            bonds=bonds,
            molecular_weight=mw,
            common_name=mat["name"],
            iupac_name=mat.get("iupac_name", ""),
        )

    def _build_bonds(
        self,
        atom_map: dict[str, list[Atom]],
        bond_info: list[dict],
    ) -> list[Bond]:
        bonds: list[Bond] = []

        for info in bond_info:
            sym1 = info.get("atom1", "")
            sym2 = info.get("atom2", "")
            bond_type_str = info.get("type", "single")
            length = info.get("length_angstrom")
            if length is None:
                length = 1.5
            energy = info.get("dissociation_energy_ev")

            atoms1 = atom_map.get(sym1, [])
            atoms2 = atom_map.get(sym2, [])

            if not atoms1 or not atoms2:
                continue

            bond_type = _BOND_TYPE_MAP.get(bond_type_str, BondType.SINGLE)

            if sym1 == sym2:
                for i in range(0, len(atoms1) - 1, 2):
                    if i + 1 < len(atoms1):
                        bonds.append(Bond.create(
                            atom_id_1=atoms1[i].id,
                            atom_id_2=atoms1[i + 1].id,
                            bond_type=bond_type,
                            reference_length=length,
                            dissociation_energy=energy,
                        ))
            else:
                for a2 in atoms2:
                    if atoms1:
                        bonds.append(Bond.create(
                            atom_id_1=atoms1[0].id,
                            atom_id_2=a2.id,
                            bond_type=bond_type,
                            reference_length=length,
                            dissociation_energy=energy,
                        ))

        return bonds
