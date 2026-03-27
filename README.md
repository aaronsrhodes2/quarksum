# sigma-ground

**Particle physics library: σ-field computation, particle inventory, and N-body dynamics.**

Pure Python. Zero external dependencies.

```bash
pip install sigma-ground
```

---

## What it does

sigma-ground resolves physical structures — materials, molecules, atoms, particles, quarks — and counts every constituent from the top down. It also provides the underlying scalar field physics and a dynamics engine for N-body simulations.

Three sub-libraries, one install:

| Sub-library | What it does |
|---|---|
| `sigma_ground.inventory` | Particle inventory and mass closure — resolves any material to its quark count |
| `sigma_ground.field` | σ-field constants, spacetime geometry, entanglement bounds |
| `sigma_ground.dynamics` | N-body dynamics, SPH fluid, Barnes-Hut gravity, leapfrog integrator |

---

## Quick start

### Particle inventory

```python
from sigma_ground.inventory import stoq, build_quick_structure, load_structure

# Count particles in 1 kg of iron
s = build_quick_structure("Iron", 1.0)
result = stoq(s)
print(result["quarks"])       # total quark count
print(result["protons"])      # proton count
print(result["mass_kg"])      # mass closure check

# Use a built-in structure
s = load_structure("gold_ring")
result = stoq(s)
```

### Full quark chain

```python
from sigma_ground.inventory import quark_chain, load_structure

s = load_structure("water_bottle")
chain = quark_chain(s)
# chain["up_quarks"], chain["down_quarks"], chain["gluons"]
```

### σ-field constants

```python
from sigma_ground.field.constants import (
    XI,              # σ-field coupling constant (dimensionless)
    HBAR,            # Reduced Planck constant (J·s)
    C,               # Speed of light (m/s)
    G,               # Gravitational constant (m³/kg/s²)
    LAMBDA_QCD_MEV,  # QCD scale (MeV)
)
```

### N-body dynamics

```python
from sigma_ground.dynamics.scene import PhysicsScene
from sigma_ground.dynamics.parcel import PhysicsParcel
from sigma_ground.dynamics.vec import Vec3

scene = PhysicsScene(gravity=Vec3(0, -9.81, 0))
body = PhysicsParcel(mass=1.0, pos=Vec3(0, 10, 0), vel=Vec3(1, 0, 0))
scene.add(body)
for _ in range(1000):
    scene.step(dt=0.001)
```

---

## CLI

```bash
# Summarize a built-in structure
python -m sigma_ground.inventory gold_ring

# List all built-in structures
python -m sigma_ground.inventory --list

# Quick material lookup
python -m sigma_ground.inventory --material Iron --mass 1.0

# Full quark chain
python -m sigma_ground.inventory gold_ring --quark-chain
```

---

## API reference

### `sigma_ground.inventory`

| Name | Description |
|---|---|
| `stoq(structure)` | Full particle checksum: protons, neutrons, electrons, quarks, gluons |
| `quark_chain(structure)` | Quark-level breakdown with mass closure |
| `inventory(structure)` | Particle inventory dict |
| `resolve(material, mass_kg)` | Resolve a material name to atomic composition |
| `build_quick_structure(material, mass_kg)` | Build a single-material structure |
| `build_structure_from_spec(spec)` | Build from a spec dict |
| `load_structure(name)` | Load a built-in structure by name |
| `list_structures()` | List all built-in structure names |
| `physics(structure)` | Compute physics properties (σ-value, binding energy) |
| `tangle(structure)` | Compute entanglement properties |
| `default_load()` | Load the default built-in structure |
| `load_by_id(id)` | Load a default structure by ID |

Built-in structures: `gold_ring`, `water_bottle`, `car_battery`, `seawater_liter`, `earths_layers`, `solar_system_xsection`, `tungsten_cube`, and more.

### `sigma_ground.field`

Key modules:

| Module | Description |
|---|---|
| `field.constants` | All physical constants (HBAR, C, G, XI, GAMMA, ETA, …) |
| `field.bounds` | Spacetime geometry, boundary conditions |
| `field.entanglement` | Entanglement field (η), tangle scanning |
| `field.universe` | Universe-scale computations |
| `field.nucleon` | Nucleon mass decomposition |
| `field.binding` | Nuclear binding energies |
| `field.scale` | Scale transition computations |
| `field.sandbox` | Proof-of-concept experiments |

### `sigma_ground.dynamics`

| Module | Description |
|---|---|
| `dynamics.vec` | `Vec3`: pure 3D vector math |
| `dynamics.scene` | `PhysicsScene`: parcels + gravity + ground |
| `dynamics.parcel` | `PhysicsParcel`: matter with dynamics state |
| `dynamics.stepper` | Leapfrog integrator with CFL-constrained dt |
| `dynamics.collision` | Sphere-sphere / sphere-plane impulse response |
| `dynamics.gravity.barnes_hut` | Barnes-Hut O(N log N) gravity |
| `dynamics.fluid.kernel` | Cubic spline smoothing kernel W(r,h) |
| `dynamics.fluid.eos` | Equation of state P(ρ, ρ₀, K) |

### `sigma_ground.constants`

Top-level constants re-exported for convenience:

```python
from sigma_ground import G, C, HBAR, L_PLANCK, XI, SIGMA_CONV, ETA, Vec3
```

---

## Structure

```
sigma_ground/
  __init__.py          # Top-level re-exports (constants + Vec3)
  constants.py         # Authoritative physical constants
  inventory/           # Particle inventory and mass closure
  field/               # σ-field physics and geometry
  dynamics/            # N-body, SPH, gravity
```

---

## What's not here yet

- **Organic science** — biochemistry, amino acids, organic molecules. Planned as a separate library (`sigma-ground-organic`).
- **Rendering** — 3D visualization lives in [matter-shaper](https://github.com/aaronsrhodes2/matter-shaper) (separate project).

---

## Testing

```bash
pip install sigma-ground[test]
pytest
```

1198 tests passing.

---

## License

MIT. See [LICENSE](LICENSE).

## Author

Aaron Rhodes
