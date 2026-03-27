"""SGEphemeris -- SSBM-patched ephemeris adapter.

Provides planet/body positions using a priority chain:

  1. SSBM 30-year forecast fixture  (future epochs, 2025-2055)
  2. DE440 annual snapshot fixture   (past epochs, J2000-J2026)
  3. jplephem kernel                 (if installed + kernel cached)
  4. Keplerian orbit fit             (last resort, no external deps)

All positions returned in ICRF barycentric equatorial km.
sg_ prefix marks all SSBM-patched query methods.

Usage
-----
    from sigma_ground.field.interface.adapters.ephemeris import SGEphemeris

    eph = SGEphemeris()

    # Query a planet at any JD (past or future):
    pos_km = eph.sg_position("Mars", jd=2461000.0)  # (x, y, z) in km

    # Heliocentric (Sun subtracted):
    hel_km = eph.sg_heliocentric("Earth", jd=2461000.0)

    # With error estimate (difference vs Keplerian fallback):
    pos_km, err_au = eph.sg_position_with_uncertainty("Jupiter", jd=2465000.0)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from sigma_ground.field.interface.orbital import (
    ANCHOR_MAP, ANCHOR_GM, fit_orbit, predict_ssb_position,
    _ecliptic_to_equatorial,
)

AU_KM = 1.495978707e8
KM_TO_M = 1000.0

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_DE440_FILE    = _FIXTURES / "de440_state_vectors.json"
_FORECAST_FILE = _FIXTURES / "ssbm_future_predictions.json"

# Obliquity (same as orbital.py / adapters constants)
import math as _math
_OBL_RAD = _math.radians(23.439291111)
_COS_OBL = _math.cos(_OBL_RAD)
_SIN_OBL = _math.sin(_OBL_RAD)


class SGEphemeris:
    """SSBM-patched ephemeris with four-tier fallback.

    Thread-safety: the fixture caches are loaded on first access (lazy).
    The object is safe to create once and reuse across calls.
    """

    def __init__(self) -> None:
        self._de440:    dict | None = None
        self._forecast: dict | None = None
        self._kepler_cache: dict = {}

    # ── data loaders ─────────────────────────────────────────────────────

    def _load_de440(self) -> dict:
        if self._de440 is None:
            with open(_DE440_FILE) as f:
                self._de440 = json.load(f)
        return self._de440

    def _load_forecast(self) -> dict:
        if self._forecast is None:
            if _FORECAST_FILE.exists():
                with open(_FORECAST_FILE) as f:
                    self._forecast = json.load(f)
            else:
                self._forecast = {}
        return self._forecast

    def _kepler(self, body_name: str):
        """Cached Keplerian orbit fit for body_name."""
        if body_name not in self._kepler_cache:
            data = self._load_de440()
            orbit = fit_orbit(body_name, data)
            self._kepler_cache[body_name] = orbit
        return self._kepler_cache[body_name]

    # ── internal: per-tier lookups ────────────────────────────────────────

    def _de440_position(self, body_name: str, jd: float) -> np.ndarray | None:
        """Exact DE440 snapshot position (SSB-equatorial, km).
        Only works at annual marks J2000-J2026."""
        data = self._load_de440()
        best_snap = None
        best_delta = float("inf")
        for snap_key, snap in data["snapshots"].items():
            delta = abs(snap["epoch"]["jd_tdb"] - jd)
            if delta < best_delta:
                best_delta = delta
                best_snap = snap_key
        if best_snap is None or best_delta > 5.0:  # within 5 days of a snapshot
            return None
        for b in data["snapshots"][best_snap]["bodies"]:
            if b["name"] == body_name:
                sv = b["state_vector"]
                return np.array([sv["x_km"], sv["y_km"], sv["z_km"]])
        return None

    def _forecast_position(self, body_name: str, jd: float) -> np.ndarray | None:
        """SSBM forecast heliocentric position → convert to SSB (km).

        Forecast stores heliocentric equatorial coords.  To get SSB position,
        we add the Sun's SSB position from DE440 (nearest annual snapshot).
        """
        fc = self._load_forecast()
        if not fc or "predictions" not in fc:
            return None

        meta       = fc["metadata"]
        start_jd   = meta["start_jd"]
        month_days = meta["month_days"]
        month_f    = (jd - start_jd) / month_days
        month_i    = int(round(month_f))
        if month_i < 0 or month_i >= len(fc["predictions"]):
            return None

        entry = fc["predictions"][month_i]
        ssbm  = entry.get("ssbm", {})
        if body_name not in ssbm:
            return None

        hel_km = np.array(ssbm[body_name])  # heliocentric equatorial

        # Add nearest-snapshot Sun SSB position
        sun_ssb = self._de440_position("Sun", jd)
        if sun_ssb is None:
            # Use j2025 Sun as best available anchor
            sun_ssb = self._de440_position("Sun", start_jd)
        if sun_ssb is None:
            return None

        return hel_km + sun_ssb

    def _kepler_position(self, body_name: str, jd: float) -> np.ndarray | None:
        """Keplerian orbit prediction (SSB-equatorial, km)."""
        orbit = self._kepler(body_name)
        if orbit is None:
            return None
        # Get anchor SSB position
        data      = self._load_de440()
        snap_keys = sorted(data["snapshots"].keys())
        anchor_snap = snap_keys[-1]  # latest available
        pos = predict_ssb_position(orbit, data["snapshots"][anchor_snap], jd)
        if pos is None:
            return None
        return np.array(pos)

    def _jplephem_position(self, body_name: str, jd: float) -> np.ndarray | None:
        """jplephem kernel lookup (km) -- requires jplephem + downloaded kernel."""
        try:
            from sigma_ground.field.interface.adapters._jplephem_bridge import (
                query_jplephem,
            )
            return query_jplephem(body_name, jd)
        except Exception:
            return None

    # ── public sg_ API ────────────────────────────────────────────────────

    def sg_position(self, body_name: str, jd: float) -> np.ndarray:
        """SSB-equatorial barycentric position (km) using best available source.

        Priority: DE440 snapshot > SSBM forecast > Keplerian > jplephem.

        Parameters
        ----------
        body_name : planet name matching DE440/forecast fixture (e.g. 'Mars')
        jd        : Julian Date (TDB)

        Returns
        -------
        np.ndarray shape (3,) in km, ICRF equatorial
        """
        # Tier 1: DE440 exact snapshot
        pos = self._de440_position(body_name, jd)
        if pos is not None:
            return pos

        # Tier 2: SSBM 30-year forecast
        pos = self._forecast_position(body_name, jd)
        if pos is not None:
            return pos

        # Tier 3: Keplerian orbit fit
        pos = self._kepler_position(body_name, jd)
        if pos is not None:
            return pos

        # Tier 4: jplephem (optional external)
        pos = self._jplephem_position(body_name, jd)
        if pos is not None:
            return pos

        raise ValueError(
            f"Cannot determine position for {body_name!r} at JD={jd:.2f}. "
            f"All four tiers failed. "
            f"For future epochs beyond 2055, regenerate forecast with "
            f"MATERIA_RUN_PROPAGATION=1."
        )

    def sg_heliocentric(self, body_name: str, jd: float) -> np.ndarray:
        """Heliocentric equatorial position (km).

        Subtracts Sun's SSB position from body's SSB position.
        """
        body_pos = self.sg_position(body_name, jd)
        sun_pos  = self.sg_position("Sun", jd)
        return body_pos - sun_pos

    def sg_distance_au(self, body_name: str, jd: float) -> float:
        """Heliocentric distance in AU."""
        hel = self.sg_heliocentric(body_name, jd)
        return float(np.linalg.norm(hel)) / AU_KM

    def sg_position_with_uncertainty(
        self, body_name: str, jd: float,
    ) -> tuple[np.ndarray, float]:
        """Position (km) with estimated uncertainty in AU.

        Uncertainty = difference between SSBM forecast and Keplerian.
        For past epochs in DE440, uncertainty is effectively zero.
        For future epochs, this gives a conservative error bound.

        Returns
        -------
        pos_km  : np.ndarray (3,) -- best position estimate
        err_au  : float           -- estimated error bound in AU
        """
        pos = self.sg_position(body_name, jd)

        # Cross-check with Keplerian
        kepl = self._kepler_position(body_name, jd)
        if kepl is None:
            return pos, float("nan")

        diff_au = float(np.linalg.norm(pos - kepl)) / AU_KM
        return pos, diff_au

    def sg_available_bodies(self) -> list[str]:
        """All bodies for which position queries will succeed."""
        bodies: set[str] = set()
        data = self._load_de440()
        for snap in data["snapshots"].values():
            for b in snap["bodies"]:
                bodies.add(b["name"])
        fc = self._load_forecast()
        if fc and "predictions" in fc and fc["predictions"]:
            ssbm_bodies = fc["predictions"][0].get("ssbm", {}).keys()
            bodies.update(ssbm_bodies)
        return sorted(bodies)

    def sg_tier(self, body_name: str, jd: float) -> str:
        """Which data tier would serve this query: 'de440', 'forecast', 'kepler', 'jplephem', 'none'."""
        if self._de440_position(body_name, jd) is not None:
            return "de440"
        if self._forecast_position(body_name, jd) is not None:
            return "forecast"
        if self._kepler_position(body_name, jd) is not None:
            return "kepler"
        if self._jplephem_position(body_name, jd) is not None:
            return "jplephem"
        return "none"
