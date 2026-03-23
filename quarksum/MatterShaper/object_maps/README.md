# MatterShaper Object Maps

## What This Is

Object maps are compact mathematical descriptions of 3D objects built from
geometric primitives (spheres, ellipsoids, cones, planes). Each object is
fully defined by two small JSON files — typically a few hundred bytes total.

The renderer (MatterShaper) reconstructs every pixel from these maps using
**pure analytic ray tracing**: ray-quadratic intersections, Blinn-Phong
shading, shadow casting. No neural networks. No image generation models.
No textures. Every pixel is a solved equation.

## What AI Did and Didn't Do

**AI role: cartography, not creation.**

An AI assistant (Claude) was used to create these maps — translating
real-world object dimensions and proportions into primitive parameters.
This is analogous to someone measuring a coffee mug with calipers and
writing down the numbers. The AI looked at reference dimensions
(e.g. "standard 11oz mug: 9.6cm tall, 8.3cm top diameter") and mapped
those measurements onto cones, ellipsoids, and spheres.

**The AI did NOT:**
- Generate any images (no diffusion, no GANs, no DALL-E/Midjourney)
- Train on or copy any existing 3D models
- Use any neural rendering or NeRF-like techniques
- Produce any pixels — that's pure math in the ray tracer

**The AI DID:**
- Read reference dimensions from public sources
- Choose which primitives to use (cone vs ellipsoid, etc.)
- Position and size each primitive to match the reference
- Select material properties (color, reflectance, roughness)

This is the same work a human would do when modeling in a CAD tool —
just with an AI assistant doing the measurement-to-parameter translation.

## Provenance

Each map file includes:
- `reference`: what real-world object was measured/studied
- `scale_note`: the coordinate system used
- `provenance`: how the map was created

## File Format

### Shape Map (`{name}.shape.json`)

Geometry only — primitives, positions, sizes, rotations.

```json
{
  "name": "Object Name",
  "reference": "What real object this maps",
  "scale_note": "1 unit = 10cm",
  "provenance": "AI-mapped from published dimensions",
  "layers": [
    {
      "id": "unique_id",
      "label": "Human-readable description",
      "type": "cone|ellipsoid|sphere|plane",
      "...type-specific fields..."
      "material": "material_id from color map"
    }
  ]
}
```

### Color Map (`{name}.color.json`)

Materials only — colors, surface physics, composition.

```json
{
  "name": "Object Name Colors",
  "materials": {
    "material_id": {
      "label": "Description",
      "color": [r, g, b],
      "reflectance": 0.0-1.0,
      "roughness": 0.0-1.0,
      "density_kg_m3": 1000,
      "composition": "What it's made of"
    }
  }
}
```

## Storage Efficiency

A complete coffee mug: **12 primitives, ~2 KB of JSON.**
That's the entire object — infinitely re-renderable at any resolution,
any angle, any lighting. No mesh files, no texture images, no UV maps.

## Workflow

1. Find reference object with known dimensions
2. AI maps dimensions → primitive parameters → shape map
3. AI selects material colors/properties → color map
4. Render from maps (deterministic ray trace)
5. Human reviews, requests changes
6. Iterate until approved
7. Save final maps — the object is now permanently stored
