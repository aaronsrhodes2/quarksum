"""
render_physics_showcase.py — Three-row physics showcase render.

Demonstrates all three new local_library physics modules:
  Row 0 (bottom): Thermal emission — iron and blackbody at T = 300K→5778K
  Row 1 (middle): Semiconductor band gap — Si, Ge, GaP, CdS, diamond
  Row 2 (top):    Crystal field minerals — ruby, emerald, malachite, azurite, cobalt blue

Each sphere's color is DERIVED FROM PHYSICS:
  - Minerals: Tanabe-Sugano crystal field theory (Burns 1993)
  - Semiconductors: Varshni band gap + Fresnel 3-regime model
  - Thermal: Planck × Kirchhoff emissivity (no polynomial fit — exact)

"The atom tells the renderer what color it is."
□σ = −ξR
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.shapes import EntanglerSphere
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.render.red_carpet import red_carpet_render
from mattershaper.materials.material import Material
from mattershaper.materials.physics_materials import (
    crystal_field_mineral,
    semiconductor_material,
    glowing_material,
    iron,
)

# ── Scene geometry ─────────────────────────────────────────────────────────
# 5 spheres across, 3 rows up.
# Spacing: 2.2 units apart in X, 2.5 units apart in Y.
# Sphere radius: 0.85 units.

_RADIUS    = 0.85
_X_STEP    = 2.2
_Y_ROWS    = [0.0, 2.5, 5.0]   # thermal, semiconductor, mineral
_X_COLS    = [-4.4, -2.2, 0.0, 2.2, 4.4]
_S         = _RADIUS

def _sphere(col, row, mat):
    return EntanglerSphere(
        center=Vec3(_X_COLS[col], _Y_ROWS[row], 0.0),
        radius=_RADIUS,
        material=mat,
    )


# ── Row 0 — Thermal emission ────────────────────────────────────────────────
# Spheres show iron / blackbody at increasing temperatures.
# All colors from Planck × Kirchhoff. No hand-painting.
_cold_iron   = iron(T=300)                              # grey (room temp, no glow)
_iron_1000k  = glowing_material('iron',      T=1000.0)  # deep red
_iron_1500k  = glowing_material('iron',      T=1500.0)  # orange
_bb_3000k    = glowing_material('blackbody', T=3000.0)  # warm white
_bb_5778k    = glowing_material('blackbody', T=5778.0)  # solar white

thermal_row = [
    _sphere(0, 0, _cold_iron),
    _sphere(1, 0, _iron_1000k),
    _sphere(2, 0, _iron_1500k),
    _sphere(3, 0, _bb_3000k),
    _sphere(4, 0, _bb_5778k),
]


# ── Row 1 — Semiconductor band gap ─────────────────────────────────────────
# Colors from Varshni + 3-regime Fresnel model.
# No empirical fit — band gaps from spectroscopy, n+ik from Palik.
_mat_si   = semiconductor_material('silicon',           T=300.0)  # grey
_mat_ge   = semiconductor_material('germanium',         T=300.0)  # shiny grey
_mat_gap  = semiconductor_material('gallium_phosphide', T=300.0)  # amber
_mat_cds  = semiconductor_material('cadmium_sulfide',   T=300.0)  # yellow
_mat_diam = semiconductor_material('diamond',           T=300.0)  # colorless

semiconductor_row = [
    _sphere(0, 1, _mat_si),
    _sphere(1, 1, _mat_ge),
    _sphere(2, 1, _mat_gap),
    _sphere(3, 1, _mat_cds),
    _sphere(4, 1, _mat_diam),
]


# ── Row 2 — Crystal field minerals ─────────────────────────────────────────
# Colors from Tanabe-Sugano d-electron transitions.
# Ruby and emerald are both Cr³⁺ — different ligand fields, different colors.
_mat_ruby  = crystal_field_mineral('ruby')        # red — Cr³⁺ in corundum
_mat_emer  = crystal_field_mineral('emerald')     # green — Cr³⁺ in beryl
_mat_mal   = crystal_field_mineral('malachite')   # green-cyan — Cu²⁺ in carbonate
_mat_az    = crystal_field_mineral('azurite')     # blue — Cu²⁺ in azurite coord
_mat_cob   = crystal_field_mineral('cobalt_blue') # deep blue — Co²⁺ tetrahedral

mineral_row = [
    _sphere(0, 2, _mat_ruby),
    _sphere(1, 2, _mat_emer),
    _sphere(2, 2, _mat_mal),
    _sphere(3, 2, _mat_az),
    _sphere(4, 2, _mat_cob),
]


# ── All objects ─────────────────────────────────────────────────────────────
objects = thermal_row + semiconductor_row + mineral_row


# ── Light ───────────────────────────────────────────────────────────────────
# Three-point lighting: key (upper right), fill (left), rim (back-top)
light = PushLight(
    pos=Vec3(6.0, 9.0, 7.0),
    color=Vec3(1.0, 0.98, 0.92),
    intensity=1.5,
)


# ── Print material summary ──────────────────────────────────────────────────
print("\n  ── PHYSICS SHOWCASE MATERIALS ──────────────────────────────────────")
print(f"  {'Name':<28} {'R':>6} {'G':>6} {'B':>6}  {'Composition'}")
print("  " + "─" * 72)
for label, mat in [
    ('THERMAL EMISSION',          None),
    ('Iron (300K, cold)',          _cold_iron),
    ('Iron (1000K, dark red)',     _iron_1000k),
    ('Iron (1500K, orange)',       _iron_1500k),
    ('Blackbody (3000K)',          _bb_3000k),
    ('Blackbody (5778K, solar)',   _bb_5778k),
    ('SEMICONDUCTOR BAND GAP',    None),
    ('Silicon (Z=14)',             _mat_si),
    ('Germanium (Z=32)',           _mat_ge),
    ('GaP (band gap in visible)',  _mat_gap),
    ('CdS (yellow)',               _mat_cds),
    ('Diamond (Z=6, colorless)',   _mat_diam),
    ('CRYSTAL FIELD MINERALS',    None),
    ('Ruby (Cr³⁺/oxide)',          _mat_ruby),
    ('Emerald (Cr³⁺/silicate)',    _mat_emer),
    ('Malachite (Cu²⁺/carbonate)', _mat_mal),
    ('Azurite (Cu²⁺/azurite)',     _mat_az),
    ('Cobalt blue (Co²⁺/tet)',     _mat_cob),
]:
    if mat is None:
        print(f"\n  ── {label}")
    else:
        c = mat.color
        print(f"  {label:<28} {c.x:6.3f} {c.y:6.3f} {c.z:6.3f}  {mat.composition[:36]}")
print()


# ── Render ──────────────────────────────────────────────────────────────────
OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'triplestones', 'misc', 'physics_showcase.gif'
)
OUTPUT = os.path.abspath(OUTPUT)

t0 = time.time()
result = red_carpet_render(
    objects=objects,
    light=light,
    output_gif=OUTPUT,
    n_frames=12,
    density=240,
    width=700,
    height=480,
    fov=60.0,
    cam_dist=11.5,
    cam_height=4.5,
    look_at=Vec3(0.0, 2.5, 0.0),
    start_angle=0.05,
    fps=8,
    bg_color=Vec3(0.12, 0.12, 0.16),   # dark background → colors pop
    title='PHYSICS SHOWCASE  ♦  crystal field  ·  semiconductor  ·  thermal emission',
    counter_rotate=False,
    verbose=True,
)

print(f"\n  ✓ render complete: {result['n_frames']} frames in {result['total_time']:.1f}s")
print(f"  → {OUTPUT}")
print(f"  → {result['size_kb']:.0f} KB")
