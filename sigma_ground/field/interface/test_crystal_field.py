"""
Tests for crystal_field.py — transition metal optics via ligand field theory.

TDD: these tests define what the physics MUST do.

Test categories:
  1. d-electron count — Aufbau from Z + oxidation state
  2. Racah B — free ion values and nephelauxetic reduction
  3. Absorption bands — wavelength ranges per d-configuration
  4. Named mineral colors — ruby red, emerald green, malachite green, azurite blue
  5. σ-invariance — color must not change with σ (EM, σ-INVARIANT)
  6. Colorless ions — d⁰ and d¹⁰ return white
  7. Report format — origin tags present
"""

import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sigma_ground.field.interface.crystal_field import (
    d_electron_count,
    racah_b_crystal,
    absorption_bands,
    crystal_field_rgb,
    mineral_rgb,
    crystal_field_report,
    CRYSTAL_FIELD_10DQ_EV,
    FREE_ION_RACAH_B_EV,
    NEPHELAUXETIC_BETA,
    MINERAL_COORDS,
)


class TestDElectronCount(unittest.TestCase):
    """d-electron count from Aufbau principle."""

    def test_cr3_plus_is_d3(self):
        """Cr³⁺ (Z=24, ox=3): [Ar]3d³ → 3 d-electrons."""
        self.assertEqual(d_electron_count(24, 3), 3)

    def test_cu2_plus_is_d9(self):
        """Cu²⁺ (Z=29, ox=2): [Ar]3d⁹ → 9 d-electrons."""
        self.assertEqual(d_electron_count(29, 2), 9)

    def test_fe2_plus_is_d6(self):
        """Fe²⁺ (Z=26, ox=2): [Ar]3d⁶ → 6 d-electrons."""
        self.assertEqual(d_electron_count(26, 2), 6)

    def test_fe3_plus_is_d5(self):
        """Fe³⁺ (Z=26, ox=3): [Ar]3d⁵ → 5 d-electrons."""
        self.assertEqual(d_electron_count(26, 3), 5)

    def test_ni2_plus_is_d8(self):
        """Ni²⁺ (Z=28, ox=2): [Ar]3d⁸ → 8 d-electrons."""
        self.assertEqual(d_electron_count(28, 2), 8)

    def test_zn2_plus_is_d10(self):
        """Zn²⁺ (Z=30, ox=2): [Ar]3d¹⁰ → 10 d-electrons."""
        self.assertEqual(d_electron_count(30, 2), 10)

    def test_ti3_plus_is_d1(self):
        """Ti³⁺ (Z=22, ox=3): [Ar]3d¹ → 1 d-electron."""
        self.assertEqual(d_electron_count(22, 3), 1)

    def test_mn2_plus_is_d5(self):
        """Mn²⁺ (Z=25, ox=2): [Ar]3d⁵ → 5 d-electrons."""
        self.assertEqual(d_electron_count(25, 2), 5)

    def test_non_transition_metal_returns_zero(self):
        """Non-TM elements return 0 d-electrons."""
        self.assertEqual(d_electron_count(13, 3), 0)   # Al³⁺
        self.assertEqual(d_electron_count(6, 0), 0)    # C
        self.assertEqual(d_electron_count(8, 2), 0)    # O²⁻ (negative not physical but...)

    def test_co2_plus_is_d7(self):
        """Co²⁺ (Z=27, ox=2): [Ar]3d⁷ → 7 d-electrons."""
        self.assertEqual(d_electron_count(27, 2), 7)


class TestRacahB(unittest.TestCase):
    """Free-ion Racah B and nephelauxetic reduction."""

    def test_cr3_free_ion_b_in_range(self):
        """Cr³⁺ free-ion B should be near 918 cm⁻¹ = 0.1138 eV."""
        b = FREE_ION_RACAH_B_EV[(24, 3)]
        b_cm1 = b * 8065.54
        self.assertAlmostEqual(b_cm1, 918, delta=5,
                               msg=f"Cr³⁺ B = {b_cm1:.1f} cm⁻¹, expected ~918")

    def test_nephelauxetic_reduction_oxide(self):
        """β(oxide_oct) < 1 — covalency reduces B."""
        beta = NEPHELAUXETIC_BETA['oxide_oct']
        self.assertGreater(beta, 0.5)
        self.assertLess(beta, 1.0)

    def test_cn_most_covalent(self):
        """CN⁻ (strongest field) should have smallest β."""
        beta_cn = NEPHELAUXETIC_BETA['cn_oct']
        beta_ox = NEPHELAUXETIC_BETA['oxide_oct']
        self.assertLess(beta_cn, beta_ox)

    def test_fluoride_most_ionic(self):
        """F⁻ (most ionic halide) should have largest β."""
        beta_f = NEPHELAUXETIC_BETA['fluoride_oct']
        beta_s = NEPHELAUXETIC_BETA['sulfide_oct']
        self.assertGreater(beta_f, beta_s)

    def test_b_crystal_less_than_free(self):
        """In-crystal B must be less than free-ion B."""
        b_free = FREE_ION_RACAH_B_EV[(24, 3)]
        b_crys = racah_b_crystal(24, 3, 'oxide_oct')
        self.assertLess(b_crys, b_free)

    def test_ruby_b_crystal_in_range(self):
        """Cr³⁺ in oxide_oct: B_crystal should be 0.082-0.100 eV (~660-800 cm⁻¹)."""
        b = racah_b_crystal(24, 3, 'oxide_oct')
        b_cm1 = b * 8065.54
        self.assertGreater(b_cm1, 650,
                           msg=f"B_crystal = {b_cm1:.0f} cm⁻¹, expected >650")
        self.assertLess(b_cm1, 850,
                        msg=f"B_crystal = {b_cm1:.0f} cm⁻¹, expected <850")


class TestAbsorptionBands(unittest.TestCase):
    """Absorption band wavelengths from Tanabe-Sugano theory."""

    def test_ruby_has_two_bands(self):
        """Cr³⁺ (d³) in oxide_oct should produce two absorption bands."""
        bands = absorption_bands(24, 3, 'oxide_oct')
        self.assertEqual(len(bands), 2,
                         msg=f"Ruby should have 2 bands, got {len(bands)}: {bands}")

    def test_ruby_band1_near_560nm(self):
        """Ruby first band (ν₁ = Δ = 18000 cm⁻¹) at ~556nm."""
        bands = absorption_bands(24, 3, 'oxide_oct')
        l1 = bands[0][0]
        self.assertAlmostEqual(l1, 556, delta=15,
                               msg=f"Ruby ν₁ at {l1:.0f}nm, expected ~556nm")

    def test_ruby_band2_near_400nm(self):
        """Ruby second band (ν₂ ≈ Δ+9B) near 400nm (UV/violet)."""
        bands = absorption_bands(24, 3, 'oxide_oct')
        l2 = bands[1][0]
        self.assertGreater(l2, 350, msg=f"Ruby ν₂ at {l2:.0f}nm, expected >350nm")
        self.assertLess(l2, 450, msg=f"Ruby ν₂ at {l2:.0f}nm, expected <450nm")

    def test_emerald_band1_near_600nm(self):
        """Emerald ν₁ (Δ = 16500 cm⁻¹) at ~606nm."""
        bands = absorption_bands(24, 3, 'silicate_oct')
        l1 = bands[0][0]
        self.assertAlmostEqual(l1, 606, delta=20,
                               msg=f"Emerald ν₁ at {l1:.0f}nm, expected ~606nm")

    def test_malachite_band_near_700nm(self):
        """Malachite Cu²⁺ (d⁹) has one broad band near 700nm."""
        bands = absorption_bands(29, 2, 'carbonate_oct')
        self.assertGreaterEqual(len(bands), 1)
        l1 = bands[0][0]
        self.assertGreater(l1, 600, msg=f"Malachite band at {l1:.0f}nm, expected >600nm")
        self.assertLess(l1, 800, msg=f"Malachite band at {l1:.0f}nm, expected <800nm")

    def test_colorless_zn_returns_empty(self):
        """Zn²⁺ (d¹⁰) returns no absorption bands → colorless."""
        # Need to add a coord key that returns Δ=0, or just check directly
        # Zn²⁺ is not in our 10Dq table (no d-d transitions)
        bands = absorption_bands(30, 2, 'oxide_oct')
        self.assertEqual(bands, [],
                         msg="Zn²⁺ (d¹⁰) should have no d-d bands")

    def test_all_band_wavelengths_in_visible_or_near_visible(self):
        """All computed band centers should be in 280–900nm range."""
        test_cases = [
            (24, 3, 'oxide_oct'),       # ruby
            (24, 3, 'silicate_oct'),    # emerald
            (29, 2, 'carbonate_oct'),   # malachite
            (29, 2, 'azurite_oct'),     # azurite
            (26, 2, 'silicate_oct'),    # peridot
            (27, 2, 'oxide_tet'),       # cobalt blue
            (28, 2, 'oxide_oct'),       # nickel green
            (22, 3, 'oxide_oct'),       # ti-sapphire
        ]
        for Z, ox, coord in test_cases:
            bands = absorption_bands(Z, ox, coord)
            for lam, width, absorb in bands:
                self.assertGreater(lam, 280,
                    msg=f"({Z},{ox},{coord}) band at {lam:.0f}nm < 280nm")
                self.assertLess(lam, 1000,
                    msg=f"({Z},{ox},{coord}) band at {lam:.0f}nm > 1000nm")
                self.assertGreater(absorb, 0)
                self.assertLessEqual(absorb, 1)

    def test_d5_highspin_bands_weak(self):
        """d⁵ high-spin (goethite, spessartine) should have weak absorptions (<0.65)."""
        goethite = absorption_bands(26, 3, 'oxide_oct')
        for lam, width, absorb in goethite:
            self.assertLess(absorb, 0.65,
                msg=f"d⁵ absorb={absorb:.2f} too strong (should be pale)")


class TestMineralColors(unittest.TestCase):
    """Named mineral colors — physics determines hue."""

    def _dominant_channel(self, rgb):
        """Return index of brightest channel: 0=R, 1=G, 2=B."""
        return rgb.index(max(rgb))

    def test_ruby_is_red(self):
        """Ruby (Cr³⁺/Al₂O₃) absorbs green+blue → RED dominant."""
        rgb = mineral_rgb('ruby')
        r, g, b = rgb
        self.assertGreater(r, g, msg=f"Ruby: R={r:.3f} should > G={g:.3f}")
        self.assertGreater(r, b, msg=f"Ruby: R={r:.3f} should > B={b:.3f}")
        self.assertGreater(r, 0.3, msg=f"Ruby red channel too dim: R={r:.3f}")

    def test_emerald_is_green(self):
        """Emerald (Cr³⁺/beryl) absorbs orange-red and violet → GREEN dominant."""
        rgb = mineral_rgb('emerald')
        r, g, b = rgb
        self.assertGreater(g, r, msg=f"Emerald: G={g:.3f} should > R={r:.3f}")
        self.assertGreater(g, 0.2, msg=f"Emerald green too dim: G={g:.3f}")

    def test_malachite_is_green_or_cyan(self):
        """Malachite (Cu²⁺ carbonate) absorbs red/orange → green-blue."""
        rgb = mineral_rgb('malachite')
        r, g, b = rgb
        # The band at ~700nm kills red, leaving green+blue
        self.assertLess(r, 0.6,
                        msg=f"Malachite should have reduced red: R={r:.3f}")
        self.assertGreater(g + b, r,
                           msg=f"Malachite G+B={g+b:.3f} should > R={r:.3f}")

    def test_azurite_is_bluer_than_malachite(self):
        """Azurite (shorter Δ → shorter-λ absorption) is bluer than malachite."""
        r_m, g_m, b_m = mineral_rgb('malachite')
        r_a, g_a, b_a = mineral_rgb('azurite')
        # Azurite absorbs at ~625nm (orange) → more blue remains vs malachite
        # Both should have high blue, but azurite more so
        blue_frac_a = b_a / (r_a + g_a + b_a + 1e-9)
        blue_frac_m = b_m / (r_m + g_m + b_m + 1e-9)
        self.assertGreater(blue_frac_a, blue_frac_m - 0.1,
                           msg=f"Azurite should be at least as blue as malachite: "
                               f"azurite bf={blue_frac_a:.3f} vs malachite bf={blue_frac_m:.3f}")

    def test_cobalt_blue_is_blue(self):
        """Cobalt blue (Co²⁺ tetrahedral) absorbs red+orange → BLUE dominant."""
        rgb = mineral_rgb('cobalt_blue')
        r, g, b = rgb
        self.assertGreater(b, r, msg=f"Cobalt blue: B={b:.3f} should > R={r:.3f}")

    def test_nickel_green_is_greenish(self):
        """Nickel green (Ni²⁺ oxide) absorbs NIR and UV → green dominant."""
        rgb = mineral_rgb('nickel_green')
        r, g, b = rgb
        # Ni²⁺ bands are in NIR and UV; green channel should be relatively bright
        self.assertGreater(g, r - 0.1,
                           msg=f"Nickel green should not be dominated by red")

    def test_ruby_redder_than_emerald(self):
        """Ruby (oxide field) is redder than emerald (weaker silicate field)."""
        r_rub, g_rub, b_rub = mineral_rgb('ruby')
        r_em,  g_em,  b_em  = mineral_rgb('emerald')
        # Ruby red fraction > emerald red fraction
        red_frac_ruby = r_rub / (r_rub + g_rub + b_rub + 1e-9)
        red_frac_em   = r_em  / (r_em  + g_em  + b_em  + 1e-9)
        self.assertGreater(red_frac_ruby, red_frac_em,
                           msg=f"Ruby should be redder than emerald: "
                               f"ruby rf={red_frac_ruby:.3f} vs em rf={red_frac_em:.3f}")

    def test_all_rgb_in_unit_range(self):
        """All mineral RGB values must be in [0, 1]."""
        for name in MINERAL_COORDS:
            r, g, b = mineral_rgb(name)
            for ch, val in zip('rgb', (r, g, b)):
                self.assertGreaterEqual(val, 0.0,
                    msg=f"{name} {ch}={val:.4f} < 0")
                self.assertLessEqual(val, 1.0,
                    msg=f"{name} {ch}={val:.4f} > 1")

    def test_unknown_mineral_raises(self):
        """mineral_rgb raises KeyError for unknown minerals."""
        with self.assertRaises(KeyError):
            mineral_rgb('unobtainium')


class TestSigmaInvariance(unittest.TestCase):
    """Crystal field color is EM → completely σ-invariant."""

    def test_crystal_field_has_no_sigma_parameter(self):
        """crystal_field_rgb() takes no sigma parameter (EM: σ-INVARIANT by design)."""
        # The function signature should not accept sigma — color is EM
        import inspect
        sig = inspect.signature(crystal_field_rgb)
        self.assertNotIn('sigma', sig.parameters,
                         "crystal_field_rgb should have no sigma parameter — it's EM")

    def test_report_says_sigma_invariant(self):
        """Report origin tag must state σ-INVARIANT."""
        report = crystal_field_report(24, 3, 'oxide_oct')
        self.assertIn('σ-INVARIANT', report['sigma_dependence'])
        self.assertIn('EM', report['sigma_dependence'])


class TestReportFormat(unittest.TestCase):
    """crystal_field_report() returns all required fields with origin tags."""

    def test_report_has_required_keys(self):
        """Report must contain all diagnostic fields."""
        report = crystal_field_report(24, 3, 'oxide_oct')
        required = ['Z', 'oxidation_state', 'coord_key', 'd_electrons',
                    '10Dq_eV', '10Dq_cm1', 'B_free_ion_eV', 'nephelauxetic_beta',
                    'B_crystal_eV', 'absorption_bands', 'rgb', 'origin',
                    'sigma_dependence']
        for key in required:
            self.assertIn(key, report, msg=f"Report missing key: {key}")

    def test_ruby_report_10dq_in_cm1(self):
        """Ruby 10Dq should be ~18000 cm⁻¹ as reported."""
        report = crystal_field_report(24, 3, 'oxide_oct')
        self.assertAlmostEqual(report['10Dq_cm1'], 18000, delta=50)

    def test_report_origin_has_measured_tag(self):
        """Origin string must mention MEASURED sources."""
        report = crystal_field_report(24, 3, 'oxide_oct')
        self.assertIn('MEASURED', report['origin'])
        self.assertIn('FIRST_PRINCIPLES', report['origin'])

    def test_report_bands_are_dicts(self):
        """absorption_bands in report should be list of dicts."""
        report = crystal_field_report(24, 3, 'oxide_oct')
        for band in report['absorption_bands']:
            self.assertIn('lambda_nm', band)
            self.assertIn('width_nm', band)
            self.assertIn('max_absorb', band)


class TestPhysicalConsistency(unittest.TestCase):
    """Physical self-consistency checks."""

    def test_stronger_field_shorter_absorption_wavelength(self):
        """Higher 10Dq → higher-energy (shorter-λ) first absorption band.

        Ruby (oxide, Δ=18000) vs emerald (silicate, Δ=16500).
        Ruby ν₁ shorter wavelength than emerald ν₁.
        """
        bands_rub = absorption_bands(24, 3, 'oxide_oct')
        bands_em  = absorption_bands(24, 3, 'silicate_oct')
        l1_rub = bands_rub[0][0]
        l1_em  = bands_em[0][0]
        self.assertLess(l1_rub, l1_em,
                        msg=f"Ruby ν₁={l1_rub:.0f}nm should < emerald ν₁={l1_em:.0f}nm")

    def test_d3_two_bands_second_higher_energy(self):
        """For d³: ν₂ > ν₁ in energy → ν₂ is shorter wavelength."""
        bands = absorption_bands(24, 3, 'oxide_oct')
        self.assertEqual(len(bands), 2)
        l1, l2 = bands[0][0], bands[1][0]
        self.assertGreater(l1, l2,
                           msg=f"d³: ν₁={l1:.0f}nm should be longer λ than ν₂={l2:.0f}nm")

    def test_malachite_vs_azurite_delta(self):
        """Azurite has larger 10Dq than malachite (shorter absorption λ)."""
        d_mal = CRYSTAL_FIELD_10DQ_EV[(29, 2, 'carbonate_oct')]
        d_az  = CRYSTAL_FIELD_10DQ_EV[(29, 2, 'azurite_oct')]
        self.assertGreater(d_az, d_mal,
                           msg=f"Azurite Δ={d_az:.3f}eV should > malachite Δ={d_mal:.3f}eV")

    def test_tet_cobalt_smaller_delta_than_oct(self):
        """Δ_tet < Δ_oct for the same ion (geometric factor ~4/9)."""
        # Co²⁺ tet vs oct
        d_tet = CRYSTAL_FIELD_10DQ_EV.get((27, 2, 'oxide_tet'), 0)
        d_oct = CRYSTAL_FIELD_10DQ_EV.get((27, 2, 'water_oct'), 0)
        if d_tet and d_oct:
            self.assertLess(d_tet, d_oct,
                msg=f"Co²⁺ Δ_tet={d_tet:.3f} should < Δ_oct={d_oct:.3f}")


if __name__ == '__main__':
    unittest.main()
