"""CLI integration tests — exercise __main__.main() and verify JSON output."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from report import sci, pct, report

STRUCTURES = ["gold_ring", "water_bottle", "car_battery", "earths_layers", "solar_system_xsection"]


def _run_cli(*args: str, expect_fail: bool = False) -> dict | str:
    """Run quarksum CLI and return parsed JSON (or raw stderr on failure)."""
    result = subprocess.run(
        [sys.executable, "-m", "sigma_ground.inventory", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if expect_fail:
        assert result.returncode != 0, f"Expected failure but got 0: {result.stdout}"
        return result.stderr
    assert result.returncode == 0, f"CLI failed (rc={result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


class TestDefaultChecksum:
    """Default invocation loads Sol and runs StoQ checksum."""

    def test_default_runs_earth_with_moon(self):
        data = _run_cli()
        report("CLI Default — Earth with Moon StoQ", [
            f"Structure:   {data['structure_name']}",
            f"Stated mass: {sci(data['stated_mass_kg'])} kg",
            f"Defect:      {pct(data['mass_defect_percent'])}",
        ])
        assert "Earth" in data["structure_name"]
        assert data["stated_mass_kg"] > 0
        assert "mass_defect_percent" in data

    def test_default_defect_near_minus_99(self):
        data = _run_cli()
        report("CLI Default — Mass Defect", [
            f"Reconstructed: {sci(data['reconstructed_mass_kg'])} kg",
            f"Stated:        {sci(data['stated_mass_kg'])} kg",
            f"Defect:        {pct(data['mass_defect_percent'])}",
            f"Expected:      ~-99% (bare quarks ≈ 1% of nucleon mass)",
        ])
        assert data["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)


class TestStructureChecksum:
    """Run checksum on each built-in structure by name."""

    @pytest.mark.parametrize("structure", STRUCTURES)
    def test_structure_checksum(self, structure: str):
        data = _run_cli(structure)
        s = data["scope_summary"]
        report(f"CLI Structure — {data.get('structure_name', structure)}", [
            f"Stated mass: {sci(data['stated_mass_kg'])} kg",
            f"Defect:      {pct(data['mass_defect_percent'])}",
            f"Protons:     {sci(s['nucleons']['protons'])}",
            f"Neutrons:    {sci(s['nucleons']['neutrons'])}",
            f"Electrons:   {sci(s['electrons'])}",
            f"Up quarks:   {sci(s['quarks']['up'])}",
            f"Down quarks: {sci(s['quarks']['down'])}",
            f"Bodies: {s['bodies']}  Materials: {s['materials']}",
        ])
        assert data["stated_mass_kg"] > 0
        assert "mass_defect_percent" in data
        assert "scope_summary" in data
        assert "per_body" in data or isinstance(data.get("per_body"), list)


class TestListStructures:
    """--list prints a JSON array of the built-in structures."""

    def test_list_returns_16(self):
        data = _run_cli("--list")
        lines = [f"{s['id']:30s}  {s['name']}" for s in data]
        report("CLI --list", lines)
        assert isinstance(data, list)
        assert len(data) == 16  # 7 originals + 9 default loads

    def test_list_has_expected_fields(self):
        data = _run_cli("--list")
        for entry in data:
            assert "id" in entry
            assert "name" in entry


class TestSpec:
    """--spec dumps a structure's raw JSON spec."""

    def test_spec_default_is_earth_with_moon(self):
        data = _run_cli("--spec")
        report("CLI --spec (default=Earth with Moon)", [
            f"Mass:     {sci(data.get('stated_mass_kg', 0))} kg",
            f"Children: {len(data.get('children', []))} layer specs",
            f"Name:     {data.get('name', 'N/A')}",
        ])
        assert isinstance(data, dict)
        assert "children" in data
        assert "Earth" in data.get("name", "")
        assert data.get("stated_mass_kg", 0) > 1e23  # Earth mass scale

    def test_spec_named_structure(self):
        data = _run_cli("gold_ring", "--spec")
        report("CLI --spec gold_ring", [
            f"Mass:     {data.get('stated_mass_kg')} kg",
            f"Children: {len(data.get('children', []))} layer specs",
        ])
        assert isinstance(data, dict)
        assert data.get("stated_mass_kg") == 0.01

    def test_spec_unknown_structure_fails(self):
        stderr = _run_cli("no_such_structure", "--spec", expect_fail=True)
        report("CLI --spec unknown (expected failure)", [
            f"stderr: {stderr.strip()[:80]}",
        ])
        assert "unknown structure" in stderr.lower()

    def test_spec_roundtrip(self, tmp_path: pathlib.Path):
        """Export a structure spec, save it, checksum from file — same result."""
        spec = _run_cli("gold_ring", "--spec")
        spec_file = tmp_path / "roundtrip.json"
        spec_file.write_text(json.dumps(spec))
        from_file = _run_cli("--file", str(spec_file))
        direct = _run_cli("gold_ring")
        report("CLI Roundtrip — gold_ring → file → checksum", [
            f"Direct mass:    {sci(direct['stated_mass_kg'])} kg",
            f"Roundtrip mass: {sci(from_file['stated_mass_kg'])} kg",
            f"Direct defect:    {pct(direct['mass_defect_percent'])}",
            f"Roundtrip defect: {pct(from_file['mass_defect_percent'])}",
            f"Match: ✓",
        ])
        assert from_file["stated_mass_kg"] == pytest.approx(direct["stated_mass_kg"])
        assert from_file["mass_defect_percent"] == pytest.approx(direct["mass_defect_percent"], abs=0.01)


class TestQuarkChain:
    """--quark-chain runs full quark-chain reconstruction."""

    def test_quark_chain_default(self):
        data = _run_cli("--quark-chain")
        report("CLI --quark-chain (Sol)", [
            f"Stated mass:       {sci(data['stated_mass_kg'])} kg",
            f"Predicted mass:    {sci(data['predicted_mass_kg'])} kg",
            f"Residual defect:   {pct(data['mass_defect_percent'])}",
            f"",
            f"Bare quark mass:   {sci(data['bare_quark_mass_kg'])} kg",
            f"Electron mass:     {sci(data['electron_mass_kg'])} kg",
            f"+ QCD binding:     {sci(data['qcd_binding_joules'])} J",
            f"- Nuclear binding: {sci(data['nuclear_binding_joules'])} J",
            f"- Chemical binding:{sci(data['chemical_binding_joules'])} J",
            f"Atoms:             {sci(data['atom_count'])}",
        ])
        assert "bare_quark_mass_kg" in data
        assert "qcd_binding_joules" in data
        assert "predicted_mass_kg" in data
        assert abs(data["mass_defect_percent"]) < 1.0

    def test_quark_chain_on_structure(self):
        data = _run_cli("gold_ring", "--quark-chain")
        report("CLI --quark-chain gold_ring", [
            f"Stated mass:       {sci(data['stated_mass_kg'])} kg",
            f"Predicted mass:    {sci(data['predicted_mass_kg'])} kg",
            f"Residual defect:   {pct(data['mass_defect_percent'])}",
            f"Atoms:             {sci(data['atom_count'])}",
        ])
        assert "bare_quark_mass_kg" in data
        assert abs(data["mass_defect_percent"]) < 2.0


class TestQuickMode:
    """--material / --mass quick single-material checksum."""

    def test_quick_iron(self):
        data = _run_cli("--material", "Iron", "--mass", "1.0")
        s = data["scope_summary"]
        report("CLI Quick — Iron 1 kg", [
            f"Stated mass: {sci(data['stated_mass_kg'])} kg",
            f"Defect:      {pct(data['mass_defect_percent'])}",
            f"Protons:     {sci(s['nucleons']['protons'])}",
            f"Neutrons:    {sci(s['nucleons']['neutrons'])}",
        ])
        assert data["stated_mass_kg"] == pytest.approx(1.0, rel=1e-6)
        assert data["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_quick_missing_mass_fails(self):
        stderr = _run_cli("--material", "Iron", expect_fail=True)
        report("CLI Quick — missing --mass (expected failure)", [
            f"stderr: {stderr.strip()[:80]}",
        ])
        assert "mass" in stderr.lower()

    def test_quick_unknown_material_fails(self):
        stderr = _run_cli("--material", "Unobtainium", "--mass", "1.0", expect_fail=True)
        report("CLI Quick — unknown material (expected failure)", [
            f"stderr: {stderr.strip()[:80]}",
        ])
        assert "error" in stderr.lower()


class TestCustomFile:
    """--file loads a custom structure spec."""

    def test_custom_file(self, tmp_path: pathlib.Path):
        spec = {
            "name": "TestBlock",
            "stated_mass_kg": 100.0,
            "geometry_type": "spherical",
            "children": [
                {
                    "thickness": 50.0,
                    "materials": [
                        {"material": "Iron", "ratio": 0.85},
                        {"material": "Nickel", "ratio": 0.15},
                    ],
                }
            ],
        }
        spec_file = tmp_path / "test_block.json"
        spec_file.write_text(json.dumps(spec))

        data = _run_cli("--file", str(spec_file))
        report("CLI --file custom Fe/Ni block", [
            f"Structure:   {data.get('structure_name', 'N/A')}",
            f"Stated mass: {sci(data['stated_mass_kg'])} kg",
            f"Defect:      {pct(data['mass_defect_percent'])}",
        ])
        assert data["stated_mass_kg"] == pytest.approx(100.0)
        assert data["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_missing_file_fails(self):
        stderr = _run_cli("--file", "/tmp/nonexistent_xyz.json", expect_fail=True)
        report("CLI --file missing (expected failure)", [
            f"stderr: {stderr.strip()[:80]}",
        ])
        assert "not found" in stderr.lower()


class TestUnknownStructure:
    """Requesting a non-existent structure produces a clear error."""

    def test_unknown_structure(self):
        stderr = _run_cli("totally_fake_structure", expect_fail=True)
        report("CLI unknown structure (expected failure)", [
            f"stderr: {stderr.strip()[:80]}",
        ])
        assert "unknown structure" in stderr.lower()


class TestVersion:
    """--version prints version string."""

    def test_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "sigma_ground.inventory", "--version"],
            capture_output=True,
            text=True,
        )
        version = (result.stdout + result.stderr).strip()
        report("CLI --version", [f"Output: {version}"])
        assert "1.0.0" in result.stdout or "1.0.0" in result.stderr


class TestHelp:
    """--help shows usage examples."""

    def test_help_shows_examples(self):
        result = subprocess.run(
            [sys.executable, "-m", "sigma_ground.inventory", "--help"],
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        lines = combined.strip().split("\n")
        report("CLI --help", [
            f"Lines: {len(lines)}",
            f"Has 'quarksum': {'✓' if 'quarksum' in combined.lower() else '✗'}",
            f"Has '--material': {'✓' if '--material' in combined else '✗'}",
            f"Has '--quark-chain': {'✓' if '--quark-chain' in combined else '✗'}",
        ])
        assert result.returncode == 0
        assert "quarksum" in combined.lower()
        assert "--material" in combined
        assert "--quark-chain" in combined
