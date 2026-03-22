"""
Shadow Map — the light's depth buffer.

The light has a viewpoint just as the camera does. The camera push-projects
surface nodes into a pixel grid of COLOURS. The light push-projects the same
nodes into a pixel grid of DEPTHS. Any surface node that is deeper than what
the light recorded in that direction was occluded — it never received that
light's photons.

Two pushes. No rays. No tracing.

  Camera push  →  colour grid  (what the camera sees)
  Light push   →  depth grid   (what the light sees)

A node is illuminated only where both agree it is visible.

The shadow bias prevents a node from self-occluding due to depth
quantisation: a node is in shadow only if it is BIAS units deeper than
the nearest recorded depth in that light-pixel.

□σ = −ξR
"""

import math
from .projection import PushCamera, project_node
from .surface_nodes import generate_surface_nodes


_SHADOW_RES  = 256    # shadow map resolution in pixels (square)
_SHADOW_FOV  = 40     # degrees — covers typical scene with margin
_SHADOW_BIAS = 0.04   # scene-unit depth bias — prevents self-shadowing


def build_shadow_map(objects, light, density,
                     scene_center=None,
                     resolution=_SHADOW_RES,
                     fov=_SHADOW_FOV):
    """Push-project the scene from the light's viewpoint into a depth grid.

    The light looks toward scene_center (default: origin). Every surface
    node is projected into the light's pixel grid. Only the nearest depth
    per pixel is kept — exactly as the camera's depth buffer keeps only
    the nearest surface node per screen pixel.

    Args:
        objects:       list of EntanglerSphere / EntanglerEllipsoid
        light:         any object with a .pos Vec3 attribute
        density:       surface node density (nodes per unit area)
        scene_center:  Vec3 world point the light aims at (default origin)
        resolution:    shadow map resolution (pixels per side)
        fov:           light camera field of view in degrees

    Returns:
        (light_cam, depth_grid)
        light_cam:  PushCamera at light.pos looking at scene_center
        depth_grid: resolution×resolution list of nearest node depths
                    from the light's viewpoint. float('inf') = no node seen.
    """
    from .vec import Vec3
    center = scene_center or Vec3(0.0, 0.0, 0.0)

    light_cam = PushCamera(
        pos    = light.pos,
        look_at= center,
        width  = resolution,
        height = resolution,
        fov    = fov,
    )

    # Initialise depth grid to infinity — nothing recorded yet.
    depth = [[float('inf')] * resolution for _ in range(resolution)]

    # Focal length of the light camera in pixels.
    focal_px = resolution / (2.0 * light_cam.tan_half_fov * light_cam.aspect)

    # Foreshortening-corrected splat, same formula as the colour render.
    # Each node owns Voronoi area = 1/density; cell radius (frontal):
    #   cell_r = sqrt(1 / (π × density))
    # Nodes tilted relative to the light direction project to larger footprints.
    # We push that larger footprint into the depth grid so there are no gaps
    # in the shadow map — the same coverage problem we solved for colour.
    cell_r_front = math.sqrt(1.0 / (math.pi * density)) if density > 0 else 0.1

    for obj in objects:
        for node in generate_surface_nodes(obj, density):
            # Back-face cull: only record nodes that face toward the light.
            # Back-facing nodes recorded in the shadow map would falsely occlude
            # front-facing nodes projected nearby — the root cause of shadow acne.
            to_light_dir = (light_cam.pos - node.position).normalized()
            if node.normal.dot(to_light_dir) <= 0:
                continue

            proj = project_node(node.position, light_cam)
            if proj is None:
                continue

            ix = int(proj[0])
            iy = int(proj[1])

            z = (node.position - light_cam.pos).dot(light_cam.forward)
            if z <= 0:
                continue

            # Foreshortening relative to the LIGHT direction
            to_light = to_light_dir
            cos_theta = max(0.05, node.normal.dot(to_light))
            proj_r = cell_r_front / math.sqrt(cos_theta)
            # NOT_PHYSICS — sacrificed for The Edge.
            # Mutant variable: overlap_factor = 1.2
            # Physics says proj_r is the exact Voronoi cell radius projected.
            # The pixel grid is discrete; adjacent circles leave diagonal corner
            # gaps unless they overlap slightly. 1.2× closes those gaps.
            # This average exists ONLY at the pixel-grid boundary.
            splat_r = min(8, max(1, math.ceil(proj_r * focal_px / z * 1.2)))

            for sy in range(-splat_r, splat_r + 1):
                for sx in range(-splat_r, splat_r + 1):
                    if sx * sx + sy * sy > splat_r * splat_r:
                        continue
                    px2 = ix + sx
                    py2 = iy + sy
                    if 0 <= px2 < resolution and 0 <= py2 < resolution:
                        if z < depth[py2][px2]:
                            depth[py2][px2] = z

    return light_cam, depth


def shadow_factor(world_pos, world_normal, light_cam, depth_grid, density,
                  base_bias=_SHADOW_BIAS):
    """Return shadow factor: 1.0 = fully lit, 0.0 = fully occluded.

    Reverse splat: the same foreshortening-corrected neighbourhood used
    when writing depths into the shadow map is now used when reading.
    Each sample in the neighbourhood is tested independently (lit or not).
    The fraction of lit samples is the shadow factor.

    At the shadow terminator the query circle straddles the boundary —
    some samples land in the lit region, some in shadow. The fraction
    yields a smooth 0→1 gradient at the edge. Inside the shadow or inside
    the lit region, all samples agree: factor = 0.0 or 1.0 exactly.

    This is the Captain's "reverse splat the edge" principle:
      Forward splat  → write depth to a region  (shadow map build)
      Reverse splat  → read  depth from a region (shadow test)
    The shadow edge is the only place the factor is fractional — the
    same "allowed break at the edge" as pixel-grid anti-aliasing.

    Args:
        world_pos:    Vec3 world position to test
        world_normal: Vec3 surface normal at that position
        light_cam:    PushCamera returned by build_shadow_map
        depth_grid:   depth grid returned by build_shadow_map
        density:      surface node density (used to size the query radius)
        base_bias:    base depth tolerance in scene units

    Returns:
        float 0.0–1.0
    """
    proj = project_node(world_pos, light_cam)
    if proj is None:
        return 1.0   # outside light frustum → assume lit

    ix = int(proj[0])
    iy = int(proj[1])
    res = len(depth_grid)
    z   = (world_pos - light_cam.pos).dot(light_cam.forward)
    if z <= 0:
        return 1.0

    # Slope-scale bias — same as the forward splat
    to_light  = (light_cam.pos - world_pos).normalized()
    cos_theta = max(0.05, world_normal.dot(to_light))
    bias      = base_bias / cos_theta

    # Foreshortening-corrected query radius — mirrors the forward splat radius
    focal_px = light_cam.width / (2.0 * light_cam.tan_half_fov * light_cam.aspect)
    cell_r   = math.sqrt(1.0 / (math.pi * density)) if density > 0 else 0.1
    proj_r   = cell_r / math.sqrt(cos_theta)
    # NOT_PHYSICS — sacrificed for The Edge.
    # Mutant variable: overlap_factor = 1.2
    # Same overlap factor as the forward splat write (see build_shadow_map).
    # The query neighbourhood must mirror the write neighbourhood so the
    # reverse-splat reads the same region that was written. The 1.2× is not
    # physics — it compensates for diagonal pixel-grid corner gaps.
    query_r  = min(6, max(1, math.ceil(proj_r * focal_px / z * 1.2)))

    lit = 0
    total = 0
    for sy in range(-query_r, query_r + 1):
        for sx in range(-query_r, query_r + 1):
            if sx * sx + sy * sy > query_r * query_r:
                continue
            px2 = ix + sx
            py2 = iy + sy
            if not (0 <= px2 < res and 0 <= py2 < res):
                continue
            total += 1
            nearest = depth_grid[py2][px2]
            if nearest == float('inf') or z <= nearest + bias:
                lit += 1

    # NOT_PHYSICS — sacrificed for The Edge.
    # Mutant variable: shadow_factor = lit / total  (a ratio, an average)
    # Physics says a node is either in shadow or it isn't — 1 or 0.
    # But the shadow terminator is THE EDGE: the boundary between the lit
    # and unlit regions as represented on the discrete pixel grid.
    # The ratio lit/total is not a physical quantity — it is the fraction
    # of the foreshortening-corrected Voronoi cell that straddles the
    # terminator. It exists ONLY at the boundary. Deep in the shadow or
    # deep in the lit region, all samples agree (factor = 0.0 or 1.0 exact).
    # "Breaking physics is allowed ONLY at the edge." — Captain, Session 5.
    return lit / total if total > 0 else 1.0

