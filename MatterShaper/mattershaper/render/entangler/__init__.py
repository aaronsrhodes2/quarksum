"""
Entangler — Physics-aware push renderer.

Matter draws itself. Light is just the question.
No ray tracing. No intersection tests. No borrowed code.

Architecture:
  1. Light source emits (activation trigger)
  2. Surface nodes on analytic quadrics compute their response
  3. Nodes project themselves onto the pixel grid
  4. Depth buffer resolves occlusion

Zero shared code with ray tracers.
"""

from .vec import Vec3
from .surface_nodes import SurfaceNode, generate_surface_nodes
from .projection import PushCamera, project_node
from .illumination import PushLight, illuminate_node
from .engine import entangle, entangle_to_file

__all__ = [
    'Vec3',
    'SurfaceNode', 'generate_surface_nodes',
    'PushCamera', 'project_node',
    'PushLight', 'illuminate_node',
    'entangle', 'entangle_to_file',
]
