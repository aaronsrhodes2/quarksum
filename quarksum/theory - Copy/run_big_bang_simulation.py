#!/usr/bin/env python3
"""Big Bang Forward Simulation — SSBM/RODM Cosmic Evolution.

Integrates the Friedmann equation from deep in the radiation era through
the present epoch and into the far future, tracking:

  1. r_s/R_H = 1.0 at EVERY timestep (the BH-universe identity)
  2. σ(T) field evolution through the QCD transition
  3. All Standard Model particle species (present, frozen, confined)
  4. Phase transitions and their SSBM relevance
  5. Bekenstein-Hawking entropy of the Hubble volume

All numbers derived from CONSTANTS and COSMOLOGY. No magic numbers.

Usage:
    PYTHONPATH="$PWD/../:$PWD/../Materia/qamss" python3 theory/run_big_bang_simulation.py
"""

import sys
import os

# Ensure paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'Materia', 'qamss'))

from materia.core.constants import CONSTANTS, PLANCK
from materia.core.cosmology import COSMOLOGY
from materia.core.scale_field import XI_SSBM, LAMBDA_QCD_GEV
from materia.models.cosmic_evolution import (
    run_evolution, print_evolution_report,
    snapshot_at_a, PHASE_TRANSITIONS,
    _g_full_SM, _g_photon_nu, _g_quark_per_flavor,
    _g_charged_lepton_per_flavor, _g_neutrino_per_flavor,
)


def main():
    print("=" * 100)
    print("BIG BANG FORWARD SIMULATION")
    print("SSBM/RODM Cosmic Evolution — Materia Framework")
    print("=" * 100)
    print()

    # ── Provenance ──────────────────────────────────────────────────────
    print("PROVENANCE — All inputs are measured or derived:")
    print(f"  H₀       = {COSMOLOGY.H0_km_s_Mpc} km/s/Mpc    (Planck 2018)")
    print(f"  Ω_b h²   = {COSMOLOGY.Omega_b_h2}               (Planck 2018)")
    print(f"  Ω_c h²   = {COSMOLOGY.Omega_c_h2}               (Planck 2018)")
    print(f"  n_s       = {COSMOLOGY.n_s}                      (Planck 2018)")
    print(f"  τ_reion   = {COSMOLOGY.tau_reion}                (Planck 2018)")
    print(f"  T_CMB     = {COSMOLOGY.T_CMB_K} K               (FIRAS)")
    print(f"  N_eff     = {COSMOLOGY.N_eff}                    (Standard Model)")
    print()
    print("DERIVED cosmological parameters:")
    print(f"  Ω_m      = {COSMOLOGY.Omega_m:.6f}    (= Ω_b + Ω_c)")
    print(f"  Ω_Λ      = {COSMOLOGY.Omega_Lambda:.6f}    (= 1 - Ω_m - Ω_r, flat)")
    print(f"  Ω_r      = {COSMOLOGY.Omega_r:.6e}    (from T_CMB + N_eff)")
    print(f"  Age      = {COSMOLOGY.age_gyr:.4f} Gyr  (Friedmann integral)")
    print(f"  R_H      = {COSMOLOGY.hubble_radius_gly:.4f} Gly   (= c/H₀)")
    print()
    print("SSBM parameters (derived from Planck inputs):")
    print(f"  ξ        = {XI_SSBM}              (= Ω_b/(Ω_b+Ω_c))")
    print(f"  γ        = {3-COSMOLOGY.n_s:.4f}               (= 3 - n_s)")
    print(f"  Λ_QCD    = {LAMBDA_QCD_GEV} GeV            (PDG reference)")
    print()
    print("DERIVED particle physics (from CONSTANTS, sourced from QuarkSum/PDG):")
    print(f"  m_top    = {CONSTANTS.m_top_quark:.3f} GeV     (QuarkSum)")
    print(f"  m_bottom = {CONSTANTS.m_bottom_quark:.3f} GeV      (QuarkSum)")
    print(f"  m_charm  = {CONSTANTS.m_charm_quark:.3f} GeV      (QuarkSum)")
    print(f"  m_W      = {CONSTANTS.m_W_GeV:.3f} GeV      (QuarkSum)")
    print(f"  m_Z      = {CONSTANTS.m_Z_GeV:.3f} GeV      (QuarkSum)")
    print(f"  m_Higgs  = {CONSTANTS.m_higgs_GeV:.3f} GeV    (QuarkSum)")
    print(f"  m_tau    = {CONSTANTS.m_tau_GeV:.4f} GeV     (QuarkSum)")
    print(f"  m_muon   = {CONSTANTS.m_muon_GeV:.4f} GeV    (QuarkSum)")
    print(f"  m_e      = {CONSTANTS.m_electron_GeV:.6f} GeV  (QuarkSum)")
    print(f"  G_F      = {CONSTANTS.G_F_GeV2:.7e} GeV⁻²  (PDG 2024)")
    print(f"  v_Higgs  = {CONSTANTS.v_higgs_GeV:.2f} GeV        (derived from G_F)")
    print()
    print("DERIVED g*(T) from DOF counting (no lookup tables):")
    print(f"  g*(full SM) = {_g_full_SM:.2f}    (28 bosonic + 78.75 fermionic)")
    print(f"  g*(today)   = {_g_photon_nu:.3f}     (γ + cooled ν)")
    print()

    # ── Run evolution ───────────────────────────────────────────────────
    # Start from a = 1e-15 (T ~ 2.3×10⁵ GeV, well above electroweak)
    # to capture the full σ field evolution.
    print("Running evolution from a = 1e-15 (T ~ 2.3×10⁵ GeV) to a = 10 (far future)...")
    print()

    snapshots = run_evolution(a_start=1e-15, a_end=10.0, n_points=300)

    # ── Main evolution table ────────────────────────────────────────────
    report = print_evolution_report(snapshots)
    print(report)

    # ── Particle species detail at key epochs ───────────────────────────
    print()
    print("=" * 100)
    print("PARTICLE SPECIES CENSUS AT KEY EPOCHS")
    print("=" * 100)

    # Pick representative epochs
    key_epochs = {
        "T ~ 200 GeV (above EW)": None,
        "T ~ 10 GeV (post-EW)": None,
        "T ~ 1 GeV (pre-QCD)": None,
        "T ~ 100 MeV (post-QCD)": None,
        "T ~ 1 MeV (BBN era)": None,
        "T ~ 0.1 MeV (post-e⁺e⁻)": None,
        "T ~ 0.3 eV (recombination)": None,
        "T ~ 0.235 meV (today)": None,
    }

    target_temps = [200.0, 10.0, 1.0, 0.1, 0.001, 0.0001, 3e-10, 2.35e-13]

    for (label, _), T_target in zip(key_epochs.items(), target_temps):
        # Find closest snapshot
        best = min(snapshots, key=lambda s: abs(s.temperature_GeV - T_target))
        print(f"\n  ── {label} (a={best.scale_factor:.2e}, "
              f"T={best.temperature_GeV:.3e} GeV, t={best.cosmic_time_display}) ──")
        print(f"  {'Species':<25s} {'Mass (GeV)':>12s} {'g_i':>6s} "
              f"{'Relativistic':>12s} {'Confined':>10s} {'Decoupled':>10s} "
              f"{'n (m⁻³)':>14s}")
        print(f"  {'-'*25} {'-'*12} {'-'*6} {'-'*12} {'-'*10} {'-'*10} {'-'*14}")
        for p in best.particle_species:
            rel_str = "YES" if p.is_relativistic else "no"
            conf_str = "CONFINED" if p.is_confined else "-"
            dec_str = "decoupled" if p.is_decoupled else "thermal"
            print(f"  {p.name:<25s} {p.mass_GeV:>12.4e} {p.g_contribution:>6.2f} "
                  f"{rel_str:>12s} {conf_str:>10s} {dec_str:>10s} "
                  f"{p.number_density_m3:>14.4e}")

    # ── σ field deep dive ───────────────────────────────────────────────
    print()
    print("=" * 100)
    print("σ FIELD EVOLUTION — DETAILED")
    print("=" * 100)
    print()
    print("The SSBM σ field measures deviation from standard QCD:")
    print("  σ(T) = ξ × ln(T/Λ_QCD)  when T > Λ_QCD")
    print("  σ(T) = 0                  when T ≤ Λ_QCD")
    print(f"  ξ = {XI_SSBM}, Λ_QCD = {LAMBDA_QCD_GEV} GeV")
    print()
    print(f"  {'a':>12s}  {'T (GeV)':>12s}  {'σ':>10s}  "
          f"{'Λ_eff (GeV)':>12s}  {'Λ_eff/Λ_QCD':>12s}  {'t':>14s}  Notes")
    print(f"  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*14}  -----")

    for snap in snapshots:
        if snap.sigma > 0 or (snap.temperature_GeV > 0.1 and snap.temperature_GeV < 0.5):
            ratio = snap.lambda_eff_GeV / LAMBDA_QCD_GEV
            note = ""
            if 0.14 < snap.temperature_GeV < 0.17:
                note = "← QCD TRANSITION (σ → 0 here)"
            elif snap.temperature_GeV > 150:
                note = "← Electroweak regime"
            elif 0.2 < snap.temperature_GeV < 0.3:
                note = "← Just above Λ_QCD"
            print(f"  {snap.scale_factor:>12.4e}  {snap.temperature_GeV:>12.4e}  "
                  f"{snap.sigma:>10.6f}  {snap.lambda_eff_GeV:>12.6f}  "
                  f"{ratio:>12.6f}  {snap.cosmic_time_display:>14s}  {note}")

    print()
    print("  KEY: At the QCD transition, σ → 0 and Λ_eff → Λ_QCD.")
    print("  After this moment, the universe is in the σ=0 regime.")
    print("  Standard physics applies everywhere EXCEPT near local BHs/NS,")
    print("  which have their own gravitational σ(r) profiles.")

    # ── The money shot: r_s/R_H ─────────────────────────────────────────
    print()
    print("=" * 100)
    print("THE IDENTITY: r_s/R_H = 1.0 AT ALL TIMES")
    print("=" * 100)
    print()
    print("  PROOF (algebraic, no approximations):")
    print("    At any time t, for a flat (Ω_total=1) Friedmann universe:")
    print("    R_H(t) = c / H(t)")
    print("    ρ_total(t) = 3H(t)² / (8πG)     [Friedmann equation, flat]")
    print("    V_H(t) = (4π/3) R_H³")
    print("    M_total(t) = ρ_total × V_H = 3H²/(8πG) × (4π/3)(c/H)³ = c³/(2GH)")
    print("    r_s(t) = 2GM/c² = 2G × c³/(2GH) / c² = c/H = R_H(t)")
    print()
    print("    Therefore r_s(t) = R_H(t) identically, ∀t.")
    print("    This holds in radiation domination, matter domination,")
    print("    dark energy domination, and all transitions between them.")
    print()

    rs_values = [s.rs_over_RH for s in snapshots]
    print(f"  NUMERICAL VERIFICATION ({len(snapshots)} timesteps, "
          f"a = {snapshots[0].scale_factor:.1e} to {snapshots[-1].scale_factor:.1e}):")
    print(f"    min(r_s/R_H)  = {min(rs_values):.15f}")
    print(f"    max(r_s/R_H)  = {max(rs_values):.15f}")
    print(f"    mean(r_s/R_H) = {sum(rs_values)/len(rs_values):.15f}")
    print(f"    max |Δ|       = {max(abs(v-1.0) for v in rs_values):.2e}")
    print()

    # Show a few representative epochs
    print("  Spot checks:")
    for snap in snapshots:
        if snap.temperature_GeV > 1e4 and snap.temperature_GeV < 2e4:
            print(f"    a={snap.scale_factor:.2e}  T={snap.temperature_GeV:.1e} GeV  "
                  f"(radiation era)     r_s/R_H = {snap.rs_over_RH:.15f}")
            break
    for snap in snapshots:
        if 0.1 < snap.temperature_GeV < 0.2:
            print(f"    a={snap.scale_factor:.2e}  T={snap.temperature_GeV:.1e} GeV  "
                  f"(QCD transition)    r_s/R_H = {snap.rs_over_RH:.15f}")
            break
    for snap in snapshots:
        if 2e-10 < snap.temperature_GeV < 4e-10:
            print(f"    a={snap.scale_factor:.2e}  T={snap.temperature_GeV:.1e} GeV  "
                  f"(recombination)     r_s/R_H = {snap.rs_over_RH:.15f}")
            break
    for snap in snapshots:
        if 2e-13 < snap.temperature_GeV < 3e-13:
            print(f"    a={snap.scale_factor:.2e}  T={snap.temperature_GeV:.1e} GeV  "
                  f"(today, a≈1)        r_s/R_H = {snap.rs_over_RH:.15f}")
            break
    for snap in snapshots:
        if snap.scale_factor > 9.0:
            print(f"    a={snap.scale_factor:.2e}  T={snap.temperature_GeV:.1e} GeV  "
                  f"(far future)        r_s/R_H = {snap.rs_over_RH:.15f}")
            break

    print()
    print("  CONCLUSION: The universe satisfies the black hole boundary")
    print("  condition r_s = R_H at every moment in cosmic history.")
    print("  This is not a numerical coincidence — it is an algebraic")
    print("  identity of flat Friedmann cosmology.")
    print()
    print("  SSBM INTERPRETATION: The universe IS the interior of a")
    print("  Schwarzschild geometry whose radius grows with the Hubble")
    print("  flow. The identity holds in radiation, matter, and dark")
    print("  energy dominated eras. The boundary condition that makes")
    print("  the universe 'look like a black hole' is never broken.")
    print()

    # ── Assertions ──────────────────────────────────────────────────────
    n_pass = 0
    n_fail = 0

    def check(name, condition):
        nonlocal n_pass, n_fail
        if condition:
            n_pass += 1
        else:
            n_fail += 1
            print(f"  FAIL: {name}")

    print("=" * 100)
    print("CROSS-CHECK ASSERTIONS")
    print("=" * 100)

    # r_s/R_H identity
    for snap in snapshots:
        check(f"r_s/R_H = 1 at a={snap.scale_factor:.2e}",
              abs(snap.rs_over_RH - 1.0) < 1e-10)

    # σ should be zero below Λ_QCD
    for snap in snapshots:
        if snap.temperature_GeV < LAMBDA_QCD_GEV * 0.9:
            check(f"σ = 0 below QCD at T={snap.temperature_GeV:.2e}",
                  snap.sigma == 0.0)

    # σ should be positive above Λ_QCD
    for snap in snapshots:
        if snap.temperature_GeV > LAMBDA_QCD_GEV * 1.1:
            check(f"σ > 0 above QCD at T={snap.temperature_GeV:.2e}",
                  snap.sigma > 0.0)

    # Radiation dominates early, matter in middle, Λ late
    check("Radiation dominates at a=1e-15",
          snapshots[0].dominant_component == "radiation")
    check("Dark energy dominates at a=10",
          snapshots[-1].dominant_component == "dark energy")

    # Entropy increases monotonically
    for i in range(1, len(snapshots)):
        check(f"S_BH increases at step {i}",
              snapshots[i].bekenstein_entropy >= snapshots[i-1].bekenstein_entropy * 0.999)

    # g* should decrease over time (species freeze out)
    check("g* decreases from early to late",
          snapshots[0].gstar_value > snapshots[-1].gstar_value)

    # Today's temperature
    snap_today = min(snapshots, key=lambda s: abs(s.scale_factor - 1.0))
    check(f"T(a=1) ≈ T_CMB = {COSMOLOGY.T_CMB_K} K",
          abs(snap_today.temperature_K - COSMOLOGY.T_CMB_K) / COSMOLOGY.T_CMB_K < 0.01)

    # Particle species checks at today
    for p in snap_today.particle_species:
        if "top" in p.name:
            check("Top quark not relativistic today", not p.is_relativistic)
            check("Top quark decoupled today", p.is_decoupled)
        if "photon" in p.name:
            check("Photon relativistic today", p.is_relativistic)
            check("Photon not decoupled today", not p.is_decoupled)
        if "gluon" in p.name:
            check("Gluon confined today", p.is_confined)
        if "ν_e" in p.name:
            check("ν_e decoupled today", p.is_decoupled)
            check("ν_e relativistic today", p.is_relativistic)

    print()
    print(f"  Results: {n_pass} passed, {n_fail} failed, {n_pass + n_fail} total")
    if n_fail == 0:
        print("  ✓ ALL CHECKS PASSED")
    else:
        print(f"  ✗ {n_fail} checks FAILED")

    print()
    print("=" * 100)
    print("END OF SIMULATION")
    print("=" * 100)

    return n_fail == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
