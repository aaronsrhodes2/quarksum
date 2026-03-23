"""
Vector math and ray primitives — the foundation of the renderer.

No numpy. No external libraries. Just arithmetic.
Every operation is explicit so anyone can read it.
"""

import math


class Vec3:
    """3D vector. Immutable. Used for positions, directions, colors."""

    __slots__ = ('x', 'y', 'z')

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, o):
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o):
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, s):
        if isinstance(s, Vec3):
            # Component-wise multiply (for colors)
            return Vec3(self.x * s.x, self.y * s.y, self.z * s.z)
        return Vec3(self.x * s, self.y * s, self.z * s)

    def __rmul__(self, s):
        return self.__mul__(s)

    def __neg__(self):
        return Vec3(-self.x, -self.y, -self.z)

    def __repr__(self):
        return f"Vec3({self.x:.4f}, {self.y:.4f}, {self.z:.4f})"

    def dot(self, o):
        """Dot product: a·b = |a||b|cos(θ)"""
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o):
        """Cross product: a×b = normal to both a and b"""
        return Vec3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def length(self):
        return math.sqrt(self.dot(self))

    def length_sq(self):
        return self.dot(self)

    def normalized(self):
        """Unit vector in same direction."""
        L = self.length()
        if L < 1e-12:
            return Vec3(0, 0, 0)
        return Vec3(self.x / L, self.y / L, self.z / L)

    def reflect(self, normal):
        """Reflect this vector off a surface with given normal."""
        return self - normal * (2.0 * self.dot(normal))

    def clamp(self, lo=0.0, hi=1.0):
        """Clamp each component to [lo, hi]. Used for colors."""
        return Vec3(
            max(lo, min(hi, self.x)),
            max(lo, min(hi, self.y)),
            max(lo, min(hi, self.z)),
        )

    def to_rgb(self):
        """Convert to 0-255 RGB tuple."""
        c = self.clamp(0, 1)
        return (int(c.x * 255), int(c.y * 255), int(c.z * 255))

    def to_hex(self):
        """Convert to #rrggbb hex string."""
        r, g, b = self.to_rgb()
        return f"#{r:02x}{g:02x}{b:02x}"


class Ray:
    """A ray: origin + direction. The fundamental rendering primitive.

    P(t) = origin + t × direction, for t > 0.
    """

    __slots__ = ('origin', 'direction')

    def __init__(self, origin, direction):
        self.origin = origin
        self.direction = direction.normalized()

    def at(self, t):
        """Point along the ray at parameter t."""
        return self.origin + self.direction * t


class Hit:
    """Record of a ray-surface intersection.

    Contains everything needed for lighting:
    - t: distance along ray
    - point: world-space hit position
    - normal: surface normal at hit (outward-facing)
    - material: what the surface is made of
    """

    __slots__ = ('t', 'point', 'normal', 'material', 'obj')

    def __init__(self, t, point, normal, material=None, obj=None):
        self.t = t
        self.point = point
        self.normal = normal
        self.material = material
        self.obj = obj
