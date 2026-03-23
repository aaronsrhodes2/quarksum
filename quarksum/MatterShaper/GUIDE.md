# MatterShaper — Scene Building Guide

Pure-math 3D renderer. Zero dependencies. Part of the SSBM project family.

```
Materia (spacetime) → QuarkSum (atoms) → local_library (POC)
                                          MatterShaper (rendering)
```

## Quick Start

```python
from mattershaper import MatterShaper

ms = MatterShaper()

ms.sphere(pos=(0, 0.5, -3), radius=0.5, material='ceramic')
ms.plane(y=0, material='steel')
ms.preset_studio()
ms.camera(pos=(0, 2, 2), look_at=(0, 0, -3))

ms.render('scene.png', width=400, height=300)
```

That's it. Five lines from import to rendered image.


## The MatterShaper Object

Everything goes through one class:

```python
ms = MatterShaper()           # empty scene
ms = MatterShaper(background=(0.05, 0.05, 0.1))  # custom background
```

All methods return `self`, so you can chain:

```python
ms.sphere(...).sphere(...).plane(...).light(...).camera(...).render(...)
```


## Adding Geometry

### Spheres

```python
ms.sphere(
    pos=(x, y, z),       # center position (default: origin)
    radius=1.0,          # sphere radius (default: 1.0)
    material='ceramic',  # material name or Material object
)
```

### Ellipsoids

Triaxial shapes — for asteroids, eggs, stretched objects, fragments.

```python
ms.ellipsoid(
    pos=(x, y, z),           # center position
    radii=(a, b, c),         # semi-axis lengths along X, Y, Z
    material='iron',         # material
    rotate=(rx, ry, rz),     # Euler angles in RADIANS (default: no rotation)
)
```

Rotation is applied as Rz @ Ry @ Rx (standard Euler order).

**Examples:**
```python
# Tall vase shape
ms.ellipsoid(pos=(0, 0.5, -3), radii=(0.3, 0.6, 0.3), material='ceramic')

# Flat disc on the ground
ms.ellipsoid(pos=(0, 0.01, -3), radii=(0.5, 0.01, 0.5), material='water')

# Tilted shard (rotated 45° around Z)
import math
ms.ellipsoid(
    pos=(1, 0.1, -3),
    radii=(0.15, 0.02, 0.10),
    rotate=(0, 0, math.pi/4),
    material='ceramic',
)
```

### Planes

Infinite flat surfaces — floors, walls, tables.

```python
# Horizontal floor at y=0 (shorthand)
ms.plane(y=0, material='steel')

# Explicit definition
ms.plane(point=(0, 0, 0), normal=(0, 1, 0), material='basalt')

# Angled surface
ms.plane(point=(0, 0, -5), normal=(0, 0.3, 1), material='silicate')
```

### Raw Objects

For advanced use, pass pre-built geometry directly:

```python
from mattershaper import Sphere, Vec3, Material

custom = Sphere(
    center=Vec3(0, 1, -3),
    radius=0.5,
    material=Material(name='Gold', color=Vec3(1, 0.84, 0),
                      reflectance=0.8, roughness=0.1),
)
ms.custom(custom)
```


## Materials

### Built-in Library

Pass any of these as a string:

| Name       | Color         | Reflectance | Roughness | Density   | Composition         |
|------------|---------------|-------------|-----------|-----------|---------------------|
| `ceramic`  | off-white     | 0.05        | 0.6       | 2,400     | SiO₂ + Al₂O₃       |
| `steel`    | grey metallic | 0.60        | 0.15      | 7,800     | Fe + C              |
| `glass`    | clear blue    | 0.40        | 0.02      | 2,500     | SiO₂                |
| `water`    | dark blue     | 0.30        | 0.05      | 1,000     | H₂O                 |
| `basalt`   | dark grey     | 0.04        | 0.8       | 2,900     | Plagioclase+pyroxene|
| `iron`     | dark metallic | 0.65        | 0.2       | 7,874     | Fe                  |
| `ice`      | pale blue     | 0.30        | 0.1       | 917       | H₂O (crystalline)  |
| `carbon`   | very dark     | 0.02        | 0.9       | 1,500     | C + organics        |
| `silicate` | brown         | 0.06        | 0.7       | 3,300     | MgSiO₃ / olivine   |
| `regolith` | dusty grey    | 0.03        | 0.95      | 1,500     | Fragmented silicate |

```python
ms.sphere(pos=(0, 0.5, -3), radius=0.5, material='steel')
```

### Custom Materials

```python
from mattershaper import Material, Vec3

gold = Material(
    name='Gold',
    color=Vec3(1.0, 0.84, 0.0),
    reflectance=0.8,
    roughness=0.1,
    density_kg_m3=19300,
    mean_Z=79,
    mean_A=197,
    composition='Au',
)

ms.sphere(pos=(0, 0.5, -3), radius=0.5, material=gold)
```

### Inline Materials (dict)

For quick one-offs without importing Material:

```python
ms.sphere(
    pos=(0, 0.5, -3),
    radius=0.5,
    material={'name': 'Ruby', 'color': (0.8, 0.1, 0.1), 'reflectance': 0.4, 'roughness': 0.1},
)
```

### Material Queries

```python
ms.materials                    # list all available names
ms.material_info('steel')       # dict of properties
```


## Lighting

### Point Lights

```python
ms.light(
    pos=(5, 10, 5),           # light position
    color=(1.0, 0.95, 0.9),   # warm white
    intensity=1.0,             # brightness multiplier
)
```

### Ambient + Background

```python
ms.ambient(0.08, 0.08, 0.12)     # blue-tinted ambient fill
ms.background(0.02, 0.02, 0.04)  # near-black for rays that miss everything
```

### Lighting Presets

Three-point setups you can apply in one call:

```python
ms.preset_studio()    # Key + fill + rim. Good for objects.
ms.preset_outdoor()   # Sunlight + sky. Good for geology.
ms.preset_space()     # Single harsh light, black ambient. Good for asteroids.
```


## Camera

```python
ms.camera(
    pos=(0, 2, 3),        # camera position
    look_at=(0, 0, 0),    # what it's aimed at
    up=(0, 1, 0),         # world up direction
    fov=55,               # field of view in degrees
)
```

If you don't call `ms.camera(...)`, a default is used: position (0, 2, 3), looking at origin, 55° FOV.


## Rendering

### To File

```python
# SVG output (vector, universal, no dependencies)
result = ms.render('scene.svg', width=400, height=300, pixel_size=3)

# PNG output (raster, pure-Python encoder)
result = ms.render('scene.png', width=400, height=300)
```

Both return a stats dict:
```python
{
    'filepath': '/absolute/path/to/scene.png',
    'width': 400,
    'height': 300,
    'rays': 120000,
    'objects': 5,
    'lights': 3,
    'render_time_s': 3.42,
    'format': 'png',
}
```

### Raw Pixels

For custom post-processing:

```python
pixels = ms.render_pixels(width=400, height=300)
# pixels[y][x] is a Vec3(r, g, b) with values in [0, 1]
```


## Scene Management

```python
ms.clear()            # wipe everything
ms.clear_objects()    # keep lights + camera, remove geometry
ms.clear_lights()     # keep geometry, remove lights
ms.scene              # access raw Scene object for advanced use
```


## Composing Complex Objects

MatterShaper only has three primitives: sphere, ellipsoid, plane. But you can
compose anything from them. The key insight: enough ellipsoids at different
orientations approximate any shape.

### Example: Coffee Cup

```python
import math

ms = MatterShaper()
ms.preset_studio()
ms.plane(y=0, material='steel')

# Cup body — tall ellipsoid
ms.ellipsoid(pos=(0, 0.42, -3), radii=(0.38, 0.45, 0.38), material='ceramic')

# Coffee surface — flat disc inside
ms.ellipsoid(pos=(0, 0.72, -3), radii=(0.32, 0.03, 0.32),
             material={'name': 'coffee', 'color': (0.25, 0.14, 0.07),
                       'reflectance': 0.35, 'roughness': 0.05})

# Handle — three spheres on the side
ms.sphere(pos=(0.48, 0.55, -3), radius=0.10, material='ceramic')
ms.sphere(pos=(0.52, 0.40, -3), radius=0.09, material='ceramic')
ms.sphere(pos=(0.48, 0.25, -3), radius=0.08, material='ceramic')

ms.camera(pos=(0, 2, 1), look_at=(0, 0.3, -3))
ms.render('cup.png', width=400, height=300)
```

### Example: Broken Shards

Rotated flat ellipsoids make excellent fragment debris:

```python
# A ceramic shard on the ground, tilted
ms.ellipsoid(
    pos=(1.5, 0.04, -3),
    radii=(0.14, 0.025, 0.10),      # flat and sharp
    rotate=(0.3, 0.5, 0.8),          # random-looking tilt
    material='ceramic',
)
```

### Example: Liquid Puddle

Very flat ellipsoids with high reflectance:

```python
ms.ellipsoid(
    pos=(1, 0.005, -3),
    radii=(0.6, 0.008, 0.45),
    material={'name': 'puddle', 'color': (0.22, 0.12, 0.06),
              'reflectance': 0.4, 'roughness': 0.02},
)
```


## Connection to SSBM

MatterShaper is part of the SSBM project family:

- **Materia** — spacetime geometry, σ field computation
- **QuarkSum** — atomic physics, nucleon masses, binding energies
- **local_library** — lightweight proof-of-concept (□σ = −ξR)
- **MatterShaper** — visualization, rendering from physics

Each material carries atomic composition data (Z, A). When connected to
local_library, MatterShaper can compute how materials behave at different
σ values — density shifts, structural changes, all from first principles.

The optical properties (color, reflectance) are **σ-invariant** because
they're electromagnetic. The mass properties (density, bond strength) are
**σ-dependent** because they involve QCD.

This means: a ceramic cup near a black hole looks the same color but
weighs more. MatterShaper can render both cases from the same Material
definition — just provide a σ value.


## Performance Notes

- Pure Python. No GPU, no numpy, no PIL.
- Each pixel = one primary ray + shadow rays + up to 2 reflection bounces.
- 160×120 preview: ~0.3s
- 320×240 standard: ~2s
- 400×300 with 20+ objects: ~20s
- SVG output uses run-length optimization (same-color pixel merging).
- PNG output uses a zero-dependency encoder (zlib + struct).
