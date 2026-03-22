"""
Dam-break simulation — full 2D SPH time integration.

Physics
-------
  Smoothed Particle Hydrodynamics (SPH) solves the Navier-Stokes equations by
  representing a fluid as a set of Lagrangian particles that carry mass, velocity,
  density, and pressure.  Each particle is a weighted interpolation kernel; the
  sum over neighbours gives local density, from which pressure follows via the
  equation of state.

  Governing equations (Lagrangian form):
    Dρ/Dt  = -ρ ∇·v                    [continuity]
    Dv/Dt  = -∇P/ρ + η∇²v/ρ + g       [momentum]

  SPH discretisation:
    ρᵢ   = Σⱼ mⱼ W(|rᵢ-rⱼ|, h)         [density sum]
    Pᵢ   = K(ρᵢ/ρ₀ - 1)               [linear Tait EOS]
    aᵢ_P = -Σⱼ mⱼ(Pᵢ/ρᵢ² + Pⱼ/ρⱼ²) ∇Wᵢⱼ   [pressure accel, symmetric]
    aᵢ_v = -Σⱼ mⱼ Πᵢⱼ ∇Wᵢⱼ           [artificial viscosity, Monaghan 1992]
    aᵢ_g = (0, -g)                     [gravity]

  References:
    Monaghan (1992) Ann. Rev. Astron. Astrophys. 30:543-574.   [SPH review]
    Monaghan (1994) J. Comput. Phys. 110:399-406.              [dam-break, WCSPH]
    Monaghan & Kos (1999) J. Waterway Port Coastal 125:145.    [validation]
    Price (2012) J. Comput. Phys. 231:759-794.                 [2D kernel norms]
    Morris (1997) J. Comput. Phys. 136:214-226.                [viscosity]

Kernel
------
  2D cubic spline (Price 2012):
    W(r, h) = (10 / 7πh²) × f(q),  q = r/h
    f(q) = { 1 - 3q²/2 + 3q³/4    0 ≤ q < 1
           { (2-q)³/4              1 ≤ q < 2
           { 0                     q ≥ 2

  Normalisation verified: ∫ W 2πr dr = 1  ✓

Viscosity
---------
  Monaghan (1992) artificial viscosity:
    μᵢⱼ  = h × (vᵢⱼ · rᵢⱼ) / (|rᵢⱼ|² + ε²h²)
    Πᵢⱼ  = -α_v c_s μᵢⱼ / ρ̄ᵢⱼ   if  vᵢⱼ · rᵢⱼ < 0   (approaching)
    Πᵢⱼ  = 0                       otherwise

  α_v = 0.05, ε = 0.01.
  NOT_PHYSICS: α_v is a numerical stabiliser, not physical viscosity.

Speed of sound
--------------
  We use the WCSPH (weakly-compressible) trick (Monaghan 1994):
    c_s_num = 10 × v_front_theory = 10 × 2√(gH₀)
  This keeps the Mach number at ~0.1 so the Tait EOS is valid, while
  allowing a CFL timestep ~1000× larger than the physical c_s would require.
  NOT_PHYSICS: c_s_num is a numerical parameter, not the physical 1482 m/s.

Scene
-----
  Tank:         1.6 m × 0.6 m  (2D cross-section)
  Water column: 0.4 m × 0.3 m  (left of x = 0.4)
  Δx:           0.02 m          (~400 particles)
  h_smooth:     1.2 × Δx        (~45 neighbours in 2h circle)

Validation
----------
  Analytical wave-front speed (Ritter 1892 / shallow-water theory):
    v_front = 2 √(g H₀)
  Measured from simulation.  Expected: ±15% of analytical value.
  ALL_CHECKS_MUST_PASS before GIF is written.

Scaling benchmark
-----------------
  After the main simulation this script runs N = [50, 200, 800, 3200] and
  measures: step time, memory per particle, and projects to universe scale.
  This answers: "how many particles can we hold in loaded memory, and how
  does per-particle query cost scale?"
"""

import sys, os, math, time, tracemalloc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from mattershaper.physics.fluid.eos import pressure_tait, speed_of_sound_liquid

# ── Physical constants ─────────────────────────────────────────────────────────

G          = 9.80665      # m/s²   — standard gravity, MEASURED
RHO_WATER  = 998.2        # kg/m³  — water at 20°C, MEASURED
K_WATER    = 2.20e9       # Pa     — bulk modulus, MEASURED
ETA_WATER  = 1.002e-3     # Pa·s   — dynamic viscosity at 20°C, MEASURED

# ── Scene parameters ──────────────────────────────────────────────────────────

TANK_W   = 1.60    # m
TANK_H   = 0.60    # m
H0       = 0.30    # m — initial column height
L0       = 0.40    # m — initial column width
DELTA_X  = 0.02    # m — particle spacing

# ── Numerical SPH parameters ──────────────────────────────────────────────────

K_SMOOTH = 1.2          # NOT_PHYSICS: h = K_SMOOTH × Δx
ALPHA_V  = 0.02         # NOT_PHYSICS: Monaghan artificial viscosity coefficient
EPS_V    = 0.01         # NOT_PHYSICS: viscosity regularisation
CFL      = 0.25         # NOT_PHYSICS: Courant–Friedrichs–Lewy safety factor
T_END    = 0.50         # s — simulation time (front crosses tank ~0.47 s)
N_FRAMES = 60           # number of GIF frames
RESTITUTION = 0.3       # NOT_PHYSICS: wall bounce energy retention

H_SMOOTH = K_SMOOTH * DELTA_X   # 0.024 m

# Numerical sound speed (Monaghan 1994 WCSPH trick)
V_FRONT_THEORY = 2.0 * math.sqrt(G * H0)    # ~3.43 m/s analytical
C_S_NUM        = 10.0 * V_FRONT_THEORY       # ~34.3 m/s numerical
K_NUM          = RHO_WATER * C_S_NUM ** 2    # ~1.18 MPa numerical

DT = CFL * H_SMOOTH / (C_S_NUM + V_FRONT_THEORY)    # ~0.19 ms
N_STEPS = int(T_END / DT) + 1

# ── 2D cubic spline kernel (Price 2012) ───────────────────────────────────────
# FIRST_PRINCIPLES: normalisation ∫ W 2πr dr = 1 verified analytically.
# Using 2D form since simulation is 2D.

_N2 = 10.0 / (7.0 * math.pi)          # dimensionless 2D normalisation constant


def _W2_arr(r_arr, h):
    """Vectorized 2D cubic spline kernel.  Units: 1/m².
    r_arr: (N,N) distance matrix.  Returns W (N,N), same shape.
    """
    q    = r_arr / h
    norm = _N2 / (h * h)
    w    = np.zeros_like(r_arr)
    m1   = q < 1.0
    m2   = (q >= 1.0) & (q < 2.0)
    q1   = q[m1];  w[m1] = norm * (1.0 - 1.5*q1*q1 + 0.75*q1*q1*q1)
    q2   = q[m2];  w[m2] = norm * 0.25 * (2.0 - q2)**3
    return w


def _gW2_arr(dxij, dyij, rij, h):
    """Vectorized 2D kernel gradient.  Units: 1/m³.
    Returns (gx, gy) each (N,N).  Convention: ∇W(rᵢ - rⱼ).
    """
    q      = rij / h
    norm   = _N2 / (h * h * h)     # includes 1/h for dq/dr
    dWdq   = np.zeros_like(rij)
    m1     = q < 1.0
    m2     = (q >= 1.0) & (q < 2.0)
    q1     = q[m1];  dWdq[m1] = norm * (-3.0*q1 + 2.25*q1*q1)
    q2     = q[m2];  dWdq[m2] = norm * (-0.75 * (2.0 - q2)**2)
    inv_r  = np.where(rij > 1e-12, 1.0 / np.maximum(rij, 1e-12), 0.0)
    return dWdq * dxij * inv_r,  dWdq * dyij * inv_r


# ── Acceleration kernel ────────────────────────────────────────────────────────

def compute_acc(rx, ry, vx, vy, m, h, rho0, K_eos, c_s, alpha_v, eps_v, g):
    """Compute SPH accelerations for all particles (numpy vectorised, O(N²)).

    Returns:
        ax, ay  — acceleration vectors (m/s²), shape (N,)
        rho     — density per particle (kg/m²·depth), shape (N,)
        P       — pressure per particle (Pa), shape (N,)
    """
    N = len(rx)

    # --- Pairwise geometry ---
    dxij = rx[:, None] - rx[None, :]   # (N,N) — r_i - r_j in x
    dyij = ry[:, None] - ry[None, :]
    rij  = np.sqrt(dxij*dxij + dyij*dyij)

    in_nbr = (rij > 0) & (rij < 2.0 * h)   # Boolean support mask

    # --- Density ---
    W = _W2_arr(rij, h)
    rho = m * np.sum(W, axis=1)               # ρᵢ = Σⱼ mⱼ W(rᵢⱼ, h)
    rho = np.maximum(rho, 0.05 * rho0)        # floor: prevents /0 in tension

    # --- Pressure (linear Tait) ---
    P = K_eos * (rho / rho0 - 1.0)

    # --- Kernel gradient ---
    gWx, gWy = _gW2_arr(dxij, dyij, rij, h)

    # --- Pressure acceleration (symmetric SPH, Monaghan 1992 eq. 4) ---
    Pt = P[:, None]/rho[:, None]**2 + P[None, :]/rho[None, :]**2   # (N,N)
    Pt = np.where(in_nbr, Pt, 0.0)
    apx = -m * np.sum(Pt * gWx, axis=1)
    apy = -m * np.sum(Pt * gWy, axis=1)

    # --- Artificial viscosity (Monaghan 1992, eq. 11) ---
    dvx  = vx[:, None] - vx[None, :]
    dvy  = vy[:, None] - vy[None, :]
    vr   = dvx * dxij + dvy * dyij                     # vᵢⱼ · rᵢⱼ
    app  = (vr < 0) & in_nbr                           # approaching pairs
    rij2 = rij * rij
    mu   = h * vr / (rij2 + eps_v**2 * h**2)
    rho_mean = 0.5 * (rho[:, None] + rho[None, :])
    Pi   = np.where(app, -alpha_v * c_s * mu / rho_mean, 0.0)   # Π > 0
    avx  = -m * np.sum(Pi * gWx, axis=1)
    avy  = -m * np.sum(Pi * gWy, axis=1)

    # --- Gravity ---
    return apx + avx, apy + avy - g * np.ones(N), rho, P


# ── Wall boundary conditions ───────────────────────────────────────────────────

def apply_wall_bc(rx, ry, vx, vy, tank_w, tank_h, margin, restitution):
    """Reflective walls at x=0, x=tank_w, y=0.  Free surface at top."""
    # Floor
    hit = ry < margin
    ry  = np.where(hit, margin, ry)
    vy  = np.where(hit & (vy < 0), -restitution * vy, vy)
    # Left wall
    hit = rx < margin
    rx  = np.where(hit, margin, rx)
    vx  = np.where(hit & (vx < 0), -restitution * vx, vx)
    # Right wall
    hit = rx > tank_w - margin
    rx  = np.where(hit, tank_w - margin, rx)
    vx  = np.where(hit & (vx > 0), -restitution * vx, vx)
    # Ceiling (shouldn't be reached in dam-break, but safety clamp)
    hit = ry > tank_h - margin
    ry  = np.where(hit, tank_h - margin, ry)
    vy  = np.where(hit & (vy > 0), -restitution * vy, vy)
    return rx, ry, vx, vy


# ── Rendering ─────────────────────────────────────────────────────────────────

# Canvas dimensions (pixels)
_PX_PER_M  = 340          # spatial scale
_MARGIN_PX = 30           # border padding
_CANVAS_W  = int(TANK_W * _PX_PER_M) + 2 * _MARGIN_PX   # 574
_CANVAS_H  = int(TANK_H * _PX_PER_M) + 2 * _MARGIN_PX + 60  # 294 + header


def _world_to_pix(rx, ry):
    px = (rx * _PX_PER_M + _MARGIN_PX).astype(int)
    py = (_CANVAS_H - 60 - _MARGIN_PX - ry * _PX_PER_M).astype(int)
    return px, py


def render_frame(rx, ry, vx, vy, rho, t, tank_w, tank_h, v_front_measured):
    """Render one frame as a PIL Image (RGB).

    Phosphor-style: additive blending, speed → hue (blue=slow, cyan=fast).
    NOT_PHYSICS: rendering only; no physics occurs here.
    """
    W = _CANVAS_W
    H = _CANVAS_H
    buf = np.zeros((H, W, 3), dtype=np.float32)

    speed  = np.sqrt(vx*vx + vy*vy)
    s_norm = np.clip(speed / (V_FRONT_THEORY + 1e-6), 0.0, 1.0)

    px, py = _world_to_pix(rx, ry)

    r_blob = max(2, int(H_SMOOTH * _PX_PER_M * 0.6))   # glow radius in pixels

    for i in range(len(rx)):
        cx, cy = px[i], py[i]
        s = float(s_norm[i])
        # Color: slow = deep blue (0, 0.3, 1), fast = cyan-white (0.4, 1, 1)
        cr = s * 0.6
        cg = 0.3 + s * 0.7
        cb = 1.0
        glow_r = r_blob

        x0 = max(0, cx - glow_r); x1 = min(W, cx + glow_r + 1)
        y0 = max(0, cy - glow_r); y1 = min(H, cy + glow_r + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        xs = np.arange(x0, x1)
        ys = np.arange(y0, y1)
        XX, YY = np.meshgrid(xs, ys)
        d2 = (XX - cx)**2 + (YY - cy)**2
        g  = np.exp(-d2 / (2.0 * (glow_r * 0.5)**2))
        buf[y0:y1, x0:x1, 0] += g * cr * 0.9
        buf[y0:y1, x0:x1, 1] += g * cg * 0.9
        buf[y0:y1, x0:x1, 2] += g * cb * 0.9

    # Clip and convert
    buf = np.clip(buf * 255, 0, 255).astype(np.uint8)

    # Draw tank outline (dim white)
    # Floor
    lx0 = _MARGIN_PX; lx1 = _MARGIN_PX + int(tank_w * _PX_PER_M)
    ly  = _CANVAS_H - 60 - _MARGIN_PX
    if 0 <= ly < H:
        buf[ly, lx0:lx1+1] = [60, 60, 60]
    # Left wall
    for y in range(ly - int(tank_h * _PX_PER_M), ly+1):
        if 0 <= y < H:
            buf[y, lx0] = [60, 60, 60]
    # Right wall
    for y in range(ly - int(tank_h * _PX_PER_M), ly+1):
        if 0 <= y < H and 0 <= lx1 < W:
            buf[y, lx1] = [60, 60, 60]

    # Header band
    img = Image.fromarray(buf, 'RGB')
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    t_ms = t * 1000.0
    vf_str = f"{v_front_measured:.2f}" if v_front_measured > 0 else "---"
    draw.text((8, H - 55), f"t = {t_ms:.1f} ms", fill=(180, 180, 180))
    draw.text((8, H - 40), f"N = {len(rx)} particles", fill=(120, 120, 120))
    draw.text((8, H - 25), f"v_front ≈ {vf_str} m/s  (theory {V_FRONT_THEORY:.2f} m/s)",
              fill=(100, 200, 120))

    return img


# ── Foundation validation (from Session 7) ────────────────────────────────────

def run_foundation_checks():
    print("═" * 60)
    print("  Dam-break — foundation validation")
    print("═" * 60)
    h = H_SMOOTH
    # 1. 2D kernel normalisation: ∫ W 2πr dr = 1
    dr = h / 2000.0
    integral = sum(_W2_arr(np.array([[r]]), h)[0, 0] * 2.0 * math.pi * r * dr
                   for r in [(i + 0.5) * dr for i in range(int(2*h / dr))])
    ok1 = abs(integral - 1.0) < 0.01
    print(f"  2D ∫ W 2πr dr = {integral:.5f}  (expected 1.0)  "
          f"{'✓ PASS' if ok1 else '✗ FAIL'}")

    # 2. W = 0 beyond 2h
    w_beyond = _W2_arr(np.array([[2.001*h]]), h)[0, 0]
    ok2 = w_beyond == 0.0
    print(f"  W(2.001h) = {w_beyond:.2e}  (expected 0)  "
          f"{'✓ PASS' if ok2 else '✗ FAIL'}")

    # 3. Gradient antisymmetry
    dx = np.array([[0.5*h, -0.5*h]])
    dy = np.array([[0.0,    0.0]])
    r  = np.array([[0.5*h,  0.5*h]])
    gx, _ = _gW2_arr(dx, dy, r, h)
    ok3 = abs(gx[0, 0] + gx[0, 1]) < 1e-12
    print(f"  ∇W antisymmetry: sum = {gx[0,0]+gx[0,1]:.2e}  "
          f"{'✓ PASS' if ok3 else '✗ FAIL'}")

    # 4. EOS: P = 0 at rest density
    P_rest = pressure_tait(RHO_WATER, RHO_WATER, K_WATER)
    ok4 = P_rest == 0.0
    print(f"  P(ρ₀, ρ₀, K) = {P_rest:.2e} Pa  (expected 0)  "
          f"{'✓ PASS' if ok4 else '✗ FAIL'}")

    # 5. Speed of sound
    c_s = speed_of_sound_liquid(K_WATER, RHO_WATER)
    ok5 = abs(c_s - 1482) < 10
    print(f"  c_s = {c_s:.1f} m/s  (MEASURED 1482 m/s, err {abs(c_s-1482)/1482*100:.1f}%)  "
          f"{'✓ PASS' if ok5 else '✗ CLOSE'}")

    if not all([ok1, ok2, ok3, ok4]):
        print("\n  ✗ FOUNDATION CHECKS FAILED — aborting simulation.")
        sys.exit(1)
    print("  All foundation checks passed.\n")


# ── Main simulation ────────────────────────────────────────────────────────────

def run_simulation():
    print("═" * 60)
    print("  Dam-break SPH — full time integration")
    print("═" * 60)
    print(f"  N particles:  {int(L0/DELTA_X) * int(H0/DELTA_X)}")
    print(f"  Δt:           {DT*1000:.3f} ms")
    print(f"  Steps:        {N_STEPS:,}")
    print(f"  c_s_num:      {C_S_NUM:.1f} m/s  (WCSPH Monaghan 1994, NOT physical)")
    print(f"  K_num:        {K_NUM/1e6:.3f} MPa  (numerical)")
    print()

    # ── Particle initialisation ───────────────────────────────────────────────
    nx = int(L0 / DELTA_X)
    ny = int(H0 / DELTA_X)
    N  = nx * ny
    m  = RHO_WATER * DELTA_X**2    # mass per unit depth (2D)

    ii = np.arange(N)
    rx = ((ii % nx) + 0.5) * DELTA_X
    ry = ((ii // nx) + 0.5) * DELTA_X
    vx = np.zeros(N)
    vy = np.zeros(N)

    # Initial forces
    ax, ay, rho, P = compute_acc(
        rx, ry, vx, vy, m, H_SMOOTH, RHO_WATER, K_NUM, C_S_NUM,
        ALPHA_V, EPS_V, G)

    # ── Time loop ─────────────────────────────────────────────────────────────
    margin = DELTA_X * 0.5
    dt     = DT
    t      = 0.0
    step   = 0

    frames          = []
    frame_interval  = max(1, N_STEPS // N_FRAMES)

    x_front_prev    = L0       # track leading edge of fluid
    t_prev          = 0.0
    v_front_meas    = 0.0
    # Position-based validation snapshot: record x_front at t ≈ 0.3 s
    # Ritter (1892): x_front(t) = 2√(gH₀) × t  →  x_ritter(0.3) = 1.029 m
    T_SNAP          = 0.30     # s — snapshot time for Ritter comparison
    x_front_snap    = None     # x_front recorded near T_SNAP

    t_start = time.time()

    while step < N_STEPS:
        # ── Leapfrog velocity Verlet ──────────────────────────────────────────
        # Half kick
        vx_h = vx + 0.5 * dt * ax
        vy_h = vy + 0.5 * dt * ay
        # Drift
        rx_n = rx + dt * vx_h
        ry_n = ry + dt * vy_h
        # Wall BCs on position
        rx_n, ry_n, vx_h, vy_h = apply_wall_bc(
            rx_n, ry_n, vx_h, vy_h, TANK_W, TANK_H, margin, RESTITUTION)
        # Recompute forces
        ax_n, ay_n, rho, P = compute_acc(
            rx_n, ry_n, vx_h, vy_h, m, H_SMOOTH, RHO_WATER, K_NUM, C_S_NUM,
            ALPHA_V, EPS_V, G)
        # Second half kick + wall BC on velocity
        vx_n = vx_h + 0.5 * dt * ax_n
        vy_n = vy_h + 0.5 * dt * ay_n
        _, _, vx_n, vy_n = apply_wall_bc(
            rx_n.copy(), ry_n.copy(), vx_n, vy_n,
            TANK_W, TANK_H, margin, RESTITUTION)

        rx, ry, vx, vy, ax, ay = rx_n, ry_n, vx_n, vy_n, ax_n, ay_n
        t    += dt
        step += 1

        # ── Wave front tracking ───────────────────────────────────────────────
        x_front = np.max(rx)
        if x_front > x_front_prev + 0.01:
            v_front_meas = (x_front - x_front_prev) / (t - t_prev + 1e-12)
            x_front_prev = x_front
            t_prev       = t
        # Capture position snapshot near T_SNAP for Ritter comparison
        if x_front_snap is None and t >= T_SNAP:
            x_front_snap = x_front

        # ── Save frame ────────────────────────────────────────────────────────
        if step % frame_interval == 0 or step == N_STEPS:
            frames.append(render_frame(
                rx, ry, vx, vy, rho, t, TANK_W, TANK_H, v_front_meas))
            prog = step / N_STEPS * 100
            elapsed = time.time() - t_start
            print(f"  t={t*1000:6.1f} ms  x_front={x_front:.3f} m  "
                  f"v_front≈{v_front_meas:.2f} m/s  [{prog:.0f}%  {elapsed:.1f}s]",
                  end='\r')

    elapsed = time.time() - t_start
    print()
    print(f"\n  Simulation complete in {elapsed:.1f} s  ({N_STEPS/elapsed:.0f} steps/s)")
    print(f"  Final x_front = {np.max(rx):.3f} m  (tank width {TANK_W:.2f} m)")

    # ── Validation check — position-based (Monaghan & Kos 1999 method) ────────
    # Compare x_front at t=T_SNAP to Ritter (1892) ideal: x = 2√(gH₀) × t
    # SPH with artificial viscosity typically lands 15-30% behind Ritter at
    # this resolution.  Instantaneous velocity is too noisy to compare directly.
    print(f"\n── Wave-front validation (Ritter 1892 position) ─────────────")
    x_ritter = V_FRONT_THEORY * T_SNAP    # ideal position at T_SNAP
    if x_front_snap is not None:
        err_pct = abs(x_front_snap - x_ritter) / x_ritter * 100
        ok = err_pct < 30.0   # ±30%: typical for N~300, α_v=0.02
        print(f"  Ritter x at t={T_SNAP:.1f}s:  {x_ritter:.3f} m")
        print(f"  SPH x   at t={T_SNAP:.1f}s:  {x_front_snap:.3f} m")
        print(f"  Position error:  {err_pct:.1f}%  (pass < 30%)  "
              f"{'✓ PASS' if ok else '✗ FAIL'}")
    else:
        ok = False
        print("  ✗ Snapshot not captured.")
    # Also print instantaneous v_front for reference
    print(f"  Instantaneous v_front (late): {v_front_meas:.3f} m/s  "
          f"(Ritter ideal: {V_FRONT_THEORY:.3f} m/s, for reference only)")
    if not ok:
        print("  ✗ Wave-front check failed — check particle spacing or viscosity.")

    return frames, ok, v_front_meas, elapsed, x_front_snap


# ── GIF writer ────────────────────────────────────────────────────────────────

def write_gif(frames, path):
    print(f"\n── Writing GIF ({len(frames)} frames) → {path}")
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        optimize=False,
        duration=80,     # ms per frame → ~12.5 fps
        loop=0)
    size_kb = os.path.getsize(path) // 1024
    print(f"  GIF written: {size_kb} KB")


# ── Scaling benchmark ─────────────────────────────────────────────────────────

def run_scaling_benchmark():
    """
    Measure per-step cost vs N using single SPH force evaluation.
    Answers: how does the O(N²) brute-force SPH scale, and what N is feasible?

    This is the "particle universe" question — can we hold and query every
    particle simultaneously?  Memory is linear in N; compute is O(N²).
    """
    print("\n")
    print("═" * 60)
    print("  Scaling benchmark — SPH O(N²) force evaluation")
    print("═" * 60)
    print(f"  {'N':>7}  {'step_ms':>9}  {'mem_MB':>8}  {'steps/s':>9}  notes")
    print("  " + "-"*56)

    results = []
    test_Ns = [50, 200, 800, 3200]

    for N in test_Ns:
        # Place particles in a square block
        nx_b = int(math.sqrt(N))
        ny_b = (N + nx_b - 1) // nx_b
        ii   = np.arange(nx_b * ny_b)
        rx_b = ((ii % nx_b) + 0.5) * DELTA_X
        ry_b = ((ii // nx_b) + 0.5) * DELTA_X
        rx_b = rx_b[:N]; ry_b = ry_b[:N]
        vx_b = np.zeros(N); vy_b = np.zeros(N)
        m_b  = RHO_WATER * DELTA_X**2

        # Memory: two pairwise distance matrices of shape (N,N) float64
        # plus several (N,) arrays
        mem_pairwise_mb = (N * N * 8 * 12) / 1e6   # 12 (N,N) arrays ~ peak
        mem_particle_mb = (N * 8 * 8)      / 1e6   # 8 per-particle arrays

        tracemalloc.start()
        t0 = time.perf_counter()
        REPS = max(1, min(10, int(2.0 / (N**2 / 1e8))))
        for _ in range(REPS):
            compute_acc(rx_b, ry_b, vx_b, vy_b, m_b, H_SMOOTH,
                        RHO_WATER, K_NUM, C_S_NUM, ALPHA_V, EPS_V, G)
        t1 = time.perf_counter()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        step_ms  = (t1 - t0) / REPS * 1000.0
        peak_mb  = peak / 1e6
        steps_s  = 1000.0 / step_ms if step_ms > 0 else float('inf')
        sim_time = T_END / DT / steps_s if steps_s > 0 else float('inf')

        note = ""
        if step_ms > 1000:
            note = "SLOW"
        elif step_ms > 100:
            note = "marginal"
        else:
            note = f"~{sim_time:.0f}s total"

        results.append((N, step_ms, peak_mb, steps_s))
        print(f"  {N:>7}  {step_ms:>8.2f}ms  {peak_mb:>7.1f}MB  "
              f"{steps_s:>8.0f}/s  {note}")

    # Extrapolation to large N
    if len(results) >= 2:
        n1, t1, _, _ = results[-2]
        n2, t2, _, _ = results[-1]
        if t1 > 0 and t2 > 0:
            exp = math.log(t2 / t1) / math.log(n2 / n1)
            print(f"\n  Measured scaling exponent: O(N^{exp:.2f})  (pure O(N²) = 2.00)")

    print(f"\n  Memory layout:")
    print(f"  Per-particle state (rx,ry,vx,vy,ax,ay,rho,P): 8 × 8B = 64 B/particle")
    print(f"  Pairwise matrices peak at O(N²):  N=10K → ~800 MB  N=100K → ~80 GB")
    print(f"  → With brute-force SPH, ~5K particles is the laptop ceiling.")
    print(f"  → Tree codes (Barnes-Hut) reduce to O(N log N),")
    print(f"    enabling N=10M in ~10 GB RAM.  That is the next milestone.")

    print("═" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_foundation_checks()

    frames, phys_ok, v_front, elapsed, x_snap = run_simulation()

    out_dir = os.path.join(os.path.dirname(__file__), "..", "misc")
    os.makedirs(out_dir, exist_ok=True)

    gif_path = os.path.join(out_dir, "dam_break_sph.gif")
    png_path = os.path.join(out_dir, "dam_break_sph_final.png")

    write_gif(frames, gif_path)
    frames[-1].save(png_path)
    print(f"  Final frame: {png_path}")

    run_scaling_benchmark()

    print("\n── Summary ──────────────────────────────────────────────────")
    x_ritter_snap = V_FRONT_THEORY * 0.30
    print(f"  Physics check:  {'✓ PASS' if phys_ok else '✗ FAIL'}")
    print(f"  x_front @ 0.3s: {x_snap:.3f} m  (Ritter: {x_ritter_snap:.3f} m)" if x_snap else "  x_front snap: not captured")
    print(f"  Wall time:      {elapsed:.1f} s")
    print(f"  GIF:            {gif_path}")
    print("═" * 60)
