"""
Vec3 — 3D vector arithmetic for sigma-ground-physics.

Pure math. No rendering concepts. No ray tracing.

Terminology note: "ray" means one specific thing in rendering — the photon
sightline between a surface and the camera sensor. Vec3 is used for positions,
directions, and colors; it is not a ray.

Length floor
────────────
All normalized() and division-by-length operations guard against zero length
using _L_PLANCK = 1.616255e-35 m (the Planck length). This is the physically
motivated minimum length: below it, spacetime itself is quantum-uncertain.
The choice is not arbitrary — see sgphysics/constants.py for the full
derivation and the note on infinity and different conceptions of "zero."

In normal operation at render scales (mm to m), this guard NEVER fires.
If it fires, two nodes have numerically coincident positions — inspect the
surface node generator.
"""

import math

# Planck length — the fundamental UV length floor.
# sqrt(ħG/c³) = 1.616255e-35 m  (CODATA 2018)
# Defined locally to avoid circular import at module load time.
_L_PLANCK = 1.616255e-35   # m


class Vec3:
    """3D vector. Positions, directions, colors.

    Component convention: x=right, y=up, z=toward-viewer (right-handed).
    Used for both world-space geometry and HDR color (components ≥ 0).
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
            # Component-wise product (for color attenuation, e.g. albedo × light)
            return Vec3(self.x * s.x, self.y * s.y, self.z * s.z)
        # Scalar scale
        return Vec3(self.x * s, self.y * s, self.z * s)

    def __rmul__(self, s):
        return self.__mul__(s)

    def __neg__(self):
        return Vec3(-self.x, -self.y, -self.z)

    def __repr__(self):
        return f"Vec3({self.x:.4f}, {self.y:.4f}, {self.z:.4f})"

    def dot(self, o):
        """Dot product: a·b = |a||b|cos(θ).

        For unit vectors this gives the cosine of the angle between them,
        which is the fundamental quantity for Lambert shading and BH opening
        angle tests.
        """
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o):
        """Cross product: a×b — vector normal to both a and b.

        Magnitude: |a||b|sin(θ). Direction: right-hand rule.
        Used for surface normal computation and torus parametric sampling.
        """
        return Vec3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def length(self):
        """Euclidean magnitude |v| = sqrt(x² + y² + z²)."""
        return math.sqrt(self.dot(self))

    def length_sq(self):
        """Squared magnitude |v|² = x² + y² + z². No sqrt — faster for comparisons."""
        return self.dot(self)

    def normalized(self):
        """Unit vector in the same direction: v / |v|.

        Returns Vec3(0, 0, 0) for any vector shorter than the Planck length
        (_L_PLANCK = 1.616e-35 m). Below that scale, direction is physically
        undefined. This is the honest floor — not an arbitrary epsilon.
        """
        L = self.length()
        if L < _L_PLANCK:
            return Vec3(0, 0, 0)
        return Vec3(self.x / L, self.y / L, self.z / L)

    def reflect(self, normal):
        """Reflect this vector off a surface with outward normal n.

        r = v - 2(v·n)n
        FIRST_PRINCIPLES: specular reflection (Snell's law, angle-of-incidence
        = angle-of-reflection, in the plane of incidence).
        """
        return self - normal * (2.0 * self.dot(normal))

    def clamp(self, lo=0.0, hi=1.0):
        """Clamp each component independently to [lo, hi].

        Used to keep HDR color values in [0, 1] before gamma encoding
        and to enforce domain bounds on particle positions.
        """
        return Vec3(
            max(lo, min(hi, self.x)),
            max(lo, min(hi, self.y)),
            max(lo, min(hi, self.z)),
        )

    def to_rgb(self):
        """Convert to 8-bit sRGB tuple (R, G, B) in [0, 255].

        Clamps components to [0, 1] before quantizing. Values above 1
        (HDR) are clipped — no tone mapping applied here.
        """
        c = self.clamp(0, 1)
        return (int(c.x * 255), int(c.y * 255), int(c.z * 255))

    def to_hex(self):
        """Convert to #rrggbb hex string."""
        r, g, b = self.to_rgb()
        return f"#{r:02x}{g:02x}{b:02x}"
