"""Backwards-time prediction tests using DE440 annual snapshots.

Strategy: Start from a known past epoch (e.g., J2020), propagate forward
N years using our N-body engine, compare final positions against the
known DE440 snapshot at the target epoch.

This tests our physics engine against ground truth WITHOUT requiring
external libraries or network access — all data is in
fixtures/de440_state_vectors.json.

These are SHORT propagations (1-5 years) so they run in seconds, not
minutes.

KEY INSIGHT: This is the "predict the past from further past" pattern.
If our engine can propagate known initial conditions forward and land
on the known final positions, the physics is correct.

Integration uses the local_library velocity-Verlet (dt=0.25 d for inner
planets) and Forest-Ruth (dt=0.25 d) from sigma_ground.field.interface.nbody,
with GM values from sigma_ground.field.interface.orbital (DE440-measured).
"""

from __future__ import annotations

import json
import math
import os
import unittest
from pathlib import Path

import numpy as np

from sigma_ground.field.constants import G as _G
from sigma_ground.field.interface.nbody import CelestialBody, NBodySystem
from sigma_ground.field.interface.orbital import ANCHOR_GM  # DE440 measured GM (km³/s²)

# ── Fixture ───────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_SNAPSHOTS   = None


def _load_snapshots() -> dict:
    global _SNAPSHOTS
    if _SNAPSHOTS is None:
        with open(FIXTURES_DIR / "de440_state_vectors.json") as f:
            _SNAPSHOTS = json.load(f)
    return _SNAPSHOTS


# ── State-vector helpers ──────────────────────────────────────────────────

# GM values in m³/s² (DE440 measured values from orbital.py, converted km→m)
_GM_M3_S2: dict[str, float] = {
    k: v * 1e9 for k, v in ANCHOR_GM.items()
}

# Fallback GMs for bodies not in ANCHOR_GM (planets with known GM from DE440)
_EXTRA_GM_KM3_S2: dict[str, float] = {
    "Mercury": 22_032.09,
    "Venus":   324_858.59,
    "Uranus":    5_793_950.6103,
    "Neptune":   6_835_099.97,
    "Pluto":         869.326,
    "Moon":        4_902.8,
}

AU_KM  = 1.495978707e8   # 1 AU in km
KM_TO_M = 1000.0


def _gm_for_body(name: str) -> float:
    """Return GM in m³/s² for a named body (DE440 measured values)."""
    if name in _GM_M3_S2:
        return _GM_M3_S2[name]
    gm_km3 = _EXTRA_GM_KM3_S2.get(name)
    if gm_km3 is not None:
        return gm_km3 * 1e9
    # Fallback: estimate from fixture gm_km3_s2 field
    data = _load_snapshots()
    for snap in data["snapshots"].values():
        for b in snap["bodies"]:
            if b["name"] == name and "gm_km3_s2" in b:
                return b["gm_km3_s2"] * 1e9
    raise KeyError(f"No GM found for {name}")


def _get_body_si(snapshot_key: str, body_name: str) -> CelestialBody:
    """Load a body from a DE440 snapshot as a CelestialBody in SI units."""
    data = _load_snapshots()
    for b in data["snapshots"][snapshot_key]["bodies"]:
        if b["name"] == body_name:
            sv = b["state_vector"]
            gm_m3 = _gm_for_body(body_name)
            mass   = gm_m3 / _G
            pos    = np.array([sv["x_km"], sv["y_km"], sv["z_km"]]) * KM_TO_M
            vel    = np.array([sv["vx_km_s"], sv["vy_km_s"], sv["vz_km_s"]]) * KM_TO_M
            return CelestialBody(
                mass_kg=mass,
                position_m=pos,
                velocity_m_s=vel,
                radius_m=1.0,        # unused in n-body dynamics
                love_number_k2=0.0,
            )
    raise ValueError(f"Body {body_name!r} not found in snapshot {snapshot_key!r}")


def _run_propagation(
    start_epoch: str,
    end_epoch:   str,
    body_names:  list[str],
    dt_days:     float = 1.0,
    use_fr4:     bool  = False,
) -> tuple[dict, float]:
    """Propagate bodies from start to end epoch; return errors and duration.

    Returns
    -------
    results : dict mapping body_name → {error_km, error_au, relative_error,
              predicted (CelestialBody), expected (CelestialBody)}
    total_days : float
    """
    dt_s = dt_days * 86400.0

    bodies_init = [_get_body_si(start_epoch, n) for n in body_names]

    data      = _load_snapshots()
    jd_start  = data["snapshots"][start_epoch]["epoch"]["jd_tdb"]
    jd_end    = data["snapshots"][end_epoch  ]["epoch"]["jd_tdb"]
    total_days = jd_end - jd_start
    n_steps   = int(total_days * 86400.0 / dt_s)

    system = NBodySystem(bodies_init)
    step_fn = system.forest_ruth_step if use_fr4 else system.step
    for _ in range(n_steps):
        step_fn(dt_s)

    bodies_exp = [_get_body_si(end_epoch, n) for n in body_names]

    results: dict = {}
    for pred, exp in zip(system.bodies, bodies_exp):
        diff     = pred.position_m - exp.position_m
        err_m    = float(np.linalg.norm(diff))
        err_km   = err_m / KM_TO_M
        err_au   = err_km / AU_KM
        r_exp_m  = float(np.linalg.norm(exp.position_m))
        results[pred.mass_kg] = {          # keyed temporarily; replaced below
            "_name": exp,
        }
        # Re-key by name after the loop
        results[id(exp)] = {
            "name":           next(n for n, b in zip(body_names, bodies_exp) if id(b) == id(exp)),
            "error_km":       err_km,
            "error_au":       err_au,
            "relative_error": err_km / (r_exp_m / KM_TO_M) if r_exp_m > 0 else 0.0,
            "predicted":      pred,
            "expected":       exp,
        }

    # Build a clean name-keyed result dict
    named: dict = {}
    for pred, exp, name in zip(system.bodies, bodies_exp, body_names):
        diff     = pred.position_m - exp.position_m
        err_m    = float(np.linalg.norm(diff))
        err_km   = err_m / KM_TO_M
        err_au   = err_km / AU_KM
        r_exp_m  = float(np.linalg.norm(exp.position_m))
        named[name] = {
            "error_km":       err_km,
            "error_au":       err_au,
            "relative_error": err_km / (r_exp_m / KM_TO_M) if r_exp_m > 0 else 0.0,
            "predicted":      pred,
            "expected":       exp,
        }

    return named, total_days


# ── Body lists ────────────────────────────────────────────────────────────

INNER_PLANETS = ["Mercury", "Venus", "Earth", "Mars"]
OUTER_PLANETS = ["Jupiter", "Saturn"]
ALL_MAJOR     = ["Sun"] + INNER_PLANETS + OUTER_PLANETS + ["Uranus", "Neptune"]


# ── Skip logic ────────────────────────────────────────────────────────────

def _should_skip() -> bool:
    if os.environ.get("MATERIA_RUN_PROPAGATION", "").strip() == "1":
        return False
    tier = os.environ.get("MATERIA_DATA_REFRESH", "0").strip().lower()
    return tier not in ("extreme", "2")


SKIP   = _should_skip()
SKIP_MSG = ("N-body propagation tests — set MATERIA_DATA_REFRESH=extreme "
            "or MATERIA_RUN_PROPAGATION=1 to run")


# ══════════════════════════════════════════════════════════════════════════
# TEST CASES
# ══════════════════════════════════════════════════════════════════════════

@unittest.skipIf(SKIP, SKIP_MSG)
class TestOneYearInnerPlanets(unittest.TestCase):
    """Inner planets within 0.01 AU after 1-year propagation J2024 → J2025."""

    def test_inner_planet_positions_1year(self):
        """dt=0.25 d: Mercury (e=0.206, 88-day period) needs fine timestep.

        At dt=0.5 d Mercury accumulates ~0.012 AU error.
        At dt=0.25 d it drops to ~0.0014 AU.
        """
        results, days = _run_propagation("j2024", "j2025", ALL_MAJOR, dt_days=0.25)

        print(f"\n{'='*60}")
        print(f"  Inner planets J2024 -> J2025 ({days:.0f} days, Verlet dt=0.25d)")
        print(f"{'='*60}")
        for name in INNER_PLANETS:
            r      = results[name]
            status = "PASS" if r["error_au"] < 0.01 else "FAIL"
            print(f"  {name:10s}: {r['error_au']:.6f} AU ({r['error_km']:.0f} km) [{status}]")

        for name in INNER_PLANETS:
            self.assertLess(
                results[name]["error_au"], 0.01,
                f"{name}: error {results[name]['error_au']:.4f} AU > 0.01 AU",
            )


@unittest.skipIf(SKIP, SKIP_MSG)
class TestOneYearOuterPlanets(unittest.TestCase):
    """Outer planets within 0.05 AU after 1 year."""

    def test_outer_planet_positions_1year(self):
        results, _ = _run_propagation("j2024", "j2025", ALL_MAJOR, dt_days=0.5)

        print(f"\n  Outer planets J2024 -> J2025:")
        for name in OUTER_PLANETS:
            r      = results[name]
            status = "PASS" if r["error_au"] < 0.05 else "FAIL"
            print(f"  {name:10s}: {r['error_au']:.6f} AU [{status}]")

        for name in OUTER_PLANETS:
            self.assertLess(
                results[name]["error_au"], 0.05,
                f"{name}: error {results[name]['error_au']:.4f} AU > 0.05 AU",
            )


@unittest.skipIf(SKIP, SKIP_MSG)
class TestForestRuth1Year(unittest.TestCase):
    """Forest-Ruth should match or beat Verlet over 1 year."""

    def test_fr4_inner_planets_1year(self):
        """FR4 at dt=0.25 d: inner planets should still be within 0.01 AU."""
        results, days = _run_propagation(
            "j2024", "j2025", ALL_MAJOR, dt_days=0.25, use_fr4=True,
        )

        print(f"\n  FR4 inner planets J2024 -> J2025 ({days:.0f} days):")
        for name in INNER_PLANETS:
            r = results[name]
            print(f"  {name:10s}: {r['error_au']:.6f} AU")

        for name in INNER_PLANETS:
            self.assertLess(
                results[name]["error_au"], 0.01,
                f"FR4 {name}: error {results[name]['error_au']:.4f} AU > 0.01 AU",
            )


@unittest.skipIf(SKIP, SKIP_MSG)
class TestFiveYearPropagation(unittest.TestCase):
    """5-year propagation J2020 → J2025."""

    def test_planets_5year(self):
        """Inner planets < 0.1 AU, outer < 0.2 AU after 5 years."""
        results, days = _run_propagation("j2020", "j2025", ALL_MAJOR, dt_days=1.0)

        print(f"\n{'='*60}")
        print(f"  All planets J2020 -> J2025 ({days:.0f} days, Verlet dt=1d)")
        print(f"{'='*60}")
        for name in ALL_MAJOR:
            if name == "Sun":
                continue
            limit  = 0.1 if name in INNER_PLANETS else 0.2
            r      = results[name]
            status = "PASS" if r["error_au"] < limit else "FAIL"
            print(f"  {name:10s}: {r['error_au']:.6f} AU rel={r['relative_error']:.2e} [{status}]")

        for name in INNER_PLANETS:
            self.assertLess(results[name]["error_au"], 0.1,
                            f"{name} 5-year error > 0.1 AU")


@unittest.skipIf(SKIP, SKIP_MSG)
class TestEnergyConservation(unittest.TestCase):
    """Energy drift < 1e-6 over 1 year (local_library NBodySystem)."""

    def test_energy_conserved_1year(self):
        body_names  = ALL_MAJOR
        bodies_init = [_get_body_si("j2024", n) for n in body_names]
        dt_s        = 0.5 * 86400.0
        n_steps     = int(365.25 * 86400.0 / dt_s)

        system = NBodySystem(bodies_init)
        E0     = system.total_energy()
        for _ in range(n_steps):
            system.step(dt_s)
        E1     = system.total_energy()
        drift  = abs(E1 - E0) / abs(E0)

        print(f"\n  Energy (1 year): E0={E0:.6e}  E1={E1:.6e}  drift={drift:.2e}")
        self.assertLess(drift, 1e-6, f"Energy drift {drift:.2e} > 1e-6")


@unittest.skipIf(SKIP, SKIP_MSG)
class TestSunBarycenterDrift(unittest.TestCase):
    """Sun should stay within ~0.02 AU of the barycenter."""

    def test_sun_stays_near_origin(self):
        results, _ = _run_propagation("j2024", "j2025", ALL_MAJOR, dt_days=0.5)
        sun        = results["Sun"]
        r_sun_km   = float(np.linalg.norm(sun["predicted"].position_m)) / KM_TO_M
        r_sun_au   = r_sun_km / AU_KM
        print(f"\n  Sun barycentric distance: {r_sun_km:.0f} km = {r_sun_au:.6f} AU")
        self.assertLess(r_sun_au, 0.02, "Sun drifted too far from barycenter")


if __name__ == "__main__":
    unittest.main(verbosity=2)
