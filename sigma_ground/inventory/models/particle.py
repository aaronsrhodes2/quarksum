"""Level 4 — Subatomic particles.

Each particle exposes its physical constants and tunable quantum numbers.
Nucleons (protons and neutrons) contain quarks as children.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from uuid import uuid4

from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.core.types import PhysicsObject, constant, variable
from sigma_ground.inventory.models.quark import Quark
from sigma_ground.inventory.models.gluon import Gluon


class ParticleType(Enum):
    ELECTRON = "electron"
    PROTON = "proton"
    NEUTRON = "neutron"
    POSITRON = "positron"
    ANTIPROTON = "antiproton"
    ANTINEUTRON = "antineutron"
    MUON = "muon"
    TAU = "tau"
    ELECTRON_NEUTRINO = "electron_neutrino"
    MUON_NEUTRINO = "muon_neutrino"
    TAU_NEUTRINO = "tau_neutrino"


@dataclass
class Particle(PhysicsObject):
    """A subatomic particle within an atom."""

    id: str = constant(description="Unique identifier")
    particle_type: str = constant(description="Particle type")
    symbol: str = constant(description="Symbol")
    rest_mass_kg: float = constant(description="Rest mass", unit="kg")
    charge_e: float = constant(description="Electric charge in units of e", unit="e")
    magnetic_moment: float = constant(description="Magnetic moment", unit="J/T")
    antiparticle: str = constant(description="Antiparticle name")

    spin: float = constant(description="Intrinsic spin quantum number", default=0.5)
    lepton_number: int = constant(description="Lepton number", default=0)
    baryon_number: float = constant(description="Baryon number", default=0.0)
    is_antimatter: bool = constant(description="Is an antiparticle", default=False)

    quarks: list[Quark] = dataclass_field(default_factory=list)
    gluons: list[Gluon] = dataclass_field(default_factory=list)
    sea_quarks: list[Quark] = dataclass_field(default_factory=list)

    energy_level: float = variable(
        description="Energy relative to ground state",
        unit="eV", quantity_type="energy_eV",
        min_val=0.0, default=0.0,
    )
    spin_projection: float = variable(
        description="Spin projection mₛ",
        quantity_type="angular_momentum",
        min_val=-0.5, max_val=0.5, step=1.0, default=0.5,
    )

    _C2 = (2.99792458e8) ** 2
    _MEV_TO_KG = 1.602176634e-13 / _C2

    @property
    def stable_mass_kg(self) -> float:
        return self.rest_mass_kg

    @property
    def constituent_mass_kg(self) -> float:
        if not self.quarks:
            return self.rest_mass_kg
        return sum(q.bare_mass_mev for q in self.quarks) * self._MEV_TO_KG

    @property
    def binding_energy_joules(self) -> float:
        return (self.stable_mass_kg - self.constituent_mass_kg) * self._C2


@dataclass
class Electron(Particle):
    """An electron with orbital quantum numbers."""

    principal_n: int = variable(
        description="Principal quantum number n",
        quantity_type="dimensionless",
        min_val=1, max_val=7, step=1, default=1,
    )
    angular_l: int = variable(
        description="Angular momentum quantum number l",
        quantity_type="dimensionless",
        min_val=0, max_val=6, step=1, default=0,
    )
    magnetic_ml: int = variable(
        description="Magnetic quantum number mₗ",
        quantity_type="dimensionless",
        min_val=-6, max_val=6, step=1, default=0,
    )
    orbital_name: str = variable(
        description="Orbital assignment (e.g. 1s, 2p)",
        default="1s",
    )

    @classmethod
    def create(
        cls, n: int = 1, l: int = 0, ml: int = 0,
        ms: float = 0.5, orbital: str = "",
    ) -> Electron:
        l_labels = "spdfghij"
        if not orbital:
            orbital = f"{n}{l_labels[l] if l < len(l_labels) else '?'}"
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.ELECTRON.value,
            symbol="e⁻",
            rest_mass_kg=CONSTANTS.m_e,
            charge_e=-1.0,
            magnetic_moment=-9.2847647043e-24,
            antiparticle="positron",
            lepton_number=1,
            quarks=[],
            principal_n=n, angular_l=l, magnetic_ml=ml,
            spin_projection=ms, orbital_name=orbital,
        )


@dataclass
class Proton(Particle):
    """A proton containing three quarks (uud)."""

    charge_radius_fm: float = constant(
        description="RMS charge radius (PRad 2019)", unit="fm", default=0.8414,
    )
    qcd_binding_energy_mev: float = constant(
        description="QCD confinement energy: m_p − (2m_u + m_d)",
        unit="MeV", default=929.282088,
    )

    @classmethod
    def create(cls) -> Proton:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.PROTON.value,
            symbol="p⁺",
            rest_mass_kg=CONSTANTS.m_p,
            charge_e=1.0,
            magnetic_moment=1.41060674333e-26,
            baryon_number=1.0,
            antiparticle="antiproton",
            quarks=[
                Quark.up(color="red"),
                Quark.up(color="blue"),
                Quark.down(color="green"),
            ],
            gluons=Gluon.create_octet(),
            sea_quarks=_proton_sea_quarks(),
        )


@dataclass
class Neutron(Particle):
    """A neutron containing three quarks (udd)."""

    charge_radius_fm: float = constant(
        description="RMS charge radius", unit="fm", default=0.0,
    )
    qcd_binding_energy_mev: float = constant(
        description="QCD confinement energy: m_n − (m_u + 2m_d)",
        unit="MeV", default=928.065421,
    )

    @classmethod
    def create(cls) -> Neutron:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.NEUTRON.value,
            symbol="n⁰",
            rest_mass_kg=CONSTANTS.m_n,
            charge_e=0.0,
            magnetic_moment=-9.6623651e-27,
            baryon_number=1.0,
            antiparticle="antineutron",
            quarks=[
                Quark.up(color="red"),
                Quark.down(color="blue"),
                Quark.down(color="green"),
            ],
            gluons=Gluon.create_octet(),
            sea_quarks=_neutron_sea_quarks(),
        )


@dataclass
class Positron(Particle):
    """A positron — the electron's antiparticle."""

    @classmethod
    def create(cls) -> Positron:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.POSITRON.value,
            symbol="e⁺",
            rest_mass_kg=CONSTANTS.m_e,
            charge_e=1.0,
            magnetic_moment=9.2847647043e-24,
            antiparticle="electron",
            lepton_number=-1,
            is_antimatter=True,
        )


@dataclass
class Antiproton(Particle):
    """An antiproton containing three antiquarks (ūūd̄)."""

    @classmethod
    def create(cls) -> Antiproton:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.ANTIPROTON.value,
            symbol="p̄",
            rest_mass_kg=CONSTANTS.m_p,
            charge_e=-1.0,
            magnetic_moment=-1.41060674333e-26,
            baryon_number=-1.0,
            antiparticle="proton",
            is_antimatter=True,
            quarks=[
                Quark.anti_up(color="anti-red"),
                Quark.anti_up(color="anti-blue"),
                Quark.anti_down(color="anti-green"),
            ],
            gluons=Gluon.create_octet(),
        )


@dataclass
class Antineutron(Particle):
    """An antineutron containing three antiquarks (ūd̄d̄)."""

    @classmethod
    def create(cls) -> Antineutron:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.ANTINEUTRON.value,
            symbol="n̄",
            rest_mass_kg=CONSTANTS.m_n,
            charge_e=0.0,
            magnetic_moment=9.6623651e-27,
            baryon_number=-1.0,
            antiparticle="neutron",
            is_antimatter=True,
            quarks=[
                Quark.anti_up(color="anti-red"),
                Quark.anti_down(color="anti-blue"),
                Quark.anti_down(color="anti-green"),
            ],
            gluons=Gluon.create_octet(),
        )


@dataclass
class Muon(Particle):
    """A muon — second-generation charged lepton (unstable, tau = 2.2 us)."""

    lifetime_s: float = constant(
        description="Mean lifetime", unit="s", default=2.1969811e-6,
    )

    @classmethod
    def create(cls) -> Muon:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.MUON.value,
            symbol="μ⁻",
            rest_mass_kg=CONSTANTS.m_muon,
            charge_e=-1.0,
            magnetic_moment=-4.49044830e-26,
            antiparticle="antimuon",
            lepton_number=1,
        )


@dataclass
class Tau(Particle):
    """A tau — third-generation charged lepton (unstable, tau = 2.9e-13 s)."""

    lifetime_s: float = constant(
        description="Mean lifetime", unit="s", default=2.903e-13,
    )

    @classmethod
    def create(cls) -> Tau:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.TAU.value,
            symbol="τ⁻",
            rest_mass_kg=CONSTANTS.m_tau,
            charge_e=-1.0,
            magnetic_moment=0.0,
            antiparticle="antitau",
            lepton_number=1,
        )


@dataclass
class ElectronNeutrino(Particle):
    """An electron neutrino — nearly massless, weakly interacting."""

    @classmethod
    def create(cls) -> ElectronNeutrino:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.ELECTRON_NEUTRINO.value,
            symbol="νₑ",
            rest_mass_kg=0.0,
            charge_e=0.0,
            magnetic_moment=0.0,
            antiparticle="anti-electron-neutrino",
            lepton_number=1,
        )


@dataclass
class MuonNeutrino(Particle):
    """A muon neutrino — nearly massless, weakly interacting."""

    @classmethod
    def create(cls) -> MuonNeutrino:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.MUON_NEUTRINO.value,
            symbol="ν_μ",
            rest_mass_kg=0.0,
            charge_e=0.0,
            magnetic_moment=0.0,
            antiparticle="anti-muon-neutrino",
            lepton_number=1,
        )


@dataclass
class TauNeutrino(Particle):
    """A tau neutrino — nearly massless, weakly interacting."""

    @classmethod
    def create(cls) -> TauNeutrino:
        return cls(
            id=str(uuid4()),
            particle_type=ParticleType.TAU_NEUTRINO.value,
            symbol="ν_τ",
            rest_mass_kg=0.0,
            charge_e=0.0,
            magnetic_moment=0.0,
            antiparticle="anti-tau-neutrino",
            lepton_number=1,
        )


def _proton_sea_quarks() -> list[Quark]:
    """Virtual qq̄ sea inside a proton: ūu + d̄d + s̄s."""
    return [
        Quark.up(color="red", spin_proj=0.5),
        Quark.anti_up(color="anti-red", spin_proj=-0.5),
        Quark.down(color="green", spin_proj=0.5),
        Quark.anti_down(color="anti-green", spin_proj=-0.5),
        Quark.strange(color="blue", spin_proj=0.5),
        Quark.anti_strange(color="anti-blue", spin_proj=-0.5),
    ]


def _neutron_sea_quarks() -> list[Quark]:
    """Virtual qq̄ sea inside a neutron: ūu + d̄d + s̄s."""
    return [
        Quark.up(color="red", spin_proj=0.5),
        Quark.anti_up(color="anti-red", spin_proj=-0.5),
        Quark.down(color="green", spin_proj=0.5),
        Quark.anti_down(color="anti-green", spin_proj=-0.5),
        Quark.strange(color="blue", spin_proj=0.5),
        Quark.anti_strange(color="anti-blue", spin_proj=-0.5),
    ]
