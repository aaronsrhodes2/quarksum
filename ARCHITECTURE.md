# QuarkSum / SSBM — Architecture

## The Physics/Rendering Boundary

The fundamental rule of this codebase:

> **Physics never imports from renderers. Renderers may import from physics.**

```
local_library/   ──┐
quarksum/         ─┼──► sgphysics/   ◄── MatterShaper/render/ (entangler)
MatterShaper/      │                          ↑
  physics/ ────────┘                     (one-way)
```

---

## Package Map

### `sgphysics/` — Sigma-Ground Physics Library
The canonical unified physics package. Consolidates all SSBM physics into
one importable namespace. **Zero rendering imports.**

```
sgphysics/
├── __init__.py          public API: G, C, HBAR, L_PLANCK, Vec3, ...
├── constants.py         all physical constants (re-exports local_library.constants)
├── dynamics/
│   ├── vec.py           Vec3 — 3D vector math (pure math, NO renderer dependency)
│   ├── collision.py     sphere-sphere / sphere-plane impulse response
│   ├── stepper.py       leapfrog integrator with CFL-constrained dt
│   ├── parcel.py        PhysicsParcel: matter + dynamics state
│   ├── scene.py         PhysicsScene: parcels + gravity + ground
│   ├── fluid/
│   │   ├── kernel.py    cubic spline SPH kernel W(r,h)
│   │   └── eos.py       equation of state P(ρ,ρ₀,K)
│   └── gravity/
│       └── barnes_hut.py  Barnes-Hut O(N log N) gravity
├── core/                SSBM σ-field physics (re-exports local_library)
├── celestial/           N-body: NBodySystem, CelestialBody (re-exports local_library)
└── inventory/           particle inventory / mass closure (re-exports quarksum)
```

### `local_library/` — SSBM Light Proofs
Proof-of-concept implementations for □σ = −ξR. Contains:
- `constants.py` — authoritative physical constants (G, C, HBAR, L_PLANCK, ...)
- `interface/nbody.py` — Forest-Ruth FR4 N-body + 1PN GR + SRP
- `interface/` — σ-field tests, celestial mechanics, bond failure layers
- `entanglement.py` — quantum entanglement fraction η, photon emission (PHYSICS, not rendering)

Note: "rendering" in local_library means matter becoming electromagnetically
visible at the σ-transition — SSBM physics terminology, not computer graphics.

### `quarksum/` — Particle Inventory & Mass Closure
CLI tool resolving materials → molecules → atoms → quarks. Proves the books
balance. Pure Python, zero external dependencies.

### `Materia/` — Full SSBM Physics Engine
Spacetime geometry, σ-field computation, orbital mechanics, fluid dynamics,
nucleosynthesis, gravitational waves.

### `MatterShaper/` — 3D Push Renderer
Pure-Python ray-free renderer. Physics layer and render layer are strictly
separated within MatterShaper itself:

```
MatterShaper/
├── mattershaper/physics/    rigid-body sim, SPH, gravity (imports from sgphysics)
└── mattershaper/render/     Entangler push renderer — pixels, PNG, GIF
    └── entangler/
        └── vec.py           self-contained Vec3 copy (renderer standalone use)
```

`mattershaper/physics/` imports Vec3 from `..render.entangler.vec` — this is
a legacy dependency. The canonical Vec3 lives in `sgphysics/dynamics/vec.py`.
New code should import from sgphysics.

---

## Vec3 — The Migration Path

`Vec3` is pure math (3D vector arithmetic). It belongs in physics, not rendering.

| Location | Status | Use |
|---|---|---|
| `sgphysics/dynamics/vec.py` | **CANONICAL** | New code imports from here |
| `MatterShaper/render/entangler/vec.py` | Legacy (self-contained) | MatterShaper standalone |
| `MatterShaper/physics/*.py` | Legacy (imports from render) | Unchanged for now |

Future migration: `MatterShaper/physics/` files should import Vec3 from
`sgphysics.dynamics.vec` rather than `..render.entangler.vec`.

---

## Constants — Single Source of Truth

`local_library/constants.py` is the authoritative source.
`sgphysics/constants.py` re-exports everything from it.

**Never define a physical constant in two places.** If a constant is needed
in a new module, import it from `sgphysics.constants` or `local_library.constants`.

---

## N-Body Integration Hierarchy

```
Keplerian (analytic)
    ↓ add mutual perturbations
Standard N-body (Verlet/FR4)
    ↓ add 1PN GR correction
Standard + GR
    ↓ add solar radiation pressure
Standard + GR + SRP                    ← "over-physics-nbody"
    ↓ add GW damping + tidal deformation
Full kitchen-sink (test_physics_stability.py)
```

Shootout result (J2026, 26 bodies): Keplerian wins 17/26, over-physics 7/26,
standard 1/26. Inner moon phase problem documented in fixture metadata.

---

## Testing

| Suite | Location | Count | Notes |
|---|---|---|---|
| quarksum | `tests/` | ~354 | mass closure, material resolution |
| local_library | `local_library/interface/` | ~709 | σ-field, N-body, celestial |
| MatterShaper | `MatterShaper/` | ~130 | physics + render |

Run all: `pytest` (from project root runs `tests/` only — see pyproject.toml).
Full run: `pytest tests/ local_library/ && cd MatterShaper && pytest`

Permanently red (expected): `test_jpl_ephemeris` (network-gated),
`test_position_precision` (simulation-gated).
