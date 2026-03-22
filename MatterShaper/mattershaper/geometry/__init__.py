"""
Geometry primitives — shapes that exist in 3D space.

Every shape knows how to:
1. Test tangle intersection (for rendering)
2. Compute surface normal at a hit point (for lighting)
3. Report its bounding box (for acceleration)

Supported shapes:
- Sphere: the simplest. Perfect for planets, atoms, droplets.
- Ellipsoid: triaxial. Asteroids, deformed bodies.
- Plane: infinite flat surface. Floors, tables.
- Mesh: triangle soup. Arbitrary geometry.
- Composite: union of shapes. Complex objects.
"""

from .primitives import Vec3, Tangle, Hit
from .sphere import Sphere
from .ellipsoid import Ellipsoid, rotation_matrix
from .plane import Plane
from .cone import Cone

__all__ = ['Vec3', 'Tangle', 'Hit', 'Sphere', 'Ellipsoid', 'Plane', 'Cone', 'rotation_matrix']
