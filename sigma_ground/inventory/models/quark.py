"""Level 5 — Quarks and antiquarks inside nucleons.

Each quark carries electric charge, color charge, weak isospin, weak
hypercharge, chirality, and two distinct mass scales: the bare (current)
mass from the QCD Lagrangian and the constituent mass that includes
QCD dressing (~330 MeV for u/d).

See: https://en.wikipedia.org/wiki/Quark
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from sigma_ground.inventory.core.types import PhysicsObject, constant, variable


class QuarkFlavor(Enum):
    UP = "up"
    DOWN = "down"
    STRANGE = "strange"
    CHARM = "charm"
    BOTTOM = "bottom"
    TOP = "top"
    ANTI_UP = "anti-up"
    ANTI_DOWN = "anti-down"
    ANTI_STRANGE = "anti-strange"
    ANTI_CHARM = "anti-charm"
    ANTI_BOTTOM = "anti-bottom"
    ANTI_TOP = "anti-top"


@dataclass
class Quark(PhysicsObject):
    """A single quark (or antiquark) inside a nucleon."""

    id: str = constant(description="Unique identifier")
    flavor: str = constant(description="Quark flavor")
    charge: float = constant(description="Electric charge in units of e", unit="e")
    bare_mass_mev: float = constant(description="Current quark mass (MS-bar)", unit="MeV/c²")
    antiparticle: str = constant(description="Antiparticle name")

    spin: float = constant(description="Intrinsic spin", default=0.5)
    baryon_number: float = constant(description="Baryon number", default=1 / 3)
    generation: int = constant(description="Generation number", default=1)
    is_antimatter: bool = constant(description="Is an antiquark", default=False)

    weak_isospin_t3: float = constant(
        description="Weak isospin third component T₃", default=0.0,
    )
    weak_hypercharge: float = constant(
        description="Weak hypercharge Y_W (left-handed doublet)", default=0.0,
    )
    chirality: str = constant(
        description="Chirality (left-handed couples to W boson)", default="left",
    )
    constituent_mass_mev: float | None = constant(
        description="Constituent quark mass including QCD dressing",
        unit="MeV/c²", default=None,
    )
    strangeness: int = constant(
        description="Strangeness quantum number S", default=0,
    )
    isospin: float = constant(
        description="Strong isospin magnitude I", default=0.0,
    )
    isospin_3: float = constant(
        description="Strong isospin third component I₃", default=0.0,
    )
    parity: int = constant(
        description="Intrinsic parity P (+1 quarks, −1 antiquarks)", default=1,
    )

    color_charge: str = variable(
        description="Color charge state",
        options=["red", "green", "blue", "anti-red", "anti-green", "anti-blue"],
        default="red",
    )
    spin_projection: float = variable(
        description="Spin projection mₛ",
        quantity_type="angular_momentum",
        min_val=-0.5, max_val=0.5, step=1.0, default=0.5,
    )

    @classmethod
    def up(cls, color: str = "red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.UP.value,
            charge=2 / 3, bare_mass_mev=2.16, antiparticle="anti-up",
            generation=1, weak_isospin_t3=0.5, weak_hypercharge=1 / 3,
            constituent_mass_mev=336.0, isospin=0.5, isospin_3=0.5,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def down(cls, color: str = "green", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.DOWN.value,
            charge=-1 / 3, bare_mass_mev=4.67, antiparticle="anti-down",
            generation=1, weak_isospin_t3=-0.5, weak_hypercharge=1 / 3,
            constituent_mass_mev=340.0, isospin=0.5, isospin_3=-0.5,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def strange(cls, color: str = "red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.STRANGE.value,
            charge=-1 / 3, bare_mass_mev=93.4, antiparticle="anti-strange",
            generation=2, weak_isospin_t3=-0.5, weak_hypercharge=1 / 3,
            constituent_mass_mev=486.0, strangeness=-1,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def anti_up(cls, color: str = "anti-red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.ANTI_UP.value,
            charge=-2 / 3, bare_mass_mev=2.16, antiparticle="up",
            baryon_number=-1 / 3, is_antimatter=True,
            weak_isospin_t3=-0.5, weak_hypercharge=-1 / 3,
            constituent_mass_mev=336.0, isospin=0.5, isospin_3=-0.5,
            parity=-1, color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def anti_down(cls, color: str = "anti-green", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.ANTI_DOWN.value,
            charge=1 / 3, bare_mass_mev=4.67, antiparticle="down",
            baryon_number=-1 / 3, is_antimatter=True,
            weak_isospin_t3=0.5, weak_hypercharge=-1 / 3,
            constituent_mass_mev=340.0, isospin=0.5, isospin_3=0.5,
            parity=-1, color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def anti_strange(cls, color: str = "anti-red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.ANTI_STRANGE.value,
            charge=1 / 3, bare_mass_mev=93.4, antiparticle="strange",
            baryon_number=-1 / 3, generation=2, is_antimatter=True,
            weak_isospin_t3=0.5, weak_hypercharge=-1 / 3,
            constituent_mass_mev=486.0, strangeness=1, parity=-1,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def charm(cls, color: str = "red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.CHARM.value,
            charge=2 / 3, bare_mass_mev=1270.0, antiparticle="anti-charm",
            generation=2, weak_isospin_t3=0.5, weak_hypercharge=1 / 3,
            constituent_mass_mev=1550.0,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def bottom(cls, color: str = "red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.BOTTOM.value,
            charge=-1 / 3, bare_mass_mev=4180.0, antiparticle="anti-bottom",
            generation=3, weak_isospin_t3=-0.5, weak_hypercharge=1 / 3,
            constituent_mass_mev=4730.0,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def top(cls, color: str = "red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.TOP.value,
            charge=2 / 3, bare_mass_mev=172500.0, antiparticle="anti-top",
            generation=3, weak_isospin_t3=0.5, weak_hypercharge=1 / 3,
            constituent_mass_mev=172500.0,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def anti_charm(cls, color: str = "anti-red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.ANTI_CHARM.value,
            charge=-2 / 3, bare_mass_mev=1270.0, antiparticle="charm",
            baryon_number=-1 / 3, generation=2, is_antimatter=True,
            weak_isospin_t3=-0.5, weak_hypercharge=-1 / 3,
            constituent_mass_mev=1550.0, parity=-1,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def anti_bottom(cls, color: str = "anti-red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.ANTI_BOTTOM.value,
            charge=1 / 3, bare_mass_mev=4180.0, antiparticle="bottom",
            baryon_number=-1 / 3, generation=3, is_antimatter=True,
            weak_isospin_t3=0.5, weak_hypercharge=-1 / 3,
            constituent_mass_mev=4730.0, parity=-1,
            color_charge=color, spin_projection=spin_proj,
        )

    @classmethod
    def anti_top(cls, color: str = "anti-red", spin_proj: float = 0.5) -> Quark:
        return cls(
            id=str(uuid4()), flavor=QuarkFlavor.ANTI_TOP.value,
            charge=-2 / 3, bare_mass_mev=172500.0, antiparticle="top",
            baryon_number=-1 / 3, generation=3, is_antimatter=True,
            weak_isospin_t3=-0.5, weak_hypercharge=-1 / 3,
            constituent_mass_mev=172500.0, parity=-1,
            color_charge=color, spin_projection=spin_proj,
        )
