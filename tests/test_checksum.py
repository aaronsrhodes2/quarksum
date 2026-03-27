"""Tests for the QuarkSum pipeline."""

import pytest

from sigma_ground.inventory.builder import (
    build_quick_structure,
    build_structure_from_spec,
    list_structures,
    load_structure,
)
from sigma_ground.inventory.checksum.particle_count import count_particles_in_structure
from sigma_ground.inventory.checksum.stoq_checksum import compute_stoq_checksum
from sigma_ground.inventory.checksum.quark_chain import (
    compute_quark_chain_checksum,
    predict_from_quark_chain,
    walk_quark_chain,
)
from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.models.particle import Proton, Neutron, Particle
from report import sci, pct, report


class TestParticleCount:
    """Basic particle counting on single-material structures."""

    def test_iron_1kg_has_positive_counts(self):
        s = build_quick_structure("Iron", 1.0)
        mass_used, p, n, e = count_particles_in_structure(s, stated_mass=1.0)
        report("Iron 1 kg — Particle Inventory", [
            f"Protons:    {sci(p)}",
            f"Neutrons:   {sci(n)}",
            f"Electrons:  {sci(e)}",
            f"Mass used:  {sci(mass_used)} kg",
            f"Charge neutrality: p-e = {sci(p - e)}",
        ])
        assert p > 0
        assert n > 0
        assert e > 0

    def test_iron_electrons_equal_protons(self):
        s = build_quick_structure("Iron", 1.0)
        _, p, n, e = count_particles_in_structure(s, stated_mass=1.0)
        report("Iron 1 kg — Charge Neutrality", [
            f"Protons:    {sci(p)}",
            f"Electrons:  {sci(e)}",
            f"Ratio e/p:  {e / p:.12f}",
            f"Neutral matter: protons == electrons ✓",
        ])
        assert p == pytest.approx(e, rel=1e-10)

    def test_water_1kg_particle_counts(self):
        s = build_quick_structure("Water", 1.0)
        mass_used, p, n, e = count_particles_in_structure(s, stated_mass=1.0)
        report("Water 1 kg — Particle Inventory", [
            f"Protons:    {sci(p)}",
            f"Neutrons:   {sci(n)}",
            f"Electrons:  {sci(e)}",
            f"Mass used:  {sci(mass_used)} kg",
            f"N/Z ratio:  {n / p:.4f}  (pure H₂O → ~1.0)",
        ])
        assert p > 0
        assert n > 0


class TestStoQChecksum:
    """Structure-to-Quark checksum (bare quark mass reconstruction)."""

    def _report_stoq(self, name: str, result: dict) -> None:
        s = result["scope_summary"]
        report(f"StoQ Checksum — {name}", [
            f"Stated mass:     {sci(result['stated_mass_kg'])} kg",
            f"Reconstructed:   {sci(result['reconstructed_mass_kg'])} kg",
            f"Mass defect:     {pct(result['mass_defect_percent'])}",
            f"",
            f"Protons:         {sci(s['nucleons']['protons'])}",
            f"Neutrons:        {sci(s['nucleons']['neutrons'])}",
            f"Electrons:       {sci(s['electrons'])}",
            f"Up quarks:       {sci(s['quarks']['up'])}",
            f"Down quarks:     {sci(s['quarks']['down'])}",
            f"Bodies:          {s['bodies']}",
            f"Materials:       {s['materials']}",
        ])

    def test_gold_ring_defect_near_minus_99(self):
        s = load_structure("gold_ring")
        result = compute_stoq_checksum(s)
        self._report_stoq("Gold Wedding Ring", result)
        assert result["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_water_bottle_defect_near_minus_99(self):
        s = load_structure("water_bottle")
        result = compute_stoq_checksum(s)
        self._report_stoq("Water Bottle", result)
        assert result["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_car_battery_defect_near_minus_99(self):
        s = load_structure("car_battery")
        result = compute_stoq_checksum(s)
        self._report_stoq("Car Battery", result)
        assert result["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_earths_layers_defect_near_minus_99(self):
        s = load_structure("earths_layers")
        result = compute_stoq_checksum(s)
        self._report_stoq("Earth's Layers", result)
        assert result["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_solar_system_defect_near_minus_99(self):
        s = load_structure("solar_system_xsection")
        result = compute_stoq_checksum(s)
        self._report_stoq("Solar System", result)
        if result.get("per_body"):
            lines = []
            for b in result["per_body"]:
                lines.append(
                    f"{b['name']:20s}  mass={sci(b['stated_mass_kg'])} kg"
                    f"  p={sci(b['total_protons'])}  defect={pct(b['mass_defect_percent'])}"
                )
            report("Solar System — Per-Body Breakdown", lines)
        assert result["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_quick_iron_defect(self):
        s = build_quick_structure("Iron", 1.0)
        result = compute_stoq_checksum(s)
        self._report_stoq("Iron 1 kg (quick)", result)
        assert result["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_checksum_has_expected_fields(self):
        s = load_structure("gold_ring")
        result = compute_stoq_checksum(s)
        fields = ["stated_mass_kg", "scope_summary", "reconstructed_mass_kg",
                   "mass_defect_percent", "per_body", "note"]
        present = [f for f in fields if f in result]
        report("StoQ — Field Audit", [
            f"Expected: {', '.join(fields)}",
            f"Present:  {', '.join(present)}",
            f"All present: {'✓' if len(present) == len(fields) else '✗'}",
        ])
        for f in fields:
            assert f in result


class TestQuarkChain:
    """Full quark-chain reconstruction tests."""

    def _report_qc(self, name: str, result: dict) -> None:
        report(f"Quark Chain — {name}", [
            f"Stated mass:         {sci(result['stated_mass_kg'])} kg",
            f"Predicted mass:      {sci(result['predicted_mass_kg'])} kg",
            f"Mass defect:         {pct(result['mass_defect_percent'])}",
            f"",
            f"Bare quark mass:     {sci(result['bare_quark_mass_kg'])} kg",
            f"Electron mass:       {sci(result['electron_mass_kg'])} kg",
            f"+ QCD binding:       {sci(result['qcd_binding_joules'])} J",
            f"- Nuclear binding:   {sci(result['nuclear_binding_joules'])} J",
            f"- Chemical binding:  {sci(result['chemical_binding_joules'])} J",
            f"Atoms counted:       {sci(result['atom_count'])}",
        ])

    def test_quark_chain_closes_near_zero_simple(self):
        """Quark chain on a single-material structure should close well."""
        s = build_quick_structure("Iron", 1.0)
        t = walk_quark_chain(s, stated_mass=1.0)
        predicted = predict_from_quark_chain(t)
        defect_pct = (predicted - 1.0) / 1.0 * 100.0
        report("Quark Chain — Iron 1 kg (walk)", [
            f"Predicted mass:  {sci(predicted)} kg",
            f"Stated mass:     {sci(1.0)} kg",
            f"Residual defect: {pct(defect_pct)}",
            f"Books close:     {'✓' if abs(defect_pct) < 1.0 else '✗'}",
        ])
        assert abs(defect_pct) < 1.0

    def test_quark_chain_closes_gold_ring(self):
        s = load_structure("gold_ring")
        result = compute_quark_chain_checksum(s)
        self._report_qc("Gold Wedding Ring", result)
        assert abs(result["mass_defect_percent"]) < 2.0

    def test_quark_chain_closes_solar_system(self):
        s = load_structure("solar_system_xsection")
        result = compute_quark_chain_checksum(s)
        self._report_qc("Solar System", result)
        assert abs(result["mass_defect_percent"]) < 1.0

    def test_quark_chain_has_expected_fields(self):
        s = load_structure("gold_ring")
        result = compute_quark_chain_checksum(s)
        fields = ["bare_quark_mass_kg", "electron_mass_kg", "qcd_binding_joules",
                   "nuclear_binding_joules", "chemical_binding_joules",
                   "predicted_mass_kg", "mass_defect_percent"]
        present = [f for f in fields if f in result]
        report("Quark Chain — Field Audit", [
            f"Expected: {len(fields)} fields",
            f"Present:  {len(present)} fields",
            f"All present: {'✓' if len(present) == len(fields) else '✗'}",
        ])
        for f in fields:
            assert f in result


class TestThreeMeasureMass:
    """Verify three-measure mass decomposition at each scope."""

    def test_proton_binding_positive(self):
        p = Proton.create()
        quarks = [(q.flavor, q.bare_mass_mev) for q in p.quarks]
        report("Proton — Three-Measure Mass", [
            f"Stable mass:       {sci(p.stable_mass_kg)} kg",
            f"Constituent mass:  {sci(p.constituent_mass_kg)} kg",
            f"Binding energy:    {sci(p.binding_energy_joules)} J",
            f"",
            f"Quarks: {', '.join(f'{f}({m:.2f} MeV)' for f, m in quarks)}",
            f"Bare quark total:  {sum(m for _, m in quarks):.2f} MeV",
            f"Proton rest mass:  938.272 MeV",
            f"QCD accounts for:  ~99% of proton mass ✓",
        ])
        assert p.binding_energy_joules > 0

    def test_neutron_binding_positive(self):
        n = Neutron.create()
        quarks = [(q.flavor, q.bare_mass_mev) for q in n.quarks]
        report("Neutron — Three-Measure Mass", [
            f"Stable mass:       {sci(n.stable_mass_kg)} kg",
            f"Constituent mass:  {sci(n.constituent_mass_kg)} kg",
            f"Binding energy:    {sci(n.binding_energy_joules)} J",
            f"",
            f"Quarks: {', '.join(f'{f}({m:.2f} MeV)' for f, m in quarks)}",
            f"Bare quark total:  {sum(m for _, m in quarks):.2f} MeV",
            f"Neutron rest mass: 939.565 MeV",
        ])
        assert n.binding_energy_joules > 0

    def test_proton_constituent_mass_is_quark_sum(self):
        p = Proton.create()
        quark_sum_kg = sum(q.bare_mass_mev for q in p.quarks) * Particle._MEV_TO_KG
        report("Proton — Constituent Mass Audit", [
            f"Quark sum (MeV→kg): {sci(quark_sum_kg)} kg",
            f"Constituent mass:   {sci(p.constituent_mass_kg)} kg",
            f"Match: {'✓' if abs(quark_sum_kg - p.constituent_mass_kg) < 1e-40 else '✗'}",
        ])
        assert p.constituent_mass_kg == pytest.approx(quark_sum_kg, rel=1e-10)


class TestRestoredModels:
    """Verify restored Standard Model particle factories."""

    def test_charm_quark_has_correct_mass(self):
        from sigma_ground.inventory.models.quark import Quark
        c = Quark.charm()
        assert c.bare_mass_mev == pytest.approx(1270.0, rel=1e-3)
        assert c.flavor == "charm"
        assert c.generation == 2

    def test_bottom_quark_has_correct_mass(self):
        from sigma_ground.inventory.models.quark import Quark
        b = Quark.bottom()
        assert b.bare_mass_mev == pytest.approx(4180.0, rel=1e-3)
        assert b.generation == 3

    def test_top_quark_has_correct_mass(self):
        from sigma_ground.inventory.models.quark import Quark
        t = Quark.top()
        assert t.bare_mass_mev == pytest.approx(172500.0, rel=1e-3)
        assert t.generation == 3

    def test_anti_charm_is_antimatter(self):
        from sigma_ground.inventory.models.quark import Quark
        ac = Quark.anti_charm()
        assert ac.is_antimatter is True
        assert ac.charge == pytest.approx(-2 / 3)

    def test_muon_has_correct_mass_and_lepton_number(self):
        from sigma_ground.inventory.models.particle import Muon
        m = Muon.create()
        assert m.rest_mass_kg == pytest.approx(1.883531627e-28, rel=1e-6)
        assert m.lepton_number == 1
        assert m.symbol == "μ⁻"

    def test_tau_has_correct_mass(self):
        from sigma_ground.inventory.models.particle import Tau
        t = Tau.create()
        assert t.rest_mass_kg == pytest.approx(3.16754e-27, rel=1e-3)

    def test_neutrinos_are_massless(self):
        from sigma_ground.inventory.models.particle import ElectronNeutrino, MuonNeutrino, TauNeutrino
        for cls in (ElectronNeutrino, MuonNeutrino, TauNeutrino):
            nu = cls.create()
            assert nu.rest_mass_kg == 0.0
            assert nu.lepton_number == 1

    def test_positron_is_antimatter_electron(self):
        from sigma_ground.inventory.models.particle import Positron
        p = Positron.create()
        assert p.is_antimatter is True
        assert p.charge_e == 1.0
        assert p.antiparticle == "electron"

    def test_antiproton_has_antiquarks(self):
        from sigma_ground.inventory.models.particle import Antiproton
        ap = Antiproton.create()
        assert ap.is_antimatter is True
        assert ap.baryon_number == -1.0
        assert len(ap.quarks) == 3
        assert all(q.is_antimatter for q in ap.quarks)

    def test_antineutron_has_antiquarks(self):
        from sigma_ground.inventory.models.particle import Antineutron
        an = Antineutron.create()
        assert an.is_antimatter is True
        assert len(an.quarks) == 3


class TestParticleInventory:
    """Full Standard Model particle inventory."""

    def _inv(self, material="Iron", mass=1.0):
        from sigma_ground.inventory.checksum.particle_inventory import compute_particle_inventory
        s = build_quick_structure(material, mass)
        return compute_particle_inventory(s)

    def test_inventory_has_all_standard_model_keys(self):
        result = self._inv()
        expected_keys = [
            "protons", "neutrons", "electrons",
            "up_quarks", "down_quarks", "strange_quarks",
            "charm_quarks", "bottom_quarks", "top_quarks",
            "gluons", "sea_quarks",
            "muons", "taus",
            "electron_neutrinos", "muon_neutrinos", "tau_neutrinos",
            "photons", "w_bosons", "z_bosons", "higgs_bosons",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_iron_gluons_are_8_per_nucleon(self):
        result = self._inv()
        nucleons = result["protons"] + result["neutrons"]
        assert result["gluons"] == pytest.approx(8 * nucleons, rel=1e-10)

    def test_iron_valence_quarks_match_nucleon_counts(self):
        result = self._inv()
        p, n = result["protons"], result["neutrons"]
        assert result["up_quarks"] == pytest.approx(2 * p + n, rel=1e-10)
        assert result["down_quarks"] == pytest.approx(p + 2 * n, rel=1e-10)

    def test_iron_sea_quarks_6_per_nucleon(self):
        result = self._inv()
        nucleons = result["protons"] + result["neutrons"]
        assert result["sea_quarks"] == pytest.approx(6 * nucleons, rel=1e-10)

    def test_iron_electrons_equal_protons(self):
        result = self._inv()
        assert result["electrons"] == pytest.approx(result["protons"], rel=1e-10)

    def test_mass_percents_nucleon_dominated(self):
        result = self._inv()
        p_pct = result["protons_mass_percent"]
        n_pct = result["neutrons_mass_percent"]
        assert p_pct + n_pct > 99.0

    def test_zero_counts_for_exotic_particles(self):
        result = self._inv()
        for key in ("muons", "taus", "electron_neutrinos", "muon_neutrinos",
                     "tau_neutrinos", "charm_quarks", "bottom_quarks",
                     "top_quarks", "photons", "w_bosons", "z_bosons", "higgs_bosons"):
            assert result[key] == 0, f"{key} should be 0"

    def test_bond_counts_for_water(self):
        result = self._inv("Water", 1.0)
        assert result["bonds_total"] > 0
        assert result["bonds_single"] > 0

    def test_atoms_and_molecules_counted(self):
        result = self._inv()
        assert result["atoms"] > 0
        assert result["molecules"] > 0

    def test_inventory_has_standard_model_note(self):
        result = self._inv()
        assert "standard_model_note" in result


class TestInventoryCLI:
    """CLI --inventory flag integration test."""

    def test_inventory_cli_returns_json_with_expected_keys(self):
        import json
        from sigma_ground.inventory.__main__ import main
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        try:
            rc = main(["gold_ring", "--inventory"])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        data = json.loads(captured.getvalue())
        assert "protons" in data
        assert "gluons" in data
        assert "standard_model_note" in data

    def test_inventory_via_library_api(self):
        import sigma_ground.inventory as quarksum
        s = quarksum.load_structure("gold_ring")
        result = quarksum.inventory(s)
        assert result["protons"] > 0
        assert result["gluons"] > 0


class TestQuarkBehaviors:
    """QCD behavioral computations for individual quarks."""

    def _beh(self, flavor="up", color="red"):
        from sigma_ground.inventory.behaviors.quark_behaviors import compute_quark_behaviors
        from sigma_ground.inventory.models.quark import Quark
        factory = getattr(Quark, flavor)
        q = factory(color=color)
        return compute_quark_behaviors(q)

    def test_behaviors_has_intrinsic_and_operable(self):
        result = self._beh()
        assert "intrinsic" in result
        assert "operable" in result
        for key in ("confinement", "asymptotic_freedom", "ckm_couplings", "entanglement"):
            assert key in result["intrinsic"], f"Missing intrinsic section: {key}"

    def test_operable_has_color_charge_with_mechanism(self):
        result = self._beh()
        cc = result["operable"]["color_charge"]
        assert cc["mechanism"] == "gluon exchange"
        assert "transitions" in cc

    def test_red_up_quark_can_emit_two_gluons(self):
        result = self._beh("up", "red")
        emissions = result["operable"]["color_charge"]["transitions"]["emissions"]
        result_colors = {e["result_color"] for e in emissions}
        assert result_colors == {"green", "blue"}

    def test_color_transition_is_reversible(self):
        r = self._beh("up", "red")
        t = r["operable"]["color_charge"]["transitions"]
        emitted_targets = {e["result_color"] for e in t["emissions"]}
        absorbed_sources = {a["from_color"] for a in t["absorptions"]}
        assert emitted_targets == absorbed_sources

    def test_cornell_potential_attractive_at_short_range(self):
        r = self._beh()
        potentials = r["intrinsic"]["confinement"]["cornell_potential"]
        v_01 = next(p for p in potentials if p["r_fm"] == pytest.approx(0.1))
        assert v_01["V_gev"] < 0

    def test_cornell_potential_confining_at_long_range(self):
        r = self._beh()
        potentials = r["intrinsic"]["confinement"]["cornell_potential"]
        v_10 = next(p for p in potentials if p["r_fm"] == pytest.approx(1.0))
        v_20 = next(p for p in potentials if p["r_fm"] == pytest.approx(2.0))
        assert v_20["V_gev"] > v_10["V_gev"]
        assert v_20["V_gev"] > 0

    def test_alpha_s_at_mz_is_0_1179(self):
        r = self._beh()
        points = r["intrinsic"]["asymptotic_freedom"]["alpha_s"]
        mz_point = next(p for p in points if p["Q_gev"] == pytest.approx(91.2, abs=0.5))
        assert mz_point["alpha_s"] == pytest.approx(0.1179, abs=0.005)

    def test_alpha_s_decreases_with_energy(self):
        r = self._beh()
        points = r["intrinsic"]["asymptotic_freedom"]["alpha_s"]
        a_low = next(p for p in points if p["Q_gev"] == pytest.approx(1.0))
        a_high = next(p for p in points if p["Q_gev"] == pytest.approx(91.2, abs=0.5))
        assert a_high["alpha_s"] < a_low["alpha_s"]

    def test_ckm_up_quark_favors_down(self):
        r = self._beh("up")
        transitions = r["intrinsic"]["ckm_couplings"]["transitions"]
        down_t = next(t for t in transitions if t["to"] == "down")
        assert down_t["probability"] > 0.94

    def test_ckm_row_unitarity(self):
        r = self._beh("up")
        transitions = r["intrinsic"]["ckm_couplings"]["transitions"]
        total = sum(t["probability"] for t in transitions)
        assert total == pytest.approx(1.0, abs=0.01)

    def test_entanglement_entropy_is_ln3(self):
        import math
        r = self._beh()
        assert r["intrinsic"]["entanglement"]["von_neumann_entropy"] == pytest.approx(
            math.log(3), rel=1e-6,
        )

    def test_behaviors_for_all_six_flavors(self):
        for flavor in ("up", "down", "strange", "charm", "bottom", "top"):
            r = self._beh(flavor)
            assert r["flavor"] == flavor
            assert len(r["intrinsic"]["ckm_couplings"]["transitions"]) == 3


class TestParticleBehaviors:
    """Behavior getter for subatomic particles."""

    def test_electron_has_intrinsic_and_operable(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import compute_particle_behaviors
        from sigma_ground.inventory.models.particle import Electron
        e = Electron.create()
        result = compute_particle_behaviors(e)
        assert "intrinsic" in result
        assert "operable" in result
        assert result["entity_type"] == "particle"
        assert result["particle_type"] == "electron"

    def test_electron_operable_has_orbital_quantum_numbers(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import compute_particle_behaviors
        from sigma_ground.inventory.models.particle import Electron
        e = Electron.create(n=2, l=1, ml=0)
        result = compute_particle_behaviors(e)
        assert result["operable"]["principal_n"]["value"] == 2
        assert result["operable"]["angular_l"]["value"] == 1

    def test_proton_intrinsic_has_qcd_binding(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import compute_particle_behaviors
        from sigma_ground.inventory.models.particle import Proton
        p = Proton.create()
        result = compute_particle_behaviors(p)
        assert result["intrinsic"]["qcd_binding_energy_mev"]["value"] == pytest.approx(
            929.282088, rel=1e-3,
        )

    def test_proton_has_quark_children_summary(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import compute_particle_behaviors
        from sigma_ground.inventory.models.particle import Proton
        p = Proton.create()
        result = compute_particle_behaviors(p)
        assert result["children"]["quarks"] == 3
        assert result["children"]["gluons"] == 8

    def test_muon_has_lepton_number(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import compute_particle_behaviors
        from sigma_ground.inventory.models.particle import Muon
        m = Muon.create()
        result = compute_particle_behaviors(m)
        assert result["intrinsic"]["lepton_number"]["value"] == 1


class TestAtomBehaviors:
    """Behavior getter for atoms."""

    def _atom(self, material="Iron"):
        s = build_quick_structure(material, 1.0)
        return s.children[0].molecules[0].atoms[0]

    def test_atom_has_intrinsic_and_operable(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import compute_atom_behaviors
        a = self._atom()
        result = compute_atom_behaviors(a)
        assert "intrinsic" in result
        assert "operable" in result
        assert result["entity_type"] == "atom"

    def test_atom_intrinsic_has_nuclear_properties(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import compute_atom_behaviors
        a = self._atom()
        result = compute_atom_behaviors(a)
        assert "nuclear_binding_energy_mev" in result["intrinsic"]
        assert result["intrinsic"]["atomic_number"]["value"] == 26

    def test_atom_intrinsic_has_ionization_energies(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import compute_atom_behaviors
        a = self._atom()
        result = compute_atom_behaviors(a)
        assert result["intrinsic"]["ionization_energy_1"]["value"] == pytest.approx(
            7.9024, rel=1e-3,
        )

    def test_atom_operable_has_charge_state(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import compute_atom_behaviors
        a = self._atom()
        result = compute_atom_behaviors(a)
        assert "charge_state" in result["operable"]
        assert result["operable"]["charge_state"]["value"] == 0

    def test_atom_children_summary(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import compute_atom_behaviors
        a = self._atom()
        result = compute_atom_behaviors(a)
        assert result["children"]["protons"] == 26
        assert result["children"]["neutrons"] > 0
        assert result["children"]["electrons"] == 26


class TestMoleculeBehaviors:
    """Behavior getter for molecules."""

    def _mol(self, material="Water"):
        s = build_quick_structure(material, 1.0)
        return s.children[0].molecules[0]

    def test_molecule_has_intrinsic_and_operable(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import compute_molecule_behaviors
        m = self._mol()
        result = compute_molecule_behaviors(m)
        assert "intrinsic" in result
        assert "operable" in result
        assert result["entity_type"] == "molecule"

    def test_molecule_has_bond_inventory(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import compute_molecule_behaviors
        m = self._mol()
        result = compute_molecule_behaviors(m)
        assert result["children"]["bonds"] == 2
        assert result["children"]["atoms"] == 3

    def test_molecule_has_dissociation_energies(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import compute_molecule_behaviors
        m = self._mol()
        result = compute_molecule_behaviors(m)
        assert result["bond_summary"]["weakest_bond_ev"] == pytest.approx(4.77, rel=1e-2)

    def test_molecule_has_formula_and_weight(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import compute_molecule_behaviors
        m = self._mol()
        result = compute_molecule_behaviors(m)
        assert result["formula"] == "H2O"
        assert result["intrinsic"]["molecular_weight"]["value"] == pytest.approx(18.015, rel=1e-3)


class TestMoleculeApply:
    """Environment delta/update resolution for molecules."""

    def _mol(self, material="Water"):
        s = build_quick_structure(material, 1.0)
        return s.children[0].molecules[0]

    def test_energy_ev_delta_breaks_weakest_bond(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import resolve_molecule_env
        m = self._mol()
        n_bonds = len(m.bonds)
        weakest = min(b.dissociation_energy for b in m.bonds if b.dissociation_energy)
        resolve_molecule_env(m, {"energy_ev": weakest + 0.5}, mode="delta")
        assert len(m.bonds) == n_bonds - 1

    def test_temperature_k_delta_stretches_bonds(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import resolve_molecule_env
        m = self._mol()
        orig_lengths = [b.length for b in m.bonds]
        resolve_molecule_env(m, {"temperature_k": 1000.0}, mode="delta")
        for b, orig in zip(m.bonds, orig_lengths):
            assert b.length >= orig

    def test_pressure_pa_update_compresses_bonds(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import resolve_molecule_env
        m = self._mol()
        orig_lengths = [b.length for b in m.bonds]
        resolve_molecule_env(m, {"pressure_pa": 1e9}, mode="update")
        for b, orig in zip(m.bonds, orig_lengths):
            assert b.length <= orig

    def test_electric_field_vm_delta_polarizes(self):
        from sigma_ground.inventory.behaviors.molecule_behaviors import resolve_molecule_env
        m = self._mol()
        result = resolve_molecule_env(m, {"electric_field_vm": 1e6}, mode="delta")
        assert any(ap["key"] == "electric_field_vm" for ap in result["applied"])
        assert "dipole" in result["applied"][-1]["consequence"].lower()


class TestUniversalDispatcher:
    """Universal behaviors() getter and apply_env() setter."""

    def test_behaviors_routes_quark(self):
        from sigma_ground.inventory.behaviors import behaviors
        from sigma_ground.inventory.models.quark import Quark
        q = Quark.up()
        result = behaviors(q)
        assert result["entity_type"] == "quark"
        assert "intrinsic" in result

    def test_behaviors_routes_atom(self):
        from sigma_ground.inventory.behaviors import behaviors
        s = build_quick_structure("Iron", 1.0)
        atom = s.children[0].molecules[0].atoms[0]
        result = behaviors(atom)
        assert result["entity_type"] == "atom"

    def test_behaviors_routes_molecule(self):
        from sigma_ground.inventory.behaviors import behaviors
        s = build_quick_structure("Water", 1.0)
        mol = s.children[0].molecules[0]
        result = behaviors(mol)
        assert result["entity_type"] == "molecule"

    def test_apply_delta_adds_to_current(self):
        from sigma_ground.inventory.behaviors import apply_env
        from sigma_ground.inventory.models.particle import Electron
        e = Electron.create()
        old_energy = e.energy_level
        apply_env(e, {"momentum_gev": 0.001}, mode="delta")
        assert e.energy_level > old_energy

    def test_apply_update_replaces_value(self):
        from sigma_ground.inventory.behaviors import apply_env
        s = build_quick_structure("Water", 1.0)
        mol = s.children[0].molecules[0]
        bond = mol.bonds[0]
        apply_env(mol, {"pressure_pa": 1e9}, mode="update")
        assert bond.length < bond.reference_length

    def test_unknown_type_raises_type_error(self):
        from sigma_ground.inventory.behaviors import behaviors
        with pytest.raises(TypeError):
            behaviors("not an entity")


class TestCascade:
    """Environment changes cascade through the hierarchy."""

    def test_molecule_temperature_cascades_to_atom_electrons(self):
        from sigma_ground.inventory.behaviors import apply_env
        s = build_quick_structure("Water", 1.0)
        mol = s.children[0].molecules[0]
        electron = mol.atoms[0].electrons[0]
        old_spin = electron.spin_projection
        apply_env(mol, {"magnetic_field_t": 1.0}, mode="delta")
        assert electron.spin_projection != old_spin

    def test_atom_magnetic_field_cascades_to_electrons(self):
        from sigma_ground.inventory.behaviors import apply_env
        s = build_quick_structure("Iron", 1.0)
        atom = s.children[0].molecules[0].atoms[0]
        electron = atom.electrons[0]
        old_spin = electron.spin_projection
        apply_env(atom, {"magnetic_field_t": 1.0}, mode="delta")
        assert electron.spin_projection != old_spin

    def test_structure_temperature_cascades_to_bonds(self):
        from sigma_ground.inventory.behaviors import apply_env
        s = build_quick_structure("Water", 1.0)
        bond = s.children[0].molecules[0].bonds[0]
        orig_length = bond.length
        apply_env(s, {"temperature_k": 1000.0}, mode="delta")
        assert bond.length > orig_length


class TestAtomApply:
    """Environment delta/update resolution for atoms."""

    def _atom(self, material="Iron"):
        s = build_quick_structure(material, 1.0)
        return s.children[0].molecules[0].atoms[0]

    def test_energy_ev_delta_ionizes_atom(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import resolve_atom_env
        a = self._atom()
        ie1 = a.ionization_energy_1
        assert a.charge_state == 0
        resolve_atom_env(a, {"energy_ev": ie1 + 1.0}, mode="delta")
        assert a.charge_state == 1
        assert len(a.electrons) == 25

    def test_energy_ev_delta_below_threshold_excites(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import resolve_atom_env
        a = self._atom()
        ie1 = a.ionization_energy_1
        resolve_atom_env(a, {"energy_ev": ie1 * 0.5}, mode="delta")
        assert a.charge_state == 0

    def test_temperature_k_update_sets_thermal_state(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import resolve_atom_env
        a = self._atom()
        result = resolve_atom_env(a, {"temperature_k": 5000.0}, mode="update")
        assert any(ap["key"] == "temperature_k" for ap in result["applied"])

    def test_magnetic_field_delta_zeeman(self):
        from sigma_ground.inventory.behaviors.atom_behaviors import resolve_atom_env
        a = self._atom()
        result = resolve_atom_env(a, {"magnetic_field_t": 2.0}, mode="delta")
        assert any(ap["key"] == "magnetic_field_t" for ap in result["applied"])
        assert "Zeeman" in result["applied"][-1]["consequence"]


class TestParticleApply:
    """Environment delta/update resolution for particles."""

    def test_energy_ev_delta_excites_electron(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import resolve_particle_env
        from sigma_ground.inventory.models.particle import Electron
        e = Electron.create(n=1, l=0, ml=0)
        result = resolve_particle_env(e, {"energy_ev": 10.2}, mode="delta")
        assert e.principal_n == 2
        assert any(a["key"] == "energy_ev" for a in result["applied"])

    def test_magnetic_field_delta_flips_spin(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import resolve_particle_env
        from sigma_ground.inventory.models.particle import Electron
        e = Electron.create()
        assert e.spin_projection == 0.5
        result = resolve_particle_env(e, {"magnetic_field_t": 1.0}, mode="delta")
        assert e.spin_projection == -0.5

    def test_momentum_gev_delta_deposits_energy(self):
        from sigma_ground.inventory.behaviors.particle_behaviors import resolve_particle_env
        from sigma_ground.inventory.models.particle import Electron
        e = Electron.create()
        old_e = e.energy_level
        resolve_particle_env(e, {"momentum_gev": 0.001}, mode="delta")
        assert e.energy_level > old_e


class TestQuarkApply:
    """Environment delta/update resolution for quarks."""

    def _quark(self, flavor="up", color="red"):
        from sigma_ground.inventory.models.quark import Quark
        return getattr(Quark, flavor)(color=color)

    def test_energy_gev_delta_recomputes_alpha_s(self):
        from sigma_ground.inventory.behaviors.quark_behaviors import resolve_quark_env
        q = self._quark()
        result = resolve_quark_env(q, {"energy_gev": 91.2}, mode="delta")
        alpha_s_entries = result["intrinsic"]["asymptotic_freedom"]["alpha_s"]
        mz = next(p for p in alpha_s_entries if p["Q_gev"] == pytest.approx(91.2, abs=0.5))
        assert mz["alpha_s"] == pytest.approx(0.1179, abs=0.005)
        assert any(a["key"] == "energy_gev" for a in result["applied"])

    def test_magnetic_field_delta_flips_spin(self):
        from sigma_ground.inventory.behaviors.quark_behaviors import resolve_quark_env
        q = self._quark()
        assert q.spin_projection == 0.5
        result = resolve_quark_env(q, {"magnetic_field_t": 1.0}, mode="delta")
        assert q.spin_projection == -0.5
        assert result["operable"]["spin_projection"]["value"] == -0.5

    def test_color_field_update_changes_color(self):
        from sigma_ground.inventory.behaviors.quark_behaviors import resolve_quark_env
        q = self._quark("up", "red")
        result = resolve_quark_env(q, {"color_field": "rg\u0304"}, mode="update")
        assert q.color_charge == "green"
        assert result["operable"]["color_charge"]["value"] == "green"
        assert any(a["key"] == "color_field" for a in result["applied"])


class TestBehaviorsCLI:
    """CLI --behaviors flag integration test."""

    def test_behaviors_cli_returns_json_with_sections(self):
        import json
        from sigma_ground.inventory.__main__ import main
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        try:
            rc = main(["--behaviors", "up"])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        data = json.loads(captured.getvalue())
        assert data["flavor"] == "up"
        assert "intrinsic" in data
        assert "operable" in data
        assert "confinement" in data["intrinsic"]
        assert "ckm_couplings" in data["intrinsic"]

    def test_behaviors_via_library_api(self):
        import sigma_ground.inventory as quarksum
        from sigma_ground.inventory.models.quark import Quark
        result = quarksum.quark_behaviors(Quark.charm(color="blue"))
        assert result["flavor"] == "charm"
        assert result["color"] == "blue"
        assert result["generation"] == 2

    def test_behaviors_cli_bad_flavor_returns_error(self):
        from sigma_ground.inventory.__main__ import main
        from io import StringIO
        import sys

        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        try:
            rc = main(["--behaviors", "gluon"])
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        assert rc == 1


class TestPhysicalConstants:
    """Verify new fundamental constants and derived values."""

    def test_derived_constants_are_consistent(self):
        import math
        assert CONSTANTS.hbar == pytest.approx(CONSTANTS.h / (2 * math.pi), rel=1e-10)
        assert CONSTANTS.c_squared == pytest.approx(CONSTANTS.c ** 2, rel=1e-10)
        assert CONSTANTS.MeV_to_kg == pytest.approx(
            CONSTANTS.e * 1e6 / CONSTANTS.c ** 2, rel=1e-10,
        )

    def test_bohr_magneton_from_fundamentals(self):
        computed = CONSTANTS.e * CONSTANTS.hbar / (2 * CONSTANTS.m_e)
        assert CONSTANTS.mu_B == pytest.approx(computed, rel=1e-6)


class TestApplyCLI:
    """CLI --apply flag integration tests."""

    def test_apply_cli_delta_mode(self):
        import json
        from sigma_ground.inventory.__main__ import main
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        try:
            rc = main([
                "--apply", "--env", '{"magnetic_field_t": 1.0}',
                "--mode", "delta", "--behaviors", "up",
            ])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        data = json.loads(captured.getvalue())
        assert "applied" in data

    def test_apply_cli_update_mode(self):
        import json
        from sigma_ground.inventory.__main__ import main
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        try:
            rc = main([
                "--apply", "--env", '{"color_field": "rg\u0304"}',
                "--mode", "update", "--behaviors", "up",
            ])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        data = json.loads(captured.getvalue())
        assert data["operable"]["color_charge"]["value"] == "green"


class TestBaryonicNote:
    """Checksum output includes a baryonic context note."""

    def test_stoq_has_baryonic_note(self):
        s = build_quick_structure("Iron", 1.0)
        result = compute_stoq_checksum(s)
        assert "baryonic_note" in result
        assert "baryonic" in result["baryonic_note"].lower()

    def test_quark_chain_has_baryonic_note(self):
        s = build_quick_structure("Iron", 1.0)
        result = compute_quark_chain_checksum(s)
        assert "baryonic_note" in result
        assert "baryonic" in result["baryonic_note"].lower()

    def test_baryonic_note_mentions_scale(self):
        s = load_structure("solar_system_xsection")
        result = compute_stoq_checksum(s)
        note = result["baryonic_note"]
        assert "100%" in note or "~5%" in note


class TestFlatModel:
    """The structure model is recursive: children + molecules, no layers."""

    def test_structure_has_children_not_layers(self):
        s = build_quick_structure("Iron", 1.0)
        assert hasattr(s, "children"), "Structure should have 'children'"
        assert not hasattr(s, "layers"), "Structure should NOT have 'layers'"
        assert len(s.children) == 1

    def test_structure_has_name(self):
        s = build_quick_structure("Iron", 1.0)
        assert s.name == "Iron"

    def test_multi_child_from_spec(self):
        spec = {
            "stated_mass_kg": 100.0,
            "children": [
                {"thickness": 50.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 20.0, "materials": [{"material": "Copper", "ratio": 1.0}]},
            ],
        }
        s = build_structure_from_spec(spec)
        assert len(s.children) == 2
        assert s.resolved_mass_kg == pytest.approx(100.0)
        assert all(c.ratio > 0 for c in s.children)

    def test_child_ratio_proportional_to_thickness_times_density(self):
        spec = {
            "stated_mass_kg": 1.0,
            "children": [
                {"thickness": 100.0, "materials": [{"material": "Iron", "ratio": 1.0}]},
                {"thickness": 100.0, "materials": [{"material": "Water", "ratio": 1.0}]},
            ],
        }
        s = build_structure_from_spec(spec)
        iron_child, water_child = s.children
        assert iron_child.ratio > water_child.ratio, "Iron (denser) should have higher ratio"

    def test_stoq_checksum_works_with_unified_model(self):
        s = build_quick_structure("Iron", 1.0)
        result = compute_stoq_checksum(s)
        report("Unified Model StoQ — Iron 1 kg", [
            f"Children:    {len(s.children)}",
            f"Stated mass: {sci(result['stated_mass_kg'])} kg",
            f"Defect:      {pct(result['mass_defect_percent'])}",
        ])
        assert result["mass_defect_percent"] == pytest.approx(-99.0, abs=1.0)

    def test_quark_chain_works_with_unified_model(self):
        s = load_structure("gold_ring")
        result = compute_quark_chain_checksum(s)
        report("Unified Model QC — Gold Ring", [
            f"Children:    {len(s.children)}",
            f"Defect:      {pct(result['mass_defect_percent'])}",
        ])
        assert abs(result["mass_defect_percent"]) < 2.0


class TestBuilder:
    """Structure builder tests."""

    def test_list_structures_returns_16(self):
        structures = list_structures()
        report("Built-in Structures", [
            f"{s['id']:30s}  mass={sci(s['stated_mass_kg'])} kg"
            for s in structures
        ])
        assert len(structures) == 16  # 7 originals + 9 default loads

    def test_all_structures_loadable(self):
        lines = []
        for entry in list_structures():
            s = load_structure(entry["id"])
            assert s is not None
            assert len(s.children) > 0
            lines.append(
                f"{entry['id']:30s}  children={len(s.children):2d}"
                f"  mass={sci(s.resolved_mass_kg)} kg"
            )
        report("Load — All Structures", lines)

    def test_custom_spec_builds(self):
        spec = {
            "stated_mass_kg": 100.0,
            "children": [
                {
                    "thickness": 50.0,
                    "materials": [
                        {"material": "Iron", "ratio": 0.85},
                        {"material": "Nickel", "ratio": 0.15},
                    ],
                },
                {
                    "thickness": 20.0,
                    "materials": [
                        {"material": "Copper", "ratio": 1.0},
                    ],
                },
            ],
        }
        s = build_structure_from_spec(spec)
        report("Custom Spec Build", [
            f"Children:    {len(s.children)}",
            f"Root mass:   {sci(s.resolved_mass_kg)} kg",
            f"Child 0:     Fe/Ni alloy",
            f"Child 1:     Cu",
        ])
        assert len(s.children) == 2
        assert s.resolved_mass_kg == pytest.approx(100.0)

    def test_quick_structure_builds(self):
        s = build_quick_structure("Water", 0.5)
        report("Quick Build — Water 0.5 kg", [
            f"Children:    {len(s.children)}",
            f"Root mass:   {sci(s.resolved_mass_kg)} kg",
            f"Child:       Water (H₂O)",
        ])
        assert len(s.children) == 1
        assert s.resolved_mass_kg == pytest.approx(0.5)
