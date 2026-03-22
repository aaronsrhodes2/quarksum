"""
Mesh-to-Sigma Converter — Pure Python, Zero Dependencies
=========================================================
Converts an OBJ mesh file into Sigma Signature format
(.shape.json + .color.json) by:
  1. Parsing the OBJ and its materials
  2. Analyzing mesh complexity to decide primitive count
  3. Segmenting the mesh intelligently
  4. Fitting primitives to each segment
  5. Extracting materials into a color map
  6. Normalizing to consistent scale

This is Nagatha's eye — how she sees polygon soup and
reimagines it as clean analytic geometry.

"Right then, let's see what we're working with."
"""

import os
import json
import math
import random
from typing import Dict, List, Tuple, Optional

from obj_parser import parse_obj, ParsedMesh, MeshGroup, Material
from primitive_fitter import (
    fit_primitive, fit_mesh_groups, normalize_to_unit,
    compute_fit_quality, FittedPrimitive,
    covariance_matrix_3x3, jacobi_eigen_3x3
)


# ── Complexity Analyzer ──────────────────────────────────────────

class ComplexityAnalyzer:
    """
    Nagatha's judgment on how many primitives an object deserves.

    She doesn't just count faces — she considers:
    - Number of distinct material regions
    - Geometric spread (is it compact or sprawling?)
    - Group count from the original modeling
    - Vertex count as a complexity proxy
    - Aspect ratio (tall thin vs squat round)

    "A teacup wants eight primitives. A grand piano wants forty.
     One does not force a budget upon the geometry."
    """

    # Rough guidelines — she'll adjust from here
    MIN_PRIMITIVES = 4
    MAX_PRIMITIVES = 50
    SWEET_SPOT = 12  # Nagatha's favorite — enough to be recognizable

    @staticmethod
    def estimate_primitive_count(mesh: ParsedMesh) -> int:
        """
        Decide how many primitives this object deserves.

        Returns an integer — Nagatha's professional opinion.
        """
        # Base factors
        n_groups = mesh.group_count
        n_materials = len(mesh.materials)
        n_vertices = mesh.total_vertices
        n_faces = mesh.total_faces

        # Geometric complexity: aspect ratio of bounding box
        dx = mesh.bbox_max[0] - mesh.bbox_min[0]
        dy = mesh.bbox_max[1] - mesh.bbox_min[1]
        dz = mesh.bbox_max[2] - mesh.bbox_min[2]
        extents = sorted([max(dx, 0.001), max(dy, 0.001), max(dz, 0.001)])
        aspect = extents[2] / extents[0]  # longest / shortest

        # Start with the number of material regions
        # (most meaningful semantic division)
        base = max(n_groups, n_materials)

        # Adjust for geometric complexity
        if n_vertices > 10000:
            base = max(base, 15)
        elif n_vertices > 5000:
            base = max(base, 10)
        elif n_vertices > 1000:
            base = max(base, 8)

        # High aspect ratio = probably needs more primitives along its length
        if aspect > 5.0:
            base = int(base * 1.5)
        elif aspect > 3.0:
            base = int(base * 1.2)

        # Objects with many materials likely have detail
        if n_materials > 5:
            base = max(base, n_materials + 3)

        # Clamp to reasonable range
        count = max(ComplexityAnalyzer.MIN_PRIMITIVES,
                    min(ComplexityAnalyzer.MAX_PRIMITIVES, base))

        return count

    @staticmethod
    def describe_complexity(mesh: ParsedMesh, target_primitives: int) -> str:
        """Nagatha's assessment, in her own words."""
        if target_primitives <= 6:
            adjective = "simple little"
        elif target_primitives <= 12:
            adjective = "modest"
        elif target_primitives <= 20:
            adjective = "rather detailed"
        elif target_primitives <= 35:
            adjective = "quite involved"
        else:
            adjective = "properly complex"

        return (f"A {adjective} piece — {mesh.total_vertices:,} vertices, "
                f"{mesh.total_faces:,} faces, {len(mesh.materials)} materials. "
                f"I'll represent it with {target_primitives} primitives.")


# ── Intelligent Segmentation ─────────────────────────────────────

class MeshSegmenter:
    """
    When the OBJ's own groups aren't enough (or there are too many),
    Nagatha re-segments the mesh to match her target primitive count.

    Strategy:
    - If OBJ has good groups ≈ target count: use them directly
    - If too few groups: subdivide large groups spatially
    - If too many groups: merge small adjacent groups
    """

    @staticmethod
    def segment(mesh: ParsedMesh, target_count: int) -> List[MeshGroup]:
        """
        Produce approximately target_count segments from the mesh.
        """
        groups = mesh.groups

        if not groups:
            # No groups at all — create one big group
            return MeshSegmenter._segment_from_scratch(mesh, target_count)

        current_count = len(groups)

        if abs(current_count - target_count) <= 2:
            # Close enough — use as-is
            return groups

        elif current_count < target_count:
            # Need to subdivide large groups
            return MeshSegmenter._subdivide(groups, target_count, mesh)

        else:
            # Need to merge small groups
            return MeshSegmenter._merge(groups, target_count)

    @staticmethod
    def _segment_from_scratch(mesh: ParsedMesh, target_count: int) -> List[MeshGroup]:
        """
        No groups at all — divide vertices spatially using axis-aligned slicing.
        """
        if not mesh.all_vertices:
            return []

        # Find the longest axis and slice along it
        dx = mesh.bbox_max[0] - mesh.bbox_min[0]
        dy = mesh.bbox_max[1] - mesh.bbox_min[1]
        dz = mesh.bbox_max[2] - mesh.bbox_min[2]

        if dx >= dy and dx >= dz:
            axis = 0
        elif dy >= dz:
            axis = 1
        else:
            axis = 2

        # Sort vertices by position along the chosen axis
        sorted_verts = sorted(mesh.all_vertices, key=lambda v: v[axis])
        chunk_size = max(1, len(sorted_verts) // target_count)

        groups = []
        for i in range(target_count):
            start = i * chunk_size
            end = start + chunk_size if i < target_count - 1 else len(sorted_verts)
            chunk = sorted_verts[start:end]
            if not chunk:
                continue

            g = MeshGroup(f"segment_{i}", "default")
            g.vertices = chunk
            # Compute bounds
            xs = [v[0] for v in chunk]
            ys = [v[1] for v in chunk]
            zs = [v[2] for v in chunk]
            n = len(chunk)
            g.centroid = (sum(xs)/n, sum(ys)/n, sum(zs)/n)
            g.bbox_min = (min(xs), min(ys), min(zs))
            g.bbox_max = (max(xs), max(ys), max(zs))
            groups.append(g)

        return groups

    @staticmethod
    def _subdivide(groups: List[MeshGroup], target_count: int,
                   mesh: ParsedMesh) -> List[MeshGroup]:
        """Split the largest groups until we reach target count."""
        result = list(groups)

        while len(result) < target_count:
            # Find largest group by vertex count
            largest_idx = max(range(len(result)),
                            key=lambda i: len(result[i].vertices))
            largest = result[largest_idx]

            if len(largest.vertices) < 8:
                break  # Can't split further

            # Split along its longest axis
            dx = largest.bbox_max[0] - largest.bbox_min[0]
            dy = largest.bbox_max[1] - largest.bbox_min[1]
            dz = largest.bbox_max[2] - largest.bbox_min[2]

            if dx >= dy and dx >= dz:
                axis = 0
            elif dy >= dz:
                axis = 1
            else:
                axis = 2

            mid = (largest.bbox_min[axis] + largest.bbox_max[axis]) / 2.0
            lower_verts = [v for v in largest.vertices if v[axis] <= mid]
            upper_verts = [v for v in largest.vertices if v[axis] > mid]

            if not lower_verts or not upper_verts:
                break  # Can't split meaningfully

            g1 = MeshGroup(f"{largest.name}_a", largest.material_name)
            g1.vertices = lower_verts
            _compute_group_bounds(g1)

            g2 = MeshGroup(f"{largest.name}_b", largest.material_name)
            g2.vertices = upper_verts
            _compute_group_bounds(g2)

            result[largest_idx] = g1
            result.append(g2)

        return result

    @staticmethod
    def _merge(groups: List[MeshGroup], target_count: int) -> List[MeshGroup]:
        """Merge smallest groups into their nearest neighbor."""
        result = list(groups)

        while len(result) > target_count and len(result) > 1:
            # Find smallest group
            smallest_idx = min(range(len(result)),
                             key=lambda i: len(result[i].vertices))
            smallest = result[smallest_idx]

            # Find nearest other group by centroid distance
            best_dist = float('inf')
            best_idx = -1
            for i, g in enumerate(result):
                if i == smallest_idx:
                    continue
                d = _dist3(smallest.centroid, g.centroid)
                if d < best_dist:
                    best_dist = d
                    best_idx = i

            if best_idx < 0:
                break

            # Merge smallest into nearest
            target = result[best_idx]
            target.vertices = target.vertices + smallest.vertices
            target.face_indices = target.face_indices + smallest.face_indices
            _compute_group_bounds(target)

            result.pop(smallest_idx)

        return result


def _compute_group_bounds(group: MeshGroup):
    """Recompute centroid and bbox for a group."""
    if not group.vertices:
        return
    xs = [v[0] for v in group.vertices]
    ys = [v[1] for v in group.vertices]
    zs = [v[2] for v in group.vertices]
    n = len(group.vertices)
    group.centroid = (sum(xs)/n, sum(ys)/n, sum(zs)/n)
    group.bbox_min = (min(xs), min(ys), min(zs))
    group.bbox_max = (max(xs), max(ys), max(zs))


def _dist3(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)


# ── Main Converter ───────────────────────────────────────────────

class MeshToSigma:
    """
    The full conversion pipeline.

    Takes an OBJ file path, produces .shape.json and .color.json
    in Sigma Signature format, ready for MatterShaper rendering.

    This is Nagatha's analytical core — her ability to look at
    raw geometry and see the clean primitives underneath.
    """

    def __init__(self, normalize_height: float = 1.0, verbose: bool = True):
        self.normalize_height = normalize_height
        self.verbose = verbose
        self.analyzer = ComplexityAnalyzer()

    def convert(self, obj_path: str,
                output_dir: str = None,
                object_name: str = None) -> Optional[dict]:
        """
        Convert an OBJ file to Sigma Signature format.

        Args:
            obj_path: Path to the .obj file
            output_dir: Where to write the JSON files (default: same dir)
            object_name: Name for the object (default: derived from filename)

        Returns:
            dict with keys: name, shape_path, color_path, shape_map, color_map,
                           quality, primitive_count, analysis
            or None if conversion failed
        """
        if not os.path.exists(obj_path):
            if self.verbose:
                print(f"  [Nagatha] Can't find that file. {obj_path}")
            return None

        # ── Step 1: Parse ────────────────────────────────────────
        if self.verbose:
            print(f"  [Nagatha] Right then, let's see what we're working with...")

        mesh = parse_obj(obj_path, merge_by_material=True)

        if mesh.total_vertices < 4:
            if self.verbose:
                print(f"  [Nagatha] Barely anything here — {mesh.total_vertices} vertices.")
                print(f"           Not enough to work with, I'm afraid.")
            return None

        # ── Step 2: Analyze complexity ───────────────────────────
        target_primitives = self.analyzer.estimate_primitive_count(mesh)
        if self.verbose:
            print(f"  [Nagatha] {self.analyzer.describe_complexity(mesh, target_primitives)}")

        # ── Step 3: Segment ──────────────────────────────────────
        if self.verbose:
            print(f"  [Nagatha] Breaking it down into regions...")

        segments = MeshSegmenter.segment(mesh, target_primitives)

        if not segments:
            if self.verbose:
                print(f"  [Nagatha] Couldn't find meaningful segments. Odd geometry.")
            return None

        if self.verbose:
            print(f"  [Nagatha] Found {len(segments)} workable regions.")

        # ── Step 4: Fit primitives ───────────────────────────────
        if self.verbose:
            print(f"  [Nagatha] Fitting primitives... this is the interesting bit.")

        primitives = fit_mesh_groups(segments, mesh.materials)

        if not primitives:
            if self.verbose:
                print(f"  [Nagatha] No primitives survived fitting. The mesh may be degenerate.")
            return None

        # ── Step 5: Normalize ────────────────────────────────────
        primitives = normalize_to_unit(primitives, self.normalize_height)

        # ── Step 6: Assess quality ───────────────────────────────
        quality = compute_fit_quality(primitives)

        if self.verbose:
            types = quality['type_distribution']
            type_str = ", ".join(f"{v} {k}{'s' if v > 1 else ''}" for k, v in types.items())
            print(f"  [Nagatha] {quality['primitive_count']} primitives — {type_str}.")
            print(f"           Confidence: {quality['avg_confidence']:.0%} — "
                  f"rated {quality['coverage_rating']}.")

        # ── Step 7: Build Sigma maps ─────────────────────────────
        if object_name is None:
            base = os.path.splitext(os.path.basename(obj_path))[0]
            object_name = base.replace('-', '_').replace(' ', '_').lower()

        shape_map = self._build_shape_map(primitives, object_name)
        color_map = self._build_color_map(primitives, mesh.materials)

        # ── Step 8: Write files ──────────────────────────────────
        if output_dir is None:
            output_dir = os.path.dirname(obj_path)

        os.makedirs(output_dir, exist_ok=True)

        shape_path = os.path.join(output_dir, f"{object_name}.shape.json")
        color_path = os.path.join(output_dir, f"{object_name}.color.json")

        with open(shape_path, 'w') as f:
            json.dump(shape_map, f, indent=2)
        with open(color_path, 'w') as f:
            json.dump(color_map, f, indent=2)

        if self.verbose:
            print(f"  [Nagatha] There we are. Written to:")
            print(f"           {shape_path}")
            print(f"           {color_path}")
            size_kb = (os.path.getsize(shape_path) + os.path.getsize(color_path)) / 1024
            print(f"           Total: {size_kb:.1f} KB — rather compact, if I say so myself.")

        return {
            "name": object_name,
            "shape_path": shape_path,
            "color_path": color_path,
            "shape_map": shape_map,
            "color_map": color_map,
            "quality": quality,
            "primitive_count": len(primitives),
            "source_vertices": mesh.total_vertices,
            "source_faces": mesh.total_faces,
            "analysis": {
                "target_primitives": target_primitives,
                "actual_primitives": len(primitives),
                "segments_found": len(segments),
                "materials_found": len(mesh.materials),
                "mesh_summary": mesh.summary()
            }
        }

    def _build_shape_map(self, primitives: List[FittedPrimitive],
                         object_name: str) -> dict:
        """Build the Sigma shape map JSON structure."""
        layers = []
        for i, prim in enumerate(primitives):
            layer = prim.to_sigma_layer(f"{prim.label}_{i}")
            layers.append(layer)

        return {
            "object": object_name,
            "format": "sigma_v1",
            "source": "shapenet_harvest",
            "converter": "nagatha_mesh_to_sigma",
            "layers": layers
        }

    def _build_color_map(self, primitives: List[FittedPrimitive],
                         materials: Dict[str, Material]) -> dict:
        """Build the Sigma color map JSON structure."""
        color_map = {"materials": {}}

        # Collect unique materials used by the primitives
        used_materials = set(p.material_name for p in primitives)

        for mat_name in used_materials:
            if mat_name in materials:
                mat = materials[mat_name]
                color_map["materials"][mat_name] = mat.to_sigma_material()
            else:
                # Default neutral material
                color_map["materials"][mat_name] = {
                    "r": 0.7, "g": 0.7, "b": 0.7,
                    "specular": 0.3,
                    "shininess": 10.0
                }

        return color_map


# ── Batch convenience ────────────────────────────────────────────

def convert_single(obj_path: str, output_dir: str = None,
                   name: str = None, verbose: bool = True) -> Optional[dict]:
    """Convenience function for converting a single OBJ file."""
    converter = MeshToSigma(verbose=verbose)
    return converter.convert(obj_path, output_dir, name)


# ── Self-test ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        obj_file = sys.argv[1]
        out_dir = sys.argv[2] if len(sys.argv) > 2 else None

        print("╔══════════════════════════════════════╗")
        print("║  N A G A T H A  —  M E S H  E Y E   ║")
        print("╚══════════════════════════════════════╝")
        print()

        result = convert_single(obj_file, out_dir)

        if result:
            print(f"\n  [Nagatha] Into the library it goes.")
            print(f"           Welcome home, little {result['name']}.")
        else:
            print(f"\n  [Nagatha] I'm afraid that one didn't make it through.")
            print(f"           Better luck next mesh, as they say.")
    else:
        print("Usage: python mesh_to_sigma.py <file.obj> [output_dir]")
        print()
        print("Converts an OBJ mesh to Sigma Signature format.")
        print("Nagatha decides how many primitives the object deserves.")
