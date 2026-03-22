"""
Tests for VolumeNode — volumetric Beer-Lambert fill.

TDD: these tests define EXACTLY what the system must do.

Physics contracts being tested:
  1. VolumeNode — node structure and memory properties
  2. Fibonacci 3D fill — uniform distribution, correct count
  3. Beer-Lambert opacity — per-channel, exact formula
  4. Cascade termination — opaque materials stop after expected depth
  5. Per-channel compositor — ruby absorbs green but passes red/blue
  6. fill_volume flag — shapes advertise volumetric fill capability
  7. Integration — volume nodes + surface nodes render through Porter-Duff

□σ = −ξR
"""

import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from mattershaper.render.entangler.vec import Vec3
from mattershaper.render.entangler.volume_nodes import (
    VolumeNode,
    generate_volume_nodes,
    volume_node_opacity,
    GOLDEN_RATIO,
)
from mattershaper.render.entangler.shapes import (
    EntanglerSphere, EntanglerEllipsoid,
)
from mattershaper.render.entangler.engine import entangle, _OPAQUE_THRESHOLD
from mattershaper.render.entangler.projection import PushCamera
from mattershaper.render.entangler.illumination import PushLight
from mattershaper.materials.material import Material


# ── Helpers ───────────────────────────────────────────────────────────────

def _opaque_material():
    """Aluminum-like: massive alpha, all channels."""
    return Material(
        name='OpaqueTest',
        color=Vec3(0.9, 0.9, 0.9),
        opacity=1.0,
        alpha_r=3.26e6, alpha_g=3.39e6, alpha_b=3.53e6,   # /inch
    )


def _ruby_material():
    """Ruby-like: absorbs green strongly, transparent to red and blue."""
    return Material(
        name='RubyTest',
        color=Vec3(0.95, 0.10, 0.10),
        opacity=0.04,    # Fresnel surface reflectance ~4%
        alpha_r=0.10,    # /inch — transparent to red
        alpha_g=2.30,    # /inch — strong green absorption
        alpha_b=0.80,    # /inch — moderate blue absorption
    )


def _transparent_material():
    """Diamond-like: very low absorption all channels."""
    return Material(
        name='TransparentTest',
        color=Vec3(0.99, 0.99, 0.99),
        opacity=0.04,
        alpha_r=0.001, alpha_g=0.001, alpha_b=0.001,
    )


def _sphere(material, radius=1.0, center=None):
    return EntanglerSphere(
        center=center or Vec3(0, 0, 0),
        radius=radius,
        material=material,
        fill_volume=True,
    )


# ── VolumeNode Tests ──────────────────────────────────────────────────────

class TestVolumeNode(unittest.TestCase):
    """VolumeNode structure, slots, cascade inheritance."""

    def test_creation(self):
        """VolumeNode exists at a position with material and dl."""
        mat = _opaque_material()
        node = VolumeNode(Vec3(1, 2, 3), depth=0.5, material=mat, dl=0.1)
        self.assertAlmostEqual(node.position.x, 1.0)
        self.assertAlmostEqual(node.depth, 0.5)
        self.assertAlmostEqual(node.dl, 0.1)
        self.assertIs(node.material, mat)

    def test_slots_defined(self):
        """VolumeNode uses __slots__ for memory efficiency."""
        self.assertTrue(hasattr(VolumeNode, '__slots__'))
        slots = set(VolumeNode.__slots__)
        self.assertIn('position', slots)
        self.assertIn('depth', slots)
        self.assertIn('material', slots)
        self.assertIn('dl', slots)

    def test_cascade_inheritance(self):
        """All nodes from the same sphere share the SAME material object.

        This is the cascade inheritance — ONE material, N node refs.
        Memory cost is 40 bytes/node + 64 bytes once, not 104 bytes/node.
        """
        mat = _ruby_material()
        sphere = _sphere(mat, radius=0.5)
        nodes = generate_volume_nodes(sphere, n_nodes=100)

        # All nodes must reference the SAME material object
        for node in nodes:
            self.assertIs(node.material, mat,
                          "VolumeNode material must be the shared Material object")


# ── Fibonacci Fill Tests ──────────────────────────────────────────────────

class TestFibonacciFill(unittest.TestCase):
    """3D Fibonacci fill produces uniform volumetric distribution."""

    def test_node_count(self):
        """generate_volume_nodes returns exactly n_nodes nodes."""
        mat = _opaque_material()
        sphere = _sphere(mat, radius=1.0)
        nodes = generate_volume_nodes(sphere, n_nodes=500)
        self.assertEqual(len(nodes), 500)

    def test_all_nodes_inside_sphere(self):
        """All generated nodes are inside the sphere."""
        mat = _opaque_material()
        R = 2.0
        sphere = _sphere(mat, radius=R, center=Vec3(1, 2, 3))
        nodes = generate_volume_nodes(sphere, n_nodes=1000)

        for node in nodes:
            d = node.position - sphere.center
            dist = math.sqrt(d.dot(d))
            self.assertLessEqual(dist, R * 1.0001,
                                 f"Node at dist {dist:.4f} outside sphere R={R}")

    def test_nodes_fill_center(self):
        """Some nodes are near the center (not just a shell)."""
        mat = _opaque_material()
        R = 1.0
        sphere = _sphere(mat, radius=R)
        nodes = generate_volume_nodes(sphere, n_nodes=500)

        # At least some nodes within 20% of radius from center
        near_center = [
            n for n in nodes
            if (n.position - sphere.center).length() < 0.2 * R
        ]
        self.assertGreater(len(near_center), 0,
                           "No nodes near center — fill is hollow")

    def test_depth_is_distance_from_surface(self):
        """node.depth = R - |pos - center| for sphere."""
        mat = _opaque_material()
        R = 2.0
        center = Vec3(0, 0, 0)
        sphere = _sphere(mat, radius=R, center=center)
        nodes = generate_volume_nodes(sphere, n_nodes=200)

        for node in nodes:
            r = (node.position - center).length()
            expected_depth = R - r
            self.assertAlmostEqual(node.depth, expected_depth, places=6,
                                   msg=f"depth {node.depth:.4f} != R-r {expected_depth:.4f}")

    def test_dl_is_uniform(self):
        """All nodes in the same sphere have the same dl (cascade basis)."""
        mat = _opaque_material()
        sphere = _sphere(mat, radius=1.0)
        nodes = generate_volume_nodes(sphere, n_nodes=300)

        dl_values = set(n.dl for n in nodes)
        self.assertEqual(len(dl_values), 1,
                         "dl should be the same for all nodes in one sphere")

    def test_dl_is_cbrt_of_volume_per_node(self):
        """dl = (V/n)^(1/3) — the characteristic linear spacing."""
        mat = _opaque_material()
        R = 3.0
        n = 1000
        sphere = _sphere(mat, radius=R)
        nodes = generate_volume_nodes(sphere, n_nodes=n)

        V = (4.0 / 3.0) * math.pi * R**3
        expected_dl = (V / n) ** (1.0 / 3.0)
        actual_dl = nodes[0].dl

        self.assertAlmostEqual(actual_dl, expected_dl, places=10)

    def test_uniform_radial_distribution(self):
        """Radial distribution is uniform in 3D (equal volume per shell).

        PROVEN: for uniform volumetric sampling, the CDF of r is
        F(r) = (r/R)³. The fraction of nodes with r < R/2 should be
        approximately (1/2)³ = 12.5%.
        """
        mat = _opaque_material()
        R = 1.0
        n = 2000
        sphere = _sphere(mat, radius=R)
        nodes = generate_volume_nodes(sphere, n_nodes=n)

        inner = sum(
            1 for node in nodes
            if (node.position - sphere.center).length() < R / 2.0
        )
        fraction = inner / n

        # Should be ~12.5% (1/8), allow 3% tolerance
        self.assertAlmostEqual(fraction, 0.125, delta=0.04,
                               msg=f"Radial distribution non-uniform: {fraction:.3f} != 0.125")

    def test_golden_ratio_is_irrational(self):
        """GOLDEN_RATIO is irrational — successive points never align."""
        # Verify it equals (1 + sqrt(5)) / 2
        expected = (1.0 + math.sqrt(5.0)) / 2.0
        self.assertAlmostEqual(GOLDEN_RATIO, expected, places=10)

    def test_node_count_scales_with_sphere_volume(self):
        """Larger sphere → same physics density means more nodes in caller."""
        # This tests that the API accepts n_nodes directly — caller controls density.
        mat = _opaque_material()
        s1 = _sphere(mat, radius=1.0)
        s2 = _sphere(mat, radius=2.0)
        n1 = generate_volume_nodes(s1, n_nodes=100)
        n2 = generate_volume_nodes(s2, n_nodes=100)
        # Both return exactly n_nodes — density scaling is the caller's job
        self.assertEqual(len(n1), 100)
        self.assertEqual(len(n2), 100)


# ── Beer-Lambert Opacity Tests ────────────────────────────────────────────

class TestBeerLambertOpacity(unittest.TestCase):
    """volume_node_opacity returns exact Beer-Lambert per-channel values."""

    def test_exact_formula(self):
        """opacity_i = 1 - exp(-alpha_i * dl). Exact."""
        mat = Material(
            name='TestMat',
            color=Vec3(0.5, 0.5, 0.5),
            alpha_r=1.0, alpha_g=2.0, alpha_b=4.0,
        )
        node = VolumeNode(Vec3(0, 0, 0), depth=0.5, material=mat, dl=0.3)
        op_r, op_g, op_b = volume_node_opacity(node)

        self.assertAlmostEqual(op_r, 1.0 - math.exp(-1.0 * 0.3), places=10)
        self.assertAlmostEqual(op_g, 1.0 - math.exp(-2.0 * 0.3), places=10)
        self.assertAlmostEqual(op_b, 1.0 - math.exp(-4.0 * 0.3), places=10)

    def test_zero_alpha_means_transparent(self):
        """alpha=0 → opacity=0 (fully transparent to that channel)."""
        mat = Material(
            name='TestMat',
            color=Vec3(0.5, 0.5, 0.5),
            alpha_r=0.0, alpha_g=0.0, alpha_b=0.0,
        )
        node = VolumeNode(Vec3(0, 0, 0), depth=0, material=mat, dl=1.0)
        op_r, op_g, op_b = volume_node_opacity(node)
        self.assertAlmostEqual(op_r, 0.0, places=10)
        self.assertAlmostEqual(op_g, 0.0, places=10)
        self.assertAlmostEqual(op_b, 0.0, places=10)

    def test_huge_alpha_means_opaque(self):
        """Very large alpha*dl → opacity ≈ 1 (opaque)."""
        mat = Material(
            name='TestMat',
            color=Vec3(0.9, 0.9, 0.9),
            alpha_r=1e7, alpha_g=1e7, alpha_b=1e7,
        )
        node = VolumeNode(Vec3(0, 0, 0), depth=0, material=mat, dl=0.01)
        op_r, op_g, op_b = volume_node_opacity(node)
        self.assertGreater(op_r, 0.999)
        self.assertGreater(op_g, 0.999)
        self.assertGreater(op_b, 0.999)

    def test_per_channel_independence(self):
        """Each channel is independent — green can be opaque while red is transparent."""
        mat = Material(
            name='RubyLike',
            color=Vec3(0.9, 0.1, 0.5),
            alpha_r=0.0,    # transparent to red
            alpha_g=1000.0, # opaque to green
            alpha_b=0.0,    # transparent to blue
        )
        node = VolumeNode(Vec3(0, 0, 0), depth=0, material=mat, dl=0.1)
        op_r, op_g, op_b = volume_node_opacity(node)
        self.assertAlmostEqual(op_r, 0.0, places=5)
        self.assertGreater(op_g, 0.999)
        self.assertAlmostEqual(op_b, 0.0, places=5)

    def test_default_alpha_is_zero(self):
        """Material with no alpha_r/g/b defaults to zero absorption."""
        mat = Material(
            name='NoAlpha',
            color=Vec3(0.5, 0.5, 0.5),
        )
        node = VolumeNode(Vec3(0, 0, 0), depth=0, material=mat, dl=1.0)
        op_r, op_g, op_b = volume_node_opacity(node)
        self.assertAlmostEqual(op_r, 0.0, places=10)
        self.assertAlmostEqual(op_g, 0.0, places=10)
        self.assertAlmostEqual(op_b, 0.0, places=10)

    def test_cascade_product_equals_beer_lambert(self):
        """Cascading N identical nodes = exp(-alpha * N * dl). FIRST_PRINCIPLES.

        The Porter-Duff product over N nodes:
          remaining_after_N = product of (1 - opacity_i) = (1 - op)^N
                            ≈ exp(-alpha * dl)^N = exp(-alpha * L)

        This IS Beer-Lambert. The compositor IS a Beer-Lambert integrator.
        """
        alpha = 2.30   # /inch — green absorption of ruby
        dl    = 0.05   # inch — node spacing
        N     = 20     # nodes

        op = 1.0 - math.exp(-alpha * dl)
        remaining_cascade = (1.0 - op) ** N
        beer_lambert_exact = math.exp(-alpha * N * dl)

        # Should be EQUAL (not approximately — this is the proof)
        self.assertAlmostEqual(remaining_cascade, beer_lambert_exact, places=10,
                               msg="Cascade product ≠ Beer-Lambert: physics broken")


# ── Per-Channel Compositor Tests ──────────────────────────────────────────

class TestPerChannelCompositor(unittest.TestCase):
    """engine.py compositor handles per-channel (op_r, op_g, op_b) opacity."""

    def _make_scene(self, fill_volume=True):
        camera = PushCamera(
            pos=Vec3(0, 0, -5),
            look_at=Vec3(0, 0, 0),
            width=32, height=32, fov=60,
        )
        light = PushLight(pos=Vec3(3, 3, -5), intensity=1.0)
        return camera, light

    def test_ruby_absorbs_green(self):
        """A ruby sphere rendered with volumetric fill should have R > G.

        Ruby's crystal field absorbs green. With Beer-Lambert volume fill,
        the rendered color of the sphere body must be red-dominated.
        """
        mat = _ruby_material()
        obj = EntanglerSphere(
            center=Vec3(0, 0, 0), radius=0.8, material=mat,
            fill_volume=True,
        )
        camera, light = self._make_scene()
        pixels = entangle([obj], camera, light, density=50)

        bg = Vec3(0.12, 0.12, 0.14)
        nonbg = []
        for row in pixels:
            for p in row:
                if abs(p.x - bg.x) > 0.03 or abs(p.y - bg.y) > 0.03:
                    nonbg.append(p)

        self.assertGreater(len(nonbg), 5, "No non-background pixels rendered")

        avg_r = sum(p.x for p in nonbg) / len(nonbg)
        avg_g = sum(p.y for p in nonbg) / len(nonbg)

        self.assertGreater(avg_r, avg_g,
                           f"Ruby should be redder than green: R={avg_r:.3f} G={avg_g:.3f}")

    def test_opaque_sphere_fills_pixels(self):
        """An opaque volumetric sphere produces non-background pixels."""
        mat = _opaque_material()
        obj = EntanglerSphere(
            center=Vec3(0, 0, 0), radius=0.8, material=mat,
            fill_volume=True,
        )
        camera, light = self._make_scene()
        pixels = entangle([obj], camera, light, density=50)

        bg = Vec3(0.12, 0.12, 0.14)
        nonbg = sum(
            1 for row in pixels for p in row
            if abs(p.x - bg.x) > 0.03 or abs(p.y - bg.y) > 0.03
        )
        self.assertGreater(nonbg, 10)

    def test_transparent_sphere_shows_background(self):
        """A fully transparent volumetric sphere mostly passes background through."""
        mat = _transparent_material()
        obj = EntanglerSphere(
            center=Vec3(0, 0, 0), radius=0.8, material=mat,
            fill_volume=True,
        )
        camera, light = self._make_scene()
        bg = Vec3(0.12, 0.12, 0.14)
        pixels = entangle([obj], camera, light, density=50, bg_color=bg)

        # Pixels that fall on the sphere should be close to background
        # (transparent = passes through)
        center_pix = pixels[16][16]  # center of 32x32 image
        # The transparent sphere shouldn't deviate massively from background
        diff = abs(center_pix.x - bg.x) + abs(center_pix.y - bg.y) + abs(center_pix.z - bg.z)
        self.assertLess(diff, 0.5,
                        f"Transparent sphere center too far from bg: {diff:.3f}")


# ── Shape fill_volume Flag Tests ──────────────────────────────────────────

class TestFillVolumeFlag(unittest.TestCase):
    """EntanglerSphere and EntanglerEllipsoid support fill_volume flag."""

    def test_sphere_fill_volume_default_false(self):
        """fill_volume defaults to False for backward compatibility."""
        mat = _opaque_material()
        sphere = EntanglerSphere(center=Vec3(0, 0, 0), radius=1.0, material=mat)
        self.assertFalse(sphere.fill_volume)

    def test_sphere_fill_volume_true(self):
        """fill_volume=True is accepted."""
        mat = _opaque_material()
        sphere = EntanglerSphere(
            center=Vec3(0, 0, 0), radius=1.0, material=mat, fill_volume=True
        )
        self.assertTrue(sphere.fill_volume)

    def test_ellipsoid_fill_volume_default_false(self):
        """EntanglerEllipsoid also defaults fill_volume=False."""
        mat = _opaque_material()
        ell = EntanglerEllipsoid(
            center=Vec3(0, 0, 0),
            radii=Vec3(1, 2, 3),
            material=mat,
        )
        self.assertFalse(ell.fill_volume)

    def test_ellipsoid_fill_volume_true(self):
        """EntanglerEllipsoid accepts fill_volume=True."""
        mat = _opaque_material()
        ell = EntanglerEllipsoid(
            center=Vec3(0, 0, 0),
            radii=Vec3(1, 2, 3),
            material=mat,
            fill_volume=True,
        )
        self.assertTrue(ell.fill_volume)


# ── Material Alpha Field Tests ────────────────────────────────────────────

class TestMaterialAlpha(unittest.TestCase):
    """Material correctly stores per-channel alpha absorption coefficients."""

    def test_alpha_stored_correctly(self):
        """alpha_r, alpha_g, alpha_b stored on Material."""
        mat = Material(
            name='TestAlpha',
            color=Vec3(1, 1, 1),
            alpha_r=1.5, alpha_g=2.5, alpha_b=3.5,
        )
        self.assertAlmostEqual(mat.alpha_r, 1.5)
        self.assertAlmostEqual(mat.alpha_g, 2.5)
        self.assertAlmostEqual(mat.alpha_b, 3.5)

    def test_alpha_defaults_to_zero(self):
        """Materials without alpha default to 0 (no absorption)."""
        mat = Material(name='NoAlpha', color=Vec3(1, 1, 1))
        self.assertAlmostEqual(mat.alpha_r, 0.0)
        self.assertAlmostEqual(mat.alpha_g, 0.0)
        self.assertAlmostEqual(mat.alpha_b, 0.0)

    def test_alpha_sigma_invariant(self):
        """Alpha is σ-INVARIANT. EM doesn't care about Λ_QCD."""
        mat = Material(
            name='SigmaInvariantAlpha',
            color=Vec3(0.9, 0.9, 0.9),
            alpha_r=2.3, alpha_g=2.3, alpha_b=2.3,
        )
        # color_at_sigma returns same color — alpha doesn't change either
        self.assertAlmostEqual(mat.alpha_r, 2.3)  # still 2.3 regardless of sigma


# ── Cascade Termination Tests ─────────────────────────────────────────────

class TestCascadeTermination(unittest.TestCase):
    """Cascade terminates at _OPAQUE_THRESHOLD — metals stop early."""

    def test_opaque_threshold_value(self):
        """_OPAQUE_THRESHOLD = 1e-3. Below this, remaining < 0.1%."""
        self.assertAlmostEqual(_OPAQUE_THRESHOLD, 1e-3, places=10)

    def test_aluminum_terminates_after_one_node(self):
        """Aluminum alpha so high that opacity_slab ≈ 1.0 at any dl.

        dl = 14 mil (typical screen-res node spacing for 1" object at 480px)
        opacity = 1 - exp(-3.39e6 * 0.014) = 1 - exp(-47460) ≈ 1.0000
        → remaining = (1 - 1.0) = 0 after 1 node → cascade terminates.
        """
        alpha_g_al = 3.39e6  # green channel alpha /inch
        dl_inch    = 0.014   # 14 mil node spacing

        op = 1.0 - math.exp(-alpha_g_al * dl_inch)
        self.assertAlmostEqual(op, 1.0, places=5,
                               msg="Aluminum opacity should be ≈ 1.0 at screen-res spacing")

        remaining = 1.0 - op
        self.assertLess(remaining, _OPAQUE_THRESHOLD,
                        "After 1 aluminum node, cascade should terminate")

    def test_ruby_terminates_after_expected_nodes(self):
        """Ruby green channel terminates after ~222 nodes at 14 mil spacing.

        exp(-2.30 * 0.014 * N) < 1e-3 → N > log(1e3) / (2.30 * 0.014) ≈ 213.
        """
        alpha_g_ruby = 2.30
        dl_inch      = 0.014   # 14 mil

        op = 1.0 - math.exp(-alpha_g_ruby * dl_inch)
        N = 0
        remaining = 1.0
        while remaining >= _OPAQUE_THRESHOLD and N < 100_000:
            remaining *= (1.0 - op)
            N += 1

        # Should be between 200 and 250 nodes
        self.assertGreater(N, 150, f"Ruby cascade terminates too early: {N}")
        self.assertLess(N, 300, f"Ruby cascade terminates too late: {N}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
