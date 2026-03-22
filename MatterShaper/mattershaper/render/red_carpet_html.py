"""
red_carpet_html — Interactive HTML renderer for the Entangler physics pipeline.

Produces a self-contained HTML file with:
  - Three.js WebGL rendering of the scene
  - Observer (camera) position controls — theta / phi / distance
  - Non-Observer (subject) controls — object rotation Rx / Ry / Rz
  - Light source controls — theta / phi / intensity
  - Time slider → temperature (K) → thermal emission color
  - 3D rotation via mouse drag (left = camera orbit, right = object spin)
  - Physics material params displayed in HUD

The HTML file has zero external dependencies at runtime except:
  Three.js r128  (cdnjs.cloudflare.com)

Usage:
    from mattershaper.render.red_carpet_html import red_carpet_html

    red_carpet_html(
        scene='beercan',
        material=mat,             # Material instance from physics_materials
        geometry={
            'type': 'beercan',
            'diameter_in': 3.5,
            'height_in': 6.5,
        },
        thermal_steps=thermal_data,   # list of (T, r, g, b) tuples
        output_html='/path/to/out.html',
        title='My Can',
    )

□σ = −ξR
"""

import os
import math
import json


# ── Thermal emission data embedded as JS ──────────────────────────────────

def _thermal_js(steps):
    """Convert (T, r, g, b) tuples to a JS array literal."""
    entries = [f"  {{ T:{T}, r:{r:.4f}, g:{g:.4f}, b:{b:.4f} }}" for T, r, g, b in steps]
    return "[\n" + ",\n".join(entries) + "\n]"


# ── HTML template ──────────────────────────────────────────────────────────

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0e0e10; color:#e0e0e0; font-family:'Courier New',monospace;
          display:flex; height:100vh; overflow:hidden; }}

  #canvas-wrap {{ flex:1; position:relative; }}
  canvas {{ display:block; width:100%; height:100%; }}

  #panel {{
    width:280px; min-width:280px;
    background:#141416;
    border-left:1px solid #2a2a30;
    display:flex; flex-direction:column;
    overflow-y:auto;
  }}

  .panel-header {{
    background:#1e1e24;
    padding:12px 14px 10px;
    border-bottom:1px solid #2a2a30;
  }}
  .panel-header h1 {{
    font-size:12px; letter-spacing:2px; color:#ffd700;
    text-transform:uppercase;
  }}
  .panel-header p {{
    font-size:10px; color:#666; margin-top:3px;
  }}

  .section {{
    padding:12px 14px;
    border-bottom:1px solid #1e1e24;
  }}
  .section-title {{
    font-size:10px; letter-spacing:1.5px; color:#888;
    text-transform:uppercase; margin-bottom:8px;
  }}

  .control-row {{
    display:flex; align-items:center; margin-bottom:6px; gap:6px;
  }}
  .control-row label {{
    font-size:11px; color:#aaa; width:28px; flex-shrink:0;
  }}
  .control-row input[type=range] {{
    flex:1; height:4px; accent-color:#ffd700;
    cursor:pointer;
  }}
  .control-row .val {{
    font-size:10px; color:#ffd700; width:52px; text-align:right;
    flex-shrink:0;
  }}

  #temp-swatch {{
    width:100%; height:18px; border-radius:3px;
    margin-top:6px;
    border:1px solid #333;
  }}

  .mat-grid {{
    display:grid; grid-template-columns:1fr 1fr;
    gap:4px 10px;
  }}
  .mat-cell {{
    font-size:10px;
  }}
  .mat-cell .k {{ color:#666; }}
  .mat-cell .v {{ color:#0cf; }}

  #hud {{
    position:absolute; top:10px; left:10px;
    font-size:10px; color:#555;
    pointer-events:none;
    user-select:none;
  }}
  #hud span {{ color:#888; }}

  .badge {{
    display:inline-block;
    background:#ffd70022;
    border:1px solid #ffd70044;
    border-radius:3px;
    padding:1px 6px;
    font-size:9px;
    color:#ffd700;
    letter-spacing:1px;
    margin-bottom:6px;
  }}

  button.reset-btn {{
    background:#1e1e24;
    border:1px solid #333;
    color:#aaa;
    font-size:10px;
    font-family:inherit;
    padding:4px 10px;
    border-radius:3px;
    cursor:pointer;
    margin-top:6px;
    width:100%;
  }}
  button.reset-btn:hover {{ background:#252530; color:#ffd700; }}
</style>
</head>
<body>

<div id="canvas-wrap">
  <canvas id="c"></canvas>
  <div id="hud">
    🎥 <span id="hud-cam">cam</span> &nbsp;|&nbsp;
    💡 <span id="hud-light">light</span> &nbsp;|&nbsp;
    🌡 <span id="hud-temp">300K</span>
  </div>
</div>

<div id="panel">
  <div class="panel-header">
    <h1>⚛ Physics Renderer</h1>
    <p>{subtitle}</p>
  </div>

  <!-- OBSERVER (camera) -->
  <div class="section">
    <div class="badge">📷 OBSERVER</div>
    <div class="section-title">Camera Position</div>

    <div class="control-row">
      <label>θ</label>
      <input type="range" id="cam-theta" min="-180" max="180" value="30" step="1">
      <span class="val" id="v-cam-theta">30°</span>
    </div>
    <div class="control-row">
      <label>φ</label>
      <input type="range" id="cam-phi" min="5" max="85" value="25" step="1">
      <span class="val" id="v-cam-phi">25°</span>
    </div>
    <div class="control-row">
      <label>r</label>
      <input type="range" id="cam-dist" min="4" max="30" value="12" step="0.5">
      <span class="val" id="v-cam-dist">12.0"</span>
    </div>
    <div class="control-row">
      <label>fov</label>
      <input type="range" id="cam-fov" min="20" max="80" value="45" step="1">
      <span class="val" id="v-cam-fov">45°</span>
    </div>
    <button class="reset-btn" onclick="resetCam()">Reset Camera</button>
  </div>

  <!-- NON-OBSERVER (object) -->
  <div class="section">
    <div class="badge">📦 NON-OBSERVER</div>
    <div class="section-title">Object Orientation</div>

    <div class="control-row">
      <label>Rx</label>
      <input type="range" id="obj-rx" min="-180" max="180" value="0" step="1">
      <span class="val" id="v-obj-rx">0°</span>
    </div>
    <div class="control-row">
      <label>Ry</label>
      <input type="range" id="obj-ry" min="-180" max="180" value="0" step="1">
      <span class="val" id="v-obj-ry">0°</span>
    </div>
    <div class="control-row">
      <label>Rz</label>
      <input type="range" id="obj-rz" min="-180" max="180" value="0" step="1">
      <span class="val" id="v-obj-rz">0°</span>
    </div>
    <button class="reset-btn" onclick="resetObj()">Reset Object</button>
  </div>

  <!-- LIGHT -->
  <div class="section">
    <div class="badge">💡 LIGHT SOURCE</div>
    <div class="section-title">Key Light</div>

    <div class="control-row">
      <label>θ</label>
      <input type="range" id="lt-theta" min="-180" max="180" value="45" step="1">
      <span class="val" id="v-lt-theta">45°</span>
    </div>
    <div class="control-row">
      <label>φ</label>
      <input type="range" id="lt-phi" min="5" max="85" value="50" step="1">
      <span class="val" id="v-lt-phi">50°</span>
    </div>
    <div class="control-row">
      <label>r</label>
      <input type="range" id="lt-dist" min="4" max="30" value="15" step="0.5">
      <span class="val" id="v-lt-dist">15.0"</span>
    </div>
    <div class="control-row">
      <label>Iv</label>
      <input type="range" id="lt-int" min="0" max="20000" value="5000" step="100">
      <span class="val" id="v-lt-int">5000</span>
    </div>
    <button class="reset-btn" onclick="resetLight()">Reset Light</button>
  </div>

  <!-- EXPOSURE -->
  <div class="section">
    <div class="badge">🎞 EXPOSURE</div>
    <div class="section-title">Tone Mapping</div>

    <div class="control-row">
      <label>exp</label>
      <input type="range" id="exposure" min="0.25" max="8" value="2.5" step="0.05">
      <span class="val" id="v-exposure">2.5×</span>
    </div>
    <div style="font-size:9px;color:#555;margin-top:4px;">
      ACES filmic — adjust for scene brightness
    </div>
  </div>

  <!-- TIME / TEMPERATURE -->
  <div class="section">
    <div class="badge">🕐 TIME → TEMPERATURE</div>
    <div class="section-title">Thermal State</div>

    <div class="control-row">
      <label>T</label>
      <input type="range" id="temp" min="300" max="6000" value="300" step="100">
      <span class="val" id="v-temp">300K</span>
    </div>
    <div id="temp-swatch"></div>
    <div style="font-size:10px;color:#666;margin-top:5px;" id="temp-desc">
      Room temperature — no thermal emission
    </div>
  </div>

  <!-- MATERIAL PARAMS -->
  <div class="section">
    <div class="badge">⚗ MATERIAL PHYSICS</div>
    <div class="section-title">{mat_name}</div>
    <div class="mat-grid">
      <div class="mat-cell"><span class="k">R</span> <span class="v">{mat_r:.4f}</span></div>
      <div class="mat-cell"><span class="k">G</span> <span class="v">{mat_g:.4f}</span></div>
      <div class="mat-cell"><span class="k">B</span> <span class="v">{mat_b:.4f}</span></div>
      <div class="mat-cell"><span class="k">ρ</span> <span class="v">{mat_refl:.4f}</span></div>
      <div class="mat-cell"><span class="k">α</span> <span class="v">{mat_rough:.4f}</span></div>
      <div class="mat-cell"><span class="k">Z</span> <span class="v">{mat_Z}</span></div>
      <div class="mat-cell"><span class="k">A</span> <span class="v">{mat_A}</span></div>
      <div class="mat-cell"><span class="k">kg/m³</span> <span class="v">{mat_den}</span></div>
    </div>
    <div style="font-size:9px;color:#444;margin-top:8px;">
      {mat_origin}
    </div>
  </div>

  <!-- GEOMETRY INFO -->
  <div class="section">
    <div class="badge">📐 GEOMETRY</div>
    <div class="section-title">{geom_desc}</div>
    <div style="font-size:9px;color:#555;">
      □σ = −ξR &nbsp;|&nbsp; Quarksum Physics Engine
    </div>
  </div>

</div><!-- panel -->

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
'use strict';

// ── Physics material parameters (from quarksum) ────────────────────────
const MAT = {{
  color:       {{ r:{mat_r:.4f}, g:{mat_g:.4f}, b:{mat_b:.4f} }},
  reflectance: {mat_refl:.4f},
  roughness:   {mat_rough:.4f},
}};

// ── Thermal emission lookup table (from local_library thermal_emission) ─
const THERMAL = {thermal_js};

// ── Scene state ────────────────────────────────────────────────────────
let camTheta  = 30 * Math.PI / 180;
let camPhi    = 25 * Math.PI / 180;
let camDist   = 12.0;
let camFov    = 45;
let objRx = 0, objRy = 0, objRz = 0;
let ltTheta = 45 * Math.PI / 180;
let ltPhi   = 50 * Math.PI / 180;
let ltDist  = 15.0;
let ltInt   = 5000;
let temperature = 300;
let exposure    = 2.5;

// ── Three.js Setup ─────────────────────────────────────────────────────
const canvas   = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{ canvas, antialias:true }});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.physicallyCorrectLights = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = exposure;
renderer.outputEncoding = THREE.sRGBEncoding;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e0e10);

// ── Environment map — aluminum reflects its surroundings (Drude model).
// Without an env map, a smooth metal with ρ≈0.90 just mirrors black space.
// This gradient canvas gives the can a studio-like environment to reflect.
(function buildEnvMap() {{
  const W = 512, H = 256;
  const cvs = document.createElement('canvas');
  cvs.width = W; cvs.height = H;
  const ctx = cvs.getContext('2d');

  // Sky-to-ground gradient — approximates a photographic studio
  // Top (sky): cool blue-grey; horizon: neutral mid; bottom: warm dark
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0.00, '#6070a0'); // sky — cool blue
  grad.addColorStop(0.35, '#505060'); // upper mid
  grad.addColorStop(0.55, '#383840'); // horizon
  grad.addColorStop(0.75, '#2c2820'); // lower mid — warm shadow
  grad.addColorStop(1.00, '#201810'); // ground — dark warm
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Soft bright patch at upper-left — key light direction
  const spot = ctx.createRadialGradient(W*0.25, H*0.20, 0, W*0.25, H*0.20, H*0.35);
  spot.addColorStop(0, 'rgba(240,240,210,0.55)');
  spot.addColorStop(1, 'rgba(240,240,210,0.00)');
  ctx.fillStyle = spot;
  ctx.fillRect(0, 0, W, H);

  const tex = new THREE.CanvasTexture(cvs);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  // Assign as scene environment (reflections) but NOT as background
  scene.environment = tex;
}})();

const camera = new THREE.PerspectiveCamera(camFov, 1, 0.1, 200);

// ── Beer Can Geometry ─────────────────────────────────────────────────
// Profile: (radius, y) pairs — y=0 is bottom, y=6.5 is top lid
// Dimensions: 3.5" dia (1.75" radius), 6.5" tall.  1 unit = 1 inch.
const canProfile = [
  // Bottom rim and chamfer
  new THREE.Vector2(0.00, 0.00),   // centre of bottom dome
  new THREE.Vector2(0.80, 0.00),
  new THREE.Vector2(1.50, 0.08),
  new THREE.Vector2(1.62, 0.18),
  new THREE.Vector2(1.74, 0.35),   // body starts
  // Long straight body
  new THREE.Vector2(1.75, 0.50),
  new THREE.Vector2(1.75, 5.40),
  // Shoulder taper
  new THREE.Vector2(1.74, 5.55),
  new THREE.Vector2(1.68, 5.75),
  new THREE.Vector2(1.50, 5.95),
  new THREE.Vector2(1.28, 6.08),
  new THREE.Vector2(1.10, 6.18),
  // Neck / top rim
  new THREE.Vector2(1.05, 6.30),
  new THREE.Vector2(1.04, 6.38),
  new THREE.Vector2(1.05, 6.50),   // top edge
];

// Close the profile at the top (lid disc is added separately)
const canGeo = new THREE.LatheGeometry(canProfile, 96);
canGeo.computeVertexNormals();

// Lid disc (top face at y=6.5)
const lidGeo  = new THREE.CircleGeometry(1.04, 96);
lidGeo.rotateX(Math.PI / 2);
lidGeo.translate(0, 6.50, 0);

// Pull tab — flat rectangular loop raised slightly above lid
const tabGeo  = new THREE.TorusGeometry(0.22, 0.04, 8, 24, Math.PI);
tabGeo.rotateX(Math.PI / 2);
tabGeo.translate(0.30, 6.60, 0);

const tabBodyGeo = new THREE.BoxGeometry(0.55, 0.08, 0.10);
tabBodyGeo.translate(0.30, 6.60, 0);

// ── Material ────────────────────────────────────────────────────────────
const matColor = new THREE.Color(MAT.color.r, MAT.color.g, MAT.color.b);

const canMat = new THREE.MeshStandardMaterial({{
  color:       matColor,
  metalness:   MAT.reflectance,
  roughness:   MAT.roughness,
  emissive:    new THREE.Color(0, 0, 0),
  emissiveIntensity: 0,
}});

const tabMat = new THREE.MeshStandardMaterial({{
  color:    new THREE.Color(0.75, 0.75, 0.78),
  metalness: 0.9,
  roughness: 0.25,
}});

// ── Meshes ──────────────────────────────────────────────────────────────
const can    = new THREE.Mesh(canGeo,  canMat);
const lid    = new THREE.Mesh(lidGeo,  canMat);
const tab    = new THREE.Mesh(tabGeo,  tabMat);
const tabBod = new THREE.Mesh(tabBodyGeo, tabMat);

// Group everything — y-centre = 3.25" (half of 6.5")
const canGroup = new THREE.Group();
canGroup.add(can, lid, tab, tabBod);
canGroup.position.set(0, -3.25, 0);   // centre the can at world origin
scene.add(canGroup);

// Shadow-receiving ground plane (subtle)
const groundGeo = new THREE.PlaneGeometry(60, 60);
const groundMat = new THREE.MeshStandardMaterial({{
  color:     new THREE.Color(0.06, 0.06, 0.07),
  metalness: 0.0,
  roughness: 0.9,
}});
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -3.40;
ground.receiveShadow = true;
scene.add(ground);

// ── Lights ──────────────────────────────────────────────────────────────
// Aluminum is ~90% reflective (Drude free electrons). It needs both
// point lights (for specular highlights) AND an environment to reflect.
// physicallyCorrectLights=true: PointLight intensity is in candela,
// falloff ∝ 1/r². At r=15 scene-units, I=5000 → E≈22 (indoor studio).

// Hemisphere — sky/ground ambient; gives metals a color gradient to reflect
const hemiLight = new THREE.HemisphereLight(0x8090c0, 0x302820, 2.0);
scene.add(hemiLight);

// Minimal fill ambient (so shadow sides aren't pitch black)
const ambLight = new THREE.AmbientLight(0x404055, 1.5);
scene.add(ambLight);

// Key light (user-controlled) — main studio strobe
const keyLight = new THREE.PointLight(0xfff8f0, ltInt, 200, 2);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(1024, 1024);
scene.add(keyLight);

// Fill light (fixed, opposite side — cool tone; half key intensity)
const fillLight = new THREE.PointLight(0x8090c0, 1200, 120, 2);
fillLight.position.set(-8, 4, -6);
scene.add(fillLight);

// Rim / back light (fixed, behind the can — warm highlight)
const rimLight = new THREE.PointLight(0xffe8c0, 800, 100, 2);
rimLight.position.set(0, 8, -12);
scene.add(rimLight);

// Ground bounce (fixed, below — warm grey)
const bounceLight = new THREE.PointLight(0x604848, 400, 60, 2);
bounceLight.position.set(0, -4, 5);
scene.add(bounceLight);

// ── Camera + light positioning helpers ─────────────────────────────────
function spherePos(theta, phi, r) {{
  return {{
    x: r * Math.cos(phi) * Math.sin(theta),
    y: r * Math.sin(phi),
    z: r * Math.cos(phi) * Math.cos(theta),
  }};
}}

function updateCamera() {{
  const p = spherePos(camTheta, camPhi, camDist);
  camera.position.set(p.x, p.y, p.z);
  camera.lookAt(0, 0, 0);
  camera.fov = camFov;
  camera.updateProjectionMatrix();
  document.getElementById('hud-cam').textContent =
    `θ${{Math.round(camTheta*180/Math.PI)}}° φ${{Math.round(camPhi*180/Math.PI)}}° r${{camDist.toFixed(1)}}"`;
}}

function updateLight() {{
  const p = spherePos(ltTheta, ltPhi, ltDist);
  keyLight.position.set(p.x, p.y, p.z);
  keyLight.intensity = ltInt;
  document.getElementById('hud-light').textContent =
    `θ${{Math.round(ltTheta*180/Math.PI)}}° φ${{Math.round(ltPhi*180/Math.PI)}}° Iv${{ltInt}}`;
}}

function updateObject() {{
  canGroup.rotation.set(
    objRx * Math.PI / 180,
    objRy * Math.PI / 180,
    objRz * Math.PI / 180,
  );
}}

// ── Thermal emission interpolation ─────────────────────────────────────
function thermalColor(T) {{
  if (T <= 300) return {{ r:0, g:0, b:0, intensity:0 }};
  // Find surrounding entries
  let lo = THERMAL[0], hi = THERMAL[THERMAL.length - 1];
  for (let i = 0; i < THERMAL.length - 1; i++) {{
    if (THERMAL[i].T <= T && THERMAL[i+1].T >= T) {{
      lo = THERMAL[i]; hi = THERMAL[i+1]; break;
    }}
  }}
  const t = (T - lo.T) / Math.max(1, hi.T - lo.T);
  const r = lo.r + (hi.r - lo.r) * t;
  const g = lo.g + (hi.g - lo.g) * t;
  const b = lo.b + (hi.b - lo.b) * t;
  // Intensity ramps from 0 at Draper (700K) to 1 at 6000K
  const intensity = Math.min(1.0, Math.max(0, (T - 700) / 5300)) * 1.5;
  return {{ r, g, b, intensity }};
}}

function thermalDesc(T) {{
  if (T < 700)  return 'Room temperature — no thermal emission';
  if (T < 900)  return 'Draper point — first faint red glow (barely visible)';
  if (T < 1200) return 'Dark red — incandescent but dim';
  if (T < 1800) return 'Orange-red — typical molten metal glow';
  if (T < 2500) return 'Bright orange — metal melting range';
  if (T < 4000) return 'Yellow-orange — arc furnace / plasma';
  if (T < 5500) return 'Yellow-white — hotter than the solar corona';
  return 'Near-white — ~solar surface temperature (5778K)';
}}

function updateThermal() {{
  const tc = thermalColor(temperature);
  canMat.emissive.setRGB(tc.r, tc.g, tc.b);
  canMat.emissiveIntensity = tc.intensity;

  // Update swatch
  const sw = document.getElementById('temp-swatch');
  if (tc.intensity > 0) {{
    const rh = Math.round(tc.r * 255);
    const gh = Math.round(tc.g * 255);
    const bh = Math.round(tc.b * 255);
    sw.style.background = `rgb(${{rh}},${{gh}},${{bh}})`;
    sw.style.boxShadow = `0 0 ${{Math.round(tc.intensity*12)}}px rgb(${{rh}},${{gh}},${{bh}})`;
  }} else {{
    sw.style.background = '#1a1a1c';
    sw.style.boxShadow = 'none';
  }}

  document.getElementById('temp-desc').textContent = thermalDesc(temperature);
  document.getElementById('hud-temp').textContent = temperature + 'K';
}}

// ── Slider wiring ───────────────────────────────────────────────────────
function wire(id, valId, suffix, scale, onchange) {{
  const el = document.getElementById(id);
  const vl = document.getElementById(valId);
  el.addEventListener('input', () => {{
    const raw = parseFloat(el.value);
    vl.textContent = (raw * (scale||1)).toFixed(suffix === '°' ? 0 : 1) + (suffix||'');
    onchange(raw);
  }});
}}

wire('cam-theta', 'v-cam-theta', '°', 1, v => {{ camTheta = v * Math.PI/180; updateCamera(); }});
wire('cam-phi',   'v-cam-phi',   '°', 1, v => {{ camPhi   = v * Math.PI/180; updateCamera(); }});
wire('cam-dist',  'v-cam-dist',  '"', 1, v => {{ camDist  = v;               updateCamera(); }});
wire('cam-fov',   'v-cam-fov',   '°', 1, v => {{ camFov   = v;               updateCamera(); }});

wire('obj-rx', 'v-obj-rx', '°', 1, v => {{ objRx = v; updateObject(); }});
wire('obj-ry', 'v-obj-ry', '°', 1, v => {{ objRy = v; updateObject(); }});
wire('obj-rz', 'v-obj-rz', '°', 1, v => {{ objRz = v; updateObject(); }});

wire('lt-theta', 'v-lt-theta', '°',  1, v => {{ ltTheta = v * Math.PI/180; updateLight(); }});
wire('lt-phi',   'v-lt-phi',   '°',  1, v => {{ ltPhi   = v * Math.PI/180; updateLight(); }});
wire('lt-dist',  'v-lt-dist',  '"',  1, v => {{ ltDist  = v;               updateLight(); }});
wire('lt-int',   'v-lt-int',   '',   1, v => {{ ltInt   = v;               updateLight(); }});

document.getElementById('exposure').addEventListener('input', function() {{
  exposure = parseFloat(this.value);
  document.getElementById('v-exposure').textContent = exposure.toFixed(2) + '×';
  renderer.toneMappingExposure = exposure;
}});

document.getElementById('temp').addEventListener('input', function() {{
  temperature = parseInt(this.value);
  document.getElementById('v-temp').textContent = temperature + 'K';
  updateThermal();
}});

// ── Mouse drag — camera orbit (left) + object spin (right) ────────────
let drag = null;
canvas.addEventListener('mousedown', e => {{
  drag = {{ btn: e.button, x: e.clientX, y: e.clientY }};
}});
window.addEventListener('mousemove', e => {{
  if (!drag) return;
  const dx = e.clientX - drag.x;
  const dy = e.clientY - drag.y;
  drag.x = e.clientX; drag.y = e.clientY;

  if (drag.btn === 0) {{
    // Left drag → orbit camera
    camTheta -= dx * 0.008;
    camPhi = Math.max(2*Math.PI/180, Math.min(88*Math.PI/180, camPhi - dy*0.005));
    // Sync sliders
    document.getElementById('cam-theta').value = Math.round(camTheta * 180/Math.PI);
    document.getElementById('v-cam-theta').textContent = Math.round(camTheta*180/Math.PI) + '°';
    document.getElementById('cam-phi').value = Math.round(camPhi * 180/Math.PI);
    document.getElementById('v-cam-phi').textContent = Math.round(camPhi*180/Math.PI) + '°';
    updateCamera();
  }} else if (drag.btn === 2) {{
    // Right drag → spin object
    objRy += dx * 0.5;
    objRx += dy * 0.3;
    document.getElementById('obj-ry').value = (objRy % 360).toFixed(0);
    document.getElementById('v-obj-ry').textContent = Math.round(objRy % 360) + '°';
    document.getElementById('obj-rx').value = (objRx % 360).toFixed(0);
    document.getElementById('v-obj-rx').textContent = Math.round(objRx % 360) + '°';
    updateObject();
  }}
}});
window.addEventListener('mouseup', () => drag = null);
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('wheel', e => {{
  camDist = Math.max(4, Math.min(30, camDist + e.deltaY * 0.02));
  document.getElementById('cam-dist').value = camDist.toFixed(1);
  document.getElementById('v-cam-dist').textContent = camDist.toFixed(1) + '"';
  updateCamera();
  e.preventDefault();
}}, {{ passive:false }});

// Touch support
let lastTouch = null;
canvas.addEventListener('touchstart', e => {{
  if (e.touches.length === 1) lastTouch = {{ x:e.touches[0].clientX, y:e.touches[0].clientY }};
}});
canvas.addEventListener('touchmove', e => {{
  if (!lastTouch || e.touches.length !== 1) return;
  const dx = e.touches[0].clientX - lastTouch.x;
  const dy = e.touches[0].clientY - lastTouch.y;
  lastTouch = {{ x:e.touches[0].clientX, y:e.touches[0].clientY }};
  camTheta -= dx * 0.01;
  camPhi = Math.max(2*Math.PI/180, Math.min(88*Math.PI/180, camPhi - dy*0.006));
  updateCamera();
  e.preventDefault();
}}, {{ passive:false }});

// ── Reset functions ─────────────────────────────────────────────────────
function resetCam() {{
  camTheta = 30*Math.PI/180; camPhi = 25*Math.PI/180; camDist = 12; camFov = 45;
  document.getElementById('cam-theta').value = 30;
  document.getElementById('cam-phi').value   = 25;
  document.getElementById('cam-dist').value  = 12;
  document.getElementById('cam-fov').value   = 45;
  document.getElementById('v-cam-theta').textContent = '30°';
  document.getElementById('v-cam-phi').textContent   = '25°';
  document.getElementById('v-cam-dist').textContent  = '12.0"';
  document.getElementById('v-cam-fov').textContent   = '45°';
  updateCamera();
}}
function resetObj() {{
  objRx = 0; objRy = 0; objRz = 0;
  ['obj-rx','obj-ry','obj-rz'].forEach(id => document.getElementById(id).value = 0);
  ['v-obj-rx','v-obj-ry','v-obj-rz'].forEach(id => document.getElementById(id).textContent = '0°');
  updateObject();
}}
function resetLight() {{
  ltTheta = 45*Math.PI/180; ltPhi = 50*Math.PI/180; ltDist = 15; ltInt = 5000;
  document.getElementById('lt-theta').value = 45;
  document.getElementById('lt-phi').value   = 50;
  document.getElementById('lt-dist').value  = 15;
  document.getElementById('lt-int').value   = 5000;
  document.getElementById('v-lt-theta').textContent = '45°';
  document.getElementById('v-lt-phi').textContent   = '50°';
  document.getElementById('v-lt-dist').textContent  = '15.0"';
  document.getElementById('v-lt-int').textContent   = '5000';
  updateLight();
  // Reset exposure
  exposure = 2.5;
  document.getElementById('exposure').value = 2.5;
  document.getElementById('v-exposure').textContent = '2.50×';
  renderer.toneMappingExposure = 2.5;
}}

// ── Resize ──────────────────────────────────────────────────────────────
function onResize() {{
  const wrap = document.getElementById('canvas-wrap');
  const w = wrap.clientWidth, h = wrap.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}}
window.addEventListener('resize', onResize);

// ── Render loop ─────────────────────────────────────────────────────────
function animate() {{
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
}}

// ── Init ────────────────────────────────────────────────────────────────
onResize();
updateCamera();
updateLight();
updateObject();
updateThermal();
animate();

</script>
</body>
</html>
"""


def red_carpet_html(
    scene,
    output_html,
    *,
    title='SKIPPY — Physics Renderer',
    material=None,
    geometry=None,
    thermal_steps=None,
    subtitle=None,
):
    """Generate an interactive HTML physics renderer.

    Parameters
    ----------
    scene : str
        Scene identifier (currently 'beercan' is the primary scene).
    output_html : str
        Output path for the .html file.
    title : str
        Page/title bar text.
    material : Material
        Physics-derived Material instance. If None, uses aluminum fallback.
    geometry : dict
        Geometry specification with 'type' key. E.g.:
            {'type': 'beercan', 'diameter_in': 3.5, 'height_in': 6.5}
    thermal_steps : list of (T, r, g, b)
        Thermal emission data. If None, uses embedded aluminum defaults.
    subtitle : str
        Short subtitle shown under title in panel.

    Returns
    -------
    str
        Path to the generated HTML file.
    """
    # ── Material params ──
    if material is not None:
        mat_r = material.color.x
        mat_g = material.color.y
        mat_b = material.color.z
        mat_refl  = float(material.reflectance)
        mat_rough = float(material.roughness)
        mat_name  = material.name
        mat_Z     = getattr(material, 'mean_Z', 13)
        mat_A     = getattr(material, 'mean_A', 27)
        mat_den   = int(getattr(material, 'density_kg_m3', 2700))
        mat_comp  = getattr(material, 'composition', 'Al')
    else:
        mat_r, mat_g, mat_b = 0.9018, 0.9186, 0.9375
        mat_refl, mat_rough = 1.0, 0.12
        mat_name = 'Aluminum (fallback)'
        mat_Z, mat_A, mat_den, mat_comp = 13, 27, 2700, 'Al (FCC)'

    mat_origin = (
        f'Color: Drude/Fresnel FIRST_PRINCIPLES. '
        f'Reflectance: specular_fraction MEASURED. '
        f'Roughness: microfacet MEASURED. '
        f'σ-INVARIANT (EM).'
    )

    # ── Geometry description ──
    if geometry is None:
        geometry = {'type': 'beercan', 'diameter_in': 3.5, 'height_in': 6.5}
    gtype = geometry.get('type', 'beercan')
    dia   = geometry.get('diameter_in', 3.5)
    ht    = geometry.get('height_in', 6.5)
    geom_desc = f'{gtype} — ⌀{dia}" × {ht}" | LatheGeometry 96-seg'

    # ── Thermal steps ──
    if thermal_steps is None:
        thermal_steps = [
            (300,  0.000, 0.000, 0.000),
            (700,  1.000, 0.006, 0.000),
            (900,  1.000, 0.022, 0.000),
            (1000, 1.000, 0.034, 0.000),
            (1200, 1.000, 0.067, 0.001),
            (1500, 1.000, 0.131, 0.006),
            (2000, 1.000, 0.256, 0.029),
            (3000, 1.000, 0.500, 0.151),
            (4000, 1.000, 0.697, 0.341),
            (5778, 1.000, 0.942, 0.717),
        ]

    if subtitle is None:
        subtitle = f'{mat_name} · ⌀{dia}" × {ht}" · quarksum physics'

    # ── Render HTML ──
    html = _HTML_TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        thermal_js=_thermal_js(thermal_steps),
        mat_r=mat_r, mat_g=mat_g, mat_b=mat_b,
        mat_refl=mat_refl, mat_rough=mat_rough,
        mat_name=mat_name,
        mat_Z=mat_Z, mat_A=mat_A, mat_den=mat_den,
        mat_origin=mat_origin,
        geom_desc=geom_desc,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(output_html) / 1024
    print(f'  ✓  {output_html}  ({size_kb:.0f} KB)')
    return output_html
