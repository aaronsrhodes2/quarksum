"""
SPH smoothing kernel — cubic spline (Monaghan & Lattanzio 1985).

The SPH kernel W(r, h) replaces the Dirac delta in the continuum equations.
Any field quantity A at position x is approximated as:
  A(x) ≈ Σⱼ mⱼ/ρⱼ × Aⱼ × W(|x - xⱼ|, h)

Where the sum is over all neighbouring particles j within 2h.

Cubic spline kernel (Monaghan & Lattanzio 1985)
────────────────────────────────────────────────
W(q) = α_d × {
    2/3 - q² + q³/2      if 0 ≤ q < 1
    (1/6)(2 - q)³         if 1 ≤ q < 2
    0                     if q ≥ 2
}

where q = r/h and α_d is the normalisation constant:
  α_d = 1/h        in 1D
  α_d = 15/(7πh²)  in 2D
  α_d = 3/(2πh³)   in 3D  ← this module

FIRST_PRINCIPLES: the kernel must be (a) positive definite, (b) normalised
to 1 over all space, (c) compact-supported (radius 2h), (d) C¹ continuous.
These properties guarantee that SPH converges to the continuum Navier-Stokes
equations as N → ∞ and h → 0 with N h³ = const.

C¹ (not C²) is the minimum for stable pressure forces — second derivatives
of W appear in viscosity terms. For C² kernels see the Wendland kernels.
We use C¹ here for simplicity and comparability with Monaghan (1992).

Reference:
  Monaghan (1992) "Smoothed particle hydrodynamics"
  Ann. Rev. Astron. Astrophys. 30:543-574.
  Monaghan & Lattanzio (1985) Astron. Astrophys. 149:135-143.

Smoothing length h
──────────────────
  h = k × Δx   where Δx = (V_total / N)^(1/3) is the inter-particle spacing.

  k ≈ 1.2 gives ~57 neighbours in 3D (within 2h sphere), which is the
  standard resolution for stable free-surface SPH. See smoothing_length().

  NOT_PHYSICS: k is a numerical resolution parameter, not a physical one.

Length floor
────────────
  grad_W uses L_PLANCK = 1.616e-35 m from physics.constants as the zero
  guard for coincident particles. This is the physically motivated minimum
  length scale — see physics/constants.py for the full argument.
"""

import math

from ...constants import L_PLANCK


_NORM_3D = 3.0 / (2.0 * math.pi)   # α_d × h³ in 3D (dimensionless)


def W(r, h):
    """Cubic spline kernel value (3D).

    W(r, h) = α_d × f(r/h), where q = r/h and f is piecewise cubic.

    Properties:
      ∫ W dV = 1   (normalised — kernel integrates to unity)
      W ≥ 0        (positive definite — no negative density contributions)
      W = 0        for r ≥ 2h  (compact support)
      C¹ at q = 1  (gradient is continuous — required for force stability)

    Args:
        r (float): particle separation distance |xᵢ - xⱼ| in metres.
                   Must be ≥ 0. Negative values are reflected (kernel is even).
        h (float): smoothing length in metres. Must be > 0.

    Returns:
        float: kernel value in 1/m³. Exactly zero for r ≥ 2h.

    FIRST_PRINCIPLES: Monaghan & Lattanzio (1985) cubic spline.
    """
    q = r / h
    h3 = h * h * h
    norm = _NORM_3D / h3

    if q < 0.0:
        q = -q   # safety — kernel is even (W(−r) = W(r))

    if q < 1.0:
        return norm * (2.0/3.0 - q*q + 0.5 * q*q*q)
    elif q < 2.0:
        f = 2.0 - q
        return norm * (1.0/6.0) * f * f * f
    else:
        return 0.0


def grad_W(dx, dy, dz, h):
    """Gradient of cubic spline kernel (3D): ∇ᵢW(rᵢⱼ, h).

    Returns ∇ᵢW — the gradient with respect to particle i's position.
    Points FROM particle j TOWARD particle i (in the direction of (xᵢ − xⱼ)
    for q < 1 where dW/dq < 0, meaning the kernel pushes particles apart
    when they are too close).

    Used in the SPH pressure gradient term:
      a_pressure_i = −Σⱼ mⱼ (Pᵢ/ρᵢ² + Pⱼ/ρⱼ²) ∇ᵢWᵢⱼ

    and the pairwise cohesion force (water surface tension):
      a_cohesion_i = −Σⱼ mⱼ · a_ww · W(rᵢⱼ) · r̂ᵢⱼ
      (see simulate_water_glass.py — Tartakovsky & Meakin 2005 calibration)

    Derivation:
      ∇ᵢW = (dW/dr) × r̂ᵢⱼ = (dW/dq × 1/h) × (r_vec / r)
      dW/dq:
        q ∈ [0,1):   −2q + 1.5q²
        q ∈ [1,2):   −0.5(2−q)²
        q ≥ 2:        0

    Args:
        dx, dy, dz (float): components of (xᵢ − xⱼ) in metres.
        h (float): smoothing length in metres. Must be > 0.

    Returns:
        tuple (gx, gy, gz): gradient vector in 1/m⁴.
                            Returns (0, 0, 0) for:
                              - r < L_PLANCK (coincident particles)
                              - r ≥ 2h (outside support radius)

    Zero-guard:
        Returns (0, 0, 0) if r < L_PLANCK = 1.616e-35 m (the Planck length).
        An arbitrary epsilon such as 1e-12 would be less honest — L_PLANCK
        is the physical boundary below which spatial direction is undefined.
        If this guard fires in simulation, two SPH particles are at
        physically coincident positions: inspect the timestep and initial
        particle placement.

    FIRST_PRINCIPLES: analytic derivative of the Monaghan cubic spline.
    """
    r = math.sqrt(dx*dx + dy*dy + dz*dz)
    if r < L_PLANCK:
        # Direction is physically undefined below the Planck length.
        # This should never fire at SPH particle scales (h ~ 0.84 mm).
        return 0.0, 0.0, 0.0

    q  = r / h
    h4 = h * h * h * h
    norm = _NORM_3D / h4

    if q < 1.0:
        dW_dq = -2.0*q + 1.5 * q*q
    elif q < 2.0:
        f = 2.0 - q
        dW_dq = -0.5 * f * f
    else:
        return 0.0, 0.0, 0.0

    # ∇W = (dW/dq / h) × r̂ = norm × dW_dq × (r_vec / r)
    # (the 1/h factor is absorbed into norm through h4 = h³ × h)
    dW_dr = norm * dW_dq
    inv_r = 1.0 / r

    return dW_dr * dx * inv_r, dW_dr * dy * inv_r, dW_dr * dz * inv_r


def smoothing_length(volume_per_particle, k=1.2):
    """Compute SPH smoothing length h from particle volume.

    h = k × V_particle^(1/3) = k × Δx

    where Δx is the inter-particle spacing for a uniform 3D lattice packing.

    Neighbour count within 2h in 3D (sphere of radius 2h):
      N_nbr ≈ (4/3)π(2h)³ / V_particle = (4/3)π × 8k³ ≈ 33.5 k³

    k choices:
      k = 1.0 → N_nbr ≈ 34   minimal smoothing, noisy forces
      k = 1.2 → N_nbr ≈ 58   standard choice (DEFAULT)
      k = 1.5 → N_nbr ≈ 113  heavy smoothing, more diffusion, more stable
      k = 2.0 → N_nbr ≈ 268  suitable for free-surface without tension

    Args:
        volume_per_particle (float): V_total / N_particles, in m³.
        k (float): smoothing factor. Default 1.2.

    Returns:
        float: smoothing length h in metres.

    NOT_PHYSICS: k is a numerical resolution parameter. It governs the
    accuracy-vs-stability trade-off. The physics is correct for any k
    in the limit N → ∞. In practice: larger k → more stable, more diffusive.
    """
    return k * (volume_per_particle ** (1.0 / 3.0))
