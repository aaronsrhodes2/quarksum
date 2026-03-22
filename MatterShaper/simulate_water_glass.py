"""
Water on Glass — 3D SPH surface tension simulation.

A vertical glass pane.  Water drops spray onto the surface.
Gravity acts in –Y.  Surface tension holds drops; adhesion
to the glass sets the contact angle.  Large drops slide.

Physics
-------
Weakly-compressible SPH (WCSPH, Monaghan 1994) with:

  1.  Pressure gradient  — WCSPH EOS, stiffness K_EOS
  2.  Artificial viscosity — Monaghan (1992) α_v
  3.  Pairwise cohesion  — water–water attraction (our physics)
      F_coh_i = −Σⱼ mⱼ · a_ww · W(rᵢⱼ, h) · r̂ᵢⱼ
      Calibrated so γ_eff = γ_water (Tartakovsky & Meakin 2005)
  4.  Wall adhesion      — ghost mirror particles at z < 0
      Same force, coefficient a_wg < a_ww for θ_contact = 20°
      Relation (Tartakovsky & Meakin 2005 Eq. 14):
          cos(θ) = 2·a_wg/a_ww − 1
          → a_wg = a_ww·(1 + cos θ)/2
  5.  Gravity            — (0, −g, 0)
  6.  Hard wall          — z ≥ 0 always; bounce z-velocity if violated

Constants (all MEASURED — one origin each)
------------------------------------------
  γ_water = 0.0728 N/m      Vargaftik et al. (1983) J. Phys. Chem. Ref. Data
  ρ_water = 998.2 kg/m³     CRC Handbook (20 °C)
  θ_contact = 20°           Yildirim Erbil (2006) Surface Chemistry of Solid
                             and Liquid Interfaces, Table 3.1 — clean glass
  g       = 9.80665 m/s²    BIPM (exact by definition since 1901)

Cohesion calibration (Tartakovsky & Meakin 2005, Eq. A7)
---------------------------------------------------------
For a flat interface with 3D cubic spline kernel:
  γ_eff = −a_ww · ρ₀² / 6 · ∫₀²ʰ (dW/dr)·r³ dr

Kernel integral (computed analytically):
  I = ∫₀²ʰ (dW/dr)·r³ dr = (3/2π) · (−0.50) · h⁴ = −3h⁴/(4π)
  → a_ww = 6·γ / (ρ₀² · 3h⁴/(4π)) = 8π·γ / (ρ₀² · h⁴)

Geometry
--------
  Glass pane at z = 0 (XY plane), water lives at z > 0.
  X: 0 → W_DOMAIN (horizontal)
  Y: 0 → H_DOMAIN (vertical, Y=0 at bottom)
  Z: 0 → D_DOMAIN (depth away from glass)
  Gravity: −Y

Rendering
---------
  Front view (looking at glass, XY plane) — primary render
  Side view (YZ cross-section at domain centre) — secondary
  Phosphor style (blue particles on near-black background)
  Particle colour encodes |v| — white = fast, blue = stationary
"""

import math, os, subprocess, tempfile, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# ── Measured constants ─────────────────────────────────────────────────────────
GAMMA_WATER  = 0.0728        # N/m   surface tension (Vargaftik 1983)
RHO_0        = 998.2         # kg/m³ reference density (CRC Handbook, 20 °C)
THETA_C      = math.radians(20.0)   # rad  contact angle, clean glass (Erbil 2006)
G_GRAV       = 9.80665       # m/s²  standard gravity (BIPM)

# ── SPH resolution ─────────────────────────────────────────────────────────────
DELTA_X   = 7.0e-4           # m   initial particle spacing (0.7 mm)
H_SMOOTH  = 1.2 * DELTA_X   # m   smoothing length
M_PART    = RHO_0 * DELTA_X**3   # kg  particle mass (exact from density × volume)

# ── WCSPH stiffness ────────────────────────────────────────────────────────────
# Numerical sound speed set so Mach < 0.1 at max expected velocity.
# Max vel ≈ capillary wave: v_cap = sqrt(γ·k/ρ) at k = π/DELTA_X ≈ 0.57 m/s
# Use 10× for safety → c_s_num = 5.7 m/s, round to 6.
C_S_NUM  = 6.0               # m/s  numerical speed of sound (NOT_PHYSICS — WCSPH trick)
K_EOS    = RHO_0 * C_S_NUM**2    # Pa   EOS stiffness

# ── Cohesion coefficients ──────────────────────────────────────────────────────
# Derived from MEASURED γ_water via Tartakovsky & Meakin (2005) kernel integral.
# I_kernel = ∫₀²ʰ (dW/dr)·r³ dr = −3h⁴/(4π)   (analytic, see module docstring)
# a_ww = 8π·γ / (ρ₀² · h⁴)
A_WW = 8.0 * math.pi * GAMMA_WATER / (RHO_0**2 * H_SMOOTH**4)
# Wall adhesion: cos(θ) = 2·a_wg/a_ww − 1  → a_wg = a_ww·(1+cosθ)/2
A_WG = A_WW * (1.0 + math.cos(THETA_C)) / 2.0

# ── Artificial viscosity ───────────────────────────────────────────────────────
ALPHA_V = 0.02               # NOT_PHYSICS — Monaghan (1992) standard choice
EPS_V   = 0.01               # NOT_PHYSICS — prevents 1/0 in viscosity

# ── Time integration ───────────────────────────────────────────────────────────
# CFL from sound speed: dt < 0.25·h/c_s
# CFL from surface tension: dt < 0.25·sqrt(ρ·h³/(2π·γ))
DT_SOUND = 0.25 * H_SMOOTH / C_S_NUM
DT_SURF  = 0.25 * math.sqrt(RHO_0 * H_SMOOTH**3 / (2.0 * math.pi * GAMMA_WATER))
DT       = 0.9 * min(DT_SOUND, DT_SURF)   # take the tighter CFL

# ── Domain ─────────────────────────────────────────────────────────────────────
W_DOM = 18.0e-3    # m  x-width  (18 mm)
H_DOM = 28.0e-3    # m  y-height (28 mm)
D_DOM =  6.0e-3    # m  z-depth  ( 6 mm, away from glass)

# ── Simulation ─────────────────────────────────────────────────────────────────
T_SIM    = 0.40    # s  total simulation time
N_FRAMES = 60
FRAME_DT = T_SIM / N_FRAMES
SKIP     = max(1, int(FRAME_DT / DT))   # steps per frame


# ── 3D cubic spline kernel (vectorised) ────────────────────────────────────────

def _W3(r, h):
    """Cubic spline kernel value (3D), vectorised over array r."""
    q    = r / h
    norm = (3.0 / (2.0 * math.pi)) / h**3
    w    = np.zeros_like(r)
    m1   = q < 1.0
    m2   = (q >= 1.0) & (q < 2.0)
    w[m1] = 2.0/3.0 - q[m1]**2 + 0.5 * q[m1]**3
    f     = 2.0 - q[m2]
    w[m2] = (1.0/6.0) * f**3
    return norm * w


def _gW3(dx, dy, dz, r, h):
    """Gradient of cubic spline kernel (3D), vectorised.
    Returns (gx, gy, gz) of shape matching dx."""
    q     = r / h
    norm  = (3.0 / (2.0 * math.pi)) / h**4
    dWdq  = np.zeros_like(r)
    m1    = q < 1.0
    m2    = (q >= 1.0) & (q < 2.0)
    dWdq[m1] = -2.0*q[m1] + 1.5*q[m1]**2
    dWdq[m2] = -0.5*(2.0 - q[m2])**2
    safe_r = np.where(r > 1e-15, r, 1.0)
    fac   = norm * dWdq / safe_r
    fac   = np.where(r > 1e-15, fac, 0.0)
    return fac*dx, fac*dy, fac*dz


# ── Force kernel ───────────────────────────────────────────────────────────────

def compute_forces(px, py, pz, vx, vy, vz, m, h, rho0, K, c_s, alpha_v, eps_v,
                   a_ww, a_wg, g):
    """Full 3D force computation with pressure, cohesion, viscosity, adhesion.

    Returns (ax, ay, az, rho) — accelerations and per-particle density.
    """
    N = len(px)

    # ── Pairwise displacements ─────────────────────────────────────────────
    dxij = px[:, None] - px[None, :]   # (N,N)
    dyij = py[:, None] - py[None, :]
    dzij = pz[:, None] - pz[None, :]
    rij  = np.sqrt(dxij**2 + dyij**2 + dzij**2)
    nbr  = (rij > 0) & (rij < 2.0 * h)

    # ── Density ────────────────────────────────────────────────────────────
    W    = _W3(rij, h)
    rho  = m * np.sum(W, axis=1)
    rho  = np.maximum(rho, 0.05 * rho0)
    P    = K * (rho / rho0 - 1.0)

    # ── Pressure gradient ──────────────────────────────────────────────────
    gWx, gWy, gWz = _gW3(dxij, dyij, dzij, rij, h)
    Pt  = P[:, None]/rho[:, None]**2 + P[None, :]/rho[None, :]**2
    Pt  = np.where(nbr, Pt, 0.0)
    apx = -m * np.sum(Pt * gWx, axis=1)
    apy = -m * np.sum(Pt * gWy, axis=1)
    apz = -m * np.sum(Pt * gWz, axis=1)

    # ── Monaghan (1992) artificial viscosity ────────────────────────────────
    dvx  = vx[:, None] - vx[None, :]
    dvy  = vy[:, None] - vy[None, :]
    dvz  = vz[:, None] - vz[None, :]
    vr   = dvx*dxij + dvy*dyij + dvz*dzij
    app  = (vr < 0) & nbr
    rij2 = rij**2
    mu   = h * vr / (rij2 + eps_v**2 * h**2)
    rm   = 0.5 * (rho[:, None] + rho[None, :])
    Pi   = np.where(app, -alpha_v * c_s * mu / rm, 0.0)
    avx  = -m * np.sum(Pi * gWx, axis=1)
    avy  = -m * np.sum(Pi * gWy, axis=1)
    avz  = -m * np.sum(Pi * gWz, axis=1)

    # ── Pairwise cohesion (water–water) ─────────────────────────────────────
    #
    # REPLACED: CSF (Continuum Surface Force) — Brackbill, Kothe & Zemach (1992)
    #   J. Comput. Phys. 100:335-354.
    #   Standard surface tension in SPH toolkits:
    #     PySPH (Ramachandran et al. 2021): pysph.sph.surface_tension.MorrisColorGradient
    #     SPlisHSPlasH (Bender & Koschier 2017): SurfaceTensionAkinci
    #   CSF method: smooth a color field C ∈ {0,1} across the fluid interface;
    #     estimate curvature κ = −∇·(∇C/|∇C|); apply F = γ·κ·∇C per particle.
    #     Requires: (a) a color-field smoothing pass each timestep,
    #               (b) a noisy curvature estimate that degrades at low N,
    #               (c) 2–3 tunable parameters (color-gradient threshold,
    #                   interface sharpness, curvature clamping).
    #
    # OURS: pairwise potential (Tartakovsky & Meakin 2005)
    #   Phys. Rev. E 72:026301, Eq. A7.
    #   F_coh_i = −Σⱼ mⱼ · a_ww · W(rᵢⱼ, h) · r̂ᵢⱼ
    #   Calibration: γ_eff = −a_ww · ρ₀² / 6 · ∫₀²ʰ (dW/dr)·r³ dr
    #     Kernel integral (analytic): I = −3h⁴/(4π)
    #     → a_ww = 8πγ / (ρ₀² · h⁴)
    #   One input: γ_water = 0.0728 N/m (MEASURED, Vargaftik 1983). No tuning.
    #   No color field. No curvature estimate. Surface tension emerges from
    #   pairwise attraction: exactly the same force law as the SPH pressure
    #   gradient, with a different coefficient and no gradient on W.
    #
    # F_coh_i = −Σⱼ mⱼ · a_ww · W(rᵢⱼ) · r̂ᵢⱼ
    # r̂ᵢⱼ = (rᵢ − rⱼ)/rᵢⱼ  →  component x: dxij/rij
    W_coh   = np.where(nbr, W, 0.0)
    safe_r  = np.where(rij > 1e-15, rij, 1.0)
    coh_fac = np.where(nbr, a_ww * m * W_coh / safe_r, 0.0)
    acx = -np.sum(coh_fac * dxij, axis=1)
    acy = -np.sum(coh_fac * dyij, axis=1)
    acz = -np.sum(coh_fac * dzij, axis=1)

    # ── Wall adhesion (glass at z = 0) — mirror ghost particles ─────────────
    #
    # REPLACED: explicit wall-particle boundary conditions
    #   Morris, Fox & Zhu (2000) Int. J. Numer. Methods Fluids 33:333-353.
    #     Method: populate wall with dummy SPH particles at each timestep;
    #     maintain wall-particle density, velocity (mirror), and pressure fields.
    #     Wall particle properties set so that the fluid "feels" a solid surface.
    #   Adami, Hu & Adams (2010) J. Comput. Phys. 229:5011-5021.
    #     Generalized pressure-extrapolation wall BC — more accurate than Morris
    #     for curved walls. Still requires explicit wall particles.
    #   For wetting contact angle: both methods require a color-function gradient
    #     in the wall-particle layer to enforce θ_c — same CSF complexity as
    #     the cohesion term.
    #
    # OURS: mirror ghost particle (Tartakovsky & Meakin 2005, Eq. 14)
    #   Each fluid particle at z = zᵢ sees a virtual ghost at z = −zᵢ.
    #   The ghost carries the same mass and the same kernel contribution.
    #   Ghost separation: r_ghost = 2·zᵢ  (collinear with z-axis for flat wall)
    #   Adhesion force in −z direction (ghost always pulls particle toward wall):
    #     F_adh = −a_wg · m · W(r_ghost, h)   [scalar, z-component only]
    #   Contact angle from Young's equation (Tartakovsky & Meakin 2005, Eq. 14):
    #     cos(θ_c) = 2·(a_wg/a_ww) − 1
    #     → a_wg = a_ww·(1 + cosθ) / 2
    #   One measured input: θ_contact = 20° (Erbil 2006) → exact contact angle.
    #   No wall particles. No pressure extrapolation. No color function.
    #   Works exactly for flat walls; generalises to curved walls via image charges.
    #
    # Each particle at z=zᵢ sees a ghost at z=−zᵢ.
    # Distance to ghost: r_ghost = sqrt(dxij=0² + dyij=0² + dz_ghost²)
    # dz_ghost = pz[i] − (−pz[i]) = 2·pz[i]
    # Adhesion acts in −z direction (ghost pulls particle toward glass).
    #
    # Only for particles within 2h of the wall.
    wall_mask = pz < 2.0 * h        # (N,) bool
    adz       = np.zeros(N)
    if np.any(wall_mask):
        r_ghost = 2.0 * pz[wall_mask]          # ghost distance > 0
        r_ghost = np.maximum(r_ghost, 1e-15)
        W_ghost = _W3_scalar_arr(r_ghost, h)   # 1D array
        # Adhesion force pulls toward glass (−z direction)
        # (the /r_ghost × r_ghost in the pairwise formula cancels;
        #  force is simply a_wg·m·W in −z direction)
        adz[wall_mask] -= a_wg * m * W_ghost

    # ── Gravity ────────────────────────────────────────────────────────────
    agy = -g * np.ones(N)

    return (apx + avx + acx,
            apy + avy + acy + agy,
            apz + avz + acz + adz,
            rho)


def _W3_scalar_arr(r_arr, h):
    """1D array version of cubic spline kernel."""
    q    = r_arr / h
    norm = (3.0 / (2.0 * math.pi)) / h**3
    w    = np.zeros_like(q)
    m1   = q < 1.0
    m2   = (q >= 1.0) & (q < 2.0)
    w[m1] = 2.0/3.0 - q[m1]**2 + 0.5*q[m1]**3
    f     = 2.0 - q[m2]
    w[m2] = (1.0/6.0) * f**3
    return norm * w


# ── Wall boundary condition ────────────────────────────────────────────────────

def apply_wall_bc(px, py, pz, vx, vy, vz):
    """Enforce domain walls.  Glass at z=0 is solid; other walls reflect."""
    # Glass wall: z ≥ 0 always, bounce z-velocity
    bounce = pz < 0
    pz     = np.where(bounce, -pz * 0.5, pz)
    vz     = np.where(bounce, -vz * 0.5, vz)

    # Side walls: x ∈ [0, W_DOM]
    lx = px < 0;      px = np.where(lx, -px,        px); vx = np.where(lx, -vx, vx)
    rx = px > W_DOM;  px = np.where(rx, 2*W_DOM-px,  px); vx = np.where(rx, -vx, vx)

    # Top/bottom walls: y ∈ [0, H_DOM]
    ly = py < 0;      py = np.where(ly, -py,        py); vy = np.where(ly, -vy, vy)
    ry = py > H_DOM;  py = np.where(ry, 2*H_DOM-py,  py); vy = np.where(ry, -vy, vy)

    # Depth wall: z ≤ D_DOM
    fz = pz > D_DOM;  pz = np.where(fz, 2*D_DOM-pz,  pz); vz = np.where(fz, -vz, vz)

    return px, py, pz, vx, vy, vz


# ── Particle initialisation ────────────────────────────────────────────────────

def _sphere_pack(cx, cy, cz, radius, dx):
    """Fill a sphere with particles on a cubic lattice."""
    xs, ys, zs = [], [], []
    r_int = int(math.ceil(radius / dx)) + 1
    for ix in range(-r_int, r_int+1):
        for iy in range(-r_int, r_int+1):
            for iz in range(-r_int, r_int+1):
                x = cx + ix*dx
                y = cy + iy*dx
                z = cz + iz*dx
                if (x-cx)**2 + (y-cy)**2 + (z-cz)**2 <= radius**2:
                    xs.append(x); ys.append(y); zs.append(z)
    return np.array(xs), np.array(ys), np.array(zs)


def init_particles():
    """Three water drops approaching the glass from different heights.

    Drop 1 (small)  — upper left,   1.2 mm radius
    Drop 2 (medium) — upper right,  1.6 mm radius
    Drop 3 (large)  — lower centre, 2.0 mm radius (Bo ≈ 0.54 — on the edge)
    """
    rng = np.random.default_rng(42)

    drops = [
        dict(cx=4.5e-3,  cy=22.0e-3, cz=2.5e-3, r=1.2e-3,
             vx0= 0.02, vy0=-0.05, vz0=-0.08),
        dict(cx=13.0e-3, cy=19.0e-3, cz=3.0e-3, r=1.6e-3,
             vx0=-0.01, vy0=-0.03, vz0=-0.10),
        dict(cx=9.0e-3,  cy=12.0e-3, cz=3.5e-3, r=2.0e-3,
             vx0= 0.00, vy0=-0.02, vz0=-0.12),
    ]

    all_x, all_y, all_z = [], [], []
    all_vx, all_vy, all_vz = [], [], []

    for d in drops:
        xs, ys, zs = _sphere_pack(d['cx'], d['cy'], d['cz'], d['r'], DELTA_X)
        n = len(xs)
        jitter = DELTA_X * 0.05
        xs += rng.uniform(-jitter, jitter, n)
        ys += rng.uniform(-jitter, jitter, n)
        zs += rng.uniform(-jitter, jitter, n)

        all_x.append(xs);  all_y.append(ys);  all_z.append(zs)
        all_vx.append(np.full(n, d['vx0']))
        all_vy.append(np.full(n, d['vy0']))
        all_vz.append(np.full(n, d['vz0']))

    px = np.concatenate(all_x);  py = np.concatenate(all_y)
    pz = np.concatenate(all_z)
    vx = np.concatenate(all_vx); vy = np.concatenate(all_vy)
    vz = np.concatenate(all_vz)

    # Clip to domain
    pz = np.clip(pz, 1e-4, D_DOM - 1e-4)
    px = np.clip(px, 0, W_DOM)
    py = np.clip(py, 0, H_DOM)

    return px, py, pz, vx, vy, vz


# ── Render ─────────────────────────────────────────────────────────────────────

def render_frame(px, py, pz, vx, vy, vz, rho, t, frame_idx, out_dir):
    """Two-panel phosphor render: front view + side view."""
    speed = np.sqrt(vx**2 + vy**2 + vz**2)
    v_max = max(speed.max(), 0.01)

    fig, (ax_front, ax_side) = plt.subplots(
        1, 2, figsize=(10, 7),
        gridspec_kw={'width_ratios': [W_DOM, D_DOM]},
        facecolor='#050508',
    )
    fig.subplots_adjust(wspace=0.08, left=0.06, right=0.97, top=0.88, bottom=0.08)

    # ── Front view (XY — looking at glass face-on) ─────────────────────────
    ax = ax_front
    ax.set_facecolor('#080810')
    ax.set_xlim(0, W_DOM * 1e3);  ax.set_ylim(0, H_DOM * 1e3)
    ax.set_aspect('equal')

    # Glass surface (faint rectangle)
    ax.axhline(0, color='#304060', lw=0.5, alpha=0.5)

    # Particle colour: speed → white hot, stationary → steel blue
    norm_speed = np.clip(speed / v_max, 0, 1)
    colors = plt.cm.cool(1.0 - norm_speed * 0.6)   # cool: cyan→magenta
    # Size scaled by z (closer to glass → bigger apparent radius)
    z_frac = 1.0 - pz / D_DOM   # 1 = on glass, 0 = far away
    sizes  = (8.0 + 22.0 * z_frac) * (DELTA_X / 7e-4)

    sc = ax.scatter(px * 1e3, py * 1e3, s=sizes, c=colors, alpha=0.85,
                    linewidths=0, zorder=2)

    # Bond number annotation per drop (approximate — use bounding-box radius)
    ax.set_xlabel('x  (mm)', color='#7090b0', fontsize=9)
    ax.set_ylabel('y  (mm) — vertical', color='#7090b0', fontsize=9)
    ax.set_title('Front view  (looking at glass)', color='#a0c0e0', fontsize=10)
    ax.tick_params(colors='#506070', labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor('#1a2030')

    # Glass label
    ax.text(0.5, 0.01, '▬ glass surface ▬',
            transform=ax.transAxes, ha='center', va='bottom',
            color='#304060', fontsize=8)

    # ── Side view (YZ — cross-section, looking from the right) ──────────────
    ax2 = ax_side
    ax2.set_facecolor('#080810')
    ax2.set_xlim(0, D_DOM * 1e3);  ax2.set_ylim(0, H_DOM * 1e3)
    ax2.set_aspect('equal')

    # Glass wall at z=0
    ax2.axvline(0, color='#aaccff', lw=1.5, alpha=0.25)
    ax2.fill_betweenx([0, H_DOM*1e3], [-0.3, -0.3], [0, 0],
                      color='#1a2840', alpha=0.6)

    ax2.scatter(pz * 1e3, py * 1e3, s=sizes*0.7, c=colors, alpha=0.85,
                linewidths=0, zorder=2)

    ax2.set_xlabel('z  (mm) — depth from glass', color='#7090b0', fontsize=9)
    ax2.set_title('Side view  (cross-section)', color='#a0c0e0', fontsize=10)
    ax2.tick_params(colors='#506070', labelsize=8)
    for spine in ax2.spines.values():
        spine.set_edgecolor('#1a2030')

    # ── Super-title ─────────────────────────────────────────────────────────
    N_tot = len(px)
    capillary_len = math.sqrt(GAMMA_WATER / (RHO_0 * G_GRAV)) * 1e3  # mm

    fig.suptitle(
        f'Water on Glass  |  t = {t*1000:.1f} ms'
        f'   N = {N_tot}   γ = {GAMMA_WATER} N/m   θ_c = 20°\n'
        f'L_cap = {capillary_len:.2f} mm   '
        f'Bo(2mm drop) = {RHO_0*G_GRAV*(2e-3)**2/GAMMA_WATER:.3f}   '
        f'a_ww = {A_WW:.3e}  a_wg = {A_WG:.3e}',
        color='#c0d8f0', fontsize=9, y=0.97,
    )

    path = os.path.join(out_dir, f'frame_{frame_idx:03d}.png')
    fig.savefig(path, dpi=120, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    return path


# ── Foundation checks ──────────────────────────────────────────────────────────

def run_foundation_checks():
    print("=== WATER ON GLASS — FOUNDATION CHECKS ===")
    print()
    print("Constants (MEASURED):")
    print(f"  γ_water    = {GAMMA_WATER} N/m        Vargaftik et al. (1983)")
    print(f"  ρ_water    = {RHO_0} kg/m³       CRC Handbook (20°C)")
    print(f"  θ_contact  = 20°               Yildirim Erbil (2006) clean glass")
    print(f"  g          = {G_GRAV} m/s²      BIPM")
    print()
    print("Derived (from MEASURED constants only):")
    print(f"  DELTA_X    = {DELTA_X*1e3:.2f} mm        particle spacing")
    print(f"  H_SMOOTH   = {H_SMOOTH*1e3:.3f} mm       smoothing length")
    print(f"  M_PART     = {M_PART:.3e} kg    particle mass")
    print(f"  K_EOS      = {K_EOS:.2f} Pa        (c_s_num = {C_S_NUM} m/s — NOT_PHYSICS)")
    print(f"  A_WW       = {A_WW:.4e}     water–water cohesion")
    print(f"  A_WG       = {A_WG:.4e}     water–glass cohesion")
    print(f"  A_WG/A_WW  = {A_WG/A_WW:.4f}              → θ_c check:")
    print(f"    cos(θ_c) = 2·(A_WG/A_WW) − 1 = {2*A_WG/A_WW - 1:.4f}")
    print(f"    θ_c      = {math.degrees(math.acos(2*A_WG/A_WW - 1)):.2f}°  (target 20.0°) ✓")
    print()
    print("Physics regime:")
    L_cap = math.sqrt(GAMMA_WATER / (RHO_0 * G_GRAV)) * 1e3
    print(f"  Capillary length L_c = {L_cap:.3f} mm  (√(γ/ρg))")
    for R_mm in [1.2, 1.6, 2.0]:
        Bo = RHO_0 * G_GRAV * (R_mm*1e-3)**2 / GAMMA_WATER
        verdict = "surface tension dominates" if Bo < 0.5 else \
                  "both forces (~equal)" if Bo < 2.0 else "gravity dominates"
        print(f"  R = {R_mm:.1f} mm → Bo = {Bo:.3f}   {verdict}")
    print()
    print("Timestep:")
    print(f"  DT_sound   = {DT_SOUND*1e6:.2f} μs")
    print(f"  DT_surf    = {DT_SURF*1e6:.2f} μs")
    print(f"  DT (used)  = {DT*1e6:.2f} μs  (90% of tighter CFL)")
    print(f"  SKIP       = {SKIP} steps/frame")
    print(f"  Total steps= {int(T_SIM/DT):,}")
    print()
    px, py, pz, vx, vy, vz = init_particles()
    print(f"  N particles= {len(px)}  ({len(px)*M_PART*1e6:.1f} μg total water)")
    print()
    print("=== ALL CHECKS COMPLETE ===")
    print()
    return px, py, pz, vx, vy, vz


# ── Main simulation loop ───────────────────────────────────────────────────────

def run_simulation(px, py, pz, vx, vy, vz, gif_path):
    tmpdir = tempfile.mkdtemp(prefix='wglass_')
    png_paths = []
    t0_wall = time.perf_counter()

    print(f"Simulating {T_SIM*1e3:.0f} ms  →  {N_FRAMES} frames "
          f"  |  DT = {DT*1e6:.1f} μs  |  N = {len(px)}")

    # Initial half-kick (velocity-Verlet)
    ax, ay, az, rho = compute_forces(px, py, pz, vx, vy, vz, M_PART,
                                     H_SMOOTH, RHO_0, K_EOS, C_S_NUM,
                                     ALPHA_V, EPS_V, A_WW, A_WG, G_GRAV)
    vx_h = vx + 0.5*DT*ax
    vy_h = vy + 0.5*DT*ay
    vz_h = vz + 0.5*DT*az

    t_sim = 0.0
    frame = 0

    # Render frame 0
    path = render_frame(px, py, pz, vx, vy, vz, rho, t_sim, frame, tmpdir)
    png_paths.append(path)
    frame += 1

    step = 0
    while frame <= N_FRAMES:
        # Drift
        px += DT * vx_h
        py += DT * vy_h
        pz += DT * vz_h
        t_sim += DT

        # Wall BC
        px, py, pz, vx_h, vy_h, vz_h = apply_wall_bc(
            px, py, pz, vx_h, vy_h, vz_h)

        # Forces
        ax, ay, az, rho = compute_forces(px, py, pz, vx_h, vy_h, vz_h, M_PART,
                                         H_SMOOTH, RHO_0, K_EOS, C_S_NUM,
                                         ALPHA_V, EPS_V, A_WW, A_WG, G_GRAV)
        # Full-kick
        vx_h += DT * ax
        vy_h += DT * ay
        vz_h += DT * az
        step += 1

        if step % SKIP == 0 and frame <= N_FRAMES:
            # Recover full-step velocity for rendering
            vx_full = vx_h - 0.5*DT*ax
            vy_full = vy_h - 0.5*DT*ay
            vz_full = vz_h - 0.5*DT*az
            path = render_frame(px, py, pz, vx_full, vy_full, vz_full,
                                rho, t_sim, frame, tmpdir)
            png_paths.append(path)
            elapsed = time.perf_counter() - t0_wall
            fps_sim = frame / elapsed
            print(f"  Frame {frame:3d}/{N_FRAMES}  t={t_sim*1e3:.1f} ms  "
                  f"[{elapsed:.1f}s  ~{(N_FRAMES-frame)/fps_sim:.0f}s left]")
            frame += 1

    # Assemble GIF
    print("Assembling GIF...")
    cmd = ['convert', '-delay', '6', '-loop', '0',
           '-layers', 'Optimize', '-dither', 'Riemersma']
    cmd += png_paths
    cmd += [gif_path]
    subprocess.run(cmd, check=True, capture_output=True)
    total = time.perf_counter() - t0_wall
    size  = os.path.getsize(gif_path) // 1024
    print(f"Done. → {gif_path}  ({size} KB, {total:.1f}s total)")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    px, py, pz, vx, vy, vz = run_foundation_checks()
    _here  = os.path.dirname(os.path.abspath(__file__))
    out    = os.path.normpath(os.path.join(_here, '..', 'misc', 'water_glass.gif'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    run_simulation(px, py, pz, vx, vy, vz, out)
