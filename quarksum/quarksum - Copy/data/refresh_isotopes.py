"""Refresh isotope mass data from IAEA AME (Atomic Mass Evaluation).

Downloads the AME mass table from the IAEA Atomic Mass Data Center and
updates mass-related fields in isotopes.json.

Source: IAEA AMDC — https://www-nds.iaea.org/amdc/
DOI:    10.1088/1674-1137/abddaf (AME2020)

Run:  python -m quarksum.data.refresh_isotopes
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_DATA_DIR = Path(__file__).parent
_OUTPUT = _DATA_DIR / "isotopes.json"

AME_URL = "https://www-nds.iaea.org/amdc/ame2020/mass_1.mas20.txt"


def _parse_ame_line(line: str) -> dict | None:
    if len(line) < 120:
        return None

    try:
        n = int(line[5:10].strip())
        z = int(line[10:15].strip())
        a = int(line[15:20].strip())
    except (ValueError, IndexError):
        return None

    if z < 1:
        return None

    el = line[20:23].strip()
    if not el:
        return None

    mass_excess_str = line[29:43].strip().replace("#", ".")
    be_per_a_str = line[55:68].strip().replace("#", ".")
    atomic_mass_int_str = line[106:110].strip()
    atomic_mass_frac_str = line[110:124].strip().replace("#", ".")

    mass_excess_kev = _safe_float(mass_excess_str)
    be_per_nucleon_kev = _safe_float(be_per_a_str)

    atomic_mass_u = None
    if atomic_mass_int_str and atomic_mass_frac_str:
        try:
            integer_part = int(atomic_mass_int_str)
            fractional_micro = float(atomic_mass_frac_str)
            atomic_mass_u = integer_part + fractional_micro * 1e-6
        except (ValueError, TypeError):
            pass

    return {
        "Z": z,
        "A": a,
        "N": n,
        "symbol": el,
        "atomic_mass_u": atomic_mass_u,
        "mass_excess_kev": mass_excess_kev,
        "binding_energy_per_nucleon_kev": be_per_nucleon_kev,
    }


def _safe_float(s: str) -> float | None:
    if not s or s == "*":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _download_ame(url: str = AME_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ParticleChecksum/1.0 (educational)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_ame_table(text: str) -> dict[tuple[int, int], dict]:
    lines = text.splitlines()
    data_started = False
    results: dict[tuple[int, int], dict] = {}

    for line in lines:
        if "MASS EXCESS" in line and "BINDING ENERGY" in line:
            data_started = False
            continue
        if "(keV)" in line and "(micro-u)" in line:
            data_started = True
            continue
        if not data_started:
            continue
        parsed = _parse_ame_line(line)
        if parsed:
            results[(parsed["Z"], parsed["A"])] = parsed

    return results


def refresh(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Fetch AME data and update mass fields in isotopes.json."""
    if on_progress:
        on_progress(1, 3, "Loading existing isotopes")

    existing = json.loads(_OUTPUT.read_text(encoding="utf-8")) if _OUTPUT.exists() else []

    if on_progress:
        on_progress(2, 3, "Fetching AME table from IAEA")

    ame_text = _download_ame()
    ame_data = _parse_ame_table(ame_text)
    updated = 0
    not_found = 0

    for isotope in existing:
        key = (isotope["Z"], isotope["A"])
        ame_entry = ame_data.get(key)
        if ame_entry is None:
            not_found += 1
            continue

        if ame_entry["atomic_mass_u"] is not None:
            isotope["atomic_mass_u"] = ame_entry["atomic_mass_u"]
        if ame_entry["mass_excess_kev"] is not None:
            isotope["mass_excess_kev"] = ame_entry["mass_excess_kev"]
        if ame_entry["binding_energy_per_nucleon_kev"] is not None:
            isotope["binding_energy_per_nucleon_kev"] = ame_entry["binding_energy_per_nucleon_kev"]
        updated += 1

    if on_progress:
        on_progress(3, 3, "Writing isotopes.json")

    _OUTPUT.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "updated": updated,
        "not_found": not_found,
        "total_ame_nuclides": len(ame_data),
        "total_local_isotopes": len(existing),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    def _progress(i: int, total: int, desc: str) -> None:
        print(f"  [{i}/{total}] {desc}")

    print("Refreshing isotope data from IAEA AME...")
    result = refresh(on_progress=_progress)
    print(f"Done: {result['updated']} updated, {result['not_found']} not found in AME, "
          f"{result['total_ame_nuclides']} total nuclides in AME table")
