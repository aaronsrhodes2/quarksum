"""
Lattice Fill — build matter by filling a shape with crystal structure.

Given a shape boundary and a material, this module:
  1. Generates lattice sites (FCC, BCC, HCP, diamond cubic)
  2. Tests each site against the shape boundary (inside/outside)
  3. Connects neighbors (entanglement bonds)
  4. Identifies surface nodes (broken bonds at boundary)

The result is a cloud of MatterNodes where:
  - Interior nodes have full coordination (silent, invisible)
  - Surface nodes have broken bonds (they emit, they render)

This replaces the Fibonacci spiral surface sampling with
physically real atomic positions. The surface isn't sampled —
it's DISCOVERED by where the crystal lattice meets the shape edge.

Crystal basis vectors (fractional coordinates):
  FCC:  (0,0,0), (½,½,0), (½,0,½), (0,½,½) — 4 atoms/cell
  BCC:  (0,0,0), (½,½,½) — 2 atoms/cell
  HCP:  (0,0,0), (⅓,⅔,½) — 2 atoms/cell (using ortho box)
  Diamond: FCC basis + shifted FCC — 8 atoms/cell

Neighbor finding:
  Instead of searching all-pairs (O(N²)), we use lattice indices.
  For FCC with basis atom b at cell (i,j,k), the 12 nearest neighbors
  are at known offsets in (Δi, Δj, Δk, Δb) space.
  This is O(N) — each atom checks a fixed number of neighbor slots.

Zero shared code with any ray tracer.
"""

import math
from .vec import Vec3
from .matter_node import MatterNode


# ── Crystal basis definitions ─────────────────────────────────────
# Fractional coordinates within the conventional unit cell.
# FIRST_PRINCIPLES: these are pure geometry of each crystal packing.

CRYSTAL_BASIS = {
    'fcc': [
        (0.0, 0.0, 0.0),
        (0.5, 0.5, 0.0),
        (0.5, 0.0, 0.5),
        (0.0, 0.5, 0.5),
    ],
    'bcc': [
        (0.0, 0.0, 0.0),
        (0.5, 0.5, 0.5),
    ],
    'hcp': [
        # Orthogonal box: a₁ = a, a₂ = a√3, a₃ = c = a√(8/3)
        (0.0, 0.0, 0.0),
        (0.5, 1.0 / (2.0 * math.sqrt(3.0)), 0.5),
    ],
    'diamond_cubic': [
        (0.0, 0.0, 0.0),
        (0.5, 0.5, 0.0),
        (0.5, 0.0, 0.5),
        (0.0, 0.5, 0.5),
        (0.25, 0.25, 0.25),
        (0.75, 0.75, 0.25),
        (0.75, 0.25, 0.75),
        (0.25, 0.75, 0.75),
    ],
}

# Bulk coordination numbers (same as surface.py — geometry of packing)
COORDINATION = {
    'fcc': 12,
    'bcc': 8,
    'hcp': 12,
    'diamond_cubic': 4,
}

# Nearest neighbor distance in units of lattice parameter
# FIRST_PRINCIPLES: geometry of each structure
NN_DISTANCE_FACTOR = {
    'fcc': math.sqrt(2) / 2.0,           # a/√2 ≈ 0.707a
    'bcc': math.sqrt(3) / 2.0,           # a√3/2 ≈ 0.866a
    'hcp': 1.0,                           # = a (within basal plane)
    'diamond_cubic': math.sqrt(3) / 4.0,  # a√3/4 ≈ 0.433a
}


def _inside_cube(pos, center, half_size):
    """Test if a point is inside an axis-aligned cube.

    Args:
        pos: Vec3 position to test
        center: Vec3 cube center
        half_size: float, half the cube edge length

    Returns:
        True if inside (inclusive of boundary).
    """
    return (abs(pos.x - center.x) <= half_size and
            abs(pos.y - center.y) <= half_size and
            abs(pos.z - center.z) <= half_size)


def _inside_sphere(pos, center, radius):
    """Test if a point is inside a sphere."""
    d = pos - center
    return d.dot(d) <= radius * radius


def fill_cube_with_lattice(center, edge_length, crystal_structure,
                           lattice_param_m, material):
    """Fill a cube-shaped region with crystal lattice sites.

    Args:
        center: Vec3, center of the cube in world coordinates
        edge_length: float, edge length in meters
        crystal_structure: 'fcc', 'bcc', 'hcp', 'diamond_cubic'
        lattice_param_m: float, lattice parameter in meters
        material: Material object for all nodes

    Returns:
        dict mapping (i, j, k, b) → MatterNode for all sites inside the cube.
    """
    if crystal_structure not in CRYSTAL_BASIS:
        raise ValueError(f"Unknown crystal structure: {crystal_structure}")

    basis = CRYSTAL_BASIS[crystal_structure]
    coord = COORDINATION[crystal_structure]
    a = lattice_param_m
    half = edge_length / 2.0

    # How many unit cells do we need along each axis?
    # Overshoot by 1 to ensure full coverage
    n_cells = int(math.ceil(edge_length / a)) + 1

    # Center the lattice grid on the cube center
    # Offset so that cell (0,0,0) is near one corner
    offset = Vec3(
        center.x - (n_cells * a) / 2.0,
        center.y - (n_cells * a) / 2.0,
        center.z - (n_cells * a) / 2.0,
    )

    nodes = {}  # (i, j, k, b) → MatterNode

    for i in range(n_cells):
        for j in range(n_cells):
            for k in range(n_cells):
                for b, (fx, fy, fz) in enumerate(basis):
                    # World position of this lattice site
                    pos = Vec3(
                        offset.x + (i + fx) * a,
                        offset.y + (j + fy) * a,
                        offset.z + (k + fz) * a,
                    )

                    # Shape test: is this site inside the cube?
                    if not _inside_cube(pos, center, half):
                        continue

                    idx = (i, j, k, b)
                    node = MatterNode(pos, idx, material, coord)
                    nodes[idx] = node

    return nodes


def fill_sphere_with_lattice(center, radius, crystal_structure,
                             lattice_param_m, material):
    """Fill a sphere-shaped region with crystal lattice sites.

    Same logic as fill_cube, but with spherical boundary test.
    """
    if crystal_structure not in CRYSTAL_BASIS:
        raise ValueError(f"Unknown crystal structure: {crystal_structure}")

    basis = CRYSTAL_BASIS[crystal_structure]
    coord = COORDINATION[crystal_structure]
    a = lattice_param_m

    n_cells = int(math.ceil(2 * radius / a)) + 1

    offset = Vec3(
        center.x - (n_cells * a) / 2.0,
        center.y - (n_cells * a) / 2.0,
        center.z - (n_cells * a) / 2.0,
    )

    nodes = {}

    for i in range(n_cells):
        for j in range(n_cells):
            for k in range(n_cells):
                for b, (fx, fy, fz) in enumerate(basis):
                    pos = Vec3(
                        offset.x + (i + fx) * a,
                        offset.y + (j + fy) * a,
                        offset.z + (k + fz) * a,
                    )

                    if not _inside_sphere(pos, center, radius):
                        continue

                    idx = (i, j, k, b)
                    node = MatterNode(pos, idx, material, coord)
                    nodes[idx] = node

    return nodes


def connect_neighbors(nodes, crystal_structure, lattice_param_m, tolerance=1.15):
    """Connect nearest neighbors in the lattice — form entanglement bonds.

    FIRST_PRINCIPLES: Nearest neighbor distance is a geometric property
    of the crystal structure. We connect any two nodes within
    nn_distance × tolerance.

    This is O(N × Z) where Z is the coordination number, because
    we only check lattice-adjacent cells. For a dict keyed by
    (i,j,k,b) we can enumerate candidate neighbors directly.

    But for simplicity and correctness, we use the distance-based
    approach with a spatial hash for O(N) average case.

    Args:
        nodes: dict of (i,j,k,b) → MatterNode
        crystal_structure: crystal type
        lattice_param_m: lattice parameter in meters
        tolerance: multiplicative tolerance on NN distance (>1.0 for numerical safety)
    """
    nn_dist = NN_DISTANCE_FACTOR[crystal_structure] * lattice_param_m
    cutoff = nn_dist * tolerance
    cutoff_sq = cutoff * cutoff

    # Build spatial hash for O(N) neighbor finding
    cell_size = cutoff * 1.01  # slightly larger than cutoff
    spatial_hash = {}

    node_list = list(nodes.values())

    for node in node_list:
        cx = int(math.floor(node.position.x / cell_size))
        cy = int(math.floor(node.position.y / cell_size))
        cz = int(math.floor(node.position.z / cell_size))
        key = (cx, cy, cz)
        if key not in spatial_hash:
            spatial_hash[key] = []
        spatial_hash[key].append(node)

    # For each node, check 27 neighboring cells (3³)
    for node in node_list:
        cx = int(math.floor(node.position.x / cell_size))
        cy = int(math.floor(node.position.y / cell_size))
        cz = int(math.floor(node.position.z / cell_size))

        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for dk in (-1, 0, 1):
                    key = (cx + di, cy + dj, cz + dk)
                    if key not in spatial_hash:
                        continue
                    for other in spatial_hash[key]:
                        if other is node:
                            continue
                        d = node.position - other.position
                        dist_sq = d.dot(d)
                        if dist_sq <= cutoff_sq:
                            node.add_neighbor(other)


def resolve_all_surfaces(nodes):
    """Mark surface nodes and compute their outward normals.

    After this call:
      - node.is_surface is True for nodes with broken bonds
      - node.normal points outward (away from bulk)

    The surface nodes are the rendering layer. They emit.
    Interior nodes are invisible.
    """
    for node in nodes.values():
        node.resolve_surface()


def get_surface_nodes(nodes):
    """Extract only the surface nodes — the emitters.

    These are the nodes that will push-render. Everything else
    is silent interior matter.

    Returns:
        list of MatterNode where is_surface is True.
    """
    return [n for n in nodes.values() if n.is_surface]


def build_matter_cube(center, edge_length, crystal_structure,
                      lattice_param_m, material):
    """Complete pipeline: fill cube → connect bonds → find surface.

    This is the full construction of a piece of matter:
      1. Crystal lattice fills the shape volume
      2. Entanglement bonds connect nearest neighbors
      3. Surface detected where bonds are broken by shape boundary
      4. Surface normals computed from missing neighbor geometry

    Args:
        center: Vec3, cube center
        edge_length: float, edge length in meters
        crystal_structure: 'fcc', 'bcc', etc.
        lattice_param_m: float, lattice parameter in meters
        material: Material

    Returns:
        (all_nodes_dict, surface_nodes_list)
    """
    nodes = fill_cube_with_lattice(
        center, edge_length, crystal_structure, lattice_param_m, material
    )
    connect_neighbors(nodes, crystal_structure, lattice_param_m)
    resolve_all_surfaces(nodes)
    surface = get_surface_nodes(nodes)

    return nodes, surface


def build_matter_sphere(center, radius, crystal_structure,
                        lattice_param_m, material):
    """Same as build_matter_cube but with spherical shape."""
    nodes = fill_sphere_with_lattice(
        center, radius, crystal_structure, lattice_param_m, material
    )
    connect_neighbors(nodes, crystal_structure, lattice_param_m)
    resolve_all_surfaces(nodes)
    surface = get_surface_nodes(nodes)

    return nodes, surface
