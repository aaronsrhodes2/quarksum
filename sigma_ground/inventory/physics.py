"""
QuarkSum physics layer — derive all physics from a loaded structure.

Every quantity here is DERIVED from the loaded structure's particle inventory.
No hardcoded values beyond physical constants (G, c, ħ, η).

ENTANGLEMENT — THE OBSERVER TANGLE
===================================

In SSBM, entanglement is the mechanism by which the universe decides what
needs to be in a definite state.

η = 0.4153 (cosmic entanglement fraction, from dark energy constraint).

When you OBSERVE an object (receive photons from it), you become entangled
with it through the photon interaction:

  1. A photon bounces off (or is emitted by) the object's surface electrons.
  2. The photon carries the electron's quantum state as a correlation.
  3. The photon reaches your detector — you become part of the electron's
     entanglement network.
  4. Collapse: the electron's state (and yours) becomes definite.

The "observer tangle" for a loaded structure is:

  N_observer_tangle = η × N_particles × illumination_fraction

where:
  η = 0.4153   — the fraction of particles already cross-hadron entangled
                  with the broader universe (SSBM constant)
  N_particles  — total baryonic particle count (protons + neutrons + electrons)
  illumination_fraction — fraction of structure visible to the observer (0–1)

Physical interpretation:
  - η particles in ANY object are already in quantum superposition states
    entangled with the universe.
  - When you illuminate the object, photon exchange connects you into that
    network for the illuminated fraction.
  - The "tangle" between observer and object = the count of particles whose
    quantum state becomes correlated with the observer's frame upon observation.

For a fully illuminated object: tangle = η × N_total ≈ 41.5% of all particles.
This is why macroscopic objects look classical: 10²⁵ × 0.415 = 4×10²⁴ particles
are simultaneously entangled with you — any quantum uncertainty averages out
completely.

PHYSICS DERIVED FROM LOADED MATTER
====================================

  total_mass_kg      resolved_mass_kg from the structure tree
  N_protons          counted protons (from particle inventory)
  N_neutrons         counted neutrons
  N_electrons        counted electrons
  N_particles        N_protons + N_neutrons + N_electrons
  N_baryons          N_protons + N_neutrons (nuclear mass carriers)

  GM                 G × total_mass_kg  (gravitational parameter, m³/s²)
  v_escape           sqrt(2 GM / R)     (requires radius_m)
  sigma_surface      −GM / (R c²)       (SSBM σ-field at surface, dimensionless)
  sigma_effective    σ with η-smoothing toward cosmic mean (= 0)

  eta                0.4153             (SSBM cosmic entanglement fraction)
  N_entangled_cosmic η × N_particles    (cross-hadron entangled with universe)
  N_observer_tangle  η × N_particles × illumination_fraction
  tangle_fraction    η × illumination_fraction

  qcd_binding_fraction  fraction of total_mass from QCD binding (~0.99)
  nuclear_binding_J     total nuclear binding energy in joules
  de_broglie_m          thermal de Broglie wavelength at temperature_k
"""

from __future__ import annotations

import math

from sigma_ground.inventory.checksum.particle_inventory import compute_particle_inventory
from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.core.sigma import ETA as _ETA, XI as _XI

# Physical constants (CODATA 2018)
_G    = 6.67430e-11             # m³/(kg·s²) gravitational constant
_C    = CONSTANTS.c             # 2.99792458e8 m/s
_HBAR = CONSTANTS.hbar          # 1.054571817e-34 J·s
_K_B  = CONSTANTS.k_B           # 1.380649e-23 J/K
_M_P  = CONSTANTS.m_p           # proton rest mass kg
_M_N  = CONSTANTS.m_n           # neutron rest mass kg
_M_E  = CONSTANTS.m_e           # electron rest mass kg

# SSBM constants — imported from sigma_ground.inventory.core.sigma (single source of truth)
# _ETA = ETA = 0.4153  (cosmic entanglement fraction, dark energy constraint)
# _XI  = XI  = 0.1582  (baryon fraction, Planck 2018)
_PROTON_QCD_FRACTION  = 0.9904  # fraction of proton mass from QCD binding
_NEUTRON_QCD_FRACTION = 0.9878  # fraction of neutron mass from QCD binding


def compute_tangle(
    structure,
    illumination_fraction: float = 1.0,
) -> dict:
    """Compute the observer tangle for a loaded structure.

    The "tangle" is the number of particles in the structure whose quantum
    state becomes correlated with an observing frame when the structure is
    illuminated.

    Args:
        structure: resolved Structure from quarksum (must have resolved_mass_kg)
        illumination_fraction: fraction of structure visible to observer (0–1).
            1.0 = fully illuminated (e.g. a planet in full sunlight, looking at
            all faces of a cube simultaneously).
            0.5 = half illuminated (e.g. a hemisphere, a waning moon).

    Returns:
        dict with tangle physics derived entirely from the loaded particles.
    """
    if not (0.0 <= illumination_fraction <= 1.0):
        raise ValueError(
            f"illumination_fraction must be in [0, 1], got {illumination_fraction}"
        )

    inv = compute_particle_inventory(structure)
    N_p = inv["protons"]
    N_n = inv["neutrons"]
    N_e = inv["electrons"]
    N_total = N_p + N_n + N_e
    N_baryons = N_p + N_n

    N_entangled_cosmic = _ETA * N_total
    N_observer_tangle  = _ETA * N_total * illumination_fraction
    tangle_fraction    = _ETA * illumination_fraction

    return {
        "structure_name":        structure.name,
        "total_mass_kg":         structure.resolved_mass_kg,
        "N_protons":             N_p,
        "N_neutrons":            N_n,
        "N_electrons":           N_e,
        "N_particles_total":     N_total,
        "N_baryons":             N_baryons,
        "eta":                   _ETA,
        "illumination_fraction": illumination_fraction,
        "N_entangled_cosmic":    N_entangled_cosmic,
        "N_observer_tangle":     N_observer_tangle,
        "tangle_fraction":       tangle_fraction,
        "note": (
            f"Of {N_total:.3e} particles, {N_entangled_cosmic:.3e} are "
            f"cross-hadron entangled with the universe (η={_ETA}). "
            f"When {illumination_fraction*100:.1f}% is illuminated, "
            f"{N_observer_tangle:.3e} particles are tangled with the observer."
        ),
    }


def compute_physics(
    structure,
    radius_m: float | None = None,
    temperature_k: float = 300.0,
    illumination_fraction: float = 1.0,
) -> dict:
    """Derive ALL physics from a loaded structure.

    Every number in the output traces back to the particles in the loaded
    structure — no hardcoded assumptions about what the structure IS.

    Args:
        structure:            resolved Structure from quarksum
        radius_m:             characteristic radius in metres (optional).
                              Required for: v_escape, sigma_surface, sigma_effective.
                              Use DefaultLoad.radius_m for canonical values.
        temperature_k:        ambient temperature for thermal physics (default: 300 K)
        illumination_fraction: observer illumination fraction for tangle (default: 1.0)

    Returns:
        dict with all physics derived from the loaded matter.
    """
    mass = structure.resolved_mass_kg

    # ── Particle inventory ────────────────────────────────────────────────────
    inv = compute_particle_inventory(structure)
    N_p = inv["protons"]
    N_n = inv["neutrons"]
    N_e = inv["electrons"]
    N_total   = N_p + N_n + N_e
    N_baryons = N_p + N_n

    # ── Gravitational physics ─────────────────────────────────────────────────
    GM = _G * mass

    v_escape = None
    sigma_surface = None
    sigma_effective = None

    if radius_m is not None and radius_m > 0:
        v_escape = math.sqrt(2.0 * GM / radius_m)
        # SSBM σ-field at the surface (dimensionless gravitational potential)
        # σ = −Φ/c² = −GM/(Rc²)  (negative = deeper than background)
        sigma_surface = -GM / (radius_m * _C**2)
        # σ_eff: entanglement pulls σ toward cosmic mean (σ_mean = 0)
        # σ_eff = σ_local - η/2 × (σ_local - σ_mean)
        sigma_effective = sigma_surface - (_ETA / 2.0) * (sigma_surface - 0.0)

    # ── QCD & nuclear binding ─────────────────────────────────────────────────
    # Constituent mass (what the particles would weigh if quarks were free)
    constituent_mass_p = N_p * _M_P
    constituent_mass_n = N_n * _M_N
    constituent_mass_e = N_e * _M_E
    constituent_mass_total = constituent_mass_p + constituent_mass_n + constituent_mass_e

    # QCD binding = the difference between constituent mass and stable mass
    # (nuclear binding energy is additional, smaller correction)
    # For protons: ~99.04% of mass is QCD binding energy
    # For neutrons: ~98.78% of mass is QCD binding energy
    qcd_binding_mass_kg = (
        N_p * _M_P * _PROTON_QCD_FRACTION
        + N_n * _M_N * _NEUTRON_QCD_FRACTION
    )
    # QCD binding fraction of total structure mass
    qcd_binding_fraction = qcd_binding_mass_kg / mass if mass > 0 else 0.0

    # Nuclear binding energy: the ~8 MeV/nucleon that holds nuclei together
    # This is ADDITIONAL to QCD binding. It is the much smaller correction.
    # Approximate: nuclear_be ≈ 8.0 MeV per baryon (empirical average for Z>2)
    # Hydrogen has zero nuclear binding (single proton, no nucleus to bind).
    # Exact: would require per-isotope data. This is the order-of-magnitude.
    _MEV_TO_J = 1.602176634e-13
    nuclear_be_per_baryon_mev = 8.0    # MeV (average for stable nuclei, A>4)
    nuclear_binding_J = N_baryons * nuclear_be_per_baryon_mev * _MEV_TO_J

    # ── Entanglement / observer tangle ────────────────────────────────────────
    tangle = compute_tangle(structure, illumination_fraction)

    # ── Thermal physics ───────────────────────────────────────────────────────
    # Thermal de Broglie wavelength λ = ħ / sqrt(m_avg × k_B × T)
    # Using average baryon mass for the thermal wavelength
    if N_baryons > 0 and temperature_k > 0:
        m_avg = mass / N_baryons  # average mass per baryon
        lambda_dB = _HBAR / math.sqrt(m_avg * _K_B * temperature_k)
    else:
        lambda_dB = None

    # Equipartition energy: <E> = (3/2) k_B T per degree of freedom
    # For N_baryons particles with 3 translational DOF each:
    thermal_energy_J = 1.5 * N_baryons * _K_B * temperature_k

    # ── Assemble report ───────────────────────────────────────────────────────
    result: dict = {
        "structure_name":          structure.name,

        # Mass
        "total_mass_kg":           mass,
        "constituent_mass_kg":     constituent_mass_total,
        "mass_defect_kg":          mass - constituent_mass_total,

        # Particles (all derived from loaded matter)
        "N_protons":               N_p,
        "N_neutrons":              N_n,
        "N_electrons":             N_e,
        "N_particles_total":       N_total,
        "N_baryons":               N_baryons,

        # Gravitational
        "GM_m3_s2":                GM,
        "v_escape_m_s":            v_escape,
        "radius_m":                radius_m,
        "sigma_surface":           sigma_surface,
        "sigma_effective":         sigma_effective,

        # QCD / nuclear
        "qcd_binding_mass_kg":     qcd_binding_mass_kg,
        "qcd_binding_fraction":    qcd_binding_fraction,
        "nuclear_binding_J":       nuclear_binding_J,

        # Entanglement (observer tangle)
        "eta":                     _ETA,
        "N_entangled_cosmic":      tangle["N_entangled_cosmic"],
        "N_observer_tangle":       tangle["N_observer_tangle"],
        "tangle_fraction":         tangle["tangle_fraction"],
        "illumination_fraction":   illumination_fraction,

        # Thermal
        "temperature_k":           temperature_k,
        "thermal_energy_J":        thermal_energy_J,
        "de_broglie_m":            lambda_dB,
    }

    return result
