"""Universal recursive structure model.

Everything is a Structure — from a quark-gluon plasma sample to a solar system.
A structure can contain molecules (leaf level) and/or child structures (any level).

Mass is resolved via the resolver module before walkers run.  Each node specifies
its contribution as one of: mass_kg (concrete), volume_m3 (converted via density),
or ratio (fraction of parent).  At least one concrete mass must exist in the tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from sigma_ground.inventory.models.molecule import Molecule


class MaterialClass(Enum):
    METAL = "metal"
    SEMIMETAL = "semimetal"
    SEMICONDUCTOR = "semiconductor"
    INSULATOR = "insulator"
    MOLECULAR = "molecular"
    IONIC = "ionic"
    NETWORK_COVALENT = "network_covalent"
    NOBLE_GAS = "noble_gas"
    VACUUM = "vacuum"


@dataclass
class Structure:
    """Universal recursive structure.

    Construction inputs (set one per node):
        mass_kg      — concrete mass in kilograms (anchor candidate)
        volume_m3    — volume in m³, converted to mass via standard_density
        ratio        — fraction of parent mass (needs anchor elsewhere)

    After resolve() runs, every node has a concrete ``resolved_mass_kg``.
    """

    name: str = ""
    resolved_mass_kg: float = 0.0

    mass_kg: float | None = None
    volume_m3: float | None = None
    ratio: float | None = None
    count: int = 1

    id: str = field(default_factory=lambda: str(uuid4()))

    formula: str = ""
    material_class: str = ""
    crystal_structure: str = "amorphous"
    standard_density: float = 0.0
    standard_melting_point: float | None = None
    standard_boiling_point: float | None = None
    band_gap: float | None = None
    is_antimatter: bool = False
    permittivity_override: float | None = None

    children: list["Structure"] = field(default_factory=list)
    molecules: list[Molecule] = field(default_factory=list)

    def _value_fields(self) -> tuple:
        """All fields except the random UUID id, for equality/hashing."""
        return (
            self.name,
            self.resolved_mass_kg,
            self.mass_kg,
            self.volume_m3,
            self.ratio,
            self.count,
            self.formula,
            self.material_class,
            self.crystal_structure,
            self.standard_density,
            self.standard_melting_point,
            self.standard_boiling_point,
            self.band_gap,
            self.is_antimatter,
            self.permittivity_override,
            tuple(self.children),
            tuple(self.molecules),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Structure):
            return NotImplemented
        return self._value_fields() == other._value_fields()

    def __hash__(self) -> int:
        return hash(self._value_fields())

    @property
    def unique_molecules(self) -> list[Molecule]:
        seen: set[str] = set()
        result = []
        for mol in self.molecules:
            if mol.formula not in seen:
                seen.add(mol.formula)
                result.append(mol)
        return result

    @classmethod
    def vacuum(cls) -> Structure:
        return cls(
            name="Vacuum",
            formula="",
            material_class=MaterialClass.VACUUM.value,
            crystal_structure="none",
            standard_density=0.0,
            permittivity_override=1.0,
        )
