"""
The Carbon Cigar: gas-phase physics test.

Setup:
  A cylinder of porous compressed carbon (the "cigar"), lit at one end.
  On the mouth end: a spherical vacuum chamber, sealed against the
  cigar but allowing gas/smoke through.

  The vacuum pulls air through the burning carbon. Combustion products
  (CO₂, CO, soot particles) flow through the porous carbon column
  and collect in the sphere.

Physics stack:
  1. Combustion: C + O₂ → CO₂ (complete) or 2C + O₂ → 2CO (incomplete)
     Enthalpy from bond energies via Hess's law (FIRST_PRINCIPLES).

  2. Darcy flow: v = −(κ_perm / η) × ∇P
     Flow through porous medium (FIRST_PRINCIPLES: Darcy 1856).
     κ_perm from Kozeny-Carman equation (FIRST_PRINCIPLES for packed beds).

  3. Temperature profile: gas cools as it flows through the cigar.
     Heat transfer to carbon walls (Newton cooling).

  4. Vacuum sphere: gas fills a known volume.
     PV = nRT gives pressure from accumulated moles.

  5. Soot emission: incomplete combustion produces C nanoparticles.
     These glow as blackbodies at the combustion temperature.
     Push rendering from matter — even in a gas phase.

  6. σ-spectroscopy: the CO₂ in the sphere has vibrational frequencies
     that depend on nuclear mass. Measure the spectrum → read σ.

Derivation chain from σ:
  σ → nuclear mass → molecular mass → gas density → Darcy flow rate
  σ → nuclear mass → reduced mass → vibrational frequencies
  σ → nuclear mass → combustion enthalpy (second order, through ZPE)
  σ → nuclear mass → viscosity → flow resistance

Measured inputs:
  - Bond dissociation energies (C=O, O=O, C-C): MEASURED, EM
  - Porosity of carbon cylinder: MEASURED (geometry)
  - Sphere volume: MEASURED (geometry)

Everything else: DERIVED.

Origin tags:
  - Combustion enthalpy: FIRST_PRINCIPLES (Hess's law) + MEASURED (bond energies)
  - Darcy flow: FIRST_PRINCIPLES (momentum balance in porous media)
  - Kozeny-Carman: FIRST_PRINCIPLES (hydraulic radius model) +
    APPROXIMATION (spherical particle assumption)
  - Temperature profile: FIRST_PRINCIPLES (Newton cooling)
  - Sphere pressure: FIRST_PRINCIPLES (ideal gas law)
  - Soot emission: FIRST_PRINCIPLES (Planck blackbody)
"""

import math
from .gas import (
    MOLECULES, BOND_ENERGIES_EV,
    ideal_gas_density, gas_viscosity, gas_thermal_conductivity,
    gas_cv_molar, gas_cp_molar, number_density_gas,
    molecular_mass_kg, molecule_vibrational_spectrum,
    vibrational_wavenumber, buoyancy_velocity,
    _K_BOLTZMANN, _R_GAS, _AVOGADRO, _EV_TO_JOULE, _AMU_KG,
)
from .thermal import blackbody_color, is_visibly_glowing, _STEFAN_BOLTZMANN

# ── Constants ─────────────────────────────────────────────────────
_ATM_PA = 101325.0  # 1 atmosphere in Pascals


# ── Combustion Chemistry ─────────────────────────────────────────

def combustion_enthalpy_per_mol_C(complete=True):
    """Enthalpy of combustion of carbon, per mole of C (J/mol).

    Complete:   C + O₂ → CO₂
      Bonds broken:  1 × O=O (5.12 eV)
      Bonds formed:  2 × C=O (8.33 eV each)
      ΔH = broken - formed = 5.12 - 16.66 = -11.54 eV/atom
      But wait — we also break C-C bonds in the solid.
      For graphite: each C has 3 bonds, shared between 2 atoms → 1.5 C-C per atom
      C-C bond energy: 3.61 eV → 1.5 × 3.61 = 5.415 eV needed to free one C

      Net: (5.12 + 5.415) - 16.66 = -6.125 eV per C atom
      = -6.125 × 96485 J/mol = -591 kJ/mol
      Measured: -393.5 kJ/mol (for graphite → CO₂)

      Our estimate is off because graphite C-C is aromatic (resonance
      stabilization), not a simple single bond. The effective C-C in
      graphite is ~5.0 eV total cohesive energy (not 3 × 3.61/2).
      We'll use the MEASURED cohesive energy of carbon instead.

    Incomplete: 2C + O₂ → 2CO
      Bonds broken: 1 × O=O (5.12 eV) + 2 × C_solid
      Bonds formed: 2 × C≡O (11.09 eV each)

    FIRST_PRINCIPLES: Hess's law — enthalpy is a state function.
    ΔH_rxn = Σ(bonds broken) - Σ(bonds formed)
    This is exact thermodynamics.

    APPROXIMATION: using average bond energies, not formation enthalpies.
    For precision, we'd use NIST formation enthalpies directly.

    For honesty, we use MEASURED heats of formation:
      C(graphite) + O₂(g) → CO₂(g)   ΔH = -393.5 kJ/mol
      C(graphite) + ½O₂(g) → CO(g)    ΔH = -110.5 kJ/mol

    Args:
        complete: if True, C→CO₂; if False, C→CO

    Returns:
        ΔH in J/mol (negative = exothermic).
    """
    if complete:
        # MEASURED: standard enthalpy of formation of CO₂
        # Source: NIST-JANAF Thermochemical Tables
        return -393500.0  # J/mol
    else:
        # MEASURED: standard enthalpy of formation of CO
        return -110500.0  # J/mol


def combustion_temperature(T_ambient=300.0, complete_fraction=0.8):
    """Adiabatic flame temperature for carbon combustion (K).

    T_flame = T_ambient + |ΔH| / (n_products × C_p_products)

    FIRST_PRINCIPLES: energy conservation. All combustion heat goes
    into heating the products (adiabatic = no heat loss).

    In reality, the flame loses heat by radiation and conduction,
    so actual temperature is lower. We compute both.

    The complete_fraction determines how much C→CO₂ vs C→CO.

    Args:
        T_ambient: ambient temperature in K
        complete_fraction: fraction of C that burns completely (0-1)

    Returns:
        Dict with adiabatic and estimated actual temperatures.
    """
    # Weighted average enthalpy per mole of C
    dH_complete = combustion_enthalpy_per_mol_C(complete=True)
    dH_incomplete = combustion_enthalpy_per_mol_C(complete=False)
    dH_avg = complete_fraction * dH_complete + (1.0 - complete_fraction) * dH_incomplete

    # Products per mole of C:
    # Complete: 1 mol CO₂
    # Incomplete: 1 mol CO
    # Plus excess N₂ from air (~3.76 mol N₂ per mol O₂)
    # For C + O₂ → CO₂: 1 mol O₂ needed, brings 3.76 mol N₂
    # So products: ~1 mol CO₂ + 3.76 mol N₂ = 4.76 mol total

    mol_products = 4.76  # per mol C burned (with air, not pure O₂)

    # Average C_p of products at flame temperature (~1500K)
    # CO₂ at high T: ~50 J/(mol·K), N₂: ~33 J/(mol·K)
    # Weighted: (1 × 50 + 3.76 × 33) / 4.76 ≈ 36.6 J/(mol·K)
    cp_co2_high_T = gas_cp_molar('CO2', T=1500.0)
    cp_n2_high_T = gas_cp_molar('N2', T=1500.0)
    cp_avg = (1.0 * cp_co2_high_T + 3.76 * cp_n2_high_T) / mol_products

    # Adiabatic flame temperature
    delta_T = abs(dH_avg) / (mol_products * cp_avg)
    T_adiabatic = T_ambient + delta_T

    # Actual flame temperature is lower due to radiation losses
    # For carbon combustion in air: typically 60-75% of adiabatic
    # APPROXIMATION: radiation loss factor
    radiation_loss_fraction = 0.35  # ~35% lost to radiation
    T_actual = T_ambient + delta_T * (1.0 - radiation_loss_fraction)

    return {
        'T_adiabatic_K': T_adiabatic,
        'T_actual_K': T_actual,
        'enthalpy_per_mol_C_J': dH_avg,
        'cp_avg_products_J_molK': cp_avg,
        'mol_products_per_mol_C': mol_products,
        'complete_fraction': complete_fraction,
        'origin': (
            "Combustion enthalpy: MEASURED (NIST-JANAF formation enthalpies). "
            "Adiabatic flame T: FIRST_PRINCIPLES (energy conservation). "
            "Actual flame T: APPROXIMATION (radiation loss factor ~35%)."
        ),
    }


# ── Soot Properties ──────────────────────────────────────────────

def soot_fraction(complete_fraction=0.8):
    """Mass fraction of carbon that becomes soot (unburned solid C).

    In a real flame, incomplete combustion produces soot — nanometer-
    scale carbon particles that glow as blackbody emitters. This is
    why flames are yellow: soot at ~1200-1500K.

    For our carbon cigar, the soot fraction depends on the oxygen
    supply. With vacuum suction pulling air through, most carbon
    burns, but some remains as solid particles.

    APPROXIMATION: empirical soot fraction.

    Args:
        complete_fraction: fraction of C that burns completely

    Returns:
        Mass fraction of C that becomes soot (0 to 1).
    """
    # If 80% burns completely (CO₂) and 15% incompletely (CO),
    # the remaining 5% is soot
    co_fraction = min(1.0 - complete_fraction, 0.2)
    soot = max(0.0, 1.0 - complete_fraction - co_fraction)
    return soot


def soot_emission_color(T_combustion):
    """Color of glowing soot particles at combustion temperature.

    Soot particles are solid carbon. They emit as blackbodies.
    This IS push rendering: matter at a temperature broadcasts
    its thermal radiation, regardless of observer.

    The yellow/orange of a flame is soot at 1200-1500K.
    The blue base (if present) is C₂ molecular emission — a
    different mechanism we'd note but not model yet.

    Uses blackbody_color from thermal module.

    Args:
        T_combustion: temperature of soot particles in K

    Returns:
        Dict with color, glowing status, emission power.
    """
    color = blackbody_color(T_combustion)
    glowing = is_visibly_glowing(T_combustion)
    power = _STEFAN_BOLTZMANN * T_combustion**4  # perfect blackbody

    return {
        'rgb': color,
        'visibly_glowing': glowing,
        'emission_power_W_m2': power,
        'temperature_K': T_combustion,
        'origin': 'FIRST_PRINCIPLES (Planck blackbody, Stefan-Boltzmann)',
    }


# ── Darcy Flow Through Porous Carbon ────────────────────────────

def kozeny_carman_permeability(particle_diameter_m, porosity):
    """Permeability of a packed bed of particles (m²).

    κ = d² × ε³ / (180 × (1 - ε)²)

    FIRST_PRINCIPLES: Kozeny-Carman equation. Models the porous
    medium as a bundle of tortuous capillaries. The factor 180
    comes from the Kozeny constant (≈5) × tortuosity correction.

    This is the standard model for flow through packed beds.
    Valid for ε < 0.5 (our carbon cigar is tightly packed).

    APPROXIMATION: assumes spherical particles, uniform packing.

    Args:
        particle_diameter_m: average particle size in meters
        porosity: void fraction (0 to 1)

    Returns:
        Permeability in m² (Darcy's constant).
    """
    d = particle_diameter_m
    eps = porosity

    if eps <= 0 or eps >= 1:
        return 0.0

    return d**2 * eps**3 / (180.0 * (1.0 - eps)**2)


def darcy_flow_velocity(permeability_m2, viscosity_Pa_s,
                         pressure_drop_Pa, length_m):
    """Darcy flow velocity through porous medium (m/s).

    v = −(κ / η) × (ΔP / L)

    FIRST_PRINCIPLES: Darcy's law (1856). The volume-averaged
    velocity of fluid flowing through a porous medium is proportional
    to the pressure gradient and inversely proportional to viscosity.

    This is the gas-phase analog of Ohm's law:
      Flow rate ↔ current
      Pressure drop ↔ voltage
      κ/η ↔ conductance

    Args:
        permeability_m2: Kozeny-Carman permeability
        viscosity_Pa_s: gas viscosity at flow conditions
        pressure_drop_Pa: pressure difference across the cigar
        length_m: length of the porous section

    Returns:
        Superficial velocity in m/s (volume flow / total cross-section).
    """
    if length_m <= 0 or viscosity_Pa_s <= 0:
        return 0.0
    return permeability_m2 * pressure_drop_Pa / (viscosity_Pa_s * length_m)


def darcy_mass_flow_rate(velocity_m_s, density_kg_m3, area_m2):
    """Mass flow rate through cigar cross-section (kg/s).

    ṁ = ρ × v × A

    FIRST_PRINCIPLES: conservation of mass.

    Args:
        velocity_m_s: Darcy velocity
        density_kg_m3: gas density at flow conditions
        area_m2: cross-sectional area of cigar

    Returns:
        Mass flow rate in kg/s.
    """
    return density_kg_m3 * velocity_m_s * area_m2


# ── Vacuum Sphere ────────────────────────────────────────────────

def sphere_pressure(n_moles, T, volume_m3):
    """Pressure in the vacuum sphere from accumulated gas (Pa).

    P = nRT / V

    FIRST_PRINCIPLES: ideal gas law.

    As combustion products flow into the initially evacuated sphere,
    the pressure rises. This is directly measurable.

    Args:
        n_moles: total moles of gas in sphere
        T: temperature of gas in sphere (K)
        volume_m3: sphere volume

    Returns:
        Pressure in Pascals.
    """
    if volume_m3 <= 0 or T <= 0:
        return 0.0
    return n_moles * _R_GAS * T / volume_m3


def sphere_volume(radius_m):
    """Volume of the collection sphere (m³)."""
    return (4.0 / 3.0) * math.pi * radius_m**3


def gas_temperature_after_cooling(T_combustion, T_wall, length_m,
                                    velocity_m_s, diameter_m,
                                    mol_key='CO2', sigma=0.0):
    """Temperature of gas after flowing through the cigar (K).

    Uses Newton's law of cooling along the flow path:
      T(x) = T_wall + (T_combustion - T_wall) × exp(−x/L_cool)

    Where L_cool = ṁ × c_p / (h × P_wetted) is the cooling length.
    h = κ_gas / d_pore is the heat transfer coefficient
    (APPROXIMATION: Nusselt number ≈ 1 for laminar flow in pores).

    FIRST_PRINCIPLES: energy balance on a fluid element.
    APPROXIMATION: Nu = 1 (laminar, fully developed flow in narrow channel).

    Args:
        T_combustion: temperature at the hot end (K)
        T_wall: temperature of the carbon walls (K)
        length_m: length of the cigar porous section
        velocity_m_s: Darcy velocity
        diameter_m: cigar diameter
        mol_key: gas species
        sigma: σ-field value

    Returns:
        Exit temperature in K.
    """
    if velocity_m_s <= 0 or length_m <= 0:
        return T_wall

    T_avg = (T_combustion + T_wall) / 2.0
    kappa_gas = gas_thermal_conductivity(mol_key, T_avg, sigma)
    rho_gas = ideal_gas_density(mol_key, T_avg, sigma=sigma)
    cp = gas_cp_molar(mol_key, T_avg, sigma)
    M = molecular_mass_kg(mol_key, sigma) * _AVOGADRO  # kg/mol

    # Convert cp from J/(mol·K) to J/(kg·K)
    cp_mass = cp / M if M > 0 else 0.0

    # Pore diameter ~ particle diameter (order of magnitude)
    d_pore = diameter_m * 0.1  # APPROXIMATION: pore ~ 10% of cigar diameter

    # Heat transfer coefficient: h = κ/d (Nu ≈ 1)
    if d_pore <= 0:
        return T_wall
    h = kappa_gas / d_pore

    # Cooling length: L_cool = ρ v cp d / (4h) for pipe flow
    # (4h/d comes from perimeter/area = 4/d for a circular pore)
    if h <= 0 or cp_mass <= 0:
        return T_wall
    L_cool = rho_gas * velocity_m_s * cp_mass * d_pore / (4.0 * h)

    # Temperature at exit
    if L_cool <= 0:
        return T_wall
    T_exit = T_wall + (T_combustion - T_wall) * math.exp(-length_m / L_cool)

    return T_exit


# ── Full Cigar Simulation ────────────────────────────────────────

def simulate_carbon_cigar(
    cigar_length_m=0.10,         # 10 cm cigar
    cigar_diameter_m=0.015,      # 15 mm diameter
    particle_diameter_m=100e-6,  # 100 μm carbon particles
    porosity=0.35,               # 35% void fraction
    sphere_radius_m=0.05,        # 5 cm radius sphere (524 mL)
    burn_time_s=60.0,            # 60 seconds of burning
    burn_rate_m_s=1e-4,          # 0.1 mm/s burn rate (MEASURED for charcoal)
    T_ambient=300.0,             # room temperature
    complete_fraction=0.8,       # 80% complete combustion
    sigma=0.0,
):
    """Simulate the complete carbon cigar experiment.

    Setup:
      [lit end] ═══════════════════ [vacuum sphere]
         🔥    carbon porous body      ○

    The vacuum sphere creates a pressure differential that pulls
    air through the burning carbon. Combustion products (CO₂, CO,
    soot) flow through the porous body and collect in the sphere.

    Derivation chain:
      σ → mass → gas density, viscosity → Darcy flow rate
      σ → mass → combustion products → sphere pressure
      σ → mass → vibrational frequencies → IR spectrum in sphere
      σ → mass → soot temperature → blackbody emission color

    Returns:
        Dict with complete characterization of the experiment.
    """
    # ── Geometry ──
    cigar_area = math.pi * (cigar_diameter_m / 2.0)**2
    cigar_volume = cigar_area * cigar_length_m
    V_sphere = sphere_volume(sphere_radius_m)

    # ── Combustion ──
    combustion = combustion_temperature(T_ambient, complete_fraction)
    T_flame = combustion['T_actual_K']

    # ── Darcy flow ──
    # Gas properties at average temperature in the cigar
    T_avg_flow = (T_flame + T_ambient) / 2.0
    eta_gas = gas_viscosity('N2', T_avg_flow, sigma)  # air ≈ N₂

    permeability = kozeny_carman_permeability(particle_diameter_m, porosity)

    # Initial pressure drop: atmospheric on lit end, vacuum on sphere end
    # As sphere fills, the pressure drop decreases
    delta_P_initial = _ATM_PA  # full atmosphere initially

    v_darcy = darcy_flow_velocity(permeability, eta_gas,
                                   delta_P_initial, cigar_length_m)

    mass_flow = darcy_mass_flow_rate(
        v_darcy,
        ideal_gas_density('N2', T_avg_flow, sigma=sigma),
        cigar_area)

    # ── Carbon burned ──
    # Volume of carbon consumed
    burn_length = burn_rate_m_s * burn_time_s
    burn_length = min(burn_length, cigar_length_m)
    V_burned = cigar_area * burn_length
    V_solid_burned = V_burned * (1.0 - porosity)

    # Mass of carbon burned (graphite density ≈ 2200 kg/m³)
    rho_carbon = 2200.0  # kg/m³ (MEASURED for amorphous carbon)
    mass_C_burned = V_solid_burned * rho_carbon

    # Moles of carbon burned
    M_C = 12.011e-3  # kg/mol
    mol_C_burned = mass_C_burned / M_C

    # ── Combustion products ──
    # Complete: C + O₂ → CO₂ (1:1 molar)
    # Incomplete: 2C + O₂ → 2CO (1:0.5:1 molar)
    mol_CO2 = mol_C_burned * complete_fraction
    mol_CO = mol_C_burned * (1.0 - complete_fraction) * 0.8
    mol_soot_C = mol_C_burned * soot_fraction(complete_fraction)

    # O₂ consumed
    mol_O2_consumed = mol_CO2 + mol_CO / 2.0

    # N₂ dragged along (air is 78% N₂, 21% O₂)
    mol_N2_dragged = mol_O2_consumed * (78.0 / 21.0)

    # Total gas moles in sphere
    total_mol_gas = mol_CO2 + mol_CO + mol_N2_dragged

    # ── Gas cooling through cigar ──
    T_exit = gas_temperature_after_cooling(
        T_flame, T_ambient + 50.0,  # walls warm slightly
        cigar_length_m - burn_length,  # remaining unburned length
        v_darcy, cigar_diameter_m,
        mol_key='CO2', sigma=sigma)

    # ── Sphere state ──
    T_sphere = min(T_exit, T_ambient + 20.0)  # sphere itself is near ambient
    P_sphere = sphere_pressure(total_mol_gas, T_sphere, V_sphere)

    # ── Soot emission ──
    soot_color = soot_emission_color(T_flame)

    # ── CO₂ IR spectrum in sphere ──
    co2_spectrum = molecule_vibrational_spectrum('CO2', sigma)

    # ── σ-spectroscopy ──
    # The CO₂ in the sphere has vibrational frequencies that depend on σ.
    # At Earth σ ~ 7e-10, the shift is negligible.
    # But at σ = 0.1 (neutron star surface), CO₂ asymmetric stretch
    # would shift from 2349 cm⁻¹ to a lower frequency.
    co2_asym_bond = MOLECULES['CO2']['bonds'][0]
    wn_sigma0 = vibrational_wavenumber(
        co2_asym_bond['force_constant_N_m'],
        co2_asym_bond['atom_A_amu'], co2_asym_bond['atom_B_amu'],
        sigma=0.0)
    wn_sigma = vibrational_wavenumber(
        co2_asym_bond['force_constant_N_m'],
        co2_asym_bond['atom_A_amu'], co2_asym_bond['atom_B_amu'],
        sigma=sigma)
    frequency_shift_cm_inv = wn_sigma0 - wn_sigma

    # ── Pole-to-pole electricity ──
    # The carbon cigar IS electrically conductive (graphite/carbon).
    # With T_flame at the lit end and ~T_ambient at the mouth end,
    # there's a Seebeck voltage across the cigar body.
    #
    # Carbon/graphite Seebeck coefficient: ~3-5 μV/K (MEASURED)
    # Resistivity: ~3.5 × 10⁻⁵ Ω·m (MEASURED for graphite)
    #
    # V = S × ΔT
    # R = ρ × L / A (accounting for porosity: effective area = A × (1-ε))
    # I = V / (2R) at max power
    # P = V² / (4R)
    #
    # The cigar simultaneously burns, transports gas, AND generates electricity.

    S_carbon_V_K = 4.0e-6  # MEASURED: ~4 μV/K for graphite
    rho_elec_carbon = 3.5e-5  # MEASURED: Ω·m for graphite

    delta_T_cigar = T_flame - T_ambient
    V_seebeck = S_carbon_V_K * delta_T_cigar

    # Effective cross-section for conduction (solid fraction only)
    A_solid = cigar_area * (1.0 - porosity)
    R_cigar = rho_elec_carbon * cigar_length_m / A_solid if A_solid > 0 else float('inf')

    # At max power transfer
    if R_cigar > 0 and R_cigar != float('inf'):
        I_max_power = V_seebeck / (2.0 * R_cigar)
        P_electric = V_seebeck**2 / (4.0 * R_cigar)
    else:
        I_max_power = 0.0
        P_electric = 0.0

    return {
        # Geometry
        'cigar_length_m': cigar_length_m,
        'cigar_diameter_m': cigar_diameter_m,
        'cigar_volume_m3': cigar_volume,
        'sphere_volume_m3': V_sphere,
        'sphere_radius_m': sphere_radius_m,

        # Combustion
        'T_flame_K': T_flame,
        'T_adiabatic_K': combustion['T_adiabatic_K'],
        'burn_length_m': burn_length,
        'mass_carbon_burned_g': mass_C_burned * 1000,
        'mol_carbon_burned': mol_C_burned,

        # Products
        'mol_CO2': mol_CO2,
        'mol_CO': mol_CO,
        'mol_N2': mol_N2_dragged,
        'mol_soot_C': mol_soot_C,
        'total_mol_gas': total_mol_gas,
        'soot_mass_g': mol_soot_C * M_C * 1000,

        # Flow
        'permeability_m2': permeability,
        'darcy_velocity_m_s': v_darcy,
        'mass_flow_rate_kg_s': mass_flow,
        'pressure_drop_Pa': delta_P_initial,
        'gas_viscosity_Pa_s': eta_gas,

        # Temperature
        'T_exit_gas_K': T_exit,
        'T_sphere_K': T_sphere,

        # Sphere
        'sphere_pressure_Pa': P_sphere,
        'sphere_pressure_atm': P_sphere / _ATM_PA,

        # Soot emission
        'soot_color_rgb': soot_color['rgb'],
        'soot_visibly_glowing': soot_color['visibly_glowing'],
        'soot_emission_W_m2': soot_color['emission_power_W_m2'],

        # Pole-to-pole electricity
        'seebeck_voltage_V': V_seebeck,
        'seebeck_voltage_mV': V_seebeck * 1000,
        'cigar_resistance_ohm': R_cigar,
        'electric_current_A': I_max_power,
        'electric_power_W': P_electric,
        'electric_power_uW': P_electric * 1e6,

        # σ-spectroscopy
        'co2_asym_stretch_cm_inv': wn_sigma,
        'co2_asym_stretch_at_sigma0': wn_sigma0,
        'frequency_shift_cm_inv': frequency_shift_cm_inv,
        'co2_spectrum': co2_spectrum,

        # σ
        'sigma': sigma,

        # Origin
        'origin': (
            "Combustion enthalpy: MEASURED (NIST-JANAF). "
            "Flame temperature: FIRST_PRINCIPLES (energy conservation) + "
            "APPROXIMATION (radiation loss ~35%). "
            "Darcy flow: FIRST_PRINCIPLES (Darcy 1856). "
            "Permeability: FIRST_PRINCIPLES (Kozeny-Carman) + "
            "APPROXIMATION (spherical particles). "
            "Gas cooling: FIRST_PRINCIPLES (Newton cooling) + "
            "APPROXIMATION (Nu ≈ 1). "
            "Sphere pressure: FIRST_PRINCIPLES (ideal gas law). "
            "Soot emission: FIRST_PRINCIPLES (Planck blackbody). "
            "Vibrational frequencies: FIRST_PRINCIPLES (ω=√(k/μ)) + "
            "MEASURED (force constants). "
            "σ-spectroscopy: FIRST_PRINCIPLES (mass → frequency shift). "
            "Seebeck voltage: FIRST_PRINCIPLES (thermoelectric effect) + "
            "MEASURED (carbon Seebeck coefficient, resistivity)."
        ),
    }
