# Baseline Bookmark — 2026-03-14

## Combined Baseline C (QuarkSum + Materia)

- **50 files**, **2047 tests**, **89.8% pass rate**, **63.5s**
- 1838 passed, 12 failed, 3 errors, 45 skipped, 149 xfail
- **48 green files**, **2 red files**

### Δ from Baseline B (2026-03-13)
- Files: 48 → 50 (+2 new test files)
- Tests: 1926 → 2047 (+121 tests)
- Passed: 1698 → 1838 (+140)
- Failed: 23 → 12 (−11)
- Errors: 35 → 3 (−32)
- Green files: 40 → 48 (+8 flipped green)
- Red files: 8 → 2 (−6 fixed)
- xfail: 149 → 149 (unchanged — 30 science_gaps + 118 model_conformance + 1 chaotic_nbody)

### What changed (B → C)
- **New:** test_sigma_chain.py (64 tests) — σ-aware mass chain with Higgs/QCD decomposition
- **New:** test_sigma_cross_project.py (59 tests) — cross-project σ consistency proof
- **Fixed:** a_C_MeV in sigma.py — derived from first principles, now bit-identical across projects
- **Fixed:** 6 previously-red files flipped green (library_db, nubase_cross_validation, particle_mass_checksum, scientific_data, sol_characterization, test_checksum)
- **Remaining red:** test_jpl_ephemeris (network-gated EXTREME), test_position_precision (simulation-gated EXTREME)

## Green (48 files)

### QuarkSum (8 files, all green)
- test_allocation.py: 12 pass
- test_api_coverage.py: 46 pass
- test_checksum.py: 108 pass
- test_cli.py: 23 pass
- test_reference_validation.py: 77 pass
- test_resolver.py: 18 pass
- test_sigma_chain.py: 64 pass
- test_structure.py: 6 pass

### Materia (40 green files)
- test_backwards_time.py: 0 pass +6 skip
- test_bh_conversion.py: 9 pass
- test_chaotic_nbody.py: 4 pass +1 xfail +2 skip
- test_cross_module_consistency.py: 28 pass +1 skip
- test_em_radiation.py: 28 pass
- test_ephemeris_prediction.py: 12 pass +1 skip
- test_falsification.py: 48 pass
- test_fluid_dynamics.py: 36 pass
- test_friedmann.py: 34 pass
- test_generator/test_material_generator.py: 6 pass
- test_gravity_celestial.py: 38 pass
- test_gw_waveform.py: 29 pass
- test_library/test_library_db.py: 9 pass
- test_local_library.py: 89 pass
- test_material_response.py: 29 pass
- test_mhd.py: 18 pass
- test_models/test_hierarchy.py: 19 pass
- test_models/test_model_conformance.py: 47 pass +118 xfail
- test_models/test_multi_layer.py: 12 pass
- test_nbody.py: 15 pass +1 skip
- test_nubase_cross_validation.py: 25 pass
- test_nucleosynthesis.py: 38 pass
- test_numerical_relativity.py: 32 pass
- test_observational_comparison.py: 19 pass
- test_orbit_fit.py: 22 pass
- test_orbital_mechanics.py: 35 pass
- test_particle_mass_checksum.py: 108 pass +24 skip
- test_quantum/test_piecewise_potential.py: 9 pass
- test_rotation_curves.py: 29 pass
- test_science_gaps.py: 0 pass +30 xfail
- test_scientific_data.py: 202 pass
- test_scientific_structure.py: 152 pass +10 skip
- test_sigma_cross_project.py: 59 pass
- test_sigma_feedback.py: 28 pass
- test_sigma_sweep.py: 56 pass
- test_sol_characterization.py: 25 pass
- test_spectral_data.py: 36 pass
- test_stellar_composition.py: 31 pass
- test_stellar_structure.py: 32 pass
- test_wave_physics.py: 23 pass

## Red (2 files)

| File | P | F | E | S | Category |
|------|---|---|---|---|----------|
| [Materia] test_jpl_ephemeris.py | 13 | 12 | 2 | 0 | Network-gated (EXTREME) |
| [Materia] test_position_precision.py | -- | -- | 1 | 0 | Simulation-gated (EXTREME) |

## Simulation Runners (theory/)

### run_bh_formation_simulation.py
- 12/12 cross-checks pass
- 10 M☉ iron core collapse, 500 points, R = 100 r_s → 10⁻¹⁴ r_s
- All 8 bond types fail in correct order
- Conversion at r/r_s = 1.54×10⁻¹³

### run_big_bang_simulation.py
- All assertions pass (300+ individual checks)
- r_s/R_H = 1.0 verified at every timestep (max |Δ| < 10⁻¹⁵)
- Full SM particle census at 8 key epochs
- σ field evolution through QCD transition

### run_bh_to_universe.py (NEW — chained simulation)
- 16/16 cross-checks pass
- BH formation → conversion → cosmic evolution as one timeline
- σ overlap found: σ_BH = 1.085 ≈ σ_cosmic = 1.082 at T ≈ 203 GeV (EW scale)
- r_s = R_H identity verified on both sides of the junction

### tangent_check.py (NEW — C¹ continuity test)
- Result: **C⁰ only, NOT C¹**
- σ values match (1.085) but slopes differ by ~10⁹
- σ_BH(T_virial) is NOT ξ ln(T) — different functional form (A_fit/ξ = 0.14)
- BH gravitational σ and cosmic thermal σ are different functions that happen to cross
- Parked for later investigation — may indicate missing physics in the σ mapping

## xfail Inventory (149 total, unchanged)
- test_science_gaps.py: 30 xfails (missing model implementations)
- test_model_conformance.py: 118 xfails (incomplete physics modules)
- test_chaotic_nbody.py: 1 xfail (numerical edge case)

## Runner
- `/sessions/loving-pensive-euler/run_baseline.py` — combined runner with file-based module loading
- Pytest shim v3.0.0 at `/sessions/loving-pensive-euler/pytest_shim/pytest.py`
