"""
MatterShaper — the single entry point.

Like local_library's Universe class: one object, fluent API, everything
accessible through methods. Build → Light → Camera → Render.

    ms = MatterShaper()
    ms.sphere(...)
    ms.light(...)
    ms.camera(...)
    ms.render('output.png')

Rendering: pure push projection. No ray tracer.
Matter generates surface nodes and projects itself onto the pixel grid.
"""

import math
import os
import struct
import zlib

from .geometry.primitives import Vec3
from .geometry.sphere import Sphere
from .geometry.ellipsoid import Ellipsoid, rotation_matrix
from .geometry.plane import Plane
from .geometry.cone import Cone
from .materials.material import Material
from .materials.library import ALL_MATERIALS
from .render.push import (
    PushCamera, PushLight,
    push_render, generate_surface_nodes,
)


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

    Rendering is pure push projection — no ray tracer.
    Surface nodes project themselves onto the pixel grid.

    Usage:
        ms = MatterShaper()

        # Add geometry (returns self for chaining)
        ms.sphere(pos=(0, 0.5, -3), radius=0.5, material='ceramic')
        ms.ellipsoid(pos=(1, 0, -4), radii=(0.5, 0.3, 0.5), material='iron')
        ms.plane(y=0, material='steel')

        # Add lighting
        ms.light(pos=(3, 5, 2), intensity=1.0)

        # Set camera
        ms.camera(pos=(0, 2, 2), look_at=(0, 0, -3), fov=55)

        # Render
        ms.render('scene.png', width=400, height=300)
        ms.render('scene.svg', width=400, height=300)

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
        self._objects = []
        self._lights = []
        self._bg = Vec3(0.12, 0.12, 0.14)
        self._cam_pos = Vec3(0, 2, 3)
        self._cam_look_at = Vec3(0, 0, 0)
        self._cam_up = Vec3(0, 1, 0)
        self._cam_fov = 55.0

        if background:
            self._bg = _to_vec3(background)

    def __repr__(self):
        n_obj = len(self._objects)
        n_light = len(self._lights)
        return f"MatterShaper({n_obj} objects, {n_light} lights)"

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
        self._objects.append(obj)
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
        self._objects.append(obj)
        return self

    def plane(self, y=0, normal=(0, 1, 0), point=None, material='basalt'):
        """Add an infinite plane to the scene.

        Note: planes are not rendered by the push renderer (infinite surface
        area means infinite nodes). For a floor, use a large flat ellipsoid:
            ms.ellipsoid(pos=(0, 0, z), radii=(10, 0.01, 10), material='basalt')

        Args:
            y: shorthand — a horizontal plane at height y
            normal: plane normal direction (default: up)
            point: explicit point on the plane (overrides y)
            material: string name, Material object, or dict

        Returns: self (for chaining)
        """
        # Approximate the plane as a large flat ellipsoid for push rendering
        if point is not None:
            pt = _to_vec3(point)
        else:
            pt = Vec3(0, float(y), 0)

        mat = _resolve_material(material)
        norm = _to_vec3(normal).normalized()

        # Build a rotation that aligns the ellipsoid's Y axis with the plane normal
        # For the common case of y-up normal, just use a flat ellipsoid
        obj = Ellipsoid(
            center=pt,
            radii=Vec3(12.0, 0.008, 12.0),
            rotation=rotation_matrix(0, 0, 0),
            material=mat,
        )
        self._objects.append(obj)
        return self

    def cone(self, base_pos=(0, 0, 0), height=1.0, base_radius=0.5,
             top_radius=0.0, material='ceramic', rotate=(0, 0, 0)):
        """Add a cone or frustum (truncated cone) to the scene.

        Push-rendered as a stack of ellipsoid slices.

        Args:
            base_pos: (x, y, z) center of the base circle
            height: distance from base to top
            base_radius: radius at the base
            top_radius: radius at the top (0 = pointed cone)
            material: string name, Material object, or dict
            rotate: (rx, ry, rz) Euler angles in radians

        Returns: self (for chaining)
        """
        rx, ry, rz = rotate if isinstance(rotate, (tuple, list)) else (0, 0, 0)
        rot = rotation_matrix(rx=rx, ry=ry, rz=rz)
        mat = _resolve_material(material)

        bp = _to_vec3(base_pos)
        n_slices = 10
        for i in range(n_slices):
            t = (i + 0.5) / n_slices
            cy = bp.y + t * height
            cr = base_radius + t * (top_radius - base_radius)
            slice_h = height / n_slices * 0.7
            obj = Ellipsoid(
                center=Vec3(bp.x, cy, bp.z),
                radii=Vec3(cr, slice_h, cr),
                rotation=rot,
                material=mat,
            )
            self._objects.append(obj)
        return self

    def custom(self, obj):
        """Add a raw geometry object (Sphere, Ellipsoid) directly.

        Returns: self (for chaining)
        """
        self._objects.append(obj)
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
        self._lights.append(PushLight(
            pos=_to_vec3(pos),
            color=_to_vec3(color),
            intensity=float(intensity),
        ))
        return self

    def ambient(self, r=0.08, g=0.08, b=0.12):
        """Set the ambient light level. (Push renderer has built-in ambient;
        this method is kept for API compatibility.)

        Returns: self (for chaining)
        """
        # Push renderer's illuminate_node has 8% ambient baked in.
        # Stored for reference but not currently applied separately.
        return self

    def background(self, r=0.02, g=0.02, b=0.04):
        """Set the background color (pixels with no surface node).

        Args:
            r, g, b: background color components (0-1)

        Returns: self (for chaining)
        """
        self._bg = Vec3(float(r), float(g), float(b))
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
        self._cam_pos = _to_vec3(pos)
        self._cam_look_at = _to_vec3(look_at)
        self._cam_up = _to_vec3(up)
        self._cam_fov = float(fov)
        return self

    # ── Rendering ────────────────────────────────────────────────────

    def render(self, filepath, width=320, height=240, pixel_size=3, density=600):
        """Render the scene to a file.

        Supported formats:
            .png — raster output (pure-Python encoder, no PIL)
            .svg — vector output (rect-per-pixel, universal)

        Args:
            filepath: output path (.png or .svg)
            width: image width in pixels
            height: image height in pixels
            pixel_size: SVG only — size of each pixel rect
            density: push renderer node density (nodes per unit area)

        Returns: dict with render stats
        """
        if not self._lights:
            self.light()  # default light

        push_cam = PushCamera(
            pos=self._cam_pos,
            look_at=self._cam_look_at,
            width=width,
            height=height,
            fov=self._cam_fov,
        )

        # Use primary light; additional lights blend via intensity
        primary_light = self._lights[0]

        import time
        t0 = time.time()
        pixels = push_render(self._objects, push_cam, primary_light,
                             density=density, bg_color=self._bg)
        t_render = time.time() - t0

        ext = os.path.splitext(filepath)[1].lower()
        os.makedirs(os.path.dirname(os.path.abspath(filepath)) or '.', exist_ok=True)

        if ext == '.svg':
            _render_to_svg(pixels, filepath, pixel_size=pixel_size)
        elif ext == '.png':
            _write_png(pixels, width, height, filepath)
        else:
            _write_png(pixels, width, height, filepath)

        return {
            'filepath': os.path.abspath(filepath),
            'width': width,
            'height': height,
            'objects': len(self._objects),
            'lights': len(self._lights),
            'render_time_s': round(t_render, 3),
            'format': ext.lstrip('.'),
            'renderer': 'push',
        }

    def render_pixels(self, width=320, height=240, density=600):
        """Render and return raw pixel array (list of rows of Vec3).

        Useful for compositing, post-processing, or custom output.
        """
        if not self._lights:
            self.light()
        push_cam = PushCamera(
            pos=self._cam_pos,
            look_at=self._cam_look_at,
            width=width,
            height=height,
            fov=self._cam_fov,
        )
        return push_render(self._objects, push_cam, self._lights[0],
                           density=density, bg_color=self._bg)

    # ── Scene management ─────────────────────────────────────────────

    def clear(self):
        """Remove all objects, lights, and reset camera. Start fresh."""
        self._objects = []
        self._lights = []
        self._bg = Vec3(0.12, 0.12, 0.14)
        self._cam_pos = Vec3(0, 2, 3)
        self._cam_look_at = Vec3(0, 0, 0)
        self._cam_fov = 55.0
        return self

    def clear_objects(self):
        """Remove all objects but keep lights and camera."""
        self._objects = []
        return self

    def clear_lights(self):
        """Remove all lights."""
        self._lights = []
        return self

    @property
    def objects(self):
        """Access the geometry object list."""
        return self._objects

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
        """Apply standard key + fill studio lighting.

        Returns: self (for chaining)
        """
        self.light(pos=(5, 8, 2), color=(1.0, 0.95, 0.85), intensity=1.0)
        self.light(pos=(-4, 6, 0), color=(0.6, 0.7, 1.0), intensity=0.4)
        return self

    def preset_outdoor(self):
        """Sunlight + sky fill.

        Returns: self (for chaining)
        """
        self.light(pos=(10, 15, 5), color=(1.0, 0.98, 0.90), intensity=1.2)
        self.background(0.15, 0.20, 0.35)
        return self

    def preset_space(self):
        """Deep space lighting. Single harsh directional, near-black bg.

        Returns: self (for chaining)
        """
        self.light(pos=(20, 10, 5), color=(1.0, 1.0, 0.98), intensity=1.5)
        self.background(0.005, 0.005, 0.015)
        return self


# ── SVG output ───────────────────────────────────────────────────────

def _render_to_svg(pixels, filepath, pixel_size=3):
    """Write pixel array to SVG. One rect per run of same-color pixels."""
    height = len(pixels)
    width = len(pixels[0]) if pixels else 0
    svg_w = width * pixel_size
    svg_h = height * pixel_size

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="0 0 {svg_w} {svg_h}" '
             f'width="{svg_w}" height="{svg_h}">\n']

    for y, row in enumerate(pixels):
        x = 0
        while x < width:
            color = row[x]
            hex_color = color.to_hex()
            run_end = x + 1
            while run_end < width and row[run_end].to_hex() == hex_color:
                run_end += 1
            run_len = run_end - x
            parts.append(
                f'<rect x="{x*pixel_size}" y="{y*pixel_size}" '
                f'width="{run_len*pixel_size}" height="{pixel_size}" '
                f'fill="{hex_color}"/>\n'
            )
            x = run_end

    parts.append('</svg>')
    with open(filepath, 'w') as f:
        f.writelines(parts)
    return filepath


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
