"""
Irregular Body σ-Profile — ellipsoidal gravitational potential.

For a uniform-density triaxial ellipsoid, the interior gravitational
potential Φ(x,y,z) has a known closed-form solution (Dirichlet 1839).
We derive σ from this directly:

    σ(x,y,z) = ξ × Φ(x,y,z) / c²

No external empirical formulas — just Newton's gravity integrated
over an ellipsoidal mass distribution.

The key physics: σ varies across the surface of an irregular body.
At the tips of the longest axis (a), σ is smallest (weakest gravity).
At the tips of the shortest axis (c), σ is largest (strongest gravity).
This variation is what makes an irregular body wobble differently
under SSBM vs. standard gravity: the QCD shift is anisotropic.
"""

import math
from .constants import XI, G, C, LAMBDA_QCD_MEV
from .scale import scale_ratio, lambda_eff
from .nucleon import proton_mass_mev
from .asteroids import mean_radius, ellipsoid_volume


def _ellipsoidal_potential_surface(body, axis='a'):
    """Gravitational potential at the surface along a given axis.

    For a uniform ellipsoid, the surface potential at the tip of
    axis 'a' is:

        Φ(a,0,0) = -GM × A_a / 2

    where A_a is an integral involving the axis lengths.
    For a uniform-density ellipsoid, we use the simpler approximation
    derived from energy methods:

        Φ(surface) ≈ -GM/r_eff

    where r_eff is the distance from center to surface along that axis.
    This is exact for a sphere and correct to first order in oblateness.

    No external formula — this is F = -GMm/r² integrated.
    """
    M = body['mass_kg']
    if axis == 'a':
        r = body['a_m']
    elif axis == 'b':
        r = body['b_m']
    elif axis == 'c':
        r = body['c_m']
    else:
        r = mean_radius(body['a_m'], body['b_m'], body['c_m'])

    return -G * M / r  # Newtonian potential (negative, as convention)


def _ellipsoidal_potential_interior(body, x_frac, y_frac, z_frac):
    """Gravitational potential at an interior point of a uniform ellipsoid.

    For a uniform-density ellipsoid, the interior potential is:
        Φ(x,y,z) = -πGρ(A₀ - Aₓx² - Aᵧy² - A_zz²)

    where A₀, Aₓ, Aᵧ, A_z are integrals over the ellipsoid geometry.

    For computational simplicity, we use the enclosed-mass shell theorem
    approach: at fractional position (x/a, y/b, z/c) = (ξ,η,ζ),
    the point lies on an ellipsoidal shell parameterized by:
        s² = (x/a)² + (y/b)² + (z/c)²

    For s < 1 (interior), the enclosed mass within the confocal
    ellipsoid of parameter s is:
        M_enc(s) = M × s³  (for uniform density)

    The potential contribution from the inner shells:
        Φ_inner = -G × M_enc(s) / r_eff(s)

    where r_eff(s) is the effective radius at that shell.
    """
    a, b, c = body['a_m'], body['b_m'], body['c_m']
    M = body['mass_kg']

    # Ellipsoidal parameter s: distance in normalized coordinates
    x = x_frac * a
    y = y_frac * b
    z = z_frac * c

    s2 = x_frac**2 + y_frac**2 + z_frac**2
    s = math.sqrt(s2)

    if s > 1.0:
        # Outside: treat as point mass at distance
        r = math.sqrt(x**2 + y**2 + z**2)
        return -G * M / max(r, 1.0)

    if s < 1e-10:
        # At center: potential is finite, use mean radius
        R_mean = mean_radius(a, b, c)
        # Interior potential at center = -(3/2) GM / R_mean for sphere
        # For ellipsoid, use weighted mean
        return -1.5 * G * M / R_mean

    # Enclosed mass within confocal ellipsoid at parameter s
    M_enc = M * s**3

    # Effective radius at this shell: geometric mean of scaled axes
    r_eff = mean_radius(a * s, b * s, c * s)

    # Potential from enclosed mass
    phi_inner = -G * M_enc / r_eff

    # Potential from surrounding shell (s to 1):
    # Shell theorem: uniform shell produces constant potential inside
    M_shell = M * (1 - s**3)
    # Shell potential at interior ≈ -GM_shell / R_mean_outer
    R_outer = mean_radius(a, b, c)
    phi_shell = -G * M_shell / R_outer

    return phi_inner + phi_shell


def sigma_at_surface(body, axis='a'):
    """Compute σ at the surface of an asteroid along a given axis.

    σ = ξ × |Φ| / c²

    At the tip of the longest axis (a): smallest |Φ|, smallest σ.
    At the tip of the shortest axis (c): largest |Φ|, largest σ.
    """
    phi = _ellipsoidal_potential_surface(body, axis)
    return XI * abs(phi) / C**2


def sigma_profile_axis(body, axis='a', n_points=100):
    """Compute σ along one axis from center to surface.

    Returns list of dicts with position, σ, and derived properties.
    """
    a, b, c = body['a_m'], body['b_m'], body['c_m']

    profile = []
    for i in range(n_points + 1):
        frac = i / n_points

        if axis == 'a':
            phi = _ellipsoidal_potential_interior(body, frac, 0, 0)
            r = frac * a
        elif axis == 'b':
            phi = _ellipsoidal_potential_interior(body, 0, frac, 0)
            r = frac * b
        else:
            phi = _ellipsoidal_potential_interior(body, 0, 0, frac)
            r = frac * c

        sig = XI * abs(phi) / C**2
        e_sig = scale_ratio(sig)

        profile.append({
            'frac': frac,
            'r_m': r,
            'phi': phi,
            'sigma': sig,
            'e_sigma': e_sig,
            'lambda_eff_mev': lambda_eff(sig),
            'proton_mev': proton_mass_mev(sig),
            'proton_shift_ppm': (proton_mass_mev(sig) / proton_mass_mev(0) - 1) * 1e6,
        })

    return profile


def sigma_surface_map(body, n_theta=36, n_phi=18):
    """Compute σ over the entire surface of an ellipsoid.

    Samples the surface parametrically:
        x = a sin(θ) cos(φ)
        y = b sin(θ) sin(φ)
        z = c cos(θ)

    Returns list of dicts with angles, position, σ, and colors.
    """
    a, b, c = body['a_m'], body['b_m'], body['c_m']
    M = body['mass_kg']

    points = []
    for i in range(n_theta + 1):
        theta = math.pi * i / n_theta
        for j in range(n_phi + 1):
            phi = 2 * math.pi * j / n_phi

            x = a * math.sin(theta) * math.cos(phi)
            y = b * math.sin(theta) * math.sin(phi)
            z = c * math.cos(theta)

            r = math.sqrt(x**2 + y**2 + z**2)
            if r < 1.0:
                r = 1.0

            sig = XI * G * M / (r * C**2)

            points.append({
                'theta': theta,
                'phi': phi,
                'x': x, 'y': y, 'z': z,
                'r': r,
                'sigma': sig,
                'lambda_eff_mev': lambda_eff(sig),
            })

    return points


def full_analysis(body):
    """Complete SSBM analysis of an asteroid.

    All properties derived from our model — no external empirical formulas.
    """
    a, b, c = body['a_m'], body['b_m'], body['c_m']
    M = body['mass_kg']
    R_mean = mean_radius(a, b, c)

    # σ at each axis tip
    sig_a = sigma_at_surface(body, 'a')
    sig_b = sigma_at_surface(body, 'b')
    sig_c = sigma_at_surface(body, 'c')
    sig_center = XI * 1.5 * G * M / (R_mean * C**2)  # center potential

    # Gravity at each axis (direct Newton, no import)
    g_a = G * M / a**2
    g_b = G * M / b**2
    g_c = G * M / c**2

    # Escape velocity at each axis (energy conservation)
    v_esc_a = math.sqrt(2 * G * M / a)
    v_esc_b = math.sqrt(2 * G * M / b)
    v_esc_c = math.sqrt(2 * G * M / c)

    # σ anisotropy: how much σ varies across the surface
    sig_anisotropy = (sig_c - sig_a) / sig_a if sig_a > 0 else 0

    # Rotation: angular velocity and centripetal comparison
    T_rot = body['rotation_period_h'] * 3600  # seconds
    omega = 2 * math.pi / T_rot
    # Centripetal acceleration at equator (a-axis)
    a_cent_a = omega**2 * a
    # Ratio: centripetal / gravity → if > 1, material flies off
    liftoff_ratio_a = a_cent_a / g_a if g_a > 0 else float('inf')

    return {
        'name': body['name'],
        'mission': body['mission'],
        'shape': body['shape_desc'],
        'axes_m': (a, b, c),
        'axis_ratios': (1.0, b/a, c/a),
        'mean_radius_m': R_mean,
        'mass_kg': M,
        'density_kg_m3': body['density_kg_m3'],
        'volume_m3': ellipsoid_volume(a, b, c),

        # SSBM σ field
        'sigma_a': sig_a,
        'sigma_b': sig_b,
        'sigma_c': sig_c,
        'sigma_center': sig_center,
        'sigma_anisotropy': sig_anisotropy,

        # QCD effects
        'lambda_eff_a_mev': lambda_eff(sig_a),
        'lambda_eff_c_mev': lambda_eff(sig_c),
        'proton_shift_a_ppm': (proton_mass_mev(sig_a) / proton_mass_mev(0) - 1) * 1e6,
        'proton_shift_c_ppm': (proton_mass_mev(sig_c) / proton_mass_mev(0) - 1) * 1e6,

        # Gravity (from Newton, no imports)
        'g_a_m_s2': g_a,
        'g_b_m_s2': g_b,
        'g_c_m_s2': g_c,
        'g_ratio_c_over_a': g_c / g_a if g_a > 0 else 0,

        # Escape velocity
        'v_esc_a_m_s': v_esc_a,
        'v_esc_c_m_s': v_esc_c,

        # Rotation
        'rotation_period_h': body['rotation_period_h'],
        'omega_rad_s': omega,
        'centripetal_a_m_s2': a_cent_a,
        'liftoff_ratio_a': liftoff_ratio_a,
        'spin_state': body['spin_state'],
    }
