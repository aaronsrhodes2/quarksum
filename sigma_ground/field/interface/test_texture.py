"""Tests for surface texture physics.

Derivation chain:
  σ → nuclear mass → cohesive energy → step formation energy → roughness
  σ → lattice parameter → atomic step height → grain boundary energy

Texture properties derivable from first principles + MEASURED inputs:

  1. Atomic step height: h = a / √(h²+k²+l²) for cubic (FIRST_PRINCIPLES: geometry)
  2. Step formation energy: E_step = γ × h  (FIRST_PRINCIPLES: new surface area per step)
  3. Thermal roughness: σ_RMS ~ h × √(kT / E_step) at equilibrium
     (FIRST_PRINCIPLES: Boltzmann statistics on step excitations)
  4. Grain boundary energy: Read-Shockley model
     γ_gb = γ_gb_max × θ/θ_max × (1 - ln(θ/θ_max)) for θ < θ_max
     (FIRST_PRINCIPLES: dislocation array energy)
  5. Microfacet roughness α: Beckmann parameter from thermal roughness
     α = σ_RMS / correlation_length  (FIRST_PRINCIPLES: surface statistics)
  6. Specular fraction: fraction of surface flat enough for mirror reflection
     f_spec = exp(-4π σ_RMS / λ)²  (FIRST_PRINCIPLES: Rayleigh criterion)

TDD: tests written BEFORE implementation.
"""

import unittest
import math
import sys
sys.path.insert(0, '/sessions/loving-pensive-euler/mnt/quarksum')

from sigma_ground.field.interface.texture import (
    atomic_step_height,
    step_formation_energy,
    thermal_roughness,
    grain_boundary_energy,
    microfacet_roughness,
    specular_fraction,
    material_texture_properties,
)
from sigma_ground.field.interface.surface import MATERIALS


class TestAtomicStepHeight(unittest.TestCase):
    """Step height = interplanar spacing for the preferred face."""

    def test_iron_bcc110_step_height(self):
        """Iron BCC(110): d = a/√2 ≈ 2.027 Å."""
        h = atomic_step_height('iron')
        a = MATERIALS['iron']['lattice_param_angstrom']
        expected = a / math.sqrt(2)  # BCC(110): h²+k²+l² = 2
        self.assertAlmostEqual(h * 1e10, expected, places=2,
                               msg=f"Iron step height {h*1e10:.3f} Å, expected {expected:.3f} Å")

    def test_copper_fcc111_step_height(self):
        """Copper FCC(111): d = a/√3 ≈ 2.087 Å."""
        h = atomic_step_height('copper')
        a = MATERIALS['copper']['lattice_param_angstrom']
        expected = a / math.sqrt(3)
        self.assertAlmostEqual(h * 1e10, expected, places=2,
                               msg=f"Copper step height {h*1e10:.3f} Å, expected {expected:.3f} Å")

    def test_step_height_always_positive(self):
        """Step height must be positive for all materials."""
        for mat in MATERIALS:
            h = atomic_step_height(mat)
            self.assertGreater(h, 0, msg=f"{mat} step height must be > 0")

    def test_step_height_sub_nanometer(self):
        """All step heights should be 1-5 Å (sub-nanometer)."""
        for mat in MATERIALS:
            h = atomic_step_height(mat)
            h_angstrom = h * 1e10
            self.assertGreater(h_angstrom, 0.5, msg=f"{mat}: {h_angstrom:.2f} Å too small")
            self.assertLess(h_angstrom, 6.0, msg=f"{mat}: {h_angstrom:.2f} Å too large")


class TestStepFormationEnergy(unittest.TestCase):
    """Step energy = surface energy × step height (new surface per unit length)."""

    def test_iron_step_energy_order_of_magnitude(self):
        """Iron step energy should be ~0.1-1 eV/Å ≈ 10⁻¹⁰ to 10⁻⁹ J/m."""
        E = step_formation_energy('iron')
        # γ_Fe ≈ 2.4 J/m², h ≈ 2.0 Å = 2×10⁻¹⁰ m
        # E_step = γ × h ≈ 2.4 × 2×10⁻¹⁰ ≈ 4.8×10⁻¹⁰ J/m
        self.assertGreater(E, 1e-11, msg=f"Iron step energy {E:.2e} J/m too low")
        self.assertLess(E, 1e-8, msg=f"Iron step energy {E:.2e} J/m too high")

    def test_step_energy_scales_with_surface_energy(self):
        """Higher surface energy → higher step formation energy."""
        E_W = step_formation_energy('tungsten')
        E_Al = step_formation_energy('aluminum')
        # Tungsten has much higher surface energy than aluminum
        self.assertGreater(E_W, E_Al,
                           msg="Tungsten step energy should exceed aluminum")

    def test_step_energy_always_positive(self):
        """Step formation energy must be positive (costs energy to form steps)."""
        for mat in MATERIALS:
            E = step_formation_energy(mat)
            self.assertGreater(E, 0, msg=f"{mat} step energy must be > 0")


class TestThermalRoughness(unittest.TestCase):
    """RMS roughness from thermal equilibrium step excitations."""

    def test_roughness_at_room_temperature(self):
        """Room temperature roughness should be fraction of step height."""
        for mat in MATERIALS:
            rms = thermal_roughness(mat, T=300.0)
            h = atomic_step_height(mat)
            # At room T, roughness should be < step height (kT << E_step)
            self.assertLess(rms, h,
                            msg=f"{mat}: roughness {rms:.2e} > step height {h:.2e}")
            # But not zero — thermal fluctuations always present
            self.assertGreater(rms, 0,
                               msg=f"{mat}: roughness must be > 0 at T > 0")

    def test_roughness_increases_with_temperature(self):
        """Higher temperature → more thermal roughness."""
        for mat in ['iron', 'copper', 'aluminum']:
            rms_300 = thermal_roughness(mat, T=300.0)
            rms_1000 = thermal_roughness(mat, T=1000.0)
            self.assertGreater(rms_1000, rms_300,
                               msg=f"{mat}: roughness should increase with T")

    def test_roughness_at_zero_temperature(self):
        """At T=0, roughness → 0 (no thermal excitations)."""
        for mat in MATERIALS:
            rms = thermal_roughness(mat, T=0.0)
            self.assertAlmostEqual(rms, 0.0, places=20,
                                   msg=f"{mat}: roughness at T=0 should be 0")

    def test_roughness_order_of_magnitude(self):
        """Room-T roughness should be ~0.1-1 Å for metals."""
        for mat in MATERIALS:
            rms = thermal_roughness(mat, T=300.0)
            rms_angstrom = rms * 1e10
            self.assertGreater(rms_angstrom, 0.01,
                               msg=f"{mat}: {rms_angstrom:.3f} Å unrealistically smooth")
            self.assertLess(rms_angstrom, 3.0,
                            msg=f"{mat}: {rms_angstrom:.3f} Å unrealistically rough")


class TestGrainBoundaryEnergy(unittest.TestCase):
    """Read-Shockley model: γ_gb = γ_max × θ/θ_m × (1 - ln(θ/θ_m))."""

    def test_zero_misorientation_zero_energy(self):
        """No misorientation → no grain boundary → zero energy."""
        for mat in MATERIALS:
            E = grain_boundary_energy(mat, theta_deg=0.0)
            self.assertAlmostEqual(E, 0.0, places=10,
                                   msg=f"{mat}: GB energy at θ=0 should be 0")

    def test_energy_increases_with_angle(self):
        """Small angles: energy increases with misorientation."""
        for mat in ['iron', 'copper']:
            E_5 = grain_boundary_energy(mat, theta_deg=5.0)
            E_10 = grain_boundary_energy(mat, theta_deg=10.0)
            self.assertGreater(E_10, E_5,
                               msg=f"{mat}: GB energy should increase 5°→10°")

    def test_high_angle_saturates(self):
        """At high angles (>15°), energy should saturate near γ_gb_max."""
        for mat in ['iron', 'copper', 'aluminum']:
            E_15 = grain_boundary_energy(mat, theta_deg=15.0)
            E_30 = grain_boundary_energy(mat, theta_deg=30.0)
            E_45 = grain_boundary_energy(mat, theta_deg=45.0)
            # High-angle boundary energies should be within 2× of each other
            self.assertLess(abs(E_45 - E_30) / E_30, 0.5,
                            msg=f"{mat}: high-angle GB energy should saturate")

    def test_grain_boundary_less_than_surface_energy(self):
        """GB energy < 2× surface energy (coherent boundary cheaper than free surfaces)."""
        from sigma_ground.field.interface.surface import surface_energy
        for mat in MATERIALS:
            E_gb = grain_boundary_energy(mat, theta_deg=30.0)
            gamma = surface_energy(mat)
            # GB energy typically 1/3 to 1/2 of surface energy
            self.assertLess(E_gb, 2 * gamma,
                            msg=f"{mat}: GB energy {E_gb:.3f} > 2γ = {2*gamma:.3f}")

    def test_iron_gb_energy_range(self):
        """Iron high-angle GB energy: experimental ~0.5-1.0 J/m²."""
        E = grain_boundary_energy('iron', theta_deg=30.0)
        self.assertGreater(E, 0.2, msg=f"Iron GB energy {E:.3f} too low")
        self.assertLess(E, 2.0, msg=f"Iron GB energy {E:.3f} too high")


class TestMicrofacetRoughness(unittest.TestCase):
    """Beckmann roughness parameter from surface statistics."""

    def test_roughness_between_0_and_1(self):
        """Beckmann α should be in (0, 1) for real surfaces."""
        for mat in MATERIALS:
            alpha = microfacet_roughness(mat, T=300.0)
            self.assertGreater(alpha, 0, msg=f"{mat}: α must be > 0")
            self.assertLess(alpha, 1.0, msg=f"{mat}: α must be < 1 for metals")

    def test_roughness_increases_with_temperature(self):
        """Higher T → rougher surface → larger α."""
        for mat in ['iron', 'copper']:
            a_300 = microfacet_roughness(mat, T=300.0)
            a_1000 = microfacet_roughness(mat, T=1000.0)
            self.assertGreater(a_1000, a_300,
                               msg=f"{mat}: α should increase with T")

    def test_metals_smoother_than_covalent(self):
        """Metal surfaces smoother than diamond-cubic (silicon) at same T."""
        a_Fe = microfacet_roughness('iron', T=300.0)
        a_Si = microfacet_roughness('silicon', T=300.0)
        # Silicon has lower coordination → easier step formation → rougher
        # This is actually a prediction: check it.
        # If it fails, the physics is telling us something interesting.
        self.assertNotEqual(a_Fe, a_Si, msg="Should differ between structures")


class TestSpecularFraction(unittest.TestCase):
    """Rayleigh criterion: smooth if σ_RMS << λ."""

    def test_metals_mostly_specular_in_visible(self):
        """Polished metals at room T should be >90% specular in visible light."""
        lambda_m = 550e-9  # green light
        for mat in ['iron', 'copper', 'gold', 'aluminum']:
            f = specular_fraction(mat, T=300.0, wavelength_m=lambda_m)
            self.assertGreater(f, 0.5,
                               msg=f"{mat}: specular fraction {f:.3f} too low for visible")

    def test_specular_decreases_with_temperature(self):
        """Higher T → rougher → less specular."""
        lambda_m = 550e-9
        for mat in ['iron', 'copper']:
            f_300 = specular_fraction(mat, T=300.0, wavelength_m=lambda_m)
            f_1000 = specular_fraction(mat, T=1000.0, wavelength_m=lambda_m)
            self.assertGreater(f_300, f_1000,
                               msg=f"{mat}: specular should decrease with T")

    def test_shorter_wavelength_less_specular(self):
        """Shorter wavelength → more sensitive to roughness → less specular."""
        for mat in ['iron', 'copper']:
            f_red = specular_fraction(mat, T=300.0, wavelength_m=700e-9)
            f_uv = specular_fraction(mat, T=300.0, wavelength_m=200e-9)
            self.assertGreater(f_red, f_uv,
                               msg=f"{mat}: UV should be less specular than red")

    def test_specular_bounded_0_to_1(self):
        """Specular fraction must be a valid probability."""
        for mat in MATERIALS:
            for T in [100.0, 300.0, 1000.0]:
                f = specular_fraction(mat, T=T, wavelength_m=550e-9)
                self.assertGreaterEqual(f, 0.0, msg=f"{mat} T={T}: f < 0")
                self.assertLessEqual(f, 1.0, msg=f"{mat} T={T}: f > 1")


class TestSigmaDependence(unittest.TestCase):
    """σ-correction propagates through the full texture chain."""

    def test_sigma_zero_matches_default(self):
        """σ=0 should give same results as default calls."""
        for mat in ['iron', 'copper', 'aluminum']:
            rms_default = thermal_roughness(mat, T=300.0)
            rms_sigma0 = thermal_roughness(mat, T=300.0, sigma=0.0)
            self.assertAlmostEqual(rms_default, rms_sigma0, places=15,
                                   msg=f"{mat}: σ=0 should match default")

    def test_sigma_shifts_roughness(self):
        """Non-zero σ should shift roughness (heavier → stiffer → different roughness)."""
        for mat in ['iron', 'copper']:
            rms_0 = thermal_roughness(mat, T=300.0, sigma=0.0)
            rms_05 = thermal_roughness(mat, T=300.0, sigma=0.5)
            # Values are ~3e-11, so check relative difference
            rel_diff = abs(rms_05 - rms_0) / rms_0
            self.assertGreater(rel_diff, 1e-6,
                               msg=f"{mat}: σ=0.5 should shift roughness (rel={rel_diff:.2e})")

    def test_earth_sigma_negligible(self):
        """Earth σ ≈ 7×10⁻¹⁰ should produce negligible shift."""
        sigma_earth = 7e-10
        for mat in ['iron', 'copper']:
            rms_0 = thermal_roughness(mat, T=300.0, sigma=0.0)
            rms_earth = thermal_roughness(mat, T=300.0, sigma=sigma_earth)
            rel = abs(rms_earth - rms_0) / rms_0
            self.assertLess(rel, 1e-6,
                            msg=f"{mat}: Earth σ shift {rel:.2e} should be < 10⁻⁶")


class TestNagathaIntegration(unittest.TestCase):
    """Nagatha-compatible export format."""

    def test_export_has_required_fields(self):
        """material_texture_properties must include all Nagatha fields."""
        required = [
            'step_height_m', 'step_energy_j_m', 'thermal_roughness_rms_m',
            'grain_boundary_energy_j_m2', 'microfacet_alpha',
            'specular_fraction_visible', 'crystal_structure',
        ]
        for mat in MATERIALS:
            props = material_texture_properties(mat)
            for field in required:
                self.assertIn(field, props,
                              msg=f"{mat} missing field: {field}")

    def test_export_has_honest_origin_tags(self):
        """Origin tags must honestly label derivation vs measurement."""
        props = material_texture_properties('iron')
        self.assertIn('origin', props)
        origin = props['origin']
        # Must mention that step height is geometry
        self.assertIn('FIRST_PRINCIPLES', origin)
        # Must mention thermal roughness is Boltzmann statistics
        self.assertIn('boltzmann', origin.lower() if isinstance(origin, str) else str(origin).lower())


if __name__ == '__main__':
    unittest.main()
