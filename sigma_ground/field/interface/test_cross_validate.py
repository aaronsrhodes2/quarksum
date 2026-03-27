"""
Cross-validation: Interface physics vs QuarkSum σ-chain.

The adhesion and mechanical modules compute σ-corrections to material
properties. QuarkSum computes σ-corrections to nuclear mass. Both
flow through the SAME physical pathway:

  Nuclear mass (99% QCD) → scales with e^σ → shifts lattice dynamics
  → shifts cohesive energy → shifts surface/adhesion/mechanical properties

These tests verify that the two codebases agree on:
  1. The QCD mass fraction (the load-bearing constant)
  2. The mass ratio at arbitrary σ
  3. The direction and magnitude of σ-corrections

If any of these disagree, the two projects have diverged and one
of them is lying about the physics.

IMPORTANT: These tests import from BOTH quarksum.core.sigma AND
local_library. They are the seam where the two projects meet.
"""

import math
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestConstantsAgreement(unittest.TestCase):
    """The two projects must use the same fundamental constants."""

    def test_xi_matches(self):
        """ξ must be identical in both projects."""
        from sigma_ground.field.constants import XI as local_xi
        from sigma_ground.inventory.core.sigma import XI as qs_xi

        self.assertEqual(local_xi, qs_xi,
            f"ξ mismatch: local={local_xi}, quarksum={qs_xi}")

    def test_qcd_fraction_matches(self):
        """Proton QCD fraction must agree at machine precision.

        This is the load-bearing constant. If these disagree,
        every σ-correction in both projects is inconsistent.
        """
        from sigma_ground.field.constants import PROTON_QCD_FRACTION
        from sigma_ground.inventory.core.sigma import nucleon_qcd_fraction

        qs_frac = nucleon_qcd_fraction()['proton']['qcd_fraction']

        # Allow tiny floating point difference (different computation paths)
        self.assertAlmostEqual(PROTON_QCD_FRACTION, qs_frac, places=3,
            msg=f"QCD fraction: local={PROTON_QCD_FRACTION:.6f}, "
                f"quarksum={qs_frac:.6f}")

    def test_scale_ratio_matches(self):
        """e^σ must agree exactly (both are just math.exp)."""
        from sigma_ground.field.scale import scale_ratio as local_sr
        from sigma_ground.inventory.core.sigma import scale_ratio as qs_sr

        for sigma in [0.0, 0.001, 0.1, 0.5, 1.0, 1.85]:
            self.assertAlmostEqual(local_sr(sigma), qs_sr(sigma), places=12,
                msg=f"scale_ratio diverged at σ={sigma}")


class TestAdhesionCrossValidation(unittest.TestCase):
    """Adhesion σ-correction must be consistent with QuarkSum mass shift.

    The adhesion σ-pathway:
      σ → mass_ratio → √mass_ratio → ZPE correction → E_coh shift
      → surface energy shift → adhesion shift

    QuarkSum σ-pathway:
      σ → proton_mass(σ) / proton_mass(0) = mass_ratio

    Both must compute the same mass_ratio for a given σ.
    """

    def test_mass_ratio_agreement(self):
        """The nuclear mass ratio at σ must match between projects.

        local_library computes: mass_ratio = (1 - f_qcd) + f_qcd × e^σ
        QuarkSum computes: mass_ratio = proton_mass(σ) / proton_mass(0)

        These should agree within 1% (different decomposition paths).
        """
        from sigma_ground.field.constants import PROTON_QCD_FRACTION
        from sigma_ground.field.scale import scale_ratio
        from sigma_ground.inventory.core.sigma import proton_mass_mev

        for sigma in [0.0, 0.01, 0.1, 0.5, 1.0]:
            # local_library's mass ratio (used in surface/adhesion/mechanical)
            f_qcd = PROTON_QCD_FRACTION
            local_ratio = (1.0 - f_qcd) + f_qcd * scale_ratio(sigma)

            # QuarkSum's mass ratio (from nucleon mass decomposition)
            qs_ratio = proton_mass_mev(sigma) / proton_mass_mev(0.0)

            self.assertAlmostEqual(local_ratio, qs_ratio, places=3,
                msg=f"Mass ratio at σ={sigma}: "
                    f"local={local_ratio:.6f}, qs={qs_ratio:.6f}")

    def test_adhesion_sigma_direction(self):
        """Higher σ → heavier nuclei → stiffer lattice → stronger adhesion.

        QuarkSum says: proton gets heavier with σ.
        Adhesion module says: W increases with σ.
        These must point the same direction.
        """
        from sigma_ground.field.interface.adhesion import work_of_adhesion
        from sigma_ground.inventory.core.sigma import proton_mass_mev

        sigma = 0.5

        # QuarkSum: mass goes up
        mass_up = proton_mass_mev(sigma) > proton_mass_mev(0.0)
        self.assertTrue(mass_up, "QuarkSum: proton should be heavier at σ>0")

        # Adhesion: W goes up (through ZPE → tighter binding)
        W0 = work_of_adhesion('iron', 'copper', sigma=0.0)
        W_sigma = work_of_adhesion('iron', 'copper', sigma=sigma)
        adhesion_up = W_sigma > W0
        self.assertTrue(adhesion_up, "Adhesion should increase with σ")

    def test_adhesion_sensitivity_consistent_with_mass_shift(self):
        """The fractional adhesion shift should be << the fractional mass shift.

        Nuclear mass shifts ~99% with σ (because 99% is QCD).
        But adhesion only shifts ~1% with σ (because bonding is EM,
        only the ZPE channel couples to mass).

        So: δW/W << δm/m. If adhesion shifts MORE than mass,
        something is very wrong.
        """
        from sigma_ground.field.interface.adhesion import work_of_adhesion
        from sigma_ground.inventory.core.sigma import proton_mass_mev

        sigma = 0.5

        # Fractional mass shift
        m0 = proton_mass_mev(0.0)
        m_sigma = proton_mass_mev(sigma)
        delta_m = (m_sigma - m0) / m0

        # Fractional adhesion shift
        W0 = work_of_adhesion('iron', 'copper', sigma=0.0)
        W_sigma = work_of_adhesion('iron', 'copper', sigma=sigma)
        delta_W = (W_sigma - W0) / W0

        self.assertGreater(delta_m, delta_W,
            f"Adhesion shift ({delta_W:.4f}) should be << mass shift ({delta_m:.4f})")

        # Adhesion should shift by roughly f_zpe × delta_m
        # f_zpe = 0.01, so δW/W ≈ 0.01 × δm/m × correction_factor
        ratio = delta_W / delta_m if delta_m > 0 else 0
        self.assertLess(ratio, 0.1,
            f"Adhesion/mass ratio {ratio:.4f} too high — "
            "adhesion shouldn't shift more than 10% of mass")


class TestMechanicalCrossValidation(unittest.TestCase):
    """Mechanical σ-correction must be consistent with QuarkSum mass shift.

    The mechanical σ-pathway:
      σ → mass_ratio → ZPE correction → E_coh shift → K shift → E, G shift

    Same mass_ratio, same ZPE, same direction. The leverage test:
    does σ amplify or suppress the mechanical response correctly?
    """

    def test_bulk_modulus_sigma_direction(self):
        """Higher σ → heavier nuclei → stiffer lattice → higher K.

        Same direction as adhesion, same reason.
        """
        from sigma_ground.field.interface.mechanical import bulk_modulus
        from sigma_ground.inventory.core.sigma import proton_mass_mev

        sigma = 0.5

        K0 = bulk_modulus('iron', sigma=0.0)
        K_sigma = bulk_modulus('iron', sigma=sigma)

        # Mass goes up → K should go up
        self.assertGreater(K_sigma, K0,
            "Bulk modulus should increase with σ (stiffer lattice)")

    def test_mechanical_sensitivity_bounded(self):
        """Fractional K shift should be << fractional mass shift.

        Same argument as adhesion: bonding is EM, only ZPE couples.
        """
        from sigma_ground.field.interface.mechanical import bulk_modulus
        from sigma_ground.inventory.core.sigma import proton_mass_mev

        sigma = 0.5

        m0 = proton_mass_mev(0.0)
        m_sigma = proton_mass_mev(sigma)
        delta_m = (m_sigma - m0) / m0

        K0 = bulk_modulus('iron', sigma=0.0)
        K_sigma = bulk_modulus('iron', sigma=sigma)
        delta_K = (K_sigma - K0) / K0

        self.assertGreater(delta_m, delta_K,
            f"K shift ({delta_K:.4f}) should be << mass shift ({delta_m:.4f})")

    def test_mechanical_and_adhesion_same_sensitivity(self):
        """Adhesion and mechanical must have the same σ-sensitivity.

        Both flow through the same pathway (E_coh correction from
        ZPE × mass_ratio). Their fractional shifts should be equal
        (they use the same f_zpe = 0.01 and same mass_ratio).
        """
        from sigma_ground.field.interface.adhesion import work_of_adhesion
        from sigma_ground.field.interface.mechanical import bulk_modulus

        sigma = 0.5

        # Adhesion fractional shift
        W0 = work_of_adhesion('iron', 'iron', sigma=0.0)
        W_s = work_of_adhesion('iron', 'iron', sigma=sigma)
        delta_W = (W_s - W0) / W0

        # Mechanical fractional shift
        K0 = bulk_modulus('iron', sigma=0.0)
        K_s = bulk_modulus('iron', sigma=sigma)
        delta_K = (K_s - K0) / K0

        # They should be nearly identical (same E_coh correction)
        self.assertAlmostEqual(delta_W, delta_K, places=4,
            msg=f"Adhesion shift ({delta_W:.6f}) and mechanical shift "
                f"({delta_K:.6f}) should match — same σ pathway")

    def test_all_materials_consistent_direction(self):
        """Every material: K(σ>0) > K(0). No exceptions."""
        from sigma_ground.field.interface.mechanical import bulk_modulus
        from sigma_ground.field.interface.surface import MATERIALS

        sigma = 0.5
        for mat in MATERIALS:
            K0 = bulk_modulus(mat, sigma=0.0)
            K_s = bulk_modulus(mat, sigma=sigma)
            self.assertGreater(K_s, K0,
                msg=f"{mat}: K should increase with σ")


class TestLeverageRatio(unittest.TestCase):
    """The leverage test: how much does σ amplify material response?

    At σ=0.5:
      - Nuclear mass shifts by ~63% (e^0.5 ≈ 1.65, QCD is 99%)
      - Material properties shift by ~0.3% (only ZPE channel)

    The leverage ratio = δ(property) / δ(mass) ≈ f_zpe = 0.01.
    This is the key number. If it's wrong, the σ-chain is broken.
    """

    def test_leverage_ratio_near_f_zpe(self):
        """The leverage ratio should be approximately f_zpe = 0.01.

        Not exact — the √mass_ratio pathway introduces nonlinearity.
        But it should be in the right ballpark (0.001 to 0.05).
        """
        from sigma_ground.field.interface.mechanical import bulk_modulus
        from sigma_ground.inventory.core.sigma import proton_mass_mev

        sigma = 0.5
        m0 = proton_mass_mev(0.0)
        m_s = proton_mass_mev(sigma)
        delta_m = (m_s - m0) / m0

        K0 = bulk_modulus('iron', sigma=0.0)
        K_s = bulk_modulus('iron', sigma=sigma)
        delta_K = (K_s - K0) / K0

        leverage = delta_K / delta_m
        self.assertGreater(leverage, 0.001,
            f"Leverage {leverage:.4f} too low — σ not reaching material")
        self.assertLess(leverage, 0.05,
            f"Leverage {leverage:.4f} too high — σ amplification unphysical")


if __name__ == '__main__':
    unittest.main()
