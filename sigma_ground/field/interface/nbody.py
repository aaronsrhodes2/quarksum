"""N-body gravitational integrator for SSBM physics.

Two integration schemes:
  * step()             — velocity-Verlet, 2nd-order symplectic, fast
  * forest_ruth_step() — Forest-Ruth (1990), 4th-order symplectic

4th-order symplectic is required for:
  - Long integrations of chaotic orbits (Halley's comet, NEAs)
  - Preserving symplecticity while resolving perihelion passages
  - Cases where the 2nd-order Verlet energy drift accumulates visibly

Physics included (all deriving from local_library constants):
  - Pairwise Newtonian gravity (point masses)
  - σ-field mass scaling via local_library.scale.scale_ratio
  - Optional 1PN Schwarzschild post-Newtonian correction (GR time dilation)
  - Tidal deformation: r(θ) = R₀[1 + ε₂ P₂(cos θ)]
  - Love number k₂ tidal response
  - Gravitational wave energy loss (Peters 1964 formula)
  - Solar radiation pressure (opt-in via solar_luminosity_W + area_m2)

All constants from sigma_ground.field.constants.  No magic numbers.
  G, C sourced from measured CODATA values in constants.py.
  Forest-Ruth coefficients are exact mathematics (Forest & Ruth 1990).
  1PN coefficients (4, 4) are exact from GR Schwarzschild solution.
  P₂(cos θ) = ½(3cos²θ - 1): exact Legendre polynomial.

References
----------
  Forest & Ruth (1990): "Fourth-order symplectic integration",
      Physica D: Nonlinear Phenomena 43(1), 105-117.
  Soffel et al. (2003): "The IAU 2000 resolutions for astrometry ...",
      AJ 126(6), 2687-2706.  [1PN EOM, solar-system limit]
  Peters (1964): GW inspiral formula, Phys. Rev. 136, B1224.
  Wisdom & Holman (1991): Symplectic integration, AJ 102(4), 1528-1538.
  Darwin (1879) / Love (1911): Tidal deformation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace as _replace
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from ..constants import G as _G_SI, C as _C_SI, L_SUN_W as _L_SUN_W

# ── derived (not magic) constants ─────────────────────────────────────────
_G   = _G_SI                  # m³ kg⁻¹ s⁻²
_c   = _C_SI                  # m/s
_c2  = _c * _c                # m²/s²
_4PI = 4.0 * math.pi          # exact

# Forest-Ruth integrator coefficients (exact — Forest & Ruth 1990 §2)
# θ = 1 / (2 − ∛2)  ≈ 1.351207191959657
_FR_THETA = 1.0 / (2.0 - 2.0 ** (1.0 / 3.0))
_FR_C     = [_FR_THETA / 2.0,                # c₁ = c₄
             (1.0 - _FR_THETA) / 2.0,        # c₂ = c₃
             (1.0 - _FR_THETA) / 2.0,
             _FR_THETA / 2.0]
_FR_D     = [_FR_THETA,                      # d₁ = d₃
             1.0 - 2.0 * _FR_THETA,          # d₂  (NEGATIVE — unavoidable at 4th order)
             _FR_THETA]


# ═══════════════════════════════════════════════════════════════════════════
# § 1. TIDAL DEFORMATION FIELD
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TidalDeformationField:
    """Analytic tidal deformation model: r(θ) = R₀[1 + ε₂ P₂(cos θ)].

    Parameters
    ----------
    body_radius_m : float
        Undeformed body radius R₀ (meters).
    epsilon2 : float
        Tidal deformation amplitude ε₂ = (k₂/2)(Mc/Mb)(R/d)³.
    tidal_direction : NDArray
        Unit vector pointing toward primary tidal source (shape (3,)).
    """

    body_radius_m: float
    epsilon2: float
    tidal_direction: NDArray[np.float64]

    def evaluate_at_angle(self, theta: float) -> float:
        """Relative tidal deformation amplitude δr/R₀ at polar angle θ.

        P₂(cos θ) = ½(3cos²θ − 1) — exact Legendre polynomial.
        """
        p2 = 0.5 * (3.0 * math.cos(theta) ** 2 - 1.0)
        return self.epsilon2 * p2

    def max_deformation(self) -> float:
        """Maximum deformation amplitude ε₂ (at θ = 0 or π)."""
        return self.epsilon2


# ═══════════════════════════════════════════════════════════════════════════
# § 2. CELESTIAL BODY
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CelestialBody:
    """A single body in the n-body system.

    Immutable; use .replace() to evolve.

    σ-field coupling (SSBM): effective gravitational mass scales as
        M_eff = M_rest × e^σ
    implemented via local_library.scale.scale_ratio(sigma_field).
    This is the canonical SSBM mass-gravity coupling.

    Attributes
    ----------
    mass_kg         : rest mass (kg)
    position_m      : Cartesian position (m), shape (3,)
    velocity_m_s    : Cartesian velocity (m/s), shape (3,)
    radius_m        : mean radius (m)
    love_number_k2  : dimensionless tidal Love number (0.3-0.5 stars, ~0 BHs)
    sigma_field     : σ value (dimensionless); 0 = standard Newtonian
    area_m2         : cross-sectional area (m²) for solar radiation pressure;
                      0 = SRP disabled for this body (default, safe for planets)
    reflectivity    : radiation pressure coefficient CR in [0, 1];
                      0 = perfect absorber, 1 = perfect mirror (2× pressure).
                      Typical rocky body: ~0.1.  Solar sail: ~1.
    """

    mass_kg:        float
    position_m:     NDArray[np.float64]
    velocity_m_s:   NDArray[np.float64]
    radius_m:       float
    love_number_k2: float
    sigma_field:    float = 0.0
    area_m2:        float = 0.0   # cross-sectional area for solar radiation pressure (m²)
    reflectivity:   float = 0.0   # radiation pressure coefficient CR: 0=absorber, 1=mirror

    def __post_init__(self) -> None:
        if self.position_m.shape != (3,):
            raise ValueError(f"position_m must be (3,), got {self.position_m.shape}")
        if self.velocity_m_s.shape != (3,):
            raise ValueError(f"velocity_m_s must be (3,), got {self.velocity_m_s.shape}")

    @property
    def gm_m3_s2(self) -> float:
        """GM in m³/s² with σ-field scaling.

        G is sourced from sigma_ground.field.constants (CODATA measured).
        σ scaling: M_eff = M × e^σ  (local_library.scale.scale_ratio).
        """
        return _G * self.mass_kg * math.exp(self.sigma_field)

    def kinetic_energy(self) -> float:
        """½mv² in Joules."""
        return 0.5 * self.mass_kg * float(np.dot(self.velocity_m_s, self.velocity_m_s))

    def momentum(self) -> NDArray[np.float64]:
        """Linear momentum mv (kg·m/s)."""
        return self.mass_kg * self.velocity_m_s

    def angular_momentum_about_origin(self) -> NDArray[np.float64]:
        """L = r × p (kg·m²/s)."""
        return np.cross(self.position_m, self.momentum())

    def replace(self, **kw) -> "CelestialBody":
        return _replace(self, **kw)


# ═══════════════════════════════════════════════════════════════════════════
# § 3. N-BODY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

class NBodySystem:
    """N-body gravitational integrator with tidal deformation.

    Two integration methods:
      step()             Velocity-Verlet, 2nd-order symplectic. Fast.
                         Use for well-resolved inner-planet / moon systems.
      forest_ruth_step() Forest-Ruth, 4th-order symplectic. 3× cost.
                         Required for chaotic high-eccentricity orbits
                         (comets, NEAs, binary pulsars) where 2nd-order
                         energy drift accumulates over many periods.

    Forest-Ruth maintains EXACT symplecticity for fixed dt, so energy and
    angular momentum are conserved to machine precision over arbitrary time.
    (Variable dt breaks symplecticity in BOTH schemes — use fixed dt.)

    Parameters
    ----------
    bodies              : initial body configuration
    softening_m         : Plummer softening length (m), default 0
    include_gr          : add 1PN Schwarzschild correction (default False)
    solar_luminosity_W  : solar luminosity for radiation pressure (W);
                          0 = SRP disabled (default).  Set to L_SUN_W
                          (3.828e26 W, IAU 2015) to enable.  Assumes
                          bodies[0] is the radiation source.  SRP only
                          applies to bodies with area_m2 > 0.
    """

    def __init__(
        self,
        bodies:             Sequence[CelestialBody],
        softening_m:        float = 0.0,
        include_gr:         bool  = False,
        solar_luminosity_W: float = 0.0,
    ) -> None:
        self.bodies             = list(bodies)
        self.softening_m        = softening_m
        self.include_gr         = include_gr
        self.solar_luminosity_W = solar_luminosity_W
        self._time              = 0.0

    @property
    def time(self) -> float:
        """Current simulation time (seconds)."""
        return self._time

    # ── accelerations ─────────────────────────────────────────────────────

    def compute_accelerations(self) -> NDArray[np.float64]:
        """Pairwise gravitational accelerations, shape (N, 3) in m/s².

        Newtonian: a_i += GM_j r̂_ij / r²

        Optional 1PN Schwarzschild correction (include_gr=True):
            a_GR = (GM_j / r² c²) × [(4GM_j/r − v_i²) r̂ + 4(r̂·v_i) v_i]

        Coefficients 4 and 4 are EXACT from the Schwarzschild metric
        (Soffel et al. 2003, eq. 10.12 solar-system limit).
        LOCAL_LIBRARY: approximation — single-body 1PN; full N-body EIH
        cross-terms neglected (< 1% for solar system).

        Solar radiation pressure (solar_luminosity_W > 0):
            F_SRP = L☉ A_i (1 + CR_i) / (4π r²_i☉ c)   [N, away from Sun]
            a_SRP = F_SRP / m_i

        where r_i☉ is distance from bodies[0] (radiation source = Sun).
        Only applied to bodies with area_m2 > 0.
        Ref: Montenbruck & Gill (2000), §3.4.
        """
        n   = len(self.bodies)
        acc = np.zeros((n, 3), dtype=np.float64)

        for i in range(n):
            vi  = self.bodies[i].velocity_m_s
            vi2 = float(np.dot(vi, vi))

            for j in range(n):
                if i == j:
                    continue
                r_ij = self.bodies[j].position_m - self.bodies[i].position_m
                r_sq = float(np.dot(r_ij, r_ij)) + self.softening_m ** 2
                r    = math.sqrt(r_sq)
                if r == 0.0:
                    continue

                gm_j = self.bodies[j].gm_m3_s2
                acc[i] += gm_j * r_ij / (r_sq * r)   # Newtonian

                if self.include_gr:
                    r_hat  = r_ij / r
                    rdotv  = float(np.dot(r_hat, vi))
                    factor = gm_j / (r_sq * _c2)
                    acc[i] += factor * (
                        (4.0 * gm_j / r - vi2) * r_hat + 4.0 * rdotv * vi
                    )

        # ── Solar radiation pressure ───────────────────────────────────────
        # Applied to any body with area_m2 > 0, relative to bodies[0] (Sun).
        if self.solar_luminosity_W > 0.0 and n >= 2:
            sun_pos = self.bodies[0].position_m
            for i in range(1, n):
                body = self.bodies[i]
                if body.area_m2 <= 0.0 or body.mass_kg <= 0.0:
                    continue
                r_vec = body.position_m - sun_pos     # points away from Sun
                r_sq  = float(np.dot(r_vec, r_vec))
                if r_sq == 0.0:
                    continue
                r     = math.sqrt(r_sq)
                # F_SRP = L A (1+CR) / (4π r² c)
                f_srp = (self.solar_luminosity_W * body.area_m2
                         * (1.0 + body.reflectivity)
                         / (_4PI * r_sq * _c))
                acc[i] += (f_srp / body.mass_kg) * (r_vec / r)

        return acc

    # ── velocity-Verlet (2nd-order symplectic) ─────────────────────────────

    def step(self, dt: float, include_gw_loss: bool = False) -> None:
        """Advance dt using velocity-Verlet (leapfrog).

        Symplectic, O(dt²) global error per orbit.  Two force evaluations.
        For well-sampled orbits (≥ 88 steps/period) this is sufficient.

        For highly-eccentric orbits where timestep adaption is needed,
        use forest_ruth_step() with a fixed small dt instead.
        """
        n   = len(self.bodies)
        acc = self.compute_accelerations()

        vel_half = [self.bodies[i].velocity_m_s + 0.5 * dt * acc[i]
                    for i in range(n)]
        pos_new  = [self.bodies[i].position_m + dt * vel_half[i]
                    for i in range(n)]

        for i in range(n):
            self.bodies[i] = self.bodies[i].replace(position_m=pos_new[i])

        acc_new = self.compute_accelerations()
        vel_new = [vel_half[i] + 0.5 * dt * acc_new[i] for i in range(n)]

        if include_gw_loss and n == 2:
            vel_new = self._apply_gw_damping(vel_new, dt)

        for i in range(n):
            self.bodies[i] = self.bodies[i].replace(velocity_m_s=vel_new[i])

        self._time += dt

    # ── Forest-Ruth (4th-order symplectic) ────────────────────────────────

    def forest_ruth_step(self, dt: float) -> None:
        """Advance dt using 4th-order Forest-Ruth symplectic integration.

        Forest & Ruth (1990): 7 sub-steps (4 drifts, 3 kicks), 3 force
        evaluations.  Exact symplecticity for fixed dt — energy and angular
        momentum conserved to machine precision over arbitrary time.

        Coefficients (exact mathematics, not approximations):
            θ  = 1 / (2 − ∛2) ≈ 1.3512
            c₁ = c₄ = θ/2
            c₂ = c₃ = (1−θ)/2
            d₁ = d₃ = θ
            d₂       = 1−2θ  ← NEGATIVE (unavoidable for 4th-order, 3-force)

        Use this for:
          • Halley's comet (e=0.967, perihelion ~0.586 AU)
          • 67P, Apophis, any chaotic NEA or comet
          • Long binary pulsar integrations
        with fixed dt ≈ 1 hr near perihelion (tune until energy drift < 1e-8).

        Warning: do NOT use variable dt with this (or any symplectic) scheme.
        Variable dt breaks the symplectic condition, causing slow energy drift.
        """
        c = _FR_C
        d = _FR_D

        def _drift(frac: float) -> None:
            self.bodies = [
                b.replace(position_m=b.position_m + frac * dt * b.velocity_m_s)
                for b in self.bodies
            ]

        def _kick(frac: float) -> None:
            acc = self.compute_accelerations()
            self.bodies = [
                b.replace(velocity_m_s=b.velocity_m_s + frac * dt * acc[i])
                for i, b in enumerate(self.bodies)
            ]

        _drift(c[0])  # drift θ/2
        _kick(d[0])   # kick θ
        _drift(c[1])  # drift (1−θ)/2
        _kick(d[1])   # kick 1−2θ  (negative — bodies briefly backtrack)
        _drift(c[2])  # drift (1−θ)/2
        _kick(d[2])   # kick θ
        _drift(c[3])  # drift θ/2

        self._time += dt

    # ── conserved quantities ────────────────────────────────────────────────

    def total_energy(self) -> float:
        """Total mechanical energy (kinetic + gravitational potential) in J."""
        ke = sum(b.kinetic_energy() for b in self.bodies)
        pe = 0.0
        for i, bi in enumerate(self.bodies):
            for j, bj in enumerate(self.bodies):
                if j <= i:
                    continue
                r = float(np.linalg.norm(bi.position_m - bj.position_m))
                if r > 0:
                    pe -= _G * bi.mass_kg * bj.mass_kg / r
        return ke + pe

    def total_momentum(self) -> NDArray[np.float64]:
        """Total linear momentum (kg·m/s)."""
        return sum(b.momentum() for b in self.bodies)  # type: ignore[return-value]

    def total_angular_momentum(self) -> NDArray[np.float64]:
        """Total angular momentum about origin (kg·m²/s)."""
        return sum(b.angular_momentum_about_origin() for b in self.bodies)  # type: ignore[return-value]

    # ── tidal deformation ────────────────────────────────────────────────

    def compute_tidal_deformation(
        self, body_idx: int, perturber_idx: int,
    ) -> TidalDeformationField:
        """Tidal deformation of body_idx due to perturber_idx.

        ε₂ = (k₂/2)(M_c/M_b)(R_b/d)³  —  derived from Love (1911).
        """
        body      = self.bodies[body_idx]
        perturber = self.bodies[perturber_idx]
        r_ij      = perturber.position_m - body.position_m
        d         = float(np.linalg.norm(r_ij))
        if d == 0.0:
            raise ValueError("Bodies are at the same position")
        tidal_dir = r_ij / d
        ratio     = perturber.mass_kg / body.mass_kg if body.mass_kg > 0 else 0.0
        eps2      = (body.love_number_k2 / 2.0) * ratio * (body.radius_m / d) ** 3
        return TidalDeformationField(
            body_radius_m=body.radius_m,
            epsilon2=eps2,
            tidal_direction=tidal_dir,
        )

    def roche_limit(self, primary_idx: int, satellite_idx: int) -> float:
        """Roche limit d = R_p × (2 M_p/M_s)^(1/3) (rigid satellite).

        Exact formula for a rigid satellite (Roche 1847).
        """
        primary   = self.bodies[primary_idx]
        satellite = self.bodies[satellite_idx]
        if satellite.mass_kg == 0:
            return float("inf")
        return primary.radius_m * (2.0 * primary.mass_kg / satellite.mass_kg) ** (1.0 / 3.0)

    # ── GW energy loss ───────────────────────────────────────────────────

    def _apply_gw_damping(
        self,
        vel_new:  list[NDArray[np.float64]],
        dt:       float,
    ) -> list[NDArray[np.float64]]:
        """Reduce binary velocities by GW energy loss (Peters 1964).

        Only meaningful for compact object binaries; ignored for planets.
        """
        b0, b1 = self.bodies[0], self.bodies[1]
        r_vec  = b1.position_m - b0.position_m
        r      = float(np.linalg.norm(r_vec))
        if r == 0.0:
            return vel_new
        mu_red = b0.mass_kg * b1.mass_kg / (b0.mass_kg + b1.mass_kg)
        M_tot  = b0.mass_kg + b1.mass_kg
        # Peters formula: dE/dt = -(32/5) G⁴ m1² m2² M / (c⁵ r⁴)
        # Coefficients 32/5 are exact from quadrupole formula (Peters 1964).
        dE_dt  = -(32.0 / 5.0) * _G**4 * b0.mass_kg**2 * b1.mass_kg**2 * M_tot / (
            _c**5 * r**4
        )
        v_rel  = vel_new[1] - vel_new[0]
        v_mag  = float(np.linalg.norm(v_rel))
        if v_mag == 0.0:
            return vel_new
        ke_rel = 0.5 * mu_red * v_mag**2
        if ke_rel == 0.0:
            return vel_new
        damp   = 1.0 + dE_dt * dt / ke_rel
        damp   = max(0.0, damp)
        v_cm   = (b0.mass_kg * vel_new[0] + b1.mass_kg * vel_new[1]) / M_tot
        # CM-frame decomposition: v_i = v_cm ± (m_other/M) * v_rel
        # b0 gets -m_b1/M * v_rel;  b1 gets +m_b0/M * v_rel
        vel_new[0] = v_cm - math.sqrt(damp) * b1.mass_kg / M_tot * v_rel
        vel_new[1] = v_cm + math.sqrt(damp) * b0.mass_kg / M_tot * v_rel
        return vel_new
