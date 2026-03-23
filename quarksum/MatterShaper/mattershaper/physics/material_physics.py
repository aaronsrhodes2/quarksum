"""
Material Physics — density & thermal lookup for MatterShaper.

Priority chain:
  1. local_library (predict_density_kg_m3 from atomic number) — exact physics
  2. DENSITY_TABLE — curated everyday materials (measured values)
  3. 1800 kg/m³ generic solid fallback

Usage:
    from mattershaper.physics.material_physics import get_density, get_phase
    rho = get_density('ceramic')          # 2300 kg/m³
    rho = get_density('iron')             # 7874 from local_library
    phase = get_phase('water', T_K=300)   # 'liquid'
"""

import sys
from pathlib import Path

# local_library sits four levels up from this file
_LOCAL_LIB = Path(__file__).resolve().parents[4] / 'local_library'

# ── Element Z lookup ──────────────────────────────────────────────────────────
_ELEMENT_Z = {
    'hydrogen': 1,  'carbon': 6,    'nitrogen': 7,  'oxygen': 8,
    'sodium': 11,   'magnesium': 12,'aluminum': 13, 'silicon': 14,
    'phosphorus': 15,'sulfur': 16,  'chlorine': 17, 'argon': 18,
    'potassium': 19,'calcium': 20,  'titanium': 22, 'chromium': 24,
    'iron': 26,     'cobalt': 27,   'nickel': 28,   'copper': 29,
    'zinc': 30,     'gallium': 31,  'germanium': 32,'arsenic': 33,
    'silver': 47,   'tin': 50,      'gold': 79,     'tungsten': 74,
    'lead': 82,     'platinum': 78, 'palladium': 46,'rhodium': 45,
}

# ── Curated density table (kg/m³) ─────────────────────────────────────────────
# Values from engineering handbooks / Wikipedia
DENSITY_TABLE = {
    # Metals (fallback; local_library preferred for these)
    'steel': 7900,       'cast_iron': 7200,    'stainless_steel': 8000,
    'chrome': 7190,      'brass': 8500,         'bronze': 8800,
    'solder': 9000,      'pewter': 9750,

    # Ceramics / minerals
    'ceramic': 2300,     'porcelain': 2400,     'terracotta': 1800,
    'glass': 2500,       'borosilicate_glass': 2230, 'tempered_glass': 2530,
    'marble': 2700,      'granite': 2700,       'limestone': 2500,
    'sandstone': 2200,   'slate': 2700,         'obsidian': 2350,
    'stone': 2600,       'concrete': 2300,      'mortar': 2100,
    'brick': 1900,       'sand': 1600,          'clay': 1750,
    'plaster': 1800,     'gypsum': 2320,        'chalk': 2500,
    'quartz': 2650,      'basalt': 2900,

    # Wood
    'oak': 750,          'dark_oak_wood': 760,  'light_oak': 740,
    'pine': 550,         'spruce': 450,         'cedar': 380,
    'mahogany': 700,     'walnut': 680,         'teak': 900,
    'bamboo': 800,       'plywood': 600,        'mdf': 750,
    'wood': 650,         'dark_wood': 730,      'light_wood': 500,
    'balsa': 160,        'hardwood': 800,       'softwood': 500,
    'chipboard': 650,

    # Polymers / plastics
    'rubber': 1200,      'natural_rubber': 1100,'silicone': 1100,
    'plastic': 950,      'polyethylene': 950,   'polypropylene': 900,
    'pvc': 1400,         'abs_plastic': 1050,   'nylon': 1150,
    'polycarbonate': 1200,'acrylic': 1180,      'teflon': 2200,
    'foam': 50,          'polystyrene_foam': 30,'memory_foam': 50,
    'epoxy': 1300,       'fiberglass': 1800,    'carbon_fiber': 1600,
    'bakelite': 1400,

    # Organic / biological
    'leather': 860,      'suede': 860,
    'fabric': 350,       'cotton': 500,         'wool': 600,
    'silk': 500,         'canvas': 750,         'denim': 900,
    'paper': 800,        'cardboard': 680,      'kraft_paper': 850,
    'wax': 900,          'paraffin': 870,       'beeswax': 960,
    'cork': 200,
    'bone': 1800,        'ivory': 1850,
    'flesh': 1050,       'skin': 1100,
    'fat': 900,          'muscle': 1050,

    # Food
    'water': 1000,       'ice': 917,            'salt': 2160,
    'sugar': 1590,       'flour': 600,          'flour_bulk': 700,
    'honey': 1400,       'oil': 870,            'coffee': 330,

    # Paints / coatings
    'paint': 1200,       'enamel': 1300,        'lacquer': 1100,
    'varnish': 1050,     'primer': 1300,
    'red_paint': 1200,   'black_paint': 1200,   'white_paint': 1200,
    'blue_paint': 1200,  'green_paint': 1200,   'yellow_paint': 1200,

    # Other
    'air': 1.2,          'steam': 0.6,          'co2': 1.96,
    'cardboard': 680,
}

# ── Melting/boiling points (K) for phase determination ───────────────────────
# Only materials where phase at room temperature might be ambiguous or important
_MELTING_K = {
    'water': 273.15,  'ice': 273.15,  'wax': 330,  'paraffin': 325,
    'solder': 456,    'lead': 600,    'tin': 505,   'bismuth': 544,
    'gallium': 303,   'mercury': 234,
}
_BOILING_K = {
    'water': 373.15, 'air': 87, 'nitrogen': 77, 'oxygen': 90,
}

ROOM_TEMP_K = 293.15  # 20°C


def get_density(material_name: str) -> float:
    """Return density in kg/m³ for a material name string.

    Normalises the name (lower, underscores), then tries:
      1. local_library.interface.element.predict_density_kg_m3 (by Z)
      2. DENSITY_TABLE exact match
      3. DENSITY_TABLE keyword substring match
      4. 1800 kg/m³ generic solid fallback
    """
    key = material_name.lower().replace(' ', '_').replace('-', '_')

    # 1 — local_library for pure elements
    z = _ELEMENT_Z.get(key)
    if z is not None:
        try:
            if str(_LOCAL_LIB) not in sys.path:
                sys.path.insert(0, str(_LOCAL_LIB))
            from interface.element import predict_density_kg_m3
            return predict_density_kg_m3(z)
        except Exception:
            pass  # fall through

    # 2 — exact match in curated table
    if key in DENSITY_TABLE:
        return DENSITY_TABLE[key]

    # 3 — keyword substring (e.g. "glazed_ceramic" → "ceramic")
    best_len = 0
    best_rho = None
    for kw, rho in DENSITY_TABLE.items():
        if kw in key and len(kw) > best_len:
            best_len = len(kw)
            best_rho = rho
    if best_rho is not None:
        return best_rho

    # 4 — generic solid fallback
    return 1800.0


def get_phase(material_name: str, T_K: float = ROOM_TEMP_K) -> str:
    """Return 'solid', 'liquid', or 'gas' for a material at temperature T_K.

    Uses melting/boiling points where known; defaults to 'solid' for most
    engineering materials at room temperature.
    """
    key = material_name.lower().replace(' ', '_').replace('-', '_')
    mp = _MELTING_K.get(key)
    bp = _BOILING_K.get(key)

    if bp is not None and T_K >= bp:
        return 'gas'
    if mp is not None and T_K >= mp:
        return 'liquid'

    # Air and named gases are always gas at room temp
    if key in ('air', 'steam', 'co2', 'nitrogen', 'oxygen', 'hydrogen'):
        return 'gas'

    return 'solid'


def material_report(material_name: str, T_K: float = ROOM_TEMP_K) -> dict:
    """Return a summary dict of physics properties for a material."""
    rho = get_density(material_name)
    phase = get_phase(material_name, T_K)

    report = {
        'material': material_name,
        'density_kg_m3': rho,
        'phase': phase,
        'T_K': T_K,
    }

    # Add thermal color if hot enough to glow
    try:
        if str(_LOCAL_LIB) not in sys.path:
            sys.path.insert(0, str(_LOCAL_LIB))
        from interface.thermal import blackbody_color, is_visibly_glowing
        report['visibly_glowing'] = is_visibly_glowing(T_K)
        if report['visibly_glowing']:
            report['emission_rgb'] = list(blackbody_color(T_K))
    except Exception:
        pass

    return report
