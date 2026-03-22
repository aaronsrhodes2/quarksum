"""
Orrery Foam — Solar System Visualization.

Translucent orbital shells rendered via the MatterShaper Entangler.
Each planet's orbit is shown as a hollow glass sphere (n≈1.02) centred on
the Sun.  The planet rides on the equator of its shell.  Saturn carries a
torus ring system.

Physics of the shells
---------------------
An orbital shell is NOT the orbit itself — it is the locus of points at the
planet's semi-major axis.  The shell's equator (θ=0 great circle in the XZ
ecliptic plane) IS the orbit.  Viewing it from 25° elevation shows the shell
as a translucent oblate halo — you can see all nested shells through each other
because opacity ≈ 0.12.

Kepler time-stepper
-------------------
All orbits are circular (e=0) for the orrery visual.  Period T scales as T ∝ a^1.5
(Kepler's third law).  Angular position:

    θ(t) = 2π × t_yr / T_yr     (rad, measured from +X axis)
    x     = a_scene × cos(θ)
    z     = a_scene × sin(θ)
    y     = 0                    (ecliptic plane)

Scale
-----
Real AU values → scene units: a_scene = SCALE × sqrt(a_AU)
SCALE = 2.0 compresses the huge outer-planet distances into a legible view
while preserving the qualitative Kepler spacing.

    Mercury  0.387 AU → 1.24 scene
    Venus    0.723 AU → 1.70 scene
    Earth    1.000 AU → 2.00 scene
    Mars     1.524 AU → 2.47 scene
    Jupiter  5.203 AU → 4.56 scene
    Saturn   9.537 AU → 6.17 scene

Animation
---------
36 frames covering 3 Earth years (30 Earth-day steps per frame).
Camera orbits 360° at 25° elevation.  Saturn is visible from frame 1.
"""

import math
import os
import subprocess
import tempfile
import time

from mattershaper.render.entangler.engine import entangle, _write_ppm
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.render.entangler.shapes import (
    EntanglerSphere, EntanglerTorus, rotation_matrix,
)
from mattershaper.render.entangler.vec import Vec3
from mattershaper.materials.material import Material

# ── Scale ──────────────────────────────────────────────────────────────────────

SCALE = 2.0    # a_scene = SCALE × sqrt(a_AU)

def _au_to_scene(a_au):
    return SCALE * math.sqrt(a_au)


# ── Planetary data ─────────────────────────────────────────────────────────────
#   a_au:        semi-major axis [AU]
#   T_yr:        orbital period [Earth years]  — from Kepler: T = a^1.5
#   r_vis:       visual radius in scene units (exaggerated for legibility)
#   color:       Vec3 surface color
#   shell_color: Vec3 orbital shell tint (usually pale)
#   has_rings:   True for Saturn

PLANETS = [
    dict(
        name='Mercury',
        a_au=0.387, T_yr=0.387**1.5,
        r_vis=0.07,
        color=Vec3(0.55, 0.52, 0.50),          # iron-grey
        shell_color=Vec3(0.55, 0.60, 0.65),
        has_rings=False,
    ),
    dict(
        name='Venus',
        a_au=0.723, T_yr=0.723**1.5,
        r_vis=0.12,
        color=Vec3(0.90, 0.82, 0.58),          # pale gold-yellow
        shell_color=Vec3(0.72, 0.70, 0.55),
        has_rings=False,
    ),
    dict(
        name='Earth',
        a_au=1.000, T_yr=1.000,
        r_vis=0.13,
        color=Vec3(0.18, 0.45, 0.72),          # ocean blue
        shell_color=Vec3(0.35, 0.55, 0.75),
        has_rings=False,
    ),
    dict(
        name='Mars',
        a_au=1.524, T_yr=1.524**1.5,
        r_vis=0.10,
        color=Vec3(0.78, 0.38, 0.18),          # rust-red
        shell_color=Vec3(0.65, 0.45, 0.38),
        has_rings=False,
    ),
    dict(
        name='Jupiter',
        a_au=5.203, T_yr=5.203**1.5,
        r_vis=0.28,
        color=Vec3(0.80, 0.68, 0.52),          # tan-orange banded
        shell_color=Vec3(0.65, 0.58, 0.45),
        has_rings=False,
    ),
    dict(
        name='Saturn',
        a_au=9.537, T_yr=9.537**1.5,
        r_vis=0.24,
        color=Vec3(0.88, 0.82, 0.62),          # pale gold
        shell_color=Vec3(0.70, 0.65, 0.50),
        has_rings=True,
        ring_R=0.48,    # torus major radius (relative to planet centre)
        ring_r=0.06,    # torus minor radius (tube thickness)
        ring_color=Vec3(0.80, 0.74, 0.60),
    ),
]

# ── Materials ──────────────────────────────────────────────────────────────────

def _planet_mat(p):
    return Material(
        name=p['name'],
        color=p['color'],
        reflectance=0.12,
        roughness=0.55,
        opacity=1.0,
        emission=Vec3(0, 0, 0),
    )

def _shell_mat(p):
    """Translucent orbital shell — n≈1.02 glass (barely more than air)."""
    c = p['shell_color']
    # Scale tint down so it reads as a faint halo, not a coloured sphere
    tint = Vec3(0.70 + 0.30 * c.x, 0.70 + 0.30 * c.y, 0.70 + 0.30 * c.z)
    return Material(
        name=f"{p['name']}_shell",
        color=tint,
        reflectance=0.04,   # Fresnel at normal incidence for n=1.02
        roughness=0.10,
        opacity=0.11,       # very translucent — stacks of shells visible through each other
        emission=Vec3(0, 0, 0),
    )

def _ring_mat(p):
    return Material(
        name='saturn_rings',
        color=p['ring_color'],
        reflectance=0.25,
        roughness=0.70,
        opacity=0.65,
        emission=Vec3(0, 0, 0),
    )

SUN_MAT = Material(
    name='Sol',
    color=Vec3(1.0, 0.92, 0.60),
    reflectance=0.0,
    roughness=1.0,
    opacity=1.0,
    emission=Vec3(8.0, 7.2, 4.0),   # auto-light derivation uses this
)

# Sun is rebuilt each frame in build_scene() with density_override set.


# ── Kepler position ────────────────────────────────────────────────────────────

def _kepler_pos(a_scene, t_yr, T_yr):
    """Circular Keplerian orbit in the XZ ecliptic plane.

    θ(t) = 2π × t_yr / T_yr
    Returns Vec3(x, 0, z).
    """
    theta = 2.0 * math.pi * t_yr / T_yr
    return Vec3(a_scene * math.cos(theta), 0.0, a_scene * math.sin(theta))


# ── Scene builder ──────────────────────────────────────────────────────────────

# Tilt Saturn's rings 26.7° (actual axial tilt) around the Z axis for realism
_SATURN_RING_TILT = rotation_matrix(rx=math.radians(26.7), ry=0, rz=0)

SHELL_DENSITY  = 4     # orbital shells: large but translucent — 4 nodes/unit² is enough
PLANET_DENSITY = 120   # planet bodies: small but solid — need good coverage

def build_scene(t_yr):
    """Return list of all objects at time t_yr (Earth years)."""
    sun = EntanglerSphere(center=Vec3(0, 0, 0), radius=0.38, material=SUN_MAT)
    sun.density_override = PLANET_DENSITY
    objects = [sun]

    for p in PLANETS:
        a_scene = _au_to_scene(p['a_au'])
        pos     = _kepler_pos(a_scene, t_yr, p['T_yr'])

        # Orbital shell (hollow sphere centred on Sun) — low density
        shell = EntanglerSphere(
            center=Vec3(0, 0, 0),
            radius=a_scene,
            material=_shell_mat(p),
        )
        shell.density_override = SHELL_DENSITY
        objects.append(shell)

        # Planet body — high density
        planet = EntanglerSphere(
            center=pos,
            radius=p['r_vis'],
            material=_planet_mat(p),
        )
        planet.density_override = PLANET_DENSITY
        objects.append(planet)

        # Saturn's rings (torus centred on Saturn, tilted)
        if p.get('has_rings'):
            rings = EntanglerTorus(
                center=pos,
                R_major=p['ring_R'],
                r_minor=p['ring_r'],
                rotation=_SATURN_RING_TILT,
                material=_ring_mat(p),
            )
            rings.density_override = 40   # thin torus, moderate density
            objects.append(rings)

    return objects


# ── Render pipeline ────────────────────────────────────────────────────────────

N_FRAMES     = 36
DAYS_PER_STEP = 30          # 30 Earth days per frame
T_STEP_YR    = DAYS_PER_STEP / 365.25

WIDTH, HEIGHT = 600, 420
FOV          = 52
CAM_DIST     = 14.5
CAM_HEIGHT   = 5.5          # scene units above ecliptic
# Per-shape density is set in build_scene() via density_override.
# entangle() is called with density=1 as a fallback — all shapes override it.


LOOK_AT = Vec3(0, 0.5, 0)   # slightly above ecliptic centre

def _build_camera(angle_rad):
    """Orbital camera at fixed elevation, rotating around Y axis."""
    cx  = CAM_DIST * math.cos(angle_rad)
    cz  = CAM_DIST * math.sin(angle_rad)
    pos = Vec3(cx, CAM_HEIGHT, cz)
    return PushCamera(pos=pos, look_at=LOOK_AT, width=WIDTH, height=HEIGHT, fov=FOV)


def _render_frame(t_yr, cam_angle):
    """Render one frame, return W×H array of Vec3."""
    objects = build_scene(t_yr)
    cam     = _build_camera(cam_angle)
    bg      = Vec3(0.02, 0.02, 0.04)   # near-black space

    # Two-pass density: render shells at low density, planets at full density.
    # The entangle() call processes all objects together but we can pre-generate
    # nodes and call entangle with pre-built node lists — or, simpler, just set
    # a moderate DENSITY that works for both (shells are large, so even density=8
    # gives thousands of nodes per shell).
    #
    # We use the overloaded density approach: one call, density chosen so
    # planet spheres (~0.1 r) get ~80 × 4π × 0.01 ≈ 10 nodes minimum (too few).
    # So we override: planets added twice at high density, shells at low.
    # Simpler: just use density=DENSITY everywhere and accept that shells are
    # over-sampled (fast) and planets are decently sampled.  Render quality wins.

    pixels = entangle(objects, cam, density=1, bg_color=bg, shadows=False)
    return pixels


def _vec3_to_ppm_bytes(pixels):
    rows = []
    for row in pixels:
        r_bytes = []
        for px in row:
            r = max(0, min(255, int(px.x * 255)))
            g = max(0, min(255, int(px.y * 255)))
            b = max(0, min(255, int(px.z * 255)))
            r_bytes += [r, g, b]
        rows.append(bytes(r_bytes))
    header = f"P6\n{WIDTH} {HEIGHT}\n255\n".encode()
    return header + b''.join(rows)


def render_orrery_gif(output_path):
    """Render all frames and assemble into a GIF."""
    tmpdir = tempfile.mkdtemp(prefix='orrery_')
    png_paths = []

    t0 = time.perf_counter()
    print(f"Rendering {N_FRAMES} frames  |  {DAYS_PER_STEP} Earth-day steps  "
          f"|  {WIDTH}×{HEIGHT}  shells={SHELL_DENSITY}/planets={PLANET_DENSITY}")

    for i in range(N_FRAMES):
        t_yr    = i * T_STEP_YR
        cam_ang = 2.0 * math.pi * i / N_FRAMES + math.radians(15)

        frame_px = _render_frame(t_yr, cam_ang)

        ppm_path = os.path.join(tmpdir, f'frame_{i:03d}.ppm')
        png_path = os.path.join(tmpdir, f'frame_{i:03d}.png')

        ppm_data = _vec3_to_ppm_bytes(frame_px)
        with open(ppm_path, 'wb') as f:
            f.write(ppm_data)

        # Annotate: year + day label
        days_elapsed = i * DAYS_PER_STEP
        yr_label = f"t = {days_elapsed:4d} d  ({t_yr:.2f} yr)"
        subprocess.run([
            'convert', ppm_path,
            '-fill', 'white', '-font', 'DejaVu-Sans', '-pointsize', '11',
            '-gravity', 'SouthEast', '-annotate', '+8+6', yr_label,
            '-fill', 'white', '-pointsize', '10',
            '-gravity', 'SouthWest', '-annotate', '+8+6', 'ORRERY FOAM  |  θ = 1/φ²',
            png_path,
        ], check=True, capture_output=True)

        png_paths.append(png_path)

        elapsed = time.perf_counter() - t0
        fps = (i + 1) / elapsed
        remaining = (N_FRAMES - i - 1) / fps if fps > 0 else 0
        print(f"  Frame {i+1:2d}/{N_FRAMES}  t={t_yr:.2f} yr  "
              f"[{elapsed:.1f}s elapsed, ~{remaining:.0f}s remaining]")

    # Assemble GIF
    print("Assembling GIF...")
    cmd = ['convert', '-delay', '8', '-loop', '0',
           '-layers', 'Optimize', '-dither', 'Riemersma']
    cmd += png_paths
    cmd += [output_path]
    subprocess.run(cmd, check=True, capture_output=True)

    total = time.perf_counter() - t0
    size  = os.path.getsize(output_path) // 1024
    print(f"Done. → {output_path}  ({size} KB, {total:.1f}s)")


# ── Foundation checks ──────────────────────────────────────────────────────────

def run_foundation_checks():
    """Verify Kepler spacing and torus geometry before rendering."""
    print("=== ORRERY FOUNDATION CHECKS ===")
    print()
    print("Orbital radii (scene units, scale = 2√AU):")
    for p in PLANETS:
        a = _au_to_scene(p['a_au'])
        pos = _kepler_pos(a, 0.0, p['T_yr'])
        r   = math.sqrt(pos.x**2 + pos.z**2)
        print(f"  {p['name']:8s}  a_AU={p['a_au']:.3f}  a_scene={a:.3f}  "
              f"r_check={r:.3f}  T={p['T_yr']:.3f} yr")

    print()
    print("Kepler 3rd law check (T ∝ a^1.5):")
    for p in PLANETS:
        T_expected = p['a_au'] ** 1.5
        err = abs(p['T_yr'] - T_expected)
        print(f"  {p['name']:8s}  T_stored={p['T_yr']:.4f}  "
              f"a^1.5={T_expected:.4f}  Δ={err:.2e}  {'✓' if err < 1e-10 else '✗'}")

    print()
    print("Torus surface area check (Saturn rings):")
    saturn = next(p for p in PLANETS if p['name'] == 'Saturn')
    R, r = saturn['ring_R'], saturn['ring_r']
    area = 4.0 * math.pi**2 * R * r
    print(f"  R_major={R}  r_minor={r}  4π²Rr = {area:.4f} scene²")

    print()
    print("Shell opacity budget (stacked Porter-Duff):")
    op = 0.11
    remaining = 1.0
    for i, p in enumerate(PLANETS):
        remaining *= (1.0 - op)
        print(f"  After {i+1} shells ({p['name']:8s}):  remaining = {remaining:.4f}  "
              f"({100*remaining:.1f}% passes through)")

    print()
    print("=== ALL CHECKS COMPLETE ===")
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    run_foundation_checks()
    # Resolve misc/ relative to the quarksum project root, not __file__
    # (which may be relative when run from inside MatterShaper/)
    _here = os.path.dirname(os.path.abspath(__file__))   # MatterShaper/
    out   = os.path.normpath(os.path.join(_here, '..', 'misc', 'orrery_foam.gif'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    render_orrery_gif(out)
