"""
OBJ + MTL Mesh Parser — Pure Python, Zero Dependencies
=======================================================
Reads Wavefront OBJ files (the format ShapeNet uses) and their
associated MTL material files into structured Python data.

Part of the Nagatha harvest pipeline.
"One does not simply pillage a dataset. We parse politely."
"""

import os
import math
from typing import Dict, List, Tuple, Optional


class Material:
    """A single material from an MTL file."""
    __slots__ = ('name', 'diffuse', 'specular', 'shininess', 'ambient',
                 'opacity', 'diffuse_map')

    def __init__(self, name: str):
        self.name = name
        self.diffuse = (0.8, 0.8, 0.8)      # Kd — default light grey
        self.specular = (1.0, 1.0, 1.0)      # Ks
        self.shininess = 10.0                  # Ns
        self.ambient = (0.2, 0.2, 0.2)        # Ka
        self.opacity = 1.0                     # d or Tr
        self.diffuse_map = None                # map_Kd (texture path, for reference)

    def to_sigma_material(self) -> dict:
        """Convert to Sigma color map entry."""
        return {
            "r": round(self.diffuse[0], 4),
            "g": round(self.diffuse[1], 4),
            "b": round(self.diffuse[2], 4),
            "specular": round(max(self.specular), 3),
            "shininess": round(self.shininess, 1)
        }

    def __repr__(self):
        return f"Material({self.name}, Kd={self.diffuse})"


class MeshGroup:
    """A named group of faces sharing a material."""
    __slots__ = ('name', 'material_name', 'face_indices', 'vertices',
                 'normals', 'centroid', 'bbox_min', 'bbox_max')

    def __init__(self, name: str, material_name: str = "default"):
        self.name = name
        self.material_name = material_name
        self.face_indices: List[List[int]] = []  # each face = list of vertex indices
        self.vertices: List[Tuple[float, float, float]] = []  # populated after extraction
        self.normals: List[Tuple[float, float, float]] = []
        self.centroid = (0.0, 0.0, 0.0)
        self.bbox_min = (0.0, 0.0, 0.0)
        self.bbox_max = (0.0, 0.0, 0.0)

    @property
    def face_count(self):
        return len(self.face_indices)

    @property
    def vertex_count(self):
        return len(self.vertices)

    def __repr__(self):
        return f"MeshGroup({self.name}, faces={self.face_count}, mat={self.material_name})"


class ParsedMesh:
    """Complete parsed result from an OBJ file."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.all_vertices: List[Tuple[float, float, float]] = []
        self.all_normals: List[Tuple[float, float, float]] = []
        self.all_texcoords: List[Tuple[float, float]] = []
        self.groups: List[MeshGroup] = []
        self.materials: Dict[str, Material] = {}
        self.total_faces = 0
        self.bbox_min = (0.0, 0.0, 0.0)
        self.bbox_max = (0.0, 0.0, 0.0)
        self.centroid = (0.0, 0.0, 0.0)

    @property
    def total_vertices(self):
        return len(self.all_vertices)

    @property
    def group_count(self):
        return len(self.groups)

    def summary(self) -> str:
        lines = [
            f"Mesh: {self.filename}",
            f"  Vertices: {self.total_vertices:,}",
            f"  Faces: {self.total_faces:,}",
            f"  Groups: {self.group_count}",
            f"  Materials: {len(self.materials)}",
            f"  BBox: ({self.bbox_min[0]:.3f}, {self.bbox_min[1]:.3f}, {self.bbox_min[2]:.3f}) → "
            f"({self.bbox_max[0]:.3f}, {self.bbox_max[1]:.3f}, {self.bbox_max[2]:.3f})",
        ]
        for g in self.groups:
            lines.append(f"    [{g.name}] {g.face_count} faces, mat={g.material_name}")
        return "\n".join(lines)


def parse_mtl(filepath: str) -> Dict[str, Material]:
    """
    Parse a Wavefront MTL file into Material objects.

    Handles: newmtl, Ka, Kd, Ks, Ns, d, Tr, map_Kd
    Gracefully ignores unknown directives.
    """
    materials = {}
    current = None

    if not os.path.exists(filepath):
        return materials

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split(None, 1)
            if len(parts) < 1:
                continue

            key = parts[0].lower()
            val = parts[1] if len(parts) > 1 else ""

            if key == 'newmtl':
                name = val.strip()
                current = Material(name)
                materials[name] = current

            elif current is None:
                continue  # skip directives before first newmtl

            elif key == 'kd':
                current.diffuse = _parse_rgb(val)

            elif key == 'ks':
                current.specular = _parse_rgb(val)

            elif key == 'ka':
                current.ambient = _parse_rgb(val)

            elif key == 'ns':
                try:
                    current.shininess = float(val.strip())
                except ValueError:
                    pass

            elif key == 'd':
                try:
                    current.opacity = float(val.strip())
                except ValueError:
                    pass

            elif key == 'tr':
                # Tr = 1 - d (transparency vs opacity)
                try:
                    current.opacity = 1.0 - float(val.strip())
                except ValueError:
                    pass

            elif key == 'map_kd':
                current.diffuse_map = val.strip()

    return materials


def parse_obj(filepath: str, merge_by_material: bool = True) -> ParsedMesh:
    """
    Parse a Wavefront OBJ file into a ParsedMesh.

    Args:
        filepath: Path to the .obj file
        merge_by_material: If True, merge groups that share a material name.
                          This produces cleaner segments for primitive fitting.

    Returns:
        ParsedMesh with all vertices, faces, groups, and materials populated.
        Each group's vertices are extracted (duplicated from global list)
        with bounding boxes and centroids computed.
    """
    mesh = ParsedMesh(filepath)

    # ── Phase 1: Read raw data ──────────────────────────────────
    raw_groups = []  # list of (group_name, material_name, faces)
    current_group_name = "default"
    current_material = "default"
    current_faces = []

    obj_dir = os.path.dirname(filepath)

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            key = parts[0]

            if key == 'v' and len(parts) >= 4:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                mesh.all_vertices.append((x, y, z))

            elif key == 'vn' and len(parts) >= 4:
                nx, ny, nz = float(parts[1]), float(parts[2]), float(parts[3])
                mesh.all_normals.append((nx, ny, nz))

            elif key == 'vt' and len(parts) >= 3:
                u, v = float(parts[1]), float(parts[2])
                mesh.all_texcoords.append((u, v))

            elif key == 'f':
                face_verts = []
                for token in parts[1:]:
                    # Handle f v, f v/vt, f v/vt/vn, f v//vn
                    indices = token.split('/')
                    vi = int(indices[0])
                    # OBJ indices are 1-based, can be negative
                    if vi < 0:
                        vi = len(mesh.all_vertices) + vi
                    else:
                        vi -= 1
                    face_verts.append(vi)
                current_faces.append(face_verts)
                mesh.total_faces += 1

            elif key == 'g' or key == 'o':
                # Save current group, start new one
                if current_faces:
                    raw_groups.append((current_group_name, current_material, current_faces))
                    current_faces = []
                current_group_name = parts[1] if len(parts) > 1 else "default"

            elif key == 'usemtl':
                # Material change — save current faces, start new segment
                if current_faces:
                    raw_groups.append((current_group_name, current_material, current_faces))
                    current_faces = []
                current_material = parts[1] if len(parts) > 1 else "default"

            elif key == 'mtllib':
                mtl_name = parts[1] if len(parts) > 1 else ""
                mtl_path = os.path.join(obj_dir, mtl_name)
                mesh.materials = parse_mtl(mtl_path)

    # Don't forget the last group
    if current_faces:
        raw_groups.append((current_group_name, current_material, current_faces))

    # ── Phase 2: Merge groups by material (optional) ────────────
    if merge_by_material:
        merged = {}  # material_name → (group_name, faces)
        for gname, matname, faces in raw_groups:
            if matname in merged:
                merged[matname][1].extend(faces)
            else:
                merged[matname] = [gname, faces]

        final_groups = [(data[0], matname, data[1]) for matname, data in merged.items()]
    else:
        final_groups = raw_groups

    # ── Phase 3: Build MeshGroup objects with extracted vertices ─
    for gname, matname, faces in final_groups:
        group = MeshGroup(gname, matname)
        group.face_indices = faces

        # Collect unique vertex indices used by this group
        used_indices = set()
        for face in faces:
            for vi in face:
                if 0 <= vi < len(mesh.all_vertices):
                    used_indices.add(vi)

        # Extract the actual vertex positions
        group.vertices = [mesh.all_vertices[vi] for vi in sorted(used_indices)]

        if group.vertices:
            _compute_bounds(group)

        mesh.groups.append(group)

    # ── Phase 4: Global bounds ──────────────────────────────────
    if mesh.all_vertices:
        xs = [v[0] for v in mesh.all_vertices]
        ys = [v[1] for v in mesh.all_vertices]
        zs = [v[2] for v in mesh.all_vertices]
        mesh.bbox_min = (min(xs), min(ys), min(zs))
        mesh.bbox_max = (max(xs), max(ys), max(zs))
        mesh.centroid = (
            sum(xs) / len(xs),
            sum(ys) / len(ys),
            sum(zs) / len(zs)
        )

    # If no MTL was loaded, create a default material
    if not mesh.materials:
        mesh.materials["default"] = Material("default")

    return mesh


def _compute_bounds(group: MeshGroup):
    """Compute centroid, bbox_min, bbox_max for a group's vertices."""
    verts = group.vertices
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    n = len(verts)
    group.centroid = (sum(xs) / n, sum(ys) / n, sum(zs) / n)
    group.bbox_min = (min(xs), min(ys), min(zs))
    group.bbox_max = (max(xs), max(ys), max(zs))


def _parse_rgb(val: str) -> Tuple[float, float, float]:
    """Parse an RGB triplet from a string like '0.8 0.2 0.1'."""
    parts = val.strip().split()
    try:
        r = max(0.0, min(1.0, float(parts[0])))
        g = max(0.0, min(1.0, float(parts[1]))) if len(parts) > 1 else r
        b = max(0.0, min(1.0, float(parts[2]))) if len(parts) > 2 else r
        return (r, g, b)
    except (ValueError, IndexError):
        return (0.8, 0.8, 0.8)


# ── Convenience: scan a directory for OBJ files ─────────────────

def scan_for_objs(directory: str, recursive: bool = True) -> List[str]:
    """
    Find all .obj files in a directory.

    Args:
        directory: Root directory to scan
        recursive: If True, walk subdirectories (ShapeNet structure)

    Returns:
        Sorted list of absolute paths to .obj files
    """
    results = []
    if recursive:
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.lower().endswith('.obj'):
                    results.append(os.path.join(root, f))
    else:
        for f in os.listdir(directory):
            if f.lower().endswith('.obj'):
                results.append(os.path.join(directory, f))

    return sorted(results)


# ── Self-test ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isfile(path):
            m = parse_obj(path)
            print(m.summary())
            print(f"\nMaterials:")
            for name, mat in m.materials.items():
                print(f"  {mat} → sigma: {mat.to_sigma_material()}")
        elif os.path.isdir(path):
            objs = scan_for_objs(path)
            print(f"Found {len(objs)} OBJ files in {path}")
            for p in objs[:10]:
                print(f"  {p}")
            if len(objs) > 10:
                print(f"  ... and {len(objs) - 10} more")
        else:
            print(f"Not found: {path}")
    else:
        print("Usage: python obj_parser.py <file.obj | directory>")
        print("Parses OBJ meshes for the Nagatha harvest pipeline.")
