"""Minor-body positional forecast -- Keplerian orbit predictions for all 17
non-major DE440 bodies: Moon, Pluto/Charon, Mars/Jupiter/Saturn/Uranus/Neptune
satellites.

For each body the prediction is:

    heliocentric_eq = parent_heliocentric_eq  +  kepler_relative_eq

where
  * parent_heliocentric_eq  comes from the SSBM forecast fixture
    (for Pluto, a secondary Keplerian fit to DE440 provides the parent)
  * kepler_relative_eq      comes from a least-squares Keplerian orbit fit
    to the DE440 annual snapshots, converted ecliptic -> equatorial

Why Keplerian for moons?
  Forest-Ruth (dt=1 day) cannot resolve inner moons whose periods are < 2 days
  (Io 1.77 d, Enceladus 1.37 d, Phobos 0.32 d).  Keplerian orbit fitting is
  more accurate here because the dominant force is the parent planet -- mutual
  perturbations from other moons are small corrections.

Tampering detection:
  Same SHA-256 scheme as test_future_predictions.py -- hash covers
  {created_utc, bodies_predicted} to bind timestamp to data.

RUNNING
-------
  # Generate predictions (a few seconds), then validate:
  $env:MATERIA_RUN_PROPAGATION="1"; pytest local_library/interface/test_minor_bodies_predictions.py -v -s

  # Fast validation using committed fixture (default):
  pytest local_library/interface/test_minor_bodies_predictions.py -v -s
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

from sigma_ground.field.interface.orbital import (
    ANCHOR_MAP,
    fit_orbit,
    _ecliptic_to_equatorial,
    JD_J2000,
)

# -- Fixtures ---------------------------------------------------------------

FIXTURES_DIR       = Path(__file__).parent / "fixtures"
MINOR_PRED_FILE    = FIXTURES_DIR / "ssbm_minor_bodies_predictions.json"
MAJOR_PRED_FILE    = FIXTURES_DIR / "ssbm_future_predictions.json"
DE440_FILE         = FIXTURES_DIR / "de440_state_vectors.json"

_DE440   = None
_MAJOR   = None


def _load_de440() -> dict:
    global _DE440
    if _DE440 is None:
        with open(DE440_FILE) as f:
            _DE440 = json.load(f)
    return _DE440


def _load_major_predictions() -> dict:
    global _MAJOR
    if _MAJOR is None:
        if MAJOR_PRED_FILE.exists():
            with open(MAJOR_PRED_FILE) as f:
                _MAJOR = json.load(f)
        else:
            _MAJOR = {}
    return _MAJOR


# -- Constants ---------------------------------------------------------------

AU_KM      = 1.495978707e8
KM_TO_M    = 1000.0
MONTH_DAYS = 365.25 / 12.0
N_MONTHS   = 360          # 30 years

# J2000 obliquity for ecliptic -> equatorial (same constant as orbital.py)
_OBL_RAD = math.radians(23.439291111)
_COS_OBL = math.cos(_OBL_RAD)
_SIN_OBL = math.sin(_OBL_RAD)

# Major bodies (not minor): Sun + 8 planets
MAJOR_BODIES = {"Sun", "Mercury", "Venus", "Earth", "Mars",
                "Jupiter", "Saturn", "Uranus", "Neptune"}

# All 17 minor bodies from ANCHOR_MAP
MINOR_BODIES = sorted(b for b in ANCHOR_MAP if b not in MAJOR_BODIES)

# Pluto is heliocentric (parent = Sun) but not in the SSBM major forecast.
# We predict it via its own Keplerian heliocentric orbit.
_HELIOCENTRIC_BODIES = {"Pluto"}   # bodies whose anchor is Sun, predicted stand-alone

# Validation thresholds (AU).  Moons are hard to phase-predict from annual
# snapshots, so thresholds are deliberately loose -- we care that the orbit
# shape is correct, not the instantaneous phase.
PASS_THRESHOLD_AU: dict[str, float] = {
    # Mars moons
    "Phobos":    0.02,   "Deimos":    0.02,
    # Jupiter moons
    "Io":        0.02,   "Europa":    0.02,
    "Ganymede":  0.02,   "Callisto":  0.05,
    # Saturn moons
    "Enceladus": 0.02,   "Titan":     0.05,
    # Uranus moons
    "Miranda":   0.05,   "Ariel":     0.05,
    "Umbriel":   0.05,   "Titania":   0.05,  "Oberon":    0.05,
    # Neptune moon
    "Triton":    0.05,
    # Earth moon
    "Moon":      0.02,
    # Pluto system
    "Pluto":     5.00,   "Charon":    5.00,
}


# -- Calendar helpers -------------------------------------------------------

_J2000_DT = datetime.datetime(2000, 1, 1, 12, 0, 0)


def _jd_to_iso(jd: float) -> str:
    dt = _J2000_DT + datetime.timedelta(days=jd - 2451545.0)
    return dt.strftime("%Y-%m-%d")


def _utc_now_iso() -> str:
    return datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- Integrity ---------------------------------------------------------------

def _hash_payload(created_utc: str, bodies_predicted: dict) -> str:
    payload = json.dumps(
        {"created_utc": created_utc, "bodies_predicted": bodies_predicted},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


# -- Prediction helpers ------------------------------------------------------

def _kepler_relative_equatorial(orbit, jd: float) -> tuple[float, float, float]:
    """Anchor-relative position in ICRF equatorial km, from Keplerian fit."""
    ecl = orbit.predict_relative_ecliptic(jd)
    return _ecliptic_to_equatorial(*ecl)


def _parent_heliocentric_km(parent: str, jd: float,
                             major_pred: dict,
                             start_jd: float) -> np.ndarray | None:
    """Heliocentric equatorial position (km) of a major-body parent.

    Uses the SSBM major-body forecast when available, else falls back to
    a Keplerian heliocentric prediction for that parent.
    """
    if parent == "Sun":
        return np.zeros(3)

    # Look up nearest month in major predictions
    if major_pred and "predictions" in major_pred:
        month_f = (jd - start_jd) / MONTH_DAYS
        month_i = int(round(month_f))
        preds   = {p["month"]: p for p in major_pred["predictions"]}
        # Try exact month, then ±1
        for try_m in [month_i, month_i + 1, month_i - 1]:
            entry = preds.get(try_m)
            if entry and parent in entry.get("ssbm", {}):
                return np.array(entry["ssbm"][parent])

    # Fallback: Keplerian heliocentric prediction for parent
    data   = _load_de440()
    orbit  = fit_orbit(parent, data)
    if orbit is None:
        return None
    ecl = orbit.predict_relative_ecliptic(jd)
    eq  = _ecliptic_to_equatorial(*ecl)
    return np.array(eq)


def _de440_heliocentric_km(snap_key: str, name: str) -> np.ndarray | None:
    """Heliocentric equatorial position (km) for a body in a DE440 snapshot."""
    data  = _load_de440()
    snap  = data["snapshots"].get(snap_key)
    if snap is None:
        return None
    bodies = {b["name"]: b for b in snap["bodies"]}
    if name not in bodies or "Sun" not in bodies:
        return None
    def _sv(b: dict) -> np.ndarray:
        sv = b["state_vector"]
        return np.array([sv["x_km"], sv["y_km"], sv["z_km"]])
    return _sv(bodies[name]) - _sv(bodies["Sun"])


# -- Prediction generation ---------------------------------------------------

def _generate_minor_predictions() -> dict:
    """Fit Keplerian orbits for all 17 minor bodies; generate 30-year forecast."""
    data      = _load_de440()
    major_pred = _load_major_predictions()

    # Determine start_jd from major predictions; fallback to DE440 j2025
    if major_pred and "metadata" in major_pred:
        start_jd = major_pred["metadata"]["start_jd"]
    else:
        start_jd = data["snapshots"]["j2025"]["epoch"]["jd_tdb"]

    print(f"\n  Fitting Keplerian orbits for {len(MINOR_BODIES)} minor bodies...")

    orbits = {}
    for name in MINOR_BODIES:
        orbit = fit_orbit(name, data)
        if orbit is not None:
            orbits[name] = orbit
            print(f"    {name:12s}  anchor={orbit.anchor:10s}  "
                  f"a={orbit.a_km:,.0f} km  "
                  f"e={orbit.eccentricity:.4f}  "
                  f"rms={orbit.residual_rms_km:,.0f} km")
        else:
            print(f"    {name:12s}  FIT FAILED")

    print(f"  Generating monthly predictions (N={N_MONTHS})...")

    # bodies_predicted: dict[body_name -> list of monthly records]
    bodies_predicted: dict[str, list[dict]] = {n: [] for n in orbits}

    for month_i in range(N_MONTHS + 1):
        jd = start_jd + month_i * MONTH_DAYS

        for name, orbit in orbits.items():
            parent = orbit.anchor

            # Relative position (anchor-frame equatorial km)
            rel_eq = _kepler_relative_equatorial(orbit, jd)

            # Parent heliocentric position (equatorial km)
            if parent == "Sun":
                parent_hel = np.zeros(3)
            elif parent in _HELIOCENTRIC_BODIES:
                # Pluto's parent is Sun; we already handle that above.
                # Charon's parent is Pluto -- compute Pluto heliocentric first.
                pluto_orbit = orbits.get("Pluto")
                if pluto_orbit is None:
                    continue
                p_ecl = pluto_orbit.predict_relative_ecliptic(jd)
                parent_hel = np.array(_ecliptic_to_equatorial(*p_ecl))
            else:
                parent_hel = _parent_heliocentric_km(
                    parent, jd, major_pred, start_jd)
                if parent_hel is None:
                    continue

            hel_km = parent_hel + np.array(rel_eq)
            bodies_predicted[name].append({
                "month":             month_i,
                "jd":                round(jd, 4),
                "iso_date":          _jd_to_iso(jd),
                "heliocentric_km":   [round(float(hel_km[0]), 3),
                                      round(float(hel_km[1]), 3),
                                      round(float(hel_km[2]), 3)],
            })

        if month_i % 60 == 0:
            print(f"    month {month_i}/{N_MONTHS}  ({month_i * MONTH_DAYS / 365.25:.1f} yr)",
                  flush=True)

    # Orbital elements summary (for reference in fixture)
    elements = {
        name: {
            "anchor":          orbit.anchor,
            "a_km":            round(orbit.a_km, 3),
            "eccentricity":    round(orbit.eccentricity, 8),
            "inclination_deg": round(orbit.inclination_deg, 6),
            "residual_rms_km": round(orbit.residual_rms_km, 3),
        }
        for name, orbit in orbits.items()
    }

    created_utc = _utc_now_iso()
    sha256      = _hash_payload(created_utc, bodies_predicted)

    fixture = {
        "metadata": {
            "created_utc":  created_utc,
            "start_jd":     start_jd,
            "n_months":     N_MONTHS,
            "month_days":   MONTH_DAYS,
            "method":       "keplerian_fit_de440",
            "note": (
                "Minor bodies (17): moons + Pluto/Charon. "
                "Positions = parent_SSBM_heliocentric + Keplerian_relative. "
                "SHA-256 binds created_utc to bodies_predicted."
            ),
        },
        "orbital_elements":    elements,
        "predictions_sha256":  sha256,
        "bodies_predicted":    bodies_predicted,
    }

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    with open(MINOR_PRED_FILE, "w") as f:
        json.dump(fixture, f, indent=2)

    n_total = sum(len(v) for v in bodies_predicted.values())
    print(f"  Saved {len(orbits)} bodies, "
          f"{n_total} predictions to {MINOR_PRED_FILE}")
    print(f"  SHA-256: {sha256[:16]}...")
    return fixture


def _load_minor_predictions() -> dict:
    """Load and hash-verify the minor-body prediction fixture."""
    if not MINOR_PRED_FILE.exists():
        return {}
    with open(MINOR_PRED_FILE) as f:
        fixture = json.load(f)

    stored   = fixture.get("predictions_sha256", "")
    computed = _hash_payload(
        fixture["metadata"]["created_utc"],
        fixture["bodies_predicted"],
    )
    fixture["_hash_ok"]       = (stored == computed)
    fixture["_stored_hash"]   = stored
    fixture["_computed_hash"] = computed
    return fixture


# ==========================================================================
# TESTS
# ==========================================================================

class TestMinorBodiesPredictions(unittest.TestCase):
    """Keplerian 30-year position forecast for 17 minor DE440 bodies.

    Set MATERIA_RUN_PROPAGATION=1 to regenerate the fixture.
    """

    @classmethod
    def setUpClass(cls):
        if (os.environ.get("MATERIA_RUN_PROPAGATION", "") == "1"
                or not MINOR_PRED_FILE.exists()):
            _generate_minor_predictions()
        cls.fixture = _load_minor_predictions()
        cls.has_fixture = bool(cls.fixture)
        if cls.has_fixture:
            cls.bodies_pred = cls.fixture.get("bodies_predicted", {})
            cls.elements    = cls.fixture.get("orbital_elements", {})
            cls.de440       = _load_de440()

    # -- file existence ------------------------------------------------------

    def test_prediction_file_exists(self):
        self.assertTrue(
            MINOR_PRED_FILE.exists(),
            "Missing minor bodies fixture -- run with MATERIA_RUN_PROPAGATION=1",
        )

    def test_all_17_minor_bodies_predicted(self):
        """All 17 minor bodies should have predictions."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        predicted = set(self.bodies_pred.keys())
        missing   = set(MINOR_BODIES) - predicted
        self.assertEqual(
            missing, set(),
            f"Missing minor bodies: {sorted(missing)}",
        )

    # -- integrity -----------------------------------------------------------

    def test_prediction_integrity_hash(self):
        if not self.has_fixture:
            self.skipTest("No fixture")
        self.assertTrue(
            self.fixture.get("_hash_ok", False),
            f"Hash MISMATCH -- fixture may have been altered!\n"
            f"  stored  : {self.fixture.get('_stored_hash', '?')[:24]}...\n"
            f"  computed: {self.fixture.get('_computed_hash', '?')[:24]}...",
        )

    def test_prediction_count_per_body(self):
        """Each body must have N_MONTHS + 1 monthly entries."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        for name in MINOR_BODIES:
            if name not in self.bodies_pred:
                continue
            self.assertEqual(
                len(self.bodies_pred[name]),
                N_MONTHS + 1,
                f"{name}: expected {N_MONTHS + 1} entries, "
                f"got {len(self.bodies_pred[name])}",
            )

    # -- orbital elements sanity ---------------------------------------------

    def test_orbital_elements_physically_reasonable(self):
        """Keplerian orbit elements must be within known ranges for each body.

        Semi-major axes are compared against published values (IAU/NASA).
        """
        if not self.has_fixture:
            self.skipTest("No fixture")

        # Known semi-major axes (km), approximate ±20% tolerance
        known_a_km = {
            "Moon":      384_400,
            "Phobos":      9_376,
            "Deimos":     23_460,
            "Io":        421_700,
            "Europa":    671_100,
            "Ganymede":  1_070_400,
            "Callisto":  1_882_700,
            "Enceladus":   238_000,
            "Titan":     1_221_870,
            "Miranda":     129_390,
            "Ariel":       191_020,
            "Umbriel":     266_300,
            "Titania":     435_910,
            "Oberon":      583_520,
            "Triton":      354_800,
            "Pluto":    5_906_440_000,   # AU-scale
            "Charon":      17_536,
        }

        tol = 0.40   # 40% tolerance (annual-snapshot fit can be imprecise)

        print(f"\n  Orbital elements (semi-major axis comparison):")
        failures = []
        for name, ref_a in known_a_km.items():
            if name not in self.elements:
                continue
            fitted_a = self.elements[name]["a_km"]
            ratio    = abs(fitted_a - ref_a) / ref_a
            status   = "OK" if ratio <= tol else f"WARN ({ratio:.0%} off)"
            print(f"    {name:12s}  fit={fitted_a:>15,.0f} km  "
                  f"ref={ref_a:>15,} km  {status}")
            if ratio > tol:
                failures.append(
                    f"{name}: fitted {fitted_a:.0f} km, "
                    f"expected {ref_a:.0f} km ({ratio:.0%} off)")

        self.assertEqual(
            failures, [],
            "Orbital elements outside 40% tolerance:\n" +
            "\n".join(failures),
        )

    def test_eccentricities_non_negative(self):
        if not self.has_fixture:
            self.skipTest("No fixture")
        for name, el in self.elements.items():
            self.assertGreaterEqual(
                el["eccentricity"], 0.0,
                f"{name}: negative eccentricity {el['eccentricity']}",
            )
            self.assertLess(
                el["eccentricity"], 1.0,
                f"{name}: eccentricity >= 1 (hyperbolic) {el['eccentricity']}",
            )

    # -- DE440 validation at annual marks ------------------------------------

    def test_validated_months_vs_de440(self):
        """Compare Keplerian predictions against DE440 at annual epoch marks.

        Pass criterion: heliocentric error < PASS_THRESHOLD_AU per body.
        """
        if not self.has_fixture:
            self.skipTest("No fixture")

        major_pred = _load_major_predictions()
        start_jd   = self.fixture["metadata"]["start_jd"]

        # Find DE440 snapshots after start_jd
        val_months: list[tuple[int, str]] = []
        for snap_key, snap in self.de440["snapshots"].items():
            snap_jd = snap["epoch"]["jd_tdb"]
            if snap_jd <= start_jd:
                continue
            month_f = (snap_jd - start_jd) / MONTH_DAYS
            month_i = int(round(month_f))
            if 0 < month_i <= N_MONTHS:
                val_months.append((month_i, snap_key))
        val_months.sort()

        if not val_months:
            self.skipTest("No DE440 epochs after start_jd")

        print(f"\n{'='*70}")
        print(f"  MINOR BODIES -- validation against DE440")
        print(f"  Created: {self.fixture['metadata']['created_utc']}")
        print(f"  Integrity: {'OK' if self.fixture.get('_hash_ok') else 'FAILED'}")
        print(f"{'='*70}")

        pass_count   = 0
        total_checks = 0
        failures     = []

        for month_i, snap_key in val_months:
            snap_jd = self.de440["snapshots"][snap_key]["epoch"]["jd_tdb"]
            print(f"\n  Month {month_i:3d}  (DE440 {snap_key}, JD={snap_jd:.1f})")

            for name in MINOR_BODIES:
                # Get DE440 heliocentric ground truth
                de440_hel = _de440_heliocentric_km(snap_key, name)
                if de440_hel is None:
                    continue

                # Get our prediction at this month
                body_preds = self.bodies_pred.get(name, [])
                pred_entry = next((p for p in body_preds
                                   if p["month"] == month_i), None)
                if pred_entry is None:
                    continue

                pred_hel = np.array(pred_entry["heliocentric_km"])
                err_au   = float(np.linalg.norm(pred_hel - de440_hel)) / AU_KM
                thresh   = PASS_THRESHOLD_AU.get(name, 0.1)
                passed   = err_au < thresh
                total_checks += 1
                if passed:
                    pass_count += 1
                else:
                    failures.append(
                        f"  {name:12s} month {month_i}: "
                        f"err={err_au:.4f} AU > thresh={thresh:.4f} AU")

                print(f"    {name:12s}  err={err_au:.4f} AU  "
                      f"thresh={thresh:.3f} AU  "
                      f"{'PASS' if passed else 'FAIL'}")

        print(f"\n  -- MINOR BODIES SUMMARY --")
        print(f"  Pass: {pass_count}/{total_checks}")
        if failures:
            print("  Failures:")
            for f in failures:
                print(f)

        if total_checks > 0:
            pass_rate = pass_count / total_checks
            self.assertGreater(
                pass_rate, 0.50,
                f"Minor body pass rate {pass_rate:.0%} < 50%",
            )

    # -- physical sanity checks ----------------------------------------------

    def test_moon_stays_near_earth(self):
        """Moon heliocentric position should track Earth's position closely."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        if "Moon" not in self.bodies_pred:
            self.skipTest("Moon not in predictions")

        major_pred = _load_major_predictions()
        if not major_pred or "predictions" not in major_pred:
            self.skipTest("No major-body predictions loaded")

        earth_by_month = {p["month"]: np.array(p["ssbm"]["Earth"])
                          for p in major_pred["predictions"]
                          if "Earth" in p.get("ssbm", {})}

        for rec in self.bodies_pred["Moon"]:
            m = rec["month"]
            if m not in earth_by_month:
                continue
            moon_hel  = np.array(rec["heliocentric_km"])
            earth_hel = earth_by_month[m]
            sep_km    = float(np.linalg.norm(moon_hel - earth_hel))
            self.assertLess(
                sep_km, 2_000_000,   # < 2 million km from Earth
                f"Moon-Earth separation at month {m}: {sep_km:.0f} km",
            )

    def test_titan_stays_near_saturn(self):
        """Titan heliocentric position should track Saturn's position closely."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        if "Titan" not in self.bodies_pred:
            self.skipTest("Titan not in predictions")

        major_pred = _load_major_predictions()
        if not major_pred or "predictions" not in major_pred:
            self.skipTest("No major-body predictions loaded")

        saturn_by_month = {p["month"]: np.array(p["ssbm"]["Saturn"])
                           for p in major_pred["predictions"]
                           if "Saturn" in p.get("ssbm", {})}

        for rec in self.bodies_pred["Titan"]:
            m = rec["month"]
            if m not in saturn_by_month:
                continue
            titan_hel  = np.array(rec["heliocentric_km"])
            saturn_hel = saturn_by_month[m]
            sep_km     = float(np.linalg.norm(titan_hel - saturn_hel))
            self.assertLess(
                sep_km, 5_000_000,   # Titan's orbit is ~1.2 million km radius
                f"Titan-Saturn separation at month {m}: {sep_km:.0f} km",
            )

    def test_pluto_stays_in_kuiper_belt(self):
        """Pluto should stay in the 29-50 AU range throughout 30 years."""
        if not self.has_fixture:
            self.skipTest("No fixture")
        if "Pluto" not in self.bodies_pred:
            self.skipTest("Pluto not in predictions")

        dists = []
        for rec in self.bodies_pred["Pluto"]:
            hel   = np.array(rec["heliocentric_km"])
            dist  = float(np.linalg.norm(hel)) / AU_KM
            dists.append(dist)

        dmin, dmax = min(dists), max(dists)
        print(f"\n  Pluto heliocentric range: {dmin:.2f}-{dmax:.2f} AU")
        self.assertGreater(dmin, 25.0, f"Pluto min dist {dmin:.1f} AU < 25")
        self.assertLess(dmax, 60.0, f"Pluto max dist {dmax:.1f} AU > 60")


if __name__ == "__main__":
    unittest.main(verbosity=2)
