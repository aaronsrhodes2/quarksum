"""
MatterShaper — Physics-based scene renderer for SSBM.

Build a scene. Add objects. Render it. Pure math, zero dependencies.

    from mattershaper import MatterShaper

    ms = MatterShaper()

    # Add objects
    ms.sphere(pos=(0, 0.5, -3), radius=0.5, material='ceramic')
    ms.sphere(pos=(1.5, 0.3, -3), radius=0.3, material='steel')
    ms.plane(y=0, material='basalt')

    # Add lights
    ms.light(pos=(3, 5, 2), color=(1, 0.95, 0.9), intensity=1.0)

    # Render
    ms.camera(pos=(0, 2, 2), look_at=(0, 0, -3))
    ms.render('my_scene.svg', width=400, height=300)
    ms.render('my_scene.png', width=400, height=300)

Materials can be strings (from the library: 'ceramic', 'steel', 'glass',
'water', 'basalt', 'iron', 'ice', 'carbon', 'silicate', 'regolith')
or custom Material objects.

Architecture:
    Materia  → σ(x,y,z) at every point in the scene
    QuarkSum → material properties at that σ
    MatterShaper → geometry + lighting + projection → pixels

Zero external rendering dependencies. Pure math.
"""

from .shaper import MatterShaper
from .geometry import Vec3, Sphere, Ellipsoid, Plane, rotation_matrix
from .materials import Material
from .materials.library import ALL_MATERIALS
from .render import PushCamera, PushLight
from .signature import ShapeSignature

__version__ = "0.1.0"
__all__ = [
    'MatterShaper', 'ShapeSignature',
    'Vec3', 'Sphere', 'Ellipsoid', 'Plane', 'rotation_matrix',
    'Material', 'PushCamera', 'PushLight',
]
