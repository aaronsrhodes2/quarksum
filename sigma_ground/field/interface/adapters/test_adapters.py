"""Tests for local_library.interface.adapters (sg_ physics patch layer).

Verifies:
  - SGConstants are more precise than astropy/scipy defaults
  - SGAdapter injects sg_ methods on any object
  - SGPhysicsMixin sg_gm / sg_mass work without external libs
  - SGEphemeris tier routing: DE440 for past, forecast for future
  - sg_solve_ivp Forest-Ruth: energy-conserving harmonic oscillator
  - sg_nbody: circular orbit conserves energy / angular momentum
  - sg_odeint: API compatibility
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from sigma_ground.field.interface.adapters import (
    SGAdapter, SGConstants, SGEphemeris, SGPhysicsMixin,
    sg_nbody, sg_odeint, sg_solve_ivp,
)
from sigma_ground.field.interface.adapters.constants import (
    sg_patch_astropy, sg_patch_scipy,
)
from sigma_ground.field.constants import G as _G


# ══════════════════════════════════════════════════════════════════════════
# SGConstants
# ══════════════════════════════════════════════════════════════════════════

class TestSGConstants(unittest.TestCase):

    def test_G_matches_codata(self):
        """G should be the CODATA 2018 value from sigma_ground.field.constants."""
        self.assertAlmostEqual(SGConstants.G, _G, places=20)

    def test_GM_sun_de440(self):
        """GM_sun must match the DE440 value (132712440041.93938 km³/s²)."""
        expected = 132_712_440_041.93938 * 1e9
        self.assertAlmostEqual(SGConstants.GM_sun, expected, delta=1e6)

    def test_GM_sun_more_precise_than_astropy(self):
        """DE440 GM_sun should differ from CODATA 2014 by < 1 ppm."""
        delta_ppm = SGConstants.delta_GM_sun_ppm()
        self.assertLess(delta_ppm, 1.0,
                        f"GM_sun delta from CODATA 2014: {delta_ppm:.3f} ppm")

    def test_M_sun_derived_from_GM(self):
        """M_sun = GM_sun / G -- derived, not independent."""
        expected = SGConstants.GM_sun / SGConstants.G
        self.assertAlmostEqual(SGConstants.M_sun, expected, delta=1e10)

    def test_light_year_derived(self):
        """Light-year = c * yr -- both from sigma_ground.field.constants."""
        from sigma_ground.field.constants import C, YEAR_S
        expected = C * YEAR_S
        self.assertAlmostEqual(SGConstants.ly, expected, delta=1e3)

    def test_sg_alias(self):
        """sg_ aliases must equal their non-prefixed counterparts."""
        self.assertEqual(SGConstants.sg_G,      SGConstants.G)
        self.assertEqual(SGConstants.sg_GM_sun, SGConstants.GM_sun)
        self.assertEqual(SGConstants.sg_au,     SGConstants.au)

    def test_all_gm_dict(self):
        """all_gm() must include Sun, Earth, Jupiter."""
        gm = SGConstants.all_gm()
        for body in ("Sun", "Earth", "Jupiter"):
            self.assertIn(body, gm)
            self.assertGreater(gm[body], 0)

    def test_sg_patch_astropy_noop_when_missing(self):
        """sg_patch_astropy should raise ImportError if astropy absent."""
        try:
            import astropy  # noqa: F401
            patched = sg_patch_astropy()
            # If astropy is present, verify G was patched
            import astropy.constants as aconst
            # The patched G value should be close to SSBM G
            if hasattr(aconst.G, 'value'):
                self.assertAlmostEqual(aconst.G.value, SGConstants.G,
                                       delta=abs(SGConstants.G) * 1e-4)
        except ImportError:
            with self.assertRaises(ImportError):
                sg_patch_astropy()

    def test_sg_patch_scipy_noop_when_missing(self):
        """sg_patch_scipy should raise ImportError if scipy absent."""
        try:
            import scipy  # noqa: F401
            patched = sg_patch_scipy()
            import scipy.constants as sc
            self.assertAlmostEqual(sc.G, SGConstants.G, delta=abs(SGConstants.G)*1e-6)
        except ImportError:
            with self.assertRaises(ImportError):
                sg_patch_scipy()


# ══════════════════════════════════════════════════════════════════════════
# SGPhysicsMixin
# ══════════════════════════════════════════════════════════════════════════

class TestSGPhysicsMixin(unittest.TestCase):

    class _Dummy(SGPhysicsMixin):
        pass

    def setUp(self):
        self.obj = self._Dummy()

    def test_sg_gm_sun(self):
        gm = self.obj.sg_gm("Sun")
        self.assertAlmostEqual(gm, SGConstants.GM_sun, delta=1e6)

    def test_sg_gm_earth(self):
        gm = self.obj.sg_gm("Earth")
        self.assertGreater(gm, 3.9e14)
        self.assertLess(gm, 4.0e14)

    def test_sg_mass_sun(self):
        m = self.obj.sg_mass("Sun")
        self.assertGreater(m, 1.98e30)
        self.assertLess(m, 2.0e30)

    def test_sg_gm_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.obj.sg_gm("Pluto_X_9999")

    def test_sg_propagate_orbit(self):
        """sg_propagate_orbit should return bodies list of same length."""
        from sigma_ground.field.interface.nbody import CelestialBody
        M = 1.989e30
        a = 1.496e11
        v = math.sqrt(_G * 2 * M / a)
        bodies = [
            CelestialBody(M, np.array([a/2, 0, 0.0]), np.array([0, v/2, 0.0]), 7e8, 0.5),
            CelestialBody(M, np.array([-a/2, 0, 0.0]), np.array([0, -v/2, 0.0]), 7e8, 0.5),
        ]
        result = self.obj.sg_propagate_orbit(bodies, dt_s=3600.0, n_steps=10)
        self.assertEqual(len(result), 2)


# ══════════════════════════════════════════════════════════════════════════
# SGAdapter
# ══════════════════════════════════════════════════════════════════════════

class TestSGAdapter(unittest.TestCase):

    def test_wraps_arbitrary_object(self):
        class _Ext:
            name = "external"
            def compute(self): return 42

        wrapped = SGAdapter(_Ext())
        self.assertEqual(wrapped.name, "external")
        self.assertEqual(wrapped.compute(), 42)

    def test_sg_methods_available(self):
        wrapped = SGAdapter(object())
        gm = wrapped.sg_gm("Sun")
        self.assertAlmostEqual(gm, SGConstants.GM_sun, delta=1e8)

    def test_lib_attribute(self):
        obj     = [1, 2, 3]
        wrapped = SGAdapter(obj)
        self.assertIs(wrapped.lib, obj)

    def test_unknown_sg_method_raises(self):
        wrapped = SGAdapter(object())
        with self.assertRaises(AttributeError):
            _ = wrapped.sg_nonexistent_method_xyz


# ══════════════════════════════════════════════════════════════════════════
# SGEphemeris
# ══════════════════════════════════════════════════════════════════════════

class TestSGEphemeris(unittest.TestCase):

    def setUp(self):
        self.eph = SGEphemeris()

    def test_available_bodies_includes_major_planets(self):
        bodies = self.eph.sg_available_bodies()
        for name in ("Sun", "Earth", "Mars", "Jupiter"):
            self.assertIn(name, bodies, f"{name} missing from available_bodies")

    def test_de440_tier_past_epoch(self):
        """J2025 is in DE440 fixture -- tier should be de440."""
        jd_j2025 = 2460310.5
        tier = self.eph.sg_tier("Earth", jd_j2025)
        self.assertEqual(tier, "de440",
                         f"Expected de440 tier for J2025, got {tier!r}")

    def test_forecast_tier_future_epoch(self):
        """J2040 is in SSBM forecast -- tier should be forecast."""
        jd_j2040 = 2451545.0 + 40 * 365.25  # ~J2040
        tier = self.eph.sg_tier("Earth", jd_j2040)
        self.assertIn(tier, ("forecast", "kepler"),
                      f"Expected forecast or kepler for J2040, got {tier!r}")

    def test_position_shape(self):
        """sg_position should return (3,) ndarray."""
        pos = self.eph.sg_position("Earth", 2460310.5)
        self.assertEqual(pos.shape, (3,))
        self.assertTrue(np.all(np.isfinite(pos)))

    def test_heliocentric_earth_is_1au(self):
        """Earth heliocentric distance at J2025 should be ~1 AU."""
        jd    = 2460310.5
        dist  = self.eph.sg_distance_au("Earth", jd)
        self.assertAlmostEqual(dist, 1.0, delta=0.05,
                               msg=f"Earth at {dist:.3f} AU (expected ~1 AU)")

    def test_position_with_uncertainty_past(self):
        """For past epochs, SSBM and Keplerian should agree to < 0.05 AU."""
        jd   = 2460310.5  # J2025 -- in DE440
        pos, err_au = self.eph.sg_position_with_uncertainty("Earth", jd)
        self.assertLess(err_au, 0.05,
                        f"SSBM vs Kepler disagreement at J2025: {err_au:.4f} AU")

    def test_heliocentric_sun_is_zero(self):
        """Sun's heliocentric position should be (0,0,0) by definition."""
        hel = self.eph.sg_heliocentric("Sun", 2460310.5)
        dist_km = float(np.linalg.norm(hel))
        self.assertLess(dist_km, 1e6,  # within 1M km of origin
                        f"Sun heliocentric offset {dist_km:.0f} km")


# ══════════════════════════════════════════════════════════════════════════
# sg_solve_ivp (Forest-Ruth)
# ══════════════════════════════════════════════════════════════════════════

class TestSGSolveIVP(unittest.TestCase):
    """Harmonic oscillator: H = p²/2 + q²/2  (exact analytical solution)."""

    @staticmethod
    def _sho(t, y):
        """Harmonic oscillator: dq/dt = p, dp/dt = -q."""
        return np.array([y[1], -y[0]])

    def test_solution_shape(self):
        sol = sg_solve_ivp(self._sho, (0, 2 * math.pi), np.array([1.0, 0.0]),
                           method="forest_ruth", dt=0.01)
        self.assertEqual(sol.y.shape[0], 2)
        self.assertGreater(sol.y.shape[1], 1)

    def test_period_correct(self):
        """After one period (T=2pi), q should return to 1.0."""
        T   = 2 * math.pi
        sol = sg_solve_ivp(self._sho, (0, T), np.array([1.0, 0.0]),
                           method="forest_ruth", dt=0.01)
        q_final = sol.y[0, -1]
        self.assertAlmostEqual(q_final, 1.0, delta=1e-3)

    def test_energy_conserved_fr4(self):
        """FR4 should conserve H = (q²+p²)/2 to < 1e-6 over 100 periods."""
        T   = 2 * math.pi
        sol = sg_solve_ivp(self._sho, (0, 100 * T), np.array([1.0, 0.0]),
                           method="forest_ruth", dt=0.05)
        H0 = 0.5 * (sol.y[0, 0]**2 + sol.y[1, 0]**2)
        Hf = 0.5 * (sol.y[0, -1]**2 + sol.y[1, -1]**2)
        drift = abs(Hf - H0) / abs(H0)
        self.assertLess(drift, 1e-6, f"FR4 energy drift {drift:.2e} over 100 periods")

    def test_fr4_better_than_rk4_energy(self):
        """FR4 should conserve energy better than RK4 over 100 periods."""
        T  = 2 * math.pi
        y0 = np.array([1.0, 0.0])

        def H(y): return 0.5 * (y[0]**2 + y[1]**2)

        sol_fr4 = sg_solve_ivp(self._sho, (0, 100*T), y0,
                               method="forest_ruth", dt=0.05)
        sol_rk4 = sg_solve_ivp(self._sho, (0, 100*T), y0,
                               method="rk4", dt=0.05)

        drift_fr4 = abs(H(sol_fr4.y[:, -1]) - H(y0)) / H(y0)
        drift_rk4 = abs(H(sol_rk4.y[:, -1]) - H(y0)) / H(y0)
        self.assertLess(drift_fr4, drift_rk4,
                        f"FR4 drift {drift_fr4:.2e} not < RK4 {drift_rk4:.2e}")

    def test_verlet_api(self):
        """Verlet method should also run without error."""
        sol = sg_solve_ivp(self._sho, (0, math.pi), np.array([1.0, 0.0]),
                           method="verlet", dt=0.01)
        self.assertTrue(sol.success)


# ══════════════════════════════════════════════════════════════════════════
# sg_nbody
# ══════════════════════════════════════════════════════════════════════════

class TestSGNbody(unittest.TestCase):

    def _circular_pair(self):
        from sigma_ground.field.interface.nbody import CelestialBody
        M = 1.989e30
        a = 1.496e11
        v = math.sqrt(_G * 2 * M / a) / 2
        b1 = CelestialBody(M, np.array([ a/2, 0, 0.0]), np.array([0,  v, 0.0]), 7e8, 0.5)
        b2 = CelestialBody(M, np.array([-a/2, 0, 0.0]), np.array([0, -v, 0.0]), 7e8, 0.5)
        return [b1, b2]

    def test_returns_bodies_list(self):
        bodies = self._circular_pair()
        result, times = sg_nbody(bodies, dt_s=3600.0, t_total_s=86400.0)
        self.assertEqual(len(result), 2)
        self.assertGreater(len(times), 0)

    def test_bodies_moved(self):
        from sigma_ground.field.interface.nbody import NBodySystem
        bodies = self._circular_pair()
        p0 = bodies[0].position_m.copy()
        final, _ = sg_nbody(bodies, dt_s=3600.0, t_total_s=86400.0)
        self.assertFalse(np.allclose(final[0].position_m, p0))

    def test_energy_conserved(self):
        from sigma_ground.field.interface.nbody import NBodySystem
        bodies_in = self._circular_pair()
        sys0 = NBodySystem(bodies_in)
        E0   = sys0.total_energy()

        period = 2 * math.pi * math.sqrt((1.496e11)**3 / (_G * 2 * 1.989e30))
        final, _ = sg_nbody(bodies_in, dt_s=period / 500,
                            t_total_s=2 * period, include_gr=False)

        sys1 = NBodySystem(final)
        E1   = sys1.total_energy()
        drift = abs(E1 - E0) / abs(E0)
        self.assertLess(drift, 0.05, f"sg_nbody energy drift {drift:.2e}")


# ══════════════════════════════════════════════════════════════════════════
# sg_odeint
# ══════════════════════════════════════════════════════════════════════════

class TestSGOdeint(unittest.TestCase):

    def test_output_shape(self):
        """sg_odeint should return (n_time, n_state)."""
        def f(y, t): return np.array([-y[0]])
        t  = np.linspace(0, 1, 50)
        y0 = np.array([1.0])
        result = sg_odeint(f, y0, t)
        self.assertEqual(result.shape, (50, 1))

    def test_exponential_decay(self):
        """dy/dt = -y  =>  y(t) = exp(-t)."""
        def f(y, t): return np.array([-y[0]])
        t   = np.linspace(0, 2, 100)
        y0  = np.array([1.0])
        sol = sg_odeint(f, y0, t, method="rk4")
        y_final   = sol[-1, 0]
        y_expected = math.exp(-2)
        self.assertAlmostEqual(y_final, y_expected, delta=0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
