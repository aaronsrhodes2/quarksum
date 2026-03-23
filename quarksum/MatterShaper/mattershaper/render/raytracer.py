"""
Ray Tracer — the core rendering loop.

For each pixel:
1. Generate a ray from the camera
2. Find the nearest surface intersection
3. Compute lighting at that point
4. Return the color

Outputs SVG (rect per pixel) — no PIL, no external image libraries.
"""

import math
from ..geometry.primitives import Vec3


class Light:
    """A point light source."""

    def __init__(self, pos=None, color=None, intensity=1.0):
        self.pos = pos or Vec3(5, 10, 5)
        self.color = color or Vec3(1, 1, 1)
        self.intensity = intensity


class Scene:
    """Container for objects and lights."""

    def __init__(self):
        self.objects = []
        self.lights = []
        self.ambient = Vec3(0.08, 0.08, 0.12)  # slight blue ambient
        self.background = Vec3(0.02, 0.02, 0.04)  # near-black

    def add(self, obj):
        self.objects.append(obj)

    def add_light(self, light):
        self.lights.append(light)

    def intersect(self, ray, t_min=0.001, t_max=float('inf')):
        """Find the nearest intersection in the scene."""
        nearest = None
        for obj in self.objects:
            hit = obj.intersect(ray, t_min, t_max)
            if hit and (nearest is None or hit.t < nearest.t):
                nearest = hit
                t_max = hit.t  # only check closer objects
        return nearest


def shade(hit, scene, ray, depth=0):
    """Compute the color at a hit point.

    Blinn-Phong shading: ambient + diffuse + specular + reflection.
    All electromagnetic → σ-invariant in SSBM.
    """
    if hit is None or hit.material is None:
        return scene.background

    mat = hit.material
    color = mat.color
    point = hit.point
    normal = hit.normal
    view = -ray.direction

    # Start with ambient
    result = Vec3(
        scene.ambient.x * color.x,
        scene.ambient.y * color.y,
        scene.ambient.z * color.z,
    )

    for light in scene.lights:
        # Direction to light
        to_light = light.pos - point
        dist = to_light.length()
        L = to_light * (1.0 / dist)

        # Shadow test
        shadow_ray_origin = point + normal * 0.002
        from ..geometry.primitives import Ray as RayClass
        shadow_ray = RayClass(shadow_ray_origin, L)
        shadow_hit = scene.intersect(shadow_ray, 0.001, dist)
        if shadow_hit:
            continue  # in shadow

        # Diffuse (Lambertian)
        NdotL = max(0, normal.dot(L))
        diffuse_strength = NdotL * light.intensity * (1 - mat.reflectance)

        # Specular (Blinn-Phong)
        H = (L + view).normalized()
        NdotH = max(0, normal.dot(H))
        shininess = max(1, int(200 * (1 - mat.roughness)))
        spec_strength = math.pow(NdotH, shininess) * mat.reflectance * light.intensity

        # Accumulate
        result = result + Vec3(
            color.x * diffuse_strength * light.color.x,
            color.y * diffuse_strength * light.color.y,
            color.z * diffuse_strength * light.color.z,
        ) + Vec3(
            spec_strength * light.color.x,
            spec_strength * light.color.y,
            spec_strength * light.color.z,
        )

    # Reflection (one bounce)
    if mat.reflectance > 0.05 and depth < 2:
        reflect_dir = ray.direction.reflect(normal)
        from ..geometry.primitives import Ray as RayClass
        reflect_ray = RayClass(point + normal * 0.002, reflect_dir)
        reflect_hit = scene.intersect(reflect_ray)
        reflect_color = shade(reflect_hit, scene, reflect_ray, depth + 1)
        result = result + reflect_color * mat.reflectance * 0.5

    return result.clamp(0, 1)


def render_scene(scene, camera, width=200, height=150):
    """Render a scene to a 2D pixel array.

    Returns a list of rows, each row is a list of Vec3 colors.
    """
    pixels = []
    for y in range(height):
        row = []
        v = y / (height - 1)
        for x in range(width):
            u = x / (width - 1)
            ray = camera.ray_for_pixel(u, v)
            hit = scene.intersect(ray)
            color = shade(hit, scene, ray)
            row.append(color)
        pixels.append(row)
    return pixels


def render_to_svg(pixels, filepath, pixel_size=4):
    """Write rendered pixels to an SVG file.

    Each pixel becomes a rect. Simple but universal — no PIL needed.
    """
    height = len(pixels)
    width = len(pixels[0]) if pixels else 0
    svg_w = width * pixel_size
    svg_h = height * pixel_size

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="0 0 {svg_w} {svg_h}" '
             f'width="{svg_w}" height="{svg_h}">\n']

    # Optimization: batch same-colored pixels into horizontal runs
    for y, row in enumerate(pixels):
        x = 0
        while x < width:
            color = row[x]
            hex_color = color.to_hex()

            # Find run of same color
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
