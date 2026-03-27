"""Level 3 — Atoms.

Each atom carries full element data as constants, isotope-dependent
properties, and variable attributes. Contains electrons, protons,
and neutrons as children.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dataclass_field
from uuid import uuid4

from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.core.types import PhysicsObject, constant, variable
from sigma_ground.inventory.models.particle import Electron, Neutron, Proton


@dataclass
class Atom(PhysicsObject):
    """An atom with full element data and subatomic particle children."""

    id: str = constant(description="Unique identifier")
    symbol: str = constant(description="Element symbol")
    name: str = constant(description="Element name")
    atomic_number: int = constant(description="Atomic number (Z)")
    atomic_mass: float = constant(description="Standard atomic mass", unit="u")
    electron_configuration: str = constant(description="Ground-state electron configuration")
    element_category: str = constant(description="Element category")
    period: int = constant(description="Period in the periodic table")
    block: str = constant(description="Block (s, p, d, f)")
    mass_number: int = constant(description="Mass number A (protons + neutrons)")
    neutron_count: int = constant(description="Number of neutrons N")

    electronegativity: float | None = constant(default=None)
    ionization_energy_1: float | None = constant(default=None)
    ionization_energy_2: float | None = constant(default=None)
    ionization_energy_3: float | None = constant(default=None)
    ionization_energy_4: float | None = constant(default=None)
    ionization_energy_5: float | None = constant(default=None)
    ionization_energy_6: float | None = constant(default=None)
    electron_affinity_ev: float | None = constant(default=None)
    atomic_radius: float | None = constant(default=None)
    van_der_waals_radius: float | None = constant(default=None)
    group: int | None = constant(default=None)
    is_antimatter: bool = constant(default=False)

    nuclear_spin: float | None = constant(default=None)
    nuclear_parity: str | None = constant(default=None)
    nuclear_magnetic_moment: float | None = constant(default=None)
    nuclear_radius_fm: float | None = constant(default=None)
    nuclear_binding_energy_mev: float | None = constant(default=None)
    nuclear_quadrupole_moment: float | None = constant(default=None)
    half_life_s: float | None = constant(default=None)
    decay_mode: str | None = constant(default=None)
    is_stable: bool = constant(default=True)
    measured_atomic_mass_u: float | None = constant(default=None)

    protons: list[Proton] = dataclass_field(default_factory=list)
    neutrons: list[Neutron] = dataclass_field(default_factory=list)
    electrons: list[Electron] = dataclass_field(default_factory=list)

    charge_state: int = variable(
        description="Net charge (ionization level)",
        quantity_type="charge", min_val=-4, max_val=8, step=1, default=0,
    )
    oxidation_state: int = variable(default=0)
    spin_state: float = variable(default=0.0)
    position_x: float = variable(default=0.0)
    position_y: float = variable(default=0.0)
    position_z: float = variable(default=0.0)
    isotope_label: str = variable(default="")
    effective_nuclear_charge: float | None = variable(default=None)

    _C2 = (2.99792458e8) ** 2
    _MEV_TO_JOULES = 1.602176634e-13

    @property
    def stable_mass_kg(self) -> float:
        if self.measured_atomic_mass_u is not None:
            return self.measured_atomic_mass_u * CONSTANTS.u
        return self.atomic_mass * CONSTANTS.u

    @property
    def constituent_mass_kg(self) -> float:
        return (
            len(self.protons) * CONSTANTS.m_p
            + len(self.neutrons) * CONSTANTS.m_n
            + len(self.electrons) * CONSTANTS.m_e
        )

    @property
    def binding_energy_joules(self) -> float:
        if self.nuclear_binding_energy_mev is not None:
            return self.nuclear_binding_energy_mev * self._MEV_TO_JOULES
        return (self.constituent_mass_kg - self.stable_mass_kg) * self._C2

    @classmethod
    def create(
        cls,
        element_data: dict,
        isotope_mass_number: int | None = None,
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Atom:
        z = element_data["atomic_number"]
        n_neutrons = (
            (isotope_mass_number - z) if isotope_mass_number
            else element_data.get("neutron_count", round(element_data["atomic_mass"]) - z)
        )
        mass_num = isotope_mass_number or (z + n_neutrons)

        protons = [Proton.create() for _ in range(z)]
        neutrons = [Neutron.create() for _ in range(n_neutrons)]
        electrons = _build_ground_state_electrons(
            element_data.get("electron_configuration", "")
        )

        log = logging.getLogger(__name__)
        sym = element_data["symbol"]
        if "element_category" not in element_data:
            log.warning(f"Local library gap: element_category for {sym} not yet catalogued")
        if "period" not in element_data:
            log.warning(f"Local library gap: period for {sym} not yet catalogued")

        nuc = _lookup_isotope(z, mass_num)

        nuc_spin: float | None = None
        nuc_parity: str | None = None
        nuc_mag: float | None = None
        nuc_quad: float | None = None
        nuc_be_mev: float | None = None
        half_life: float | None = None
        decay: str | None = None
        stable = True
        measured_mass: float | None = None

        if nuc:
            spin_str = nuc.get("nuclear_spin")
            if spin_str is not None:
                nuc_spin = _parse_spin(spin_str)
            nuc_parity = nuc.get("nuclear_parity")
            nuc_mag = nuc.get("nuclear_magnetic_moment_mu_n")
            nuc_quad = nuc.get("nuclear_quadrupole_moment_b")
            be_per_a = nuc.get("binding_energy_per_nucleon_kev")
            if be_per_a is not None and mass_num > 0:
                nuc_be_mev = be_per_a * mass_num / 1000.0
            half_life = nuc.get("half_life_s")
            decay = nuc.get("decay_mode", "stable")
            stable = nuc.get("is_stable", True)
            measured_mass = nuc.get("atomic_mass_u")

        r0 = 1.2
        nuc_radius = r0 * (mass_num ** (1.0 / 3.0)) if mass_num > 0 else None

        return cls(
            id=str(uuid4()),
            symbol=sym,
            name=element_data["name"],
            atomic_number=z,
            atomic_mass=element_data["atomic_mass"],
            electron_configuration=element_data.get("electron_configuration", ""),
            electronegativity=element_data.get("electronegativity"),
            ionization_energy_1=element_data.get("ionization_energy_1"),
            ionization_energy_2=element_data.get("ionization_energy_2"),
            ionization_energy_3=element_data.get("ionization_energy_3"),
            ionization_energy_4=element_data.get("ionization_energy_4"),
            ionization_energy_5=element_data.get("ionization_energy_5"),
            ionization_energy_6=element_data.get("ionization_energy_6"),
            electron_affinity_ev=element_data.get("electron_affinity_ev"),
            atomic_radius=element_data.get("atomic_radius"),
            van_der_waals_radius=element_data.get("van_der_waals_radius"),
            element_category=element_data.get("element_category", "unknown"),
            period=element_data.get("period", 0),
            group=element_data.get("group"),
            block=element_data.get("block", "s"),
            mass_number=mass_num,
            neutron_count=n_neutrons,
            nuclear_spin=nuc_spin,
            nuclear_parity=nuc_parity,
            nuclear_magnetic_moment=nuc_mag,
            nuclear_radius_fm=nuc_radius,
            nuclear_binding_energy_mev=nuc_be_mev,
            nuclear_quadrupole_moment=nuc_quad,
            half_life_s=half_life,
            decay_mode=decay,
            is_stable=stable,
            measured_atomic_mass_u=measured_mass,
            protons=protons,
            neutrons=neutrons,
            electrons=electrons,
            position_x=position[0],
            position_y=position[1],
            position_z=position[2],
            isotope_label=f"{mass_num}{sym}",
        )


def _lookup_isotope(z: int, a: int) -> dict | None:
    try:
        from sigma_ground.inventory.data.loader import IsotopeDB
        return IsotopeDB.get().by_z_and_a(z, a)
    except Exception:
        return None


def _parse_spin(spin_str: str) -> float:
    spin_str = spin_str.strip()
    if "/" in spin_str:
        num, den = spin_str.split("/")
        return float(num) / float(den)
    return float(spin_str)


def _build_ground_state_electrons(config_str: str) -> list[Electron]:
    if not config_str:
        return []

    electrons: list[Electron] = []
    l_map = {"s": 0, "p": 1, "d": 2, "f": 3}
    tokens = config_str.replace("[", "").replace("]", "").strip().split()

    for token in tokens:
        if len(token) < 2:
            continue
        try:
            n = int(token[0])
            l_char = token[1]
            count = int(token[2:]) if len(token) > 2 else 1
        except (ValueError, IndexError):
            continue

        l_val = l_map.get(l_char, 0)
        ml_values = list(range(-l_val, l_val + 1))

        placed = 0
        for ml in ml_values:
            for ms in (0.5, -0.5):
                if placed >= count:
                    break
                electrons.append(Electron.create(n=n, l=l_val, ml=ml, ms=ms))
                placed += 1
            if placed >= count:
                break

    return electrons
