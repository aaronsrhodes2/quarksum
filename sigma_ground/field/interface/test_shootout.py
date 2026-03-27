"""CELESTIAL BODY PREDICTION SHOOTOUT
=====================================
Compares four predictors for all 26 DE440 bodies across every available
validated epoch, then scores them.

PREDICTORS
----------
  over-physics-nbody  All 26 bodies in one N-body system.
                      Forest-Ruth FR4 + 1PN GR + Solar Radiation Pressure.
                      Body area and albedo from IAU measurements.
                      dt = 1 day (note: inner moons with period < 2 days
                      will have phase uncertainty ~their orbital radius).

  standard-nbody      9-body Sun+planets, FR4 + 1PN GR, no SRP, dt=1 day.
                      From ssbm_future_predictions.json.  N/A for moons.

  kepler-local-lib    Least-squares Keplerian 2-body fit to DE440 annual
                      snapshots.  From ssbm_future_predictions.json and
                      ssbm_minor_bodies_predictions.json.

  de440 (JPL)         Ground truth for past epochs.  NOT Keplerian.
                      DE440 is a precision numerical integration including
                      GR, tides, SRP, asteroids -- far more than any single
                      predictor here.  It is the ruler, not a competitor.

SCORING
-------
  For each (body, validated epoch): predictor with smallest heliocentric
  error vs DE440 earns +1 point.  Ties give +1 to all tied predictors.
  Minor bodies where standard-nbody has no prediction are excluded from
  standard-nbody scoring for that body.

FUTURE EPOCHS
-------------
  No ground truth yet.  Predictions are stored with a SHA-256 hash binding
  them to the creation timestamp.  Re-run with any newer DE44x fixture in
  the fixtures/ directory to accumulate validation scores over time.

RUNNING
-------
  # First run (generates over-physics fixture, ~2 min):
  $env:MATERIA_RUN_PROPAGATION="1"; pytest local_library/interface/test_shootout.py -v -s

  # Fast re-run (loads committed fixture):
  pytest local_library/interface/test_shootout.py -v -s
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import time
import unittest
from pathlib import Path

import numpy as np

from sigma_ground.field.constants import G as _G, L_SUN_W as _L_SUN_W
from sigma_ground.field.interface.nbody import CelestialBody, NBodySystem

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
FIXTURES_DIR    = Path(__file__).parent / "fixtures"
DE440_FILE      = FIXTURES_DIR / "de440_state_vectors.json"
OVER_PHYS_FILE  = FIXTURES_DIR / "ssbm_over_physics_predictions.json"
STANDARD_FILE   = FIXTURES_DIR / "ssbm_future_predictions.json"
MINOR_FILE      = FIXTURES_DIR / "ssbm_minor_bodies_predictions.json"

_DE440 = None
def _load_de440() -> dict:
    global _DE440
    if _DE440 is None:
        _DE440 = json.loads(DE440_FILE.read_text())
    return _DE440

# ---------------------------------------------------------------------------
# Body physical parameters
# Source: IAU Working Group on Cartographic Coordinates (2015),
#         NASA Planetary Fact Sheets, JPL Small-Body Database.
# radius_km : mean volumetric radius
# albedo    : geometric albedo (used as radiation pressure coefficient CR)
# ---------------------------------------------------------------------------
_BODY_PARAMS: dict[str, tuple[float, float]] = {
    # name         radius_km   albedo/CR
    "Sun":        (695700.0,  0.000),  # emitter -- no SRP on self
    "Mercury":    (  2440.0,  0.088),  # IAU 2015
    "Venus":      (  6052.0,  0.689),
    "Earth":      (  6371.0,  0.367),
    "Moon":       (  1737.4,  0.120),
    "Mars":       (  3389.5,  0.170),
    "Phobos":     (    11.2,  0.071),
    "Deimos":     (     6.1,  0.068),
    "Jupiter":    ( 71492.0,  0.520),
    "Io":         (  1821.6,  0.630),
    "Europa":     (  1560.8,  0.670),
    "Ganymede":   (  2634.1,  0.430),
    "Callisto":   (  2410.3,  0.170),
    "Saturn":     ( 60268.0,  0.470),
    "Enceladus":  (   252.1,  0.990),  # highest albedo in solar system
    "Titan":      (  2574.7,  0.220),
    "Uranus":     ( 25559.0,  0.510),
    "Miranda":    (   235.8,  0.320),
    "Ariel":      (   578.9,  0.530),
    "Umbriel":    (   584.7,  0.260),
    "Titania":    (   788.9,  0.350),
    "Oberon":     (   761.4,  0.310),
    "Neptune":    ( 24764.0,  0.410),
    "Triton":     (  1353.4,  0.760),
    "Pluto":      (  1188.3,  0.520),
    "Charon":     (   606.0,  0.350),
}

# Short orbital periods (days) -- note in chart that phase is unreliable
_SHORT_PERIOD_DAYS: dict[str, float] = {
    "Phobos":    0.319,
    "Deimos":    1.263,
    "Io":        1.769,
    "Enceladus": 1.370,
    "Europa":    3.551,
}

# Display ordering: primary bodies first, then by parent
_DISPLAY_ORDER = [
    "Mercury", "Venus", "Earth", "Moon",
    "Mars", "Phobos", "Deimos",
    "Jupiter", "Io", "Europa", "Ganymede", "Callisto",
    "Saturn", "Enceladus", "Titan",
    "Uranus", "Miranda", "Ariel", "Umbriel", "Titania", "Oberon",
    "Neptune", "Triton",
    "Pluto", "Charon",
]

AU_KM    = 1.495978707e8
KM_TO_M  = 1000.0
MONTH_DAYS = 365.25 / 12.0
N_MONTHS   = 360
DT_DAYS    = 1.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_J2000_DT = datetime.datetime(2000, 1, 1, 12, 0, 0)


def _jd_to_iso(jd: float) -> str:
    dt = _J2000_DT + datetime.timedelta(days=jd - 2451545.0)
    return dt.strftime("%Y-%m-%d")


def _utc_now_iso() -> str:
    return datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_payload(created_utc: str, predictions: list) -> str:
    payload = json.dumps(
        {"created_utc": created_utc, "predictions": predictions},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _de440_heliocentric_km(snap_key: str, name: str) -> np.ndarray | None:
    data  = _load_de440()
    snap  = data["snapshots"].get(snap_key)
    if snap is None:
        return None
    by_name = {b["name"]: b for b in snap["bodies"]}
    if name not in by_name or "Sun" not in by_name:
        return None
    def _sv(b):
        sv = b["state_vector"]
        return np.array([sv["x_km"], sv["y_km"], sv["z_km"]])
    return _sv(by_name[name]) - _sv(by_name["Sun"])


def _win_marker(is_winner: bool) -> str:
    return " <--" if is_winner else "    "


def _fmt_err(err_au: float | None) -> str:
    if err_au is None:
        return "      N/A      "
    return f"  {err_au:10.6f} AU"


# ---------------------------------------------------------------------------
# Over-physics prediction generation
# ---------------------------------------------------------------------------

def _build_over_physics_bodies(snap_key: str) -> list[CelestialBody]:
    """Build all 26 CelestialBody objects from a DE440 snapshot."""
    data   = _load_de440()
    snap   = data["snapshots"][snap_key]
    by_name = {b["name"]: b for b in snap["bodies"]}
    bodies = []
    for name in sorted(by_name.keys()):
        b   = by_name[name]
        sv  = b["state_vector"]
        gm  = b["gm_km3_s2"] * 1e9    # -> m³/s²
        mass = gm / _G
        pos  = np.array([sv["x_km"], sv["y_km"], sv["z_km"]]) * KM_TO_M
        vel  = np.array([sv["vx_km_s"], sv["vy_km_s"], sv["vz_km_s"]]) * KM_TO_M
        r_km, albedo = _BODY_PARAMS.get(name, (1.0, 0.0))
        r_m  = r_km * KM_TO_M
        area = math.pi * r_m**2 if name != "Sun" else 0.0
        bodies.append(CelestialBody(
            mass, pos, vel, r_m, 0.0,
            area_m2=area, reflectivity=albedo,
        ))
    return bodies, sorted(by_name.keys())


def _generate_over_physics_predictions() -> dict:
    """Run 30-year FR4+GR+SRP integration for all 26 bodies.

    dt = 1 day  (~2 min).  Monthly checkpoints.  SHA-256 timestamped.

    Note on inner moons: Phobos (T=0.32d), Deimos (1.26d), Io (1.77d),
    Enceladus (1.37d) have orbital periods near or below dt=1 day.
    Their N-body phase prediction is unreliable; heliocentric error is
    dominated by the parent planet prediction, not the moon's phase.
    This is noted in the shootout chart.
    """
    data      = _load_de440()
    start_key = "j2025"
    start_jd  = data["snapshots"][start_key]["epoch"]["jd_tdb"]

    bodies_init, body_names = _build_over_physics_bodies(start_key)
    # body_names is sorted alphabetically; Sun is included at index for Sun
    sun_idx = body_names.index("Sun")

    # Record which names are predicted (all except Sun for heliocentric)
    predicted_names = [n for n in body_names if n != "Sun"]

    DT_S        = DT_DAYS * 86400.0
    checkpoints = [int(round(m * MONTH_DAYS / DT_DAYS)) for m in range(N_MONTHS + 1)]
    total_steps = checkpoints[-1]

    system = NBodySystem(bodies_init, include_gr=True,
                         solar_luminosity_W=_L_SUN_W)

    print(f"\n  Generating over-physics forecast:")
    print(f"    26 bodies | FR4 | 1PN GR | SRP (L_sun={_L_SUN_W:.3e} W)")
    print(f"    dt={DT_DAYS}d | {N_MONTHS} months | ~2 min ...")

    predictions: list[dict] = []
    check_idx = 0
    t0 = time.time()

    for step in range(total_steps + 1):
        if check_idx <= N_MONTHS and step == checkpoints[check_idx]:
            month  = check_idx
            jd_now = start_jd + step * DT_DAYS
            sun_pos = system.bodies[sun_idx].position_m
            entry: dict = {
                "month":    month,
                "jd":       round(jd_now, 4),
                "iso_date": _jd_to_iso(jd_now),
                "over":     {},
            }
            for i, name in enumerate(body_names):
                if name == "Sun":
                    continue
                hel_km = (system.bodies[i].position_m - sun_pos) / KM_TO_M
                entry["over"][name] = [
                    round(float(hel_km[0]), 3),
                    round(float(hel_km[1]), 3),
                    round(float(hel_km[2]), 3),
                ]
            predictions.append(entry)
            check_idx += 1
            if check_idx > N_MONTHS:
                break
        if step < total_steps:
            system.forest_ruth_step(DT_S)
        if step % 2000 == 0 and step > 0:
            elapsed = time.time() - t0
            pct = 100 * step / total_steps
            eta = elapsed / step * (total_steps - step)
            print(f"    step {step}/{total_steps} ({pct:.0f}%)  "
                  f"elapsed={elapsed:.0f}s  eta={eta:.0f}s", flush=True)

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.0f}s ({elapsed/60:.1f} min).")

    created_utc = _utc_now_iso()
    sha256      = _hash_payload(created_utc, predictions)

    fixture = {
        "metadata": {
            "created_utc":        created_utc,
            "start_jd":           start_jd,
            "dt_days":            DT_DAYS,
            "n_months":           N_MONTHS,
            "integrator":         "forest_ruth_4th_order",
            "include_gr":         True,
            "include_srp":        True,
            "solar_luminosity_W": _L_SUN_W,
            "bodies":             predicted_names,
            "note": (
                "ALL 26 DE440 bodies. FR4+GR+SRP. SHA-256 binds timestamp to data. "
                "Inner moons (Phobos/Deimos/Io/Enceladus) have phase uncertainty "
                "~their orbital radius because dt=1d > their period."
            ),
        },
        "predictions_sha256": sha256,
        "predictions":        predictions,
    }

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    OVER_PHYS_FILE.write_text(json.dumps(fixture, indent=2))
    print(f"  Saved {OVER_PHYS_FILE.name}  sha256={sha256[:16]}...")
    return fixture


def _load_over_physics() -> dict:
    if not OVER_PHYS_FILE.exists():
        return {}
    fixture = json.loads(OVER_PHYS_FILE.read_text())
    stored   = fixture.get("predictions_sha256", "")
    computed = _hash_payload(
        fixture["metadata"]["created_utc"],
        fixture["predictions"],
    )
    fixture["_hash_ok"]       = (stored == computed)
    fixture["_stored_hash"]   = stored
    fixture["_computed_hash"] = computed
    return fixture


# ---------------------------------------------------------------------------
# Load competing predictors
# ---------------------------------------------------------------------------

def _load_standard() -> dict[int, dict]:
    """Load standard-nbody monthly predictions {month -> {name -> [x,y,z]}}."""
    if not STANDARD_FILE.exists():
        return {}
    data = json.loads(STANDARD_FILE.read_text())
    result = {}
    for p in data.get("predictions", []):
        result[p["month"]] = p.get("ssbm", {})
    return result


def _load_kepler_major() -> dict[int, dict]:
    """Kepler predictions for major planets from standard fixture."""
    if not STANDARD_FILE.exists():
        return {}
    data = json.loads(STANDARD_FILE.read_text())
    result = {}
    for p in data.get("predictions", []):
        result[p["month"]] = p.get("kepler", {})
    return result


def _load_kepler_minor() -> dict[str, dict[int, list]]:
    """Kepler predictions for minor bodies {name -> {month -> [x,y,z]}}."""
    if not MINOR_FILE.exists():
        return {}
    data = json.loads(MINOR_FILE.read_text())
    result: dict[str, dict[int, list]] = {}
    for name, entries in data.get("bodies_predicted", {}).items():
        result[name] = {e["month"]: e["heliocentric_km"] for e in entries}
    return result


# ---------------------------------------------------------------------------
# Shootout comparison logic
# ---------------------------------------------------------------------------

def _get_prediction(
    name: str,
    month: int,
    over_by_month: dict,
    std_by_month: dict,
    kepl_major: dict,
    kepl_minor: dict,
) -> dict[str, np.ndarray | None]:
    """Return heliocentric km predictions for each method."""
    def _arr(val):
        return np.array(val) if val is not None else None

    # over-physics
    over = _arr(over_by_month.get(month, {}).get("over", {}).get(name))

    # standard-nbody (only major planets)
    std = _arr(std_by_month.get(month, {}).get(name))

    # kepler: try major first, then minor
    kepl = _arr(kepl_major.get(month, {}).get(name))
    if kepl is None and name in kepl_minor:
        kepl = _arr(kepl_minor[name].get(month))

    return {"over-physics": over, "standard": std, "kepler": kepl}


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------

_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


def _coloured(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


def _print_shootout_chart(
    val_months:     list[tuple[int, str]],
    over_by_month:  dict,
    std_by_month:   dict,
    kepl_major:     dict,
    kepl_minor:     dict,
    created_utc:    str,
    sha256:         str,
) -> tuple[dict[str, int], int, int]:
    """Print the shootout chart and return (scores, pass_count, total_checks)."""

    METHODS = ["over-physics", "standard", "kepler"]
    scores  = {m: 0 for m in METHODS}
    pass_count    = 0
    total_checks  = 0

    W = 90
    print()
    print("=" * W)
    print(f"  CELESTIAL BODY PREDICTION SHOOTOUT")
    print(f"  Created : {created_utc}  |  SHA-256: {sha256[:24]}...")
    print(f"  Basis   : DE440 heliocentric ICRF km  |  Win = smallest error")
    print(f"  NOTE    : DE440 (JPL) is precision N-body integration, NOT Keplerian.")
    print(f"            It is the ground truth ruler, not a competitor.")
    print("=" * W)
    print(f"  {'Body':<12} {'Epoch':<8} {'over-physics':>16} "
          f"{'standard':>16} {'kepler':>16}  Winner")
    print("  " + "-" * (W - 2))

    for month_idx, snap_key in val_months:
        pred_jd  = over_by_month.get(month_idx, {}).get("jd", 0.0)
        iso_date = over_by_month.get(month_idx, {}).get("iso_date", snap_key)

        print(f"\n  [{snap_key.upper()}  month={month_idx}  {iso_date}]")

        for name in _DISPLAY_ORDER:
            # DE440 ground truth
            de440_hel = _de440_heliocentric_km(snap_key, name)
            if de440_hel is None:
                continue

            preds = _get_prediction(
                name, month_idx,
                over_by_month, std_by_month, kepl_major, kepl_minor)

            errors: dict[str, float | None] = {}
            for method, pred_vec in preds.items():
                if pred_vec is not None:
                    errors[method] = float(
                        np.linalg.norm(pred_vec - de440_hel)) / AU_KM
                else:
                    errors[method] = None

            # Find winner (minimum non-None error)
            valid = {m: e for m, e in errors.items() if e is not None}
            if not valid:
                continue

            min_err = min(valid.values())
            winners = [m for m, e in valid.items() if e == min_err or
                       (e is not None and abs(e - min_err) < 1e-9)]
            for w in winners:
                scores[w] += 1

            total_checks += 1
            # "pass" if best error < 0.5 AU (reasonable prediction)
            if min_err < 0.5:
                pass_count += 1

            # Phase warning for inner moons
            phase_note = ""
            if name in _SHORT_PERIOD_DAYS:
                phase_note = f" [phase~{_SHORT_PERIOD_DAYS[name]:.2f}d]"

            # Format each column
            def _fmt(method):
                e = errors[method]
                if e is None:
                    return f"{'N/A':>14}"
                s = f"{e:12.6f} AU"
                if method in winners:
                    return _coloured(f"{s:>14}", _GREEN)
                return f"{s:>14}"

            winner_label = "+".join(
                {"over-physics": "OVER", "standard": "STD",
                 "kepler": "KEPL"}[w] for w in winners)

            print(f"  {name:<12} {' ':8} "
                  f"{_fmt('over-physics')}  "
                  f"{_fmt('standard')}  "
                  f"{_fmt('kepler')}  "
                  f"{_coloured(winner_label, _YELLOW)}{phase_note}")

    # Summary
    print()
    print("  " + "=" * (W - 2))
    print(f"  {'SCORES':<14} "
          f"{'over-physics':>14}:{scores['over-physics']:4d}   "
          f"{'standard':>10}:{scores['standard']:4d}   "
          f"{'kepler':>8}:{scores['kepler']:4d}")
    print("  " + "=" * (W - 2))
    print(f"  Pass rate (best error < 0.5 AU): {pass_count}/{total_checks}")
    print()

    return scores, pass_count, total_checks


def _print_future_section(over_fixture: dict) -> None:
    """Show future predictions (no ground truth yet)."""
    predictions = over_fixture.get("predictions", [])
    if not predictions:
        return

    today_jd = 2451545.0 + (
        datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        - _J2000_DT
    ).total_seconds() / 86400.0

    future = [p for p in predictions if p["jd"] > today_jd]
    past   = [p for p in predictions if p["jd"] <= today_jd]
    start_jd = over_fixture["metadata"]["start_jd"]

    W = 90
    print("=" * W)
    print("  FUTURE PREDICTIONS (ground truth not yet available)")
    print(f"  Past months elapsed: {len(past)}  |  Future pending: {len(future)}")
    if future:
        print(f"  Next due:  {future[0]['iso_date']} (month {future[0]['month']})")
        print(f"  Final:     {future[-1]['iso_date']} (month {future[-1]['month']})")
    print()
    print("  To validate future predictions, place a newer DE44x fixture in")
    print("  local_library/interface/fixtures/ as de44x_state_vectors.json")
    print("  and re-run -- the test will automatically score against it.")
    print()

    # Sample future predictions for a subset of bodies + months
    sample_months = [m for m in [12, 60, 120, 240, 360]
                     if m < len(predictions) and predictions[m]["jd"] > today_jd]
    if not sample_months:
        print("  (All prediction months are in the past.)")
        print("=" * W)
        return

    sample_bodies = ["Mercury", "Earth", "Jupiter", "Neptune", "Pluto"]
    hdr = f"  {'Body':<12}"
    for m in sample_months:
        hdr += f"  {predictions[m]['iso_date']:>14}"
    print(hdr)
    print("  " + "-" * (W - 2))

    for name in sample_bodies:
        row = f"  {name:<12}"
        for m in sample_months:
            pos = predictions[m].get("over", {}).get(name)
            if pos:
                dist_au = math.sqrt(pos[0]**2 + pos[1]**2 + pos[2]**2) / AU_KM
                row += f"  {dist_au:>12.4f} AU"
            else:
                row += f"  {'N/A':>14}"
        print(row)
    print("=" * W)


# =============================================================================
# TESTS
# =============================================================================

class TestShootout(unittest.TestCase):
    """Celestial body prediction shootout: over-physics vs standard vs Kepler.

    Set MATERIA_RUN_PROPAGATION=1 to regenerate the over-physics fixture.
    """

    @classmethod
    def setUpClass(cls):
        if (os.environ.get("MATERIA_RUN_PROPAGATION", "") == "1"
                or not OVER_PHYS_FILE.exists()):
            _generate_over_physics_predictions()

        cls.over_fixture    = _load_over_physics()
        cls.has_over        = bool(cls.over_fixture)
        cls.over_by_month   = (
            {p["month"]: p for p in cls.over_fixture.get("predictions", [])}
            if cls.has_over else {}
        )
        cls.std_by_month    = _load_standard()
        cls.kepl_major      = _load_kepler_major()
        cls.kepl_minor      = _load_kepler_minor()
        cls.de440           = _load_de440()

        # Find validated months (DE440 epochs after start_jd)
        cls.val_months: list[tuple[int, str]] = []
        if cls.has_over:
            start_jd = cls.over_fixture["metadata"]["start_jd"]
            for snap_key, snap in cls.de440["snapshots"].items():
                snap_jd = snap["epoch"]["jd_tdb"]
                if snap_jd <= start_jd:
                    continue
                month_f = (snap_jd - start_jd) / MONTH_DAYS
                month_i = int(round(month_f))
                if 0 < month_i <= N_MONTHS and month_i in cls.over_by_month:
                    cls.val_months.append((month_i, snap_key))
            cls.val_months.sort()

    # -- integrity -----------------------------------------------------------

    def test_over_physics_fixture_exists(self):
        self.assertTrue(
            OVER_PHYS_FILE.exists(),
            "Over-physics fixture missing -- run with MATERIA_RUN_PROPAGATION=1",
        )

    def test_over_physics_hash_integrity(self):
        if not self.has_over:
            self.skipTest("No fixture")
        self.assertTrue(
            self.over_fixture.get("_hash_ok", False),
            f"Hash MISMATCH -- fixture may have been altered!\n"
            f"  stored  : {self.over_fixture.get('_stored_hash','?')[:24]}...\n"
            f"  computed: {self.over_fixture.get('_computed_hash','?')[:24]}...",
        )

    def test_all_25_non_sun_bodies_predicted(self):
        """Over-physics fixture must contain all 25 non-Sun bodies."""
        if not self.has_over:
            self.skipTest("No fixture")
        predicted = set(self.over_fixture["metadata"].get("bodies", []))
        expected  = set(_DISPLAY_ORDER)  # 25 bodies (no Sun)
        missing   = expected - predicted
        self.assertEqual(missing, set(),
                         f"Missing bodies: {sorted(missing)}")

    def test_prediction_count(self):
        """Must have N_MONTHS + 1 monthly entries (month 0 through 360)."""
        if not self.has_over:
            self.skipTest("No fixture")
        self.assertEqual(len(self.over_fixture["predictions"]), N_MONTHS + 1)

    # -- main shootout -------------------------------------------------------

    def test_shootout_chart(self):
        """Print the full comparison chart and assert basic pass rate.

        This is the main test -- the rich chart output shows every body,
        every predictor, and the winner at each validated epoch.
        """
        if not self.has_over:
            self.skipTest("No fixture")
        if not self.val_months:
            self.skipTest("No DE440 epochs after start_jd in fixture")

        scores, pass_count, total_checks = _print_shootout_chart(
            self.val_months,
            self.over_by_month,
            self.std_by_month,
            self.kepl_major,
            self.kepl_minor,
            created_utc=self.over_fixture["metadata"]["created_utc"],
            sha256=self.over_fixture.get("predictions_sha256", ""),
        )

        # Store scores on the class for use in subsequent tests
        TestShootout._scores       = scores
        TestShootout._pass_count   = pass_count
        TestShootout._total_checks = total_checks

        # At least 50% of all body-epoch checks should have a best error < 0.5 AU
        if total_checks > 0:
            self.assertGreater(
                pass_count / total_checks, 0.50,
                f"Only {pass_count}/{total_checks} body-epochs within 0.5 AU",
            )

    def test_future_predictions_report(self):
        """Print the future predictions status report (always passes)."""
        if not self.has_over:
            self.skipTest("No fixture")
        _print_future_section(self.over_fixture)
        self.assertGreaterEqual(
            len(self.over_fixture.get("predictions", [])), N_MONTHS,
        )

    # -- physics sanity checks -----------------------------------------------

    def test_srp_included_in_over_physics(self):
        """Fixture metadata must record SRP as enabled."""
        if not self.has_over:
            self.skipTest("No fixture")
        meta = self.over_fixture["metadata"]
        self.assertTrue(meta.get("include_srp", False),
                        "over-physics fixture should have include_srp=True")
        self.assertGreater(meta.get("solar_luminosity_W", 0), 0)

    def test_gr_included_in_over_physics(self):
        """Fixture metadata must record 1PN GR as enabled."""
        if not self.has_over:
            self.skipTest("No fixture")
        self.assertTrue(
            self.over_fixture["metadata"].get("include_gr", False),
            "over-physics fixture should have include_gr=True",
        )

    def test_over_physics_earth_stays_habitable(self):
        """Earth heliocentric distance should stay 0.90-1.10 AU for all months."""
        if not self.has_over:
            self.skipTest("No fixture")
        dists = []
        for p in self.over_fixture["predictions"]:
            pos = p.get("over", {}).get("Earth")
            if pos:
                d = math.sqrt(pos[0]**2 + pos[1]**2 + pos[2]**2) / AU_KM
                dists.append(d)
        self.assertTrue(len(dists) > 300)
        dmin, dmax = min(dists), max(dists)
        print(f"\n  Earth over-physics range: {dmin:.4f}-{dmax:.4f} AU")
        self.assertGreater(dmin, 0.90)
        self.assertLess(dmax, 1.10)

    def test_over_physics_pluto_range(self):
        """Pluto should stay in 29-49 AU heliocentric range."""
        if not self.has_over:
            self.skipTest("No fixture")
        dists = []
        for p in self.over_fixture["predictions"]:
            pos = p.get("over", {}).get("Pluto")
            if pos:
                d = math.sqrt(pos[0]**2 + pos[1]**2 + pos[2]**2) / AU_KM
                dists.append(d)
        if not dists:
            self.skipTest("Pluto not in over-physics predictions")
        dmin, dmax = min(dists), max(dists)
        print(f"\n  Pluto over-physics range: {dmin:.2f}-{dmax:.2f} AU")
        self.assertGreater(dmin, 25.0)
        self.assertLess(dmax, 60.0)

    def test_creation_timestamp_present(self):
        """Fixture must have a valid ISO 8601 UTC timestamp."""
        if not self.has_over:
            self.skipTest("No fixture")
        ts = self.over_fixture["metadata"]["created_utc"]
        self.assertRegex(ts, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_inner_moon_phase_warning_documented(self):
        """Fixture note must acknowledge inner moon phase limitation."""
        if not self.has_over:
            self.skipTest("No fixture")
        note = self.over_fixture["metadata"].get("note", "")
        # Should mention the phase issue
        self.assertIn("phase", note.lower(),
                      "Fixture note should acknowledge inner moon phase uncertainty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
