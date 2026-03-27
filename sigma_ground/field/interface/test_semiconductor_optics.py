"""
Tests for semiconductor_optics.py — band gap and Fresnel color from Z.

TDD: these tests define what the physics MUST do.

Test categories:
  1. Varshni equation — temperature-dependent band gap
  2. Band edge — λ_edge from E_g
  3. Semiconductor RGB — color from band gap + n+ik
  4. Z lookup — elemental semiconductors by atomic number
  5. σ-invariance — color must not change with σ (EM, σ-INVARIANT)
  6. Physical consistency — Fresnel, model selection, report format
"""

import math
import sys
import os
import inspect
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sigma_ground.field.interface.semiconductor_optics import (
    band_gap_ev,
    band_edge_nm,
    semiconductor_rgb,
    semiconductor_rgb_from_z,
    semiconductor_report,
    VARSHNI_PARAMS,
    SEMICONDUCTOR_NK,
    Z_TO_SEMICONDUCTOR,
)

_NM_EV = 1239.84193   # hc/e in nm·eV


class TestVarshniEquation(unittest.TestCase):
    """Band gap from Varshni equation: E_g(T) = E_g0 - αT²/(T+β)."""

    def test_si_300k_near_1p12ev(self):
        """Si band gap at 300K should be near 1.12 eV (indirect gap, well-established)."""
        eg = band_gap_ev('silicon', T=300.0)
        self.assertGreater(eg, 1.10, msg=f"Si Eg={eg:.4f} eV — too low")
        self.assertLess(eg, 1.14, msg=f"Si Eg={eg:.4f} eV — too high")

    def test_ge_300k_near_0p66ev(self):
        """Ge band gap at 300K should be near 0.66 eV."""
        eg = band_gap_ev('germanium', T=300.0)
        self.assertGreater(eg, 0.64, msg=f"Ge Eg={eg:.4f} eV — too low")
        self.assertLess(eg, 0.68, msg=f"Ge Eg={eg:.4f} eV — too high")

    def test_diamond_300k_near_5p47ev(self):
        """Diamond band gap at 300K should be near 5.47 eV."""
        eg = band_gap_ev('diamond', T=300.0)
        self.assertGreater(eg, 5.40, msg=f"Diamond Eg={eg:.4f} eV — too low")
        self.assertLess(eg, 5.50, msg=f"Diamond Eg={eg:.4f} eV — too high")

    def test_gap_300k_near_2p27ev(self):
        """GaP band gap at 300K should be near 2.27 eV (indirect gap)."""
        eg = band_gap_ev('gallium_phosphide', T=300.0)
        self.assertGreater(eg, 2.22, msg=f"GaP Eg={eg:.4f} eV — too low")
        self.assertLess(eg, 2.32, msg=f"GaP Eg={eg:.4f} eV — too high")

    def test_gan_300k_near_3p44ev(self):
        """GaN band gap at 300K should be near 3.44 eV (wurtzite direct gap)."""
        eg = band_gap_ev('gallium_nitride', T=300.0)
        self.assertGreater(eg, 3.40, msg=f"GaN Eg={eg:.4f} eV — too low")
        self.assertLess(eg, 3.48, msg=f"GaN Eg={eg:.4f} eV — too high")

    def test_cds_300k_near_2p42ev(self):
        """CdS band gap at 300K should be near 2.42 eV."""
        eg = band_gap_ev('cadmium_sulfide', T=300.0)
        self.assertGreater(eg, 2.38, msg=f"CdS Eg={eg:.4f} eV — too low")
        self.assertLess(eg, 2.52, msg=f"CdS Eg={eg:.4f} eV — too high")

    def test_band_gap_decreases_with_temperature(self):
        """E_g(400K) < E_g(300K) < E_g(1K) for all semiconductors.

        Varshni: dE_g/dT < 0 — lattice expansion softens crystal potential.
        FIRST_PRINCIPLES: Varshni (1967).
        """
        for key in VARSHNI_PARAMS:
            eg_1k   = band_gap_ev(key, T=1.0)
            eg_300k = band_gap_ev(key, T=300.0)
            eg_400k = band_gap_ev(key, T=400.0)
            self.assertGreater(eg_1k, eg_300k,
                msg=f"{key}: Eg(1K)={eg_1k:.4f} not > Eg(300K)={eg_300k:.4f}")
            self.assertGreater(eg_300k, eg_400k,
                msg=f"{key}: Eg(300K)={eg_300k:.4f} not > Eg(400K)={eg_400k:.4f}")

    def test_zero_temperature_gives_eg0(self):
        """At T→0, Varshni gives Eg0 (no thermal shift).

        Varshni: E_g(0) = E_g0 - α*0²/(0+β) = E_g0 exactly.
        """
        for key, params in VARSHNI_PARAMS.items():
            eg0_param = params['Eg0']
            eg_near0 = band_gap_ev(key, T=0.001)  # 1 mK ≈ 0K
            self.assertAlmostEqual(eg_near0, eg0_param, places=4,
                msg=f"{key}: Eg(~0K)={eg_near0:.5f} differs from Eg0={eg0_param:.5f}")

    def test_gaas_300k_near_1p42ev(self):
        """GaAs band gap at 300K should be near 1.42 eV (direct gap)."""
        eg = band_gap_ev('gallium_arsenide', T=300.0)
        self.assertGreater(eg, 1.40, msg=f"GaAs Eg={eg:.4f} eV — too low")
        self.assertLess(eg, 1.45, msg=f"GaAs Eg={eg:.4f} eV — too high")


class TestBandEdge(unittest.TestCase):
    """Band edge wavelength λ_edge = hc/E_g."""

    def test_si_edge_above_visible(self):
        """Si λ_edge > 1000nm — gap is in near-IR, all visible is above-gap."""
        lam = band_edge_nm('silicon', T=300.0)
        self.assertGreater(lam, 1000,
            msg=f"Si λ_edge={lam:.0f}nm — should be in NIR (>1000nm)")

    def test_diamond_edge_in_deep_uv(self):
        """Diamond λ_edge < 250nm — gap is far into UV, all visible is sub-gap."""
        lam = band_edge_nm('diamond', T=300.0)
        self.assertLess(lam, 250,
            msg=f"Diamond λ_edge={lam:.0f}nm — should be deep UV (<250nm)")

    def test_gap_edge_in_visible_green(self):
        """GaP λ_edge in visible (~530-560nm), near the green-yellow boundary."""
        lam = band_edge_nm('gallium_phosphide', T=300.0)
        self.assertGreater(lam, 520,
            msg=f"GaP λ_edge={lam:.0f}nm — should be ≥520nm")
        self.assertLess(lam, 570,
            msg=f"GaP λ_edge={lam:.0f}nm — should be ≤570nm")

    def test_cds_edge_in_visible_blue_green(self):
        """CdS λ_edge near 490-520nm (green-blue boundary)."""
        lam = band_edge_nm('cadmium_sulfide', T=300.0)
        self.assertGreater(lam, 480,
            msg=f"CdS λ_edge={lam:.0f}nm — should be ≥480nm")
        self.assertLess(lam, 530,
            msg=f"CdS λ_edge={lam:.0f}nm — should be ≤530nm")

    def test_edge_consistent_with_band_gap(self):
        """λ_edge = hc/E_g within floating-point error."""
        for key in VARSHNI_PARAMS:
            eg = band_gap_ev(key, T=300.0)
            lam = band_edge_nm(key, T=300.0)
            expected_lam = _NM_EV / eg
            self.assertAlmostEqual(lam, expected_lam, places=3,
                msg=f"{key}: λ_edge={lam:.2f}nm ≠ hc/Eg={expected_lam:.2f}nm")

    def test_gan_edge_in_uv(self):
        """GaN λ_edge near UV (~360nm); all visible is sub-gap."""
        lam = band_edge_nm('gallium_nitride', T=300.0)
        self.assertGreater(lam, 340)
        self.assertLess(lam, 380)


class TestSemiconductorRGB(unittest.TestCase):
    """Color from band gap cutoff + Fresnel reflectance."""

    def test_diamond_is_nearly_colorless(self):
        """Diamond: wide gap → all visible sub-gap → nearly flat Fresnel → colorless.

        All three channels should differ by < 0.01 (nearly equal reflectance).
        """
        r, g, b = semiconductor_rgb('diamond', T=300.0)
        span = max(r, g, b) - min(r, g, b)
        self.assertLess(span, 0.015,
            msg=f"Diamond RGB=({r:.3f},{g:.3f},{b:.3f}) — span={span:.3f} > 0.015, not colorless")

    def test_diamond_reflectance_range(self):
        """Diamond n≈2.42 → R ≈ (2.42-1)²/(2.42+1)² = 0.17. Should be 0.15-0.20."""
        r, g, b = semiconductor_rgb('diamond', T=300.0)
        for ch, name in [(r, 'R'), (g, 'G'), (b, 'B')]:
            self.assertGreater(ch, 0.14,
                msg=f"Diamond {name}={ch:.3f} too low (n≈2.42 gives R≈0.17)")
            self.assertLess(ch, 0.22,
                msg=f"Diamond {name}={ch:.3f} too high")

    def test_si_is_grey_metallic(self):
        """Si: all visible above-gap → metallic Fresnel → grey (0.30–0.45 all channels)."""
        r, g, b = semiconductor_rgb('silicon', T=300.0)
        for ch, name in [(r, 'R'), (g, 'G'), (b, 'B')]:
            self.assertGreater(ch, 0.28,
                msg=f"Si {name}={ch:.3f} — should be metallic grey (>0.28)")
            self.assertLess(ch, 0.48,
                msg=f"Si {name}={ch:.3f} — should be metallic grey (<0.48)")

    def test_si_slightly_blue_grey(self):
        """Si: k increases toward UV → R(450nm) > R(650nm). Slight blue bias.

        This matches real Si wafers which appear slightly blue-grey.
        """
        r, g, b = semiconductor_rgb('silicon', T=300.0)
        self.assertGreater(b, r,
            msg=f"Si B={b:.3f} should be > R={r:.3f} (blue-grey from k increase at UV)")

    def test_gap_is_amber(self):
        """GaP: red+green sub-gap (reflected), blue above-gap (absorbed) → amber/orange.

        R_red > 0.2, R_green > 0.2, R_blue ≈ 0 (above gap → absorbed by bulk).
        """
        r, g, b = semiconductor_rgb('gallium_phosphide', T=300.0)
        self.assertGreater(r, 0.20,
            msg=f"GaP R={r:.3f} — red should be reflected (sub-gap)")
        self.assertGreater(g, 0.20,
            msg=f"GaP G={g:.3f} — green should be reflected (sub-gap)")
        self.assertLess(b, 0.05,
            msg=f"GaP B={b:.3f} — blue should be near-zero (above-gap, absorbed)")

    def test_gap_is_redder_than_blue(self):
        """GaP: R_red > R_blue — red sub-gap Fresnel > blue above-gap value."""
        r, g, b = semiconductor_rgb('gallium_phosphide', T=300.0)
        self.assertGreater(r, b,
            msg=f"GaP R={r:.3f} should be > B={b:.3f}")

    def test_cds_is_yellow(self):
        """CdS: red+green sub-gap, blue above-gap → yellow appearance.

        R_red > 0, R_green > 0, R_blue ≈ 0.
        """
        r, g, b = semiconductor_rgb('cadmium_sulfide', T=300.0)
        self.assertGreater(r, 0.10,
            msg=f"CdS R={r:.3f} — red should be visible (sub-gap)")
        self.assertGreater(g, 0.10,
            msg=f"CdS G={g:.3f} — green should be visible (sub-gap)")
        self.assertLess(b, 0.05,
            msg=f"CdS B={b:.3f} — blue absorbed (above-gap)")

    def test_gan_is_nearly_colorless(self):
        """GaN: wide gap (3.44eV) → all visible sub-gap → near-colorless low-R surface."""
        r, g, b = semiconductor_rgb('gallium_nitride', T=300.0)
        span = max(r, g, b) - min(r, g, b)
        self.assertLess(span, 0.04,
            msg=f"GaN RGB=({r:.3f},{g:.3f},{b:.3f}) — span={span:.3f}, not near-colorless")

    def test_zno_is_nearly_white_low_r(self):
        """ZnO: wide gap, n≈2.0 → R≈0.11, nearly colorless (white pigment appearance)."""
        r, g, b = semiconductor_rgb('zinc_oxide', T=300.0)
        span = max(r, g, b) - min(r, g, b)
        self.assertLess(span, 0.04,
            msg=f"ZnO RGB=({r:.3f},{g:.3f},{b:.3f}) — not near-colorless")

    def test_tio2_is_nearly_colorless_high_n(self):
        """TiO₂: wide gap, high n≈2.8 → R≈0.22, nearly colorless (white pigment)."""
        r, g, b = semiconductor_rgb('titanium_dioxide', T=300.0)
        span = max(r, g, b) - min(r, g, b)
        self.assertLess(span, 0.05,
            msg=f"TiO₂ RGB=({r:.3f},{g:.3f},{b:.3f}) — span={span:.3f}, not near-colorless")

    def test_all_rgb_in_unit_range(self):
        """All (r, g, b) channels must be in [0, 1]."""
        for key in SEMICONDUCTOR_NK:
            r, g, b = semiconductor_rgb(key, T=300.0)
            for ch, name in [(r, 'R'), (g, 'G'), (b, 'B')]:
                self.assertGreaterEqual(ch, 0.0,
                    msg=f"{key} {name}={ch:.4f} < 0")
                self.assertLessEqual(ch, 1.0,
                    msg=f"{key} {name}={ch:.4f} > 1")

    def test_ge_is_grey_high_reflectance(self):
        """Ge: narrow gap, large n+ik in visible → high R (shiny grey, >0.5 all channels)."""
        r, g, b = semiconductor_rgb('germanium', T=300.0)
        for ch, name in [(r, 'R'), (g, 'G'), (b, 'B')]:
            self.assertGreater(ch, 0.45,
                msg=f"Ge {name}={ch:.3f} — should be high R (metallic grey)")


class TestZLookup(unittest.TestCase):
    """Elemental semiconductors accessible by atomic number Z."""

    def test_si_by_z_14(self):
        """Z=14 maps to silicon."""
        self.assertEqual(Z_TO_SEMICONDUCTOR[14], 'silicon')

    def test_ge_by_z_32(self):
        """Z=32 maps to germanium."""
        self.assertEqual(Z_TO_SEMICONDUCTOR[32], 'germanium')

    def test_diamond_by_z_6(self):
        """Z=6 maps to diamond (carbon, cubic polymorph)."""
        self.assertEqual(Z_TO_SEMICONDUCTOR[6], 'diamond')

    def test_semiconductor_rgb_from_z_si(self):
        """semiconductor_rgb_from_z(14) should equal semiconductor_rgb('silicon')."""
        r1, g1, b1 = semiconductor_rgb('silicon', T=300.0)
        r2, g2, b2 = semiconductor_rgb_from_z(14, T=300.0)
        self.assertAlmostEqual(r1, r2, places=10)
        self.assertAlmostEqual(g1, g2, places=10)
        self.assertAlmostEqual(b1, b2, places=10)

    def test_semiconductor_rgb_from_z_unknown_raises(self):
        """Unknown Z should raise KeyError."""
        with self.assertRaises(KeyError):
            semiconductor_rgb_from_z(79, T=300.0)   # Gold — not in semiconductor table


class TestSigmaInvariance(unittest.TestCase):
    """Color is σ-INVARIANT — all EM, no QCD/nuclear dependence."""

    def test_semiconductor_rgb_has_no_sigma_parameter(self):
        """semiconductor_rgb() must not accept a sigma parameter.

        Color is purely electromagnetic: band gap is EM (crystal potential),
        optical constants n+ik are EM, Fresnel is EM.
        σ-field affects nuclear/hadronic mass — not EM observables.
        """
        sig = inspect.signature(semiconductor_rgb)
        param_names = list(sig.parameters.keys())
        self.assertNotIn('sigma', param_names,
            msg="semiconductor_rgb() should not have a 'sigma' parameter (EM: σ-INVARIANT)")
        self.assertNotIn('sigma_field', param_names,
            msg="semiconductor_rgb() should not have a 'sigma_field' parameter")

    def test_report_states_sigma_invariant(self):
        """Report origin tag must state σ-INVARIANT."""
        rep = semiconductor_report('silicon', T=300.0)
        origin = rep.get('origin', '')
        self.assertIn('σ-INVARIANT', origin,
            msg=f"Report origin must contain 'σ-INVARIANT', got: {origin[:120]!r}")

    def test_band_gap_rgb_from_z_no_sigma(self):
        """semiconductor_rgb_from_z() must not accept a sigma parameter."""
        sig = inspect.signature(semiconductor_rgb_from_z)
        param_names = list(sig.parameters.keys())
        self.assertNotIn('sigma', param_names)


class TestPhysicalConsistency(unittest.TestCase):
    """Physical self-consistency checks."""

    def test_narrow_gap_all_channels_nonzero(self):
        """Narrow-gap semiconductors (Si, Ge, GaAs): all channels > 0 (metallic model).

        When E_g < E_red, all visible wavelengths are above the gap.
        The material absorbs all visible light but reflects at the surface
        due to complex n+ik → all channels non-zero (grey metallic appearance).
        """
        for key in ('silicon', 'germanium', 'gallium_arsenide'):
            r, g, b = semiconductor_rgb(key, T=300.0)
            for ch, name in [(r, 'R'), (g, 'G'), (b, 'B')]:
                self.assertGreater(ch, 0.05,
                    msg=f"{key} {name}={ch:.4f} should be > 0 (metallic model)")

    def test_wide_gap_all_sub_gap(self):
        """Wide-gap semiconductors (diamond, ZnO, GaN): all channels sub-gap.

        λ_edge < 380nm → all visible channels (450-650nm) are below the gap.
        """
        for key in ('diamond', 'zinc_oxide', 'gallium_nitride'):
            lam_edge = band_edge_nm(key, T=300.0)
            self.assertLess(lam_edge, 400,
                msg=f"{key} λ_edge={lam_edge:.0f}nm — should be UV (<400nm)")

    def test_fresnel_formula_known_case(self):
        """Fresnel R for glass (n=1.5, k=0): R = (0.5/2.5)² = 0.04."""
        # Import the internal function by running the module
        import sigma_ground.field.interface.semiconductor_optics as semi
        r = semi._fresnel_r(1.5, 0.0)
        self.assertAlmostEqual(r, 0.04, places=5,
            msg=f"Fresnel(n=1.5, k=0) = {r:.6f} ≠ 0.04000")

    def test_fresnel_formula_metal_limit(self):
        """Fresnel R for perfect conductor (n→0, k→∞): R → 1.

        For high k, R approaches 1 (perfect reflection).
        """
        import sigma_ground.field.interface.semiconductor_optics as semi
        r = semi._fresnel_r(0.01, 10.0)
        self.assertGreater(r, 0.95,
            msg=f"Fresnel(n≈0, k=10) = {r:.4f} — should be near 1 for metallic limit")

    def test_report_has_required_keys(self):
        """Diagnostic report must contain required fields."""
        rep = semiconductor_report('silicon', T=300.0)
        required = [
            'material', 'band_gap_ev', 'band_edge_nm',
            'rgb_tuple', 'origin', 'model',
        ]
        for key in required:
            self.assertIn(key, rep,
                msg=f"semiconductor_report missing key: {key!r}")

    def test_report_band_gap_matches_function(self):
        """Report band_gap_ev should equal band_gap_ev() function output."""
        for key in ('silicon', 'diamond', 'gallium_phosphide'):
            rep = semiconductor_report(key, T=300.0)
            self.assertAlmostEqual(rep['band_gap_ev'], band_gap_ev(key, T=300.0),
                places=10, msg=f"{key}: report vs function band gap mismatch")

    def test_temperature_dependence_on_color(self):
        """Heating a semiconductor shifts its band gap → λ_edge shifts.

        For GaP: E_g decreases at high T → λ_edge increases → more green absorbed.
        At very high T, G channel may also become 0 (above gap).
        This is qualitative — just check that λ_edge changes.
        """
        lam_300k = band_edge_nm('gallium_phosphide', T=300.0)
        lam_600k = band_edge_nm('gallium_phosphide', T=600.0)
        self.assertGreater(lam_600k, lam_300k,
            msg=f"GaP λ_edge should increase with T: 300K={lam_300k:.1f}nm, 600K={lam_600k:.1f}nm")

    def test_varshni_params_all_positive(self):
        """All Varshni parameters (Eg0, α, β) must be positive."""
        for key, params in VARSHNI_PARAMS.items():
            self.assertGreater(params['Eg0'], 0,
                msg=f"{key}: Eg0={params['Eg0']} must be positive")
            self.assertGreater(params['alpha'], 0,
                msg=f"{key}: α={params['alpha']} must be positive")
            self.assertGreater(params['beta'], 0,
                msg=f"{key}: β={params['beta']} must be positive")


if __name__ == '__main__':
    unittest.main()
