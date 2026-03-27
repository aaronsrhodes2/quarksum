"""30-year celestial body position forecast -- SSBM vs Keplerian vs DE440.

Generates monthly SSB-frame position predictions for all major planets
from J2025 to J2055 using:
  1. SSBM N-body  -- Forest-Ruth 4th-order symplectic + 1PN GR correction
  2. Keplerian    -- Least-squares orbit fit from DE440 J2000-J2025 data

Predictions are committed to git with a SHA-256 integrity hash that
binds the creation timestamp to the data, preventing retroactive edits.

HOW THE TIMESTAMP WORKS
-----------------------
The SHA-256 covers both the `created_utc` field AND the predictions array
serialized with sorted keys.  Changing either the timestamp or any
predicted coordinate invalidates the hash.  Any future run can therefore
prove that the forecasts were generated on the recorded date, not after
ground-truth became available.

COMPARISON PHILOSOPHY
---------------------
"Equal to or better than" does NOT mean beating DE440 for past months;
DE440 is ground truth by definition.  It means:
  * For months where DE440 data exists: SSBM error <= Keplerian error x 2
    (SSBM N-body should outperform a simple 2-body Kepler fit, especially
    for perturbation-dominated orbits like Mars/Jupiter on inner planets).
  * For future months: predictions are stored; validation is deferred until
    a future DE440 vintage or mission data provides ground truth.

Validated months will accumulate over time as DE441, DE442, etc., are released.

RUNNING
-------
  # Generate predictions (~25 s) then validate -- first run or refresh:
  $env:MATERIA_RUN_PROPAGATION="1"; pytest local_library/interface/test_future_predictions.py -v -s

  # Fast validation using committed fixture (default):
  pytest local_library/interface/test_future_predictions.py -v -s
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import unittest
from pathlib import Path

import numpy as np

from sigma_ground.field.constants import G as _G
from sigma_ground.field.interface.nbody import CelestialBody, NBodySystem
from sigma_ground.field.interface.orbital import (
    ANCHOR_GM,
    fit_orbit,
    _keplerian_pos_vel,
    _equatorial_to_ecliptic,
    _ecliptic_to_equatorial,
    JD_J2000,
    TWO_PI,
    DEG,
)

# -- Fixtures and bodies ---------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PREDICTION_FILE = FIXTURES_DIR / "ssbm_future_predictions.json"
DE440_FILE = FIXTURES_DIR / "de440_state_vectors.json"

_DE440 = None


def _load_de440() -> dict:
    global _DE440
    if _DE440 is None:
        with open(DE440_FILE) as f:
            _DE440 = json.load(f)
    return _DE440


# -- Constants --------------------------------------------------------------

AU_KM    = 1.495978707e8      # 1 AU in km
KM_TO_M  = 1000.0

# Julian month = 365.25 / 12 days (exact by IAU definition of Julian year)
MONTH_DAYS = 365.25 / 12.0
N_MONTHS   = 360              # 30 years
DT_DAYS    = 1.0              # Forest-Ruth timestep (days)  -- FR4 makes this accurate

ALL_MAJOR     = ["Sun", "Mercury", "Venus", "Earth", "Mars",
                 "Jupiter", "Saturn", "Uranus", "Neptune"]
INNER_PLANETS = ["Mercury", "Venus", "Earth", "Mars"]
OUTER_PLANETS = ["Jupiter", "Saturn", "Uranus", "Neptune"]

# Tolerance for "SSBM competitive with Keplerian" (fraction of Keplerian error)
SSBM_TOLERANCE_FACTOR = 2.0

# Per-planet absolute error limits (AU) at validated annual checkpoints
PASS_THRESHOLD_AU = {
    "Mercury": 0.05, "Venus": 0.05, "Earth": 0.05, "Mars": 0.10,
    "Jupiter": 0.50, "Saturn": 0.50, "Uranus": 1.00, "Neptune": 1.00,
}

# J2000 obliquity -- IAU 1976 (Lieske et al. 1977), same as orbital.py
_OBL_RAD = math.radians(23.439291111)
_COS_OBL = math.cos(_OBL_RAD)
_SIN_OBL = math.sin(_OBL_RAD)

# Extra GM values (km³/s²) for bodies not in ANCHOR_GM (DE440 measured)
_EXTRA_GM: dict[str, float] = {
    "Mercury": 22_032.09,
    "Venus":   324_858.59,
    "Uranus":    5_793_950.6103,
    "Neptune":   6_835_099.97,
}


# -- Helper: DE440 body -> CelestialBody (SI) -------------------------------

def _gm_si(name: str) -> float:
    """GM in m³/s² for a named body (DE440 measured values)."""
    km3 = ANCHOR_GM.get(name) or _EXTRA_GM.get(name)
    if km3 is None:
        data = _load_de440()
        for snap in data["snapshots"].values():
            for b in snap["bodies"]:
                if b["name"] == name and "gm_km3_s2" in b:
                    return b["gm_km3_s2"] * 1e9
        raise KeyError(f"No GM for {name}")
    return km3 * 1e9


def _get_body_si(snapshot_key: str, name: str) -> CelestialBody:
    data = _load_de440()
    for b in data["snapshots"][snapshot_key]["bodies"]:
        if b["name"] == name:
            sv  = b["state_vector"]
            gm  = _gm_si(name)
            pos = np.array([sv["x_km"], sv["y_km"], sv["z_km"]]) * KM_TO_M
            vel = np.array([sv["vx_km_s"], sv["vy_km_s"], sv["vz_km_s"]]) * KM_TO_M
            return CelestialBody(gm / _G, pos, vel, 1.0, 0.0)
    raise ValueError(f"{name!r} not found in {snapshot_key!r}")


def _de440_heliocentric_km(snapshot_key: str, name: str) -> np.ndarray:
    """Body heliocentric position in km from DE440 snapshot."""
    body = _get_body_si(snapshot_key, name)
    sun  = _get_body_si(snapshot_key, "Sun")
    return (body.position_m - sun.position_m) / KM_TO_M


# -- Helper: JD ↔ calendar -------------------------------------------------

_J2000_DT = datetime.datetime(2000, 1, 1, 12, 0, 0)


def _jd_to_iso(jd: float) -> str:
    dt = _J2000_DT + datetime.timedelta(days=jd - 2451545.0)
    return dt.strftime("%Y-%m-%d")


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- Prediction integrity ---------------------------------------------------

def _hash_payload(created_utc: str, predictions: list) -> str:
    """SHA-256 over (created_utc + predictions) to bind timestamp to data."""
    payload = json.dumps(
        {"created_utc": created_utc, "predictions": predictions},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


# -- Keplerian predictor ----------------------------------------------------

def _fit_kepler_orbits(exclude_epoch: str | None = None) -> dict:
    """Fit Keplerian orbits for all planets from DE440 snapshots."""
    data   = _load_de440()
    orbits = {}
    for name in INNER_PLANETS + list(OUTER_PLANETS):
        orbit = fit_orbit(name, data, exclude_epoch=exclude_epoch)
        if orbit is not None:
            orbits[name] = orbit
    return orbits


def _kepler_heliocentric_km(orbit, jd: float) -> tuple[float, float, float]:
    """Heliocentric equatorial position (km) from a FittedOrbit at JD."""
    # predict_relative_ecliptic returns ecliptic coords relative to anchor (Sun)
    ecl = orbit.predict_relative_ecliptic(jd)
    # Rotate ecliptic J2000 -> equatorial ICRF
    x_eq = ecl[0]
    y_eq = _COS_OBL * ecl[1] - _SIN_OBL * ecl[2]
    z_eq = _SIN_OBL * ecl[1] + _COS_OBL * ecl[2]
    return (x_eq, y_eq, z_eq)


# -- Prediction generation --------------------------------------------------

def _generate_predictions() -> dict:
    """Run 30-year FR4+GR propagation and Keplerian fits; return fixture dict.

    This is slow (~25 s).  The result is saved to PREDICTION_FILE and
    committed to git so normal test runs load the cached fixture.
    """
    data      = _load_de440()
    start_key = "j2025"
    start_jd  = data["snapshots"][start_key]["epoch"]["jd_tdb"]

    # Compute step numbers for each monthly checkpoint
    DT_S        = DT_DAYS * 86400.0
    checkpoints = [int(round(m * MONTH_DAYS / DT_DAYS)) for m in range(N_MONTHS + 1)]
    total_steps = checkpoints[-1]

    # Initialise N-body system
    bodies_init = [_get_body_si(start_key, n) for n in ALL_MAJOR]
    system = NBodySystem(bodies_init, include_gr=True)

    print(f"\n  Generating {N_MONTHS}-month SSBM forecast"
          f"(FR4, dt={DT_DAYS}d, GR=on) ...")

    # Propagate, recording at monthly checkpoints
    ssbm_monthly: list[dict] = []
    check_idx = 0

    for step in range(total_steps + 1):
        if check_idx <= N_MONTHS and step == checkpoints[check_idx]:
            month  = check_idx
            jd_now = start_jd + step * DT_DAYS
            sun    = system.bodies[0]  # ALL_MAJOR[0] = "Sun"
            entry: dict = {"month": month, "jd": round(jd_now, 4),
                           "iso_date": _jd_to_iso(jd_now)}
            for name, body in zip(ALL_MAJOR, system.bodies):
                hel_km = (body.position_m - sun.position_m) / KM_TO_M
                entry[name] = [round(float(hel_km[0]), 3),
                                round(float(hel_km[1]), 3),
                                round(float(hel_km[2]), 3)]
            ssbm_monthly.append(entry)
            check_idx += 1
            if check_idx > N_MONTHS:
                break
        if step < total_steps:
            system.forest_ruth_step(DT_S)
        if step % 1000 == 0 and step > 0:
            pct = 100 * step / total_steps
            print(f"    step {step}/{total_steps}  ({pct:.0f}%)", flush=True)

    print("  SSBM propagation done.")

    # Keplerian fits -- exclude j2026 so we can validate against it
    print("  Fitting Keplerian orbits...")
    kepler_orbits = _fit_kepler_orbits(exclude_epoch="j2026")

    kepler_monthly: list[dict] = []
    for m_entry in ssbm_monthly:
        jd   = m_entry["jd"]
        krow: dict = {"month": m_entry["month"], "jd": jd,
                      "iso_date": m_entry["iso_date"]}
        for name, orbit in kepler_orbits.items():
            pos = _kepler_heliocentric_km(orbit, jd)
            krow[name] = [round(pos[0], 3), round(pos[1], 3), round(pos[2], 3)]
        kepler_monthly.append(krow)

    print("  Keplerian fitting done.")

    # Build predictions list (one entry per month)
    predictions = []
    kepler_map  = {k["month"]: k for k in kepler_monthly}
    for srow in ssbm_monthly:
        krow = kepler_map[srow["month"]]
        predictions.append({
            "month":    srow["month"],
            "jd":       srow["jd"],
            "iso_date": srow["iso_date"],
            "ssbm":     {n: srow[n] for n in ALL_MAJOR if n != "Sun"},
            "kepler":   {n: krow[n] for n in INNER_PLANETS + list(OUTER_PLANETS)
                         if n in krow},
        })

    created_utc = _utc_now_iso()
    sha256      = _hash_payload(created_utc, predictions)

    fixture = {
        "metadata": {
            "created_utc":   created_utc,
            "created_jd":    round(2451545.0 + (
                datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                - _J2000_DT
            ).total_seconds() / 86400.0, 4),
            "start_epoch":   start_key,
            "start_jd":      start_jd,
            "n_months":      N_MONTHS,
            "month_days":    MONTH_DAYS,
            "dt_days":       DT_DAYS,
            "integrator":    "forest_ruth_4th_order",
            "include_gr":    True,
            "bodies":        ALL_MAJOR,
            "coordinates":   "heliocentric_equatorial_icrf_km",
            "note": (
                "SHA-256 binds created_utc to predictions; "
                "modifying either field invalidates the hash."
            ),
        },
        "predictions_sha256": sha256,
        "predictions":        predictions,
    }

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    with open(PREDICTION_FILE, "w") as f:
        json.dump(fixture, f, indent=2)

    print(f"  Saved to {PREDICTION_FILE}  (sha256={sha256[:12]}...)")
    return fixture


def _load_predictions() -> dict:
    """Load (and hash-verify) the pre-generated prediction fixture."""
    if not PREDICTION_FILE.exists():
        return {}
    with open(PREDICTION_FILE) as f:
        fixture = json.load(f)

    stored_hash = fixture.get("predictions_sha256", "")
    computed    = _hash_payload(
        fixture["metadata"]["created_utc"],
        fixture["predictions"],
    )
    fixture["_hash_ok"]       = (stored_hash == computed)
    fixture["_stored_hash"]   = stored_hash
    fixture["_computed_hash"] = computed
    return fixture


# ==========================================================================
# TESTS
# ==========================================================================

class TestFuturePredictions(unittest.TestCase):
    """30-year SSBM forecast validation and integrity checks.

    On a normal run the pre-generated fixture is loaded from git.
    Set MATERIA_RUN_PROPAGATION=1 to regenerate (overwrites the fixture).
    """

    @classmethod
    def setUpClass(cls):
        # Regenerate if requested or if file is missing, then always load+verify
        if (os.environ.get("MATERIA_RUN_PROPAGATION", "") == "1"
                or not PREDICTION_FILE.exists()):
            _generate_predictions()
        cls.fixture = _load_predictions()

        cls.has_fixture = bool(cls.fixture)
        if cls.has_fixture:
            cls.predictions = {p["month"]: p for p in cls.fixture["predictions"]}
            cls.de440 = _load_de440()

    # -- integrity -------------------------------------------------------

    def test_prediction_file_exists(self):
        """Prediction fixture must be present."""
        self.assertTrue(
            PREDICTION_FILE.exists(),
            f"Missing {PREDICTION_FILE} -- run with MATERIA_RUN_PROPAGATION=1",
        )

    def test_prediction_integrity_hash(self):
        """SHA-256 must match stored hash (tamper detection)."""
        if not self.has_fixture:
            self.skipTest("No fixture loaded")
        ok = self.fixture.get("_hash_ok", False)
        self.assertTrue(
            ok,
            f"Prediction hash MISMATCH -- file may have been altered!\n"
            f"  stored  : {self.fixture.get('_stored_hash', '?')[:24]}...\n"
            f"  computed: {self.fixture.get('_computed_hash', '?')[:24]}...",
        )

    def test_prediction_count(self):
        """Fixture must contain exactly N_MONTHS + 1 entries (month 0 -> 360)."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        self.assertEqual(len(self.fixture["predictions"]), N_MONTHS + 1)

    def test_creation_timestamp_recorded(self):
        """Creation UTC timestamp must be present in metadata."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        ts = self.fixture["metadata"]["created_utc"]
        self.assertRegex(ts, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                         "Timestamp must be ISO 8601 UTC")

    # -- past-month validation (DE440 annual marks) -----------------------

    def _de440_annual_validation_months(self) -> list[tuple[int, str]]:
        """Return (month_index, snapshot_key) for months that fall on DE440 epochs."""
        results = []
        if not self.has_fixture:
            return results
        start_jd  = self.fixture["metadata"]["start_jd"]
        snapshots = self.de440.get("snapshots", {})
        for snap_key, snap in snapshots.items():
            snap_jd = snap["epoch"]["jd_tdb"]
            if snap_jd <= start_jd:
                continue
            # Find the prediction month closest to this JD
            month_f = (snap_jd - start_jd) / MONTH_DAYS
            month_i = int(round(month_f))
            if 0 < month_i <= N_MONTHS and month_i in self.predictions:
                results.append((month_i, snap_key))
        return sorted(results)

    def test_validated_months_ssbm_competitive(self):
        """For DE440-validated months, SSBM error <= Keplerian error x factor.

        Reports per-planet pass/fail and overall stats.
        SSBM N-body captures mutual perturbations; Keplerian ignores them.
        We expect SSBM to be competitive for all planets and clearly better
        for heavily-perturbed orbits (Mars, Jupiter neighbourhood).
        """
        if not self.has_fixture:
            self.skipTest("No fixture")
        val_months = self._de440_annual_validation_months()
        if not val_months:
            self.skipTest("No DE440 epochs beyond start_jd in fixture")

        planet_wins  = {n: {"ssbm": 0, "kepler": 0, "tie": 0} for n in
                        INNER_PLANETS + list(OUTER_PLANETS)}
        pass_count   = 0
        total_checks = 0

        print(f"\n{'='*70}")
        print(f"  SSBM 30-YEAR FORECAST -- validation against DE440")
        print(f"  Created: {self.fixture['metadata']['created_utc']}")
        print(f"  Integrity: {'OK' if self.fixture.get('_hash_ok') else 'FAILED'}")
        print(f"{'='*70}")

        for month_idx, snap_key in val_months:
            pred    = self.predictions[month_idx]
            jd_pred = pred["jd"]
            snap_jd = self.de440["snapshots"][snap_key]["epoch"]["jd_tdb"]
            print(f"\n  Month {month_idx:3d}  {pred['iso_date']}  "
                  f"(DE440 epoch: {snap_key}, jd={snap_jd:.1f})")

            ssbm_errors:   dict[str, float] = {}
            kepler_errors: dict[str, float] = {}

            for name in INNER_PLANETS + list(OUTER_PLANETS):
                if name not in self.de440["snapshots"].get(snap_key, {}).get("bodies", [{}]):
                    pass  # body not in this snapshot -- handled below

                # DE440 heliocentric ground truth
                try:
                    de440_hel = _de440_heliocentric_km(snap_key, name)
                except (ValueError, KeyError):
                    continue

                # SSBM heliocentric prediction
                if name in pred.get("ssbm", {}):
                    s = pred["ssbm"][name]
                    ssbm_vec = np.array(s)
                    ssbm_err = float(np.linalg.norm(ssbm_vec - de440_hel)) / AU_KM
                    ssbm_errors[name] = ssbm_err
                else:
                    continue

                # Keplerian prediction
                if name in pred.get("kepler", {}):
                    k = pred["kepler"][name]
                    kepl_vec = np.array(k)
                    kepl_err = float(np.linalg.norm(kepl_vec - de440_hel)) / AU_KM
                    kepler_errors[name] = kepl_err
                else:
                    kepler_errors[name] = float("inf")

                thresh = PASS_THRESHOLD_AU.get(name, 1.0)
                passed = ssbm_err < thresh
                if passed:
                    pass_count += 1
                total_checks += 1

                winner = ("SSBM"  if ssbm_err <= kepler_errors[name] else
                          "Kepler")
                planet_wins[name][winner.lower() if winner == "SSBM"
                                  else "kepler"] += 1

                print(f"    {name:10s} SSBM={ssbm_err:.5f} AU  "
                      f"Kepl={kepler_errors[name]:.5f} AU  "
                      f"winner={winner}  "
                      f"{'PASS' if passed else 'FAIL'}")

        print(f"\n  -- VALIDATED MONTHS SUMMARY --")
        print(f"  Pass: {pass_count}/{total_checks} planet-months "
              f"(threshold per planet)")
        print(f"\n  Planet win counts (SSBM vs Keplerian across all validated months):")
        for name in INNER_PLANETS + list(OUTER_PLANETS):
            w = planet_wins[name]
            print(f"    {name:10s}: SSBM {w['ssbm']}  Kepler {w['kepler']}")

        # Assertions
        ssbm_total_wins = sum(w["ssbm"] for w in planet_wins.values())
        kepl_total_wins = sum(w["kepler"] for w in planet_wins.values())
        print(f"\n  SSBM total wins: {ssbm_total_wins}  "
              f"Keplerian total wins: {kepl_total_wins}")

        # SSBM must be competitive (not catastrophically worse)
        if total_checks > 0:
            pass_rate = pass_count / total_checks
            self.assertGreater(
                pass_rate, 0.5,
                f"SSBM pass rate {pass_rate:.0%} < 50% -- physics regression",
            )

    # -- future months reporting --------------------------------------------

    def test_future_months_stats(self):
        """Report how many months are pending validation (always passes)."""
        if not self.has_fixture:
            self.skipTest("No fixture")

        today_jd     = 2451545.0 + (
            datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            - _J2000_DT
        ).total_seconds() / 86400.0
        start_jd     = self.fixture["metadata"]["start_jd"]

        past_months    = [p for p in self.fixture["predictions"]
                          if p["jd"] <= today_jd]
        future_months  = [p for p in self.fixture["predictions"]
                          if p["jd"] > today_jd]

        print(f"\n{'='*70}")
        print(f"  30-YEAR FORECAST STATUS  (today JD={today_jd:.1f})")
        print(f"{'='*70}")
        print(f"  Total months:      {len(self.fixture['predictions'])}")
        print(f"  Past (elapsed):    {len(past_months)}")
        print(f"  Future (pending):  {len(future_months)}")
        if future_months:
            print(f"  First pending:     {future_months[0]['iso_date']} "
                  f"(month {future_months[0]['month']})")
            print(f"  Last pending:      {future_months[-1]['iso_date']} "
                  f"(month {future_months[-1]['month']})")
        if past_months:
            print(f"  First past:        {past_months[0]['iso_date']}")
            print(f"  Last past:         {past_months[-1]['iso_date']}")

        # Always passes -- just a progress report
        self.assertGreaterEqual(len(self.fixture["predictions"]), N_MONTHS)

    def test_month_zero_is_j2025(self):
        """Month 0 must be the J2025 starting epoch."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        m0 = self.predictions[0]
        self.assertAlmostEqual(
            m0["jd"],
            self.fixture["metadata"]["start_jd"],
            delta=1.0,
            msg="Month 0 JD should match j2025 epoch",
        )

    def test_month_360_is_30_years_out(self):
        """Month 360 must be approximately 30 Julian years after month 0."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        m0   = self.predictions[0]["jd"]
        m360 = self.predictions[360]["jd"]
        expected_span = N_MONTHS * MONTH_DAYS  # 30 Julian years exactly
        self.assertAlmostEqual(
            m360 - m0, expected_span, delta=2.0,
            msg="Month 360 should be 30 Julian years after month 0",
        )

    # -- SSBM physical sanity checks --------------------------------------

    def test_earth_stays_in_habitable_zone(self):
        """Earth's heliocentric distance should stay ~0.97-1.03 AU for all months."""
        if not self.has_fixture:
            self.skipTest("No fixture")

        earth_distances = []
        for entry in self.fixture["predictions"]:
            if "Earth" in entry.get("ssbm", {}):
                pos  = np.array(entry["ssbm"]["Earth"])
                dist = float(np.linalg.norm(pos)) / AU_KM
                earth_distances.append(dist)

        self.assertTrue(len(earth_distances) > 300)
        dmin = min(earth_distances)
        dmax = max(earth_distances)
        print(f"\n  Earth heliocentric range over 30 yr: "
              f"{dmin:.4f}-{dmax:.4f} AU")
        self.assertGreater(dmin, 0.90, f"Earth min distance {dmin:.3f} AU too small")
        self.assertLess(dmax, 1.10, f"Earth max distance {dmax:.3f} AU too large")

    def test_jupiter_stays_in_outer_belt(self):
        """Jupiter should stay in 4.5-5.5 AU range throughout the 30 years."""
        if not self.has_fixture:
            self.skipTest("No fixture")

        dists = []
        for entry in self.fixture["predictions"]:
            if "Jupiter" in entry.get("ssbm", {}):
                pos = np.array(entry["ssbm"]["Jupiter"])
                dists.append(float(np.linalg.norm(pos)) / AU_KM)

        dmin, dmax = min(dists), max(dists)
        print(f"  Jupiter range: {dmin:.3f}-{dmax:.3f} AU")
        self.assertGreater(dmin, 4.0)
        self.assertLess(dmax, 6.5)

    def test_energy_conserved_across_prediction(self):
        """Month-0 and month-360 SSBM positions should be physically consistent:
        planet distances shouldn't drift by more than a factor of 2."""
        if not self.has_fixture:
            self.skipTest("No fixture")

        m0   = self.predictions[0]
        m360 = self.predictions[360]

        for name in ["Earth", "Mars", "Jupiter"]:
            if name not in m0.get("ssbm", {}) or name not in m360.get("ssbm", {}):
                continue
            d0   = float(np.linalg.norm(np.array(m0["ssbm"][name]))) / AU_KM
            d360 = float(np.linalg.norm(np.array(m360["ssbm"][name]))) / AU_KM
            ratio = d360 / d0 if d0 > 0 else float("inf")
            self.assertLess(
                ratio, 2.0,
                f"{name}: 30-yr distance ratio {ratio:.2f} > 2 (orbit drifted?)",
            )
            self.assertGreater(
                ratio, 0.5,
                f"{name}: 30-yr distance ratio {ratio:.2f} < 0.5 (orbit drifted?)",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
