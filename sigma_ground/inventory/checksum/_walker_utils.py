"""Shared utilities for checksum walkers.

All walkers need to extract per-molecule mass fractions from a
structure's unique_molecules list.  The composition ratios are
encoded in the structure name for mixed materials (e.g.
"Iron(85%) + Copper(15%)").
"""

from __future__ import annotations

import re

RATIO_RE = re.compile(r"\((\d+(?:\.\d+)?)%\)")


def molecule_ratios(structure) -> list[float]:
    """Return per-molecule mass fractions for a structure's unique molecules.

    Parses percentage annotations from the structure name if present,
    otherwise splits evenly across all unique molecules.
    """
    unique = structure.unique_molecules
    if not unique:
        return []

    formulas = [m.formula for m in unique]
    parts = RATIO_RE.findall(structure.name)
    if parts and len(parts) == len(formulas):
        return [float(p) / 100.0 for p in parts]
    return [1.0 / len(formulas)] * len(formulas)
