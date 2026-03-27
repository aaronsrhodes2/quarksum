"""Load and query the element, material, and isotope databases."""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent


class ElementDB:
    """Lookup interface for the periodic table."""

    _instance: ElementDB | None = None
    _elements: list[dict]
    _by_symbol: dict[str, dict]

    def __init__(self) -> None:
        path = _DATA_DIR / "elements.json"
        with open(path, encoding="utf-8") as f:
            self._elements = json.load(f)
        self._by_symbol = {e["symbol"]: e for e in self._elements}

    @classmethod
    def get(cls) -> ElementDB:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def by_symbol(self, symbol: str) -> dict:
        result = self._by_symbol.get(symbol)
        if result is None:
            raise KeyError(f"Unknown element symbol: '{symbol}'")
        return result


class MaterialDB:
    """Lookup interface for the materials database."""

    _instance: MaterialDB | None = None
    _materials: list[dict]
    _by_name: dict[str, dict]

    def __init__(self) -> None:
        path = _DATA_DIR / "materials.json"
        with open(path, encoding="utf-8") as f:
            self._materials = json.load(f)
        self._by_name = {m["name"].lower(): m for m in self._materials}

    @classmethod
    def get(cls) -> MaterialDB:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def by_name(self, name: str) -> dict:
        result = self._by_name.get(name.lower())
        if result is None:
            raise KeyError(
                f"Unknown material: '{name}'. "
                f"Available: {', '.join(self.names())}"
            )
        return result

    def names(self) -> list[str]:
        return [m["name"] for m in self._materials]


class IsotopeDB:
    """Lookup interface for the isotope database (AME2020/NUBASE2020)."""

    _instance: IsotopeDB | None = None
    _isotopes: list[dict]
    _by_key: dict[tuple[int, int], dict]

    def __init__(self) -> None:
        path = _DATA_DIR / "isotopes.json"
        with open(path, encoding="utf-8") as f:
            self._isotopes = json.load(f)
        self._by_key = {(iso["Z"], iso["A"]): iso for iso in self._isotopes}

    @classmethod
    def get(cls) -> IsotopeDB:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def by_z_and_a(self, z: int, a: int) -> dict | None:
        return self._by_key.get((z, a))
