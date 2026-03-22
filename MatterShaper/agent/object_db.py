"""
object_db.py — MatterShaper Object & Scene Database
====================================================

Four concerns, one file:

  ObjectLibrary       — search and retrieve atomic quarksum objects (Sigma Signatures)
  SceneDB             — save, load, and search scene compositions (.scene.json)
  RenderRegistry      — log every simulation render output with a link back to its scene
  ReferenceComparison — fetch reference images from the web and compare against renders

Architecture
────────────
All persistent state lives in two places:

  object_maps/library_index.json   ← unified index: objects + scenes
  scenes/<key>.scene.json          ← one file per scene composition
  quarksum/renders/                ← final outputs (HTML / PNG / GIF)

The index is human-readable JSON, version-controllable, and diff-friendly.
No SQLite. No external dependencies.  One import: json, pathlib, datetime.

Scene Composition Format (.scene.json)
───────────────────────────────────────
A scene is an arrangement of atomic objects + lights + optional physics config.
Objects are referenced by their library key — never embedded inline.
This is what makes reuse work: the banana in the fruit bowl is the same banana
in the lunchbox, loaded from the same Sigma Signature pair.

Schema:
{
  "key": "kitchen_table_with_fruit_bowl",       ← snake_case, unique
  "name": "Kitchen Table with Fruit Bowl",      ← human-readable
  "description": "...",                         ← one sentence
  "aliases": ["table scene", "fruit table"],    ← what Nagatha searches on
  "created": "ISO-8601",
  "created_by": "nagatha | human",
  "contains": ["wooden_chair", "banana", ...],  ← flat list of object keys used
  "objects": [
    {
      "object_key": "wooden_chair",             ← must exist in library index
      "label": "dining table",                  ← role in this scene
      "pos": [0.0, 0.0, 0.0],                  ← world position [x, y, z] meters
      "rotation": [0.0, 0.0, 0.0],             ← Euler angles radians [rx, ry, rz]
      "scale": 1.0                              ← uniform scale multiplier
    },
    ...
  ],
  "lights": [
    {
      "type": "point",                          ← "point" | "directional" | "blackbody"
      "label": "incandescent bulb",
      "pos": [2.65, 3.35, 0.85],               ← world position
      "blackbody_K": 3200,                      ← temperature → emergent RGB via Planck
      "intensity": 2.0
    },
    {
      "type": "point",
      "label": "candle",
      "pos": [0.35, 0.22, 0.65],
      "blackbody_K": 1800,
      "intensity": 1.2,
      "flicker": true
    }
  ],
  "camera": {
    "pos": [3.0, 2.0, 3.0],
    "look_at": [1.5, 1.0, 0.0],
    "fov": 55,
    "up": [0.0, 1.0, 0.0]
  },
  "physics": null,                             ← null = static render; or a config block:
  "renders": []                                ← filled in by RenderRegistry after each run
}

Physics config block (when physics != null):
{
  "type": "SPH_water",                         ← simulator to invoke
  "script": "simulate_water_pane.py",          ← relative to MatterShaper root
  "params": {
    "delta_x": 0.025,
    "t_sim": 2.0,
    "n_frames": 60
  }
}

Render log entry (appended to scene["renders"] and to renders/render_log.json):
{
  "render_id": "kitchen_table_with_fruit_bowl_20260321_143012",
  "scene_key": "kitchen_table_with_fruit_bowl",
  "output_path": "../../renders/kitchen_table_with_fruit_bowl_20260321_143012.html",
  "type": "html_webgl",
  "created": "ISO-8601",
  "created_by": "nagatha"
}
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ────────────────────────────────────────────────────────────────────

AGENT_DIR     = Path(__file__).parent
PROJECT_DIR   = AGENT_DIR.parent
MAPS_DIR      = PROJECT_DIR / "object_maps"
SCENES_DIR    = PROJECT_DIR / "scenes"
RENDERS_DIR   = PROJECT_DIR.parent / "renders"   # quarksum/renders/
INDEX_PATH    = MAPS_DIR / "library_index.json"
RENDER_LOG    = RENDERS_DIR / "render_log.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_index():
    """Load (or initialise) the unified library index."""
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"version": "1.0", "engine": "MatterShaper",
            "format": "Sigma Signature v1",
            "created_by": "Aaron Rhodes & Claude",
            "agent": "Nagatha",
            "objects": {}, "scenes": {}}


def _save_index(idx):
    """Write the index back to disk."""
    INDEX_PATH.write_text(
        json.dumps(idx, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _normalise(text):
    """Lowercase, strip punctuation — for fuzzy matching."""
    return text.lower().replace("-", " ").replace("_", " ").strip()


# ── ObjectLibrary ─────────────────────────────────────────────────────────────

class ObjectLibrary:
    """Search and retrieve atomic quarksum objects.

    Every approved Sigma Signature pair (*.shape.json + *.color.json) has
    an entry in the library index.  This class provides fuzzy lookup so
    Nagatha (or a human) can ask for "banana" and get back the object record
    without knowing the exact key.

    Usage
    ─────
        lib = ObjectLibrary()
        record = lib.find("banana")
        if record:
            shape = lib.load_shape(record)
            color = lib.load_color(record)
    """

    def __init__(self):
        self._idx = _load_index()
        self._objects = self._idx.get("objects", {})

    def reload(self):
        """Re-read the index from disk (useful in long-running sessions)."""
        self._idx = _load_index()
        self._objects = self._idx.get("objects", {})

    # ── Lookup ────────────────────────────────────────────────────────────────

    def find(self, query):
        """Return the best-matching object record for a natural-language query.

        Matches against: key, name, and all aliases.
        Returns a dict (the record) or None if nothing matches.
        """
        q = _normalise(query)

        # 1. Exact key match
        if q.replace(" ", "_") in self._objects:
            return self._objects[q.replace(" ", "_")]

        # 2. Exact alias match
        for obj in self._objects.values():
            aliases = [_normalise(a) for a in obj.get("aliases", [])]
            if q in aliases or _normalise(obj.get("name", "")) == q:
                return obj

        # 3. Substring match (query is contained in any alias or name)
        candidates = []
        for obj in self._objects.values():
            searchable = [_normalise(obj.get("name", ""))] + \
                         [_normalise(a) for a in obj.get("aliases", [])]
            if any(q in s or s in q for s in searchable):
                candidates.append(obj)

        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            # Return the closest by name length (most specific match)
            return min(candidates,
                       key=lambda o: abs(len(_normalise(o.get("name", ""))) - len(q)))

        return None

    def find_all(self, query):
        """Return all objects whose name or aliases contain the query."""
        q = _normalise(query)
        results = []
        for obj in self._objects.values():
            searchable = [_normalise(obj.get("name", ""))] + \
                         [_normalise(a) for a in obj.get("aliases", [])]
            if any(q in s or s in q for s in searchable):
                results.append(obj)
        return results

    def list_all(self):
        """Return all object records."""
        return list(self._objects.values())

    def get(self, key):
        """Return object record by exact key, or None."""
        return self._objects.get(key)

    # ── Load ─────────────────────────────────────────────────────────────────

    def load_shape(self, record):
        """Load and return the shape JSON for a given record dict."""
        path = PROJECT_DIR / record["shape_path"]
        return json.loads(path.read_text(encoding="utf-8"))

    def load_color(self, record):
        """Load and return the color JSON for a given record dict."""
        path = PROJECT_DIR / record["color_path"]
        return json.loads(path.read_text(encoding="utf-8"))

    # ── Register ──────────────────────────────────────────────────────────────

    def register(self, key, name, aliases, shape_path, color_path,
                 primitives, materials, approved=False, approved_by=None,
                 created_by="nagatha"):
        """Add or update an object entry in the index and save."""
        self._idx = _load_index()
        self._objects = self._idx.setdefault("objects", {})
        self._objects[key] = {
            "key": key,
            "name": name,
            "aliases": aliases,
            "shape_path": str(shape_path),
            "color_path": str(color_path),
            "primitives": primitives,
            "materials": materials,
            "approved": approved,
            "approved_by": approved_by,
            "approved_date": datetime.now(timezone.utc).isoformat()
                             if approved else None,
            "created_by": created_by,
        }
        _save_index(self._idx)
        return self._objects[key]

    def approve(self, key, approved_by="Aaron"):
        """Mark an object as approved."""
        self._idx = _load_index()
        obj = self._idx.get("objects", {}).get(key)
        if not obj:
            raise KeyError(f"Object not found: {key}")
        obj["approved"] = True
        obj["approved_by"] = approved_by
        obj["approved_date"] = datetime.now(timezone.utc).isoformat()
        _save_index(self._idx)


# ── SceneDB ───────────────────────────────────────────────────────────────────

class SceneDB:
    """Save, load, and search scene compositions.

    A scene composition is an arrangement of atomic objects + lights +
    optional physics configuration.  Each scene is stored as:

        scenes/<key>.scene.json

    and registered in the library index under "scenes".

    The key design invariant: objects are referenced by their library key,
    never embedded inline.  If the banana is updated, every scene that
    references "banana" automatically uses the new version on next load.

    Usage
    ─────
        db   = SceneDB()
        lib  = ObjectLibrary()

        # Build a scene programmatically
        scene = db.new_scene(
            key="fruit_bowl_on_table",
            name="Fruit Bowl on Table",
            description="Wooden table with a fruit bowl holding banana, apple, orange.",
        )
        scene["objects"] = [
            db.place("wooden_chair", label="dining table",
                     pos=[0, 0, 0], scale=1.5),
            db.place("banana",  label="banana in bowl", pos=[0.05, 0.92, 0.02]),
            db.place("red_apple", label="apple in bowl", pos=[-0.06, 0.91, 0.04]),
        ]
        scene["lights"] = [
            db.blackbody_light("ceiling bulb", pos=[0, 3, 0], K=3200, intensity=2.0),
        ]
        scene["camera"] = db.camera([3, 2, 3], look_at=[0, 1, 0])
        db.save(scene)

        # Later — find and load it
        record = db.find("fruit bowl")
        scene  = db.load(record["key"])
    """

    def __init__(self):
        self._idx = _load_index()
        self._scenes = self._idx.get("scenes", {})
        SCENES_DIR.mkdir(parents=True, exist_ok=True)

    def reload(self):
        self._idx = _load_index()
        self._scenes = self._idx.get("scenes", {})

    # ── Scene builders ────────────────────────────────────────────────────────

    def new_scene(self, key, name, description="", aliases=None,
                  created_by="nagatha"):
        """Return a blank scene dict with the given key."""
        return {
            "key": key,
            "name": name,
            "description": description,
            "aliases": aliases or [],
            "created": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
            "contains": [],
            "objects": [],
            "lights": [],
            "camera": self.camera([4, 2.5, 4], look_at=[1.5, 1.0, 0.0]),
            "physics": None,
            "renders": [],
        }

    @staticmethod
    def place(object_key, label=None, pos=None, rotation=None, scale=1.0):
        """Build an object placement entry for a scene."""
        return {
            "object_key": object_key,
            "label": label or object_key,
            "pos": pos or [0.0, 0.0, 0.0],
            "rotation": rotation or [0.0, 0.0, 0.0],
            "scale": float(scale),
        }

    @staticmethod
    def blackbody_light(label, pos, K, intensity=1.0, flicker=False):
        """Build a blackbody light entry.

        Color emerges from K via Planck function — no hand-specified RGB.
        The renderer calls planck_to_srgb(K) at render time.
        """
        return {
            "type": "point",
            "label": label,
            "pos": list(pos),
            "blackbody_K": int(K),
            "intensity": float(intensity),
            "flicker": flicker,
        }

    @staticmethod
    def camera(pos, look_at, fov=55, up=None):
        """Build a camera entry."""
        return {
            "pos": list(pos),
            "look_at": list(look_at),
            "fov": fov,
            "up": list(up) if up else [0.0, 1.0, 0.0],
        }

    @staticmethod
    def physics_config(script, sim_type="SPH_water", **params):
        """Build a physics config block."""
        return {
            "type": sim_type,
            "script": script,
            "params": params,
        }

    # ── Derive 'contains' list automatically ─────────────────────────────────

    @staticmethod
    def derive_contains(scene):
        """Populate scene['contains'] from the object placements."""
        seen = set()
        result = []
        for entry in scene.get("objects", []):
            k = entry.get("object_key")
            if k and k not in seen:
                seen.add(k)
                result.append(k)
        scene["contains"] = result
        return scene

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, scene):
        """Write scene to scenes/<key>.scene.json and register in the index."""
        self.derive_contains(scene)
        key = scene["key"]
        scene_path = SCENES_DIR / f"{key}.scene.json"
        scene_path.write_text(
            json.dumps(scene, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Register in index
        self._idx = _load_index()
        self._idx.setdefault("scenes", {})[key] = {
            "key": key,
            "name": scene["name"],
            "description": scene.get("description", ""),
            "aliases": scene.get("aliases", []),
            "contains": scene.get("contains", []),
            "created": scene.get("created"),
            "created_by": scene.get("created_by", "nagatha"),
            "scene_path": f"scenes/{key}.scene.json",
            "render_count": len(scene.get("renders", [])),
        }
        _save_index(self._idx)
        return scene_path

    def load(self, key):
        """Load a scene from disk by key."""
        scene_path = SCENES_DIR / f"{key}.scene.json"
        if not scene_path.exists():
            raise FileNotFoundError(f"Scene not found: {key}")
        return json.loads(scene_path.read_text(encoding="utf-8"))

    # ── Lookup ────────────────────────────────────────────────────────────────

    def find(self, query):
        """Return the best-matching scene record for a natural-language query."""
        self.reload()
        scenes = self._idx.get("scenes", {})
        q = _normalise(query)

        if q.replace(" ", "_") in scenes:
            return scenes[q.replace(" ", "_")]

        for s in scenes.values():
            aliases = [_normalise(a) for a in s.get("aliases", [])]
            if q in aliases or _normalise(s.get("name", "")) == q:
                return s

        candidates = []
        for s in scenes.values():
            searchable = ([_normalise(s.get("name", ""))] +
                          [_normalise(a) for a in s.get("aliases", [])] +
                          [_normalise(c) for c in s.get("contains", [])])
            if any(q in txt or txt in q for txt in searchable):
                candidates.append(s)

        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            return min(candidates,
                       key=lambda s: abs(len(_normalise(s.get("name", ""))) - len(q)))
        return None

    def find_scenes_containing(self, object_key):
        """Return all scene records that use a given object key."""
        self.reload()
        return [s for s in self._idx.get("scenes", {}).values()
                if object_key in s.get("contains", [])]

    def list_all(self):
        self.reload()
        return list(self._idx.get("scenes", {}).values())


# ── RenderRegistry ────────────────────────────────────────────────────────────

class RenderRegistry:
    """Log every simulation render output with a back-link to its scene.

    Writes to:
      quarksum/renders/render_log.json      ← global render log
      scenes/<key>.scene.json  renders[]    ← scene-local render history
    """

    def __init__(self):
        RENDERS_DIR.mkdir(parents=True, exist_ok=True)
        self._log_path = RENDER_LOG

    def _load_log(self):
        if self._log_path.exists():
            return json.loads(self._log_path.read_text(encoding="utf-8"))
        return {"version": "1.0", "renders": []}

    def register(self, scene_key, output_path, render_type="html_webgl",
                 created_by="nagatha", notes=""):
        """Log a completed render.

        Args:
            scene_key:    key of the scene that was rendered
            output_path:  path to the output file (absolute or relative to quarksum/)
            render_type:  "html_webgl" | "png" | "gif" | "ppm"
            created_by:   "nagatha" or user name
            notes:        any extra context

        Returns the render_id string.
        """
        ts = datetime.now(timezone.utc)
        render_id = f"{scene_key}_{ts.strftime('%Y%m%d_%H%M%S')}"

        entry = {
            "render_id": render_id,
            "scene_key": scene_key,
            "output_path": str(output_path),
            "type": render_type,
            "created": ts.isoformat(),
            "created_by": created_by,
            "notes": notes,
        }

        # Append to global log
        log = self._load_log()
        log["renders"].append(entry)
        self._log_path.write_text(
            json.dumps(log, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Append to scene file if it exists
        scene_path = PROJECT_DIR / "scenes" / f"{scene_key}.scene.json"
        if scene_path.exists():
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene.setdefault("renders", []).append(entry)
            scene_path.write_text(
                json.dumps(scene, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

        return render_id

    def renders_for_scene(self, scene_key):
        """Return all render entries for a given scene key."""
        log = self._load_log()
        return [r for r in log["renders"] if r["scene_key"] == scene_key]

    def latest_render(self, scene_key):
        """Return the most recent render entry for a scene, or None."""
        renders = self.renders_for_scene(scene_key)
        return renders[-1] if renders else None


# ── ReferenceComparison ───────────────────────────────────────────────────────

class ReferenceComparison:
    """Fetch reference images from the web to ground Nagatha's geometry checks.

    Two image types, two purposes:

      REAL PHOTO  — "picture of a real [object]"
        What the object actually looks like in the world.
        Loaded with chaos: variable lighting, backgrounds, partial occlusion.
        Used for: overall silhouette, proportions, scale relative to surroundings.
        NOT used for: shading, reflections, shadows — the Entangler handles those.

      3D DRAWING  — "3D drawing of a [object]" or "3D model of a [object]"
        Usually a render with flat/ambient lighting and clean, defined edges.
        Less realistic but cleaner geometry.
        Used for: verifying primitive placement, visible edges, part proportions.
        NOT used for: shading, shadows, surface finish.

    The comparison note passed to the LLM is scoped:
      "Does the SILHOUETTE and PROPORTION match?
       Do NOT comment on shading, shadows, reflections, or surface finish —
       the renderer computes those from physics. Only comment on shape and geometry."

    Fetch strategy: DuckDuckGo image search (no API key required, no rate limiting
    in normal use). Falls back to a hardcoded reference URL cache for offline use.

    Images are saved to:
      object_maps/reference/<key>_real.jpg
      object_maps/reference/<key>_3d.jpg
    """

    REFERENCE_DIR = MAPS_DIR / "reference"

    # ── DuckDuckGo image search (no key needed) ───────────────────────────────

    @classmethod
    def _ddg_first_image_url(cls, query, timeout=8):
        """Return the URL of the first DuckDuckGo image result for a query.

        Uses the DDG HTML endpoint — no API key, no JS required.
        Returns None on failure (network, parse error, timeout).
        """
        encoded = urllib.parse.quote_plus(query)
        # DDG returns an HTML page; image URLs are in vqd= token, then fetched via
        # the /i.js endpoint.  The simpler path: scrape the i.js JSON endpoint.
        vqd_url = f"https://duckduckgo.com/?q={encoded}&iax=images&ia=images"
        try:
            req = urllib.request.Request(
                vqd_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NagathaBot/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Extract vqd token from the page
            vqd_match = re.search(r'vqd=(["\'])([^"\']+)\1', html)
            if not vqd_match:
                vqd_match = re.search(r"vqd='([^']+)'", html)
            if not vqd_match:
                return None
            vqd = vqd_match.group(2) if vqd_match.lastindex == 2 else vqd_match.group(1)

            # Fetch image JSON
            img_url = (f"https://duckduckgo.com/i.js"
                       f"?q={encoded}&o=json&vqd={urllib.parse.quote(vqd)}")
            req2 = urllib.request.Request(
                img_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NagathaBot/1.0)"}
            )
            with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                data = json.loads(resp2.read())

            results = data.get("results", [])
            if results:
                return results[0].get("image")
        except Exception:
            pass
        return None

    # ── Download ──────────────────────────────────────────────────────────────

    @classmethod
    def fetch(cls, object_name, force=False):
        """Fetch one real photo and one 3D drawing for the given object name.

        Returns dict with keys "real" and "3d", each a Path or None.
        Uses cached images if they already exist (unless force=True).
        """
        cls.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
        key = object_name.lower().replace(" ", "_")
        real_path = cls.REFERENCE_DIR / f"{key}_real.jpg"
        draw_path = cls.REFERENCE_DIR / f"{key}_3d.jpg"
        result = {"real": None, "3d": None, "key": key}

        # ── Real photo ──
        if force or not real_path.exists():
            print(f"[Nagatha] Fetching reference photo for '{object_name}'...")
            url = cls._ddg_first_image_url(f"picture of a real {object_name}")
            if url:
                if cls._download_image(url, real_path):
                    print(f"[Nagatha] Reference photo saved: {real_path.name}")
                    result["real"] = real_path
                else:
                    print(f"[Nagatha] Couldn't save the reference photo. Continuing without.")
            else:
                print(f"[Nagatha] No reference photo found online. Proceeding on first principles.")
        else:
            print(f"[Nagatha] Reference photo already in cache: {real_path.name}")
            result["real"] = real_path

        # ── 3D drawing ──
        if force or not draw_path.exists():
            print(f"[Nagatha] Fetching 3D drawing reference for '{object_name}'...")
            url = cls._ddg_first_image_url(f"3D drawing of a {object_name}")
            if url:
                if cls._download_image(url, draw_path):
                    print(f"[Nagatha] 3D reference saved: {draw_path.name}")
                    result["3d"] = draw_path
                else:
                    print(f"[Nagatha] Couldn't save the 3D reference. Continuing without.")
            else:
                print(f"[Nagatha] No 3D drawing found online.")
        else:
            print(f"[Nagatha] 3D reference already in cache: {draw_path.name}")
            result["3d"] = draw_path

        return result

    @staticmethod
    def _download_image(url, dest_path, timeout=10, max_bytes=5 * 1024 * 1024):
        """Download url to dest_path. Returns True on success."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NagathaBot/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read(max_bytes)
            dest_path.write_bytes(data)
            return True
        except Exception as e:
            return False

    # ── Comparison prompt builder ─────────────────────────────────────────────

    @classmethod
    def build_comparison_note(cls, object_name, refs):
        """Build a text note for the LLM about what to check against references.

        This is intentionally scoped: only shape and proportion, never shading.
        """
        lines = [
            f"Reference images for '{object_name}' are available at:",
        ]
        if refs.get("real"):
            lines.append(f"  REAL PHOTO:  {refs['real'].name}")
        if refs.get("3d"):
            lines.append(f"  3D DRAWING:  {refs['3d'].name}")
        lines += [
            "",
            "Comparison scope — CHECK ONLY:",
            "  - Overall silhouette: does the shape read as a recognisable " + object_name + "?",
            "  - Proportions: are the major parts correctly sized relative to each other?",
            "  - Part count: are any large components missing?",
            "",
            "DO NOT comment on:",
            "  - Shading, shadows, or highlights",
            "  - Reflections or surface finish",
            "  - Colour accuracy",
            "  - Background or scene context",
            "",
            "Reason: the Entangler (MatterShaper's renderer) computes shading, shadows,",
            "and reflections from physical first principles. Those aspects are correct",
            "by construction. Shape and proportion are what Nagatha controls directly.",
        ]
        return "\n".join(lines)

    # ── Convenience: fetch + build note in one call ───────────────────────────

    @classmethod
    def comparison_note_for(cls, object_name, force=False):
        """Fetch references and return the scoped comparison note string."""
        refs = cls.fetch(object_name, force=force)
        if not refs["real"] and not refs["3d"]:
            return None   # Nothing to compare against
        return cls.build_comparison_note(object_name, refs)


# ── WikidataFetcher ───────────────────────────────────────────────────────────

class WikidataFetcher:
    """Query Wikidata for physical properties of everyday objects.

    Fetches three things per object:
      dimensions  — height (P2048), width (P2049), length (P2043),
                    depth (P2045), diameter (P2386)  all normalised to metres
      mass        — P2067, normalised to kilograms
      materials   — P186 (made from material), returned as human-readable labels

    Results are cached to:
      object_maps/wikidata_cache.json

    so every subsequent lookup is a local dict read, not a network call.

    Design rules
    ────────────
    - No API key required (Wikidata is open)
    - Polite: 0.6 s delay between search requests, batch entity fetches
    - Resilient: partial data is fine; missing fields come back as None
    - Transparent: every record carries its wikidata_id and a confidence tag

    Confidence levels
    ─────────────────
      "wikidata"     — dimensions/mass found in Wikidata
      "dimension_db" — fell back to Nagatha's local DIMENSION_DB
      "none"         — no reliable data found

    Usage
    ─────
        fetcher = WikidataFetcher()
        data = fetcher.lookup("banana")
        # → {"height_m": 0.2, "diameter_m": 0.03, "mass_kg": 0.12,
        #    "materials": ["peel", "pulp"], "confidence": "wikidata", ...}

    To refresh the cache:
        python agent/fetch_wikidata.py          # bulk — all objects
        python agent/fetch_wikidata.py banana   # single item
    """

    CACHE_PATH  = MAPS_DIR / "wikidata_cache.json"
    API_BASE    = "https://www.wikidata.org/w/api.php"
    USER_AGENT  = "NagathaBot/1.0 (MatterShaper; physics renderer; polite)"

    # Wikidata property IDs we care about
    PROP_HEIGHT   = "P2048"
    PROP_WIDTH    = "P2049"
    PROP_LENGTH   = "P2043"
    PROP_DEPTH    = "P2045"
    PROP_DIAMETER = "P2386"
    PROP_MASS     = "P2067"
    PROP_MATERIAL = "P186"

    # Unit Q-IDs → multiplier to convert to SI (metres / kilograms)
    UNIT_TO_SI = {
        "Q11573":  1.0,        # metre
        "Q174728": 0.01,       # centimetre
        "Q174789": 0.001,      # millimetre
        "Q218593": 0.0254,     # inch
        "Q3710":   0.3048,     # foot
        "Q11570":  1.0,        # kilogram
        "Q41803":  0.001,      # gram
        "Q48013":  0.0000001,  # microgram
        "Q11469":  1000.0,     # tonne
        "Q100995":  0.45359237,# pound (mass)
        "Q41803":  0.001,      # gram (duplicate key is fine, same value)
        "Q39369":  0.0283495,  # ounce (mass)
    }

    def __init__(self):
        self._cache = self._load_cache()

    def _load_cache(self):
        if self.CACHE_PATH.exists():
            return json.loads(self.CACHE_PATH.read_text(encoding="utf-8"))
        return {"version": "1.0", "source": "Wikidata",
                "note": "Snapshot of physical properties for common objects. "
                        "Fetched once; everyday objects don't change meaningfully.",
                "objects": {}}

    def _save_cache(self):
        self.CACHE_PATH.write_text(
            json.dumps(self._cache, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def reload(self):
        self._cache = self._load_cache()

    # ── Public API ────────────────────────────────────────────────────────────

    def lookup(self, object_name):
        """Return cached physical data for object_name, or None if not cached.

        Does NOT fetch from Wikidata — use fetch_and_cache() for that.
        This is the fast path called at runtime by Nagatha.
        """
        key = _normalise(object_name).replace(" ", "_")
        return self._cache.get("objects", {}).get(key)

    def fetch_and_cache(self, object_name, delay=0.6):
        """Search Wikidata for object_name, fetch its properties, cache result.

        Returns the cached record dict.
        """
        key = _normalise(object_name).replace(" ", "_")

        qid, label, description = self._search(object_name, delay=delay)
        if not qid:
            record = {"search_term": object_name, "wikidata_id": None,
                      "wikidata_label": None, "confidence": "none",
                      "height_m": None, "width_m": None, "length_m": None,
                      "depth_m": None, "diameter_m": None, "mass_kg": None,
                      "materials": [], "material_qids": []}
            self._cache.setdefault("objects", {})[key] = record
            self._save_cache()
            return record

        props = self._fetch_props(qid)
        materials, mat_qids = self._resolve_materials(
            props.get(self.PROP_MATERIAL, []), delay=delay)

        def dim(pid):
            vals = props.get(pid, [])
            return self._best_value_m(vals) if vals else (None, self.PREC_NONE)

        h,  hp  = dim(self.PROP_HEIGHT)
        w,  wp  = dim(self.PROP_WIDTH)
        l,  lp  = dim(self.PROP_LENGTH)
        d,  dp  = dim(self.PROP_DEPTH)
        dm, dmp = dim(self.PROP_DIAMETER)
        m,  mp  = self._best_value_kg(props.get(self.PROP_MASS, []))

        has_data = any(v is not None for v in [h, w, l, d, dm, m]) or bool(materials)

        precision = {
            "height_m": hp, "width_m": wp, "length_m": lp,
            "depth_m": dp, "diameter_m": dmp, "mass_kg": mp,
        }
        precision_labels = {k: self.PREC_LABELS.get(v, "?")
                            for k, v in precision.items()}

        record = {
            "search_term":      object_name,
            "wikidata_id":      qid,
            "wikidata_label":   label,
            "wikidata_desc":    description,
            "height_m":         h,
            "width_m":          w,
            "length_m":         l,
            "depth_m":          d,
            "diameter_m":       dm,
            "mass_kg":          m,
            "materials":        materials,
            "material_qids":    mat_qids,
            "confidence":       "wikidata" if has_data else "none",
            "_precision":       precision,
            "_precision_labels":precision_labels,
            "fetched":          datetime.now(timezone.utc).isoformat(),
        }
        self._cache.setdefault("objects", {})[key] = record
        self._save_cache()
        return record

    # ── Wikidata HTTP helpers ─────────────────────────────────────────────────

    def _get(self, params, timeout=10):
        """GET from Wikidata API. Returns parsed JSON or {}."""
        params["format"] = "json"
        url = self.API_BASE + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            return {}

    def _search(self, term, limit=5, delay=0.6):
        """Search Wikidata for term. Returns (qid, label, description) or (None, None, None)."""
        time.sleep(delay)
        data = self._get({
            "action": "wbsearchentities",
            "search": term,
            "language": "en",
            "type": "item",
            "limit": limit,
        })
        results = data.get("search", [])
        if not results:
            return None, None, None
        # Prefer items whose description mentions physical/object attributes
        # rather than organisations, people, or places.
        BAD_DESC = {"human", "person", "organization", "country", "city",
                    "company", "character", "film", "book", "song", "album",
                    "taxon", "species", "genus", "family"}
        for r in results:
            desc = r.get("description", "").lower()
            if not any(bad in desc for bad in BAD_DESC):
                return r["id"], r.get("label", term), r.get("description", "")
        # Fall back to first result
        r = results[0]
        return r["id"], r.get("label", term), r.get("description", "")

    def _fetch_props(self, qid):
        """Fetch claims for a Wikidata item. Returns dict {propid: [snaks]}."""
        data = self._get({
            "action": "wbgetentities",
            "ids": qid,
            "props": "claims",
        })
        entities = data.get("entities", {})
        entity = entities.get(qid, {})
        return entity.get("claims", {})

    def _batch_fetch_labels(self, qids):
        """Fetch English labels for a list of Q-IDs in one call."""
        if not qids:
            return {}
        data = self._get({
            "action": "wbgetentities",
            "ids": "|".join(qids[:50]),   # API limit 50
            "props": "labels",
            "languages": "en",
        })
        result = {}
        for qid, entity in data.get("entities", {}).items():
            labels = entity.get("labels", {})
            en = labels.get("en", {})
            result[qid] = en.get("value", qid)
        return result

    # ── Precision scoring ─────────────────────────────────────────────────────
    #
    # Every numerical value gets a precision score 0–5:
    #
    #   5  wikidata — explicit bounds, tight   (relative uncertainty ≤ 2 %)
    #   4  wikidata — explicit bounds, looser  (relative uncertainty ≤ 20 %)
    #   3  wikidata — stated value, no bounds
    #   2  dimension_db — curated offline table (Nagatha's DIMENSION_DB)
    #   1  llm_estimated — rough LLM guess
    #   0  none — field absent
    #
    # Merge rule: for each dimension field independently, the value with the
    # higher score wins.  Ties go to wikidata.

    PREC_WIKIDATA_TIGHT  = 5
    PREC_WIKIDATA_LOOSE  = 4
    PREC_WIKIDATA_STATED = 3
    PREC_DIMENSION_DB    = 2
    PREC_LLM_ESTIMATED   = 1
    PREC_NONE            = 0

    PREC_LABELS = {5: "wikidata_tight", 4: "wikidata_loose",
                   3: "wikidata_stated", 2: "dimension_db",
                   1: "llm_estimated",  0: "none"}

    @classmethod
    def _precision_score(cls, amount, upper, lower):
        """Compute a precision score from a Wikidata quantity snak."""
        if upper is None or lower is None:
            return cls.PREC_WIKIDATA_STATED
        span = abs(upper - lower)
        if span == 0 or amount == 0:
            return cls.PREC_WIKIDATA_TIGHT
        relative = span / abs(amount)
        if relative <= 0.02:
            return cls.PREC_WIKIDATA_TIGHT
        if relative <= 0.20:
            return cls.PREC_WIKIDATA_LOOSE
        return cls.PREC_WIKIDATA_STATED

    # ── Value extractors ──────────────────────────────────────────────────────

    def _best_value_m(self, snaks):
        """Extract the best metre-normalised value + precision score.

        Returns (value_m, precision_score) or (None, 0).
        """
        best_val, best_prec = None, self.PREC_NONE
        for snak in snaks:
            try:
                dv = snak["mainsnak"]["datavalue"]["value"]
                amount = float(dv["amount"])
                upper  = float(dv["upperBound"]) if "upperBound" in dv else None
                lower  = float(dv["lowerBound"]) if "lowerBound" in dv else None
                unit_url = dv.get("unit", "")
                unit_qid = unit_url.split("/")[-1] if "/" in unit_url else ""
                mult = self.UNIT_TO_SI.get(unit_qid)
                if mult is None:
                    # Unknown unit — accept only if value looks like metres
                    if 0.001 < abs(amount) < 10.0:
                        mult = 1.0
                    else:
                        continue
                val  = round(abs(amount) * mult, 6)
                prec = self._precision_score(
                    amount, upper * mult if upper else None,
                    lower  * mult if lower  else None)
                if prec > best_prec:
                    best_val, best_prec = val, prec
            except (KeyError, TypeError, ValueError):
                continue
        return best_val, best_prec

    def _best_value_kg(self, snaks):
        """Extract the best kg-normalised mass + precision score.

        Returns (value_kg, precision_score) or (None, 0).
        """
        MASS_UNITS = {
            "Q11570": 1.0, "Q41803": 0.001, "Q39369": 0.0283495,
            "Q100995": 0.45359237, "Q11469": 1000.0,
        }
        best_val, best_prec = None, self.PREC_NONE
        for snak in snaks:
            try:
                dv = snak["mainsnak"]["datavalue"]["value"]
                amount = float(dv["amount"])
                upper  = float(dv["upperBound"]) if "upperBound" in dv else None
                lower  = float(dv["lowerBound"]) if "lowerBound" in dv else None
                unit_url = dv.get("unit", "")
                unit_qid = unit_url.split("/")[-1] if "/" in unit_url else ""
                mult = MASS_UNITS.get(unit_qid)
                if mult is None:
                    continue
                val  = round(abs(amount) * mult, 6)
                prec = self._precision_score(
                    amount, upper * mult if upper else None,
                    lower  * mult if lower  else None)
                if prec > best_prec:
                    best_val, best_prec = val, prec
            except (KeyError, TypeError, ValueError):
                continue
        return best_val, best_prec

    # ── Merge: combine Wikidata + offline DB with precision ranking ───────────

    def best_data(self, object_name, dimension_db_entry=None):
        """Return the highest-precision data for each field.

        Merges the cached Wikidata record with an optional dimension_db_entry
        dict (from nagatha.py's DIMENSION_DB).  For each dimension field, the
        value with the higher precision score is used.

        Returns a dict with keys:
          height_m, width_m, length_m, depth_m, diameter_m, mass_kg,
          materials, _precision  (sub-dict of scores per field)
        """
        wd = self.lookup(object_name) or {}
        db = dimension_db_entry or {}

        result = {}
        prec   = {}

        def pick(field_wd, field_db, unit_scale=1.0):
            """Pick the higher-precision value between wikidata and DB."""
            wd_val  = wd.get(field_wd)
            wd_prec = wd.get("_precision", {}).get(field_wd, self.PREC_NONE)
            # Convert DB value from whatever unit to SI
            db_raw = db.get(field_db)
            db_val = round(db_raw * unit_scale, 6) if db_raw is not None else None
            db_prec = self.PREC_DIMENSION_DB if db_val is not None else self.PREC_NONE

            if wd_val is not None and wd_prec >= db_prec:
                return wd_val, wd_prec
            if db_val is not None:
                return db_val, db_prec
            return None, self.PREC_NONE

        # DIMENSION_DB stores cm → convert to metres (*0.01)
        h, hp = pick("height_m",   "height_cm",   0.01)
        w, wp = pick("width_m",    "width_cm",    0.01)
        l, lp = pick("length_m",   "length_cm",   0.01)
        d, dp = pick("depth_m",    "depth_cm",    0.01)
        dm,dmp= pick("diameter_m", "dia_cm",      0.01)
        m, mp = pick("mass_kg",    "mass_kg",     1.0)

        result["height_m"]   = h;  prec["height_m"]   = hp
        result["width_m"]    = w;  prec["width_m"]    = wp
        result["length_m"]   = l;  prec["length_m"]   = lp
        result["depth_m"]    = d;  prec["depth_m"]    = dp
        result["diameter_m"] = dm; prec["diameter_m"] = dmp
        result["mass_kg"]    = m;  prec["mass_kg"]    = mp
        result["materials"]  = wd.get("materials", [])
        result["wikidata_id"]= wd.get("wikidata_id")
        result["_precision"] = prec
        result["_precision_labels"] = {
            k: self.PREC_LABELS.get(v, "?") for k, v in prec.items()}

        return result

    def _resolve_materials(self, snaks, delay=0.3):
        """Resolve material Q-IDs to human-readable labels."""
        qids = []
        for snak in snaks:
            try:
                qid = snak["mainsnak"]["datavalue"]["value"]["id"]
                qids.append(qid)
            except (KeyError, TypeError):
                continue
        if not qids:
            return [], []
        time.sleep(delay)
        labels = self._batch_fetch_labels(qids)
        return [labels.get(q, q) for q in qids], qids


# ── CLI convenience ───────────────────────────────────────────────────────────

def _cmd_list_objects(args):
    lib = ObjectLibrary()
    objs = lib.list_all()
    print(f"\n{'KEY':<28} {'NAME':<32} {'PRIM':>5} {'MAT':>4}  APPROVED")
    print("─" * 80)
    for o in sorted(objs, key=lambda x: x.get("key", "")):
        approved = "✓" if o.get("approved") else " "
        print(f"{o['key']:<28} {o.get('name','?'):<32} "
              f"{o.get('primitives',0):>5} {o.get('materials',0):>4}  {approved}")
    print(f"\n{len(objs)} objects total.\n")


def _cmd_list_scenes(args):
    db = SceneDB()
    scenes = db.list_all()
    if not scenes:
        print("\nNo scenes registered yet.\n")
        return
    print(f"\n{'KEY':<36} {'NAME':<36} CONTAINS")
    print("─" * 90)
    for s in sorted(scenes, key=lambda x: x.get("key", "")):
        contains = ", ".join(s.get("contains", []))
        print(f"{s['key']:<36} {s.get('name','?'):<36} {contains}")
    print(f"\n{len(scenes)} scenes total.\n")


def _cmd_find(args):
    query = " ".join(args.query)
    lib = ObjectLibrary()
    obj = lib.find(query)
    if obj:
        print(f"\nObject match: {obj['name']}  (key: {obj['key']})")
        print(f"  Primitives: {obj.get('primitives')}  Materials: {obj.get('materials')}")
        print(f"  Aliases: {', '.join(obj.get('aliases', []))}")
        print(f"  Approved: {obj.get('approved')}")
    else:
        print(f"\nNo object found for '{query}'.")
    db = SceneDB()
    scene = db.find(query)
    if scene:
        print(f"\nScene match:  {scene['name']}  (key: {scene['key']})")
        print(f"  Contains: {', '.join(scene.get('contains', []))}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Nagatha Object & Scene Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("objects", help="List all objects in the library")
    sub.add_parser("scenes",  help="List all scene compositions")
    p_find = sub.add_parser("find", help="Find object or scene by name")
    p_find.add_argument("query", nargs="+", help="Search query")

    args = parser.parse_args()

    if args.cmd == "objects":
        _cmd_list_objects(args)
    elif args.cmd == "scenes":
        _cmd_list_scenes(args)
    elif args.cmd == "find":
        _cmd_find(args)
    else:
        parser.print_help()
