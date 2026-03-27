"""
2D Cross-Section Renderer — mathematically computed SVG output.

Takes a planetary body + its σ-profile and renders:
- Half-circle cross-section with colored layers
- σ gradient overlay (blue = low σ, red = high σ)
- Radial σ-profile graph
- Data labels for each layer
- Surface/center σ values

Pure SVG output. No external dependencies.
"""

import math
from .constants import XI
from .interior import compute_profile, surface_summary, center_summary
from .scale import sigma_conversion


def _sigma_to_color(sigma, sigma_max):
    """Map σ value to a color (blue=0 → red=max)."""
    if sigma_max <= 0:
        return "rgba(0,80,200,0.15)"
    t = min(sigma / sigma_max, 1.0)
    r = int(40 + 215 * t)
    g = int(80 + 40 * (1 - t))
    b = int(200 * (1 - t))
    return f"rgba({r},{g},{b},0.3)"


def _format_sci(val, precision=2):
    """Format number in scientific notation for SVG labels."""
    if val == 0:
        return "0"
    exp = math.floor(math.log10(abs(val)))
    mantissa = val / (10 ** exp)
    if abs(exp) <= 2:
        return f"{val:.{precision}f}"
    return f"{mantissa:.{precision}f}×10<tspan baseline-shift='super' font-size='9'>{exp}</tspan>"


def _format_e(val, precision=2):
    """Format for plain text (no SVG tags)."""
    if val == 0:
        return "0"
    if abs(val) >= 0.01 and abs(val) < 10000:
        return f"{val:.{precision}f}"
    return f"{val:.{precision}e}"


def render_cross_section(body, width=900, height=900):
    """Render a planetary interior cross-section as SVG.

    Returns SVG string.

    Layout:
    - Left half: full-circle cross-section with layers
    - Right side: σ-profile graph + data panel
    """
    profile = compute_profile(body, n_points=300)
    layers = body['layers']
    R = body['radius_m']
    M = body['mass_kg']
    name = body['name']

    surf = surface_summary(body)
    cent = center_summary(body)

    # Find max σ in profile
    sigma_max = max(p['sigma'] for p in profile)
    sigma_min = min(p['sigma'] for p in profile if p['sigma'] > 0)

    # ── Layout constants ──────────────────────────────────────────
    margin = 40
    cx = 280          # center of cross-section circle
    cy = height // 2
    cr = 220          # radius of cross-section circle

    graph_x = 560     # x start of σ-profile graph
    graph_w = 290     # width of graph
    graph_y = 120     # y start
    graph_h = 350     # height

    svg_parts = []

    # ── SVG Header ────────────────────────────────────────────────
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
     font-family="Helvetica, Arial, sans-serif">

  <defs>
    <clipPath id="circle-clip">
      <circle cx="{cx}" cy="{cy}" r="{cr}"/>
    </clipPath>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="#0a0a1a"/>
''')

    # ── Title ─────────────────────────────────────────────────────
    svg_parts.append(f'''
  <text x="{width//2}" y="35" text-anchor="middle" fill="#ffffff"
        font-size="18" font-weight="bold">{name.upper()} — SSBM INTERIOR CROSS-SECTION</text>
  <text x="{width//2}" y="55" text-anchor="middle" fill="#888888"
        font-size="11">Scale field σ computed from enclosed mass: σ(r) = ξ·GM(r)/(rc²)</text>
''')

    # ── Cross-section circle: draw layers from outside in ─────────
    for layer in reversed(layers):
        r_frac = layer['r_outer_m'] / R
        lr = cr * r_frac
        color = layer['color']

        svg_parts.append(f'''  <circle cx="{cx}" cy="{cy}" r="{lr}"
          fill="{color}" stroke="#333" stroke-width="0.5"
          clip-path="url(#circle-clip)"/>''')

    # ── σ gradient overlay (concentric rings) ─────────────────────
    n_rings = 50
    for i in range(n_rings, 0, -1):
        r_frac = i / n_rings
        r_px = cr * r_frac
        # Find σ at this radius
        r_m = R * r_frac
        # Interpolate from profile
        sig = 0
        for p in profile:
            if p['r_frac'] >= r_frac - 0.005:
                sig = p['sigma']
                break
        color = _sigma_to_color(sig, sigma_max)
        svg_parts.append(f'''  <circle cx="{cx}" cy="{cy}" r="{r_px}"
          fill="{color}" stroke="none" clip-path="url(#circle-clip)"/>''')

    # ── Layer boundary lines and labels ───────────────────────────
    for i, layer in enumerate(layers):
        r_frac = layer['r_outer_m'] / R
        lr = cr * r_frac

        # Dashed circle for boundary
        svg_parts.append(f'''  <circle cx="{cx}" cy="{cy}" r="{lr}"
          fill="none" stroke="#ffffff" stroke-width="0.8"
          stroke-dasharray="4,4" opacity="0.5"/>''')

        # Label on the left side
        label_y = cy - lr + 14 if i < len(layers) - 1 else cy - lr + 14
        label_x = cx - lr + 8
        if lr < 30:
            label_x = cx - 25
            label_y = cy + 5

        # Compute σ at mid-layer
        r_prev = layers[i-1]['r_outer_m'] if i > 0 else 0
        r_mid = (r_prev + layer['r_outer_m']) / 2
        sig_mid = 0
        for p in profile:
            if p['r_m'] >= r_mid * 0.95:
                sig_mid = p['sigma']
                break

        svg_parts.append(f'''  <text x="{label_x}" y="{label_y}" fill="#ffffff"
          font-size="8" opacity="0.9">{layer['name']}</text>''')

    # ── Center marker ─────────────────────────────────────────────
    svg_parts.append(f'''  <circle cx="{cx}" cy="{cy}" r="3" fill="#ffffff" opacity="0.8"/>
  <text x="{cx+6}" y="{cy+3}" fill="#ffffff" font-size="7" opacity="0.7">center</text>''')

    # ── Outer rim label ───────────────────────────────────────────
    svg_parts.append(f'''  <circle cx="{cx}" cy="{cy}" r="{cr}"
      fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.6"/>''')

    # ── σ-Profile Graph ───────────────────────────────────────────
    gx = graph_x
    gy = graph_y
    gw = graph_w
    gh = graph_h

    svg_parts.append(f'''
  <!-- σ-Profile Graph -->
  <rect x="{gx-5}" y="{gy-5}" width="{gw+10}" height="{gh+40}"
        fill="#111122" rx="5" stroke="#333" stroke-width="1"/>
  <text x="{gx + gw//2}" y="{gy + 15}" text-anchor="middle"
        fill="#aaaaaa" font-size="11" font-weight="bold">σ PROFILE</text>
''')

    # Axes
    ax_left = gx + 45
    ax_right = gx + gw - 10
    ax_top = gy + 30
    ax_bottom = gy + gh + 10
    ax_w = ax_right - ax_left
    ax_h = ax_bottom - ax_top

    svg_parts.append(f'''  <line x1="{ax_left}" y1="{ax_bottom}" x2="{ax_right}" y2="{ax_bottom}"
        stroke="#555" stroke-width="1"/>
  <line x1="{ax_left}" y1="{ax_top}" x2="{ax_left}" y2="{ax_bottom}"
        stroke="#555" stroke-width="1"/>
  <text x="{ax_left + ax_w//2}" y="{ax_bottom + 25}" text-anchor="middle"
        fill="#888" font-size="9">r / R</text>
  <text x="{ax_left - 30}" y="{ax_top + ax_h//2}" text-anchor="middle"
        fill="#888" font-size="9" transform="rotate(-90,{ax_left-30},{ax_top + ax_h//2})">σ(r)</text>
''')

    # Plot σ(r) as polyline
    use_log = sigma_max > 0 and (sigma_max / max(sigma_min, 1e-30)) > 100
    points = []
    for p in profile:
        x = ax_left + p['r_frac'] * ax_w
        if sigma_max > 0:
            if use_log:
                if p['sigma'] > 0:
                    log_sig = math.log10(p['sigma'])
                    log_max = math.log10(sigma_max)
                    log_min = math.log10(max(sigma_min, sigma_max * 1e-6))
                    t = (log_sig - log_min) / (log_max - log_min) if log_max != log_min else 0
                else:
                    t = 0
            else:
                t = p['sigma'] / sigma_max
            y = ax_bottom - t * ax_h
        else:
            y = ax_bottom
        points.append(f"{x:.1f},{y:.1f}")

    if points:
        svg_parts.append(f'''  <polyline points="{' '.join(points)}"
          fill="none" stroke="#44aaff" stroke-width="2"/>''')

    # Layer boundaries on graph
    for layer in layers:
        r_frac = layer['r_outer_m'] / R
        x = ax_left + r_frac * ax_w
        svg_parts.append(f'''  <line x1="{x}" y1="{ax_top}" x2="{x}" y2="{ax_bottom}"
          stroke="#444" stroke-width="0.5" stroke-dasharray="3,3"/>''')

    # Axis tick labels
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        x = ax_left + frac * ax_w
        svg_parts.append(f'''  <text x="{x}" y="{ax_bottom + 12}" text-anchor="middle"
          fill="#666" font-size="7">{frac:.2f}</text>''')

    # σ axis ticks
    for frac in [0, 0.5, 1.0]:
        y = ax_bottom - frac * ax_h
        if sigma_max > 0:
            if use_log:
                log_max = math.log10(sigma_max)
                log_min = math.log10(max(sigma_min, sigma_max * 1e-6))
                val = 10 ** (log_min + frac * (log_max - log_min))
            else:
                val = frac * sigma_max
            label = _format_e(val)
        else:
            label = "0"
        svg_parts.append(f'''  <text x="{ax_left - 4}" y="{y + 3}" text-anchor="end"
          fill="#666" font-size="7">{label}</text>''')

    # ── Data Panel ────────────────────────────────────────────────
    panel_y = gy + gh + 60
    svg_parts.append(f'''
  <!-- Data Panel -->
  <rect x="{gx - 5}" y="{panel_y}" width="{gw + 10}" height="230"
        fill="#111122" rx="5" stroke="#333" stroke-width="1"/>
  <text x="{gx + gw//2}" y="{panel_y + 20}" text-anchor="middle"
        fill="#aaaaaa" font-size="11" font-weight="bold">SSBM PROPERTIES</text>
''')

    # Property lines
    props = [
        (f"M = {_format_e(M)} kg", "#cccccc"),
        (f"R = {_format_e(R)} m", "#cccccc"),
        (f"ξ = {XI}", "#44aaff"),
        (f"σ(surface) = {_format_e(surf['sigma_surface'])}", "#ffaa44"),
        (f"σ(center)  = {_format_e(cent['sigma_center'])}", "#ffaa44"),
        (f"Λ_eff(surface) = {_format_e(surf['lambda_eff_mev'])} MeV", "#88cc88"),
        (f"Λ_eff(center)  = {_format_e(cent['lambda_eff_mev'])} MeV", "#88cc88"),
        (f"Proton shift(surface) = {_format_e(surf['proton_shift_ppm'])} ppm", "#cc88cc"),
        (f"Proton shift(center)  = {_format_e(cent['proton_shift_ppm'])} ppm", "#cc88cc"),
        (f"σ_conv (bonds fail) = {_format_e(sigma_conversion())}", "#ff4444"),
    ]

    for i, (text, color) in enumerate(props):
        y = panel_y + 40 + i * 18
        svg_parts.append(f'''  <text x="{gx + 10}" y="{y}" fill="{color}" font-size="9"
        font-family="monospace">{text}</text>''')

    # ── Layer Legend (bottom left) ────────────────────────────────
    legend_y = height - 30 - len(layers) * 22
    svg_parts.append(f'''
  <text x="40" y="{legend_y - 10}" fill="#aaaaaa" font-size="10"
        font-weight="bold">LAYERS</text>''')

    for i, layer in enumerate(layers):
        y = legend_y + i * 22
        svg_parts.append(f'''  <rect x="40" y="{y}" width="14" height="14"
          fill="{layer['color']}" rx="2"/>
  <text x="60" y="{y + 11}" fill="#cccccc" font-size="9">
    {layer['name']} — ρ={_format_e(layer['density_kg_m3'])} kg/m³ — {layer['composition']}</text>''')

    # ── Footer ────────────────────────────────────────────────────
    svg_parts.append(f'''
  <text x="{width//2}" y="{height - 12}" text-anchor="middle"
        fill="#555555" font-size="8">
    □σ = −ξR  ·  ξ = {XI}  ·  SSBM / local_library  ·  computed, not drawn</text>
''')

    # ── Close SVG ─────────────────────────────────────────────────
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def render_to_file(body, filepath):
    """Render a planetary cross-section to an SVG file."""
    svg = render_cross_section(body)
    with open(filepath, 'w') as f:
        f.write(svg)
    return filepath


def render_all(output_dir):
    """Render all known bodies to SVG files in output_dir."""
    import os
    from .planets import ALL_BODIES
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    for key, body in ALL_BODIES.items():
        path = os.path.join(output_dir, f"{key}_interior.svg")
        render_to_file(body, path)
        paths[key] = path
    return paths
