"""
Tests for mechanical.py — elastic and strength properties from bond physics.

TDD: tests written first. Module must pass all of these.

Physics hierarchy:
  1. Bulk modulus K: from cohesive energy / atomic volume × geometric factor.
     FIRST_PRINCIPLES: harmonic approximation of interatomic potential well.
  2. Young's modulus E = 3K(1−2ν). FIRST_PRINCIPLES: continuum elasticity.
  3. Shear modulus G = E/(2(1+ν)). FIRST_PRINCIPLES: continuum elasticity.
  4. Theoretical shear strength τ_th = G/(2π). FIRST_PRINCIPLES: Frenkel (1926).
  5. Poisson's ratio ν: MEASURED per material.
  6. σ-dependence: inherited through cohesive energy (nuclear mass correction).
"""

import math
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestBulkModulus(unittest.TestCase):
    """Bulk modulus K — resistance to uniform compression.

    Derived from cohesive energy and atomic volume:
      K ≈ E_coh × n_atoms × f(structure)

    This is the harmonic approximation: the curvature of the energy
    well at equilibrium determines the stiffness.
    """

    def test_iron_bulk_modulus_order_of_magnitude(self):
        """Iron: experimental K = 170 GPa. Accept ±50%."""
        from sigma_ground.field.interface.mechanical import bulk_modulus

        K = bulk_modulus('iron')
        K_gpa = K / 1e9
        self.assertGreater(K_gpa, 85, f"Iron K={K_gpa:.0f} GPa too low")
        self.assertLess(K_gpa, 340, f"Iron K={K_gpa:.0f} GPa too high")

    def test_copper_bulk_modulus_order_of_magnitude(self):
        """Copper: experimental K = 140 GPa. Accept ±50%."""
        from sigma_ground.field.interface.mechanical import bulk_modulus

        K = bulk_modulus('copper')
        K_gpa = K / 1e9
        self.assertGreater(K_gpa, 70, f"Copper K={K_gpa:.0f} GPa too low")
        self.assertLess(K_gpa, 280, f"Copper K={K_gpa:.0f} GPa too high")

    def test_tungsten_stiffest(self):
        """Tungsten should have highest bulk modulus (highest E_coh)."""
        from sigma_ground.field.interface.mechanical import bulk_modulus

        K_W = bulk_modulus('tungsten')
        for mat in ['iron', 'copper', 'aluminum', 'gold']:
            K_other = bulk_modulus(mat)
            self.assertGreater(K_W, K_other,
                msg=f"Tungsten K should exceed {mat}")

    def test_aluminum_softer_than_iron(self):
        """Aluminum (K~76 GPa) should be softer than iron (K~170 GPa)."""
        from sigma_ground.field.interface.mechanical import bulk_modulus

        self.assertLess(bulk_modulus('aluminum'), bulk_modulus('iron'))

    def test_always_positive(self):
        """Bulk modulus must be positive for all materials."""
        from sigma_ground.field.interface.mechanical import bulk_modulus
        from sigma_ground.field.interface.surface import MATERIALS

        for mat in MATERIALS:
            K = bulk_modulus(mat)
            self.assertGreater(K, 0, msg=f"{mat} K should be > 0")


class TestYoungsModulus(unittest.TestCase):
    """Young's modulus E — resistance to uniaxial tension/compression.

    E = 3K(1 − 2ν). FIRST_PRINCIPLES: isotropic elasticity.
    Requires Poisson's ratio ν (MEASURED).
    """

    def test_iron_youngs_modulus(self):
        """Iron: experimental E = 211 GPa. Accept ±50%."""
        from sigma_ground.field.interface.mechanical import youngs_modulus

        E = youngs_modulus('iron')
        E_gpa = E / 1e9
        self.assertGreater(E_gpa, 105, f"Iron E={E_gpa:.0f} GPa too low")
        self.assertLess(E_gpa, 420, f"Iron E={E_gpa:.0f} GPa too high")

    def test_aluminum_youngs_modulus(self):
        """Aluminum: experimental E = 70 GPa. Accept ±50%."""
        from sigma_ground.field.interface.mechanical import youngs_modulus

        E = youngs_modulus('aluminum')
        E_gpa = E / 1e9
        self.assertGreater(E_gpa, 35, f"Al E={E_gpa:.0f} GPa too low")
        self.assertLess(E_gpa, 140, f"Al E={E_gpa:.0f} GPa too high")

    def test_youngs_less_than_3x_bulk(self):
        """E ≤ 3K always (since ν ≥ 0 for normal materials).

        E = 3K(1-2ν). For ν ∈ [0, 0.5], the factor (1-2ν) ∈ [0, 1].
        """
        from sigma_ground.field.interface.mechanical import youngs_modulus, bulk_modulus

        for mat in ['iron', 'copper', 'aluminum', 'gold', 'tungsten']:
            E = youngs_modulus(mat)
            K = bulk_modulus(mat)
            self.assertLessEqual(E, 3.001 * K,
                msg=f"{mat}: E should ≤ 3K")


class TestShearModulus(unittest.TestCase):
    """Shear modulus G — resistance to shape change at constant volume.

    G = E / (2(1+ν)). FIRST_PRINCIPLES: isotropic elasticity.
    """

    def test_iron_shear_modulus(self):
        """Iron: experimental G = 82 GPa. Accept ±50%."""
        from sigma_ground.field.interface.mechanical import shear_modulus

        G = shear_modulus('iron')
        G_gpa = G / 1e9
        self.assertGreater(G_gpa, 41, f"Iron G={G_gpa:.0f} GPa too low")
        self.assertLess(G_gpa, 164, f"Iron G={G_gpa:.0f} GPa too high")

    def test_shear_less_than_youngs(self):
        """G < E for all materials with ν > −0.5 (all real materials)."""
        from sigma_ground.field.interface.mechanical import shear_modulus, youngs_modulus

        for mat in ['iron', 'copper', 'aluminum', 'nickel']:
            G = shear_modulus(mat)
            E = youngs_modulus(mat)
            self.assertLess(G, E, msg=f"{mat}: G should < E")

    def test_gold_soft(self):
        """Gold (G~27 GPa) should be one of the softest metals."""
        from sigma_ground.field.interface.mechanical import shear_modulus

        G_Au = shear_modulus('gold')
        G_Fe = shear_modulus('iron')
        self.assertLess(G_Au, G_Fe, "Gold should be softer than iron")


class TestElasticRelations(unittest.TestCase):
    """Verify internal consistency of elastic constants.

    These relations are FIRST_PRINCIPLES (continuum mechanics).
    If they fail, the code has a bug, not a physics problem.
    """

    def test_E_from_K_and_nu(self):
        """E = 3K(1−2ν) must hold exactly."""
        from sigma_ground.field.interface.mechanical import (
            youngs_modulus, bulk_modulus, MECHANICAL_DATA,
        )

        for mat in ['iron', 'copper', 'aluminum']:
            E = youngs_modulus(mat)
            K = bulk_modulus(mat)
            nu = MECHANICAL_DATA[mat]['poisson_ratio']
            E_check = 3 * K * (1 - 2 * nu)
            self.assertAlmostEqual(E, E_check, places=5,
                msg=f"{mat}: E ≠ 3K(1−2ν)")

    def test_G_from_E_and_nu(self):
        """G = E/(2(1+ν)) must hold exactly."""
        from sigma_ground.field.interface.mechanical import (
            shear_modulus, youngs_modulus, MECHANICAL_DATA,
        )

        for mat in ['iron', 'copper', 'aluminum']:
            G = shear_modulus(mat)
            E = youngs_modulus(mat)
            nu = MECHANICAL_DATA[mat]['poisson_ratio']
            G_check = E / (2 * (1 + nu))
            self.assertAlmostEqual(G, G_check, places=5,
                msg=f"{mat}: G ≠ E/(2(1+ν))")


class TestTheoreticalStrength(unittest.TestCase):
    """Frenkel theoretical shear strength: τ_th = G/(2π).

    FIRST_PRINCIPLES: energy barrier for one atomic plane sliding
    over another, assuming perfect crystal (no dislocations).

    Real yield is 100-1000× lower. We compute theoretical and
    note the limitation honestly.
    """

    def test_theoretical_strength_positive(self):
        """Theoretical strength must be positive."""
        from sigma_ground.field.interface.mechanical import theoretical_shear_strength
        from sigma_ground.field.interface.surface import MATERIALS

        for mat in MATERIALS:
            tau = theoretical_shear_strength(mat)
            self.assertGreater(tau, 0, msg=f"{mat} τ_th should be > 0")

    def test_theoretical_strength_exceeds_real(self):
        """Theoretical >> real yield strength.

        Iron theoretical ~13 GPa vs real yield ~0.2 GPa.
        Theoretical should be at least 10× real for metals.
        """
        from sigma_ground.field.interface.mechanical import theoretical_shear_strength

        tau_Fe = theoretical_shear_strength('iron')
        tau_gpa = tau_Fe / 1e9
        # Real iron yield ~0.2 GPa, so theoretical should be >> 0.2
        self.assertGreater(tau_gpa, 2.0,
            f"Iron τ_th = {tau_gpa:.1f} GPa should be >> real yield")

    def test_frenkel_relation(self):
        """τ_th = G/(2π) must hold exactly."""
        from sigma_ground.field.interface.mechanical import (
            theoretical_shear_strength, shear_modulus,
        )

        for mat in ['iron', 'copper', 'tungsten']:
            tau = theoretical_shear_strength(mat)
            G = shear_modulus(mat)
            self.assertAlmostEqual(tau, G / (2 * math.pi), places=3,
                msg=f"{mat}: τ_th ≠ G/(2π)")


class TestSigmaDependence(unittest.TestCase):
    """Mechanical properties respond to σ through cohesive energy."""

    def test_sigma_zero_matches_standard(self):
        """At σ=0, mechanical properties match plain values."""
        from sigma_ground.field.interface.mechanical import (
            bulk_modulus, bulk_modulus_at_sigma,
        )

        for mat in ['iron', 'copper']:
            K0 = bulk_modulus(mat)
            Ks = bulk_modulus_at_sigma(mat, sigma=0.0)
            self.assertAlmostEqual(K0, Ks, places=6,
                msg=f"{mat}: K at σ=0 should match standard")

    def test_large_sigma_shifts_modulus(self):
        """At σ=0.5, bulk modulus should shift measurably."""
        from sigma_ground.field.interface.mechanical import (
            bulk_modulus, bulk_modulus_at_sigma,
        )

        K0 = bulk_modulus('iron')
        K_sigma = bulk_modulus_at_sigma('iron', sigma=0.5)
        self.assertNotAlmostEqual(K0, K_sigma, places=4,
            msg="σ=0.5 should shift bulk modulus")

    def test_earth_sigma_negligible(self):
        """At Earth (σ~7e-10), shift should be negligible."""
        from sigma_ground.field.interface.mechanical import (
            bulk_modulus, bulk_modulus_at_sigma,
        )

        K0 = bulk_modulus('iron')
        K_earth = bulk_modulus_at_sigma('iron', sigma=7e-10)
        rel = abs(K_earth - K0) / K0
        self.assertLess(rel, 1e-8)


class TestNagathaIntegration(unittest.TestCase):
    """Mechanical properties in Nagatha-compatible format."""

    def test_mechanical_properties_format(self):
        """Export should contain required fields."""
        from sigma_ground.field.interface.mechanical import material_mechanical_properties

        props = material_mechanical_properties('iron')
        required = ['bulk_modulus_pa', 'youngs_modulus_pa',
                    'shear_modulus_pa', 'poisson_ratio',
                    'theoretical_shear_strength_pa',
                    'sigma', 'origin_tag']
        for field in required:
            self.assertIn(field, props, msg=f"Missing field: {field}")

    def test_origin_tags_honest(self):
        """Origin tags must mark Poisson's ratio as MEASURED."""
        from sigma_ground.field.interface.mechanical import material_mechanical_properties

        props = material_mechanical_properties('iron')
        tag = props['origin_tag']
        self.assertIn('MEASURED', tag,
            "Must acknowledge Poisson's ratio is MEASURED")


if __name__ == '__main__':
    unittest.main()
