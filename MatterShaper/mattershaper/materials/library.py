"""
Material Library — common materials with physics properties.

Colors from electromagnetic properties (σ-invariant).
Densities and compositions from atomic structure (via QuarkSum).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from ..geometry.primitives import Vec3
from .material import Material


# ── Everyday Materials ────────────────────────────────────────────────

CERAMIC = Material(
    name='Ceramic',
    color=Vec3(0.92, 0.88, 0.82),  # off-white
    reflectance=0.05,
    roughness=0.6,
    density_kg_m3=2400,
    mean_Z=11, mean_A=22,  # weighted avg of Si, O, Al
    composition='SiO₂ + Al₂O₃ (porcelain)',
)

STEEL = Material(
    name='Steel',
    color=Vec3(0.55, 0.56, 0.58),  # grey metallic
    reflectance=0.6,
    roughness=0.15,
    density_kg_m3=7800,
    mean_Z=26, mean_A=56,  # iron-dominated
    composition='Fe + C (carbon steel)',
)

WATER = Material(
    name='Water',
    color=Vec3(0.15, 0.25, 0.35),  # dark blue-ish
    reflectance=0.3,
    roughness=0.05,
    opacity=0.4,
    ior=1.33,
    density_kg_m3=1000,
    mean_Z=3.3, mean_A=6,  # H₂O weighted
    composition='H₂O',
)

GLASS = Material(
    name='Glass',
    color=Vec3(0.85, 0.90, 0.92),  # clear with slight blue
    reflectance=0.4,
    roughness=0.02,
    opacity=0.15,
    ior=1.52,
    density_kg_m3=2500,
    mean_Z=10, mean_A=20,  # SiO₂
    composition='SiO₂ (soda-lime glass)',
)

# ── Geological Materials ──────────────────────────────────────────────

BASALT = Material(
    name='Basalt',
    color=Vec3(0.25, 0.25, 0.27),  # dark grey
    reflectance=0.04,
    roughness=0.8,
    density_kg_m3=2900,
    mean_Z=12, mean_A=24,
    composition='Plagioclase + pyroxene',
)

IRON = Material(
    name='Iron',
    color=Vec3(0.42, 0.40, 0.38),  # dark metallic
    reflectance=0.65,
    roughness=0.2,
    density_kg_m3=7874,
    mean_Z=26, mean_A=56,
    composition='Fe (metallic iron)',
)

SILICATE = Material(
    name='Silicate',
    color=Vec3(0.55, 0.50, 0.42),  # brownish
    reflectance=0.06,
    roughness=0.7,
    density_kg_m3=3300,
    mean_Z=12, mean_A=24,
    composition='MgSiO₃ / olivine',
)

ICE = Material(
    name='Water Ice',
    color=Vec3(0.80, 0.88, 0.95),  # pale blue-white
    reflectance=0.3,
    roughness=0.1,
    opacity=0.6,
    ior=1.31,
    density_kg_m3=917,
    mean_Z=3.3, mean_A=6,
    composition='H₂O (crystalline ice)',
)

CARBON = Material(
    name='Carbonaceous',
    color=Vec3(0.12, 0.11, 0.10),  # very dark
    reflectance=0.02,
    roughness=0.9,
    density_kg_m3=1500,
    mean_Z=6, mean_A=12,
    composition='C + organics (chondrite)',
)

REGOLITH = Material(
    name='Regolith',
    color=Vec3(0.45, 0.42, 0.38),  # dusty grey-brown
    reflectance=0.03,
    roughness=0.95,
    density_kg_m3=1500,
    mean_Z=12, mean_A=24,
    composition='Fragmented silicate + metal',
)


# ── Material Registry ─────────────────────────────────────────────────
ALL_MATERIALS = {
    'ceramic': CERAMIC,
    'steel': STEEL,
    'water': WATER,
    'glass': GLASS,
    'basalt': BASALT,
    'iron': IRON,
    'silicate': SILICATE,
    'ice': ICE,
    'carbon': CARBON,
    'regolith': REGOLITH,
}
