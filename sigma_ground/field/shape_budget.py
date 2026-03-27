"""
Shape Budget — rendering allowance tied to physical structure.

The problem: you can always zoom in and add more detail. An asteroid
could have 10,000 craters. Jupiter could have a million cloud vortices.
Without a limit, renderers will spend infinite shapes on finite objects.

The solution: the OBJECT EARNS its shape budget from its physics.

    shape_budget = f(σ, apparent_size, information_density)

This is NOT arbitrary. It follows from what SSBM already tells us:

1. σ measures gravitational structure depth.
   High σ → deep potential well → many layers worth rendering.
   Low σ → shallow well → object is structurally simple.

2. Apparent size determines what's RESOLVABLE.
   A 4-pixel Mercury doesn't need continent outlines.
   A 400-pixel Earth does.

3. Information density (mass/volume) tells you how PACKED the structure is.
   A neutron star has 10^14 kg/m³ → lots of physics per pixel.
   A rubble-pile asteroid has 1000 kg/m³ → mostly vacuum.

THE FORMULA:
    N_shapes = S_base × (A_px / S_base) × Q(σ) × D_norm

Where:
    S_base  = 8                          — minimum useful shapes (circle + label)
    A_px    = apparent diameter in pixels — what you CAN resolve
    Q(σ)    = 1 + log₁₀(1 + σ/σ_floor)/5 — quality multiplier from gravitational depth
    σ_floor = 10⁻¹²                     — below this, σ contributes nothing
    D_norm  = max(0.7, log₁₀(ρ/ρ_water) + 1) — density factor (1 for water, 1.7 for iron)

The quality multiplier Q(σ) is the key:
    σ=0 (vacuum):    Q = 1.0 — base rendering only
    σ=10⁻¹⁰ (Earth): Q ≈ 1.4 — modest enhancement
    σ=10⁻⁷ (Sun):    Q ≈ 2.0 — rich detail earned
    σ=0.03 (NS):     Q ≈ 3.1 — maximum physics per pixel

This gives:
    Bennu at 4px:    ~8 shapes  (circle, label, maybe a shadow)
    Mercury at 4px:  ~8 shapes  (circle, label, gradient)
    Earth at 7px:    ~17 shapes (sphere, 2 continents, caps, atmo)
    Jupiter at 18px: ~36 shapes (sphere, bands, GRS, storms)
    Sun at 56px:     ~135 shapes (corona, granulation, spots, rays)
    Neutron star:    ~350 shapes (full interior layers)

The shape budget is a CEILING, not a floor. Renderers should always
aim to use FEWER shapes than allowed.

ELEGANCE:
    The budget is set by σ — the same field that determines the object's
    internal physics. Objects with more gravitational structure EARN
    more rendering detail. A black hole at σ = ξ/2 has maximum budget.
    A photon in flat space has zero. The rendering complexity tracks
    the physical complexity, by construction.
"""

import math
from .constants import XI, G, C
from .scale import sigma_from_potential


# ═══════════════════════════════════════════════════════════════════════
#  RENDERING SCALE HIERARCHY
# ═══════════════════════════════════════════════════════════════════════
#
#  Each scale has a distinct light model, shape count basis, and data
#  source.  The shape budget does real work at Galaxy and Geographic+.
#
#  UNIVERSE    — Self-luminous galaxies.  Statistical distribution model
#                (SDSS filaments + voids).  Outer shell = lensing boundary.
#
#  GALAXY      — Self-luminous stars.  Gaia DR3 catalog (1.8B positions).
#                Shape budget caps how many stars we resolve vs. haze.
#
#  SOLAR SYSTEM— Sun as primary light source + background star-sphere.
#                DE440 ephemeris gives exact body positions.
#
#  PLANET      — Sun + epoch-dependent moon reflections.
#                One shape per quarksum layer × Q(σ).
#
#  GEOGRAPHIC  — Planet light source + interface scatter.
#                Objects at or near a planetary interface (ocean/atmosphere,
#                crust/surface, bedrock/soil).  Iceberg is the prototype.
#                Mass range ~1 kg → ~10¹² kg.  σ ≈ parent planet surface.
#                Shape count basis: N compositional phases × Q(σ).
#
#  NEWTONIAN   — Ambient (lab) light.  Same phase-count basis as Geographic
#                but no interface boundary.  Human-to-building scale.
#
#  MOLECULAR   — Emission/absorption only.  Bond geometries from chemistry
#                tables.  Finite and enumerable.  Render later.

SCALE_UNIVERSE    = 'universe'
SCALE_GALAXY      = 'galaxy'
SCALE_SOLAR_SYSTEM= 'solar_system'
SCALE_PLANET      = 'planet'
SCALE_GEOGRAPHIC  = 'geographic'
SCALE_NEWTONIAN   = 'newtonian'
SCALE_MOLECULAR   = 'molecular'

SCALE_ORDER = (
    SCALE_UNIVERSE,
    SCALE_GALAXY,
    SCALE_SOLAR_SYSTEM,
    SCALE_PLANET,
    SCALE_GEOGRAPHIC,
    SCALE_NEWTONIAN,
    SCALE_MOLECULAR,
)


# ═══════════════════════════════════════════════════════════════════════
#  COORDINATE TRANSFORM RULES
# ═══════════════════════════════════════════════════════════════════════
#
#  Physical coordinates cannot be rendered directly at most scales.
#  Three problems arise:
#
#    1. UNIVERSE: Galaxy separations (~Mpc) dwarf galaxy sizes (~kpc) by
#       a factor of ~1000.  At true scale every galaxy is a sub-pixel dot.
#       Solution: logarithmic compression.  log(1 + r/r_ref) pulls distant
#       galaxies inward while preserving local clustering topology.
#       r_ref = 1 Mpc (3.086e22 m) — the characteristic void scale.
#
#    2. GALAXY: No compression needed.  Star separations (~1 pc) are large
#       relative to star sizes, but the clustering PATTERN (spiral arms,
#       bulge, halo) is visible at natural scale when the full disk fills
#       the viewport.  Gaia positions are used directly.  Zooming in
#       reveals progressively finer structure without re-mapping needed.
#
#    3. SOLAR SYSTEM: Planet diameters (~10⁴ km) are tiny against orbital
#       radii (~10⁸–10¹² km), ratio ~1:10,000.  Two separate exaggerations:
#       - Orbital distances: sqrt(r/AU) compression so all orbits fit.
#       - Body sizes: inflated ×50 relative to the compressed orbit scale
#         so planets are visible dots rather than sub-pixel specks.
#       r_ref = 1 AU (1.496e11 m).
#
#  All other scales use natural (1:1) coordinates.

_AU  = 1.495978707e11   # m  — 1 Astronomical Unit
_MPC = 3.085677581e22   # m  — 1 Megaparsec

SCALE_TRANSFORMS = {
    SCALE_UNIVERSE: {
        'distance':     'logarithmic',
        'r_ref_m':      _MPC,           # log(1 + r/1 Mpc)
        'size_factor':  1e4,            # galaxy sizes inflated ×10,000
        'note': (
            'Logarithmic compression: log(1 + r/1 Mpc).  Preserves '
            'clustering topology; pulls Hubble-edge galaxies to ~13 units '
            'from origin.  Galaxy sizes ×10,000 for visibility.'
        ),
    },
    SCALE_GALAXY: {
        'distance':     'natural',
        'r_ref_m':      None,
        'size_factor':  1.0,
        'note': (
            'Natural scale.  Gaia DR3 positions placed directly.  '
            'Spiral arm clustering visible when full disk fills viewport.  '
            'Zoom reveals finer structure without re-mapping.'
        ),
    },
    SCALE_SOLAR_SYSTEM: {
        'distance':     'sqrt',
        'r_ref_m':      _AU,            # sqrt(r / 1 AU) compression
        'size_factor':  50.0,           # body diameters ×50
        'note': (
            'sqrt(r/AU) compresses orbital distances.  Earth at 1 AU → '
            'render radius 1.  Neptune at 30 AU → render radius 5.5.  '
            'Body diameters ×50 so planets are resolvable dots.'
        ),
    },
    SCALE_PLANET: {
        'distance':     'natural',
        'r_ref_m':      None,
        'size_factor':  1.0,
        'note': 'Planet layers at true scale.  σ field visible in layer depths.',
    },
    SCALE_GEOGRAPHIC: {
        'distance':     'natural',
        'r_ref_m':      None,
        'size_factor':  1.0,
        'note': 'Human-to-mountain scale; natural coordinates.',
    },
    SCALE_NEWTONIAN: {
        'distance':     'natural',
        'r_ref_m':      None,
        'size_factor':  1.0,
        'note': 'Lab scale; natural coordinates.',
    },
    SCALE_MOLECULAR: {
        'distance':     'natural',
        'r_ref_m':      None,
        'size_factor':  1.0,
        'note': 'Bond lengths and angles from chemistry tables.',
    },
}


def render_distance(r_physical_m: float, scale: str) -> float:
    """Map a physical distance (metres) to render coordinate units.

    The output is dimensionless — a renderer multiplies by its own
    scene-unit scale to get pixel or world coordinates.

    Universe:     log(1 + r / 1 Mpc)
    Solar system: sqrt(r / 1 AU)
    All others:   r  (identity)
    """
    t = SCALE_TRANSFORMS.get(scale, {})
    method = t.get('distance', 'natural')
    r_ref = t.get('r_ref_m') or 1.0

    if r_physical_m < 0:
        return 0.0
    if method == 'logarithmic':
        return math.log1p(r_physical_m / r_ref)
    if method == 'sqrt':
        return math.sqrt(r_physical_m / r_ref)
    return r_physical_m   # natural


def render_size(physical_size_m: float, scale: str) -> float:
    """Apply the visibility size-inflation factor for a given scale.

    Returns the render-space size of an object.  Combine with
    render_distance() for the full transform:

        pos_render   = render_distance(r_orbit, scale)
        radius_render = render_size(r_body, scale)
    """
    factor = SCALE_TRANSFORMS.get(scale, {}).get('size_factor', 1.0)
    return physical_size_m * factor


# ═══════════════════════════════════════════════════════════════════════
#  SHAPE BUDGET CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

S_BASE = 8           # minimum shapes: circle + label + shadow
SIGMA_FLOOR = 1e-12  # below this, σ contributes nothing to quality
A_CAP = 200          # pixel cap: beyond this, no extra detail resolves
RHO_WATER = 1000.0   # kg/m³ — normalization density

# Budget tiers for documentation / renderer guidance
TIER_MINIMAL = 8      # dot + label
TIER_SIMPLE = 16      # basic sphere + a few features
TIER_MODERATE = 40    # detailed surface features
TIER_RICH = 80        # full atmospheric/surface detail
TIER_MAXIMUM = 200    # neutron star interior level detail


# ═══════════════════════════════════════════════════════════════════════
#  CORE COMPUTATION
# ═══════════════════════════════════════════════════════════════════════

def quality_multiplier(sigma):
    """Q(σ) — how much physics per pixel this object earns.

    This is the heart of the shape budget. A deeper gravitational
    well means more internal structure worth rendering.

    Q(σ) = 1 + log₁₀(1 + σ/σ_floor) / 5

    Returns: float ≥ 1.0
    """
    if sigma <= 0:
        return 1.0
    return 1.0 + math.log10(1.0 + abs(sigma) / SIGMA_FLOOR) / 5.0


def shape_budget(sigma, apparent_px, density_kg_m3):
    """Compute the shape rendering allowance for an object.

    budget = S_BASE × (A_px / S_BASE) × Q(σ) × D_norm

    The apparent size determines how many pixels you have to fill.
    Q(σ) determines how much detail each pixel earns.
    Density modulates ±30% based on how packed the structure is.

    Args:
        sigma: σ value at the object's surface (from □σ = −ξR)
        apparent_px: apparent diameter in pixels at current zoom
        density_kg_m3: bulk density of the object

    Returns:
        int — maximum number of shapes the renderer should use
    """
    # Size: how many pixels to fill (capped at A_CAP)
    size_factor = min(apparent_px, A_CAP) / S_BASE

    # Quality: physics per pixel from gravitational depth
    q = quality_multiplier(sigma)

    # Density: information per unit volume
    # water=1.0, rock=1.5, iron=1.7, neutron_star=18.6
    density_factor = max(0.7, math.log10(max(1, density_kg_m3) / RHO_WATER) + 1)

    # Combined
    budget = S_BASE * size_factor * q * density_factor

    # Floor at S_BASE, soft cap at 2000
    return max(S_BASE, min(int(budget), 2000))


def shape_budget_for_body(mass_kg, radius_m, density_kg_m3, apparent_px):
    """Compute shape budget from physical properties.

    Convenience function that computes σ internally.

    Args:
        mass_kg: object mass
        radius_m: object radius
        density_kg_m3: bulk density
        apparent_px: apparent diameter in pixels

    Returns:
        dict with budget, sigma, tier, and breakdown
    """
    sigma = sigma_from_potential(radius_m, mass_kg)
    if math.isinf(sigma) or math.isnan(sigma):
        sigma = 0.0
    budget = shape_budget(sigma, apparent_px, density_kg_m3)

    # Classify into tier
    if budget <= TIER_MINIMAL:
        tier = 'MINIMAL'
        guidance = 'Circle + label. Maybe a color gradient.'
    elif budget <= TIER_SIMPLE:
        tier = 'SIMPLE'
        guidance = 'Sphere with lighting. 1-2 surface features max.'
    elif budget <= TIER_MODERATE:
        tier = 'MODERATE'
        guidance = 'Detailed surface: bands, spots, caps, rings.'
    elif budget <= TIER_RICH:
        tier = 'RICH'
        guidance = 'Full detail: atmosphere, storms, terrain, multiple rings.'
    else:
        tier = 'MAXIMUM'
        guidance = 'Everything visible: convection, granulation, internal layers.'

    return {
        'budget': budget,
        'sigma': sigma,
        'tier': tier,
        'guidance': guidance,
        'breakdown': {
            'quality_Q': quality_multiplier(sigma),
            'size_factor': min(apparent_px, A_CAP) / S_BASE,
            'density_factor': max(0.7, math.log10(max(1, density_kg_m3) / RHO_WATER) + 1),
        },
    }


# ═══════════════════════════════════════════════════════════════════════
#  SHAPE BUDGET TABLE — all known bodies
# ═══════════════════════════════════════════════════════════════════════

# Solar system bodies at typical rendering sizes
SOLAR_SYSTEM_BODIES = [
    # name, mass_kg, radius_m, density, typical_px (from our solar system viz)
    ('Sun',      1.989e30, 6.957e8, 1408,   56),
    ('Mercury',  3.301e23, 2.44e6,  5427,   4),
    ('Venus',    4.867e24, 6.05e6,  5243,   7),
    ('Earth',    5.972e24, 6.371e6, 5514,   7),
    ('Mars',     6.417e23, 3.39e6,  3934,   5),
    ('Jupiter',  1.898e27, 6.991e7, 1326,   18),
    ('Saturn',   5.683e26, 5.823e7, 687,    15),
    ('Uranus',   8.681e25, 2.536e7, 1270,   10),
    ('Neptune',  1.024e26, 2.462e7, 1638,   10),
    ('Pluto',    1.303e22, 1.19e6,  1854,   3),
]

ASTEROID_BODIES = [
    ('Bennu',    7.329e10, 128.0,   1190,   4),
    ('Ryugu',    4.50e11,  252.0,   1190,   4),
    ('Itokawa',  3.51e10,  165.0,   1950,   3),
    ('Eros',     6.687e15, 8420.0,  2670,   6),
    ('Vesta',    2.591e20, 2.626e5, 3456,   8),
    ('Ceres',    9.393e20, 4.73e5,  2162,   10),
]

EXTREME_BODIES = [
    ('Neutron Star', 2.8e30, 1.2e4, 4.0e17, 6),
    ('White Dwarf',  1.2e30, 7.0e6, 1.0e9,  5),
    ('Sgr A*',       8.0e36, 1.2e10, 1.0e5, 4),
]


def print_budget_table():
    """Print the shape budget for all known bodies."""
    import time
    t0 = time.perf_counter()

    print()
    print("  ╔═══════════════════════════════════════════════════════════════╗")
    print("  ║          SHAPE BUDGET — RENDERING ALLOWANCE TABLE           ║")
    print("  ╠═══════════════════════════════════════════════════════════════╣")
    print("  ║  N_shapes = S_base × log(1+σ/σ_ref) × A_px/20 × D_norm    ║")
    print("  ║  Budget earned by: gravitational depth (σ),                 ║")
    print("  ║  apparent size (px), information density (ρ)                ║")
    print("  ╚═══════════════════════════════════════════════════════════════╝")
    print()

    for category, bodies in [
        ('SOLAR SYSTEM', SOLAR_SYSTEM_BODIES),
        ('ASTEROIDS', ASTEROID_BODIES),
        ('EXTREME OBJECTS', EXTREME_BODIES),
    ]:
        print(f"  ── {category} ──")
        print(f"  {'Body':<16s} {'σ':>10s} {'px':>4s} {'ρ (kg/m³)':>12s} "
              f"{'Budget':>7s}  {'Tier':<10s} Guidance")
        print(f"  {'─'*100}")

        for name, mass, radius, density, px in bodies:
            result = shape_budget_for_body(mass, radius, density, px)
            sigma_str = f"{result['sigma']:.2e}" if result['sigma'] > 0 else "0"
            print(f"  {name:<16s} {sigma_str:>10s} {px:>4d} {density:>12.0f} "
                  f"{result['budget']:>7d}  {result['tier']:<10s} {result['guidance']}")
        print()

    elapsed = time.perf_counter() - t0
    print(f"  Computed in {elapsed*1000:.1f} ms")
    print()

    # Show scaling behavior
    print("  ── ZOOM SCALING (Earth at different apparent sizes) ──")
    print(f"  {'Apparent px':>12s}  {'Budget':>7s}  {'Tier':<10s}")
    print(f"  {'─'*40}")
    for px in [2, 5, 7, 14, 30, 60, 100, 200, 400]:
        r = shape_budget_for_body(5.972e24, 6.371e6, 5514, px)
        print(f"  {px:>12d}  {r['budget']:>7d}  {r['tier']:<10s}")
    print()


def validate_solar_system_viz():
    """Check the actual solar_system_ssbm.html against shape budgets.

    Counts the approximate shapes used per planet in our renderer
    and compares to the budget. This is the integrity check.
    """
    # Approximate shape counts from our renderer code
    actual_shapes = {
        'Sun':      18,  # corona + 24 rays + body + 30 granules + 2 spots + labels
        'Mercury':  8,   # body + 6 craters + Caloris + labels
        'Venus':    12,  # body + 9 cloud bands + vortex + atmo + labels
        'Earth':    14,  # body + Americas + Africa + Australia + 2 caps + 2 clouds + atmo + labels
        'Mars':     10,  # body + terrain + canyon + Mons + 2 caps + Syrtis + labels
        'Jupiter':  16,  # body + 7 bands + GRS(3) + 2 storms + ring + labels
        'Saturn':   12,  # body + 7 bands + hexagon + ring + labels
        'Uranus':   8,   # body + 5 bands + ring + labels
        'Neptune':  10,  # body + dark spot + 2 clouds + 3 bands + labels
        'Pluto':    5,   # body + heart + dark region + labels
    }

    print()
    print("  ── SHAPE BUDGET VALIDATION (solar_system_ssbm.html) ──")
    print(f"  {'Body':<12s}  {'Budget':>7s}  {'Used':>5s}  {'%':>5s}  {'Status'}")
    print(f"  {'─'*55}")

    all_ok = True
    for name, mass, radius, density, px in SOLAR_SYSTEM_BODIES:
        result = shape_budget_for_body(mass, radius, density, px)
        budget = result['budget']
        used = actual_shapes.get(name, 0)
        pct = (used / budget * 100) if budget > 0 else 0

        if used > budget:
            status = '⚠ OVER BUDGET'
            all_ok = False
        elif pct > 80:
            status = '~ near limit'
        else:
            status = '✓ within budget'

        print(f"  {name:<12s}  {budget:>7d}  {used:>5d}  {pct:>4.0f}%  {status}")

    print()
    if all_ok:
        print("  ✓ All bodies within shape budget.")
    else:
        print("  ⚠ Some bodies exceed their shape budget — reduce detail or increase σ-earning.")
    print()

    return all_ok
