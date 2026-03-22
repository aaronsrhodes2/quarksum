"""
render_skippy.py — Skippy the Magnificent, Admiral of the Infinite.

Renders a full 360° horizontal rotation as an animated GIF.
Pure Entangler push rendering. No ray tracer. Matter speaks for itself.

Materials are DERIVED FROM QUARKSUM ATOMS — no string keys:
  - Body: quarksum Al atom (Z=13) → Drude + Palik → silver
  - Trim: quarksum Au atom (Z=79) → Drude + JC72 → gold
  - Neck: quarksum Fe atom (Z=26) → Drude + Palik → dark grey
  - Admiral coat: wool + admiralty blue dye (compound-level, no atom yet)
  - Hat: black felt (compound-level, no atom yet)

The atom tells the renderer what color it is.
The rendering is a side-effect of what the atom IS.

"The quark pixels fire from the outside."
"""

import sys
import os
import math
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.shapes import (
    EntanglerSphere, EntanglerEllipsoid, rotation_matrix, IDENTITY,
)
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.render.red_carpet import red_carpet_render
from mattershaper.materials.material import Material
from mattershaper.materials.physics_materials import (
    material_from_atom,          # ← unified atom-sourced factory
    dyed_wool, wool_natural, felt,  # compound materials (no atom yet)
)

# ── Load quarksum Atom objects ────────────────────────────────────────────
# These are real atoms from the quarksum element database.
# atomic_number (Z) IS the material specification — no name string needed.
try:
    from quarksum.data.loader import ElementDB
    from quarksum.models.atom import Atom as QAtom

    _db = ElementDB.get()
    _atom_Al = QAtom.create(_db.by_symbol('Al'))   # Z=13: aluminum
    _atom_Au = QAtom.create(_db.by_symbol('Au'))   # Z=79: gold
    _atom_Fe = QAtom.create(_db.by_symbol('Fe'))   # Z=26: iron

    # Material from atom — the cascade runs from Z, not from a name string
    _Al   = material_from_atom(_atom_Al)   # Z=13 → Drude+Palik → silver
    _Gold = material_from_atom(_atom_Au)   # Z=79 → Drude+JC72 → gold
    _Iron = material_from_atom(_atom_Fe)   # Z=26 → Drude+Palik → dark grey

    _ATOM_SOURCED = True

except Exception as _e:
    # Fallback to named factories if quarksum not available
    import warnings
    warnings.warn(f"Atom-sourced materials failed ({_e}), using named fallbacks.")
    from mattershaper.materials.physics_materials import aluminum, gold, iron
    _Al   = aluminum()
    _Gold = gold()
    _Iron = iron()
    _ATOM_SOURCED = False

# Compound materials — these remain name-keyed until organic/molecular
# orbital theory is in local_library. Honest about the gap.
_Navy = dyed_wool('admiralty_blue')  # keratin + indigo+iron mordant: navy RGB(0.28, 0.27, 0.68)
_Felt = felt('black_iron')           # keratin + carbon black: near-black RGB(0.04, 0.04, 0.04)
_Wool = wool_natural()               # undyed keratin: cream RGB(0.82, 0.78, 0.68)

# Convert from geometry Vec3 → entangler Vec3 (same API, explicit conversion for clarity)
def _cv(c): return Vec3(c.x, c.y, c.z)

def _mat(phys_mat, name=None):
    """Wrap a physics Material for use in the Entangler."""
    return Material(
        name=name or phys_mat.name,
        color=_cv(phys_mat.color),
        reflectance=phys_mat.reflectance,
        roughness=phys_mat.roughness,
        density_kg_m3=phys_mat.density_kg_m3,
        mean_Z=phys_mat.mean_Z,
        mean_A=phys_mat.mean_A,
        composition=phys_mat.composition,
    )

# ── Materials used in the model ───────────────────────────────────────────
# PHYSICS-DERIVED (from local_library.interface.optics + texture):
white_body  = _mat(_Al,   'Aluminum body')    # beer-can body: aluminum
blue_coat   = _mat(_Navy, 'Admiral coat')     # wool + admiralty blue dye
blue_hat    = _mat(_Felt, 'Felt hat')         # black felt
yellow_trim = _mat(_Gold, 'Gold trim')        # gold buttons and braid
front_panel = _mat(_Navy, 'Front panel')      # same wool as coat

# NOT YET PHYSICS-DERIVED (organic/glass — pending organic chemistry module):
# These retain hand-specified colors until the organic optics module exists.
def Mx(name, r, g, b, refl=0.10, rough=0.50, Z=8, A=16, rho=1200):
    return Material(name=name, color=Vec3(r, g, b),
                    reflectance=refl, roughness=rough,
                    density_kg_m3=rho, mean_Z=Z, mean_A=A,
                    composition=name)

dark_visor  = Mx('Visor (glass)',  0.06, 0.06, 0.12, refl=0.45, rough=0.05, Z=14, A=28, rho=2500)
eye_white   = _mat(_Al, 'Eye dome (Al)')      # aluminum dome eyes
eye_blue    = Mx('Iris (pigment)', 0.18, 0.44, 0.96, refl=0.45, rough=0.06)
pupil_black = Mx('Pupil (absorber)', 0.04, 0.04, 0.08, refl=0.10, rough=0.20)
red_mouth   = Mx('Mouth (painted Al)', 0.88, 0.10, 0.10, refl=0.12, rough=0.40, Z=13, A=27, rho=2700)
teeth_white = _mat(_Al, 'Teeth (Al)')
grey_neck   = _mat(_Iron, 'Neck (iron)')      # iron-grey mechanical neck
light_green = Mx('Green LED', 0.08, 0.96, 0.30, refl=0.35, rough=0.05)
light_amber = Mx('Amber LED', 0.98, 0.55, 0.08, refl=0.35, rough=0.05)
hat_badge_y = _mat(_Gold, 'Badge (gold)')
hat_badge_b = _mat(_Navy, 'Badge (navy)')
floor_mat   = Mx('Floor (granite)', 0.62, 0.60, 0.59, refl=0.06, rough=0.88, Z=12, A=24, rho=2700)


# ── Shape helpers ─────────────────────────────────────────────────────────

def Sp(cx, cy, cz, r, mat):
    return EntanglerSphere(center=Vec3(cx, cy, cz), radius=r, material=mat)

def El(cx, cy, cz, rx, ry, rz, mat, rot=(0, 0, 0)):
    R = rotation_matrix(*rot) if any(rot) else IDENTITY
    return EntanglerEllipsoid(
        center=Vec3(cx, cy, cz), radii=Vec3(rx, ry, rz),
        rotation=R, material=mat)


# ── Build Skippy ──────────────────────────────────────────────────────────

print("Building Skippy the Magnificent...")
objects = []

# Floor / pedestal
objects.append(El(0, -0.06, -0.5,   2.4, 0.065, 2.0, floor_mat))

# Body / coat
objects.append(El(0,  1.25,  0.00,  0.74, 0.92, 0.62, blue_coat))
objects.append(El(0,  1.30,  0.46,  0.36, 0.78, 0.10, front_panel))

# Yellow buttons (front column)
for yi in [2.00, 1.72, 1.44, 1.16, 0.88]:
    objects.append(Sp(0, yi, 0.53, 0.068, yellow_trim))

# Shoulder epaulette dots
for (dx, dy, dz) in [
    (-0.70, 2.00, 0.18), (-0.76, 1.84, 0.12), (-0.66, 2.10, 0.28),
    ( 0.70, 2.00, 0.18), ( 0.76, 1.84, 0.12), ( 0.66, 2.10, 0.28),
]:
    objects.append(Sp(dx, dy, dz, 0.063, yellow_trim))

# Neck
objects.append(El(0, 2.20, 0.08,    0.22, 0.26, 0.20, grey_neck))

# Head (big round white dome)
objects.append(Sp(0, 3.00, 0.00,    0.74, white_body))

# Face visor
objects.append(El(0, 2.90, 0.60,    0.54, 0.44, 0.10, dark_visor))

# Eyes (left & right from camera front)
objects.append(Sp(-0.20, 2.96, 0.68, 0.178, eye_white))
objects.append(Sp(-0.18, 2.97, 0.79, 0.118, eye_blue))
objects.append(Sp(-0.17, 2.97, 0.86, 0.056, pupil_black))
objects.append(Sp( 0.20, 2.96, 0.68, 0.178, eye_white))
objects.append(Sp( 0.18, 2.97, 0.79, 0.118, eye_blue))
objects.append(Sp( 0.17, 2.97, 0.86, 0.056, pupil_black))

# Nose + mouth
objects.append(Sp(0, 2.77, 0.74,    0.074, red_mouth))
objects.append(El(0, 2.58, 0.70,    0.29, 0.105, 0.068, red_mouth))
objects.append(El(0, 2.63, 0.75,    0.22, 0.056, 0.050, teeth_white))

# Ear panels + LED indicators
objects.append(El(-0.74, 2.92, 0.15, 0.045, 0.24, 0.20, grey_neck))
objects.append(El( 0.74, 2.92, 0.15, 0.045, 0.24, 0.20, grey_neck))
objects.append(Sp(-0.78, 3.03, 0.16, 0.046, light_green))
objects.append(Sp( 0.78, 3.03, 0.16, 0.046, light_green))
objects.append(Sp(-0.78, 2.82, 0.16, 0.036, light_amber))
objects.append(Sp( 0.78, 2.82, 0.16, 0.036, light_amber))

# Left arm (out to side / down)
objects.append(El(-0.90, 1.52, 0.10, 0.24, 0.54, 0.22, blue_coat, rot=(0, 0, 0.28)))
objects.append(Sp(-1.04, 1.14, 0.20, 0.22, white_body))

# Right arm (raised — pointing up!)
objects.append(El(0.84, 2.08, 0.14,  0.24, 0.58, 0.22, blue_coat, rot=(0, 0, -0.46)))
objects.append(Sp(0.78, 2.58, 0.24,  0.22, white_body))
objects.append(El(0.76, 2.90, 0.27,  0.072, 0.32, 0.072, white_body))   # finger
objects.append(Sp(0.76, 3.21, 0.28,  0.072, white_body))                # fingertip

# Hat crown
objects.append(El(0, 3.82, -0.05,    0.54, 0.62, 0.48, blue_hat))

# Hat brim (main flat ring)
objects.append(El(0, 3.22, -0.05,    1.00, 0.10, 0.82, blue_hat))

# Tricorn brim corner upswepts
objects.append(El(-0.64, 3.30, -0.12, 0.34, 0.095, 0.24, blue_hat, rot=(0, 0,  0.32)))
objects.append(El( 0.64, 3.30, -0.12, 0.34, 0.095, 0.24, blue_hat, rot=(0, 0, -0.32)))

# Yellow hat band
objects.append(El(0, 3.26, -0.05,    1.01, 0.065, 0.84, yellow_trim))

# Yellow brim dots (ring around hat brim)
for angle_deg in range(0, 360, 40):
    a = math.radians(angle_deg)
    xd = 0.84 * math.cos(a)
    zd = 0.70 * math.sin(a) - 0.05
    objects.append(Sp(xd, 3.34, zd, 0.057, yellow_trim))

# Hat badge / cockade
objects.append(Sp(0, 3.74, 0.48,     0.125, hat_badge_y))
objects.append(Sp(0, 3.74, 0.52,     0.080, hat_badge_b))
objects.append(Sp(0, 3.74, 0.56,     0.046, hat_badge_y))

print(f"  {len(objects)} primitives")


# ── Light (fixed in world space — Skippy rotates around it) ───────────────

light = PushLight(
    pos=Vec3(5.0, 8.0, 5.0),
    intensity=1.15,
    color=Vec3(1.0, 0.96, 0.86),
)
bg_color = Vec3(0.82, 0.84, 0.88)


# ── Animation parameters ──────────────────────────────────────────────────

OUT_GIF = '/sessions/brave-magical-brown/mnt/triplestones/misc/skippy_two_act.gif'
os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)

# ── Two-act red carpet ────────────────────────────────────────────────────
# ACT I  — camera orbits 360°, Skippy stands proud
# ACT II — camera orbits again, Skippy slowly counter-rotates (×0.5 speed)
#           giving 180° of opposite-direction drift: the parallax reveal

result = red_carpet_render(
    objects=objects,
    light=light,
    output_gif=OUT_GIF,
    n_frames=16,
    density=420,
    width=400,
    height=500,
    fov=47,
    cam_dist=7.4,
    cam_height=3.55,
    look_at=Vec3(0.0, 2.10, 0.0),
    start_angle=-0.26,
    fps=10,
    bg_color=bg_color,
    title='SKIPPY THE MAGNIFICENT',
    counter_rotate=True,
    counter_rotate_ratio=0.5,
    verbose=True,
)

n_total   = result['n_frames']
total_t   = result['total_time']
avg_t     = result['avg_frame_time']
size_kb   = result['size_kb']

print()
print("  ╔══════════════════════════════════════════════════════════════╗")
print("  ║  SKIPPY THE MAGNIFICENT — two-act orbital by the Entangler  ║")
print("  ║  ACT I : camera orbits, model fixed                         ║")
print("  ║  ACT II: camera orbits, model counter-rotates ×0.5          ║")
print("  ║  No ray tracer. No rays at all. Matter drew itself.         ║")
print(f"  ║  {n_total} frames × {avg_t:.2f}s = {total_t:.1f}s total  |  {size_kb:.0f} KB          ║")
print("  ╚══════════════════════════════════════════════════════════════╝")
