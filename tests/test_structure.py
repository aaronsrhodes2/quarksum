"""Tests for Structure value equality and hashing.

Two Structures with the same physical content but different UUIDs
should compare equal and hash the same, enabling deduplication in
sets and dicts.
"""

from sigma_ground.inventory.models.structure import Structure
from sigma_ground.inventory.models.molecule import Molecule


class TestStructureEquality:
    """Value-based equality ignoring the UUID id field."""

    def test_identical_structures_are_equal(self):
        a = Structure(name="Iron", mass_kg=1.0, standard_density=7874.0)
        b = Structure(name="Iron", mass_kg=1.0, standard_density=7874.0)
        assert a.id != b.id, "sanity: UUIDs should differ"
        assert a == b

    def test_different_structures_are_not_equal(self):
        a = Structure(name="Iron", mass_kg=1.0)
        b = Structure(name="Copper", mass_kg=1.0)
        assert a != b

    def test_hash_consistent_with_eq(self):
        a = Structure(name="Iron", mass_kg=1.0, standard_density=7874.0)
        b = Structure(name="Iron", mass_kg=1.0, standard_density=7874.0)
        assert hash(a) == hash(b)

    def test_structures_usable_in_set(self):
        a = Structure(name="Iron", mass_kg=1.0)
        b = Structure(name="Iron", mass_kg=1.0)
        s = {a, b}
        assert len(s) == 1

    def test_children_included_in_equality(self):
        child = Structure(name="Core", mass_kg=0.5)
        a = Structure(name="Shell", children=[child])
        b = Structure(name="Shell", children=[Structure(name="Core", mass_kg=0.5)])
        assert a == b

    def test_children_difference_breaks_equality(self):
        a = Structure(name="Shell", children=[Structure(name="Core", mass_kg=0.5)])
        b = Structure(name="Shell", children=[Structure(name="Core", mass_kg=0.9)])
        assert a != b
