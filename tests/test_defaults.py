"""
Tests for quarksum default loads, physics derivation, and observer tangle.

All 9 default loads must:
  - Load without error
  - Resolve to the correct stated_mass_kg
  - Produce a valid particle inventory
  - Pass compute_physics with their canonical radius

Physics derivation tests verify:
  - All quantities are derived from loaded matter (no hardcoded numbers)
  - Escape velocity matches known values
  - σ-field at surface is negative (deeper than cosmic background)
  - Observer tangle = eta * N_particles * illumination_fraction
  - tangle_fraction is always in [0, 1]
  - QCD binding fraction ≈ 99% for all baryonic matter

Defaults registry tests:
  - All 9 loads present
  - Registry is immutable (NamedTuple in tuple)
  - DEFAULT_ID is 'earth_with_moon'
  - by_id() finds by id
  - default_load() returns earth_with_moon
"""

import math
import pytest

from sigma_ground.field.constants import ETA
from sigma_ground.inventory.builder import load_structure
from sigma_ground.inventory.defaults import (
    LOADS, DEFAULT_ID, default_load, by_id, DefaultLoad
)
from sigma_ground.inventory.physics import compute_physics, compute_tangle


# ── Registry tests ─────────────────────────────────────────────────────────

class TestDefaultRegistry:
    def test_nine_loads_present(self):
        assert len(LOADS) == 9

    def test_all_loads_are_named_tuples(self):
        for load in LOADS:
            assert isinstance(load, DefaultLoad)

    def test_loads_tuple_is_immutable(self):
        with pytest.raises((TypeError, AttributeError)):
            LOADS[0] = None  # type: ignore

    def test_default_is_earth_with_moon(self):
        assert DEFAULT_ID == "earth_with_moon"

    def test_default_load_function(self):
        d = default_load()
        assert d.id == "earth_with_moon"
        assert "earth" in d.name.lower()
        assert "moon" in d.name.lower()

    def test_default_message_is_fun(self):
        d = default_load()
        assert "earth" in d.message.lower()
        assert "moon" in d.message.lower()
        assert len(d.message) > 10

    def test_by_id_known(self):
        result = by_id("hydrogen_atom")
        assert result is not None
        assert result.id == "hydrogen_atom"

    def test_by_id_unknown(self):
        assert by_id("not_a_real_thing") is None

    def test_all_ids_unique(self):
        ids = [l.id for l in LOADS]
        assert len(ids) == len(set(ids))

    def test_all_names_unique(self):
        names = [l.name for l in LOADS]
        assert len(names) == len(set(names))

    def test_radii_have_correct_scale(self):
        radii = {l.id: l.radius_m for l in LOADS if l.radius_m is not None}
        # Universe > galaxy > solar system > Earth > iceberg > apple > cube > molecule > atom
        assert radii["universe"]         > radii["milky_way"]
        assert radii["milky_way"]        > radii["sol_solar_system"]
        assert radii["sol_solar_system"] > radii["earth_with_moon"]
        assert radii["earth_with_moon"]  > radii["iceberg_in_ocean"]
        assert radii["iceberg_in_ocean"] > radii["apple_on_table"]
        # apple (~38mm) and bronze_cube (~87mm circumradius) are both cm-scale — no ordering required
        assert radii["bronze_cube"]      > radii["water_molecule"]
        assert radii["water_molecule"]   > radii["hydrogen_atom"]

    def test_all_messages_non_empty(self):
        for load in LOADS:
            assert isinstance(load.message, str) and len(load.message) > 5

    def test_order_largest_to_smallest(self):
        """Universe is first, hydrogen atom is last."""
        assert LOADS[0].id == "universe"
        assert LOADS[-1].id == "hydrogen_atom"


# ── Default load tests ─────────────────────────────────────────────────────

EXPECTED_MASSES = {
    "universe":         1.5e53,
    "milky_way":        1.19e41,
    "sol_solar_system": 1.991077989796853e30,
    "earth_with_moon":  6.046588e24,
    "iceberg_in_ocean": 1.0e11,
    "apple_on_table":   5.182,
    "bronze_cube":      8.8,
    "water_molecule":   2.9907e-26,
    "hydrogen_atom":    1.6736e-27,
}

@pytest.mark.parametrize("load_id", [l.id for l in LOADS])
class TestAllDefaultsLoad:
    def test_loads_without_error(self, load_id):
        structure = load_structure(load_id)
        assert structure is not None

    def test_mass_matches_stated(self, load_id):
        structure = load_structure(load_id)
        expected = EXPECTED_MASSES[load_id]
        # Allow 1% tolerance (thickness/density ratio approximation)
        assert abs(structure.resolved_mass_kg - expected) / expected < 0.01

    def test_has_molecules(self, load_id):
        structure = load_structure(load_id)
        # At least the root or a child should have molecules
        def has_molecules(s):
            if s.molecules:
                return True
            return any(has_molecules(c) for c in s.children)
        assert has_molecules(structure)

    def test_particle_inventory_runs(self, load_id):
        from sigma_ground.inventory.checksum.particle_inventory import compute_particle_inventory
        structure = load_structure(load_id)
        inv = compute_particle_inventory(structure)
        assert inv["protons"] > 0
        assert inv["electrons"] > 0

    def test_stoq_runs(self, load_id):
        from sigma_ground.inventory.checksum.stoq_checksum import compute_stoq_checksum
        structure = load_structure(load_id)
        result = compute_stoq_checksum(structure)
        assert "reconstructed_mass_kg" in result
        assert "mass_defect_percent" in result


# ── Physics derivation tests ──────────────────────────────────────────────

class TestComputePhysics:
    @pytest.fixture
    def earth_moon(self):
        s = load_structure("earth_with_moon")
        return compute_physics(s, radius_m=6.371e6)

    @pytest.fixture
    def hydrogen(self):
        s = load_structure("hydrogen_atom")
        return compute_physics(s, radius_m=5.29e-11)

    def test_mass_matches_structure(self, earth_moon):
        s = load_structure("earth_with_moon")
        assert earth_moon["total_mass_kg"] == s.resolved_mass_kg

    def test_particle_counts_positive(self, earth_moon):
        assert earth_moon["N_protons"]   > 0
        assert earth_moon["N_neutrons"]  > 0
        assert earth_moon["N_electrons"] > 0
        assert earth_moon["N_baryons"]   > 0

    def test_N_particles_equals_sum(self, earth_moon):
        expected = earth_moon["N_protons"] + earth_moon["N_neutrons"] + earth_moon["N_electrons"]
        assert earth_moon["N_particles_total"] == expected

    def test_GM_correct_units(self, earth_moon):
        # GM for Earth ≈ 3.986e14 m³/s²; Earth+Moon slightly larger
        GM = earth_moon["GM_m3_s2"]
        assert 3.9e14 < GM < 4.1e14, f"GM out of range: {GM:.4e}"

    def test_v_escape_reasonable(self, earth_moon):
        # Earth surface escape velocity = 11.186 km/s; Earth+Moon total slightly higher
        v = earth_moon["v_escape_m_s"]
        assert 11_000 < v < 12_000, f"v_escape out of range: {v:.1f} m/s"

    def test_sigma_surface_negative(self, earth_moon):
        # σ is always negative at the surface (gravitational well)
        assert earth_moon["sigma_surface"] < 0

    def test_sigma_effective_less_negative(self, earth_moon):
        # Entanglement pulls σ toward 0 (cosmic mean)
        s_raw = earth_moon["sigma_surface"]
        s_eff = earth_moon["sigma_effective"]
        # Both negative; effective is closer to 0
        assert s_raw < s_eff < 0

    def test_eta_is_ssbm_constant(self, earth_moon):
        assert earth_moon["eta"] == ETA

    def test_N_entangled_cosmic_proportional_to_eta(self, earth_moon):
        ratio = earth_moon["N_entangled_cosmic"] / earth_moon["N_particles_total"]
        assert abs(ratio - ETA) < 1e-10

    def test_observer_tangle_full_illumination(self, earth_moon):
        # With illumination=1.0 (default), tangle = eta * N_total
        assert abs(earth_moon["tangle_fraction"] - ETA) < 1e-10
        expected_tangle = ETA * earth_moon["N_particles_total"]
        assert abs(earth_moon["N_observer_tangle"] - expected_tangle) < 1

    def test_tangle_fraction_in_range(self, earth_moon):
        assert 0 <= earth_moon["tangle_fraction"] <= 1

    def test_qcd_binding_fraction_high(self, earth_moon):
        # QCD binding is ~99% of nucleon mass
        assert earth_moon["qcd_binding_fraction"] > 0.98

    def test_no_radius_skips_geometry(self):
        s = load_structure("bronze_cube")
        phys = compute_physics(s)  # no radius_m
        assert phys["v_escape_m_s"]    is None
        assert phys["sigma_surface"]   is None
        assert phys["sigma_effective"] is None
        assert phys["radius_m"]        is None

    def test_hydrogen_atom_counts(self, hydrogen):
        # H atom: 1 proton, 0 neutrons (bare proton), 1 electron
        # But quarksum works with ~N_A hydrogen atoms per stated_mass_kg
        # Just verify the ratios
        assert hydrogen["N_protons"] > 0
        # For H, electrons ≈ protons (neutral)
        ratio_pe = hydrogen["N_protons"] / hydrogen["N_electrons"]
        assert 0.8 < ratio_pe < 1.2  # protons ≈ electrons

    def test_thermal_energy_scales_with_baryons(self):
        """More baryons → more thermal energy at same temperature."""
        s_big = load_structure("earth_with_moon")
        s_small = load_structure("hydrogen_atom")
        big = compute_physics(s_big, temperature_k=300.0)
        small = compute_physics(s_small, temperature_k=300.0)
        assert big["thermal_energy_J"] > small["thermal_energy_J"]


# ── Tangle-specific tests ─────────────────────────────────────────────────

class TestComputeTangle:
    def test_tangle_full_illumination(self):
        s = load_structure("bronze_cube")
        t = compute_tangle(s, illumination_fraction=1.0)
        assert abs(t["tangle_fraction"] - ETA) < 1e-10

    def test_tangle_half_illumination(self):
        s = load_structure("bronze_cube")
        t = compute_tangle(s, illumination_fraction=0.5)
        assert abs(t["tangle_fraction"] - ETA * 0.5) < 1e-10

    def test_tangle_zero_illumination(self):
        s = load_structure("bronze_cube")
        t = compute_tangle(s, illumination_fraction=0.0)
        assert t["N_observer_tangle"] == 0.0
        assert t["tangle_fraction"] == 0.0

    def test_tangle_observer_tangle_equals_eta_times_N(self):
        s = load_structure("water_molecule")
        t = compute_tangle(s, illumination_fraction=1.0)
        expected = ETA * t["N_particles_total"]
        assert abs(t["N_observer_tangle"] - expected) < 1e-3

    def test_tangle_invalid_illumination_raises(self):
        s = load_structure("bronze_cube")
        with pytest.raises(ValueError):
            compute_tangle(s, illumination_fraction=1.5)
        with pytest.raises(ValueError):
            compute_tangle(s, illumination_fraction=-0.1)

    def test_tangle_cosmic_entanglement_is_independent_of_illumination(self):
        """N_entangled_cosmic doesn't change with illumination — it's a cosmic property."""
        s = load_structure("apple_on_table")
        t1 = compute_tangle(s, illumination_fraction=0.1)
        t2 = compute_tangle(s, illumination_fraction=0.9)
        assert t1["N_entangled_cosmic"] == t2["N_entangled_cosmic"]

    def test_tangle_scales_with_particle_count(self):
        """Larger structures have more tangled particles."""
        s_big = load_structure("earth_with_moon")
        s_small = load_structure("water_molecule")
        t_big = compute_tangle(s_big)
        t_small = compute_tangle(s_small)
        assert t_big["N_observer_tangle"] > t_small["N_observer_tangle"]


# ── Earth/Moon mass split accuracy test ──────────────────────────────────

class TestEarthMoonMassSplit:
    def test_earth_fraction_within_tolerance(self):
        s = load_structure("earth_with_moon")
        earth = sum(c.resolved_mass_kg for c in s.children[:6])
        target = 5.972168e24
        assert abs(earth - target) / target < 0.002  # within 0.2%

    def test_moon_fraction_within_tolerance(self):
        s = load_structure("earth_with_moon")
        moon = sum(c.resolved_mass_kg for c in s.children[6:])
        target = 7.342e22
        assert abs(moon - target) / target < 0.002  # within 0.2%

    def test_total_mass_is_sum(self):
        s = load_structure("earth_with_moon")
        earth = sum(c.resolved_mass_kg for c in s.children[:6])
        moon  = sum(c.resolved_mass_kg for c in s.children[6:])
        assert abs((earth + moon) - s.resolved_mass_kg) / s.resolved_mass_kg < 1e-10
