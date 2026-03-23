"""
Remap Library — re-runs Nagatha's physics pipeline on all real-world objects.

Skips geometric test primitives (sphere, cylinder, cone, capsule, mobius).
Overwrites existing .shape.json / .color.json with physics-built versions.
Re-generates HTML viewer for each.

Usage:
    python gallery/remap_library.py
    python gallery/remap_library.py --only coffee_mug hammer brick
    python gallery/remap_library.py --skip banana egg   # skip specific objects
"""

import sys
import json
import time
import argparse
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from agent.nagatha import (
    Nagatha, MAPS_DIR, parse_manifest_from_response,
    _try_physics_builder, _resolve_color_map, validate_maps,
)
from gallery.sigma_to_html import sigma_to_html

# ── Objects to skip (geometric test primitives, not real-world) ───────────────
SKIP_ALWAYS = {
    'sphere', 'cylinder', 'cone', 'capsule', 'mobius',
}

# ── Objects where physics pipeline is especially important ────────────────────
# Listed first so failures are obvious early
PRIORITY = [
    'brick', 'coffee_mug', 'hammer', 'beer_bottle', 'wine_bottle',
    'fire_hydrant', 'rubber_duck', 'dumbbell', 'toaster',
]


def remap_one(nagatha: Nagatha, key: str, dry_run: bool = False) -> dict:
    """Run the physics pipeline for one object. Returns a result dict."""
    t0 = time.time()
    result = {'key': key, 'status': 'pending', 'layers': 0, 'elapsed': 0}

    print(f"\n{'-'*60}")
    print(f"  Remapping: {key}")
    print(f"{'-'*60}")

    # ── Physics pipeline ──────────────────────────────────────────
    manifest_prompt = nagatha.brain.build_manifest_prompt(key.replace('_', ' '))
    try:
        response = nagatha.llm.generate(nagatha._system_prompt, manifest_prompt)
    except Exception as e:
        print(f"  [ERROR] LLM call failed: {e}")
        result.update(status='llm_error', elapsed=round(time.time()-t0, 1))
        return result

    manifest = parse_manifest_from_response(response)
    shape_map = None

    if manifest:
        shape_map = _try_physics_builder(manifest)
    else:
        print(f"  [WARN] No manifest parsed — falling back to legacy SHAPE_MAP")

    if not shape_map:
        # Fallback: legacy shape map path
        user_prompt = nagatha.brain.build_mapping_prompt(key.replace('_', ' '))
        try:
            response2 = nagatha.llm.generate(nagatha._system_prompt, user_prompt)
        except Exception as e:
            print(f"  [ERROR] Legacy LLM call failed: {e}")
            result.update(status='llm_error', elapsed=round(time.time()-t0, 1))
            return result
        from agent.nagatha import parse_maps_from_response, _normalize_shape_map
        shape_map, _ = parse_maps_from_response(response2)

    if not shape_map:
        print(f"  [ERROR] No valid shape map produced")
        result.update(status='parse_error', elapsed=round(time.time()-t0, 1))
        return result

    # ── Color resolution ──────────────────────────────────────────
    color_map = _resolve_color_map(shape_map)

    # ── Validate ──────────────────────────────────────────────────
    errors, warnings = validate_maps(shape_map, color_map)
    for w in warnings:
        print(f"  [note] {w}")
    for e in errors:
        print(f"  [problem] {e}")

    if errors:
        print(f"  [ERROR] Validation failed — keeping old maps")
        result.update(status='validation_error', errors=errors,
                      elapsed=round(time.time()-t0, 1))
        return result

    # ── Analyze & fix ─────────────────────────────────────────────
    shape_map, color_map, fix_log = nagatha.analyze_and_fix(shape_map, color_map)
    if fix_log:
        for f in fix_log:
            print(f"  [fix] {f}")

    if dry_run:
        print(f"  [DRY RUN] Would save {len(shape_map['layers'])} layers")
        result.update(status='dry_run', layers=len(shape_map['layers']),
                      elapsed=round(time.time()-t0, 1))
        return result

    # ── Save maps ─────────────────────────────────────────────────
    shape_path = MAPS_DIR / f"{key}.shape.json"
    color_path = MAPS_DIR / f"{key}.color.json"
    shape_path.write_text(json.dumps(shape_map, indent=2, ensure_ascii=False),
                          encoding='utf-8')
    color_path.write_text(json.dumps(color_map, indent=2, ensure_ascii=False),
                          encoding='utf-8')
    print(f"  [SAVED] {key}.shape.json  ({len(shape_map['layers'])} layers)")

    # ── Regenerate HTML viewer ────────────────────────────────────
    html_dir = PROJECT_DIR / 'gallery' / 'html_scenes'
    html_dir.mkdir(exist_ok=True)
    try:
        html_path = html_dir / f"{key}.html"
        sigma_to_html(key, shape_map, color_map, str(html_path))
        print(f"  [HTML] {key}.html regenerated")
    except Exception as e:
        print(f"  [WARN] HTML generation failed: {e}")

    result.update(
        status='ok',
        layers=len(shape_map['layers']),
        materials=len(color_map['materials']),
        physics='physics' in shape_map,
        elapsed=round(time.time()-t0, 1),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description='Remap library objects with physics pipeline')
    parser.add_argument('--only', nargs='+', metavar='KEY',
                        help='Remap only these keys')
    parser.add_argument('--skip', nargs='+', metavar='KEY',
                        help='Skip these keys (in addition to geometric primitives)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run pipeline but do not write files')
    parser.add_argument('--backend', default='ollama',
                        help='LLM backend (ollama, anthropic)')
    parser.add_argument('--model', default='qwen2.5:14b',
                        help='Model name for ollama backend')
    args = parser.parse_args()

    # Build object list
    index_path = MAPS_DIR / 'library_index.json'
    if not index_path.exists():
        print("ERROR: library_index.json not found")
        sys.exit(1)

    library = json.loads(index_path.read_text(encoding='utf-8'))
    all_keys = list(library.get('objects', {}).keys())

    skip = SKIP_ALWAYS | set(args.skip or [])

    if args.only:
        keys = [k for k in args.only if k in all_keys]
    else:
        # Priority objects first, then the rest
        rest = [k for k in all_keys if k not in PRIORITY and k not in skip]
        keys = [k for k in PRIORITY if k not in skip] + rest

    print(f"\nNagatha Library Remap — Physics Pipeline")
    print(f"{'='*60}")
    print(f"Objects to remap : {len(keys)}")
    print(f"Skipping         : {sorted(skip)}")
    print(f"Backend          : {args.backend}")
    print(f"Dry run          : {args.dry_run}")
    print()

    # Initialise Nagatha
    if args.backend == 'ollama':
        nagatha = Nagatha(backend='ollama', model=args.model)
    else:
        nagatha = Nagatha(backend='anthropic')

    # Run
    results = []
    for i, key in enumerate(keys, 1):
        print(f"\n[{i}/{len(keys)}]", end='')
        r = remap_one(nagatha, key, dry_run=args.dry_run)
        results.append(r)

    # Summary
    ok      = [r for r in results if r['status'] == 'ok']
    physics = [r for r in ok if r.get('physics')]
    fallback = [r for r in ok if not r.get('physics')]
    errors  = [r for r in results if r['status'] not in ('ok', 'dry_run')]

    print(f"\n{'='*60}")
    print(f"  REMAP COMPLETE")
    print(f"{'='*60}")
    print(f"  Success (physics) : {len(physics)}")
    print(f"  Success (fallback): {len(fallback)}")
    print(f"  Errors            : {len(errors)}")
    if errors:
        for r in errors:
            print(f"    {r['key']:20s} — {r['status']}")
    total_time = sum(r['elapsed'] for r in results)
    print(f"  Total time        : {total_time:.0f}s")
    print()


if __name__ == '__main__':
    main()
