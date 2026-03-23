"""
MatterShaper — the single entry point.

Like local_library's Universe class: one object, fluent API, everything
accessible through methods. Build → Light → Camera → Render.

    ms = MatterShaper()
    ms.sphere(...)
    ms.light(...)
    ms.camera(...)
    ms.render('output.png')
"""

import math
import os
import struct
import zlib

from .geometry.primitives import Vec3, Ray
from .geometry.sphere import Sphere
from .geometry.ellipsoid import Ellipsoid, rotation_matrix
from .geometry.plane import Plane
from .geometry.cone import Cone
from .materials.material import Material
from .materials.library import ALL_MATERIALS
from .camera import Camera
from .render.raytracer import Light, Scene, render_scene, render_to_svg


def _resolve_material(mat):
    """Accept a Material, a string name, or a dict of properties."""
    if isinstance(mat, Material):
        return mat
    if isinstance(mat, str):
        key = mat.lower().strip()
        if key in ALL_MATERIALS:
            return ALL_MATERIALS[key]
        raise ValueError(
            f"Unknown material '{mat}'. "
            f"Available: {', '.join(sorted(ALL_MATERIALS.keys()))}"
        )
    if isinstance(mat, dict):
        color = mat.get('color', (0.5, 0.5, 0.5))
        if isinstance(color, (tuple, list)):
            color = Vec3(*color)
        return Material(
            name=mat.get('name', 'custom'),
            color=color,
            reflectance=mat.get('reflectance', 0.1),
            roughness=mat.get('roughness', 0.5),
        )
    raise TypeError(f"Material must be a string, Material, or dict. Got {type(mat)}")


def _to_vec3(v):
    """Convert tuple/list/Vec3 to Vec3."""
    if isinstance(v, Vec3):
        return v
    if isinstance(v, (tuple, list)):
        return Vec3(*v)
    raise TypeError(f"Expected Vec3 or tuple, got {type(v)}")


class MatterShaper:
    """Build and render 3D scenes from pure math.

    This is the single entry point for MatterShaper. It mirrors
    local_library's Universe class: one object, method-based,
    everything accessible from here.

    Usage:
        ms = MatterShaper()

        # Add geometry (returns self for chaining)
        ms.sphere(pos=(0, 0.5, -3), radius=0.5, material='ceramic')
        ms.ellipsoid(pos=(1, 0, -4), radii=(0.5, 0.3, 0.5), material='iron')
        ms.plane(y=0, material='steel')

        # Add lighting
        ms.light(pos=(3, 5, 2), intensity=1.0)
        ms.ambient(0.1, 0.1, 0.12)

        # Set camera
        ms.camera(pos=(0, 2, 2), look_at=(0, 0, -3), fov=55)

        # Render
        ms.render('scene.svg', width=400, height=300)
        ms.render('scene.png', width=400, height=300)

    Available materials (by name):
        ceramic, steel, glass, water, basalt, iron,
        ice, carbon, silicate, regolith

    Or pass a custom Material:
        from mattershaper import Material, Vec3
        gold = Material(name='Gold', color=Vec3(1.0, 0.84, 0),
                        reflectance=0.8, roughness=0.1,
                        density_kg_m3=19300, mean_Z=79, mean_A=197)
        ms.sphere(pos=(0, 0, -3), radius=0.5, material=gold)
    """

    def __init__(self, background=None):
        self._scene = Scene()
        self._camera = None
        self._object_count = 0

        if background:
            self._scene.background = _to_vec3(background)

    def __repr__(self):
        n_obj = len(self._scene.objects)
        n_light = len(self._scene.lights)
        cam = "set" if self._camera else "not set"
        return f"MatterShaper({n_obj} objects, {n_light} lights, camera={cam})"

    # ── Geometry ─────────────────────────────────────────────────────

    def sphere(self, pos=(0, 0, 0), radius=1.0, material='ceramic'):
        """Add a sphere to the scene.

        Args:
            pos: (x, y, z) center position
            radius: sphere radius in scene units
            material: string name, Material object, or dict

        Returns: self (for chaining)
        """
        obj = Sphere(
            center=_to_vec3(pos),
            radius=float(radius),
            material=_resolve_material(material),
        )
        self._scene.add(obj)
        self._object_count += 1
        return self

    def ellipsoid(self, pos=(0, 0, 0), radii=(1, 1, 1), material='ceramic',
                  rotate=(0, 0, 0)):
        """Add an ellipsoid to the scene.

        Args:
            pos: (x, y, z) center position
            radii: (a, b, c) semi-axis lengths along X, Y, Z
            material: string name, Material object, or dict
            rotate: (rx, ry, rz) Euler angles in radians

        Returns: self (for chaining)
        """
        rx, ry, rz = rotate if isinstance(rotate, (tuple, list)) else (0, 0, 0)
        rot = rotation_matrix(rx=rx, ry=ry, rz=rz)

        obj = Ellipsoid(
            center=_to_vec3(pos),
            radii=_to_vec3(radii),
            rotation=rot,
            material=_resolve_material(material),
        )
        self._scene.add(obj)
        self._object_count += 1
        return self

    def plane(self, y=0, normal=(0, 1, 0), point=None, material='basalt'):
        """Add an infinite plane to the scene.

        Args:
            y: shorthand — a horizontal plane at height y
            normal: plane normal direction (default: up)
            point: explicit point on the plane (overrides y)
            material: string name, Material object, or dict

        Returns: self (for chaining)
        """
        if point is not None:
            pt = _to_vec3(point)
        else:
            pt = Vec3(0, float(y), 0)

        obj = Plane(
            point=pt,
            normal=_to_vec3(normal),
            material=_resolve_material(material),
        )
        self._scene.add(obj)
        self._object_count += 1
        return self

    def cone(self, base_pos=(0, 0, 0), height=1.0, base_radius=0.5,
             top_radius=0.0, material='ceramic', rotate=(0, 0, 0)):
        """Add a cone or frustum (truncated cone) to the scene.

        A frustum is defined by two circular ends stacked along the local Y axis.
        Special cases: top_radius=0 → pointed cone, top_radius=base_radius → cylinder.

        Args:
            base_pos: (x, y, z) center of the base circle
            height: distance from base to top
            base_radius: radius at the base
            top_radius: radius at the top (0 = pointed cone)
            material: string name, Material object, or dict
            rotate: (rx, ry, rz) Euler angles in radians

        Returns: self (for chaining)

        Examples:
            ms.cone(base_pos=(0, 0, 0), height=0.8, base_radius=0.35,
                    top_radius=0.37, material='ceramic')   # cup wall (frustum)
            ms.cone(base_pos=(0, 0, 0), height=0.9,
                    base_radius=0.03, top_radius=0.03,
                    material='iron')                        # chair leg (cylinder)
            ms.cone(base_pos=(0, 0, 0), height=0.5,
                    base_radius=0.3, top_radius=0,
                    material='ceramic')                     # pointed cone
        """
        rx, ry, rz = rotate if isinstance(rotate, (tuple, list)) else (0, 0, 0)
        rot = rotation_matrix(rx=rx, ry=ry, rz=rz)

        obj = Cone(
            base_center=_to_vec3(base_pos),
            height=float(height),
            base_radius=float(base_radius),
            top_radius=float(top_radius),
            rotation=rot,
            material=_resolve_material(material),
        )
        self._scene.add(obj)
        self._object_count += 1
        return self

    def custom(self, obj):
        """Add a raw geometry object (Sphere, Ellipsoid, Plane, Cone) directly.

        For advanced use when you've already constructed the object.

        Returns: self (for chaining)
        """
        self._scene.add(obj)
        self._object_count += 1
        return self

    # ── Lighting ─────────────────────────────────────────────────────

    def light(self, pos=(5, 10, 5), color=(1, 1, 1), intensity=1.0):
        """Add a point light source.

        Args:
            pos: (x, y, z) light position
            color: (r, g, b) light color, 0-1
            intensity: brightness multiplier

        Returns: self (for chaining)
        """
        self._scene.add_light(Light(
            pos=_to_vec3(pos),
            color=_to_vec3(color),
            intensity=float(intensity),
        ))
        return self

    def ambient(self, r=0.08, g=0.08, b=0.12):
        """Set the ambient light level.

        Args:
            r, g, b: ambient color components (0-1)

        Returns: self (for chaining)
        """
        self._scene.ambient = Vec3(float(r), float(g), float(b))
        return self

    def background(self, r=0.02, g=0.02, b=0.04):
        """Set the background color (for rays that miss everything).

        Args:
            r, g, b: background color components (0-1)

        Returns: self (for chaining)
        """
        self._scene.background = Vec3(float(r), float(g), float(b))
        return self

    # ── Camera ───────────────────────────────────────────────────────

    def camera(self, pos=(0, 2, 3), look_at=(0, 0, 0), up=(0, 1, 0), fov=55):
        """Set the camera (viewpoint).

        Args:
            pos: (x, y, z) camera position
            look_at: (x, y, z) point the camera aims at
            up: (x, y, z) world up direction
            fov: field of view in degrees

        Returns: self (for chaining)
        """
        self._camera = Camera(
            pos=_to_vec3(pos),
            look_at=_to_vec3(look_at),
            up=_to_vec3(up),
            fov=float(fov),
        )
        return self

    # ── Rendering ────────────────────────────────────────────────────

    def render(self, filepath, width=320, height=240, pixel_size=3):
        """Render the scene to a file.

        Supported formats:
            .svg — vector output (rect-per-pixel, universal)
            .png — raster output (pure-Python encoder, no PIL)

        Args:
            filepath: output path (.svg or .png)
            width: image width in pixels (rays cast)
            height: image height in pixels
            pixel_size: SVG only — size of each pixel rect

        Returns: dict with render stats
        """
        if self._camera is None:
            self.camera()  # use defaults

        if not self._scene.lights:
            self.light()  # add a default light

        import time
        t0 = time.time()
        pixels = render_scene(self._scene, self._camera, width, height)
        t_render = time.time() - t0

        ext = os.path.splitext(filepath)[1].lower()
        os.makedirs(os.path.dirname(os.path.abspath(filepath)) or '.', exist_ok=True)

        if ext == '.svg':
            render_to_svg(pixels, filepath, pixel_size=pixel_size)
        elif ext == '.png':
            _write_png(pixels, width, height, filepath)
        else:
            # Default to SVG
            render_to_svg(pixels, filepath, pixel_size=pixel_size)

        return {
            'filepath': os.path.abspath(filepath),
            'width': width,
            'height': height,
            'rays': width * height,
            'objects': len(self._scene.objects),
            'lights': len(self._scene.lights),
            'render_time_s': round(t_render, 3),
            'format': ext.lstrip('.'),
        }

    def render_pixels(self, width=320, height=240):
        """Render and return raw pixel array (list of rows of Vec3).

        Useful for compositing, post-processing, or custom output.
        """
        if self._camera is None:
            self.camera()
        if not self._scene.lights:
            self.light()
        return render_scene(self._scene, self._camera, width, height)

    # ── Scene management ─────────────────────────────────────────────

    def clear(self):
        """Remove all objects, lights, and camera. Start fresh."""
        self._scene = Scene()
        self._camera = None
        self._object_count = 0
        return self

    def clear_objects(self):
        """Remove all objects but keep lights and camera."""
        self._scene.objects = []
        self._object_count = 0
        return self

    def clear_lights(self):
        """Remove all lights."""
        self._scene.lights = []
        return self

    @property
    def scene(self):
        """Access the raw Scene object for advanced use."""
        return self._scene

    @property
    def materials(self):
        """List available material names."""
        return sorted(ALL_MATERIALS.keys())

    def material_info(self, name):
        """Get details about a named material."""
        mat = _resolve_material(name)
        return {
            'name': mat.name,
            'color': (mat.color.x, mat.color.y, mat.color.z),
            'reflectance': mat.reflectance,
            'roughness': mat.roughness,
            'density_kg_m3': mat.density_kg_m3,
            'mean_Z': mat.mean_Z,
            'mean_A': mat.mean_A,
            'composition': mat.composition,
        }

    # ── Presets ──────────────────────────────────────────────────────

    def preset_studio(self):
        """Apply standard 3-point studio lighting.

        Key light (warm, upper right), fill (cool, upper left),
        rim light (behind). Good starting point for any scene.

        Returns: self (for chaining)
        """
        self.light(pos=(5, 8, 2), color=(1.0, 0.95, 0.85), intensity=1.0)
        self.light(pos=(-4, 6, 0), color=(0.6, 0.7, 1.0), intensity=0.4)
        self.light(pos=(0, 3, -8), color=(0.8, 0.8, 1.0), intensity=0.3)
        self.ambient(0.06, 0.06, 0.08)
        return self

    def preset_outdoor(self):
        """Sunlight + sky ambient. Good for geological/planetary scenes.

        Returns: self (for chaining)
        """
        self.light(pos=(10, 15, 5), color=(1.0, 0.98, 0.90), intensity=1.2)
        self.light(pos=(-5, 10, -3), color=(0.5, 0.6, 0.9), intensity=0.3)
        self.ambient(0.10, 0.12, 0.18)
        self.background(0.15, 0.20, 0.35)
        return self

    def preset_space(self):
        """Deep space lighting. Single harsh directional, near-black ambient.

        Returns: self (for chaining)
        """
        self.light(pos=(20, 10, 5), color=(1.0, 1.0, 0.98), intensity=1.5)
        self.ambient(0.01, 0.01, 0.02)
        self.background(0.005, 0.005, 0.015)
        return self


# ── Pure-Python PNG writer ───────────────────────────────────────────

def _write_png(pixels, width, height, filepath):
    """Write pixel array to PNG. Zero dependencies."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter byte
        for x in range(width):
            c = pixels[y][x].clamp(0, 1)
            raw.append(int(c.x * 255))
            raw.append(int(c.y * 255))
            raw.append(int(c.z * 255))

    compressed = zlib.compress(bytes(raw), 9)

    def chunk(chunk_type, data):
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    with open(filepath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)))
        f.write(chunk(b'IDAT', compressed))
        f.write(chunk(b'IEND', b''))
