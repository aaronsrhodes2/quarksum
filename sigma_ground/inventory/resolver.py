"""Anchor-anywhere mass resolver.

Resolves every node's ``resolved_mass_kg`` in a structure tree.

Algorithm:
    Phase 1 — Convert volume → mass at every node (volume_m3 * density).
    Phase 2 — Propagate concrete masses UP to the root.
    Phase 3 — Propagate resolved masses DOWN to all ratio children.
    Post-check — Verify the root was resolved (at least one anchor exists).
"""

from __future__ import annotations

from sigma_ground.inventory.models.structure import Structure


class ResolutionError(Exception):
    """Raised when the tree cannot be resolved (no anchor, conflicting anchors)."""


def resolve(structure: Structure) -> None:
    """Resolve all masses in *structure* in-place.

    After this call every node has a concrete ``resolved_mass_kg``.
    """
    _phase1_volume_to_mass(structure)
    _phase2_propagate_up(structure)

    if structure.resolved_mass_kg == 0 and structure.mass_kg is None and structure.children:
        has_any_ratio = any(c.ratio is not None for c in structure.children)
        has_any_concrete = any(c.resolved_mass_kg > 0 for c in structure.children)
        if has_any_ratio and not has_any_concrete:
            raise ResolutionError(
                f"Cannot resolve '{structure.name}': all children use ratios but "
                f"at least one concrete mass (mass_kg or volume_m3) is required"
            )

    _phase3_propagate_down(structure)


# ---------------------------------------------------------------------------
# Phase 1: volume → mass
# ---------------------------------------------------------------------------

def _phase1_volume_to_mass(node: Structure) -> None:
    """Convert volume_m3 to mass_kg at every node (depth-first)."""
    if node.volume_m3 is not None and node.mass_kg is None:
        node.mass_kg = node.volume_m3 * node.standard_density
    for child in node.children:
        _phase1_volume_to_mass(child)


# ---------------------------------------------------------------------------
# Phase 2: propagate UP (children → parent)
# ---------------------------------------------------------------------------

def _phase2_propagate_up(node: Structure) -> None:
    """Bottom-up pass: infer parent mass from concrete children.

    Nodes whose children are all ratio-only are left unresolved here;
    they will be filled by the DOWN pass from their parent.
    """
    for child in node.children:
        _phase2_propagate_up(child)

    if node.mass_kg is not None:
        node.resolved_mass_kg = node.mass_kg
        return

    if not node.children:
        return

    concrete_children = [c for c in node.children if c.resolved_mass_kg > 0]
    if not concrete_children:
        return

    concrete_mass = sum(c.resolved_mass_kg * c.count for c in concrete_children)

    ratio_only = [c for c in node.children if c.resolved_mass_kg == 0 and c.ratio is not None]
    ratio_sum_of_unresolved = sum(c.ratio for c in ratio_only if c.ratio)

    if ratio_sum_of_unresolved > 0:
        concrete_fraction = 1.0 - ratio_sum_of_unresolved
        if concrete_fraction > 0:
            node.resolved_mass_kg = concrete_mass / concrete_fraction
        else:
            node.resolved_mass_kg = concrete_mass
    else:
        node.resolved_mass_kg = concrete_mass

    _check_anchor_consistency(node)


def _check_anchor_consistency(node: Structure) -> None:
    """Verify that multiple anchored children agree on the parent mass."""
    inferred_masses: list[tuple[str, float]] = []

    for child in node.children:
        if child.mass_kg is not None and child.ratio is not None and child.ratio > 0:
            implied_parent = (child.mass_kg * child.count) / child.ratio
            inferred_masses.append((child.name, implied_parent))

    if len(inferred_masses) < 2:
        return

    base_name, base_mass = inferred_masses[0]
    for other_name, other_mass in inferred_masses[1:]:
        if base_mass > 0 and abs(other_mass - base_mass) / base_mass > 0.01:
            raise ResolutionError(
                f"Anchor conflict in '{node.name}': "
                f"'{base_name}' implies parent={base_mass:.4g} kg, "
                f"'{other_name}' implies parent={other_mass:.4g} kg"
            )


# ---------------------------------------------------------------------------
# Phase 3: propagate DOWN (parent → ratio children)
# ---------------------------------------------------------------------------

def _phase3_propagate_down(node: Structure) -> None:
    """Top-down pass: resolve ratio children from parent mass."""
    if not node.children:
        return

    unresolved = [c for c in node.children if c.resolved_mass_kg == 0 and c.ratio is not None]
    if unresolved and node.resolved_mass_kg > 0:
        concrete_used = sum(
            c.resolved_mass_kg * c.count
            for c in node.children
            if c.resolved_mass_kg > 0
        )
        remaining = node.resolved_mass_kg - concrete_used

        ratio_sum = sum(c.ratio for c in unresolved if c.ratio)
        if ratio_sum > 0 and remaining > 0:
            for child in unresolved:
                child.resolved_mass_kg = remaining * (child.ratio / ratio_sum)
        elif ratio_sum > 0 and node.resolved_mass_kg > 0:
            for child in unresolved:
                child.resolved_mass_kg = node.resolved_mass_kg * (child.ratio / ratio_sum)

    for child in node.children:
        _phase3_propagate_down(child)
