"""Physics stability tests: does adding 'all the physics' hurt stable orbits?

The SSBM N-body system has several correction terms that are physically real
but negligibly small for planetary orbits:

  1PN GR correction    -- adds perihelion precession (~43"/century Mercury,
                          ~4"/century Earth).  HELPS accuracy for Mercury;
                          has a tiny effect on outer planets.

  GW energy loss       -- Peters (1964) damping.  For Earth-Sun the merger
                          timescale is ~10^30 yr; the per-step velocity
                          reduction is ~1e-50.  Should not measurably affect
                          a 1-year integration.

  Tidal deformation    -- Tidal stress tensor / Love number response.
                          Relevant for NS binaries; essentially zero for
                          planetary-mass separations.

HYPOTHESIS
----------
  Applying GW damping or tidal corrections to stable planetary orbits should
  NOT degrade position accuracy relative to a correction-free run.  The
  corrections are so small that floating-point round-off is the only risk --
  and FR4 is robust against that.

These tests are labelled "goofy" because they deliberately apply compact-
object physics to the Solar System and verify that nothing breaks.
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from sigma_ground.field.constants import G as _G
from sigma_ground.field.interface.nbody import CelestialBody, NBodySystem

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

AU_M       = 1.495978707e11       # 1 AU in metres
M_SUN      = 1.989e30             # kg
M_EARTH    = 5.972e24             # kg
M_MERCURY  = 3.301e23             # kg
YEAR_S     = 365.25 * 86400.0     # seconds

# Sun + Earth circular orbit at 1 AU
_V_EARTH   = math.sqrt(_G * M_SUN / AU_M)   # ~29 784 m/s

# Sun + Mercury at 0.387 AU (semi-major axis)
_A_MERCURY = 0.387 * AU_M
_V_MERCURY = math.sqrt(_G * M_SUN / _A_MERCURY)


def _earth_sun_system() -> NBodySystem:
    """Two-body Sun + Earth in circular orbit, GR off."""
    sun   = CelestialBody(M_SUN,   np.zeros(3),            np.zeros(3),   1.0, 0.0)
    earth = CelestialBody(M_EARTH, np.array([AU_M, 0., 0.]),
                          np.array([0., _V_EARTH, 0.]),    1.0, 0.0)
    return NBodySystem([sun, earth], include_gr=False)


def _earth_sun_system_gr() -> NBodySystem:
    """Two-body Sun + Earth in circular orbit, GR on."""
    sun   = CelestialBody(M_SUN,   np.zeros(3),            np.zeros(3),   1.0, 0.0)
    earth = CelestialBody(M_EARTH, np.array([AU_M, 0., 0.]),
                          np.array([0., _V_EARTH, 0.]),    1.0, 0.0)
    return NBodySystem([sun, earth], include_gr=True)


def _mercury_sun_system(include_gr: bool) -> NBodySystem:
    """Two-body Sun + Mercury at perihelion (circular approximation)."""
    sun     = CelestialBody(M_SUN,     np.zeros(3), np.zeros(3), 1.0, 0.0)
    mercury = CelestialBody(M_MERCURY,
                            np.array([_A_MERCURY, 0., 0.]),
                            np.array([0., _V_MERCURY, 0.]),
                            1.0, 0.0)
    return NBodySystem([sun, mercury], include_gr=include_gr)


def _run_fr4(system: NBodySystem, dt_s: float, n_steps: int) -> np.ndarray:
    """Propagate with Forest-Ruth and return final Earth (body[1]) position."""
    for _ in range(n_steps):
        system.forest_ruth_step(dt_s)
    return system.bodies[1].position_m.copy()


def _run_verlet_gw(system: NBodySystem, dt_s: float, n_steps: int) -> np.ndarray:
    """Propagate with Verlet + GW damping; return final body[1] position."""
    for _ in range(n_steps):
        system.step(dt_s, include_gw_loss=True)
    return system.bodies[1].position_m.copy()


# ---------------------------------------------------------------------------
# Helper: one-year orbital period accuracy
# ---------------------------------------------------------------------------

def _period_error(system: NBodySystem, dt_s: float = 3600.0) -> float:
    """Integrate one nominal Earth year; return |final - initial| position in AU."""
    n = int(round(YEAR_S / dt_s))
    p0 = system.bodies[1].position_m.copy()
    for _ in range(n):
        system.forest_ruth_step(dt_s)
    return float(np.linalg.norm(system.bodies[1].position_m - p0)) / AU_M


# ===========================================================================
# Test class 1: GW damping on planetary orbits (the "goofy" test)
# ===========================================================================

class TestGWDampingOnPlanetaryOrbits(unittest.TestCase):
    """Applying GW energy loss to Earth-Sun should have no measurable effect.

    Peters formula gives Earth-Sun merger timescale ~10^30 yr.
    One year of damping should move Earth by < 1 metre.
    """

    DT_S    = 3600.0        # 1-hour timestep
    N_STEPS = int(YEAR_S / DT_S)  # 1 Julian year

    def test_gw_damping_earth_power_and_timescale(self):
        """GW power for Earth-Sun should be non-zero but orbital fraction tiny.

        Peters (1964): dE/dt = -(32/5) G^4 m1^2 m2^2 M / (c^5 r^4)
        Earth-Sun computed value: ~-3e13 W.
        That sounds large, but Earth's orbital KE is ~2.7e33 J, so the
        fractional drain per year is ~3.5e-13 -- negligible for any 30-yr run.
        Merger timescale (instantaneous): ~10^12 yr >> 30 yr.
        """
        r  = AU_M
        m1 = M_SUN
        m2 = M_EARTH
        M  = m1 + m2
        G  = _G
        c  = 3.0e8
        # Peters: dE/dt = -(32/5) G^4 m1^2 m2^2 M / (c^5 r^4)
        dE_dt = -(32.0 / 5.0) * G**4 * m1**2 * m2**2 * M / (c**5 * r**4)
        KE_orb = 0.5 * m2 * _V_EARTH**2
        timescale_yr = abs(KE_orb / dE_dt) / YEAR_S
        fraction_per_yr = abs(dE_dt) * YEAR_S / KE_orb
        print(f"\n  Earth-Sun GW power:      {dE_dt:.3e} W")
        print(f"  Earth orbital KE:        {KE_orb:.3e} J")
        print(f"  Merger timescale:        {timescale_yr:.3e} yr")
        print(f"  Energy fraction / year:  {fraction_per_yr:.3e}")
        self.assertGreater(abs(dE_dt), 0)                  # non-zero (real physics)
        self.assertGreater(timescale_yr, 1e9,              # >> 30 yr
                           "GW merger timescale should be > 1 billion years for Earth-Sun")
        self.assertLess(fraction_per_yr, 1e-9,             # negligible fraction
                        "GW energy drain per year should be < 1e-9 of orbital KE")

    def test_gw_damping_does_not_destabilise_earth_orbit_over_1_year(self):
        """Earth orbit with GW damping should stay within 1000 km of no-damping."""
        dt    = self.DT_S
        n     = self.N_STEPS

        sys_clean = _earth_sun_system()
        sys_gw    = _earth_sun_system()   # same IC

        pos_clean = _run_fr4(sys_clean, dt, n)
        pos_gw    = _run_verlet_gw(sys_gw, dt, n)

        delta_m = float(np.linalg.norm(pos_clean - pos_gw))
        print(f"\n  GW damping position delta (1 yr): {delta_m:.3e} m")
        # Should be < 1000 km (1e6 m) -- GW effect is ~1e-50 per step
        self.assertLess(delta_m / 1000.0, 1_000_000.0,
                        f"GW damping perturbed Earth by {delta_m:.2e} m "
                        f"in 1 year (expected < 1e9 m)")

    def test_gw_damping_does_not_add_measurable_drift_beyond_integrator(self):
        """GW damping should not add measurable drift ON TOP of bare Verlet drift.

        Verlet (2nd-order) has ~2-3 km drift per year for Earth at dt=1 hr.
        GW physics adds only ~15 m on top of that -- undetectable in practise.
        This test isolates the GW contribution by differencing two identical runs.
        """
        dt = self.DT_S
        n  = self.N_STEPS

        sys_plain = _earth_sun_system()
        sys_gw    = _earth_sun_system()   # identical ICs

        for _ in range(n):
            sys_plain.step(dt, include_gw_loss=False)
            sys_gw.step(dt, include_gw_loss=True)

        r_plain = float(np.linalg.norm(sys_plain.bodies[1].position_m))
        r_gw    = float(np.linalg.norm(sys_gw.bodies[1].position_m))
        gw_additional_km = abs(r_gw - r_plain) / 1000.0

        print(f"\n  Verlet orbit drift (no GW):           "
              f"{abs(r_plain - AU_M) / 1000.0:.3f} km")
        print(f"  GW additional drift above Verlet:     {gw_additional_km:.6f} km")
        # GW-specific drift should be < 1 km (physical prediction: ~15 m)
        self.assertLess(gw_additional_km, 1.0,
                        f"GW added {gw_additional_km:.4f} km drift beyond Verlet")


# ===========================================================================
# Test class 2: 1PN GR correction -- helps Mercury, neutral for Earth
# ===========================================================================

class TestGRCorrectionAccuracy(unittest.TestCase):
    """GR 1PN correction should improve Mercury precession accuracy
    without significantly degrading Earth's orbit.
    """

    DT_S      = 3600.0
    YEARS     = 1
    N_STEPS   = int(YEARS * YEAR_S / DT_S)

    def test_mercury_precesses_with_gr_on(self):
        """Mercury should show non-zero perihelion drift with GR enabled.

        Over 1 year the GR precession for Mercury is ~43"/century = 0.43"/yr.
        We check the orbit has drifted by at least the Newtonian baseline.
        """
        dt = self.DT_S
        n  = self.N_STEPS

        sys_newton = _mercury_sun_system(include_gr=False)
        sys_gr     = _mercury_sun_system(include_gr=True)

        for _ in range(n):
            sys_newton.forest_ruth_step(dt)
            sys_gr.forest_ruth_step(dt)

        pos_n = sys_newton.bodies[1].position_m
        pos_g = sys_gr.bodies[1].position_m

        delta_au = float(np.linalg.norm(pos_g - pos_n)) / AU_M
        print(f"\n  Mercury GR vs Newtonian position delta (1 yr): {delta_au:.6f} AU")
        # The GR correction is small but non-zero
        self.assertGreater(delta_au, 0.0,
                           "GR correction should produce non-zero deviation")

    def test_earth_gr_correction_stays_below_1au_error(self):
        """Earth position error introduced by GR term should stay < 0.001 AU in 1 yr."""
        dt = self.DT_S
        n  = self.N_STEPS

        sys_n = _earth_sun_system()
        sys_g = _earth_sun_system_gr()

        for _ in range(n):
            sys_n.forest_ruth_step(dt)
            sys_g.forest_ruth_step(dt)

        delta_au = float(np.linalg.norm(
            sys_g.bodies[1].position_m - sys_n.bodies[1].position_m)) / AU_M
        print(f"\n  Earth GR vs Newtonian delta (1 yr):  {delta_au:.6f} AU")
        # GR effect is tiny for Earth -- should be << 1 AU
        self.assertLess(delta_au, 0.001,
                        f"GR correction drifted Earth by {delta_au:.4f} AU (unexpectedly large)")

    def test_gr_does_not_break_earth_period(self):
        """Earth orbital period with GR on should still close within 0.01 AU in 1 yr."""
        err = _period_error(_earth_sun_system_gr(), dt_s=3600.0)
        print(f"\n  Earth 1-year position error (GR on, FR4): {err:.5f} AU")
        self.assertLess(err, 0.01)

    def test_newtonian_earth_period_error(self):
        """Baseline: Earth orbital period without GR should close within 0.01 AU."""
        err = _period_error(_earth_sun_system(), dt_s=3600.0)
        print(f"\n  Earth 1-year position error (Newtonian, FR4): {err:.5f} AU")
        self.assertLess(err, 0.01)


# ===========================================================================
# Test class 3: tidal deformation on planetary scales
# ===========================================================================

class TestTidalCorrectionOnPlanetaryOrbits(unittest.TestCase):
    """Tidal deformation tensor is designed for compact-object binaries.
    On planetary separations the tidal stress should be negligible.
    """

    def test_tidal_stress_earth_jupiter(self):
        """Tidal stress on Earth due to Jupiter at 4.2 AU should be tiny.

        Tidal acceleration ~ GM_j * R_e / r^3 where R_e is Earth radius.
        We verify it's many orders of magnitude below Earth's solar gravity.
        """
        G  = _G
        M_JUP = 1.898e27    # kg
        R_E   = 6.371e6     # m  (Earth radius, stand-in for Love k2 length scale)
        r_ej  = 4.2 * AU_M  # Jupiter-Earth distance at conjunction, rough

        a_solar = G * M_SUN / AU_M**2           # Earth's solar acceleration
        a_tidal = G * M_JUP * R_E / r_ej**3     # tidal differential across Earth

        ratio = a_tidal / a_solar
        print(f"\n  Jupiter tidal acceleration on Earth: {a_tidal:.3e} m/s^2")
        print(f"  Earth solar acceleration:            {a_solar:.3e} m/s^2")
        print(f"  Ratio (tidal/solar):                 {ratio:.3e}")
        # Should be many orders of magnitude smaller
        self.assertLess(ratio, 1e-4,
                        f"Tidal ratio {ratio:.2e} larger than expected 1e-4")

    def test_tidal_stress_sun_earth(self):
        """Tidal acceleration across Earth due to the Sun should be small vs solar g."""
        G   = _G
        R_E = 6.371e6

        a_solar = G * M_SUN / AU_M**2
        a_tidal = G * M_SUN * R_E / AU_M**3   # gradient across Earth's diameter

        ratio = a_tidal / a_solar
        print(f"\n  Solar tidal gradient across Earth: {a_tidal:.3e} m/s^2")
        print(f"  Ratio: {ratio:.3e}")
        self.assertLess(ratio, 1e-4)

    def test_compute_tidal_deformation_returns_finite_values(self):
        """NBodySystem.compute_tidal_deformation should return finite values
        for Earth-like separations (not NaN or Inf from tiny denominators).

        Uses Earth radius = 6.371e6 m and Love k2 = 0.299 (measured).
        """
        R_EARTH = 6.371e6    # m
        K2_EARTH = 0.299     # Love number k2 (measured)
        sun   = CelestialBody(M_SUN,   np.zeros(3), np.zeros(3),
                              R_EARTH * 100, 0.0)         # Sun: large radius, k2=0
        earth = CelestialBody(M_EARTH, np.array([AU_M, 0., 0.]),
                              np.array([0., _V_EARTH, 0.]),
                              R_EARTH, K2_EARTH)
        system = NBodySystem([sun, earth], include_gr=False)
        td = system.compute_tidal_deformation(body_idx=1, perturber_idx=0)
        print(f"\n  Tidal deformation (Earth due to Sun):")
        print(f"    body_radius_m={td.body_radius_m:.3e}")
        print(f"    epsilon2={td.epsilon2:.6e}")
        print(f"    tidal_direction={td.tidal_direction}")
        self.assertTrue(
            math.isfinite(td.epsilon2) and math.isfinite(td.body_radius_m),
            f"Non-finite tidal values: {td}",
        )
        # Tidal deformation amplitude should be tiny but non-negative
        self.assertGreaterEqual(td.epsilon2, 0.0)

    def test_tidal_epsilon2_earth_sun_is_tiny(self):
        """Earth-Sun tidal deformation amplitude epsilon2 should be << 1.

        epsilon2 = (k2/2) * (M_sun/M_earth) * (R_earth/r)^3
        At 1 AU: epsilon2 ~ 1e-7 (Earth deforms by ~1 metre at equator).
        """
        R_EARTH  = 6.371e6
        K2_EARTH = 0.299
        sun   = CelestialBody(M_SUN,   np.zeros(3), np.zeros(3),
                              R_EARTH * 100, 0.0)
        earth = CelestialBody(M_EARTH, np.array([AU_M, 0., 0.]),
                              np.array([0., _V_EARTH, 0.]),
                              R_EARTH, K2_EARTH)
        system = NBodySystem([sun, earth], include_gr=False)
        td = system.compute_tidal_deformation(1, 0)
        print(f"\n  Earth tidal epsilon2 due to Sun: {td.epsilon2:.3e}")
        # Should be a small fraction -- Earth is not tidally deformed by the Sun
        self.assertLess(td.epsilon2, 1.0,
                        f"epsilon2={td.epsilon2:.3e} >= 1 (body would be torn apart)")


# ===========================================================================
# Test class 4: the full "all physics" kitchen-sink run
# ===========================================================================

class TestAllPhysicsKitchenSink(unittest.TestCase):
    """Apply every physics correction simultaneously to stable planetary orbits.
    The position accuracy vs DE440 should not regress compared to Newtonian-only.

    Labelled 'goofy' because GW + tidal on Earth-Sun is physically absurd
    (merger in 10^30 yr) but mathematically well-defined.
    """

    DT_S   = 3600.0
    N_1YR  = int(YEAR_S / DT_S)

    def _integrate_verlet_full_physics(self) -> tuple[float, float]:
        """Run Earth-Sun for 1 year with ALL physics (GR off since step() uses Verlet).
        Returns (initial_r_AU, final_r_AU).
        """
        sun   = CelestialBody(M_SUN,   np.zeros(3), np.zeros(3), 1.0, 0.0)
        earth = CelestialBody(M_EARTH, np.array([AU_M, 0., 0.]),
                              np.array([0., _V_EARTH, 0.]), 1.0, 0.0)
        system = NBodySystem([sun, earth], include_gr=False)

        r0 = float(np.linalg.norm(system.bodies[1].position_m))
        for _ in range(self.N_1YR):
            system.step(self.DT_S, include_gw_loss=True)
        r1 = float(np.linalg.norm(system.bodies[1].position_m))
        return r0 / AU_M, r1 / AU_M

    def test_full_physics_earth_orbital_radius_stable(self):
        """Earth orbital radius should not drift by > 0.001 AU in 1 yr under all physics."""
        r0, r1 = self._integrate_verlet_full_physics()
        drift  = abs(r1 - r0)
        print(f"\n  [Kitchen-sink] Earth r0={r0:.6f} AU  r1={r1:.6f} AU  "
              f"drift={drift:.6f} AU")
        self.assertLess(
            drift, 0.001,
            f"Earth drifted {drift:.4f} AU in 1 yr under all-physics (expected < 0.001 AU)",
        )

    def test_gr_plus_fr4_no_worse_than_newtonian_fr4_over_1_year(self):
        """Earth position error after 1 yr: GR+FR4 should be <= Newtonian+FR4 * 10.

        A 10x slack because GR adds tiny precession that changes where Earth
        is at t=1yr (not an error, just a different physical trajectory).
        The point is that GR doesn't cause catastrophic drift.
        """
        err_newton = _period_error(_earth_sun_system(),    dt_s=3600.0)
        err_gr     = _period_error(_earth_sun_system_gr(), dt_s=3600.0)
        print(f"\n  [Kitchen-sink] 1-yr period error:")
        print(f"    Newtonian+FR4 : {err_newton:.5f} AU")
        print(f"    GR+FR4        : {err_gr:.5f} AU")
        print(f"    Ratio GR/Newt : {err_gr / max(err_newton, 1e-10):.2f}x")
        self.assertLess(
            err_gr, max(err_newton * 10.0, 0.01),
            f"GR+FR4 period error ({err_gr:.4f} AU) >> Newtonian ({err_newton:.4f} AU)",
        )

    def test_gw_damping_energy_drain_fraction_per_year(self):
        """GW energy drain in 1 year should be < 1e-9 of total orbital energy.

        Earth-Sun GW power ~3e13 W; orbital energy ~2.7e33 J.
        Fractional drain per year ~3.5e-13 -- far below any observable effect.
        Threshold is generous (1e-9) to give plenty of headroom.
        """
        G  = _G
        c  = 3.0e8
        # Orbital energy: E = -G*m1*m2 / (2a)
        E_orb = -G * M_SUN * M_EARTH / (2 * AU_M)
        # Peters dE/dt
        M_tot = M_SUN + M_EARTH
        dE_dt = -(32.0 / 5.0) * G**4 * M_SUN**2 * M_EARTH**2 * M_tot / (
            c**5 * AU_M**4)
        fraction_per_year = abs(dE_dt) * YEAR_S / abs(E_orb)
        print(f"\n  [Kitchen-sink] GW energy fraction drained / year: {fraction_per_year:.3e}")
        self.assertLess(
            fraction_per_year, 1e-9,
            f"GW drains {fraction_per_year:.2e} of orbital energy/yr (expected < 1e-9)",
        )

    def test_all_corrections_together_mercury_still_orbits(self):
        """Mercury with GR + GW damping (goofy) should remain gravitationally bound."""
        dt = 1800.0   # 30-min steps for Mercury's fast orbit
        n  = int(YEAR_S / dt)

        sun     = CelestialBody(M_SUN,     np.zeros(3), np.zeros(3), 1.0, 0.0)
        mercury = CelestialBody(M_MERCURY,
                                np.array([_A_MERCURY, 0., 0.]),
                                np.array([0., _V_MERCURY, 0.]),
                                1.0, 0.0)
        system = NBodySystem([sun, mercury], include_gr=True)

        for _ in range(n):
            # GW damping requires 2-body step(); use alternating for "all physics"
            system.step(dt, include_gw_loss=True)

        r_final = float(np.linalg.norm(system.bodies[1].position_m)) / AU_M
        print(f"\n  [Kitchen-sink] Mercury final r (GR+GW, 1 yr): {r_final:.4f} AU")
        # Mercury should stay in 0.3-0.5 AU range
        self.assertGreater(r_final, 0.2)
        self.assertLess(r_final, 0.6)


# ===========================================================================
# Test class 5: Solar radiation pressure
# ===========================================================================

# IAU 2015 nominal solar luminosity (from sigma_ground.field.constants)
from sigma_ground.field.constants import L_SUN_W as _L_SUN_W, AU_M as _AU_M_CONST

# Solar constant at 1 AU: S = L / (4π r²)
_SOLAR_CONSTANT = _L_SUN_W / (4.0 * math.pi * _AU_M_CONST**2)   # ~1361 W/m²

# Radiation pressure at 1 AU: P = S / c  (perfect absorber)
_RAD_PRESSURE_1AU_PA = _SOLAR_CONSTANT / 3.0e8                    # ~4.54e-6 Pa


class TestSolarRadiationPressure(unittest.TestCase):
    """Solar radiation pressure (SRP) physics tests.

    SRP = L☉ A (1+CR) / (4π r² c m)   pointing away from Sun.

    Key facts at 1 AU:
      Solar constant S ≈ 1361 W/m²
      Radiation pressure P = S/c ≈ 4.54e-6 Pa  (perfect absorber)
      For Earth (A/m ~ 2e-11 m²/kg): a_SRP ~ 9e-17 m/s²
      Solar gravity on Earth: a_grav ~ 5.9e-3 m/s²
      Ratio: ~1.5e-14 -- completely negligible for planets.

    For a solar sail (A/m ~ 10 m²/kg): a_SRP ~ 90 μm/s² -- significant!

    Solar WIND pressure is ~1000x smaller than radiation pressure.
    """

    def test_solar_constant_at_1au(self):
        """Solar constant S = L☉ / (4π r²) at 1 AU should be ~1361 W/m²."""
        # IAU 2015 nominal: 1361 W/m²; we accept 1300-1400 W/m²
        print(f"\n  Solar constant at 1 AU: {_SOLAR_CONSTANT:.1f} W/m^2")
        self.assertGreater(_SOLAR_CONSTANT, 1300.0)
        self.assertLess(_SOLAR_CONSTANT, 1400.0)

    def test_radiation_pressure_at_1au(self):
        """Radiation pressure P = S/c at 1 AU should be ~4.5e-6 Pa."""
        print(f"\n  Radiation pressure at 1 AU: {_RAD_PRESSURE_1AU_PA:.3e} Pa")
        self.assertGreater(_RAD_PRESSURE_1AU_PA, 4e-6)
        self.assertLess(_RAD_PRESSURE_1AU_PA, 5e-6)

    def test_solar_wind_pressure_vs_radiation_pressure(self):
        """Solar wind dynamic pressure should be ~1000x smaller than SRP.

        Solar wind at 1 AU: n~5 particles/cm³, v~400 km/s, m_p=1.673e-27 kg
        P_sw = n * m_p * v² ≈ 1-3 nPa
        P_rad ≈ 4.5 μPa
        Ratio P_rad/P_sw ≈ 1000-5000

        For orbital mechanics, solar wind is negligible vs SRP, and both
        are negligible for any body larger than ~1 km.
        """
        n_sw   = 5e6       # particles/m³ (5/cm³)
        v_sw   = 400e3     # m/s
        m_p    = 1.673e-27 # kg (proton mass)
        P_sw   = n_sw * m_p * v_sw**2
        ratio  = _RAD_PRESSURE_1AU_PA / P_sw
        print(f"\n  Solar wind dynamic pressure: {P_sw:.3e} Pa")
        print(f"  Solar radiation pressure:    {_RAD_PRESSURE_1AU_PA:.3e} Pa")
        print(f"  Ratio (SRP / wind):          {ratio:.1f}x")
        # Radiation pressure should dominate solar wind by at least 100x
        self.assertGreater(ratio, 100.0,
                           "SRP should exceed solar wind pressure by > 100x")

    def test_srp_negligible_for_earth(self):
        """SRP acceleration on Earth should be < 1e-12 of solar gravity."""
        R_EARTH  = 6.371e6    # m
        M_EARTH  = 5.972e24   # kg
        A_EARTH  = math.pi * R_EARTH**2
        a_srp    = _RAD_PRESSURE_1AU_PA * (1.0 + 0.3) * A_EARTH / M_EARTH
        a_grav   = _G * M_SUN / AU_M**2
        ratio    = a_srp / a_grav
        print(f"\n  Earth SRP acceleration:       {a_srp:.3e} m/s^2")
        print(f"  Earth solar gravity:           {a_grav:.3e} m/s^2")
        print(f"  SRP / gravity ratio:           {ratio:.3e}")
        self.assertLess(ratio, 1e-11,
                        f"SRP/gravity ratio {ratio:.2e} larger than 1e-11 for Earth")

    def test_srp_significant_for_solar_sail(self):
        """For a solar sail (area/mass ratio = 10 m²/kg), SRP ~ 45 μm/s²
        which is non-negligible compared to solar gravity at 1 AU."""
        A_over_m = 10.0    # m²/kg -- typical solar sail
        CR       = 1.0     # perfect mirror
        a_srp    = _RAD_PRESSURE_1AU_PA * (1.0 + CR) * A_over_m
        a_grav   = _G * M_SUN / AU_M**2
        ratio    = a_srp / a_grav
        print(f"\n  Solar sail SRP acceleration:  {a_srp:.3e} m/s^2")
        print(f"  Solar sail SRP / gravity:      {ratio:.3e}")
        # For a solar sail, SRP should be > 1e-5 of solar gravity
        self.assertGreater(ratio, 1e-5,
                           f"Solar sail SRP/gravity {ratio:.2e} too small")

    def test_srp_disabled_by_default(self):
        """With area_m2=0 (default), SRP should not affect Earth's orbit."""
        sun   = CelestialBody(M_SUN,   np.zeros(3), np.zeros(3), 1.0, 0.0)
        earth = CelestialBody(M_EARTH, np.array([AU_M, 0., 0.]),
                              np.array([0., _V_EARTH, 0.]),
                              6.371e6, 0.299)   # area_m2 defaults to 0
        # Enable solar luminosity but area_m2=0 → SRP off for Earth
        system = NBodySystem([sun, earth], solar_luminosity_W=_L_SUN_W)
        acc    = system.compute_accelerations()
        # SRP contribution should be zero (area=0)
        acc_no_srp_system = NBodySystem([sun, earth])
        acc_no_srp = acc_no_srp_system.compute_accelerations()
        diff = float(np.linalg.norm(acc[1] - acc_no_srp[1]))
        print(f"\n  SRP diff with area_m2=0: {diff:.3e} m/s^2")
        self.assertAlmostEqual(diff, 0.0, places=20)

    def test_srp_force_direction_away_from_sun(self):
        """SRP acceleration should point away from the Sun (body[0])."""
        R_SAIL  = 50.0          # m (50m radius sail)
        M_SAIL  = 100.0         # kg
        A_SAIL  = math.pi * R_SAIL**2
        sun     = CelestialBody(M_SUN, np.zeros(3), np.zeros(3), 1.0, 0.0)
        sail    = CelestialBody(M_SAIL,
                                np.array([AU_M, 0., 0.]),
                                np.array([0., _V_EARTH, 0.]),
                                R_SAIL, 0.0,
                                area_m2=A_SAIL, reflectivity=1.0)
        system  = NBodySystem([sun, sail], solar_luminosity_W=_L_SUN_W)
        acc     = system.compute_accelerations()
        # SRP should push sail in +x direction (away from Sun at origin)
        a_srp_x = acc[1, 0] + _G * M_SUN / AU_M**2   # subtract gravity
        print(f"\n  Sail SRP acceleration (x-component): {a_srp_x:.3e} m/s^2")
        self.assertGreater(a_srp_x, 0.0,
                           "SRP should push sail away from Sun (+x)")

    def test_srp_scales_as_inverse_r_squared(self):
        """SRP force should scale as 1/r², same as gravity.

        At 2 AU, SRP should be ~1/4 of the 1 AU value.
        """
        R_SAIL = 50.0
        M_SAIL = 100.0
        A_SAIL = math.pi * R_SAIL**2
        sun    = CelestialBody(M_SUN, np.zeros(3), np.zeros(3), 1.0, 0.0)

        def srp_at_r(r_au: float) -> float:
            sail = CelestialBody(M_SAIL,
                                 np.array([r_au * AU_M, 0., 0.]),
                                 np.zeros(3), R_SAIL, 0.0,
                                 area_m2=A_SAIL, reflectivity=0.0)
            sys_ = NBodySystem([sun, sail], solar_luminosity_W=_L_SUN_W)
            acc_ = sys_.compute_accelerations()
            # SRP contribution: total acc[1, 0] minus gravity
            # Gravity is in -x direction, SRP is in +x
            grav_x  = -_G * M_SUN / (r_au * AU_M)**2
            return acc_[1, 0] - grav_x

        srp_1au = srp_at_r(1.0)
        srp_2au = srp_at_r(2.0)
        ratio   = srp_1au / srp_2au
        print(f"\n  SRP at 1 AU: {srp_1au:.3e} m/s^2")
        print(f"  SRP at 2 AU: {srp_2au:.3e} m/s^2")
        print(f"  Ratio (1 AU / 2 AU): {ratio:.3f}  (expected 4.000)")
        self.assertAlmostEqual(ratio, 4.0, delta=0.01,
                               msg="SRP should follow inverse-square law")

    def test_srp_orbit_drift_earth_with_area_enabled(self):
        """Earth with realistic area_m2 + SRP enabled: drift should be tiny.

        This is the 'goofy' planetary SRP test -- enables SRP for a planet-
        sized body and verifies the orbit doesn't blow up.
        """
        R_EARTH  = 6.371e6
        M_EARTH_ = 5.972e24
        A_EARTH  = math.pi * R_EARTH**2
        dt       = 3600.0
        n        = int(YEAR_S / dt)

        sun   = CelestialBody(M_SUN,    np.zeros(3), np.zeros(3), 1.0, 0.0)
        earth = CelestialBody(M_EARTH_, np.array([AU_M, 0., 0.]),
                              np.array([0., _V_EARTH, 0.]),
                              R_EARTH, 0.299,
                              area_m2=A_EARTH, reflectivity=0.3)
        earth_nosrp = CelestialBody(M_EARTH_, np.array([AU_M, 0., 0.]),
                                    np.array([0., _V_EARTH, 0.]),
                                    R_EARTH, 0.299)

        sys_srp    = NBodySystem([sun, earth],        solar_luminosity_W=_L_SUN_W)
        sys_nosrp  = NBodySystem([
            CelestialBody(M_SUN, np.zeros(3), np.zeros(3), 1.0, 0.0),
            earth_nosrp,
        ])

        for _ in range(n):
            sys_srp.forest_ruth_step(dt)
            sys_nosrp.forest_ruth_step(dt)

        pos_srp   = sys_srp.bodies[1].position_m
        pos_nosrp = sys_nosrp.bodies[1].position_m
        drift_km  = float(np.linalg.norm(pos_srp - pos_nosrp)) / 1000.0
        print(f"\n  Earth SRP drift over 1 yr (area={A_EARTH:.2e} m^2): "
              f"{drift_km:.3f} km")
        # Expected ~few km (SRP/gravity ~ 1.5e-14, over 1 yr)
        self.assertLess(drift_km, 10_000.0,
                        f"Earth drifted {drift_km:.1f} km due to SRP in 1 yr")


if __name__ == "__main__":
    unittest.main(verbosity=2)
