#!/usr/bin/env python3
"""Solar System Cross-Section — Full information dump.

Loads the solar_system_xsection structure and combines every API call
into one comprehensive report: inventory, checksum, quark chain,
behaviors, and environment application.
"""

import json
import quarksum


def divider(title):
    print(f"\n{'#' * 64}")
    print(f"#  {title}")
    print(f"{'#' * 64}\n")


def pretty(data, max_lines=40):
    text = json.dumps(data, indent=2, default=str)
    lines = text.splitlines()
    for line in lines[:max_lines]:
        print(f"  {line}")
    if len(lines) > max_lines:
        print(f"  ... ({len(lines) - max_lines} more lines)")


def main():
    struct = quarksum.load_structure("solar_system_xsection")

    divider(f"{struct.name}  —  {struct.resolved_mass_kg:.3e} kg")

    print("Children:")
    for child in struct.children:
        formulas = [m.formula for m in child.molecules]
        print(f"  {child.name:40s}  mass={child.resolved_mass_kg:.3e}  "
              f"{', '.join(formulas)}")

    # 1. Particle inventory
    divider("Particle Inventory")
    inv = quarksum.inventory(struct)
    for key, val in inv.items():
        if isinstance(val, (int, float)):
            if isinstance(val, int) or val == int(val):
                print(f"  {key:35s} {int(val):>25,}")
            else:
                print(f"  {key:35s} {val:>25.6e}")
        else:
            print(f"  {key:35s} {val}")

    # 2. StoQ checksum
    divider("StoQ Mass Checksum")
    cs = quarksum.stoq(struct)
    pretty(cs)

    # 3. Quark chain
    divider("Quark Chain Reconstruction")
    qc = quarksum.quark_chain(struct)
    pretty(qc)

    # 4. Behaviors — pick the first H2 molecule from the solar core
    h2_child = next(
        child for child in struct.children
        if any(m.formula == "H2" for m in child.molecules)
    )
    h2 = next(m for m in h2_child.molecules if m.formula == "H2")

    divider(f"Behaviors: {h2.formula} from [{h2_child.name}]")
    pretty(quarksum.behaviors(h2))

    # 5. Apply — solar core conditions (~15 million K)
    divider(f"Apply: {h2.formula} + 15 million K temperature delta")
    result = quarksum.apply(h2, {"temperature_k": 15_000_000}, mode="delta")
    for entry in result.get("applied", []):
        print(f"  [molecule] {entry['key']}: {entry['consequence']}")

    for atom in h2.atoms:
        info = quarksum.behaviors(atom)
        print(f"  [{atom.symbol}] Z={atom.atomic_number}  "
              f"operable: {list(info.get('operable', {}).keys())}")

    divider("Done")


if __name__ == "__main__":
    main()
