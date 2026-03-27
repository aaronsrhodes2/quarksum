"""Behavioral computations for subatomic particles (electrons, protons, neutrons).

Returns intrinsic/operable dict for any Particle subclass.
Environment resolution handles energy, magnetic field, and momentum stimuli.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sigma_ground.inventory.core.constants import CONSTANTS

if TYPE_CHECKING:
    from sigma_ground.inventory.models.particle import Particle

_PARTICLE_VALID_KEYS = {"energy_ev", "magnetic_field_t", "momentum_gev"}


def compute_particle_behaviors(particle: Particle) -> dict:
    """Compute behaviors for a subatomic particle.

    Returns a dict with ``intrinsic``, ``operable``, ``children``,
    and identifying metadata.
    """
    from sigma_ground.inventory.behaviors import extract_fields

    intrinsic_fields, operable_fields = extract_fields(particle)

    children = {
        "quarks": len(particle.quarks),
        "gluons": len(particle.gluons),
        "sea_quarks": len(particle.sea_quarks),
    }

    return {
        "entity_type": "particle",
        "particle_type": particle.particle_type,
        "symbol": particle.symbol,
        "rest_mass_kg": particle.rest_mass_kg,
        "charge_e": particle.charge_e,
        "intrinsic": intrinsic_fields,
        "operable": operable_fields,
        "children": children,
    }


def resolve_particle_env(particle: Particle, env: dict, mode: str = "delta") -> dict:
    """Apply environment values to a particle and return updated behaviors."""
    bad_keys = set(env) - _PARTICLE_VALID_KEYS
    if bad_keys:
        raise ValueError(
            f"Invalid particle environment keys: {bad_keys}. "
            f"Valid keys: {sorted(_PARTICLE_VALID_KEYS)}"
        )

    applied: list[dict] = []

    if "energy_ev" in env:
        E = env["energy_ev"]
        from sigma_ground.inventory.models.particle import Electron
        if isinstance(particle, Electron):
            old_n = particle.principal_n
            if mode == "delta" and E > 0:
                target_n = old_n + 1
                while target_n <= 7:
                    E_transition = CONSTANTS.E_rydberg_ev * (
                        1.0 / old_n**2 - 1.0 / target_n**2
                    )
                    if E >= E_transition * 0.95:
                        particle.principal_n = target_n
                        l_labels = "spdfghij"
                        l_val = min(target_n - 1, particle.angular_l)
                        particle.angular_l = l_val
                        particle.orbital_name = (
                            f"{target_n}{l_labels[l_val] if l_val < len(l_labels) else '?'}"
                        )
                        break
                    target_n += 1
            elif mode == "update":
                particle.energy_level = E
        applied.append({
            "key": "energy_ev", "mode": mode, "value": E,
            "consequence": (
                f"principal_n: {old_n} -> {particle.principal_n}"
                if isinstance(particle, Electron) else "energy_level adjusted"
            ),
        })

    if "magnetic_field_t" in env:
        B = env["magnetic_field_t"]
        old_spin = particle.spin_projection
        g_factor = particle.magnetic_moment / CONSTANTS.mu_B if CONSTANTS.mu_B else 1.0
        delta_E = abs(g_factor) * CONSTANTS.mu_B * abs(B)
        particle.spin_projection = -old_spin
        applied.append({
            "key": "magnetic_field_t", "mode": mode, "value": B,
            "consequence": (
                f"spin_projection: {old_spin} -> {particle.spin_projection} "
                f"(Zeeman delta_E={delta_E:.3e} J)"
            ),
        })

    if "momentum_gev" in env:
        p_gev = env["momentum_gev"]
        if mode == "delta":
            p_gev_abs = abs(p_gev)
        else:
            p_gev_abs = p_gev
        m_kg = particle.rest_mass_kg
        p_kg_m_s = p_gev_abs * 1e9 * CONSTANTS.e / CONSTANTS.c
        KE_J = math.sqrt((p_kg_m_s * CONSTANTS.c)**2 + (m_kg * CONSTANTS.c_squared)**2) - m_kg * CONSTANTS.c_squared
        KE_eV = KE_J / CONSTANTS.e
        old_e = particle.energy_level
        if mode == "delta":
            particle.energy_level = old_e + KE_eV
        else:
            particle.energy_level = KE_eV
        applied.append({
            "key": "momentum_gev", "mode": mode, "value": p_gev,
            "consequence": f"energy_level: {old_e:.3f} -> {particle.energy_level:.3f} eV",
        })

    result = compute_particle_behaviors(particle)
    result["applied"] = applied
    return result
