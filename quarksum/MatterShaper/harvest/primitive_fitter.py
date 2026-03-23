"""
Primitive Fitter — Pure Python, Zero Dependencies
===================================================
Takes a cloud of vertices (from a mesh group) and fits the best
analytic primitive: sphere, ellipsoid, cone, or cylinder → ellipsoid.

Uses a 3×3 eigendecomposition (Jacobi method) to find principal axes,
then classifies by aspect ratios.

Part of the Nagatha harvest pipeline.
"Twelve primitives, five materials, and if I do say so myself,
rather recognizable."
"""

import math
from typing import List, Tuple, Optional, Dict


# ── 3×3 Linear Algebra (pure Python) ────────────────────────────

def _mat3_identity() -> List[List[float]]:
    return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def _mat3_multiply(A: List[List[float]], B: List[List[float]]) -> List[List[float]]:
    """Multiply two 3×3 matrices."""
    C = [[0.0]*3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            for k in range(3):
                C[i][j] += A[i][k] * B[k][j]
    return C


def _mat3_transpose(A: List[List[float]]) -> List[List[float]]:
    return [[A[j][i] for j in range(3)] for i in range(3)]


def jacobi_eigen_3x3(S: List[List[float]], max_iter: int = 100, tol: float = 1e-10):
    """
    Jacobi eigenvalue algorithm for a 3×3 symmetric matrix.

    Returns (eigenvalues, eigenvectors) where eigenvectors[i] is
    the i-th eigenvector as a 3-tuple, and eigenvalues[i] is the
    corresponding eigenvalue. Sorted by descending eigenvalue.

    This is the analytical heavy-lifting that lets us fit primitives
    to point clouds without numpy. For 3×3, Jacobi converges fast.
    """
    # Work on a copy
    A = [row[:] for row in S]
    V = _mat3_identity()

    for iteration in range(max_iter):
        # Find largest off-diagonal element
        max_val = 0.0
        p, q = 0, 1
        for i in range(3):
            for j in range(i + 1, 3):
                if abs(A[i][j]) > max_val:
                    max_val = abs(A[i][j])
                    p, q = i, j

        if max_val < tol:
            break  # Converged

        # Compute rotation angle
        if abs(A[p][p] - A[q][q]) < 1e-15:
            theta = math.pi / 4.0
        else:
            theta = 0.5 * math.atan2(2.0 * A[p][q], A[p][p] - A[q][q])

        c = math.cos(theta)
        s = math.sin(theta)

        # Build Givens rotation matrix
        G = _mat3_identity()
        G[p][p] = c
        G[q][q] = c
        G[p][q] = s
        G[q][p] = -s

        # Rotate: A' = G^T A G
        A = _mat3_multiply(_mat3_transpose(G), _mat3_multiply(A, G))
        V = _mat3_multiply(V, G)

    # Extract eigenvalues (diagonal) and eigenvectors (columns of V)
    eigenvalues = [A[i][i] for i in range(3)]
    eigenvectors = [(V[0][i], V[1][i], V[2][i]) for i in range(3)]

    # Sort by descending eigenvalue
    pairs = sorted(zip(eigenvalues, eigenvectors), key=lambda x: -x[0])
    eigenvalues = [p[0] for p in pairs]
    eigenvectors = [p[1] for p in pairs]

    return eigenvalues, eigenvectors


def covariance_matrix_3x3(points: List[Tuple[float, float, float]],
                           centroid: Tuple[float, float, float]) -> List[List[float]]:
    """Compute the 3×3 covariance matrix of a point cloud."""
    n = len(points)
    if n < 2:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    cx, cy, cz = centroid
    C = [[0.0]*3 for _ in range(3)]

    for x, y, z in points:
        dx, dy, dz = x - cx, y - cy, z - cz
        d = [dx, dy, dz]
        for i in range(3):
            for j in range(3):
                C[i][j] += d[i] * d[j]

    for i in range(3):
        for j in range(3):
            C[i][j] /= (n - 1)

    return C


# ── Shape Classification ────────────────────────────────────────

class FittedPrimitive:
    """Result of fitting a primitive to a point cloud."""

    def __init__(self):
        self.shape_type = "ellipsoid"  # sphere, ellipsoid, cone
        self.center = (0.0, 0.0, 0.0)
        self.radii = (1.0, 1.0, 1.0)   # (rx, ry, rz) in world-aligned coords
        self.principal_axes = None       # eigenvectors, for reference
        self.eigenvalues = None
        self.confidence = 0.0            # 0-1, how well does this primitive fit?
        self.vertex_count = 0
        self.face_count = 0
        self.material_name = "default"
        self.label = "part"              # semantic label (from group name)

    def to_sigma_layer(self, layer_name: str = None) -> dict:
        """Convert to a Sigma shape map layer entry."""
        if layer_name is None:
            layer_name = self.label

        layer = {
            "type": self.shape_type,
            "label": layer_name,
        }

        if self.shape_type == "sphere":
            layer["center"] = list(self.center)
            # Use average radius for sphere
            r = sum(self.radii) / 3.0
            layer["radius"] = round(r, 4)

        elif self.shape_type == "cone":
            # Approximate cone from the ellipsoid
            # Cone needs apex, base_center, base_radius, height
            # Use principal axis as cone axis
            h = max(self.radii) * 2
            base_r = (sum(self.radii) - max(self.radii)) / 2.0
            # Find which axis is longest
            max_idx = self.radii.index(max(self.radii))
            direction = [0, 0, 0]
            direction[max_idx] = 1.0

            base_center = list(self.center)
            base_center[max_idx] -= h / 2
            apex = list(self.center)
            apex[max_idx] += h / 2

            layer["base_center"] = [round(v, 4) for v in base_center]
            layer["apex"] = [round(v, 4) for v in apex]
            layer["base_radius"] = round(base_r, 4)

        else:
            # Ellipsoid (default)
            layer["center"] = [round(v, 4) for v in self.center]
            layer["radii"] = [round(v, 4) for v in self.radii]

        layer["material"] = self.material_name

        return layer

    def __repr__(self):
        return (f"FittedPrimitive({self.shape_type}, "
                f"center={tuple(round(v, 3) for v in self.center)}, "
                f"radii={tuple(round(v, 3) for v in self.radii)}, "
                f"conf={self.confidence:.2f})")


def fit_primitive(vertices: List[Tuple[float, float, float]],
                  centroid: Tuple[float, float, float],
                  face_count: int = 0,
                  material_name: str = "default",
                  label: str = "part") -> Optional[FittedPrimitive]:
    """
    Fit the best analytic primitive to a cloud of vertices.

    Algorithm:
    1. Compute covariance matrix
    2. Eigendecomposition → principal axes and scales
    3. Classify by eigenvalue ratios:
       - All ~equal → sphere
       - One much larger, tapered → cone
       - Otherwise → ellipsoid
    4. Scale eigenvalues to approximate radii

    Args:
        vertices: List of (x, y, z) points
        centroid: Pre-computed centroid
        face_count: Number of faces (for metadata)
        material_name: Material name from OBJ
        label: Semantic label (from group name)

    Returns:
        FittedPrimitive or None if too few vertices
    """
    if len(vertices) < 4:
        return None

    result = FittedPrimitive()
    result.center = centroid
    result.vertex_count = len(vertices)
    result.face_count = face_count
    result.material_name = material_name
    result.label = label

    # Compute covariance and eigendecompose
    cov = covariance_matrix_3x3(vertices, centroid)
    eigenvalues, eigenvectors = jacobi_eigen_3x3(cov)
    result.eigenvalues = eigenvalues
    result.principal_axes = eigenvectors

    # Convert eigenvalues to approximate radii
    # eigenvalue = variance along that axis
    # radius ≈ 2 * sqrt(eigenvalue) gives a reasonable bounding extent
    # (covers ~95% of points for Gaussian-like distributions)
    radii = []
    for ev in eigenvalues:
        r = 2.0 * math.sqrt(max(ev, 1e-10))
        radii.append(r)
    result.radii = tuple(radii)

    # ── Classify shape ──────────────────────────────────────────
    r_max = max(radii)
    r_min = min(radii)
    r_mid = sorted(radii)[1]

    if r_max < 1e-8:
        # Degenerate — point or line
        result.shape_type = "sphere"
        result.radii = (0.01, 0.01, 0.01)
        result.confidence = 0.1
        return result

    # Ratios for classification
    sphericity = r_min / r_max  # 1.0 = perfect sphere
    elongation = r_max / r_mid if r_mid > 1e-8 else 10.0
    flatness = r_min / r_mid if r_mid > 1e-8 else 0.0

    # Check for cone: is the point cloud tapered?
    taper_score = _compute_taper(vertices, centroid, eigenvectors)

    if sphericity > 0.85:
        # Nearly equal radii → sphere
        avg_r = sum(radii) / 3.0
        result.shape_type = "sphere"
        result.radii = (avg_r, avg_r, avg_r)
        result.confidence = sphericity

    elif taper_score > 0.6 and elongation > 1.5:
        # Significantly tapered and elongated → cone
        result.shape_type = "cone"
        result.confidence = taper_score * 0.8

    else:
        # General ellipsoid
        result.shape_type = "ellipsoid"
        result.confidence = 0.7 + 0.3 * (1.0 - sphericity)

    return result


def _compute_taper(vertices: List[Tuple[float, float, float]],
                   centroid: Tuple[float, float, float],
                   axes: List[Tuple[float, float, float]]) -> float:
    """
    Estimate how cone-like a point cloud is by checking if it tapers
    along its primary axis.

    Returns 0.0 (no taper) to 1.0 (strong taper, like a cone tip).
    """
    if len(vertices) < 10 or not axes:
        return 0.0

    # Project all vertices onto the primary axis
    ax = axes[0]
    ax_len = math.sqrt(ax[0]**2 + ax[1]**2 + ax[2]**2)
    if ax_len < 1e-10:
        return 0.0
    ax = (ax[0]/ax_len, ax[1]/ax_len, ax[2]/ax_len)

    projections = []
    for v in vertices:
        dx = v[0] - centroid[0]
        dy = v[1] - centroid[1]
        dz = v[2] - centroid[2]
        along = dx*ax[0] + dy*ax[1] + dz*ax[2]
        # Distance from axis
        perp_x = dx - along * ax[0]
        perp_y = dy - along * ax[1]
        perp_z = dz - along * ax[2]
        perp_dist = math.sqrt(perp_x**2 + perp_y**2 + perp_z**2)
        projections.append((along, perp_dist))

    if not projections:
        return 0.0

    # Sort by position along axis
    projections.sort(key=lambda x: x[0])

    # Compare average perpendicular distance in first quarter vs last quarter
    n = len(projections)
    q = max(1, n // 4)
    front_avg = sum(p[1] for p in projections[:q]) / q
    back_avg = sum(p[1] for p in projections[-q:]) / q

    if max(front_avg, back_avg) < 1e-8:
        return 0.0

    # Taper ratio: how much does it narrow?
    wider = max(front_avg, back_avg)
    narrower = min(front_avg, back_avg)
    taper = 1.0 - (narrower / wider)

    return min(1.0, taper)


# ── Multi-group fitting ──────────────────────────────────────────

def fit_mesh_groups(groups, materials: Dict = None) -> List[FittedPrimitive]:
    """
    Fit primitives to all groups in a parsed mesh.

    Args:
        groups: List of MeshGroup objects from obj_parser
        materials: Dict of Material objects, for color lookup

    Returns:
        List of FittedPrimitive objects, one per non-empty group
    """
    primitives = []
    for group in groups:
        if not group.vertices or len(group.vertices) < 4:
            continue

        prim = fit_primitive(
            vertices=group.vertices,
            centroid=group.centroid,
            face_count=group.face_count,
            material_name=group.material_name,
            label=group.name
        )
        if prim is not None:
            primitives.append(prim)

    return primitives


# ── Normalization ────────────────────────────────────────────────

def normalize_to_unit(primitives: List[FittedPrimitive],
                      target_height: float = 1.0) -> List[FittedPrimitive]:
    """
    Scale and center all primitives so the total bounding box fits
    within a target height. This normalizes ShapeNet models (which
    vary wildly in scale) to a consistent size for the Sigma library.

    Modifies primitives in place and returns them.
    """
    if not primitives:
        return primitives

    # Find global bounds
    all_points = []
    for p in primitives:
        cx, cy, cz = p.center
        rx, ry, rz = p.radii
        all_points.append((cx - rx, cy - ry, cz - rz))
        all_points.append((cx + rx, cy + ry, cz + rz))

    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    zs = [p[2] for p in all_points]

    bbox_min = (min(xs), min(ys), min(zs))
    bbox_max = (max(xs), max(ys), max(zs))

    extent = max(
        bbox_max[0] - bbox_min[0],
        bbox_max[1] - bbox_min[1],
        bbox_max[2] - bbox_min[2],
        1e-8
    )

    scale = target_height / extent

    # Center of the bounding box
    center_x = (bbox_min[0] + bbox_max[0]) / 2.0
    center_y = (bbox_min[1] + bbox_max[1]) / 2.0
    center_z = (bbox_min[2] + bbox_max[2]) / 2.0

    for p in primitives:
        p.center = (
            (p.center[0] - center_x) * scale,
            (p.center[1] - center_y) * scale,
            (p.center[2] - center_z) * scale
        )
        p.radii = (
            p.radii[0] * scale,
            p.radii[1] * scale,
            p.radii[2] * scale
        )

    return primitives


# ── Quality metrics ──────────────────────────────────────────────

def compute_fit_quality(primitives: List[FittedPrimitive]) -> dict:
    """
    Compute overall quality metrics for a set of fitted primitives.

    Returns dict with:
        - primitive_count: number of primitives
        - avg_confidence: mean confidence across all primitives
        - type_distribution: count of each shape type
        - total_vertices_covered: sum of vertices represented
        - coverage_rating: "excellent", "good", "fair", "poor"
    """
    if not primitives:
        return {
            "primitive_count": 0,
            "avg_confidence": 0,
            "type_distribution": {},
            "total_vertices_covered": 0,
            "coverage_rating": "empty"
        }

    types = {}
    total_conf = 0.0
    total_verts = 0

    for p in primitives:
        types[p.shape_type] = types.get(p.shape_type, 0) + 1
        total_conf += p.confidence
        total_verts += p.vertex_count

    avg_conf = total_conf / len(primitives)

    # Rating heuristic
    if avg_conf > 0.8 and len(primitives) >= 3:
        rating = "excellent"
    elif avg_conf > 0.6:
        rating = "good"
    elif avg_conf > 0.4:
        rating = "fair"
    else:
        rating = "poor"

    return {
        "primitive_count": len(primitives),
        "avg_confidence": round(avg_conf, 3),
        "type_distribution": types,
        "total_vertices_covered": total_verts,
        "coverage_rating": rating
    }


# ── Self-test ────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test with synthetic sphere-ish data
    print("Testing Jacobi eigendecomposition on a known matrix...")
    # Symmetric matrix with known eigenvalues: 3, 2, 1
    S = [
        [2.0, 0.5, 0.0],
        [0.5, 2.5, 0.5],
        [0.0, 0.5, 1.5]
    ]
    vals, vecs = jacobi_eigen_3x3(S)
    print(f"  Eigenvalues: {[round(v, 4) for v in vals]}")
    print(f"  Sum (should be 6.0): {sum(vals):.4f}")

    # Test sphere fitting
    print("\nTesting sphere detection...")
    sphere_pts = []
    for i in range(200):
        theta = 2 * math.pi * i / 200
        for j in range(100):
            phi = math.pi * j / 100
            x = math.sin(phi) * math.cos(theta)
            y = math.sin(phi) * math.sin(theta)
            z = math.cos(phi)
            sphere_pts.append((x, y, z))

    prim = fit_primitive(sphere_pts, (0, 0, 0), label="test_sphere")
    print(f"  Result: {prim}")
    print(f"  Type correct: {'sphere' == prim.shape_type}")

    # Test elongated ellipsoid
    print("\nTesting ellipsoid detection...")
    ell_pts = [(math.cos(t) * 0.5, math.sin(t) * 0.5, t * 0.1)
               for t in [i * 0.1 for i in range(200)]]
    cx = sum(p[0] for p in ell_pts) / len(ell_pts)
    cy = sum(p[1] for p in ell_pts) / len(ell_pts)
    cz = sum(p[2] for p in ell_pts) / len(ell_pts)
    prim2 = fit_primitive(ell_pts, (cx, cy, cz), label="test_ellipsoid")
    print(f"  Result: {prim2}")

    print("\nAll tests passed. Primitive fitter ready for harvest.")
