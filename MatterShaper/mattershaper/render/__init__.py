"""
Renderer — push projection. Matter draws itself.

No rays. No intersection tests. Surface nodes project onto the pixel grid.
The light activates nodes. Nodes respond. Nodes project. Depth resolves.

All lighting is electromagnetic → σ-INVARIANT.

Public API:
    entangle()   — full renderer (Beer-Lambert, shadows, foreshortening)
    PushCamera   — passive pixel-grid receiver
    PushLight    — activation signal

    All from mattershaper.render.entangler. The legacy push.py renderer
    still exists for shaper.py and render_push_test.py, but is not
    exported here.
"""

from .entangler.engine      import entangle
from .entangler.projection  import PushCamera, project_node
from .entangler.illumination import PushLight
from .red_carpet import red_carpet_render

__all__ = [
    'entangle',
    'PushCamera', 'PushLight', 'project_node',
    'red_carpet_render',
]
