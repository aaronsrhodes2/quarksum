#!/usr/bin/env python3
"""
Mechanical Test Samples — Generate elastic properties for all materials
and feed through Nagatha's pipeline.

"Every material knows how stiff it is.
 Now we can ask it to prove it."
"""

import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
HARVEST_DIR = os.path.dirname(HERE)
PROJECT_ROOT = os.path.join(HARVEST_DIR, '..', '..')

sys.path.insert(0, PROJECT_ROOT)

from local_library.interface.surface import MATERIALS
from local_library.interface.mechanical import (
    bulk_modulus, youngs_modulus, shear_modulus,
    theoretical_shear_strength, material_mechanical_properties,
    MECHANICAL_DATA,
)


# ── Experimental reference values (MEASURED, GPa) ────────────────
# Source: ASM Handbook, CRC Handbook
EXPERIMENTAL = {
    'iron':     {'K': 170, 'E': 211, 'G': 82},
    'copper':   {'K': 140, 'E': 130, 'G': 48},
    'aluminum': {'K': 76,  'E': 70,  'G': 26},
    'gold':     {'K': 180, 'E': 79,  'G': 27},
    'silicon':  {'K': 98,  'E': 130, 'G': 52},
    'tungsten': {'K': 310, 'E': 411, 'G': 161},
    'nickel':   {'K': 180, 'E': 200, 'G': 76},
    'titanium': {'K': 110, 'E': 116, 'G': 44},
}


def generate_mechanical_report():
    """Generate mechanical properties and compare to experiment."""
    results = {}

    print(f"  {'Material':>12s}  {'K_calc':>7s} {'K_exp':>6s} {'err%':>5s}"
          f"  {'E_calc':>7s} {'E_exp':>6s} {'err%':>5s}"
          f"  {'G_calc':>7s} {'G_exp':>6s} {'err%':>5s}"
          f"  {'τ_th':>6s}")
    print(f"  {'':>12s}  {'(GPa)':>7s} {'(GPa)':>6s} {'':>5s}"
          f"  {'(GPa)':>7s} {'(GPa)':>6s} {'':>5s}"
          f"  {'(GPa)':>7s} {'(GPa)':>6s} {'':>5s}"
          f"  {'(GPa)':>6s}")
    print("  " + "─" * 95)

    for mat in sorted(MATERIALS.keys()):
        K = bulk_modulus(mat) / 1e9
        E = youngs_modulus(mat) / 1e9
        G = shear_modulus(mat) / 1e9
        tau = theoretical_shear_strength(mat) / 1e9

        exp = EXPERIMENTAL.get(mat, {})
        K_exp = exp.get('K', 0)
        E_exp = exp.get('E', 0)
        G_exp = exp.get('G', 0)

        K_err = ((K - K_exp) / K_exp * 100) if K_exp else 0
        E_err = ((E - E_exp) / E_exp * 100) if E_exp else 0
        G_err = ((G - G_exp) / G_exp * 100) if G_exp else 0

        print(f"  {mat:>12s}  {K:7.1f} {K_exp:6.0f} {K_err:+5.0f}%"
              f"  {E:7.1f} {E_exp:6.0f} {E_err:+5.0f}%"
              f"  {G:7.1f} {G_exp:6.0f} {G_err:+5.0f}%"
              f"  {tau:6.1f}")

        results[mat] = {
            'bulk_modulus_gpa': round(K, 1),
            'youngs_modulus_gpa': round(E, 1),
            'shear_modulus_gpa': round(G, 1),
            'theoretical_shear_strength_gpa': round(tau, 1),
            'poisson_ratio': MECHANICAL_DATA[mat]['poisson_ratio'],
            'experimental_K_gpa': K_exp,
            'experimental_E_gpa': E_exp,
            'experimental_G_gpa': G_exp,
            'K_error_pct': round(K_err, 1),
            'E_error_pct': round(E_err, 1),
            'G_error_pct': round(G_err, 1),
        }

    return results


def enrich_nagatha(results):
    """Write mechanical data to Nagatha feed."""
    out_dir = os.path.join(HERE, 'mechanical_enriched')
    os.makedirs(out_dir, exist_ok=True)

    summary = {
        'description': 'Mechanical properties from bond physics',
        'origin': ('Bulk modulus from harmonic approximation (E_coh × n × f). '
                  'E, G from isotropic elasticity. τ_th from Frenkel.'),
        'materials': results,
    }

    path = os.path.join(out_dir, 'mechanical_properties.json')
    with open(path, 'w') as f:
        json.dump(summary, f, indent=2)
    return path


def main():
    print("=" * 60)
    print("  MECHANICAL TEST SAMPLES — Nagatha Feed")
    print("=" * 60)
    print()

    results = generate_mechanical_report()
    print()

    # Statistics
    errors_K = [abs(v['K_error_pct']) for v in results.values() if v['experimental_K_gpa']]
    errors_E = [abs(v['E_error_pct']) for v in results.values() if v['experimental_E_gpa']]
    errors_G = [abs(v['G_error_pct']) for v in results.values() if v['experimental_G_gpa']]

    print(f"  Mean |error|: K={sum(errors_K)/len(errors_K):.0f}%, "
          f"E={sum(errors_E)/len(errors_E):.0f}%, "
          f"G={sum(errors_G)/len(errors_G):.0f}%")
    print(f"  Max  |error|: K={max(errors_K):.0f}%, "
          f"E={max(errors_E):.0f}%, "
          f"G={max(errors_G):.0f}%")
    print()

    path = enrich_nagatha(results)
    print(f"  Written to: {path}")
    print()
    print("  Done. Mechanical data ready for Nagatha.")


if __name__ == '__main__':
    main()
