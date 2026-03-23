"""
Physics-Driven Object Builder for MatterShaper / Nagatha.

Converts a COMPONENT_MANIFEST (LLM topology output) into a valid
Sigma Signature shape_map using real-world material densities.

The LLM decides:
  - What components exist (cylinder body, torus handle, etc.)
  - What material each component is made of
  - Proportions / aspect ratios
  - Position roles (how components relate spatially)
  - Total mass estimate

Physics (local_library + DENSITY_TABLE) computes:
  - Actual density for each material
  - Volume = mass_fraction × total_mass / density
  - Dimensions = geometry_builder(volume, shape_type, aspect)

Layout engine converts position roles to 3D coordinates.
"""

from .material_physics import get_density, get_phase
from .geometry_builder import dims_from_component


# ── Position roles ────────────────────────────────────────────────────────────
# Role → how to place relative to the running bounding box / parent.
#
# The layout engine maintains a simple state:
#   main_body:  the first 'base' component (sets the size reference)
#   top_y:      current stacking height
#   body_dims:  dimensions of the main body (for side attachment)

class LayoutState:
    """Tracks placement state as components are added."""

    def __init__(self):
        self.top_y = 0.0
        self.body_radius = 0.0   # for side-attachment reference
        self.body_center_y = 0.0
        self.body_height = 0.0
        self.placed = []         # list of {name, pos, dims, type}

    def place(self, name: str, shape_type: str, dims: dict,
              pos_role: str) -> list:
        """Return [x, y, z] center for this component.

        pos_role options:
          "base"       — bottom of stack (y=0 for first, else on top)
          "stack"      — same as base, stacks upward
          "top"        — sits at top of previous component
          "cap_top"    — thin layer on top of main body
          "cap_bottom" — thin layer at bottom of main body
          "side"       — offset sideways from main body, at mid-height
          "side_low"   — offset sideways, lower third
          "side_high"  — offset sideways, upper third
          "interior"   — same centre as main body (hollow or inset detail)
          "surface"    — slightly outside main body surface
          "wrap"       — concentric with previous, slightly larger radius
          "center"     — at scene origin (0, h/2, 0)
        """
        st = shape_type.lower()
        role = (pos_role or 'base').lower()

        # Half-extents of this component
        h = _height(st, dims)
        r = _radius(st, dims)

        if role in ('base', 'stack', ''):
            x, z = 0.0, 0.0
            y = self.top_y + h / 2
            self.top_y = self.top_y + h
            # First base component sets body reference
            if not self.placed:
                self.body_radius = r
                self.body_height = h
                self.body_center_y = y

        elif role == 'top':
            x, z = 0.0, 0.0
            y = self.top_y + h / 2
            self.top_y += h

        elif role == 'cap_top':
            x, z = 0.0, 0.0
            y = self.body_center_y + self.body_height / 2 + h / 2

        elif role == 'cap_bottom':
            x, z = 0.0, 0.0
            y = self.body_center_y - self.body_height / 2 - h / 2
            if y < 0:
                y = h / 2

        elif role in ('side', 'side_mid'):
            x = self.body_radius + r * 0.6
            z = 0.0
            y = self.body_center_y

        elif role == 'side_low':
            x = self.body_radius + r * 0.6
            z = 0.0
            y = self.body_center_y - self.body_height * 0.25

        elif role == 'side_high':
            x = self.body_radius + r * 0.6
            z = 0.0
            y = self.body_center_y + self.body_height * 0.25

        elif role == 'interior':
            x, z = 0.0, 0.0
            y = self.body_center_y

        elif role in ('surface', 'wrap'):
            x, z = 0.0, 0.0
            y = self.body_center_y

        elif role == 'center':
            x, z = 0.0, 0.0
            y = h / 2

        else:
            # Fallback: stack
            x, z = 0.0, 0.0
            y = self.top_y + h / 2
            self.top_y += h

        pos = [round(x, 3), round(y, 3), round(z, 3)]
        self.placed.append({'name': name, 'type': shape_type, 'pos': pos, 'dims': dims})
        return pos


def _height(shape_type: str, dims: dict) -> float:
    """Approximate Y-extent of a component from its dims dict."""
    st = shape_type.lower()
    if st == 'sphere':
        return dims.get('radius', 0.1) * 2
    elif st == 'ellipsoid':
        return dims.get('radii', [0.1, 0.1, 0.1])[1] * 2
    elif st == 'cylinder':
        return dims.get('height', 0.1)
    elif st == 'box':
        return dims.get('size', [0.1, 0.1, 0.1])[1]
    elif st == 'torus':
        return dims.get('minor_radius', 0.05) * 2
    elif st == 'cone':
        return dims.get('height', 0.1)
    return 0.1


def _radius(shape_type: str, dims: dict) -> float:
    """Approximate XZ half-width of a component."""
    st = shape_type.lower()
    if st == 'sphere':
        return dims.get('radius', 0.1)
    elif st == 'ellipsoid':
        r = dims.get('radii', [0.1, 0.1, 0.1])
        return max(r[0], r[2])
    elif st == 'cylinder':
        return dims.get('radius', 0.1)
    elif st == 'box':
        s = dims.get('size', [0.1, 0.1, 0.1])
        return max(s[0], s[2]) / 2
    elif st == 'torus':
        return dims.get('major_radius', 0.1) + dims.get('minor_radius', 0.02)
    elif st == 'cone':
        return dims.get('base_radius', 0.1)
    return 0.1


# ── Main build function ───────────────────────────────────────────────────────

def build_sigma_from_manifest(manifest: dict) -> dict:
    """Convert a COMPONENT_MANIFEST to a Sigma Signature shape_map.

    manifest format:
    {
      "object_name": str,
      "total_mass_kg": float,
      "components": [
        {
          "name": str,
          "material": str,
          "shape_type": "sphere"|"cylinder"|"box"|"ellipsoid"|"torus"|"cone",
          "mass_fraction": float,      # fraction of total_mass_kg
          "aspect": float | list,      # proportion hint (shape-type dependent)
          "taper": float,              # cone only: top_r / base_r
          "pos_role": str,             # layout hint
          "rotate": [rx, ry, rz],      # optional Euler rotation (radians)
        },
        ...
      ],
      "provenance": str
    }

    Returns a shape_map dict (sigma structure).
    """
    object_name = manifest.get('object_name', 'object')
    total_mass_kg = float(manifest.get('total_mass_kg', 1.0))
    components = manifest.get('components', [])
    provenance = manifest.get('provenance', 'physics-built by Nagatha')

    # Normalise mass fractions so they sum to 1
    raw_fractions = [float(c.get('mass_fraction', 1.0)) for c in components]
    total_frac = sum(raw_fractions) or 1.0
    fractions = [f / total_frac for f in raw_fractions]

    layout = LayoutState()
    layers = []
    physics_log = []

    for comp, frac in zip(components, fractions):
        mat_name  = comp.get('material', 'generic')
        shape_type = comp.get('shape_type', 'sphere')
        aspect    = comp.get('aspect', None)
        taper     = float(comp.get('taper', 0.1))
        pos_role  = comp.get('pos_role', 'base')
        rotate    = comp.get('rotate', None)

        # ── Physics: mass → volume → dimensions ──────────────────────────
        mass_kg  = total_mass_kg * frac
        density  = get_density(mat_name)
        phase    = get_phase(mat_name)
        volume_m3 = mass_kg / density

        dims = dims_from_component(shape_type, volume_m3, aspect, taper)

        physics_log.append({
            'component': comp.get('name', mat_name),
            'material':  mat_name,
            'density_kg_m3': round(density, 1),
            'phase':     phase,
            'mass_kg':   round(mass_kg, 4),
            'volume_cm3': round(volume_m3 * 1e6, 2),
            'dims':      dims,
        })

        # ── Layout: pos_role → 3D position ────────────────────────────────
        pos = layout.place(comp.get('name', mat_name), shape_type, dims, pos_role)

        # ── Build sigma layer ─────────────────────────────────────────────
        layer = {
            'type': shape_type,
            'material': _mat_key(mat_name),
        }

        # Merge dims into layer
        if shape_type == 'cone':
            layer['base_pos'] = pos
            layer.update(dims)
        else:
            layer['pos'] = pos
            layer.update(dims)

        if rotate:
            layer['rotate'] = rotate

        layers.append(layer)

    shape_map = {
        'name':       object_name,
        'layers':     layers,
        'provenance': provenance,
        'physics': {
            'total_mass_kg': total_mass_kg,
            'components':    physics_log,
            'builder':       'mattershaper.physics.object_builder',
        },
    }

    return shape_map


def _mat_key(name: str) -> str:
    """Normalise material name to a valid identifier."""
    return name.lower().replace(' ', '_').replace('-', '_')


# ── Manifest validation ───────────────────────────────────────────────────────

def validate_manifest(manifest: dict) -> list:
    """Return list of error strings (empty = valid)."""
    errors = []

    if 'object_name' not in manifest:
        errors.append("manifest missing 'object_name'")
    if 'total_mass_kg' not in manifest:
        errors.append("manifest missing 'total_mass_kg'")
    elif not isinstance(manifest['total_mass_kg'], (int, float)):
        errors.append("total_mass_kg must be a number")
    if 'components' not in manifest or not manifest['components']:
        errors.append("manifest missing 'components' list")
        return errors

    valid_shapes = {'sphere', 'ellipsoid', 'cylinder', 'box', 'torus', 'cone'}
    for i, c in enumerate(manifest['components']):
        if 'material' not in c:
            errors.append(f"component[{i}] missing 'material'")
        if 'shape_type' not in c:
            errors.append(f"component[{i}] missing 'shape_type'")
        elif c['shape_type'] not in valid_shapes:
            errors.append(
                f"component[{i}] unknown shape_type '{c['shape_type']}'"
                f" — valid: {sorted(valid_shapes)}"
            )
        frac = c.get('mass_fraction', 1.0)
        if not isinstance(frac, (int, float)) or frac <= 0:
            errors.append(f"component[{i}] mass_fraction must be > 0")

    return errors
