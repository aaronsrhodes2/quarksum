"""
Nagatha's Gallery — FastAPI backend.

Serves the 3D viewer frontend, manages object inventory,
triggers entangler renders, and generates interactive HTML scenes.
"""

import sys
import os
import json
import time
import threading
import subprocess
import psutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
GALLERY_DIR = Path(__file__).resolve().parent
RENDERS_DIR = GALLERY_DIR / 'renders'
INVENTORY_PATH = GALLERY_DIR / 'inventory.json'
STATIC_DIR = GALLERY_DIR / 'static'

sys.path.insert(0, str(PROJECT_DIR))

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from gallery.entangler_render import render_object_entangler
from gallery.sigma_to_html import sigma_to_html

app = FastAPI(title="Nagatha's Gallery")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── State ─────────────────────────────────────────────────────

_lock = threading.Lock()
_library = {}          # key → library entry
_inventory = {         # persistent render log
    'renders': [],
    'rotation_index': 0,
}
_render_status = {}    # key → 'rendering' | 'done' | 'error'
_jobs = {}             # job_id → {status, log, prompt, started_at, new_key}


def _load_library():
    global _library
    index_path = PROJECT_DIR / 'object_maps' / 'library_index.json'
    if not index_path.exists():
        return
    with open(index_path, encoding='utf-8') as f:
        data = json.load(f)
    _library = data.get('objects', {})


def _resolve_path(rel_path):
    p = PROJECT_DIR / rel_path
    if p.exists():
        return p
    p2 = PROJECT_DIR / 'object_maps' / rel_path
    if p2.exists():
        return p2
    return p


def _load_maps(key):
    entry = _library.get(key)
    if not entry:
        raise HTTPException(404, f"Object '{key}' not in library")

    shape_path = _resolve_path(entry['shape_path'])
    color_path = _resolve_path(entry['color_path'])

    if not shape_path.exists():
        raise HTTPException(404, f"Shape file not found: {shape_path}")
    if not color_path.exists():
        raise HTTPException(404, f"Color file not found: {color_path}")

    with open(shape_path, encoding='utf-8') as f:
        shape = json.load(f)
    with open(color_path, encoding='utf-8') as f:
        color = json.load(f)

    return shape, color


def _load_inventory():
    global _inventory
    if INVENTORY_PATH.exists():
        with open(INVENTORY_PATH, encoding='utf-8') as f:
            _inventory = json.load(f)
    if 'renders' not in _inventory:
        _inventory['renders'] = []
    if 'rotation_index' not in _inventory:
        _inventory['rotation_index'] = 0


def _save_inventory():
    with open(INVENTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(_inventory, f, indent=2)


# ── API Routes ────────────────────────────────────────────────

@app.get("/api/objects")
def list_objects():
    result = []
    for key, entry in _library.items():
        html_path = RENDERS_DIR / f'{key}.html'
        result.append({
            'key':       key,
            'name':      entry.get('name', key),
            'primitives': entry.get('primitives', 0),
            'materials': entry.get('materials', 0),
            'approved':  entry.get('approved', False),
            'has_html':  html_path.exists(),
        })
    return result


@app.get("/api/object/{key}/shape")
def get_shape(key: str):
    shape, _ = _load_maps(key)
    return shape


@app.get("/api/object/{key}/color")
def get_color(key: str):
    _, color = _load_maps(key)
    return color


@app.get("/api/inventory")
def get_inventory():
    with _lock:
        return _inventory


@app.get("/api/schema")
def get_schema():
    """Return the Sigma Signature format specification (shape map + color map structure)."""
    return {
        "version": "1.0",
        "description": "Sigma Signature — MatterShaper object map format",
        "scale": "1 unit = 10cm",
        "coordinate_system": "Y-up, object base at Y=0, centered on X/Z",
        "shape_map": {
            "required_fields": ["layers"],
            "recommended_fields": ["name", "reference", "scale_note", "provenance"],
            "layer_types": {
                "sphere": {
                    "required": ["id", "type", "pos", "radius", "material"],
                    "optional": ["label"],
                    "example": {"id": "knob", "type": "sphere", "pos": [0, 1.5, 0], "radius": 0.1, "material": "chrome"}
                },
                "ellipsoid": {
                    "required": ["id", "type", "pos", "radii", "material"],
                    "optional": ["label", "rotate"],
                    "notes": "radii=[rx,ry,rz] half-extents. rotate=[rx_rad,ry_rad,rz_rad] Euler angles.",
                    "example": {"id": "body", "type": "ellipsoid", "pos": [0, 1.0, 0], "radii": [0.3, 0.6, 0.3], "material": "steel"}
                },
                "cone": {
                    "required": ["id", "type", "base_pos", "height", "base_radius", "top_radius", "material"],
                    "optional": ["label", "rotate"],
                    "notes": "base_pos=center of bottom circle; height extends upward (+Y). Set base_radius==top_radius for cylinders.",
                    "example": {"id": "leg", "type": "cone", "base_pos": [0, 0, 0], "height": 0.8, "base_radius": 0.05, "top_radius": 0.04, "material": "wood"}
                }
            }
        },
        "color_map": {
            "required_fields": ["materials"],
            "recommended_fields": ["name", "reference", "provenance"],
            "material_schema": {
                "required": ["color"],
                "optional": ["label", "reflectance", "roughness", "density_kg_m3", "mean_Z", "mean_A", "composition"],
                "color_format": "[r, g, b] each in range 0.0–1.0",
                "reflectance_notes": "0=fully diffuse, 1=mirror. Typical: metal~0.8, plastic~0.05, ceramic~0.1",
                "roughness_notes": "0=mirror-smooth, 1=fully matte. Typical: polished~0.1, matte~0.7",
                "example": {
                    "steel": {
                        "label": "Brushed Steel",
                        "color": [0.72, 0.72, 0.74],
                        "reflectance": 0.8,
                        "roughness": 0.25,
                        "density_kg_m3": 7850,
                        "mean_Z": 26,
                        "mean_A": 56,
                        "composition": "Fe 98%, C 2%"
                    }
                }
            }
        }
    }


@app.get("/api/system")
def system_stats():
    """Return current CPU, RAM and disk usage percentages."""
    disk = psutil.disk_usage('/')
    return {
        'cpu_pct':  psutil.cpu_percent(interval=0.1),
        'ram_pct':  psutil.virtual_memory().percent,
        'disk_pct': disk.percent,
        'disk_free_gb': round(disk.free / 1e9, 1),
    }


@app.post("/api/render/{key}")
def trigger_render(
    key: str,
    density: int = Query(1200, ge=100, le=5000),
    width:   int = Query(512,  ge=128, le=2048),
    height:  int = Query(512,  ge=128, le=2048),
):
    """Trigger an entangler render + HTML scene generation for an object."""
    if key not in _library:
        raise HTTPException(404, f"Object '{key}' not in library")

    with _lock:
        if _render_status.get(key) == 'rendering':
            return {'status': 'already_rendering', 'key': key}
        _render_status[key] = 'rendering'

    def _do_render():
        try:
            shape, color = _load_maps(key)

            # 1. Entangler still → {key}.png
            result = render_object_entangler(
                key, shape, color, str(RENDERS_DIR),
                width=width, height=height, density=density,
            )

            # 2. Interactive HTML scene → {key}.html
            html_path = RENDERS_DIR / f'{key}.html'
            sigma_to_html(
                key=key,
                shape_map=shape,
                color_map=color,
                output_path=str(html_path),
                title=_library[key].get('name', key),
            )
            result['html_file'] = f'renders/{key}.html'

            with _lock:
                _inventory['renders'] = [
                    r for r in _inventory['renders'] if r['key'] != key
                ]
                _inventory['renders'].append(result)
                _save_inventory()
                _render_status[key] = 'done'

        except Exception as e:
            with _lock:
                _render_status[key] = 'error'
            print(f"[Gallery] Render error for {key}: {e}")
            import traceback; traceback.print_exc()

    threading.Thread(target=_do_render, daemon=True).start()
    return {'status': 'rendering', 'key': key}


@app.get("/api/render-status/{key}")
def render_status(key: str):
    with _lock:
        status = _render_status.get(key, 'idle')
    html_ready = (RENDERS_DIR / f'{key}.html').exists()
    return {'key': key, 'status': status, 'html_ready': html_ready}


@app.post("/api/html/{key}")
def generate_html_only(key: str):
    """(Re-)generate the interactive HTML for an object without re-rendering the PNG."""
    if key not in _library:
        raise HTTPException(404, f"Object '{key}' not in library")
    shape, color = _load_maps(key)
    html_path = RENDERS_DIR / f'{key}.html'
    sigma_to_html(
        key=key,
        shape_map=shape,
        color_map=color,
        output_path=str(html_path),
        title=_library[key].get('name', key),
    )
    return {'key': key, 'html_file': f'renders/{key}.html'}


@app.post("/api/prompt")
async def submit_prompt(body: dict):
    """Submit a prompt to Nagatha. Runs nagatha.py as a subprocess and streams logs."""
    prompt = body.get('prompt', '').strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")

    job_id = f"job_{int(time.time() * 1000)}"
    _jobs[job_id] = {
        'status':     'running',
        'prompt':     prompt,
        'started_at': time.time(),
        'log':        [],
        'new_key':    None,
    }

    def _run():
        job = _jobs[job_id]
        nagatha_py = PROJECT_DIR / 'agent' / 'nagatha.py'
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        job['log'].append(f'[Gallery] Starting Nagatha for: "{prompt}"')

        try:
            proc = subprocess.Popen(
                [sys.executable, str(nagatha_py), prompt,
                 '--backend', 'ollama', '--approve', 'auto'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                cwd=str(PROJECT_DIR),
            )

            for raw_line in proc.stdout:
                line = raw_line.rstrip()
                if line:
                    job['log'].append(line)

            proc.wait()

            if proc.returncode == 0:
                job['status'] = 'done'
                job['log'].append('[Gallery] Nagatha finished successfully.')
                # Reload library so new objects appear immediately
                _load_library()
                # Find newly added object key (last entry in library)
                keys = list(_library.keys())
                if keys:
                    new_key = keys[-1]
                    job['new_key'] = new_key
                    job['log'].append(f'[Gallery] New object registered: {new_key}')
                    # Auto-render it
                    try:
                        shape, color = _load_maps(new_key)
                        result = render_object_entangler(
                            new_key, shape, color, str(RENDERS_DIR))
                        result['html_file'] = f'renders/{new_key}.html'
                        sigma_to_html(
                            key=new_key, shape_map=shape, color_map=color,
                            output_path=str(RENDERS_DIR / f'{new_key}.html'),
                            title=_library[new_key].get('name', new_key),
                        )
                        with _lock:
                            _inventory['renders'] = [
                                r for r in _inventory['renders'] if r['key'] != new_key
                            ]
                            _inventory['renders'].append(result)
                            _save_inventory()
                        job['log'].append(f'[Gallery] Rendered and added to inventory.')
                    except Exception as re:
                        job['log'].append(f'[Gallery] Render warning: {re}')
            else:
                job['status'] = 'error'
                job['log'].append(f'[Gallery] ERROR: Nagatha exited with code {proc.returncode}')

        except Exception as e:
            job['status'] = 'error'
            job['log'].append(f'[Gallery] ERROR: {e}')

    threading.Thread(target=_run, daemon=True).start()
    return {'job_id': job_id, 'prompt': prompt, 'status': 'running'}


@app.get("/api/prompt/{job_id}")
def get_prompt_status(job_id: str, since: int = Query(0)):
    """Poll a Nagatha job. Returns status + log lines since offset `since`."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    log = job['log']
    return {
        'job_id':    job_id,
        'status':    job['status'],
        'prompt':    job['prompt'],
        'log':       log[since:],
        'total':     len(log),
        'new_key':   job.get('new_key'),
        'elapsed':   round(time.time() - job['started_at'], 1),
    }


@app.get("/api/next")
def next_object():
    keys = list(_library.keys())
    if not keys:
        raise HTTPException(404, "No objects in library")
    with _lock:
        idx  = _inventory.get('rotation_index', 0)
        key  = keys[idx % len(keys)]
        _inventory['rotation_index'] = idx + 1
        _save_inventory()
    html_ready = (RENDERS_DIR / f'{key}.html').exists()
    return {
        'key':       key,
        'name':      _library[key].get('name', key),
        'html_ready': html_ready,
        'html_url':  f'/renders/{key}.html' if html_ready else None,
    }


# ── Static files ──────────────────────────────────────────────

RENDERS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/renders", StaticFiles(directory=str(RENDERS_DIR)), name="renders")
app.mount("/static",  StaticFiles(directory=str(STATIC_DIR)),  name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / 'index.html'))


# ── Startup ───────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    _load_library()
    _load_inventory()
    print(f"[Gallery] Loaded {len(_library)} objects from library")
    print(f"[Gallery] {len(_inventory['renders'])} renders in inventory")
    print(f"[Gallery] Renders dir: {RENDERS_DIR}")

    # Pre-generate HTML for any object that has PNG but no HTML yet
    missing = [
        k for k in _library
        if (RENDERS_DIR / f'{k}.png').exists()
        and not (RENDERS_DIR / f'{k}.html').exists()
    ]
    if missing:
        print(f"[Gallery] Generating HTML for {len(missing)} objects without viewers...")
        def _gen_missing():
            for k in missing:
                try:
                    shape, color = _load_maps(k)
                    sigma_to_html(
                        key=k, shape_map=shape, color_map=color,
                        output_path=str(RENDERS_DIR / f'{k}.html'),
                        title=_library[k].get('name', k),
                    )
                    print(f"[Gallery]   ✓ {k}.html")
                except Exception as e:
                    print(f"[Gallery]   ✗ {k}: {e}")
        threading.Thread(target=_gen_missing, daemon=True).start()


# ── Run directly ──────────────────────────────────────────────

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8422)
