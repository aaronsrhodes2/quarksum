"""
Entangler Illumination — surface nodes compute their own response.

The light is the activation trigger. It provides direction and intensity.
Each surface node computes its own color response from:
  - Its normal (orientation)
  - Its material (physics)
  - The light direction and intensity

Lambertian diffuse: I = max(0, n̂·l̂) × material_color × light_intensity
This is exact — Lambert's cosine law is proven physics (1760).

No rays. No shadow casting. No global illumination.
The node responds to what reaches it.

Zero shared code with any ray tracer.
"""

from .vec import Vec3


class PushLight:
    """An activation signal — position and intensity.

    The light doesn't trace anything. It exists at a location
    with a given intensity. Surface nodes compute their response.
    """
    def __init__(self, pos, intensity=1.0, color=None):
        self.pos = pos
        self.intensity = intensity
        self.color = color or Vec3(1, 1, 1)


def illuminate_node(node, light, shadow=1.0):
    """A surface node computes its response to a light source.

    Lambertian diffuse (proven physics) + minimal ambient.

    Args:
        node:   SurfaceNode
        light:  PushLight
        shadow: float 0.0–1.0. 1.0 = fully lit, 0.0 = fully occluded.
                The shadow map sets this; default 1.0 (no occlusion test).
                Ambient is NOT modulated — a shadowed node still receives
                8% ambient (sky bounce, physically justifiable).

    Returns:
        Vec3 color response
    """
    # Direction from node to light (exact vector math)
    to_light = light.pos - node.position
    dist = to_light.length()
    if dist < 1e-10:
        return Vec3(0, 0, 0)
    to_light_dir = to_light * (1.0 / dist)

    # Lambert's cosine law: I ∝ cos(θ) = n̂·l̂
    n_dot_l = max(0.0, node.normal.dot(to_light_dir))

    # Material color × light color × intensity × angular factor × shadow occlusion
    # light.color is the spectral tint of the source (warm amber for tungsten,
    # white for neutral, blue-white for daylight). Applied per channel so a
    # 2800K tungsten filament gives warm-tinted shadows, not grey ones.
    mat_color = node.material.color
    scale = n_dot_l * light.intensity * shadow
    diff = Vec3(
        mat_color.x * light.color.x * scale,
        mat_color.y * light.color.y * scale,
        mat_color.z * light.color.z * scale,
    )

    # Ambient: 8% so shapes are visible even in full shadow.
    # Not modulated by shadow or light color — ambient is sky/indirect, not
    # from this specific source.
    ambient = mat_color * 0.08

    return (diff + ambient).clamp(0, 1)
