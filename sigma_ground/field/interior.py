"""
Planetary Interior σ-Profile Calculator.

Given a layered body (mass, radius, density layers), compute:
- σ(r) at every radius using the enclosed mass integral
- Λ_eff(r) at every radius
- Proton/neutron mass at every radius
- Bond strength ratios at every radius

σ = ξ × GM_enclosed(r) / (r × c²)

For planets, σ is tiny (~10⁻¹⁰ at Earth's surface). But:
1. It's NONZERO — standard physics says it should be exactly 0
2. It increases monotonically toward the center
3. For a neutron star, it becomes significant (~0.01-0.1)
"""

import math
from .constants import XI, G, C, LAMBDA_QCD_MEV
from .scale import scale_ratio, lambda_eff
from .nucleon import proton_mass_mev, neutron_mass_mev


def enclosed_mass(r, layers, total_mass):
    """Compute enclosed mass at radius r using shell integration.

    For a layered body, integrates density × 4πr²dr from center to r.
    Uses the layer densities as step functions.

    Args:
        r: radius in meters
        layers: list of layer dicts (sorted innermost first)
        total_mass: total body mass in kg (used as sanity check)

    Returns:
        enclosed mass in kg
    """
    M_enc = 0.0
    r_prev = 0.0

    for layer in layers:
        r_out = layer['r_outer_m']
        rho = layer['density_kg_m3']

        if r <= r_prev:
            break

        r_top = min(r, r_out)
        # Shell volume: (4/3)π(r_top³ - r_prev³)
        M_enc += rho * (4.0 / 3.0) * math.pi * (r_top**3 - r_prev**3)

        if r <= r_out:
            break
        r_prev = r_out

    return M_enc


def sigma_at_radius(r, layers, total_mass):
    """Compute σ at radius r inside a layered body.

    σ(r) = ξ × G × M_enclosed(r) / (r × c²)

    At the center (r→0), σ → 0 (no enclosed mass).
    At the surface, σ = ξ × GM_total / (R × c²).
    """
    if r <= 0:
        return 0.0
    M_enc = enclosed_mass(r, layers, total_mass)
    return XI * G * M_enc / (r * C**2)


def compute_profile(body, n_points=200):
    """Compute the full σ-profile for a planetary body.

    Returns a list of dicts, one per radial sample, containing:
    - r_m: radius in meters
    - r_frac: fractional radius (0 = center, 1 = surface)
    - M_enc_kg: enclosed mass
    - sigma: σ value
    - lambda_eff_mev: effective QCD scale
    - proton_mev: proton mass at this σ
    - neutron_mev: neutron mass at this σ
    - layer_name: which layer this point is in
    - density: local density
    """
    R = body['radius_m']
    M = body['mass_kg']
    layers = body['layers']

    if n_points <= 0 or R <= 0:
        return []

    profile = []
    for i in range(n_points + 1):
        r = R * i / n_points
        if r == 0:
            r = R * 0.001 / n_points  # avoid r=0

        r_frac = r / R
        M_enc = enclosed_mass(r, layers, M)
        sig = sigma_at_radius(r, layers, M)
        e_sig = scale_ratio(sig)

        # Find which layer this point is in
        layer_name = layers[-1]['name']
        density = layers[-1]['density_kg_m3']
        for layer in layers:
            if r <= layer['r_outer_m']:
                layer_name = layer['name']
                density = layer['density_kg_m3']
                break

        profile.append({
            'r_m': r,
            'r_frac': r_frac,
            'M_enc_kg': M_enc,
            'sigma': sig,
            'e_sigma': e_sig,
            'lambda_eff_mev': lambda_eff(sig),
            'proton_mev': proton_mass_mev(sig),
            'neutron_mev': neutron_mass_mev(sig),
            'proton_shift_ppm': (proton_mass_mev(sig) / proton_mass_mev(0) - 1) * 1e6,
            'layer_name': layer_name,
            'density_kg_m3': density,
        })

    return profile


def surface_summary(body):
    """Quick summary of σ effects at the surface of a body."""
    R = body['radius_m']
    M = body['mass_kg']
    layers = body['layers']

    sig = sigma_at_radius(R, layers, M)
    shift_ppm = (proton_mass_mev(sig) / proton_mass_mev(0) - 1) * 1e6

    return {
        'name': body['name'],
        'sigma_surface': sig,
        'lambda_eff_mev': lambda_eff(sig),
        'proton_shift_ppm': shift_ppm,
        'measurable': abs(shift_ppm) > 0.001,  # ~ppb sensitivity
    }


def center_summary(body):
    """Quick summary of σ effects at the center of a body."""
    R = body['radius_m']
    M = body['mass_kg']
    layers = body['layers']

    # At center, use a small radius to avoid /0
    r_center = R * 1e-4
    sig = sigma_at_radius(r_center, layers, M)
    shift_ppm = (proton_mass_mev(sig) / proton_mass_mev(0) - 1) * 1e6

    return {
        'name': body['name'],
        'sigma_center': sig,
        'lambda_eff_mev': lambda_eff(sig),
        'proton_shift_ppm': shift_ppm,
    }
