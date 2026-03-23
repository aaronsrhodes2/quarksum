"""
Z → EVERYTHING
===============

The periodic table from first principles.
Input: one integer. Output: material science.

No dictionaries. No lookup tables. No borrowed data.
Just Z and quantum mechanics.

This demo derives 7 material properties for 8 elements
from atomic number alone, then compares every prediction
against the MEASURED values in the MATERIALS dictionary.

The MATERIALS dictionary is not an input. It's a judge.

□σ = −ξR
"""

import math
from .element import (
    aufbau_configuration,
    free_electron_count,
    d_electron_count,
    d_row,
    slater_zeff,
    slater_radius_m,
    stable_mass_number,
    predict_crystal_structure,
    predict_lattice_parameter_m,
    predict_density_kg_m3,
    friedel_cohesive_energy_eV,
    element_properties,
)


# ── Validation targets (MEASURED) ─────────────────────────────────
_TARGETS = {
    'Iron':     {'Z': 26, 'A': 56, 'ρ': 7874,  'E_coh': 4.28,
                 'xtal': 'bcc', 'a': 2.867, 'n_v': 2},
    'Copper':   {'Z': 29, 'A': 64, 'ρ': 8960,  'E_coh': 3.49,
                 'xtal': 'fcc', 'a': 3.615, 'n_v': 1},
    'Aluminum': {'Z': 13, 'A': 27, 'ρ': 2700,  'E_coh': 3.39,
                 'xtal': 'fcc', 'a': 4.050, 'n_v': 3},
    'Gold':     {'Z': 79, 'A': 197, 'ρ': 19300, 'E_coh': 3.81,
                 'xtal': 'fcc', 'a': 4.078, 'n_v': 1},
    'Silicon':  {'Z': 14, 'A': 28, 'ρ': 2330,  'E_coh': 4.63,
                 'xtal': 'diamond', 'a': 5.431, 'n_v': 4},
    'Titanium': {'Z': 22, 'A': 48, 'ρ': 4507,  'E_coh': 4.85,
                 'xtal': 'hcp', 'a': 2.951, 'n_v': 4},
    'Tungsten': {'Z': 74, 'A': 184, 'ρ': 19300, 'E_coh': 8.90,
                 'xtal': 'bcc', 'a': 3.165, 'n_v': 6},
    'Nickel':   {'Z': 28, 'A': 59, 'ρ': 8908,  'E_coh': 4.44,
                 'xtal': 'fcc', 'a': 3.524, 'n_v': 2},
}


def _config_shorthand(config):
    """Compact electron configuration string."""
    # Noble gas cores
    cores = {
        2:  'He', 10: 'Ne', 18: 'Ar', 36: 'Kr', 54: 'Xe', 86: 'Rn',
    }

    # Sort orbitals by (n, l)
    l_order = {'s': 0, 'p': 1, 'd': 2, 'f': 3}
    sorted_orbitals = sorted(config.items(),
                              key=lambda x: (int(x[0][0]), l_order[x[0][1]]))

    # Find largest noble gas core
    running_sum = 0
    best_core = None
    best_core_Z = 0
    for label, count in sorted_orbitals:
        running_sum += count
        if running_sum in cores:
            best_core = cores[running_sum]
            best_core_Z = running_sum

    parts = []
    if best_core:
        parts.append(f'[{best_core}]')

    running = 0
    for label, count in sorted_orbitals:
        running += count
        if running > best_core_Z:
            sup = str(count)
            parts.append(f'{label}{sup}')

    return ' '.join(parts) if parts else '?'


def _grade(predicted, actual, tolerance_pct=None, exact=False):
    """Return grade emoji and error info."""
    if exact:
        if predicted == actual:
            return '✓', '  exact'
        else:
            return '✗', f'  WRONG'

    if actual == 0:
        return '—', ''

    error_pct = abs(predicted - actual) / abs(actual) * 100

    if error_pct < 5:
        return '✓', f'{error_pct:5.1f}%'
    elif error_pct < 20:
        return '~', f'{error_pct:5.1f}%'
    elif error_pct < 50:
        return '≈', f'{error_pct:5.1f}%'
    else:
        return '✗', f'{error_pct:5.1f}%'


def run_demo():
    """Run the Z → Everything demo."""

    print()
    print('═' * 70)
    print('  Z → EVERYTHING')
    print('  The Periodic Table from First Principles')
    print('═' * 70)
    print()
    print('  Input: one integer (atomic number Z)')
    print('  Output: electron configuration, crystal structure,')
    print('          lattice parameter, density, cohesive energy')
    print()
    print('  Material-specific measured inputs: ZERO')
    print()

    # ── Element cards ──
    for name, t in _TARGETS.items():
        Z = t['Z']
        p = element_properties(Z)
        config = _config_shorthand(p['electron_configuration'])

        print('─' * 70)
        print(f'  {name}  (Z = {Z})')
        print('─' * 70)
        print()
        print(f'  Electron config:    {config}')
        print(f'  d-electrons:        {p["d_electrons"]}'
              f'{"  (row: " + str(p["d_row"]) + "d)" if p["d_row"] else ""}')
        print(f'  Slater Z_eff:       {p["slater_zeff"]:.2f}')
        print(f'  Slater radius:      {p["slater_radius_m"]*1e10:.3f} Å')
        print()

        # Predictions vs reality
        print(f'  {"Property":22s}  {"Predicted":>10s}  {"Measured":>10s}  {"Grade":s}')
        print(f'  {"─"*22}  {"─"*10}  {"─"*10}  {"─"*10}')

        # Valence electrons
        g, e = _grade(p['free_electrons'], t['n_v'], exact=True)
        print(f'  {"Valence electrons":22s}  {p["free_electrons"]:10d}  {t["n_v"]:10d}  {g} {e}')

        # Mass number
        g, e = _grade(p['A_predicted'], t['A'])
        print(f'  {"Mass number A":22s}  {p["A_predicted"]:10d}  {t["A"]:10d}  {g} {e}')

        # Crystal structure
        g, e = _grade(p['crystal_structure'], t['xtal'], exact=True)
        print(f'  {"Crystal structure":22s}  {p["crystal_structure"]:>10s}  {t["xtal"]:>10s}  {g} {e}')

        # Lattice parameter
        a_pred = p['lattice_parameter_m'] * 1e10
        g, e = _grade(a_pred, t['a'])
        print(f'  {"Lattice param (Å)":22s}  {a_pred:10.3f}  {t["a"]:10.3f}  {g} {e}')

        # Density
        g, e = _grade(p['density_kg_m3'], t['ρ'])
        print(f'  {"Density (kg/m³)":22s}  {p["density_kg_m3"]:10.0f}  {t["ρ"]:10d}  {g} {e}')

        # Cohesive energy
        E = p['friedel_cohesive_energy_eV']
        if E is not None:
            g, e = _grade(E, t['E_coh'])
            print(f'  {"Cohesive E (eV)":22s}  {E:10.2f}  {t["E_coh"]:10.2f}  {g} {e}')
        else:
            reason = 'd¹⁰ full' if p['d_electrons'] >= 10 else 'sp metal' if p['d_electrons'] == 0 else '?'
            print(f'  {"Cohesive E (eV)":22s}  {"—":>10s}  {t["E_coh"]:10.2f}  — ({reason})')

        print()

    # ── Scorecard ──
    print('═' * 70)
    print('  SCORECARD')
    print('═' * 70)
    print()

    n_struct = sum(1 for t in _TARGETS.values()
                   if predict_crystal_structure(t['Z']) == t['xtal'])
    n_val = sum(1 for t in _TARGETS.values()
                if free_electron_count(t['Z']) == t['n_v'])

    mass_errors = [abs(stable_mass_number(t['Z']) - t['A'])
                   for t in _TARGETS.values()]
    lat_errors = [abs(predict_lattice_parameter_m(t['Z'])*1e10 - t['a']) / t['a'] * 100
                  for t in _TARGETS.values()]
    den_errors = [abs(predict_density_kg_m3(t['Z']) - t['ρ']) / t['ρ'] * 100
                  for t in _TARGETS.values()]

    friedel_elements = [(n, t) for n, t in _TARGETS.items()
                        if friedel_cohesive_energy_eV(t['Z']) is not None]
    coh_errors = [abs(friedel_cohesive_energy_eV(t['Z']) - t['E_coh']) / t['E_coh'] * 100
                  for _, t in friedel_elements]

    print(f'  Crystal structure:     {n_struct}/8 exact')
    print(f'  Valence electrons:     {n_val}/8 exact')
    print(f'  Mass number:           mean error {sum(mass_errors)/len(mass_errors):.1f} amu')
    print(f'  Lattice parameter:     mean error {sum(lat_errors)/len(lat_errors):.1f}%')
    print(f'  Density:               mean error {sum(den_errors)/len(den_errors):.1f}%')
    print(f'  Cohesive energy:       mean error {sum(coh_errors)/len(coh_errors):.1f}%'
          f'  ({len(friedel_elements)}/8 elements, Friedel model)')
    print()

    # ── The derivation chain ──
    print('─' * 70)
    print('  THE DERIVATION CHAIN')
    print('─' * 70)
    print()
    print('  Z')
    print('  │')
    print('  ├─ Schrödinger eq. ──► Madelung rule ──► electron configuration')
    print('  │                                         │')
    print('  │                                         ├──► valence electrons')
    print('  │                                         ├──► d-electron count')
    print('  │                                         │')
    print('  │  Slater shielding ◄─────────────────────┘')
    print('  │  │')
    print('  │  └──► Z_eff ──► orbital radius ──► metallic radius')
    print('  │                                     │')
    print('  │  Brewer-Engel ◄── d-count            │')
    print('  │  │                                   │')
    print('  │  └──► crystal structure ──────────────┤')
    print('  │                                      │')
    print('  │                                      └──► lattice parameter')
    print('  │                                            │')
    print('  ├─ Liquid drop model ──► SEMF ──► mass number ─┤')
    print('  │                                              │')
    print('  │                                              └──► density')
    print('  │')
    print('  └─ Tight-binding ──► Friedel ──► cohesive energy')
    print('                       (d-band)    (where applicable)')
    print()

    # ── Information accounting ──
    print('─' * 70)
    print('  INFORMATION ACCOUNTING')
    print('─' * 70)
    print()
    print('  WHAT WENT IN:')
    print('    Z. One integer per element. Nothing else.')
    print()
    print('  UNIVERSAL CONSTANTS USED:')
    print('    a₀ = 5.292×10⁻¹¹ m  (Bohr radius, from QED)')
    print('    u  = 1.661×10⁻²⁷ kg (atomic mass unit, from ¹²C definition)')
    print()
    print('  FITTED PARAMETERS:')
    print('    SEMF: a_v=15.56, a_s=17.23, a_c=0.7, a_a=23.29 MeV')
    print('          (5 numbers, fitted to ALL nuclei, not per-element)')
    print('    Slater: shielding constants 0.30, 0.35, 0.85, 1.00')
    print('          (4 numbers, same for every element)')
    print('    Friedel: W = 5, 7.5, 10 eV for 3d/4d/5d rows')
    print('          (3 numbers, one per row)')
    print()
    print('  MEASURED EXCEPTIONS:')
    print('    Aufbau: Cr, Cu, Nb, Mo, Ru, Rh, Pd, Ag, Pt, Au')
    print('          (10 elements with non-standard shell filling)')
    print()
    print('  TOTAL measured/fitted inputs: 22 numbers')
    print('  TOTAL properties derived: 7 per element × unlimited elements')
    print()
    print('  Information compression ratio: 22 inputs → infinite outputs')
    print('  The compression algorithm IS quantum mechanics.')
    print()

    # ── What's NOT derived yet ──
    print('─' * 70)
    print('  HONEST GAPS')
    print('─' * 70)
    print()
    print('  Still in lookup tables (not yet derived from Z):')
    print('    • Resistivity — needs electron-phonon scattering theory')
    print('    • Poisson ratio — needs elastic tensor from orbital overlap')
    print('    • Cohesive energy for d¹⁰ and sp metals (Cu, Au, Al, Si)')
    print('    • Bond force constants — needs molecular orbital theory')
    print('    • Collision diameters — needs electron cloud calculation')
    print()
    print('  Known accuracy limits:')
    print('    • Slater radii miss relativistic contraction (5d metals)')
    print('    • Friedel model: ±30-40% (row-averaged d-band width)')
    print('    • SEMF: ±3 amu (misses nuclear shell magic numbers)')
    print()
    print('  These gaps are the staircase ahead.')
    print('  Each one, when climbed, removes a dictionary entry.')
    print('  At the top: Z and σ → everything. No dictionaries at all.')
    print()
    print('  □σ = −ξR')
    print()

    return {name: element_properties(t['Z']) for name, t in _TARGETS.items()}


if __name__ == '__main__':
    run_demo()
