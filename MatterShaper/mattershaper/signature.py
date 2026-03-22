"""
Shape Signatures — save and reload object definitions.

A shape signature is a JSON-serializable list of primitives that defines
an object. Each primitive is stored as:
    {
        "type": "sphere" | "ellipsoid",
        "pos": [x, y, z],           # center of mass / position
        "radius": float,             # sphere only
        "radii": [a, b, c],          # ellipsoid only
        "rotate": [rx, ry, rz],      # ellipsoid only (Euler radians)
        "material": "ceramic" | {...} # name or custom dict
    }

The signature captures the shape's DNA — every bump, ridge, curve.
Load it, place it anywhere in a scene, scale it, rotate it. The math
IS the shape. No vertices. No triangle soup. Pure equations.

    # Save a cup shape
    sig = ShapeSignature("coffee_cup")
    sig.sphere(pos=(0, 0.5, 0), radius=0.065, material="ceramic")
    sig.sphere(pos=(0.06, 0.5, 0), radius=0.065, material="ceramic")
    ...
    sig.save("coffee_cup.shape.json")

    # Load and place it in a scene
    cup = ShapeSignature.load("coffee_cup.shape.json")
    cup.place(ms, offset=(2, 0, -3), scale=1.5)

    # Or stamp it multiple times
    cup.place(ms, offset=(-1, 0, -3))  # left cup
    cup.place(ms, offset=(1, 0, -3))   # right cup
"""

import json
import math
import os

from .geometry.primitives import Vec3
from .geometry.ellipsoid import rotation_matrix


class ShapeSignature:
    """A reusable shape definition — the DNA of an object.

    Stores a list of primitives (spheres, ellipsoids) with positions,
    sizes, orientations, and materials. Can be saved to JSON, loaded,
    and stamped into any scene at any position and scale.
    """

    def __init__(self, name="untitled", description=""):
        self.name = name
        self.description = description
        self.primitives = []
        self._bounds_dirty = True
        self._center_of_mass = None
        self._bounding_box = None

    def __repr__(self):
        return (f"ShapeSignature('{self.name}', "
                f"{len(self.primitives)} primitives, "
                f"center={self.center_of_mass})")

    # ── Building ─────────────────────────────────────────────────

    def sphere(self, pos=(0, 0, 0), radius=0.1, material="ceramic"):
        """Add a sphere to the signature."""
        self.primitives.append({
            "type": "sphere",
            "pos": list(pos) if isinstance(pos, (tuple, list)) else [pos.x, pos.y, pos.z],
            "radius": float(radius),
            "material": _serialize_material(material),
        })
        self._bounds_dirty = True
        return self

    def ellipsoid(self, pos=(0, 0, 0), radii=(0.1, 0.1, 0.1),
                  rotate=(0, 0, 0), material="ceramic"):
        """Add an ellipsoid to the signature."""
        self.primitives.append({
            "type": "ellipsoid",
            "pos": list(pos) if isinstance(pos, (tuple, list)) else [pos.x, pos.y, pos.z],
            "radii": list(radii) if isinstance(radii, (tuple, list)) else [radii.x, radii.y, radii.z],
            "rotate": list(rotate) if isinstance(rotate, (tuple, list)) else [0, 0, 0],
            "material": _serialize_material(material),
        })
        self._bounds_dirty = True
        return self

    # ── Analysis ─────────────────────────────────────────────────

    @property
    def count(self):
        """Number of primitives in the signature."""
        return len(self.primitives)

    @property
    def center_of_mass(self):
        """Geometric center of all primitive positions."""
        if self._bounds_dirty:
            self._compute_bounds()
        return self._center_of_mass

    @property
    def bounding_box(self):
        """Axis-aligned bounding box: ((min_x, min_y, min_z), (max_x, max_y, max_z))."""
        if self._bounds_dirty:
            self._compute_bounds()
        return self._bounding_box

    def _compute_bounds(self):
        if not self.primitives:
            self._center_of_mass = (0, 0, 0)
            self._bounding_box = ((0, 0, 0), (0, 0, 0))
            self._bounds_dirty = False
            return

        sum_x = sum_y = sum_z = 0
        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')

        for p in self.primitives:
            x, y, z = p["pos"]
            sum_x += x; sum_y += y; sum_z += z

            # Rough bounding extent
            if p["type"] == "sphere":
                r = p["radius"]
                ext = (r, r, r)
            else:
                ext = tuple(max(p["radii"]) for _ in range(3))  # conservative for rotated

            min_x = min(min_x, x - ext[0])
            min_y = min(min_y, y - ext[1])
            min_z = min(min_z, z - ext[2])
            max_x = max(max_x, x + ext[0])
            max_y = max(max_y, y + ext[1])
            max_z = max(max_z, z + ext[2])

        n = len(self.primitives)
        self._center_of_mass = (sum_x / n, sum_y / n, sum_z / n)
        self._bounding_box = ((min_x, min_y, min_z), (max_x, max_y, max_z))
        self._bounds_dirty = False

    # ── Placement ────────────────────────────────────────────────

    def place(self, ms, offset=(0, 0, 0), scale=1.0):
        """Stamp this shape into a MatterShaper scene.

        Args:
            ms: MatterShaper instance
            offset: (x, y, z) world position offset
            scale: uniform scale factor (1.0 = original size)

        Returns: ms (for chaining)
        """
        ox, oy, oz = offset

        for p in self.primitives:
            px, py, pz = p["pos"]
            # Apply scale relative to signature's center of mass
            cx, cy, cz = self.center_of_mass
            sx = ox + (px - cx) * scale + cx
            sy = oy + (py - cy) * scale + cy
            sz = oz + (pz - cz) * scale + cz

            mat = _deserialize_material(p["material"])

            if p["type"] == "sphere":
                ms.sphere(
                    pos=(sx, sy, sz),
                    radius=p["radius"] * scale,
                    material=mat,
                )
            elif p["type"] == "ellipsoid":
                radii = tuple(r * scale for r in p["radii"])
                ms.ellipsoid(
                    pos=(sx, sy, sz),
                    radii=radii,
                    rotate=tuple(p.get("rotate", (0, 0, 0))),
                    material=mat,
                )

        return ms

    # ── Serialization ────────────────────────────────────────────

    def to_dict(self):
        """Serialize the full signature to a dict."""
        return {
            "name": self.name,
            "description": self.description,
            "version": "1.0",
            "primitive_count": len(self.primitives),
            "center_of_mass": list(self.center_of_mass),
            "bounding_box": [list(self.bounding_box[0]), list(self.bounding_box[1])],
            "primitives": self.primitives,
        }

    def save(self, filepath):
        """Save signature to a JSON file.

        Convention: use .shape.json extension.
        """
        os.makedirs(os.path.dirname(os.path.abspath(filepath)) or '.', exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        return filepath

    @classmethod
    def load(cls, filepath):
        """Load a signature from a JSON file."""
        with open(filepath) as f:
            data = json.load(f)

        sig = cls(
            name=data.get("name", "loaded"),
            description=data.get("description", ""),
        )
        sig.primitives = data["primitives"]
        sig._bounds_dirty = True
        return sig

    @classmethod
    def from_dict(cls, data):
        """Create a signature from a dict (e.g., parsed JSON)."""
        sig = cls(
            name=data.get("name", "parsed"),
            description=data.get("description", ""),
        )
        sig.primitives = data["primitives"]
        sig._bounds_dirty = True
        return sig

    # ── Capture from MatterShaper ────────────────────────────────

    @classmethod
    def capture(cls, ms, name="captured"):
        """Capture the current scene's objects as a signature.

        Reads all spheres and ellipsoids from the MatterShaper's scene
        and records them. Planes are skipped (they're infinite).
        """
        from .geometry.sphere import Sphere as SphereClass
        from .geometry.ellipsoid import Ellipsoid as EllipsoidClass

        sig = cls(name=name)

        for obj in ms.scene.objects:
            if isinstance(obj, SphereClass):
                sig.sphere(
                    pos=(obj.center.x, obj.center.y, obj.center.z),
                    radius=obj.radius,
                    material=_serialize_material(obj.material),
                )
            elif isinstance(obj, EllipsoidClass):
                sig.ellipsoid(
                    pos=(obj.center.x, obj.center.y, obj.center.z),
                    radii=(obj.radii.x, obj.radii.y, obj.radii.z),
                    rotate=(0, 0, 0),  # rotation extraction would need decomposition
                    material=_serialize_material(obj.material),
                )

        return sig


# ── Material serialization helpers ───────────────────────────────

def _serialize_material(mat):
    """Convert a Material or string to a JSON-safe representation."""
    if isinstance(mat, str):
        return mat
    if isinstance(mat, dict):
        return mat
    # It's a Material object
    from .materials.library import ALL_MATERIALS
    # Check if it matches a known material by name
    for key, known in ALL_MATERIALS.items():
        if mat is known:
            return key
    # Custom material — serialize its properties
    return {
        "name": getattr(mat, 'name', 'custom'),
        "color": [mat.color.x, mat.color.y, mat.color.z],
        "reflectance": mat.reflectance,
        "roughness": mat.roughness,
        "density_kg_m3": getattr(mat, 'density_kg_m3', 1000),
        "mean_Z": getattr(mat, 'mean_Z', 8),
        "mean_A": getattr(mat, 'mean_A', 16),
        "composition": getattr(mat, 'composition', ''),
    }


def _deserialize_material(data):
    """Convert a JSON material representation back to a usable material."""
    if isinstance(data, str):
        return data  # MatterShaper._resolve_material handles string lookup
    if isinstance(data, dict):
        return data  # MatterShaper handles dict→Material conversion
    return "ceramic"  # fallback
