#!/usr/bin/env python3
"""Earth's Layers — Apply environment deltas to atoms and molecules.

Loads the earths_layers structure and subjects entities from different
shells to various stimuli: temperature, pressure, electric and
magnetic fields, demonstrating the universal apply() API.
"""

import quarksum


def main():
    struct = quarksum.load_structure("earths_layers")
    print(f"Structure: {struct.name}  (mass={struct.resolved_mass_kg:.3e} kg)")
    print(f"Layers: {len(struct.children)}")
    for child in struct.children:
        formulas = [m.formula for m in child.molecules]
        print(f"  [{child.name}]  {', '.join(formulas)}")
    print()

    # Inner core — Fe at extreme temperature delta
    core_child = next(
        child for child in struct.children
        if "iron" in child.name.lower()
    )
    iron_mol = next(
        m for m in core_child.molecules if m.formula == "Fe"
    )
    iron_atom = iron_mol.atoms[0]

    print("— Iron atom in inner core: +5000 K temperature delta —")
    result = quarksum.apply(iron_atom, {"temperature_k": 5000}, mode="delta")
    for entry in result.get("applied", []):
        print(f"  {entry['key']}: {entry['consequence']}")
    print()

    # Crust — SiO2 under electric field
    crust_child = next(
        child for child in struct.children
        if "silicon" in child.name.lower()
              or "aluminum" in child.name.lower()
    )
    sio2 = next(
        m for m in crust_child.molecules if m.formula == "SiO2"
    )

    print("— SiO2 in crust: electric field 1e6 V/m (absolute update) —")
    result = quarksum.apply(
        sio2, {"electric_field_vm": 1e6}, mode="update"
    )
    for entry in result.get("applied", []):
        print(f"  {entry['key']}: {entry['consequence']}")
    print()

    # Cascade: apply magnetic field to the molecule; cascade mutates atoms in-place
    print("— SiO2 cascade: magnetic field delta +2 T —")
    result = quarksum.apply(sio2, {"magnetic_field_t": 2.0}, mode="delta")
    for entry in result.get("applied", []):
        print(f"  [molecule] {entry['key']}: {entry['consequence']}")

    for atom in sio2.atoms:
        info = quarksum.behaviors(atom)
        print(f"    [{atom.symbol}] operable keys: {list(info.get('operable', {}).keys())}")
    print()

    # Quark-level: hit a quark with energy
    print("— Iron quark: energy delta +0.5 GeV —")
    proton = iron_atom.protons[0]
    quark = proton.quarks[0]
    result = quarksum.apply(quark, {"energy_gev": 0.5}, mode="delta")
    for entry in result.get("applied", []):
        print(f"  {entry['key']}: {entry['consequence']}")


if __name__ == "__main__":
    main()
