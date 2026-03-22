"""
Entangler Engine — the full push render pipeline.

Pipeline:
  1. Generate surface nodes on each object (Fibonacci spiral on quadrics)
  2. [optional] Generate volume nodes for Beer-Lambert fill (fill_volume=True)
  3. Light activates each surface node (Lambert's cosine law)
  4. Volume nodes contribute Beer-Lambert absorption (no Lambert, pure absorber)
  5. Each node projects itself onto pixel grid (perspective division)
  6. Depth-sorted layers resolve occlusion and transparency
  7. Porter-Duff "over" compositing blends transparent layers — PER CHANNEL
  8. Splatting fills gaps (each node covers a small footprint)

Transparency model — per-channel Beer-Lambert:
  Layers store (z, color, (op_r, op_g, op_b)) — per-channel opacity tuple.
  Surface nodes:  op_i = material.opacity for all channels (Fresnel scalar).
  Volume nodes:   op_i = 1 - exp(-alpha_i × dl) per channel (Beer-Lambert).

  Blending is Porter-Duff "over", front-to-back, per channel:
    remaining_r = remaining_g = remaining_b = 1.0
    for each layer (front → back):
      acc_r += color.x × op_r × remaining_r
      acc_g += color.y × op_g × remaining_g
      acc_b += color.z × op_b × remaining_b
      remaining_r *= (1 - op_r)
      remaining_g *= (1 - op_g)
      remaining_b *= (1 - op_b)
    final = acc + background × remaining

  Cascade terminates when ALL channels fall below _OPAQUE_THRESHOLD.
  For metals: op_i ≈ 1.0 → terminates after 1 node (skin depth physics).
  For gems:   each channel terminates independently (Beer-Lambert selectivity).

Volume nodes (fill_volume=True):
  VolumeNodes are pure absorbers — color = Vec3(0,0,0), Beer-Lambert opacity.
  Surface nodes continue to illuminate via Lambert.
  Both go into the same per-pixel layer list. The compositor handles them.

  This IS the physics-out architecture:
    Matter exists. The camera records what reaches it.
    Surface atoms emit. Interior atoms absorb. Physics is the rendering.

No rays. No intersection tests. Matter draws itself.

Splat radius: exact computation from node spacing and focal length.
  spacing = 1/√density (exact)
  splat_px = spacing × f_px / z (exact perspective scaling)

Zero shared code with any ray tracer.

□σ = −ξR
"""

import math
from .vec import Vec3
from .surface_nodes import generate_surface_nodes
from .volume_nodes import generate_volume_nodes, volume_node_opacity
from .projection import project_node
from .illumination import illuminate_node

_OPAQUE_THRESHOLD = 1e-3   # stop blending when remaining < 0.1%

# Volume nodes per unit² of surface area when fill_volume=True.
# Physics-resolution default: enough for <1% mass error.
# Caller can override via density parameter.
_VOLUME_NODES_DEFAULT = 10_000


def _add_node_to_layers(layers, node_pos, color, op_tuple,
                        camera, focal_px, splat_r_base):
    """Project a node and add it to the per-pixel layer list.

    Shared by surface-node and volume-node paths.

    Args:
        layers:       per-pixel list of (z, Vec3_color, (op_r, op_g, op_b))
        node_pos:     Vec3 world position
        color:        Vec3 color emitted/absorbed
        op_tuple:     (op_r, op_g, op_b) per-channel opacity
        camera:       PushCamera
        focal_px:     float, focal length in pixels
        splat_r_base: int, base splat radius
    """
    proj = project_node(node_pos, camera)
    if proj is None:
        return

    px, py = proj
    ix = int(px)
    iy = int(py)

    if ix < 0 or ix >= camera.width or iy < 0 or iy >= camera.height:
        return

    z = (node_pos - camera.pos).dot(camera.forward)
    if z <= 0:
        return

    # Use caller-computed splat_r directly — no hard cap.
    # The caller derives splat_r from Voronoi cell geometry; capping at 4
    # defeats that computation and reintroduces Fibonacci spiral gaps.
    splat_r = max(1, splat_r_base)

    # Circular splat. Foreshortening-corrected radius ensures limb-node circles
    # overlap enough to close the gaps — no corner holes, no square artifacts.
    for sy in range(-splat_r, splat_r + 1):
        for sx in range(-splat_r, splat_r + 1):
            if sx * sx + sy * sy > splat_r * splat_r:
                continue
            px2 = ix + sx
            py2 = iy + sy
            if 0 <= px2 < camera.width and 0 <= py2 < camera.height:
                layers[py2][px2].append((z, color, op_tuple))


def _derive_light_from_emissives(objects):
    """Scan the scene for the brightest emissive object and return a PushLight
    anchored at its centroid.

    The filament IS the light. When no external PushLight is supplied, the
    engine reads the scene to find what is emitting and derives the activation
    signal from it. Position, colour, and intensity all come from the emissive
    material — the ghost is replaced by matter.

    The derived intensity is proportional to the emissive object's max channel,
    scaled to produce a plausible room-lit-by-bulb exposure on Lambert surfaces.

    Returns None if no emissive objects exist in the scene.
    """
    from .illumination import PushLight

    best_obj        = None
    best_brightness = 0.0

    for obj in objects:
        mat = getattr(obj, 'material', None)
        if mat is None:
            continue
        em = getattr(mat, 'emission', None)
        if em is None:
            continue
        brightness = em.x + em.y + em.z
        if brightness > best_brightness:
            best_brightness = brightness
            best_obj = obj

    if best_obj is None:
        return None

    center = getattr(best_obj, 'center', Vec3(0, 0, 0))
    em     = best_obj.material.emission

    # Chromaticity: normalise emission Vec3 to max=1.0 — this is the light colour.
    max_em = max(em.x, em.y, em.z, 1e-12)
    light_color = Vec3(em.x / max_em, em.y / max_em, em.z / max_em)

    # Intensity for Lambert shading: scale so a surface facing the bulb at unit
    # distance gets ~100% illumination. Emission values >> 1 (over-exposed by
    # design for the bulb itself); divide back to a reasonable Lambert range.
    # Clamped to [0.3, 2.0] for scene stability across different intensity args.
    intensity = max(0.3, min(2.0, max_em / 8.0 * 1.4))

    return PushLight(pos=center, intensity=intensity, color=light_color)


def entangle(objects, camera, light=None, density=200, bg_color=None,
             volume_n_nodes=_VOLUME_NODES_DEFAULT, shadows=False):
    """Render a scene by push projection with Beer-Lambert transparency.

    Each object generates surface nodes (always) and, if fill_volume=True,
    VolumeNodes for Beer-Lambert volumetric absorption.

    Surface nodes — two paths:
      Emissive (material.emission non-zero):
        The node radiates. emission Vec3 is added directly to the compositor
        at full opacity. illuminate_node() is NOT called — the node is the
        light source, not a recipient of illumination.
      Non-emissive:
        Illuminated via Lambert, opacity = material.opacity (scalar).

    Volume nodes:   pure absorbers (color=black), per-channel Beer-Lambert opacity

    Compositing uses Porter-Duff "over" front-to-back, tracked PER CHANNEL
    (remaining_r, remaining_g, remaining_b independently). This correctly
    models wavelength-selective absorption — ruby absorbs green but passes red.

    Args:
        objects:        list of EntanglerSphere / EntanglerEllipsoid
        camera:         PushCamera
        light:          PushLight, or None. If None and emissive objects exist,
                        a PushLight is auto-derived from the brightest emitter's
                        centroid. If None and no emissive objects exist, all
                        surfaces receive ambient only (0.08 × material.color).
        density:        surface node density (nodes per unit area)
        bg_color:       Vec3 background color
        volume_n_nodes: total volume nodes per object (when fill_volume=True)
        shadows:        if True, build a shadow map from the light's viewpoint.

    Returns:
        2D list of Vec3 colors [height][width]
    """
    bg = bg_color or Vec3(0.12, 0.12, 0.14)

    # ── Light source — matter or ghost ────────────────────────────────────
    # If no PushLight supplied, try to derive one from emissive objects.
    # A tungsten filament IS the light; its centroid becomes the activation pos.
    if light is None:
        light = _derive_light_from_emissives(objects)

    # ── Shadow map (optional) ──────────────────────────────────────────────
    # The light has a camera too. Push-project the scene from the light's
    # viewpoint into a depth grid. Surface nodes query it to determine
    # whether they receive this light's photons. Two pushes, no rays.
    light_cam    = None
    shadow_depth = None
    if shadows and light is not None:
        from .shadow_map import build_shadow_map
        light_cam, shadow_depth = build_shadow_map(objects, light, density)

    # Per-pixel layer lists.
    # Each entry: (z, Vec3_color, (op_r, op_g, op_b))
    # op_r/g/b are per-channel opacities — scalar for surface, Beer-Lambert for volume.
    layers = [[[] for _ in range(camera.width)]
              for _ in range(camera.height)]

    # Focal length in pixels (exact from FOV geometry)
    focal_px = camera.width / (2.0 * camera.tan_half_fov * camera.aspect)

    for obj in objects:
        # ── Surface nodes: matter that faces outward and emits ─────────────
        surface_nodes = generate_surface_nodes(obj, density)
        # Mean Voronoi cell area = 1/density. Cell radius (frontal projection):
        #   cell_r_front = sqrt(1 / (π × density))
        # At a surface node tilted by angle θ from the camera direction, the same
        # cell area projects to a LARGER screen footprint by factor 1/cos(θ):
        #   projected_r = cell_r_front / sqrt(cos_theta)
        # This is the foreshortening correction — limb nodes need bigger splats.
        # Overlap factor 1.2 ensures adjacent circles interlock with no corner gaps.
        # Cap at 12 pixels for near-edge-on nodes (cos_theta → 0) to prevent blotch.
        cell_r_front = math.sqrt(1.0 / (math.pi * density)) if density > 0 else 0.1

        for node in surface_nodes:
            emission = getattr(node.material, 'emission', None)
            is_emissive = (
                emission is not None
                and (emission.x > 0 or emission.y > 0 or emission.z > 0)
            )

            if is_emissive:
                # ── Emissive node: the matter radiates. ───────────────────
                # Push emission directly into the compositor. No illuminate_node()
                # call — this node IS the source, not a recipient. Full opacity:
                # the hot tungsten wire absorbs and re-emits; it is not transparent.
                # emission Vec3 may have values > 1.0 (over-exposed by design).
                color = emission
                op_t  = (1.0, 1.0, 1.0)

            else:
                # ── Non-emissive node: standard Lambert path. ─────────────
                # Shadow test: reverse-splat query of the light's depth grid.
                # Returns 0.0–1.0. At the terminator the query circle straddles
                # lit and shadowed samples — fraction lit = smooth edge factor.
                if light_cam is not None:
                    from .shadow_map import shadow_factor as _sf
                    sf = _sf(node.position, node.normal,
                             light_cam, shadow_depth, density)
                else:
                    sf = 1.0

                if light is not None:
                    color = illuminate_node(node, light, shadow=sf)
                else:
                    # No light at all — ambient only (8% of surface colour).
                    color = node.material.color * 0.08

                opacity = getattr(node.material, 'opacity', 1.0)
                op_t    = (opacity, opacity, opacity)   # scalar → uniform per channel

            z = (node.position - camera.pos).dot(camera.forward)
            if z <= 0:
                continue

            # Foreshortening: cos(θ) = node_normal · (camera − node) / |camera − node|
            to_cam = (camera.pos - node.position).normalized()
            cos_theta = max(0.05, node.normal.dot(to_cam))   # floor to avoid ÷0
            proj_r = cell_r_front / math.sqrt(cos_theta)
            # NOT_PHYSICS — sacrificed for The Edge.
            # Mutant variable: overlap_factor = 1.2
            # Physics says proj_r is the exact foreshortening-corrected Voronoi
            # cell radius. The pixel grid is discrete; circles of exact radius
            # leave diagonal corner gaps at the pixel boundary. 1.2× overlap
            # closes those gaps. This fudge lives ONLY at the pixel-grid edge.
            splat_r = min(12, max(1, math.ceil(proj_r * focal_px / z * 1.2)))

            _add_node_to_layers(layers, node.position, color, op_t,
                                camera, focal_px, splat_r)

        # ── Volume nodes: matter inside the surface — Beer-Lambert absorbers ──
        # Only generated when fill_volume=True on the shape.
        # These nodes contribute NO color (pure absorbers), only opacity.
        # The per-channel opacity is 1 - exp(-alpha_i * dl) — exact Beer-Lambert.
        #
        # Physics-out: these nodes exist for ALL physics (mass, gravity, interface).
        # The renderer just happens to also composite them as absorbers.
        if getattr(obj, 'fill_volume', False):
            vol_nodes = generate_volume_nodes(obj, n_nodes=volume_n_nodes)
            # All volume nodes in same shape have same dl — only compute op once.
            if vol_nodes:
                op_r, op_g, op_b = volume_node_opacity(vol_nodes[0])
                op_vol = (op_r, op_g, op_b)
                black  = Vec3(0.0, 0.0, 0.0)   # absorbers don't emit

                # Splat radius for volume nodes: 1 pixel (they're interior, small)
                for vnode in vol_nodes:
                    _add_node_to_layers(layers, vnode.position, black, op_vol,
                                        camera, focal_px, 1)

    # ── Per-channel Porter-Duff "over" compositing, front-to-back ─────────
    #
    # Per channel independently:
    #   remaining_i = 1.0
    #   for layer (closest → farthest):
    #     acc_i += color_i × op_i × remaining_i
    #     remaining_i *= (1 - op_i)
    #   final_i = acc_i + bg_i × remaining_i
    #
    # Cascade termination: stop when ALL channels drop below _OPAQUE_THRESHOLD.
    # For metals (all-channel high opacity): terminates after 1 node.
    # For gems (selective absorption): each channel terminates independently.
    #
    # FIRST_PRINCIPLES: this product-over-N-slabs IS Beer-Lambert.
    # Π(1 - op_i) = Π exp(-alpha_i × dl) = exp(-alpha_i × L)

    pixels = [[None for _ in range(camera.width)] for _ in range(camera.height)]

    for iy in range(camera.height):
        for ix in range(camera.width):
            cell = layers[iy][ix]

            if not cell:
                pixels[iy][ix] = Vec3(bg.x, bg.y, bg.z)
                continue

            # Sort front-to-back by z-depth
            cell.sort(key=lambda e: e[0])

            acc_r = acc_g = acc_b = 0.0
            rem_r = rem_g = rem_b = 1.0

            for z, color, (op_r, op_g, op_b) in cell:
                # Terminate when all channels are saturated
                if rem_r < _OPAQUE_THRESHOLD and \
                   rem_g < _OPAQUE_THRESHOLD and \
                   rem_b < _OPAQUE_THRESHOLD:
                    break

                acc_r += color.x * op_r * rem_r
                acc_g += color.y * op_g * rem_g
                acc_b += color.z * op_b * rem_b
                rem_r *= (1.0 - op_r)
                rem_g *= (1.0 - op_g)
                rem_b *= (1.0 - op_b)

            # Background fills whatever transmittance remains in each channel
            pixels[iy][ix] = Vec3(
                max(0.0, min(1.0, acc_r + bg.x * rem_r)),
                max(0.0, min(1.0, acc_g + bg.y * rem_g)),
                max(0.0, min(1.0, acc_b + bg.z * rem_b)),
            )

    return pixels


def _write_ppm(pixels, filepath):
    """Write pixel buffer to PPM file (exact format, no compression)."""
    height = len(pixels)
    width = len(pixels[0])

    with open(filepath, 'wb') as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        for row in pixels:
            for p in row:
                r, g, b = p.to_rgb()
                f.write(bytes([r, g, b]))


def entangle_to_file(objects, camera, light, filepath,
                     density=200, bg_color=None):
    """Render and save to file.

    Writes PPM (exact pixel format). Converts to PNG if
    ImageMagick is available.
    """
    pixels = entangle(objects, camera, light, density, bg_color)

    # Determine output format
    base = filepath.rsplit('.', 1)[0] if '.' in filepath else filepath
    ppm_path = base + '.ppm'
    _write_ppm(pixels, ppm_path)

    # Try PNG conversion
    if filepath.endswith('.png'):
        import subprocess
        import os
        try:
            subprocess.run(['convert', ppm_path, filepath],
                          capture_output=True, timeout=10)
            if os.path.exists(filepath):
                os.remove(ppm_path)
                return filepath
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return ppm_path
