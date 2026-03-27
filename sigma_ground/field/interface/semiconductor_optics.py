"""
Semiconductor optical properties — band gap and Fresnel reflectance.

Color in semiconductors originates from two physical mechanisms:

  1. Band-gap cutoff: photons with E > E_g are absorbed in the bulk (Beer-Lambert).
     Band gap from Varshni equation: E_g(T) = E_g0 − αT²/(T+β).

  2. Surface reflectance: at air-semiconductor interface, Fresnel R(n, k).
     Narrow-gap (all visible above-gap): metallic-like response from complex n+ik.
     Wide-gap (gap in visible): below-gap channels reflect as dielectric,
     above-gap channels absorbed by bulk (not reflected back to viewer).

Derivation chain:
  Z (elemental) or key (compound) → Varshni parameters (MEASURED)
  + temperature T → E_g(T) (FIRST_PRINCIPLES: Varshni 1967)
  E_g → λ_edge = hc/E_g (FIRST_PRINCIPLES: photon energy)
  λ vs λ_edge → channel model (FIRST_PRINCIPLES: Beer-Lambert + Fresnel)
  n+ik at R/G/B → R(λ) (FIRST_PRINCIPLES: Fresnel normal incidence)
  R(λ) per channel → RGB color (FIRST_PRINCIPLES)

Three-regime color model:
  Narrow-gap (E_g < E_red ≈ 1.91 eV, λ_edge > 650nm):
    ALL visible channels are above-gap → complex Fresnel(n, k) for all.
    Materials: Si, Ge, GaAs. Appear metallic grey.
  Mid-gap (E_red ≤ E_g ≤ E_UV ≈ 3.26 eV, λ_edge 380-650nm):
    Sub-gap channels: dielectric Fresnel(n, 0) — reflected.
    Above-gap channels: 0 — absorbed by bulk, not returned to viewer.
    Materials: GaP (amber), CdS (yellow), TiO₂ (white-ish).
  Wide-gap (E_g > E_UV ≈ 3.26 eV, λ_edge < 380nm):
    ALL visible channels are sub-gap → dielectric Fresnel(n, 0) for all.
    Materials: diamond, GaN, ZnO. Appear colorless.

σ-dependence: NONE — all EM.
  Band gap: set by crystal potential (electrostatic → EM → σ-INVARIANT).
  Optical constants n+ik: EM → σ-INVARIANT.
  Fresnel: EM boundary conditions → σ-INVARIANT.
  Color: EM → σ-INVARIANT.

Origin tags:
  - Varshni parameters: MEASURED (optical absorption, photoluminescence)
    Si, Ge: Bludau et al. (1974); Ioffe Institute database.
    GaAs, GaP, GaN: Vurgaftman et al. (2001) JAP 89:5815.
    CdS: Bücher et al. (1994); Ioffe database.
    ZnO: Liang et al. (1968); Ioffe database.
    TiO₂ rutile: Tang et al. (1994).
    Diamond: Collins & Williams (1971); Slack & Bartram (1975).
  - Complex refractive index n+ik: MEASURED (ellipsometry / spectrophotometry)
    Si: Green & Keevers (1995); Palik (1985).
    Ge: Palik (1985).
    GaAs, GaP: Aspnes & Studna (1983) Phys Rev B 27:985.
    GaN: Barker & Ilegems (1973); Kawashima et al. (1997).
    CdS: Khawaja & Tomlin (1975); Palik (1985).
    ZnO: Palik (1985).
    TiO₂: Devore (1951); Bond (1965).
    Diamond: Peter (1923); Palik (1985).
  - Fresnel equation: FIRST_PRINCIPLES (Maxwell boundary conditions)
  - Band-gap model (3-regime): FIRST_PRINCIPLES (Beer-Lambert + Fresnel)

□σ = −ξR   (all quantities here: EM, σ-invariant)
"""

import math

# ── Fundamental constants ──────────────────────────────────────────────────
_NM_EV = 1239.84193      # hc/e in nm·eV (exact from SI 2019)

# ── Visible wavelength energies for RGB channel model selection ────────────
# These are the photon energies at the three RGB sampling wavelengths.
_E_RED  = _NM_EV / 650.0   # 1.9075 eV — energy of λ=650nm (L-cone peak, long-wave edge)
_E_UV   = _NM_EV / 380.0   # 3.2627 eV — energy at UV/visible boundary

# ── Visible wavelengths for RGB sampling ──────────────────────────────────
_LAMBDA_R_NM = 650.0   # L-cone peak (CIE 1931)
_LAMBDA_G_NM = 550.0   # M-cone peak
_LAMBDA_B_NM = 450.0   # S-cone peak


# ── Varshni parameters (MEASURED) ─────────────────────────────────────────
#
# E_g(T) = E_g0 − α·T² / (T + β)
#
# Keys:
#   Eg0   : band gap at T=0K (eV)
#   alpha : Varshni α parameter (eV/K)
#   beta  : Varshni β parameter (K) — related to Debye temperature
#   density_kg_m3 : bulk crystal density (for Material factory)
#   Z     : atomic number (elemental semiconductors only; None for compounds)
#   formula : chemical formula string
#
# Sources documented in module docstring.

VARSHNI_PARAMS = {
    'silicon': {
        'Eg0'          : 1.1692,     # eV  (Bludau et al. 1974)
        'alpha'        : 4.73e-4,    # eV/K
        'beta'         : 636.0,      # K
        'density_kg_m3': 2329,
        'Z'            : 14,
        'formula'      : 'Si',
        'origin'       : 'MEASURED: Bludau et al. (1974); Ioffe Institute database',
    },
    'germanium': {
        'Eg0'          : 0.7437,     # eV  (indirect L-valley gap; Ioffe)
        'alpha'        : 4.77e-4,    # eV/K
        'beta'         : 235.0,      # K
        'density_kg_m3': 5323,
        'Z'            : 32,
        'formula'      : 'Ge',
        'origin'       : 'MEASURED: Ioffe Institute database',
    },
    'diamond': {
        'Eg0'          : 5.490,      # eV  (indirect gap; Collins & Williams 1971)
        'alpha'        : 3.68e-4,    # eV/K
        'beta'         : 1156.0,     # K  (very stiff lattice → high β)
        'density_kg_m3': 3515,
        'Z'            : 6,
        'formula'      : 'C (diamond)',
        'origin'       : 'MEASURED: Collins & Williams (1971); Slack & Bartram (1975)',
    },
    'gallium_arsenide': {
        'Eg0'          : 1.519,      # eV  (direct Γ gap; Vurgaftman 2001)
        'alpha'        : 5.405e-4,   # eV/K
        'beta'         : 204.0,      # K
        'density_kg_m3': 5360,
        'Z'            : None,       # compound
        'formula'      : 'GaAs',
        'origin'       : 'MEASURED: Vurgaftman et al. (2001) JAP 89:5815',
    },
    'gallium_phosphide': {
        'Eg0'          : 2.350,      # eV  (indirect gap; Vurgaftman 2001)
        'alpha'        : 6.2e-4,     # eV/K
        'beta'         : 460.0,      # K
        'density_kg_m3': 4138,
        'Z'            : None,
        'formula'      : 'GaP',
        'origin'       : 'MEASURED: Vurgaftman et al. (2001) JAP 89:5815',
    },
    'gallium_nitride': {
        'Eg0'          : 3.510,      # eV  (direct wurtzite; Vurgaftman 2001)
        'alpha'        : 9.09e-4,    # eV/K
        'beta'         : 830.0,      # K
        'density_kg_m3': 6150,
        'Z'            : None,
        'formula'      : 'GaN (wurtzite)',
        'origin'       : 'MEASURED: Vurgaftman et al. (2001) JAP 89:5815',
    },
    'cadmium_sulfide': {
        'Eg0'          : 2.501,      # eV  (direct wurtzite; Bücher et al. 1994)
        'alpha'        : 5.0e-4,     # eV/K
        'beta'         : 201.0,      # K
        'density_kg_m3': 4820,
        'Z'            : None,
        'formula'      : 'CdS (wurtzite)',
        'origin'       : 'MEASURED: Bücher et al. (1994); Ioffe Institute database',
    },
    'zinc_oxide': {
        'Eg0'          : 3.4376,     # eV  (direct wurtzite; Liang et al. 1968)
        'alpha'        : 7.2e-4,     # eV/K
        'beta'         : 1028.0,     # K
        'density_kg_m3': 5600,
        'Z'            : None,
        'formula'      : 'ZnO (wurtzite)',
        'origin'       : 'MEASURED: Liang et al. (1968); Ioffe Institute database',
    },
    'titanium_dioxide': {
        'Eg0'          : 3.10,       # eV  (rutile direct gap; Tang et al. 1994)
        'alpha'        : 2.0e-4,     # eV/K
        'beta'         : 200.0,      # K  (approximate; TiO₂ Varshni less characterized)
        'density_kg_m3': 4250,
        'Z'            : None,
        'formula'      : 'TiO₂ (rutile)',
        'origin'       : 'MEASURED: Tang et al. (1994); approximate Varshni fit',
    },
}

# ── Z → key mapping for elemental semiconductors ──────────────────────────
Z_TO_SEMICONDUCTOR = {
    params['Z']: key
    for key, params in VARSHNI_PARAMS.items()
    if params['Z'] is not None
}
# Z=6 → diamond (carbon in cubic diamond polymorph)
# Z=14 → silicon
# Z=32 → germanium


# ── Measured complex refractive index n+ik (MEASURED) ─────────────────────
#
# Tabulated at RGB peak wavelengths:
#   650nm (λ_R, L-cone peak), 550nm (λ_G, M-cone peak), 450nm (λ_B, S-cone peak)
#
# For sub-gap wavelengths (E_photon < E_g): k≈0, only n is relevant.
# For above-gap (E_photon > E_g) in narrow-gap materials: both n and k large.
#
# Sources documented in module docstring.
# σ-dependence: NONE — optical constants are purely electromagnetic.

SEMICONDUCTOR_NK = {
    # Silicon — Palik (1985); Green & Keevers (1995)
    # All visible is above Si band gap (1.12eV, λ_edge≈1107nm).
    # Absorbing throughout: n is large (4-5), k small but nonzero.
    'silicon': {
        650e-9: (3.846, 0.017),
        550e-9: (4.084, 0.033),
        450e-9: (4.587, 0.076),
    },
    # Germanium — Palik (1985)
    # Band gap 0.66eV (λ_edge≈1880nm). All visible above gap.
    # High n and k → high metallic reflectance (~55%).
    'germanium': {
        650e-9: (5.590, 2.190),
        550e-9: (5.082, 2.912),
        450e-9: (4.660, 3.396),
    },
    # Diamond — Peter (1923); Palik (1985)
    # Band gap 5.47eV (λ_edge≈227nm). All visible sub-gap.
    # k≈0 throughout visible; near-constant n≈2.42 → colorless.
    'diamond': {
        650e-9: (2.409, 0.000),
        550e-9: (2.426, 0.000),
        450e-9: (2.447, 0.000),
    },
    # GaAs — Aspnes & Studna (1983) Phys Rev B 27:985
    # Band gap 1.42eV (λ_edge≈873nm). All visible above gap.
    # Large k above band edge → metallic-like grey.
    'gallium_arsenide': {
        650e-9: (3.856, 0.196),
        550e-9: (4.333, 1.666),
        450e-9: (3.850, 2.540),
    },
    # GaP — Aspnes & Studna (1983)
    # Band gap 2.28eV (λ_edge≈544nm). 650nm and 550nm sub-gap (transparent);
    # 450nm above gap (absorbing). → Amber/orange appearance.
    'gallium_phosphide': {
        650e-9: (3.308, 0.000),
        550e-9: (3.570, 0.010),
        450e-9: (3.836, 1.359),
    },
    # GaN — Barker & Ilegems (1973); Kawashima et al. (1997)
    # Band gap 3.44eV (λ_edge≈360nm). All visible sub-gap.
    # Wurtzite; n increases toward UV end.
    'gallium_nitride': {
        650e-9: (2.350, 0.000),
        550e-9: (2.400, 0.000),
        450e-9: (2.500, 0.000),
    },
    # CdS — Khawaja & Tomlin (1975); Palik (1985)
    # Band gap ~2.41eV (λ_edge≈515nm). Red and green sub-gap; blue above-gap.
    # → Yellow appearance (absorbs blue).
    'cadmium_sulfide': {
        650e-9: (2.529, 0.000),
        550e-9: (2.680, 0.000),
        450e-9: (2.750, 0.600),
    },
    # ZnO — Palik (1985)
    # Band gap 3.37eV (λ_edge≈368nm). All visible sub-gap.
    # n≈2.0 → R≈11% → appears white (white pigment).
    'zinc_oxide': {
        650e-9: (1.955, 0.000),
        550e-9: (2.017, 0.000),
        450e-9: (2.094, 0.000),
    },
    # TiO₂ rutile — Devore (1951); Bond (1965)
    # Band gap ~3.06eV (λ_edge≈406nm). All visible sub-gap.
    # Very high n (2.7-3.0 in visible) → R≈22-25% → bright white pigment.
    'titanium_dioxide': {
        650e-9: (2.748, 0.000),
        550e-9: (2.843, 0.000),
        450e-9: (3.050, 0.000),
    },
}


# ── Fresnel reflectance ────────────────────────────────────────────────────

def _fresnel_r(n: float, k: float) -> float:
    """Normal-incidence reflectance from complex refractive index n + ik.

    FIRST_PRINCIPLES (Maxwell boundary conditions):
      R = |(ñ − 1) / (ñ + 1)|²  where ñ = n + ik
        = ((n−1)² + k²) / ((n+1)² + k²)

    Exact for planar air-semiconductor surface at normal incidence.
    n=1.5, k=0 → R=0.04 (crown glass, exactly).
    """
    return ((n - 1.0)**2 + k**2) / ((n + 1.0)**2 + k**2)


# ── Varshni band gap ───────────────────────────────────────────────────────

def band_gap_ev(key: str, T: float = 300.0) -> float:
    """Band gap energy E_g in eV at temperature T (Kelvin).

    FIRST_PRINCIPLES (Varshni 1967):
      E_g(T) = E_g0 − α·T² / (T + β)

    Physical meaning:
      α: strength of electron-phonon coupling to lattice expansion
      β: related to Debye temperature — governs low-T saturation

    At T=0: E_g = E_g0 (no phonon contribution → maximum gap).
    At finite T: gap shrinks as lattice thermally expands and softens.

    Parameters
    ----------
    key : str
        Material key from VARSHNI_PARAMS.
    T : float
        Temperature in Kelvin (default 300 K = room temperature).

    Returns
    -------
    float
        Band gap in eV.
    """
    params = VARSHNI_PARAMS[key]
    Eg0   = params['Eg0']
    alpha = params['alpha']
    beta  = params['beta']
    return Eg0 - alpha * T**2 / (T + beta)


def band_edge_nm(key: str, T: float = 300.0) -> float:
    """Band edge wavelength λ_edge in nm at temperature T.

    FIRST_PRINCIPLES:
      λ_edge = hc / E_g = 1239.84193 nm·eV / E_g(eV)

    Photons with λ < λ_edge have E > E_g and are absorbed.
    Photons with λ > λ_edge have E < E_g and are transmitted (sub-gap).

    Parameters
    ----------
    key : str
        Material key from VARSHNI_PARAMS.
    T : float
        Temperature in Kelvin.

    Returns
    -------
    float
        Band edge wavelength in nm.
    """
    eg = band_gap_ev(key, T)
    return _NM_EV / eg


# ── Per-channel reflectance model ─────────────────────────────────────────

def _channel_r(n: float, k: float, e_photon_ev: float, e_gap_ev: float) -> float:
    """Effective reflectance for one color channel of a semiconductor.

    Three-regime model based on the relationship between photon energy and
    band gap:

    Regime A — Narrow gap (E_g < E_red ≈ 1.91 eV):
      E_g is below red light energy → ALL visible channels are above-gap.
      The semiconductor is opaque to all visible light.
      Surface reflectance comes from complex n+ik → metallic-like.
      R = Fresnel(n, k)

    Regime B — Mid gap (E_red ≤ E_g ≤ E_UV ≈ 3.26 eV):
      Gap falls within the visible range.
      Sub-gap channels (E_photon < E_g): transparent dielectric → Fresnel(n, 0)
      Above-gap channels (E_photon ≥ E_g): absorbed in bulk → not returned
        to viewer → R = 0 (channel contributes nothing to reflected color)

    Regime C — Wide gap (E_g > E_UV):
      E_g is above UV edge → ALL visible channels are sub-gap.
      Transparent dielectric across full visible → Fresnel(n, 0) for all.

    Parameters
    ----------
    n, k : float
        Measured refractive index and extinction coefficient at this wavelength.
    e_photon_ev : float
        Photon energy in eV (= hc/λ = 1239.84/λ_nm).
    e_gap_ev : float
        Band gap energy in eV at the current temperature.

    Returns
    -------
    float
        Reflectance in [0, 1].
    """
    if e_gap_ev < _E_RED:
        # Regime A: narrow gap — all visible above-gap → metallic response
        return _fresnel_r(n, k)
    elif e_photon_ev >= e_gap_ev:
        # Regime B/C above-gap: bulk absorbs photon → zero reflected contribution
        return 0.0
    else:
        # Sub-gap (Regime B or C): dielectric — use real n only (k≈0 below gap)
        return _fresnel_r(n, 0.0)


# ── Main color function ────────────────────────────────────────────────────

def semiconductor_rgb(key: str, T: float = 300.0):
    """RGB reflectance color of a semiconductor surface at temperature T.

    Full pipeline:
      key → Varshni params → E_g(T) (MEASURED + FIRST_PRINCIPLES)
      key → n+ik at R/G/B (MEASURED: Palik, Aspnes, etc.)
      For each channel: three-regime model → R (FIRST_PRINCIPLES)
      → (r, g, b) tuple ∈ [0, 1]

    σ-dependence: NONE — all EM → σ-INVARIANT.

    Parameters
    ----------
    key : str
        Material key from SEMICONDUCTOR_NK.
    T : float
        Temperature in Kelvin (default 300 K).

    Returns
    -------
    tuple of float
        (r, g, b) reflectance at 650nm, 550nm, 450nm. All ∈ [0, 1].
    """
    e_gap = band_gap_ev(key, T)
    nk    = SEMICONDUCTOR_NK[key]

    result = []
    for lam_m, lam_nm in [
        (650e-9, _LAMBDA_R_NM),
        (550e-9, _LAMBDA_G_NM),
        (450e-9, _LAMBDA_B_NM),
    ]:
        n, k = nk[lam_m]
        e_photon = _NM_EV / lam_nm   # eV
        r_ch = _channel_r(n, k, e_photon, e_gap)
        result.append(max(0.0, min(1.0, r_ch)))

    return tuple(result)


def semiconductor_rgb_from_z(Z: int, T: float = 300.0):
    """RGB color for an elemental semiconductor from atomic number Z.

    Looks up the semiconductor material key via Z_TO_SEMICONDUCTOR, then
    delegates to semiconductor_rgb().

    Supported Z: 6 (diamond), 14 (silicon), 32 (germanium).

    Parameters
    ----------
    Z : int
        Atomic number.
    T : float
        Temperature in Kelvin.

    Returns
    -------
    tuple of float
        (r, g, b) reflectance.

    Raises
    ------
    KeyError
        If Z is not in Z_TO_SEMICONDUCTOR.
    """
    key = Z_TO_SEMICONDUCTOR[Z]   # KeyError if not found — intentional
    return semiconductor_rgb(key, T)


# ── Diagnostic report ─────────────────────────────────────────────────────

def semiconductor_report(key: str, T: float = 300.0) -> dict:
    """Diagnostic report for a semiconductor's optical properties.

    Returns a dict containing:
      material, band_gap_ev, band_edge_nm, rgb_tuple, model,
      and origin tags for provenance.

    σ-INVARIANT: color is EM.

    Parameters
    ----------
    key : str
        Material key.
    T : float
        Temperature in Kelvin.

    Returns
    -------
    dict
        Diagnostic fields with provenance tags.
    """
    params   = VARSHNI_PARAMS[key]
    eg       = band_gap_ev(key, T)
    lam_edge = band_edge_nm(key, T)
    r, g, b  = semiconductor_rgb(key, T)

    # Determine which color model was applied
    if eg < _E_RED:
        model = 'A: narrow-gap metallic (E_g < E_red; all visible above-gap)'
    elif any((_NM_EV / lam_nm) >= eg
             for lam_nm in [_LAMBDA_R_NM, _LAMBDA_G_NM, _LAMBDA_B_NM]):
        model = 'B: mid-gap visible cutoff (sub-gap channels reflected, above-gap channels absorbed)'
    else:
        model = 'C: wide-gap dielectric (E_g > E_UV; all visible sub-gap → transparent)'

    origin = (
        f"E_g(T): FIRST_PRINCIPLES (Varshni 1967) + MEASURED params "
        f"({params['origin']}). "
        f"n+ik: MEASURED (Palik / Aspnes — see module docstring). "
        f"Fresnel: FIRST_PRINCIPLES (Maxwell boundary conditions). "
        f"Band-gap color model: FIRST_PRINCIPLES (Beer-Lambert + Fresnel, 3-regime). "
        f"σ-INVARIANT: band gap is EM (electrostatic crystal potential); "
        f"optical constants n+ik are EM; Fresnel is EM. □σ = −ξR."
    )

    return {
        'material'     : key,
        'formula'      : params['formula'],
        'T_K'          : T,
        'band_gap_ev'  : eg,
        'band_edge_nm' : lam_edge,
        'rgb_tuple'    : (r, g, b),
        'R_red_650nm'  : r,
        'R_green_550nm': g,
        'R_blue_450nm' : b,
        'model'        : model,
        'Eg0_eV'       : params['Eg0'],
        'alpha_eV_K'   : params['alpha'],
        'beta_K'       : params['beta'],
        'density_kg_m3': params['density_kg_m3'],
        'origin'       : origin,
    }
