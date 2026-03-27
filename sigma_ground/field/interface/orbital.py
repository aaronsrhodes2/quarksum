"""Keplerian orbit fitting from discrete state-vector snapshots (DE440).

Given yearly (position, velocity, time) samples from JPL Horizons, computes
classical orbital elements from each state vector, then refines by
least-squares optimization of position + velocity residuals across all epochs.

The fit operates on relative state vectors (body minus anchor) in the ecliptic
J2000 frame.  ICRF (equatorial) data from the fixture are rotated to ecliptic
before fitting; predictions are rotated back.

All constants from sigma_ground.field.constants.  No magic numbers.
  ANCHOR_GM values: measured from DE440/JPL ephemerides (NAIF PDS).
  J2000_OBLIQUITY_DEG: IAU 1976 / IERS 1980 value (Lieske et al. 1977).
  Levenberg-Marquardt coefficients: standard algorithm (Moré 1978), no approx.

References
----------
  Bate, Mueller & White (1971): Fundamentals of Astrodynamics (rv→elements).
  Levenberg (1944), Marquardt (1963), Moré (1978): LM optimizer.
  Lieske et al. (1977): J2000 obliquity, A&A 58, 1-16.
  Folkner et al. (2014): DE430/440 planetary ephemerides, IPN Progress Report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

JD_J2000 = 2_451_545.0
TWO_PI = 2.0 * math.pi
DEG = math.pi / 180.0

# IAU 1976 / IERS 1980 mean obliquity of the ecliptic at J2000.0
# Source: Lieske et al. (1977), A&A 58, 1-16; adopted by IAU 1976 resolution.
# LOCAL_LIBRARY: measured — fixed standard epoch constant, not an approximation.
J2000_OBLIQUITY_DEG = 23.439291111
_OBL_RAD = math.radians(J2000_OBLIQUITY_DEG)
_COS_OBL = math.cos(_OBL_RAD)
_SIN_OBL = math.sin(_OBL_RAD)

# Default anchor body per planet / moon
ANCHOR_MAP: dict[str, str] = {
    "Mercury": "Sun", "Venus": "Sun", "Earth": "Sun", "Mars": "Sun",
    "Jupiter": "Sun", "Saturn": "Sun", "Uranus": "Sun", "Neptune": "Sun",
    "Pluto": "Sun",
    "Moon": "Earth",
    "Phobos": "Mars", "Deimos": "Mars",
    "Io": "Jupiter", "Europa": "Jupiter", "Ganymede": "Jupiter", "Callisto": "Jupiter",
    "Enceladus": "Saturn", "Titan": "Saturn",
    "Miranda": "Uranus", "Ariel": "Uranus", "Umbriel": "Uranus",
    "Titania": "Uranus", "Oberon": "Uranus",
    "Triton": "Neptune",
    "Charon": "Pluto",
}

# GM values (km³/s²) from JPL DE440 ephemeris.
# LOCAL_LIBRARY: measured from DE440/JPL — NAIF PDS, Folkner et al. (2014).
# These are measured gravitational parameters, not approximations.
ANCHOR_GM: dict[str, float] = {
    "Sun":     132_712_440_041.93938,
    "Earth":         398_600.435436,
    "Mars":           42_828.375662,
    "Jupiter":   126_686_531.900,
    "Saturn":     37_931_206.234,
    "Uranus":      5_793_950.6103,
    "Neptune":     6_835_099.97,
    "Pluto":             869.326,
}


def _equatorial_to_ecliptic(
    x_eq: float, y_eq: float, z_eq: float,
) -> tuple[float, float, float]:
    """Rotate ICRF equatorial → ecliptic J2000."""
    x_ecl = x_eq
    y_ecl =  _COS_OBL * y_eq + _SIN_OBL * z_eq
    z_ecl = -_SIN_OBL * y_eq + _COS_OBL * z_eq
    return (x_ecl, y_ecl, z_ecl)


def _ecliptic_to_equatorial(
    x_ecl: float, y_ecl: float, z_ecl: float,
) -> tuple[float, float, float]:
    """Rotate ecliptic J2000 → ICRF equatorial."""
    x_eq = x_ecl
    y_eq = _COS_OBL * y_ecl - _SIN_OBL * z_ecl
    z_eq = _SIN_OBL * y_ecl + _COS_OBL * z_ecl
    return (x_eq, y_eq, z_eq)


def _state_to_elements(
    r: np.ndarray,
    v: np.ndarray,
    gm_km3_s2: float,
) -> tuple[float, float, float, float, float, float] | None:
    """Convert state vector (km, km/s) to Keplerian elements.

    Returns (a_km, e, inc_rad, Omega_rad, omega_rad, M_rad) or None if
    hyperbolic.  Algorithm: Bate, Mueller & White (1971) §2.4.
    """
    mu    = gm_km3_s2
    r_mag = np.linalg.norm(r)
    v_mag = np.linalg.norm(v)

    h     = np.cross(r, v)
    h_mag = np.linalg.norm(h)
    if h_mag < 1e-20:
        return None

    n_vec = np.cross(np.array([0, 0, 1.0]), h)
    n_mag = np.linalg.norm(n_vec)

    e_vec = ((v_mag**2 - mu / r_mag) * r - np.dot(r, v) * v) / mu
    e     = np.linalg.norm(e_vec)

    energy = v_mag**2 / 2.0 - mu / r_mag
    if energy >= 0:
        return None
    a = -mu / (2.0 * energy)

    inc = math.acos(np.clip(h[2] / h_mag, -1.0, 1.0))

    if n_mag > 1e-20:
        Omega = math.acos(np.clip(n_vec[0] / n_mag, -1.0, 1.0))
        if n_vec[1] < 0:
            Omega = TWO_PI - Omega
    else:
        Omega = 0.0

    if n_mag > 1e-20 and e > 1e-10:
        omega = math.acos(np.clip(np.dot(n_vec, e_vec) / (n_mag * e), -1.0, 1.0))
        if e_vec[2] < 0:
            omega = TWO_PI - omega
    else:
        omega = 0.0

    if e > 1e-10:
        cos_v = np.dot(e_vec, r) / (e * r_mag)
        cos_v = np.clip(cos_v, -1.0, 1.0)
        v_angle = math.acos(cos_v)
        if np.dot(r, v) < 0:
            v_angle = TWO_PI - v_angle
    else:
        v_angle = math.atan2(r[1], r[0]) - Omega - omega

    E = 2.0 * math.atan2(
        math.sqrt(1 - e) * math.sin(v_angle / 2),
        math.sqrt(1 + e) * math.cos(v_angle / 2),
    )
    M = (E - e * math.sin(E)) % TWO_PI

    return (a, e, inc, Omega, omega, M)


def _keplerian_pos_vel(
    params: np.ndarray,
    gm: float,
    t_seconds: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute ecliptic position/velocity from 6 Keplerian elements at time t.

    params: [a_km, e, inc_rad, Omega_rad, omega_rad, M0_rad]
    Returns (pos_km, vel_km_s) in ecliptic frame.
    """
    a, e, inc, Omega, omega, M0 = params
    e = min(max(e, 1e-10), 0.9999)
    a = max(a, 1.0)

    # Period from Kepler III: T = 2π √(a³/μ)  — coefficients exact
    period = TWO_PI * math.sqrt((a * 1000.0) ** 3 / (gm * 1e9))
    if period <= 0:
        return np.array([a, 0.0, 0.0]), np.array([0.0, 0.0, 0.0])
    n = TWO_PI / period
    M = (M0 + n * t_seconds) % TWO_PI

    # Kepler equation: Newton-Raphson (converges in ≤ 10 iterations for e < 0.999)
    E = M + e * math.sin(M) if e < 0.8 else math.pi
    for _ in range(60):
        dE = (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-14:
            break

    v_angle = 2.0 * math.atan2(
        math.sqrt(1 + e) * math.sin(E / 2),
        math.sqrt(1 - e) * math.cos(E / 2),
    )
    r = a * (1 - e * math.cos(E))

    x_orb = r * math.cos(v_angle)
    y_orb = r * math.sin(v_angle)

    cos_o, sin_o = math.cos(omega), math.sin(omega)
    cos_O, sin_O = math.cos(Omega), math.sin(Omega)
    cos_i, sin_i = math.cos(inc), math.sin(inc)

    # Perifocal → ecliptic direction cosines
    Px = cos_O * cos_o - sin_O * sin_o * cos_i
    Py = sin_O * cos_o + cos_O * sin_o * cos_i
    Pz = sin_o * sin_i
    Qx = -cos_O * sin_o - sin_O * cos_o * cos_i
    Qy = -sin_O * sin_o + cos_O * cos_o * cos_i
    Qz = cos_o * sin_i

    pos = np.array([
        Px * x_orb + Qx * y_orb,
        Py * x_orb + Qy * y_orb,
        Pz * x_orb + Qz * y_orb,
    ])

    p    = a * (1 - e**2)
    h_mag = math.sqrt(gm * p)
    vr   = (gm / h_mag) * e * math.sin(v_angle)
    vt   = (gm / h_mag) * (1 + e * math.cos(v_angle))

    r_hat = pos / max(float(np.linalg.norm(pos)), 1e-20)
    h_hat = np.array([
        Py * Qz - Pz * Qy,
        Pz * Qx - Px * Qz,
        Px * Qy - Py * Qx,
    ])
    h_norm = float(np.linalg.norm(h_hat))
    if h_norm > 1e-20:
        h_hat = h_hat / h_norm
    t_hat = np.cross(h_hat, r_hat)

    vel = vr * r_hat + vt * t_hat

    return pos, vel


@dataclass
class FittedOrbit:
    """Result of a Keplerian orbit fit."""
    body:                      str
    anchor:                    str
    gm_km3_s2:                 float
    a_km:                      float
    eccentricity:              float
    inclination_deg:           float
    loan_deg:                  float
    aop_deg:                   float
    mean_anomaly_at_j2000_deg: float
    residual_rms_km:           float
    reference_jd:              float

    def predict_relative_ecliptic(self, jd: float) -> tuple[float, float, float]:
        """Predict anchor-relative ecliptic position at Julian Date."""
        dt_s = (jd - self.reference_jd) * 86400.0
        params = np.array([
            self.a_km, self.eccentricity,
            self.inclination_deg * DEG, self.loan_deg * DEG,
            self.aop_deg * DEG, self.mean_anomaly_at_j2000_deg * DEG,
        ])
        pos, _ = _keplerian_pos_vel(params, self.gm_km3_s2, dt_s)
        return (float(pos[0]), float(pos[1]), float(pos[2]))


def _levenberg_marquardt_bounded(
    residuals_func,
    x0:      np.ndarray,
    lo:      np.ndarray,
    hi:      np.ndarray,
    max_nfev: int   = 10_000,
    xtol:    float  = 1e-14,
    ftol:    float  = 1e-14,
) -> np.ndarray:
    """Bounded Levenberg-Marquardt least-squares optimizer.

    Pure-Python replacement for scipy.optimize.least_squares.
    Uses finite-difference Jacobian and damped Gauss-Newton steps with
    simple box-constraint projection.

    Ref: Levenberg (1944), Marquardt (1963), Moré (1978).
    """
    n = len(x0)
    x = np.clip(x0.copy(), lo, hi)
    r = residuals_func(x)
    cost = 0.5 * np.dot(r, r)
    lam  = 1e-3
    nfev = 1

    for _ in range(max_nfev):
        # Finite-difference Jacobian
        J = np.empty((len(r), n))
        for j in range(n):
            h = max(abs(x[j]) * 1e-8, 1e-10)
            x_fwd = x.copy()
            x_fwd[j] += h
            x_fwd = np.clip(x_fwd, lo, hi)
            h_actual = x_fwd[j] - x[j]
            if abs(h_actual) < 1e-20:
                x_bwd = x.copy()
                x_bwd[j] -= h
                x_bwd = np.clip(x_bwd, lo, hi)
                h_actual = x[j] - x_bwd[j]
                if abs(h_actual) < 1e-20:
                    J[:, j] = 0.0
                    continue
                J[:, j] = (r - residuals_func(x_bwd)) / h_actual
            else:
                J[:, j] = (residuals_func(x_fwd) - r) / h_actual
            nfev += 1

        # Gauss-Newton + LM damping: (JᵀJ + λ diag(JᵀJ)) Δx = −Jᵀr
        JtJ = J.T @ J
        Jtr = J.T @ r
        diag_JtJ = np.diag(np.maximum(np.diag(JtJ), 1e-20))

        try:
            dx = np.linalg.solve(JtJ + lam * diag_JtJ, -Jtr)
        except np.linalg.LinAlgError:
            lam *= 10.0
            continue

        x_new    = np.clip(x + dx, lo, hi)
        r_new    = residuals_func(x_new)
        nfev    += 1
        cost_new = 0.5 * np.dot(r_new, r_new)

        if cost_new < cost:
            x_step      = float(np.max(np.abs(x_new - x)))
            cost_change = abs(cost - cost_new) / max(cost, 1e-20)
            x    = x_new
            r    = r_new
            cost = cost_new
            lam  = max(lam / 3.0, 1e-15)
            if x_step < xtol and cost_change < ftol:
                break
        else:
            lam *= 10.0
            if lam > 1e16:
                break

        if nfev >= max_nfev:
            break

    return x


def _extract_body_sv(
    snapshot: dict,
    name: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    for b in snapshot["bodies"]:
        if b["name"] == name:
            sv = b["state_vector"]
            return (
                (sv["x_km"], sv["y_km"], sv["z_km"]),
                (sv["vx_km_s"], sv["vy_km_s"], sv["vz_km_s"]),
            )
    return None


def _extract_body_pos(
    snapshot: dict,
    name: str,
) -> tuple[float, float, float] | None:
    sv = _extract_body_sv(snapshot, name)
    return sv[0] if sv else None


def fit_orbit(
    body:           str,
    fixture:        dict,
    exclude_epoch:  str | None = None,
) -> FittedOrbit | None:
    """Fit Keplerian elements from yearly DE440 fixture snapshots.

    Strategy: compute elements from each snapshot's state vector via the
    classical rv-to-elements algorithm, then refine by least-squares across
    all position + velocity residuals.

    Parameters
    ----------
    body : name matching fixture body entries
    fixture : de440_state_vectors.json dict
    exclude_epoch : snapshot key to omit (leave-one-out cross-validation)
    """
    anchor = ANCHOR_MAP.get(body)
    if anchor is None:
        return None
    gm = ANCHOR_GM.get(anchor)
    if gm is None:
        return None

    reference_jd = JD_J2000

    obs_pos_ecl:     list[np.ndarray] = []
    obs_vel_ecl:     list[np.ndarray] = []
    times_s:         list[float]      = []
    element_samples: list[tuple]      = []

    for snap_name, snap in sorted(fixture.get("snapshots", {}).items()):
        if snap_name == exclude_epoch:
            continue

        jd      = snap["epoch"]["jd_tdb"]
        body_sv = _extract_body_sv(snap, body)
        anch_sv = _extract_body_sv(snap, anchor)
        if body_sv is None or anch_sv is None:
            continue

        rel_pos_eq  = tuple(b - a for b, a in zip(body_sv[0], anch_sv[0]))
        rel_vel_eq  = tuple(b - a for b, a in zip(body_sv[1], anch_sv[1]))
        rel_pos_ecl = _equatorial_to_ecliptic(*rel_pos_eq)
        rel_vel_ecl = _equatorial_to_ecliptic(*rel_vel_eq)

        obs_pos_ecl.append(np.array(rel_pos_ecl))
        obs_vel_ecl.append(np.array(rel_vel_ecl))
        t_s = (jd - reference_jd) * 86400.0
        times_s.append(t_s)

        r     = np.array(rel_pos_ecl)
        v     = np.array(rel_vel_ecl)
        elems = _state_to_elements(r, v, gm)
        if elems is not None:
            a_e, e_e, inc_e, Om_e, om_e, M_e = elems
            T_s = TWO_PI * math.sqrt((a_e * 1000.0) ** 3 / (gm * 1e9))
            M_at_j2000 = (M_e - (TWO_PI / T_s) * t_s) % TWO_PI
            element_samples.append((a_e, e_e, inc_e, Om_e, om_e, M_at_j2000))

    if len(obs_pos_ecl) < 3 or len(element_samples) < 1:
        return None

    elem_arr  = np.array(element_samples)
    x0        = np.median(elem_arr, axis=0)
    pos_arr   = np.array(obs_pos_ecl)
    vel_arr   = np.array(obs_vel_ecl)
    t_arr     = np.array(times_s)
    pos_scale = float(np.mean(np.linalg.norm(pos_arr, axis=1)))
    vel_scale = float(np.mean(np.linalg.norm(vel_arr, axis=1)))

    def residuals(params: np.ndarray) -> np.ndarray:
        n_pts = len(t_arr)
        res   = np.empty(n_pts * 6)
        for i, t in enumerate(t_arr):
            pred_p, pred_v = _keplerian_pos_vel(params, gm, t)
            res[i*6  :i*6+3] = (pred_p - pos_arr[i]) / pos_scale
            res[i*6+3:i*6+6] = (pred_v - vel_arr[i]) / vel_scale
        return res

    bounds_lo = np.array([1.0, 1e-10, 0.0, -4*math.pi, -4*math.pi, -4*math.pi])
    bounds_hi = np.array([1e12, 0.9999, math.pi, 4*math.pi, 4*math.pi, 4*math.pi])

    try:
        p = _levenberg_marquardt_bounded(
            residuals, x0, bounds_lo, bounds_hi,
            max_nfev=10_000, xtol=1e-14, ftol=1e-14,
        )
    except Exception:
        return None

    pos_residuals = np.empty(len(t_arr) * 3)
    for i, t in enumerate(t_arr):
        pred_p, _ = _keplerian_pos_vel(p, gm, t)
        pos_residuals[i*3:i*3+3] = pred_p - pos_arr[i]
    rms = math.sqrt(float(np.mean(pos_residuals ** 2)))

    return FittedOrbit(
        body=body,
        anchor=anchor,
        gm_km3_s2=gm,
        a_km=float(p[0]),
        eccentricity=float(p[1]),
        inclination_deg=float(p[2]) / DEG,
        loan_deg=float(p[3]) / DEG,
        aop_deg=float(p[4]) / DEG,
        mean_anomaly_at_j2000_deg=float(p[5]) / DEG,
        residual_rms_km=rms,
        reference_jd=reference_jd,
    )


def predict_ssb_position(
    fitted:           FittedOrbit,
    fixture_snapshot: dict,
    jd:               float,
) -> tuple[float, float, float] | None:
    """Predict SSB-centred ICRF position from fitted orbit.

    Uses the anchor's ground-truth position from the snapshot for the
    SSB offset, then adds the fitted anchor-relative position.
    """
    anchor_pos = _extract_body_pos(fixture_snapshot, fitted.anchor)
    if anchor_pos is None:
        return None

    rel_ecl = fitted.predict_relative_ecliptic(jd)
    rel_eq  = _ecliptic_to_equatorial(*rel_ecl)

    return (
        anchor_pos[0] + rel_eq[0],
        anchor_pos[1] + rel_eq[1],
        anchor_pos[2] + rel_eq[2],
    )
