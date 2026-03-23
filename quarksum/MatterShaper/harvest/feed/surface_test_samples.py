#!/usr/bin/env python3
"""
Surface Test Samples — Generate materials with known surface properties
and feed them through Nagatha's analysis pipeline.

This creates test OBJ objects with specific material assignments,
runs them through the harvest parser, and validates that the surface
energy module produces correct results for each material.

"Every object knows what it's made of.
 Now it knows what happens at its edges."
"""

import os
import sys
import json
import math

# Set up paths
HERE = os.path.dirname(os.path.abspath(__file__))
HARVEST_DIR = os.path.dirname(HERE)
PROJECT_ROOT = os.path.join(HARVEST_DIR, '..', '..')

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, HARVEST_DIR)

from local_library.interface.surface import (
    MATERIALS, surface_energy, surface_energy_at_sigma,
    surface_energy_decomposition, material_surface_properties,
    bulk_coordination, surface_coordination, surface_atom_density
)


# ── Test Material Map ──────────────────────────────────────────────
# Maps our physics materials to Nagatha's format.
# These go into color.json as enriched material entries.

def enrich_material_for_nagatha(material_key):
    """Take a material from surface.py and produce Nagatha-format entry."""
    mat = MATERIALS[material_key]
    props = material_surface_properties(material_key)
    dec = surface_energy_decomposition(material_key)

    return {
        'label': mat['name'],
        'composition': mat['composition'],
        'density_kg_m3': mat['density_kg_m3'],
        'mean_Z': mat['Z'],
        'mean_A': mat['A'],
        # ── Surface physics (new) ──
        'surface_energy_j_m2': round(props['surface_energy_j_m2'], 4),
        'em_fraction': round(props['em_fraction'], 4),
        'sigma_sensitivity': round(props['sigma_sensitivity'], 6),
        'crystal_structure': mat['crystal_structure'],
        'cohesive_energy_ev': mat['cohesive_energy_ev'],
        'lattice_param_angstrom': mat['lattice_param_angstrom'],
    }


# ── Test Object Definitions ───────────────────────────────────────
# Each object is a simple quadric-only geometry with known materials.

TEST_OBJECTS = {
    'iron_sphere': {
        'obj_file': 'sphere.obj',
        'material': 'iron',
        'description': 'Pure iron sphere — surface energy test',
        'expected_gamma_range': (1.7, 3.1),  # J/m², BBM range for iron
    },
    'copper_egg': {
        'obj_file': 'egg.obj',
        'material': 'copper',
        'description': 'Copper egg — FCC(111) surface energy',
        'expected_gamma_range': (0.8, 2.4),
    },
    'aluminum_cylinder': {
        'obj_file': 'cylinder.obj',
        'material': 'aluminum',
        'description': 'Aluminum cylinder — lightweight metal surface',
        'expected_gamma_range': (0.8, 1.4),
    },
    'gold_sphere': {
        'obj_file': 'sphere.obj',
        'material': 'gold',
        'description': 'Gold sphere — noble metal surface',
        'expected_gamma_range': (1.0, 2.0),
    },
    'silicon_cone': {
        'obj_file': 'cone.obj',
        'material': 'silicon',
        'description': 'Silicon cone — covalent semiconductor surface',
        'expected_gamma_range': (0.5, 1.5),
    },
    'tungsten_capsule': {
        'obj_file': 'capsule.obj',
        'material': 'tungsten',
        'description': 'Tungsten capsule — refractory metal, highest γ',
        'expected_gamma_range': (3.0, 8.0),
    },
    'nickel_dumbbell': {
        'obj_file': 'dumbbell.obj',
        'material': 'nickel',
        'description': 'Nickel dumbbell — transition metal surface',
        'expected_gamma_range': (1.5, 3.0),
    },
    'titanium_bottle': {
        'obj_file': 'bottle.obj',
        'material': 'titanium',
        'description': 'Titanium bottle — HCP metal surface',
        'expected_gamma_range': (1.5, 3.5),
    },
}


def generate_test_color_maps():
    """Generate Nagatha-format color.json files enriched with surface physics."""
    results = {}

    for obj_key, obj_def in TEST_OBJECTS.items():
        mat_key = obj_def['material']
        enriched = enrich_material_for_nagatha(mat_key)
        gamma = enriched['surface_energy_j_m2']
        lo, hi = obj_def['expected_gamma_range']

        status = 'PASS' if lo <= gamma <= hi else 'FAIL'
        results[obj_key] = {
            'material': mat_key,
            'gamma_j_m2': gamma,
            'range': obj_def['expected_gamma_range'],
            'status': status,
            'enriched_material': enriched,
        }

    return results


def run_nagatha_feed_test():
    """Run test samples through surface physics and report results."""
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  S U R F A C E  E N E R G Y  —  T E S T  F E E D ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    results = generate_test_color_maps()
    all_pass = True

    print(f"  {'Object':<25} {'Material':<12} {'γ (J/m²)':<10} {'Range':<15} {'Status'}")
    print(f"  {'─'*25} {'─'*12} {'─'*10} {'─'*15} {'─'*6}")

    for obj_key, r in results.items():
        lo, hi = r['range']
        status_mark = '✓' if r['status'] == 'PASS' else '✗'
        print(f"  {obj_key:<25} {r['material']:<12} {r['gamma_j_m2']:<10.4f} "
              f"[{lo:.1f}, {hi:.1f}]      {status_mark} {r['status']}")
        if r['status'] != 'PASS':
            all_pass = False

    print()

    # ── σ-field survey ─────────────────────────────────────────────
    print("  σ-field sensitivity (dγ/γ per unit σ):")
    print(f"  {'Material':<12} {'γ₀ (J/m²)':<12} {'γ(σ=0.1)':<12} {'Δγ/γ₀':<10} {'EM%'}")
    print(f"  {'─'*12} {'─'*12} {'─'*12} {'─'*10} {'─'*6}")

    for mat_key in sorted(MATERIALS.keys()):
        g0 = surface_energy(mat_key)
        g1 = surface_energy_at_sigma(mat_key, 0.1)
        dec = surface_energy_decomposition(mat_key)
        delta = (g1 - g0) / g0 * 100
        em_pct = dec['em_fraction'] * 100
        print(f"  {mat_key:<12} {g0:<12.4f} {g1:<12.4f} {delta:<+10.4f}% {em_pct:.1f}%")

    print()

    # ── Generate enriched color maps for Nagatha ──────────────────
    output_dir = os.path.join(HERE, 'surface_enriched')
    os.makedirs(output_dir, exist_ok=True)

    for obj_key, r in results.items():
        color_map = {
            'name': f"{obj_key} Surface Test",
            'reference': TEST_OBJECTS[obj_key]['description'],
            'provenance': 'Generated by surface_test_samples.py — broken-bond model surface energy from SSBM framework',
            'materials': {
                'primary': r['enriched_material']
            }
        }
        path = os.path.join(output_dir, f'{obj_key}.color.json')
        with open(path, 'w') as f:
            json.dump(color_map, f, indent=2)

    print(f"  Wrote {len(results)} enriched color maps to {os.path.relpath(output_dir, PROJECT_ROOT)}")

    # ── Parse existing feed OBJs to verify Nagatha can eat them ────
    print()
    print("  Checking feed OBJs parseable by Nagatha...")
    try:
        from obj_parser import parse_obj
        feed_dir = HERE
        obj_files = [f for f in os.listdir(feed_dir) if f.endswith('.obj')]
        parsed = 0
        for obj_file in sorted(obj_files):
            obj_path = os.path.join(feed_dir, obj_file)
            mesh = parse_obj(obj_path)
            verts = mesh.total_vertices
            faces = mesh.total_faces
            print(f"    {obj_file:<20} {verts:>5} verts  {faces:>5} faces  ✓")
            parsed += 1
        print(f"  {parsed}/{len(obj_files)} OBJ files parsed successfully.")
    except Exception as e:
        print(f"  Warning: Could not test OBJ parsing: {e}")

    print()
    if all_pass:
        print("  ═══════════════════════════════════════════════")
        print("  ALL SURFACE ENERGY TESTS PASS")
        print("  Materials are ready for Nagatha's enriched maps")
        print("  ═══════════════════════════════════════════════")
    else:
        print("  ⚠ SOME TESTS FAILED — check ranges above")

    return all_pass


if __name__ == '__main__':
    success = run_nagatha_feed_test()
    sys.exit(0 if success else 1)
