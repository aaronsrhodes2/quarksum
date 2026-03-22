"""
render_beercan.py — Aluminum beer can physics render.

Geometry: 3.5" diameter × 6.5" tall — standard 12oz American can.
Material: Aluminum from Drude/Fresnel physics (FIRST_PRINCIPLES + MEASURED).
Output:   triplestones/misc/beercan.html  (interactive Three.js renderer)

Interactive controls (in the HTML):
  - Observer (camera): θ, φ, distance, fov via sliders + left-drag
  - Non-Observer (object): Rx, Ry, Rz via sliders + right-drag
  - Light Source: θ, φ, distance, intensity via sliders
  - Time / Temperature: 300K–6000K, shows thermal emission glow
  - 3D rotation: mouse drag on canvas

□σ = −ξR
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mattershaper.materials.physics_materials import aluminum
from mattershaper.render.red_carpet_html import red_carpet_html

# ── Get physics-derived aluminum material ──────────────────────────────
mat = aluminum(T=300.0)

print("\n⚗  ALUMINUM PHYSICS PARAMETERS")
print(f"   Color (Drude/Fresnel):   R={mat.color.x:.4f}  G={mat.color.y:.4f}  B={mat.color.z:.4f}")
print(f"   Reflectance:             {mat.reflectance:.4f}")
print(f"   Roughness (Beckmann α):  {mat.roughness:.4f}")
print(f"   Density:                 {mat.density_kg_m3} kg/m³")
print(f"   Z={mat.mean_Z}  A={mat.mean_A}")

# ── Thermal emission steps from local_library ──────────────────────────
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    from local_library.interface.thermal_emission import thermal_emission_rgb, is_visibly_glowing
    temps = [300, 700, 900, 1000, 1200, 1500, 2000, 3000, 4000, 5778]
    thermal_steps = []
    for T in temps:
        if is_visibly_glowing(T):
            r, g, b = thermal_emission_rgb('aluminum', T)
        else:
            r, g, b = 0.0, 0.0, 0.0
        thermal_steps.append((T, r, g, b))
    print(f"\n🌡  Thermal emission: {len(thermal_steps)} temperature steps loaded")
except ImportError:
    thermal_steps = None
    print("\n🌡  Thermal emission: using embedded fallback data")

# ── Output path ────────────────────────────────────────────────────────
OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '..', 'triplestones', 'misc')
OUT_HTML = os.path.join(OUT_DIR, 'beercan.html')

# ── Generate HTML ──────────────────────────────────────────────────────
print("\n🎬  Generating interactive HTML renderer...")

red_carpet_html(
    scene='beercan',
    output_html=OUT_HTML,
    title='SKIPPY — Aluminum Beer Can  ·  Quarksum Physics',
    material=mat,
    geometry={
        'type':        'beercan',
        'diameter_in': 3.5,
        'height_in':   6.5,
    },
    thermal_steps=thermal_steps,
    subtitle='Aluminum · ⌀3.5" × 6.5" · Drude/Fresnel FIRST_PRINCIPLES',
)

print("\n✓  Done. Open beercan.html to interact with the can.")
print("   Left-drag  → orbit camera (Observer)")
print("   Right-drag → spin can (Non-Observer)")
print("   Scroll     → zoom")
print("   Panel sliders → fine-tune all vectors + temperature")
