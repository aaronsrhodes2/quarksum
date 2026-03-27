"""Level 2 — Molecules.

A molecule is a collection of atoms connected by bonds, with aggregate
properties for the checksum pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from uuid import uuid4

from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.core.types import PhysicsObject, constant, variable
from sigma_ground.inventory.models.atom import Atom
from sigma_ground.inventory.models.bond import Bond


@dataclass
class Molecule(PhysicsObject):
    """A molecule composed of atoms and bonds."""

    id: str = constant(description="Unique identifier")
    formula: str = constant(description="Molecular formula (e.g. H2O)")
    molecular_weight: float = constant(description="Molecular weight", unit="u")

    iupac_name: str = constant(default="")
    common_name: str = constant(default="")
    is_antimatter: bool = constant(default=False)

    atoms: list[Atom] = dataclass_field(default_factory=list)
    bonds: list[Bond] = dataclass_field(default_factory=list)

    _EV_TO_JOULES = 1.602176634e-19
    _C2 = (2.99792458e8) ** 2

    @property
    def stable_mass_kg(self) -> float:
        """Measured molecular rest mass from molecular_weight (mass spec / AME data).

        This is an independent measurement — NOT derived from constituent or
        binding.  The three-measure check  stable ≈ constituent − binding/c²
        must be verified externally, never enforced by definition.
        """
        return self.molecular_weight * CONSTANTS.u

    @property
    def constituent_mass_kg(self) -> float:
        return sum(a.stable_mass_kg for a in self.atoms)

    @property
    def binding_energy_joules(self) -> float:
        total_ev = sum(
            b.dissociation_energy
            for b in self.bonds
            if b.dissociation_energy is not None
        )
        return total_ev * self._EV_TO_JOULES

    @property
    def unique_molecules(self) -> list["Molecule"]:
        """Compatibility: material.unique_molecules delegates here."""
        return [self]

    @classmethod
    def create(
        cls,
        formula: str,
        atoms: list[Atom],
        bonds: list[Bond] | None = None,
        molecular_weight: float | None = None,
        **kwargs,
    ) -> Molecule:
        # molecular_weight should be the measured molecular mass (mass-spec / NIST).
        # If not provided, fall back to sum of standard atomic weights — this is
        # an approximation that conflates stable and constituent mass.  Callers
        # who care about three-measure closure must supply a measured value.
        mw = molecular_weight if molecular_weight is not None else sum(a.atomic_mass for a in atoms)
        return cls(
            id=str(uuid4()),
            formula=formula,
            molecular_weight=mw,
            atoms=atoms,
            bonds=bonds or [],
            **kwargs,
        )
