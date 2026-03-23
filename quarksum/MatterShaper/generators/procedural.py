"""
Procedural Object Generator — zero-dependency shape+color JSON factory.

Generates Nagatha-consumable .shape.json + .color.json pairs from
parameterized templates. No LLM, no network, no external data.

Each template is a function that returns (layers, materials) given
optional randomized parameters. Output is registered in the library
index automatically.

Usage:
    python generators/procedural.py                  # generate all
    python generators/procedural.py --list           # list templates
    python generators/procedural.py wine_glass       # generate one
    python generators/procedural.py --render         # generate + render all
"""

import json
import math
import os
import sys
import random
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJECT_MAPS_DIR = os.path.join(PROJECT_DIR, 'object_maps')
LIBRARY_INDEX = os.path.join(OBJECT_MAPS_DIR, 'library_index.json')


# ── Material palette ──────────────────────────────────────────

MATERIALS = {
    # Ceramics
    'white_ceramic': {
        'label': 'White glazed ceramic',
        'color': [0.92, 0.90, 0.85], 'reflectance': 0.12, 'roughness': 0.25,
        'density_kg_m3': 2400, 'mean_Z': 11, 'mean_A': 22,
        'composition': 'SiO2 + Al2O3 glaze',
    },
    'terracotta': {
        'label': 'Terracotta clay',
        'color': [0.76, 0.40, 0.22], 'reflectance': 0.08, 'roughness': 0.70,
        'density_kg_m3': 1800, 'mean_Z': 14, 'mean_A': 28,
        'composition': 'Fired clay',
    },
    'blue_ceramic': {
        'label': 'Blue glazed ceramic',
        'color': [0.25, 0.40, 0.72], 'reflectance': 0.14, 'roughness': 0.22,
        'density_kg_m3': 2400, 'mean_Z': 11, 'mean_A': 22,
        'composition': 'Cobalt-glazed ceramic',
    },
    # Glass
    'clear_glass': {
        'label': 'Clear glass',
        'color': [0.85, 0.90, 0.88], 'reflectance': 0.45, 'roughness': 0.02,
        'density_kg_m3': 2500, 'mean_Z': 10, 'mean_A': 20,
        'composition': 'Soda-lime glass',
    },
    'green_glass': {
        'label': 'Green bottle glass',
        'color': [0.20, 0.42, 0.18], 'reflectance': 0.35, 'roughness': 0.05,
        'density_kg_m3': 2500, 'mean_Z': 10, 'mean_A': 20,
        'composition': 'Iron-tinted soda-lime glass',
    },
    'amber_glass': {
        'label': 'Amber glass',
        'color': [0.55, 0.30, 0.08], 'reflectance': 0.30, 'roughness': 0.05,
        'density_kg_m3': 2500, 'mean_Z': 10, 'mean_A': 20,
        'composition': 'Sulfur-carbon tinted glass',
    },
    # Metals
    'steel': {
        'label': 'Brushed steel',
        'color': [0.58, 0.60, 0.62], 'reflectance': 0.65, 'roughness': 0.30,
        'density_kg_m3': 7800, 'mean_Z': 26, 'mean_A': 56,
        'composition': 'Fe-C alloy',
    },
    'brass': {
        'label': 'Polished brass',
        'color': [0.78, 0.62, 0.22], 'reflectance': 0.72, 'roughness': 0.15,
        'density_kg_m3': 8500, 'mean_Z': 29, 'mean_A': 63,
        'composition': 'Cu-Zn alloy',
    },
    'copper': {
        'label': 'Aged copper',
        'color': [0.72, 0.45, 0.20], 'reflectance': 0.60, 'roughness': 0.25,
        'density_kg_m3': 8960, 'mean_Z': 29, 'mean_A': 64,
        'composition': 'Cu',
    },
    'chrome': {
        'label': 'Chrome plate',
        'color': [0.75, 0.75, 0.78], 'reflectance': 0.85, 'roughness': 0.05,
        'density_kg_m3': 7190, 'mean_Z': 24, 'mean_A': 52,
        'composition': 'Cr plating',
    },
    # Wood
    'light_wood': {
        'label': 'Light oak wood',
        'color': [0.68, 0.52, 0.32], 'reflectance': 0.10, 'roughness': 0.60,
        'density_kg_m3': 700, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Cellulose + lignin',
    },
    'dark_wood': {
        'label': 'Dark walnut wood',
        'color': [0.35, 0.22, 0.12], 'reflectance': 0.12, 'roughness': 0.50,
        'density_kg_m3': 650, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Cellulose + lignin',
    },
    # Plastic
    'red_plastic': {
        'label': 'Red ABS plastic',
        'color': [0.82, 0.15, 0.12], 'reflectance': 0.18, 'roughness': 0.35,
        'density_kg_m3': 1050, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'ABS polymer',
    },
    'black_plastic': {
        'label': 'Black polycarbonate',
        'color': [0.08, 0.08, 0.10], 'reflectance': 0.20, 'roughness': 0.30,
        'density_kg_m3': 1200, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Polycarbonate',
    },
    'white_plastic': {
        'label': 'White HDPE',
        'color': [0.90, 0.88, 0.86], 'reflectance': 0.15, 'roughness': 0.40,
        'density_kg_m3': 950, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'HDPE polymer',
    },
    # Fabric/soft
    'cream_fabric': {
        'label': 'Cream linen',
        'color': [0.88, 0.82, 0.72], 'reflectance': 0.05, 'roughness': 0.90,
        'density_kg_m3': 300, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Linen fiber',
    },
    # Stone
    'marble_white': {
        'label': 'White marble',
        'color': [0.90, 0.88, 0.84], 'reflectance': 0.25, 'roughness': 0.15,
        'density_kg_m3': 2700, 'mean_Z': 10, 'mean_A': 20,
        'composition': 'CaCO3 crystalline',
    },
    'granite_grey': {
        'label': 'Grey granite',
        'color': [0.45, 0.44, 0.42], 'reflectance': 0.20, 'roughness': 0.35,
        'density_kg_m3': 2700, 'mean_Z': 13, 'mean_A': 27,
        'composition': 'Feldspar + quartz + mica',
    },
    # Organic
    'skin_orange': {
        'label': 'Orange peel',
        'color': [0.90, 0.55, 0.10], 'reflectance': 0.08, 'roughness': 0.65,
        'density_kg_m3': 900, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Cellulose + limonene',
    },
    'skin_red': {
        'label': 'Red fruit skin',
        'color': [0.72, 0.10, 0.08], 'reflectance': 0.12, 'roughness': 0.40,
        'density_kg_m3': 900, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Cellulose + anthocyanin',
    },
    'skin_yellow': {
        'label': 'Yellow fruit skin',
        'color': [0.92, 0.82, 0.15], 'reflectance': 0.10, 'roughness': 0.45,
        'density_kg_m3': 900, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Cellulose + carotenoids',
    },
    'skin_green': {
        'label': 'Green fruit skin',
        'color': [0.30, 0.58, 0.15], 'reflectance': 0.08, 'roughness': 0.50,
        'density_kg_m3': 900, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Cellulose + chlorophyll',
    },
    'flesh_white': {
        'label': 'White fruit flesh',
        'color': [0.88, 0.85, 0.75], 'reflectance': 0.05, 'roughness': 0.70,
        'density_kg_m3': 850, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Cellulose + fructose',
    },
    'stem_brown': {
        'label': 'Brown stem',
        'color': [0.35, 0.25, 0.12], 'reflectance': 0.05, 'roughness': 0.80,
        'density_kg_m3': 600, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Lignin + cellulose',
    },
    'leaf_green': {
        'label': 'Green leaf',
        'color': [0.18, 0.48, 0.12], 'reflectance': 0.08, 'roughness': 0.50,
        'density_kg_m3': 700, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Chlorophyll leaf',
    },
    # Liquids
    'water': {
        'label': 'Clear water',
        'color': [0.70, 0.80, 0.88], 'reflectance': 0.40, 'roughness': 0.02,
        'density_kg_m3': 1000, 'mean_Z': 7, 'mean_A': 14,
        'composition': 'H2O',
    },
    'coffee': {
        'label': 'Black coffee',
        'color': [0.22, 0.12, 0.06], 'reflectance': 0.35, 'roughness': 0.03,
        'density_kg_m3': 1000, 'mean_Z': 7, 'mean_A': 14,
        'composition': 'H2O + organics',
    },
    # Wax
    'candle_wax': {
        'label': 'Cream candle wax',
        'color': [0.90, 0.85, 0.72], 'reflectance': 0.08, 'roughness': 0.40,
        'density_kg_m3': 900, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Paraffin wax',
    },
    'flame_core': {
        'label': 'Flame core',
        'color': [1.0, 0.85, 0.30], 'reflectance': 0.02, 'roughness': 0.10,
        'density_kg_m3': 1, 'mean_Z': 7, 'mean_A': 14,
        'composition': 'Incandescent gas',
    },
    'flame_tip': {
        'label': 'Flame tip',
        'color': [1.0, 0.50, 0.05], 'reflectance': 0.02, 'roughness': 0.10,
        'density_kg_m3': 1, 'mean_Z': 7, 'mean_A': 14,
        'composition': 'Incandescent gas',
    },
    # Rubber
    'black_rubber': {
        'label': 'Black rubber',
        'color': [0.10, 0.10, 0.10], 'reflectance': 0.05, 'roughness': 0.80,
        'density_kg_m3': 1100, 'mean_Z': 6, 'mean_A': 12,
        'composition': 'Vulcanized rubber',
    },
}


# ── Helper: handle arc (for mugs, cups, pitchers) ────────────

def make_handle(cx, cy_top, cy_bot, reach, n_segments, mat_id):
    """Generate overlapping ellipsoid arc for a handle."""
    layers = []
    for i in range(n_segments):
        t = i / (n_segments - 1)
        angle = math.pi * t
        y = cy_top + (cy_bot - cy_top) * t
        x = cx + reach * math.sin(angle)
        layers.append({
            'id': f'handle_{i}',
            'label': f'Handle segment {i}',
            'type': 'ellipsoid',
            'pos': [round(x, 4), round(y, 4), 0],
            'radii': [0.05, 0.06, 0.04],
            'rotate': [0, 0, round(math.atan2(reach * math.cos(angle),
                                               (cy_bot - cy_top) / n_segments), 3)],
            'material': mat_id,
        })
    return layers


# ── TEMPLATES ─────────────────────────────────────────────────

def wine_glass():
    """Wine glass — thin stem, wide bowl, circular base."""
    return {
        'key': 'wine_glass',
        'name': 'Wine Glass',
        'reference': 'Standard 250ml wine glass — 21cm tall, 8cm bowl dia',
        'scale_note': '1 unit = 10cm',
        'aliases': ['wine glass', 'glass', 'stemware', 'goblet'],
        'layers': [
            {'id': 'base', 'label': 'Circular base', 'type': 'ellipsoid',
             'pos': [0, 0.02, 0], 'radii': [0.38, 0.02, 0.38],
             'rotate': [0, 0, 0], 'material': 'clear_glass'},
            {'id': 'stem', 'label': 'Stem', 'type': 'cone',
             'base_pos': [0, 0.04, 0], 'height': 0.9, 'base_radius': 0.04,
             'top_radius': 0.04, 'rotate': [0, 0, 0], 'material': 'clear_glass'},
            {'id': 'bowl_base', 'label': 'Bowl base taper', 'type': 'cone',
             'base_pos': [0, 0.9, 0], 'height': 0.4, 'base_radius': 0.05,
             'top_radius': 0.38, 'rotate': [0, 0, 0], 'material': 'clear_glass'},
            {'id': 'bowl_mid', 'label': 'Bowl widest', 'type': 'ellipsoid',
             'pos': [0, 1.4, 0], 'radii': [0.40, 0.20, 0.40],
             'rotate': [0, 0, 0], 'material': 'clear_glass'},
            {'id': 'bowl_top', 'label': 'Bowl narrowing', 'type': 'cone',
             'base_pos': [0, 1.5, 0], 'height': 0.5, 'base_radius': 0.38,
             'top_radius': 0.34, 'rotate': [0, 0, 0], 'material': 'clear_glass'},
            {'id': 'rim', 'label': 'Rim', 'type': 'ellipsoid',
             'pos': [0, 2.0, 0], 'radii': [0.35, 0.015, 0.35],
             'rotate': [0, 0, 0], 'material': 'clear_glass'},
        ],
        'materials_used': ['clear_glass'],
    }


def beer_bottle():
    """Standard 330ml brown beer bottle."""
    return {
        'key': 'beer_bottle',
        'name': 'Beer Bottle',
        'reference': '330ml longneck beer bottle — 24cm tall, 6.5cm body dia',
        'scale_note': '1 unit = 10cm',
        'aliases': ['beer bottle', 'bottle', 'longneck'],
        'layers': [
            {'id': 'base', 'label': 'Base', 'type': 'ellipsoid',
             'pos': [0, 0.01, 0], 'radii': [0.33, 0.02, 0.33],
             'rotate': [0, 0, 0], 'material': 'amber_glass'},
            {'id': 'body', 'label': 'Body', 'type': 'cone',
             'base_pos': [0, 0, 0], 'height': 1.4, 'base_radius': 0.32,
             'top_radius': 0.33, 'rotate': [0, 0, 0], 'material': 'amber_glass'},
            {'id': 'shoulder', 'label': 'Shoulder taper', 'type': 'cone',
             'base_pos': [0, 1.35, 0], 'height': 0.4, 'base_radius': 0.33,
             'top_radius': 0.13, 'rotate': [0, 0, 0], 'material': 'amber_glass'},
            {'id': 'neck', 'label': 'Neck', 'type': 'cone',
             'base_pos': [0, 1.7, 0], 'height': 0.65, 'base_radius': 0.13,
             'top_radius': 0.13, 'rotate': [0, 0, 0], 'material': 'amber_glass'},
            {'id': 'lip', 'label': 'Lip ring', 'type': 'ellipsoid',
             'pos': [0, 2.35, 0], 'radii': [0.15, 0.025, 0.15],
             'rotate': [0, 0, 0], 'material': 'amber_glass'},
            {'id': 'cap', 'label': 'Bottle cap', 'type': 'ellipsoid',
             'pos': [0, 2.40, 0], 'radii': [0.14, 0.03, 0.14],
             'rotate': [0, 0, 0], 'material': 'steel'},
        ],
        'materials_used': ['amber_glass', 'steel'],
    }


def candle():
    """Pillar candle with flame."""
    return {
        'key': 'candle',
        'name': 'Pillar Candle',
        'reference': 'Pillar candle — 15cm tall, 7cm diameter',
        'scale_note': '1 unit = 10cm',
        'aliases': ['candle', 'pillar candle', 'wax candle'],
        'layers': [
            {'id': 'body', 'label': 'Wax body', 'type': 'cone',
             'base_pos': [0, 0, 0], 'height': 1.5, 'base_radius': 0.35,
             'top_radius': 0.34, 'rotate': [0, 0, 0], 'material': 'candle_wax'},
            {'id': 'top', 'label': 'Melted wax pool', 'type': 'ellipsoid',
             'pos': [0, 1.48, 0], 'radii': [0.33, 0.025, 0.33],
             'rotate': [0, 0, 0], 'material': 'candle_wax'},
            {'id': 'wick', 'label': 'Wick', 'type': 'cone',
             'base_pos': [0, 1.45, 0], 'height': 0.12, 'base_radius': 0.008,
             'top_radius': 0.005, 'rotate': [0, 0, 0], 'material': 'stem_brown'},
            {'id': 'flame_core', 'label': 'Flame inner', 'type': 'ellipsoid',
             'pos': [0, 1.65, 0], 'radii': [0.025, 0.08, 0.025],
             'rotate': [0, 0, 0], 'material': 'flame_core'},
            {'id': 'flame_outer', 'label': 'Flame outer', 'type': 'ellipsoid',
             'pos': [0, 1.68, 0], 'radii': [0.035, 0.10, 0.035],
             'rotate': [0, 0, 0], 'material': 'flame_tip'},
        ],
        'materials_used': ['candle_wax', 'stem_brown', 'flame_core', 'flame_tip'],
    }


def soup_bowl():
    """Ceramic soup bowl."""
    return {
        'key': 'soup_bowl',
        'name': 'Soup Bowl',
        'reference': 'Ceramic soup bowl — 8cm tall, 16cm diameter',
        'scale_note': '1 unit = 10cm',
        'aliases': ['soup bowl', 'bowl', 'cereal bowl'],
        'layers': [
            {'id': 'outer', 'label': 'Outer wall', 'type': 'ellipsoid',
             'pos': [0, 0.25, 0], 'radii': [0.80, 0.40, 0.80],
             'rotate': [0, 0, 0], 'material': 'white_ceramic'},
            {'id': 'base', 'label': 'Flat base', 'type': 'ellipsoid',
             'pos': [0, 0.02, 0], 'radii': [0.45, 0.025, 0.45],
             'rotate': [0, 0, 0], 'material': 'white_ceramic'},
            {'id': 'rim', 'label': 'Rim', 'type': 'ellipsoid',
             'pos': [0, 0.55, 0], 'radii': [0.82, 0.02, 0.82],
             'rotate': [0, 0, 0], 'material': 'white_ceramic'},
        ],
        'materials_used': ['white_ceramic'],
    }


def table_lamp():
    """Bedside table lamp with shade."""
    return {
        'key': 'table_lamp',
        'name': 'Table Lamp',
        'reference': 'Bedside lamp — 40cm tall, 25cm shade diameter',
        'scale_note': '1 unit = 10cm',
        'aliases': ['table lamp', 'bedside lamp', 'lamp', 'night lamp'],
        'layers': [
            {'id': 'base', 'label': 'Heavy base', 'type': 'ellipsoid',
             'pos': [0, 0.05, 0], 'radii': [0.50, 0.05, 0.50],
             'rotate': [0, 0, 0], 'material': 'brass'},
            {'id': 'stem_low', 'label': 'Lower stem', 'type': 'cone',
             'base_pos': [0, 0.08, 0], 'height': 1.0, 'base_radius': 0.08,
             'top_radius': 0.06, 'rotate': [0, 0, 0], 'material': 'brass'},
            {'id': 'stem_mid', 'label': 'Stem knob', 'type': 'sphere',
             'pos': [0, 1.1, 0], 'radius': 0.10, 'material': 'brass'},
            {'id': 'stem_upper', 'label': 'Upper stem', 'type': 'cone',
             'base_pos': [0, 1.15, 0], 'height': 0.6, 'base_radius': 0.06,
             'top_radius': 0.05, 'rotate': [0, 0, 0], 'material': 'brass'},
            {'id': 'shade', 'label': 'Lampshade', 'type': 'cone',
             'base_pos': [0, 1.7, 0], 'height': 0.8, 'base_radius': 1.25,
             'top_radius': 0.60, 'rotate': [0, 0, 0], 'material': 'cream_fabric'},
            {'id': 'shade_rim', 'label': 'Shade bottom rim', 'type': 'ellipsoid',
             'pos': [0, 1.72, 0], 'radii': [1.26, 0.015, 1.26],
             'rotate': [0, 0, 0], 'material': 'brass'},
        ],
        'materials_used': ['brass', 'cream_fabric'],
    }


def orange():
    """Orange fruit."""
    return {
        'key': 'orange',
        'name': 'Orange',
        'reference': 'Navel orange — 8cm diameter',
        'scale_note': '1 unit = 10cm',
        'aliases': ['orange', 'navel orange', 'citrus', 'fruit'],
        'layers': [
            {'id': 'body', 'label': 'Orange body', 'type': 'sphere',
             'pos': [0, 0.40, 0], 'radius': 0.40, 'material': 'skin_orange'},
            {'id': 'navel', 'label': 'Navel dimple', 'type': 'sphere',
             'pos': [0, 0.02, 0], 'radius': 0.06, 'material': 'skin_yellow'},
            {'id': 'stem_bump', 'label': 'Stem end bump', 'type': 'ellipsoid',
             'pos': [0, 0.80, 0], 'radii': [0.04, 0.02, 0.04],
             'rotate': [0, 0, 0], 'material': 'stem_brown'},
        ],
        'materials_used': ['skin_orange', 'skin_yellow', 'stem_brown'],
    }


def pear():
    """Pear fruit."""
    return {
        'key': 'pear',
        'name': 'Pear',
        'reference': 'Bartlett pear — 10cm tall, 7cm wide at base',
        'scale_note': '1 unit = 10cm',
        'aliases': ['pear', 'bartlett pear', 'fruit'],
        'layers': [
            {'id': 'base', 'label': 'Wide bottom', 'type': 'ellipsoid',
             'pos': [0, 0.30, 0], 'radii': [0.35, 0.32, 0.35],
             'rotate': [0, 0, 0], 'material': 'skin_green'},
            {'id': 'mid', 'label': 'Mid taper', 'type': 'ellipsoid',
             'pos': [0, 0.55, 0], 'radii': [0.28, 0.22, 0.28],
             'rotate': [0, 0, 0], 'material': 'skin_green'},
            {'id': 'neck', 'label': 'Narrow neck', 'type': 'ellipsoid',
             'pos': [0, 0.78, 0], 'radii': [0.16, 0.18, 0.16],
             'rotate': [0, 0, 0], 'material': 'skin_yellow'},
            {'id': 'stem', 'label': 'Stem', 'type': 'cone',
             'base_pos': [0, 0.92, 0], 'height': 0.15, 'base_radius': 0.02,
             'top_radius': 0.01, 'rotate': [0, 0, 0], 'material': 'stem_brown'},
        ],
        'materials_used': ['skin_green', 'skin_yellow', 'stem_brown'],
    }


def lemon():
    """Lemon."""
    return {
        'key': 'lemon',
        'name': 'Lemon',
        'reference': 'Standard lemon — 9cm long, 6cm diameter',
        'scale_note': '1 unit = 10cm',
        'aliases': ['lemon', 'citrus', 'fruit'],
        'layers': [
            {'id': 'body', 'label': 'Lemon body', 'type': 'ellipsoid',
             'pos': [0, 0.30, 0], 'radii': [0.30, 0.22, 0.22],
             'rotate': [0, 0, 0.15], 'material': 'skin_yellow'},
            {'id': 'tip_l', 'label': 'Left tip', 'type': 'ellipsoid',
             'pos': [-0.30, 0.32, 0], 'radii': [0.10, 0.06, 0.06],
             'rotate': [0, 0, 0.2], 'material': 'skin_yellow'},
            {'id': 'tip_r', 'label': 'Right tip', 'type': 'ellipsoid',
             'pos': [0.30, 0.28, 0], 'radii': [0.10, 0.06, 0.06],
             'rotate': [0, 0, -0.2], 'material': 'skin_yellow'},
        ],
        'materials_used': ['skin_yellow'],
    }


def vase():
    """Ceramic vase with curved profile."""
    return {
        'key': 'vase',
        'name': 'Ceramic Vase',
        'reference': 'Decorative vase — 30cm tall, 12cm max diameter',
        'scale_note': '1 unit = 10cm',
        'aliases': ['vase', 'flower vase', 'ceramic vase'],
        'layers': [
            {'id': 'base', 'label': 'Base ring', 'type': 'ellipsoid',
             'pos': [0, 0.02, 0], 'radii': [0.35, 0.025, 0.35],
             'rotate': [0, 0, 0], 'material': 'blue_ceramic'},
            {'id': 'body_low', 'label': 'Lower body', 'type': 'cone',
             'base_pos': [0, 0, 0], 'height': 0.8, 'base_radius': 0.32,
             'top_radius': 0.58, 'rotate': [0, 0, 0], 'material': 'blue_ceramic'},
            {'id': 'body_wide', 'label': 'Widest section', 'type': 'ellipsoid',
             'pos': [0, 1.0, 0], 'radii': [0.60, 0.30, 0.60],
             'rotate': [0, 0, 0], 'material': 'blue_ceramic'},
            {'id': 'body_upper', 'label': 'Upper taper', 'type': 'cone',
             'base_pos': [0, 1.2, 0], 'height': 0.8, 'base_radius': 0.55,
             'top_radius': 0.30, 'rotate': [0, 0, 0], 'material': 'blue_ceramic'},
            {'id': 'neck', 'label': 'Neck', 'type': 'cone',
             'base_pos': [0, 1.95, 0], 'height': 0.6, 'base_radius': 0.28,
             'top_radius': 0.35, 'rotate': [0, 0, 0], 'material': 'blue_ceramic'},
            {'id': 'rim', 'label': 'Rim', 'type': 'ellipsoid',
             'pos': [0, 2.55, 0], 'radii': [0.36, 0.02, 0.36],
             'rotate': [0, 0, 0], 'material': 'blue_ceramic'},
        ],
        'materials_used': ['blue_ceramic'],
    }


def teapot():
    """Classic round teapot."""
    layers = [
        {'id': 'body', 'label': 'Round body', 'type': 'sphere',
         'pos': [0, 0.50, 0], 'radius': 0.50, 'material': 'white_ceramic'},
        {'id': 'base', 'label': 'Base ring', 'type': 'ellipsoid',
         'pos': [0, 0.03, 0], 'radii': [0.30, 0.03, 0.30],
         'rotate': [0, 0, 0], 'material': 'white_ceramic'},
        {'id': 'lid_seat', 'label': 'Lid seat', 'type': 'ellipsoid',
         'pos': [0, 0.95, 0], 'radii': [0.20, 0.03, 0.20],
         'rotate': [0, 0, 0], 'material': 'white_ceramic'},
        {'id': 'lid', 'label': 'Lid dome', 'type': 'ellipsoid',
         'pos': [0, 1.02, 0], 'radii': [0.22, 0.08, 0.22],
         'rotate': [0, 0, 0], 'material': 'white_ceramic'},
        {'id': 'lid_knob', 'label': 'Lid knob', 'type': 'sphere',
         'pos': [0, 1.12, 0], 'radius': 0.06, 'material': 'brass'},
        # Spout
        {'id': 'spout_base', 'label': 'Spout base', 'type': 'ellipsoid',
         'pos': [0.45, 0.50, 0], 'radii': [0.08, 0.10, 0.06],
         'rotate': [0, 0, 0.3], 'material': 'white_ceramic'},
        {'id': 'spout_mid', 'label': 'Spout mid', 'type': 'ellipsoid',
         'pos': [0.58, 0.60, 0], 'radii': [0.06, 0.08, 0.05],
         'rotate': [0, 0, 0.5], 'material': 'white_ceramic'},
        {'id': 'spout_tip', 'label': 'Spout tip', 'type': 'ellipsoid',
         'pos': [0.68, 0.72, 0], 'radii': [0.04, 0.06, 0.04],
         'rotate': [0, 0, 0.7], 'material': 'white_ceramic'},
    ]
    # Handle on the other side
    layers += make_handle(-0.45, 0.65, 0.30, 0.18, 6, 'white_ceramic')

    return {
        'key': 'teapot',
        'name': 'Teapot',
        'reference': 'Classic round teapot — 12cm body, 15cm tall with lid',
        'scale_note': '1 unit = 10cm',
        'aliases': ['teapot', 'tea pot', 'kettle'],
        'layers': layers,
        'materials_used': ['white_ceramic', 'brass'],
    }


def trophy():
    """Gold trophy cup."""
    return {
        'key': 'trophy',
        'name': 'Trophy Cup',
        'reference': 'Award trophy — 30cm tall',
        'scale_note': '1 unit = 10cm',
        'aliases': ['trophy', 'trophy cup', 'award', 'cup trophy'],
        'layers': [
            {'id': 'base_plate', 'label': 'Base plate', 'type': 'ellipsoid',
             'pos': [0, 0.03, 0], 'radii': [0.50, 0.03, 0.50],
             'rotate': [0, 0, 0], 'material': 'dark_wood'},
            {'id': 'base_col', 'label': 'Base column', 'type': 'cone',
             'base_pos': [0, 0.06, 0], 'height': 0.5, 'base_radius': 0.15,
             'top_radius': 0.10, 'rotate': [0, 0, 0], 'material': 'brass'},
            {'id': 'stem', 'label': 'Stem', 'type': 'cone',
             'base_pos': [0, 0.55, 0], 'height': 0.6, 'base_radius': 0.08,
             'top_radius': 0.06, 'rotate': [0, 0, 0], 'material': 'brass'},
            {'id': 'cup_base', 'label': 'Cup taper', 'type': 'cone',
             'base_pos': [0, 1.1, 0], 'height': 0.5, 'base_radius': 0.08,
             'top_radius': 0.45, 'rotate': [0, 0, 0], 'material': 'brass'},
            {'id': 'cup_body', 'label': 'Cup bowl', 'type': 'ellipsoid',
             'pos': [0, 1.8, 0], 'radii': [0.48, 0.35, 0.48],
             'rotate': [0, 0, 0], 'material': 'brass'},
            {'id': 'cup_rim', 'label': 'Cup rim', 'type': 'ellipsoid',
             'pos': [0, 2.1, 0], 'radii': [0.50, 0.02, 0.50],
             'rotate': [0, 0, 0], 'material': 'brass'},
        ],
        'materials_used': ['dark_wood', 'brass'],
    }


def flower_pot():
    """Terracotta flower pot with saucer."""
    return {
        'key': 'flower_pot',
        'name': 'Flower Pot',
        'reference': 'Standard terracotta pot — 15cm tall, 16cm top diameter',
        'scale_note': '1 unit = 10cm',
        'aliases': ['flower pot', 'pot', 'planter', 'terracotta pot'],
        'layers': [
            {'id': 'saucer', 'label': 'Saucer', 'type': 'ellipsoid',
             'pos': [0, 0.02, 0], 'radii': [0.90, 0.025, 0.90],
             'rotate': [0, 0, 0], 'material': 'terracotta'},
            {'id': 'body', 'label': 'Pot body', 'type': 'cone',
             'base_pos': [0, 0.05, 0], 'height': 1.4, 'base_radius': 0.50,
             'top_radius': 0.78, 'rotate': [0, 0, 0], 'material': 'terracotta'},
            {'id': 'rim', 'label': 'Rim lip', 'type': 'ellipsoid',
             'pos': [0, 1.44, 0], 'radii': [0.82, 0.04, 0.82],
             'rotate': [0, 0, 0], 'material': 'terracotta'},
        ],
        'materials_used': ['terracotta'],
    }


def salt_shaker():
    """Salt shaker."""
    return {
        'key': 'salt_shaker',
        'name': 'Salt Shaker',
        'reference': 'Glass salt shaker — 10cm tall',
        'scale_note': '1 unit = 10cm',
        'aliases': ['salt shaker', 'shaker', 'salt', 'pepper shaker'],
        'layers': [
            {'id': 'body', 'label': 'Glass body', 'type': 'cone',
             'base_pos': [0, 0, 0], 'height': 0.7, 'base_radius': 0.22,
             'top_radius': 0.18, 'rotate': [0, 0, 0], 'material': 'clear_glass'},
            {'id': 'base', 'label': 'Base', 'type': 'ellipsoid',
             'pos': [0, 0.01, 0], 'radii': [0.22, 0.015, 0.22],
             'rotate': [0, 0, 0], 'material': 'clear_glass'},
            {'id': 'cap', 'label': 'Metal cap', 'type': 'ellipsoid',
             'pos': [0, 0.75, 0], 'radii': [0.19, 0.06, 0.19],
             'rotate': [0, 0, 0], 'material': 'chrome'},
            {'id': 'cap_top', 'label': 'Cap top', 'type': 'ellipsoid',
             'pos': [0, 0.82, 0], 'radii': [0.16, 0.02, 0.16],
             'rotate': [0, 0, 0], 'material': 'chrome'},
        ],
        'materials_used': ['clear_glass', 'chrome'],
    }


def hammer():
    """Claw hammer."""
    return {
        'key': 'hammer',
        'name': 'Claw Hammer',
        'reference': 'Standard claw hammer — 33cm long',
        'scale_note': '1 unit = 10cm',
        'aliases': ['hammer', 'claw hammer', 'tool'],
        'layers': [
            {'id': 'handle', 'label': 'Wood handle', 'type': 'cone',
             'base_pos': [0, 0, 0], 'height': 2.5, 'base_radius': 0.12,
             'top_radius': 0.10, 'rotate': [0, 0, 0], 'material': 'light_wood'},
            {'id': 'head', 'label': 'Steel head', 'type': 'ellipsoid',
             'pos': [0, 2.55, 0], 'radii': [0.45, 0.12, 0.12],
             'rotate': [0, 0, 0], 'material': 'steel'},
            {'id': 'face', 'label': 'Striking face', 'type': 'ellipsoid',
             'pos': [0.45, 2.55, 0], 'radii': [0.06, 0.11, 0.11],
             'rotate': [0, 0, 0], 'material': 'steel'},
            {'id': 'claw', 'label': 'Claw', 'type': 'ellipsoid',
             'pos': [-0.40, 2.58, 0], 'radii': [0.12, 0.08, 0.10],
             'rotate': [0, 0, -0.3], 'material': 'steel'},
        ],
        'materials_used': ['light_wood', 'steel'],
    }


def chess_pawn():
    """Chess pawn piece."""
    return {
        'key': 'chess_pawn',
        'name': 'Chess Pawn',
        'reference': 'Staunton chess pawn — 5cm tall',
        'scale_note': '1 unit = 10cm',
        'aliases': ['chess pawn', 'pawn', 'chess piece'],
        'layers': [
            {'id': 'base', 'label': 'Wide base', 'type': 'ellipsoid',
             'pos': [0, 0.02, 0], 'radii': [0.20, 0.025, 0.20],
             'rotate': [0, 0, 0], 'material': 'marble_white'},
            {'id': 'pedestal', 'label': 'Pedestal', 'type': 'cone',
             'base_pos': [0, 0.03, 0], 'height': 0.10, 'base_radius': 0.18,
             'top_radius': 0.12, 'rotate': [0, 0, 0], 'material': 'marble_white'},
            {'id': 'shaft', 'label': 'Shaft', 'type': 'cone',
             'base_pos': [0, 0.12, 0], 'height': 0.22, 'base_radius': 0.10,
             'top_radius': 0.07, 'rotate': [0, 0, 0], 'material': 'marble_white'},
            {'id': 'collar', 'label': 'Collar ring', 'type': 'ellipsoid',
             'pos': [0, 0.34, 0], 'radii': [0.09, 0.015, 0.09],
             'rotate': [0, 0, 0], 'material': 'marble_white'},
            {'id': 'head', 'label': 'Head sphere', 'type': 'sphere',
             'pos': [0, 0.43, 0], 'radius': 0.08, 'material': 'marble_white'},
        ],
        'materials_used': ['marble_white'],
    }


def rubber_duck():
    """Classic rubber duck."""
    return {
        'key': 'rubber_duck',
        'name': 'Rubber Duck',
        'reference': 'Classic rubber duck — 8cm tall',
        'scale_note': '1 unit = 10cm',
        'aliases': ['rubber duck', 'duck', 'bath duck', 'rubber ducky'],
        'layers': [
            {'id': 'body', 'label': 'Body', 'type': 'ellipsoid',
             'pos': [0, 0.25, 0], 'radii': [0.30, 0.25, 0.35],
             'rotate': [0, 0, 0], 'material': 'skin_yellow'},
            {'id': 'head', 'label': 'Head', 'type': 'sphere',
             'pos': [0.15, 0.55, 0], 'radius': 0.20, 'material': 'skin_yellow'},
            {'id': 'beak', 'label': 'Beak', 'type': 'ellipsoid',
             'pos': [0.35, 0.52, 0], 'radii': [0.10, 0.03, 0.05],
             'rotate': [0, 0, -0.1], 'material': 'skin_orange'},
            {'id': 'tail', 'label': 'Tail', 'type': 'ellipsoid',
             'pos': [-0.28, 0.35, 0], 'radii': [0.08, 0.10, 0.06],
             'rotate': [0, 0, 0.5], 'material': 'skin_yellow'},
        ],
        'materials_used': ['skin_yellow', 'skin_orange'],
    }


# ── Registry ──────────────────────────────────────────────────

TEMPLATES = {
    'wine_glass': wine_glass,
    'beer_bottle': beer_bottle,
    'candle': candle,
    'soup_bowl': soup_bowl,
    'table_lamp': table_lamp,
    'orange': orange,
    'pear': pear,
    'lemon': lemon,
    'vase': vase,
    'teapot': teapot,
    'trophy': trophy,
    'flower_pot': flower_pot,
    'salt_shaker': salt_shaker,
    'hammer': hammer,
    'chess_pawn': chess_pawn,
    'rubber_duck': rubber_duck,
}


# ── Output ────────────────────────────────────────────────────

def generate_object(template_fn):
    """Run a template and produce shape+color JSON dicts."""
    spec = template_fn()

    shape_map = {
        'name': spec['name'],
        'reference': spec['reference'],
        'scale_note': spec['scale_note'],
        'provenance': 'Procedural generator — parametric template, no LLM',
        'layers': spec['layers'],
    }

    color_map = {
        'name': f"{spec['name']} Colors",
        'reference': f"Materials for {spec['name']}",
        'provenance': 'Procedural generator material palette',
        'materials': {k: MATERIALS[k] for k in spec['materials_used']},
    }

    return spec['key'], spec, shape_map, color_map


def save_object(key, spec, shape_map, color_map):
    """Write shape+color JSON and update library index."""
    os.makedirs(OBJECT_MAPS_DIR, exist_ok=True)

    shape_path = os.path.join(OBJECT_MAPS_DIR, f'{key}.shape.json')
    color_path = os.path.join(OBJECT_MAPS_DIR, f'{key}.color.json')

    with open(shape_path, 'w', encoding='utf-8') as f:
        json.dump(shape_map, f, indent=2)
    with open(color_path, 'w', encoding='utf-8') as f:
        json.dump(color_map, f, indent=2)

    # Update library index
    if os.path.exists(LIBRARY_INDEX):
        with open(LIBRARY_INDEX, encoding='utf-8') as f:
            index = json.load(f)
    else:
        index = {'version': '1.0', 'engine': 'MatterShaper',
                 'format': 'Sigma Signature v1', 'objects': {}}

    index['objects'][key] = {
        'key': key,
        'name': spec['name'],
        'aliases': spec.get('aliases', []),
        'shape_path': f'object_maps/{key}.shape.json',
        'color_path': f'object_maps/{key}.color.json',
        'primitives': len(spec['layers']),
        'materials': len(spec['materials_used']),
        'approved': True,
        'approved_by': 'procedural_generator',
        'approved_date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'created_by': 'procedural_v1',
    }

    with open(LIBRARY_INDEX, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)

    return shape_path, color_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Procedural object generator')
    parser.add_argument('templates', nargs='*', help='Template names to generate (default: all)')
    parser.add_argument('--list', action='store_true', help='List available templates')
    parser.add_argument('--render', action='store_true', help='Also render with entangler')
    parser.add_argument('--density', type=int, default=1200, help='Render density')
    args = parser.parse_args()

    if args.list:
        print(f'{len(TEMPLATES)} templates available:')
        for name, fn in sorted(TEMPLATES.items()):
            spec = fn()
            print(f'  {name:20s}  {spec["name"]:25s}  {len(spec["layers"]):2d} layers')
        return

    targets = args.templates if args.templates else list(TEMPLATES.keys())
    generated = 0

    for name in targets:
        if name not in TEMPLATES:
            print(f'  [skip] Unknown template: {name}')
            continue

        key, spec, shape_map, color_map = generate_object(TEMPLATES[name])
        sp, cp = save_object(key, spec, shape_map, color_map)
        print(f'  [ok] {spec["name"]:25s}  {len(spec["layers"]):2d} layers  -> {key}.shape.json')
        generated += 1

        if args.render:
            sys.path.insert(0, PROJECT_DIR)
            from gallery.entangler_render import render_object_entangler
            renders_dir = os.path.join(PROJECT_DIR, 'gallery', 'renders')
            result = render_object_entangler(
                key, shape_map, color_map, renders_dir,
                density=args.density,
            )
            rt = result.get('render_time_s', '?')
            print(f'         rendered in {rt}s -> {result.get("filename", "?")}')

    print(f'\n  Generated {generated} objects.')


if __name__ == '__main__':
    main()
