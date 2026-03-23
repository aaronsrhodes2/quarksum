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


# ── Common Metals ─────────────────────────────────────────────────────

ALUMINUM = Material(
    name='Aluminum',
    color=Vec3(0.78, 0.79, 0.80),  # light silver-grey
    reflectance=0.55,
    roughness=0.2,
    density_kg_m3=2700,
    mean_Z=13, mean_A=27,
    composition='Al (aluminium alloy)',
)

COPPER = Material(
    name='Copper',
    color=Vec3(0.72, 0.45, 0.20),  # warm reddish-orange
    reflectance=0.7,
    roughness=0.12,
    density_kg_m3=8960,
    mean_Z=29, mean_A=64,
    composition='Cu (metallic copper)',
)

BRASS = Material(
    name='Brass',
    color=Vec3(0.71, 0.60, 0.22),  # golden yellow
    reflectance=0.55,
    roughness=0.2,
    density_kg_m3=8500,
    mean_Z=29, mean_A=64,  # Cu-dominated
    composition='Cu + Zn (brass alloy)',
)

CHROME = Material(
    name='Chrome',
    color=Vec3(0.80, 0.82, 0.84),  # bright cool silver
    reflectance=0.85,
    roughness=0.04,
    density_kg_m3=7190,
    mean_Z=24, mean_A=52,
    composition='Cr (chromium plating)',
)

GOLD = Material(
    name='Gold',
    color=Vec3(0.83, 0.68, 0.22),  # rich yellow-gold
    reflectance=0.75,
    roughness=0.08,
    density_kg_m3=19320,
    mean_Z=79, mean_A=197,
    composition='Au (metallic gold)',
)

SILVER = Material(
    name='Silver',
    color=Vec3(0.88, 0.88, 0.90),  # bright cool white
    reflectance=0.80,
    roughness=0.06,
    density_kg_m3=10490,
    mean_Z=47, mean_A=108,
    composition='Ag (metallic silver)',
)

CAST_IRON = Material(
    name='Cast Iron',
    color=Vec3(0.28, 0.27, 0.26),  # dark grey
    reflectance=0.3,
    roughness=0.5,
    density_kg_m3=7200,
    mean_Z=26, mean_A=56,
    composition='Fe + C (cast iron, ~2.5% C)',
)


# ── Wood ──────────────────────────────────────────────────────────────

OAK = Material(
    name='Oak Wood',
    color=Vec3(0.62, 0.48, 0.27),  # medium warm tan
    reflectance=0.04,
    roughness=0.75,
    density_kg_m3=750,
    mean_Z=6, mean_A=12,
    composition='Cellulose + lignin (Quercus)',
)

DARK_WOOD = Material(
    name='Dark Wood',
    color=Vec3(0.28, 0.18, 0.10),  # deep brown
    reflectance=0.04,
    roughness=0.65,
    density_kg_m3=850,
    mean_Z=6, mean_A=12,
    composition='Cellulose + lignin (hardwood)',
)

LIGHT_WOOD = Material(
    name='Light Wood',
    color=Vec3(0.80, 0.68, 0.48),  # pale pine/maple
    reflectance=0.04,
    roughness=0.7,
    density_kg_m3=550,
    mean_Z=6, mean_A=12,
    composition='Cellulose + lignin (softwood/pine)',
)


# ── Polymers & Rubber ────────────────────────────────────────────────

RUBBER = Material(
    name='Rubber',
    color=Vec3(0.14, 0.13, 0.12),  # near-black
    reflectance=0.03,
    roughness=0.85,
    density_kg_m3=1200,
    mean_Z=6, mean_A=12,
    composition='C₅H₈ (natural rubber / polyisoprene)',
)

PLASTIC_BLACK = Material(
    name='Black Plastic',
    color=Vec3(0.10, 0.10, 0.11),  # dark charcoal
    reflectance=0.06,
    roughness=0.45,
    density_kg_m3=1050,
    mean_Z=6, mean_A=12,
    composition='ABS (acrylonitrile butadiene styrene)',
)

PLASTIC_WHITE = Material(
    name='White Plastic',
    color=Vec3(0.92, 0.92, 0.93),  # bright white
    reflectance=0.06,
    roughness=0.4,
    density_kg_m3=1050,
    mean_Z=6, mean_A=12,
    composition='ABS or polypropylene',
)


# ── Paints & Finishes ────────────────────────────────────────────────

PAINT_WHITE = Material(
    name='White Paint',
    color=Vec3(0.95, 0.95, 0.94),
    reflectance=0.08,
    roughness=0.55,
    density_kg_m3=1500,
    mean_Z=8, mean_A=16,
    composition='TiO₂ pigment + acrylic binder',
)

PAINT_RED = Material(
    name='Red Paint',
    color=Vec3(0.80, 0.10, 0.08),
    reflectance=0.08,
    roughness=0.55,
    density_kg_m3=1500,
    mean_Z=8, mean_A=16,
    composition='Fe₂O₃ pigment + acrylic binder',
)

PAINT_BLUE = Material(
    name='Blue Paint',
    color=Vec3(0.12, 0.22, 0.72),
    reflectance=0.08,
    roughness=0.55,
    density_kg_m3=1500,
    mean_Z=8, mean_A=16,
    composition='Ultramarine pigment + acrylic binder',
)

PAINT_YELLOW = Material(
    name='Yellow Paint',
    color=Vec3(0.90, 0.80, 0.10),
    reflectance=0.08,
    roughness=0.55,
    density_kg_m3=1500,
    mean_Z=8, mean_A=16,
    composition='Cadmium yellow pigment + binder',
)

PAINT_GREEN = Material(
    name='Green Paint',
    color=Vec3(0.15, 0.55, 0.18),
    reflectance=0.08,
    roughness=0.55,
    density_kg_m3=1500,
    mean_Z=8, mean_A=16,
    composition='Chrome oxide pigment + binder',
)

PAINT_BLACK = Material(
    name='Black Paint',
    color=Vec3(0.06, 0.06, 0.07),
    reflectance=0.04,
    roughness=0.6,
    density_kg_m3=1500,
    mean_Z=6, mean_A=12,
    composition='Carbon black pigment + binder',
)


# ── Organic / Botanical ──────────────────────────────────────────────

LEAF_GREEN = Material(
    name='Leaf',
    color=Vec3(0.18, 0.50, 0.14),  # medium green
    reflectance=0.06,
    roughness=0.7,
    density_kg_m3=700,
    mean_Z=6, mean_A=12,
    composition='Chlorophyll + cellulose',
)

FLESH = Material(
    name='Flesh',
    color=Vec3(0.88, 0.68, 0.52),  # warm skin tone
    reflectance=0.06,
    roughness=0.7,
    density_kg_m3=985,
    mean_Z=7, mean_A=14,
    composition='Water + protein + lipid (tissue)',
)


# ── Ceramic & Stone ───────────────────────────────────────────────────

TERRACOTTA = Material(
    name='Terracotta',
    color=Vec3(0.72, 0.38, 0.22),  # burnt orange-red
    reflectance=0.04,
    roughness=0.8,
    density_kg_m3=1900,
    mean_Z=12, mean_A=24,
    composition='Fired clay (SiO₂ + Fe₂O₃)',
)

MARBLE = Material(
    name='Marble',
    color=Vec3(0.92, 0.90, 0.88),  # near-white with slight warmth
    reflectance=0.2,
    roughness=0.15,
    density_kg_m3=2700,
    mean_Z=12, mean_A=24,
    composition='CaCO₃ (calcite marble)',
)

CONCRETE = Material(
    name='Concrete',
    color=Vec3(0.52, 0.51, 0.50),  # mid grey
    reflectance=0.04,
    roughness=0.85,
    density_kg_m3=2300,
    mean_Z=11, mean_A=22,
    composition='Portland cement + aggregate',
)

STONE = Material(
    name='Stone',
    color=Vec3(0.55, 0.53, 0.50),  # warm grey
    reflectance=0.04,
    roughness=0.9,
    density_kg_m3=2600,
    mean_Z=12, mean_A=24,
    composition='Granite / sandstone mix',
)

BRICK = Material(
    name='Brick',
    color=Vec3(0.65, 0.30, 0.18),  # reddish-brown
    reflectance=0.04,
    roughness=0.9,
    density_kg_m3=1900,
    mean_Z=12, mean_A=24,
    composition='Fired clay + sand (brick)',
)


# ── Fabric & Soft Materials ───────────────────────────────────────────

FABRIC = Material(
    name='Fabric',
    color=Vec3(0.72, 0.68, 0.62),  # warm beige-grey
    reflectance=0.02,
    roughness=0.95,
    density_kg_m3=200,
    mean_Z=6, mean_A=12,
    composition='Cellulose (cotton) or polyester',
)

LEATHER = Material(
    name='Leather',
    color=Vec3(0.35, 0.22, 0.12),  # dark tan-brown
    reflectance=0.06,
    roughness=0.6,
    density_kg_m3=860,
    mean_Z=7, mean_A=14,
    composition='Collagen protein (tanned hide)',
)

WAX = Material(
    name='Wax',
    color=Vec3(0.95, 0.92, 0.80),  # cream-yellow
    reflectance=0.12,
    roughness=0.3,
    density_kg_m3=900,
    mean_Z=6, mean_A=12,
    composition='Paraffin (C₂₀–C₄₀ alkanes)',
)


# ── Material Registry ─────────────────────────────────────────────────
ALL_MATERIALS = {
    # Geological / Space
    'ceramic':    CERAMIC,
    'steel':      STEEL,
    'water':      WATER,
    'glass':      GLASS,
    'basalt':     BASALT,
    'iron':       IRON,
    'silicate':   SILICATE,
    'ice':        ICE,
    'carbon':     CARBON,
    'regolith':   REGOLITH,
    # Common metals
    'aluminum':   ALUMINUM,
    'aluminium':  ALUMINUM,
    'copper':     COPPER,
    'brass':      BRASS,
    'chrome':     CHROME,
    'gold':       GOLD,
    'silver':     SILVER,
    'cast_iron':  CAST_IRON,
    # Wood
    'oak':        OAK,
    'wood':       OAK,
    'dark_wood':  DARK_WOOD,
    'light_wood': LIGHT_WOOD,
    # Polymers
    'rubber':         RUBBER,
    'plastic_black':  PLASTIC_BLACK,
    'plastic_white':  PLASTIC_WHITE,
    'plastic':        PLASTIC_BLACK,
    # Paints
    'paint_white':  PAINT_WHITE,
    'paint_red':    PAINT_RED,
    'paint_blue':   PAINT_BLUE,
    'paint_yellow': PAINT_YELLOW,
    'paint_green':  PAINT_GREEN,
    'paint_black':  PAINT_BLACK,
    # Organic
    'leaf':         LEAF_GREEN,
    'leaf_green':   LEAF_GREEN,
    'flesh':        FLESH,
    # Ceramic & stone
    'terracotta': TERRACOTTA,
    'marble':     MARBLE,
    'concrete':   CONCRETE,
    'stone':      STONE,
    'brick':      BRICK,
    # Fabric & soft
    'fabric': FABRIC,
    'leather': LEATHER,
    'wax':    WAX,
}
