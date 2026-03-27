"""Tests for the anchor-anywhere mass resolver.

These tests define the behavior of the new resolver module:
- Three allocation modes: mass_kg, volume_m3, ratio
- Anchor-anywhere resolution (up, down, sideways)
- Edge cases: no anchor, multiple anchors, ratio normalization
"""

import pytest

from sigma_ground.inventory.models.structure import Structure
from sigma_ground.inventory.resolver import resolve, ResolutionError


# ---------------------------------------------------------------------------
# Mass mode (concrete anchor)
# ---------------------------------------------------------------------------

class TestMassMode:
    """Children with mass_kg are concrete anchors."""

    def test_single_child_mass_resolves(self):
        root = Structure(name="Root")
        root.children = [
            Structure(name="Iron", mass_kg=60.0),
        ]
        resolve(root)
        assert root.children[0].resolved_mass_kg == pytest.approx(60.0)
        assert root.resolved_mass_kg == pytest.approx(60.0)

    def test_two_mass_children_sum_to_parent(self):
        root = Structure(name="Root")
        root.children = [
            Structure(name="Iron", mass_kg=60.0),
            Structure(name="Copper", mass_kg=40.0),
        ]
        resolve(root)
        assert root.resolved_mass_kg == pytest.approx(100.0)
        assert root.children[0].resolved_mass_kg == pytest.approx(60.0)
        assert root.children[1].resolved_mass_kg == pytest.approx(40.0)

    def test_mass_with_count_multiplier(self):
        root = Structure(name="Root")
        root.children = [
            Structure(name="Bolt", mass_kg=0.5, count=10),
        ]
        resolve(root)
        assert root.children[0].resolved_mass_kg == pytest.approx(0.5)
        assert root.resolved_mass_kg == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Volume mode (converted to mass via density)
# ---------------------------------------------------------------------------

class TestVolumeMode:
    """Children with volume_m3 resolve mass = volume * density."""

    def test_volume_converts_to_mass(self):
        root = Structure(name="Root")
        root.children = [
            Structure(name="Water", volume_m3=0.001, standard_density=997.0),
        ]
        resolve(root)
        assert root.children[0].resolved_mass_kg == pytest.approx(0.997)
        assert root.resolved_mass_kg == pytest.approx(0.997)

    def test_two_volumes_sum_to_parent(self):
        root = Structure(name="Root")
        root.children = [
            Structure(name="Water", volume_m3=0.002, standard_density=997.0),
            Structure(name="Iron", volume_m3=0.001, standard_density=7874.0),
        ]
        resolve(root)
        expected_water = 0.002 * 997.0
        expected_iron = 0.001 * 7874.0
        assert root.children[0].resolved_mass_kg == pytest.approx(expected_water)
        assert root.children[1].resolved_mass_kg == pytest.approx(expected_iron)
        assert root.resolved_mass_kg == pytest.approx(expected_water + expected_iron)


# ---------------------------------------------------------------------------
# Ratio mode (fraction of parent)
# ---------------------------------------------------------------------------

class TestRatioMode:
    """Children with ratio get fraction of parent mass."""

    def test_ratios_with_anchor_at_root(self):
        root = Structure(name="Root", mass_kg=100.0)
        root.children = [
            Structure(name="Iron", ratio=0.6),
            Structure(name="Copper", ratio=0.4),
        ]
        resolve(root)
        assert root.resolved_mass_kg == pytest.approx(100.0)
        assert root.children[0].resolved_mass_kg == pytest.approx(60.0)
        assert root.children[1].resolved_mass_kg == pytest.approx(40.0)

    def test_ratios_normalized_when_not_summing_to_one(self):
        """Ratios 3:1 that don't sum to 1.0 get normalized."""
        root = Structure(name="Root", mass_kg=100.0)
        root.children = [
            Structure(name="A", ratio=3.0),
            Structure(name="B", ratio=1.0),
        ]
        resolve(root)
        assert root.children[0].resolved_mass_kg == pytest.approx(75.0)
        assert root.children[1].resolved_mass_kg == pytest.approx(25.0)

    def test_nested_ratios_propagate_down(self):
        root = Structure(name="Root", mass_kg=100.0)
        child = Structure(name="Alloy", ratio=1.0)
        child.children = [
            Structure(name="Iron", ratio=0.8),
            Structure(name="Copper", ratio=0.2),
        ]
        root.children = [child]
        resolve(root)
        assert child.resolved_mass_kg == pytest.approx(100.0)
        assert child.children[0].resolved_mass_kg == pytest.approx(80.0)
        assert child.children[1].resolved_mass_kg == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Mixed modes
# ---------------------------------------------------------------------------

class TestMixedModes:
    """Mass + ratio children coexist; mass children anchor, ratio children fill."""

    def test_mass_and_ratio_siblings(self):
        """One child has concrete mass, the other has ratio."""
        root = Structure(name="Root")
        root.children = [
            Structure(name="Iron", mass_kg=60.0),
            Structure(name="Copper", ratio=0.4),
        ]
        resolve(root)
        assert root.children[0].resolved_mass_kg == pytest.approx(60.0)
        assert root.children[1].resolved_mass_kg == pytest.approx(40.0)
        assert root.resolved_mass_kg == pytest.approx(100.0)

    def test_volume_and_ratio_siblings(self):
        """Volume child anchors, ratio child gets fraction of inferred parent."""
        root = Structure(name="Root")
        root.children = [
            Structure(name="Water", volume_m3=0.001, standard_density=1000.0),
            Structure(name="Air", ratio=0.5),
        ]
        resolve(root)
        # Water = 1.0 kg, Air is 50% of parent → Water is 50% → parent = 2.0
        assert root.children[0].resolved_mass_kg == pytest.approx(1.0)
        assert root.children[1].resolved_mass_kg == pytest.approx(1.0)
        assert root.resolved_mass_kg == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Anchor-anywhere propagation
# ---------------------------------------------------------------------------

class TestAnchorPropagation:
    """One anchor mass anywhere in the tree resolves the whole tree."""

    def test_anchor_at_leaf_propagates_up_and_sideways(self):
        """
        Root (ratio children)
        ├── A (ratio=0.7)
        └── B (ratio=0.3)
            └── B1 (mass_kg=30.0)   ← anchor

        B1 is 100% of B → B = 30 kg
        B is 30% of Root → Root = 100 kg
        A is 70% of Root → A = 70 kg
        """
        b1 = Structure(name="B1", mass_kg=30.0)
        b = Structure(name="B", ratio=0.3, children=[b1])
        a = Structure(name="A", ratio=0.7)
        root = Structure(name="Root", children=[a, b])

        resolve(root)

        assert b1.resolved_mass_kg == pytest.approx(30.0)
        assert b.resolved_mass_kg == pytest.approx(30.0)
        assert root.resolved_mass_kg == pytest.approx(100.0)
        assert a.resolved_mass_kg == pytest.approx(70.0)

    def test_anchor_in_middle_propagates_all_directions(self):
        """
        Root
        ├── A (ratio=0.7)
        │   ├── A1 (ratio=0.8)
        │   └── A2 (ratio=0.2)
        └── B (ratio=0.3, mass_kg=30.0)  ← anchor
            ├── B1 (ratio=0.5)
            └── B2 (ratio=0.5)
        """
        a1 = Structure(name="A1", ratio=0.8)
        a2 = Structure(name="A2", ratio=0.2)
        a = Structure(name="A", ratio=0.7, children=[a1, a2])

        b1 = Structure(name="B1", ratio=0.5)
        b2 = Structure(name="B2", ratio=0.5)
        b = Structure(name="B", ratio=0.3, mass_kg=30.0, children=[b1, b2])

        root = Structure(name="Root", children=[a, b])
        resolve(root)

        assert root.resolved_mass_kg == pytest.approx(100.0)
        assert a.resolved_mass_kg == pytest.approx(70.0)
        assert a1.resolved_mass_kg == pytest.approx(56.0)
        assert a2.resolved_mass_kg == pytest.approx(14.0)
        assert b.resolved_mass_kg == pytest.approx(30.0)
        assert b1.resolved_mass_kg == pytest.approx(15.0)
        assert b2.resolved_mass_kg == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """No anchor, multiple anchors, empty structures."""

    def test_no_anchor_raises_error(self):
        root = Structure(name="Root")
        root.children = [
            Structure(name="A", ratio=0.6),
            Structure(name="B", ratio=0.4),
        ]
        with pytest.raises(ResolutionError, match="at least one"):
            resolve(root)

    def test_consistent_multiple_anchors_ok(self):
        """Two anchors that agree: 60 kg at 60% and 40 kg at 40% both imply 100 kg root."""
        root = Structure(name="Root")
        root.children = [
            Structure(name="Iron", mass_kg=60.0, ratio=0.6),
            Structure(name="Copper", mass_kg=40.0, ratio=0.4),
        ]
        resolve(root)
        assert root.resolved_mass_kg == pytest.approx(100.0)

    def test_conflicting_anchors_raises_error(self):
        """Two anchors that disagree on what root mass should be."""
        root = Structure(name="Root")
        root.children = [
            Structure(name="Iron", mass_kg=60.0, ratio=0.6),
            Structure(name="Copper", mass_kg=60.0, ratio=0.4),
        ]
        with pytest.raises(ResolutionError, match="conflict"):
            resolve(root)

    def test_leaf_with_no_children_and_mass(self):
        leaf = Structure(name="Leaf", mass_kg=5.0)
        resolve(leaf)
        assert leaf.resolved_mass_kg == pytest.approx(5.0)

    def test_empty_structure_resolves_to_zero(self):
        root = Structure(name="Empty")
        resolve(root)
        assert root.resolved_mass_kg == pytest.approx(0.0)

    def test_count_propagates_up(self):
        """Parent mass includes count: 3 bolts at 0.5 kg = 1.5 kg total."""
        root = Structure(name="Root")
        root.children = [
            Structure(name="Bolt", mass_kg=0.5, count=3),
            Structure(name="Plate", mass_kg=10.0),
        ]
        resolve(root)
        assert root.resolved_mass_kg == pytest.approx(11.5)
