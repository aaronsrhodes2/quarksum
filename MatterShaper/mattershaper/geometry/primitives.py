"""
Vector math and tangle primitives — the foundation of the renderer.

No numpy. No external libraries. Just arithmetic.
Every operation is explicit so anyone can read it.

Length floor
────────────
Normalized vectors use _L_PLANCK = 1.616255e-35 m as the zero guard.
Below the Planck length, spatial direction is physically undefined.
See physics/constants.py for the full derivation and the note on infinity.
"""

import math

# Planck length — universal UV length floor. sqrt(ħG/c³). CODATA 2018.
# Defined locally to keep geometry ↛ physics import dependency clean.
_L_PLANCK = 1.616255e-35   # m


class Vec3:
    """3D vector. Immutable. Used for positions, directions, colors.

    Component convention: x=right, y=up, z=toward-viewer (right-handed).
    Immutable by design — operations return new Vec3 instances.
    """

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
        """Unit vector in the same direction: v / |v|.

        Returns Vec3(0,0,0) for any vector shorter than the Planck length.
        Below _L_PLANCK = 1.616e-35 m, spatial direction is undefined.
        """
        L = self.length()
        if L < _L_PLANCK:
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


class Tangle:
    """A sightline: origin + direction.  The photon-path primitive.

    P(t) = origin + t × direction, for t > 0.

    Named "Tangle" because when you pull a sightline far enough apart —
    beyond THETA_NATURAL ≈ 1/φ² of solid angle — it breaks apart.
    The far end becomes information paste.  The name carries the physics.

    Scope: this class models exactly one thing — the path a photon travels
    between a surface and the camera sensor (or the reverse, depending on
    rendering convention).  It is NOT a general "directed line" or trajectory.
    In physics code, use displacement vectors or particle trajectories;
    never import Tangle for non-rendering purposes.

    t_max convention: initialise to the scene bounding-box diagonal, not
    float('inf').  The sightline exits the finite scene at a finite t.
    float('inf') as a sentinel ("not yet intersected") is IEEE 754 state —
    acceptable during intersection testing, but not a claim that the sightline
    is physically infinite.  Per the BH Claying argument: beyond the distance
    at which scene geometry subtends less than THETA_NATURAL ≈ 1/φ² of solid
    angle, that geometry is physically indistinguishable from a point — the
    renderer can treat it as such without any loss of physical fidelity.
    """

    __slots__ = ('origin', 'direction')

    def __init__(self, origin, direction):
        self.origin = origin
        self.direction = direction.normalized()

    def at(self, t):
        """Point along the tangle at parameter t."""
        return self.origin + self.direction * t


class Hit:
    """Record of a tangle-surface intersection.

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
