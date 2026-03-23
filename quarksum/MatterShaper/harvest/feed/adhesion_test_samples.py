#!/usr/bin/env python3
"""
Adhesion Test Samples — Generate material-pair adhesion data
and feed through Nagatha's pipeline.

For every pair of materials in our database, compute:
  - Work of adhesion (Dupré equation)
  - Interface energy (Berthelot combining rule)
  - Contact angle (Young-Dupré, using reference liquid surface tensions)
  - EM/QCD decomposition

Then enrich the Nagatha color maps with adhesion data.

"Two surfaces walk into a bar. The bartender asks: how much
 energy did you spend getting here? They answer: γ₁ + γ₂ − γ₁₂."
"""

import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
HARVEST_DIR = os.path.dirname(HERE)
PROJECT_ROOT = os.path.join(HARVEST_DIR, '..', '..')

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, HARVEST_DIR)

from local_library.interface.surface import MATERIALS, surface_energy
from local_library.interface.adhesion import (
    work_of_adhesion, interface_energy, contact_angle,
    adhesion_decomposition, material_adhesion_properties,
)

# ── Reference liquid surface tensions (MEASURED, J/m²) ──────────
# These are needed for contact angle calculations.
# Source: CRC Handbook of Chemistry and Physics
LIQUID_SURFACE_TENSIONS = {
    'iron':     1.862,   # liquid iron at melting point
    'copper':   1.303,   # liquid copper at melting point
    'aluminum': 0.871,   # liquid aluminum at melting point
    'gold':     1.140,   # liquid gold at melting point
    'nickel':   1.778,   # liquid nickel at melting point
    'tungsten': 2.500,   # liquid tungsten (estimated, very high mp)
    'titanium': 1.650,   # liquid titanium at melting point
    'silicon':  0.865,   # liquid silicon at melting point
}


def generate_adhesion_matrix():
    """Compute adhesion for all material pairs.

    Returns a dict: {(mat1, mat2): adhesion_props}
    """
    materials = sorted(MATERIALS.keys())
    matrix = {}

    for i, m1 in enumerate(materials):
        for m2 in materials[i:]:
            W = work_of_adhesion(m1, m2)
            gamma_12 = interface_energy(m1, m2)
            dec = adhesion_decomposition(m1, m2)

            # Contact angle: use m2's liquid surface tension on m1 solid
            gamma_lv = LIQUID_SURFACE_TENSIONS.get(m2, 1.0)
            theta = contact_angle(m1, m2, gamma_lv=gamma_lv)

            matrix[(m1, m2)] = {
                'material_1': m1,
                'material_2': m2,
                'work_of_adhesion_j_m2': round(W, 4),
                'interface_energy_j_m2': round(gamma_12, 4),
                'contact_angle_deg': round(theta, 1) if theta is not None else None,
                'em_fraction': round(dec['em_component_j_m2'] / dec['total_j_m2'], 4),
                'gamma_1_j_m2': round(surface_energy(m1), 4),
                'gamma_2_j_m2': round(surface_energy(m2), 4),
            }

    return matrix


def validate_matrix(matrix):
    """Run sanity checks on the adhesion matrix."""
    errors = []

    for key, props in matrix.items():
        m1, m2 = key
        W = props['work_of_adhesion_j_m2']
        gamma_12 = props['interface_energy_j_m2']

        # W must be positive
        if W <= 0:
            errors.append(f"W({m1},{m2}) = {W} ≤ 0")

        # γ₁₂ must be ≥ 0
        if gamma_12 < -1e-10:
            errors.append(f"γ({m1},{m2}) = {gamma_12} < 0")

        # Self-adhesion: γ₁₂ = 0
        if m1 == m2 and abs(gamma_12) > 1e-10:
            errors.append(f"Self-interface {m1}: γ₁₂ = {gamma_12} ≠ 0")

        # Dupré check: W = γ₁ + γ₂ − γ₁₂
        g1 = props['gamma_1_j_m2']
        g2 = props['gamma_2_j_m2']
        W_check = g1 + g2 - gamma_12
        if abs(W - W_check) > 0.001:
            errors.append(f"Dupré violated for ({m1},{m2}): "
                         f"W={W}, γ₁+γ₂-γ₁₂={W_check}")

    return errors


def enrich_nagatha_colors(matrix):
    """Add adhesion data to Nagatha's color map format."""
    out_dir = os.path.join(HERE, 'adhesion_enriched')
    os.makedirs(out_dir, exist_ok=True)

    # Create a summary JSON with the full matrix
    summary = {
        'description': 'Adhesion matrix for all material pairs',
        'origin': 'Dupré equation + Berthelot combining rule',
        'pairs': {}
    }

    for key, props in matrix.items():
        m1, m2 = key
        pair_key = f"{m1}-{m2}"
        summary['pairs'][pair_key] = props

    summary_path = os.path.join(out_dir, 'adhesion_matrix.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    return summary_path


def main():
    print("=" * 60)
    print("  ADHESION TEST SAMPLES — Nagatha Feed")
    print("=" * 60)
    print()

    # Generate full adhesion matrix
    print("Generating adhesion matrix for all material pairs...")
    matrix = generate_adhesion_matrix()
    print(f"  Computed {len(matrix)} material pairs")
    print()

    # Print the matrix
    materials = sorted(MATERIALS.keys())
    print(f"  {'':>12s}", end='')
    for m in materials:
        print(f"  {m[:6]:>6s}", end='')
    print()
    print(f"  {'':>12s}", end='')
    for _ in materials:
        print(f"  {'─'*6}", end='')
    print()

    for m1 in materials:
        print(f"  {m1:>12s}", end='')
        for m2 in materials:
            key = (m1, m2) if (m1, m2) in matrix else (m2, m1)
            if key in matrix:
                W = matrix[key]['work_of_adhesion_j_m2']
                print(f"  {W:6.2f}", end='')
            else:
                print(f"  {'---':>6s}", end='')
        print()
    print()

    # Validate
    print("Validating adhesion matrix...")
    errors = validate_matrix(matrix)
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
    else:
        print(f"  All {len(matrix)} pairs pass validation")
    print()

    # Enrich Nagatha
    print("Enriching Nagatha color maps with adhesion data...")
    summary_path = enrich_nagatha_colors(matrix)
    print(f"  Written to: {summary_path}")
    print()

    # Show interesting pairs
    print("Notable adhesion pairs:")
    # Strongest
    strongest = max(matrix.items(), key=lambda x: x[1]['work_of_adhesion_j_m2'])
    print(f"  Strongest: {strongest[0][0]}-{strongest[0][1]} "
          f"W = {strongest[1]['work_of_adhesion_j_m2']:.3f} J/m²")

    # Weakest cross-pair
    cross_pairs = {k: v for k, v in matrix.items() if k[0] != k[1]}
    if cross_pairs:
        weakest = min(cross_pairs.items(),
                     key=lambda x: x[1]['work_of_adhesion_j_m2'])
        print(f"  Weakest cross: {weakest[0][0]}-{weakest[0][1]} "
              f"W = {weakest[1]['work_of_adhesion_j_m2']:.3f} J/m²")

    # Highest interface energy
    highest_if = max(matrix.items(),
                     key=lambda x: x[1]['interface_energy_j_m2'])
    print(f"  Most dissimilar: {highest_if[0][0]}-{highest_if[0][1]} "
          f"γ₁₂ = {highest_if[1]['interface_energy_j_m2']:.3f} J/m²")

    print()
    print("Done. Adhesion data ready for Nagatha.")


if __name__ == '__main__':
    main()
