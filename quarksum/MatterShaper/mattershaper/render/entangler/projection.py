"""
Entangler Projection — surface nodes project themselves onto pixel grid.

The camera is passive. It's a coordinate frame and a bucket array.
Surface nodes do the projecting — exact perspective division.

Math:
  - Camera basis: Gram-Schmidt orthonormalization (exact)
  - Projection: x_ndc = x_cam / (z × tan(fov/2) × aspect)
  - NDC → pixel: linear map [-1,1] → [0, width]

No rays fired. No intersection computed. The node knows where it lands.

Zero shared code with any ray tracer.
"""

import math
from .vec import Vec3


class PushCamera:
    """A passive receiver — a grid of pixel buckets.

    The camera doesn't DO anything. It defines a coordinate frame
    and a resolution. Surface nodes project onto it.
    """

    def __init__(self, pos, look_at, width, height, fov=60):
        self.pos = pos
        self.look_at = look_at
        self.width = width
        self.height = height
        self.fov = fov

        # Camera basis vectors (Gram-Schmidt, exact)
        self.forward = (look_at - pos).normalized()
        world_up = Vec3(0, 1, 0)

        # Degenerate case: looking straight up or down
        if abs(self.forward.dot(world_up)) > 0.999:
            world_up = Vec3(0, 0, 1)

        self.right = self.forward.cross(world_up).normalized()
        self.up = self.right.cross(self.forward).normalized()

        # Perspective parameters (exact trig)
        self.aspect = width / height
        self.tan_half_fov = math.tan(math.radians(fov / 2.0))


def project_node(world_pos, camera):
    """Project a 3D world point onto the pixel grid.

    Exact perspective projection. No rays.

    Args:
        world_pos: Vec3 position in world space
        camera: PushCamera

    Returns:
        (px, py) pixel coordinates, or None if behind camera or off-screen
    """
    # Vector from camera to point
    to_point = world_pos - camera.pos

    # Project onto camera basis (exact dot products)
    z = to_point.dot(camera.forward)
    if z <= 0.001:
        return None  # behind camera

    x = to_point.dot(camera.right)
    y = to_point.dot(camera.up)

    # Perspective division (exact)
    ndc_x = x / (z * camera.tan_half_fov * camera.aspect)
    ndc_y = y / (z * camera.tan_half_fov)

    # NDC [-1, 1] → pixel [0, width/height]
    px = (ndc_x + 1.0) * 0.5 * camera.width
    py = (1.0 - ndc_y) * 0.5 * camera.height  # screen Y points down

    # Bounds check (exact integer comparison)
    if px < 0 or px >= camera.width or py < 0 or py >= camera.height:
        return None

    return (px, py)
