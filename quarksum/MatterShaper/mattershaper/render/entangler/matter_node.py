"""
MatterNode — a quark that knows where it is, what it's connected to,
and whether it faces the outside.

This is the unification of geometry, physics, and rendering.

The key insight:
  - SHAPE defines the boundary (what region of space this object occupies)
  - ENTANGLEMENT defines the lattice (bonds between quarks/atoms)
  - SURFACE = where entanglement meets shape boundary
    (atoms whose bond network extends past the shape edge)
  - EMISSION = surface nodes push their color outward

Position is NOT assigned by a mesh. Position is DERIVED from:
  1. Crystal structure (FCC for copper, BCC for iron, etc.)
  2. Lattice parameter (from MEASURED data)
  3. Shape boundary (defines which lattice sites are inside)

An atom is a SURFACE atom if it has fewer neighbors than the bulk
coordination number — meaning some of its entanglement bonds
were severed by the shape boundary.

This is reality's rendering engine:
  Matter doesn't wait to be seen. It broadcasts.
  Entanglement is reality's TV.

Zero shared code with any ray tracer.
"""

import math
from .vec import Vec3


class MatterNode:
    """An atom/quark that exists at a lattice site inside a shape.

    It knows:
      - Where it is (lattice position)
      - What it's made of (material properties from σ chain)
      - Who it's bonded to (entanglement network)
      - Whether it's on the surface (broken bonds at shape boundary)
      - What direction it faces (normal from missing neighbor geometry)

    A surface MatterNode IS a rendering node. It emits.
    An interior MatterNode is silent — it contributes mass, not photons.
    """
    __slots__ = (
        'position',         # Vec3: world position (from lattice + shape)
        'lattice_index',    # (i, j, k, basis): position in crystal grid
        'material',         # Material: physics + optical properties
        'neighbors',        # list of MatterNode: entanglement bonds
        'max_neighbors',    # int: bulk coordination number
        'is_surface',       # bool: True if broken bonds exist
        'normal',           # Vec3: outward normal (from missing neighbor direction)
        '_neighbor_count',  # int: cached count for fast surface check
    )

    def __init__(self, position, lattice_index, material, max_neighbors):
        self.position = position
        self.lattice_index = lattice_index
        self.material = material
        self.neighbors = []
        self.max_neighbors = max_neighbors
        self.is_surface = False
        self.normal = Vec3(0, 1, 0)  # placeholder until bonds are resolved
        self._neighbor_count = 0

    def add_neighbor(self, other):
        """Form an entanglement bond with another node."""
        if other not in self.neighbors:
            self.neighbors.append(other)
            self._neighbor_count += 1

    def broken_bond_count(self):
        """How many entanglement bonds were severed by the shape boundary.

        FIRST_PRINCIPLES: An atom in bulk has max_neighbors bonds.
        An atom at a surface has fewer — the missing bonds point outward.
        This is exactly the broken-bond model from surface.py.
        """
        return self.max_neighbors - self._neighbor_count

    def resolve_surface(self):
        """Determine if this node is on the surface and compute its normal.

        FIRST_PRINCIPLES:
          Surface = broken bonds exist (some entanglement extends past shape)
          Normal = average direction of missing neighbor sites
                 = direction AWAY from the occupied neighbors

        This is physically exact: the outward normal of a crystal surface
        points away from the bulk, in the direction of the broken bonds.
        """
        self.is_surface = self._neighbor_count < self.max_neighbors

        if not self.is_surface:
            return

        # Normal: direction away from center of mass of existing neighbors
        if self._neighbor_count > 0:
            neighbor_centroid = Vec3(0, 0, 0)
            for n in self.neighbors:
                neighbor_centroid = neighbor_centroid + n.position
            neighbor_centroid = neighbor_centroid * (1.0 / self._neighbor_count)

            # Point AWAY from bulk (away from neighbor centroid)
            outward = self.position - neighbor_centroid
            length = outward.length()
            if length > 1e-12:
                self.normal = outward.normalized()
            else:
                # Degenerate: use position direction from origin as fallback
                self.normal = self.position.normalized()
        else:
            # Isolated node: normal points outward from origin
            self.normal = self.position.normalized()

    @property
    def broken_fraction(self):
        """Fraction of bonds broken — directly maps to surface energy.

        This IS the broken-bond model: γ ∝ (Z_b - Z_s) / (2 Z_b).
        Each surface node carries its own broken fraction.
        """
        if self.max_neighbors == 0:
            return 0.0
        return self.broken_bond_count() / self.max_neighbors

    def __repr__(self):
        tag = "SURFACE" if self.is_surface else "bulk"
        return (f"MatterNode({tag}, bonds={self._neighbor_count}/"
                f"{self.max_neighbors}, pos={self.position})")
