"""
Triaxial Asteroid Renderer — 2D projection of 3D ellipsoid with σ map.

Projects a triaxial ellipsoid at an arbitrary viewing angle and overlays:
- Surface σ color gradient (blue→red mapping)
- Internal cross-section with σ radial profile
- σ profiles along all three axes
- Data panel with SSBM-computed properties
- Shape silhouette with axis labels

Pure SVG. No external libraries. Every pixel computed from mass + geometry.
"""

import math
from .constants import XI
from .irregular import (
    full_analysis, sigma_at_surface, sigma_profile_axis,
    sigma_surface_map,
)
from .asteroids import mean_radius, axis_ratios


def _project_ellipse(a_px, b_px, c_px, elev_deg=25, azim_deg=30):
    """Project a 3D ellipsoid to a 2D ellipse at given viewing angle.

    Returns (semi_major_px, semi_minor_px, tilt_deg) of the projected ellipse.

    Uses the fact that the projection of an ellipsoid onto a plane
    is always an ellipse (linear algebra, no external formula).
    """
    elev = math.radians(elev_deg)
    azim = math.radians(azim_deg)

    # View direction
    vx = math.cos(elev) * math.sin(azim)
    vy = math.cos(elev) * math.cos(azim)
    vz = math.sin(elev)

    # The projected ellipse on the plane perpendicular to view direction
    # For an axis-aligned ellipsoid, the projection semi-axes can be
    # computed from the singular values of the projection matrix.
    # Simplified: project the three axis endpoints and fit an ellipse.

    # Right vector (horizontal in view)
    rx = math.cos(azim)
    ry = -math.sin(azim)
    rz = 0

    # Up vector
    ux = -math.sin(elev) * math.sin(azim)
    uy = -math.sin(elev) * math.cos(azim)
    uz = math.cos(elev)

    # Project the three axis endpoints
    points = []
    for ax_len, dx, dy, dz in [
        (a_px, 1, 0, 0), (a_px, -1, 0, 0),
        (b_px, 0, 1, 0), (b_px, 0, -1, 0),
        (c_px, 0, 0, 1), (c_px, 0, 0, -1),
    ]:
        x3d = ax_len * dx
        y3d = ax_len * dy
        z3d = ax_len * dz
        px = rx * x3d + ry * y3d + rz * z3d
        py = ux * x3d + uy * y3d + uz * z3d
        points.append((px, py))

    # Find the bounding ellipse: use the max extent in each direction
    # This is approximate but visually correct
    max_h = max(abs(p[0]) for p in points)
    max_v = max(abs(p[1]) for p in points)

    return max_h, max_v


def _sigma_to_color(sigma, sigma_min, sigma_max):
    """Map σ to a color: deep blue (low) → cyan → yellow → red (high)."""
    if sigma_max <= sigma_min:
        return "#2244aa"
    t = (sigma - sigma_min) / (sigma_max - sigma_min)
    t = max(0, min(1, t))

    if t < 0.33:
        s = t / 0.33
        r, g, b = int(20 + 30*s), int(50 + 150*s), int(170 + 60*s)
    elif t < 0.66:
        s = (t - 0.33) / 0.33
        r, g, b = int(50 + 180*s), int(200 - 20*s), int(230 - 150*s)
    else:
        s = (t - 0.66) / 0.34
        r, g, b = int(230 + 25*s), int(180 - 130*s), int(80 - 60*s)

    return f"#{r:02x}{g:02x}{b:02x}"


def _format_e(val, precision=2):
    """Format number for labels."""
    if val == 0:
        return "0"
    if abs(val) >= 0.01 and abs(val) < 10000:
        return f"{val:.{precision}f}"
    return f"{val:.{precision}e}"


def render_asteroid(body, width=1000, height=800, elev=25, azim=30):
    """Render a triaxial asteroid cross-section as SVG.

    Layout:
    - Left: 3D-projected ellipsoid with σ surface coloring
    - Right top: σ profile along all three axes
    - Right bottom: data panel

    Args:
        body: asteroid dict from asteroids.py
        width, height: SVG dimensions
        elev, azim: viewing angles in degrees
    """
    analysis = full_analysis(body)
    a_m, b_m, c_m = body['a_m'], body['b_m'], body['c_m']
    name = body['name']

    # Profiles along each axis
    prof_a = sigma_profile_axis(body, 'a', n_points=80)
    prof_b = sigma_profile_axis(body, 'b', n_points=80)
    prof_c = sigma_profile_axis(body, 'c', n_points=80)

    # Scale factor: map the largest axis to ~200px
    max_axis = max(a_m, b_m, c_m)
    scale = 180 / max_axis

    a_px = a_m * scale
    b_px = b_m * scale
    c_px = c_m * scale

    # Project to 2D
    proj_h, proj_v = _project_ellipse(a_px, b_px, c_px, elev, azim)

    # Center of ellipsoid drawing
    cx = 250
    cy = height // 2

    # σ range for coloring
    sig_min = analysis['sigma_a']
    sig_max = analysis['sigma_c']
    sig_center = analysis['sigma_center']

    svg = []

    # ── SVG Header ────────────────────────────────────────────────
    svg.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
     font-family="Helvetica, Arial, sans-serif">

  <defs>
    <radialGradient id="body-grad" cx="40%" cy="35%">
      <stop offset="0%" stop-color="{body['color_accent']}"/>
      <stop offset="70%" stop-color="{body['color_primary']}"/>
      <stop offset="100%" stop-color="#111111"/>
    </radialGradient>
    <radialGradient id="sigma-grad" cx="40%" cy="35%">
      <stop offset="0%" stop-color="{_sigma_to_color(sig_center, sig_min, sig_max)}" stop-opacity="0.4"/>
      <stop offset="60%" stop-color="{_sigma_to_color((sig_min+sig_max)/2, sig_min, sig_max)}" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="{_sigma_to_color(sig_min, sig_min, sig_max)}" stop-opacity="0.2"/>
    </radialGradient>
    <clipPath id="body-clip">
      <ellipse cx="{cx}" cy="{cy}" rx="{proj_h}" ry="{proj_v}"/>
    </clipPath>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="#0a0a1a"/>
''')

    # ── Title ─────────────────────────────────────────────────────
    svg.append(f'''
  <text x="{width//2}" y="30" text-anchor="middle" fill="#ffffff"
        font-size="16" font-weight="bold">{name.upper()} — SSBM INTERIOR ANALYSIS</text>
  <text x="{width//2}" y="48" text-anchor="middle" fill="#777777"
        font-size="10">{body['mission']} · {body['shape_desc']} · {body['spectral_type']}</text>
''')

    # ── Ellipsoid body ────────────────────────────────────────────
    # Main body
    svg.append(f'''  <ellipse cx="{cx}" cy="{cy}" rx="{proj_h}" ry="{proj_v}"
      fill="url(#body-grad)" stroke="#555" stroke-width="1"/>''')

    # σ overlay
    svg.append(f'''  <ellipse cx="{cx}" cy="{cy}" rx="{proj_h}" ry="{proj_v}"
      fill="url(#sigma-grad)" stroke="none"/>''')

    # Internal structure: concentric ellipses at 25%, 50%, 75%
    for frac in [0.75, 0.50, 0.25]:
        rh = proj_h * frac
        rv = proj_v * frac
        # σ at this shell
        sig_shell = sig_center * (1 - 0.3 * frac)  # approximate interior σ
        col = _sigma_to_color(sig_shell, sig_min, sig_max)
        svg.append(f'''  <ellipse cx="{cx}" cy="{cy}" rx="{rh}" ry="{rv}"
      fill="none" stroke="{col}" stroke-width="0.8" opacity="0.5"
      stroke-dasharray="4,3"/>''')

    # ── Axis lines ────────────────────────────────────────────────
    # a-axis (horizontal-ish)
    ah = proj_h * 1.15
    svg.append(f'''  <line x1="{cx-ah}" y1="{cy}" x2="{cx+ah}" y2="{cy}"
      stroke="#ff6644" stroke-width="0.8" stroke-dasharray="6,3" opacity="0.6"/>
  <text x="{cx+ah+5}" y="{cy+4}" fill="#ff6644" font-size="9" font-weight="bold">a</text>
  <text x="{cx+ah+5}" y="{cy+14}" fill="#ff6644" font-size="7">{_format_e(a_m*2)}m</text>''')

    # c-axis (vertical-ish)
    cv = proj_v * 1.15
    svg.append(f'''  <line x1="{cx}" y1="{cy-cv}" x2="{cx}" y2="{cy+cv}"
      stroke="#4488ff" stroke-width="0.8" stroke-dasharray="6,3" opacity="0.6"/>
  <text x="{cx+5}" y="{cy-cv-4}" fill="#4488ff" font-size="9" font-weight="bold">c</text>
  <text x="{cx+5}" y="{cy-cv+8}" fill="#4488ff" font-size="7">{_format_e(c_m*2)}m</text>''')

    # Center dot
    svg.append(f'''  <circle cx="{cx}" cy="{cy}" r="2.5" fill="#ffffff" opacity="0.8"/>''')

    # ── σ-Profile Graph (all three axes) ──────────────────────────
    gx = 520
    gy = 70
    gw = 430
    gh = 280

    svg.append(f'''
  <rect x="{gx-5}" y="{gy-5}" width="{gw+10}" height="{gh+45}"
        fill="#111122" rx="5" stroke="#333" stroke-width="1"/>
  <text x="{gx + gw//2}" y="{gy + 15}" text-anchor="middle"
        fill="#aaaaaa" font-size="11" font-weight="bold">σ PROFILE ALONG EACH AXIS</text>
''')

    ax_left = gx + 60
    ax_right = gx + gw - 15
    ax_top = gy + 30
    ax_bottom = gy + gh + 10
    ax_w = ax_right - ax_left
    ax_h = ax_bottom - ax_top

    # Axes
    svg.append(f'''  <line x1="{ax_left}" y1="{ax_bottom}" x2="{ax_right}" y2="{ax_bottom}"
      stroke="#555" stroke-width="1"/>
  <line x1="{ax_left}" y1="{ax_top}" x2="{ax_left}" y2="{ax_bottom}"
      stroke="#555" stroke-width="1"/>
  <text x="{ax_left + ax_w//2}" y="{ax_bottom + 25}" text-anchor="middle"
      fill="#888" font-size="9">fractional radius (0 = center, 1 = surface)</text>
  <text x="{ax_left - 42}" y="{ax_top + ax_h//2}" text-anchor="middle"
      fill="#888" font-size="9" transform="rotate(-90,{ax_left-42},{ax_top + ax_h//2})">σ(r)</text>
''')

    # Find global σ range
    all_sigs = [p['sigma'] for p in prof_a + prof_b + prof_c if p['sigma'] > 0]
    if all_sigs:
        plot_max = max(all_sigs) * 1.05
        plot_min = min(all_sigs) * 0.95
    else:
        plot_max = 1e-15
        plot_min = 0

    # Plot each axis profile
    for prof, color, label in [
        (prof_a, '#ff6644', 'a-axis'),
        (prof_b, '#44cc44', 'b-axis'),
        (prof_c, '#4488ff', 'c-axis'),
    ]:
        points = []
        for p in prof:
            x = ax_left + p['frac'] * ax_w
            if plot_max > plot_min:
                t = (p['sigma'] - plot_min) / (plot_max - plot_min)
            else:
                t = 0.5
            y = ax_bottom - t * ax_h
            points.append(f"{x:.1f},{y:.1f}")

        if points:
            svg.append(f'''  <polyline points="{' '.join(points)}"
      fill="none" stroke="{color}" stroke-width="1.8" opacity="0.9"/>''')

    # Legend
    for i, (color, label) in enumerate([
        ('#ff6644', 'a-axis (longest)'),
        ('#44cc44', 'b-axis (middle)'),
        ('#4488ff', 'c-axis (shortest)'),
    ]):
        lx = ax_right - 120
        ly = ax_top + 12 + i * 14
        svg.append(f'''  <line x1="{lx}" y1="{ly}" x2="{lx+15}" y2="{ly}"
      stroke="{color}" stroke-width="2"/>
  <text x="{lx+20}" y="{ly+3}" fill="{color}" font-size="8">{label}</text>''')

    # σ axis ticks
    for frac in [0, 0.5, 1.0]:
        y = ax_bottom - frac * ax_h
        val = plot_min + frac * (plot_max - plot_min)
        svg.append(f'''  <text x="{ax_left - 4}" y="{y + 3}" text-anchor="end"
      fill="#666" font-size="7">{_format_e(val)}</text>''')

    # r ticks
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        x = ax_left + frac * ax_w
        svg.append(f'''  <text x="{x}" y="{ax_bottom + 12}" text-anchor="middle"
      fill="#666" font-size="7">{frac:.2f}</text>''')

    # ── Data Panel ────────────────────────────────────────────────
    panel_y = gy + gh + 60
    panel_h = 320

    svg.append(f'''
  <rect x="{gx - 5}" y="{panel_y}" width="{gw + 10}" height="{panel_h}"
        fill="#111122" rx="5" stroke="#333" stroke-width="1"/>
  <text x="{gx + gw//2}" y="{panel_y + 20}" text-anchor="middle"
        fill="#aaaaaa" font-size="11" font-weight="bold">SSBM PROPERTIES</text>
''')

    # Two columns of data
    col1_x = gx + 10
    col2_x = gx + gw // 2 + 10

    props_left = [
        ("SHAPE", "#aaaaaa", True),
        (f"  a = {_format_e(a_m*2)} m", "#ff6644", False),
        (f"  b = {_format_e(b_m*2)} m", "#44cc44", False),
        (f"  c = {_format_e(c_m*2)} m", "#4488ff", False),
        (f"  b/a = {analysis['axis_ratios'][1]:.3f}", "#cccccc", False),
        (f"  c/a = {analysis['axis_ratios'][2]:.3f}", "#cccccc", False),
        (f"  M = {_format_e(analysis['mass_kg'])} kg", "#cccccc", False),
        (f"  ρ = {analysis['density_kg_m3']} kg/m³", "#cccccc", False),
        ("", "#000000", False),
        ("GRAVITY (Newton)", "#aaaaaa", True),
        (f"  g(a) = {_format_e(analysis['g_a_m_s2'])} m/s²", "#ff6644", False),
        (f"  g(c) = {_format_e(analysis['g_c_m_s2'])} m/s²", "#4488ff", False),
        (f"  ratio = {analysis['g_ratio_c_over_a']:.3f}×", "#cccccc", False),
        (f"  v_esc(a) = {_format_e(analysis['v_esc_a_m_s'])} m/s", "#cccccc", False),
    ]

    props_right = [
        ("SSBM σ FIELD", "#aaaaaa", True),
        (f"  ξ = {XI}", "#44aaff", False),
        (f"  σ(a-tip) = {_format_e(analysis['sigma_a'])}", "#ff6644", False),
        (f"  σ(c-tip) = {_format_e(analysis['sigma_c'])}", "#4488ff", False),
        (f"  σ(center) = {_format_e(analysis['sigma_center'])}", "#ffaa44", False),
        (f"  anisotropy = {analysis['sigma_anisotropy']*100:.2f}%", "#ffaa44", False),
        (f"  Λ(a) = {_format_e(analysis['lambda_eff_a_mev'])} MeV", "#88cc88", False),
        (f"  Λ(c) = {_format_e(analysis['lambda_eff_c_mev'])} MeV", "#88cc88", False),
        ("", "#000000", False),
        ("ROTATION", "#aaaaaa", True),
        (f"  P = {body['rotation_period_h']:.3f} h", "#cccccc", False),
        (f"  ω = {_format_e(analysis['omega_rad_s'])} rad/s", "#cccccc", False),
        (f"  liftoff ratio = {_format_e(analysis['liftoff_ratio_a'])}", "#cccccc", False),
        (f"  spin: {body['spin_state']}", "#cc88cc", False),
    ]

    for i, (text, color, bold) in enumerate(props_left):
        y = panel_y + 40 + i * 18
        weight = "bold" if bold else "normal"
        svg.append(f'''  <text x="{col1_x}" y="{y}" fill="{color}" font-size="9"
      font-family="monospace" font-weight="{weight}">{text}</text>''')

    for i, (text, color, bold) in enumerate(props_right):
        y = panel_y + 40 + i * 18
        weight = "bold" if bold else "normal"
        svg.append(f'''  <text x="{col2_x}" y="{y}" fill="{color}" font-size="9"
      font-family="monospace" font-weight="{weight}">{text}</text>''')

    # ── σ Color Bar ───────────────────────────────────────────────
    bar_x = 50
    bar_y = height - 55
    bar_w = 400
    bar_h = 12

    svg.append(f'''
  <text x="{bar_x}" y="{bar_y - 5}" fill="#888" font-size="8">σ surface gradient:</text>''')

    n_bars = 40
    for i in range(n_bars):
        t = i / (n_bars - 1)
        sig_val = sig_min + t * (sig_max - sig_min)
        col = _sigma_to_color(sig_val, sig_min, sig_max)
        bx = bar_x + (bar_w * i / n_bars)
        bw = bar_w / n_bars + 1
        svg.append(f'''  <rect x="{bx:.1f}" y="{bar_y}" width="{bw:.1f}" height="{bar_h}"
      fill="{col}"/>''')

    svg.append(f'''  <text x="{bar_x}" y="{bar_y + bar_h + 10}" fill="#888" font-size="7">
    σ={_format_e(sig_min)} (a-tip, weakest)</text>
  <text x="{bar_x + bar_w}" y="{bar_y + bar_h + 10}" text-anchor="end" fill="#888" font-size="7">
    σ={_format_e(sig_max)} (c-tip, strongest)</text>''')

    # ── Footer ────────────────────────────────────────────────────
    svg.append(f'''
  <text x="{width//2}" y="{height - 8}" text-anchor="middle"
        fill="#444444" font-size="8">
    □σ = −ξR  ·  ξ = {XI}  ·  SSBM / local_library  ·  all properties derived from mass + geometry</text>
''')

    svg.append('</svg>')
    return '\n'.join(svg)


def render_asteroid_to_file(body, filepath, **kwargs):
    """Render an asteroid to SVG file."""
    svg = render_asteroid(body, **kwargs)
    with open(filepath, 'w') as f:
        f.write(svg)
    return filepath


def render_all_asteroids(output_dir):
    """Render all 6 asteroids to SVG files."""
    import os
    from .asteroids import ALL_ASTEROIDS
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    for key, body in ALL_ASTEROIDS.items():
        path = os.path.join(output_dir, f"{key}_ssbm.svg")
        render_asteroid_to_file(body, path)
        paths[key] = path
    return paths
