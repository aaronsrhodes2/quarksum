"""
SSBM Shape Limits — Safety bounds on every computed quantity.

□σ = −ξR defines the physics. These bounds define the EDGES —
where the model is valid, where it breaks, and what happens at the walls.

PHILOSOPHY:
    Every physical model has a domain of validity. Newtonian gravity
    breaks at v ~ c. The Standard Model breaks at E > M_Planck.
    SSBM breaks at σ → σ_conv (matter conversion threshold).

    Rather than silently return nonsense outside the domain, we:
    1. Define the bounds explicitly
    2. Clamp outputs to physical ranges
    3. Raise warnings when approaching edges
    4. Hard-stop when past the wall

STRUCTURE LIMITS:
    σ ∈ [0, σ_conv)       — gravitational scale field
    η ∈ [0, 1]            — entanglement fraction
    m_nucleon ∈ [m_bare, ∞) — can't go below bare quark mass
    BE ≥ 0                — bound state or unbound, never negative
    ξ ∈ (0, 1)            — baryon fraction is a ratio
    nesting level ∈ [0, 76] — Hubble to Planck

SAFETY CATEGORIES:
    SAFE       — well within model domain
    EDGE       — approaching a boundary, results getting less reliable
    WALL       — at the boundary, model makes a definite prediction
    BEYOND     — past the wall, model is silent (returns None)
"""

import math
from .constants import (
    XI, ETA, SIGMA_CONV, G, C, HBAR,
    PROTON_BARE_MEV, PROTON_TOTAL_MEV, PROTON_QCD_MEV,
    NEUTRON_BARE_MEV, NEUTRON_TOTAL_MEV, NEUTRON_QCD_MEV,
    M_PLANCK_KG, M_HUBBLE_KG,
)


# ═══════════════════════════════════════════════════════════════════════
#  DOMAIN BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════

# σ field boundaries
SIGMA_MIN = 0.0                  # vacuum (flat spacetime)
SIGMA_EDGE = SIGMA_CONV * 0.8   # 80% of conversion — entering danger zone
SIGMA_WALL = SIGMA_CONV          # -ln(ξ) ≈ 1.849 — matter conversion
SIGMA_MAX = SIGMA_CONV           # model is undefined past here

# η boundaries
ETA_MIN = 0.0   # fully classical (no cross-hadron entanglement)
ETA_MAX = 1.0   # every particle entangled

# Mass boundaries (MeV)
PROTON_MASS_MIN = PROTON_BARE_MEV    # 8.99 MeV — quarks with zero QCD
PROTON_MASS_VACUUM = PROTON_TOTAL_MEV  # 938.272 MeV — standard
NEUTRON_MASS_MIN = NEUTRON_BARE_MEV  # 11.50 MeV
NEUTRON_MASS_VACUUM = NEUTRON_TOTAL_MEV

# Nesting boundaries
NESTING_MIN = 0    # Hubble mass
NESTING_MAX = 76   # Planck mass

# Binding energy: can't be negative for a bound state
BE_MIN = 0.0


# ═══════════════════════════════════════════════════════════════════════
#  SAFETY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════

class Safety:
    """Safety status of a computed value."""
    SAFE = 'SAFE'         # well within domain
    EDGE = 'EDGE'         # approaching boundary
    WALL = 'WALL'         # at the boundary exactly
    BEYOND = 'BEYOND'     # outside domain — result invalid

    @staticmethod
    def symbol(status):
        return {
            'SAFE': '●',
            'EDGE': '◐',
            'WALL': '▪',
            'BEYOND': '✗',
        }.get(status, '?')


# ═══════════════════════════════════════════════════════════════════════
#  σ FIELD BOUNDS
# ═══════════════════════════════════════════════════════════════════════

def check_sigma(sigma):
    """Classify σ value and return safety status.

    Returns:
        dict with 'value', 'status', 'clamped', 'note'
    """
    if sigma < SIGMA_MIN:
        return {
            'value': sigma,
            'clamped': SIGMA_MIN,
            'status': Safety.BEYOND,
            'note': 'σ < 0 is unphysical (negative gravitational potential). Clamped to 0.',
        }

    if sigma > SIGMA_WALL:
        return {
            'value': sigma,
            'clamped': None,  # can't clamp — model breaks
            'status': Safety.BEYOND,
            'note': (f'σ = {sigma:.4f} > σ_conv = {SIGMA_WALL:.4f}. '
                     f'Matter has converted. QCD bonds are broken. '
                     f'Nucleon mass formula is undefined past here.'),
        }

    if sigma == SIGMA_WALL:
        return {
            'value': sigma,
            'clamped': sigma,
            'status': Safety.WALL,
            'note': (f'σ = σ_conv exactly. This is the matter conversion threshold. '
                     f'QCD binding energy equals the gravitational potential energy. '
                     f'Nuclear bonds break.'),
        }

    if sigma > SIGMA_EDGE:
        fraction = sigma / SIGMA_WALL
        return {
            'value': sigma,
            'clamped': sigma,
            'status': Safety.EDGE,
            'note': (f'σ is at {fraction*100:.1f}% of σ_conv. '
                     f'Approaching matter conversion. '
                     f'Results are becoming less reliable — QCD perturbation theory '
                     f'breaks down as confinement weakens.'),
        }

    return {
        'value': sigma,
        'clamped': sigma,
        'status': Safety.SAFE,
        'note': None,
    }


def clamp_sigma(sigma):
    """Clamp σ to valid domain [0, σ_conv).

    Returns (clamped_value, was_clamped, safety_status).
    """
    check = check_sigma(sigma)
    if check['status'] == Safety.BEYOND:
        if sigma < 0:
            return (SIGMA_MIN, True, check)
        else:
            return (None, True, check)  # can't clamp past conversion
    return (sigma, False, check)


# ═══════════════════════════════════════════════════════════════════════
#  η BOUNDS
# ═══════════════════════════════════════════════════════════════════════

def check_eta(eta):
    """Classify η value and return safety status."""
    if eta is None:
        return {
            'value': None,
            'clamped': None,
            'status': Safety.SAFE,
            'note': 'η is declared unknown. Functions must propagate symbolically.',
        }

    if eta < ETA_MIN:
        return {
            'value': eta,
            'clamped': ETA_MIN,
            'status': Safety.BEYOND,
            'note': f'η = {eta} < 0. Entanglement fraction cannot be negative.',
        }

    if eta > ETA_MAX:
        return {
            'value': eta,
            'clamped': ETA_MAX,
            'status': Safety.BEYOND,
            'note': f'η = {eta} > 1. Entanglement fraction cannot exceed 1.',
        }

    return {
        'value': eta,
        'clamped': eta,
        'status': Safety.SAFE,
        'note': None,
    }


def clamp_eta(eta):
    """Clamp η to [0, 1]. Returns (clamped, was_clamped, check)."""
    if eta is None:
        return (None, False, check_eta(None))
    clamped = max(ETA_MIN, min(ETA_MAX, eta))
    was_clamped = (clamped != eta)
    return (clamped, was_clamped, check_eta(clamped))


# ═══════════════════════════════════════════════════════════════════════
#  NUCLEON MASS BOUNDS
# ═══════════════════════════════════════════════════════════════════════

def check_nucleon_mass(mass_mev, particle='proton'):
    """Verify nucleon mass is within physical bounds."""
    bare = PROTON_BARE_MEV if particle == 'proton' else NEUTRON_BARE_MEV
    vacuum = PROTON_MASS_VACUUM if particle == 'proton' else NEUTRON_MASS_VACUUM

    if mass_mev < bare:
        return {
            'value': mass_mev,
            'status': Safety.BEYOND,
            'note': (f'{particle} mass {mass_mev:.3f} MeV < bare quark mass {bare:.2f} MeV. '
                     f'This is unphysical — the QCD contribution cannot be negative.'),
        }

    if mass_mev < vacuum * 0.5:
        return {
            'value': mass_mev,
            'status': Safety.EDGE,
            'note': (f'{particle} mass {mass_mev:.1f} MeV is less than half vacuum value. '
                     f'This implies extreme σ — approaching confinement loss.'),
        }

    # Mass enhancement check — how far above vacuum?
    ratio = mass_mev / vacuum
    if ratio > 10:
        return {
            'value': mass_mev,
            'status': Safety.EDGE,
            'note': (f'{particle} mass enhanced {ratio:.1f}× above vacuum. '
                     f'Very deep gravitational well. Check σ proximity to σ_conv.'),
        }

    return {
        'value': mass_mev,
        'status': Safety.SAFE,
        'note': None,
    }


# ═══════════════════════════════════════════════════════════════════════
#  NESTING LEVEL BOUNDS
# ═══════════════════════════════════════════════════════════════════════

def check_nesting_level(n):
    """Verify nesting level is within the hierarchy."""
    if not isinstance(n, (int, float)) or n < NESTING_MIN:
        return {
            'value': n,
            'clamped': NESTING_MIN,
            'status': Safety.BEYOND,
            'note': f'Nesting level {n} < 0 is unphysical.',
        }

    if n > NESTING_MAX:
        return {
            'value': n,
            'clamped': NESTING_MAX,
            'status': Safety.BEYOND,
            'note': (f'Nesting level {n} > {NESTING_MAX}. '
                     f'Below Planck mass — quantum gravity takes over. '
                     f'SSBM is undefined here.'),
        }

    return {
        'value': n,
        'clamped': n,
        'status': Safety.SAFE,
        'note': None,
    }


# ═══════════════════════════════════════════════════════════════════════
#  BINDING ENERGY BOUNDS
# ═══════════════════════════════════════════════════════════════════════

def check_binding_energy(be_mev, Z, A, sigma):
    """Check if binding energy remains physical.

    At high σ, the strong binding scales as e^σ while Coulomb stays fixed.
    For very high Z, Coulomb can OVERCOME strong binding → unbound.
    This is a REAL prediction: superheavy nuclei are LESS stable at high σ.
    """
    if be_mev < BE_MIN:
        return {
            'value': be_mev,
            'status': Safety.WALL,
            'note': (f'BE = {be_mev:.2f} MeV < 0 for Z={Z}, A={A} at σ={sigma:.4f}. '
                     f'Nucleus is UNBOUND at this σ. Coulomb repulsion wins. '
                     f'This is a valid prediction, not an error.'),
        }

    return {
        'value': be_mev,
        'status': Safety.SAFE,
        'note': None,
    }


# ═══════════════════════════════════════════════════════════════════════
#  PHYSICAL RADIUS BOUNDS
# ═══════════════════════════════════════════════════════════════════════

def check_radius(r_m, context='general'):
    """Check if a radius is physically meaningful."""
    l_P = math.sqrt(HBAR * G / C**3)  # Planck length ≈ 1.616e-35 m

    if r_m <= 0:
        return {
            'value': r_m,
            'status': Safety.BEYOND,
            'note': 'Radius ≤ 0 is unphysical.',
        }

    if r_m < l_P:
        return {
            'value': r_m,
            'status': Safety.BEYOND,
            'note': (f'r = {r_m:.2e} m < Planck length {l_P:.2e} m. '
                     f'Quantum gravity regime. SSBM (and all semiclassical physics) '
                     f'is undefined below Planck length.'),
        }

    return {
        'value': r_m,
        'status': Safety.SAFE,
        'note': None,
    }


# ═══════════════════════════════════════════════════════════════════════
#  SAFE WRAPPERS — guarded versions of core functions
# ═══════════════════════════════════════════════════════════════════════

def safe_sigma(r_m, M_kg):
    """Compute σ with full safety checking.

    Returns (sigma, safety_check) — never silently returns garbage.
    """
    from .scale import sigma_from_potential

    r_check = check_radius(r_m)
    if r_check['status'] == Safety.BEYOND:
        return (None, r_check)

    sigma = sigma_from_potential(r_m, M_kg)
    s_check = check_sigma(sigma)

    return (sigma if s_check['status'] != Safety.BEYOND else None, s_check)


def safe_proton_mass(sigma):
    """Compute proton mass with safety bounds.

    Returns (mass_mev, safety_check).
    """
    from .nucleon import proton_mass_mev

    s_check = check_sigma(sigma)
    if s_check['status'] == Safety.BEYOND and sigma > SIGMA_WALL:
        return (None, s_check)

    # Clamp σ to valid range
    sigma_use = max(SIGMA_MIN, sigma)
    mass = proton_mass_mev(sigma_use)

    m_check = check_nucleon_mass(mass, 'proton')
    # Return the more severe status
    if m_check['status'] == Safety.BEYOND:
        return (None, m_check)

    return (mass, s_check if s_check['status'] != Safety.SAFE else m_check)


def safe_neutron_mass(sigma):
    """Compute neutron mass with safety bounds.

    Returns (mass_mev, safety_check).
    """
    from .nucleon import neutron_mass_mev

    s_check = check_sigma(sigma)
    if s_check['status'] == Safety.BEYOND and sigma > SIGMA_WALL:
        return (None, s_check)

    sigma_use = max(SIGMA_MIN, sigma)
    mass = neutron_mass_mev(sigma_use)

    m_check = check_nucleon_mass(mass, 'neutron')
    if m_check['status'] == Safety.BEYOND:
        return (None, m_check)

    return (mass, s_check if s_check['status'] != Safety.SAFE else m_check)


def safe_binding(be_total_mev, Z, A, sigma):
    """Compute binding energy with safety checking.

    Returns (be_mev, safety_check).
    Unbound nuclei (BE < 0) return BE=0 with WALL status — that's a prediction.
    """
    from .binding import binding_energy_mev

    s_check = check_sigma(sigma)
    if s_check['status'] == Safety.BEYOND and sigma > SIGMA_WALL:
        return (None, s_check)

    sigma_use = max(SIGMA_MIN, sigma)
    be = binding_energy_mev(be_total_mev, Z, A, sigma_use)

    be_check = check_binding_energy(be, Z, A, sigma_use)
    return (be, be_check)


# ═══════════════════════════════════════════════════════════════════════
#  FULL DOMAIN MAP
# ═══════════════════════════════════════════════════════════════════════

def domain_map():
    """Print the complete domain map for SSBM.

    Shows every variable, its valid range, what happens at the walls,
    and where the model makes predictions vs where it's silent.
    """
    lines = []
    lines.append("")
    lines.append("  ╔═══════════════════════════════════════════════════════════╗")
    lines.append("  ║          SSBM DOMAIN MAP — SHAPE LIMITS                 ║")
    lines.append("  ╚═══════════════════════════════════════════════════════════╝")
    lines.append("")
    lines.append("  VARIABLE          RANGE                  WALL BEHAVIOR")
    lines.append("  ─────────────────────────────────────────────────────────────")
    lines.append(f"  σ (scale field)   [0, {SIGMA_CONV:.4f})           Matter converts at σ_conv")
    lines.append(f"                                           Nucleon mass → bare quark mass")
    lines.append(f"                                           Nuclear bonds break")
    lines.append(f"  η (entanglement)  [0, 1]                 Fully classical ↔ fully entangled")
    lines.append(f"  η = None                                 UNKNOWN — propagates symbolically")
    lines.append(f"  m_p(σ)            [{PROTON_BARE_MEV:.2f}, ∞) MeV       Can't go below bare quarks")
    lines.append(f"  m_n(σ)            [{NEUTRON_BARE_MEV:.2f}, ∞) MeV      Can't go below bare quarks")
    lines.append(f"  BE(σ)             [0, ∞) MeV             BE < 0 → nucleus unbound (prediction)")
    lines.append(f"  nesting level     [0, {NESTING_MAX}]               Hubble mass → Planck mass")
    lines.append(f"  r (radius)        [l_P, ∞) m             Below Planck → quantum gravity")
    lines.append(f"  ξ                 {XI} (fixed)          Measured from Planck 2018")
    lines.append("")
    lines.append("  EDGE WARNINGS:")
    lines.append(f"    σ > {SIGMA_EDGE:.4f}  (80% of σ_conv)   → QCD perturbation theory unreliable")
    lines.append(f"    m_nucleon < 0.5 × m_vacuum         → extreme gravitational field")
    lines.append(f"    m_nucleon > 10 × m_vacuum           → very deep potential well")
    lines.append("")
    lines.append("  HARD STOPS:")
    lines.append("    σ > σ_conv → model returns None (matter doesn't exist)")
    lines.append("    σ < 0     → clamped to 0 (negative σ is unphysical)")
    lines.append("    η < 0     → clamped to 0")
    lines.append("    η > 1     → clamped to 1")
    lines.append("    r ≤ 0     → model returns None")
    lines.append("    r < l_P   → model returns None (quantum gravity)")
    lines.append("")

    return '\n'.join(lines)


def run_boundary_tests():
    """Test every boundary condition explicitly.

    Returns list of (test_name, passed, detail).
    """
    from .scale import sigma_from_potential, scale_ratio
    from .nucleon import proton_mass_mev

    tests = []

    # 1. σ = 0 (vacuum)
    s = check_sigma(0.0)
    tests.append(('σ=0 (vacuum)', s['status'] == Safety.SAFE, s))

    # 2. σ = σ_conv (wall)
    s = check_sigma(SIGMA_CONV)
    tests.append(('σ=σ_conv (wall)', s['status'] == Safety.WALL, s))

    # 3. σ > σ_conv (beyond)
    s = check_sigma(SIGMA_CONV + 0.1)
    tests.append(('σ>σ_conv (beyond)', s['status'] == Safety.BEYOND, s))

    # 4. σ < 0 (unphysical)
    s = check_sigma(-0.01)
    tests.append(('σ<0 (unphysical)', s['status'] == Safety.BEYOND, s))

    # 5. σ at edge
    s = check_sigma(SIGMA_EDGE + 0.01)
    tests.append(('σ=80%+ε of σ_conv (edge)', s['status'] == Safety.EDGE, s))

    # 6. η = None
    e = check_eta(None)
    tests.append(('η=None (unknown)', e['status'] == Safety.SAFE, e))

    # 7. η = ETA (0.4153 — derived from dark energy constraint)
    e = check_eta(ETA)
    tests.append((f'η={ETA} (from DE)', e['status'] == Safety.SAFE, e))

    # 8. η = -0.1
    e = check_eta(-0.1)
    tests.append(('η=-0.1 (invalid)', e['status'] == Safety.BEYOND, e))

    # 9. η = 1.5
    e = check_eta(1.5)
    tests.append(('η=1.5 (invalid)', e['status'] == Safety.BEYOND, e))

    # 10. Proton mass at vacuum
    m = check_nucleon_mass(PROTON_TOTAL_MEV, 'proton')
    tests.append(('m_p at vacuum', m['status'] == Safety.SAFE, m))

    # 11. Proton mass at high σ
    mass_high = proton_mass_mev(1.0)  # σ=1
    m = check_nucleon_mass(mass_high, 'proton')
    # This should be SAFE but enhanced
    tests.append(('m_p at σ=1', m['status'] in (Safety.SAFE, Safety.EDGE), m))

    # 12. Nesting level 0
    n = check_nesting_level(0)
    tests.append(('Level 0 (Hubble)', n['status'] == Safety.SAFE, n))

    # 13. Nesting level 76
    n = check_nesting_level(76)
    tests.append(('Level 76 (Planck)', n['status'] == Safety.SAFE, n))

    # 14. Nesting level 100 (beyond)
    n = check_nesting_level(100)
    tests.append(('Level 100 (beyond)', n['status'] == Safety.BEYOND, n))

    # 15. Safe sigma wrapper
    val, chk = safe_sigma(6.371e6, 5.972e24)  # Earth surface
    tests.append(('safe_sigma(Earth)', val is not None and chk['status'] == Safety.SAFE, chk))

    return tests


def print_boundary_tests():
    """Run and display boundary tests."""
    import time
    t0 = time.perf_counter()

    tests = run_boundary_tests()

    print()
    print("  ╔═══════════════════════════════════════════════════════════╗")
    print("  ║          SHAPE LIMIT TESTS — BOUNDARY CONDITIONS        ║")
    print("  ╚═══════════════════════════════════════════════════════════╝")
    print()

    passed = 0
    for name, ok, detail in tests:
        status = '✓' if ok else '✗'
        color_status = detail.get('status', '?')
        symbol = Safety.symbol(color_status)
        note = detail.get('note', '')
        note_short = (note[:60] + '…') if note and len(note) > 60 else (note or '')
        print(f"  {status}  {symbol} {name:<30s}  {color_status:<7s}  {note_short}")
        if ok:
            passed += 1

    elapsed = time.perf_counter() - t0
    print()
    print(f"  {passed}/{len(tests)} boundary tests passed in {elapsed*1000:.1f} ms")
    print()

    return passed == len(tests)
