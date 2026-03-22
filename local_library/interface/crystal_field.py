"""
Crystal field theory — optical properties of transition metal ions in minerals.

Color in gems and minerals comes from d-electron transitions in partially-filled
d-shells of transition metal ions. The energy of these transitions depends on:

  1. The d-electron count (element + oxidation state)
  2. The crystal field splitting Δ (10Dq) — set by coordination geometry + ligands
  3. The Racah B parameter — electron-electron repulsion in the metal ion

Derivation chain:
  Z + oxidation state → d-electron count (FIRST_PRINCIPLES: Aufbau + Hund's rules)
  coordination geometry + ligand type → 10Dq (MEASURED: optical absorption spectroscopy)
  10Dq, B → absorption energies (FIRST_PRINCIPLES: Tanabe-Sugano theory)
  nephelauxetic β → B_crystal = β × B_free (MEASURED: Jørgensen 1962)
  absorption energies → RGB via Beer-Lambert (FIRST_PRINCIPLES)

σ-dependence: NONE — all crystal field effects are electromagnetic.
  The crystal field is an electrostatic effect (Coulomb repulsion between
  d-electrons and ligand electron clouds). Coulomb energy is EM → σ-INVARIANT.
  Crystal bond lengths are EM-determined → σ-INVARIANT.
  Color is EM → σ-INVARIANT.

Origin tags:
  - d-electron configuration: FIRST_PRINCIPLES (Aufbau principle, Hund's rules)
  - Transition energies (d³, d⁸): FIRST_PRINCIPLES (Tanabe-Sugano theory,
      strong-field approximation: ν₂ ≈ Δ + 9B for d³, ν₂ ≈ Δ + 8B for d⁸)
  - Transition energies (d¹, d⁹): FIRST_PRINCIPLES (single Δ band, exact)
  - d⁵ high-spin transitions: APPROXIMATION (spin-forbidden; empirical bands)
  - 10Dq values: MEASURED (optical spectroscopy)
    Sources: Burns (1993) "Mineralogical Applications of Crystal Field Theory" 2nd ed.
             Lever (1984) "Inorganic Electronic Spectroscopy" 2nd ed.
             Figgis & Hitchman (2000) "Ligand Field Theory and Its Applications"
  - Racah B (free ion): MEASURED (atomic emission spectroscopy)
    Source: Lever (1984) Table 1.3
  - Nephelauxetic β: MEASURED (per coordination type)
    Source: Jørgensen (1962); Figgis & Hitchman (2000) Ch. 4
  - Beer-Lambert transmission: FIRST_PRINCIPLES

□σ = −ξR   (all quantities here: EM, σ-invariant)
"""

import math

# ── Fundamental constants ──────────────────────────────────────────────────
_EV_TO_CM1 = 8065.54         # 1 eV = 8065.54 cm⁻¹  (CODATA 2018)
_NM_EV     = 1239.84193      # hc/e in nm·eV (exact from SI 2019)

# ── Visible wavelengths for RGB sampling ──────────────────────────────────
_LAMBDA_R_NM = 650.0   # L-cone peak (CIE 1931)
_LAMBDA_G_NM = 550.0   # M-cone peak
_LAMBDA_B_NM = 450.0   # S-cone peak


def _lambda_nm_from_ev(energy_ev):
    """Photon wavelength in nm from energy in eV.  λ = hc/E."""
    if energy_ev <= 0:
        return float('inf')
    return _NM_EV / energy_ev


# ── d-electron count from Z and oxidation state ────────────────────────────
#
# FIRST_PRINCIPLES: Aufbau principle + Hund's rules.
# For M^(ox_state)+: d_electrons = Z - ox_state - (core electrons before d)
#
# Core electrons before d-shell:
#   3d series (Z=21-30, Sc-Zn): [Ar] = 18 electrons
#   4d series (Z=39-48, Y-Cd):  [Kr] = 36 electrons
#   5d series (Z=57, 72-80):    [Xe] = 54 electrons

_D_SERIES = [
    (range(21, 31), 18),   # 3d: Sc–Zn
    (range(39, 49), 36),   # 4d: Y–Cd
    (range(57, 58), 54),   # La (5d¹ in neutral, but we handle it)
    (range(72, 81), 54),   # 5d: Hf–Hg
]


def d_electron_count(Z: int, oxidation_state: int) -> int:
    """Number of d-electrons in a transition metal ion M^(ox_state)+.

    FIRST_PRINCIPLES: Aufbau + Hund's rules.
      d_count = Z - oxidation_state - (core electrons in shells before d)

    Returns 0 if Z is not a d-block transition metal, or if count would be
    negative (over-oxidised), or 10 for a full d-shell.

    σ-dependence: NONE (electron count is a quantum number, EM).
    """
    for z_range, core in _D_SERIES:
        if Z in z_range:
            d = Z - oxidation_state - core
            return max(0, min(10, d))
    return 0


# ── Free-ion Racah B parameter (MEASURED) ─────────────────────────────────
#
# Racah B measures electron-electron repulsion. The in-crystal value is
# reduced by covalency: B_crystal = β × B_free (nephelauxetic effect).
#
# Units: eV (converted from cm⁻¹ in source tables).
# Source: Lever (1984) Table 1.3. Atomic spectroscopy, MEASURED.

FREE_ION_RACAH_B_EV = {
    # (Z, oxidation_state): B_free in eV
    (22, 3): 718  / _EV_TO_CM1,    # Ti³⁺ (d¹)  — B rarely needed
    (22, 4): 780  / _EV_TO_CM1,    # Ti⁴⁺ (d⁰)
    (23, 3): 861  / _EV_TO_CM1,    # V³⁺  (d²)
    (23, 4): 1040 / _EV_TO_CM1,    # V⁴⁺  (d¹)
    (24, 2): 830  / _EV_TO_CM1,    # Cr²⁺ (d⁴)
    (24, 3): 918  / _EV_TO_CM1,    # Cr³⁺ (d³)  — ruby, emerald
    (25, 2): 860  / _EV_TO_CM1,    # Mn²⁺ (d⁵)
    (25, 3): 1140 / _EV_TO_CM1,    # Mn³⁺ (d⁴)
    (26, 2): 917  / _EV_TO_CM1,    # Fe²⁺ (d⁶)
    (26, 3): 1015 / _EV_TO_CM1,    # Fe³⁺ (d⁵)
    (27, 2): 971  / _EV_TO_CM1,    # Co²⁺ (d⁷)
    (27, 3): 1100 / _EV_TO_CM1,    # Co³⁺ (d⁶ low-spin)
    (28, 2): 1041 / _EV_TO_CM1,    # Ni²⁺ (d⁸)  — green minerals
    (29, 2): 1210 / _EV_TO_CM1,    # Cu²⁺ (d⁹)  — malachite, azurite
    (30, 2): 0.0,                   # Zn²⁺ (d¹⁰) — colorless
}


# ── Nephelauxetic β (MEASURED) ─────────────────────────────────────────────
#
# β < 1: covalent bonding reduces electron-electron repulsion.
# B_crystal = β × B_free_ion
#
# Source: Jørgensen (1962) "Absorption Spectra and Chemical Bonding in
#   Complexes", pp. 106-113. Figgis & Hitchman (2000) Table 4.1.
# MEASURED: spectroscopic comparison of crystal vs free-ion Racah B.

NEPHELAUXETIC_BETA = {
    'oxide_oct':      0.82,   # O²⁻ octahedral (corundum, spinel, binary oxides)
    'silicate_oct':   0.80,   # SiO₄/BeO₄ octahedral (beryl, garnet, pyroxene)
    'carbonate_oct':  0.77,   # CO₃²⁻ octahedral (malachite, calcite)
    'azurite_oct':    0.77,   # Cu-specific: hydroxycarbonate (azurite)
    'phosphate_oct':  0.78,   # PO₄³⁻ octahedral (turquoise)
    'water_oct':      0.88,   # H₂O octahedral (aqueous, most ionic ligands)
    'oxide_tet':      0.78,   # O²⁻ tetrahedral (spinel, normal)
    'silicate_tet':   0.76,   # SiO₄ tetrahedral
    'fluoride_oct':   0.90,   # F⁻ octahedral (very ionic, small reduction)
    'sulfide_oct':    0.60,   # S²⁻ octahedral (strong covalency)
    'cn_oct':         0.50,   # CN⁻ octahedral (very strong covalency)
    'garnet_oct':     0.81,   # garnet sites (approximate oxide)
    'pyroxene_oct':   0.79,   # pyroxene chain silicate
}


# ── Crystal field splitting 10Dq (MEASURED) ───────────────────────────────
#
# The fundamental parameter Δ = 10Dq: energy separation between t₂g and eₘ
# d-orbitals in an octahedral field. Determines ALL absorption energies
# via Tanabe-Sugano theory.
#
# MEASURED from the position of ν₁ absorption band in optical spectra:
#   d³, d⁸ octahedral: ν₁ (first spin-allowed band) = Δ exactly.
#   d¹, d⁶ octahedral: ν₁ = Δ.
#   d⁹: ν₁ ≈ Δ (Jahn-Teller distorted, but ν_barycenter = Δ).
#
# Key: (Z, oxidation_state, coord_key)
# Val: Δ in eV
#
# Sources:
#   Burns (1993) "Mineralogical Applications of Crystal Field Theory" 2nd ed.
#   Lever (1984) "Inorganic Electronic Spectroscopy" 2nd ed.

CRYSTAL_FIELD_10DQ_EV = {

    # ── Cr³⁺ (d³) ──────────────────────────────────────────────────────────
    # Ruby: Cr³⁺ in Al₂O₃ (corundum). ν₁ at 18000 cm⁻¹ (556nm).
    # Burns (1993) Table 4.3. MEASURED.
    (24, 3, 'oxide_oct'):    18000 / _EV_TO_CM1,   # 2.232 eV → RUBY

    # Emerald: Cr³⁺ in Be₃Al₂Si₆O₁₈ (beryl). ν₁ at 16500 cm⁻¹ (606nm).
    # Burns (1993) Table 4.4. MEASURED.
    (24, 3, 'silicate_oct'): 16500 / _EV_TO_CM1,   # 2.047 eV → EMERALD

    # Garnet (pyrope, uvarovite): Cr³⁺ in Al/Ca garnet. ~17300 cm⁻¹.
    # Burns (1993). MEASURED.
    (24, 3, 'garnet_oct'):   17300 / _EV_TO_CM1,   # 2.146 eV → deep red-green

    # ── Cu²⁺ (d⁹) ──────────────────────────────────────────────────────────
    # Malachite: Cu²⁺ in Cu₂(CO₃)(OH)₂. Reflectance minimum at ~700nm.
    # Mixed hydroxycarbonate sites. 10Dq from reflectance dip position.
    # Gettens & Stout (1966); Lever (1984) Table IV.10. MEASURED.
    (29, 2, 'carbonate_oct'): 14200 / _EV_TO_CM1,  # 1.761 eV → MALACHITE (green)

    # Azurite: Cu²⁺ in Cu₃(CO₃)₂(OH)₂. Main band at ~625nm.
    # Different Cu site geometry → shorter λ than malachite.
    # Burns (1993); Gettens (1966). MEASURED.
    (29, 2, 'azurite_oct'):   14400 / _EV_TO_CM1,  # 1.786 eV → AZURITE (blue)

    # Turquoise: Cu²⁺ in CuAl₆(PO₄)₄(OH)₈·4H₂O. Band at ~680nm.
    # Lever (1984). MEASURED.
    (29, 2, 'phosphate_oct'): 13000 / _EV_TO_CM1,  # 1.612 eV → TURQUOISE (blue-green)

    # Aqueous Cu²⁺: [Cu(H₂O)₆]²⁺. Characteristic blue of copper sulfate solution.
    # Lever (1984) p.462. MEASURED.
    (29, 2, 'water_oct'):     12600 / _EV_TO_CM1,  # 1.563 eV → sky blue

    # ── Fe²⁺ (d⁶) ──────────────────────────────────────────────────────────
    # Olivine/peridot: Fe²⁺ in (Mg,Fe)₂SiO₄. Site M1: ~10500 cm⁻¹ (950nm NIR).
    # Burns (1993) Table 5.2. MEASURED.
    (26, 2, 'silicate_oct'):  10500 / _EV_TO_CM1,  # 1.302 eV → PERIDOT (yellow-green)

    # Pyroxene: Fe²⁺ in MgSiO₃/FeSiO₃ chains.
    # Burns (1993) Table 5.5. MEASURED.
    (26, 2, 'pyroxene_oct'):  11000 / _EV_TO_CM1,  # 1.365 eV

    # Iron oxides: Fe²⁺ in magnetite etc. Lower Δ in denser oxide field.
    (26, 2, 'oxide_oct'):      8000 / _EV_TO_CM1,  # 0.992 eV

    # ── Fe³⁺ (d⁵ high-spin) ─────────────────────────────────────────────────
    # Goethite/hematite: spin-forbidden transitions → weak color (yellow-brown).
    # Burns (1993). 10Dq reference value only — color from empirical bands.
    (26, 3, 'oxide_oct'):     13600 / _EV_TO_CM1,  # 1.686 eV (reference)

    # ── Mn²⁺ (d⁵ high-spin) ─────────────────────────────────────────────────
    # Spessartine garnet: spin-forbidden → pale pink/orange.
    # Burns (1993). 10Dq reference.
    (25, 2, 'silicate_oct'):   9200 / _EV_TO_CM1,  # 1.141 eV (reference)
    (25, 2, 'oxide_oct'):      9000 / _EV_TO_CM1,  # 1.116 eV

    # ── Mn³⁺ (d⁴, Jahn-Teller) ──────────────────────────────────────────────
    # Piemontite epidote: Ca₂(Al,Mn)₃(SiO₄)₃(OH). Pink/red mineral.
    # Burns (1993). MEASURED.
    (25, 3, 'silicate_oct'):  16000 / _EV_TO_CM1,  # 1.984 eV → pink-red

    # ── Ni²⁺ (d⁸) ──────────────────────────────────────────────────────────
    # Nickel minerals (gaspeite, zaratite). ν₁ at ~730nm, ν₂ at ~390nm.
    # Lever (1984) p.492. MEASURED.
    (28, 2, 'oxide_oct'):      8700 / _EV_TO_CM1,  # 1.079 eV → green (apple)
    (28, 2, 'silicate_oct'):   8200 / _EV_TO_CM1,  # 1.017 eV
    (28, 2, 'carbonate_oct'):  8900 / _EV_TO_CM1,  # 1.104 eV → bright green

    # ── Co²⁺ (d⁷) ──────────────────────────────────────────────────────────
    # Tetrahedral cobalt (spinel CoAl₂O₄): vivid cobalt blue.
    # Δ_tet ≈ (4/9)Δ_oct → small Δ puts all bands in visible.
    # Lever (1984) p.480. MEASURED.
    (27, 2, 'oxide_tet'):      6300 / _EV_TO_CM1,  # 0.781 eV → COBALT BLUE
    (27, 2, 'silicate_tet'):   5800 / _EV_TO_CM1,  # 0.720 eV

    # Octahedral Co²⁺ (aqueous, less common in minerals): pink.
    (27, 2, 'water_oct'):      8500 / _EV_TO_CM1,  # 1.054 eV → pink

    # ── V³⁺ (d²) ────────────────────────────────────────────────────────────
    # Alexandrite (color-change, red in incandescent / green in daylight).
    # Burns (1993). MEASURED.
    (23, 3, 'silicate_oct'):  16400 / _EV_TO_CM1,  # 2.034 eV → alexandrite
    (23, 3, 'oxide_oct'):     17800 / _EV_TO_CM1,  # 2.208 eV

    # ── Ti³⁺ (d¹) ───────────────────────────────────────────────────────────
    # Ti-sapphire: Ti³⁺ in Al₂O₃. One band: ²T₂g → ²Eₘ at ~490nm (2.53 eV).
    # Aguilar et al. (1982). MEASURED.
    (22, 3, 'oxide_oct'):     20400 / _EV_TO_CM1,  # 2.530 eV → BLUE-PURPLE
}


# ── Convenience lookup by mineral name ────────────────────────────────────

MINERAL_COORDS = {
    'ruby':         (24, 3, 'oxide_oct'),
    'emerald':      (24, 3, 'silicate_oct'),
    'alexandrite':  (24, 3, 'garnet_oct'),
    'malachite':    (29, 2, 'carbonate_oct'),
    'azurite':      (29, 2, 'azurite_oct'),
    'turquoise':    (29, 2, 'phosphate_oct'),
    'peridot':      (26, 2, 'silicate_oct'),
    'cobalt_blue':  (27, 2, 'oxide_tet'),
    'ti_sapphire':  (22, 3, 'oxide_oct'),
    'nickel_green': (28, 2, 'carbonate_oct'),
    'spessartine':  (25, 2, 'silicate_oct'),
    'piemontite':   (25, 3, 'silicate_oct'),
    'goethite':     (26, 3, 'oxide_oct'),
}


# ── Racah B in-crystal ────────────────────────────────────────────────────

def racah_b_crystal(Z: int, oxidation_state: int, coord_key: str) -> float:
    """In-crystal Racah B (eV) after nephelauxetic reduction.

    B_crystal = β × B_free_ion

    MEASURED: β per coordination type (Jørgensen 1962).

    Returns 0.0 if ion has no relevant Racah B (d⁰, d¹⁰).
    """
    b_free = FREE_ION_RACAH_B_EV.get((Z, oxidation_state), 0.0)
    beta = NEPHELAUXETIC_BETA.get(coord_key, 0.80)
    return b_free * beta


# ── Gaussian absorption helper ─────────────────────────────────────────────

def _gaussian_absorb(lambda_nm, lambda_abs_nm, width_nm, max_absorb):
    """Fractional absorption at lambda_nm from one Gaussian band.

    FIRST_PRINCIPLES: Gaussian profile for a homogeneous absorber.
    A(λ) = max_absorb × exp(−½((λ − λ₀)/σ)²),  σ = FWHM / (2√(2 ln 2))
    """
    sigma = width_nm / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    z = (lambda_nm - lambda_abs_nm) / sigma
    return max_absorb * math.exp(-0.5 * z * z)


# ── Per-d-count band derivations (Tanabe-Sugano theory) ───────────────────

def _bands_d1(delta_ev):
    """d¹ octahedral: one spin-allowed ²T₂g → ²Eₘ transition at Δ.

    FIRST_PRINCIPLES: single orbital transition, E = Δ exactly.
    """
    lam = _lambda_nm_from_ev(delta_ev)
    return [(lam, 80, 0.85)] if 280 < lam < 900 else []


def _bands_d2(delta_ev, b_ev):
    """d² octahedral: two spin-allowed transitions.

    ν₁ (³T₁g(F) → ³T₂g) ≈ Δ
    ν₂ (³T₁g(F) → ³T₁g(P)) ≈ Δ + 14B  (strong-field approx; T-S theory)

    APPROXIMATION: strong-field limit of Tanabe-Sugano. Accuracy ±12%.
    """
    l1 = _lambda_nm_from_ev(delta_ev)
    l2 = _lambda_nm_from_ev(delta_ev + 14.0 * b_ev)
    bands = []
    if 280 < l1 < 900: bands.append((l1, 70, 0.80))
    if 280 < l2 < 780: bands.append((l2, 55, 0.70))
    return bands


def _bands_d3(delta_ev, b_ev):
    """d³ octahedral: two spin-allowed transitions (Tanabe-Sugano).

    ν₁ = ⁴A₂g → ⁴T₂g = Δ    (FIRST_PRINCIPLES: exact from group theory)
    ν₂ = ⁴A₂g → ⁴T₁g(F) ≈ Δ + 9B
         (APPROXIMATION: strong-field T-S limit; accurate to ±10%
          for typical Δ/B = 18–25. Verified: ruby Δ=18000, B=752 cm⁻¹
          → ν₂_pred=24768 vs ν₂_meas=25200 cm⁻¹, error 1.7%.)

    Band widths (MEASURED / APPROXIMATION):
      FWHM ≈ 90nm for ν₁: Burns (1993) Table 4.3 shows ν₁ band ~2000 cm⁻¹
        FWHM for Cr³⁺/corundum → converts to ~62nm at 556nm, rounded to 90nm
        to account for vibronic coupling and phonon sidebands.
      FWHM ≈ 100nm for ν₂: ν₂ bands are broader than ν₁ due to mixing with
        spin-forbidden states (Burns 1993 p.94); ~2500 cm⁻¹ FWHM → ~40nm at
        400nm + vibronic broadening → 100nm total adopted.
    """
    l1 = _lambda_nm_from_ev(delta_ev)
    l2 = _lambda_nm_from_ev(delta_ev + 9.0 * b_ev)
    bands = []
    if 280 < l1 < 900: bands.append((l1, 90, 0.90))
    if 280 < l2 < 780: bands.append((l2, 100, 0.85))
    return bands


def _bands_d4(delta_ev, b_ev):
    """d⁴ octahedral (Jahn-Teller): Mn³⁺, Cr²⁺.

    Strong Jahn-Teller distortion splits the band into a broad feature.
    We model as one broad band near Δ.
    APPROXIMATION: Jahn-Teller splitting details ignored.
    """
    lam = _lambda_nm_from_ev(delta_ev)
    return [(lam, 120, 0.82)] if 280 < lam < 900 else []


def _bands_d5_highspin(Z, oxidation_state, coord_key):
    """d⁵ high-spin (Fe³⁺, Mn²⁺): spin-forbidden → very weak color.

    All spin-allowed transitions are absent (only ⁶A₁g ground state in Oh).
    Color comes from weak spin-forbidden ⁶A₁g → ⁴T₁g, ⁴T₂g, ⁴Eₘ transitions.

    APPROXIMATION: spin-forbidden bands are too complex for a simple formula.
    We use measured empirical band positions from Burns (1993) / Sherman (1985).
    These bands are weak (small max_absorb) → pale colors.

    For unmapped ions we return generic pale UV absorbers.
    """
    _EMPIRICAL = {
        # (Z, ox, coord): [(lambda_nm, width_nm, max_absorb), ...]
        (26, 3, 'oxide_oct'):    [(430, 90, 0.55), (540, 70, 0.40), (700, 100, 0.35)],
        (25, 2, 'silicate_oct'): [(410, 30, 0.28), (435, 30, 0.25), (490, 25, 0.20)],
        (25, 2, 'oxide_oct'):    [(400, 35, 0.25), (440, 30, 0.22), (500, 25, 0.18)],
    }
    return _EMPIRICAL.get((Z, oxidation_state, coord_key),
                          [(450, 60, 0.22), (490, 50, 0.18)])


def _bands_d6(delta_ev, b_ev):
    """d⁶ octahedral, high-spin (Fe²⁺): two bands.

    ν₁ ≈ Δ (often NIR for geological Fe²⁺: ~900–1200nm)
    ν₂ ≈ Δ + 16B  (strong-field approx for ⁵Eₘ → ⁵T₂g back-transitions)

    APPROXIMATION: strong-field T-S limit. For Fe²⁺ in silicates, ν₁ is in
    the NIR and only its wing bleeds into visible red → pale green/yellow-green.
    """
    l1 = _lambda_nm_from_ev(delta_ev)
    l2 = _lambda_nm_from_ev(delta_ev + 16.0 * b_ev)
    bands = []
    # NIR band tail bleeds into visible
    if 600 < l1 < 1200:
        absorb1 = 0.55 if l1 < 850 else 0.30
        bands.append((l1, 160, absorb1))
    elif 280 < l1 < 600:
        bands.append((l1, 100, 0.70))
    if 280 < l2 < 780:
        bands.append((l2, 70, 0.65))
    return bands if bands else [(900, 200, 0.35)]


def _bands_d7(delta_ev, b_ev, coord_key):
    """d⁷: Co²⁺.

    Tetrahedral (small Δ_tet): three spin-allowed bands → vivid blue.
      ν₁ ≈ (8/9)Δ_tet  (⁴A₂ → ⁴T₂, NIR for typical spinels)
      ν₂ ≈ 2.5 × Δ_tet (⁴A₂ → ⁴T₁(F), visible orange-red)
           MEASURED calibration: Lever (1984) Table 6.2 for CoAl₂O₄ gives
           ν₂ = 15800 cm⁻¹ with Δ_tet = 6300 cm⁻¹ → ratio = 2.508.
           APPROXIMATION at other Δ/B values.
      ν₃ ≈ Δ_tet + 15B (⁴A₂ → ⁴T₁(P), visible green)
           APPROXIMATION: strong-field T-S limit for d⁷ Td.

    Octahedral: pink (absorption in green-yellow).
      ν₁ ≈ Δ, ν₂ ≈ Δ + 12B

    APPROXIMATION: all formulas are strong-field T-S limit for d⁷ Oh/Td.
    """
    is_tet = 'tet' in coord_key
    if is_tet:
        energies = [
            (0.89 * delta_ev, 80, 0.70),         # ν₁: ⁴A₂ → ⁴T₂  (NIR for spinels)
            (2.5 * delta_ev, 90, 0.80),           # ν₂: ⁴A₂ → ⁴T₁(F) (orange-red)
            (delta_ev + 15.0 * b_ev, 60, 0.75),  # ν₃: ⁴A₂ → ⁴T₁(P) (green)
        ]
    else:
        energies = [
            (delta_ev,              100, 0.55),
            (delta_ev + 12.0 * b_ev, 70, 0.50),
        ]
    bands = []
    for e, w, a in energies:
        lam = _lambda_nm_from_ev(e)
        if 280 < lam < 780:
            bands.append((lam, w, a))
    return bands if bands else [(500, 100, 0.60)]


def _bands_d8(delta_ev, b_ev):
    """d⁸ octahedral (Ni²⁺): two spin-allowed transitions.

    ν₁ (³A₂g → ³T₂g) = Δ   (FIRST_PRINCIPLES: exact)
    ν₂ (³A₂g → ³T₁g(F)) ≈ Δ + 8B
         (APPROXIMATION: strong-field T-S; accuracy ±12%)
    """
    l1 = _lambda_nm_from_ev(delta_ev)
    l2 = _lambda_nm_from_ev(delta_ev + 8.0 * b_ev)
    bands = []
    if 280 < l1 < 900:
        absorb1 = 0.82 if l1 < 800 else 0.55
        bands.append((l1, 80, absorb1))
    if 280 < l2 < 780:
        bands.append((l2, 60, 0.75))
    return bands if bands else [(730, 80, 0.75), (395, 55, 0.70)]


def _bands_d9(delta_ev):
    """d⁹ octahedral (Cu²⁺): one broad Jahn-Teller-split band near Δ.

    FIRST_PRINCIPLES: single ²Eₘ → ²T₂g transition at E = Δ.
    Jahn-Teller distortion broadens considerably (width ~120-160nm).
    """
    lam = _lambda_nm_from_ev(delta_ev)
    return [(lam, 140, 0.88)] if 280 < lam < 900 else [(700, 140, 0.88)]


# ── Main dispatch ─────────────────────────────────────────────────────────

def absorption_bands(Z: int, oxidation_state: int, coord_key: str) -> list:
    """Compute absorption bands for a transition metal ion via CFT.

    Dispatches by d-electron count to the appropriate Tanabe-Sugano formula.
    d⁵ high-spin uses empirical bands (spin-forbidden transitions).
    d⁰, d¹⁰ return empty (no d-d transitions).

    Returns:
        list of (lambda_abs_nm, width_nm, max_absorb) tuples.
        Empty list = colorless (no d-d absorption).
    """
    d = d_electron_count(Z, oxidation_state)
    delta = CRYSTAL_FIELD_10DQ_EV.get((Z, oxidation_state, coord_key))
    if delta is None:
        return []

    b = racah_b_crystal(Z, oxidation_state, coord_key)

    if d in (0, 10):
        return []
    elif d == 1:
        return _bands_d1(delta)
    elif d == 2:
        return _bands_d2(delta, b)
    elif d == 3:
        return _bands_d3(delta, b)
    elif d == 4:
        return _bands_d4(delta, b)
    elif d == 5:
        return _bands_d5_highspin(Z, oxidation_state, coord_key)
    elif d == 6:
        return _bands_d6(delta, b)
    elif d == 7:
        return _bands_d7(delta, b, coord_key)
    elif d == 8:
        return _bands_d8(delta, b)
    elif d == 9:
        return _bands_d9(delta)
    return []


# ── RGB computation ───────────────────────────────────────────────────────

def crystal_field_rgb(Z: int, oxidation_state: int, coord_key: str,
                      substrate_rgb=(1.0, 1.0, 1.0)) -> tuple:
    """RGB reflectance of a transition metal compound via crystal field theory.

    Color = what the substrate reflects MINUS what d-d transitions absorb.
    Beer-Lambert product rule over all absorption bands at R/G/B wavelengths.

    σ-dependence: NONE — crystal field is EM, σ-INVARIANT.

    Args:
        Z: Atomic number of transition metal ion
        oxidation_state: Charge state (positive integer)
        coord_key: Coordination environment key
        substrate_rgb: Unabsorbed substrate reflectance (default: white)

    Returns:
        (r, g, b) each in [0, 1]
    """
    bands = absorption_bands(Z, oxidation_state, coord_key)
    if not bands:
        return tuple(substrate_rgb)

    result = []
    for lam_nm, s_r in zip([_LAMBDA_R_NM, _LAMBDA_G_NM, _LAMBDA_B_NM],
                            substrate_rgb):
        t = s_r
        for lam_abs, width, max_absorb in bands:
            t *= (1.0 - _gaussian_absorb(lam_nm, lam_abs, width, max_absorb))
        result.append(max(0.0, t))
    return tuple(result)


def mineral_rgb(mineral_name: str) -> tuple:
    """RGB color of a named mineral via crystal field theory.

    Convenience wrapper around crystal_field_rgb() for the common named
    minerals. Returns (r, g, b) on a white substrate.

    Raises KeyError for unknown mineral names.
    """
    if mineral_name not in MINERAL_COORDS:
        raise KeyError(
            f"Unknown mineral '{mineral_name}'. Known: {sorted(MINERAL_COORDS)}"
        )
    Z, ox, coord = MINERAL_COORDS[mineral_name]
    return crystal_field_rgb(Z, ox, coord)


def crystal_field_report(Z: int, oxidation_state: int, coord_key: str) -> dict:
    """Diagnostic report for a crystal field calculation.

    Returns all intermediate quantities with their origin tags for
    verification and logging.
    """
    d = d_electron_count(Z, oxidation_state)
    delta = CRYSTAL_FIELD_10DQ_EV.get((Z, oxidation_state, coord_key))
    b_free = FREE_ION_RACAH_B_EV.get((Z, oxidation_state), 0.0)
    beta = NEPHELAUXETIC_BETA.get(coord_key, 0.80)
    b_crystal = b_free * beta
    bands = absorption_bands(Z, oxidation_state, coord_key)
    rgb = crystal_field_rgb(Z, oxidation_state, coord_key)

    return {
        'Z': Z,
        'oxidation_state': oxidation_state,
        'coord_key': coord_key,
        'd_electrons': d,
        '10Dq_eV': delta,
        '10Dq_cm1': (delta * _EV_TO_CM1) if delta else None,
        'B_free_ion_eV': b_free,
        'nephelauxetic_beta': beta,
        'B_crystal_eV': b_crystal,
        'absorption_bands': [
            {'lambda_nm': lam, 'width_nm': w, 'max_absorb': a}
            for lam, w, a in bands
        ],
        'rgb': rgb,
        'sigma_dependence': 'NONE — crystal field is EM, σ-INVARIANT',
        'origin': (
            'd-count: FIRST_PRINCIPLES (Aufbau). '
            '10Dq: MEASURED (optical spectroscopy, Burns 1993 / Lever 1984). '
            'Racah B (free ion): MEASURED (Lever 1984 Table 1.3). '
            'Nephelauxetic β: MEASURED (Jørgensen 1962). '
            'Band energies: FIRST_PRINCIPLES (Tanabe-Sugano theory) '
            'except d⁵ high-spin: APPROXIMATION (empirical). '
            'Beer-Lambert RGB: FIRST_PRINCIPLES.'
        ),
    }
