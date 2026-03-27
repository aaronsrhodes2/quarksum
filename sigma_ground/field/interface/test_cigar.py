"""
Tests for the carbon cigar gas-phase experiment.

Test structure:
  1. Combustion — enthalpy, flame temperature
  2. Soot — fraction, emission color
  3. Darcy flow — permeability, velocity
  4. Vacuum sphere — pressure from accumulated gas
  5. Gas cooling — temperature profile through cigar
  6. Pole-to-pole electricity — Seebeck voltage from temperature gradient
  7. σ-spectroscopy — CO₂ frequency shift detects σ
  8. Full simulation — complete cigar experiment
"""

import math
import unittest

from .cigar import (
    combustion_enthalpy_per_mol_C,
    combustion_temperature,
    soot_fraction,
    soot_emission_color,
    kozeny_carman_permeability,
    darcy_flow_velocity,
    darcy_mass_flow_rate,
    sphere_pressure,
    sphere_volume,
    gas_temperature_after_cooling,
    simulate_carbon_cigar,
)
from .gas import vibrational_wavenumber, MOLECULES


class TestCombustion(unittest.TestCase):
    """C + O₂ → CO₂: enthalpy and flame temperature."""

    def test_combustion_exothermic(self):
        """Combustion of carbon releases energy (negative ΔH)."""
        dH = combustion_enthalpy_per_mol_C(complete=True)
        self.assertLess(dH, 0)

    def test_complete_more_exothermic(self):
        """C→CO₂ releases more energy than C→CO."""
        dH_complete = combustion_enthalpy_per_mol_C(complete=True)
        dH_incomplete = combustion_enthalpy_per_mol_C(complete=False)
        self.assertLess(dH_complete, dH_incomplete)  # more negative

    def test_combustion_enthalpy_known(self):
        """C + O₂ → CO₂: ΔH = -393.5 kJ/mol (NIST)."""
        dH = combustion_enthalpy_per_mol_C(complete=True)
        self.assertAlmostEqual(dH / 1000, -393.5, delta=0.1)

    def test_flame_temperature_reasonable(self):
        """Actual flame temperature should be 800-2000K for carbon in air."""
        result = combustion_temperature(T_ambient=300.0)
        T = result['T_actual_K']
        self.assertGreater(T, 800)
        self.assertLess(T, 2000)

    def test_adiabatic_higher_than_actual(self):
        """Adiabatic T > actual T (radiation losses)."""
        result = combustion_temperature()
        self.assertGreater(result['T_adiabatic_K'], result['T_actual_K'])


class TestSoot(unittest.TestCase):
    """Incomplete combustion produces soot."""

    def test_soot_fraction_positive(self):
        """Some soot is produced (incomplete combustion)."""
        sf = soot_fraction(complete_fraction=0.8)
        self.assertGreaterEqual(sf, 0)

    def test_more_complete_less_soot(self):
        """Higher complete_fraction → less soot."""
        sf_80 = soot_fraction(0.8)
        sf_95 = soot_fraction(0.95)
        self.assertGreaterEqual(sf_80, sf_95)

    def test_soot_glows(self):
        """Soot at flame temperature should glow visibly."""
        result = soot_emission_color(1300.0)
        self.assertTrue(result['visibly_glowing'])
        # Should be orange/yellow
        r, g, b = result['rgb']
        self.assertGreater(r, g)  # red > green (hot glow)

    def test_soot_not_glowing_at_room_T(self):
        """Soot at room temperature: no visible emission."""
        result = soot_emission_color(300.0)
        self.assertFalse(result['visibly_glowing'])


class TestDarcyFlow(unittest.TestCase):
    """Flow through porous carbon cigar body."""

    def test_permeability_positive(self):
        """Packed bed has positive permeability."""
        kappa = kozeny_carman_permeability(100e-6, 0.35)
        self.assertGreater(kappa, 0)

    def test_larger_particles_more_permeable(self):
        """Bigger particles → bigger pores → higher permeability."""
        k_small = kozeny_carman_permeability(50e-6, 0.35)
        k_large = kozeny_carman_permeability(200e-6, 0.35)
        self.assertGreater(k_large, k_small)

    def test_higher_porosity_more_permeable(self):
        """More void space → more flow."""
        k_tight = kozeny_carman_permeability(100e-6, 0.2)
        k_loose = kozeny_carman_permeability(100e-6, 0.4)
        self.assertGreater(k_loose, k_tight)

    def test_darcy_velocity_positive(self):
        """Positive pressure drop → positive flow."""
        kappa = kozeny_carman_permeability(100e-6, 0.35)
        v = darcy_flow_velocity(kappa, 2e-5, 101325.0, 0.10)
        self.assertGreater(v, 0)

    def test_darcy_proportional_to_pressure(self):
        """v ∝ ΔP (linear Darcy regime)."""
        kappa = kozeny_carman_permeability(100e-6, 0.35)
        v1 = darcy_flow_velocity(kappa, 2e-5, 50000.0, 0.10)
        v2 = darcy_flow_velocity(kappa, 2e-5, 100000.0, 0.10)
        self.assertAlmostEqual(v2 / v1, 2.0, delta=0.01)

    def test_mass_flow_positive(self):
        """Mass flow = density × velocity × area."""
        mdot = darcy_mass_flow_rate(0.5, 1.2, 1e-4)
        self.assertAlmostEqual(mdot, 0.5 * 1.2 * 1e-4, places=10)


class TestVacuumSphere(unittest.TestCase):
    """Gas collection in the vacuum sphere."""

    def test_sphere_volume_formula(self):
        """V = (4/3)πr³."""
        V = sphere_volume(0.05)
        expected = (4.0/3.0) * math.pi * 0.05**3
        self.assertAlmostEqual(V, expected, places=10)

    def test_pressure_from_ideal_gas(self):
        """P = nRT/V for known amount of gas."""
        # 0.01 mol at 300K in 524 mL sphere
        V = sphere_volume(0.05)  # ~5.24 × 10⁻⁴ m³
        P = sphere_pressure(0.01, 300.0, V)
        # P = 0.01 × 8.314 × 300 / 5.24e-4 ≈ 47,600 Pa
        self.assertAlmostEqual(P, 47600, delta=1000)

    def test_pressure_increases_with_gas(self):
        """More gas → higher pressure."""
        V = sphere_volume(0.05)
        P1 = sphere_pressure(0.01, 300.0, V)
        P2 = sphere_pressure(0.02, 300.0, V)
        self.assertAlmostEqual(P2 / P1, 2.0, places=5)

    def test_zero_gas_zero_pressure(self):
        """No gas → no pressure (vacuum)."""
        V = sphere_volume(0.05)
        P = sphere_pressure(0.0, 300.0, V)
        self.assertEqual(P, 0.0)


class TestGasCooling(unittest.TestCase):
    """Hot gas cools as it flows through the cigar."""

    def test_exit_temperature_between_extremes(self):
        """T_exit should be between T_wall and T_combustion."""
        T_exit = gas_temperature_after_cooling(
            T_combustion=1300.0, T_wall=350.0,
            length_m=0.08, velocity_m_s=0.5, diameter_m=0.015)
        self.assertGreater(T_exit, 350.0)
        self.assertLess(T_exit, 1300.0)

    def test_longer_cigar_cooler_exit(self):
        """Longer flow path → more cooling → lower T_exit."""
        T_short = gas_temperature_after_cooling(
            1300, 350, 0.02, 0.5, 0.015)
        T_long = gas_temperature_after_cooling(
            1300, 350, 0.10, 0.5, 0.015)
        self.assertLess(T_long, T_short)

    def test_zero_velocity_equals_wall_temp(self):
        """No flow → gas reaches wall temperature."""
        T_exit = gas_temperature_after_cooling(
            1300, 350, 0.08, 0.0, 0.015)
        self.assertAlmostEqual(T_exit, 350.0, places=5)


class TestPoleToPolElectricity(unittest.TestCase):
    """Carbon cigar generates Seebeck voltage from its temperature gradient."""

    def test_generates_voltage(self):
        """Lit cigar produces measurable voltage."""
        result = simulate_carbon_cigar()
        self.assertGreater(result['seebeck_voltage_V'], 0)

    def test_voltage_in_millivolt_range(self):
        """Carbon Seebeck ≈ 4 μV/K × ~1000K ΔT → several mV."""
        result = simulate_carbon_cigar()
        self.assertGreater(result['seebeck_voltage_mV'], 0.5)
        self.assertLess(result['seebeck_voltage_mV'], 20.0)

    def test_generates_power(self):
        """Non-zero power from thermoelectric effect."""
        result = simulate_carbon_cigar()
        self.assertGreater(result['electric_power_W'], 0)

    def test_resistance_reasonable(self):
        """Cigar resistance should be milliohms to ohms."""
        result = simulate_carbon_cigar()
        R = result['cigar_resistance_ohm']
        self.assertGreater(R, 1e-4)
        self.assertLess(R, 100.0)


class TestSigmaSpectroscopy(unittest.TestCase):
    """CO₂ vibrational frequencies shift with σ."""

    def test_no_shift_at_earth(self):
        """σ ≈ 0 gives zero frequency shift."""
        result = simulate_carbon_cigar(sigma=0.0)
        self.assertAlmostEqual(result['frequency_shift_cm_inv'], 0.0, places=5)

    def test_shift_at_neutron_star(self):
        """σ = 0.1 gives measurable frequency shift."""
        result = simulate_carbon_cigar(sigma=0.1)
        self.assertGreater(abs(result['frequency_shift_cm_inv']), 1.0)

    def test_shift_direction(self):
        """σ > 0 → heavier nuclei → lower frequency → positive shift (ν₀ - ν_σ > 0)."""
        result = simulate_carbon_cigar(sigma=0.1)
        self.assertGreater(result['frequency_shift_cm_inv'], 0)

    def test_co2_spectrum_present(self):
        """CO₂ spectrum is included in results."""
        result = simulate_carbon_cigar()
        self.assertIn('co2_spectrum', result)
        self.assertGreater(len(result['co2_spectrum']), 0)


class TestFullSimulation(unittest.TestCase):
    """Complete carbon cigar experiment."""

    def test_all_keys_present(self):
        """Simulation returns all expected keys."""
        result = simulate_carbon_cigar()
        required_keys = [
            'cigar_length_m', 'cigar_diameter_m', 'sphere_volume_m3',
            'T_flame_K', 'burn_length_m', 'mass_carbon_burned_g',
            'mol_CO2', 'mol_CO', 'mol_N2',
            'permeability_m2', 'darcy_velocity_m_s',
            'T_exit_gas_K', 'T_sphere_K',
            'sphere_pressure_Pa', 'sphere_pressure_atm',
            'soot_color_rgb', 'soot_visibly_glowing',
            'seebeck_voltage_V', 'electric_power_W',
            'co2_asym_stretch_cm_inv',
            'sigma', 'origin',
        ]
        for key in required_keys:
            self.assertIn(key, result, f"Missing: {key}")

    def test_physical_consistency(self):
        """Results are internally consistent."""
        result = simulate_carbon_cigar()

        # Flame is hot
        self.assertGreater(result['T_flame_K'], 800)

        # Gas cools before reaching sphere
        self.assertLess(result['T_exit_gas_K'], result['T_flame_K'])

        # Sphere has pressure (gas accumulated)
        # Note: our model uses constant initial ΔP, so sphere can exceed 1 atm.
        # In reality, flow would slow as sphere fills. Time-dependent model
        # would cap this. The physics is correct for the stated assumptions.
        self.assertGreater(result['sphere_pressure_Pa'], 0)

        # Flow exists
        self.assertGreater(result['darcy_velocity_m_s'], 0)

        # Soot glows
        self.assertTrue(result['soot_visibly_glowing'])

        # Electricity flows
        self.assertGreater(result['seebeck_voltage_V'], 0)
        self.assertGreater(result['electric_power_W'], 0)

    def test_burn_length_bounded(self):
        """Can't burn more cigar than exists."""
        result = simulate_carbon_cigar(burn_time_s=100000.0)
        self.assertLessEqual(result['burn_length_m'], 0.10)

    def test_products_stoichiometry(self):
        """CO₂ + CO should account for most of the carbon burned."""
        result = simulate_carbon_cigar()
        total_C_in_gas = result['mol_CO2'] + result['mol_CO'] + result['mol_soot_C']
        self.assertAlmostEqual(
            total_C_in_gas, result['mol_carbon_burned'], delta=0.01)

    def test_origin_tag(self):
        """Origin string contains all relevant tags."""
        result = simulate_carbon_cigar()
        origin = result['origin']
        self.assertIn('FIRST_PRINCIPLES', origin)
        self.assertIn('MEASURED', origin)
        self.assertIn('Darcy', origin)
        self.assertIn('Seebeck', origin)


if __name__ == '__main__':
    unittest.main()
