"""Level 5 — Gluons: the 8 color-octet gauge bosons of QCD.

Gluons mediate the strong interaction between quarks. They carry both color
and anticolor charge, transforming as the adjoint (8-dimensional) representation
of SU(3). Unlike photons in QED, gluons participate in the strong interaction
themselves. The nine color-anticolor combinations reduce to eight because the
color-neutral combination is excluded.

See: https://en.wikipedia.org/wiki/Gluon
See: https://en.wikipedia.org/wiki/Quantum_chromodynamics
See: https://en.wikipedia.org/wiki/Color_charge
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar
from uuid import uuid4

from sigma_ground.inventory.core.types import PhysicsObject, constant, variable


@dataclass
class Gluon(PhysicsObject):
    """A gluon: massless spin-1 gauge boson carrying color and anticolor charge."""

    # SU(3) octet: 6 off-diagonal + 2 diagonal states
    # 1–6 = r-b̄, r-ḡ, b-r̄, b-ḡ, g-r̄, g-b̄; 7–8 = diagonal
    SU3_OCTET: ClassVar[list[tuple[str, str]]] = [
        ("red", "anti-blue"),           # 1. r-b̄
        ("red", "anti-green"),          # 2. r-ḡ
        ("blue", "anti-red"),           # 3. b-r̄
        ("blue", "anti-green"),         # 4. b-ḡ
        ("green", "anti-red"),          # 5. g-r̄
        ("green", "anti-blue"),         # 6. g-b̄
        ("(rr̄−bb̄)/√2", "diagonal_1"),  # 7. (rr̄−bb̄)/√2
        ("(rr̄+bb̄−2gḡ)/√6", "diagonal_2"),  # 8. (rr̄+bb̄−2gḡ)/√6
    ]

    # Required constants (no defaults — must come first)
    id: str = constant(description="Unique identifier")
    color_charge: str = constant(description="Color charge (e.g. red)")
    anti_color_charge: str = constant(description="Anticolor charge (e.g. anti-blue)")

    # Constants with defaults
    symbol: str = constant(description="Particle symbol", default="g")
    rest_mass_kg: float = constant(description="Rest mass", unit="kg", default=0.0)
    spin: float = constant(description="Intrinsic spin", default=1.0)
    charge_e: float = constant(description="Electric charge in units of e", unit="e", default=0.0)
    is_fermion: bool = constant(description="Is a fermion", default=False)
    is_boson: bool = constant(description="Is a boson", default=True)

    # Variable
    spin_projection: float = variable(
        description="Spin projection mₛ",
        quantity_type="angular_momentum",
        min_val=-1.0, max_val=1.0, step=1.0, default=1.0,
    )

    @classmethod
    def create(cls, color: str, anti_color: str, spin_proj: float = 1.0) -> Gluon:
        """Create a gluon with given color and anticolor charges."""
        return cls(
            id=str(uuid4()),
            color_charge=color,
            anti_color_charge=anti_color,
            spin_projection=spin_proj,
        )

    @classmethod
    def create_octet(cls, spin_proj: float = 1.0) -> list[Gluon]:
        """Return a list of the 8 gluon states of the SU(3) color octet."""
        return [
            cls.create(color=c, anti_color=a, spin_proj=spin_proj)
            for c, a in cls.SU3_OCTET
        ]
