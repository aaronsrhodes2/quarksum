# QuarkSum v1.0.0

Particle inventory and mass closure tool.

Define a physical object (geometry, materials, ratios, mass). The tool resolves
materials -> molecules -> atoms -> particles -> quarks, counts every fundamental
particle, and proves the books balance. Zero external dependencies -- pure Python.

## Quick start

```bash
pip install -e .
python -m quarksum              # checksum Sol (default)
python -m quarksum gold_ring    # checksum a built-in structure
```

## CLI usage

```
$ python -m quarksum --help

QuarkSum v1.0.0 — Particle inventory and mass closure tool

Commands:
  python -m quarksum                              # Checksum Sol (default)
  python -m quarksum gold_ring                    # Checksum a built-in structure
  python -m quarksum --list                       # List all built-in structures
  python -m quarksum --spec                       # Dump Sol's raw JSON spec
  python -m quarksum gold_ring --spec             # Dump a structure's raw JSON spec
  python -m quarksum --quark-chain                # Quark-chain on Sol
  python -m quarksum gold_ring --quark-chain      # Quark-chain on a structure
  python -m quarksum --material Iron --mass 1.0   # Quick single-material
  python -m quarksum --file my_structure.json     # Custom spec from file
  python -m quarksum --refresh                    # Refresh isotope data from IAEA

Workflow — clone Sol, rename it, checksum the copy:
  python -m quarksum --spec > custom_sol.json     # Export Sol spec
  # edit custom_sol.json (change name, materials, mass…)
  python -m quarksum --file custom_sol.json       # Checksum your version
```

All output is JSON to stdout. Errors go to stderr. Pipe-friendly.

## Built-in structures

| Structure | Mass | Materials |
|-----------|------|-----------|
| `gold_ring` | 0.01 kg | Au/Cu/Ag alloy, NaCl + Water |
| `water_bottle` | 0.8 kg | SS304, Water, Helium, Air |
| `car_battery` | 15 kg | Lead, H2SO4 + Water |
| `seawater_liter` | 1.025 kg | Seawater (H2O-NaCl) |
| `tungsten_cube` | 0.019 kg | Pure tungsten (W) |
| `earths_layers` | 5.97e24 kg | Fe/Ni, MgO/SiO2, Al2O3, seawater, air |
| `solar_system_xsection` | 1.99e30 kg | H/He, silicates, ISM, ices |

## Custom structures

Export any built-in structure's spec, modify it, and feed it back:

```bash
python -m quarksum gold_ring --spec > my_ring.json
# edit my_ring.json (change name, materials, mass, layers…)
python -m quarksum --file my_ring.json
```

Or see `examples/clone_sol.sh` for a complete end-to-end demo that clones the
Sol structure, renames it to "Custom_Sol", and runs both checksums on the copy.

## Dependencies

None. The checksum pipeline uses pure Python `float` and `math`.
Data refresh uses `urllib` (stdlib).

## Docker

```bash
docker build -t quarksum .
docker run quarksum                         # Sol (default)
docker run quarksum gold_ring               # built-in structure
docker run quarksum --material Iron --mass 1.0
```

## Tests

```bash
pip install -e ".[test]"
pytest                        # standard run
pytest -v -s                  # verbose with physics reports (particle counts, mass closures, energy budgets)
pytest -v -s --no-reports     # verbose without the physics mansplaining
```

Tests print boxed physics reports by default when stdout is visible (`-s`).
Pass `--no-reports` to suppress them.
