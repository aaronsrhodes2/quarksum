#!/usr/bin/env python3
"""
Nagatha — Sigma Signature Mapping Agent
========================================

"I map what is real. The renderer draws what I map."

Nagatha is the encapsulated AI agent that maps real-world objects into
Sigma Signature format. She reads her permanent instructions from
AGENT_BRAIN.md, uses approved objects as few-shot examples, and outputs
.shape.json + .color.json pairs.

Supports three backends:
  1. Local LLM (llama.cpp / ollama) — fully offline
  2. Anthropic API (Claude) — highest quality
  3. OpenAI-compatible API — any provider

Usage:
  python nagitha.py "toaster"
  python nagitha.py "red fire hydrant" --backend ollama
  python nagitha.py "office stapler" --backend anthropic --approve auto
  python nagitha.py --list
"""

import json
import os
import sys
import argparse
import hashlib
import math
import re
from pathlib import Path
from datetime import datetime, timezone

# Object & Scene DB — same package, no cloud dependency
sys.path.insert(0, str(Path(__file__).parent))
try:
    from object_db import (ObjectLibrary, SceneDB, RenderRegistry,
                           ReferenceComparison, WikidataFetcher)
    _HAS_OBJECT_DB = True
except ImportError:
    _HAS_OBJECT_DB = False

# ═══════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════

AGENT_DIR = Path(__file__).parent
PROJECT_DIR = AGENT_DIR.parent
MAPS_DIR = PROJECT_DIR / "object_maps"
RENDERS_DIR = PROJECT_DIR.parent / "renders"
BRAIN_PATH = AGENT_DIR / "AGENT_BRAIN.md"
LIBRARY_INDEX_PATH = MAPS_DIR / "library_index.json"

# ═══════════════════════════════════════════════════════════
# AGENT BRAIN — loaded once, stays in memory
# ═══════════════════════════════════════════════════════════

class AgentBrain:
    """Loads and caches the permanent instructions + examples."""

    def __init__(self):
        self.instructions = self._load_brain()
        self.examples = self._load_examples()
        self.library = self._load_library()

    def _load_brain(self):
        """Load AGENT_BRAIN.md as the system prompt."""
        if BRAIN_PATH.exists():
            return BRAIN_PATH.read_text(encoding='utf-8')
        raise FileNotFoundError(f"Agent brain not found at {BRAIN_PATH}")

    def _load_examples(self):
        """Load all approved object maps as few-shot examples."""
        examples = {}
        if not MAPS_DIR.exists():
            return examples
        for shape_file in MAPS_DIR.glob("*.shape.json"):
            name = shape_file.stem.replace('.shape', '')
            color_file = MAPS_DIR / f"{name}.color.json"
            if color_file.exists():
                examples[name] = {
                    'shape': json.loads(shape_file.read_text(encoding='utf-8')),
                    'color': json.loads(color_file.read_text(encoding='utf-8'))
                }
        return examples

    def _load_library(self):
        """Load or initialize the library index."""
        if LIBRARY_INDEX_PATH.exists():
            return json.loads(LIBRARY_INDEX_PATH.read_text(encoding='utf-8'))
        return {"objects": {}, "version": "1.0"}

    def save_library(self):
        """Persist the library index."""
        LIBRARY_INDEX_PATH.write_text(
            json.dumps(self.library, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def build_system_prompt(self):
        """Construct the full system prompt with brain + examples."""
        prompt = self.instructions + "\n\n"
        prompt += "## LOADED EXAMPLES FROM APPROVED LIBRARY\n\n"
        prompt += f"You have {len(self.examples)} approved objects to learn from:\n"
        for name, data in self.examples.items():
            prompt += f"\n### {data['shape'].get('name', name)}\n"
            prompt += f"- Primitives: {len(data['shape']['layers'])}\n"
            prompt += f"- Materials: {len(data['color']['materials'])}\n"
            prompt += f"- Shape: `{name}.shape.json`\n"
            prompt += f"- Color: `{name}.color.json`\n"
        return prompt

    def build_mapping_prompt(self, object_name):
        """Build the user prompt for mapping a specific object."""
        return f"""Map the following object into Sigma Signature format: "{object_name}"

Follow your permanent instructions exactly. Output TWO JSON blocks:

1. First, output the SHAPE MAP as a JSON code block labeled "SHAPE_MAP":
```json
SHAPE_MAP
{{...}}
```

2. Then output the COLOR MAP as a JSON code block labeled "COLOR_MAP":
```json
COLOR_MAP
{{...}}
```

Remember:
- Research real dimensions (cite your source in provenance)
- Use 1 unit = 10cm scale
- Keep to ≤15 primitives
- Include 3-5 materials for visual variety
- Include a character detail
- Y is up, object base at Y=0, centered on X/Z
- Run your self-review checklist before outputting

Map "{object_name}" now."""


# ═══════════════════════════════════════════════════════════
# LLM BACKENDS
# ═══════════════════════════════════════════════════════════

class LLMBackend:
    """Base class for LLM backends."""

    def generate(self, system_prompt, user_prompt):
        raise NotImplementedError


class OllamaBackend(LLMBackend):
    """Local LLM via Ollama (fully offline)."""

    def __init__(self, model="llama3.1:8b", host="http://localhost:11434"):
        self.model = model
        self.host = host

    def generate(self, system_prompt, user_prompt):
        import urllib.request
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 4096}
        }).encode('utf-8')

        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["message"]["content"]


class AnthropicBackend(LLMBackend):
    """Claude via Anthropic API."""

    def __init__(self, model="claude-sonnet-4-20250514"):
        self.model = model
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

    def generate(self, system_prompt, user_prompt):
        import urllib.request
        payload = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}]
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]


class OpenAICompatBackend(LLMBackend):
    """Any OpenAI-compatible API (local or remote)."""

    def __init__(self, model="gpt-4", base_url="https://api.openai.com/v1"):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.api_key = os.environ.get("OPENAI_API_KEY", "not-needed")

    def generate(self, system_prompt, user_prompt):
        import urllib.request
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4096
        }).encode('utf-8')

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════
# RESPONSE PARSER
# ═══════════════════════════════════════════════════════════

def parse_maps_from_response(text):
    """Extract shape and color JSON from LLM response."""
    import re

    # Find JSON code blocks
    blocks = re.findall(r'```json\s*\n?(.*?)\n?```', text, re.DOTALL)

    shape_map = None
    color_map = None

    for block in blocks:
        block = block.strip()
        # Remove label lines like "SHAPE_MAP" or "COLOR_MAP"
        lines = block.split('\n')
        if lines[0].strip().upper() in ('SHAPE_MAP', 'COLOR_MAP', 'SHAPE MAP', 'COLOR MAP'):
            label = lines[0].strip().upper()
            block = '\n'.join(lines[1:])
        else:
            label = None

        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue

        # Determine if this is a shape or color map
        if label and 'SHAPE' in label:
            shape_map = parsed
        elif label and 'COLOR' in label:
            color_map = parsed
        elif 'layers' in parsed:
            shape_map = parsed
        elif 'materials' in parsed:
            color_map = parsed

    return shape_map, color_map


# ═══════════════════════════════════════════════════════════
# VALIDATOR
# ═══════════════════════════════════════════════════════════

def validate_maps(shape_map, color_map):
    """Validate that the maps are well-formed and cross-reference correctly."""
    errors = []
    warnings = []

    if not shape_map:
        errors.append("No shape map found")
        return errors, warnings

    if not color_map:
        errors.append("No color map found")
        return errors, warnings

    # Check required fields
    if 'layers' not in shape_map:
        errors.append("Shape map missing 'layers' array")
    if 'materials' not in color_map:
        errors.append("Color map missing 'materials' object")

    if errors:
        return errors, warnings

    layers = shape_map['layers']
    materials = color_map['materials']

    # Check layer count
    if len(layers) > 20:
        warnings.append(f"High primitive count: {len(layers)} (target ≤15)")
    if len(layers) < 3:
        warnings.append(f"Very few primitives: {len(layers)} — object may be too simple")

    # Check material references
    used_materials = set()
    for layer in layers:
        mat_id = layer.get('material')
        if not mat_id:
            errors.append(f"Layer '{layer.get('id', '?')}' missing material reference")
        elif mat_id not in materials:
            errors.append(f"Layer '{layer.get('id', '?')}' references undefined material '{mat_id}'")
        used_materials.add(mat_id)

    # Check for orphan materials
    for mat_id in materials:
        if mat_id not in used_materials:
            warnings.append(f"Material '{mat_id}' defined but never used")

    # Check layer types
    valid_types = {'sphere', 'ellipsoid', 'cone', 'plane'}
    for layer in layers:
        lt = layer.get('type')
        if lt not in valid_types:
            errors.append(f"Layer '{layer.get('id', '?')}' has unknown type '{lt}'")

        # Check required fields per type
        if lt == 'sphere':
            if 'pos' not in layer: errors.append(f"Sphere '{layer.get('id')}' missing 'pos'")
            if 'radius' not in layer: errors.append(f"Sphere '{layer.get('id')}' missing 'radius'")
        elif lt == 'ellipsoid':
            if 'pos' not in layer: errors.append(f"Ellipsoid '{layer.get('id')}' missing 'pos'")
            if 'radii' not in layer: errors.append(f"Ellipsoid '{layer.get('id')}' missing 'radii'")
        elif lt == 'cone':
            for field in ('base_pos', 'height', 'base_radius', 'top_radius'):
                if field not in layer:
                    errors.append(f"Cone '{layer.get('id')}' missing '{field}'")

    # Check material completeness
    for mat_id, mat in materials.items():
        if 'color' not in mat:
            errors.append(f"Material '{mat_id}' missing 'color'")
        elif len(mat['color']) != 3:
            errors.append(f"Material '{mat_id}' color must be [r,g,b]")
        elif any(c < 0 or c > 1 for c in mat['color']):
            warnings.append(f"Material '{mat_id}' color values should be 0-1")

    # Check scale sanity (objects should be roughly 0.05 - 5.0 units)
    if layers:
        all_y = []
        for L in layers:
            if L.get('type') == 'cone':
                all_y.append(L.get('base_pos', [0,0,0])[1])
                all_y.append(L.get('base_pos', [0,0,0])[1] + L.get('height', 0))
            elif 'pos' in L:
                all_y.append(L['pos'][1])
        if all_y:
            height = max(all_y) - min(all_y)
            if height < 0.01:
                warnings.append(f"Object height {height:.4f} seems very small — check scale")
            if height > 10.0:
                warnings.append(f"Object height {height:.2f} seems very large — check scale (1 unit = 10cm)")

    # Check provenance
    if 'provenance' not in shape_map:
        warnings.append("Shape map missing provenance field")
    if 'provenance' not in color_map:
        warnings.append("Color map missing provenance field")

    return errors, warnings


# ═══════════════════════════════════════════════════════════
# RENDERING ENGINE (MatterShaper integration)
# ═══════════════════════════════════════════════════════════

def _try_import_mattershaper():
    """Try to import MatterShaper from the project directory."""
    sys.path.insert(0, str(PROJECT_DIR))
    try:
        from mattershaper import MatterShaper, Material, Vec3
        return MatterShaper, Material, Vec3
    except ImportError:
        return None, None, None


def render_from_maps(shape_map, color_map, output_path, width=400, height=400):
    """Render a Sigma Signature using MatterShaper. Returns True on success."""
    MatterShaper, Material, Vec3 = _try_import_mattershaper()
    if MatterShaper is None:
        print("[Nagatha] MatterShaper isn't available just now. I'll skip the render, but the maps are still good.")
        return False

    import time

    name = shape_map.get('name', 'object')
    print(f"[Nagatha] Handing off to MatterShaper for rendering: {name}")

    # Compute bounding box for auto-scaling
    bbox = compute_bounding_box(shape_map)
    cx, cy, cz = bbox['center']
    extent = bbox['extent']

    camera_distance = max(0.6, extent * 2.5)
    camera_height = max(0.2, cy + extent * 0.4)
    look_y = cy

    ms = MatterShaper()
    ms.background(0.08, 0.08, 0.12)
    ms.ambient(0.10, 0.10, 0.13)

    # Floor
    floor_mat = Material(name='Studio Floor', color=Vec3(0.35, 0.35, 0.38),
                         reflectance=0.15, roughness=0.40)
    ms.plane(y=0, material=floor_mat)

    # Build object from maps
    mat_cache = {}
    for layer in shape_map['layers']:
        mat_id = layer['material']
        if mat_id not in mat_cache:
            m = color_map['materials'][mat_id]
            c = m['color']
            mat_cache[mat_id] = Material(
                name=m.get('label', mat_id),
                color=Vec3(c[0], c[1], c[2]),
                reflectance=m.get('reflectance', 0.1),
                roughness=m.get('roughness', 0.5),
                density_kg_m3=m.get('density_kg_m3', 1000),
                mean_Z=m.get('mean_Z', 7),
                mean_A=m.get('mean_A', 14),
                composition=m.get('composition', ''),
            )
        mat = mat_cache[mat_id]
        lt = layer['type']

        if lt == 'sphere':
            p = layer['pos']
            ms.sphere(pos=tuple(p), radius=layer['radius'], material=mat)
        elif lt == 'ellipsoid':
            p = layer['pos']
            r = layer['radii']
            rot = layer.get('rotate', [0, 0, 0])
            ms.ellipsoid(pos=tuple(p), radii=tuple(r), rotate=tuple(rot), material=mat)
        elif lt == 'cone':
            p = layer['base_pos']
            rot = layer.get('rotate', [0, 0, 0])
            ms.cone(base_pos=tuple(p), height=layer['height'],
                    base_radius=layer['base_radius'], top_radius=layer['top_radius'],
                    rotate=tuple(rot), material=mat)
        elif lt == 'plane':
            ms.plane(y=layer.get('y', 0), material=mat)

    # Lights
    light_dist = max(2.0, extent * 4)
    ms.light(pos=(light_dist*0.75, light_dist*1.0, light_dist*0.5),
             color=(1.0, 0.95, 0.88), intensity=0.85)
    ms.light(pos=(-light_dist*0.75, light_dist*0.75, light_dist*0.25),
             color=(0.65, 0.72, 0.95), intensity=0.40)
    ms.light(pos=(0, light_dist*0.5, -light_dist),
             color=(0.8, 0.8, 0.9), intensity=0.30)

    # Camera
    ms.camera(pos=(camera_distance*0.7, camera_height, camera_distance*0.7),
              look_at=(cx, look_y, cz), fov=45)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    t0 = time.time()
    result = ms.render(output_path, width=width, height=height)
    t1 = time.time()

    print(f"[Nagatha] There we are. Rendered in {t1-t0:.2f}s. Every pixel a solved equation.")
    return True


def compute_bounding_box(shape_map):
    """Compute axis-aligned bounding box from shape map layers."""
    mins = [float('inf')] * 3
    maxs = [float('-inf')] * 3

    for layer in shape_map['layers']:
        lt = layer['type']
        if lt == 'sphere':
            p = layer['pos']; r = layer['radius']
            for i in range(3):
                mins[i] = min(mins[i], p[i] - r)
                maxs[i] = max(maxs[i], p[i] + r)
        elif lt == 'ellipsoid':
            p = layer['pos']; radii = layer['radii']
            for i in range(3):
                mins[i] = min(mins[i], p[i] - radii[i])
                maxs[i] = max(maxs[i], p[i] + radii[i])
        elif lt == 'cone':
            p = layer['base_pos']; h = layer['height']
            r_max = max(layer['base_radius'], layer['top_radius'])
            mins[0] = min(mins[0], p[0] - r_max)
            mins[1] = min(mins[1], p[1])
            mins[2] = min(mins[2], p[2] - r_max)
            maxs[0] = max(maxs[0], p[0] + r_max)
            maxs[1] = max(maxs[1], p[1] + h)
            maxs[2] = max(maxs[2], p[2] + r_max)

    cx = (mins[0] + maxs[0]) / 2
    cy = (mins[1] + maxs[1]) / 2
    cz = (mins[2] + maxs[2]) / 2
    dx = maxs[0] - mins[0]; dy = maxs[1] - mins[1]; dz = maxs[2] - mins[2]
    return {'center': (cx, cy, cz), 'size': (dx, dy, dz),
            'extent': math.sqrt(dx**2 + dy**2 + dz**2)}


# ═══════════════════════════════════════════════════════════
# SHAPE ANALYSIS & SELF-CORRECTION
# Nagatha's ability to inspect and improve her own maps.
# ═══════════════════════════════════════════════════════════

class ShapeAnalyzer:
    """
    Nagatha's eyes. Analyzes shape maps for structural problems
    and applies fixes without needing an LLM call.

    These are the lessons learned from building the first 4 objects,
    encoded as deterministic rules so Nagatha never forgets them.
    """

    @staticmethod
    def analyze(shape_map):
        """Inspect a shape map and return a list of (issue, severity, fix_description)."""
        issues = []
        layers = shape_map.get('layers', [])

        # Group layers by material to find logical components
        by_material = {}
        for L in layers:
            mat = L.get('material', 'unknown')
            by_material.setdefault(mat, []).append(L)

        # ── Check 1: Sphere Chain Detection (The Caterpillar Problem) ──
        # Find sequences of spheres/small ellipsoids that form a curve
        # and should be overlapping ellipsoids instead
        sphere_groups = ShapeAnalyzer._find_sphere_chains(layers)
        for group in sphere_groups:
            if len(group) >= 3:
                # Check if they form a chain with gaps
                gap_ratio = ShapeAnalyzer._chain_gap_ratio(group)
                if gap_ratio > 0.3:  # More than 30% gap between adjacent
                    issues.append((
                        f"Sphere chain detected ({len(group)} primitives, material '{group[0]['material']}'): "
                        f"gap ratio {gap_ratio:.0%}. Will look bumpy.",
                        'high',
                        'Replace with overlapping ellipsoids with rotation to form smooth arc'
                    ))

        # ── Check 2: Insufficient Overlap ──
        # Adjacent ellipsoids in the same material should overlap by 30-50%
        for mat, group in by_material.items():
            if len(group) >= 3:
                for i in range(len(group) - 1):
                    a, b = group[i], group[i + 1]
                    if a['type'] == 'ellipsoid' and b['type'] == 'ellipsoid':
                        overlap = ShapeAnalyzer._compute_overlap(a, b)
                        if overlap < 0.15:
                            issues.append((
                                f"Low overlap ({overlap:.0%}) between '{a.get('id','?')}' and '{b.get('id','?')}' "
                                f"(material '{mat}'). May show visible seam.",
                                'medium',
                                'Increase radii or tighten spacing so overlap is 30-50%'
                            ))

        # ── Check 3: Attachment Point Depth ──
        # Parts that attach to a body should sink in by at least 40% of their radius
        for L in layers:
            if 'attach' in L.get('id', '').lower() or 'attach' in L.get('label', '').lower():
                # Find the body it should attach to
                body = ShapeAnalyzer._find_nearest_body(L, layers)
                if body:
                    penetration = ShapeAnalyzer._compute_penetration(L, body)
                    if penetration < 0.3:
                        issues.append((
                            f"Attachment '{L.get('id','?')}' doesn't sink deep enough into body "
                            f"(penetration {penetration:.0%}). Joint will look disconnected.",
                            'medium',
                            'Move attachment point closer to body center'
                        ))

        # ── Check 4: Missing Character Detail ──
        # Objects should have at least one small decorative/character element
        has_detail = any(
            L.get('type') == 'ellipsoid' and
            L.get('radii', [1,1,1])[0] < 0.02 and
            L.get('radii', [1,1,1])[1] < 0.02
            for L in layers
        )
        has_sphere_detail = any(
            L.get('type') == 'sphere' and L.get('radius', 1) < 0.02
            for L in layers
        )
        if not has_detail and not has_sphere_detail and len(layers) > 5:
            issues.append((
                'No character detail detected (small decorative element). '
                'Object may look too clean/generic.',
                'low',
                'Add a small detail: a bruise spot, wear mark, label, or decorative element'
            ))

        return issues

    @staticmethod
    def smooth_handle(shape_map, handle_material):
        """
        Fix a bumpy handle by replacing sphere chains with overlapping
        rotated ellipsoids that form a smooth arc.

        This is the exact fix used on the coffee mug handle v1→v2.

        Args:
            shape_map: The shape map dict
            handle_material: Material ID of the handle layers

        Returns:
            (new_shape_map, changes_description)
        """
        import copy
        new_map = copy.deepcopy(shape_map)
        layers = new_map['layers']

        # Find handle layers
        handle_layers = [L for L in layers if L.get('material') == handle_material]
        other_layers = [L for L in layers if L.get('material') != handle_material]

        if len(handle_layers) < 3:
            return new_map, "Handle has fewer than 3 parts — no smoothing needed"

        # Extract the path (sequence of positions)
        positions = []
        for L in handle_layers:
            if L['type'] == 'sphere':
                positions.append(L['pos'])
            elif L['type'] == 'ellipsoid':
                positions.append(L['pos'])

        if len(positions) < 3:
            return new_map, "Not enough positioned handle parts to smooth"

        # Compute the arc parameters
        n = len(positions)
        new_handle = []

        for i, pos in enumerate(positions):
            # Progress along the arc: 0.0 → 1.0
            t = i / max(1, n - 1)

            # Radii: thicker at attachment points (ends), slimmer in the middle arc
            # This creates a natural handle cross-section
            is_attachment = (i == 0 or i == n - 1)
            is_near_attach = (i == 1 or i == n - 2)

            if is_attachment:
                # Attachment point — wider to sink into body
                rx = 0.08
                ry = 0.06
                rz = 0.045
            elif is_near_attach:
                rx = 0.055
                ry = 0.07
                rz = 0.04
            else:
                # Mid-arc — slightly slimmer
                rx = 0.045
                ry = 0.065
                rz = 0.038

            # Rotation: smooth arc from +0.6 rad at top to -0.6 at bottom
            # This makes each ellipsoid follow the curve direction
            arc_angle = 0.6 * (1 - 2 * t)  # Goes from +0.6 to -0.6
            if is_attachment:
                arc_angle = 0.3 * (1 - 2 * t)  # Gentler at attachment

            new_layer = {
                "id": f"handle_{i}",
                "label": f"Handle segment {i+1}" + (" (attachment)" if is_attachment else ""),
                "type": "ellipsoid",
                "pos": list(pos),
                "radii": [rx, ry, rz],
                "rotate": [0, 0, arc_angle],
                "material": handle_material
            }
            new_handle.append(new_layer)

        new_map['layers'] = other_layers + new_handle

        changes = (
            f"Smoothed handle: replaced {len(handle_layers)} primitives with "
            f"{len(new_handle)} overlapping rotated ellipsoids. "
            f"Used progressive rotation ({0.6:.1f} → {-0.6:.1f} rad) for smooth arc. "
            f"Attachment points use wider radii [0.08, 0.06, 0.045] to sink into body. "
            f"Mid-arc uses slimmer radii [0.045, 0.065, 0.038]."
        )

        return new_map, changes

    @staticmethod
    def increase_overlap(shape_map, material, factor=1.3):
        """
        Increase radii of all ellipsoids in a material group to eliminate gaps.

        Args:
            shape_map: The shape map dict
            material: Material ID of the group to fix
            factor: Multiplier for radii (1.3 = 30% bigger)

        Returns:
            (new_shape_map, changes_description)
        """
        import copy
        new_map = copy.deepcopy(shape_map)
        count = 0

        for L in new_map['layers']:
            if L.get('material') == material and L['type'] == 'ellipsoid':
                old_radii = L['radii'][:]
                L['radii'] = [r * factor for r in L['radii']]
                count += 1

        changes = f"Increased overlap: scaled {count} ellipsoids in '{material}' by {factor:.0%}"
        return new_map, changes

    # ── Internal helpers ──

    @staticmethod
    def _find_sphere_chains(layers):
        """Group layers that are likely part of a chain (same material, close together)."""
        from collections import defaultdict
        groups = defaultdict(list)
        for L in layers:
            if L['type'] in ('sphere', 'ellipsoid'):
                groups[L.get('material', 'unknown')].append(L)
        return [g for g in groups.values() if len(g) >= 3]

    @staticmethod
    def _chain_gap_ratio(group):
        """Compute average gap between adjacent items relative to their size."""
        if len(group) < 2:
            return 0
        total_gap = 0
        total_size = 0
        for i in range(len(group) - 1):
            a, b = group[i], group[i+1]
            pa = a.get('pos', [0,0,0])
            pb = b.get('pos', [0,0,0])
            dist = math.sqrt(sum((pa[j]-pb[j])**2 for j in range(3)))

            ra = a.get('radius', max(a.get('radii', [0.01])))
            rb = b.get('radius', max(b.get('radii', [0.01])))

            gap = max(0, dist - ra - rb)
            total_gap += gap
            total_size += ra + rb

        return total_gap / max(0.001, total_size)

    @staticmethod
    def _compute_overlap(a, b):
        """Estimate overlap fraction between two ellipsoids."""
        pa = a.get('pos', [0,0,0])
        pb = b.get('pos', [0,0,0])
        dist = math.sqrt(sum((pa[j]-pb[j])**2 for j in range(3)))

        ra = max(a.get('radii', [0.01]))
        rb = max(b.get('radii', [0.01]))

        if dist >= ra + rb:
            return 0  # No overlap
        overlap = (ra + rb - dist) / (ra + rb)
        return min(1.0, overlap)

    @staticmethod
    def _find_nearest_body(attachment, layers):
        """Find the largest layer closest to an attachment point."""
        pa = attachment.get('pos', [0,0,0])
        best = None
        best_dist = float('inf')
        for L in layers:
            if L is attachment:
                continue
            if L['type'] == 'cone':
                # Cones are often the body
                pb = L.get('base_pos', [0,0,0])
                pb = [pb[0], pb[1] + L.get('height', 0)/2, pb[2]]
            elif 'pos' in L:
                pb = L['pos']
            else:
                continue
            dist = math.sqrt(sum((pa[j]-pb[j])**2 for j in range(3)))
            # Prefer larger objects (more likely the body)
            size = L.get('radius', max(L.get('radii', [0.01]) if isinstance(L.get('radii'), list) else [0.01]))
            score = dist / max(0.01, size)
            if score < best_dist:
                best_dist = score
                best = L
        return best

    @staticmethod
    def _compute_penetration(attachment, body):
        """Estimate how deeply an attachment penetrates into the body."""
        pa = attachment.get('pos', [0,0,0])
        ra = max(attachment.get('radii', [0.01]))

        if body['type'] == 'cone':
            pb = body.get('base_pos', [0,0,0])
            pb = [pb[0], pb[1] + body.get('height', 0)/2, pb[2]]
            rb = max(body.get('base_radius', 0.01), body.get('top_radius', 0.01))
        elif body['type'] in ('ellipsoid', 'sphere'):
            pb = body.get('pos', [0,0,0])
            rb = body.get('radius', max(body.get('radii', [0.01])))
        else:
            return 0

        dist = math.sqrt(sum((pa[j]-pb[j])**2 for j in range(3)))
        if dist >= rb:
            return 0  # Not penetrating at all
        return (rb - dist) / rb


# ═══════════════════════════════════════════════════════════
# OFFLINE DIMENSION KNOWLEDGE BASE
# Things Nagatha knows without asking the internet.
# ═══════════════════════════════════════════════════════════

DIMENSION_DB = {
    # Kitchenware
    "coffee mug": {"height_cm": 9.6, "top_dia_cm": 8.3, "base_dia_cm": 7.2, "source": "Standard 11oz ceramic mug"},
    "tea cup": {"height_cm": 7.5, "top_dia_cm": 9.0, "base_dia_cm": 5.0, "source": "Standard teacup"},
    "wine glass": {"height_cm": 21, "bowl_dia_cm": 8.5, "base_dia_cm": 7.5, "stem_height_cm": 8, "source": "Standard red wine glass"},
    "water glass": {"height_cm": 14, "top_dia_cm": 7.5, "base_dia_cm": 6.5, "source": "Standard 12oz tumbler"},
    "plate": {"dia_cm": 26, "depth_cm": 2.5, "source": "Standard dinner plate"},
    "bowl": {"dia_cm": 16, "depth_cm": 7, "source": "Standard cereal bowl"},
    "fork": {"length_cm": 19, "width_cm": 2.5, "source": "Standard dinner fork"},
    "knife": {"length_cm": 23, "blade_width_cm": 2, "source": "Standard dinner knife"},
    "spoon": {"length_cm": 17, "bowl_width_cm": 4, "source": "Standard tablespoon"},
    "pot": {"height_cm": 15, "dia_cm": 20, "source": "Standard 3qt saucepan"},
    "frying pan": {"dia_cm": 26, "depth_cm": 5, "handle_cm": 20, "source": "Standard 10in skillet"},
    "toaster": {"height_cm": 20, "width_cm": 30, "depth_cm": 18, "source": "Standard 2-slice toaster"},
    "kettle": {"height_cm": 23, "dia_cm": 16, "source": "Standard electric kettle"},
    "blender": {"height_cm": 38, "base_dia_cm": 16, "jar_dia_cm": 14, "source": "Standard countertop blender"},

    # Furniture
    "dining chair": {"seat_height_cm": 46, "seat_width_cm": 43, "seat_depth_cm": 41, "back_height_cm": 86, "leg_width_cm": 4, "source": "Standard dining chair"},
    "office chair": {"seat_height_cm": 48, "seat_width_cm": 50, "seat_depth_cm": 45, "back_height_cm": 100, "source": "Standard office task chair"},
    "desk": {"height_cm": 75, "width_cm": 120, "depth_cm": 60, "source": "Standard office desk"},
    "table": {"height_cm": 75, "width_cm": 120, "depth_cm": 80, "source": "Standard dining table"},
    "bookshelf": {"height_cm": 180, "width_cm": 80, "depth_cm": 30, "source": "Standard 5-shelf bookcase"},
    "stool": {"height_cm": 65, "seat_dia_cm": 32, "source": "Standard bar stool"},
    "couch": {"height_cm": 85, "width_cm": 200, "depth_cm": 90, "seat_height_cm": 45, "source": "Standard 3-seat sofa"},
    "bed": {"height_cm": 60, "width_cm": 150, "length_cm": 200, "source": "Standard queen bed frame"},
    "nightstand": {"height_cm": 60, "width_cm": 45, "depth_cm": 40, "source": "Standard bedside table"},
    "dresser": {"height_cm": 90, "width_cm": 120, "depth_cm": 45, "source": "Standard 6-drawer dresser"},
    "tv_stand": {"height_cm": 50, "width_cm": 120, "depth_cm": 40, "source": "Standard media console"},

    # Lighting
    "desk lamp": {"height_cm": 48, "shade_dia_cm": 30, "base_dia_cm": 14, "source": "Classic table desk lamp"},
    "floor lamp": {"height_cm": 170, "shade_dia_cm": 35, "base_dia_cm": 25, "source": "Standard floor lamp"},
    "ceiling fan": {"blade_span_cm": 132, "height_cm": 35, "source": "Standard 52in ceiling fan"},
    "candle": {"height_cm": 20, "dia_cm": 7.5, "source": "Standard pillar candle"},
    "lantern": {"height_cm": 30, "width_cm": 18, "source": "Decorative lantern"},

    # Electronics
    "laptop": {"width_cm": 33, "depth_cm": 23, "closed_height_cm": 2, "source": "Standard 14in laptop"},
    "monitor": {"width_cm": 61, "height_cm": 36, "depth_cm": 5, "stand_height_cm": 15, "source": "Standard 27in monitor"},
    "keyboard": {"width_cm": 44, "depth_cm": 14, "height_cm": 3.5, "source": "Standard full-size keyboard"},
    "mouse": {"width_cm": 6.5, "depth_cm": 12, "height_cm": 4, "source": "Standard optical mouse"},
    "phone": {"width_cm": 7.5, "height_cm": 15, "depth_cm": 0.8, "source": "Standard smartphone"},
    "tablet": {"width_cm": 17.5, "height_cm": 25, "depth_cm": 0.6, "source": "Standard 10in tablet"},
    "speaker": {"height_cm": 18, "width_cm": 8, "depth_cm": 8, "source": "Standard bluetooth speaker"},
    "headphones": {"width_cm": 17, "height_cm": 20, "depth_cm": 8, "source": "Standard over-ear headphones"},
    "television": {"width_cm": 123, "height_cm": 71, "depth_cm": 6, "source": "Standard 55in TV"},

    # Fruit & Food
    "banana": {"length_cm": 20, "dia_cm": 3, "curve_deg": 40, "source": "Average Cavendish banana"},
    "apple": {"dia_cm": 8, "height_cm": 7, "source": "Standard medium apple"},
    "orange": {"dia_cm": 8, "source": "Standard navel orange"},
    "pear": {"height_cm": 10, "max_dia_cm": 7.5, "source": "Standard Bartlett pear"},
    "watermelon": {"length_cm": 30, "dia_cm": 25, "source": "Standard seedless watermelon"},
    "egg": {"height_cm": 5.5, "dia_cm": 4.3, "source": "Standard large chicken egg"},
    "bread_loaf": {"length_cm": 25, "width_cm": 12, "height_cm": 12, "source": "Standard sandwich loaf"},
    "pizza": {"dia_cm": 35, "height_cm": 1.5, "source": "Standard 14in pizza"},
    "wine_bottle": {"height_cm": 30, "body_dia_cm": 7.5, "neck_dia_cm": 3, "source": "Standard 750ml wine bottle"},
    "beer_bottle": {"height_cm": 23, "body_dia_cm": 6.5, "neck_dia_cm": 2.6, "source": "Standard 12oz beer bottle"},
    "can": {"height_cm": 12.2, "dia_cm": 6.6, "source": "Standard 12oz soda can"},

    # Office
    "pencil": {"length_cm": 19, "dia_cm": 0.7, "source": "Standard #2 pencil"},
    "pen": {"length_cm": 14, "dia_cm": 1, "source": "Standard ballpoint pen"},
    "stapler": {"length_cm": 17, "width_cm": 4, "height_cm": 6, "source": "Standard desktop stapler"},
    "tape_dispenser": {"length_cm": 15, "width_cm": 6, "height_cm": 7, "source": "Standard desk tape dispenser"},
    "book": {"width_cm": 15, "height_cm": 23, "depth_cm": 2.5, "source": "Standard paperback novel"},
    "binder": {"width_cm": 28, "height_cm": 32, "depth_cm": 5, "source": "Standard 3-ring binder"},

    # Outdoor
    "fire_hydrant": {"height_cm": 60, "body_dia_cm": 25, "source": "Standard US fire hydrant"},
    "mailbox": {"height_cm": 50, "width_cm": 17, "depth_cm": 20, "source": "Standard US mailbox"},
    "trash_can": {"height_cm": 65, "dia_cm": 40, "source": "Standard 13-gallon kitchen trash can"},
    "flower_pot": {"height_cm": 15, "top_dia_cm": 16, "base_dia_cm": 12, "source": "Standard 6in terracotta pot"},
    "watering_can": {"height_cm": 25, "width_cm": 35, "source": "Standard 2-gallon watering can"},
    "bicycle": {"wheel_dia_cm": 70, "frame_height_cm": 55, "length_cm": 175, "source": "Standard adult bicycle"},

    # Bathroom
    "soap_bar": {"width_cm": 9, "depth_cm": 6, "height_cm": 3, "source": "Standard bath soap"},
    "toothbrush": {"length_cm": 19, "head_width_cm": 1.2, "source": "Standard manual toothbrush"},
    "toilet_paper": {"dia_cm": 12, "width_cm": 10, "core_dia_cm": 4.5, "source": "Standard toilet paper roll"},
    "shampoo_bottle": {"height_cm": 20, "width_cm": 7, "depth_cm": 4, "source": "Standard 12oz shampoo bottle"},
}


# ═══════════════════════════════════════════════════════════
# MAIN AGENT
# ═══════════════════════════════════════════════════════════

class Nagatha:
    """Nagatha — the mapping agent. Call .map_object(name) to create a new Sigma Signature."""

    def __init__(self, backend='ollama', **backend_kwargs):
        self.brain = AgentBrain()

        if backend == 'ollama':
            self.llm = OllamaBackend(**backend_kwargs)
        elif backend == 'anthropic':
            self.llm = AnthropicBackend(**backend_kwargs)
        elif backend == 'openai':
            self.llm = OpenAICompatBackend(**backend_kwargs)
        else:
            raise ValueError(f"Unknown backend: {backend}")

        self._system_prompt = self.brain.build_system_prompt()
        print(f"[Nagatha] Right then. Brain loaded ({len(self._system_prompt)} chars), "
              f"{len(self.brain.examples)} approved objects in my library.")
        print(f"[Nagatha] Backend: {backend}. I map what is real.")

    def map_object(self, object_name, max_retries=2):
        """Map a real-world object to Sigma Signature format."""
        print(f"\n{'='*60}")
        print(f"  Nagatha — mapping: {object_name}")
        print(f"{'='*60}\n")

        # ── Dimension lookup: Wikidata cache → DIMENSION_DB → nothing ──────────
        # Higher-precision source wins field-by-field.
        db_dims  = self.get_dimensions(object_name)   # from offline DIMENSION_DB
        wd_data  = None
        dim_note = ""

        if _HAS_OBJECT_DB:
            try:
                wd_fetcher = WikidataFetcher()
                wd_data    = wd_fetcher.best_data(object_name, db_dims)
            except Exception as _wd_err:
                print(f"[Nagatha] Wikidata cache not available ({_wd_err}). Falling back to offline DB.")

        if wd_data:
            # Build a human-readable dimension note for the LLM prompt
            lines = []
            for field, val in wd_data.items():
                if field.startswith("_") or field in ("materials", "wikidata_id"):
                    continue
                if val is not None:
                    prec_label = wd_data["_precision_labels"].get(field, "?")
                    lines.append(f"  {field}: {val}  [{prec_label}]")
            if wd_data.get("materials"):
                lines.append(f"  materials: {', '.join(wd_data['materials'])}")
            if lines:
                print(f"[Nagatha] Physical data on hand ({wd_data.get('wikidata_id','offline')}):")
                for l in lines:
                    print(l)
                dim_note = ("KNOWN PHYSICAL PROPERTIES (cite these; "
                            "higher precision = more trustworthy):\n"
                            + "\n".join(lines))
            else:
                print(f"[Nagatha] No cached dimensions — I'll work from first principles.")
        elif db_dims:
            print(f"[Nagatha] Offline dimensions available:")
            for k, v in db_dims.items():
                if k != 'source':
                    print(f"  {k}: {v}")
            print(f"  Source: {db_dims.get('source', 'offline DB')}")
            lines = [f"  {k}: {v}  [dimension_db]" for k, v in db_dims.items()
                     if k != 'source' and v is not None]
            dim_note = ("KNOWN PHYSICAL PROPERTIES (cite these):\n"
                        + "\n".join(lines))
        else:
            print(f"[Nagatha] No dimension data for '{object_name}' — mapping from first principles.")

        user_prompt = self.brain.build_mapping_prompt(object_name)
        if dim_note:
            user_prompt = dim_note + "\n\n" + user_prompt

        # Fetch reference images and append scoped comparison note to the prompt.
        # Scope: silhouette and proportion ONLY — the renderer handles shading/shadows/reflections.
        if _HAS_OBJECT_DB:
            try:
                ref_note = ReferenceComparison.comparison_note_for(object_name)
                if ref_note:
                    user_prompt += (
                        "\n\n--- REFERENCE IMAGES AVAILABLE ---\n"
                        + ref_note
                        + "\n--- END REFERENCE ---\n"
                    )
                    print("[Nagatha] Reference images fetched. Silhouette and proportion only — "
                          "the Entangler handles the rest.")
            except Exception as _ref_err:
                print(f"[Nagatha] Couldn't fetch references ({_ref_err}). Proceeding on first principles.")

        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"\n[Nagatha] Right, having another go. Attempt {attempt + 1} of {max_retries + 1}.")

            # Step 1: Generate
            print("[Nagatha] Thinking about primitives...")
            try:
                response = self.llm.generate(self._system_prompt, user_prompt)
            except Exception as e:
                print(f"[Nagatha] Oh dear. The LLM didn't cooperate: {e}")
                if attempt < max_retries:
                    continue
                return None, None

            # Step 2: Parse
            print("[Nagatha] Reading what came back...")
            shape_map, color_map = parse_maps_from_response(response)
            if not shape_map or not color_map:
                print("[Nagatha] Hmm. Couldn't make sense of that response. The JSON wasn't quite right.")
                if attempt < max_retries:
                    user_prompt += "\n\nYour previous response could not be parsed. Make sure to output exactly two JSON code blocks — one for SHAPE_MAP and one for COLOR_MAP."
                    continue
                return None, None

            # Step 3: Validate
            print("[Nagatha] Running my checks...")
            errors, warnings = validate_maps(shape_map, color_map)

            for w in warnings:
                print(f"  [note] {w}")
            for e in errors:
                print(f"  [problem] {e}")

            if errors:
                if attempt < max_retries:
                    user_prompt += f"\n\nYour previous output had validation errors:\n" + "\n".join(f"- {e}" for e in errors) + "\nPlease fix and try again."
                    continue
                print("[Nagatha] I've tried my best, but the validation keeps failing. This one may need manual attention.")
                return None, None

            # Step 4: Analyze & self-correct
            print("[Nagatha] Now let me have a proper look at the geometry...")
            shape_map, color_map, fix_log = self.analyze_and_fix(shape_map, color_map)

            # Step 5: Render with MatterShaper
            print("[Nagatha] Handing off to MatterShaper for the render...")
            safe_name = object_name.lower().replace(' ', '_')
            render_path = str(RENDERS_DIR / f"{safe_name}_map.png")
            rendered = render_from_maps(shape_map, color_map, render_path)
            if rendered:
                print(f"[Nagatha] Render complete. Every pixel a solved equation.")
            else:
                print("[Nagatha] MatterShaper isn't available, but the maps are sound.")

            # Step 6: Done
            n_layers = len(shape_map['layers'])
            n_mats = len(color_map['materials'])
            print(f"\n[Nagatha] There we are. {n_layers} primitives, {n_mats} materials, "
                  f"and if I do say so myself, rather recognizable.")
            if fix_log:
                print(f"[Nagatha] I did make {len(fix_log)} correction(s) along the way:")
                for fix in fix_log:
                    print(f"    {fix}")

            return shape_map, color_map

        return None, None

    def analyze_and_fix(self, shape_map, color_map):
        """
        Nagatha inspects her own output and fixes known problems.
        Returns (fixed_shape_map, color_map, list_of_changes).

        Uses ShapeAnalyzer — deterministic rules, no LLM needed.
        Always renders using MatterShaper, never an external renderer.
        """
        fix_log = []
        issues = ShapeAnalyzer.analyze(shape_map)

        if not issues:
            print("[Nagatha] Clean bill of health. No structural issues.")
            return shape_map, color_map, fix_log

        for issue_text, severity, fix_desc in issues:
            print(f"  [{severity.upper()}] {issue_text}")

        # Apply automatic fixes for high-severity issues
        for issue_text, severity, fix_desc in issues:
            if severity == 'high' and 'sphere chain' in issue_text.lower():
                # Find which material has the sphere chain
                for mat_id in set(L.get('material') for L in shape_map['layers']):
                    group = [L for L in shape_map['layers'] if L.get('material') == mat_id]
                    if len(group) >= 3:
                        gap = ShapeAnalyzer._chain_gap_ratio(group)
                        if gap > 0.3:
                            shape_map, changes = ShapeAnalyzer.smooth_handle(shape_map, mat_id)
                            fix_log.append(f"[AUTO-FIX] {changes}")

            elif severity in ('high', 'medium') and 'low overlap' in issue_text.lower():
                # Find the material and increase overlap
                import re
                mat_match = re.search(r"material '(\w+)'", issue_text)
                if mat_match:
                    mat_id = mat_match.group(1)
                    shape_map, changes = ShapeAnalyzer.increase_overlap(shape_map, mat_id, factor=1.25)
                    fix_log.append(f"[AUTO-FIX] {changes}")

        return shape_map, color_map, fix_log

    def fix_object(self, key):
        """Load an existing object, analyze it, fix it, re-render with MatterShaper, and save."""
        shape_path = MAPS_DIR / f"{key}.shape.json"
        color_path = MAPS_DIR / f"{key}.color.json"

        if not shape_path.exists() or not color_path.exists():
            print(f"[Nagatha] I don't have a '{key}' in my library, I'm afraid.")
            return None

        shape_map = json.loads(shape_path.read_text(encoding='utf-8'))
        color_map = json.loads(color_path.read_text(encoding='utf-8'))

        print(f"[Nagatha] Right then, let's have a look at '{shape_map.get('name', key)}'...")
        shape_map, color_map, fix_log = self.analyze_and_fix(shape_map, color_map)

        if fix_log:
            # Save corrected maps
            shape_path.write_text(json.dumps(shape_map, indent=2), encoding='utf-8')
            print(f"[Nagatha] Fixed and saved. That's rather better.")

            # Re-render with MatterShaper
            render_path = str(RENDERS_DIR / f"{key}_map.png")
            render_from_maps(shape_map, color_map, render_path)
        else:
            print("[Nagatha] Looks good to me. No corrections needed.")

        return fix_log

    def get_dimensions(self, object_name):
        """Look up known dimensions offline. Returns dict or None."""
        normalized = object_name.lower().strip()
        # Try exact match first
        if normalized in DIMENSION_DB:
            return DIMENSION_DB[normalized]
        # Try partial match
        for key, dims in DIMENSION_DB.items():
            if normalized in key or key in normalized:
                return dims
        return None

    def save_object(self, object_name, shape_map, color_map, aliases=None):
        """Save maps to disk and register in library index."""
        # Sanitize name for filename
        key = object_name.lower().replace(' ', '_').replace('-', '_')
        key = ''.join(c for c in key if c.isalnum() or c == '_')

        # Save files
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        shape_path = MAPS_DIR / f"{key}.shape.json"
        color_path = MAPS_DIR / f"{key}.color.json"

        shape_path.write_text(json.dumps(shape_map, indent=2, ensure_ascii=False), encoding='utf-8')
        color_path.write_text(json.dumps(color_map, indent=2, ensure_ascii=False), encoding='utf-8')

        print(f"[Nagatha] Filed: {shape_path.name}")
        print(f"[Nagatha] Filed: {color_path.name}")

        # Register in library
        if aliases is None:
            aliases = [object_name.lower(), key.replace('_', ' ')]

        self.brain.library["objects"][key] = {
            "key": key,
            "name": shape_map.get("name", object_name),
            "aliases": list(set(aliases)),
            "shape_path": f"object_maps/{key}.shape.json",
            "color_path": f"object_maps/{key}.color.json",
            "primitives": len(shape_map.get("layers", [])),
            "materials": len(color_map.get("materials", {})),
            "approved": False,
            "created_date": datetime.now(timezone.utc).isoformat(),
            "created_by": "nagitha"
        }
        self.brain.save_library()
        print(f"[Nagatha] Registered in the library as '{key}'. Pending your approval.")

        return key

    def approve_object(self, key, approved_by="user"):
        """Mark an object as approved in the library."""
        if key in self.brain.library["objects"]:
            self.brain.library["objects"][key]["approved"] = True
            self.brain.library["objects"][key]["approved_by"] = approved_by
            self.brain.library["objects"][key]["approved_date"] = datetime.now(timezone.utc).isoformat()
            self.brain.save_library()
            print(f"[Nagatha] Into the library it goes. Welcome home, little {key}. Approved by {approved_by}.")
        else:
            print(f"[Nagatha] I can't find '{key}' in my library. Are you sure about the spelling?")

    def list_library(self):
        """Print all objects in the library."""
        objs = self.brain.library.get("objects", {})
        approved = [v for v in objs.values() if v.get("approved")]
        pending = [v for v in objs.values() if not v.get("approved")]

        print(f"\n[Nagatha] Here's what I have in my library:")
        print(f"  {len(approved)} approved, {len(pending)} awaiting your say-so.\n")

        if approved:
            print("  Approved and ready:")
            for obj in approved:
                print(f"    {obj['name']} ({obj['primitives']} primitives, {obj['materials']} materials) — \"{', '.join(obj['aliases'][:3])}\"")
        if pending:
            print("\n  Waiting for approval:")
            for obj in pending:
                print(f"    {obj['name']} ({obj['primitives']} primitives, {obj['materials']} materials)")
        print()


# ═══════════════════════════════════════════════════════════
# SCENE COMPOSER
# Nagatha's second skill: composing scenes from the library.
# ═══════════════════════════════════════════════════════════

class SceneComposer:
    """Turn a natural-language description into a saved .scene.json.

    Protocol:
      1. Extract the objects mentioned in the description
      2. For each object, check the library — retrieve if present, map if not
      3. Ask the LLM to assign positions, rotations, scales (JSON response)
      4. Build lights + camera from the description (LLM-assisted)
      5. Save scene via SceneDB
      6. Return the scene dict

    Requires _HAS_OBJECT_DB = True (object_db.py importable).
    """

    _COMPOSE_SCHEMA = """
Output a single JSON code block labeled SCENE_JSON with this schema:

```json
SCENE_JSON
{
  "key": "snake_case_scene_name",
  "name": "Human Readable Scene Name",
  "description": "One sentence description.",
  "aliases": ["alias one", "alias two"],
  "objects": [
    {
      "object_key": "<library_key>",
      "label": "<role in this scene>",
      "pos": [x, y, z],
      "rotation": [rx_rad, ry_rad, rz_rad],
      "scale": 1.0
    }
  ],
  "lights": [
    {
      "type": "point",
      "label": "<light description>",
      "pos": [x, y, z],
      "blackbody_K": <temperature in Kelvin>,
      "intensity": <float>,
      "flicker": <true|false>
    }
  ],
  "camera": {
    "pos": [x, y, z],
    "look_at": [x, y, z],
    "fov": 55,
    "up": [0.0, 1.0, 0.0]
  }
}
```

Coordinate rules:
- Y is up. Objects sit at Y = 0 (ground) unless placed on something.
- 1 unit = 1 metre (same as Sigma Signature scale: 1 unit = 10cm × 10 = 1m).
- Objects on a table: table surface at Y ≈ 0.75. Add object's own height above that.
- Lights: blackbody_K only — no RGB. Candle: 1700K flicker. Bulb: 3200K. Daylight: 6500K.
- Camera: place it so the full scene is visible. Diagonal rule: distance ≈ 2.5× scene extent.
"""

    def __init__(self, nagatha_agent):
        """
        Args:
            nagatha_agent: a Nagatha instance (provides .llm and .map_object())
        """
        if not _HAS_OBJECT_DB:
            raise RuntimeError(
                "object_db.py not found. SceneComposer requires it. "
                "Run from the MatterShaper/agent/ directory."
            )
        self.agent = nagatha_agent
        self.lib = ObjectLibrary()
        self.db = SceneDB()
        self.registry = RenderRegistry()

    def compose(self, description, auto_map_missing=True):
        """Compose a scene from a natural-language description.

        Args:
            description:        e.g. "a wooden table with a fruit bowl holding a banana
                                and an apple, lit by a candle"
            auto_map_missing:   if True, map objects not in the library before composing

        Returns:
            scene dict (already saved to scenes/<key>.scene.json), or None on failure.
        """
        print(f"\n[Nagatha] Right then. Let me see what we have in the library before I touch a primitive.")

        # ── Step 1: extract object names from description using LLM ──
        extract_prompt = (
            f'From this scene description, list every physical object that needs to be '
            f'rendered as a 3D object. Return a JSON array of lowercase English names '
            f'and nothing else.\n\nDescription: "{description}"'
        )
        try:
            raw = self.agent.llm.generate(
                "You extract object names from scene descriptions. Return only JSON.",
                extract_prompt
            )
            names = self._parse_string_list(raw)
        except Exception as e:
            print(f"[Nagatha] Hmm. Couldn't extract objects: {e}")
            return None

        print(f"[Nagatha] Objects mentioned: {', '.join(names)}")

        # ── Step 2: resolve each name against the library ──
        resolved = {}    # name → library record
        missing  = []    # names not in the library

        for name in names:
            record = self.lib.find(name)
            if record:
                print(f"[Nagatha] '{name}' → found as '{record['name']}' (key: {record['key']}). Retrieving.")
                resolved[name] = record
            else:
                print(f"[Nagatha] '{name}' — not in the library yet.")
                missing.append(name)

        if missing and auto_map_missing:
            for name in missing:
                print(f"\n[Nagatha] I don't have '{name}'. Give me a moment and I'll map one properly.")
                shape_map, color_map = self.agent.map_object(name)
                if shape_map and color_map:
                    key = self.agent.save_object(name, shape_map, color_map)
                    self.agent.approve_object(key, approved_by="nagatha_auto")
                    self.lib.reload()
                    record = self.lib.get(key)
                    if record:
                        resolved[name] = record
                        print(f"[Nagatha] '{name}' mapped and added to library. Welcome home.")
                    else:
                        print(f"[Nagatha] Odd — I mapped '{name}' but can't find it in the index. Continuing.")
                else:
                    print(f"[Nagatha] I couldn't map '{name}'. I'll proceed without it.")
        elif missing:
            print(f"[Nagatha] Missing objects (auto-map disabled): {', '.join(missing)}")
            print(f"[Nagatha] I'll compose with what I have.")

        if not resolved:
            print("[Nagatha] I have nothing to place in this scene. I'm afraid I can't compose an empty room.")
            return None

        # ── Step 3: build library summary for the LLM ──
        lib_summary = "Available objects (use these exact keys):\n"
        for name, rec in resolved.items():
            lib_summary += (
                f"  key: '{rec['key']}'  name: '{rec['name']}'  "
                f"primitives: {rec.get('primitives', '?')}  "
                f"approx_size: see shape file\n"
            )

        compose_prompt = (
            f"Compose a 3D scene from this description:\n\"{description}\"\n\n"
            f"{lib_summary}\n"
            f"Rules:\n"
            f"- Use ONLY the keys listed above. Do not invent new object_key values.\n"
            f"- Y is up. 1 unit = 1 metre. Table surface at Y ≈ 0.75.\n"
            f"- Lights use blackbody_K (temperature), never RGB.\n"
            f"- Camera must see the full scene.\n\n"
            f"{self._COMPOSE_SCHEMA}"
        )

        # ── Step 4: ask LLM to produce scene JSON ──
        print("[Nagatha] Now composing the arrangement...")
        try:
            response = self.agent.llm.generate(
                self.agent._system_prompt,
                compose_prompt
            )
        except Exception as e:
            print(f"[Nagatha] The LLM didn't cooperate during composition: {e}")
            return None

        scene = self._parse_scene_json(response)
        if not scene:
            print("[Nagatha] I couldn't parse a SCENE_JSON block from that response.")
            return None

        # ── Step 5: validate object keys ──
        valid_keys = {rec['key'] for rec in resolved.values()}
        clean_objects = []
        for entry in scene.get("objects", []):
            if entry.get("object_key") in valid_keys:
                clean_objects.append(entry)
            else:
                print(f"[Nagatha] Ignoring unknown key '{entry.get('object_key')}' — the LLM invented it.")
        scene["objects"] = clean_objects

        if not scene["objects"]:
            print("[Nagatha] After validation, no objects remained. Something went wrong with the LLM response.")
            return None

        # ── Step 6: save ──
        saved_path = self.db.save(scene)
        print(f"\n[Nagatha] Scene saved. '{scene['name']}' — "
              f"{len(scene['objects'])} objects, {len(scene.get('lights', []))} lights.")
        print(f"[Nagatha] Key: '{scene['key']}'  →  {saved_path.name}")
        print(f"[Nagatha] Contains: {', '.join(scene.get('contains', []))}")

        # ── Step 7: cross-reference ──
        for obj_key in scene.get("contains", []):
            other_scenes = self.db.find_scenes_containing(obj_key)
            other_scenes = [s for s in other_scenes if s["key"] != scene["key"]]
            if other_scenes:
                names_str = ", ".join(f"'{s['name']}'" for s in other_scenes[:3])
                print(f"[Nagatha] Note: '{obj_key}' also appears in: {names_str}")

        return scene

    # ── Parsers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_string_list(text):
        """Extract a JSON string array from LLM output."""
        # Find JSON arrays
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return [str(s).lower().strip() for s in result if s]
            except json.JSONDecodeError:
                pass
        # Fallback: split on commas/newlines
        lines = re.split(r'[,\n]+', text)
        return [l.strip().strip('"\'').lower() for l in lines
                if l.strip() and not l.strip().startswith('[')]

    @staticmethod
    def _parse_scene_json(text):
        """Extract the SCENE_JSON block from LLM output."""
        blocks = re.findall(r'```json\s*\n?(.*?)\n?```', text, re.DOTALL)
        for block in blocks:
            block = block.strip()
            lines = block.split('\n')
            if lines[0].strip().upper() in ('SCENE_JSON', 'SCENE JSON'):
                block = '\n'.join(lines[1:])
            try:
                parsed = json.loads(block)
                if 'objects' in parsed and 'camera' in parsed:
                    return parsed
            except json.JSONDecodeError:
                continue
        return None


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Nagatha — Sigma Signature Mapping Agent. Maps real objects to analytic primitives."
    )
    parser.add_argument('object', nargs='?', help='Object name to map (e.g., "toaster")')
    parser.add_argument('--backend', choices=['ollama', 'anthropic', 'openai'], default='ollama',
                       help='LLM backend (default: ollama for offline use)')
    parser.add_argument('--model', help='Model name override')
    parser.add_argument('--approve', choices=['auto', 'manual'], default='manual',
                       help='Auto-approve or require manual approval')
    parser.add_argument('--list', action='store_true', help='List library contents')
    parser.add_argument('--approve-key', help='Approve a pending object by key')
    parser.add_argument('--aliases', nargs='+', help='Alternate names for voice matching')
    parser.add_argument('--fix', help='Analyze and fix an existing object by key (e.g., --fix coffee_mug)')
    parser.add_argument('--dimensions', help='Look up known dimensions for an object (offline)')
    parser.add_argument('--compose', metavar='DESCRIPTION',
                        help='Compose a scene from a description '
                             '(e.g. --compose "a table with a banana and a candle")')
    parser.add_argument('--no-auto-map', action='store_true',
                        help='With --compose: do not map missing objects, just use what is in the library')
    parser.add_argument('--scenes', action='store_true', help='List all saved scene compositions')
    parser.add_argument('--find', metavar='QUERY', help='Find an object or scene by name')

    args = parser.parse_args()

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║         N A G A T H A                ║")
    print("  ║   Sigma Signature Mapping Agent      ║")
    print('  ║   "I map what is real."              ║')
    print("  ╚══════════════════════════════════════╝")
    print()

    # Build backend kwargs
    backend_kwargs = {}
    if args.model:
        backend_kwargs['model'] = args.model

    if args.list:
        agent = Nagatha(backend=args.backend, **backend_kwargs)
        agent.list_library()
        return

    if args.approve_key:
        agent = Nagatha(backend=args.backend, **backend_kwargs)
        agent.approve_object(args.approve_key)
        return

    if args.fix:
        agent = Nagatha(backend=args.backend, **backend_kwargs)
        fixes = agent.fix_object(args.fix)
        if fixes:
            print(f"\n[Nagatha] I made {len(fixes)} correction(s) to '{args.fix}':")
            for f in fixes:
                print(f"  {f}")
            print("\n[Nagatha] Re-rendered with MatterShaper. Every pixel a solved equation.")
        else:
            print(f"\n[Nagatha] I've had a good look at '{args.fix}'. It's fine as it is.")
        return

    if args.dimensions:
        # This doesn't need an LLM — just the offline DB
        dims = DIMENSION_DB.get(args.dimensions.lower().strip())
        if not dims:
            # Try fuzzy
            for key, val in DIMENSION_DB.items():
                if args.dimensions.lower() in key or key in args.dimensions.lower():
                    dims = val
                    break
        if dims:
            print(f"\n[Nagatha] I do know this one. Here are my dimensions for '{args.dimensions}':")
            for k, v in dims.items():
                print(f"  {k}: {v}")
        else:
            print(f"\n[Nagatha] I don't have that one in my head just yet.")
            print(f"  I know {len(DIMENSION_DB)} objects off the top of my head. Not bad for running offline, I should think.")
        return

    if args.find:
        # Library search — no LLM needed
        if not _HAS_OBJECT_DB:
            print("[Nagatha] object_db.py is not available. Cannot search.")
            return
        lib = ObjectLibrary()
        obj = lib.find(args.find)
        if obj:
            print(f"\n[Nagatha] Object match: {obj['name']}  (key: {obj['key']})")
            print(f"  Primitives: {obj.get('primitives')}  Materials: {obj.get('materials')}")
            print(f"  Aliases: {', '.join(obj.get('aliases', []))}")
        else:
            print(f"\n[Nagatha] No object in the library matches '{args.find}'.")
        db = SceneDB()
        scene = db.find(args.find)
        if scene:
            print(f"\n[Nagatha] Scene match: {scene['name']}  (key: {scene['key']})")
            print(f"  Contains: {', '.join(scene.get('contains', []))}")
            print(f"  Renders: {scene.get('render_count', 0)}")
        elif not obj:
            print(f"[Nagatha] No scenes matching '{args.find}' either, I'm afraid.")
        return

    if args.scenes:
        # List scenes — no LLM needed
        if not _HAS_OBJECT_DB:
            print("[Nagatha] object_db.py is not available.")
            return
        db = SceneDB()
        scenes = db.list_all()
        if not scenes:
            print("\n[Nagatha] No scenes in the library yet. Use --compose to build one.\n")
        else:
            print(f"\n[Nagatha] I have {len(scenes)} scene(s) in the library:\n")
            for s in sorted(scenes, key=lambda x: x.get("key", "")):
                contains = ", ".join(s.get("contains", []))
                print(f"  {s['key']}")
                print(f"    Name:     {s.get('name', '?')}")
                print(f"    Contains: {contains}")
                print(f"    Renders:  {s.get('render_count', 0)}")
                print()
        return

    if args.compose:
        if not _HAS_OBJECT_DB:
            print("[Nagatha] object_db.py is not available. Cannot compose scenes.")
            return
        agent = Nagatha(backend=args.backend, **backend_kwargs)
        composer = SceneComposer(agent)
        scene = composer.compose(
            args.compose,
            auto_map_missing=not args.no_auto_map
        )
        if scene:
            print(f"\n[Nagatha] Scene ready. '{scene['name']}' is in the library.")
            print(f"  Key: {scene['key']}")
            print(f"  Run your renderer against scenes/{scene['key']}.scene.json to produce a render.")
        else:
            print("\n[Nagatha] I wasn't able to compose the scene. Do check the description and try again.")
        return

    if not args.object:
        parser.print_help()
        return

    agent = Nagatha(backend=args.backend, **backend_kwargs)

    # Map the object
    shape_map, color_map = agent.map_object(args.object)

    if shape_map and color_map:
        # Save
        key = agent.save_object(args.object, shape_map, color_map, args.aliases)

        # Approval
        if args.approve == 'auto':
            agent.approve_object(key, approved_by="auto")
            print(f"\n[Nagatha] Into the library it goes. Welcome home, little {args.object}.")
        else:
            print(f"\n[Nagatha] Saved as '{key}'. Waiting for your approval whenever you're ready.")
            print(f"  To approve: python nagatha.py --approve-key {key}")
            print(f"  To inspect: {MAPS_DIR / key}.shape.json")

        # Summary
        size_shape = len(json.dumps(shape_map))
        size_color = len(json.dumps(color_map))
        print(f"\n[Nagatha] Total size: {size_shape + size_color:,} bytes. Smaller than a tweet, that.")
    else:
        print(f"\n[Nagatha] I'm sorry — I wasn't able to map '{args.object}' this time. Perhaps try a different backend?")
        sys.exit(1)


if __name__ == '__main__':
    main()
