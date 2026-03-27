"""Base type system for the QuarkSum hierarchy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def constant(
    description: str = "",
    unit: str = "",
    **kwargs: Any,
) -> Any:
    """Declare a dataclass field as a physical constant (read-only)."""
    meta = {"kind": "constant", "description": description, "unit": unit}
    return field(metadata=meta, **kwargs)


def variable(
    description: str = "",
    unit: str = "",
    min_val: float | None = None,
    max_val: float | None = None,
    step: float | None = None,
    options: list[str] | None = None,
    category: str = "lab",
    quantity_type: str = "dimensionless",
    **kwargs: Any,
) -> Any:
    """Declare a dataclass field as a tunable variable."""
    meta = {
        "kind": "variable",
        "description": description,
        "unit": unit,
        "min": min_val,
        "max": max_val,
        "step": step,
        "options": options,
        "category": category,
        "quantity_type": quantity_type,
    }
    return field(metadata=meta, **kwargs)


@dataclass
class PhysicsObject:
    """Base class for every entity in the hierarchy."""
    pass
