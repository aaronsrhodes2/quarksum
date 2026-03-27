"""Chemical bonds between atoms within a molecule."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from sigma_ground.inventory.core.types import PhysicsObject, constant, variable


class BondType(Enum):
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    AROMATIC = "aromatic"
    IONIC = "ionic"
    METALLIC = "metallic"
    HYDROGEN = "hydrogen"
    VAN_DER_WAALS = "van_der_waals"


@dataclass
class Bond(PhysicsObject):
    """A chemical bond connecting two atoms."""

    id: str = constant(description="Unique identifier")
    atom_id_1: str = constant(description="ID of the first atom")
    atom_id_2: str = constant(description="ID of the second atom")
    bond_type: str = constant(description="Bond type classification")
    bond_order: int = constant(description="Bond order")
    reference_length: float = constant(description="Standard bond length", unit="Å")

    length: float = variable(
        description="Current bond length",
        unit="Å", quantity_type="length_angstrom",
        min_val=0.1, max_val=10.0,
    )

    dissociation_energy: float | None = constant(
        description="Bond dissociation energy", unit="eV", default=None,
    )

    @classmethod
    def create(
        cls,
        atom_id_1: str,
        atom_id_2: str,
        bond_type: BondType,
        reference_length: float,
        dissociation_energy: float | None = None,
    ) -> Bond:
        order_map = {
            BondType.SINGLE: 1, BondType.DOUBLE: 2, BondType.TRIPLE: 3,
            BondType.AROMATIC: 1, BondType.IONIC: 1, BondType.METALLIC: 1,
            BondType.HYDROGEN: 0, BondType.VAN_DER_WAALS: 0,
        }
        return cls(
            id=str(uuid4()),
            atom_id_1=atom_id_1,
            atom_id_2=atom_id_2,
            bond_type=bond_type.value,
            bond_order=order_map.get(bond_type, 1),
            reference_length=reference_length,
            dissociation_energy=dissociation_energy,
            length=reference_length,
        )
