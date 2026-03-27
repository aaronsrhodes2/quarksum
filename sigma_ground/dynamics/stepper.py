"""
Leapfrog integrator for rigid-body dynamics.

Integration scheme: Leapfrog (Störmer-Verlet)
==============================================
Leapfrog is symplectic — it conserves a modified energy (shadow Hamiltonian)
exactly at each step, unlike Euler which accumulates energy error.

Half-step velocity update → full-step position update → half-step velocity:
  v(t + dt/2) = v(t) + a(t) × dt/2
  x(t + dt)   = x(t) + v(t + dt/2) × dt
  a(t + dt)   = F(x(t+dt)) / m          [compute new forces at new position]
  v(t + dt)   = v(t + dt/2) + a(t+dt) × dt/2

For constant gravity (no position-dependent forces beyond collision), this
simplifies in the rigid-body case to standard leapfrog.

FIRST_PRINCIPLES: symplectic integration is required for any Hamiltonian
system. Euler integration violates the symplectic structure → energy drifts
unboundedly. Leapfrog is O(dt²) accurate and time-reversible. This matches
the physical system at the cost of requiring the half-step velocity.

Reference: Leimkuhler & Reich (2004) "Simulating Hamiltonian Dynamics"
           Cambridge University Press, §4.1.

CFL timestep constraint
=======================
  dt_max = 0.4 × r_min / v_max

Where r_min is the smallest object radius and v_max is the largest speed.
This ensures no object travels more than 40% of its own radius per step,
preventing tunneling through thin objects.

The 0.4 factor is the CFL coefficient. For rigid-body simulations with
inelastic collisions, 0.3–0.5 is standard. We use 0.4.
NOT_PHYSICS: the exact coefficient is a numerical parameter, not a physical one.

Reference: Courant, Friedrichs & Lewy (1928). The continuous version limits
wave propagation to sub-cell distances. We adapt it to bounding-sphere cells.

Collision ordering
==================
All O(n²) pairs are tested per step. For small scenes (< 50 objects) this is
acceptable. For large scenes, replace with a spatial hash (see fluid/sph.py).

Gravity
=======
  a_gravity = scene.gravity   (constant Vec3, typically Vec3(0, -g, 0))
  F = m × a_gravity
  v += a_gravity × dt

σ-dependence
============
  mass m(σ) already encoded in each parcel.mass via density_at_sigma(σ).
  The acceleration a = F/m = g is σ-INVARIANT for gravity (equivalence
  principle — all masses fall at the same rate regardless of σ).
  Only the momentum p = m(σ)v and kinetic energy ½m(σ)v² change with σ.
"""

import math
from .collision import resolve_sphere_sphere, resolve_sphere_plane


_CFL_COEFF = 0.40      # NOT_PHYSICS — numerical stability parameter


def _cfl_dt(scene, dt_max):
    """Compute CFL-limited timestep.

    dt = min(dt_max, CFL × r_min / max(v_max, eps))

    Returns dt in seconds.
    """
    r_min = float('inf')
    v_max = 0.0
    for p in scene.parcels:
        if not p.is_static:
            r_min = min(r_min, p.radius)
            v = p.velocity.length()
            v_max = max(v_max, v)

    if r_min == float('inf') or v_max < 1e-12:
        return dt_max

    dt_cfl = _CFL_COEFF * r_min / v_max
    return min(dt_max, dt_cfl)


def step(scene, dt=None, dt_max=0.01, sub_steps=4):
    """Advance the scene by one timestep.

    Uses leapfrog integration with CFL-limited substeps.

    Args:
        scene:     PhysicsScene to advance.
        dt:        Desired timestep in seconds. None → use CFL-computed dt.
        dt_max:    Maximum timestep per call (default 10 ms).
        sub_steps: Number of internal substeps per call.
                   Finer resolution improves collision accuracy.
                   Default: 4 (so each substep dt = dt/4).

    Returns:
        actual_dt (float): total elapsed time this call.

    Modifies:
        scene.parcels[*].position and .velocity in place.
        scene.time incremented.
    """
    if dt is None:
        dt = _cfl_dt(scene, dt_max)
    else:
        dt = min(dt, dt_max)

    sub_dt = dt / sub_steps

    for _ in range(sub_steps):
        _leapfrog_sub_step(scene, sub_dt)

    scene.time += dt
    return dt


def step_to(scene, t_end, dt_max=0.01, sub_steps=4, callback=None):
    """Advance the scene until scene.time >= t_end.

    Args:
        scene:    PhysicsScene.
        t_end:    Target simulation time (s).
        dt_max:   Maximum timestep per call.
        sub_steps: Substeps per call.
        callback: Optional function(scene, frame_index) called after each step.
                  Useful for recording frame data.

    Returns:
        history: list of (time, [(label, pos, vel), …]) per frame.
    """
    history = []
    frame   = 0
    while scene.time < t_end:
        remaining = t_end - scene.time
        dt = min(dt_max, remaining)
        step(scene, dt=dt, sub_steps=sub_steps)
        snapshot = _snapshot(scene)
        history.append((scene.time, snapshot))
        if callback:
            callback(scene, frame)
        frame += 1

    return history


def _leapfrog_sub_step(scene, dt):
    """Single leapfrog substep.

    1. Half-step velocity update (gravity only — no collision yet)
    2. Full-step position update
    3. Collision detection and impulse response
    4. Second half-step velocity (already done implicitly for constant gravity)

    For constant gravity the full leapfrog collapses to:
      v_half = v + a × dt/2
      x_new  = x + v_half × dt
      [resolve collisions at x_new — this modifies v_half]
      v_new  = v_half + a × dt/2

    This is the "velocity Verlet" form of leapfrog, which is algebraically
    equivalent to the position-Verlet form.
    """
    g = scene.gravity

    # ── Step 1: half-step velocity from gravity ──────────────────────────────
    for p in scene.parcels:
        if p.is_static:
            continue
        half_dv = g * (dt * 0.5)
        p.velocity = p.velocity + half_dv

    # ── Step 2: full-step position update ────────────────────────────────────
    for p in scene.parcels:
        if p.is_static:
            continue
        p.position = p.position + p.velocity * dt

    # ── Step 3: collision resolution ─────────────────────────────────────────
    parcels = scene.parcels

    # Sphere-sphere (O(n²), adequate for small scenes)
    n = len(parcels)
    for i in range(n):
        for j in range(i + 1, n):
            resolve_sphere_sphere(parcels[i], parcels[j])

    # Ground plane
    if scene.ground is not None:
        gnd = scene.ground
        for p in parcels:
            if not p.is_static:
                resolve_sphere_plane(p, gnd.point, gnd.normal,
                                     gnd.restitution)

    # ── Step 4: second half-step velocity ─────────────────────────────────────
    for p in scene.parcels:
        if p.is_static:
            continue
        half_dv = g * (dt * 0.5)
        p.velocity = p.velocity + half_dv


def _snapshot(scene):
    """Capture current (label, position, velocity) for each parcel."""
    return [(p.label, Vec3(p.position.x, p.position.y, p.position.z),
             Vec3(p.velocity.x, p.velocity.y, p.velocity.z))
            for p in scene.parcels]


# ── Import fix for _snapshot's Vec3 usage ────────────────────────────────────
from .vec import Vec3
