"""
Volume → Geometry Converter for MatterShaper.

Given a volume (m³), shape type, and aspect ratio, returns primitive
dimensions in render units where 1 unit = 10 cm.

The LLM specifies topology and proportions; physics computes actual size.
"""

import math

# 1 render unit = 0.10 m
_M_PER_UNIT = 0.10
_UNITS_PER_M = 10.0


def sphere_dims(volume_m3: float) -> dict:
    """{'radius': float} in render units."""
    r_m = (3 * volume_m3 / (4 * math.pi)) ** (1 / 3)
    return {'radius': _r(r_m)}


def ellipsoid_dims(volume_m3: float, aspect: list = None) -> dict:
    """{'radii': [rx, ry, rz]} in render units.

    aspect = [x_ratio, y_ratio, z_ratio] — proportions, not absolute sizes.
    e.g. [1, 2, 1] → twice as tall as wide.
    """
    if not aspect or len(aspect) < 3:
        aspect = [1.0, 1.0, 1.0]
    ax, ay, az = float(aspect[0]), float(aspect[1]), float(aspect[2])
    # V = (4/3)π ax·ay·az·s³  →  s = (3V / (4π ax ay az))^(1/3)
    s = (3 * volume_m3 / (4 * math.pi * ax * ay * az)) ** (1 / 3)
    return {'radii': [_r(ax * s), _r(ay * s), _r(az * s)]}


def cylinder_dims(volume_m3: float, aspect: float = 1.5) -> dict:
    """{'radius': float, 'height': float} in render units.

    aspect = height / diameter  (so h = 2r × aspect).
    aspect 0.5 → flat puck   aspect 1.0 → height = diameter
    aspect 2.0 → tall, slim  aspect 3.0 → very tall
    """
    ar = float(aspect)
    # V = πr²h = πr²(2r·ar) = 2π·ar·r³
    r_m = (volume_m3 / (2 * math.pi * ar)) ** (1 / 3)
    h_m = 2 * r_m * ar
    return {'radius': _r(r_m), 'height': _r(h_m)}


def box_dims(volume_m3: float, aspect: list = None) -> dict:
    """{'size': [w, h, d]} in render units.

    aspect = [w_ratio, h_ratio, d_ratio].
    e.g. [2, 1, 1] → wide flat slab  [1, 3, 1] → tall thin box
    """
    if not aspect or len(aspect) < 3:
        aspect = [1.0, 1.0, 1.0]
    aw, ah, ad = float(aspect[0]), float(aspect[1]), float(aspect[2])
    s = (volume_m3 / (aw * ah * ad)) ** (1 / 3)
    return {'size': [_r(aw * s), _r(ah * s), _r(ad * s)]}


def torus_dims(volume_m3: float, aspect: float = 0.25) -> dict:
    """{'major_radius': float, 'minor_radius': float} in render units.

    aspect = minor_radius / major_radius  (tube thickness relative to ring size).
    0.1 → very thin ring   0.3 → chunky tube   0.5 → nearly spherical
    """
    tf = max(0.05, min(0.6, float(aspect)))
    # V = 2π²·R·r²  where r = tf·R  →  V = 2π²·tf²·R³
    R_m = (volume_m3 / (2 * math.pi ** 2 * tf ** 2)) ** (1 / 3)
    r_m = R_m * tf
    return {'major_radius': _r(R_m), 'minor_radius': _r(r_m)}


def cone_dims(volume_m3: float, aspect: float = 1.5, taper: float = 0.1) -> dict:
    """{'height': float, 'base_radius': float, 'top_radius': float} in render units.

    aspect = height / (2 × base_radius).
    taper  = top_radius / base_radius  (0 = sharp point, 1 = cylinder).
    """
    ar = float(aspect)
    t = max(0.0, min(1.0, float(taper)))
    # V = (πh/3)(r1² + r1·r2 + r2²)  h=2·ar·r1  r2=t·r1
    # V = (π·2·ar·r1/3)·r1²·(1 + t + t²) = (2π·ar/3)·(1+t+t²)·r1³
    coeff = (2 * math.pi * ar / 3) * (1 + t + t * t)
    r1_m = (volume_m3 / coeff) ** (1 / 3)
    return {
        'height':      _r(2 * ar * r1_m),
        'base_radius': _r(r1_m),
        'top_radius':  _r(t * r1_m),
    }


def dims_from_component(shape_type: str, volume_m3: float,
                         aspect=None, taper: float = 0.1) -> dict:
    """Dispatch to the right geometry function for a given shape type.

    Returns a dict with the correct field names for that primitive.
    aspect meaning per type:
      sphere    — ignored (symmetric)
      ellipsoid — list [rx, ry, rz] proportions
      cylinder  — scalar h/d ratio
      box       — list [w, h, d] proportions
      torus     — scalar minor/major ratio
      cone      — scalar h/(2r) ratio
    """
    st = shape_type.lower()
    if st == 'sphere':
        return sphere_dims(volume_m3)
    elif st == 'ellipsoid':
        return ellipsoid_dims(volume_m3, aspect if isinstance(aspect, list) else None)
    elif st == 'cylinder':
        ar = float(aspect[0] if isinstance(aspect, list) else aspect) if aspect is not None else 1.5
        return cylinder_dims(volume_m3, ar)
    elif st == 'box':
        return box_dims(volume_m3, aspect if isinstance(aspect, list) else None)
    elif st == 'torus':
        ar = float(aspect[0] if isinstance(aspect, list) else aspect) if aspect is not None else 0.25
        return torus_dims(volume_m3, ar)
    elif st == 'cone':
        ar = float(aspect[0] if isinstance(aspect, list) else aspect) if aspect is not None else 1.5
        return cone_dims(volume_m3, ar, taper)
    else:
        # Unknown: treat as sphere of same volume
        return sphere_dims(volume_m3)


def volume_of_layer(layer: dict) -> float:
    """Compute volume in m³ for an existing sigma layer dict.

    Inverse of dims_from_component — useful for reporting.
    """
    u = _M_PER_UNIT
    lt = layer.get('type', '')
    if lt == 'sphere':
        r = layer.get('radius', 0) * u
        return (4 / 3) * math.pi * r ** 3
    elif lt == 'ellipsoid':
        rx, ry, rz = [x * u for x in layer.get('radii', [0, 0, 0])]
        return (4 / 3) * math.pi * rx * ry * rz
    elif lt == 'cylinder':
        r = layer.get('radius', 0) * u
        h = layer.get('height', 0) * u
        return math.pi * r ** 2 * h
    elif lt == 'box':
        s = layer.get('size', [0, 0, 0])
        return s[0] * u * s[1] * u * s[2] * u
    elif lt == 'torus':
        R = layer.get('major_radius', 0) * u
        r = layer.get('minor_radius', 0) * u
        return 2 * math.pi ** 2 * R * r ** 2
    elif lt == 'cone':
        r1 = layer.get('base_radius', 0) * u
        r2 = layer.get('top_radius', 0) * u
        h  = layer.get('height', 0) * u
        return (math.pi * h / 3) * (r1 ** 2 + r1 * r2 + r2 ** 2)
    return 0.0


# ── Internal helper ──────────────────────────────────────────────────────────

def _r(m: float) -> float:
    """Convert metres to render units, rounded to 3 dp."""
    return round(m * _UNITS_PER_M, 3)
