#!/usr/bin/env python3
"""Car Battery — Mass reconstruction from quarks to chemistry.

Loads the car_battery structure (Pb / H2SO4 / H2O) and runs both
the StoQ checksum and the full quark-chain reconstruction,
showing how mass accounting closes at every level.
"""

import quarksum


def fmt_kg(kg):
    if kg > 1.0:
        return f"{kg:.6f} kg"
    return f"{kg:.6e} kg"


def main():
    struct = quarksum.load_structure("car_battery")

    print(f"Structure : {struct.name}")
    print(f"Mass      : {fmt_kg(struct.resolved_mass_kg)}")
    print(f"Children  : {len(struct.children)}")
    for child in struct.children:
        formulas = [m.formula for m in child.molecules]
        print(f"  [{child.name}]  {', '.join(formulas)}  "
              f"(mass={child.resolved_mass_kg:.2e} kg)")
    print()

    print("— StoQ Checksum (atom level) —")
    cs = quarksum.stoq(struct)
    print(f"  Reconstructed : {fmt_kg(cs['reconstructed_mass_kg'])}")
    print(f"  Mass defect   : {fmt_kg(cs['mass_defect_kg'])} "
          f"({cs['mass_defect_percent']:.6f}%)")
    print()

    print("— Quark Chain Reconstruction —")
    qc = quarksum.quark_chain(struct)
    print(f"  Bare quark mass   : {fmt_kg(qc['bare_quark_mass_kg'])}")
    print(f"  Electron mass     : {fmt_kg(qc['electron_mass_kg'])}")
    print(f"  QCD binding       : {qc['qcd_binding_joules']:.6e} J")
    print(f"  Nuclear binding   : {qc['nuclear_binding_joules']:.6e} J")
    print(f"  Chemical binding  : {qc['chemical_binding_joules']:.6e} J")
    print(f"  Predicted mass    : {fmt_kg(qc['predicted_mass_kg'])}")
    print(f"  Defect            : {fmt_kg(qc['mass_defect_kg'])} "
          f"({qc['mass_defect_percent']:.6f}%)")
    print()
    print(qc.get("note", ""))
    print(qc.get("baryonic_note", ""))


if __name__ == "__main__":
    main()
