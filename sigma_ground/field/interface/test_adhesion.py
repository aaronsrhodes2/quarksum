"""
Tests for adhesion.py — interface binding between two materials.

TDD: tests written first. Module must pass all of these.

Physics hierarchy:
  1. Work of adhesion (Dupré): W = γ₁ + γ₂ − γ₁₂
     FIRST_PRINCIPLES: thermodynamic energy balance.
  2. Interface energy (Berthelot): γ₁₂ ≈ γ₁ + γ₂ − 2√(γ₁γ₂)
     APPROXIMATION: geometric mean combining rule. Marked honestly.
  3. Contact angle (Young): cos θ = (γ_sv − γ_sl)/γ_lv
     FIRST_PRINCIPLES: force balance at triple line.
  4. σ-dependence: inherited from surface.py through both γ₁ and γ₂.
"""

import math
import unittest
import sys
import os

# Add parent to path so we can import the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestWorkOfAdhesion(unittest.TestCase):
    """Dupré equation: W₁₂ = γ₁ + γ₂ − γ₁₂.

    This is pure thermodynamics — the energy released when two
    surfaces come into contact = energy you had (two free surfaces)
    minus energy you're left with (one interface).
    """

    def test_self_adhesion_equals_twice_surface_energy(self):
        """W_AA = 2γ_A. Self-adhesion = work of cohesion.

        When material A adheres to itself, interface energy is zero
        (you're just making bulk again). So W = γ + γ − 0 = 2γ.
        """
        from sigma_ground.field.interface.adhesion import work_of_adhesion
        from sigma_ground.field.interface.surface import surface_energy

        for mat in ['iron', 'copper', 'aluminum', 'gold']:
            gamma = surface_energy(mat)
            W = work_of_adhesion(mat, mat)
            self.assertAlmostEqual(W, 2 * gamma, places=6,
                msg=f"Self-adhesion of {mat} should be 2γ")

    def test_adhesion_always_positive(self):
        """Work of adhesion must be positive for any material pair.

        Negative adhesion would mean surfaces repel spontaneously,
        which violates the assumption that bare surfaces want to bond.
        """
        from sigma_ground.field.interface.adhesion import work_of_adhesion

        materials = ['iron', 'copper', 'aluminum', 'gold', 'nickel', 'tungsten']
        for i, m1 in enumerate(materials):
            for m2 in materials[i:]:
                W = work_of_adhesion(m1, m2)
                self.assertGreater(W, 0,
                    f"W({m1},{m2}) = {W} should be > 0")

    def test_adhesion_symmetric(self):
        """W(A,B) = W(B,A). Adhesion doesn't depend on who touches whom."""
        from sigma_ground.field.interface.adhesion import work_of_adhesion

        self.assertAlmostEqual(
            work_of_adhesion('iron', 'copper'),
            work_of_adhesion('copper', 'iron'),
            places=10,
        )

    def test_cross_adhesion_less_than_stronger_self_adhesion(self):
        """W(A,B) ≤ max(W(A,A), W(B,B)).

        Cross-adhesion can't exceed the stronger self-adhesion,
        because the geometric mean ≤ the larger value.
        """
        from sigma_ground.field.interface.adhesion import work_of_adhesion

        pairs = [('iron', 'copper'), ('aluminum', 'gold'),
                 ('nickel', 'tungsten'), ('copper', 'titanium')]
        for m1, m2 in pairs:
            W_cross = work_of_adhesion(m1, m2)
            W_self_max = max(work_of_adhesion(m1, m1),
                            work_of_adhesion(m2, m2))
            self.assertLessEqual(W_cross, W_self_max * 1.001,
                f"W({m1},{m2}) should ≤ max self-adhesion")

    def test_iron_copper_reasonable_range(self):
        """Iron-copper adhesion should be in a physically reasonable range.

        Experimental: W(Fe-Cu) ~ 3-5 J/m² for clean metal contacts.
        Our broken-bond model gives lower-bound estimates, so we
        accept 1-6 J/m² as our target window.
        """
        from sigma_ground.field.interface.adhesion import work_of_adhesion

        W = work_of_adhesion('iron', 'copper')
        self.assertGreater(W, 1.0, "Iron-copper adhesion too low")
        self.assertLess(W, 6.0, "Iron-copper adhesion too high")


class TestInterfaceEnergy(unittest.TestCase):
    """Interface energy γ₁₂ — the energy cost of the A-B boundary.

    Uses Berthelot combining rule: γ₁₂ = γ₁ + γ₂ − 2√(γ₁γ₂).
    This is an APPROXIMATION (geometric mean of cross-bond energies).
    """

    def test_self_interface_is_zero(self):
        """γ(A,A) = 0. No interface energy for same-material contact."""
        from sigma_ground.field.interface.adhesion import interface_energy

        for mat in ['iron', 'copper', 'aluminum']:
            gamma_12 = interface_energy(mat, mat)
            self.assertAlmostEqual(gamma_12, 0, places=10,
                msg=f"Interface energy {mat}-{mat} should be 0")

    def test_interface_energy_always_nonnegative(self):
        """γ₁₂ ≥ 0. Interface energy can't be negative under Berthelot.

        Geometric mean: √(γ₁γ₂) ≤ (γ₁+γ₂)/2, so γ₁₂ ≥ 0.
        """
        from sigma_ground.field.interface.adhesion import interface_energy

        materials = ['iron', 'copper', 'aluminum', 'gold', 'nickel']
        for m1 in materials:
            for m2 in materials:
                gamma_12 = interface_energy(m1, m2)
                self.assertGreaterEqual(gamma_12, -1e-12,
                    f"γ({m1},{m2}) = {gamma_12} should be ≥ 0")

    def test_interface_energy_symmetric(self):
        """γ(A,B) = γ(B,A)."""
        from sigma_ground.field.interface.adhesion import interface_energy

        self.assertAlmostEqual(
            interface_energy('iron', 'gold'),
            interface_energy('gold', 'iron'),
            places=10,
        )

    def test_dissimilar_materials_have_higher_interface_energy(self):
        """More dissimilar materials → higher interface energy.

        Tungsten (γ ~ 3.3) and aluminum (γ ~ 0.9) are very different.
        Iron (γ ~ 1.6) and nickel (γ ~ 1.8) are close.
        The dissimilar pair should have higher interface energy.
        """
        from sigma_ground.field.interface.adhesion import interface_energy

        gamma_W_Al = interface_energy('tungsten', 'aluminum')
        gamma_Fe_Ni = interface_energy('iron', 'nickel')
        self.assertGreater(gamma_W_Al, gamma_Fe_Ni,
            "W-Al interface should cost more than Fe-Ni")


class TestSigmaDependence(unittest.TestCase):
    """Adhesion responds to σ through both surface energies."""

    def test_adhesion_at_sigma_zero_matches_standard(self):
        """At σ=0, adhesion with sigma should match plain adhesion."""
        from sigma_ground.field.interface.adhesion import (
            work_of_adhesion, work_of_adhesion_at_sigma,
        )

        for m1, m2 in [('iron', 'copper'), ('aluminum', 'gold')]:
            W0 = work_of_adhesion(m1, m2)
            Ws = work_of_adhesion_at_sigma(m1, m2, sigma=0.0)
            self.assertAlmostEqual(W0, Ws, places=10,
                msg=f"W({m1},{m2}) at σ=0 should match standard")

    def test_sigma_shifts_adhesion(self):
        """Large σ should shift adhesion (through mass correction).

        At σ=0.5, QCD mass is e^0.5 ≈ 1.65× heavier.
        Surface energies shift → adhesion shifts.
        The shift should be nonzero but small (~1%).
        """
        from sigma_ground.field.interface.adhesion import (
            work_of_adhesion, work_of_adhesion_at_sigma,
        )

        W0 = work_of_adhesion('iron', 'copper')
        W_sigma = work_of_adhesion_at_sigma('iron', 'copper', sigma=0.5)
        self.assertNotAlmostEqual(W0, W_sigma, places=4,
            msg="σ=0.5 should shift adhesion measurably")

    def test_earth_sigma_negligible_shift(self):
        """At Earth's surface (σ ~ 7e-10), adhesion shift is negligible."""
        from sigma_ground.field.interface.adhesion import (
            work_of_adhesion, work_of_adhesion_at_sigma,
        )

        W0 = work_of_adhesion('iron', 'copper')
        W_earth = work_of_adhesion_at_sigma('iron', 'copper', sigma=7e-10)
        relative = abs(W_earth - W0) / W0
        self.assertLess(relative, 1e-8, "Earth σ should be negligible")


class TestAdhesionDecomposition(unittest.TestCase):
    """Decompose adhesion into EM and QCD contributions."""

    def test_decomposition_sums_to_total(self):
        """EM + QCD = total work of adhesion."""
        from sigma_ground.field.interface.adhesion import adhesion_decomposition

        for m1, m2 in [('iron', 'copper'), ('aluminum', 'gold')]:
            d = adhesion_decomposition(m1, m2, sigma=0.0)
            total = d['em_component_j_m2'] + d['qcd_component_j_m2']
            self.assertAlmostEqual(total, d['total_j_m2'], places=10)

    def test_em_dominates(self):
        """EM component should be >90% of total at σ=0."""
        from sigma_ground.field.interface.adhesion import adhesion_decomposition

        d = adhesion_decomposition('iron', 'copper', sigma=0.0)
        em_frac = d['em_component_j_m2'] / d['total_j_m2']
        self.assertGreater(em_frac, 0.90,
            f"EM fraction {em_frac:.4f} should dominate")


class TestContactAngle(unittest.TestCase):
    """Young's equation: cos θ = (γ_sv − γ_sl) / γ_lv.

    This is a force balance at the triple line where solid, liquid,
    and vapor meet. It's FIRST_PRINCIPLES (Newton's laws on the contact
    line). But applying it requires knowing γ_lv (surface tension of
    the liquid), which is MEASURED.
    """

    def test_metal_on_metal_small_angle(self):
        """Metal-metal contacts should have small contact angles.

        When both surfaces are high-energy metals, adhesion is strong
        and the contact angle should be small (good wetting).
        We test with a liquid metal reference surface tension.
        """
        from sigma_ground.field.interface.adhesion import contact_angle

        # Liquid copper on solid iron — good wetting expected
        # γ_lv for liquid copper ≈ 1.3 J/m² (MEASURED)
        theta = contact_angle('iron', 'copper', gamma_lv=1.3)
        self.assertIsNotNone(theta, "Should have a valid contact angle")
        self.assertLess(theta, 90, "Metal-metal should wet well (θ < 90°)")

    def test_angle_in_valid_range(self):
        """Contact angle must be 0° ≤ θ ≤ 180°."""
        from sigma_ground.field.interface.adhesion import contact_angle

        theta = contact_angle('iron', 'aluminum', gamma_lv=0.9)
        if theta is not None:
            self.assertGreaterEqual(theta, 0)
            self.assertLessEqual(theta, 180)

    def test_complete_wetting_when_strong_adhesion(self):
        """When W₁₂ ≥ 2γ_lv, complete wetting (θ=0).

        This is the Young-Dupré criterion: cos θ = W₁₂/γ_lv − 1.
        If W₁₂ ≥ 2γ_lv, cos θ ≥ 1, which means θ = 0 (complete spread).
        """
        from sigma_ground.field.interface.adhesion import contact_angle

        # Use a very low surface tension liquid → guaranteed wetting
        theta = contact_angle('tungsten', 'tungsten', gamma_lv=0.01)
        self.assertEqual(theta, 0,
            "Very low γ_lv should give complete wetting (θ=0°)")


class TestNagathaIntegration(unittest.TestCase):
    """Adhesion properties in Nagatha-compatible export format."""

    def test_adhesion_properties_format(self):
        """Export should contain required fields."""
        from sigma_ground.field.interface.adhesion import material_adhesion_properties

        props = material_adhesion_properties('iron', 'copper')
        required = ['work_of_adhesion_j_m2', 'interface_energy_j_m2',
                    'material_1', 'material_2', 'sigma',
                    'em_fraction', 'origin_tag']
        for field in required:
            self.assertIn(field, props, f"Missing field: {field}")

    def test_origin_tags_honest(self):
        """Origin tags should mark the approximation honestly."""
        from sigma_ground.field.interface.adhesion import material_adhesion_properties

        props = material_adhesion_properties('iron', 'copper')
        tag = props['origin_tag']
        # Must acknowledge the Berthelot approximation
        self.assertIn('APPROXIMATION', tag,
            "Origin tag must acknowledge the Berthelot approximation")


if __name__ == '__main__':
    unittest.main()
