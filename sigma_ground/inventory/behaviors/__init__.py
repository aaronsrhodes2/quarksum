"""Behavioral physics computations for fundamental particles.

Every behavior module returns a dict with two top-level keys:
  - ``intrinsic``: properties inherited from nature (get-only)
  - ``operable``: properties that can be changed at this scope (get/set)

Top-level API:
  - ``behaviors(entity)`` — universal getter, auto-detects entity type
  - ``apply_env(entity, env, mode)`` — universal setter with cascade
"""

from __future__ import annotations

from dataclasses import fields as dc_fields
from typing import Any


def extract_fields(obj: Any) -> tuple[dict, dict]:
    """Split a PhysicsObject's fields into intrinsic (constant) and operable (variable).

    Returns (intrinsic_dict, operable_dict).  Each value is a sub-dict with
    ``value``, ``description``, ``unit``, and (for operable) constraint keys.
    """
    intrinsic: dict[str, dict] = {}
    operable: dict[str, dict] = {}

    for f in dc_fields(obj):
        meta = f.metadata
        if not meta or "kind" not in meta:
            continue

        val = getattr(obj, f.name)

        if isinstance(val, list):
            continue

        entry: dict[str, Any] = {
            "value": val,
            "description": meta.get("description", ""),
        }
        if meta.get("unit"):
            entry["unit"] = meta["unit"]

        if meta["kind"] == "constant":
            intrinsic[f.name] = entry
        elif meta["kind"] == "variable":
            if meta.get("min") is not None:
                entry["min"] = meta["min"]
            if meta.get("max") is not None:
                entry["max"] = meta["max"]
            if meta.get("step") is not None:
                entry["step"] = meta["step"]
            if meta.get("options"):
                entry["options"] = meta["options"]
            operable[f.name] = entry

    return intrinsic, operable


# ---------------------------------------------------------------------------
# Universal dispatcher
# ---------------------------------------------------------------------------

def _detect_type(entity: Any) -> str:
    """Return a type tag for the entity."""
    from sigma_ground.inventory.models.quark import Quark
    from sigma_ground.inventory.models.particle import Particle
    from sigma_ground.inventory.models.atom import Atom
    from sigma_ground.inventory.models.molecule import Molecule
    from sigma_ground.inventory.models.structure import Structure

    if isinstance(entity, Quark):
        return "quark"
    if isinstance(entity, Atom):
        return "atom"
    if isinstance(entity, Molecule):
        return "molecule"
    if isinstance(entity, Particle):
        return "particle"
    if isinstance(entity, Structure):
        return "structure"
    raise TypeError(f"Unknown entity type: {type(entity).__name__}")


def behaviors(entity: Any) -> dict:
    """Universal getter — auto-detects entity type and returns behaviors."""
    tag = _detect_type(entity)

    if tag == "quark":
        from sigma_ground.inventory.behaviors.quark_behaviors import compute_quark_behaviors
        return compute_quark_behaviors(entity)
    if tag == "particle":
        from sigma_ground.inventory.behaviors.particle_behaviors import compute_particle_behaviors
        return compute_particle_behaviors(entity)
    if tag == "atom":
        from sigma_ground.inventory.behaviors.atom_behaviors import compute_atom_behaviors
        return compute_atom_behaviors(entity)
    if tag == "molecule":
        from sigma_ground.inventory.behaviors.molecule_behaviors import compute_molecule_behaviors
        return compute_molecule_behaviors(entity)
    if tag == "structure":
        return {"entity_type": "structure", "name": entity.name}

    raise TypeError(f"No behavior getter for: {tag}")


def _cascade(entity: Any, env: dict, mode: str) -> None:
    """Walk children depth-first and apply env at each level."""
    from sigma_ground.inventory.models.molecule import Molecule
    from sigma_ground.inventory.models.atom import Atom
    from sigma_ground.inventory.models.particle import Particle
    from sigma_ground.inventory.models.structure import Structure

    if isinstance(entity, Structure):
        for mol in entity.molecules:
            _apply_single(mol, env, mode)
            _cascade(mol, env, mode)
        for child in entity.children:
            _cascade(child, env, mode)
    elif isinstance(entity, Molecule):
        for atom in entity.atoms:
            _apply_single(atom, env, mode)
            _cascade(atom, env, mode)
    elif isinstance(entity, Atom):
        for electron in entity.electrons:
            _apply_single(electron, env, mode)
        for proton in entity.protons:
            _apply_single(proton, env, mode)
        for neutron in entity.neutrons:
            _apply_single(neutron, env, mode)
    elif isinstance(entity, Particle):
        from sigma_ground.inventory.models.quark import Quark
        for quark in entity.quarks:
            _apply_single(quark, env, mode)


def _apply_single(entity: Any, env: dict, mode: str) -> dict:
    """Apply env to a single entity (no cascade)."""
    tag = _detect_type(entity)

    if tag == "quark":
        from sigma_ground.inventory.behaviors.quark_behaviors import resolve_quark_env
        quark_env = {k: v for k, v in env.items() if k in {"energy_gev", "magnetic_field_t", "color_field"}}
        if quark_env:
            return resolve_quark_env(entity, quark_env, mode)
    elif tag == "particle":
        from sigma_ground.inventory.behaviors.particle_behaviors import resolve_particle_env
        p_env = {k: v for k, v in env.items() if k in {"energy_ev", "magnetic_field_t", "momentum_gev"}}
        if p_env:
            return resolve_particle_env(entity, p_env, mode)
    elif tag == "atom":
        from sigma_ground.inventory.behaviors.atom_behaviors import resolve_atom_env
        a_env = {k: v for k, v in env.items() if k in {"energy_ev", "temperature_k", "electric_field_vm", "magnetic_field_t"}}
        if a_env:
            return resolve_atom_env(entity, a_env, mode)
    elif tag == "molecule":
        from sigma_ground.inventory.behaviors.molecule_behaviors import resolve_molecule_env
        m_env = {k: v for k, v in env.items() if k in {"energy_ev", "temperature_k", "pressure_pa", "electric_field_vm"}}
        if m_env:
            return resolve_molecule_env(entity, m_env, mode)

    return behaviors(entity)


def apply_env(entity: Any, env: dict, mode: str = "delta") -> dict:
    """Universal setter — apply environment to entity with cascade.

    Parameters
    ----------
    entity : any PhysicsObject or Structure
        The entity to mutate.
    env : dict
        Environment keys with numeric values (or categorical for update mode).
    mode : str
        ``"delta"`` for relative adjustment, ``"update"`` for absolute replacement.

    Returns the same shape as ``behaviors(entity)`` plus an ``applied`` log.
    """
    if mode not in ("delta", "update"):
        raise ValueError(f"mode must be 'delta' or 'update', got '{mode}'")

    result = _apply_single(entity, env, mode)
    _cascade(entity, env, mode)
    return result
