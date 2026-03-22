"""
Physics-derived materials for the Entangler renderer.

This module bridges local_library (physics) → Material (renderer).

Every material returned here has:
  - color derived from optical physics (not hand-painted)
  - density from measured crystal structure
  - Z, A from actual atomic composition
  - reflectance from Drude/Fresnel specular fraction
  - roughness from thermal surface physics (texture.py)

The rendering is a side-effect of the physics.

σ-dependence:
  color: INVARIANT (EM)
  density: scales with σ via material.density_at_sigma(σ)
  reflectance, roughness: INVARIANT (EM bonds set crystal structure)

□σ = −ξR
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from ..geometry.primitives import Vec3
from .material import Material

try:
    from local_library.interface.optics import (
        metal_rgb, metal_reflectance, plasma_frequency, drude_scattering_rate,
        ORGANIC_SPECTRA, DYE_DATABASE, dye_transmission_rgb, organic_rgb,
        metal_report,
        # Atom-sourced pipeline — no string key in the chain
        metal_rgb_from_atom, electron_density_from_atom,
        plasma_frequency_from_atom, drude_scattering_rate_from_atom,
        CRYSTAL_DENSITY_BY_Z, VALENCE_ELECTRONS_BY_Z,
        # Dielectric / transparency pipeline
        cauchy_n, dielectric_opacity, dielectric_color_rgb,
        dielectric_surface_reflectance, CAUCHY_COEFFICIENTS, DIELECTRIC_ABSORPTION,
        LAMBDA_G,
    )
    from local_library.interface.texture import (
        microfacet_roughness, specular_fraction,
    )
    from local_library.interface.surface import MATERIALS as SURFACE_MATERIALS
    HAS_PHYSICS = True
except ImportError:
    HAS_PHYSICS = False

# ── New physics modules — crystal field, semiconductor, thermal emission ───
# Imported separately: each can be absent without breaking the metal pipeline.

try:
    from local_library.interface.crystal_field import (
        mineral_rgb, crystal_field_report, MINERAL_COORDS,
    )
    HAS_CRYSTAL_FIELD = True
except ImportError:
    HAS_CRYSTAL_FIELD = False

try:
    from local_library.interface.semiconductor_optics import (
        semiconductor_rgb, semiconductor_rgb_from_z,
        semiconductor_report as _semi_report,
        VARSHNI_PARAMS, Z_TO_SEMICONDUCTOR,
    )
    HAS_SEMICONDUCTOR = True
except ImportError:
    HAS_SEMICONDUCTOR = False

try:
    from local_library.interface.thermal_emission import (
        thermal_emission_rgb, thermal_emission_report as _thermal_report,
        is_visibly_glowing, THERMAL_EMISSION_MATERIALS,
    )
    HAS_THERMAL_EMISSION = True
except ImportError:
    HAS_THERMAL_EMISSION = False

try:
    from local_library.interface.mechanical import bulk_modulus as _bulk_modulus
    from local_library.interface.fluid import (
        liquid_viscosity, liquid_properties, KNOWN_LIQUIDS,
    )
    from local_library.interface.gas import gas_viscosity
    HAS_DYNAMICS = True
except ImportError:
    HAS_DYNAMICS = False

# Measured restitution coefficients per metal.
# MEASURED — elastic wave theory requires the full phonon spectrum.
# Source: Cross (1999) "The bounce of a ball" Am. J. Phys. 67(3):222-227;
#         Raman (1920) Phys. Rev. 15(4):277 (steel on steel, 0.68-0.74).
_RESTITUTION = {
    'aluminum': 0.65,
    'copper':   0.60,
    'iron':     0.70,
    'gold':     0.55,
    'tungsten': 0.68,
    'nickel':   0.64,
    'titanium': 0.60,
    'silicon':  0.90,  # very elastic; Cross (2006) Am.J.Phys. 74:882
}


def _vec3(rgb):
    return Vec3(rgb[0], rgb[1], rgb[2])


# ── Per-channel Beer-Lambert absorption coefficients (1/inch) ─────────────
#
# Used by VolumeNode: opacity_i = 1 - exp(-alpha_i × dl)
# σ-INVARIANT: absorption is EM (Coulomb), independent of Λ_QCD.
#
# Representative wavelengths: R=700nm, G=550nm, B=450nm (CIE cone peaks).
#
# METALS: alpha = 4πk/λ from imaginary refractive index k.
#   Sources: Palik (1985) "Handbook of Optical Constants of Solids",
#            Rakić (1998) "Optical properties of metallic films",
#            Applied Optics 37(22):5271-5283.
#   Note: ALL metals have alpha >> 1e5 /inch → volume nodes always opaque.
#   Skin depth δ = λ/(4πk) ≈ 6-8 nm. The cascade terminates after 1 node
#   at ANY reasonable dl (dl >> δ). Beer-Lambert = skin depth physics.
#
# GEMS: alpha from optical spectroscopy measurements of gem-quality crystals.
#   Typically expressed in cm⁻¹ in the literature; converted to /inch (* 2.54).
#   Sources cited per-mineral below.

_M_PER_INCH = 0.0254

def _k_to_alpha_per_inch(k, lam_nm):
    """Beer-Lambert alpha from imaginary refractive index k.

    alpha = 4πk/λ  (in /m), converted to /inch.

    FIRST_PRINCIPLES: k is the imaginary part of the complex refractive index
    ñ = n + ik. The Beer-Lambert extinction coefficient α = 4πk/λ is exact
    from Maxwell's equations (absorption term in plane-wave propagation).

    Source: Born & Wolf (1999) "Principles of Optics" §1.1.3 eq.(1.43).
    """
    import math
    alpha_m = 4.0 * math.pi * k / (lam_nm * 1e-9)
    return alpha_m * _M_PER_INCH   # /m × m/inch → /inch


# Metal absorption coefficients derived from Drude k values.
# k values from Rakić (1998) Table 1 (Al) and Palik (1985) Vol.1 (Cu, Au, Fe).
# Wavelengths: R=700nm, G=550nm, B=450nm.
_METAL_ALPHA_RGB = {
    # Aluminum: Rakić (1998) Drude-Lorentz fit.  k_R=7.14, k_G=5.85, k_B=4.97
    'aluminum': (
        _k_to_alpha_per_inch(7.14, 700.0),   # 3.256e6 /inch
        _k_to_alpha_per_inch(5.85, 550.0),   # 3.395e6 /inch
        _k_to_alpha_per_inch(4.97, 450.0),   # 3.525e6 /inch
    ),
    # Copper: Palik (1985) Vol.1 pp.286-295.  k_R=3.42, k_G=2.55, k_B=1.96
    'copper': (
        _k_to_alpha_per_inch(3.42, 700.0),   # 1.559e6 /inch
        _k_to_alpha_per_inch(2.55, 550.0),   # 1.480e6 /inch
        _k_to_alpha_per_inch(1.96, 450.0),   # 1.390e6 /inch
    ),
    # Gold: Palik (1985) Vol.1.  k_R=2.75, k_G=2.03, k_B=1.74
    'gold': (
        _k_to_alpha_per_inch(2.75, 700.0),   # 1.254e6 /inch
        _k_to_alpha_per_inch(2.03, 550.0),   # 1.178e6 /inch
        _k_to_alpha_per_inch(1.74, 450.0),   # 1.234e6 /inch
    ),
    # Iron: Palik (1985) Vol.1.  k_R=4.0, k_G=3.5, k_B=3.0
    'iron': (
        _k_to_alpha_per_inch(4.0,  700.0),   # 1.824e6 /inch
        _k_to_alpha_per_inch(3.5,  550.0),   # 2.031e6 /inch
        _k_to_alpha_per_inch(3.0,  450.0),   # 2.128e6 /inch
    ),
}

# Gem / mineral absorption coefficients from published spectroscopy.
# All values in /inch (= measured cm⁻¹ × 2.54).
# These are the PHYSICAL Beer-Lambert alpha for volumetric rendering.
# The crystal_field_rgb function computes COLOR via Beer-Lambert (for surface),
# but these alpha values are needed for the volumetric fill compositor.
_MINERAL_ALPHA_RGB = {
    # Ruby (Cr³⁺ in Al₂O₃ corundum), 0.5 wt% Cr₂O₃, gem-quality.
    #   Source: Waychunas (1988) Am. Mineralogist 73:916–934, Fig. 3.
    #   Measured absorption coefficients: green peak ~3 cm⁻¹ (ν₁ band 18200 cm⁻¹)
    #   Red: ~0.1 cm⁻¹ (transparent — this is why rubies transmit red).
    #   Blue: ~1.2 cm⁻¹ (ν₂ band 25200 cm⁻¹, ~403nm).
    'ruby': (0.10 * 2.54, 3.0 * 2.54, 1.2 * 2.54),

    # Emerald (Cr³⁺ in Be₃Al₂Si₆O₁₈ beryl), Colombian gem-quality.
    #   Source: Smith (1963) Am. Mineralogist 48:186–192;
    #           Deer, Howie, Zussman (1992) "Rock-forming minerals" Vol. 1B.
    #   Cr³⁺ in trigonal field: ν₁ at ~16400 cm⁻¹ (~610nm, red),
    #   ν₂ at ~23100 cm⁻¹ (~433nm, blue). Green transmitted.
    'emerald': (1.5 * 2.54, 0.10 * 2.54, 0.8 * 2.54),

    # Alexandrite (Cr³⁺ in BeAl₂O₄ chrysoberyl) — color-change gem.
    #   Source: Schmetzer & Gübelin (1980) Neues Jb. Miner. Mh. 1980:200–212.
    'alexandrite': (0.5 * 2.54, 2.0 * 2.54, 1.0 * 2.54),

    # Cobalt blue (Co²⁺ in CoAl₂O₄ spinel).
    #   Source: Lever (1984) "Inorganic Electronic Spectroscopy" Table 6.2.
    #   Absorbs red (~635nm) and green (~566nm). Blue transmitted.
    'cobalt_blue': (3.0 * 2.54, 2.5 * 2.54, 0.3 * 2.54),

    # Malachite (Cu²⁺ in Cu₂CO₃(OH)₂).
    #   Source: Gaines et al. (1997) "Dana's New Mineralogy".
    #   Strong red absorption; green transmitted.
    'malachite': (2.5 * 2.54, 0.3 * 2.54, 1.8 * 2.54),

    # Azurite (Cu²⁺ in Cu₃(CO₃)₂(OH)₂) — deep blue.
    #   Source: Gaines et al. (1997). Absorbs red and green.
    'azurite': (3.0 * 2.54, 2.0 * 2.54, 0.2 * 2.54),

    # Peridot (Fe²⁺ in (Mg,Fe)₂SiO₄ olivine).
    #   Source: Burns (1993) "Mineralogical Applications of Crystal Field Theory"
    #   Table 4.5. Fe²⁺ absorbs red and blue; green transmitted.
    'peridot': (1.5 * 2.54, 0.1 * 2.54, 1.2 * 2.54),

    # Ti-sapphire (Ti³⁺ in Al₂O₃) — blue/pink.
    #   Source: Moulton (1986) J. Opt. Soc. Am. B 3:125–133. d¹ single band.
    'ti_sapphire': (0.2 * 2.54, 1.5 * 2.54, 0.1 * 2.54),

    # Diamond Type IIa — nearly colorless.
    #   Source: Berman (1965); Davies (1994) "Properties and Growth of Diamond".
    #   < 0.002 cm⁻¹ in visible range for pure IIa.
    'diamond': (0.001 * 2.54, 0.001 * 2.54, 0.002 * 2.54),
}


# ── Metal materials from Drude + Fresnel ──────────────────────────────────

def aluminum(sigma=0.0, T=300.0):
    """Polished aluminum — the beer-can material.

    Color from Drude free-electron model (FIRST_PRINCIPLES).
    Al has 3 valence electrons, high plasma frequency (~15 eV),
    very flat reflectance across visible → silver-white.

    Reflectance: specular fraction from thermal roughness (FIRST_PRINCIPLES).
    Roughness: Beckmann α from step height and thermal fluctuations.

    This is what Skippy's body is made of.
    """
    if not HAS_PHYSICS:
        ar, ag, ab = _METAL_ALPHA_RGB['aluminum']
        return Material(
            name='Aluminum (fallback)',
            color=Vec3(0.95, 0.95, 0.96),
            reflectance=0.92, roughness=0.03,
            density_kg_m3=2700, mean_Z=13, mean_A=27,
            composition='Al (FCC)',
            alpha_r=ar, alpha_g=ag, alpha_b=ab,
        )

    r, g, b = metal_rgb('aluminum')
    refl = specular_fraction('aluminum', T=T)
    rough = microfacet_roughness('aluminum', T=T)
    mat = SURFACE_MATERIALS['aluminum']

    ar, ag, ab = _METAL_ALPHA_RGB['aluminum']
    K = _bulk_modulus('aluminum', sigma) if HAS_DYNAMICS else 76e9
    return Material(
        name='Aluminum',
        color=Vec3(r, g, b),
        reflectance=float(refl),
        roughness=float(rough),
        density_kg_m3=mat['density_kg_m3'],
        mean_Z=mat['Z'],
        mean_A=mat['A'],
        composition=mat['composition'],
        alpha_r=ar, alpha_g=ag, alpha_b=ab,
        bulk_modulus_pa=K,
        restitution=_RESTITUTION['aluminum'],
    )


def copper(sigma=0.0, T=300.0):
    """Polished copper — warm orange-pink metal.

    Color from Drude + d-band interband transitions (Rakić 1998 params).
    Cu's d-band edge at ~2.1 eV absorbs blue-green → warm color.
    """
    if not HAS_PHYSICS:
        ar, ag, ab = _METAL_ALPHA_RGB['copper']
        return Material(
            name='Copper (fallback)',
            color=Vec3(0.72, 0.45, 0.20),
            reflectance=0.88, roughness=0.04,
            density_kg_m3=8960, mean_Z=29, mean_A=64,
            composition='Cu (FCC)',
            alpha_r=ar, alpha_g=ag, alpha_b=ab,
        )

    r, g, b = metal_rgb('copper')
    refl = specular_fraction('copper', T=T)
    rough = microfacet_roughness('copper', T=T)
    mat = SURFACE_MATERIALS['copper']

    ar, ag, ab = _METAL_ALPHA_RGB['copper']
    K = _bulk_modulus('copper', sigma) if HAS_DYNAMICS else 140e9
    return Material(
        name='Copper',
        color=Vec3(r, g, b),
        reflectance=float(refl),
        roughness=float(rough),
        density_kg_m3=mat['density_kg_m3'],
        mean_Z=mat['Z'],
        mean_A=mat['A'],
        composition=mat['composition'],
        alpha_r=ar, alpha_g=ag, alpha_b=ab,
        bulk_modulus_pa=K,
        restitution=_RESTITUTION['copper'],
    )


def gold(sigma=0.0, T=300.0):
    """Polished gold — warm yellow metal.

    Color from Drude + d-band. Au d-band onset at ~2.5 eV (≈ 495 nm)
    absorbs blue → gold color. The reason gold is gold.
    """
    if not HAS_PHYSICS:
        ar, ag, ab = _METAL_ALPHA_RGB['gold']
        return Material(
            name='Gold (fallback)',
            color=Vec3(0.83, 0.69, 0.22),
            reflectance=0.90, roughness=0.03,
            density_kg_m3=19300, mean_Z=79, mean_A=197,
            composition='Au (FCC)',
            alpha_r=ar, alpha_g=ag, alpha_b=ab,
        )

    r, g, b = metal_rgb('gold')
    refl = specular_fraction('gold', T=T)
    rough = microfacet_roughness('gold', T=T)
    mat = SURFACE_MATERIALS['gold']

    ar, ag, ab = _METAL_ALPHA_RGB['gold']
    K = _bulk_modulus('gold', sigma) if HAS_DYNAMICS else 180e9
    return Material(
        name='Gold',
        color=Vec3(r, g, b),
        reflectance=float(refl),
        roughness=float(rough),
        density_kg_m3=mat['density_kg_m3'],
        mean_Z=mat['Z'],
        mean_A=mat['A'],
        composition=mat['composition'],
        bulk_modulus_pa=K,
        restitution=_RESTITUTION['gold'],
        alpha_r=ar, alpha_g=ag, alpha_b=ab,
    )


def iron(sigma=0.0, T=300.0):
    """Iron — dark grey metallic."""
    if not HAS_PHYSICS:
        ar, ag, ab = _METAL_ALPHA_RGB['iron']
        return Material(
            name='Iron (fallback)',
            color=Vec3(0.42, 0.40, 0.38),
            reflectance=0.65, roughness=0.12,
            density_kg_m3=7874, mean_Z=26, mean_A=56,
            composition='Fe (BCC)',
            alpha_r=ar, alpha_g=ag, alpha_b=ab,
        )

    r, g, b = metal_rgb('iron')
    refl = specular_fraction('iron', T=T)
    rough = microfacet_roughness('iron', T=T)
    mat = SURFACE_MATERIALS['iron']

    ar, ag, ab = _METAL_ALPHA_RGB['iron']
    K = _bulk_modulus('iron', sigma) if HAS_DYNAMICS else 170e9
    return Material(
        name='Iron',
        color=Vec3(r, g, b),
        reflectance=float(refl),
        roughness=float(rough),
        density_kg_m3=mat['density_kg_m3'],
        mean_Z=mat['Z'],
        mean_A=mat['A'],
        composition=mat['composition'],
        alpha_r=ar, alpha_g=ag, alpha_b=ab,
        bulk_modulus_pa=K,
        restitution=_RESTITUTION['iron'],
    )


# ── Painted aluminum ────────────────────────────────────────────────────

def painted_aluminum(paint_r, paint_g, paint_b,
                     paint_roughness=0.35, T=300.0):
    """Aluminum with paint coat.

    Physics: the aluminum body provides the mass and structure.
    The paint is a thin polymer + pigment layer on top.
    Color comes from the paint (EM, σ-invariant).
    Density is aluminum (paint mass is negligible).
    Reflectance is reduced by paint diffusivity.

    Args:
        paint_r/g/b: measured paint color (0-1)
        paint_roughness: Beckmann α for the paint surface (default: satin)
    """
    if not HAS_PHYSICS:
        return Material(
            name='Painted Aluminum (fallback)',
            color=Vec3(paint_r, paint_g, paint_b),
            reflectance=0.12, roughness=paint_roughness,
            density_kg_m3=2700, mean_Z=13, mean_A=27,
            composition='Al substrate + polymer paint',
        )

    mat = SURFACE_MATERIALS['aluminum']
    # Paint reduces specular reflection — roughly 10-20% for satin finish
    refl = 0.12

    return Material(
        name='Painted Aluminum',
        color=Vec3(paint_r, paint_g, paint_b),
        reflectance=refl,
        roughness=paint_roughness,
        density_kg_m3=mat['density_kg_m3'],
        mean_Z=mat['Z'],
        mean_A=mat['A'],
        composition=f'Al substrate + paint (r={paint_r:.2f},g={paint_g:.2f},b={paint_b:.2f})',
    )


# ── Organic / fabric materials ─────────────────────────────────────────

def wool_natural(T=300.0):
    """Undyed natural wool (cream-white keratin fiber).

    Color from measured spectrophotometry (ORGANIC_SPECTRA).
    Keratin is a fibrous protein — color from molecular orbital
    transitions (π→π*, n→π*) that require DFT for first-principles.
    We use measured reflectance until organic chemistry module exists.
    """
    if not HAS_PHYSICS:
        return Material(
            name='Natural Wool (fallback)',
            color=Vec3(0.82, 0.78, 0.68),
            reflectance=0.03, roughness=0.65,
            density_kg_m3=1300, mean_Z=7, mean_A=14,
            composition='Keratin',
        )

    spec = ORGANIC_SPECTRA['wool_natural']
    return Material(
        name=spec['name'],
        color=Vec3(spec['reflectance_r'], spec['reflectance_g'], spec['reflectance_b']),
        reflectance=0.04,
        roughness=spec['roughness'],
        density_kg_m3=spec['density_kg_m3'],
        mean_Z=spec['mean_Z'],
        mean_A=spec['mean_A'],
        composition=spec['composition'],
    )


def dyed_wool(dye_name, T=300.0):
    """Wool fiber with a chromophore dye.

    Color derivation:
      1. Start with measured wool substrate reflectance (ORGANIC_SPECTRA)
      2. Apply dye absorption band (MEASURED: λ_abs, width from DYE_DATABASE)
      3. Beer-Lambert transmission at R, G, B wavelengths (FIRST_PRINCIPLES)
      4. Result: color that emerges from what the dye did NOT absorb

    This is the correct physical model:
      "The admiral's coat is blue because the indigo dye absorbs orange-red."

    Args:
        dye_name: key into DYE_DATABASE ('indigo', 'prussian_blue', etc.)
    """
    if not HAS_PHYSICS:
        fallback_colors = {
            'indigo': (0.14, 0.22, 0.62),
            'prussian_blue': (0.10, 0.18, 0.55),
            'madder_red': (0.72, 0.12, 0.14),
            'weld_yellow': (0.92, 0.82, 0.08),
            'black_iron': (0.05, 0.05, 0.06),
        }
        r, g, b = fallback_colors.get(dye_name, (0.5, 0.5, 0.5))
        return Material(
            name=f'Wool + {dye_name} (fallback)',
            color=Vec3(r, g, b),
            reflectance=0.04, roughness=0.65,
            density_kg_m3=1300, mean_Z=7, mean_A=14,
            composition=f'Keratin + {dye_name} chromophore',
        )

    # Substrate: natural wool
    substrate = ORGANIC_SPECTRA['wool_natural']
    sub_rgb = (substrate['reflectance_r'], substrate['reflectance_g'], substrate['reflectance_b'])

    # Apply dye absorption
    r, g, b = dye_transmission_rgb(dye_name, sub_rgb)

    dye = DYE_DATABASE[dye_name]

    return Material(
        name=f"Wool + {dye['name']}",
        color=Vec3(r, g, b),
        reflectance=0.04,
        roughness=substrate['roughness'],
        density_kg_m3=substrate['density_kg_m3'],
        mean_Z=substrate['mean_Z'],
        mean_A=substrate['mean_A'],
        composition=f"Keratin + {dye['name']}",
    )


def felt(color_key='black_iron', T=300.0):
    """Compressed wool felt — low density, high roughness.

    For hat material: black/dark felt from dyed wool.
    """
    if color_key == 'black_iron':
        spec = ORGANIC_SPECTRA.get('felt_black', {})
        if spec:
            return Material(
                name='Black felt',
                color=Vec3(spec['reflectance_r'], spec['reflectance_g'], spec['reflectance_b']),
                reflectance=0.02,
                roughness=spec.get('roughness', 0.90),
                density_kg_m3=spec['density_kg_m3'],
                mean_Z=spec['mean_Z'],
                mean_A=spec['mean_A'],
                composition=spec['composition'],
            )
    return dyed_wool(color_key)


# ── Brass: copper-zinc alloy ─────────────────────────────────────────────

def brass(zinc_fraction=0.30, T=300.0):
    """Brass (Cu-Zn alloy) — golden warm metal.

    Composition: typically 70% Cu + 30% Zn.
    Optical: dominated by Cu d-band; Zn shifts absorption slightly
    toward UV, making brass warmer/more golden than pure copper.

    Approximation: treat as pure copper + small Zn correction.
    Zn has a closed d-shell (3d¹⁰), so its interband transitions are
    in the UV — Zn's effect on visible color is minimal.
    Color is dominated by the Cu Drude + d-band response.
    Density: linear mixing rule (APPROXIMATION: real alloys may deviate).

    Origin: FIRST_PRINCIPLES for Cu component; APPROXIMATION for mixing.
    """
    cu_color = metal_rgb('copper')
    # Zn is near-white; blend colors by composition
    # Zn RGB at 650/550/450 nm: Drude with n_e≈2, ωp≈14 eV → also silvery
    # Net effect: brass is slightly less orange than Cu
    zn_frac = max(0.0, min(zinc_fraction, 0.6))
    r = cu_color[0] * (1 - zn_frac * 0.3)
    g = cu_color[1] * (1 - zn_frac * 0.1)
    b = cu_color[2] * (1 + zn_frac * 0.5)   # Zn restores some blue

    # Clamp
    r, g, b = min(r, 1.0), min(g, 1.0), min(b, 1.0)

    # Density: Cu = 8960, Zn = 7133 kg/m³
    density = 8960 * (1 - zn_frac) + 7133 * zn_frac
    # Z_eff: Cu=29, Zn=30
    z_eff = 29 * (1 - zn_frac) + 30 * zn_frac
    # A_eff: Cu=64, Zn=65
    a_eff = 64 * (1 - zn_frac) + 65 * zn_frac

    if HAS_PHYSICS:
        refl = specular_fraction('copper', T=T)
        rough = microfacet_roughness('copper', T=T)
    else:
        refl, rough = 0.85, 0.04

    return Material(
        name=f'Brass (Cu{100*(1-zn_frac):.0f}Zn{100*zn_frac:.0f})',
        color=Vec3(r, g, b),
        reflectance=float(refl),
        roughness=float(rough),
        density_kg_m3=density,
        mean_Z=z_eff,
        mean_A=a_eff,
        composition=f'Cu{100*(1-zn_frac):.0f}Zn{100*zn_frac:.0f} alloy',
    )


# ─────────────────────────────────────────────────────────────────────────
# ATOM-SOURCED MATERIAL FACTORY — the architecture endpoint
# ─────────────────────────────────────────────────────────────────────────
#
# material_from_atom(atom) takes a quarksum Atom and returns a Material.
# No string key. No name lookup. The atom's Z and electron configuration
# ARE the material specification.
#
# This is the pipeline the Captain described:
#   quarksum model (matter loaded)
#     → each atom has electron configuration, Z, σ
#     → optical response from Z (Drude + Palik, keyed by Z)
#     → Material with color, reflectance, density
#     → SurfaceNode uses that Material
#     → renderer reads color from the node
#     → rendering is a side-effect of the atom existing
#
# Scope: metallic elements (element_category contains 'metal', or block='d').
# Organic compounds require molecular orbital theory — not yet in scope.
# For those, use dyed_wool(), wool_natural(), felt() above.
#
# σ-dependence:
#   color: INVARIANT (EM)
#   density: scales at sigma via material.density_at_sigma(σ)
#
# □σ = −ξR

# String-keyed surface material data, accessed by SURFACE material key for
# roughness/reflectance when texture.py doesn't have atom-sourced lookup yet.
_SURFACE_KEY_BY_Z = {
    13: 'aluminum', 26: 'iron', 28: 'nickel',
    29: 'copper', 74: 'tungsten', 79: 'gold',
}


def material_from_atom(atom, T: float = 300.0) -> Material:
    """Create a physics-derived Material from a quarksum Atom.

    The atom's atomic_number (Z) drives the entire optical cascade.
    No name string in the chain. Z=13 IS aluminum.

    Supported element categories:
      - Metallic elements (block='d' or 's'/'p' post-transition metals):
        Drude + Palik/Johnson-Christy → RGB
      - All others: returns a grey fallback with correct density/Z/A
        (organic/molecular materials require compound-level treatment)

    Args:
        atom: quarksum Atom (quarksum.models.atom.Atom)
        T: temperature in Kelvin (used for roughness / reflectance when
           texture.py has a match; default 300 K)

    Returns:
        Material: color, reflectance, roughness, density — all from the atom
    """
    z = atom.atomic_number
    sym = atom.symbol
    name = atom.name
    A = atom.atomic_mass
    density = CRYSTAL_DENSITY_BY_Z.get(z, 0)

    # ── Determine if this is a metallic element ───────────────────────────
    cat = getattr(atom, 'element_category', '') or ''
    block = getattr(atom, 'block', '') or ''
    is_metal = (
        'metal' in cat.lower()
        or block in ('d', 'f')
        or z in VALENCE_ELECTRONS_BY_Z
    )

    # ── Semiconductor path: route known elemental semiconductors by Z ────
    if HAS_SEMICONDUCTOR and z in Z_TO_SEMICONDUCTOR:
        semi_key = Z_TO_SEMICONDUCTOR[z]
        params   = VARSHNI_PARAMS[semi_key]
        r, g, b  = semiconductor_rgb(semi_key, T=T)
        refl     = max(r, g, b)
        return Material(
            name=name,
            color=Vec3(r, g, b),
            reflectance=refl,
            roughness=0.04,
            density_kg_m3=params['density_kg_m3'],
            mean_Z=z,
            mean_A=A,
            composition=f'{sym} (Z={z}, semiconductor)',
        )

    if not is_metal or not HAS_PHYSICS or density == 0:
        # Non-metal or missing data: grey fallback with correct physics constants
        return Material(
            name=f'{name} (non-metal fallback)',
            color=Vec3(0.5, 0.5, 0.5),
            reflectance=0.05,
            roughness=0.60,
            density_kg_m3=max(density, 1000),
            mean_Z=z,
            mean_A=A,
            composition=f'{sym} (Z={z})',
        )

    # ── Metal path: color from atom's Z via Drude + Palik/JC72 ───────────
    r, g, b = metal_rgb_from_atom(atom)

    # Roughness and reflectance: try texture.py by surface key if available
    surface_key = _SURFACE_KEY_BY_Z.get(z)
    if surface_key and HAS_PHYSICS:
        try:
            refl = float(specular_fraction(surface_key, T=T))
            rough = float(microfacet_roughness(surface_key, T=T))
        except Exception:
            refl, rough = 0.90, 0.04
    else:
        refl, rough = 0.90, 0.04

    return Material(
        name=name,
        color=Vec3(r, g, b),
        reflectance=refl,
        roughness=rough,
        density_kg_m3=density,
        mean_Z=z,
        mean_A=A,
        composition=f'{sym} (Z={z}, A={A:.2f} u)',
    )


# ─────────────────────────────────────────────────────────────────────────
# DIELECTRIC / TRANSPARENT MATERIALS
# ─────────────────────────────────────────────────────────────────────────
#
# Transparent materials have:
#   - color from Beer-Lambert transmission through the bulk (wavelength-selective)
#   - opacity from Fresnel surface reflectance (R ≈ 4% for glass, 2% for water)
#   - ior from Cauchy equation n(λ=550nm)
#
# The renderer uses Material.opacity for the Porter-Duff blend weight.
# A glass sphere with opacity=0.04 lets 96% of the light behind it through.
#
# σ-dependence: NONE — all EM, all invariant.
# □σ = −ξR

# Bulk densities and compositions for common dielectrics (MEASURED: CRC)
_DIELECTRIC_PROPERTIES = {
    'fused_silica':  {'density': 2200, 'Z': 10, 'A': 20, 'formula': 'SiO₂'},
    'borosilicate':  {'density': 2230, 'Z': 10, 'A': 20, 'formula': 'SiO₂+B₂O₃'},
    'crown_glass':   {'density': 2520, 'Z': 11, 'A': 22, 'formula': 'SiO₂+Na₂O+CaO'},
    'flint_glass':   {'density': 3600, 'Z': 38, 'A': 82, 'formula': 'SiO₂+PbO'},
    'water':         {'density': 998,  'Z':  4, 'A':  6, 'formula': 'H₂O'},
    'ice':           {'density': 917,  'Z':  4, 'A':  6, 'formula': 'H₂O (solid)'},
    'diamond':       {'density': 3510, 'Z':  6, 'A': 12, 'formula': 'C'},
    'sapphire':      {'density': 3980, 'Z': 10, 'A': 20, 'formula': 'Al₂O₃'},
    'quartz':        {'density': 2650, 'Z': 10, 'A': 20, 'formula': 'SiO₂ (xtal)'},
    'acrylic':       {'density': 1185, 'Z':  6, 'A': 12, 'formula': '(C₅H₈O₂)ₙ'},
    'polycarbonate': {'density': 1200, 'Z':  6, 'A': 12, 'formula': 'PC polymer'},
}


def glass(glass_type: str = 'crown_glass',
          tint: str = 'clear',
          thickness_m: float = 3e-3,
          T: float = 300.0) -> 'Material':
    """Transparent glass from Fresnel + Cauchy + Beer-Lambert.

    Color derivation:
      1. Cauchy n(λ) → Fresnel R(λ) per surface (FIRST_PRINCIPLES)
      2. Two surfaces → T_surface = (1-R)²
      3. Beer-Lambert bulk absorption: T_bulk = exp(-α(λ)×d) (FIRST_PRINCIPLES)
      4. Color = T_surface × T_bulk at R/G/B wavelengths
      5. Opacity = R_green (Fresnel reflection at 550nm — what the renderer
         uses for Porter-Duff blending; ~4% for crown glass)

    Args:
        glass_type: key into CAUCHY_COEFFICIENTS
        tint: key into DIELECTRIC_ABSORPTION ('clear', 'amber_glass', etc.)
        thickness_m: slab thickness for Beer-Lambert (default 3mm)
        T: temperature (not yet used; reserved for thermal expansion)

    Returns:
        Material with correct transparency for the renderer
    """
    if not HAS_PHYSICS:
        return Material(
            name=f'{glass_type} (fallback)',
            color=Vec3(0.92, 0.96, 0.98),
            reflectance=0.04, roughness=0.01, opacity=0.04,
            ior=1.52,
            density_kg_m3=2500, mean_Z=10, mean_A=20,
            composition='SiO₂ (fallback)',
        )

    r, g, b = dielectric_color_rgb(glass_type, tint, thickness_m)
    opacity = dielectric_opacity(glass_type)       # Fresnel R ≈ 4%
    n_ior = cauchy_n(glass_type, LAMBDA_G)         # refractive index at 550nm

    props = _DIELECTRIC_PROPERTIES.get(glass_type, {
        'density': 2500, 'Z': 10, 'A': 20, 'formula': glass_type,
    })

    tint_label = '' if tint == 'clear' else f' ({tint})'
    return Material(
        name=f'{glass_type}{tint_label}',
        color=Vec3(r, g, b),
        reflectance=opacity,
        roughness=0.01,
        opacity=opacity,
        ior=n_ior,
        density_kg_m3=props['density'],
        mean_Z=props['Z'],
        mean_A=props['A'],
        composition=props['formula'],
    )


def water(tint: str = 'water_blue', depth_m: float = 0.1, T: float = 293.0) -> 'Material':
    """Liquid water from Cauchy n + Beer-Lambert ocean absorption.

    Water appears blue because it absorbs red light (vibrational overtones
    of O-H bond at 760nm). The deeper the water, the bluer it looks.
    This is FIRST_PRINCIPLES: Beer-Lambert through measured absorption.

    Args:
        tint: absorption profile (default: 'water_blue')
        depth_m: optical path length — controls color depth (default 10cm)
        T: temperature (affects n slightly; not yet wired)
    """
    r, g, b = dielectric_color_rgb('water', tint, depth_m)
    opacity = dielectric_opacity('water')   # Fresnel R ≈ 2%
    n_ior = cauchy_n('water', LAMBDA_G)

    if not HAS_PHYSICS:
        return Material(
            name='Water', color=Vec3(0.78, 0.93, 0.97),
            reflectance=0.02, roughness=0.05, opacity=0.02, ior=1.333,
            density_kg_m3=998, mean_Z=4, mean_A=6, composition='H₂O',
        )

    return Material(
        name='Water',
        color=Vec3(r, g, b),
        reflectance=opacity,
        roughness=0.05,
        opacity=opacity,
        ior=n_ior,
        density_kg_m3=998,
        mean_Z=4,
        mean_A=6,
        composition='H₂O',
    )


def crystal(crystal_type: str = 'quartz',
            tint: str = 'clear', T: float = 300.0) -> 'Material':
    """Crystal material — high-n dielectric, very clear.

    Covers quartz, sapphire, diamond, calcite.
    Higher refractive index → more Fresnel reflection → more sparkle.
    Diamond (n≈2.4) reflects 17% per surface — that's why it looks brilliant.
    """
    r, g, b = dielectric_color_rgb(crystal_type, tint, 1e-3)  # 1mm path
    opacity = dielectric_opacity(crystal_type)
    n_ior = cauchy_n(crystal_type, LAMBDA_G)

    props = _DIELECTRIC_PROPERTIES.get(crystal_type, {
        'density': 2650, 'Z': 10, 'A': 20, 'formula': crystal_type,
    })

    if not HAS_PHYSICS:
        return Material(
            name=crystal_type, color=Vec3(0.95, 0.97, 0.99),
            reflectance=opacity, roughness=0.005, opacity=opacity, ior=n_ior,
            density_kg_m3=props['density'], mean_Z=props['Z'], mean_A=props['A'],
            composition=props['formula'],
        )

    return Material(
        name=crystal_type,
        color=Vec3(r, g, b),
        reflectance=opacity,
        roughness=0.005,
        opacity=opacity,
        ior=n_ior,
        density_kg_m3=props['density'],
        mean_Z=props['Z'],
        mean_A=props['A'],
        composition=props['formula'],
    )


# ─────────────────────────────────────────────────────────────────────────
# CRYSTAL FIELD MINERALS — transition metal optics (ruby, emerald, etc.)
# ─────────────────────────────────────────────────────────────────────────

def crystal_field_mineral(mineral_name: str, T: float = 300.0) -> 'Material':
    """Material from crystal field theory — gem/mineral colors from d-electron transitions.

    Color derivation chain:
      mineral_name → Z + oxidation state + coordination (MEASURED: mineralogy)
      → d-electron count (FIRST_PRINCIPLES: Aufbau)
      → 10Dq crystal field splitting (MEASURED: optical spectroscopy)
      → Racah B × nephelauxetic β (MEASURED: Jørgensen 1962)
      → absorption bands (FIRST_PRINCIPLES: Tanabe-Sugano)
      → RGB via Beer-Lambert (FIRST_PRINCIPLES)
      → Material color

    σ-dependence: NONE — crystal field is EM (Coulomb) → σ-INVARIANT.

    Args:
        mineral_name: key into MINERAL_COORDS (e.g. 'ruby', 'emerald', 'malachite')
        T: temperature (not yet connected to crystal field; reserved)

    Returns:
        Material with physics-derived color.
    """
    if not HAS_CRYSTAL_FIELD:
        return Material(
            name=f'{mineral_name} (no crystal field module)',
            color=Vec3(0.5, 0.5, 0.5),
            reflectance=0.08, roughness=0.30,
            density_kg_m3=3000, mean_Z=13, mean_A=27,
            composition=mineral_name,
        )

    r, g, b = mineral_rgb(mineral_name)
    # MINERAL_COORDS stores (Z, oxidation_state, coord_key) tuples.
    # Use the transition metal Z for mean_Z; density from per-mineral table.
    Z_ion, ox_state, coord_key = MINERAL_COORDS[mineral_name]

    # Approximate mineral densities (kg/m³) — MEASURED: CRC Handbook
    _MINERAL_DENSITY = {
        'ruby': 4010, 'emerald': 2760, 'alexandrite': 3720,
        'malachite': 4050, 'azurite': 3830, 'turquoise': 2800,
        'peridot': 3320, 'cobalt_blue': 6110, 'ti_sapphire': 3990,
        'nickel_green': 4050, 'spessartine': 4190, 'piemontite': 3450,
        'goethite': 4270,
    }
    density = _MINERAL_DENSITY.get(mineral_name, 3000)
    formula = mineral_name.replace('_', ' ').title()
    z_mean  = Z_ion
    a_mean  = round(Z_ion * 2.1)   # rough approximation

    # Per-channel Beer-Lambert alpha from published spectroscopy
    # (see _MINERAL_ALPHA_RGB table above for sources).
    # The opacity is low (Fresnel ~0.04–0.12) so light enters the gem and
    # volume nodes provide the wavelength-selective absorption.
    a_rgb = _MINERAL_ALPHA_RGB.get(mineral_name, (0.0, 0.0, 0.0))

    return Material(
        name=mineral_name.replace('_', ' ').title(),
        color=Vec3(r, g, b),
        reflectance=0.12,        # gem surface Fresnel (n≈1.7; EM → σ-invariant)
        roughness=0.25,          # typical polished mineral
        opacity=0.04,            # Fresnel surface: ~4% reflects, ~96% enters gem
        density_kg_m3=density,
        mean_Z=z_mean,
        mean_A=a_mean,
        composition=formula,
        alpha_r=a_rgb[0], alpha_g=a_rgb[1], alpha_b=a_rgb[2],
    )


# ─────────────────────────────────────────────────────────────────────────
# SEMICONDUCTOR MATERIALS — band gap optics
# ─────────────────────────────────────────────────────────────────────────

def semiconductor_material(key: str, T: float = 300.0) -> 'Material':
    """Material from semiconductor band gap optics.

    Color derivation chain:
      key → Varshni params → E_g(T) (MEASURED + FIRST_PRINCIPLES: Varshni 1967)
      → band edge λ_edge = hc/E_g (FIRST_PRINCIPLES)
      → n+ik at R/G/B (MEASURED: Palik / Aspnes)
      → 3-regime Fresnel color (FIRST_PRINCIPLES)
      → Material color

    σ-dependence: NONE — band gap is EM (electrostatic crystal potential) → σ-INVARIANT.

    Args:
        key: material key from VARSHNI_PARAMS / SEMICONDUCTOR_NK
             (e.g. 'silicon', 'diamond', 'gallium_phosphide', 'cadmium_sulfide')
        T: temperature in Kelvin (affects band gap via Varshni equation)

    Returns:
        Material with physics-derived color.
    """
    if not HAS_SEMICONDUCTOR:
        return Material(
            name=f'{key} semiconductor (no module)',
            color=Vec3(0.4, 0.4, 0.4),
            reflectance=0.35, roughness=0.04,
            density_kg_m3=2000, mean_Z=14, mean_A=28,
            composition=key,
        )

    r, g, b   = semiconductor_rgb(key, T=T)
    params    = VARSHNI_PARAMS[key]
    density   = params['density_kg_m3']
    formula   = params['formula']
    Z         = params.get('Z') or 14   # fallback to Si Z for compounds

    # Reflectance: max of the three RGB channels (Fresnel surface)
    refl = max(r, g, b)

    return Material(
        name=formula,
        color=Vec3(r, g, b),
        reflectance=refl,
        roughness=0.04,        # polished wafer — very smooth
        density_kg_m3=density,
        mean_Z=Z,
        mean_A=round(Z * 2.1),   # rough approximation for mean_A
        composition=formula,
    )


# ─────────────────────────────────────────────────────────────────────────
# GLOWING MATERIALS — thermal emission (hot metal glow)
# ─────────────────────────────────────────────────────────────────────────

def glowing_material(
    material_key: str = 'iron',
    T: float = 1500.0,
    base_material: 'Material' = None,
) -> 'Material':
    """Material with thermal emission color — hot glowing metal.

    Color derivation chain:
      material_key → n+ik → ε(λ) = 1 − Fresnel(n,k) (FIRST_PRINCIPLES: Kirchhoff)
      T → B(λ,T) = Planck spectral radiance (FIRST_PRINCIPLES: Planck 1900)
      L(λ,T) = ε(λ) × B(λ,T)
      → normalised visible chromaticity → Material color

    Below the Draper point (~700K), material appears cold → uses base_material color.
    Above it, the thermal glow dominates → uses emission chromaticity.

    σ-dependence: NONE — Planck + Kirchhoff + Fresnel are all EM → σ-INVARIANT.

    Args:
        material_key: key from THERMAL_EMISSION_MATERIALS
                      ('blackbody', 'iron', 'copper', 'gold', 'aluminum',
                       'tungsten', 'nickel', 'titanium')
        T: temperature in Kelvin
        base_material: cold-temperature appearance (used if T < Draper point).
                       If None, uses grey fallback.

    Returns:
        Material representing the hot glowing object.
    """
    if not HAS_THERMAL_EMISSION or not is_visibly_glowing(T):
        if base_material is not None:
            return base_material
        return Material(
            name=f'{material_key} (cold, T={T:.0f}K)',
            color=Vec3(0.5, 0.5, 0.5),
            reflectance=0.70, roughness=0.08,
            density_kg_m3=7874, mean_Z=26, mean_A=56,
            composition=f'{material_key} (cold)',
        )

    r, g, b = thermal_emission_rgb(material_key, T=T)

    # Density / Z from base material if provided, else iron defaults
    if base_material is not None:
        density  = base_material.density_kg_m3
        mean_z   = base_material.mean_Z
        mean_a   = base_material.mean_A
        comp     = base_material.composition
    else:
        density = 7874   # iron default
        mean_z  = 26
        mean_a  = 56
        comp    = f'{material_key} (glowing)'

    return Material(
        name=f'{material_key} (T={T:.0f}K)',
        color=Vec3(r, g, b),
        reflectance=0.20,       # hot metal surface is somewhat less reflective
        roughness=0.15,
        density_kg_m3=density,
        mean_Z=mean_z,
        mean_A=mean_a,
        composition=comp,
    )


# ── Convenience: print a color report ────────────────────────────────────

def print_palette():
    """Print all Skippy materials with their physics-derived colors."""
    materials = {
        'Aluminum body': aluminum(),
        'Copper': copper(),
        'Gold buttons': gold(),
        'Iron': iron(),
        'Brass buttons': brass(),
        'Wool coat (indigo)': dyed_wool('indigo'),
        'Wool (prussian blue)': dyed_wool('prussian_blue'),
        'Wool (madder red)': dyed_wool('madder_red'),
        'Natural wool': wool_natural(),
        'Black felt hat': felt('black_iron'),
    }
    print("\n  Physics-derived material palette:")
    print(f"  {'Material':<30} {'R':>6} {'G':>6} {'B':>6}  {'refl':>6}  {'rough':>6}  Composition")
    print("  " + "─" * 90)
    for name, mat in materials.items():
        c = mat.color
        print(f"  {name:<30} {c.x:6.3f} {c.y:6.3f} {c.z:6.3f}  {mat.reflectance:6.3f}  {mat.roughness:6.4f}  {mat.composition[:40]}")
    print()


# ─────────────────────────────────────────────────────────────────────────
# EMISSIVE MATERIALS — thermal radiators that ARE the light source
# ─────────────────────────────────────────────────────────────────────────
#
# The ghost is exorcised. PushLight was the one object in the renderer that
# wasn't matter. These materials replace it: hot matter with surface nodes
# that push their emission directly to the pixel buffer, no external trigger.
#
# Physics chain:
#   T (Kelvin) → Planck B(λ,T) per wavelength → R/G/B sample
#   × ε(λ) (emissivity from Kirchhoff: ε = 1 − reflectance, real tungsten)
#   → normalize chromaticity → emission Vec3 × intensity
#
# The renderer reads material.emission and adds it directly to the compositor
# without illuminate_node(). The node glows. The engine auto-derives a
# PushLight from the emissive object's centroid to illuminate everything else.
#
# σ-dependence: NONE — Planck radiation is EM → σ-INVARIANT.
# The filament glows the same colour near a black hole. Just heavier.
#
# □σ = −ξR

import math as _math


def _blackbody_rgb(T_kelvin, ref_T=6500.0):
    """Planck spectral radiance at R/G/B wavelengths, normalised per-channel
    relative to ref_T, then normalised so max channel = 1.0.

    Evaluates B(λ,T) ∝ 1/(exp(hc/λkT) − 1) at three wavelengths:
      R = 700 nm (long-wavelength edge of CIE photopic response)
      G = 550 nm (peak of photopic response)
      B = 450 nm (short-wavelength)

    The per-channel normalisation against ref_T ensures that a
    ref_T=6500K source (D65 daylight) maps to (1, 1, 1) — white.
    Cooler sources come out warm (red-heavy); hotter sources come out
    blue-shifted.  The final max-channel normalisation gives chromaticity
    only; overall brightness is set by the intensity parameter.

    FIRST_PRINCIPLES: Planck (1900). hc/k = 0.014388 m·K.

    Returns:
        (r, g, b) floats, max = 1.0.
    """
    hc_k = 0.014388  # h×c/k  (second radiation constant, m·K)

    def _ratio(lam_m):
        # B(lam, T_hot) / B(lam, ref_T)  — the 2hc²/λ⁵ prefactor cancels.
        exp_hot = _math.exp(hc_k / (lam_m * T_kelvin))
        exp_ref = _math.exp(hc_k / (lam_m * ref_T))
        return (exp_ref - 1.0) / (exp_hot - 1.0)

    r = _ratio(700e-9)
    g = _ratio(550e-9)
    b = _ratio(450e-9)

    max_v = max(r, g, b, 1e-12)
    return r / max_v, g / max_v, b / max_v


def phys_tungsten_filament(T=2800, intensity=8.0):
    """Tungsten filament glowing at temperature T.

    T = 2800 K: bright incandescent light.  Safely below tungsten's melting
    point (3695 K / 3422 °C).  At 2800 K the Planck peak is at ~1.04 µm
    (near-infrared); the visible tail is the warm amber glow we see.

    Color chain:
      thermal_emission_rgb('tungsten', T) if local_library available
        — includes wavelength-dependent emissivity ε(λ) from Kirchhoff
           (ε = 1 − R_Fresnel, tungsten k values from Palik 1985).
      Fallback: pure blackbody _blackbody_rgb(T) normalised to 6500K=white.

    At T=2800K (fallback):
      R=1.0, G≈0.33, B≈0.10  → warm amber, correctly weighted.

    emission = Vec3(r, g, b) × intensity
      The renderer adds emission directly to the pixel compositor
      (bypass illuminate_node — the node radiates, it is not illuminated).
      intensity=8.0 makes the filament over-exposed when viewed directly,
      which is correct — you can't stare at a lightbulb.

    Physical properties:
      Tungsten (W), BCC lattice, Z=74, A≈184 u, ρ=19 300 kg/m³.
      At 2800 K tungsten is still solid (m.p. 3695 K).
      High reflectance for a metal due to sp-band transitions.

    Args:
        T:         filament temperature in Kelvin (default 2800 K).
        intensity: brightness multiplier for emission Vec3.

    Returns:
        Material with emission set; ready for entangle().
    """
    if HAS_THERMAL_EMISSION and is_visibly_glowing(T):
        r, g, b = thermal_emission_rgb('tungsten', T=T)
    else:
        r, g, b = _blackbody_rgb(T)

    emission = Vec3(r * intensity, g * intensity, b * intensity)

    # Surface colour = same warm glow (also used if the object is viewed in
    # a context where emission isn't handled — e.g. legacy push renderer).
    return Material(
        name=f'Tungsten filament ({T:.0f} K)',
        color=Vec3(r, g, b),
        emission=emission,
        reflectance=0.30,        # tungsten visible reflectance (~30%)
        roughness=0.15,          # drawn wire, slightly rough
        opacity=1.0,             # filament is opaque (skin depth << wire radius)
        density_kg_m3=19300,
        mean_Z=74,
        mean_A=184,
        composition='W (BCC, Z=74)',
    )


def phys_glass_bulb(glass_type='borosilicate'):
    """Vacuum-sealed glass envelope — the bulb around the filament.

    Borosilicate (Pyrex-type) glass: low thermal expansion coefficient,
    tolerates the thermal gradient from a 2800 K filament in vacuum.

    Optical properties:
      Fresnel reflectance ≈ 3.5% per surface (n≈1.47 for borosilicate).
      Two surfaces → ~7% total reflection, ~93% transmission.
      Nearly colourless in visible; slight blue-green tint from trace FeO.

    The renderer's Porter-Duff compositor handles transmission automatically:
      opacity=0.04 → 4% of this node's colour enters the accumulator,
      96% remaining transmittance passes to nodes behind (the filament).
    So the filament's warm glow passes through the glass at 96% efficiency.

    Falls back to a simple near-transparent material if local_library absent.
    """
    if HAS_PHYSICS:
        return glass(glass_type, tint='clear')

    # Fallback: nearly transparent, very slight warm tint (trace iron oxide)
    return Material(
        name='Borosilicate glass (fallback)',
        color=Vec3(0.93, 0.96, 0.97),
        reflectance=0.04,
        roughness=0.01,
        opacity=0.04,
        ior=1.47,
        density_kg_m3=2230,
        mean_Z=10,
        mean_A=20,
        composition='SiO₂ + B₂O₃ (borosilicate)',
    )


# ─────────────────────────────────────────────────────────────────────────
# CELESTIAL LIGHT SOURCES
# ─────────────────────────────────────────────────────────────────────────
#
# Sun and candle are genuine emitters — matter at temperature, Planck's law,
# real photons from real thermal agitation.
#
# The Moon is NOT an emitter. This is stated explicitly because making it
# one would be lying. Moonlight is reflected solar photons — the Sun's 5778K
# blackbody bounced off grey lunar regolith (albedo ≈ 0.12). There are no
# photons originating in the Moon. phys_moon_surface() returns a correct
# reflector material. Moonlit scenes require a distant Sun as the actual
# source; the Moon's reflected radiance requires photon-bounce architecture
# not yet in this renderer.
#
# □σ = −ξR


def phys_sun(intensity=500.0):
    """The photosphere of a G-type main-sequence star (Sol).

    Temperature: 5778 K.  This is measured from solar spectral irradiance
    fitting to a blackbody — the photosphere is approximately a perfect
    blackbody (FIRST_PRINCIPLES: Planck 1900; measured: Neckel & Labs 1984).

    At 5778 K the Planck peak is at λ_max = 2898/5778 µm ≈ 501 nm (green).
    The visible tail is broad and nearly flat across R/G/B, producing the
    white-yellow appearance of direct sunlight. Normalised against the
    D65 daylight reference (6500 K), the sun reads slightly warm:
      R ≈ 1.00, G ≈ 0.97, B ≈ 0.82  (at 5778 K / 6500 K ratios).

    intensity=500: the Sun is approximately 500× brighter in visible flux
    than a standard incandescent bulb at the same solid angle.  Over-exposed
    at any sane scene scale — correct, you cannot look at the Sun.

    Physical properties: solar photosphere plasma, mostly H + He.
    Density here is a notional surface value; no meaningful bulk density.

    Returns:
        Material with emission set; use as an EntanglerSphere in the scene.
    """
    if HAS_THERMAL_EMISSION and is_visibly_glowing(5778):
        r, g, b = thermal_emission_rgb('blackbody', T=5778)
    else:
        r, g, b = _blackbody_rgb(5778)

    emission = Vec3(r * intensity, g * intensity, b * intensity)

    return Material(
        name='Solar photosphere (5778 K)',
        color=Vec3(r, g, b),
        emission=emission,
        reflectance=0.0,      # plasma — no surface reflection
        roughness=0.0,
        opacity=1.0,
        density_kg_m3=200,    # photospheric plasma, notional
        mean_Z=1,             # mostly hydrogen
        mean_A=1,
        composition='H (76%) + He (24%) plasma, Z=1/2',
    )


def phys_candle_flame(T=1800, intensity=3.0):
    """A candle flame — hot soot particles in a combustion zone.

    Candle flames are NOT a hot gas emitting line spectra. They are a
    suspension of solid carbon (soot) nanoparticles at elevated temperature.
    Soot is approximately a perfect blackbody emitter (emissivity ε ≈ 0.95
    across visible; MEASURED: Charalampopoulos & Chang 1987, Appl. Opt.).

    Temperature zones:
      Inner (dark) cone:  ~600–800 K   — below Draper point, no visible glow
      Outer (blue) zone:  ~1000–1200 K — faint red, barely visible
      Luminous (yellow):  ~1400–1800 K — the bright cone we see
    Default T=1800 K represents the brightest part of a well-established flame.

    At 1800 K (blackbody):
      R ≈ 1.00, G ≈ 0.18, B ≈ 0.02 — deep red-orange, almost no blue.
    This is why candlelight is extremely warm: virtually no blue photons.

    intensity=3.0: a candle emits roughly 1/3 the visible flux of a 40W bulb.

    For flickering: generate multiple frames with
      intensity × random.uniform(0.7, 1.0)
    The physics is identical — candle brightness fluctuates ±30% due to
    convective instability in the combustion zone.

    Returns:
        Material with emission set; use as a small EntanglerEllipsoid.
    """
    if HAS_THERMAL_EMISSION and is_visibly_glowing(T):
        r, g, b = thermal_emission_rgb('blackbody', T=T)
    else:
        r, g, b = _blackbody_rgb(T)

    # Soot emissivity ε ≈ 0.95 — slight correction from pure blackbody.
    # Multiply all channels by 0.95 (soot absorbs ~5% and re-emits less).
    r, g, b = r * 0.95, g * 0.95, b * 0.95

    emission = Vec3(r * intensity, g * intensity, b * intensity)

    return Material(
        name=f'Candle flame soot ({T:.0f} K)',
        color=Vec3(r, g, b),
        emission=emission,
        reflectance=0.05,     # very slight surface reflection
        roughness=0.80,       # diffuse, turbulent surface
        opacity=0.60,         # flame is semi-transparent
        density_kg_m3=1,      # hot gas + soot suspension ≈ negligible density
        mean_Z=6,             # carbon soot
        mean_A=12,
        composition='C soot nanoparticles in combustion zone',
    )


def phys_moon_surface():
    """Lunar regolith — the surface of the Moon.

    !! THE MOON DOES NOT EMIT LIGHT !!
    emission is None. Moonlight is reflected solar photons.

    Physics:
      The Moon's geometric albedo is 0.12 (MEASURED: Lane & Irvine 1973,
      Astron. J. 78:267). It reflects 12% of incident sunlight, diffusely.
      The spectral reflectance is nearly flat across 400–700 nm (grey),
      with a slight red slope above 600 nm from space weathering of the
      regolith (iron-bearing minerals, agglutinates).

    For a moonlit scene, the correct architecture is:
      1. Place an EntanglerSphere with phys_sun() at the Sun's direction.
      2. Place an EntanglerSphere with phys_moon_surface() in the scene.
      3. The Sun's PushLight (auto-derived) illuminates the Moon's surface.
      4. The Moon's reflected radiance then illuminates the scene — but
         this requires a second bounce, which needs photon-bounce rendering
         not yet implemented.

    Workaround until bounce rendering exists:
      Derive a PushLight manually from the Sun direction with intensity
      reduced by the Moon's albedo (0.12) and the Moon's solid angle
      seen from Earth. This is an approximation, not a lie — just an
      explicit hand-off to a ghost while the architecture catches up.

    Returns:
        Material WITHOUT emission — a correct Lambert reflector.
    """
    # Lunar regolith spectral reflectance at R/G/B from Apollo sample data.
    # Source: Pieters (1999) "Mineralogy of the lunar crust", Table 1.
    #   R (700nm): 0.135  (slight reddening from space weathering)
    #   G (550nm): 0.115
    #   B (450nm): 0.090
    # These are absolute geometric albedo values per channel.
    return Material(
        name='Lunar regolith (Moon surface)',
        color=Vec3(0.135, 0.115, 0.090),   # grey with slight red slope
        emission=None,                      # THE MOON DOES NOT EMIT
        reflectance=0.12,                   # geometric albedo (diffuse)
        roughness=0.95,                     # highly porous, granular surface
        opacity=1.0,
        density_kg_m3=1500,                 # bulk regolith, MEASURED: Apollo
        mean_Z=11,                          # SiO₂ + Al₂O₃ + FeO mix
        mean_A=23,
        composition='SiO₂+Al₂O₃+FeO+MgO regolith (Apollo sample)',
    )


# ── Fluid materials — dynamics pipeline ──────────────────────────────────────

def phys_water(T=293.15, sigma=0.0):
    """Liquid water (H₂O) at temperature T.

    Physics:
      Color: MEASURED. Water is not colorless — it has a slight blue tint from
      the O-H vibrational overtone absorbing at 740 nm (red channel).
      Kd = 0.0144 m⁻¹ at 550 nm (pure water, Pope & Fry 1997, Appl. Opt.
      36:8710). For scene-scale rendering we approximate as near-clear blue.

      Density: 998.2 kg/m³ at 20°C (Kell 1975).
      Viscosity: 1.002 × 10⁻³ Pa·s at 20°C (IAPWS 2008).
      Bulk modulus: 2.20 GPa (resistance to compression; Kell 1975).
      Restitution: ~0.0 for free-surface water (splat). Not meaningful for bulk.

      IOR: 1.333 at 589 nm (sodium D line), MEASURED.

      σ-dependence: viscosity and density shift via fluid.py derivation chains.

    Args:
        T:     Temperature in K.
        sigma: σ-field value.

    Returns:
        Material with viscosity_pa_s and bulk_modulus_pa set.
    """
    eta  = liquid_viscosity('water', T=T, sigma=sigma) if HAS_DYNAMICS else 1.002e-3
    rho  = KNOWN_LIQUIDS['water']['density_kg_m3']     if HAS_DYNAMICS else 998.2
    K    = KNOWN_LIQUIDS['water']['bulk_modulus_pa']   if HAS_DYNAMICS else 2.20e9

    # Water color: very slight cyan tint (red absorption from O-H overtone)
    # Alpha coefficients from Pope & Fry (1997) absorption data, converted
    # to /inch. At ~0.014 m⁻¹ absorption for green, water is nearly clear.
    # We use small but non-zero alphas for volumetric coloring.
    alpha_r = 0.14 * 0.0254   # red slightly absorbed (~0.30 m⁻¹)
    alpha_g = 0.014 * 0.0254  # green: least absorbed
    alpha_b = 0.06  * 0.0254  # blue: slightly absorbed

    return Material(
        name=f'Liquid water (H₂O, {T:.0f} K)',
        color=Vec3(0.70, 0.85, 1.00),       # slight cyan (attenuation tint)
        reflectance=0.02,                    # Fresnel at normal incidence: ((n-1)/(n+1))² ≈ 0.020
        roughness=0.05,                      # flat surface; small capillary waves
        opacity=0.12,                        # nearly transparent in thin layer
        ior=1.333,                           # MEASURED: sodium D line, 20°C
        density_kg_m3=rho,
        mean_Z=3,                            # H₂O: mean of H(1), H(1), O(8) = 10/3 ≈ 3.3
        mean_A=6,                            # (1+1+16)/3 ≈ 6
        composition='H₂O liquid',
        alpha_r=alpha_r, alpha_g=alpha_g, alpha_b=alpha_b,
        viscosity_pa_s=eta,
        bulk_modulus_pa=K,
        restitution=0.20,                   # water surface is not very elastic
        reference_temp_K=T,
    )


def phys_air(T=293.15, P=101325.0, sigma=0.0):
    """Dry air at temperature T and pressure P.

    Composition: N₂ (78.09%) + O₂ (20.95%) + Ar (0.93%) + trace.

    Physics:
      Viscosity: Chapman-Enskog kinetic theory from gas.py, using N₂ as the
      dominant component. Air viscosity ≈ 1.81 × 10⁻⁵ Pa·s at 20°C.

      Bulk modulus: ideal gas → K = γP where γ = Cp/Cv = 1.400 for air.
      At 1 atm: K = 1.400 × 101325 ≈ 1.42 × 10⁵ Pa.
      FIRST_PRINCIPLES: from the adiabatic ideal gas law PV^γ = const.

      Density: ideal gas law ρ = PM/(RT), M = 0.02897 kg/mol (dry air).

      Color: transparent. Rayleigh scattering makes the sky blue but air
      itself is colorless in a single-node render.

      Restitution: not meaningful for a gas (no rigid collision).

    Args:
        T: temperature in K
        P: pressure in Pa
        sigma: σ-field value

    Returns:
        Material with viscosity_pa_s and bulk_modulus_pa set.
    """
    import math as _math

    # Viscosity from gas.py (N₂ as proxy for air, within ~3% of actual air)
    eta = gas_viscosity('N2', T=T, sigma=sigma) if HAS_DYNAMICS else 1.81e-5

    # Density from ideal gas law
    M_air = 0.02897  # kg/mol, dry air
    R_gas = 8.314462618
    rho = P * M_air / (R_gas * T)

    # Adiabatic bulk modulus K = γP (exact for ideal gas, adiabatic process)
    gamma = 1.400   # Cp/Cv for diatomic air; FIRST_PRINCIPLES (equipartition)
    K = gamma * P

    return Material(
        name=f'Dry air ({T:.0f} K, {P/1e3:.1f} kPa)',
        color=Vec3(1.0, 1.0, 1.0),         # transparent / colorless
        reflectance=0.0,
        roughness=1.0,
        opacity=0.0,                         # fully transparent
        ior=1.0003,                          # MEASURED: n_air ≈ 1 + 2.93e-4 at STP
        density_kg_m3=rho,
        mean_Z=7,                            # N₂ dominant: Z=7
        mean_A=14,                           # N₂: A=14
        composition='N₂ 78% + O₂ 21% + Ar 1%',
        alpha_r=0.0, alpha_g=0.0, alpha_b=0.0,
        viscosity_pa_s=eta,
        bulk_modulus_pa=K,
        restitution=0.0,                    # not meaningful for gas
        reference_temp_K=T,
    )
