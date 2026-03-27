#!/usr/bin/env python3
"""
Demo: Hot Plate → Thermoelectric Generator → Ice Cube

The complete derivation stack from □σ = −ξR to measurable electricity:

  σ → nuclear mass → electron density → Fermi energy → Seebeck coefficient
  → voltage from ΔT → current through load → power output

Setup:
  - Hot plate: copper at 500K (heated on a stove)
  - TEG: iron (p-leg) + copper (n-leg) thermocouple pairs
  - Cold side: ice cube at 273.15K (0°C)

Every number below is either DERIVED from the field equation or
honestly marked as MEASURED. No faking it.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sigma_ground.field.interface.thermoelectric import (
    free_electron_density,
    fermi_energy_ev,
    seebeck_coefficient_uv_k,
    electrical_conductivity,
    electrical_resistivity,
    figure_of_merit_ZT,
    simulate_teg_system,
    carnot_efficiency,
    _SEEBECK_MEASURED_UV_K,
)
from sigma_ground.field.interface.thermal import (
    thermal_conductivity,
    debye_temperature,
    blackbody_color,
    is_visibly_glowing,
)


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_material_card(mat_key):
    """Print thermoelectric properties of a material."""
    n_e = free_electron_density(mat_key)
    E_F = fermi_energy_ev(mat_key)
    S = seebeck_coefficient_uv_k(mat_key, T=300.0)
    S_meas = _SEEBECK_MEASURED_UV_K.get(mat_key)
    sigma_e = electrical_conductivity(mat_key)
    rho = electrical_resistivity(mat_key)
    kappa = thermal_conductivity(mat_key, T=300.0)
    theta_D = debye_temperature(mat_key)
    ZT = figure_of_merit_ZT(mat_key, T=300.0)

    print(f"\n  ── {mat_key.upper()} ──")
    print(f"  Free electrons:     {n_e:.2e} /m³  (Z_val × n_atoms)")
    print(f"  Fermi energy:       {E_F:.2f} eV     (Sommerfeld model)")
    print(f"  Seebeck (Mott):     {S:.3f} μV/K   (π²k²T / 2eE_F)")
    if S_meas is not None:
        ratio = S / abs(S_meas) * 100
        print(f"  Seebeck (MEASURED): {abs(S_meas):.3f} μV/K   "
              f"(Mott accuracy: {ratio:.0f}%)")
    print(f"  Resistivity:        {rho:.2e} Ω·m   (MEASURED)")
    print(f"  Conductivity:       {sigma_e:.2e} S/m")
    print(f"  Thermal κ:          {kappa:.1f} W/(m·K)")
    print(f"  Debye temperature:  {theta_D:.0f} K")
    print(f"  ZT at 300K:         {ZT:.2e}        (metals are terrible)")


def main():
    print_header("HOT PLATE → TEG → ICE CUBE")
    print("  Derivation: □σ = −ξR → measurable electricity")
    print("  Everything derived or honestly MEASURED")

    # ── Material Cards ──
    print_header("MATERIAL PROPERTIES")
    print_material_card('copper')
    print_material_card('iron')

    # ── Scenario 1: Lab bench ──
    print_header("SCENARIO 1: Lab Bench TEG")
    print("  Hot plate at 500K (227°C) — like a hot stove")
    print("  Ice cube at 273.15K (0°C)")
    print("  Single iron-copper thermocouple")
    print("  Leg: 1cm long, 1cm² cross-section")

    result = simulate_teg_system(
        mat_hot_plate='copper',
        mat_p='iron',
        mat_n='copper',
        T_hot=500.0,
        T_cold=273.15,
        leg_length_m=0.01,
        leg_area_m2=1e-4,
        n_couples=1,
    )

    print(f"\n  ΔT = {result['delta_T_K']:.1f} K")
    print(f"  Seebeck (Fe): {result['seebeck_p_uV_K']:.3f} μV/K")
    print(f"  Seebeck (Cu): {result['seebeck_n_uV_K']:.3f} μV/K")
    print(f"  ΔSeebeck:     {result['delta_seebeck_uV_K']:.3f} μV/K")
    print(f"\n  Open-circuit voltage:  {result['voltage_oc_V']*1e6:.3f} μV")
    print(f"  Load voltage (max P):  {result['voltage_load_V']*1e6:.3f} μV")
    print(f"  Current (max P):       {result['current_A']*1e3:.6f} mA")
    print(f"  Power output:          {result['power_max_W']*1e9:.3f} nW")
    print(f"\n  Internal resistance:   {result['resistance_internal_ohm']*1e6:.2f} μΩ")
    print(f"  Heat flow through TEG: {result['heat_flow_W']:.1f} W")
    print(f"  Carnot efficiency:     {result['carnot_efficiency']*100:.1f}%")
    print(f"  Actual efficiency:     {result['efficiency']*100:.8f}%")
    print(f"  Fraction of Carnot:    {result['efficiency_fraction_of_carnot']*100:.6f}%")

    # ── Scenario 2: 100-couple module ──
    print_header("SCENARIO 2: 100-Couple TEG Module")
    print("  Same temperatures, but 100 thermocouple pairs in series")
    print("  (like a commercial Peltier module run in reverse)")

    result_100 = simulate_teg_system(
        mat_hot_plate='copper',
        mat_p='iron',
        mat_n='copper',
        T_hot=500.0,
        T_cold=273.15,
        leg_length_m=0.01,
        leg_area_m2=1e-4,
        n_couples=100,
    )

    print(f"\n  Open-circuit voltage:  {result_100['voltage_oc_V']*1e6:.1f} μV")
    print(f"  Load voltage (max P):  {result_100['voltage_load_V']*1e6:.1f} μV")
    print(f"  Current (max P):       {result_100['current_A']*1e3:.6f} mA")
    print(f"  Power output:          {result_100['power_max_W']*1e9:.1f} nW")
    print(f"  Heat flow through TEG: {result_100['heat_flow_W']:.0f} W")

    # ── Scenario 3: Extreme temperatures ──
    print_header("SCENARIO 3: Extreme Heat — Glowing Hot Plate")
    print("  Hot plate at 1500K — visibly glowing!")

    T_extreme = 1500.0
    print(f"  Visibly glowing: {is_visibly_glowing(T_extreme)}")
    bb = blackbody_color(T_extreme)
    print(f"  Blackbody color: RGB({bb[0]:.2f}, {bb[1]:.2f}, {bb[2]:.2f})")

    result_hot = simulate_teg_system(
        mat_hot_plate='copper',
        mat_p='iron',
        mat_n='copper',
        T_hot=1500.0,
        T_cold=273.15,
        leg_length_m=0.01,
        leg_area_m2=1e-4,
        n_couples=100,
    )

    print(f"\n  ΔT = {result_hot['delta_T_K']:.1f} K")
    print(f"  Open-circuit voltage:  {result_hot['voltage_oc_V']*1e6:.1f} μV")
    print(f"  Power output:          {result_hot['power_max_W']*1e9:.1f} nW")
    print(f"  Carnot efficiency:     {result_hot['carnot_efficiency']*100:.1f}%")
    print(f"  Actual efficiency:     {result_hot['efficiency']*100:.8f}%")

    # ── The Derivation Chain ──
    print_header("THE DERIVATION CHAIN")
    print("""
  □σ = −ξR                    (field equation)
    ↓
  σ → nuclear mass            (ξ = 0.1582, Planck 2018)
    ↓
  mass → number density        (n = ρ/(A·m_u), MEASURED inputs)
    ↓
  n × Z_val → electron density (Z_val MEASURED, periodic table)
    ↓
  n_e → Fermi energy           (E_F = ℏ²(3π²n_e)^⅔ / 2m_e)
    ↓
  E_F → Seebeck coefficient    (S = π²k²T / 2eE_F, Mott formula)
    ↓
  S₁ - S₂ → voltage           (V = ΔS × ΔT, Seebeck effect)
    ↓
  V, ρ_elec → current          (I = V/2R, matched load, ρ MEASURED)
    ↓
  I × V → power                (P = V²/4R, maximum power transfer)
    ↓
  P / Q → efficiency           (η < η_Carnot, second law)

  Measured inputs: Z, A, ρ_kg, E_coh, lattice, Z_val, ρ_elec
  Everything else: DERIVED.
    """)

    # ── Why metals are bad (but the physics is beautiful) ──
    print_header("WHY METALS ARE BAD THERMOELECTRICS")
    print("""
  The Wiedemann-Franz law:  κ_elec = L₀ × σ × T

  This means: good electrical conductor = good thermal conductor.

  ZT = S² × σ × T / κ
     ≈ S² × σ × T / (L₀ × σ × T)    (WF substitution)
     = S² / L₀
     ≈ (π²k²T/2eE_F)² / (π²k²/3e²)  (Mott + Lorenz)
     ≈ (3/4) × (k_BT/E_F)²

  For copper at 300K:
    k_BT/E_F ≈ 0.026/7.0 ≈ 0.0037
    ZT ≈ 0.75 × (0.0037)² ≈ 1.0 × 10⁻⁵

  To get ZT > 1, you need materials where thermal and electrical
  conductivity are DECOUPLED. That's semiconductors — which is
  why Bi₂Te₃ (ZT ≈ 1.0) is the workhorse of thermoelectrics.

  But even with ZT = 10⁻⁵, the VOLTAGE is real and measurable.
  The physics works. The efficiency is just terrible.
    """)

    print_header("INFORMATION COMPRESSION UPDATE")
    print("""
  Previous: 76 measured inputs → surface, adhesion, mechanical,
            texture, friction, thermal predictions

  New measured inputs:
    + Z_val (valence electrons): 8 materials     → from periodic table
    + S_measured: 7 materials                     → for validation only

  Total: 76 + 8 = 84 measured inputs
  (S_measured values are validation, not derivation inputs)

  New predictions from these inputs:
    + Free electron density (all materials)
    + Fermi energy (all materials)
    + Seebeck coefficient (all materials)
    + Thermocouple voltage (any pair)
    + TEG power output (any configuration)
    + Thermoelectric efficiency (any ΔT)
    + Figure of merit ZT (all materials)

  The prediction fan keeps widening.
    """)


if __name__ == '__main__':
    main()
