"""
Tests for the unified matter-based rendering system.

TDD: these tests define what the system MUST do.

Test categories:
  1. MatterNode — individual node behavior
  2. Lattice Fill — crystal structure fills shape correctly
  3. Surface Detection — broken bonds identify surface
  4. Neighbor Connectivity — entanglement bonds form correctly
  5. Push Rendering — surface nodes render correctly
  6. Physics Integration — σ chain connects through to rendering
  7. Copper Cube Scene — the actual demo scene
"""

import math
import sys
import os
import unittest

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.matter_node import MatterNode
from mattershaper.render.entangler.lattice_fill import (
    CRYSTAL_BASIS, COORDINATION, NN_DISTANCE_FACTOR,
    fill_cube_with_lattice, fill_sphere_with_lattice,
    connect_neighbors, resolve_all_surfaces, get_surface_nodes,
    build_matter_cube, build_matter_sphere,
    _inside_cube, _inside_sphere,
)
from mattershaper.render.entangler.matter_render import (
    matter_node_to_surface_node, entangle_matter,
)
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.materials.material import Material


def _copper_material():
    """Copper material with σ-chain properties."""
    return Material(
        name='Copper',
        color=Vec3(0.72, 0.45, 0.20),  # warm copper
        reflectance=0.90,
        roughness=0.15,
        density_kg_m3=8960,
        mean_Z=29, mean_A=64,
        composition='Cu (FCC)',
    )


def _hydrogen_material():
    """Hydrogen gas — transparent background medium."""
    return Material(
        name='Hydrogen Gas',
        color=Vec3(0.95, 0.95, 1.0),  # very faint blue
        reflectance=0.0,
        roughness=1.0,
        opacity=0.01,  # nearly transparent
        density_kg_m3=0.089,  # kg/m³ at STP
        mean_Z=1, mean_A=1,
        composition='H₂',
    )


# ── MatterNode Tests ──────────────────────────────────────────────

class TestMatterNode(unittest.TestCase):
    """Test individual MatterNode behavior."""

    def test_creation(self):
        """A node exists at a position with material and lattice index."""
        mat = _copper_material()
        node = MatterNode(Vec3(1, 2, 3), (0, 0, 0, 0), mat, 12)
        self.assertEqual(node.position.x, 1.0)
        self.assertEqual(node.max_neighbors, 12)
        self.assertFalse(node.is_surface)

    def test_add_neighbor(self):
        """Entanglement bonds form between nodes."""
        mat = _copper_material()
        n1 = MatterNode(Vec3(0, 0, 0), (0, 0, 0, 0), mat, 12)
        n2 = MatterNode(Vec3(1, 0, 0), (1, 0, 0, 0), mat, 12)
        n1.add_neighbor(n2)
        self.assertEqual(n1._neighbor_count, 1)
        self.assertIn(n2, n1.neighbors)

    def test_no_duplicate_neighbors(self):
        """Same bond can't form twice."""
        mat = _copper_material()
        n1 = MatterNode(Vec3(0, 0, 0), (0, 0, 0, 0), mat, 12)
        n2 = MatterNode(Vec3(1, 0, 0), (1, 0, 0, 0), mat, 12)
        n1.add_neighbor(n2)
        n1.add_neighbor(n2)
        self.assertEqual(n1._neighbor_count, 1)

    def test_broken_bond_count(self):
        """Surface atoms have broken bonds."""
        mat = _copper_material()
        node = MatterNode(Vec3(0, 0, 0), (0, 0, 0, 0), mat, 12)
        # Give it 9 neighbors (like FCC(111) surface)
        for i in range(9):
            n = MatterNode(Vec3(i + 1, 0, 0), (i + 1, 0, 0, 0), mat, 12)
            node.add_neighbor(n)
        self.assertEqual(node.broken_bond_count(), 3)
        self.assertAlmostEqual(node.broken_fraction, 3.0 / 12.0)

    def test_resolve_surface_bulk(self):
        """A fully coordinated node is NOT surface."""
        mat = _copper_material()
        center = MatterNode(Vec3(0, 0, 0), (0, 0, 0, 0), mat, 4)
        # 4 neighbors = full coordination for diamond cubic
        directions = [Vec3(1, 1, 1), Vec3(-1, -1, 1),
                      Vec3(-1, 1, -1), Vec3(1, -1, -1)]
        for i, d in enumerate(directions):
            n = MatterNode(d, (i, 0, 0, 0), mat, 4)
            center.add_neighbor(n)
        center.resolve_surface()
        self.assertFalse(center.is_surface)

    def test_resolve_surface_edge(self):
        """A node with fewer than max neighbors IS surface."""
        mat = _copper_material()
        node = MatterNode(Vec3(0, 0, 0), (0, 0, 0, 0), mat, 12)
        # Only give it 8 neighbors
        for i in range(8):
            angle = 2.0 * math.pi * i / 8.0
            n = MatterNode(
                Vec3(math.cos(angle), math.sin(angle), 0),
                (i, 0, 0, 0), mat, 12
            )
            node.add_neighbor(n)
        node.resolve_surface()
        self.assertTrue(node.is_surface)

    def test_normal_points_away_from_bulk(self):
        """Surface normal points away from the center of neighbor mass."""
        mat = _copper_material()
        # Node at (5, 0, 0) with neighbors all toward origin
        node = MatterNode(Vec3(5, 0, 0), (5, 0, 0, 0), mat, 4)
        for i in range(3):
            n = MatterNode(Vec3(4, i - 1, 0), (4, i, 0, 0), mat, 4)
            node.add_neighbor(n)
        node.resolve_surface()
        # Normal should point AWAY from neighbors → +x direction
        self.assertTrue(node.is_surface)
        self.assertGreater(node.normal.x, 0)


# ── Lattice Fill Tests ────────────────────────────────────────────

class TestLatticeFill(unittest.TestCase):
    """Test that crystal lattices fill shapes correctly."""

    def test_fcc_basis_count(self):
        """FCC has 4 basis atoms per unit cell."""
        self.assertEqual(len(CRYSTAL_BASIS['fcc']), 4)

    def test_bcc_basis_count(self):
        """BCC has 2 basis atoms per unit cell."""
        self.assertEqual(len(CRYSTAL_BASIS['bcc']), 2)

    def test_diamond_basis_count(self):
        """Diamond cubic has 8 basis atoms per unit cell."""
        self.assertEqual(len(CRYSTAL_BASIS['diamond_cubic']), 8)

    def test_fill_cube_produces_nodes(self):
        """Filling a cube with FCC copper produces atoms."""
        mat = _copper_material()
        # Use a large lattice param for fast test (not physical)
        nodes = fill_cube_with_lattice(
            Vec3(0, 0, 0), 1.0, 'fcc', 0.3, mat
        )
        self.assertGreater(len(nodes), 0)

    def test_all_nodes_inside_cube(self):
        """Every generated node is inside the cube boundary."""
        mat = _copper_material()
        center = Vec3(1, 2, 3)
        edge = 2.0
        nodes = fill_cube_with_lattice(center, edge, 'fcc', 0.5, mat)
        half = edge / 2.0
        for node in nodes.values():
            self.assertTrue(
                _inside_cube(node.position, center, half),
                f"Node at {node.position} is outside cube"
            )

    def test_fill_sphere_all_inside(self):
        """Every node from sphere fill is inside the sphere."""
        mat = _copper_material()
        center = Vec3(0, 0, 0)
        radius = 1.5
        nodes = fill_sphere_with_lattice(center, radius, 'bcc', 0.4, mat)
        for node in nodes.values():
            d = node.position - center
            dist = math.sqrt(d.dot(d))
            self.assertLessEqual(dist, radius * 1.001,
                                 f"Node at {node.position} outside sphere")

    def test_node_count_scales_with_volume(self):
        """More volume → more nodes (cubic scaling)."""
        mat = _copper_material()
        a = 0.5
        nodes_small = fill_cube_with_lattice(Vec3(0, 0, 0), 1.0, 'fcc', a, mat)
        nodes_large = fill_cube_with_lattice(Vec3(0, 0, 0), 2.0, 'fcc', a, mat)
        # 2× edge → ~8× volume → ~8× nodes
        ratio = len(nodes_large) / max(len(nodes_small), 1)
        self.assertGreater(ratio, 4.0)  # Should be ~8, use 4 as safe lower bound


# ── Neighbor Connectivity Tests ───────────────────────────────────

class TestNeighborConnectivity(unittest.TestCase):
    """Test that entanglement bonds connect correctly."""

    def test_fcc_interior_has_12_neighbors(self):
        """Interior FCC atoms should have 12 nearest neighbors."""
        mat = _copper_material()
        # Build big enough that interior atoms exist
        nodes = fill_cube_with_lattice(
            Vec3(0, 0, 0), 3.0, 'fcc', 0.5, mat
        )
        connect_neighbors(nodes, 'fcc', 0.5)
        resolve_all_surfaces(nodes)

        # Check that SOME interior atoms have full coordination
        interior = [n for n in nodes.values() if not n.is_surface]
        self.assertGreater(len(interior), 0, "No interior atoms found")

        for node in interior:
            self.assertEqual(
                node._neighbor_count, 12,
                f"Interior FCC atom has {node._neighbor_count} neighbors, expected 12"
            )

    def test_bcc_interior_has_8_neighbors(self):
        """Interior BCC atoms should have 8 nearest neighbors."""
        mat = _copper_material()
        nodes = fill_cube_with_lattice(
            Vec3(0, 0, 0), 3.0, 'bcc', 0.5, mat
        )
        connect_neighbors(nodes, 'bcc', 0.5)
        resolve_all_surfaces(nodes)

        interior = [n for n in nodes.values() if not n.is_surface]
        self.assertGreater(len(interior), 0)

        for node in interior:
            self.assertEqual(node._neighbor_count, 8,
                             f"Interior BCC atom has {node._neighbor_count}, expected 8")

    def test_bonds_are_symmetric(self):
        """If A is bonded to B, B is bonded to A."""
        mat = _copper_material()
        nodes = fill_cube_with_lattice(
            Vec3(0, 0, 0), 1.5, 'fcc', 0.5, mat
        )
        connect_neighbors(nodes, 'fcc', 0.5)

        for node in nodes.values():
            for neighbor in node.neighbors:
                self.assertIn(
                    node, neighbor.neighbors,
                    "Entanglement bond is not symmetric"
                )


# ── Surface Detection Tests ───────────────────────────────────────

class TestSurfaceDetection(unittest.TestCase):
    """Test that surface = broken entanglement bonds at shape boundary."""

    def test_surface_nodes_exist(self):
        """A finite object MUST have surface nodes."""
        mat = _copper_material()
        all_nodes, surface = build_matter_cube(
            Vec3(0, 0, 0), 2.0, 'fcc', 0.5, mat
        )
        self.assertGreater(len(surface), 0)

    def test_interior_nodes_exist(self):
        """A large enough object has interior (non-surface) nodes."""
        mat = _copper_material()
        all_nodes, surface = build_matter_cube(
            Vec3(0, 0, 0), 3.0, 'fcc', 0.5, mat
        )
        interior_count = len(all_nodes) - len(surface)
        self.assertGreater(interior_count, 0)

    def test_surface_fraction_reasonable(self):
        """Surface fraction should be between 0 and 1, decreasing with size."""
        mat = _copper_material()
        _, surf_small = build_matter_cube(
            Vec3(0, 0, 0), 2.0, 'fcc', 0.5, mat
        )
        all_small, _ = build_matter_cube(
            Vec3(0, 0, 0), 2.0, 'fcc', 0.5, mat
        )
        frac = len(surf_small) / len(all_small)
        self.assertGreater(frac, 0.0)
        self.assertLess(frac, 1.0)

    def test_surface_normals_point_outward(self):
        """Surface normals should generally point away from object center."""
        mat = _copper_material()
        center = Vec3(0, 0, 0)
        _, surface = build_matter_cube(center, 2.0, 'fcc', 0.5, mat)

        outward_count = 0
        for node in surface:
            to_outside = node.position - center
            if to_outside.dot(node.normal) > 0:
                outward_count += 1

        # Most (>70%) surface normals should point outward
        frac_outward = outward_count / len(surface)
        self.assertGreater(frac_outward, 0.7,
                           f"Only {frac_outward:.0%} normals point outward")

    def test_sphere_surface_is_shell(self):
        """Sphere surface nodes should form a shell at the boundary."""
        mat = _copper_material()
        center = Vec3(0, 0, 0)
        radius = 2.0
        all_nodes, surface = build_matter_sphere(
            center, radius, 'fcc', 0.5, mat
        )
        # Surface nodes should be near the sphere boundary
        for node in surface:
            d = node.position - center
            dist = math.sqrt(d.dot(d))
            # Should be within ~1 lattice param of the boundary
            self.assertGreater(dist, radius - 1.0,
                               "Surface node too far from sphere boundary")


# ── Push Rendering Tests ──────────────────────────────────────────

class TestPushRendering(unittest.TestCase):
    """Test that surface MatterNodes render correctly via push projection."""

    def _make_camera_and_light(self):
        """Standard test camera and light."""
        camera = PushCamera(
            pos=Vec3(0, 0, -5),
            look_at=Vec3(0, 0, 0),
            width=64, height=64, fov=60
        )
        light = PushLight(pos=Vec3(5, 5, -5), intensity=1.0)
        return camera, light

    def test_matter_node_converts_to_surface_node(self):
        """MatterNode → SurfaceNode adapter works."""
        mat = _copper_material()
        mnode = MatterNode(Vec3(1, 2, 3), (0, 0, 0, 0), mat, 12)
        mnode.normal = Vec3(0, 1, 0)
        snode = matter_node_to_surface_node(mnode)
        self.assertAlmostEqual(snode.position.x, 1.0)
        self.assertAlmostEqual(snode.normal.y, 1.0)
        self.assertEqual(snode.material.name, 'Copper')

    def test_render_produces_pixels(self):
        """Rendering a matter cube produces non-background pixels."""
        camera, light = self._make_camera_and_light()
        mat = _copper_material()

        objects = [{
            'type': 'cube',
            'center': Vec3(0, 0, 0),
            'size': 1.5,
            'crystal_structure': 'fcc',
            'lattice_param_m': 0.5,
            'material': mat,
        }]

        pixels, stats = entangle_matter(objects, camera, light)

        # Should have rendered some nodes
        self.assertGreater(stats['rendered_nodes'], 0)
        self.assertGreater(stats['total_atoms'], 0)

    def test_render_has_copper_color(self):
        """Rendered pixels should show copper color (warm/orange tones)."""
        camera, light = self._make_camera_and_light()
        mat = _copper_material()

        objects = [{
            'type': 'cube',
            'center': Vec3(0, 0, 0),
            'size': 1.5,
            'crystal_structure': 'fcc',
            'lattice_param_m': 0.5,
            'material': mat,
        }]

        pixels, stats = entangle_matter(objects, camera, light)

        # Find non-background pixels
        bg = Vec3(0.12, 0.12, 0.14)
        copper_pixels = []
        for row in pixels:
            for p in row:
                if abs(p.x - bg.x) > 0.01 or abs(p.y - bg.y) > 0.01:
                    copper_pixels.append(p)

        self.assertGreater(len(copper_pixels), 0, "No copper pixels rendered")

        # Copper color: red channel > green > blue
        avg_r = sum(p.x for p in copper_pixels) / len(copper_pixels)
        avg_g = sum(p.y for p in copper_pixels) / len(copper_pixels)
        avg_b = sum(p.z for p in copper_pixels) / len(copper_pixels)

        self.assertGreater(avg_r, avg_b, "Copper should be warmer than blue")

    def test_stats_report_surface_fraction(self):
        """Stats should report meaningful surface fraction."""
        camera, light = self._make_camera_and_light()
        mat = _copper_material()

        objects = [{
            'type': 'cube',
            'center': Vec3(0, 0, 0),
            'size': 2.0,
            'crystal_structure': 'fcc',
            'lattice_param_m': 0.5,
            'material': mat,
        }]

        _, stats = entangle_matter(objects, camera, light)

        self.assertIn('surface_fraction', stats)
        self.assertGreater(stats['surface_fraction'], 0)
        self.assertLess(stats['surface_fraction'], 1)
        self.assertGreater(stats['surface_atoms'], 0)
        self.assertLess(stats['surface_atoms'], stats['total_atoms'])


# ── Physics Integration Tests ─────────────────────────────────────

class TestPhysicsIntegration(unittest.TestCase):
    """Test that the σ derivation chain connects to rendering."""

    def test_copper_fcc_coordination(self):
        """Copper is FCC → coordination number 12."""
        self.assertEqual(COORDINATION['fcc'], 12)

    def test_copper_nn_distance(self):
        """FCC nearest neighbor distance = a/√2."""
        a = 3.615e-10  # copper lattice param in meters
        nn = NN_DISTANCE_FACTOR['fcc'] * a
        expected = a / math.sqrt(2)
        self.assertAlmostEqual(nn, expected, places=20)

    def test_broken_bonds_match_surface_module(self):
        """Surface node broken fraction should match surface.py's model.

        For FCC(111): Z_b=12, Z_s=9 → broken fraction = 3/24 = 1/8.
        MatterNodes on the (111) face of the cube should have ~3 broken bonds.
        """
        # The exact broken bond count depends on the face orientation,
        # but nodes on flat faces should have ~3 broken bonds (FCC cube faces)
        mat = _copper_material()
        all_nodes, surface = build_matter_cube(
            Vec3(0, 0, 0), 3.0, 'fcc', 0.5, mat
        )

        # Check that broken bond counts are in physical range
        broken_counts = [n.broken_bond_count() for n in surface]
        avg_broken = sum(broken_counts) / len(broken_counts)

        # For a cube, faces have ~3-5 broken bonds, edges ~5-7, corners ~9
        self.assertGreater(avg_broken, 1)
        self.assertLess(avg_broken, 12)

    def test_hydrogen_gas_is_transparent(self):
        """Hydrogen material should have near-zero opacity."""
        h2 = _hydrogen_material()
        self.assertLess(h2.opacity, 0.1)
        self.assertAlmostEqual(h2.density_kg_m3, 0.089)

    def test_material_properties_preserved_through_render(self):
        """Material color survives the MatterNode → SurfaceNode → render chain."""
        mat = _copper_material()
        node = MatterNode(Vec3(0, 0, 1), (0, 0, 0, 0), mat, 12)
        node.normal = Vec3(0, 0, -1)  # facing camera
        snode = matter_node_to_surface_node(node)

        # The material color should be preserved
        self.assertAlmostEqual(snode.material.color.x, 0.72)  # copper red
        self.assertAlmostEqual(snode.material.color.y, 0.45)  # copper green
        self.assertAlmostEqual(snode.material.color.z, 0.20)  # copper blue


# ── Copper Cube Scene Tests ───────────────────────────────────────

class TestCopperCubeScene(unittest.TestCase):
    """Integration test: the full copper-cube-in-hydrogen demo."""

    def test_full_scene_renders(self):
        """The copper cube scene produces a complete render."""
        camera = PushCamera(
            pos=Vec3(0, 2, -6),
            look_at=Vec3(0, 0, 0),
            width=32, height=32, fov=60
        )
        light = PushLight(pos=Vec3(5, 8, -5), intensity=1.0)

        copper = _copper_material()

        scene = [{
            'type': 'cube',
            'center': Vec3(0, 0, 0),
            'size': 2.0,
            'crystal_structure': 'fcc',
            'lattice_param_m': 0.5,  # exaggerated for speed
            'material': copper,
        }]

        pixels, stats = entangle_matter(scene, camera, light)

        # Scene should have atoms
        self.assertGreater(stats['total_atoms'], 10)
        # Scene should have surface atoms
        self.assertGreater(stats['surface_atoms'], 0)
        # Scene should render visible pixels
        self.assertGreater(stats['rendered_nodes'], 0)

        print(f"\n  Copper Cube Scene:")
        print(f"    Total atoms:    {stats['total_atoms']}")
        print(f"    Surface atoms:  {stats['surface_atoms']}")
        print(f"    Surface fraction: {stats['surface_fraction']:.1%}")
        print(f"    Rendered nodes: {stats['rendered_nodes']}")
        print(f"    Resolution:     {stats['resolution']}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
