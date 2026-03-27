"""Tests for mass allocation and resolution behavior.

Documents how the resolver distributes mass through a structure tree,
and verifies the builder correctly maps existing spec formats into the
new unified Structure + resolver model.
"""

import pytest

from sigma_ground.inventory.builder import build_quick_structure, build_structure_from_spec
from sigma_ground.inventory.checksum.particle_count import count_particles_in_structure
from sigma_ground.inventory.models.structure import Structure
from sigma_ground.inventory.resolver import resolve
from report import report, sci


# ---------------------------------------------------------------------------
# Build-time ratio computation
# ---------------------------------------------------------------------------

class TestRatioFromSpec:
    """Builder converts thickness*density into ratios."""

    def test_single_child_gets_ratio_one(self):
        s = build_structure_from_spec({
            "stated_mass_kg": 100.0,
            "children": [
                {"thickness": 25.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
            ],
        })
        child = s.children[0]
        assert child.ratio == pytest.approx(1.0)
        assert child.resolved_mass_kg == pytest.approx(100.0)

    def test_denser_material_gets_higher_ratio(self):
        s = build_structure_from_spec({
            "stated_mass_kg": 1.0,
            "children": [
                {"thickness": 10.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Water", "ratio": 1.0}]},
            ],
        })
        iron, water = s.children[0], s.children[1]
        report("Ratio — same thickness, different density", [
            f"Iron ratio:  {iron.ratio:.6f}  (density={sci(iron.standard_density)})",
            f"Water ratio: {water.ratio:.6f}  (density={sci(water.standard_density)})",
        ])
        assert iron.ratio > water.ratio
        assert iron.ratio + water.ratio == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Single child
# ---------------------------------------------------------------------------

class TestSingleChild:
    """One child gets 100% of root mass."""

    def test_single_child_gets_full_mass(self):
        s = build_quick_structure("Iron", 100.0)
        report("Single child allocation", [
            f"Root mass:  {sci(s.resolved_mass_kg)} kg",
            f"Child mass: {sci(s.children[0].resolved_mass_kg)} kg",
        ])
        assert s.children[0].resolved_mass_kg == pytest.approx(100.0)
        assert s.resolved_mass_kg == pytest.approx(100.0)

    def test_particle_count_uses_full_mass(self):
        s = build_quick_structure("Iron", 1.0)
        mass_used, p, n, e = count_particles_in_structure(s, stated_mass=1.0)
        assert mass_used == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Multiple children
# ---------------------------------------------------------------------------

class TestMultipleChildren:
    """Mass distributed by ratio among siblings."""

    def test_equal_thickness_unequal_density(self):
        """Same thickness, different density → mass split by density ratio."""
        s = build_structure_from_spec({
            "stated_mass_kg": 100.0,
            "children": [
                {"thickness": 10.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Water", "ratio": 1.0}]},
            ],
        })
        iron, water = s.children[0], s.children[1]
        report("Two children — equal thickness, different density", [
            f"Iron:  ratio={iron.ratio:.6f}  → {sci(iron.resolved_mass_kg)} kg",
            f"Water: ratio={water.ratio:.6f}  → {sci(water.resolved_mass_kg)} kg",
            f"Sum:   {sci(iron.resolved_mass_kg + water.resolved_mass_kg)} kg",
        ])

        assert iron.resolved_mass_kg + water.resolved_mass_kg == pytest.approx(100.0)
        assert iron.resolved_mass_kg > water.resolved_mass_kg
        assert iron.resolved_mass_kg / water.resolved_mass_kg == pytest.approx(
            iron.standard_density / water.standard_density, rel=0.01
        )

    def test_different_thickness_same_material(self):
        """Same material, different thickness → mass split by thickness ratio."""
        s = build_structure_from_spec({
            "stated_mass_kg": 90.0,
            "children": [
                {"thickness": 20.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
            ],
        })
        thick, thin = s.children[0], s.children[1]
        report("Two iron children — 2:1 thickness", [
            f"Thick: ratio={thick.ratio:.6f}  → {sci(thick.resolved_mass_kg)} kg",
            f"Thin:  ratio={thin.ratio:.6f}  → {sci(thin.resolved_mass_kg)} kg",
        ])

        assert thick.resolved_mass_kg == pytest.approx(60.0)
        assert thin.resolved_mass_kg == pytest.approx(30.0)

    def test_total_allocation_always_equals_stated_mass(self):
        """Sum of all children == root mass."""
        s = build_structure_from_spec({
            "stated_mass_kg": 42.0,
            "children": [
                {"thickness": 5.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 12.0, "materials": [{"material": "Water", "ratio": 1.0}]},
                {"thickness": 3.0, "materials": [{"material": "Copper", "ratio": 1.0}]},
            ],
        })
        total = sum(c.resolved_mass_kg for c in s.children)
        report("Three children — total allocation", [
            f"Root mass:   {sci(42.0)} kg",
            f"Sum alloc:   {sci(total)} kg",
        ])
        assert total == pytest.approx(42.0)


# ---------------------------------------------------------------------------
# Adding a child shifts siblings
# ---------------------------------------------------------------------------

class TestSiblingShift:
    """Adding/changing one child redistributes all siblings."""

    def test_adding_third_child_shrinks_first_two(self):
        spec_2 = {
            "stated_mass_kg": 100.0,
            "children": [
                {"thickness": 10.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Copper", "ratio": 1.0}]},
            ],
        }
        s2 = build_structure_from_spec(spec_2)
        iron_before = s2.children[0].resolved_mass_kg
        copper_before = s2.children[1].resolved_mass_kg

        spec_3 = {
            "stated_mass_kg": 100.0,
            "children": [
                {"thickness": 10.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Copper", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Water", "ratio": 1.0}]},
            ],
        }
        s3 = build_structure_from_spec(spec_3)
        iron_after = s3.children[0].resolved_mass_kg
        copper_after = s3.children[1].resolved_mass_kg
        water_after = s3.children[2].resolved_mass_kg

        report("Sibling shift — adding Water to Iron+Copper", [
            f"Iron before:   {sci(iron_before)} kg",
            f"Iron after:    {sci(iron_after)} kg  (shrunk)",
            f"Copper before: {sci(copper_before)} kg",
            f"Copper after:  {sci(copper_after)} kg  (shrunk)",
            f"Water added:   {sci(water_after)} kg",
            f"Total after:   {sci(iron_after + copper_after + water_after)} kg",
        ])

        assert iron_after < iron_before
        assert copper_after < copper_before
        assert iron_after + copper_after + water_after == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Count multiplier
# ---------------------------------------------------------------------------

class TestCountMultiplier:
    """count multiplies a child's contribution to parent mass."""

    def test_count_three_bolts(self):
        bolt = Structure(name="Bolt", mass_kg=0.5, count=3)
        plate = Structure(name="Plate", mass_kg=10.0)
        root = Structure(name="Assembly", children=[bolt, plate])
        resolve(root)

        report("Count=3 bolts in assembly", [
            f"Bolt mass:  {sci(bolt.resolved_mass_kg)} kg  x{bolt.count}",
            f"Plate mass: {sci(plate.resolved_mass_kg)} kg",
            f"Total:      {sci(root.resolved_mass_kg)} kg",
        ])

        assert root.resolved_mass_kg == pytest.approx(11.5)

    def test_ratio_child_with_anchor_sibling(self):
        iron = Structure(name="Iron", mass_kg=60.0)
        copper = Structure(name="Copper", ratio=0.4)
        root = Structure(name="Alloy", children=[iron, copper])
        resolve(root)

        report("Mass + ratio siblings", [
            f"Iron:   {sci(iron.resolved_mass_kg)} kg  (anchor)",
            f"Copper: {sci(copper.resolved_mass_kg)} kg  (from ratio=0.4)",
            f"Root:   {sci(root.resolved_mass_kg)} kg",
        ])

        assert iron.resolved_mass_kg == pytest.approx(60.0)
        assert copper.resolved_mass_kg == pytest.approx(40.0)
        assert root.resolved_mass_kg == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Particle count integration
# ---------------------------------------------------------------------------

class TestParticleCountIntegration:
    """Particle counts scale linearly with mass."""

    def test_double_mass_double_particles(self):
        s1 = build_quick_structure("Iron", 1.0)
        s2 = build_quick_structure("Iron", 2.0)

        _, p1, n1, e1 = count_particles_in_structure(s1, stated_mass=1.0)
        _, p2, n2, e2 = count_particles_in_structure(s2, stated_mass=2.0)

        report("Linear scaling — 1 kg vs 2 kg Iron", [
            f"1 kg protons: {sci(p1)}",
            f"2 kg protons: {sci(p2)}",
            f"Ratio:        {p2/p1:.6f}  (expect 2.0)",
        ])

        assert p2 / p1 == pytest.approx(2.0)
        assert n2 / n1 == pytest.approx(2.0)
        assert e2 / e1 == pytest.approx(2.0)

    def test_mass_used_equals_root_mass(self):
        s = build_structure_from_spec({
            "stated_mass_kg": 50.0,
            "children": [
                {"thickness": 10.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Copper", "ratio": 1.0}]},
                {"thickness": 10.0, "materials": [{"material": "Water", "ratio": 1.0}]},
            ],
        })
        mass_used, _, _, _ = count_particles_in_structure(s, stated_mass=50.0)
        assert mass_used == pytest.approx(50.0)
