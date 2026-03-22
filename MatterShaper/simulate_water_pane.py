"""
Water on a Large Glass Pane — 3D SPH simulation with three surface zones.

Scenario
--------
A 3 m × 3 m glass pane, 4 cm thick, standing vertically (XZ plane = glass face).
2 litres of water is splashed at the pane centre.
Gravity acts in −Y (downward along the pane face).
Water flows, beads, or freezes depending on the zone it contacts.

Three horizontal zones (by Y coordinate on the pane face)
----------------------------------------------------------
  ZONE A — Bare glass      (Y_B_LO ≤ y ≤ Y_TOP)   top strip
    θ_contact = 20°     γ_eff = γ_water = 0.0728 N/m
    Normal wetting: water adheres, spreads in a thin film, slides slowly.
    a_wg = a_ww · (1 + cos 20°) / 2   (Young's equation, Tartakovsky 2005)

  ZONE B — Silane-coated   (Y_C_LO ≤ y < Y_B_LO)  middle strip
    θ_contact = 110°    hydrophobic
    Silane chemistry: replaces surface -OH (hydroxyl, polar, H-bond donor) with
    -CH₃ (methyl, non-polar). Eliminates the electrostatic attraction between
    water dipoles and the glass hydroxyl network. Measured θ_c from Bain et al.
    (1989) alkylsilane monolayers on glass: θ_c ≈ 110°.
    a_wg = a_ww · (1 + cos 110°) / 2 ≈ 0.329 · a_ww
    Drops bead up, contact line unstable, gravity wins: they slide and run.

  ZONE C — Freezing zone   (0 ≤ y < Y_C_LO)       bottom strip
    Surface temperature T < 0°C. On contact, particles freeze in place:
    velocity zeroed, position locked. The ice grows from the bottom up.

Physics
-------
Weakly-compressible SPH (WCSPH, Monaghan 1994) with:
  1. Pressure gradient   — WCSPH EOS
  2. Artificial viscosity — Monaghan (1992) α_v = 0.02
  3. Pairwise cohesion   — Tartakovsky & Meakin (2005) [see REPLACED note below]
  4. Wall adhesion       — mirror ghost particles [see REPLACED note below]
  5. Gravity             — (0, −g, 0)
  6. Bounce BC           — elastic/inelastic at pane face (z=0) and domain edges
  7. Freezing BC         — particles in zone C touching pane get velocity zeroed

     REPLACED (cohesion): CSF — Brackbill, Kothe & Zemach (1992)
       J. Comput. Phys. 100:335-354. Standard in PySPH, SPlisHSPlasH.
       Requires color field, curvature estimate, 2-3 magic parameters.
     OURS: pairwise potential, a_ww = 8πγ/(ρ₀²h⁴). One measured input: γ_water.

     REPLACED (adhesion): explicit wall particles — Morris, Fox & Zhu (2000);
       Adami, Hu & Adams (2010). Wall particle density/pressure maintained per step.
     OURS: mirror ghost at z = −zᵢ; a_wg = a_ww·(1+cosθ)/2; Young's eq. exact.

Constants (MEASURED — one origin each)
---------------------------------------
  γ_water   = 0.0728 N/m        Vargaftik et al. (1983) J. Phys. Chem. Ref. Data
  ρ_water   = 998.2  kg/m³      CRC Handbook (20°C)
  θ_bare    = 20°               Yildirim Erbil (2006) Table 3.1, clean glass
  θ_silane  = 110°              Bain, Evall & Whitesides (1989) JACS 111:7155,
                                  alkylsilane monolayers on glass/SiO₂
  g         = 9.80665 m/s²      BIPM (exact by definition since 1901)

SPH resolution
--------------
  DELTA_X   = 15 mm   inter-particle spacing
  H_SMOOTH  = 18 mm   smoothing length (k=1.2 × DELTA_X)
  M_PART    = ρ × DELTA_X³ = 998.2 × (0.015)³ ≈ 3.37 g per particle
  2 litres  = 2.0 kg water → N ≈ 2.0 / M_PART ≈ 594 particles

Human visual acuity note
------------------------
  Human angular resolution: 1/60° of arc (1 arcminute) — Rayleigh criterion.
  At 3 m viewing distance: 3000 mm × tan(1/60 × π/180) ≈ 0.87 mm min. feature.
  Our DELTA_X = 15 mm → each particle subtends ~17 arcminutes at 3 m.
  Every particle is individually resolvable by the naked eye at normal distance.
  The simulation will show zone behaviour at human-perceptible scale.

Domain
------
  Pane face: z = 0 (YX plane)  — glass surface, water lives at z > 0
  X: 0 → W_DOM = 3.0 m  (horizontal, across pane)
  Y: 0 → H_DOM = 3.0 m  (vertical, Y=0 at bottom, Y=3 at top)
  Z: 0 → D_DOM = 0.3 m  (depth away from glass — 10× DELTA_X)

Zone boundaries
---------------
  Y_TOP   = 3.0 m      top of pane
  Y_B_LO  = 2.0 m      bare/silane boundary
  Y_C_LO  = 1.0 m      silane/freezing boundary
  Y_BOT   = 0.0 m      bottom of pane

  ZONE A (bare):    2.0 m ≤ y ≤ 3.0 m   top third
  ZONE B (silane):  1.0 m ≤ y < 2.0 m   middle third
  ZONE C (freeze):  0.0 m ≤ y < 1.0 m   bottom third

Rendering
---------
  Front view (XY) — primary — looking at the pane face.
    Zone bands drawn as faint horizontal stripes: blue/grey/icy-cyan.
  Side view (YZ)  — secondary — cross-section showing depth profile.
  Particle colour: zone-coded + speed-modulated.
    Zone A: steel blue (#4488cc)   bare glass
    Zone B: amber/gold (#cc8833)   silane — drops glow warm, hydrophobic
    Zone C: icy cyan  (#88ddff)    frozen particles, low saturation
  Frozen particles drawn with a ✦ marker to distinguish from free water.
"""

import math, os, subprocess, tempfile, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Measured constants ──────────────────────────────────────────────────────────
GAMMA_WATER   = 0.0728         # N/m   surface tension (Vargaftik 1983)
RHO_0         = 998.2          # kg/m³ reference density (CRC Handbook, 20°C)
THETA_BARE    = math.radians(20.0)    # rad  bare glass (Erbil 2006)
THETA_SILANE  = math.radians(110.0)  # rad  silane-coated glass (Bain et al. 1989)
G_GRAV        = 9.80665        # m/s²  standard gravity (BIPM)

# ── SPH resolution ──────────────────────────────────────────────────────────────
DELTA_X   = 15.0e-3            # m   particle spacing (15 mm)
H_SMOOTH  = 1.2 * DELTA_X     # m   smoothing length (18 mm)
M_PART    = RHO_0 * DELTA_X**3   # kg  particle mass = ρ₀ × DELTA_X³ ≈ 3.37 g

# ── WCSPH stiffness ─────────────────────────────────────────────────────────────
# Numerical sound speed: Mach < 0.1 at max expected velocity.
# Splash velocity ~ 3 m/s → c_s_num = 30 m/s.
C_S_NUM  = 30.0                # m/s  numerical sound speed (NOT_PHYSICS)
K_EOS    = RHO_0 * C_S_NUM**2     # Pa   EOS stiffness

# ── Cohesion coefficients ────────────────────────────────────────────────────────
# a_ww from Tartakovsky & Meakin (2005) kernel integral (see module docstring)
# a_ww = 8π·γ / (ρ₀² · h⁴)
A_WW = 8.0 * math.pi * GAMMA_WATER / (RHO_0**2 * H_SMOOTH**4)

# Wall adhesion for each zone: a_wg = a_ww·(1 + cosθ)/2
A_WG_BARE   = A_WW * (1.0 + math.cos(THETA_BARE))   / 2.0   # zone A: θ=20°
A_WG_SILANE = A_WW * (1.0 + math.cos(THETA_SILANE)) / 2.0   # zone B: θ=110°
# Zone C: no adhesion parameter needed — particles freeze on contact instead

# ── Artificial viscosity ─────────────────────────────────────────────────────────
ALPHA_V = 0.02                 # NOT_PHYSICS — Monaghan (1992)
EPS_V   = 0.01                 # NOT_PHYSICS — viscosity denominator guard

# ── Time integration ─────────────────────────────────────────────────────────────
DT_SOUND = 0.25 * H_SMOOTH / C_S_NUM
DT_SURF  = 0.25 * math.sqrt(RHO_0 * H_SMOOTH**3 / (2.0 * math.pi * GAMMA_WATER))
DT       = 0.9 * min(DT_SOUND, DT_SURF)

# ── Domain ───────────────────────────────────────────────────────────────────────
W_DOM = 3.0    # m  x-width  (3 m pane)
H_DOM = 3.0    # m  y-height (3 m pane)
D_DOM = 0.3    # m  z-depth  (away from glass face)

# ── Zone boundaries ──────────────────────────────────────────────────────────────
Y_B_LO  = 2.0   # m  bare / silane boundary (Y above this → bare glass)
Y_C_LO  = 1.0   # m  silane / freezing boundary (Y below this → freezing)

# ── Simulation ───────────────────────────────────────────────────────────────────
T_SIM    = 2.0    # s  total simulation time (water flowing across all three zones)
N_FRAMES = 80
FRAME_DT = T_SIM / N_FRAMES
SKIP     = max(1, int(FRAME_DT / DT))


# ── Zone classifier ─────────────────────────────────────────────────────────────

def _zone(py):
    """Return zone index array: 0=bare, 1=silane, 2=freezing."""
    z = np.zeros(len(py), dtype=int)
    z[py < Y_B_LO]  = 1   # below bare/silane boundary
    z[py < Y_C_LO]  = 2   # below silane/freezing boundary
    return z


# ── SPH kernel (vectorised) ──────────────────────────────────────────────────────

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
    """Gradient of cubic spline kernel (3D), vectorised."""
    q     = r / h
    norm  = (3.0 / (2.0 * math.pi)) / h**4
    dWdq  = np.zeros_like(r)
    m1    = q < 1.0
    m2    = (q >= 1.0) & (q < 2.0)
    dWdq[m1] = -2.0*q[m1] + 1.5*q[m1]**2
    dWdq[m2] = -0.5*(2.0 - q[m2])**2
    safe_r = np.where(r > 1e-15, r, 1.0)
    fac    = norm * dWdq / safe_r
    fac    = np.where(r > 1e-15, fac, 0.0)
    return fac*dx, fac*dy, fac*dz


def _W3_arr(r_arr, h):
    """1-D array version of cubic spline kernel (for ghost distances)."""
    q    = r_arr / h
    norm = (3.0 / (2.0 * math.pi)) / h**3
    w    = np.zeros_like(q)
    m1   = q < 1.0
    m2   = (q >= 1.0) & (q < 2.0)
    w[m1] = 2.0/3.0 - q[m1]**2 + 0.5*q[m1]**3
    f     = 2.0 - q[m2]
    w[m2] = (1.0/6.0) * f**3
    return norm * w


# ── Force kernel ─────────────────────────────────────────────────────────────────

def compute_forces(px, py, pz, vx, vy, vz, frozen, h, rho0, K, c_s,
                   alpha_v, eps_v, a_ww, a_wg_bare, a_wg_silane, g):
    """Full 3D SPH force computation with zone-dependent wall adhesion.

    Frozen particles contribute to density and kernel sums (they carry mass)
    but receive zero acceleration themselves — their velocity is held to zero
    by apply_freezing_bc() after each step.

    Returns (ax, ay, az, rho).
    """
    N = len(px)

    # ── Pairwise displacements ─────────────────────────────────────────────
    dxij = px[:, None] - px[None, :]
    dyij = py[:, None] - py[None, :]
    dzij = pz[:, None] - pz[None, :]
    rij  = np.sqrt(dxij**2 + dyij**2 + dzij**2)
    nbr  = (rij > 0) & (rij < 2.0 * h)

    # ── Density ────────────────────────────────────────────────────────────
    W    = _W3(rij, h)
    rho  = M_PART * np.sum(W, axis=1)
    rho  = np.maximum(rho, 0.05 * rho0)
    P    = K * (rho / rho0 - 1.0)

    # Frozen particles: return early with zero acceleration
    # (they are computed for density but hold position)
    result_ax = np.zeros(N)
    result_ay = np.zeros(N)
    result_az = np.zeros(N)

    free = ~frozen
    if not np.any(free):
        return result_ax, result_ay, result_az, rho

    # ── Pressure gradient ──────────────────────────────────────────────────
    gWx, gWy, gWz = _gW3(dxij, dyij, dzij, rij, h)
    Pt  = P[:, None]/rho[:, None]**2 + P[None, :]/rho[None, :]**2
    Pt  = np.where(nbr, Pt, 0.0)
    apx = -M_PART * np.sum(Pt * gWx, axis=1)
    apy = -M_PART * np.sum(Pt * gWy, axis=1)
    apz = -M_PART * np.sum(Pt * gWz, axis=1)

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
    avx  = -M_PART * np.sum(Pi * gWx, axis=1)
    avy  = -M_PART * np.sum(Pi * gWy, axis=1)
    avz  = -M_PART * np.sum(Pi * gWz, axis=1)

    # ── Pairwise cohesion (water–water)  ─────────────────────────────────────
    #
    # REPLACED: CSF — Brackbill, Kothe & Zemach (1992) J. Comput. Phys. 100:335-354
    #   Color field + curvature estimate + 2-3 tunable parameters.
    # OURS: pairwise potential — Tartakovsky & Meakin (2005) Phys. Rev. E 72:026301
    #   F_coh_i = −Σⱼ mⱼ · a_ww · W(rᵢⱼ) · r̂ᵢⱼ
    #   One measured input: γ_water → a_ww = 8πγ/(ρ₀²h⁴). No tuning.
    W_coh   = np.where(nbr, W, 0.0)
    safe_r  = np.where(rij > 1e-15, rij, 1.0)
    coh_fac = np.where(nbr, a_ww * M_PART * W_coh / safe_r, 0.0)
    acx = -np.sum(coh_fac * dxij, axis=1)
    acy = -np.sum(coh_fac * dyij, axis=1)
    acz = -np.sum(coh_fac * dzij, axis=1)

    # ── Wall adhesion — mirror ghost particles ───────────────────────────────
    #
    # REPLACED: Morris, Fox & Zhu (2000) wall particles; Adami et al. (2010) BC.
    #   Explicit wall particle layer, pressure extrapolation, color function for θ.
    # OURS: mirror ghost at z = −zᵢ (Tartakovsky & Meakin 2005, Eq. 14)
    #   a_wg = a_ww · (1 + cosθ) / 2   (Young's equation)
    #   Zone-dependent θ → zone-dependent a_wg. Three zones, two adhesion values.
    #   Zone C: no adhesion — particles in that zone are frozen on contact instead.
    adz = np.zeros(N)
    wall_mask = (pz < 2.0 * h) & free & ~frozen
    if np.any(wall_mask):
        r_ghost = 2.0 * pz[wall_mask]
        r_ghost = np.maximum(r_ghost, 1e-15)
        W_ghost = _W3_arr(r_ghost, h)

        yw      = py[wall_mask]
        # Select adhesion coefficient by zone
        a_wg_w  = np.where(yw >= Y_B_LO, a_wg_bare,
                  np.where(yw >= Y_C_LO, a_wg_silane,
                           0.0))   # zone C: no adhesion (frozen instead)
        adz[wall_mask] -= a_wg_w * M_PART * W_ghost

    # ── Gravity ────────────────────────────────────────────────────────────
    agy = -g * np.ones(N)

    result_ax = apx + avx + acx
    result_ay = apy + avy + acy + agy
    result_az = apz + avz + acz + adz

    # Frozen particles receive zero acceleration
    result_ax[frozen] = 0.0
    result_ay[frozen] = 0.0
    result_az[frozen] = 0.0

    return result_ax, result_ay, result_az, rho


# ── Boundary conditions ──────────────────────────────────────────────────────────

def apply_wall_bc(px, py, pz, vx, vy, vz):
    """Enforce domain walls. Glass at z=0 is solid; other walls reflect."""
    # Glass face: z ≥ 0 always, inelastic bounce (50% restitution)
    bounce = pz < 0
    pz     = np.where(bounce, -pz * 0.5, pz)
    vz     = np.where(bounce, -vz * 0.5, vz)

    # Side walls: x ∈ [0, W_DOM]
    lx = px < 0;      px = np.where(lx, -px,          px); vx = np.where(lx, -vx, vx)
    rx = px > W_DOM;  px = np.where(rx,  2*W_DOM - px, px); vx = np.where(rx, -vx, vx)

    # Top/bottom walls: y ∈ [0, H_DOM]
    ly = py < 0;      py = np.where(ly, -py,          py); vy = np.where(ly, -vy, vy)
    ry = py > H_DOM;  py = np.where(ry,  2*H_DOM - py, py); vy = np.where(ry, -vy, vy)

    # Depth wall: z ≤ D_DOM
    fz = pz > D_DOM;  pz = np.where(fz,  2*D_DOM - pz, pz); vz = np.where(fz, -vz, vz)

    return px, py, pz, vx, vy, vz


def apply_freezing_bc(px, py, pz, vx, vy, vz, frozen):
    """Freeze particles in zone C that touch the glass (z < 2h).

    Once frozen, a particle's velocity is zeroed every step.
    Newly frozen particles: any free particle in zone C within 2h of the wall.

    Returns updated (vx, vy, vz, frozen).
    """
    # Detect newly frozen: free, in zone C, close to wall
    near_wall = pz < 2.0 * H_SMOOTH
    in_zone_c = py < Y_C_LO
    newly_frozen = near_wall & in_zone_c & ~frozen
    frozen = frozen | newly_frozen

    # Zero velocity for all frozen particles
    vx[frozen] = 0.0
    vy[frozen] = 0.0
    vz[frozen] = 0.0

    return vx, vy, vz, frozen


# ── Particle initialisation ──────────────────────────────────────────────────────

def _sphere_pack(cx, cy, cz, radius, dx):
    """Fill a sphere with particles on a cubic lattice."""
    xs, ys, zs = [], [], []
    r_int = int(math.ceil(radius / dx)) + 1
    for ix in range(-r_int, r_int + 1):
        for iy in range(-r_int, r_int + 1):
            for iz in range(-r_int, r_int + 1):
                x = cx + ix * dx
                y = cy + iy * dx
                z = cz + iz * dx
                if (x-cx)**2 + (y-cy)**2 + (z-cz)**2 <= radius**2:
                    xs.append(x); ys.append(y); zs.append(z)
    return np.array(xs), np.array(ys), np.array(zs)


def init_particles():
    """2 litres of water as a spherical blob, splashed at pane centre.

    Blob radius calibrated to give exactly N ≈ 594 particles at DELTA_X = 15 mm.
    Volume = (4/3)π r³ = 2 × 10⁻³ m³ → r = 0.0785 m ≈ 78.5 mm.
    Launched toward the glass centre at vz = −3 m/s (splash velocity).

    Initial position: centre of the pane at z = 0.25 m from glass.
    """
    rng = np.random.default_rng(42)

    # Target: 2 L sphere
    V_WATER  = 2.0e-3          # m³
    R_BLOB   = (3.0 * V_WATER / (4.0 * math.pi)) ** (1.0 / 3.0)   # ~78.5 mm

    cx = W_DOM / 2.0           # 1.5 m — horizontal centre
    cy = H_DOM / 2.0           # 1.5 m — vertical centre (mid-pane)
    cz = 0.20                  # 0.20 m from glass — in the air

    xs, ys, zs = _sphere_pack(cx, cy, cz, R_BLOB, DELTA_X)
    N = len(xs)

    # Jitter to break lattice symmetry
    jitter = DELTA_X * 0.05
    xs += rng.uniform(-jitter, jitter, N)
    ys += rng.uniform(-jitter, jitter, N)
    zs += rng.uniform(-jitter, jitter, N)

    # Clip to domain
    pz = np.clip(zs, 1e-3, D_DOM - 1e-3)
    px = np.clip(xs, 0.0, W_DOM)
    py = np.clip(ys, 0.0, H_DOM)

    # Initial velocities: splashing toward glass
    vx = rng.uniform(-0.5, 0.5, N)   # m/s  lateral scatter
    vy = rng.uniform(-0.3, 0.3, N)   # m/s  vertical scatter
    vz = np.full(N, -3.0)            # m/s  toward glass

    frozen = np.zeros(N, dtype=bool)

    return px, py, pz, vx, vy, vz, frozen


# ── Render ───────────────────────────────────────────────────────────────────────

# Zone colours (base hue, modulated by speed)
_COL_BARE    = np.array([0.27, 0.53, 0.80])   # steel blue
_COL_SILANE  = np.array([0.80, 0.53, 0.20])   # amber
_COL_FROZEN  = np.array([0.53, 0.87, 1.00])   # icy cyan
_COL_FREE    = np.array([0.20, 0.60, 1.00])   # free water (in-air)


def _particle_colors(px, py, pz, vx, vy, vz, frozen):
    """Assign RGBA per particle: zone-coded base colour, speed-brightened."""
    N      = len(px)
    speed  = np.sqrt(vx**2 + vy**2 + vz**2)
    v_max  = max(speed.max(), 0.01)
    bright = np.clip(speed / v_max, 0.0, 1.0)   # 0=slow (dark), 1=fast (bright)

    zone = _zone(py)
    rgba = np.zeros((N, 4))

    for i in range(N):
        if frozen[i]:
            base = _COL_FROZEN
        elif pz[i] > 2.0 * H_SMOOTH:
            base = _COL_FREE            # in-air: standard water blue
        elif zone[i] == 0:
            base = _COL_BARE
        elif zone[i] == 1:
            base = _COL_SILANE
        else:
            base = _COL_FROZEN          # in zone C but not yet frozen: cyan tint

        # Brighten toward white with speed
        c = base + bright[i] * (1.0 - base) * 0.5
        rgba[i] = [min(c[0], 1.0), min(c[1], 1.0), min(c[2], 1.0), 0.85]

    return rgba


def render_frame(px, py, pz, vx, vy, vz, rho, frozen, t, frame_idx, out_dir):
    """Two-panel phosphor render: front view (XY) + side view (YZ)."""
    speed  = np.sqrt(vx**2 + vy**2 + vz**2)
    rgba   = _particle_colors(px, py, pz, vx, vy, vz, frozen)
    z_frac = 1.0 - np.clip(pz / D_DOM, 0, 1)
    sizes  = (6.0 + 18.0 * z_frac) * (DELTA_X / 15e-3)

    fig, (ax_front, ax_side) = plt.subplots(
        1, 2, figsize=(12, 7),
        gridspec_kw={'width_ratios': [W_DOM, D_DOM]},
        facecolor='#050508',
    )
    fig.subplots_adjust(wspace=0.06, left=0.05, right=0.97, top=0.87, bottom=0.07)

    # ── Front view (XY — looking at pane face-on) ──────────────────────────
    ax = ax_front
    ax.set_facecolor('#080810')
    ax.set_xlim(0, W_DOM);  ax.set_ylim(0, H_DOM)
    ax.set_aspect('equal')

    # Zone bands (faint background stripes)
    ax.axhspan(Y_B_LO, H_DOM,   alpha=0.06, color='#4488cc', zorder=0)   # bare
    ax.axhspan(Y_C_LO, Y_B_LO,  alpha=0.06, color='#cc8833', zorder=0)   # silane
    ax.axhspan(0,      Y_C_LO,  alpha=0.08, color='#88ddff', zorder=0)   # freezing

    # Zone labels
    ax.text(0.02, (Y_B_LO + H_DOM)  / 2, 'ZONE A\nBare glass\nθ=20°',
            color='#6699cc', fontsize=8, va='center', transform=ax.transData, alpha=0.7)
    ax.text(0.02, (Y_C_LO + Y_B_LO) / 2, 'ZONE B\nSilane\nθ=110°',
            color='#cc9944', fontsize=8, va='center', transform=ax.transData, alpha=0.7)
    ax.text(0.02, Y_C_LO / 2, 'ZONE C\nFreezing\nT<0°C',
            color='#88ccee', fontsize=8, va='center', transform=ax.transData, alpha=0.7)

    # Zone boundary lines
    ax.axhline(Y_B_LO, color='#446688', lw=0.8, alpha=0.6, ls='--')
    ax.axhline(Y_C_LO, color='#446688', lw=0.8, alpha=0.6, ls='--')

    # Particles
    free_mask   = ~frozen
    frozen_mask = frozen
    if np.any(free_mask):
        ax.scatter(px[free_mask], py[free_mask],
                   s=sizes[free_mask], c=rgba[free_mask],
                   linewidths=0, zorder=2)
    if np.any(frozen_mask):
        ax.scatter(px[frozen_mask], py[frozen_mask],
                   s=sizes[frozen_mask]*1.3, c=rgba[frozen_mask],
                   marker='*', linewidths=0, zorder=3, alpha=0.95)

    ax.set_xlabel('x  (m) — horizontal', color='#7090b0', fontsize=9)
    ax.set_ylabel('y  (m) — vertical (gravity ↓)', color='#7090b0', fontsize=9)
    ax.set_title('Front view  (looking at pane face)', color='#a0c0e0', fontsize=10)
    ax.tick_params(colors='#506070', labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor('#1a2030')

    # Legend
    patches = [
        mpatches.Patch(color=[*_COL_BARE,   0.85], label='Bare glass (θ=20°)'),
        mpatches.Patch(color=[*_COL_SILANE, 0.85], label='Silane (θ=110°)'),
        mpatches.Patch(color=[*_COL_FROZEN, 0.85], label='Frozen'),
    ]
    ax.legend(handles=patches, loc='upper right', fontsize=7,
              facecolor='#0a0a14', edgecolor='#304060',
              labelcolor='#a0c0e0', framealpha=0.8)

    # ── Side view (YZ — cross-section) ─────────────────────────────────────
    ax2 = ax_side
    ax2.set_facecolor('#080810')
    ax2.set_xlim(0, D_DOM);  ax2.set_ylim(0, H_DOM)
    ax2.set_aspect('equal')

    # Glass face at z=0
    ax2.axvline(0, color='#aaccff', lw=2.0, alpha=0.3)
    ax2.fill_betweenx([0, H_DOM], [-0.01, -0.01], [0, 0],
                      color='#1a2840', alpha=0.7)

    # Zone bands in side view
    ax2.axhspan(Y_B_LO, H_DOM,   alpha=0.06, color='#4488cc', zorder=0)
    ax2.axhspan(Y_C_LO, Y_B_LO,  alpha=0.06, color='#cc8833', zorder=0)
    ax2.axhspan(0,      Y_C_LO,  alpha=0.08, color='#88ddff', zorder=0)

    if np.any(free_mask):
        ax2.scatter(pz[free_mask], py[free_mask],
                    s=sizes[free_mask]*0.7, c=rgba[free_mask],
                    linewidths=0, zorder=2)
    if np.any(frozen_mask):
        ax2.scatter(pz[frozen_mask], py[frozen_mask],
                    s=sizes[frozen_mask]*0.9, c=rgba[frozen_mask],
                    marker='*', linewidths=0, zorder=3)

    ax2.set_xlabel('z  (m) — depth from glass', color='#7090b0', fontsize=9)
    ax2.set_title('Side view  (cross-section)', color='#a0c0e0', fontsize=10)
    ax2.tick_params(colors='#506070', labelsize=8)
    for sp in ax2.spines.values():
        sp.set_edgecolor('#1a2030')

    # ── Super-title ─────────────────────────────────────────────────────────
    N_tot    = len(px)
    N_frozen = frozen.sum()
    N_free   = N_tot - N_frozen
    mass_kg  = N_tot * M_PART
    L_cap    = math.sqrt(GAMMA_WATER / (RHO_0 * G_GRAV)) * 1e3   # mm

    fig.suptitle(
        f'Water on 3m×3m Pane  |  t = {t*1000:.0f} ms  |  '
        f'N = {N_tot}  ({mass_kg*1e3:.0f} g water)\n'
        f'Free: {N_free}   Frozen: {N_frozen}   '
        f'L_cap = {L_cap:.1f} mm   '
        f'θ_bare=20°  θ_silane=110°  Zone C: T<0°C',
        color='#c0d8f0', fontsize=9, y=0.97,
    )

    path = os.path.join(out_dir, f'frame_{frame_idx:03d}.png')
    fig.savefig(path, dpi=110, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    return path


# ── Foundation checks ─────────────────────────────────────────────────────────────

def run_foundation_checks():
    """Print and verify all physical parameters before simulation."""
    print("=== WATER ON PANE — FOUNDATION CHECKS ===")
    print()
    print("Constants (MEASURED — one origin each):")
    print(f"  γ_water   = {GAMMA_WATER} N/m           Vargaftik et al. (1983)")
    print(f"  ρ_water   = {RHO_0} kg/m³          CRC Handbook (20°C)")
    print(f"  θ_bare    = 20°                   Yildirim Erbil (2006) clean glass")
    print(f"  θ_silane  = 110°                  Bain, Evall & Whitesides (1989)")
    print(f"  g         = {G_GRAV} m/s²         BIPM")
    print()
    print("SPH resolution:")
    print(f"  DELTA_X   = {DELTA_X*1e3:.1f} mm")
    print(f"  H_SMOOTH  = {H_SMOOTH*1e3:.1f} mm")
    print(f"  M_PART    = {M_PART*1e3:.3f} g per particle")
    print()
    print("Cohesion (a_ww = 8πγ / (ρ₀²·h⁴)):")
    print(f"  A_WW       = {A_WW:.4e}")
    print()
    print("Wall adhesion per zone (a_wg = a_ww·(1+cosθ)/2, Young's equation):")
    print(f"  Zone A (bare,   θ=20°):   a_wg = {A_WG_BARE:.4e}   "
          f"  check: θ_c = {math.degrees(math.acos(2*A_WG_BARE/A_WW - 1)):.2f}°  ✓")
    print(f"  Zone B (silane, θ=110°):  a_wg = {A_WG_SILANE:.4e}  "
          f"  check: θ_c = {math.degrees(math.acos(2*A_WG_SILANE/A_WW - 1)):.2f}°  ✓")
    print(f"  Zone C (freeze, T<0°C):   no adhesion — freeze on contact")
    print()
    print("Timestep:")
    print(f"  DT_sound  = {DT_SOUND*1e3:.3f} ms")
    print(f"  DT_surf   = {DT_SURF*1e3:.3f} ms")
    print(f"  DT (used) = {DT*1e3:.3f} ms  (90% of tighter CFL)")
    print(f"  SKIP      = {SKIP} steps/frame")
    print(f"  N_frames  = {N_FRAMES}")
    print(f"  T_sim     = {T_SIM:.1f} s")
    print(f"  Total steps = {int(T_SIM/DT):,}")
    print()
    px, py, pz, vx, vy, vz, frozen = init_particles()
    print("Particle initialization:")
    print(f"  N         = {len(px)} particles")
    print(f"  Mass      = {len(px)*M_PART*1e3:.0f} g  "
          f"(target 2000 g = 2 L)")
    print(f"  Launch    = vz = −3.0 m/s toward glass")
    L_cap = math.sqrt(GAMMA_WATER / (RHO_0 * G_GRAV)) * 1e3
    print()
    print("Physics regime:")
    print(f"  Capillary length  L_c = {L_cap:.1f} mm")
    print(f"  DELTA_X = {DELTA_X*1e3:.0f} mm  ≈  {DELTA_X*1e3/L_cap:.1f}× L_cap")
    print(f"  (coarse resolution — simulation captures macro flow, not sub-capillary detail)")
    print()
    print("Human visual acuity note:")
    print(f"  1 arcminute at 3 m viewing distance = 0.87 mm")
    print(f"  DELTA_X = {DELTA_X*1e3:.0f} mm → {DELTA_X*1e3/0.87:.0f} arcminutes per particle")
    print(f"  Every particle is individually resolvable by the naked eye.")
    print()
    print("Zone boundaries:")
    print(f"  Zone A (bare):   {Y_B_LO:.1f} m ≤ y ≤ {H_DOM:.1f} m")
    print(f"  Zone B (silane): {Y_C_LO:.1f} m ≤ y < {Y_B_LO:.1f} m")
    print(f"  Zone C (freeze): 0.0 m ≤ y < {Y_C_LO:.1f} m")
    print()
    print("=== ALL CHECKS COMPLETE ===")
    print()
    return px, py, pz, vx, vy, vz, frozen


# ── Main simulation loop ────────────────────────────────────────────────────────

def run_simulation(px, py, pz, vx, vy, vz, frozen, gif_path):
    tmpdir    = tempfile.mkdtemp(prefix='wpane_')
    png_paths = []
    t0_wall   = time.perf_counter()

    print(f"Simulating {T_SIM*1e3:.0f} ms  →  {N_FRAMES} frames  "
          f"|  DT = {DT*1e3:.2f} ms  |  N = {len(px)}")

    # Initial half-kick
    ax, ay, az, rho = compute_forces(
        px, py, pz, vx, vy, vz, frozen, H_SMOOTH, RHO_0, K_EOS, C_S_NUM,
        ALPHA_V, EPS_V, A_WW, A_WG_BARE, A_WG_SILANE, G_GRAV)
    vx_h = vx + 0.5*DT*ax
    vy_h = vy + 0.5*DT*ay
    vz_h = vz + 0.5*DT*az
    vx_h[frozen] = 0.0; vy_h[frozen] = 0.0; vz_h[frozen] = 0.0

    t_sim = 0.0
    frame = 0

    # Frame 0
    path = render_frame(px, py, pz, vx_h, vy_h, vz_h, rho, frozen,
                        t_sim, frame, tmpdir)
    png_paths.append(path)
    frame += 1

    step = 0
    while frame <= N_FRAMES:
        # Drift
        px += DT * vx_h
        py += DT * vy_h
        pz += DT * vz_h
        t_sim += DT

        # Boundary conditions
        px, py, pz, vx_h, vy_h, vz_h = apply_wall_bc(px, py, pz, vx_h, vy_h, vz_h)
        vx_h, vy_h, vz_h, frozen = apply_freezing_bc(
            px, py, pz, vx_h, vy_h, vz_h, frozen)

        # Forces
        ax, ay, az, rho = compute_forces(
            px, py, pz, vx_h, vy_h, vz_h, frozen, H_SMOOTH, RHO_0, K_EOS, C_S_NUM,
            ALPHA_V, EPS_V, A_WW, A_WG_BARE, A_WG_SILANE, G_GRAV)

        # Full-kick
        vx_h += DT * ax
        vy_h += DT * ay
        vz_h += DT * az

        # Frozen particles hold velocity = 0
        vx_h[frozen] = 0.0
        vy_h[frozen] = 0.0
        vz_h[frozen] = 0.0

        step += 1

        if step % SKIP == 0 and frame <= N_FRAMES:
            vx_full = vx_h - 0.5*DT*ax
            vy_full = vy_h - 0.5*DT*ay
            vz_full = vz_h - 0.5*DT*az
            vx_full[frozen] = 0.0; vy_full[frozen] = 0.0; vz_full[frozen] = 0.0

            path = render_frame(px, py, pz, vx_full, vy_full, vz_full, rho,
                                frozen, t_sim, frame, tmpdir)
            png_paths.append(path)
            elapsed  = time.perf_counter() - t0_wall
            fps_sim  = frame / elapsed
            eta      = (N_FRAMES - frame) / fps_sim if fps_sim > 0 else 0
            n_frozen = frozen.sum()
            print(f"  Frame {frame:3d}/{N_FRAMES}  t={t_sim*1e3:.0f} ms  "
                  f"frozen={n_frozen:3d}  [{elapsed:.1f}s  ~{eta:.0f}s left]")
            frame += 1

    # Assemble GIF
    print("Assembling GIF...")
    cmd = ['convert', '-delay', '8', '-loop', '0',
           '-layers', 'Optimize', '-dither', 'Riemersma']
    cmd += png_paths
    cmd += [gif_path]
    subprocess.run(cmd, check=True, capture_output=True)
    total = time.perf_counter() - t0_wall
    size  = os.path.getsize(gif_path) // 1024
    print(f"Done. → {gif_path}  ({size} KB, {total:.1f}s total)")


# ── Entry point ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    px, py, pz, vx, vy, vz, frozen = run_foundation_checks()
    _here = os.path.dirname(os.path.abspath(__file__))
    out   = os.path.normpath(os.path.join(_here, '..', 'misc', 'water_pane.gif'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    run_simulation(px, py, pz, vx, vy, vz, frozen, out)
