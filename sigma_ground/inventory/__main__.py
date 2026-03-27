"""CLI entrypoint for QuarkSum v1.0.0.

Usage:
    python -m quarksum [STRUCTURE] [OPTIONS]

All output is JSON to stdout. Errors go to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys

from sigma_ground.inventory import __version__

EPILOG = """\
examples:
  python -m quarksum                              # Load Earth with Moon (default)
  python -m quarksum --menu                       # Interactive load selector
  python -m quarksum gold_ring                    # Checksum a built-in structure
  python -m quarksum --list                       # List all built-in structures
  python -m quarksum --spec                       # Dump default structure's raw JSON spec
  python -m quarksum gold_ring --spec             # Dump a structure's raw JSON spec
  python -m quarksum --physics                    # Full physics report (mass, tangle, ...)
  python -m quarksum --quark-chain                # Quark-chain on default structure
  python -m quarksum gold_ring --quark-chain      # Quark-chain on structure
  python -m quarksum --material Iron --mass 1.0   # Quick single-material
  python -m quarksum --file my_structure.json     # Custom spec from file
  python -m quarksum --behaviors up                # QCD behaviors for an up quark
  python -m quarksum --behaviors charm --color blue # Charm quark, blue color charge
  python -m quarksum --refresh                    # Refresh isotope data from IAEA

default loads (--menu to select):
  universe          Our Universe
  milky_way         Milky Way Galaxy
  sol_solar_system  Sol Solar System
  earth_with_moon   Earth with Moon  [default]
  iceberg_in_ocean  Iceberg in Ocean
  apple_on_table    Apple on Table
  bronze_cube       Bronze Cube
  water_molecule    Water Molecule
  hydrogen_atom     Hydrogen Atom

workflow — clone a structure, rename it, checksum the copy:
  python -m quarksum --spec > custom.json         # Export current spec
  # edit custom.json (change name, materials, mass...)
  python -m quarksum --file custom.json           # Checksum your version
"""


def _run_menu(args) -> int:
    """Interactive load selector for --menu flag."""
    from sigma_ground.inventory.defaults import LOADS, by_id
    from sigma_ground.inventory.builder import load_structure

    print("\nQuarkSum — Select a load:", file=sys.stderr)
    print(file=sys.stderr)
    for i, load in enumerate(LOADS, 1):
        marker = "  [default]" if load.id == "earth_with_moon" else ""
        print(f"  {i:2d}. {load.name}{marker}", file=sys.stderr)
    print(file=sys.stderr)
    try:
        raw = input(f"Enter number (1-{len(LOADS)}): ")
        choice = int(raw.strip())
    except (ValueError, EOFError, KeyboardInterrupt):
        _err("No selection made.")
        return 1

    if not (1 <= choice <= len(LOADS)):
        _err(f"Invalid choice: {choice}. Must be 1-{len(LOADS)}.")
        return 1

    selected = LOADS[choice - 1]
    print(selected.message, file=sys.stderr)

    structure = load_structure(selected.id)
    if structure is None:
        _err(f"Failed to load: {selected.id}")
        return 1

    if args.physics:
        from sigma_ground.inventory.physics import compute_physics
        result = compute_physics(structure, radius_m=selected.radius_m)
    elif args.quark_chain:
        from sigma_ground.inventory.checksum.quark_chain import compute_quark_chain_checksum
        result = compute_quark_chain_checksum(structure)
    elif args.inventory:
        from sigma_ground.inventory.checksum.particle_inventory import compute_particle_inventory
        result = compute_particle_inventory(structure)
    else:
        from sigma_ground.inventory.checksum.stoq_checksum import compute_stoq_checksum
        result = compute_stoq_checksum(structure)

    _json_out(result)
    return 0


def _json_out(data: dict) -> None:
    """Print a dict as formatted JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quarksum",
        description=f"QuarkSum v{__version__} — Particle inventory and mass closure tool",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "structure",
        nargs="?",
        default=None,
        help="Built-in structure name (default: earth_with_moon)",
    )
    parser.add_argument(
        "--menu",
        action="store_true",
        help="Interactive menu to select a default load",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_structures",
        help="List all built-in structures",
    )
    parser.add_argument(
        "--spec",
        action="store_true",
        help="Dump a structure's raw JSON spec (for saving / editing / resubmitting)",
    )
    parser.add_argument(
        "--physics",
        action="store_true",
        help="Full physics report: mass, particles, gravity, entanglement tangle",
    )
    parser.add_argument(
        "--quark-chain",
        action="store_true",
        help="Run full quark-chain reconstruction instead of StoQ checksum",
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Full Standard Model particle inventory (JSON)",
    )
    parser.add_argument(
        "--behaviors",
        type=str,
        default=None,
        metavar="FLAVOR",
        help="QCD behaviors for a quark flavor (up, down, strange, charm, bottom, top)",
    )
    parser.add_argument(
        "--color",
        type=str,
        default="red",
        help="Color charge for --behaviors (default: red)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply environment to entity (use with --behaviors and --env)",
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help='Environment JSON dict, e.g. \'{"energy_ev": 13.6}\'',
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="delta",
        choices=["delta", "update"],
        help="Apply mode: delta (relative) or update (absolute). Default: delta",
    )
    parser.add_argument(
        "--material",
        type=str,
        default=None,
        help="Quick mode: material name (e.g. Iron)",
    )
    parser.add_argument(
        "--mass",
        type=float,
        default=None,
        help="Quick mode: mass in kg (requires --material)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        dest="spec_file",
        help="Path to a custom structure spec JSON file",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh isotope data from IAEA AME",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"quarksum {__version__}",
    )

    args = parser.parse_args(argv)

    if args.menu:
        return _run_menu(args)

    if args.list_structures:
        from sigma_ground.inventory.builder import list_structures
        _json_out(list_structures())
        return 0

    if args.spec:
        from sigma_ground.inventory.builder import load_structure_spec
        from sigma_ground.inventory.defaults import DEFAULT_ID
        name = args.structure or DEFAULT_ID
        spec = load_structure_spec(name)
        if spec is None:
            _err(f"unknown structure: '{name}'. Use --list to see available structures.")
            return 1
        _json_out(spec)
        return 0

    if args.behaviors is not None:
        from sigma_ground.inventory.models.quark import Quark
        flavor = args.behaviors.lower().replace("-", "_")
        factory = getattr(Quark, flavor, None)
        if factory is None:
            _err(f"unknown quark flavor: '{args.behaviors}'. "
                 f"Options: up, down, strange, charm, bottom, top")
            return 1
        quark = factory(color=args.color)

        if args.apply:
            if args.env is None:
                _err("--env is required when using --apply")
                return 1
            try:
                env = json.loads(args.env)
            except json.JSONDecodeError as exc:
                _err(f"invalid --env JSON: {exc}")
                return 1
            from sigma_ground.inventory.behaviors import apply_env
            try:
                result = apply_env(quark, env, mode=args.mode)
            except (ValueError, TypeError) as exc:
                _err(str(exc))
                return 1
            _json_out(result)
        else:
            from sigma_ground.inventory.behaviors.quark_behaviors import compute_quark_behaviors
            _json_out(compute_quark_behaviors(quark))
        return 0

    if args.refresh:
        from sigma_ground.inventory.data.refresh_isotopes import refresh
        def _progress(i: int, total: int, desc: str) -> None:
            print(f"  [{i}/{total}] {desc}", file=sys.stderr)
        result = refresh(on_progress=_progress)
        _json_out(result)
        return 0

    if args.material is not None:
        if args.mass is None:
            _err("--mass is required when using --material")
            return 1
        from sigma_ground.inventory.builder import build_quick_structure
        try:
            structure = build_quick_structure(args.material, args.mass)
        except KeyError as exc:
            _err(str(exc))
            return 1

    elif args.spec_file is not None:
        import pathlib
        path = pathlib.Path(args.spec_file)
        if not path.exists():
            _err(f"file not found: {args.spec_file}")
            return 1
        spec = json.loads(path.read_text(encoding="utf-8"))
        from sigma_ground.inventory.builder import build_structure_from_spec
        try:
            structure = build_structure_from_spec(spec)
        except Exception as exc:
            _err(f"invalid structure spec: {exc}")
            return 1

    else:
        from sigma_ground.inventory.builder import load_structure
        from sigma_ground.inventory.defaults import DEFAULT_ID, by_id
        is_default_load = (args.structure is None)
        name = args.structure or DEFAULT_ID
        structure = load_structure(name)
        if structure is None:
            _err(f"unknown structure: '{name}'. Use --list to see available structures.")
            return 1
        if is_default_load:
            dflt = by_id(DEFAULT_ID)
            if dflt:
                print(dflt.message, file=sys.stderr)

    _selected_load_id = (
        args.structure
        if args.structure is not None
        else (DEFAULT_ID if not args.material and not args.spec_file else None)
    )

    if args.physics:
        from sigma_ground.inventory.physics import compute_physics
        from sigma_ground.inventory.defaults import by_id as _by_id
        dflt = _by_id(_selected_load_id) if _selected_load_id else None
        radius_m = dflt.radius_m if dflt else None
        result = compute_physics(structure, radius_m=radius_m)
        _json_out(result)
        return 0

    if args.inventory:
        from sigma_ground.inventory.checksum.particle_inventory import compute_particle_inventory
        result = compute_particle_inventory(structure)
    elif args.quark_chain:
        from sigma_ground.inventory.checksum.quark_chain import compute_quark_chain_checksum
        result = compute_quark_chain_checksum(structure)
    else:
        from sigma_ground.inventory.checksum.stoq_checksum import compute_stoq_checksum
        result = compute_stoq_checksum(structure)

    _json_out(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
