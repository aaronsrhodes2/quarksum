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
    💡 <span id="hud-light">—</span><br>
    🌡 <span id="hud-temp">300 K</span>
  </div>
</div>

<div id="panel">
  <div class="panel-header">
    <h1>⚛ {title}</h1>
    <p>{subtitle[:80] if subtitle else ''}</p>
  </div>

  <div class="section">
    <div class="badge" onclick="toggleSection(this)">📷 OBSERVER</div>
    <div class="section-body">
    <div class="section-title">Camera</div>
    <div class="ctrl"><label>θ</label>
      <input type="range" id="cam-theta" min="-180" max="180" value="30" step="1">
      <span class="val" id="v-cam-theta">30°</span></div>
    <div class="ctrl"><label>φ</label>
      <input type="range" id="cam-phi" min="5" max="85" value="25" step="1">
      <span class="val" id="v-cam-phi">25°</span></div>
    <div class="ctrl"><label>r</label>
      <input type="range" id="cam-dist" min="{cam_min}" max="{cam_max}" value="{cam_default}" step="0.05">
      <span class="val" id="v-cam-dist">{cam_default}</span></div>
    <div class="ctrl"><label>fov</label>
      <input type="range" id="cam-fov" min="20" max="80" value="45" step="1">
      <span class="val" id="v-cam-fov">45°</span></div>
    <button class="rbtn" onclick="resetCam()">Reset Camera</button>
    </div>
  </div>

  <div class="section">
    <div class="badge" onclick="toggleSection(this)">📦 NON-OBSERVER</div>
    <div class="section-body">
    <div class="section-title">Object Orientation</div>
    <div class="ctrl"><label>Rx</label>
      <input type="range" id="obj-rx" min="-180" max="180" value="0" step="1">
      <span class="val" id="v-obj-rx">0°</span></div>
    <div class="ctrl"><label>Ry</label>
      <input type="range" id="obj-ry" min="-180" max="180" value="0" step="1">
      <span class="val" id="v-obj-ry">0°</span></div>
    <div class="ctrl"><label>Rz</label>
      <input type="range" id="obj-rz" min="-180" max="180" value="0" step="1">
      <span class="val" id="v-obj-rz">0°</span></div>
    <button class="rbtn" onclick="resetObj()">Reset Object</button>
    </div>
  </div>

  <div class="section">
    <div class="badge" onclick="toggleSection(this)">💡 LIGHT SOURCE</div>
    <div class="section-body">
    <div class="section-title">Key Light</div>
    <div class="ctrl"><label>θ</label>
      <input type="range" id="lt-theta" min="-180" max="180" value="45" step="1">
      <span class="val" id="v-lt-theta">45°</span></div>
    <div class="ctrl"><label>φ</label>
      <input type="range" id="lt-phi" min="5" max="85" value="50" step="1">
      <span class="val" id="v-lt-phi">50°</span></div>
    <div class="ctrl"><label>r</label>
      <input type="range" id="lt-dist" min="{cam_min}" max="{cam_max}" value="{round(cam_default*1.5,2)}" step="0.1">
      <span class="val" id="v-lt-dist">{round(cam_default*1.5,2)}</span></div>
    <div class="ctrl"><label>Iv</label>
      <input type="range" id="lt-int" min="0" max="5000" value="800" step="50">
      <span class="val" id="v-lt-int">800</span></div>
    <button class="rbtn" onclick="resetLight()">Reset Light</button>
    </div>
  </div>

  <div class="section">
    <div class="badge" onclick="toggleSection(this)">🎞 EXPOSURE</div>
    <div class="section-body">
    <div class="ctrl"><label>exp</label>
      <input type="range" id="exposure" min="0.25" max="8" value="1.5" step="0.05">
      <span class="val" id="v-exposure">1.5×</span></div>
    </div>
  </div>

  <div class="section">
    <div class="badge" onclick="toggleSection(this)">🕐 TIME → TEMPERATURE</div>
    <div class="section-body">
    <div class="section-title">Thermal State</div>
    <div class="ctrl"><label>T</label>
      <input type="range" id="temp" min="300" max="6000" value="300" step="50">
      <span class="val" id="v-temp">300 K</span></div>
    <div id="temp-swatch"></div>
    <div id="temp-desc">Room temperature — no emission</div>
    </div>
  </div>

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

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
'use strict';

// ── Material data ────────────────────────────────────────────────────────────
{materials_js}

// ── Thermal emission (blackbody approx) ─────────────────────────────────────
const THERMAL = {thermal_js};

// ── Scene state ──────────────────────────────────────────────────────────────
let camTheta = 30*Math.PI/180, camPhi = 25*Math.PI/180;
let camDist  = {cam_default}, camFov = 45;
let objRx=0, objRy=0, objRz=0;
let ltTheta=45*Math.PI/180, ltPhi=50*Math.PI/180;
let ltDist={round(cam_default*1.5,2)}, ltInt=800;
let temperature=300, exposure=1.5;
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

// Studio environment map for reflections
(function(){{
  const W=512,H=256;
  const cv=document.createElement('canvas');
  cv.width=W;cv.height=H;
  const ctx=cv.getContext('2d');
  const grad=ctx.createLinearGradient(0,0,0,H);
  grad.addColorStop(0.00,'#6070a0');
  grad.addColorStop(0.35,'#505060');
  grad.addColorStop(0.55,'#383840');
  grad.addColorStop(0.75,'#2c2820');
  grad.addColorStop(1.00,'#201810');
  ctx.fillStyle=grad; ctx.fillRect(0,0,W,H);
  const spot=ctx.createRadialGradient(W*.25,H*.20,0,W*.25,H*.20,H*.35);
  spot.addColorStop(0,'rgba(240,240,210,0.55)');
  spot.addColorStop(1,'rgba(240,240,210,0.00)');
  ctx.fillStyle=spot; ctx.fillRect(0,0,W,H);
  const tex=new THREE.CanvasTexture(cv);
  tex.mapping=THREE.EquirectangularReflectionMapping;
  scene.environment=tex;
}})();

const camera=new THREE.PerspectiveCamera(camFov,1,0.01,500);

// ── Default material fallback ────────────────────────────────────────────────
{default_mat_js}

// ── Object group ─────────────────────────────────────────────────────────────
const obj = new THREE.Group();

// Build layers from Sigma Signature
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
const hemi=new THREE.HemisphereLight(0x8090c0,0x302820,2.0);
scene.add(hemi);
const amb=new THREE.AmbientLight(0x404055,1.5);
scene.add(amb);
const keyLight=new THREE.PointLight(0xfff8f0,ltInt,500,2);
keyLight.castShadow=true;
keyLight.shadow.mapSize.set(1024,1024);
scene.add(keyLight);
const fillLight=new THREE.PointLight(0x8090c0,1200,300,2);
fillLight.position.set(-{round(cam_default*0.6,2)},{round(cam_default*0.3,2)},-{round(cam_default*0.5,2)});
scene.add(fillLight);
const rimLight=new THREE.PointLight(0xffe8c0,800,200,2);
rimLight.position.set(0,{round(cam_default*0.6,2)},-{round(cam_default*0.8,2)});
scene.add(rimLight);

// ── Mouse drag — left=object rotate, right=camera orbit ─────────────────────
let isDragging=false, rightDrag=false;
let lastX=0, lastY=0;
canvas.addEventListener('mousedown',e=>{{
  isDragging=true; rightDrag=(e.button===2);
  lastX=e.clientX; lastY=e.clientY; e.preventDefault();
}});
canvas.addEventListener('contextmenu',e=>e.preventDefault());
window.addEventListener('mouseup',()=>{{isDragging=false;}});
window.addEventListener('mousemove',e=>{{
  if(!isDragging) return;
  const dx=(e.clientX-lastX)*0.005, dy=(e.clientY-lastY)*0.005;
  if(!rightDrag){{
    // left drag — rotate the object (non-observer)
    objRy+=dx; objRx+=dy;
    setSlider('obj-ry',objRy*180/Math.PI,'v-obj-ry','°');
    setSlider('obj-rx',objRx*180/Math.PI,'v-obj-rx','°');
    updateObject();
  }} else {{
    // right drag — orbit camera (observer)
    camTheta-=dx; camPhi=Math.max(0.08,Math.min(Math.PI/2-0.05,camPhi-dy));
    setSlider('cam-theta',camTheta*180/Math.PI,'v-cam-theta','°');
    setSlider('cam-phi',camPhi*180/Math.PI,'v-cam-phi','°');
    updateCamera();
  }}
  lastX=e.clientX; lastY=e.clientY;
}});
canvas.addEventListener('wheel',e=>{{
  camDist=Math.max({cam_min},Math.min({cam_max},camDist+e.deltaY*0.01));
  document.getElementById('cam-dist').value=camDist;
  document.getElementById('v-cam-dist').textContent=camDist.toFixed(2);
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

function updateCamera(){{
  const p=spherePos(camTheta,camPhi,camDist);
  camera.position.set(p.x,p.y+LOOK_AT_Y,p.z);
  camera.lookAt(0,LOOK_AT_Y,0);
  camera.fov=camFov;
  camera.updateProjectionMatrix();
  document.getElementById('hud-cam').textContent=
    `θ${{(camTheta*180/Math.PI).toFixed(0)}}° φ${{(camPhi*180/Math.PI).toFixed(0)}}° r${{camDist.toFixed(1)}}`;
}}

function updateLight(){{
  const p=spherePos(ltTheta,ltPhi,ltDist);
  keyLight.position.set(p.x,p.y+LOOK_AT_Y,p.z);
  keyLight.intensity=ltInt;
  document.getElementById('hud-light').textContent=
    `θ${{(ltTheta*180/Math.PI).toFixed(0)}}° φ${{(ltPhi*180/Math.PI).toFixed(0)}}° I${{ltInt}}`;
}}

function updateObject(){{
  obj.rotation.set(objRx,objRy,objRz);
}}

// ── Thermal emission update ───────────────────────────────────────────────────
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
  Object.values(MATS).forEach(m=>{{
    m.emissive=emC; m.emissiveIntensity=emI;
  }});
  const sw=document.getElementById('temp-swatch');
  sw.style.background=`rgb(${{(tc.r*255)|0}},${{(tc.g*255)|0}},${{(tc.b*255)|0}})`;
  document.getElementById('temp-desc').textContent=tempDesc(temperature);
  document.getElementById('hud-temp').textContent=temperature+' K';
}}

// ── Material selection ────────────────────────────────────────────────────────
function selectMat(id){{
  document.querySelectorAll('.mat-card').forEach(c=>c.classList.remove('active'));
  const card=document.querySelector(`[data-mat="${{id}}"]`);
  if(card) card.classList.add('active');
}}

// ── Reset functions ───────────────────────────────────────────────────────────
function resetCam(){{
  camTheta=30*Math.PI/180; camPhi=25*Math.PI/180;
  camDist={cam_default}; camFov=45;
  setSlider('cam-theta',30,'v-cam-theta','°');
  setSlider('cam-phi',25,'v-cam-phi','°');
  setSlider('cam-dist',camDist,'v-cam-dist','');
  setSlider('cam-fov',45,'v-cam-fov','°');
  updateCamera();
}}
function resetObj(){{
  objRx=0;objRy=0;objRz=0;
  setSlider('obj-rx',0,'v-obj-rx','°');
  setSlider('obj-ry',0,'v-obj-ry','°');
  setSlider('obj-rz',0,'v-obj-rz','°');
  updateObject();
}}
function resetLight(){{
  ltTheta=45*Math.PI/180; ltPhi=50*Math.PI/180;
  ltDist={round(cam_default*1.5,2)}; ltInt=800;
  setSlider('lt-theta',45,'v-lt-theta','°');
  setSlider('lt-phi',50,'v-lt-phi','°');
  setSlider('lt-dist',ltDist,'v-lt-dist','');
  setSlider('lt-int',5000,'v-lt-int','');
  updateLight();
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
wire('cam-theta','v-cam-theta','°',v=>{{camTheta=v*Math.PI/180;updateCamera();}});
wire('cam-phi',  'v-cam-phi',  '°',v=>{{camPhi=v*Math.PI/180;updateCamera();}});
wire('cam-dist', 'v-cam-dist', '', v=>{{camDist=v;updateCamera();}});
wire('cam-fov',  'v-cam-fov',  '°',v=>{{camFov=v;updateCamera();}});
wire('obj-rx','v-obj-rx','°',v=>{{objRx=v*Math.PI/180;updateObject();}});
wire('obj-ry','v-obj-ry','°',v=>{{objRy=v*Math.PI/180;updateObject();}});
wire('obj-rz','v-obj-rz','°',v=>{{objRz=v*Math.PI/180;updateObject();}});
wire('lt-theta','v-lt-theta','°',v=>{{ltTheta=v*Math.PI/180;updateLight();}});
wire('lt-phi',  'v-lt-phi',  '°',v=>{{ltPhi=v*Math.PI/180;updateLight();}});
wire('lt-dist', 'v-lt-dist', '', v=>{{ltDist=v;updateLight();}});
wire('lt-int',  'v-lt-int',  '', v=>{{ltInt=v;updateLight();}});
wire('exposure','v-exposure','×',v=>{{
  exposure=v;renderer.toneMappingExposure=v;
}});
(function(){{
  const el=document.getElementById('temp');
  if(!el) return;
  el.addEventListener('input',()=>{{
    temperature=parseInt(el.value);
    document.getElementById('v-temp').textContent=temperature+' K';
    updateTemp();
  }});
}})();

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

// ── Collapsible sections ──────────────────────────────────────────────────────
function toggleSection(badge){{
  badge.closest('.section').classList.toggle('collapsed');
}}

// ── Animate ───────────────────────────────────────────────────────────────────
updateCamera();
updateLight();
updateObject();
updateTemp();

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
