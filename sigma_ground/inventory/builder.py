"""Stateless structure builder for the QuarkSum pipeline.

Builds a Structure tree from a JSON spec. No session state, no database,
no geometry — just JSON in, resolved structure out.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sigma_ground.inventory.generator.material_generator import MaterialGenerator
from sigma_ground.inventory.models.structure import Structure
from sigma_ground.inventory.resolver import resolve

log = logging.getLogger(__name__)

_STRUCTURES_DIR = Path(__file__).parent / "samples"
_generator: MaterialGenerator | None = None


def _get_generator() -> MaterialGenerator:
    global _generator
    if _generator is None:
        _generator = MaterialGenerator()
    return _generator


def build_structure_from_spec(spec: dict) -> Structure:
    """Build a Structure from a JSON spec dict.

    Expects the 'children' format:
    {
      "stated_mass_kg": 1.0,
      "children": [
        {"thickness": 10.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
        ...
      ]
    }

    The root's stated_mass_kg becomes the anchor. Each child's weight
    (thickness * density) is converted to a ratio for the resolver.
    """
    gen = _get_generator()
    stated_mass = spec.get("stated_mass_kg", 0.0) or 0.0

    structure = Structure(
        name=spec.get("name", "unnamed"),
        mass_kg=stated_mass if stated_mass > 0 else None,
    )

    weights: list[float] = []

    for child_spec in spec.get("children", []):
        thickness = child_spec.get("thickness", 10.0)
        mat_entries = child_spec.get("materials", [])

        if not mat_entries:
            child = Structure.vacuum()
        elif len(mat_entries) == 1:
            child = gen.generate(mat_entries[0]["material"])
        else:
            ratios = [(m["material"], m["ratio"]) for m in mat_entries]
            child = gen.generate_mixed(ratios)

        weight = thickness * child.standard_density
        weights.append(weight)
        child._build_weight = weight  # type: ignore[attr-defined]
        structure.children.append(child)

        for body_spec in child_spec.get("bodies", []):
            body_struct = build_structure_from_spec(body_spec)
            body_struct.count = body_spec.get("count", 1)
            body_mass = body_spec.get("mass_kg", 0.0)
            body_struct.mass_kg = body_mass
            structure.children.append(body_struct)

    total_weight = sum(weights)
    if total_weight > 0:
        for child in structure.children:
            w = getattr(child, "_build_weight", None)
            if w is not None:
                child.ratio = w / total_weight
                delattr(child, "_build_weight")

    resolve(structure)
    return structure


def build_quick_structure(material: str, mass_kg: float) -> Structure:
    """Build a single-child structure from a material name and mass."""
    gen = _get_generator()
    child = gen.generate(material)
    child.ratio = 1.0

    structure = Structure(
        name=material,
        mass_kg=mass_kg,
    )
    structure.children.append(child)
    resolve(structure)
    return structure


def list_structures() -> list[dict]:
    """List all built-in structures."""
    structures = []
    for path in sorted(_STRUCTURES_DIR.glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            structures.append({
                "id": path.stem,
                "name": spec.get("name", path.stem),
                "description": spec.get("description", ""),
                "stated_mass_kg": spec.get("stated_mass_kg"),
            })
        except Exception:
            log.warning(f"Failed to read structure: {path}")
    return structures


def load_structure_spec(name: str) -> dict | None:
    """Load a structure spec by name (filename stem)."""
    path = _STRUCTURES_DIR / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_structure(name: str) -> Structure | None:
    """Load and build a structure by name."""
    spec = load_structure_spec(name)
    if spec is None:
        return None
    return build_structure_from_spec(spec)


DEFAULT_SAMPLE = "solar_system_xsection"
