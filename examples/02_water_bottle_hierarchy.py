#!/usr/bin/env python3
"""Water Bottle — Walk the hierarchy from quark to molecule.

Loads the water_bottle structure and inspects behaviors at every
level of the object graph: quark -> particle -> atom -> molecule.
"""

import json
import quarksum


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def pretty(data, max_lines=30):
    text = json.dumps(data, indent=2, default=str)
    lines = text.splitlines()
    for line in lines[:max_lines]:
        print(f"    {line}")
    if len(lines) > max_lines:
        print(f"    ... ({len(lines) - max_lines} more lines)")


def main():
    struct = quarksum.load_structure("water_bottle")
    print(f"Structure: {struct.name}  ({struct.resolved_mass_kg} kg)")

    water_child = next(
        child for child in struct.children
        if any(m.formula == "H2O" for m in child.molecules)
    )
    water = next(
        m for m in water_child.molecules if m.formula == "H2O"
    )
    oxygen = next(a for a in water.atoms if a.symbol == "O")
    proton = oxygen.protons[0]
    quark = proton.quarks[0]

    section(f"Quark: {quark.flavor} (color={quark.color_charge})")
    pretty(quarksum.behaviors(quark))

    section("Particle: proton")
    pretty(quarksum.behaviors(proton))

    section(f"Atom: {oxygen.symbol} (Z={oxygen.atomic_number})")
    pretty(quarksum.behaviors(oxygen))

    section(f"Molecule: {water.formula}")
    pretty(quarksum.behaviors(water))


if __name__ == "__main__":
    main()
