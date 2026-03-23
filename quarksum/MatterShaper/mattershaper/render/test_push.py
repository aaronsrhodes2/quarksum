"""
TDD tests for push renderer — matter projects itself onto pixels.

The architectural shift:
  OLD (pull/ray tracing): camera fires rays → rays find surfaces → pixels colored
  NEW (push/emission):    light activates surface nodes → nodes project to pixels

No Ray objects. No intersection tests. The matter does the drawing.

The benchmark: "We can see the object without a ray tracer."
"""

import unittest
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


class TestSurfaceNodeGeneration(unittest.TestCase):
    """Surface nodes are points on the analytic surface that 'know'
    their position, normal, and material. No mesh — sampled from
    the quadric equation directly."""

    def test_sphere_generates_nodes(self):
        """A sphere should produce surface nodes covering its surface."""
        from mattershaper.render.push import generate_surface_nodes
        from mattershaper.geometry import Sphere, Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(1, 0, 0))
        sphere = Sphere(center=Vec3(0, 0, 0), radius=1.0, material=mat)
        nodes = generate_surface_nodes(sphere, density=100)

        # Should produce nodes
        self.assertGreater(len(nodes), 50)

        # Every node should be on the surface (distance from center = radius)
        for node in nodes:
            dist = node.position.length()
            self.assertAlmostEqual(dist, 1.0, places=3,
                msg=f"Node at {node.position} not on sphere surface")

    def test_node_has_required_attributes(self):
        """Each surface node must have position, normal, material."""
        from mattershaper.render.push import generate_surface_nodes
        from mattershaper.geometry import Sphere, Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(0.5, 0.5, 0.5))
        sphere = Sphere(center=Vec3(0, 0, 0), radius=1.0, material=mat)
        nodes = generate_surface_nodes(sphere, density=10)

        for node in nodes:
            self.assertTrue(hasattr(node, 'position'))
            self.assertTrue(hasattr(node, 'normal'))
            self.assertTrue(hasattr(node, 'material'))

    def test_sphere_normals_point_outward(self):
        """Surface normals should point away from center."""
        from mattershaper.render.push import generate_surface_nodes
        from mattershaper.geometry import Sphere, Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(1, 1, 1))
        sphere = Sphere(center=Vec3(0, 0, 0), radius=1.0, material=mat)
        nodes = generate_surface_nodes(sphere, density=50)

        for node in nodes:
            # Normal should equal normalized position for origin-centered sphere
            dot = node.normal.dot(node.position.normalized())
            self.assertGreater(dot, 0.99,
                f"Normal not pointing outward at {node.position}")

    def test_ellipsoid_generates_nodes(self):
        """Ellipsoids should produce surface nodes too."""
        from mattershaper.render.push import generate_surface_nodes
        from mattershaper.geometry import Ellipsoid, Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(0, 1, 0))
        ell = Ellipsoid(center=Vec3(0, 0, 0), radii=Vec3(2, 1, 1), material=mat)
        nodes = generate_surface_nodes(ell, density=100)

        self.assertGreater(len(nodes), 50)

        # Every node should satisfy the ellipsoid equation: (x/a)²+(y/b)²+(z/c)²=1
        for node in nodes:
            p = node.position
            val = (p.x/2.0)**2 + (p.y/1.0)**2 + (p.z/1.0)**2
            self.assertAlmostEqual(val, 1.0, places=2,
                msg=f"Node not on ellipsoid surface: val={val}")

    def test_density_controls_node_count(self):
        """Higher density = more surface nodes."""
        from mattershaper.render.push import generate_surface_nodes
        from mattershaper.geometry import Sphere, Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(1, 1, 1))
        sphere = Sphere(center=Vec3(0, 0, 0), radius=1.0, material=mat)
        low = generate_surface_nodes(sphere, density=50)
        high = generate_surface_nodes(sphere, density=200)

        self.assertGreater(len(high), len(low))


class TestProjection(unittest.TestCase):
    """Surface nodes project themselves onto the pixel grid.
    Pure perspective math — no rays involved."""

    def test_node_projects_to_pixel(self):
        """A node in front of the camera should map to a valid pixel."""
        from mattershaper.render.push import project_node, PushCamera
        from mattershaper.geometry import Vec3

        cam = PushCamera(
            pos=Vec3(0, 0, 5),
            look_at=Vec3(0, 0, 0),
            width=400, height=300,
            fov=60,
        )
        # A point at the origin should project near center of image
        px, py = project_node(Vec3(0, 0, 0), cam)
        self.assertAlmostEqual(px, 200, delta=5)
        self.assertAlmostEqual(py, 150, delta=5)

    def test_behind_camera_returns_none(self):
        """Nodes behind the camera should not project."""
        from mattershaper.render.push import project_node, PushCamera
        from mattershaper.geometry import Vec3

        cam = PushCamera(
            pos=Vec3(0, 0, 5),
            look_at=Vec3(0, 0, 0),
            width=400, height=300,
            fov=60,
        )
        # Point behind the camera
        result = project_node(Vec3(0, 0, 10), cam)
        self.assertIsNone(result)

    def test_off_screen_returns_none(self):
        """Nodes projecting outside the frame should return None."""
        from mattershaper.render.push import project_node, PushCamera
        from mattershaper.geometry import Vec3

        cam = PushCamera(
            pos=Vec3(0, 0, 5),
            look_at=Vec3(0, 0, 0),
            width=400, height=300,
            fov=60,
        )
        # Far off to the side
        result = project_node(Vec3(100, 0, 0), cam)
        self.assertIsNone(result)


class TestIllumination(unittest.TestCase):
    """Light source activates surface nodes. The node computes its
    own response from its material properties and surface normal."""

    def test_facing_light_is_bright(self):
        """Node facing the light source should be brightly lit."""
        from mattershaper.render.push import illuminate_node, SurfaceNode, PushLight
        from mattershaper.geometry import Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(1, 1, 1))
        node = SurfaceNode(
            position=Vec3(0, 0, 0),
            normal=Vec3(0, 0, 1),  # facing +z
            material=mat,
        )
        light = PushLight(pos=Vec3(0, 0, 5), intensity=1.0)
        color = illuminate_node(node, light)
        # Should be bright (high luminance)
        luminance = 0.299 * color.x + 0.587 * color.y + 0.114 * color.z
        self.assertGreater(luminance, 0.5)

    def test_facing_away_is_dark(self):
        """Node facing away from light should be dark."""
        from mattershaper.render.push import illuminate_node, SurfaceNode, PushLight
        from mattershaper.geometry import Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(1, 1, 1))
        node = SurfaceNode(
            position=Vec3(0, 0, 0),
            normal=Vec3(0, 0, -1),  # facing away from light
            material=mat,
        )
        light = PushLight(pos=Vec3(0, 0, 5), intensity=1.0)
        color = illuminate_node(node, light)
        luminance = 0.299 * color.x + 0.587 * color.y + 0.114 * color.z
        self.assertLess(luminance, 0.15)

    def test_color_reflects_material(self):
        """Node color should reflect its material color."""
        from mattershaper.render.push import illuminate_node, SurfaceNode, PushLight
        from mattershaper.geometry import Vec3
        from mattershaper.materials import Material

        mat = Material(name='red', color=Vec3(1, 0, 0))
        node = SurfaceNode(
            position=Vec3(0, 0, 0),
            normal=Vec3(0, 0, 1),
            material=mat,
        )
        light = PushLight(pos=Vec3(0, 0, 5), intensity=1.0)
        color = illuminate_node(node, light)
        # Red channel should dominate
        self.assertGreater(color.x, color.y)
        self.assertGreater(color.x, color.z)


class TestPushRender(unittest.TestCase):
    """End-to-end: scene with objects + light → pixel buffer.
    No ray tracer anywhere in the pipeline."""

    def test_sphere_produces_image(self):
        """A single sphere + light should produce non-empty image."""
        from mattershaper.render.push import push_render, PushCamera, PushLight
        from mattershaper.geometry import Sphere, Vec3
        from mattershaper.materials import Material

        mat = Material(name='test', color=Vec3(0.8, 0.2, 0.1))
        sphere = Sphere(center=Vec3(0, 0, 0), radius=1.0, material=mat)

        cam = PushCamera(
            pos=Vec3(0, 0, 4),
            look_at=Vec3(0, 0, 0),
            width=100, height=100,
            fov=60,
        )
        light = PushLight(pos=Vec3(3, 3, 5), intensity=1.0)
        pixels = push_render([sphere], cam, light, density=200)

        # Pixels should be a 2D list of Vec3 colors
        self.assertEqual(len(pixels), 100)
        self.assertEqual(len(pixels[0]), 100)

        # Not all black — something was rendered
        total_lum = 0
        for row in pixels:
            for p in row:
                total_lum += p.x + p.y + p.z
        self.assertGreater(total_lum, 0, "Image is entirely black")

    def test_no_ray_objects_used(self):
        """The push renderer must not import or use Ray or Hit."""
        import mattershaper.render.push as push_module
        source = open(push_module.__file__).read()
        # Should not import Ray or Hit
        self.assertNotIn('from .raytracer', source)
        self.assertNotIn('import Ray', source)
        self.assertNotIn('Ray(', source)
        self.assertNotIn('Hit(', source)
        # Should not call .intersect()
        self.assertNotIn('.intersect(', source)


class TestDepthBuffer(unittest.TestCase):
    """When multiple nodes project to the same pixel,
    the closest one wins (depth buffering)."""

    def test_closer_node_occludes_farther(self):
        """Front sphere should hide back sphere at overlapping pixels."""
        from mattershaper.render.push import push_render, PushCamera, PushLight
        from mattershaper.geometry import Sphere, Vec3
        from mattershaper.materials import Material

        red = Material(name='red', color=Vec3(1, 0, 0))
        blue = Material(name='blue', color=Vec3(0, 0, 1))

        front = Sphere(center=Vec3(0, 0, 1), radius=0.5, material=red)
        back = Sphere(center=Vec3(0, 0, -1), radius=0.5, material=blue)

        cam = PushCamera(
            pos=Vec3(0, 0, 5),
            look_at=Vec3(0, 0, 0),
            width=100, height=100,
            fov=60,
        )
        light = PushLight(pos=Vec3(3, 3, 5), intensity=1.0)
        pixels = push_render([front, back], cam, light, density=500)

        # Center pixel should be red (front sphere), not blue
        cx, cy = 50, 50
        center_pixel = pixels[cy][cx]
        if center_pixel.x + center_pixel.y + center_pixel.z > 0.01:
            self.assertGreater(center_pixel.x, center_pixel.z,
                "Red (front) should dominate over blue (back) at center")


if __name__ == '__main__':
    unittest.main()
