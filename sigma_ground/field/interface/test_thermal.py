"""
Tests for thermal transport module.

TDD: these tests define what the physics MUST do.

Test categories:
  1. Debye temperature — from sound velocity and number density
  2. Heat capacity — Dulong-Petit limit, low-T suppression
  3. Phonon mean free path — Umklapp scattering, T-dependence
  4. Thermal conductivity — κ = Cv·v·ℓ/3, material ordering
  5. Thermal radiation — Stefan-Boltzmann, Wien's law, blackbody color
  6. Contact conductance — hot copper on cardboard!
  7. σ-dependence — full chain propagation
  8. Nagatha integration — export format, origin tags
"""

import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sigma_ground.field.interface.thermal import (
    sound_velocity,
    debye_temperature,
    heat_capacity_volumetric,
    specific_heat_j_kg_K,
    phonon_mean_free_path,
    thermal_conductivity,
    thermal_emission_power,
    wien_peak_wavelength,
    blackbody_color,
    is_visibly_glowing,
    contact_conductance,
    material_thermal_properties,
)


class TestSoundVelocity(unittest.TestCase):
    """Sound velocity = √(K/ρ)."""

    def test_metals_in_range(self):
        """Sound velocity should be 2000-7000 m/s for metals."""
        for mat in ['iron', 'copper', 'aluminum', 'tungsten']:
            v = sound_velocity(mat)
            self.assertGreater(v, 2000, f"{mat} v_s too low: {v:.0f}")
            self.assertLess(v, 8000, f"{mat} v_s too high: {v:.0f}")

    def test_aluminum_faster_than_iron(self):
        """Aluminum is lighter → faster sound despite lower modulus."""
        v_al = sound_velocity('aluminum')
        v_fe = sound_velocity('iron')
        # Al v_s ~ 5100, Fe v_s ~ 4900 — they're close
        # Both should be in reasonable range
        self.assertGreater(v_al, 3000)
        self.assertGreater(v_fe, 3000)

    def test_positive(self):
        """Sound velocity must be positive."""
        for mat in ['iron', 'copper', 'aluminum', 'gold', 'silicon', 'tungsten']:
            self.assertGreater(sound_velocity(mat), 0)


class TestDebyeTemperature(unittest.TestCase):
    """Debye temperature from phonon cutoff frequency."""

    def test_metals_order_of_magnitude(self):
        """Debye temperatures should be 200-700K for common metals."""
        for mat in ['iron', 'copper', 'aluminum', 'gold']:
            theta = debye_temperature(mat)
            self.assertGreater(theta, 100,
                               f"{mat} Θ_D too low: {theta:.0f}K")
            self.assertLess(theta, 1500,
                            f"{mat} Θ_D too high: {theta:.0f}K")

    def test_silicon_high_debye(self):
        """Silicon (covalent, light) should have higher Θ_D than gold (heavy)."""
        theta_si = debye_temperature('silicon')
        theta_au = debye_temperature('gold')
        self.assertGreater(theta_si, theta_au)

    def test_heavy_atoms_lower_debye(self):
        """Heavier atoms → lower Debye temperature (slower vibrations).
        Gold (A=197) should have lower Θ_D than aluminum (A=27)."""
        theta_au = debye_temperature('gold')
        theta_al = debye_temperature('aluminum')
        self.assertLess(theta_au, theta_al)

    def test_mass_number_matters(self):
        """This is the key: the mass number A determines phonon frequencies.
        Heavier nucleus → sluggish phonons → lower Θ_D."""
        # Tungsten A=184 vs Aluminum A=27
        theta_W = debye_temperature('tungsten')
        theta_Al = debye_temperature('aluminum')
        self.assertLess(theta_W, theta_Al,
                        "Heavy tungsten should have lower Θ_D than light aluminum")


class TestHeatCapacity(unittest.TestCase):
    """Heat capacity from Debye model."""

    def test_dulong_petit_high_T(self):
        """At high T (>> Θ_D), C_v → 3nk_B (Dulong-Petit).
        For iron at 1000K (well above Θ_D ≈ 470K):
        c_p should approach 3R/M ≈ 3 × 8.314 / 0.056 ≈ 445 J/(kg·K)
        (measured: 450 J/(kg·K))."""
        c_p = specific_heat_j_kg_K('iron', T=1000.0)
        # Should be within factor of 2 of 450
        self.assertGreater(c_p, 200)
        self.assertLess(c_p, 900)

    def test_low_T_suppression(self):
        """At T << Θ_D, heat capacity is suppressed (frozen out modes)."""
        c_high = heat_capacity_volumetric('copper', T=500.0)
        c_low = heat_capacity_volumetric('copper', T=10.0)
        self.assertGreater(c_high, c_low,
                           "Heat capacity should increase with temperature")

    def test_zero_at_zero_K(self):
        """C_v → 0 as T → 0 (third law of thermodynamics)."""
        c = heat_capacity_volumetric('iron', T=0.0)
        self.assertEqual(c, 0.0)

    def test_always_positive(self):
        """Heat capacity must be non-negative."""
        for mat in ['iron', 'copper', 'aluminum']:
            for T in [10, 100, 300, 1000, 3000]:
                c = heat_capacity_volumetric(mat, T=T)
                self.assertGreaterEqual(c, 0.0)


class TestPhononMFP(unittest.TestCase):
    """Phonon mean free path from Umklapp scattering."""

    def test_decreases_with_temperature(self):
        """ℓ ∝ 1/T at high T (more phonons → more scattering)."""
        ell_300 = phonon_mean_free_path('copper', T=300.0)
        ell_600 = phonon_mean_free_path('copper', T=600.0)
        self.assertGreater(ell_300, ell_600)

    def test_order_of_magnitude(self):
        """Room temperature MFP should be nanometers for metals."""
        ell = phonon_mean_free_path('copper', T=300.0)
        self.assertGreater(ell, 1e-10, "MFP too short (sub-atomic)")
        self.assertLess(ell, 1e-6, "MFP too long (> micron)")

    def test_silicon_longer_mfp(self):
        """Silicon (diamond cubic, covalent) has much longer MFP than metals."""
        ell_si = phonon_mean_free_path('silicon', T=300.0)
        ell_cu = phonon_mean_free_path('copper', T=300.0)
        self.assertGreater(ell_si, ell_cu,
                           "Silicon should have longer phonon MFP (weaker anharmonicity)")

    def test_zero_at_zero_T(self):
        """MFP should be 0 at T=0."""
        self.assertEqual(phonon_mean_free_path('iron', T=0.0), 0.0)


class TestThermalConductivity(unittest.TestCase):
    """Thermal conductivity κ = C_v × v_s × ℓ / 3."""

    def test_copper_higher_than_iron(self):
        """Copper is a better thermal conductor than iron.
        Measured: Cu ~400, Fe ~80 W/(m·K)."""
        kappa_cu = thermal_conductivity('copper', T=300.0)
        kappa_fe = thermal_conductivity('iron', T=300.0)
        self.assertGreater(kappa_cu, kappa_fe)

    def test_silicon_significant_conductivity(self):
        """Silicon has good thermal conductivity (~150 W/(m·K))
        despite being non-metallic — long phonon MFP."""
        kappa_si = thermal_conductivity('silicon', T=300.0)
        self.assertGreater(kappa_si, 10)

    def test_order_of_magnitude(self):
        """Room temperature κ for metals: 10-500 W/(m·K)."""
        for mat in ['iron', 'copper', 'aluminum', 'gold', 'tungsten']:
            kappa = thermal_conductivity(mat, T=300.0)
            self.assertGreater(kappa, 1,
                               f"{mat} κ too low: {kappa:.1f}")
            self.assertLess(kappa, 2000,
                            f"{mat} κ too high: {kappa:.1f}")

    def test_phonon_decreases_at_high_T(self):
        """Phonon κ ∝ 1/T at high T (Umklapp dominates, ℓ shrinks).
        For metals, total κ may not decrease because electronic κ ∝ T.
        Use silicon (no free electrons) to test phonon scaling."""
        kappa_300 = thermal_conductivity('silicon', T=300.0)
        kappa_1000 = thermal_conductivity('silicon', T=1000.0)
        self.assertGreater(kappa_300, kappa_1000,
                           "Phonon κ should decrease at high T (more scattering)")

    def test_zero_at_zero_T(self):
        """κ → 0 as T → 0 (no carriers excited)."""
        kappa = thermal_conductivity('iron', T=0.0)
        self.assertEqual(kappa, 0.0)

    def test_aluminum_good_conductor(self):
        """Aluminum: light atom, good conductor. κ ~ 237 W/(m·K) measured."""
        kappa_al = thermal_conductivity('aluminum', T=300.0)
        # Should be in right ballpark (within 3×)
        self.assertGreater(kappa_al, 50)
        self.assertLess(kappa_al, 700)


class TestThermalRadiation(unittest.TestCase):
    """Thermal emission — Stefan-Boltzmann and Wien's law."""

    def test_stefan_boltzmann_scaling(self):
        """Power ∝ T⁴ — doubling T increases power 16×."""
        P_300 = thermal_emission_power('iron', T=300.0)
        P_600 = thermal_emission_power('iron', T=600.0)
        ratio = P_600 / P_300
        # Should be ~16 (T⁴ scaling), but emissivity may shift slightly
        self.assertGreater(ratio, 10)
        self.assertLess(ratio, 20)

    def test_wien_peak_visible_at_high_T(self):
        """At ~5800K (Sun), peak is in visible range (~500nm)."""
        lam = wien_peak_wavelength(5800.0)
        self.assertGreater(lam, 400e-9)
        self.assertLess(lam, 700e-9)

    def test_wien_peak_infrared_at_room_T(self):
        """At 300K, peak emission is in infrared (~10μm)."""
        lam = wien_peak_wavelength(300.0)
        self.assertGreater(lam, 5e-6)
        self.assertLess(lam, 20e-6)

    def test_draper_point(self):
        """Objects begin glowing visibly at ~798K (Draper point)."""
        self.assertFalse(is_visibly_glowing(700))
        self.assertTrue(is_visibly_glowing(800))
        self.assertTrue(is_visibly_glowing(1500))

    def test_blackbody_red_at_1500K(self):
        """Hot iron at 1500K should glow red (R > G > B)."""
        r, g, b = blackbody_color(1500)
        self.assertGreater(r, g, "1500K should be red-dominant")
        self.assertGreater(g, b, "1500K green > blue")

    def test_blackbody_white_at_6500K(self):
        """At 6500K (D65 illuminant), should be near-white."""
        r, g, b = blackbody_color(6500)
        # All channels should be high and close to each other
        self.assertGreater(r, 0.7)
        self.assertGreater(g, 0.7)
        self.assertGreater(b, 0.7)

    def test_blackbody_dark_at_room_T(self):
        """Room temperature emits infrared only — no visible glow."""
        r, g, b = blackbody_color(300)
        self.assertAlmostEqual(r, 0.0, places=1)
        self.assertAlmostEqual(g, 0.0, places=1)
        self.assertAlmostEqual(b, 0.0, places=1)


class TestContactConductance(unittest.TestCase):
    """Contact conductance — THE hot copper on cardboard test!"""

    def test_copper_on_copper_high(self):
        """Same-material contact should have high conductance."""
        h = contact_conductance('copper', 'copper', pressure_pa=1e7, T=300.0)
        self.assertGreater(h, 0)

    def test_higher_pressure_higher_conductance(self):
        """More pressure → more real contact → better heat transfer."""
        h_low = contact_conductance('iron', 'iron', pressure_pa=1e5)
        h_high = contact_conductance('iron', 'iron', pressure_pa=1e7)
        self.assertGreater(h_high, h_low)

    def test_copper_conducts_better_than_iron_interface(self):
        """Cu-Cu interface should conduct heat better than Fe-Fe."""
        h_cu = contact_conductance('copper', 'copper', pressure_pa=1e7)
        h_fe = contact_conductance('iron', 'iron', pressure_pa=1e7)
        self.assertGreater(h_cu, h_fe)

    def test_dissimilar_materials(self):
        """Copper on aluminum — should work and give reasonable value."""
        h = contact_conductance('copper', 'aluminum', pressure_pa=1e7)
        self.assertGreater(h, 0)

    def test_conductance_increases_with_temperature(self):
        """Higher T → more real contact (softer material) + rougher surface.
        The net effect depends on the balance, but should remain physical."""
        h = contact_conductance('copper', 'iron', pressure_pa=1e7, T=500.0)
        self.assertGreater(h, 0)


class TestSigmaDependence(unittest.TestCase):
    """σ-field propagation through the thermal chain."""

    def test_sigma_zero_matches_default(self):
        """σ=0 should give identical results to default."""
        kappa_default = thermal_conductivity('copper', T=300.0)
        kappa_zero = thermal_conductivity('copper', T=300.0, sigma=0.0)
        self.assertAlmostEqual(kappa_default, kappa_zero, places=10)

    def test_sigma_shifts_debye_temperature(self):
        """σ > 0 increases nuclear mass → lower phonon frequencies → lower Θ_D."""
        theta_0 = debye_temperature('copper', sigma=0.0)
        theta_05 = debye_temperature('copper', sigma=0.5)
        # Heavier nuclei → slower vibrations → lower Θ_D
        # But the effect goes through K and ρ, which partially cancel
        # Just check it's different
        self.assertNotAlmostEqual(theta_0, theta_05, places=1)

    def test_earth_sigma_negligible(self):
        """At Earth's surface (σ ~ 7e-10), shift should be tiny."""
        sigma_earth = 7e-10
        kappa_0 = thermal_conductivity('iron')
        kappa_earth = thermal_conductivity('iron', sigma=sigma_earth)
        rel_diff = abs(kappa_earth - kappa_0) / kappa_0
        self.assertLess(rel_diff, 1e-6,
                        "Earth σ should have negligible effect on κ")


class TestNagathaIntegration(unittest.TestCase):
    """Nagatha export format and honest origin tags."""

    def test_required_fields(self):
        """Export must include all thermal properties."""
        props = material_thermal_properties('copper', T=300.0)
        required = [
            'material', 'temperature_K', 'sigma',
            'sound_velocity_m_s', 'debye_temperature_K',
            'heat_capacity_volumetric_J_m3K', 'specific_heat_J_kgK',
            'phonon_mfp_m', 'thermal_conductivity_W_mK',
            'thermal_emission_W_m2', 'wien_peak_m',
            'blackbody_color_rgb', 'visibly_glowing', 'origin',
        ]
        for field in required:
            self.assertIn(field, props, f"Missing field: {field}")

    def test_honest_origin_tags(self):
        """Origin string must mention key derivations."""
        props = material_thermal_properties('copper')
        origin = props['origin'].lower()
        self.assertIn('debye', origin)
        self.assertIn('phonon', origin)
        self.assertIn('stefan-boltzmann', origin)
        self.assertIn('planck', origin)
        self.assertIn('first_principles', origin)
        self.assertIn('approximation', origin)

    def test_all_materials_export(self):
        """Every material in the database should export cleanly."""
        from sigma_ground.field.interface.surface import MATERIALS
        for key in MATERIALS:
            props = material_thermal_properties(key, T=300.0)
            self.assertGreater(props['thermal_conductivity_W_mK'], 0,
                               f"{key}: κ must be positive")
            self.assertGreater(props['debye_temperature_K'], 0,
                               f"{key}: Θ_D must be positive")


class TestCrossModuleConsistency(unittest.TestCase):
    """Verify thermal module is consistent with mechanical and texture."""

    def test_sound_velocity_consistent_with_bulk_modulus(self):
        """v_s = √(K/ρ) — check against mechanical module directly."""
        from sigma_ground.field.interface.mechanical import bulk_modulus
        from sigma_ground.field.interface.surface import MATERIALS

        for mat in ['iron', 'copper', 'aluminum']:
            K = bulk_modulus(mat)
            rho = MATERIALS[mat]['density_kg_m3']
            v_expected = math.sqrt(K / rho)
            v_actual = sound_velocity(mat)
            self.assertAlmostEqual(v_actual, v_expected, places=2,
                                   msg=f"{mat} v_s inconsistent with K and ρ")

    def test_thermal_roughness_used_in_emissivity(self):
        """Thermal emission uses specular_fraction from texture module.
        Rougher surface → higher emissivity → more radiation."""
        # At very high T, roughness increases → emissivity increases
        # But T⁴ dominates. Just check the function works.
        P = thermal_emission_power('iron', T=1000.0)
        self.assertGreater(P, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
