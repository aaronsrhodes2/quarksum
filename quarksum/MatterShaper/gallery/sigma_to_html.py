"""
sigma_to_html — Sigma Signature → interactive red-carpet HTML viewer.

Converts a .shape.json + .color.json pair into a self-contained HTML file
with the full red_carpet_html control panel:

  • Camera  — theta / phi / distance / fov
  • Object  — Rx / Ry / Rz rotation
  • Light   — theta / phi / distance / intensity
  • Time    — temperature slider (300 K → 6000 K) with thermal emission
  • Physics HUD — all materials with colour swatches + physics params

Zero runtime dependencies except three.js r128 from CDN.

Usage:
    from gallery.sigma_to_html import sigma_to_html

    sigma_to_html(
        key       = 'coffee_mug',
        shape_map = {...},   # loaded from .shape.json
        color_map = {...},   # loaded from .color.json
        output_path = 'gallery/renders/coffee_mug.html',
    )
"""

import json
import math
import os


# ── Bounding-box helper ───────────────────────────────────────────────────────

def _bbox(shape_map):
    layers = shape_map.get('layers', [])
    xs, ys, zs = [], [], []

    for layer in layers:
        t = layer.get('type', 'sphere')
        if t == 'sphere':
            p = layer.get('pos', [0, 0, 0])
            r = layer.get('radius', 0.5)
            for vals, coord in zip([xs, ys, zs], p):
                vals += [coord - r, coord + r]
        elif t == 'ellipsoid':
            p = layer.get('pos') or layer.get('center', [0, 0, 0])
            radii = layer.get('radii', [0.5, 0.5, 0.5])
            for vals, coord, rv in zip([xs, ys, zs], p, radii):
                vals += [coord - abs(rv), coord + abs(rv)]
        elif t == 'cone':
            bp = layer.get('base_pos', [0, 0, 0])
            h  = layer.get('height', 1.0)
            br = layer.get('base_radius', 0.5)
            tr = layer.get('top_radius', 0.0)
            mr = max(abs(br), abs(tr))
            xs += [bp[0] - mr, bp[0] + mr]
            ys += [bp[1], bp[1] + h]
            zs += [bp[2] - mr, bp[2] + mr]

    if not xs:
        return {'cx': 0.0, 'cy': 0.5, 'cz': 0.0, 'extent': 1.0}

    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    extent = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.1)
    return {'cx': cx, 'cy': cy, 'cz': cz, 'extent': extent}


# ── Thermal emission curve (blackbody approximation) ─────────────────────────

def _thermal_js():
    """Return a JS array literal for the 300 K → 6000 K blackbody curve."""
    entries = []
    for T in range(300, 6100, 100):
        if T < 700:
            r = (T - 300) / 400 * 0.08
            g = 0.0
            b = 0.0
        elif T < 1000:
            r = 0.08 + (T - 700) / 300 * 0.52
            g = max(0.0, (T - 850) / 150 * 0.04)
            b = 0.0
        elif T < 2000:
            frac = (T - 1000) / 1000
            r = 0.60 + frac * 0.40
            g = 0.04 + frac * 0.38
            b = max(0.0, (T - 1600) / 400 * 0.04)
        elif T < 4000:
            frac = (T - 2000) / 2000
            r = 1.0
            g = 0.42 + frac * 0.46
            b = 0.04 + frac * 0.36
        else:
            frac = (T - 4000) / 2000
            r = 1.0
            g = 0.88 + frac * 0.10
            b = 0.40 + frac * 0.55
        entries.append(
            f"  {{T:{T},r:{min(r,1):.4f},g:{min(g,1):.4f},b:{min(b,1):.4f}}}"
        )
    return "[\n" + ",\n".join(entries) + "\n]"


# ── Material JS + HTML helpers ────────────────────────────────────────────────

def _get_color(mat):
    if 'color' in mat:
        c = mat['color']
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            return float(c[0]), float(c[1]), float(c[2])
    return float(mat.get('r', 0.5)), float(mat.get('g', 0.5)), float(mat.get('b', 0.5))


def _materials_js(color_map):
    """Generate JS MATS dict for all materials in color_map."""
    mats = color_map.get('materials', {})
    lines = ['const MATS = {};', 'const MAT_PARAMS = {};']
    for mat_id, mat in mats.items():
        r, g, b = _get_color(mat)
        refl  = float(mat.get('reflectance', 0.1))
        rough = float(mat.get('roughness',   0.5))
        lines.append(
            f"MATS['{mat_id}'] = new THREE.MeshStandardMaterial({{"
            f"color:new THREE.Color({r:.4f},{g:.4f},{b:.4f}),"
            f"metalness:{refl:.4f},roughness:{rough:.4f},"
            f"emissive:new THREE.Color(0,0,0),emissiveIntensity:0"
            f"}});"
        )
        dens = mat.get('density_kg_m3', '—')
        mZ   = mat.get('mean_Z', '—')
        mA   = mat.get('mean_A', '—')
        comp = mat.get('composition', '').replace("'", "\\'")
        label = mat.get('label', mat_id).replace("'", "\\'")
        lines.append(
            f"MAT_PARAMS['{mat_id}']={{"
            f"r:{r:.4f},g:{g:.4f},b:{b:.4f},"
            f"reflectance:{refl:.4f},roughness:{rough:.4f},"
            f"density:{json.dumps(dens)},Z:{json.dumps(mZ)},A:{json.dumps(mA)},"
            f"label:'{label}',composition:'{comp}'"
            f"}};"
        )
    return '\n'.join(lines)


def _material_cards_html(color_map):
    """Generate HTML material cards for the physics HUD panel."""
    mats = color_map.get('materials', {})
    cards = []
    for mat_id, mat in mats.items():
        r, g, b = _get_color(mat)
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(r * 255), int(g * 255), int(b * 255))
        label = mat.get('label', mat_id)
        refl  = mat.get('reflectance', 0.1)
        rough = mat.get('roughness',   0.5)
        dens  = mat.get('density_kg_m3', '—')
        mZ    = mat.get('mean_Z', '—')
        mA    = mat.get('mean_A', '—')
        comp  = mat.get('composition', '')
        cards.append(f"""
    <div class="mat-card" data-mat="{mat_id}" onclick="selectMat('{mat_id}')">
      <div class="mat-swatch" style="background:{hex_color}"></div>
      <div class="mat-info">
        <div class="mat-label">{label}</div>
        <div class="mat-grid">
          <span class="k">ρ</span><span class="v">{refl:.3f}</span>
          <span class="k">α</span><span class="v">{rough:.3f}</span>
          <span class="k">Z</span><span class="v">{mZ}</span>
          <span class="k">A</span><span class="v">{mA}</span>
          <span class="k">kg/m³</span><span class="v">{dens}</span>
        </div>
        <div class="mat-comp">{comp}</div>
      </div>
    </div>""")
    return '\n'.join(cards)


# ── Three.js geometry from shape layers ──────────────────────────────────────

def _layers_js(shape_map):
    """Generate Three.js mesh-creation JS for all shape layers."""
    layers = shape_map.get('layers', [])
    lines = []
    for i, layer in enumerate(layers):
        t      = layer.get('type', 'sphere')
        mat_id = layer.get('material', '')
        mat_ref = f"MATS['{mat_id}'] || defaultMat"

        if t == 'sphere':
            p = layer.get('pos', [0, 0, 0])
            r = max(float(layer.get('radius', 0.5)), 0.005)
            lines.append(
                f"(function(){{"
                f"var g=new THREE.SphereGeometry({r:.5f},32,24);"
                f"var m=new THREE.Mesh(g,{mat_ref});"
                f"m.position.set({p[0]:.5f},{p[1]:.5f},{p[2]:.5f});"
                f"m.castShadow=true;obj.add(m);"
                f"}})();"
            )

        elif t == 'ellipsoid':
            p    = layer.get('pos') or layer.get('center', [0, 0, 0])
            radii = layer.get('radii', [0.5, 0.5, 0.5])
            rot  = layer.get('rotate', [0, 0, 0])
            rx   = max(abs(float(radii[0])), 0.005)
            ry   = max(abs(float(radii[1])), 0.005)
            rz   = max(abs(float(radii[2])), 0.005)
            lines.append(
                f"(function(){{"
                f"var g=new THREE.SphereGeometry(1,32,24);"
                f"var m=new THREE.Mesh(g,{mat_ref});"
                f"m.position.set({float(p[0]):.5f},{float(p[1]):.5f},{float(p[2]):.5f});"
                f"m.scale.set({rx:.5f},{ry:.5f},{rz:.5f});"
                f"m.rotation.set({float(rot[0]):.5f},{float(rot[1]):.5f},{float(rot[2]):.5f});"
                f"m.castShadow=true;obj.add(m);"
                f"}})();"
            )

        elif t == 'cone':
            bp  = layer.get('base_pos', [0, 0, 0])
            h   = max(float(layer.get('height', 1.0)), 0.005)
            br  = max(float(layer.get('base_radius', 0.5)), 0.0)
            tr  = max(float(layer.get('top_radius',  0.0)), 0.0)
            rot = layer.get('rotate', [0, 0, 0])
            cy  = float(bp[1]) + h / 2
            lines.append(
                f"(function(){{"
                f"var g=new THREE.CylinderGeometry({tr:.5f},{br:.5f},{h:.5f},32);"
                f"var m=new THREE.Mesh(g,{mat_ref});"
                f"m.position.set({float(bp[0]):.5f},{cy:.5f},{float(bp[2]):.5f});"
                f"m.rotation.set({float(rot[0]):.5f},{float(rot[1]):.5f},{float(rot[2]):.5f});"
                f"m.castShadow=true;obj.add(m);"
                f"}})();"
            )

    return '\n'.join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def sigma_to_html(key, shape_map, color_map, output_path, title=None):
    """Convert a Sigma Signature pair to an interactive HTML viewer.

    Parameters
    ----------
    key : str
        Object key (used for fallback title).
    shape_map : dict
        Loaded .shape.json content.
    color_map : dict
        Loaded .color.json content.
    output_path : str | Path
        Where to write the .html file.
    title : str, optional
        Display title. Falls back to shape_map['name'] or key.
    """
    title     = title or shape_map.get('name', key)
    subtitle  = shape_map.get('reference', '')
    geom_desc = shape_map.get('scale_note', '1 unit = 10 cm')
    n_layers  = len(shape_map.get('layers', []))
    n_mats    = len(color_map.get('materials', {}))

    bb         = _bbox(shape_map)
    extent     = bb['extent']
    look_y     = round(bb['cy'], 3)
    cam_default = round(extent * 3.0, 2)
    cam_min     = round(max(extent * 0.8, 0.5), 2)
    cam_max     = round(extent * 12.0, 2)

    thermal_js    = _thermal_js()
    materials_js  = _materials_js(color_map)
    mat_cards_html = _material_cards_html(color_map)
    layers_js     = _layers_js(shape_map)

    # Default material for any layer with an unknown material key
    first_mat_id = next(iter(color_map.get('materials', {})), None)
    if first_mat_id:
        default_mat_js = f"var defaultMat = MATS['{first_mat_id}'];"
    else:
        default_mat_js = (
            "var defaultMat = new THREE.MeshStandardMaterial("
            "{color:new THREE.Color(0.6,0.6,0.65),metalness:0.1,roughness:0.5});"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<link rel="icon" href="/static/favicon.ico">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0e0e10;color:#e0e0e0;font-family:'Courier New',monospace;
     display:flex;height:100vh;overflow:hidden;}}

#canvas-wrap{{flex:1;position:relative;min-width:0;}}
canvas{{display:block;width:100%;height:100%;}}

#panel{{
  width:260px;min-width:260px;
  background:#141416;
  border-left:1px solid #2a2a30;
  display:flex;flex-direction:column;
  overflow-y:auto;
}}
.panel-header{{background:#1e1e24;padding:10px 14px 8px;border-bottom:1px solid #2a2a30;}}
.panel-header h1{{font-size:11px;letter-spacing:2px;color:#ffd700;text-transform:uppercase;}}
.panel-header p{{font-size:9px;color:#555;margin-top:2px;}}

.section{{padding:10px 14px;border-bottom:1px solid #1e1e24;}}
.section-title{{font-size:9px;letter-spacing:1.5px;color:#666;
                text-transform:uppercase;margin-bottom:7px;}}
.badge{{display:inline-block;background:#ffd70018;border:1px solid #ffd70033;
        border-radius:3px;padding:1px 6px;font-size:9px;color:#ffd700;
        letter-spacing:1px;margin-bottom:6px;}}

.ctrl{{display:flex;align-items:center;margin-bottom:5px;gap:5px;}}
.ctrl label{{font-size:10px;color:#aaa;width:26px;flex-shrink:0;}}
.ctrl input[type=range]{{flex:1;height:3px;accent-color:#ffd700;cursor:pointer;}}
.ctrl .val{{font-size:9px;color:#ffd700;width:48px;text-align:right;flex-shrink:0;}}

button.rbtn{{background:#1e1e24;border:1px solid #333;color:#aaa;font-size:9px;
             font-family:inherit;padding:3px 8px;border-radius:3px;
             cursor:pointer;margin-top:5px;width:100%;}}
button.rbtn:hover{{background:#252530;color:#ffd700;}}

#hud{{position:absolute;top:10px;left:10px;font-size:9px;color:#555;
      pointer-events:none;user-select:none;line-height:1.6;}}
#hud span{{color:#888;}}

/* Observer toggle */
.obs-toggle{{display:flex;gap:0;margin-bottom:8px;}}
.obs-btn{{flex:1;padding:4px 0;font-size:9px;font-family:inherit;
          background:#1a1a1e;border:1px solid #333;color:#666;cursor:pointer;
          letter-spacing:0.5px;transition:all 0.15s;}}
.obs-btn:first-child{{border-radius:3px 0 0 3px;}}
.obs-btn:last-child{{border-radius:0 3px 3px 0;border-left:none;}}
.obs-btn.active{{background:#ffd70022;border-color:#ffd70066;color:#ffd700;}}

/* Light source rows */
.light-header{{display:flex;align-items:center;gap:6px;margin-bottom:6px;}}
.light-header .light-label{{font-size:10px;color:#aaa;flex:1;}}
.light-toggle{{background:none;border:1px solid #333;border-radius:3px;
               font-size:9px;font-family:inherit;padding:1px 7px;cursor:pointer;
               transition:all 0.15s;}}
.light-toggle.on{{color:#ffd700;border-color:#ffd70066;background:#ffd70015;}}
.light-toggle.off{{color:#444;border-color:#2a2a30;}}

/* Material cards */
.mat-card{{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid #1e1e24;
           cursor:pointer;transition:background 0.1s;}}
.mat-card:hover{{background:#1a1a22;margin:0 -14px;padding:6px 14px;}}
.mat-card.active{{background:#1e1e28;margin:0 -14px;padding:6px 14px;
                  border-left:2px solid #ffd700;}}
.mat-swatch{{width:28px;height:28px;border-radius:3px;flex-shrink:0;
             border:1px solid #333;margin-top:2px;}}
.mat-info{{flex:1;min-width:0;}}
.mat-label{{font-size:9px;color:#ccc;margin-bottom:3px;}}
.mat-grid{{display:grid;grid-template-columns:repeat(4,1fr);
           font-size:8px;gap:1px 4px;}}
.mat-grid .k{{color:#555;}}
.mat-grid .v{{color:#0cf;}}
.mat-comp{{font-size:8px;color:#444;margin-top:3px;
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}

#temp-swatch{{width:100%;height:14px;border-radius:2px;margin-top:5px;
              border:1px solid #333;}}
#temp-desc{{font-size:9px;color:#555;margin-top:4px;}}
#time-desc{{font-size:9px;color:#555;margin-top:4px;}}

.stat-row{{font-size:9px;color:#555;display:flex;justify-content:space-between;
           margin-bottom:3px;}}
.stat-row span{{color:#0cf;}}

/* Collapsible sections */
.badge{{cursor:pointer;user-select:none;}}
.badge::after{{content:' ▾';font-size:8px;opacity:0.5;}}
.section.collapsed .badge::after{{content:' ▸';}}
.section-body{{}}
.section.collapsed .section-body{{display:none;}}
</style>
</head>
<body>

<div id="canvas-wrap">
  <canvas id="c"></canvas>
  <div id="hud">
    🎥 <span id="hud-cam">—</span><br>
    🌡 <span id="hud-temp">300 K</span> &nbsp;
    🕐 <span id="hud-time">13.8 Gyr</span>
  </div>
</div>

<div id="panel">
  <div class="panel-header">
    <h1>⚛ {title}</h1>
    <p>{subtitle[:80] if subtitle else ''}</p>
  </div>

  <!-- VIEWPOINT — merged observer/non-observer -->
  <div class="section">
    <div class="badge" onclick="toggleSection(this)">👁 VIEWPOINT</div>
    <div class="section-body">
      <div class="obs-toggle">
        <button class="obs-btn active" id="btn-observer"
                onclick="setObserver(true)">⚛ OBSERVER</button>
        <button class="obs-btn" id="btn-nonobs"
                onclick="setObserver(false)">◌ NON-OBSERVER</button>
      </div>
      <div style="font-size:8px;color:#444;margin-bottom:8px;" id="obs-desc">
        Left-drag orbits you around the object · Shadows active</div>
      <div class="ctrl">
        <label style="width:36px">Edge</label>
        <input type="range" id="cam-edge" min="-20" max="20" value="0" step="0.5">
        <span class="val" id="v-cam-edge">0°</span>
      </div>
      <div class="ctrl"><label>r</label>
        <input type="range" id="cam-dist" min="{cam_min}" max="{cam_max}" value="{cam_default}" step="0.05">
        <span class="val" id="v-cam-dist">{cam_default}</span></div>
      <div class="ctrl"><label>fov</label>
        <input type="range" id="cam-fov" min="20" max="80" value="45" step="1">
        <span class="val" id="v-cam-fov">45°</span></div>
      <button class="rbtn" onclick="resetViewpoint()">Reset Viewpoint</button>
    </div>
  </div>

  <!-- LIGHT BOX -->
  <div class="section">
    <div class="badge" onclick="toggleSection(this)">📦 LIGHT BOX</div>
    <div class="section-body">
      <div class="light-header">
        <span class="light-label">6-wall diffuse · all directions</span>
        <button class="light-toggle on" id="tog-box" onclick="toggleLight('box')">ON</button>
      </div>
      <div class="ctrl"><label>Iv</label>
        <input type="range" id="box-int" min="0" max="5" value="1.2" step="0.05">
        <span class="val" id="v-box-int">1.2</span></div>
    </div>
  </div>

  <!-- CANDLE -->
  <div class="section">
    <div class="badge" onclick="toggleSection(this)">🕯 CANDLE</div>
    <div class="section-body">
      <div class="light-header">
        <span class="light-label">Warm flame · 1900 K</span>
        <button class="light-toggle on" id="tog-cnd" onclick="toggleLight('cnd')">ON</button>
      </div>
      <div class="ctrl"><label>θ</label>
        <input type="range" id="cnd-theta" min="-180" max="180" value="-60" step="1">
        <span class="val" id="v-cnd-theta">-60°</span></div>
      <div class="ctrl"><label>φ</label>
        <input type="range" id="cnd-phi" min="5" max="85" value="20" step="1">
        <span class="val" id="v-cnd-phi">20°</span></div>
      <div class="ctrl"><label>r</label>
        <input type="range" id="cnd-dist" min="{cam_min}" max="{cam_max}" value="{round(cam_default*1.2,2)}" step="0.1">
        <span class="val" id="v-cnd-dist">{round(cam_default*1.2,2)}</span></div>
      <div class="ctrl"><label>Iv</label>
        <input type="range" id="cnd-int" min="0" max="2000" value="300" step="25">
        <span class="val" id="v-cnd-int">300</span></div>
    </div>
  </div>

  <!-- TUNGSTEN BULB -->
  <div class="section">
    <div class="badge" onclick="toggleSection(this)">💡 TUNGSTEN BULB</div>
    <div class="section-body">
      <div class="light-header">
        <span class="light-label">Hot filament · 2700 K</span>
        <button class="light-toggle on" id="tog-tng" onclick="toggleLight('tng')">ON</button>
      </div>
      <div class="ctrl"><label>θ</label>
        <input type="range" id="tng-theta" min="-180" max="180" value="45" step="1">
        <span class="val" id="v-tng-theta">45°</span></div>
      <div class="ctrl"><label>φ</label>
        <input type="range" id="tng-phi" min="5" max="85" value="55" step="1">
        <span class="val" id="v-tng-phi">55°</span></div>
      <div class="ctrl"><label>r</label>
        <input type="range" id="tng-dist" min="{cam_min}" max="{cam_max}" value="{round(cam_default*1.5,2)}" step="0.1">
        <span class="val" id="v-tng-dist">{round(cam_default*1.5,2)}</span></div>
      <div class="ctrl"><label>Iv</label>
        <input type="range" id="tng-int" min="0" max="2000" value="400" step="25">
        <span class="val" id="v-tng-int">400</span></div>
    </div>
  </div>

  <!-- EXPOSURE -->
  <div class="section">
    <div class="badge" onclick="toggleSection(this)">🎞 EXPOSURE</div>
    <div class="section-body">
      <div class="ctrl"><label>exp</label>
        <input type="range" id="exposure" min="0.25" max="8" value="1.0" step="0.05">
        <span class="val" id="v-exposure">1.0×</span></div>
    </div>
  </div>

  <!-- TEMPERATURE — object thermal state -->
  <div class="section">
    <div class="badge" onclick="toggleSection(this)">🌡 TEMPERATURE</div>
    <div class="section-body">
      <div class="section-title">Object thermal emission</div>
      <div class="ctrl"><label>T</label>
        <input type="range" id="temp" min="300" max="6000" value="300" step="50">
        <span class="val" id="v-temp">300 K</span></div>
      <div id="temp-swatch"></div>
      <div id="temp-desc">Room temperature — no emission</div>
    </div>
  </div>

  <!-- TIME — cosmological epoch -->
  <div class="section">
    <div class="badge" onclick="toggleSection(this)">🕐 TIME</div>
    <div class="section-body">
      <div class="section-title">Cosmological epoch</div>
      <div class="ctrl"><label>t</label>
        <input type="range" id="cosmo-time" min="0" max="100" value="100" step="1">
        <span class="val" id="v-cosmo-time">13.8 Gyr</span></div>
      <div id="time-desc">Present epoch — cold dark universe</div>
    </div>
  </div>

  <!-- MATERIAL PHYSICS -->
  <div class="section">
    <div class="badge">⚗ MATERIAL PHYSICS</div>
    <div class="section-title">{n_mats} material{'s' if n_mats != 1 else ''} · {n_layers} primitive{'s' if n_layers != 1 else ''}</div>
    <div id="mat-cards">
{mat_cards_html}
    </div>
  </div>

  <div class="section">
    <div class="stat-row">primitives <span>{n_layers}</span></div>
    <div class="stat-row">materials  <span>{n_mats}</span></div>
    <div class="stat-row">scale      <span>1u=10cm</span></div>
    <div style="font-size:8px;color:#333;margin-top:6px;">□σ = −ξR · Quarksum</div>
  </div>

</div><!-- panel -->

<script src="/static/three.r128.min.js"></script>
<script>
'use strict';

// ── Material data ────────────────────────────────────────────────────────────
{materials_js}

// ── Thermal emission (blackbody approx) ─────────────────────────────────────
const THERMAL = {thermal_js};

// ── Scene state ──────────────────────────────────────────────────────────────
let camTheta = 30*Math.PI/180, camPhi = 25*Math.PI/180;
let camDist  = {cam_default}, camFov = 45, camEdge = 0;
let objRx=0, objRy=0, objRz=0;
let isObserver = true;  // true = left-drag orbits camera; false = left-drag rotates object
let temperature = 300, cosmoTime = 100, exposure = 1.0;
const LOOK_AT_Y = {look_y};

// ── Three.js setup ───────────────────────────────────────────────────────────
const canvas   = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{canvas,antialias:true}});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.physicallyCorrectLights = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = exposure;
renderer.outputEncoding = THREE.sRGBEncoding;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e0e10);

const camera=new THREE.PerspectiveCamera(camFov,1,0.01,500);

// ── Default material fallback ────────────────────────────────────────────────
{default_mat_js}

// ── Object group ─────────────────────────────────────────────────────────────
const obj = new THREE.Group();
{layers_js}
scene.add(obj);

// Ground plane
const gnd=new THREE.Mesh(
  new THREE.PlaneGeometry(100,100),
  new THREE.MeshStandardMaterial({{color:new THREE.Color(0.05,0.05,0.06),
    metalness:0,roughness:0.9}})
);
gnd.rotation.x=-Math.PI/2;
gnd.receiveShadow=true;
scene.add(gnd);

// ── Lights ───────────────────────────────────────────────────────────────────
// Light box — ambient from all 6 walls (photography soft-box)
const lightBox = new THREE.AmbientLight(0xd0d8f0, 1.2);
scene.add(lightBox);
let lbOn=true, lbInt=1.2;

// Candle — warm orange flame, low position
const candle = new THREE.PointLight(0xff8830, 300, 500, 2);
candle.castShadow = true;
candle.shadow.mapSize.set(512,512);
scene.add(candle);
let cndOn=true, cndTheta=-60*Math.PI/180, cndPhi=20*Math.PI/180;
let cndDist={round(cam_default*1.2,2)}, cndInt=300;

// Tungsten bulb — warm white filament (2700K colour)
const tungsten = new THREE.PointLight(0xffeab0, 400, 500, 2);
tungsten.castShadow = true;
tungsten.shadow.mapSize.set(1024,1024);
scene.add(tungsten);
let tngOn=true, tngTheta=45*Math.PI/180, tngPhi=55*Math.PI/180;
let tngDist={round(cam_default*1.5,2)}, tngInt=400;

// Cosmological ambient — set by time slider
const cosmoAmb = new THREE.AmbientLight(0xff6020, 0);
scene.add(cosmoAmb);

// ── Mouse drag ───────────────────────────────────────────────────────────────
let isDragging=false, dragIsOrbit=false;
let lastX=0, lastY=0;
canvas.addEventListener('mousedown',e=>{{
  isDragging=true;
  // Observer: left-drag = orbit (you move), right-drag = also orbit
  // Non-observer: left-drag = rotate object, right-drag = orbit
  dragIsOrbit = (e.button===2) || (e.button===0 && isObserver);
  lastX=e.clientX; lastY=e.clientY; e.preventDefault();
}});
canvas.addEventListener('contextmenu',e=>e.preventDefault());
window.addEventListener('mouseup',()=>{{isDragging=false;}});
window.addEventListener('mousemove',e=>{{
  if(!isDragging) return;
  const dx=(e.clientX-lastX)*0.005, dy=(e.clientY-lastY)*0.005;
  if(!dragIsOrbit){{
    objRy+=dx; objRx+=dy;
    updateObject();
  }} else {{
    camTheta-=dx; camPhi=Math.max(0.08,Math.min(Math.PI/2-0.05,camPhi-dy));
    updateCamera();
  }}
  lastX=e.clientX; lastY=e.clientY;
}});
canvas.addEventListener('wheel',e=>{{
  camDist=Math.max({cam_min},Math.min({cam_max},camDist+e.deltaY*0.01));
  setSlider('cam-dist',camDist,'v-cam-dist','');
  updateCamera();
  e.preventDefault();
}},{{passive:false}});

// ── Control helpers ──────────────────────────────────────────────────────────
function setSlider(id,val,vid,suffix){{
  const el=document.getElementById(id);
  if(el) el.value=val;
  const ve=document.getElementById(vid);
  if(ve) ve.textContent=(typeof val==='number'?val.toFixed(1):val)+(suffix||'');
}}

function spherePos(theta,phi,r){{
  return {{
    x:r*Math.cos(phi)*Math.sin(theta),
    y:r*Math.sin(phi),
    z:r*Math.cos(phi)*Math.cos(theta),
  }};
}}

// ── Observer toggle ───────────────────────────────────────────────────────────
function setObserver(obs){{
  isObserver = obs;
  document.getElementById('btn-observer').classList.toggle('active', obs);
  document.getElementById('btn-nonobs').classList.toggle('active', !obs);
  renderer.shadowMap.enabled = obs;
  // Rebuild shadow maps
  scene.traverse(o=>{{ if(o.castShadow) o.castShadow=obs; }});
  document.getElementById('obs-desc').textContent = obs
    ? 'Left-drag orbits you around the object · Shadows active'
    : 'Left-drag rotates the object · You are not disturbing it';
}}

// ── Camera ────────────────────────────────────────────────────────────────────
function updateCamera(){{
  const theta = camTheta + camEdge*Math.PI/180;
  const p=spherePos(theta,camPhi,camDist);
  camera.position.set(p.x,p.y+LOOK_AT_Y,p.z);
  camera.lookAt(0,LOOK_AT_Y,0);
  camera.fov=camFov;
  camera.updateProjectionMatrix();
  document.getElementById('hud-cam').textContent=
    `θ${{(theta*180/Math.PI).toFixed(0)}}° φ${{(camPhi*180/Math.PI).toFixed(0)}}° r${{camDist.toFixed(1)}}`;
}}

// ── Object rotation ───────────────────────────────────────────────────────────
function updateObject(){{
  obj.rotation.set(objRx,objRy,objRz);
}}

// ── Light updates ─────────────────────────────────────────────────────────────
function updateLightBox(){{
  lightBox.intensity = lbOn ? lbInt : 0;
}}
function updateCandle(){{
  const p=spherePos(cndTheta,cndPhi,cndDist);
  candle.position.set(p.x,p.y+LOOK_AT_Y,p.z);
  candle.intensity = cndOn ? cndInt : 0;
}}
function updateTungsten(){{
  const p=spherePos(tngTheta,tngPhi,tngDist);
  tungsten.position.set(p.x,p.y+LOOK_AT_Y,p.z);
  tungsten.intensity = tngOn ? tngInt : 0;
}}
function toggleLight(which){{
  if(which==='box')  {{ lbOn=!lbOn;  updateLightBox(); updateToggleBtn('tog-box',lbOn);  }}
  if(which==='cnd')  {{ cndOn=!cndOn; updateCandle();  updateToggleBtn('tog-cnd',cndOn); }}
  if(which==='tng')  {{ tngOn=!tngOn; updateTungsten();updateToggleBtn('tog-tng',tngOn); }}
}}
function updateToggleBtn(id,on){{
  const b=document.getElementById(id);
  b.textContent=on?'ON':'OFF';
  b.className='light-toggle '+(on?'on':'off');
}}

// ── Thermal emission ──────────────────────────────────────────────────────────
function lerp(a,b,t){{return a+(b-a)*t;}}
function thermalColor(T){{
  for(let i=0;i<THERMAL.length-1;i++){{
    if(T<=THERMAL[i+1].T){{
      const t=(T-THERMAL[i].T)/(THERMAL[i+1].T-THERMAL[i].T);
      return {{r:lerp(THERMAL[i].r,THERMAL[i+1].r,t),
               g:lerp(THERMAL[i].g,THERMAL[i+1].g,t),
               b:lerp(THERMAL[i].b,THERMAL[i+1].b,t)}};
    }}
  }}
  return THERMAL[THERMAL.length-1];
}}
function tempDesc(T){{
  if(T<500)  return 'Room temperature — no thermal emission';
  if(T<900)  return 'Warm — barely visible red glow';
  if(T<1200) return 'Hot — dull red emission';
  if(T<1800) return 'Very hot — orange-red glow';
  if(T<2500) return 'Extremely hot — yellow-orange';
  if(T<4000) return 'Incandescent — white-hot';
  return 'Stellar — blue-white emission';
}}
function updateTemp(){{
  const tc=thermalColor(temperature);
  const emC=new THREE.Color(tc.r,tc.g,tc.b);
  const emI=temperature>500?(temperature-500)/1000:0;
  Object.values(MATS).forEach(m=>{{ m.emissive=emC; m.emissiveIntensity=emI; }});
  const sw=document.getElementById('temp-swatch');
  sw.style.background=`rgb(${{(tc.r*255)|0}},${{(tc.g*255)|0}},${{(tc.b*255)|0}})`;
  document.getElementById('temp-desc').textContent=tempDesc(temperature);
  document.getElementById('hud-temp').textContent=temperature+' K';
}}

// ── Cosmological time ─────────────────────────────────────────────────────────
// t=0 → near Big Bang (hot dense universe, warm reddish ambient from CMB)
// t=100 → present (13.8 Gyr, cold dark universe)
function updateCosmoTime(){{
  const t=cosmoTime/100.0;             // 0=early, 1=now
  // Background darkens as universe cools with time
  const bg=Math.round(14+t*0);        // stays dark
  scene.background=new THREE.Color(
    0.05+0.25*(1-t), 0.04+0.06*(1-t), 0.06+0.02*(1-t));
  // Cosmological ambient: bright warm glow near Big Bang, zero today
  cosmoAmb.intensity = (1-t)*3.0;
  // Display
  const gyr=(t*13.8).toFixed(1);
  document.getElementById('v-cosmo-time').textContent=gyr+' Gyr';
  document.getElementById('hud-time').textContent=gyr+' Gyr';
  const desc = t<0.01?'Near Big Bang — hot dense plasma, σ-field extreme'
    :t<0.1?'Early universe — matter decoupling era'
    :t<0.3?'First stars forming — reionization'
    :t<0.7?'Galaxy formation epoch'
    :t<0.95?'Solar system era'
    :'Present epoch — cold dark universe';
  document.getElementById('time-desc').textContent=desc;
}}

// ── Material selection ────────────────────────────────────────────────────────
function selectMat(id){{
  document.querySelectorAll('.mat-card').forEach(c=>c.classList.remove('active'));
  const card=document.querySelector(`[data-mat="${{id}}"]`);
  if(card) card.classList.add('active');
}}

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetViewpoint(){{
  camTheta=30*Math.PI/180; camPhi=25*Math.PI/180;
  camDist={cam_default}; camFov=45; camEdge=0;
  setSlider('cam-edge',0,'v-cam-edge','°');
  setSlider('cam-dist',camDist,'v-cam-dist','');
  setSlider('cam-fov',45,'v-cam-fov','°');
  updateCamera();
}}

// ── Slider wiring ─────────────────────────────────────────────────────────────
function wire(id,vid,suffix,onchange){{
  const el=document.getElementById(id);
  if(!el) return;
  el.addEventListener('input',()=>{{
    const v=parseFloat(el.value);
    document.getElementById(vid).textContent=v.toFixed(
      suffix==='°'||suffix===''?1:2)+suffix;
    onchange(v);
  }});
}}
wire('cam-edge','v-cam-edge','°',v=>{{camEdge=v;updateCamera();}});
wire('cam-dist','v-cam-dist','', v=>{{camDist=v;updateCamera();}});
wire('cam-fov', 'v-cam-fov', '°',v=>{{camFov=v;updateCamera();}});
wire('box-int', 'v-box-int', '', v=>{{lbInt=v;updateLightBox();}});
wire('cnd-theta','v-cnd-theta','°',v=>{{cndTheta=v*Math.PI/180;updateCandle();}});
wire('cnd-phi',  'v-cnd-phi',  '°',v=>{{cndPhi=v*Math.PI/180;updateCandle();}});
wire('cnd-dist', 'v-cnd-dist', '', v=>{{cndDist=v;updateCandle();}});
wire('cnd-int',  'v-cnd-int',  '', v=>{{cndInt=v;updateCandle();}});
wire('tng-theta','v-tng-theta','°',v=>{{tngTheta=v*Math.PI/180;updateTungsten();}});
wire('tng-phi',  'v-tng-phi',  '°',v=>{{tngPhi=v*Math.PI/180;updateTungsten();}});
wire('tng-dist', 'v-tng-dist', '', v=>{{tngDist=v;updateTungsten();}});
wire('tng-int',  'v-tng-int',  '', v=>{{tngInt=v;updateTungsten();}});
wire('exposure', 'v-exposure', '×',v=>{{exposure=v;renderer.toneMappingExposure=v;}});
(function(){{
  const el=document.getElementById('temp');
  if(el) el.addEventListener('input',()=>{{
    temperature=parseInt(el.value);
    document.getElementById('v-temp').textContent=temperature+' K';
    updateTemp();
  }});
  const et=document.getElementById('cosmo-time');
  if(et) et.addEventListener('input',()=>{{
    cosmoTime=parseInt(et.value);
    updateCosmoTime();
  }});
}})();

// ── Collapsible sections ──────────────────────────────────────────────────────
function toggleSection(badge){{
  badge.closest('.section').classList.toggle('collapsed');
}}

// ── Resize ────────────────────────────────────────────────────────────────────
function resize(){{
  const wrap=document.getElementById('canvas-wrap');
  const W=wrap.clientWidth, H=wrap.clientHeight;
  renderer.setSize(W,H,false);
  camera.aspect=W/H;
  camera.updateProjectionMatrix();
}}
window.addEventListener('resize',resize);
resize();

// ── Init ──────────────────────────────────────────────────────────────────────
updateCamera();
updateLightBox();
updateCandle();
updateTungsten();
updateObject();
updateTemp();
updateCosmoTime();

function animate(){{
  requestAnimationFrame(animate);
  renderer.render(scene,camera);
}}
animate();
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return str(output_path)
