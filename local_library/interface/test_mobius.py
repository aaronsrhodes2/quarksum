"""
Tests for the Möbius conductor topology module.

Test structure:
  1. Geometry — path length, separation
  2. Resistance — DC, parallel, unlike metals
  3. Inductance — single loop, coupling, net (collapsed)
  4. Impedance — frequency sweep, phase collapse
  5. Skin depth — frequency dependence, material dependence
  6. Field cancellation — self-shielding
  7. Bimetallic — Seebeck, current partition
  8. Full analysis — compare Möbius to standard conductor
  9. Parallel pair — inductance, shielding
 10. Coaxial — inductance, Z₀, perfect shielding
 11. Twisted pair — coupling, inductance, field cancellation
 12. Four-topology comparison — head-to-head showdown
"""

import math
import unittest

from .mobius import (
    mobius_path_length,
    conductor_separation,
    conductor_resistance,
    mobius_total_resistance,
    single_loop_inductance,
    coupling_coefficient,
    mobius_net_inductance,
    impedance_magnitude,
    impedance_phase_deg,
    inductance_ratio,
    skin_depth,
    effective_resistance_ac,
    field_cancellation_ratio,
    bimetallic_seebeck_voltage,
    current_partition_ratio,
    analyze_mobius_conductor,
    # Standard cable topologies
    parallel_pair_inductance_per_m,
    parallel_pair_inductance,
    shielded_pair_field_cancellation,
    coaxial_inductance_per_m,
    coaxial_inductance,
    coaxial_characteristic_impedance,
    coaxial_field_cancellation,
    twisted_pair_coupling,
    twisted_pair_inductance_per_m,
    twisted_pair_inductance,
    twisted_pair_field_cancellation,
    compare_topologies,
)


class TestGeometry(unittest.TestCase):
    """Möbius strip geometry."""

    def test_path_length_doubles(self):
        """Conductor goes around twice in a Möbius strip."""
        L = mobius_path_length(0.10)
        self.assertAlmostEqual(L, 0.20, places=10)

    def test_separation_equals_insulator(self):
        """When pressed flat, conductors separated by insulator thickness."""
        d = conductor_separation(100e-6)
        self.assertAlmostEqual(d, 100e-6, places=15)


class TestResistance(unittest.TestCase):
    """DC resistance of Möbius conductors."""

    def test_copper_strip_resistance(self):
        """Copper strip: R = ρL/A."""
        # 20cm path, 1cm wide, 35μm thick
        R = conductor_resistance('copper', 0.20, 0.01, 35e-6)
        # R = 1.68e-8 × 0.20 / (0.01 × 35e-6) = 9.6 mΩ
        self.assertAlmostEqual(R * 1000, 9.6, delta=0.5)

    def test_identical_metals_parallel(self):
        """Two identical conductors in parallel: R_total = R/2."""
        R_total = mobius_total_resistance('copper', 'copper', 0.10, 0.01, 35e-6)
        R_single = conductor_resistance('copper', 0.20, 0.01, 35e-6)
        self.assertAlmostEqual(R_total, R_single / 2.0, places=10)

    def test_iron_higher_resistance(self):
        """Iron has higher resistivity → higher resistance."""
        R_cu = conductor_resistance('copper', 0.20, 0.01, 35e-6)
        R_fe = conductor_resistance('iron', 0.20, 0.01, 35e-6)
        self.assertGreater(R_fe, R_cu)

    def test_unlike_metals_intermediate(self):
        """Cu-Fe parallel resistance: between Cu/2 and Fe/2."""
        R_cu_cu = mobius_total_resistance('copper', 'copper', 0.10, 0.01, 35e-6)
        R_fe_fe = mobius_total_resistance('iron', 'iron', 0.10, 0.01, 35e-6)
        R_cu_fe = mobius_total_resistance('copper', 'iron', 0.10, 0.01, 35e-6)
        self.assertGreater(R_cu_fe, R_cu_cu)
        self.assertLess(R_cu_fe, R_fe_fe)


class TestInductance(unittest.TestCase):
    """Inductance and coupling in the Möbius topology."""

    def test_single_loop_positive(self):
        """Single loop has positive inductance."""
        L = single_loop_inductance(0.10, 0.01)
        self.assertGreater(L, 0)

    def test_coupling_high_for_thin_insulator(self):
        """Thin insulator → coupling coefficient near 1."""
        k = coupling_coefficient(100e-6, 0.01)  # 100μm gap, 1cm width
        self.assertGreater(k, 0.99)

    def test_coupling_lower_for_thick_insulator(self):
        """Thicker insulator → lower coupling."""
        k_thin = coupling_coefficient(100e-6, 0.01)
        k_thick = coupling_coefficient(1e-3, 0.01)
        self.assertGreater(k_thin, k_thick)

    def test_coupling_bounded(self):
        """0 ≤ k ≤ 1."""
        k = coupling_coefficient(100e-6, 0.01)
        self.assertGreaterEqual(k, 0)
        self.assertLessEqual(k, 1)

    def test_mobius_inductance_much_less(self):
        """Möbius net inductance << single loop inductance."""
        L_single = single_loop_inductance(0.10, 0.01)
        L_mobius = mobius_net_inductance(0.10, 0.01, 100e-6)
        self.assertLess(L_mobius, L_single * 0.1)  # at least 10× reduction

    def test_inductance_ratio_small(self):
        """Inductance ratio should be very small for thin insulator."""
        ratio = inductance_ratio(0.10, 0.01, 100e-6)
        self.assertLess(ratio, 0.05)  # less than 5% of single loop

    def test_thinner_insulator_lower_inductance(self):
        """Thinner insulator → better coupling → lower net L."""
        L_100um = mobius_net_inductance(0.10, 0.01, 100e-6)
        L_10um = mobius_net_inductance(0.10, 0.01, 10e-6)
        self.assertLess(L_10um, L_100um)


class TestImpedance(unittest.TestCase):
    """Impedance collapse: AC behaves like DC."""

    def test_dc_impedance_equals_resistance(self):
        """At DC (f=0): |Z| = R."""
        Z = impedance_magnitude(1.0, 1e-6, 0.0)
        self.assertAlmostEqual(Z, 1.0, places=10)

    def test_single_loop_impedance_grows_with_frequency(self):
        """Single loop: |Z| increases with frequency (inductive)."""
        R = 0.01  # 10 mΩ
        L = 1e-7  # 100 nH (typical small loop)
        Z_60 = impedance_magnitude(R, L, 60.0)
        Z_1M = impedance_magnitude(R, L, 1e6)
        self.assertGreater(Z_1M, Z_60)

    def test_mobius_impedance_nearly_flat(self):
        """Möbius: impedance barely changes with frequency."""
        R = 0.005  # 5 mΩ (parallel Cu)
        L_mobius = mobius_net_inductance(0.10, 0.01, 100e-6)

        Z_60 = impedance_magnitude(R, L_mobius, 60.0)
        Z_1M = impedance_magnitude(R, L_mobius, 1e6)

        # Should be nearly the same (both ≈ R)
        ratio = Z_1M / Z_60
        self.assertAlmostEqual(ratio, 1.0, delta=0.5)

    def test_phase_near_zero_for_mobius(self):
        """Möbius: phase angle near 0° (resistive) even at high frequency."""
        R = 0.005
        L_mobius = mobius_net_inductance(0.10, 0.01, 100e-6)
        phase = impedance_phase_deg(R, L_mobius, 1e6)
        self.assertLess(abs(phase), 45.0)  # well below 90°

    def test_single_loop_phase_large_at_high_f(self):
        """Single loop: phase angle approaches 90° at high frequency."""
        R = 0.01
        L_single = single_loop_inductance(0.10, 0.01)
        phase = impedance_phase_deg(R, L_single, 1e9)
        self.assertGreater(phase, 45.0)


class TestSkinDepth(unittest.TestCase):
    """Frequency-dependent current penetration."""

    def test_copper_60Hz(self):
        """Cu at 60Hz: δ ≈ 8.5 mm."""
        delta = skin_depth('copper', 60.0)
        self.assertAlmostEqual(delta * 1000, 8.5, delta=1.0)

    def test_copper_1MHz(self):
        """Cu at 1MHz: δ ≈ 66 μm."""
        delta = skin_depth('copper', 1e6)
        self.assertAlmostEqual(delta * 1e6, 66, delta=10)

    def test_decreases_with_frequency(self):
        """Skin depth ∝ 1/√f."""
        d_1k = skin_depth('copper', 1e3)
        d_1M = skin_depth('copper', 1e6)
        ratio = d_1k / d_1M
        self.assertAlmostEqual(ratio, math.sqrt(1e3), delta=1.0)

    def test_iron_thinner_skin(self):
        """Iron: higher resistivity → different skin depth than copper."""
        # Actually: δ = √(2ρ/ωμ₀), higher ρ → larger δ for non-magnetic
        # Iron is ferromagnetic (μ_r >> 1) but we don't model that yet
        # In our model (μ_r = 1): iron has larger δ due to higher ρ
        d_cu = skin_depth('copper', 1e6)
        d_fe = skin_depth('iron', 1e6)
        # ρ_Fe/ρ_Cu ≈ 5.8, so δ_Fe/δ_Cu ≈ √5.8 ≈ 2.4
        self.assertGreater(d_fe, d_cu)

    def test_ac_resistance_increases(self):
        """AC resistance ≥ DC resistance (skin effect)."""
        R_dc = conductor_resistance('copper', 0.20, 0.01, 35e-6)
        R_ac = effective_resistance_ac('copper', 0.20, 0.01, 35e-6, 1e6)
        self.assertGreaterEqual(R_ac, R_dc * 0.99)  # allow tiny float error


class TestFieldCancellation(unittest.TestCase):
    """Self-shielding from counter-flowing currents."""

    def test_far_field_cancellation(self):
        """At 10× separation: 90% field reduction."""
        ratio = field_cancellation_ratio(1e-3, 100e-6)
        self.assertAlmostEqual(ratio, 0.1, delta=0.01)

    def test_better_at_greater_distance(self):
        """Further away → more cancellation."""
        r_close = field_cancellation_ratio(1e-3, 100e-6)
        r_far = field_cancellation_ratio(10e-3, 100e-6)
        self.assertLess(r_far, r_close)

    def test_no_cancellation_in_near_field(self):
        """Inside the conductor pair: no cancellation."""
        ratio = field_cancellation_ratio(50e-6, 100e-6)
        self.assertEqual(ratio, 1.0)

    def test_tighter_spacing_better_shielding(self):
        """Closer conductors → better far-field cancellation."""
        r_100 = field_cancellation_ratio(1e-3, 100e-6)
        r_10 = field_cancellation_ratio(1e-3, 10e-6)
        self.assertLess(r_10, r_100)


class TestBimetallic(unittest.TestCase):
    """Unlike metals: Seebeck and current partition."""

    def test_seebeck_voltage_with_delta_T(self):
        """Cu-Fe bimetallic with ΔT produces voltage."""
        V = bimetallic_seebeck_voltage('copper', 'iron', 400.0, 300.0)
        self.assertGreater(V, 0)

    def test_no_seebeck_same_metal(self):
        """Same metal: no Seebeck voltage (ΔS = 0)."""
        V = bimetallic_seebeck_voltage('copper', 'copper', 400.0, 300.0)
        self.assertEqual(V, 0.0)

    def test_no_seebeck_no_delta_T(self):
        """No temperature difference: no voltage."""
        V = bimetallic_seebeck_voltage('copper', 'iron', 300.0, 300.0)
        self.assertEqual(V, 0.0)

    def test_current_partition_equal_for_same_metal(self):
        """Same metal: 50/50 current split."""
        frac = current_partition_ratio('copper', 'copper', 1e6, 35e-6)
        self.assertAlmostEqual(frac, 0.5, delta=0.001)

    def test_current_favors_better_conductor(self):
        """Cu carries more current than Fe at all frequencies."""
        frac_cu = current_partition_ratio('copper', 'iron', 1e6, 35e-6)
        self.assertGreater(frac_cu, 0.5)


class TestFullAnalysis(unittest.TestCase):
    """Complete Möbius conductor analysis."""

    def test_copper_mobius_all_keys(self):
        """Full analysis returns all expected keys."""
        result = analyze_mobius_conductor()
        required = [
            'mat_A', 'mat_B', 'path_length_m',
            'R_A_ohm', 'R_B_ohm', 'R_parallel_ohm',
            'L_single_H', 'L_mobius_H', 'coupling_coefficient',
            'inductance_ratio', 'frequency_analysis', 'origin',
        ]
        for key in required:
            self.assertIn(key, result, f"Missing: {key}")

    def test_impedance_reduction_at_high_f(self):
        """Möbius should show significant impedance reduction at high f."""
        result = analyze_mobius_conductor()
        # Find the 1 MHz analysis
        for fa in result['frequency_analysis']:
            if fa['frequency_hz'] == 1e6:
                self.assertGreater(fa['impedance_reduction'], 0)
                break

    def test_bimetallic_flag(self):
        """Bimetallic flag set correctly."""
        result_same = analyze_mobius_conductor(mat_A='copper', mat_B='copper')
        result_diff = analyze_mobius_conductor(mat_A='copper', mat_B='iron')
        self.assertFalse(result_same['bimetallic'])
        self.assertTrue(result_diff['bimetallic'])

    def test_bimetallic_seebeck(self):
        """Cu-Fe Möbius with ΔT generates Seebeck voltage."""
        result = analyze_mobius_conductor(
            mat_A='copper', mat_B='iron',
            T_hot=400.0, T_cold=300.0)
        self.assertGreater(result['seebeck_voltage_V'], 0)

    def test_origin_honest(self):
        """Origin tags include FIRST_PRINCIPLES and MEASURED."""
        result = analyze_mobius_conductor()
        self.assertIn('FIRST_PRINCIPLES', result['origin'])
        self.assertIn('MEASURED', result['origin'])
        self.assertIn('APPROXIMATION', result['origin'])

    def test_four_frequencies_analyzed(self):
        """Default: 4 frequencies (60Hz, 1kHz, 1MHz, 1GHz)."""
        result = analyze_mobius_conductor()
        self.assertEqual(len(result['frequency_analysis']), 4)


class TestParallelPair(unittest.TestCase):
    """Shielded parallel wire pair."""

    def test_inductance_positive(self):
        """Parallel pair has positive inductance."""
        L = parallel_pair_inductance_per_m(0.5e-3, 2.0e-3)
        self.assertGreater(L, 0)

    def test_inductance_scales_with_length(self):
        """Total inductance = per-meter × length."""
        Lpm = parallel_pair_inductance_per_m(0.5e-3, 2.0e-3)
        L_total = parallel_pair_inductance(0.5e-3, 2.0e-3, 3.0)
        self.assertAlmostEqual(L_total, Lpm * 3.0, places=12)

    def test_wider_spacing_more_inductance(self):
        """Greater separation → more inductance (more flux area)."""
        L_close = parallel_pair_inductance_per_m(0.5e-3, 1.5e-3)
        L_far = parallel_pair_inductance_per_m(0.5e-3, 5.0e-3)
        self.assertGreater(L_far, L_close)

    def test_inductance_known_value(self):
        """L/ℓ = (μ₀/π)ln(d/r) for known geometry."""
        # r=0.5mm, d=2mm: ln(4) = 1.386
        # L/ℓ = 4π×10⁻⁷ / π × 1.386 = 5.545×10⁻⁷ H/m
        Lpm = parallel_pair_inductance_per_m(0.5e-3, 2.0e-3)
        expected = 4e-7 * math.log(4.0)  # μ₀/π × ln(d/r)
        self.assertAlmostEqual(Lpm, expected, places=12)

    def test_shield_transparent_at_dc(self):
        """At DC: shield does nothing (no changing flux)."""
        ratio = shielded_pair_field_cancellation(0.1, 0.1e-3, 0.0)
        self.assertEqual(ratio, 1.0)

    def test_shield_effective_at_high_frequency(self):
        """At high frequency: shield attenuates strongly."""
        ratio = shielded_pair_field_cancellation(0.1, 0.1e-3, 1e6)
        self.assertLess(ratio, 0.5)  # significant attenuation

    def test_thicker_shield_better(self):
        """Thicker shield → more attenuation."""
        r_thin = shielded_pair_field_cancellation(0.1, 0.05e-3, 1e6)
        r_thick = shielded_pair_field_cancellation(0.1, 0.5e-3, 1e6)
        self.assertLess(r_thick, r_thin)


class TestCoaxial(unittest.TestCase):
    """Coaxial cable properties."""

    def test_inductance_positive(self):
        """Coax has positive inductance between conductors."""
        L = coaxial_inductance_per_m(0.5e-3, 1.5e-3)
        self.assertGreater(L, 0)

    def test_inductance_scales_with_length(self):
        """Total inductance = per-meter × length."""
        Lpm = coaxial_inductance_per_m(0.5e-3, 1.5e-3)
        L_total = coaxial_inductance(0.5e-3, 1.5e-3, 2.5)
        self.assertAlmostEqual(L_total, Lpm * 2.5, places=12)

    def test_inductance_known_value(self):
        """L/ℓ = (μ₀/2π)ln(D/d) for known geometry."""
        # d=0.5mm, D=1.5mm: ln(3) = 1.0986
        # L/ℓ = 4π×10⁻⁷ / (2π) × 1.0986 = 2×10⁻⁷ × 1.0986 = 2.197×10⁻⁷ H/m
        Lpm = coaxial_inductance_per_m(0.5e-3, 1.5e-3)
        expected = 2e-7 * math.log(3.0)
        self.assertAlmostEqual(Lpm, expected, places=12)

    def test_coax_less_inductance_than_parallel(self):
        """Coax (D/d=3) has less inductance than parallel pair (d/r=4)."""
        L_coax = coaxial_inductance_per_m(0.5e-3, 1.5e-3)
        L_pp = parallel_pair_inductance_per_m(0.5e-3, 2.0e-3)
        self.assertLess(L_coax, L_pp)

    def test_characteristic_impedance_50ohm(self):
        """RG-58: Z₀ ≈ 50Ω (d=0.45mm, D=1.47mm, ε_r=2.3)."""
        Z0 = coaxial_characteristic_impedance(0.45e-3, 1.47e-3, 2.3)
        self.assertAlmostEqual(Z0, 50.0, delta=5.0)

    def test_characteristic_impedance_75ohm(self):
        """RG-59: Z₀ ≈ 75Ω (d=0.32mm, D=1.85mm, ε_r=2.3)."""
        Z0 = coaxial_characteristic_impedance(0.32e-3, 1.85e-3, 2.3)
        self.assertAlmostEqual(Z0, 75.0, delta=10.0)

    def test_perfect_shielding(self):
        """Coax has zero external field (ideal solid shield)."""
        fc = coaxial_field_cancellation(0.1)
        self.assertEqual(fc, 0.0)

    def test_perfect_shielding_any_distance(self):
        """Coax shielding is distance-independent."""
        fc_near = coaxial_field_cancellation(0.001)
        fc_far = coaxial_field_cancellation(100.0)
        self.assertEqual(fc_near, fc_far)


class TestTwistedPair(unittest.TestCase):
    """Twisted pair cable properties."""

    def test_coupling_increases_with_twist(self):
        """More twists → higher coupling."""
        k_loose = twisted_pair_coupling(50.0, 1.5e-3)
        k_tight = twisted_pair_coupling(300.0, 1.5e-3)
        self.assertGreater(k_tight, k_loose)

    def test_coupling_bounded(self):
        """0 ≤ k ≤ 1."""
        k = twisted_pair_coupling(200.0, 1.5e-3)
        self.assertGreaterEqual(k, 0)
        self.assertLessEqual(k, 1)

    def test_no_twist_no_coupling(self):
        """Zero twists → k = 0 (just a parallel pair)."""
        k = twisted_pair_coupling(0.0, 1.5e-3)
        self.assertEqual(k, 0.0)

    def test_inductance_less_than_parallel(self):
        """Twisted pair inductance < parallel pair (twist reduces L)."""
        L_pp = parallel_pair_inductance_per_m(0.5e-3, 1.5e-3)
        L_tp = twisted_pair_inductance_per_m(0.5e-3, 1.5e-3, 200.0)
        self.assertLess(L_tp, L_pp)

    def test_inductance_scales_with_length(self):
        """Total inductance = per-meter × length."""
        Lpm = twisted_pair_inductance_per_m(0.5e-3, 1.5e-3, 200.0)
        L_total = twisted_pair_inductance(0.5e-3, 1.5e-3, 200.0, 4.0)
        self.assertAlmostEqual(L_total, Lpm * 4.0, places=12)

    def test_tighter_twist_lower_inductance(self):
        """More twists → lower inductance."""
        L_50 = twisted_pair_inductance_per_m(0.5e-3, 1.5e-3, 50.0)
        L_300 = twisted_pair_inductance_per_m(0.5e-3, 1.5e-3, 300.0)
        self.assertLess(L_300, L_50)

    def test_field_cancellation_near_field(self):
        """Inside the wire pair: no cancellation."""
        fc = twisted_pair_field_cancellation(0.5e-3, 1.5e-3, 200.0)
        self.assertEqual(fc, 1.0)

    def test_field_cancellation_far_field(self):
        """At distance: twisted pair cancels field."""
        fc = twisted_pair_field_cancellation(0.1, 1.5e-3, 200.0)
        self.assertLess(fc, 0.1)  # good cancellation at 10cm

    def test_more_twists_better_cancellation(self):
        """Higher twist rate → better far-field cancellation."""
        fc_loose = twisted_pair_field_cancellation(0.1, 1.5e-3, 50.0)
        fc_tight = twisted_pair_field_cancellation(0.1, 1.5e-3, 300.0)
        self.assertLess(fc_tight, fc_loose)


class TestTopologyComparison(unittest.TestCase):
    """Head-to-head four-topology showdown."""

    def test_all_keys_present(self):
        """Comparison returns all expected keys."""
        result = compare_topologies()
        required = [
            'length_m', 'material',
            'R_parallel_pair_ohm', 'R_coaxial_ohm',
            'R_twisted_pair_ohm', 'R_mobius_ohm',
            'L_parallel_pair_H', 'L_coaxial_H',
            'L_twisted_pair_H', 'L_mobius_H',
            'coax_Z0_ohm', 'twisted_pair_coupling', 'mobius_coupling',
            'frequency_sweep', 'origin',
        ]
        for key in required:
            self.assertIn(key, result, f"Missing: {key}")

    def test_frequency_sweep_has_entries(self):
        """Default sweep has 8 frequencies."""
        result = compare_topologies()
        self.assertEqual(len(result['frequency_sweep']), 8)

    def test_sweep_entry_has_all_topologies(self):
        """Each sweep entry contains data for all four topologies."""
        result = compare_topologies()
        entry = result['frequency_sweep'][0]
        for prefix in ['Z_parallel_pair', 'Z_coaxial', 'Z_twisted_pair', 'Z_mobius']:
            self.assertIn(f'{prefix}_ohm', entry)
        for prefix in ['phase_parallel_pair', 'phase_coaxial',
                        'phase_twisted_pair', 'phase_mobius']:
            self.assertIn(f'{prefix}_deg', entry)
        for prefix in ['field_cancel_parallel_pair', 'field_cancel_coaxial',
                        'field_cancel_twisted_pair', 'field_cancel_mobius']:
            self.assertIn(prefix, entry)

    def test_mobius_lowest_inductance(self):
        """Möbius has the lowest inductance of all four topologies."""
        result = compare_topologies()
        L_mob = result['L_mobius_H']
        self.assertLess(L_mob, result['L_parallel_pair_H'])
        self.assertLess(L_mob, result['L_coaxial_H'])
        self.assertLess(L_mob, result['L_twisted_pair_H'])

    def test_coax_perfect_shielding(self):
        """Coax has zero field cancellation ratio at all frequencies."""
        result = compare_topologies()
        for entry in result['frequency_sweep']:
            self.assertEqual(entry['field_cancel_coaxial'], 0.0)

    def test_mobius_flattest_impedance(self):
        """Möbius impedance changes least from low to high frequency."""
        result = compare_topologies()
        sweep = result['frequency_sweep']
        # Compare 60Hz to 1GHz
        low = sweep[0]   # 60 Hz
        high = sweep[-1]  # 1 GHz

        ratio_pp = high['Z_parallel_pair_ohm'] / low['Z_parallel_pair_ohm']
        ratio_coax = high['Z_coaxial_ohm'] / low['Z_coaxial_ohm']
        ratio_tp = high['Z_twisted_pair_ohm'] / low['Z_twisted_pair_ohm']
        ratio_mob = high['Z_mobius_ohm'] / low['Z_mobius_ohm']

        # Möbius ratio should be closest to 1.0 (flattest)
        self.assertLess(ratio_mob, ratio_pp)
        self.assertLess(ratio_mob, ratio_coax)
        self.assertLess(ratio_mob, ratio_tp)

    def test_mobius_lowest_phase_at_high_f(self):
        """Möbius has lowest phase angle at high frequency (most resistive)."""
        result = compare_topologies()
        # At 1 GHz
        high = result['frequency_sweep'][-1]
        phase_mob = abs(high['phase_mobius_deg'])
        self.assertLess(phase_mob, abs(high['phase_parallel_pair_deg']))
        self.assertLess(phase_mob, abs(high['phase_coaxial_deg']))
        self.assertLess(phase_mob, abs(high['phase_twisted_pair_deg']))

    def test_all_resistances_positive(self):
        """All topologies have positive DC resistance."""
        result = compare_topologies()
        self.assertGreater(result['R_parallel_pair_ohm'], 0)
        self.assertGreater(result['R_coaxial_ohm'], 0)
        self.assertGreater(result['R_twisted_pair_ohm'], 0)
        self.assertGreater(result['R_mobius_ohm'], 0)

    def test_coax_characteristic_impedance_reasonable(self):
        """Coax Z₀ is in a reasonable range (20-100 Ω)."""
        result = compare_topologies()
        Z0 = result['coax_Z0_ohm']
        self.assertGreater(Z0, 20)
        self.assertLess(Z0, 100)

    def test_origin_covers_all_topologies(self):
        """Origin string mentions all four topologies."""
        result = compare_topologies()
        origin = result['origin']
        self.assertIn('Parallel pair', origin)
        self.assertIn('Coaxial', origin)
        self.assertIn('Twisted pair', origin)
        self.assertIn('Möbius', origin)
        self.assertIn('FIRST_PRINCIPLES', origin)
        self.assertIn('MEASURED', origin)


# ══════════════════════════════════════════════════════════════════
# NUMERICAL ANCHOR TESTS — physics validated against known values
# ══════════════════════════════════════════════════════════════════

class TestShieldedPairKnownValues(unittest.TestCase):
    """Shielding effectiveness: validate e^(-t/δ) against known dB values.

    Shielding effectiveness SE = 20 log₁₀(1/ratio) = 8.686 × t/δ dB

    Known: copper shield, 0.1mm thick, at 1 MHz
      δ_Cu @ 1MHz ≈ 66 μm
      t/δ = 100/66 ≈ 1.515
      ratio = e^(-1.515) ≈ 0.220
      SE ≈ 13.2 dB

    INDEPENDENCE RULE: validated against textbook EM shielding formulas.
    """

    def test_copper_shield_1mhz_known_attenuation(self):
        """0.1mm Cu shield at 1MHz: ~13 dB shielding (ratio ≈ 0.22)."""
        ratio = shielded_pair_field_cancellation(0.1, 0.1e-3, 1e6, 'copper')
        # δ_Cu @ 1MHz ≈ 66μm, t=100μm, t/δ ≈ 1.52, e^(-1.52) ≈ 0.22
        self.assertAlmostEqual(ratio, 0.22, delta=0.05)

    def test_thick_shield_high_freq_strong_attenuation(self):
        """1mm Cu shield at 100MHz: should be < 0.001 (>60 dB).

        δ_Cu @ 100MHz ≈ 6.6μm, t=1000μm, t/δ ≈ 152
        ratio = e^(-152) ≈ 0 (essentially perfect)
        """
        ratio = shielded_pair_field_cancellation(0.1, 1e-3, 100e6, 'copper')
        self.assertLess(ratio, 1e-10)

    def test_shielding_dB_formula_consistency(self):
        """SE_dB = -20 log₁₀(ratio) should match 8.686 × t/δ."""
        ratio = shielded_pair_field_cancellation(0.1, 0.1e-3, 1e6, 'copper')
        SE_from_ratio = -20.0 * math.log10(ratio) if ratio > 0 else float('inf')
        # Also compute from skin depth directly
        delta = skin_depth('copper', 1e6)
        SE_from_formula = 8.686 * (0.1e-3 / delta)
        self.assertAlmostEqual(SE_from_ratio, SE_from_formula, delta=0.5)


class TestTwistedPairKnownValues(unittest.TestCase):
    """Twisted pair: validate coupling against Cat5/Cat6 specs.

    Cat5e: ~2 twists/cm = 200 twists/m, wire spacing ~1mm
    Cat6:  ~2.5 twists/cm = 250 twists/m, wire spacing ~1mm

    The coupling model: k = 1 - 1/(1 + (2π×n×d)²)

    For Cat5 (n=200, d=1mm):
      x = 2π × 200 × 0.001 = 1.257
      k = 1 - 1/(1 + 1.581) = 1 - 0.387 = 0.613

    For Cat6 (n=250, d=1mm):
      x = 2π × 250 × 0.001 = 1.571
      k = 1 - 1/(1 + 2.467) = 1 - 0.288 = 0.712

    Cat6 should have higher coupling than Cat5.

    INDEPENDENCE RULE: validated against direct formula evaluation.
    """

    def test_cat5_coupling_value(self):
        """Cat5e (200 twists/m, 1mm spacing): k ≈ 0.61."""
        k = twisted_pair_coupling(200.0, 1.0e-3)
        x = 2.0 * math.pi * 200.0 * 1.0e-3
        expected = 1.0 - 1.0 / (1.0 + x**2)
        self.assertAlmostEqual(k, expected, places=10)
        self.assertAlmostEqual(k, 0.613, delta=0.01)

    def test_cat6_coupling_value(self):
        """Cat6 (250 twists/m, 1mm spacing): k ≈ 0.71."""
        k = twisted_pair_coupling(250.0, 1.0e-3)
        self.assertAlmostEqual(k, 0.712, delta=0.01)

    def test_cat6_higher_coupling_than_cat5(self):
        """Cat6 has tighter twist → higher coupling than Cat5."""
        k5 = twisted_pair_coupling(200.0, 1.0e-3)
        k6 = twisted_pair_coupling(250.0, 1.0e-3)
        self.assertGreater(k6, k5)

    def test_cat5_inductance_reduction(self):
        """Cat5 reduces inductance to ~39% of parallel pair.

        L_tp = L_pp × (1-k) = L_pp × 0.387
        """
        L_pp = parallel_pair_inductance_per_m(0.25e-3, 1.0e-3)
        L_tp = twisted_pair_inductance_per_m(0.25e-3, 1.0e-3, 200.0)
        k = twisted_pair_coupling(200.0, 1.0e-3)
        self.assertAlmostEqual(L_tp / L_pp, 1.0 - k, places=10)

    def test_twisted_pair_field_cancel_numerical(self):
        """At 10cm, Cat5 (200 twists/m, 1mm): ratio = d/r × twist_factor.

        dipole_cancel = 0.001 / 0.1 = 0.01
        twist_factor = 1/(1 + 200 × 0.001) = 1/1.2 = 0.833
        total = 0.01 × 0.833 ≈ 0.0083
        """
        fc = twisted_pair_field_cancellation(0.1, 1.0e-3, 200.0)
        expected = (1.0e-3 / 0.1) * (1.0 / (1.0 + 200.0 * 1.0e-3))
        self.assertAlmostEqual(fc, expected, places=6)


if __name__ == '__main__':
    unittest.main()
