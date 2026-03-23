"""
Möbius conductor topology: electromagnetic properties.

The Möbius conductor stack:
  insulator → conductor A → insulator → conductor B
  Twisted into a Möbius strip, stretched into a long loop,
  flat sides pressed together.

The topology enforces counter-flowing currents in A and B.
This has profound electromagnetic consequences:

  1. Magnetic field cancellation
     Opposing currents create opposing B-fields.
     The net field falls off as 1/r³ (quadrupole) instead of
     1/r² (dipole) for a single conductor.
     FIRST_PRINCIPLES: superposition of magnetic fields.

  2. Inductance collapse
     Self-inductance L of a loop depends on the NET magnetic flux.
     Counter-flowing currents cancel most of the flux.
     L_net ≈ L_self × (1 - k²) where k is coupling coefficient.
     For tightly coupled Möbius: k → 1, L_net → 0.
     FIRST_PRINCIPLES: Neumann formula for mutual inductance.

  3. Impedance becomes purely resistive
     Z = R + jωL
     When L → 0: Z → R (frequency-independent!)
     AC behaves like DC through the conductor.
     This is NOT rectification — it's impedance collapse.
     FIRST_PRINCIPLES: circuit theory.

  4. Self-shielding
     Far-field radiation from opposing currents cancels.
     No external shielding needed for EMI suppression.
     Equivalent to an ideal twisted pair, but topologically locked.
     FIRST_PRINCIPLES: antenna theory (quadrupole radiation).

  5. Unlike metals (bimetallic Möbius)
     If conductor A ≠ conductor B (e.g., copper vs iron):
     - Different resistivities → asymmetric current distribution
     - Different Seebeck coefficients → distributed thermoelectric voltage
     - Different skin depths → frequency-dependent current partitioning
     FIRST_PRINCIPLES: Ohm's law + Seebeck effect + skin depth.

σ-dependence:
  Resistivity: EM → σ-INVARIANT
  Inductance: EM → σ-INVARIANT
  Skin depth: through ρ (EM) → σ-INVARIANT
  The Möbius topology is purely geometric → σ-INVARIANT

  But if using unlike metals with Seebeck effect:
  S depends on Fermi energy which depends on electron density
  which depends on number density which shifts with σ through mass.
  So thermoelectric effects in a bimetallic Möbius DO have σ-dependence.

Origin tags:
  - Inductance: FIRST_PRINCIPLES (Neumann formula, Maxwell's equations)
  - Field cancellation: FIRST_PRINCIPLES (Biot-Savart superposition)
  - Impedance: FIRST_PRINCIPLES (circuit theory)
  - Skin depth: FIRST_PRINCIPLES (Maxwell's equations)
  - Coupling coefficient: FIRST_PRINCIPLES (geometry) +
    APPROXIMATION (parallel plate model for tightly pressed conductors)
  - Resistivity: MEASURED (from thermal module)
  - Seebeck: MEASURED + FIRST_PRINCIPLES (Mott formula, from thermoelectric)
"""

import math
from .thermal import _RESISTIVITY_OHM_M, _K_BOLTZMANN

# ── Constants ─────────────────────────────────────────────────────
_MU_0 = 4.0 * math.pi * 1e-7     # H/m (vacuum permeability, exact pre-2019)
_EPSILON_0 = 8.854187817e-12      # F/m (vacuum permittivity)
_ELEMENTARY_CHARGE = 1.602176634e-19  # C


# ── Geometry ──────────────────────────────────────────────────────

def mobius_path_length(loop_length_m):
    """Total conductor path length in a Möbius strip (m).

    A Möbius strip has only ONE surface. A conductor on the surface
    must go around TWICE to return to its starting point.

    But in our stack (two conductors separated by insulator), each
    conductor goes around ONCE. The Möbius twist means that after
    one trip, conductor A is in the position of conductor B.

    For a long loop pressed flat:
      Total path length ≈ 2 × loop_length (there and back)

    Args:
        loop_length_m: length of one side of the pressed-flat loop

    Returns:
        Path length for one conductor in meters.
    """
    return 2.0 * loop_length_m


def conductor_separation(insulator_thickness_m):
    """Distance between the two conductors in the stack (m).

    When pressed flat, the two copper layers are separated by
    the insulator thickness. This sets the coupling.

    For a Möbius stack: insulator → Cu → insulator → Cu
    When pressed flat: Cu → insulator → Cu (the two insulators
    face each other, but the coppers face inward).

    Actually: when you press the Möbius flat, you get:
      Cu_A | insulator | Cu_B | insulator | Cu_A (wraps)

    The separation between A and B is one insulator thickness.

    Args:
        insulator_thickness_m: thickness of one insulator layer

    Returns:
        Center-to-center conductor separation in meters.
    """
    return insulator_thickness_m


# ── Resistance ────────────────────────────────────────────────────

def conductor_resistance(material_key, length_m, width_m, thickness_m):
    """DC resistance of a flat conductor strip (Ω).

    R = ρ × L / A

    FIRST_PRINCIPLES: Ohm's law.

    Args:
        material_key: 'copper', 'iron', etc.
        length_m: conductor length
        width_m: conductor width
        thickness_m: conductor thickness

    Returns:
        Resistance in Ohms.
    """
    rho = _RESISTIVITY_OHM_M.get(material_key)
    if rho is None:
        return float('inf')
    A = width_m * thickness_m
    if A <= 0:
        return float('inf')
    return rho * length_m / A


def mobius_total_resistance(mat_A, mat_B, loop_length_m,
                             width_m, thickness_m):
    """Total resistance of the Möbius conductor pair (Ω).

    The two conductors are in parallel (current splits between them)
    but each carries current in opposite directions.

    For identical metals: R_total = R/2 (parallel)
    For unlike metals: R_total = R_A × R_B / (R_A + R_B)

    FIRST_PRINCIPLES: parallel resistance formula.

    Args:
        mat_A, mat_B: conductor material keys
        loop_length_m: length of one side of the loop
        width_m: conductor width
        thickness_m: conductor thickness per layer

    Returns:
        Total resistance in Ohms.
    """
    path_len = mobius_path_length(loop_length_m)
    R_A = conductor_resistance(mat_A, path_len, width_m, thickness_m)
    R_B = conductor_resistance(mat_B, path_len, width_m, thickness_m)

    if R_A == float('inf') or R_B == float('inf'):
        return float('inf')
    if R_A + R_B <= 0:
        return 0.0

    return R_A * R_B / (R_A + R_B)


# ── Inductance ────────────────────────────────────────────────────

def single_loop_inductance(loop_length_m, width_m):
    """Self-inductance of a single rectangular loop (H).

    For a long thin rectangular loop (length >> width):
      L ≈ μ₀ × length / π × [ln(2×length/width) - 1]

    FIRST_PRINCIPLES: Neumann formula integrated for rectangular geometry.
    APPROXIMATION: assumes length >> width (long loop limit).

    Args:
        loop_length_m: loop perimeter / 2 (one side of pressed flat loop)
        width_m: width of the conductor

    Returns:
        Self-inductance in Henries.
    """
    if loop_length_m <= 0 or width_m <= 0:
        return 0.0

    # For a rectangular loop of total perimeter 2×loop_length:
    ratio = 2.0 * loop_length_m / width_m
    if ratio <= 1:
        ratio = 1.001  # prevent log(0)

    L = _MU_0 * loop_length_m / math.pi * (math.log(ratio) - 1.0)
    return max(0.0, L)


def coupling_coefficient(separation_m, width_m):
    """Magnetic coupling coefficient k between the two conductors.

    For parallel plate conductors pressed close together:
      k ≈ 1 - (d/w)²  for d << w

    Where d = separation, w = conductor width.

    k = 1 means perfect coupling (all flux links both conductors).
    k = 0 means no coupling (independent conductors).

    For a Möbius stack pressed flat with thin insulator:
      d << w → k ≈ 1 → almost complete flux cancellation.

    This is why the Möbius topology is powerful: the topology
    FORCES k to be high regardless of frequency.

    FIRST_PRINCIPLES: ratio of mutual to self flux.
    APPROXIMATION: parallel plate model for tightly pressed conductors.

    Args:
        separation_m: distance between conductors (insulator thickness)
        width_m: conductor width

    Returns:
        k (dimensionless, 0 to 1).
    """
    if width_m <= 0:
        return 0.0

    ratio = separation_m / width_m
    k = 1.0 - ratio**2
    return max(0.0, min(1.0, k))


def mobius_net_inductance(loop_length_m, width_m, separation_m):
    """Net inductance of the Möbius conductor pair (H).

    L_net = L_self × (1 - k²)

    When currents flow in opposite directions in tightly coupled
    conductors, the magnetic fields largely cancel. The net inductance
    is reduced by a factor of (1 - k²).

    For the Möbius stack with thin insulator:
      k → 1, so L_net → 0
      This is the inductance collapse.

    FIRST_PRINCIPLES: mutual inductance theory.
    L_net = L₁ + L₂ - 2M = 2L(1 - k) ≈ 2L(1-k) for identical loops.

    More precisely for counter-flowing currents:
      L_net = L₁ + L₂ - 2M
      For identical conductors: L₁ = L₂ = L, M = kL
      L_net = 2L(1 - k)

    Args:
        loop_length_m: length of one side of the loop
        width_m: conductor width
        separation_m: insulator thickness

    Returns:
        Net inductance in Henries.
    """
    L_self = single_loop_inductance(loop_length_m, width_m)
    k = coupling_coefficient(separation_m, width_m)

    # For two coupled loops with opposing currents:
    # L_net = L₁ + L₂ - 2M = 2L - 2kL = 2L(1-k)
    return 2.0 * L_self * (1.0 - k)


# ── Impedance ─────────────────────────────────────────────────────

def impedance_magnitude(R_ohm, L_henry, frequency_hz):
    """Impedance magnitude |Z| = √(R² + (ωL)²).

    FIRST_PRINCIPLES: complex impedance of RL circuit.

    At low frequency or low L: |Z| ≈ R (purely resistive)
    At high frequency with high L: |Z| ≈ ωL (purely inductive)

    The Möbius topology collapses L → |Z| ≈ R at ALL frequencies.
    This is the key result: AC behaves like DC.

    Args:
        R_ohm: resistance
        L_henry: inductance
        frequency_hz: signal frequency

    Returns:
        |Z| in Ohms.
    """
    omega = 2.0 * math.pi * frequency_hz
    return math.sqrt(R_ohm**2 + (omega * L_henry)**2)


def impedance_phase_deg(R_ohm, L_henry, frequency_hz):
    """Phase angle of impedance (degrees).

    φ = arctan(ωL / R)

    At φ = 0°: purely resistive (DC-like)
    At φ = 90°: purely inductive
    At φ = -90°: purely capacitive

    Möbius topology pushes φ → 0° at all frequencies.

    Args:
        R_ohm: resistance
        L_henry: inductance
        frequency_hz: signal frequency

    Returns:
        Phase angle in degrees.
    """
    omega = 2.0 * math.pi * frequency_hz
    X_L = omega * L_henry
    if R_ohm <= 0:
        return 90.0 if X_L > 0 else 0.0
    return math.degrees(math.atan2(X_L, R_ohm))


def inductance_ratio(loop_length_m, width_m, separation_m):
    """Ratio of Möbius net inductance to single-loop inductance.

    L_mobius / L_single = 2(1-k) / 1

    This quantifies the inductance reduction from the Möbius topology.
    For thin insulator: ratio → 0 (complete cancellation).

    Args:
        loop_length_m: loop length
        width_m: conductor width
        separation_m: insulator thickness

    Returns:
        Ratio (dimensionless). Lower is better.
    """
    L_single = single_loop_inductance(loop_length_m, width_m)
    L_mobius = mobius_net_inductance(loop_length_m, width_m, separation_m)

    if L_single <= 0:
        return 0.0
    return L_mobius / L_single


# ── Skin Depth ────────────────────────────────────────────────────

def skin_depth(material_key, frequency_hz):
    """Skin depth δ (meters) — how deep AC current penetrates.

    δ = √(2ρ / (ωμ₀))

    FIRST_PRINCIPLES: Maxwell's equations in a conductor.
    AC current concentrates near the surface. At depth δ,
    current density has dropped to 1/e of the surface value.

    At 60 Hz in copper: δ ≈ 8.5 mm
    At 1 MHz in copper: δ ≈ 66 μm
    At 1 GHz in copper: δ ≈ 2.1 μm

    For a thin conductor (thickness < δ): current fills the whole
    cross-section → skin effect is irrelevant.

    For thick conductor (thickness > δ): effective resistance
    increases because current only flows in the skin.

    Unlike metals have different skin depths → at high frequencies,
    current preferentially flows through the lower-resistivity
    conductor. This creates frequency-dependent current partitioning
    in a bimetallic Möbius.

    Args:
        material_key: conductor material
        frequency_hz: signal frequency

    Returns:
        Skin depth in meters.
    """
    rho = _RESISTIVITY_OHM_M.get(material_key)
    if rho is None or frequency_hz <= 0:
        return float('inf')

    omega = 2.0 * math.pi * frequency_hz
    return math.sqrt(2.0 * rho / (omega * _MU_0))


def effective_resistance_ac(material_key, length_m, width_m,
                             thickness_m, frequency_hz):
    """AC resistance accounting for skin effect (Ω).

    At DC: R = ρL/A (full cross-section)
    At AC: R_ac = ρL / (w × min(t, δ)) (current in skin only)

    For thin conductors where t < δ: R_ac = R_dc (no skin effect)
    For thick conductors: R_ac > R_dc (reduced effective area)

    FIRST_PRINCIPLES: skin effect from Maxwell's equations.

    Args:
        material_key: conductor material
        length_m: conductor length
        width_m: conductor width
        thickness_m: conductor thickness
        frequency_hz: signal frequency

    Returns:
        AC resistance in Ohms.
    """
    rho = _RESISTIVITY_OHM_M.get(material_key)
    if rho is None:
        return float('inf')

    delta = skin_depth(material_key, frequency_hz)

    # Effective thickness is the lesser of actual thickness and skin depth
    # For skin effect on both sides: 2δ (current enters from both surfaces)
    t_eff = min(thickness_m, 2.0 * delta)

    A_eff = width_m * t_eff
    if A_eff <= 0:
        return float('inf')

    return rho * length_m / A_eff


# ── Magnetic Field Cancellation ───────────────────────────────────

def field_cancellation_ratio(distance_m, separation_m):
    """Magnetic field reduction factor from counter-flowing currents.

    Single conductor: B ∝ 1/r (monopole... well, dipole for a loop)
    Counter-flowing pair: B ∝ d/r² for r >> d (dipole of dipoles)

    The cancellation ratio = B_pair / B_single at distance r:
      ratio ≈ separation / distance

    At 10× the conductor separation: field is reduced to 10%.
    At 100× the separation: field is reduced to 1%.

    This is the self-shielding effect. The Möbius topology
    provides it for free — no Faraday cage needed.

    FIRST_PRINCIPLES: multipole expansion of magnetic field.
    APPROXIMATION: far-field limit (r >> d).

    Args:
        distance_m: observation distance from conductor
        separation_m: distance between the two counter-flowing conductors

    Returns:
        Ratio (0 to 1). Lower = better shielding.
    """
    if distance_m <= 0:
        return 1.0
    if distance_m <= separation_m:
        return 1.0  # near-field, no cancellation

    return separation_m / distance_m


# ── Unlike Metals (Bimetallic Möbius) ────────────────────────────

def bimetallic_seebeck_voltage(mat_A, mat_B, T_hot, T_cold):
    """Seebeck voltage from a bimetallic Möbius strip (V).

    If the two conductors are different metals, every point where
    they are in thermal contact acts as a thermocouple junction.

    For the Möbius geometry: the hot end (one loop) and cold end
    (other loop) create a distributed thermocouple.

    V = (S_A - S_B) × (T_hot - T_cold)

    Uses the Mott formula from the thermoelectric module.

    FIRST_PRINCIPLES: Seebeck effect.

    Args:
        mat_A, mat_B: conductor materials
        T_hot, T_cold: temperatures at the two ends

    Returns:
        Seebeck voltage in Volts.
    """
    from .thermoelectric import seebeck_coefficient

    T_avg = (T_hot + T_cold) / 2.0
    S_A = seebeck_coefficient(mat_A, T_avg)
    S_B = seebeck_coefficient(mat_B, T_avg)

    return abs(S_A - S_B) * (T_hot - T_cold)


def current_partition_ratio(mat_A, mat_B, frequency_hz, thickness_m):
    """Fraction of AC current carried by conductor A vs B.

    At DC: current splits by conductance (1/R_A vs 1/R_B)
    At high frequency: current concentrates in the conductor with
    lower skin depth (lower resistivity).

    The ratio = G_A / (G_A + G_B) where G = 1/R_ac

    For Cu vs Fe at high frequency: almost all current flows
    through Cu because δ_Cu > δ_Fe (lower resistivity → deeper
    penetration → more effective cross-section).

    FIRST_PRINCIPLES: parallel impedance division.

    Args:
        mat_A, mat_B: conductor materials
        frequency_hz: signal frequency
        thickness_m: conductor thickness

    Returns:
        Fraction of current in conductor A (0 to 1).
    """
    delta_A = skin_depth(mat_A, frequency_hz)
    delta_B = skin_depth(mat_B, frequency_hz)

    rho_A = _RESISTIVITY_OHM_M.get(mat_A, float('inf'))
    rho_B = _RESISTIVITY_OHM_M.get(mat_B, float('inf'))

    if rho_A == float('inf') and rho_B == float('inf'):
        return 0.5

    # Effective conductance per unit length: G ∝ min(t, 2δ) / ρ
    t_eff_A = min(thickness_m, 2.0 * delta_A) if delta_A != float('inf') else thickness_m
    t_eff_B = min(thickness_m, 2.0 * delta_B) if delta_B != float('inf') else thickness_m

    G_A = t_eff_A / rho_A if rho_A > 0 else float('inf')
    G_B = t_eff_B / rho_B if rho_B > 0 else float('inf')

    total = G_A + G_B
    if total <= 0 or total == float('inf'):
        return 0.5

    return G_A / total


# ── Full Möbius Analysis ─────────────────────────────────────────

def analyze_mobius_conductor(
    mat_A='copper',
    mat_B='copper',
    loop_length_m=0.10,           # 10 cm loop
    width_m=0.01,                 # 1 cm wide strip
    thickness_m=35e-6,            # 35 μm copper (1 oz PCB standard)
    insulator_thickness_m=100e-6, # 100 μm insulator (FR4-like)
    frequencies_hz=None,          # frequencies to analyze
    T_hot=300.0,                  # temperature at one end
    T_cold=300.0,                 # temperature at other end
):
    """Complete electromagnetic analysis of a Möbius conductor.

    Compares the Möbius topology to a standard single-loop conductor
    at multiple frequencies, quantifying:
      - Inductance reduction
      - Impedance collapse
      - Field cancellation
      - Skin depth effects
      - Unlike metal effects (if mat_A ≠ mat_B)

    Args:
        mat_A, mat_B: conductor materials (same = copper Möbius, different = bimetallic)
        loop_length_m: one side of the pressed-flat loop
        width_m: strip width
        thickness_m: copper thickness per layer
        insulator_thickness_m: insulator layer thickness
        frequencies_hz: list of frequencies to analyze
        T_hot, T_cold: end temperatures (for Seebeck in bimetallic)

    Returns:
        Dict with complete analysis.
    """
    if frequencies_hz is None:
        frequencies_hz = [60.0, 1e3, 1e6, 1e9]  # 60Hz, 1kHz, 1MHz, 1GHz

    # ── Geometry ──
    path_length = mobius_path_length(loop_length_m)
    separation = conductor_separation(insulator_thickness_m)

    # ── DC Resistance ──
    R_A = conductor_resistance(mat_A, path_length, width_m, thickness_m)
    R_B = conductor_resistance(mat_B, path_length, width_m, thickness_m)
    R_parallel = R_A * R_B / (R_A + R_B) if (R_A + R_B) > 0 else float('inf')

    # Reference: single conductor (no Möbius)
    R_single = conductor_resistance(mat_A, path_length, width_m, thickness_m)

    # ── Inductance ──
    L_single = single_loop_inductance(loop_length_m, width_m)
    L_mobius = mobius_net_inductance(loop_length_m, width_m, separation)
    k = coupling_coefficient(separation, width_m)
    L_ratio = inductance_ratio(loop_length_m, width_m, separation)

    # ── Frequency sweep ──
    freq_analysis = []
    for f in frequencies_hz:
        # Single conductor impedance
        Z_single = impedance_magnitude(R_single, L_single, f)
        phase_single = impedance_phase_deg(R_single, L_single, f)

        # Möbius impedance
        Z_mobius = impedance_magnitude(R_parallel, L_mobius, f)
        phase_mobius = impedance_phase_deg(R_parallel, L_mobius, f)

        # Skin depth
        delta_A = skin_depth(mat_A, f)
        delta_B = skin_depth(mat_B, f)

        # Current partition (unlike metals)
        i_fraction_A = current_partition_ratio(mat_A, mat_B, f, thickness_m)

        # Field cancellation at 10× separation distance
        cancel = field_cancellation_ratio(10.0 * separation, separation)

        freq_analysis.append({
            'frequency_hz': f,
            'Z_single_ohm': Z_single,
            'Z_mobius_ohm': Z_mobius,
            'impedance_reduction': 1.0 - Z_mobius / Z_single if Z_single > 0 else 0,
            'phase_single_deg': phase_single,
            'phase_mobius_deg': phase_mobius,
            'skin_depth_A_m': delta_A,
            'skin_depth_B_m': delta_B,
            'current_fraction_A': i_fraction_A,
            'field_cancellation_at_10d': cancel,
        })

    # ── Bimetallic Seebeck ──
    V_seebeck = 0.0
    if mat_A != mat_B and T_hot != T_cold:
        V_seebeck = bimetallic_seebeck_voltage(mat_A, mat_B, T_hot, T_cold)

    return {
        # Geometry
        'mat_A': mat_A,
        'mat_B': mat_B,
        'loop_length_m': loop_length_m,
        'path_length_m': path_length,
        'width_m': width_m,
        'thickness_m': thickness_m,
        'insulator_thickness_m': insulator_thickness_m,
        'separation_m': separation,

        # DC properties
        'R_A_ohm': R_A,
        'R_B_ohm': R_B,
        'R_parallel_ohm': R_parallel,
        'R_single_ohm': R_single,

        # Inductance
        'L_single_H': L_single,
        'L_mobius_H': L_mobius,
        'coupling_coefficient': k,
        'inductance_ratio': L_ratio,

        # Frequency sweep
        'frequency_analysis': freq_analysis,

        # Bimetallic
        'bimetallic': mat_A != mat_B,
        'seebeck_voltage_V': V_seebeck,

        # Origin
        'origin': (
            "Resistance: FIRST_PRINCIPLES (Ohm's law) + MEASURED (resistivity). "
            "Inductance: FIRST_PRINCIPLES (Neumann formula) + "
            "APPROXIMATION (long loop limit, parallel plate coupling). "
            "Impedance: FIRST_PRINCIPLES (complex impedance Z = R + jωL). "
            "Field cancellation: FIRST_PRINCIPLES (multipole expansion). "
            "Skin depth: FIRST_PRINCIPLES (Maxwell's equations). "
            "Seebeck voltage: FIRST_PRINCIPLES (Mott formula) + MEASURED. "
            "Topology: FIRST_PRINCIPLES (Möbius geometry enforces counter-flow)."
        ),
    }


# ══════════════════════════════════════════════════════════════════
# STANDARD CABLE TOPOLOGIES — for comparison
# ══════════════════════════════════════════════════════════════════

# ── Parallel Wire Pair (Shielded) ────────────────────────────────

def parallel_pair_inductance_per_m(wire_radius_m, wire_spacing_m):
    """Inductance per meter of a parallel wire pair (H/m).

    L/ℓ = (μ₀/π) × ln(d/r)

    Where d = center-to-center spacing, r = wire radius.

    FIRST_PRINCIPLES: Neumann formula for two parallel wires.
    This is the external inductance only (internal inductance
    adds μ₀/(8π) per conductor, negligible at high frequency
    due to skin effect).

    For a shielded pair: the shield is a Faraday cage that
    blocks external fields but doesn't reduce the inductance
    between the two internal conductors.

    Args:
        wire_radius_m: radius of each conductor
        wire_spacing_m: center-to-center distance

    Returns:
        Inductance per meter in H/m.
    """
    if wire_radius_m <= 0 or wire_spacing_m <= wire_radius_m:
        return 0.0
    return _MU_0 / math.pi * math.log(wire_spacing_m / wire_radius_m)


def parallel_pair_inductance(wire_radius_m, wire_spacing_m, length_m):
    """Total inductance of a parallel wire pair (H)."""
    return parallel_pair_inductance_per_m(wire_radius_m, wire_spacing_m) * length_m


def shielded_pair_field_cancellation(distance_m, shield_thickness_m,
                                      frequency_hz, material_key='copper'):
    """Field cancellation from a conductive shield.

    Shield effectiveness depends on skin depth:
      SE = 20 × log₁₀(e^(t/δ)) dB ≈ 8.686 × t/δ dB

    Converted to a ratio (linear, not dB):
      ratio = e^(-t/δ)

    At low frequency: δ is large, shield is transparent.
    At high frequency: δ is small, shield blocks effectively.

    FIRST_PRINCIPLES: electromagnetic wave attenuation in conductor.

    Args:
        distance_m: not used directly (shield blocks regardless of distance)
        shield_thickness_m: shield wall thickness
        frequency_hz: signal frequency
        material_key: shield material

    Returns:
        Field ratio (0 to 1). Lower = better shielding.
    """
    if frequency_hz <= 0:
        return 1.0  # DC: shield is transparent (no changing flux)

    delta = skin_depth(material_key, frequency_hz)
    if delta <= 0 or delta == float('inf'):
        return 1.0

    # Attenuation through shield
    return math.exp(-shield_thickness_m / delta)


# ── Coaxial Cable ────────────────────────────────────────────────

def coaxial_inductance_per_m(inner_radius_m, outer_radius_m):
    """Inductance per meter of a coaxial cable (H/m).

    L/ℓ = (μ₀/2π) × ln(D/d)

    Where D = inner radius of outer conductor (shield),
          d = outer radius of inner conductor (center).

    FIRST_PRINCIPLES: Ampere's law + energy stored in B-field.
    The field exists only between the conductors (B = μ₀I/(2πr)).
    No external field at all — perfect self-shielding.

    This is why coax is the gold standard for RF:
      - Zero external field (perfect shielding)
      - Well-defined characteristic impedance
      - Low loss at high frequency

    But: inductance is NOT zero. The field between inner and outer
    conductors stores energy. L depends on the ratio D/d.

    Args:
        inner_radius_m: center conductor outer radius
        outer_radius_m: shield inner radius

    Returns:
        Inductance per meter in H/m.
    """
    if inner_radius_m <= 0 or outer_radius_m <= inner_radius_m:
        return 0.0
    return _MU_0 / (2.0 * math.pi) * math.log(outer_radius_m / inner_radius_m)


def coaxial_inductance(inner_radius_m, outer_radius_m, length_m):
    """Total inductance of a coaxial cable (H)."""
    return coaxial_inductance_per_m(inner_radius_m, outer_radius_m) * length_m


def coaxial_characteristic_impedance(inner_radius_m, outer_radius_m,
                                      dielectric_constant=2.3):
    """Characteristic impedance of a coaxial cable (Ω).

    Z₀ = (1/2π) × √(μ₀/ε₀ε_r) × ln(D/d)
       = (60/√ε_r) × ln(D/d)

    FIRST_PRINCIPLES: transmission line theory (Heaviside).

    Standard values: 50Ω (RF), 75Ω (video/CATV), 93Ω (early computing).

    Args:
        inner_radius_m: center conductor radius
        outer_radius_m: shield inner radius
        dielectric_constant: relative permittivity of insulator

    Returns:
        Z₀ in Ohms.
    """
    if inner_radius_m <= 0 or outer_radius_m <= inner_radius_m:
        return 0.0
    return (60.0 / math.sqrt(dielectric_constant)) * math.log(
        outer_radius_m / inner_radius_m)


def coaxial_field_cancellation(distance_m):
    """Field cancellation for coaxial cable.

    Coax has PERFECT shielding in the ideal case:
    all field is contained between inner and outer conductors.
    External field = 0 at all frequencies.

    Returns 0.0 (perfect cancellation) for any distance.

    In practice, imperfect shields (braided) leak ~1-5%.
    We model ideal (solid) shield.

    FIRST_PRINCIPLES: Gauss's law — no net current enclosed
    outside the shield → no B-field.
    """
    return 0.0  # Perfect shielding


# ── Twisted Pair ─────────────────────────────────────────────────

def twisted_pair_coupling(twists_per_meter, wire_spacing_m):
    """Magnetic coupling coefficient for a twisted pair.

    Twisting two wires alternates which conductor is "closer" to
    an external source, creating cancellation. The coupling between
    the two conductors also increases with tighter twist.

    k_twist ≈ 1 - 1/(1 + (2π × n × d)²)

    Where n = twists per meter, d = wire spacing.
    This is a sigmoid that goes from 0 (no twist) to 1 (infinitely tight).

    APPROXIMATION: empirical model for twist coupling.
    The exact solution requires integrating Neumann's formula
    over the helical geometry.

    Cat5: ~2 twists/cm = 200/m
    Cat6: ~2-3 twists/cm = 200-300/m

    Args:
        twists_per_meter: number of full twists per meter
        wire_spacing_m: center-to-center wire spacing

    Returns:
        Coupling coefficient k (0 to 1).
    """
    x = 2.0 * math.pi * twists_per_meter * wire_spacing_m
    return 1.0 - 1.0 / (1.0 + x**2)


def twisted_pair_inductance_per_m(wire_radius_m, wire_spacing_m,
                                    twists_per_meter=200.0):
    """Inductance per meter of a twisted pair (H/m).

    L_tp = L_parallel × (1 - k_twist)

    The twist creates partial field cancellation, reducing inductance.
    Higher twist rate → higher k → lower L.

    For Cat5 cable (~200 twists/m, 1mm spacing):
      k ≈ 0.61, L reduced to ~39% of parallel pair

    FIRST_PRINCIPLES: Neumann formula with twist correction.
    APPROXIMATION: coupling model is empirical.

    Args:
        wire_radius_m: radius of each conductor
        wire_spacing_m: center-to-center distance
        twists_per_meter: twist rate

    Returns:
        Inductance per meter in H/m.
    """
    L_parallel = parallel_pair_inductance_per_m(wire_radius_m, wire_spacing_m)
    k = twisted_pair_coupling(twists_per_meter, wire_spacing_m)
    return L_parallel * (1.0 - k)


def twisted_pair_inductance(wire_radius_m, wire_spacing_m,
                             twists_per_meter, length_m):
    """Total inductance of a twisted pair (H)."""
    return twisted_pair_inductance_per_m(
        wire_radius_m, wire_spacing_m, twists_per_meter) * length_m


def twisted_pair_field_cancellation(distance_m, wire_spacing_m,
                                     twists_per_meter=200.0):
    """Field cancellation from twisted pair geometry.

    Twisting creates alternating current loops that partially cancel
    the far-field radiation. The cancellation improves with:
      - More twists per meter
      - Greater observation distance
      - Tighter wire spacing

    For N twists over length L, the field at distance r >> L is:
      B_twisted / B_parallel ≈ 1 / (N + 1) for ideal twist

    More practically, the cancellation ratio is:
      ratio ≈ wire_spacing / (distance × π × twists_per_wavelength)

    APPROXIMATION: simplified model. Real twisted pairs have
    variation in twist tightness and irregular geometry.

    Args:
        distance_m: observation distance
        wire_spacing_m: wire spacing
        twists_per_meter: twist rate

    Returns:
        Field ratio (0 to 1). Lower = better.
    """
    if distance_m <= 0 or distance_m <= wire_spacing_m:
        return 1.0

    # Basic dipole cancellation (like Möbius)
    dipole_cancel = wire_spacing_m / distance_m

    # Additional cancellation from twist (alternating loops)
    # Each twist creates a half-period reversal
    # Over many twists, the far-field averages toward zero
    twist_factor = 1.0 / (1.0 + twists_per_meter * wire_spacing_m)

    return min(1.0, dipole_cancel * twist_factor)


# ── Four-Way Topology Comparison ─────────────────────────────────

def compare_topologies(
    length_m=1.0,                  # 1 meter of cable
    material_key='copper',
    # Parallel pair parameters
    pp_wire_radius_m=0.5e-3,      # 0.5mm radius (AWG 20)
    pp_wire_spacing_m=2.0e-3,     # 2mm center-to-center
    pp_shield_thickness_m=0.1e-3, # 0.1mm copper shield
    # Coaxial parameters
    coax_inner_radius_m=0.5e-3,   # RG-58 center conductor
    coax_outer_radius_m=1.5e-3,   # RG-58 shield inner radius
    coax_dielectric=2.3,          # polyethylene
    # Twisted pair parameters
    tp_wire_radius_m=0.5e-3,
    tp_wire_spacing_m=1.5e-3,
    tp_twists_per_m=200.0,        # Cat5-like
    # Möbius parameters
    mob_width_m=0.01,             # 1cm strip
    mob_thickness_m=35e-6,        # 35μm copper
    mob_insulator_m=100e-6,       # 100μm insulator
    # Frequency sweep
    frequencies_hz=None,
):
    """Compare four cable topologies: parallel pair, coax, twisted pair, Möbius.

    All cables use the same conductor material and total length.
    We compare: inductance, impedance, phase angle, and field cancellation
    across a range of frequencies.

    This is the head-to-head showdown.

    Args:
        length_m: cable length
        material_key: conductor material
        (topology-specific geometry parameters)
        frequencies_hz: frequencies to analyze

    Returns:
        Dict with comparison results for all four topologies.
    """
    if frequencies_hz is None:
        frequencies_hz = [60.0, 1e3, 10e3, 100e3, 1e6, 10e6, 100e6, 1e9]

    rho = _RESISTIVITY_OHM_M.get(material_key, 1.68e-8)

    # ── DC Resistance ──
    # Parallel pair: two wires, current goes and returns
    wire_area = math.pi * pp_wire_radius_m**2
    R_pp = rho * length_m / wire_area  # one wire (return path in other)

    # Coax: center conductor
    coax_area = math.pi * coax_inner_radius_m**2
    R_coax = rho * length_m / coax_area

    # Twisted pair: same as parallel pair
    tp_area = math.pi * tp_wire_radius_m**2
    R_tp = rho * length_m / tp_area

    # Möbius: two flat strips in parallel
    mob_area = mob_width_m * mob_thickness_m
    R_mob_single = rho * (2.0 * length_m) / mob_area  # path length = 2×L
    R_mob = R_mob_single / 2.0  # two in parallel

    # ── Inductance ──
    L_pp = parallel_pair_inductance(pp_wire_radius_m, pp_wire_spacing_m, length_m)
    L_coax = coaxial_inductance(coax_inner_radius_m, coax_outer_radius_m, length_m)
    L_tp = twisted_pair_inductance(tp_wire_radius_m, tp_wire_spacing_m,
                                    tp_twists_per_m, length_m)

    # Möbius: use the flat strip model
    mob_loop = length_m / 2.0  # loop_length = half the total path
    k_mob = coupling_coefficient(mob_insulator_m, mob_width_m)
    L_mob = mobius_net_inductance(mob_loop, mob_width_m, mob_insulator_m)

    # ── Frequency sweep ──
    observation_distance = 0.1  # 10 cm away

    sweep = []
    for f in frequencies_hz:
        # Impedance
        Z_pp = impedance_magnitude(R_pp, L_pp, f)
        Z_coax = impedance_magnitude(R_coax, L_coax, f)
        Z_tp = impedance_magnitude(R_tp, L_tp, f)
        Z_mob = impedance_magnitude(R_mob, L_mob, f)

        # Phase
        phase_pp = impedance_phase_deg(R_pp, L_pp, f)
        phase_coax = impedance_phase_deg(R_coax, L_coax, f)
        phase_tp = impedance_phase_deg(R_tp, L_tp, f)
        phase_mob = impedance_phase_deg(R_mob, L_mob, f)

        # Field cancellation
        fc_pp = shielded_pair_field_cancellation(
            observation_distance, pp_shield_thickness_m, f, material_key)
        fc_coax = coaxial_field_cancellation(observation_distance)
        fc_tp = twisted_pair_field_cancellation(
            observation_distance, tp_wire_spacing_m, tp_twists_per_m)
        fc_mob = field_cancellation_ratio(observation_distance, mob_insulator_m)

        sweep.append({
            'frequency_hz': f,
            'Z_parallel_pair_ohm': Z_pp,
            'Z_coaxial_ohm': Z_coax,
            'Z_twisted_pair_ohm': Z_tp,
            'Z_mobius_ohm': Z_mob,
            'phase_parallel_pair_deg': phase_pp,
            'phase_coaxial_deg': phase_coax,
            'phase_twisted_pair_deg': phase_tp,
            'phase_mobius_deg': phase_mob,
            'field_cancel_parallel_pair': fc_pp,
            'field_cancel_coaxial': fc_coax,
            'field_cancel_twisted_pair': fc_tp,
            'field_cancel_mobius': fc_mob,
        })

    # Coaxial characteristic impedance
    Z0_coax = coaxial_characteristic_impedance(
        coax_inner_radius_m, coax_outer_radius_m, coax_dielectric)

    # Twisted pair coupling
    k_tp = twisted_pair_coupling(tp_twists_per_m, tp_wire_spacing_m)

    return {
        'length_m': length_m,
        'material': material_key,

        # DC resistance
        'R_parallel_pair_ohm': R_pp,
        'R_coaxial_ohm': R_coax,
        'R_twisted_pair_ohm': R_tp,
        'R_mobius_ohm': R_mob,

        # Inductance
        'L_parallel_pair_H': L_pp,
        'L_coaxial_H': L_coax,
        'L_twisted_pair_H': L_tp,
        'L_mobius_H': L_mob,

        # Topology-specific
        'coax_Z0_ohm': Z0_coax,
        'twisted_pair_coupling': k_tp,
        'mobius_coupling': k_mob,

        # Frequency sweep
        'frequency_sweep': sweep,

        # Origin
        'origin': (
            "All inductances: FIRST_PRINCIPLES (Neumann formula / Ampere's law). "
            "Parallel pair: L = (μ₀/π)ln(d/r). "
            "Coaxial: L = (μ₀/2π)ln(D/d), perfect shielding (Gauss's law). "
            "Twisted pair: L_pp × (1-k_twist), APPROXIMATION (empirical twist model). "
            "Möbius: 2L(1-k), FIRST_PRINCIPLES (counter-flow cancellation). "
            "Impedance: FIRST_PRINCIPLES (Z = R + jωL). "
            "Shielding: shield skin depth (Maxwell), dipole cancellation (Biot-Savart). "
            "Resistivity: MEASURED."
        ),
    }
