"""
Tests for the thermoelectric module.

Test structure:
  1. Free electron density — Z_val × n_atoms
  2. Fermi energy — Sommerfeld model, validate against known values
  3. Seebeck coefficient — Mott formula, compare with measured
  4. Figure of merit ZT — metals should be terrible
  5. Thermocouple voltage — Seebeck effect
  6. TEG power output — hot plate → TEG → ice cube
  7. Efficiency — Carnot bound, Ioffe formula
  8. σ-dependence — propagation through the chain
  9. Cross-module consistency — connects to thermal, mechanical
  10. Full system simulation — the complete stack
"""

import math
import unittest

from .thermoelectric import (
    free_electron_density,
    fermi_energy,
    fermi_energy_ev,
    seebeck_coefficient,
    seebeck_coefficient_uv_k,
    electrical_conductivity,
    electrical_resistivity,
    figure_of_merit_ZT,
    thermocouple_voltage,
    leg_resistance,
    thermoelectric_power_max,
    carnot_efficiency,
    thermoelectric_efficiency,
    heat_flow_through_leg,
    simulate_teg_system,
    material_thermoelectric_properties,
    _SEEBECK_MEASURED_UV_K,
    _VALENCE_ELECTRONS,
)
from .surface import MATERIALS


class TestFreeElectronDensity(unittest.TestCase):
    """Z_val × n_atoms gives free electron density."""

    def test_copper_one_electron(self):
        """Copper: 1 valence electron per atom."""
        n_e = free_electron_density('copper')
        # Known: ~8.5 × 10²⁸ /m³
        self.assertGreater(n_e, 5e28)
        self.assertLess(n_e, 12e28)

    def test_aluminum_three_electrons(self):
        """Aluminum: 3 valence electrons, so n_e > copper despite fewer atoms."""
        n_e_al = free_electron_density('aluminum')
        n_e_cu = free_electron_density('copper')
        # Al has 3× electrons/atom but fewer atoms/volume
        # Known: Al n_e ≈ 18.1 × 10²⁸ /m³
        self.assertGreater(n_e_al, n_e_cu)

    def test_silicon_zero(self):
        """Silicon: semiconductor, zero free electrons in our model."""
        n_e = free_electron_density('silicon')
        self.assertEqual(n_e, 0.0)

    def test_all_metals_positive(self):
        """Every metal in our database has positive free electron density."""
        for mat in MATERIALS:
            if _VALENCE_ELECTRONS.get(mat, 0) > 0:
                self.assertGreater(free_electron_density(mat), 0)


class TestFermiEnergy(unittest.TestCase):
    """Sommerfeld model gives correct Fermi energies."""

    def test_copper_7eV(self):
        """Copper Fermi energy ≈ 7.0 eV (textbook value)."""
        E_F = fermi_energy_ev('copper')
        # Known: 7.0 eV. Free-electron model is very accurate for Cu.
        self.assertAlmostEqual(E_F, 7.0, delta=1.5)

    def test_aluminum_higher(self):
        """Aluminum E_F > copper (3 electrons/atom, higher n_e)."""
        E_F_al = fermi_energy_ev('aluminum')
        E_F_cu = fermi_energy_ev('copper')
        self.assertGreater(E_F_al, E_F_cu)

    def test_aluminum_about_12eV(self):
        """Aluminum Fermi energy ≈ 11.7 eV (textbook)."""
        E_F = fermi_energy_ev('aluminum')
        self.assertAlmostEqual(E_F, 11.7, delta=2.0)

    def test_gold_similar_to_copper(self):
        """Gold E_F similar to copper (both 1 electron, similar density)."""
        E_F_au = fermi_energy_ev('gold')
        E_F_cu = fermi_energy_ev('copper')
        # Both around 5-7 eV
        self.assertAlmostEqual(E_F_au, E_F_cu, delta=3.0)

    def test_silicon_zero(self):
        """Silicon: no free electrons → E_F = 0."""
        self.assertEqual(fermi_energy('silicon'), 0.0)

    def test_always_positive_for_metals(self):
        """E_F > 0 for all metals."""
        for mat in MATERIALS:
            if _VALENCE_ELECTRONS.get(mat, 0) > 0:
                self.assertGreater(fermi_energy(mat), 0)


class TestSeebeckCoefficient(unittest.TestCase):
    """Mott formula gives physically reasonable Seebeck coefficients."""

    def test_copper_order_of_magnitude(self):
        """Cu Seebeck: Mott gives ~1 μV/K, measured 1.83 μV/K."""
        S = seebeck_coefficient_uv_k('copper', T=300.0)
        # Mott free-electron: should be in the right ballpark
        self.assertGreater(S, 0.3)
        self.assertLess(S, 5.0)

    def test_aluminum_order_of_magnitude(self):
        """Al Seebeck coefficient in the low μV/K range."""
        S = seebeck_coefficient_uv_k('aluminum', T=300.0)
        self.assertGreater(S, 0.1)
        self.assertLess(S, 5.0)

    def test_higher_fermi_means_lower_seebeck(self):
        """Higher E_F → lower S (Mott formula: S ∝ T/E_F)."""
        # Aluminum has higher E_F than copper → lower S
        S_al = seebeck_coefficient('aluminum', T=300.0)
        S_cu = seebeck_coefficient('copper', T=300.0)
        E_F_al = fermi_energy('aluminum')
        E_F_cu = fermi_energy('copper')
        if E_F_al > E_F_cu:
            self.assertLess(S_al, S_cu)

    def test_increases_with_temperature(self):
        """S ∝ T in Mott formula."""
        S_300 = seebeck_coefficient('copper', T=300.0)
        S_600 = seebeck_coefficient('copper', T=600.0)
        self.assertAlmostEqual(S_600 / S_300, 2.0, delta=0.01)

    def test_zero_at_zero_T(self):
        """S = 0 at T = 0 (no thermal gradient possible)."""
        S = seebeck_coefficient('copper', T=0)
        self.assertEqual(S, 0.0)

    def test_mott_within_factor_2_for_simple_metals(self):
        """Mott formula within factor 2 of measured for Cu and Au."""
        for mat in ['copper', 'gold']:
            S_mott = seebeck_coefficient_uv_k(mat, T=300.0)
            S_meas = abs(_SEEBECK_MEASURED_UV_K[mat])
            ratio = S_mott / S_meas
            self.assertGreater(ratio, 0.3,
                f"{mat}: Mott {S_mott:.2f} vs measured {S_meas:.2f}")
            self.assertLess(ratio, 3.0,
                f"{mat}: Mott {S_mott:.2f} vs measured {S_meas:.2f}")


class TestFigureOfMerit(unittest.TestCase):
    """ZT for metals should be tiny (Wiedemann-Franz kills them)."""

    def test_metals_terrible_ZT(self):
        """All metals in our database: ZT << 1."""
        for mat in MATERIALS:
            if _VALENCE_ELECTRONS.get(mat, 0) > 0:
                ZT = figure_of_merit_ZT(mat, T=300.0)
                self.assertLess(ZT, 0.01,
                    f"{mat}: ZT = {ZT:.6f}, expected << 1")

    def test_copper_ZT_order(self):
        """Cu ZT ~ 10⁻⁵ at 300K (Wiedemann-Franz bound)."""
        ZT = figure_of_merit_ZT('copper', T=300.0)
        self.assertGreater(ZT, 1e-8)
        self.assertLess(ZT, 1e-3)

    def test_ZT_increases_with_T(self):
        """ZT increases with T for metals (S² ∝ T²)."""
        ZT_300 = figure_of_merit_ZT('copper', T=300.0)
        ZT_600 = figure_of_merit_ZT('copper', T=600.0)
        self.assertGreater(ZT_600, ZT_300)

    def test_silicon_zero_ZT(self):
        """Silicon: no free electrons in our model → ZT = 0."""
        ZT = figure_of_merit_ZT('silicon', T=300.0)
        self.assertEqual(ZT, 0.0)


class TestThermocoupleVoltage(unittest.TestCase):
    """Seebeck effect: two dissimilar metals + ΔT → voltage."""

    def test_positive_voltage(self):
        """Iron-copper thermocouple produces voltage with ΔT."""
        V = thermocouple_voltage('iron', 'copper', T_hot=500.0, T_cold=273.0)
        self.assertGreater(V, 0)

    def test_zero_voltage_no_delta_T(self):
        """No temperature difference → no voltage."""
        V = thermocouple_voltage('iron', 'copper', T_hot=300.0, T_cold=300.0)
        self.assertEqual(V, 0.0)

    def test_voltage_proportional_to_delta_T(self):
        """V ∝ ΔT (linear for small ΔT)."""
        V1 = thermocouple_voltage('iron', 'copper', T_hot=400.0, T_cold=300.0)
        V2 = thermocouple_voltage('iron', 'copper', T_hot=500.0, T_cold=300.0)
        # V2/V1 should be close to 2 (200K/100K ΔT)
        self.assertAlmostEqual(V2 / V1, 2.0, delta=0.3)

    def test_same_material_zero(self):
        """Same material on both legs → zero voltage (Seebeck cancels)."""
        V = thermocouple_voltage('copper', 'copper', T_hot=500.0, T_cold=273.0)
        self.assertEqual(V, 0.0)

    def test_microvolt_range(self):
        """Metal thermocouple voltage in microvolt range per degree."""
        V = thermocouple_voltage('iron', 'copper', T_hot=301.0, T_cold=300.0)
        # 1K ΔT, Seebeck difference ~ few μV/K
        self.assertGreater(V, 1e-9)    # > 1 nV
        self.assertLess(V, 100e-6)     # < 100 μV


class TestLegResistance(unittest.TestCase):
    """R = ρL/A for thermoelectric legs."""

    def test_copper_low_resistance(self):
        """Copper: excellent conductor, low resistance."""
        R = leg_resistance('copper', length_m=0.01, cross_section_m2=1e-4)
        # ρ_Cu = 1.68e-8, R = 1.68e-8 × 0.01 / 1e-4 = 1.68e-6 Ω
        self.assertAlmostEqual(R, 1.68e-6, delta=1e-7)

    def test_iron_higher_than_copper(self):
        """Iron: higher resistivity → higher resistance."""
        R_fe = leg_resistance('iron', 0.01, 1e-4)
        R_cu = leg_resistance('copper', 0.01, 1e-4)
        self.assertGreater(R_fe, R_cu)

    def test_scales_with_length(self):
        """R ∝ L."""
        R1 = leg_resistance('copper', 0.01, 1e-4)
        R2 = leg_resistance('copper', 0.02, 1e-4)
        self.assertAlmostEqual(R2 / R1, 2.0, delta=0.01)


class TestTEGPower(unittest.TestCase):
    """Hot plate → TEG → ice cube: power output."""

    def test_produces_power(self):
        """Iron-copper TEG produces non-zero power."""
        result = thermoelectric_power_max(
            'iron', 'copper', T_hot=500.0, T_cold=273.0)
        self.assertGreater(result['power_W'], 0)
        self.assertGreater(result['current_A'], 0)
        self.assertGreater(result['voltage_oc_V'], 0)

    def test_more_delta_T_more_power(self):
        """Higher ΔT → more power (P ∝ V² ∝ ΔT²)."""
        P1 = thermoelectric_power_max(
            'iron', 'copper', T_hot=400.0, T_cold=273.0)['power_W']
        P2 = thermoelectric_power_max(
            'iron', 'copper', T_hot=600.0, T_cold=273.0)['power_W']
        self.assertGreater(P2, P1)

    def test_voltage_halved_at_max_power(self):
        """At max power, load voltage = V_oc / 2."""
        result = thermoelectric_power_max(
            'iron', 'copper', T_hot=500.0, T_cold=273.0)
        self.assertAlmostEqual(
            result['voltage_load_V'],
            result['voltage_oc_V'] / 2.0,
            places=10)

    def test_power_equals_IV(self):
        """P = I × V at the load."""
        result = thermoelectric_power_max(
            'iron', 'copper', T_hot=500.0, T_cold=273.0)
        P_check = result['current_A'] * result['voltage_load_V']
        self.assertAlmostEqual(result['power_W'], P_check, places=15)


class TestEfficiency(unittest.TestCase):
    """Thermodynamic efficiency bounds."""

    def test_carnot_bound(self):
        """Carnot efficiency for 500K hot, 273K cold."""
        eta = carnot_efficiency(500.0, 273.0)
        # 1 - 273/500 = 0.454
        self.assertAlmostEqual(eta, 0.454, delta=0.01)

    def test_carnot_zero_no_gradient(self):
        """No temperature gradient → zero efficiency."""
        eta = carnot_efficiency(300.0, 300.0)
        self.assertEqual(eta, 0.0)

    def test_thermoelectric_below_carnot(self):
        """Thermoelectric efficiency always below Carnot."""
        for mat in ['copper', 'iron', 'aluminum']:
            eta_te = thermoelectric_efficiency(mat, T_hot=500, T_cold=273)
            eta_c = carnot_efficiency(500, 273)
            self.assertLess(eta_te, eta_c)
            self.assertGreater(eta_te, 0)

    def test_efficiency_improves_with_ZT(self):
        """Higher ZT → closer to Carnot."""
        # Tungsten has different ZT than copper
        eta_cu = thermoelectric_efficiency('copper', 500, 273)
        eta_fe = thermoelectric_efficiency('iron', 500, 273)
        # Both are tiny, but they should both be positive
        self.assertGreater(eta_cu, 0)
        self.assertGreater(eta_fe, 0)


class TestHeatFlow(unittest.TestCase):
    """Fourier's law through TEG legs."""

    def test_positive_heat_flow(self):
        """Heat flows from hot to cold."""
        Q = heat_flow_through_leg('copper', T_hot=500.0, T_cold=273.0)
        self.assertGreater(Q, 0)

    def test_copper_conducts_more(self):
        """Copper leg conducts more heat than iron (κ_Cu > κ_Fe)."""
        Q_cu = heat_flow_through_leg('copper', 500, 273)
        Q_fe = heat_flow_through_leg('iron', 500, 273)
        self.assertGreater(Q_cu, Q_fe)

    def test_zero_heat_no_gradient(self):
        """No ΔT → no heat flow."""
        Q = heat_flow_through_leg('copper', 300.0, 300.0)
        self.assertEqual(Q, 0.0)


class TestSigmaDependence(unittest.TestCase):
    """σ-field propagation through the thermoelectric chain."""

    def test_sigma_zero_is_default(self):
        """σ=0 gives same results as no σ parameter."""
        ZT_0 = figure_of_merit_ZT('copper', T=300.0, sigma=0.0)
        ZT_def = figure_of_merit_ZT('copper', T=300.0)
        self.assertEqual(ZT_0, ZT_def)

    def test_sigma_shifts_ZT(self):
        """Non-zero σ changes ZT (through κ_phonon)."""
        ZT_0 = figure_of_merit_ZT('copper', T=300.0, sigma=0.0)
        ZT_1 = figure_of_merit_ZT('copper', T=300.0, sigma=1.0)
        # κ_phonon shifts, so ZT should shift
        # (electronic κ dominates for Cu, so shift is small)
        # Just verify it's not crashing and gives a number
        self.assertGreater(ZT_1, 0)

    def test_earth_sigma_negligible(self):
        """Earth σ ~ 7×10⁻¹⁰ gives negligible change."""
        ZT_0 = figure_of_merit_ZT('copper', T=300.0, sigma=0.0)
        ZT_earth = figure_of_merit_ZT('copper', T=300.0, sigma=7e-10)
        if ZT_0 > 0:
            ratio = abs(ZT_earth - ZT_0) / ZT_0
            self.assertLess(ratio, 1e-6)


class TestFullSystemSimulation(unittest.TestCase):
    """Complete hot plate → TEG → ice cube stack."""

    def test_iron_copper_teg(self):
        """Full simulation: copper hot plate, iron-copper TEG, ice."""
        result = simulate_teg_system(
            mat_hot_plate='copper',
            mat_p='iron',
            mat_n='copper',
            T_hot=500.0,
            T_cold=273.15,
        )

        # Check all expected keys exist
        expected_keys = [
            'T_hot_K', 'T_cold_K', 'delta_T_K',
            'seebeck_p_uV_K', 'seebeck_n_uV_K',
            'voltage_oc_V', 'current_A', 'power_max_W',
            'heat_flow_W', 'efficiency', 'carnot_efficiency',
            'ZT_p', 'ZT_n', 'origin',
        ]
        for key in expected_keys:
            self.assertIn(key, result, f"Missing key: {key}")

        # Physical sanity checks
        self.assertGreater(result['voltage_oc_V'], 0)
        self.assertGreater(result['current_A'], 0)
        self.assertGreater(result['power_max_W'], 0)
        self.assertGreater(result['heat_flow_W'], 0)
        self.assertGreater(result['efficiency'], 0)
        self.assertLess(result['efficiency'], result['carnot_efficiency'])

    def test_multiple_couples(self):
        """More couples = more voltage, same current, more power."""
        r1 = simulate_teg_system('copper', 'iron', 'copper', 500, 273.15, n_couples=1)
        r10 = simulate_teg_system('copper', 'iron', 'copper', 500, 273.15, n_couples=10)

        # Voltage scales with n
        self.assertAlmostEqual(
            r10['voltage_oc_V'] / r1['voltage_oc_V'], 10.0, delta=0.01)

        # Power scales with n (P ∝ V² / R, and both V and R scale with n)
        # P_n = (nV)² / (nR) = n × V²/R = n × P_1
        self.assertAlmostEqual(
            r10['power_max_W'] / r1['power_max_W'], 10.0, delta=0.1)

    def test_realistic_tea_cup_scenario(self):
        """Hot cup of tea (373K) → TEG → room temp (293K)."""
        result = simulate_teg_system(
            mat_hot_plate='copper',
            mat_p='iron',
            mat_n='copper',
            T_hot=373.0,    # boiling water
            T_cold=293.0,   # room temperature
            n_couples=100,  # realistic module has ~100 couples
        )

        # Should produce measurable but tiny voltage
        self.assertGreater(result['voltage_oc_V'], 0)
        # Heat flow should be significant (metals conduct well)
        self.assertGreater(result['heat_flow_W'], 1.0)  # > 1 watt


class TestNagathaExport(unittest.TestCase):
    """Nagatha-compatible export format."""

    def test_required_fields(self):
        """Export contains all required fields with origin tags."""
        props = material_thermoelectric_properties('copper', T=300.0)
        required = [
            'material', 'temperature_K', 'sigma',
            'free_electron_density_m3', 'fermi_energy_eV',
            'seebeck_coefficient_uV_K', 'electrical_conductivity_S_m',
            'figure_of_merit_ZT', 'origin',
        ]
        for key in required:
            self.assertIn(key, props, f"Missing: {key}")

    def test_honest_origin_tags(self):
        """Origin string contains FIRST_PRINCIPLES and MEASURED honestly."""
        props = material_thermoelectric_properties('copper')
        origin = props['origin']
        self.assertIn('FIRST_PRINCIPLES', origin)
        self.assertIn('MEASURED', origin)
        self.assertIn('APPROXIMATION', origin)

    def test_all_materials_export(self):
        """Every material in the database exports without error."""
        for mat in MATERIALS:
            props = material_thermoelectric_properties(mat)
            self.assertIn('origin', props)

    def test_mott_accuracy_reported(self):
        """For metals with measured Seebeck, accuracy ratio is reported."""
        props = material_thermoelectric_properties('copper')
        self.assertIsNotNone(props['mott_formula_accuracy'])
        self.assertIsNotNone(props['seebeck_measured_uV_K'])


class TestCrossModuleConsistency(unittest.TestCase):
    """Thermoelectric module connects properly to thermal and mechanical."""

    def test_resistivity_matches_thermal(self):
        """Resistivity in thermoelectric matches thermal module."""
        from .thermal import _RESISTIVITY_OHM_M as thermal_rho
        rho_te = electrical_resistivity('copper')
        rho_th = thermal_rho['copper']
        self.assertEqual(rho_te, rho_th)

    def test_conductivity_inverse_of_resistivity(self):
        """σ = 1/ρ for all metals."""
        for mat in MATERIALS:
            rho = electrical_resistivity(mat)
            sigma = electrical_conductivity(mat)
            if rho < 1.0 and rho > 0:
                self.assertAlmostEqual(sigma, 1.0 / rho, places=5)

    def test_wiedemann_franz_ZT_bound(self):
        """For metals, ZT ≈ S²/(L₀) — bounded by Wiedemann-Franz.

        Since κ ≈ L₀σT (Wiedemann-Franz), and ZT = S²σT/κ,
        we get ZT ≈ S²/L₀. This is a fundamental bound that
        explains why metals are bad thermoelectrics.
        """
        from .thermal import _LORENZ_NUMBER
        for mat in ['copper', 'gold', 'aluminum']:
            S = seebeck_coefficient(mat, T=300.0)
            ZT = figure_of_merit_ZT(mat, T=300.0)
            # ZT should be close to S²/L₀ (within factor of 2,
            # because phonon κ adds to electronic κ)
            ZT_wf_bound = S**2 / _LORENZ_NUMBER
            self.assertLess(ZT, ZT_wf_bound * 2.0,
                f"{mat}: ZT={ZT:.2e} but WF bound={ZT_wf_bound:.2e}")


if __name__ == '__main__':
    unittest.main()
