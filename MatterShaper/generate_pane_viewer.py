"""
generate_pane_viewer.py — MatterShaper WebGL viewer, water on a 3m×3m pane.

Simulates 5 litres of water splashed from the TOP of the pane (Zone A = bare
glass, θ_c = 20°).  Water flows down through Zone B (silane-coated, θ_c = 110°)
and into Zone C (freezing zone, T < 0°C, drops freeze on contact).

Physics: identical to simulate_water_pane.py (WCSPH + Tartakovsky & Meakin 2005
pairwise cohesion + ghost-mirror wall adhesion).  See that file for full
REPLACED/OURS attribution.

Output: misc/water_pane_viewer.html — interactive Three.js WebGL viewer:
  · Water sphere shader: Fresnel (Schlick) + Snell refraction (n = 1.333)
    Refracted ray cast to pane at z=0, zone colour looked up, Beer-Lambert depth
  · Ice particle shader: n = 1.31, hash-perturbed normals (faceted look)
    Subsurface scattering approximation (internal cyan glow)
  · Candle light: 1800 K warm orange, animated multi-frequency flicker
  · Incandescent bulb: 3200 K warm white, steady
  · Mouse orbit control: drag=rotate  scroll=zoom  shift-drag=pan
  · Time-lapse scrubber + play / pause

Terminology note: "ray" in this codebase means exactly one thing — the photon
sightline from a surface point toward the camera.  In Mattershaper parlance we
now prefer the term "tangle" — the thread of light pulled from source to eye.
When you pull a tangle far enough apart, it breaks: beyond THETA_NATURAL = 1/φ²
of solid angle, the information at the far end is irrecoverable (Barnes-Hut
Claying applies equally to photon paths).  The glass-pane viewer traces tangles
from the camera into each water drop and then on to the pane.
"""

import math, os, time, json
import numpy as np

# ── Physical constants (MEASURED — one origin each) ─────────────────────────────
GAMMA_WATER  = 0.0728          # N/m   Vargaftik et al. (1983)
RHO_0        = 998.2           # kg/m³ CRC Handbook (20°C)
THETA_BARE   = math.radians(20.0)    # Erbil (2006) — clean glass
THETA_SILANE = math.radians(110.0)  # Bain, Evall & Whitesides (1989) — alkylsilane
G_GRAV       = 9.80665         # m/s²  BIPM

# ── SPH resolution ───────────────────────────────────────────────────────────────
DELTA_X  = 25.0e-3   # 25 mm
H_SMOOTH = 1.2 * DELTA_X
M_PART   = RHO_0 * DELTA_X**3

# ── WCSPH EOS ────────────────────────────────────────────────────────────────────
C_S_NUM = 30.0                 # m/s  NOT_PHYSICS (Mach < 0.1 criterion)
K_EOS   = RHO_0 * C_S_NUM**2

# ── Cohesion & adhesion (Tartakovsky & Meakin 2005) ──────────────────────────────
A_WW        = 8.0 * math.pi * GAMMA_WATER / (RHO_0**2 * H_SMOOTH**4)
A_WG_BARE   = A_WW * (1.0 + math.cos(THETA_BARE))   / 2.0
A_WG_SILANE = A_WW * (1.0 + math.cos(THETA_SILANE)) / 2.0

# ── Viscosity (Monaghan 1992, NOT_PHYSICS) ────────────────────────────────────────
ALPHA_V = 0.02
EPS_V   = 0.01

# ── Timestep (CFL) ───────────────────────────────────────────────────────────────
DT_SOUND = 0.25 * H_SMOOTH / C_S_NUM
DT_SURF  = 0.25 * math.sqrt(RHO_0 * H_SMOOTH**3 / (2.0*math.pi*GAMMA_WATER))
DT       = 0.9 * min(DT_SOUND, DT_SURF)

# ── Domain ───────────────────────────────────────────────────────────────────────
W_DOM = 3.0; H_DOM = 3.0; D_DOM = 0.5

# ── Zone boundaries ───────────────────────────────────────────────────────────────
Y_B_LO = 2.0   # bare / silane
Y_C_LO = 1.0   # silane / freezing

# ── Simulation ───────────────────────────────────────────────────────────────────
T_SIM    = 2.0
N_FRAMES = 60
SKIP     = max(1, int(T_SIM / N_FRAMES / DT))

# ── Splash (5 L from top — Zone A) ───────────────────────────────────────────────
V_WATER   = 5.0e-3
R_BLOB    = (3.0 * V_WATER / (4.0 * math.pi)) ** (1.0/3.0)
CX_SPLASH = W_DOM / 2.0   # 1.5 m centre
CY_SPLASH = 2.72           # near top of Zone A
CZ_SPLASH = 0.22           # 22 cm from glass

# ── Rendering radius (slightly larger than DELTA_X/2 for overlap) ─────────────────
R_RENDER = DELTA_X * 0.70   # 17.5 mm


# ── SPH kernels ──────────────────────────────────────────────────────────────────

def _W3(r, h):
    q = r / h; norm = 3.0 / (2.0 * math.pi * h**3)
    w = np.zeros_like(r)
    m1 = q < 1.; m2 = (q >= 1.) & (q < 2.)
    w[m1] = 2./3. - q[m1]**2 + .5*q[m1]**3
    w[m2] = (2.-q[m2])**3 / 6.
    return norm * w

def _gW3(dx, dy, dz, r, h):
    q = r / h; norm = 3.0 / (2.0 * math.pi * h**4)
    dWdq = np.zeros_like(r)
    m1 = q < 1.; m2 = (q >= 1.) & (q < 2.)
    dWdq[m1] = -2.*q[m1] + 1.5*q[m1]**2
    dWdq[m2] = -.5*(2.-q[m2])**2
    sr = np.where(r > 1e-15, r, 1.)
    fac = np.where(r > 1e-15, norm * dWdq / sr, 0.)
    return fac*dx, fac*dy, fac*dz

def _W3arr(r_arr, h):
    q = r_arr / h; norm = 3.0 / (2.0 * math.pi * h**3)
    w = np.zeros_like(q)
    m1 = q < 1.; m2 = (q >= 1.) & (q < 2.)
    w[m1] = 2./3. - q[m1]**2 + .5*q[m1]**3
    w[m2] = (2.-q[m2])**3 / 6.
    return norm * w


# ── Forces ───────────────────────────────────────────────────────────────────────

def compute_forces(px, py, pz, vx, vy, vz, frozen):
    N = len(px)
    dxij = px[:,None]-px[None,:]; dyij = py[:,None]-py[None,:]; dzij = pz[:,None]-pz[None,:]
    rij  = np.sqrt(dxij**2 + dyij**2 + dzij**2)
    nbr  = (rij > 0) & (rij < 2.*H_SMOOTH)
    W    = _W3(rij, H_SMOOTH)
    rho  = np.maximum(M_PART * np.sum(W, axis=1), 0.05 * RHO_0)
    P    = K_EOS * (rho/RHO_0 - 1.)
    gWx,gWy,gWz = _gW3(dxij,dyij,dzij,rij,H_SMOOTH)
    Pt   = np.where(nbr, P[:,None]/rho[:,None]**2 + P[None,:]/rho[None,:]**2, 0.)
    apx  = -M_PART * np.sum(Pt*gWx, axis=1)
    apy  = -M_PART * np.sum(Pt*gWy, axis=1)
    apz  = -M_PART * np.sum(Pt*gWz, axis=1)
    dvx=vx[:,None]-vx[None,:]; dvy=vy[:,None]-vy[None,:]; dvz=vz[:,None]-vz[None,:]
    vr   = dvx*dxij + dvy*dyij + dvz*dzij
    mu   = H_SMOOTH * vr / (rij**2 + EPS_V**2 * H_SMOOTH**2)
    Pi   = np.where((vr < 0) & nbr, -ALPHA_V*C_S_NUM*mu/.5/(rho[:,None]+rho[None,:]), 0.)
    avx  = -M_PART*np.sum(Pi*gWx,axis=1)
    avy  = -M_PART*np.sum(Pi*gWy,axis=1)
    avz  = -M_PART*np.sum(Pi*gWz,axis=1)
    sr   = np.where(rij > 1e-15, rij, 1.)
    cf   = np.where(nbr, A_WW*M_PART*np.where(nbr,W,0.)/sr, 0.)
    acx  = -np.sum(cf*dxij,axis=1)
    acy  = -np.sum(cf*dyij,axis=1)
    acz  = -np.sum(cf*dzij,axis=1)
    adz  = np.zeros(N)
    wm   = (pz < 2.*H_SMOOTH) & ~frozen
    if np.any(wm):
        rg  = np.maximum(2.*pz[wm], 1e-15)
        Wg  = _W3arr(rg, H_SMOOTH)
        yw  = py[wm]
        awg = np.where(yw >= Y_B_LO, A_WG_BARE,
              np.where(yw >= Y_C_LO, A_WG_SILANE, 0.))
        adz[wm] -= awg * M_PART * Wg
    ax = apx+avx+acx; ay = apy+avy+acy - G_GRAV; az = apz+avz+acz+adz
    ax[frozen]=0.; ay[frozen]=0.; az[frozen]=0.
    return ax, ay, az


# ── BCs ──────────────────────────────────────────────────────────────────────────

def apply_wall_bc(px, py, pz, vx, vy, vz):
    b = pz < 0
    pz = np.where(b,-pz*.35,pz); vz = np.where(b,-vz*.35,vz)
    lx = px<0;     px=np.where(lx,-px,px);          vx=np.where(lx,-vx,vx)
    rx = px>W_DOM; px=np.where(rx,2*W_DOM-px,px);   vx=np.where(rx,-vx,vx)
    ly = py<0;     py=np.where(ly,-py,py);           vy=np.where(ly,-vy,vy)
    ry = py>H_DOM; py=np.where(ry,2*H_DOM-py,py);   vy=np.where(ry,-vy,vy)
    fz = pz>D_DOM; pz=np.where(fz,2*D_DOM-pz,pz);  vz=np.where(fz,-vz,vz)
    return px,py,pz,vx,vy,vz

def apply_freezing_bc(px, py, pz, vx, vy, vz, frozen):
    nf = (pz < 2.*H_SMOOTH) & (py < Y_C_LO) & ~frozen
    frozen = frozen | nf
    vx[frozen]=0.; vy[frozen]=0.; vz[frozen]=0.
    return vx,vy,vz,frozen


# ── Particles ────────────────────────────────────────────────────────────────────

def init_particles():
    rng = np.random.default_rng(42)
    xs,ys,zs = [],[],[]
    ri = int(math.ceil(R_BLOB/DELTA_X))+1
    for ix in range(-ri,ri+1):
        for iy in range(-ri,ri+1):
            for iz in range(-ri,ri+1):
                x=CX_SPLASH+ix*DELTA_X; y=CY_SPLASH+iy*DELTA_X; z=CZ_SPLASH+iz*DELTA_X
                if (x-CX_SPLASH)**2+(y-CY_SPLASH)**2+(z-CZ_SPLASH)**2<=R_BLOB**2:
                    xs.append(x); ys.append(y); zs.append(z)
    N=len(xs); j=DELTA_X*.04
    px=np.clip(np.array(xs)+rng.uniform(-j,j,N),0.01,W_DOM-.01)
    py=np.clip(np.array(ys)+rng.uniform(-j,j,N),0.01,H_DOM-.01)
    pz=np.clip(np.array(zs)+rng.uniform(-j,j,N),0.001,D_DOM-.001)
    vx=rng.uniform(-1.,1.,N); vy=rng.uniform(-.5,.5,N); vz=np.full(N,-4.)
    return px,py,pz,vx,vy,vz,np.zeros(N,dtype=bool)


# ── Simulation loop ───────────────────────────────────────────────────────────────

def run_simulation():
    print("=== MatterShaper — generating WebGL viewer ===")
    px,py,pz,vx,vy,vz,frozen = init_particles()
    N=len(px)
    print(f"5L | DELTA_X={DELTA_X*1e3:.0f}mm | N={N} | "
          f"mass={N*M_PART*1e3:.0f}g | DT={DT*1e3:.3f}ms | SKIP={SKIP}")
    print(f"θ_c bare={math.degrees(math.acos(2*A_WG_BARE/A_WW-1)):.2f}° ✓  "
          f"silane={math.degrees(math.acos(2*A_WG_SILANE/A_WW-1)):.2f}° ✓")

    ax,ay,az = compute_forces(px,py,pz,vx,vy,vz,frozen)
    vxh=vx+.5*DT*ax; vyh=vy+.5*DT*ay; vzh=vz+.5*DT*az

    def _pack(t, px,py,pz,frozen):
        pos=[]
        for i in range(N):
            pos+=[round(float(px[i]),3),round(float(py[i]),3),round(float(pz[i]),3)]
        return {'t':round(t,4),'p':pos,'f':frozen.astype(int).tolist()}

    frames=[_pack(0.,px,py,pz,frozen)]
    frame=1; step=0; t_sim=0.
    t0=time.perf_counter()

    while frame<=N_FRAMES:
        px+=DT*vxh; py+=DT*vyh; pz+=DT*vzh; t_sim+=DT
        px,py,pz,vxh,vyh,vzh=apply_wall_bc(px,py,pz,vxh,vyh,vzh)
        vxh,vyh,vzh,frozen=apply_freezing_bc(px,py,pz,vxh,vyh,vzh,frozen)
        ax,ay,az=compute_forces(px,py,pz,vxh,vyh,vzh,frozen)
        vxh+=DT*ax; vyh+=DT*ay; vzh+=DT*az
        vxh[frozen]=0.; vyh[frozen]=0.; vzh[frozen]=0.
        step+=1
        if step%SKIP==0 and frame<=N_FRAMES:
            frames.append(_pack(t_sim,px,py,pz,frozen))
            elapsed=time.perf_counter()-t0
            print(f"  Frame {frame:2d}/{N_FRAMES}  t={t_sim*1e3:.0f}ms  "
                  f"frozen={frozen.sum():3d}  [{elapsed:.1f}s]")
            frame+=1

    print(f"Done: {time.perf_counter()-t0:.1f}s total")
    return frames, N


# ── HTML generation ───────────────────────────────────────────────────────────────

def generate_html(frames, N_particles):
    sim_json = json.dumps({'N': N_particles, 'R': R_RENDER,
                           'W': W_DOM, 'H': H_DOM, 'D': D_DOM,
                           'YBL': Y_B_LO, 'YCL': Y_C_LO,
                           'frames': frames},
                          separators=(',', ':'))

    WATER_VERT = r"""
attribute mat4 instanceMatrix;
varying vec3 vWorldPos;
varying vec3 vNormal;
void main() {
  mat4 iM = modelMatrix * instanceMatrix;
  vec4 wp = iM * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  vNormal = normalize(mat3(iM) * normal);
  gl_Position = projectionMatrix * viewMatrix * wp;
}"""

    WATER_FRAG = r"""
precision highp float;
uniform vec3 uCandlePos; uniform vec3 uCandleCol; uniform float uCandleInt;
uniform vec3 uBulbPos;   uniform vec3 uBulbCol;   uniform float uBulbInt;
varying vec3 vWorldPos;
varying vec3 vNormal;

vec3 zoneColor(float y) {
  if (y >= 2.0) return vec3(0.10, 0.20, 0.36);
  if (y >= 1.0) return vec3(0.24, 0.18, 0.07);
  return vec3(0.07, 0.18, 0.24);
}

vec3 ptSpec(vec3 N, vec3 V, vec3 wp, vec3 lp, vec3 lc, float li) {
  vec3 L = normalize(lp - wp);
  vec3 H = normalize(L + V);
  float d2 = max(dot(lp-wp, lp-wp), 0.04);
  return pow(max(dot(N,H),0.0), 96.0) * lc * li / d2;
}

void main() {
  vec3 N = normalize(vNormal);
  if (!gl_FrontFacing) N = -N;
  vec3 V = normalize(cameraPosition - vWorldPos);
  float NdV = max(dot(N,V), 0.0);

  // Schlick-Fresnel for water (n=1.333, F0=((1.333-1)/(1.333+1))^2=0.020)
  float fresnel = 0.020 + 0.980 * pow(1.0 - NdV, 5.0);

  // Snell refraction tangle (air→water, eta=1/1.333=0.7502)
  // A "tangle" is the photon sightline; beyond THETA_NATURAL it becomes paste.
  vec3 refDir = refract(-V, N, 0.7502);

  // Cast refracted tangle to pane (z=0 plane)
  vec3 refractColor = vec3(0.04, 0.09, 0.16);
  if (length(refDir) > 0.01 && refDir.z < -0.005) {
    float t = -vWorldPos.z / refDir.z;
    vec3 hit = vWorldPos + t * refDir;
    hit.x = clamp(hit.x, 0.0, 3.0);
    hit.y = clamp(hit.y, 0.0, 3.0);
    refractColor = zoneColor(hit.y);
    // Beer-Lambert: water absorbs red strongly, passes blue-green
    refractColor *= exp(-t * vec3(1.4, 0.6, 0.18));
    // Candle warms the refracted image slightly
    float cdist2 = max(dot(uCandlePos-hit, uCandlePos-hit), 0.1);
    refractColor += uCandleCol * uCandleInt * 0.003 / cdist2;
  }

  // Reflection tangles — pick up candle and room ambience
  vec3 reflDir = reflect(-V, N);
  float cangle = max(dot(reflDir, normalize(uCandlePos - vWorldPos)), 0.0);
  float bangle = max(dot(reflDir, normalize(uBulbPos   - vWorldPos)), 0.0);
  vec3 reflColor = vec3(0.015, 0.015, 0.03)
                 + 0.5 * pow(cangle, 24.0) * uCandleCol
                 + 0.3 * pow(bangle, 16.0) * uBulbCol;

  // Specular highlights from light sources
  vec3 spec = ptSpec(N, V, vWorldPos, uCandlePos, uCandleCol, uCandleInt*0.6)
            + ptSpec(N, V, vWorldPos, uBulbPos,   uBulbCol,   uBulbInt*0.5);

  // Zone-dependent tint on the drop itself
  float dropY = vWorldPos.y;
  vec3 zoneTint = (dropY>=2.0) ? vec3(0.88,0.94,1.00) :
                  (dropY>=1.0) ? vec3(1.00,0.96,0.90) : vec3(0.86,0.93,1.00);

  vec3 color = (mix(refractColor, reflColor, fresnel) + spec) * zoneTint;
  gl_FragColor = vec4(color, 0.80 + 0.18*fresnel);
}"""

    ICE_VERT = r"""
attribute mat4 instanceMatrix;
varying vec3 vWorldPos;
varying vec3 vNormal;
void main() {
  mat4 iM = modelMatrix * instanceMatrix;
  vec4 wp = iM * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  vNormal = normalize(mat3(iM) * normal);
  gl_Position = projectionMatrix * viewMatrix * wp;
}"""

    ICE_FRAG = r"""
precision highp float;
uniform vec3 uCandlePos; uniform vec3 uCandleCol; uniform float uCandleInt;
uniform vec3 uBulbPos;   uniform vec3 uBulbCol;   uniform float uBulbInt;
varying vec3 vWorldPos;
varying vec3 vNormal;

float h31(vec3 p) {
  return fract(sin(dot(p, vec3(127.1,311.7,74.7))) * 43758.5453);
}
float h31b(vec3 p) {
  return fract(sin(dot(p, vec3(269.5,183.3,246.1))) * 43758.5453);
}

vec3 ptSpec(vec3 N, vec3 V, vec3 wp, vec3 lp, vec3 lc, float li) {
  vec3 L = normalize(lp - wp);
  vec3 H = normalize(L + V);
  float d2 = max(dot(lp-wp, lp-wp), 0.04);
  return pow(max(dot(N,H),0.0),192.0) * lc * li / d2;
}

void main() {
  // Faceted normals — hash cells to simulate ice crystal faces
  vec3 cell = floor(vWorldPos * 28.0);
  vec3 perturb = normalize(vec3(h31(cell)-0.5, h31(cell+1.7)-0.5, h31b(cell)-0.5));
  vec3 N = normalize(vNormal + 0.35 * perturb);
  if (!gl_FrontFacing) N = -N;
  vec3 V = normalize(cameraPosition - vWorldPos);
  float NdV = max(dot(N,V), 0.0);

  // Fresnel for ice (n=1.31, F0=((1.31-1)/(1.31+1))^2=0.018)
  float fresnel = 0.018 + 0.982 * pow(1.0 - NdV, 5.0);

  // Refracted tangle (air→ice, eta=1/1.31=0.7634)
  vec3 refDir = refract(-V, N, 0.7634);
  vec3 refractColor = vec3(0.15, 0.28, 0.38);
  if (length(refDir) > 0.01 && refDir.z < -0.005) {
    float t = -vWorldPos.z / refDir.z;
    vec3 hit = vWorldPos + t * refDir;
    // Ice absorbs less than liquid water — passes more light
    refractColor = mix(vec3(0.5,0.75,0.85), vec3(0.15,0.35,0.45), min(t*2.0,1.0));
    // Candle warmth visible through ice
    float cdist2 = max(dot(uCandlePos-hit, uCandlePos-hit), 0.1);
    refractColor += uCandleCol * uCandleInt * 0.004 / cdist2;
  }

  // Subsurface scattering (blue-cyan glow from within ice)
  float sss = pow(1.0 - NdV, 2.0);
  vec3 subsurface = vec3(0.3, 0.65, 0.9) * sss * 0.35;

  // Reflection
  vec3 reflDir = reflect(-V, N);
  float cangle = max(dot(reflDir, normalize(uCandlePos-vWorldPos)), 0.0);
  vec3 reflColor = vec3(0.02, 0.02, 0.04) + 0.6*pow(cangle,32.0)*uCandleCol;

  // Specular highlights (ice is shiny)
  vec3 spec = ptSpec(N,V,vWorldPos,uCandlePos,uCandleCol,uCandleInt*0.9)
            + ptSpec(N,V,vWorldPos,uBulbPos,  uBulbCol,  uBulbInt*0.7);

  vec3 iceBase = mix(refractColor, reflColor, fresnel) + subsurface;
  // Ice tint: blue-white
  iceBase = mix(iceBase, vec3(0.65,0.85,1.0), 0.25);
  vec3 color = iceBase + spec;

  gl_FragColor = vec4(color, 0.88 + 0.10*fresnel);
}"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MatterShaper — Water on Pane</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#010106; overflow:hidden; font-family:monospace; color:#90b8d8; }}
#c {{ display:block; width:100vw; height:100vh; cursor:grab; }}
#c:active {{ cursor:grabbing; }}
#ui {{
  position:absolute; bottom:0; left:0; right:0;
  background:linear-gradient(transparent, rgba(2,4,12,0.92));
  padding:14px 20px 18px; user-select:none;
}}
#title {{
  position:absolute; top:14px; left:20px;
  font-size:13px; color:#6090b0; letter-spacing:1px;
}}
#info {{
  position:absolute; top:40px; left:20px;
  font-size:11px; color:#3a5570; line-height:1.6;
}}
#controls {{ display:flex; align-items:center; gap:14px; }}
#playBtn {{
  width:36px; height:36px; border:1px solid #2a4860; border-radius:4px;
  background:#0a1520; color:#80b0d0; cursor:pointer; font-size:16px;
  display:flex; align-items:center; justify-content:center;
}}
#playBtn:hover {{ background:#142030; color:#c0e0ff; }}
#slider {{
  flex:1; height:4px; -webkit-appearance:none; appearance:none;
  background:#0d1e2e; border-radius:2px; outline:none; cursor:pointer;
}}
#slider::-webkit-slider-thumb {{
  -webkit-appearance:none; width:14px; height:14px; border-radius:50%;
  background:#4488cc; cursor:pointer;
}}
#timeLabel {{ font-size:11px; color:#5080a0; min-width:70px; text-align:right; }}
#stats {{
  position:absolute; top:0; right:20px;
  font-size:10px; color:#2a4060; text-align:right; line-height:1.8;
}}
.legend {{ display:flex; gap:20px; margin-top:6px; }}
.litem {{ display:flex; align-items:center; gap:6px; font-size:10px; color:#3a5570; }}
.lswatch {{ width:10px; height:10px; border-radius:50%; }}
</style>
</head>
<body>
<canvas id="c"></canvas>

<div id="title">MATTERSHAPER · WATER ON GLASS PANE · 5 L · THREE ZONES</div>
<div id="info">
  drag to orbit · scroll to zoom · shift+drag to pan
</div>
<div id="stats">
  Zone A: bare glass θ=20°<br>
  Zone B: silane θ=110°<br>
  Zone C: T&lt;0°C  freeze<br>
  n_water=1.333 · n_ice=1.31
</div>

<div id="ui">
  <div class="legend">
    <div class="litem"><div class="lswatch" style="background:#4488cc"></div>free water</div>
    <div class="litem"><div class="lswatch" style="background:#88ddff"></div>frozen ice</div>
    <div class="litem"><div class="lswatch" style="background:#ff8800"></div>candle 1800K</div>
    <div class="litem"><div class="lswatch" style="background:#ffe8c0"></div>bulb 3200K</div>
  </div>
  <div id="controls" style="margin-top:8px;">
    <button id="playBtn">▶</button>
    <input id="slider" type="range" min="0" max="{N_FRAMES}" value="0" step="1">
    <span id="timeLabel">t = 0.000 s</span>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
// ── Simulation data ─────────────────────────────────────────────────────────────
const SIM = {sim_json};

// ── Renderer ────────────────────────────────────────────────────────────────────
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{canvas, antialias:true, alpha:false}});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = false;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.3;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x010208);
scene.fog = new THREE.FogExp2(0x010208, 0.14);

const camera = new THREE.PerspectiveCamera(52, window.innerWidth/window.innerHeight, 0.005, 30);
window.addEventListener('resize', () => {{
  camera.aspect = window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}});

// ── Orbit control ────────────────────────────────────────────────────────────────
const orbit = {{ theta:0.22, phi:1.20, r:5.8, cx:1.5, cy:1.5, cz:0, drag:false, shift:false, lx:0, ly:0 }};
canvas.addEventListener('mousedown', e => {{ orbit.drag=true; orbit.shift=e.shiftKey; orbit.lx=e.clientX; orbit.ly=e.clientY; }});
window.addEventListener('mouseup',   () => orbit.drag=false);
window.addEventListener('mousemove', e => {{
  if (!orbit.drag) return;
  const dx=(e.clientX-orbit.lx)/window.innerWidth;
  const dy=(e.clientY-orbit.ly)/window.innerHeight;
  if (orbit.shift) {{
    orbit.cx -= dx * orbit.r * 0.8;
    orbit.cy += dy * orbit.r * 0.8;
  }} else {{
    orbit.theta -= dx * Math.PI * 2.2;
    orbit.phi = Math.max(0.04, Math.min(Math.PI-0.04, orbit.phi + dy*Math.PI*1.2));
  }}
  orbit.lx=e.clientX; orbit.ly=e.clientY;
}});
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  orbit.r = Math.max(0.4, Math.min(14, orbit.r*(1+e.deltaY*0.0008)));
}}, {{passive:false}});
// Touch support
canvas.addEventListener('touchstart', e => {{ const t=e.touches[0]; orbit.drag=true; orbit.lx=t.clientX; orbit.ly=t.clientY; }}, {{passive:true}});
canvas.addEventListener('touchend',   () => orbit.drag=false, {{passive:true}});
canvas.addEventListener('touchmove',  e => {{
  if (!orbit.drag) return;
  const t=e.touches[0];
  const dx=(t.clientX-orbit.lx)/window.innerWidth, dy=(t.clientY-orbit.ly)/window.innerHeight;
  orbit.theta -= dx*Math.PI*2; orbit.phi=Math.max(0.04,Math.min(Math.PI-0.04,orbit.phi+dy*Math.PI));
  orbit.lx=t.clientX; orbit.ly=t.clientY;
}}, {{passive:true}});

function updateCamera() {{
  const o=orbit;
  camera.position.set(
    o.cx + o.r*Math.sin(o.phi)*Math.sin(o.theta),
    o.cy + o.r*Math.cos(o.phi),
    o.cz + o.r*Math.sin(o.phi)*Math.cos(o.theta)
  );
  camera.lookAt(o.cx, o.cy, o.cz);
}}

// ── Lights ──────────────────────────────────────────────────────────────────────
const ambient = new THREE.AmbientLight(0x0d1525, 1.0);
scene.add(ambient);

// Candle: warm orange 1800 K → CIE approximation RGB
const CANDLE_POS   = new THREE.Vector3(0.35, 0.22, 0.65);
const CANDLE_COL   = new THREE.Color(1.0, 0.42, 0.06);
const CANDLE_BASE  = 9.0;
const candleLight  = new THREE.PointLight(CANDLE_COL, CANDLE_BASE, 4.5, 2.0);
candleLight.position.copy(CANDLE_POS);
scene.add(candleLight);

// Incandescent bulb: warm white 3200 K → RGB
const BULB_POS   = new THREE.Vector3(2.65, 3.35, 0.85);
const BULB_COL   = new THREE.Color(1.0, 0.80, 0.52);
const BULB_INT   = 7.0;
const bulbLight  = new THREE.PointLight(BULB_COL, BULB_INT, 6.0, 2.0);
bulbLight.position.copy(BULB_POS);
scene.add(bulbLight);

// ── Candle geometry ──────────────────────────────────────────────────────────────
(function buildCandle() {{
  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.022, 0.14, 10),
    new THREE.MeshStandardMaterial({{color:0xfff0c0, roughness:0.7}})
  );
  body.position.copy(CANDLE_POS).add(new THREE.Vector3(0,-0.065,0));
  scene.add(body);

  const flameMat = new THREE.MeshBasicMaterial({{color:0xff9922, transparent:true, opacity:0.92}});
  const flame = new THREE.Mesh(new THREE.ConeGeometry(0.012,0.055,8), flameMat);
  flame.position.copy(CANDLE_POS).add(new THREE.Vector3(0,0.028,0));
  scene.add(flame);

  // Glow halo (sprite-like sphere)
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(0.05, 8, 6),
    new THREE.MeshBasicMaterial({{color:0xff8800, transparent:true, opacity:0.18, depthWrite:false}})
  );
  halo.position.copy(CANDLE_POS);
  scene.add(halo);

  // Animate flicker in loop
  candleLight._flame = flame;
  candleLight._halo  = halo;
}})();

// ── Bulb geometry ────────────────────────────────────────────────────────────────
(function buildBulb() {{
  const bulbMesh = new THREE.Mesh(
    new THREE.SphereGeometry(0.035, 12, 8),
    new THREE.MeshBasicMaterial({{color:0xffe8c0}})
  );
  bulbMesh.position.copy(BULB_POS);
  scene.add(bulbMesh);

  const glow = new THREE.Mesh(
    new THREE.SphereGeometry(0.08, 8, 6),
    new THREE.MeshBasicMaterial({{color:0xffd090, transparent:true, opacity:0.12, depthWrite:false}})
  );
  glow.position.copy(BULB_POS);
  scene.add(glow);
}})();

// ── Zone texture for pane ────────────────────────────────────────────────────────
const zoneCanvas = document.createElement('canvas');
zoneCanvas.width = 4; zoneCanvas.height = 768;
const ztx = zoneCanvas.getContext('2d');
// Zone C (bottom, y<1 → texture V 0..0.333 → pixels 512..768)
ztx.fillStyle = '#0a1520'; ztx.fillRect(0, 512, 4, 256);
// Zone B (middle, y 1..2 → pixels 256..512)
ztx.fillStyle = '#1c1408'; ztx.fillRect(0, 256, 4, 256);
// Zone A (top, y 2..3 → pixels 0..256)
ztx.fillStyle = '#0c1828'; ztx.fillRect(0,   0, 4, 256);
// Boundary lines
ztx.fillStyle = '#223348'; ztx.fillRect(0, 255, 4, 2);
ztx.fillStyle = '#223348'; ztx.fillRect(0, 511, 4, 2);
const zoneTex = new THREE.CanvasTexture(zoneCanvas);
zoneTex.wrapS = THREE.ClampToEdgeWrapping;
zoneTex.wrapT = THREE.ClampToEdgeWrapping;

// ── Glass pane ───────────────────────────────────────────────────────────────────
const paneMat = new THREE.MeshPhysicalMaterial({{
  map: zoneTex,
  transparent: true, opacity: 0.82,
  roughness: 0.04, metalness: 0.0,
  side: THREE.DoubleSide,
  depthWrite: false,
}});
const pane = new THREE.Mesh(new THREE.PlaneGeometry(SIM.W, SIM.H), paneMat);
pane.position.set(SIM.W/2, SIM.H/2, 0);
scene.add(pane);

// Pane edge frame (thin box outline)
const edgeMat = new THREE.LineBasicMaterial({{color:0x224466, transparent:true, opacity:0.4}});
const edgeGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(SIM.W, SIM.H, 0.001));
const edgeFrame = new THREE.LineSegments(edgeGeo, edgeMat);
edgeFrame.position.copy(pane.position);
scene.add(edgeFrame);

// Zone separator lines
const sepMat = new THREE.LineBasicMaterial({{color:0x2244aa, transparent:true, opacity:0.5}});
[[SIM.YBL],[SIM.YCL]].forEach(([y]) => {{
  const pts = [new THREE.Vector3(0,y,0.001), new THREE.Vector3(SIM.W,y,0.001)];
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), sepMat));
}});

// ── Particle meshes (InstancedMesh) ──────────────────────────────────────────────
const uCandlePos = new THREE.Uniform(CANDLE_POS);
const uCandleCol = new THREE.Uniform(new THREE.Vector3(CANDLE_COL.r, CANDLE_COL.g, CANDLE_COL.b));
const uCandleInt = new THREE.Uniform(CANDLE_BASE);
const uBulbPos   = new THREE.Uniform(BULB_POS);
const uBulbCol   = new THREE.Uniform(new THREE.Vector3(BULB_COL.r, BULB_COL.g, BULB_COL.b));
const uBulbInt   = new THREE.Uniform(BULB_INT);

const sharedUniforms = {{
  uCandlePos, uCandleCol, uCandleInt,
  uBulbPos,   uBulbCol,   uBulbInt,
}};

const waterMat = new THREE.ShaderMaterial({{
  vertexShader:   {json.dumps(WATER_VERT)},
  fragmentShader: {json.dumps(WATER_FRAG)},
  uniforms: sharedUniforms,
  transparent: true,
  depthWrite: false,
  side: THREE.FrontSide,
}});

const iceMat = new THREE.ShaderMaterial({{
  vertexShader:   {json.dumps(ICE_VERT)},
  fragmentShader: {json.dumps(ICE_FRAG)},
  uniforms: sharedUniforms,
  transparent: true,
  depthWrite: false,
  side: THREE.FrontSide,
}});

const sphereGeo = new THREE.SphereGeometry(1, 14, 10);
const N = SIM.N;
const waterMesh = new THREE.InstancedMesh(sphereGeo, waterMat, N);
const iceMesh   = new THREE.InstancedMesh(sphereGeo, iceMat,   N);
waterMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
iceMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
waterMesh.count = 0; iceMesh.count = 0;
scene.add(waterMesh); scene.add(iceMesh);

// ── Frame update ─────────────────────────────────────────────────────────────────
const dummy = new THREE.Object3D();
let currentFrame = 0;

function setFrame(fi) {{
  currentFrame = Math.max(0, Math.min(SIM.frames.length-1, fi));
  const frame = SIM.frames[currentFrame];
  const pos = frame.p;
  const frz = frame.f;
  let wi=0, ii=0;
  for (let i=0; i<N; i++) {{
    dummy.position.set(pos[3*i], pos[3*i+1], pos[3*i+2]);
    dummy.scale.setScalar(SIM.R);
    dummy.updateMatrix();
    if (frz[i]) iceMesh.setMatrixAt(ii++, dummy.matrix);
    else         waterMesh.setMatrixAt(wi++, dummy.matrix);
  }}
  waterMesh.count=wi; iceMesh.count=ii;
  waterMesh.instanceMatrix.needsUpdate=true;
  iceMesh.instanceMatrix.needsUpdate=true;

  document.getElementById('timeLabel').textContent = `t = ${{frame.t.toFixed(3)}} s`;
  document.getElementById('stats').innerHTML =
    `Zone A: bare glass θ=20°<br>Zone B: silane θ=110°<br>Zone C: T&lt;0°C  freeze<br>` +
    `n_water=1.333 · n_ice=1.31<br>` +
    `free=${{wi}}  frozen=${{ii}}  N=${{N}}`;
}}
setFrame(0);

// ── Playback ─────────────────────────────────────────────────────────────────────
let playing=false, lastFrameTime=0, simFrameRate=30;
const playBtn  = document.getElementById('playBtn');
const slider   = document.getElementById('slider');
slider.max = SIM.frames.length - 1;

playBtn.addEventListener('click', () => {{
  playing = !playing;
  playBtn.textContent = playing ? '⏸' : '▶';
  lastFrameTime = performance.now();
}});
slider.addEventListener('input', () => {{
  setFrame(parseInt(slider.value));
}});

// ── Animation loop ────────────────────────────────────────────────────────────────
const clock = new THREE.Clock();
function animate() {{
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  // Candle flicker (multi-frequency sinusoids — like actual candle turbulence)
  const flicker = 0.70 + 0.30*(0.55*Math.sin(t*7.3) + 0.30*Math.sin(t*11.7+1.2) + 0.15*Math.sin(t*23.4+2.9));
  candleLight.intensity = CANDLE_BASE * flicker;
  uCandleInt.value = CANDLE_BASE * flicker;
  if (candleLight._flame) {{
    candleLight._flame.scale.y = 0.75 + 0.5*flicker;
    candleLight._flame.material.opacity = 0.80 + 0.18*flicker;
    candleLight._flame.position.y = CANDLE_POS.y + 0.025 + 0.008*flicker;
  }}
  if (candleLight._halo) {{
    candleLight._halo.material.opacity = 0.12 + 0.10*flicker;
  }}

  // Playback advance
  if (playing) {{
    const now = performance.now();
    if (now - lastFrameTime > 1000/simFrameRate) {{
      lastFrameTime = now;
      const next = currentFrame+1;
      if (next >= SIM.frames.length) {{ playing=false; playBtn.textContent='▶'; }}
      else {{ setFrame(next); slider.value=currentFrame; }}
    }}
  }}

  updateCamera();
  renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>"""
    return html


# ── Main ──────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    frames, N = run_simulation()
    html = generate_html(frames, N)
    _here = os.path.dirname(os.path.abspath(__file__))
    out   = os.path.normpath(os.path.join(_here, '..', 'misc', 'water_pane_viewer.html'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        f.write(html)
    size_kb = os.path.getsize(out) // 1024
    print(f"\nWritten: {out}  ({size_kb} KB)")
    print("Open in a browser — drag to orbit, scroll to zoom, shift+drag to pan")
    print("Tangle refraction: Snell's law (n=1.333 water, n=1.31 ice)")
    print("Two light sources: candle 1800K (flickering) + bulb 3200K (steady)")
