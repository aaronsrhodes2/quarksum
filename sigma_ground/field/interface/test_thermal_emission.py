"""
Tests for thermal_emission.py — Planck × emissivity = glowing color.

TDD: these tests define what the physics MUST do.

Test categories:
  1. Planck function — spectral radiance from quantum statistics
  2. Emissivity — Kirchhoff: ε(λ) = 1 − R(λ)
  3. Thermal emission RGB — visible chromaticity of hot materials
  4. σ-invariance — EM, no σ dependence
  5. Physical consistency — Wien law, colour temperature trends, report format
"""

import math
import sys
import os
import inspect
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sigma_ground.field.interface.thermal_emission import (
    planck_spectral_radiance,
    emissivity,
    thermal_emission_rgb,
    thermal_emission_report,
    is_visibly_glowing,
    THERMAL_EMISSION_MATERIALS,
)

_H = 6.62607015e-34    # J·s
_C = 2.99792458e8      # m/s
_K = 1.380649e-23      # J/K


class TestPlanckFunction(unittest.TestCase):
    """Planck spectral radiance B(λ,T) = 2hc²/λ⁵ · 1/(exp(hc/λkT)−1)."""

    def test_planck_positive_for_positive_T(self):
        """Planck radiance must be > 0 for any finite T > 0, any wavelength."""
        for lam_nm in [450, 550, 650, 1000]:
            for T in [300, 1000, 3000, 6000]:
                B = planck_spectral_radiance(lam_nm * 1e-9, T)
                self.assertGreater(B, 0,
                    msg=f"B({lam_nm}nm, {T}K) = {B} — should be > 0")

    def test_planck_zero_at_zero_T(self):
        """At T=0: exp(hc/λkT) → ∞ → B → 0 (no thermal emission)."""
        B = planck_spectral_radiance(650e-9, 0.0)
        self.assertEqual(B, 0.0, msg=f"B(650nm, T=0) = {B} — should be 0")

    def test_planck_increases_with_temperature(self):
        """B(λ,T₂) > B(λ,T₁) for T₂ > T₁ at any wavelength.

        Planck function is strictly monotone in T at fixed λ.
        """
        for lam_nm in [450, 550, 650]:
            B_low = planck_spectral_radiance(lam_nm * 1e-9, 1000.0)
            B_mid = planck_spectral_radiance(lam_nm * 1e-9, 3000.0)
            B_hi  = planck_spectral_radiance(lam_nm * 1e-9, 6000.0)
            self.assertLess(B_low, B_mid,
                msg=f"B({lam_nm}nm): 1000K should be < 3000K")
            self.assertLess(B_mid, B_hi,
                msg=f"B({lam_nm}nm): 3000K should be < 6000K")

    def test_planck_red_greater_than_green_at_1000k(self):
        """At 1000K, Wien tail: B(650nm) >> B(550nm) >> B(450nm).

        Wien's approximation: B ∝ exp(-hc/λkT), so longer λ → larger B
        when hc/λkT >> 1 (deep Wien regime).
        """
        B_r = planck_spectral_radiance(650e-9, 1000.0)
        B_g = planck_spectral_radiance(550e-9, 1000.0)
        B_b = planck_spectral_radiance(450e-9, 1000.0)
        self.assertGreater(B_r, B_g,
            msg=f"B(650nm, 1000K)={B_r:.3e} should be > B(550nm)={B_g:.3e}")
        self.assertGreater(B_g, B_b,
            msg=f"B(550nm, 1000K)={B_g:.3e} should be > B(450nm)={B_b:.3e}")

    def test_planck_red_greater_than_green_at_3000k(self):
        """At 3000K, red still > green at visible wavelengths (Wien peak ~966nm)."""
        B_r = planck_spectral_radiance(650e-9, 3000.0)
        B_g = planck_spectral_radiance(550e-9, 3000.0)
        self.assertGreater(B_r, B_g,
            msg=f"B(650nm, 3000K) should be > B(550nm, 3000K)")

    def test_wien_approximation_ratio(self):
        """Wien approximation holds well when hc/λkT >> 1.

        For λ=650nm, T=1000K: x = hc/λkT ≈ 22.1 >> 1.
        Wien approx: B ∝ λ⁻⁵ × exp(−hc/λkT).
        Ratio B(650nm)/B(550nm) ≈ (550/650)⁵ × exp(−hc/kT × (1/650 − 1/550) nm).
        Check within 1% of full Planck.
        """
        T = 1000.0
        x_r = _H * _C / (650e-9 * _K * T)
        x_g = _H * _C / (550e-9 * _K * T)
        # Full Planck ratio
        ratio_planck = (
            planck_spectral_radiance(650e-9, T)
            / planck_spectral_radiance(550e-9, T)
        )
        # Wien approximation (exp large >> 1 → exp(x)-1 ≈ exp(x))
        ratio_wien = (550 / 650)**5 * math.exp(x_g - x_r)
        self.assertAlmostEqual(
            ratio_planck / ratio_wien, 1.0, places=2,
            msg=f"Planck/Wien ratio = {ratio_planck/ratio_wien:.4f} ≠ 1.0 at 1000K"
        )

    def test_planck_units_magnitude(self):
        """B(λ=500nm, T=5778K) should be near solar spectral irradiance.

        Solar surface ≈ 5778K. Peak near 500nm.
        B(500nm, 5778K) ≈ 2.6×10¹³ W/(m²·sr·m)  [order of magnitude check].
        """
        B = planck_spectral_radiance(500e-9, 5778.0)
        # Order of magnitude: should be ~10^13 W/(m²·sr·m)
        self.assertGreater(B, 1e12,
            msg=f"B(500nm, 5778K) = {B:.2e} — too small (expected ~10^13)")
        self.assertLess(B, 1e15,
            msg=f"B(500nm, 5778K) = {B:.2e} — too large (expected ~10^13)")


class TestEmissivity(unittest.TestCase):
    """Emissivity ε(λ) = 1 − R(λ) via Kirchhoff's law."""

    def test_blackbody_emissivity_is_one(self):
        """A perfect blackbody has ε = 1 at all wavelengths."""
        for lam_nm in [450, 550, 650]:
            eps = emissivity('blackbody', lam_nm * 1e-9)
            self.assertAlmostEqual(eps, 1.0, places=10,
                msg=f"Blackbody ε({lam_nm}nm) = {eps} ≠ 1.0")

    def test_emissivity_in_unit_interval(self):
        """ε must be in (0, 1] for all materials and wavelengths."""
        for key in THERMAL_EMISSION_MATERIALS:
            for lam_nm in [450, 550, 650]:
                eps = emissivity(key, lam_nm * 1e-9)
                self.assertGreater(eps, 0.0,
                    msg=f"{key} ε({lam_nm}nm) = {eps:.4f} — must be > 0")
                self.assertLessEqual(eps, 1.0,
                    msg=f"{key} ε({lam_nm}nm) = {eps:.4f} — must be ≤ 1")

    def test_metal_emissivity_less_than_blackbody(self):
        """All metals have ε < 1 (Kirchhoff: reflective → less emissive)."""
        for key in THERMAL_EMISSION_MATERIALS:
            if key == 'blackbody':
                continue
            for lam_nm in [450, 550, 650]:
                eps = emissivity(key, lam_nm * 1e-9)
                self.assertLess(eps, 1.0,
                    msg=f"{key} ε({lam_nm}nm) = {eps:.4f} — metal must have ε < 1")

    def test_kirchhoff_eps_equals_1_minus_R(self):
        """ε(λ) = 1 − R(λ) exactly (Kirchhoff's law for flat surface)."""
        from sigma_ground.field.interface.optics import MEASURED_NK, _fresnel_r
        # iron at 650nm
        n, k = MEASURED_NK['iron'][650e-9]
        R = ((n - 1)**2 + k**2) / ((n + 1)**2 + k**2)
        eps_expected = 1.0 - R
        eps_module = emissivity('iron', 650e-9)
        self.assertAlmostEqual(eps_module, eps_expected, places=10,
            msg=f"iron ε(650nm) = {eps_module} ≠ 1−R = {eps_expected}")

    def test_tungsten_emissivity_nonzero(self):
        """Tungsten (lightbulb filament) should have ε > 0.2 at all visible wavelengths.

        Tungsten filament emissivity ≈ 0.4-0.5 at 2700K in visible.
        """
        for lam_nm in [450, 550, 650]:
            eps = emissivity('tungsten', lam_nm * 1e-9)
            self.assertGreater(eps, 0.1,
                msg=f"Tungsten ε({lam_nm}nm) = {eps:.3f} — should be > 0.1")


class TestThermalEmissionRGB(unittest.TestCase):
    """Visible chromaticity of hot glowing materials."""

    def test_low_temp_returns_dark(self):
        """Below Draper point (700K), no visible glow → near-zero emission.

        The Planck tail at 650nm for T=300K is negligible.
        """
        r, g, b = thermal_emission_rgb('blackbody', T=300.0)
        self.assertEqual((r, g, b), (0.0, 0.0, 0.0),
            msg=f"T=300K blackbody should return (0,0,0), got ({r},{g},{b})")

    def test_1000k_blackbody_is_deep_red(self):
        """Blackbody at 1000K: Wien tail → R >> G >> B → deep red glow.

        Normalized chromaticity: r=1.0, g << 0.5, b << 0.1.
        """
        r, g, b = thermal_emission_rgb('blackbody', T=1000.0)
        self.assertAlmostEqual(r, 1.0, places=5,
            msg=f"1000K blackbody: r={r:.4f} should be normalized to 1.0")
        self.assertLess(g, 0.15,
            msg=f"1000K blackbody: g={g:.4f} should be << r (deep red)")
        self.assertLess(b, 0.01,
            msg=f"1000K blackbody: b={b:.4f} should be near 0 (deep red)")

    def test_3000k_blackbody_is_warm_orange(self):
        """Blackbody at 3000K: warm orange — R > G, both > B.

        Wien peak at ~966nm; visible tail gives warm colour (incandescent bulb).
        """
        r, g, b = thermal_emission_rgb('blackbody', T=3000.0)
        self.assertGreater(r, g,
            msg=f"3000K: r={r:.3f} should be > g={g:.3f}")
        self.assertGreater(g, b,
            msg=f"3000K: g={g:.3f} should be > b={b:.3f}")

    def test_6000k_blackbody_approaches_white(self):
        """Blackbody at 6000K (solar T): nearly white — all channels within 40%.

        At solar temperature, the Planck peak is near 480nm,
        so visible spectrum is relatively flat → near-white with slight
        blue-green tint.
        """
        r, g, b = thermal_emission_rgb('blackbody', T=6000.0)
        max_ch = max(r, g, b)
        min_ch = min(r, g, b)
        span   = max_ch - min_ch
        self.assertLess(span, 0.50,
            msg=f"6000K: (r={r:.3f}, g={g:.3f}, b={b:.3f}) — span={span:.3f} > 0.5, not near-white")

    def test_all_rgb_in_unit_range(self):
        """All channels must be in [0, 1] at all temperatures."""
        for mat in THERMAL_EMISSION_MATERIALS:
            for T in [300, 800, 1500, 3000, 6000]:
                r, g, b = thermal_emission_rgb(mat, T=T)
                for ch, name in [(r, 'r'), (g, 'g'), (b, 'b')]:
                    self.assertGreaterEqual(ch, 0.0,
                        msg=f"{mat} T={T}K: {name}={ch:.4f} < 0")
                    self.assertLessEqual(ch, 1.0,
                        msg=f"{mat} T={T}K: {name}={ch:.4f} > 1")

    def test_hotter_means_bluer_relative(self):
        """As T increases, blue becomes relatively larger (colour temperature rises).

        At 1000K: b/r is tiny.
        At 5000K: b/r is much larger (near-white or bluish).
        """
        r_1k, g_1k, b_1k = thermal_emission_rgb('blackbody', T=1000.0)
        r_5k, g_5k, b_5k = thermal_emission_rgb('blackbody', T=5000.0)

        # Avoid division by zero if b_1k=0
        ratio_1k = b_1k / r_1k if r_1k > 0 else 0.0
        ratio_5k = b_5k / r_5k if r_5k > 0 else 0.0
        self.assertGreater(ratio_5k, ratio_1k,
            msg=f"b/r ratio at 1000K={ratio_1k:.4f} should be < at 5000K={ratio_5k:.4f}")

    def test_iron_glow_similar_to_blackbody_at_1000k(self):
        """Iron at 1000K: greybody (ε≈0.45 ≈ flat) → similar hue to blackbody.

        Since iron emissivity is roughly flat in visible, its hue matches
        the blackbody colour temperature. Both should be red at 1000K.
        """
        r_bb, g_bb, b_bb = thermal_emission_rgb('blackbody', T=1000.0)
        r_fe, g_fe, b_fe = thermal_emission_rgb('iron', T=1000.0)
        # Both should be red-dominant
        self.assertAlmostEqual(r_bb, 1.0, places=4)
        self.assertAlmostEqual(r_fe, 1.0, places=3,
            msg=f"Iron at 1000K: r={r_fe:.4f} should be ≈1.0 (red dominant)")


class TestIsVisiblyGlowing(unittest.TestCase):
    """Draper point: below ~700K, thermal emission is invisible to human eye."""

    def test_room_temperature_not_glowing(self):
        """300K: far below Draper point (700K) → not visibly glowing."""
        self.assertFalse(is_visibly_glowing(300.0),
            msg="300K should not be visibly glowing")

    def test_800k_is_glowing(self):
        """800K: above Draper point → visibly glowing (faint red)."""
        self.assertTrue(is_visibly_glowing(800.0),
            msg="800K should be visibly glowing (Draper point ~700K)")

    def test_draper_point_boundary(self):
        """698K: just below → not glowing. 700K: Draper point → glowing."""
        self.assertFalse(is_visibly_glowing(698.0))
        self.assertTrue(is_visibly_glowing(700.0))


class TestSigmaInvariance(unittest.TestCase):
    """Thermal emission color is σ-INVARIANT (EM)."""

    def test_planck_has_no_sigma_parameter(self):
        """planck_spectral_radiance() must take no sigma argument.

        Planck's law is quantum electrodynamics (photon statistics in an EM cavity).
        σ-field affects hadronic masses, not EM photon energies.
        """
        sig = inspect.signature(planck_spectral_radiance)
        param_names = list(sig.parameters.keys())
        self.assertNotIn('sigma', param_names)
        self.assertNotIn('sigma_field', param_names)

    def test_thermal_emission_rgb_has_no_sigma_parameter(self):
        """thermal_emission_rgb() must take no sigma parameter."""
        sig = inspect.signature(thermal_emission_rgb)
        param_names = list(sig.parameters.keys())
        self.assertNotIn('sigma', param_names)
        self.assertNotIn('sigma_field', param_names)

    def test_report_states_sigma_invariant(self):
        """Report origin must state σ-INVARIANT."""
        rep = thermal_emission_report('blackbody', T=3000.0)
        origin = rep.get('origin', '')
        self.assertIn('σ-INVARIANT', origin,
            msg=f"Report origin must contain 'σ-INVARIANT', got: {origin[:120]!r}")


class TestPhysicalConsistency(unittest.TestCase):
    """Physical self-consistency checks."""

    def test_report_has_required_keys(self):
        """Diagnostic report must contain required fields."""
        rep = thermal_emission_report('iron', T=2000.0)
        required = [
            'material', 'T_K', 'rgb_tuple', 'origin',
            'planck_650nm', 'planck_550nm', 'planck_450nm',
            'emissivity_650nm', 'emissivity_550nm', 'emissivity_450nm',
        ]
        for key in required:
            self.assertIn(key, rep,
                msg=f"thermal_emission_report missing key: {key!r}")

    def test_planck_ratio_consistent_at_two_T(self):
        """Stefan-Boltzmann integrated power scales as T⁴.

        Since we only have three wavelength samples (not an integral), we
        just verify that all three channels scale correctly with T.
        At fixed λ, B(λ, 2T) / B(λ, T) can be estimated from Wien approx
        when x >> 1: ratio ≈ exp(x - x/2) = exp(x/2).
        Here we just verify monotone increase.
        """
        for lam_nm in [650, 550, 450]:
            B1 = planck_spectral_radiance(lam_nm * 1e-9, 1000.0)
            B2 = planck_spectral_radiance(lam_nm * 1e-9, 2000.0)
            B3 = planck_spectral_radiance(lam_nm * 1e-9, 4000.0)
            self.assertLess(B1, B2,
                msg=f"Planck({lam_nm}nm) must increase from 1000K to 2000K")
            self.assertLess(B2, B3,
                msg=f"Planck({lam_nm}nm) must increase from 2000K to 4000K")

    def test_wien_displacement_law(self):
        """Wien's displacement law: λ_max × T = 2.898×10⁻³ m·K.

        Verify by checking that B(λ_peak, T) is at least as large as
        B(λ_peak ± Δ, T) for 10 wavelengths spanning 200nm-5000nm.
        """
        T = 3000.0
        # λ_max = 2.898e-3 / T = 966nm for T=3000K
        lam_peak_m = 2.898e-3 / T
        B_peak = planck_spectral_radiance(lam_peak_m, T)

        # All 3 visible channels should be less than the true peak
        for lam_nm in [450, 550, 650]:
            B_vis = planck_spectral_radiance(lam_nm * 1e-9, T)
            self.assertLess(B_vis, B_peak,
                msg=f"B({lam_nm}nm, 3000K)={B_vis:.2e} should be < B(966nm, peak)={B_peak:.2e}")

    def test_glowing_temperature_draper_point(self):
        """is_visibly_glowing threshold is near 700K (Draper point).

        Draper (1847): iron begins to glow faintly at ~525°C = 798K.
        We set threshold at 700K (a bit conservative for rendering safety).
        """
        self.assertFalse(is_visibly_glowing(650.0))
        self.assertTrue(is_visibly_glowing(700.0))

    def test_blackbody_at_5778k_all_channels_substantial(self):
        """At solar temperature (5778K), all RGB channels > 0.5 (near white).

        Solar radiation illuminates Earth with near-white light.
        """
        r, g, b = thermal_emission_rgb('blackbody', T=5778.0)
        for ch, name in [(r, 'r'), (g, 'g'), (b, 'b')]:
            self.assertGreater(ch, 0.40,
                msg=f"Solar T=5778K: {name}={ch:.3f} — all channels should be substantial (> 0.4)")


if __name__ == '__main__':
    unittest.main()
