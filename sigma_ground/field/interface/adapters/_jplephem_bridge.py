"""Internal bridge to jplephem -- used only by SGEphemeris as tier-4 fallback.

NOT public API.  SGEphemeris.sg_position() calls this only after all
internal tiers (DE440 fixture, SSBM forecast, Keplerian) have failed.

The external library (jplephem) is not modified in any way.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

_KERNEL_CACHE: dict = {}
_KERNEL_DIR   = Path.home() / ".materia" / "ephemeris"

# NAIF body codes for JPL DE440
_NAIF_CODES: dict[str, int] = {
    "Sun":     10,
    "Mercury":  1,   # Mercury barycentre
    "Venus":    2,
    "Earth":    399,
    "Moon":     301,
    "Mars":     4,
    "Jupiter":  5,
    "Saturn":   6,
    "Uranus":   7,
    "Neptune":  8,
    "Pluto":    9,
}


def _load_kernel(name: str = "de440s"):
    if name in _KERNEL_CACHE:
        return _KERNEL_CACHE[name]
    from jplephem.spk import SPK
    candidates = [
        _KERNEL_DIR / f"{name}.bsp",
        Path(f"{name}.bsp"),
    ]
    for path in candidates:
        if path.exists():
            kernel = SPK.open(str(path))
            _KERNEL_CACHE[name] = kernel
            return kernel
    raise FileNotFoundError(
        f"jplephem kernel {name}.bsp not found. "
        f"Download from https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/ "
        f"and place in {_KERNEL_DIR}."
    )


def query_jplephem(body_name: str, jd: float) -> np.ndarray | None:
    """Return SSB-equatorial position (km) via jplephem, or None on failure."""
    try:
        kernel = _load_kernel("de440s")
    except Exception:
        try:
            kernel = _load_kernel("de440")
        except Exception:
            return None

    code = _NAIF_CODES.get(body_name)
    if code is None:
        return None

    try:
        # jplephem compute() returns (position, velocity) in km, km/day
        pos, _ = kernel[0, code].compute_and_differentiate(jd)
        return np.array(pos)
    except Exception:
        return None
