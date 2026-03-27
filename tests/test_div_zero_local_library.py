"""
Div/Zero Stress Test — local_library

Every public function that takes numeric inputs is called with zero (or
near-zero) values.  The contract:

  - No ZeroDivisionError
  - No math domain errors (log of zero / negative)
  - No OverflowError
  - Returns a finite float, float('inf') with intent, or raises a
    clean, documented exception (not a bare Python arithmetic error)

Tests are grouped by file.  Any test that reveals a real gap is
documented with what the fix should be (SIGMA_FLOOR guard, n_points
guard, etc.).
"""

from __future__ import annotations

import math
import pytest

from sigma_ground.field.constants import (
    XI, ETA, SIGMA_0, SIGMA_FLOOR,
    G, C, HBAR, M_SUN_KG,
)

# ── helpers ───────────────────────────────────────────────────────────

EARTH_MASS   = 5.972e24   # kg
EARTH_RADIUS = 6.371e6    # m
PROTON_MASS  = 1.6726e-27 # kg


def _is_finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def _no_arithmetic_error(fn, *args, **kwargs):
    """Assert fn(*args) doesn't raise a bare arithmetic error."""
    try:
        result = fn(*args, **kwargs)
        return result
    except (ZeroDivisionError, ValueError, OverflowError) as e:
        pytest.fail(f"{fn.__name__}({args}, {kwargs}) raised {type(e).__name__}: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  scale.py
# ═══════════════════════════════════════════════════════════════════════

class TestScaleZeroInputs:
    """Tests for local_library/scale.py"""

    def setup_method(self):
        from sigma_ground.field.scale import (
            scale_ratio, lambda_eff, sigma_from_potential,
            schwarzschild_radius, sigma_at_event_horizon, sigma_conversion,
        )
        self.scale_ratio = scale_ratio
        self.lambda_eff = lambda_eff
        self.sigma_from_potential = sigma_from_potential
        self.schwarzschild_radius = schwarzschild_radius
        self.sigma_at_event_horizon = sigma_at_event_horizon
        self.sigma_conversion = sigma_conversion

    def test_scale_ratio_sigma_zero(self):
        """exp(0) = 1.0 — no division involved."""
        assert self.scale_ratio(0) == pytest.approx(1.0)

    def test_scale_ratio_sigma_floor(self):
        """SIGMA_FLOOR is a valid input."""
        r = self.scale_ratio(SIGMA_FLOOR)
        assert _is_finite(r)
        assert r == pytest.approx(1.0, rel=1e-50)

    def test_lambda_eff_sigma_zero(self):
        """Λ_eff(0) = Λ_QCD — no division."""
        r = _no_arithmetic_error(self.lambda_eff, 0)
        assert _is_finite(r)
        assert r > 0

    def test_sigma_from_potential_zero_radius(self):
        """r=0 is a coordinate singularity; must not raise ZeroDivisionError."""
        result = _no_arithmetic_error(self.sigma_from_potential, 0, EARTH_MASS)
        # Acceptable: float('inf') or SIGMA_FLOOR-clamped value — not a crash
        assert isinstance(result, float)

    def test_sigma_from_potential_zero_mass(self):
        """M=0 → no gravity → σ = 0."""
        result = _no_arithmetic_error(self.sigma_from_potential, EARTH_RADIUS, 0)
        assert result == pytest.approx(0.0, abs=SIGMA_FLOOR)

    def test_sigma_from_potential_both_zero(self):
        """r=0, M=0 — degenerate case, must not crash."""
        result = _no_arithmetic_error(self.sigma_from_potential, 0, 0)
        assert isinstance(result, float)

    def test_sigma_from_potential_sigma_floor_radius(self):
        """r = SIGMA_FLOOR (absurdly small but non-zero) should not crash."""
        result = _no_arithmetic_error(
            self.sigma_from_potential, SIGMA_FLOOR, EARTH_MASS
        )
        assert isinstance(result, float)

    def test_schwarzschild_radius_zero_mass(self):
        """r_s(0) = 0 — multiply by zero."""
        r = _no_arithmetic_error(self.schwarzschild_radius, 0)
        assert r == pytest.approx(0.0, abs=1e-40)

    def test_sigma_at_event_horizon_zero_mass(self):
        """σ at EH is XI/2 regardless of M — should be safe."""
        result = _no_arithmetic_error(self.sigma_at_event_horizon, 0)
        assert isinstance(result, float)

    def test_sigma_conversion_no_inputs(self):
        """sigma_conversion() has no arguments — just check it runs."""
        result = _no_arithmetic_error(self.sigma_conversion)
        assert _is_finite(result)
        assert result > 0


# ═══════════════════════════════════════════════════════════════════════
#  bounds.py
# ═══════════════════════════════════════════════════════════════════════

class TestBoundsZeroInputs:
    """Tests for local_library/bounds.py"""

    def setup_method(self):
        from sigma_ground.field.bounds import (
            check_sigma, clamp_sigma, check_eta, clamp_eta,
            check_radius, safe_sigma, safe_proton_mass, safe_neutron_mass,
        )
        self.check_sigma = check_sigma
        self.clamp_sigma = clamp_sigma
        self.check_eta = check_eta
        self.clamp_eta = clamp_eta
        self.check_radius = check_radius
        self.safe_sigma = safe_sigma
        self.safe_proton_mass = safe_proton_mass
        self.safe_neutron_mass = safe_neutron_mass

    def test_check_sigma_zero(self):
        result = _no_arithmetic_error(self.check_sigma, 0.0)
        assert 'status' in result

    def test_clamp_sigma_zero(self):
        result = _no_arithmetic_error(self.clamp_sigma, 0.0)
        assert _is_finite(result[0])

    def test_check_eta_zero(self):
        result = _no_arithmetic_error(self.check_eta, 0.0)
        assert 'status' in result

    def test_check_eta_none(self):
        """None eta should be handled gracefully."""
        result = _no_arithmetic_error(self.check_eta, None)
        assert 'status' in result

    def test_clamp_eta_zero(self):
        result = _no_arithmetic_error(self.clamp_eta, 0.0)
        assert _is_finite(result[0])

    def test_check_radius_zero(self):
        """r=0 is below Planck floor — should report as problematic, not crash."""
        result = _no_arithmetic_error(self.check_radius, 0.0)
        assert 'status' in result

    def test_safe_sigma_zero_radius(self):
        """safe_sigma is the guarded wrapper — must never crash."""
        result = _no_arithmetic_error(self.safe_sigma, 0.0, EARTH_MASS)
        assert isinstance(result, tuple)  # (sigma_or_None, check_dict)

    def test_safe_sigma_zero_mass(self):
        result = _no_arithmetic_error(self.safe_sigma, EARTH_RADIUS, 0.0)
        assert isinstance(result, tuple)

    def test_safe_proton_mass_sigma_zero(self):
        result = _no_arithmetic_error(self.safe_proton_mass, 0.0)
        value, _check = result
        assert _is_finite(value)
        assert value > 0

    def test_safe_neutron_mass_sigma_zero(self):
        result = _no_arithmetic_error(self.safe_neutron_mass, 0.0)
        value, _check = result
        assert _is_finite(value)
        assert value > 0


# ═══════════════════════════════════════════════════════════════════════
#  nucleon.py
# ═══════════════════════════════════════════════════════════════════════

class TestNucleonZeroInputs:
    """Tests for local_library/nucleon.py"""

    def setup_method(self):
        from sigma_ground.field.nucleon import proton_mass_mev, neutron_mass_mev
        self.proton_mass_mev = proton_mass_mev
        self.neutron_mass_mev = neutron_mass_mev

    def test_proton_mass_sigma_zero(self):
        """σ=0 is standard physics — proton mass = 938 MeV."""
        m = _no_arithmetic_error(self.proton_mass_mev, 0.0)
        assert m == pytest.approx(938.272, rel=1e-3)

    def test_proton_mass_sigma_floor(self):
        m = _no_arithmetic_error(self.proton_mass_mev, SIGMA_FLOOR)
        assert _is_finite(m)
        assert m > 0

    def test_neutron_mass_sigma_zero(self):
        m = _no_arithmetic_error(self.neutron_mass_mev, 0.0)
        assert m == pytest.approx(939.565, rel=1e-3)

    def test_neutron_mass_sigma_floor(self):
        m = _no_arithmetic_error(self.neutron_mass_mev, SIGMA_FLOOR)
        assert _is_finite(m)
        assert m > 0


# ═══════════════════════════════════════════════════════════════════════
#  binding.py
# ═══════════════════════════════════════════════════════════════════════

class TestBindingZeroInputs:
    """Tests for local_library/binding.py"""

    def setup_method(self):
        from sigma_ground.field.binding import coulomb_energy_mev, binding_energy_mev
        self.coulomb_energy_mev = coulomb_energy_mev
        self.binding_energy_mev = binding_energy_mev

    def test_coulomb_zero_Z(self):
        """Z=0 → neutral atom → no Coulomb energy."""
        result = _no_arithmetic_error(self.coulomb_energy_mev, 0, 1)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_coulomb_zero_A(self):
        """A=0 is unphysical — must not ZeroDivisionError (A^(1/3))."""
        result = _no_arithmetic_error(self.coulomb_energy_mev, 1, 0)
        assert isinstance(result, (int, float))

    def test_binding_zero_sigma(self):
        """σ=0 → standard binding energy unchanged."""
        # Carbon-12: Z=6, A=12, BE=92.16 MeV
        be = _no_arithmetic_error(self.binding_energy_mev, 92.16, 6, 12, 0.0)
        assert be == pytest.approx(92.16, rel=1e-4)

    def test_binding_sigma_floor(self):
        be = _no_arithmetic_error(self.binding_energy_mev, 92.16, 6, 12, SIGMA_FLOOR)
        assert _is_finite(be)

    def test_binding_zero_BE(self):
        """BE=0 is valid (unbound system)."""
        result = _no_arithmetic_error(self.binding_energy_mev, 0.0, 6, 12, 0.0)
        assert _is_finite(result)


# ═══════════════════════════════════════════════════════════════════════
#  interior.py
# ═══════════════════════════════════════════════════════════════════════

class TestInteriorZeroInputs:
    """Tests for local_library/interior.py"""

    def setup_method(self):
        from sigma_ground.field.interior import (
            enclosed_mass, sigma_at_radius, compute_profile,
        )
        self.enclosed_mass = enclosed_mass
        self.sigma_at_radius = sigma_at_radius
        self.compute_profile = compute_profile
        self.body = {
            'name': 'test',
            'mass_kg': EARTH_MASS,
            'radius_m': EARTH_RADIUS,
            'layers': [
                {'name': 'core',   'r_outer_m': 0.30 * EARTH_RADIUS, 'density_kg_m3': 12000},
                {'name': 'mantle', 'r_outer_m': 0.90 * EARTH_RADIUS, 'density_kg_m3': 4500},
                {'name': 'crust',  'r_outer_m': 1.00 * EARTH_RADIUS, 'density_kg_m3': 2700},
            ],
        }

    def test_enclosed_mass_zero_radius(self):
        """r=0 → no enclosed mass."""
        layers = self.body['layers']
        result = _no_arithmetic_error(
            self.enclosed_mass, 0.0, layers, EARTH_MASS
        )
        assert isinstance(result, (int, float))

    def test_sigma_at_radius_zero_radius(self):
        """r=0 at the centre — singularity guard needed."""
        layers = self.body['layers']
        result = _no_arithmetic_error(
            self.sigma_at_radius, 0.0, layers, EARTH_MASS
        )
        assert isinstance(result, float)

    def test_sigma_at_radius_sigma_floor(self):
        layers = self.body['layers']
        result = _no_arithmetic_error(
            self.sigma_at_radius, SIGMA_FLOOR, layers, EARTH_MASS
        )
        assert isinstance(result, float)

    def test_compute_profile_zero_n_points(self):
        """n_points=0 → i/n_points would ZeroDivide."""
        result = _no_arithmetic_error(self.compute_profile, self.body, 0)
        # Should return empty list or a single-point profile, not crash
        assert isinstance(result, list)

    def test_compute_profile_one_point(self):
        """n_points=1 is the minimum meaningful value."""
        result = _no_arithmetic_error(self.compute_profile, self.body, 1)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_compute_profile_zero_mass_body(self):
        """Body with M=0 — degenerate but must not crash."""
        zero_body = dict(self.body, mass_kg=0.0)
        result = _no_arithmetic_error(self.compute_profile, zero_body, 5)
        assert isinstance(result, list)

    def test_compute_profile_zero_radius_body(self):
        """Body with R=0 — degenerate but must not crash."""
        zero_body = dict(self.body, radius_m=0.0)
        result = _no_arithmetic_error(self.compute_profile, zero_body, 5)
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════
#  nesting.py
# ═══════════════════════════════════════════════════════════════════════

class TestNestingZeroInputs:
    """Tests for local_library/nesting.py"""

    def setup_method(self):
        from sigma_ground.field.nesting import level_mass_kg, level_count, level_properties
        self.level_mass_kg = level_mass_kg
        self.level_count = level_count
        self.level_properties = level_properties

    def test_level_mass_zero(self):
        """Level 0 is the Hubble mass — should be a large finite number."""
        result = _no_arithmetic_error(self.level_mass_kg, 0)
        assert _is_finite(result)
        assert result > 0

    def test_level_count_no_inputs(self):
        """level_count() is a constant — should always return a positive int."""
        result = _no_arithmetic_error(self.level_count)
        assert isinstance(result, int)
        assert result > 0

    def test_level_properties_zero(self):
        result = _no_arithmetic_error(self.level_properties, 0)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════
#  universe.py
# ═══════════════════════════════════════════════════════════════════════

class TestUniverseZeroInputs:
    """Tests for local_library/universe.py"""

    def setup_method(self):
        from sigma_ground.field.universe import Universe
        self.u = Universe()

    def test_at_radius_zero_radius(self):
        """r=0 → calls sigma_from_potential(0, M) → must not crash."""
        result = _no_arithmetic_error(self.u.at_radius, 0.0, EARTH_MASS)
        assert isinstance(result, dict)

    def test_at_radius_zero_mass(self):
        """M=0 → σ=0 everywhere — trivial but valid."""
        result = _no_arithmetic_error(self.u.at_radius, EARTH_RADIUS, 0.0)
        assert isinstance(result, dict)

    def test_at_radius_both_zero(self):
        result = _no_arithmetic_error(self.u.at_radius, 0.0, 0.0)
        assert isinstance(result, dict)

    def test_at_sigma_zero(self):
        """σ=0 is standard physics."""
        result = _no_arithmetic_error(self.u.at_sigma, 0.0)
        assert isinstance(result, dict)

    def test_at_sigma_floor(self):
        result = _no_arithmetic_error(self.u.at_sigma, SIGMA_FLOOR)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════
#  sandbox.py
# ═══════════════════════════════════════════════════════════════════════

class TestSandboxZeroInputs:
    """Tests for local_library/sandbox.py"""

    def setup_method(self):
        from sigma_ground.field.sandbox import Sandbox
        self.sb = Sandbox()

    def test_at_sigma_zero(self):
        """σ=0 is standard physics — proton mass = 938 MeV."""
        result = _no_arithmetic_error(self.sb.at_sigma, 'H-1', 0.0)
        assert isinstance(result, dict)

    def test_at_sigma_floor(self):
        result = _no_arithmetic_error(self.sb.at_sigma, 'H-1', SIGMA_FLOOR)
        assert isinstance(result, dict)

    def test_at_location_zero_radius(self):
        """r=0 → calls sigma_from_potential(0, M)."""
        result = _no_arithmetic_error(self.sb.at_location, 'H-1', 0.0, EARTH_MASS)
        assert isinstance(result, dict)

    def test_at_location_zero_mass(self):
        result = _no_arithmetic_error(self.sb.at_location, 'H-1', EARTH_RADIUS, 0.0)
        assert isinstance(result, dict)

    def test_sweep_zero_n_points(self):
        """n_points=0 → i/n_points → ZeroDivisionError without guard."""
        result = _no_arithmetic_error(self.sb.sweep, 'H-1', 0)
        assert isinstance(result, list)

    def test_sweep_one_point(self):
        """n_points=1 is the minimum non-degenerate sweep."""
        result = _no_arithmetic_error(self.sb.sweep, 'H-1', 1)
        assert isinstance(result, list)
        assert len(result) >= 1


# ═══════════════════════════════════════════════════════════════════════
#  entanglement.py
# ═══════════════════════════════════════════════════════════════════════

class TestEntanglementZeroInputs:
    """Tests for local_library/entanglement.py"""

    def setup_method(self):
        from sigma_ground.field.entanglement import (
            dark_energy_with_eta, sigma_coherence,
            decoherence_at_horizon, eta_scan, rendering_connectivity,
        )
        self.dark_energy_with_eta = dark_energy_with_eta
        self.sigma_coherence = sigma_coherence
        self.decoherence_at_horizon = decoherence_at_horizon
        self.eta_scan = eta_scan
        self.rendering_connectivity = rendering_connectivity

    def test_dark_energy_eta_zero(self):
        """η=0 → no entanglement → condensate = 0."""
        result = _no_arithmetic_error(self.dark_energy_with_eta, 0.0)
        assert isinstance(result, dict)

    def test_dark_energy_eta_floor(self):
        result = _no_arithmetic_error(self.dark_energy_with_eta, SIGMA_FLOOR)
        assert isinstance(result, dict)

    def test_sigma_coherence_zeros(self):
        """All-zero inputs — must not log(0) or divide."""
        result = _no_arithmetic_error(self.sigma_coherence, 0.0, 0.0)
        assert isinstance(result, (int, float))

    def test_sigma_coherence_floor(self):
        result = _no_arithmetic_error(self.sigma_coherence, SIGMA_FLOOR, SIGMA_FLOOR)
        assert isinstance(result, (int, float))

    def test_decoherence_eta_zero(self):
        """η=0 → entanglement_loss_rate=0 → t_page should be inf, not crash."""
        result = _no_arithmetic_error(self.decoherence_at_horizon, 0.0, M_SUN_KG)
        assert isinstance(result, dict)
        assert result.get('t_page_s') == float('inf') or math.isfinite(result.get('t_page_s', 0))

    def test_decoherence_zero_mass(self):
        """M=0 BH — degenerate; must not crash."""
        result = _no_arithmetic_error(self.decoherence_at_horizon, ETA, 0.0)
        assert isinstance(result, dict)

    def test_eta_scan_zero_n_points(self):
        """n_points=0 → i/n_points → ZeroDivisionError without guard."""
        result = _no_arithmetic_error(self.eta_scan, 0)
        assert isinstance(result, list)

    def test_eta_scan_one_point(self):
        result = _no_arithmetic_error(self.eta_scan, 1)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_rendering_connectivity_zero(self):
        """η=0 → no rendering connectivity."""
        result = _no_arithmetic_error(self.rendering_connectivity, 0.0)
        assert isinstance(result, dict)

    def test_rendering_connectivity_floor(self):
        result = _no_arithmetic_error(self.rendering_connectivity, SIGMA_FLOOR)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════
#  shape_budget.py
# ═══════════════════════════════════════════════════════════════════════

class TestShapeBudgetZeroInputs:
    """Tests for local_library/shape_budget.py"""

    def setup_method(self):
        from sigma_ground.field.shape_budget import (
            quality_multiplier, shape_budget, shape_budget_for_body,
        )
        self.quality_multiplier = quality_multiplier
        self.shape_budget = shape_budget
        self.shape_budget_for_body = shape_budget_for_body

    def test_quality_multiplier_sigma_zero(self):
        result = _no_arithmetic_error(self.quality_multiplier, 0.0)
        assert _is_finite(result)
        assert result >= 0

    def test_quality_multiplier_sigma_floor(self):
        result = _no_arithmetic_error(self.quality_multiplier, SIGMA_FLOOR)
        assert _is_finite(result)

    def test_shape_budget_zero_sigma(self):
        result = _no_arithmetic_error(self.shape_budget, 0.0, 100, 3000)
        assert isinstance(result, int)
        assert result > 0

    def test_shape_budget_zero_pixels(self):
        """apparent_px=0 → size_factor collapses to 0."""
        result = _no_arithmetic_error(self.shape_budget, 7e-10, 0, 3000)
        assert isinstance(result, int)
        assert result > 0  # floor at S_BASE must hold

    def test_shape_budget_zero_density(self):
        """density=0 → log10(0) without the max(1, ...) guard would crash."""
        result = _no_arithmetic_error(self.shape_budget, 7e-10, 100, 0.0)
        assert isinstance(result, int)
        assert result > 0

    def test_shape_budget_all_zeros(self):
        result = _no_arithmetic_error(self.shape_budget, 0.0, 0, 0.0)
        assert isinstance(result, int)
        assert result > 0  # floor at S_BASE

    def test_shape_budget_for_body_zero_radius(self):
        """r=0 → calls sigma_from_potential(0, M) internally."""
        result = _no_arithmetic_error(
            self.shape_budget_for_body, EARTH_MASS, 0.0, 5515, 200
        )
        assert isinstance(result, dict)
        assert isinstance(result['budget'], int)

    def test_shape_budget_for_body_zero_mass(self):
        result = _no_arithmetic_error(
            self.shape_budget_for_body, 0.0, EARTH_RADIUS, 5515, 200
        )
        assert isinstance(result, dict)
        assert isinstance(result['budget'], int)


# ═══════════════════════════════════════════════════════════════════════
#  quarksum integration — compute_physics with zero radius
# ═══════════════════════════════════════════════════════════════════════

class TestQuarksumPhysicsZeroInputs:
    """compute_physics / compute_tangle with degenerate inputs."""

    def setup_method(self):
        from sigma_ground.inventory.builder import load_structure
        from sigma_ground.inventory.physics import compute_physics, compute_tangle
        self.load_structure = load_structure
        self.compute_physics = compute_physics
        self.compute_tangle = compute_tangle

    def test_compute_physics_zero_radius(self):
        """radius_m=0 must not crash — geometry fields should be None or 0."""
        s = self.load_structure("earth_with_moon")
        result = _no_arithmetic_error(self.compute_physics, s, radius_m=0.0)
        assert isinstance(result, dict)

    def test_compute_physics_no_radius(self):
        """No radius_m passed — geometry skipped gracefully."""
        s = self.load_structure("bronze_cube")
        result = _no_arithmetic_error(self.compute_physics, s)
        assert isinstance(result, dict)
        assert result["v_escape_m_s"] is None

    def test_compute_physics_zero_temperature(self):
        """temperature_k=0 → thermal energy = 0, not a div/zero."""
        s = self.load_structure("hydrogen_atom")
        result = _no_arithmetic_error(self.compute_physics, s,
                                      radius_m=5.29e-11, temperature_k=0.0)
        assert isinstance(result, dict)
        # Thermal energy at 0 K should be 0 or very small
        te = result.get("thermal_energy_J", 0)
        assert te == pytest.approx(0.0, abs=1e-50) or te >= 0

    def test_compute_tangle_full_illumination(self):
        """Standard tangle — regression guard."""
        s = self.load_structure("hydrogen_atom")
        result = _no_arithmetic_error(self.compute_tangle, s, illumination_fraction=1.0)
        assert result["eta"] == pytest.approx(ETA, rel=1e-6)

    def test_compute_tangle_zero_illumination(self):
        """illumination_fraction=0 → N_observer_tangle = 0."""
        s = self.load_structure("hydrogen_atom")
        result = _no_arithmetic_error(self.compute_tangle, s, illumination_fraction=0.0)
        assert result["N_observer_tangle"] == pytest.approx(0.0, abs=1e-10)
        assert result["tangle_fraction"] == pytest.approx(0.0, abs=1e-10)
