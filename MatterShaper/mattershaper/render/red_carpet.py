"""
red_carpet_render — Orbital animation pipeline for the Entangler.

The red carpet treatment: a full horizontal rotation rendered as an
animated GIF, with per-frame time-elapsed annotation baked in.

    "The image format incorporates time." — Captain Aaron Rhodes

Two-act structure (when counter_rotate=True):
  ACT I  — Camera orbits 360°. Model stands still. Classic red carpet.
  ACT II — Camera orbits 360° again. Model counter-rotates in the opposite
            direction at counter_rotate_ratio of camera speed. At ratio=1.0,
            the observer and the observed accumulate 720° of relative angle —
            a double-parallax pass. At ratio=0.5 (default), the model drifts
            180° against the camera's 360°, giving a slow-burn reveal of
            geometry that the first pass occluded.

Usage:
    from mattershaper.render.red_carpet import red_carpet_render

    red_carpet_render(
        objects=objects,
        light=light,
        output_gif='/path/to/output.gif',
        n_frames=16,
        density=420,
        width=400, height=500,
        fov=47,
        cam_dist=7.4, cam_height=3.55,
        look_at=Vec3(0, 2.1, 0),
        start_angle=-0.26,
        fps=10,
        bg_color=Vec3(0.82, 0.84, 0.88),
        title='SKIPPY THE MAGNIFICENT',
        counter_rotate=True,
        counter_rotate_ratio=0.5,
    )

Pipeline:
  1. For each frame i in [0, n_frames):
       a. Compute orbital camera angle = start_angle + (2π * i / n_frames)
       b. Render frame via entangle() → 2D pixel array
       c. Write PPM → annotate with ImageMagick → PNG
  2. (counter_rotate=True) For each frame i in [0, n_frames):
       a. Same camera orbit as above
       b. Rotate objects −(counter_rotate_ratio × 2π × i / n_frames) around Y
       c. Render, annotate with "PARALLAX" pass label
  3. Assemble all PNGs into GIF with -layers Optimize and -dither Riemersma

The light stays fixed in world space across both passes.
"""

import os
import math
import time
import subprocess
import tempfile

from .entangler.engine import entangle, _write_ppm
from .entangler.projection import PushCamera
from .entangler.vec import Vec3
from .entangler.shapes import (
    EntanglerSphere, EntanglerEllipsoid,
    _rot_y, _mat_mul, _apply_mat,
)


# ── Object rotation helper ─────────────────────────────────────────────────

def _rotate_objects_y(objects, angle_rad, pivot):
    """Return a new object list with all centers rotated angle_rad around
    the Y-axis at *pivot*. Ellipsoid orientation matrices are also rotated.

    Objects of unknown shape_type are passed through unchanged.
    """
    R = _rot_y(angle_rad)
    rotated = []
    for obj in objects:
        # Translate to pivot-relative frame, rotate, translate back
        v = Vec3(obj.center.x - pivot.x,
                 obj.center.y - pivot.y,
                 obj.center.z - pivot.z)
        rv = _apply_mat(R, v)
        new_center = Vec3(pivot.x + rv.x, pivot.y + rv.y, pivot.z + rv.z)

        if obj.shape_type == 'sphere':
            rotated.append(EntanglerSphere(
                center=new_center,
                radius=obj.radius,
                material=obj.material,
            ))
        elif obj.shape_type == 'ellipsoid':
            rotated.append(EntanglerEllipsoid(
                center=new_center,
                radii=obj.radii,
                rotation=_mat_mul(R, obj.rotation),
                material=obj.material,
            ))
        else:
            rotated.append(obj)   # unknown type — pass through

    return rotated


# ── Main pipeline ──────────────────────────────────────────────────────────

def red_carpet_render(
    objects,
    light,
    output_gif,
    *,
    n_frames=16,
    density=420,
    width=400,
    height=500,
    fov=47,
    cam_dist=7.4,
    cam_height=3.55,
    look_at=None,
    start_angle=-0.26,
    fps=10,
    bg_color=None,
    title='ENTANGLER',
    counter_rotate=True,
    counter_rotate_ratio=0.5,
    verbose=True,
):
    """Render a full 360° orbital animation as an animated GIF.

    Parameters
    ----------
    objects : list
        EntanglerSphere / EntanglerEllipsoid primitives.
    light : PushLight
        World-space light (stays fixed while camera orbits).
    output_gif : str
        Path for the output .gif file.
    n_frames : int
        Number of frames per 360° pass.
    density : int
        Fibonacci node density (nodes / unit²).
    width, height : int
        Frame resolution in pixels.
    fov : float
        Vertical field-of-view in degrees.
    cam_dist : float
        Camera orbit radius (world units).
    cam_height : float
        Camera Y position (world units).
    look_at : Vec3
        World-space point the camera targets. Default: (0, 2.1, 0).
    start_angle : float
        Starting orbit angle in radians (0 = +Z axis).
    fps : int
        Output GIF playback speed in frames per second.
    bg_color : Vec3
        Background colour. Default: (0.82, 0.84, 0.88).
    title : str
        Banner text burned into the lower-left corner.
    counter_rotate : bool
        When True, append a second 360° pass where the camera orbits
        normally while the model counter-rotates in the opposite direction.
        Default: True.
    counter_rotate_ratio : float
        Model rotation speed as a fraction of camera orbit speed.
        1.0 = equal and opposite (720° relative per GIF loop).
        0.5 = model drifts 180° against camera's 360° (default).
        Negative values rotate the model with the camera instead.
    verbose : bool
        Print per-frame progress.

    Returns
    -------
    dict
        {'output': output_gif, 'n_frames': total_frames,
         'total_time': float, 'avg_frame_time': float,
         'size_kb': float}
    """
    if look_at is None:
        look_at = Vec3(0.0, 2.10, 0.0)
    if bg_color is None:
        bg_color = Vec3(0.82, 0.84, 0.88)

    delay_cs = max(1, 100 // fps)   # centiseconds per frame
    n_passes = 2 if counter_rotate else 1

    os.makedirs(os.path.dirname(os.path.abspath(output_gif)), exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix='red_carpet_')

    frame_pngs = []
    render_times = []
    total_t0 = time.time()
    global_frame = 0
    total_frames = n_frames * n_passes

    if verbose:
        print(f"\n🎬  red_carpet_render — {n_passes} pass(es) × {n_frames} frames × {360/n_frames:.1f}°  |  {width}×{height}  |  density={density}")
        if counter_rotate:
            print(f"    ACT I: camera orbits, model still")
            print(f"    ACT II: camera orbits, model counter-rotates ×{counter_rotate_ratio:.2f}")
        print()

    # ── ACT I — camera orbits, model fixed ────────────────────────────────
    if verbose:
        print("  ── ACT I: ORBITAL ──")

    for i in range(n_frames):
        angle = start_angle + (2.0 * math.pi * i / n_frames)
        cam_x = math.sin(angle) * cam_dist
        cam_z = math.cos(angle) * cam_dist

        cam = PushCamera(
            pos=Vec3(cam_x, cam_height, cam_z),
            look_at=look_at,
            width=width, height=height, fov=fov,
        )

        t0 = time.time()
        pixels = entangle(objects, cam, light, density=density, bg_color=bg_color)
        frame_t = time.time() - t0
        total_elapsed = time.time() - total_t0
        render_times.append(frame_t)

        ppm = os.path.join(tmp_dir, f'frame_{global_frame:03d}.ppm')
        png = os.path.join(tmp_dir, f'frame_{global_frame:03d}.png')
        _write_ppm(pixels, ppm)

        angle_deg = math.degrees(angle) % 360
        label1 = title
        label2 = (f"Entangler | ORBITAL | frame {i+1:02d}/{n_frames}"
                  f" | cam {angle_deg:05.1f}° | t={total_elapsed:5.1f}s")

        subprocess.run([
            'convert', ppm,
            '-font', 'DejaVu-Sans-Bold', '-pointsize', '13',
            '-fill', '#ffd700', '-stroke', '#000000', '-strokewidth', '1',
            '-gravity', 'SouthWest', '-annotate', '+8+22', label1,
            '-font', 'DejaVu-Sans', '-pointsize', '11',
            '-fill', 'white', '-stroke', '#000000', '-strokewidth', '1',
            '-gravity', 'SouthWest', '-annotate', '+8+8', label2,
            png,
        ], capture_output=True, timeout=20)

        os.remove(ppm)
        frame_pngs.append(png)
        global_frame += 1

        if verbose:
            print(f"  Frame {global_frame:03d}/{total_frames}  |  cam {angle_deg:05.1f}°  |  {frame_t:.2f}s  |  Σ {total_elapsed:.1f}s")

    # ── ACT II — camera orbits, model counter-rotates ──────────────────────
    if counter_rotate:
        if verbose:
            print(f"\n  ── ACT II: PARALLAX (model × {counter_rotate_ratio:.2f} counter) ──")

        model_total_deg = counter_rotate_ratio * 360.0

        for i in range(n_frames):
            angle = start_angle + (2.0 * math.pi * i / n_frames)
            cam_x = math.sin(angle) * cam_dist
            cam_z = math.cos(angle) * cam_dist

            cam = PushCamera(
                pos=Vec3(cam_x, cam_height, cam_z),
                look_at=look_at,
                width=width, height=height, fov=fov,
            )

            # Model counter-rotates opposite to camera direction
            model_angle = -(counter_rotate_ratio * 2.0 * math.pi * i / n_frames)
            rotated_objects = _rotate_objects_y(objects, model_angle, look_at)

            t0 = time.time()
            pixels = entangle(rotated_objects, cam, light, density=density, bg_color=bg_color)
            frame_t = time.time() - t0
            total_elapsed = time.time() - total_t0
            render_times.append(frame_t)

            ppm = os.path.join(tmp_dir, f'frame_{global_frame:03d}.ppm')
            png = os.path.join(tmp_dir, f'frame_{global_frame:03d}.png')
            _write_ppm(pixels, ppm)

            cam_deg   = math.degrees(angle) % 360
            model_deg = math.degrees(abs(model_angle)) % 360
            label1 = title
            label2 = (f"Entangler | PARALLAX | frame {i+1:02d}/{n_frames}"
                      f" | cam {cam_deg:05.1f}° mdl −{model_deg:05.1f}° | t={total_elapsed:5.1f}s")

            subprocess.run([
                'convert', ppm,
                '-font', 'DejaVu-Sans-Bold', '-pointsize', '13',
                '-fill', '#00cfff', '-stroke', '#000000', '-strokewidth', '1',
                '-gravity', 'SouthWest', '-annotate', '+8+22', label1,
                '-font', 'DejaVu-Sans', '-pointsize', '11',
                '-fill', 'white', '-stroke', '#000000', '-strokewidth', '1',
                '-gravity', 'SouthWest', '-annotate', '+8+8', label2,
                png,
            ], capture_output=True, timeout=20)

            os.remove(ppm)
            frame_pngs.append(png)
            global_frame += 1

            if verbose:
                print(f"  Frame {global_frame:03d}/{total_frames}  |  cam {cam_deg:05.1f}° mdl −{model_deg:05.1f}°  |  {frame_t:.2f}s  |  Σ {total_elapsed:.1f}s")

    # ── Assemble GIF ───────────────────────────────────────────────────────
    total_time = time.time() - total_t0
    avg_frame_time = sum(render_times) / len(render_times)

    if verbose:
        print(f"\n  Rendered {global_frame} frames in {total_time:.1f}s (avg {avg_frame_time:.2f}s/frame)")
        print(f"  Assembling GIF ({global_frame} frames @ {fps} fps)...")

    gif_cmd = (
        ['convert',
         '-delay', str(delay_cs),
         '-loop', '0',
         '-layers', 'Optimize',
         '-dither', 'Riemersma',
         '-colors', '192',
        ]
        + frame_pngs
        + [output_gif]
    )
    subprocess.run(gif_cmd, capture_output=True, timeout=300)

    # Cleanup temp frames
    for p in frame_pngs:
        if os.path.exists(p):
            os.remove(p)
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    size_kb = os.path.getsize(output_gif) / 1024 if os.path.exists(output_gif) else 0

    if verbose:
        if os.path.exists(output_gif):
            print(f"  ✓  {output_gif}  ({size_kb:.0f} KB)")
        else:
            print(f"  ✗  GIF assembly failed.")

    return {
        'output': output_gif,
        'n_frames': global_frame,
        'total_time': total_time,
        'avg_frame_time': avg_frame_time,
        'size_kb': size_kb,
    }
