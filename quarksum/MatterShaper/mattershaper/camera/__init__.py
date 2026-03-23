"""
Camera — defines the viewpoint and projection.

Generates rays from the camera through each pixel of the image plane.
Standard perspective projection, derived from geometry.
"""

import math
from ..geometry.primitives import Vec3, Ray


class Camera:
    """Perspective camera.

    Args:
        pos: camera position in world space
        look_at: point the camera is aimed at
        up: world up direction (default: +Y)
        fov: field of view in degrees (default: 60)
        aspect: width/height ratio
    """

    def __init__(self, pos=None, look_at=None, up=None, fov=60.0, aspect=1.333):
        self.pos = pos or Vec3(0, 1, 3)
        self.look_at = look_at or Vec3(0, 0, 0)
        self.up = up or Vec3(0, 1, 0)
        self.fov = fov
        self.aspect = aspect

        self._setup()

    def _setup(self):
        """Compute the camera coordinate frame."""
        # Forward direction
        self.forward = (self.look_at - self.pos).normalized()
        # Right direction (perpendicular to forward and up)
        self.right = self.forward.cross(self.up).normalized()
        # True up (perpendicular to forward and right)
        self.true_up = self.right.cross(self.forward).normalized()

        # Half-dimensions of the image plane at distance 1
        self.half_h = math.tan(math.radians(self.fov) / 2.0)
        self.half_w = self.half_h * self.aspect

    def ray_for_pixel(self, u, v):
        """Generate a ray for normalized pixel coordinates (u, v).

        u: 0 = left, 1 = right
        v: 0 = top, 1 = bottom

        Returns a Ray from camera position through the image plane.
        """
        # Map (u, v) to image plane coordinates [-half_w, half_w] × [-half_h, half_h]
        px = (2 * u - 1) * self.half_w
        py = (1 - 2 * v) * self.half_h  # flip v so +y is up

        # Direction in world space
        direction = (self.forward + self.right * px + self.true_up * py).normalized()

        return Ray(self.pos, direction)

    def __repr__(self):
        return f"Camera(pos={self.pos}, look_at={self.look_at}, fov={self.fov}°)"
