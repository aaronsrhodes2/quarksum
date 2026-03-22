#!/usr/bin/env python3
"""Gold Ring — Particle inventory across precious metals.

Loads the gold_ring structure (Au/Ag/Cu alloy with NaCl sweat residue)
and prints the full Standard Model particle census.
"""

import quarksum


def main():
    struct = quarksum.load_structure("gold_ring")

    print(f"Structure : {struct.name}")
    print(f"Mass      : {struct.resolved_mass_kg:.4f} kg")
    print(f"Children  : {len(struct.children)}")
    print()

    for child in struct.children:
        formulas = [m.formula for m in child.molecules]
        print(f"  [{child.name}]  {', '.join(formulas)}")
    print()

    inv = quarksum.inventory(struct)

    print("— Fundamental Fermions —")
    for key in ("protons", "neutrons", "electrons",
                "up_quarks", "down_quarks", "gluons"):
        count = inv.get(key, 0)
        mass = inv.get(f"{key}_mass_kg")
        pct = inv.get(f"{key}_mass_percent")
        line = f"  {key:20s} {count:>20,}"
        if mass is not None:
            line += f"   {mass:.6e} kg"
        if pct is not None:
            line += f"   ({pct:.4f}%)"
        print(line)

    print()
    print(f"  Total fermions       {inv['total_fundamental_fermions']:>20,}")
    print(f"  Total gauge bosons   {inv['total_gauge_bosons']:>20,}")
    print(f"  Total all particles  {inv['total_all_particles']:>20,}")
    print()

    print("— Composite —")
    print(f"  Unique atoms         {inv['atoms']:>20,}")
    print(f"  Unique molecules     {inv['molecules']:>20,}")
    print(f"  Bonds (total)        {inv['bonds_total']:>20,}")
    print()
    print(inv.get("standard_model_note", ""))


if __name__ == "__main__":
    main()
