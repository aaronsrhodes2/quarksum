"""
Surface energy from the broken-bond model.

Physics:
  When you cleave a crystal, you break bonds. Each broken bond costs
  energy. The surface energy γ (J/m²) is the total cost per unit area.

  γ = (Z_b - Z_s) / (2 × Z_b) × E_coh × n_surface

  Where:
    Z_b       = bulk coordination number (MEASURED: crystal structure)
    Z_s       = surface coordination number (MEASURED: crystal face)
    E_coh     = cohesive energy per atom (MEASURED, in eV)
    n_surface = surface atom density (atoms/m², from lattice geometry)
    Factor 2  = cleaving creates TWO surfaces (FIRST_PRINCIPLES: geometry)

  This is geometry + measured inputs. No borrowed equations.

σ-dependence:
  At the atomic scale, bonding is electromagnetic (σ-invariant).
  The σ-correction enters through nuclear mass:
    m_nucleus(σ) = m_bare + m_QCD × e^σ

  Heavier nuclei → stiffer lattice → slightly higher surface energy.
  The correction is:
    γ(σ) = γ_EM + γ_QCD_scaling × e^σ

  where γ_QCD_scaling captures the fraction of cohesive energy that
  depends on nuclear mass through lattice dynamics (phonon hardening).

  At Earth (σ ~ 7×10⁻¹⁰): correction < 10⁻⁹, negligible.
  At neutron star surface (σ ~ 0.1): ~1% shift.
  At σ_conv ~ 1.85: lattice destroyed, concept breaks down.

Origin tags:
  - Broken-bond formula: FIRST_PRINCIPLES (geometry of bond counting)
  - Crystal structures: MEASURED
  - Cohesive energies: MEASURED
  - Lattice parameters: MEASURED
  - σ-scaling: CORE (from □σ = −ξR through nuclear mass)
"""

import math
from ..scale import scale_ratio
from ..constants import PROTON_QCD_FRACTION

# ── Conversion ─────────────────────────────────────────────────────
_EV_TO_JOULE = 1.602176634e-19  # exact (2019 SI definition)

# ── Material Database ──────────────────────────────────────────────
# All values are MEASURED from experiment.
# Sources: CRC Handbook, ASM Handbooks, Kittel "Intro to Solid State Physics"
#
# cohesive_energy_ev: energy to remove one atom from bulk to infinity (eV)
# crystal_structure: determines coordination numbers
# lattice_param_angstrom: conventional cubic cell edge (Å)
# preferred_face: lowest-energy cleave plane

MATERIALS = {
    'iron': {
        'name': 'Iron',
        'Z': 26, 'A': 56,
        'density_kg_m3': 7874,
        'cohesive_energy_ev': 4.28,
        'crystal_structure': 'bcc',
        'lattice_param_angstrom': 2.867,
        'preferred_face': '110',
        'composition': 'Fe (α-iron, ferrite)',
    },
    'copper': {
        'name': 'Copper',
        'Z': 29, 'A': 64,
        'density_kg_m3': 8960,
        'cohesive_energy_ev': 3.49,
        'crystal_structure': 'fcc',
        'lattice_param_angstrom': 3.615,
        'preferred_face': '111',
        'composition': 'Cu',
    },
    'aluminum': {
        'name': 'Aluminum',
        'Z': 13, 'A': 27,
        'density_kg_m3': 2700,
        'cohesive_energy_ev': 3.39,
        'crystal_structure': 'fcc',
        'lattice_param_angstrom': 4.050,
        'preferred_face': '111',
        'composition': 'Al',
    },
    'gold': {
        'name': 'Gold',
        'Z': 79, 'A': 197,
        'density_kg_m3': 19300,
        'cohesive_energy_ev': 3.81,
        'crystal_structure': 'fcc',
        'lattice_param_angstrom': 4.078,
        'preferred_face': '111',
        'composition': 'Au',
    },
    'silicon': {
        'name': 'Silicon',
        'Z': 14, 'A': 28,
        'density_kg_m3': 2330,
        'cohesive_energy_ev': 4.63,
        'crystal_structure': 'diamond_cubic',
        'lattice_param_angstrom': 5.431,
        'preferred_face': '111',
        'composition': 'Si (diamond cubic)',
    },
    'tungsten': {
        'name': 'Tungsten',
        'Z': 74, 'A': 184,
        'density_kg_m3': 19250,
        'cohesive_energy_ev': 8.90,
        'crystal_structure': 'bcc',
        'lattice_param_angstrom': 3.165,
        'preferred_face': '110',
        'composition': 'W',
    },
    'nickel': {
        'name': 'Nickel',
        'Z': 28, 'A': 59,
        'density_kg_m3': 8908,
        'cohesive_energy_ev': 4.44,
        'crystal_structure': 'fcc',
        'lattice_param_angstrom': 3.524,
        'preferred_face': '111',
        'composition': 'Ni',
    },
    'titanium': {
        'name': 'Titanium',
        'Z': 22, 'A': 48,
        'density_kg_m3': 4507,
        'cohesive_energy_ev': 4.85,
        'crystal_structure': 'hcp',
        'lattice_param_angstrom': 2.951,
        'preferred_face': '0001',
        'composition': 'Ti (α, HCP)',
    },
}


# ── Coordination Numbers ──────────────────────────────────────────
# Pure geometry of crystal packing. Not empirical fits.

def bulk_coordination(crystal_structure):
    """Number of nearest neighbors in bulk crystal.

    FIRST_PRINCIPLES: geometry of sphere packing.
      FCC/HCP: 12 (close-packed)
      BCC: 8
      Diamond cubic: 4 (tetrahedral bonding)
    """
    table = {
        'fcc': 12,
        'hcp': 12,
        'bcc': 8,
        'diamond_cubic': 4,
    }
    if crystal_structure not in table:
        raise ValueError(f"Unknown crystal structure: {crystal_structure}")
    return table[crystal_structure]


def surface_coordination(crystal_structure, face):
    """Number of nearest neighbors retained at a crystal surface.

    FIRST_PRINCIPLES: geometry of which bonds cross the cleave plane.
    """
    table = {
        ('fcc', '111'): 9,     # 3 broken out of 12
        ('fcc', '100'): 8,     # 4 broken out of 12
        ('fcc', '110'): 7,     # 5 broken out of 12
        ('bcc', '110'): 6,     # 2 broken out of 8
        ('bcc', '100'): 4,     # 4 broken out of 8
        ('diamond_cubic', '111'): 3,  # 1 broken out of 4
        ('diamond_cubic', '110'): 2,  # 2 broken out of 4
        ('hcp', '0001'): 9,    # same as FCC(111) for close-packed basal
    }
    key = (crystal_structure, face)
    if key not in table:
        raise ValueError(f"Unknown face {face} for {crystal_structure}")
    return table[key]


# ── Surface Atom Density ──────────────────────────────────────────
# Atoms per unit area on a given crystal face.
# Pure geometry of the lattice.

def surface_atom_density(crystal_structure, face, lattice_param_angstrom):
    """Surface atom density (atoms/m²) from lattice geometry.

    FIRST_PRINCIPLES: counting atoms on a crystal plane.

    Args:
        crystal_structure: 'fcc', 'bcc', 'hcp', 'diamond_cubic'
        face: Miller indices as string ('111', '110', '100', '0001')
        lattice_param_angstrom: conventional cell edge in Å

    Returns:
        n_surface in atoms/m²
    """
    a = lattice_param_angstrom * 1e-10  # convert to meters

    # Each entry: atoms per unit cell area on that face.
    # Derived by counting atoms in the 2D unit cell of each plane.
    density_table = {
        # FCC: conventional cube edge = a
        ('fcc', '111'): 4.0 / (math.sqrt(3) * a**2),
        ('fcc', '100'): 2.0 / a**2,
        ('fcc', '110'): 2.0 * math.sqrt(2) / a**2,
        # BCC: conventional cube edge = a
        ('bcc', '110'): 2.0 * math.sqrt(2) / a**2,
        ('bcc', '100'): 1.0 / a**2,
        # Diamond cubic: 8 atoms per conventional cell, face densities
        ('diamond_cubic', '111'): 4.0 / (math.sqrt(3) * a**2),
        ('diamond_cubic', '110'): 2.0 * math.sqrt(2) / a**2,
        # HCP: use a as basal plane edge
        ('hcp', '0001'): 4.0 / (math.sqrt(3) * a**2),
    }

    key = (crystal_structure, face)
    if key not in density_table:
        raise ValueError(f"No density formula for {face} on {crystal_structure}")
    return density_table[key]


# ── Surface Energy ────────────────────────────────────────────────

def surface_energy(material_key):
    """Surface energy γ (J/m²) from the broken-bond model at σ=0.

    FIRST_PRINCIPLES formula:
      γ = (Z_b - Z_s) / (2 × Z_b) × E_coh × n_surface

    All inputs are MEASURED. The formula is geometry (bond counting).

    Args:
        material_key: key into MATERIALS dict

    Returns:
        γ in J/m²
    """
    return surface_energy_at_sigma(material_key, sigma=0.0)


def surface_energy_at_sigma(material_key, sigma=0.0):
    """Surface energy at arbitrary σ-field value.

    The σ-correction enters through nuclear mass:
      m(σ) = m_bare + m_QCD × e^σ

    Heavier nuclei shift lattice dynamics. The cohesive energy has a
    small QCD-dependent component through the nuclear mass contribution
    to zero-point phonon energy.

    The decomposition:
      E_coh = E_coh_EM + E_coh_QCD_scaling
      E_coh_EM: electromagnetic bonding (dominant, σ-invariant)
      E_coh_QCD_scaling: nuclear mass dependent fraction

    The QCD fraction of cohesive energy is much smaller than the QCD
    fraction of nucleon mass (~99%), because atomic bonding is EM.
    We estimate it from the zero-point energy contribution:
      E_ZPE ∝ ℏω_D ∝ 1/√m_nucleus
    This gives a fractional shift ~ (1/2) × Δm/m for small σ.

    Args:
        material_key: key into MATERIALS dict
        sigma: σ-field value (dimensionless)

    Returns:
        γ(σ) in J/m²
    """
    mat = MATERIALS[material_key]
    struct = mat['crystal_structure']
    face = mat['preferred_face']
    a = mat['lattice_param_angstrom']
    e_coh_ev = mat['cohesive_energy_ev']

    z_b = bulk_coordination(struct)
    z_s = surface_coordination(struct, face)
    n_s = surface_atom_density(struct, face, a)

    # Broken-bond fraction: what fraction of bonds does a surface atom lose?
    broken_fraction = (z_b - z_s) / (2.0 * z_b)

    # σ-correction to cohesive energy through nuclear mass.
    # Nuclear mass: m(σ) = m_bare + m_QCD × e^σ
    # QCD fraction of nuclear mass ≈ 0.99 (PROTON_QCD_FRACTION)
    # But cohesive energy depends on nuclear mass only through
    # zero-point phonon energy: E_ZPE ∝ 1/√m
    # Fractional change in E_coh from mass shift:
    #   δE/E ≈ f_ZPE × (1 - √(m(0)/m(σ)))
    # where f_ZPE ≈ fraction of cohesive energy from zero-point motion
    #
    # For metals, zero-point energy is ~1-5% of cohesive energy.
    # We use the Debye estimate: E_ZPE = (9/8) k_B Θ_D
    # Typical: Θ_D ~ 300-500K, k_B Θ_D ~ 0.025-0.04 eV
    # vs E_coh ~ 3-5 eV → f_ZPE ~ 0.5-1%
    #
    # For generality, we compute it from the mass ratio:
    f_qcd_mass = PROTON_QCD_FRACTION  # ~0.99 of nuclear mass is QCD

    # Mass ratio: m(σ)/m(0) = (1 - f_qcd + f_qcd × e^σ)
    mass_ratio = (1.0 - f_qcd_mass) + f_qcd_mass * scale_ratio(sigma)

    # Zero-point phonon frequency ∝ 1/√m → E_ZPE ∝ 1/√m
    # The ZPE fraction of cohesive energy (~1% for metals, conservative)
    f_zpe = 0.01

    # Effective cohesive energy at σ:
    # E_coh(σ) = E_coh_bond (EM, invariant) + E_ZPE(σ)
    # E_ZPE(σ) = E_ZPE(0) × √(m(0)/m(σ)) = E_ZPE(0) / √(mass_ratio)
    #
    # But wait — heavier nuclei mean LOWER zero-point energy (less kinetic),
    # which means atoms sit deeper in the potential well → STRONGER effective binding.
    # The correction to surface energy goes the OTHER direction:
    # higher m → lower ZPE → atoms more tightly bound → surface energy INCREASES.
    #
    # ΔE_binding = E_ZPE(0) × (1 - 1/√(mass_ratio))
    # (positive when mass_ratio > 1, meaning tighter binding)
    zpe_correction = f_zpe * e_coh_ev * (1.0 - 1.0 / math.sqrt(mass_ratio))
    e_coh_effective = e_coh_ev + zpe_correction

    # Surface energy: broken bonds × energy per bond × surface density
    gamma = broken_fraction * (e_coh_effective * _EV_TO_JOULE) * n_s

    return gamma


def surface_energy_decomposition(material_key, sigma=0.0):
    """Decompose surface energy into EM-invariant and QCD-scaling parts.

    Returns dict with:
      em_component_j_m2: electromagnetic bonding (σ-invariant)
      qcd_scaling_component_j_m2: nuclear mass dependent (scales with e^σ)
      total_j_m2: sum of both
    """
    mat = MATERIALS[material_key]
    struct = mat['crystal_structure']
    face = mat['preferred_face']
    a = mat['lattice_param_angstrom']
    e_coh_ev = mat['cohesive_energy_ev']

    z_b = bulk_coordination(struct)
    z_s = surface_coordination(struct, face)
    n_s = surface_atom_density(struct, face, a)
    broken_fraction = (z_b - z_s) / (2.0 * z_b)

    # Zero-point energy fraction
    f_zpe = 0.01
    f_qcd_mass = PROTON_QCD_FRACTION
    mass_ratio = (1.0 - f_qcd_mass) + f_qcd_mass * scale_ratio(sigma)

    # EM component: bond energy minus the ZPE part (σ-invariant)
    e_em = e_coh_ev * (1.0 - f_zpe)
    gamma_em = broken_fraction * (e_em * _EV_TO_JOULE) * n_s

    # QCD-scaling component: the ZPE part, which shifts with nuclear mass
    # At σ=0: this is just f_zpe × E_coh
    # At σ>0: this is f_zpe × E_coh × (1 + correction) where
    #   correction = (1 - 1/√mass_ratio) → the additional binding from heavier nuclei
    # But we want pure scaling: γ_QCD(σ) = γ_QCD(0) × scale_factor
    # Scale factor = E_ZPE_correction(σ) / E_ZPE_correction(0)
    # At σ=0: E_ZPE contribution = f_zpe × E_coh (baseline zero-point energy)
    # At σ: E_ZPE contribution shifts because phonon frequency changes
    #
    # Clean decomposition:
    # γ_total(σ) = γ_EM + γ_QCD(σ)
    # γ_EM = (1 - f_zpe) × broken_fraction × E_coh × n_s  [constant]
    # γ_QCD(σ) = f_zpe × E_coh × (1 + (1 - 1/√mass_ratio)/f_zpe × f_zpe) × broken_fraction × n_s
    #
    # Simpler: γ_QCD(σ) = broken_fraction × n_s × f_zpe × E_coh × √(mass_ratio)
    # Because: tighter binding from heavier mass → effective spring constant
    # actually, the ZPE goes DOWN with mass, but binding goes UP.
    # Let's be precise:
    #
    # E_coh_eff(σ) = E_coh_EM + f_zpe × E_coh × (1/1 - 1/√mass_ratio) + f_zpe × E_coh
    # No, let me just compute it directly.

    # Total at this σ:
    zpe_correction = f_zpe * e_coh_ev * (1.0 - 1.0 / math.sqrt(mass_ratio))
    e_coh_effective = e_coh_ev + zpe_correction
    gamma_total = broken_fraction * (e_coh_effective * _EV_TO_JOULE) * n_s

    # QCD component = total - EM
    gamma_qcd = gamma_total - gamma_em

    return {
        'em_component_j_m2': gamma_em,
        'qcd_scaling_component_j_m2': gamma_qcd,
        'total_j_m2': gamma_total,
        'em_fraction': gamma_em / gamma_total if gamma_total > 0 else 0,
        'sigma': sigma,
    }


def material_surface_properties(material_key, sigma=0.0):
    """Export surface properties in Nagatha-compatible format.

    Returns a dict that can be merged into Nagatha's color.json materials.
    """
    gamma = surface_energy_at_sigma(material_key, sigma)
    dec = surface_energy_decomposition(material_key, sigma)

    # Sensitivity: how much does γ change per unit σ?
    # dγ/dσ at this σ, normalized to γ
    ds = 1e-6
    gamma_plus = surface_energy_at_sigma(material_key, sigma + ds)
    sensitivity = (gamma_plus - gamma) / (ds * gamma) if gamma > 0 else 0

    mat = MATERIALS[material_key]
    return {
        'surface_energy_j_m2': gamma,
        'em_fraction': dec['em_fraction'],
        'sigma_sensitivity': sensitivity,
        'crystal_structure': mat['crystal_structure'],
        'preferred_face': mat['preferred_face'],
        'cohesive_energy_ev': mat['cohesive_energy_ev'],
    }
