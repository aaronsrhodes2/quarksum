"""
Material Resolver — map semantic material names to physics-grounded Material objects.

When Nagatha names a layer material (e.g. "dark_oak_wood", "chrome_handle",
"red_painted_metal"), this module resolves that name to a real Material from
the library via keyword matching.  The LLM only has to name things correctly;
it never has to invent color values.
"""

from .library import (
    ALL_MATERIALS,
    # metals
    ALUMINUM, COPPER, BRASS, CHROME, GOLD, SILVER, STEEL, IRON, CAST_IRON,
    # wood
    OAK, DARK_WOOD, LIGHT_WOOD,
    # polymers
    RUBBER, PLASTIC_BLACK, PLASTIC_WHITE,
    # paints
    PAINT_WHITE, PAINT_RED, PAINT_BLUE, PAINT_YELLOW, PAINT_GREEN, PAINT_BLACK,
    # ceramic / stone
    CERAMIC, TERRACOTTA, MARBLE, CONCRETE, STONE, BRICK, GLASS,
    # organic / fabric
    LEAF_GREEN, FLESH, FABRIC, LEATHER, WAX, WATER,
)


# ── Keyword → Material priority table ────────────────────────────────
# Checked in order; first match wins.
_KEYWORD_MAP = [
    # ---- Metals ----
    ('chrome',      CHROME),
    ('polished_metal', CHROME),
    ('gold',        GOLD),
    ('silver',      SILVER),
    ('copper',      COPPER),
    ('brass',       BRASS),
    ('bronze',      BRASS),   # bronze ≈ brass for rendering
    ('aluminum',    ALUMINUM),
    ('aluminium',   ALUMINUM),
    ('cast_iron',   CAST_IRON),
    ('iron',        IRON),
    ('steel',       STEEL),
    ('metal',       STEEL),
    # ---- Wood ----
    ('dark_wood',   DARK_WOOD),
    ('dark_oak',    DARK_WOOD),
    ('mahogany',    DARK_WOOD),
    ('walnut',      DARK_WOOD),
    ('light_wood',  LIGHT_WOOD),
    ('pine',        LIGHT_WOOD),
    ('maple',       LIGHT_WOOD),
    ('birch',       LIGHT_WOOD),
    ('oak',         OAK),
    ('wood',        OAK),
    ('timber',      OAK),
    # ---- Polymers ----
    ('rubber',      RUBBER),
    ('silicone',    RUBBER),
    ('plastic_black', PLASTIC_BLACK),
    ('plastic_dark',  PLASTIC_BLACK),
    ('plastic_white', PLASTIC_WHITE),
    ('plastic',     PLASTIC_BLACK),
    ('abs',         PLASTIC_BLACK),
    ('pvc',         PLASTIC_BLACK),
    ('nylon',       PLASTIC_WHITE),
    # ---- Paints ----
    ('white',       PAINT_WHITE),
    ('cream',       PAINT_WHITE),
    ('ivory',       PAINT_WHITE),
    ('red',         PAINT_RED),
    ('crimson',     PAINT_RED),
    ('scarlet',     PAINT_RED),
    ('maroon',      PAINT_RED),
    ('blue',        PAINT_BLUE),
    ('navy',        PAINT_BLUE),
    ('cobalt',      PAINT_BLUE),
    ('yellow',      PAINT_YELLOW),
    ('amber',       PAINT_YELLOW),
    ('orange',      PAINT_RED),   # reddish-orange approximation
    ('green',       PAINT_GREEN),
    ('black',       PAINT_BLACK),
    ('dark',        PAINT_BLACK),
    # ---- Ceramic / Stone ----
    ('ceramic',     CERAMIC),
    ('porcelain',   CERAMIC),
    ('glaze',       CERAMIC),
    ('terracotta',  TERRACOTTA),
    ('marble',      MARBLE),
    ('concrete',    CONCRETE),
    ('cement',      CONCRETE),
    ('stone',       STONE),
    ('granite',     STONE),
    ('brick',       BRICK),
    ('glass',       GLASS),
    ('crystal',     GLASS),
    # ---- Organic ----
    ('leaf',        LEAF_GREEN),
    ('plant',       LEAF_GREEN),
    ('foliage',     LEAF_GREEN),
    ('flesh',       FLESH),
    ('skin',        FLESH),
    ('fabric',      FABRIC),
    ('cloth',       FABRIC),
    ('canvas',      FABRIC),
    ('cotton',      FABRIC),
    ('wool',        FABRIC),
    ('leather',     LEATHER),
    ('hide',        LEATHER),
    ('wax',         WAX),
    ('candle',      WAX),
    ('water',       WATER),
    ('liquid',      WATER),
]


def resolve_material(name: str):
    """Return a Material for the given semantic name (fuzzy match).

    Args:
        name: free-form material name, e.g. "dark_oak_wood", "chrome_handle"

    Returns:
        Material instance from library.py
    """
    key = name.lower().replace(' ', '_').replace('-', '_')

    # Exact match first
    if key in ALL_MATERIALS:
        return ALL_MATERIALS[key]

    # Keyword scan
    for keyword, mat in _KEYWORD_MAP:
        if keyword in key:
            return mat

    # Fallback — generic grey steel-ish material
    return STEEL


def material_to_color_entry(mat, label: str = None) -> dict:
    """Serialize a Material to a COLOR_MAP materials-dict entry."""
    c = mat.color
    return {
        'label':          label or mat.name,
        'color':          [round(c.x, 4), round(c.y, 4), round(c.z, 4)],
        'reflectance':    mat.reflectance,
        'roughness':      mat.roughness,
        'density_kg_m3':  mat.density_kg_m3,
        'mean_Z':         mat.mean_Z,
        'mean_A':         mat.mean_A,
        'composition':    mat.composition,
    }


def build_color_map(shape_map: dict) -> dict:
    """Auto-build a COLOR_MAP from a SHAPE_MAP by resolving each layer's material.

    Args:
        shape_map: parsed shape map dict with a 'layers' list

    Returns:
        Full color_map dict ready for validate_maps / render_from_maps
    """
    materials = {}
    for layer in shape_map.get('layers', []):
        mat_name = layer.get('material') or layer.get('mat') or 'unknown'
        if mat_name and mat_name not in materials:
            mat = resolve_material(mat_name)
            materials[mat_name] = material_to_color_entry(mat, label=mat_name)

    return {
        'materials': materials,
        'provenance': 'auto-resolved from MatterShaper material library',
    }
