"""
Nagatha's Gallery — FastAPI backend.

Serves the 3D viewer frontend, manages object inventory,
and triggers entangler renders.
"""

import sys
import os
import json
import time
import threading
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

SLOT_ORDER = [0, 1, 3, 2]  # TL, TR, BR, BL (clockwise in 2x2 grid)


def _load_library():
    """Load object library index."""
    global _library
    index_path = PROJECT_DIR / 'object_maps' / 'library_index.json'
    if not index_path.exists():
        return
    with open(index_path, encoding='utf-8') as f:
        data = json.load(f)
    _library = data.get('objects', {})


def _resolve_path(rel_path):
    """Resolve a path from library_index.json relative to PROJECT_DIR."""
    p = PROJECT_DIR / rel_path
    if p.exists():
        return p
    # Some paths are relative to object_maps/
    p2 = PROJECT_DIR / 'object_maps' / rel_path
    if p2.exists():
        return p2
    return p


def _load_maps(key):
    """Load shape + color JSON for a library object."""
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
    """Load inventory from disk."""
    global _inventory
    if INVENTORY_PATH.exists():
        with open(INVENTORY_PATH, encoding='utf-8') as f:
            _inventory = json.load(f)
    if 'renders' not in _inventory:
        _inventory['renders'] = []
    if 'rotation_index' not in _inventory:
        _inventory['rotation_index'] = 0


def _save_inventory():
    """Persist inventory to disk."""
    with open(INVENTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(_inventory, f, indent=2)


# ── API Routes ────────────────────────────────────────────────

@app.get("/api/objects")
def list_objects():
    """List all available objects from the library."""
    result = []
    for key, entry in _library.items():
        result.append({
            'key': key,
            'name': entry.get('name', key),
            'primitives': entry.get('primitives', 0),
            'materials': entry.get('materials', 0),
            'approved': entry.get('approved', False),
        })
    return result


@app.get("/api/object/{key}/shape")
def get_shape(key: str):
    """Return the shape JSON for an object."""
    shape, _ = _load_maps(key)
    return shape


@app.get("/api/object/{key}/color")
def get_color(key: str):
    """Return the color JSON for an object."""
    _, color = _load_maps(key)
    return color


@app.get("/api/inventory")
def get_inventory():
    """Return the full render inventory."""
    with _lock:
        return _inventory


@app.post("/api/render/{key}")
def trigger_render(key: str, density: int = Query(1200, ge=100, le=5000),
                   width: int = Query(512, ge=128, le=2048),
                   height: int = Query(512, ge=128, le=2048)):
    """Trigger an entangler render for an object."""
    if key not in _library:
        raise HTTPException(404, f"Object '{key}' not in library")

    with _lock:
        if _render_status.get(key) == 'rendering':
            return {'status': 'already_rendering', 'key': key}

        _render_status[key] = 'rendering'

    def _do_render():
        try:
            shape, color = _load_maps(key)
            result = render_object_entangler(
                key, shape, color, str(RENDERS_DIR),
                width=width, height=height, density=density,
            )
            with _lock:
                # Replace existing entry for this key, don't duplicate
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

    thread = threading.Thread(target=_do_render, daemon=True)
    thread.start()

    return {'status': 'rendering', 'key': key}


@app.get("/api/render-status/{key}")
def render_status(key: str):
    """Check the render status of an object."""
    with _lock:
        status = _render_status.get(key, 'idle')
    return {'key': key, 'status': status}


@app.get("/api/next")
def next_object():
    """Get the next object in the clockwise rotation cycle."""
    keys = list(_library.keys())
    if not keys:
        raise HTTPException(404, "No objects in library")

    with _lock:
        idx = _inventory.get('rotation_index', 0)
        key = keys[idx % len(keys)]
        slot = SLOT_ORDER[idx % 4]
        _inventory['rotation_index'] = idx + 1
        _save_inventory()

    return {
        'key': key,
        'name': _library[key].get('name', key),
        'slot': slot,
        'rotation_index': idx,
    }


# ── Static files ──────────────────────────────────────────────

RENDERS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/renders", StaticFiles(directory=str(RENDERS_DIR)), name="renders")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


# ── Run directly ──────────────────────────────────────────────

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8420)
