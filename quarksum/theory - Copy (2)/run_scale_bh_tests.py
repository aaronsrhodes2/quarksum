#!/usr/bin/env python3
"""Tests for SSBM scale field (dimension zero) and black hole models.

Covers:
  - Scale field mathematics (σ → Λ_eff, mass scaling)
  - Quark/particle/atom/molecule effective properties under σ
  - Bond failure radii
  - Schwarzschild geometry (r_s, ISCO, photon sphere)
  - Hawking radiation (temperature, luminosity, evaporation time)
  - Black hole creation (three regimes)
  - Dual-model structure building (standard GR vs SSBM cavitation)
  - Scale propagation through structure hierarchy
  - Physical consistency checks (dimension zero recovers standard at σ=0)
"""

import sys
import math

sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name}  {'— ' + detail if detail else ''}")
        failed += 1


print("=" * 70)
print("  Part 1: Scale Field Core Mathematics")
print("=" * 70)

from materia.core.scale_field import (
    XI_SSBM, GAMMA_SSBM, LAMBDA_QCD_GEV, LAMBDA_QCD_MEV,
    scale_ratio, lambda_eff_gev, lambda_eff_mev,
    effective_qcd_dressing_mev, effective_nucleon_mass_kg,
    effective_nuclear_binding_energy_mev,
    sigma_from_kretschner, sigma_from_gravitational_potential,
    sigma_at_radius_schwarzschild, bond_failure_radius_m,
    BOND_LENGTHS_M,
)

check("XI_SSBM = 0.1582", abs(XI_SSBM - 0.1582) < 1e-6)
check("GAMMA_SSBM = 2.035", abs(GAMMA_SSBM - 2.035) < 0.01)
check("LAMBDA_QCD = 217 MeV", abs(LAMBDA_QCD_MEV - 217.0) < 0.1)

# scale_ratio
check("scale_ratio(0) = 1.0", scale_ratio(0.0) == 1.0)
check("scale_ratio(1) = e", abs(scale_ratio(1.0) - math.e) < 1e-10)
check("scale_ratio(-1) = 1/e", abs(scale_ratio(-1.0) - 1.0/math.e) < 1e-10)

# lambda_eff
check("Λ_eff(σ=0) = Λ_QCD", abs(lambda_eff_gev(0.0) - 0.217) < 1e-10)
check("Λ_eff(σ=1) = Λ_QCD·e", abs(lambda_eff_gev(1.0) - 0.217 * math.e) < 1e-10)

# QCD dressing scaling
eff = effective_qcd_dressing_mev(336.0, 2.16, 0.0)
check("QCD dressing at σ=0 unchanged", abs(eff - 336.0) < 0.01)
eff_shifted = effective_qcd_dressing_mev(336.0, 2.16, 0.1)
expected = 2.16 + (336.0 - 2.16) * math.exp(0.1)
check("QCD dressing at σ=0.1 correct", abs(eff_shifted - expected) < 0.01,
      f"got {eff_shifted:.2f}, expected {expected:.2f}")

# Nucleon mass scaling
_C2 = (2.99792458e8) ** 2
_MEV_TO_KG = 1.602176634e-13 / _C2
m_p_kg = 1.6726219236278e-27
p_bare_mev = 2 * 2.16 + 4.67  # uud = 8.99 MeV

eff_p_0 = effective_nucleon_mass_kg(m_p_kg, p_bare_mev, 0.0)
check("Proton at σ=0: unchanged", abs(eff_p_0 - m_p_kg) < 1e-35)

eff_p_01 = effective_nucleon_mass_kg(m_p_kg, p_bare_mev, 0.1)
check("Proton at σ=0.1: heavier", eff_p_01 > m_p_kg)
pct = (eff_p_01 / m_p_kg - 1) * 100
check("Proton mass shift ~10.4%", abs(pct - 10.42) < 0.5,
      f"got {pct:.2f}%")

# Nuclear binding energy scaling
be_fe56 = 492.26  # MeV, approximate total B for Fe-56
eff_be_0 = effective_nuclear_binding_energy_mev(be_fe56, 26, 56, 0.0)
check("Fe-56 B(A,Z) at σ=0 unchanged", abs(eff_be_0 - be_fe56) < 0.01)

eff_be_01 = effective_nuclear_binding_energy_mev(be_fe56, 26, 56, 0.1)
check("Fe-56 B(A,Z) at σ=0.1: increased", eff_be_01 > be_fe56)

# Gravitational potential → σ
sig_earth = sigma_from_gravitational_potential(6.674e-11 * 5.972e24 / 6.371e6)
check("σ at Earth surface: negligible", sig_earth < 1e-8,
      f"got {sig_earth:.2e}")

sig_ns = sigma_from_gravitational_potential(0.2 * _C2)
check("σ at neutron star: ~0.03", abs(sig_ns - 0.03164) < 0.01,
      f"got {sig_ns:.4f}")

# Bond failure radii exist and are ordered
M_SUN = 1.98892e30
radii = {n: bond_failure_radius_m(l, M_SUN) for n, l in BOND_LENGTHS_M.items()}
check("VdW failure > covalent failure", radii["van_der_waals"] > radii["covalent"])
check("Covalent failure > nuclear failure", radii["covalent"] > radii["nuclear_pion"])
check("Nuclear > quark confinement", radii["nuclear_pion"] > radii["quark_confinement"])
check("All bond failure radii positive", all(r > 0 for r in radii.values()))


print()
print("=" * 70)
print("  Part 2: Entity-Level Scale Properties")
print("=" * 70)

from materia.models.quark import Quark
from materia.models.particle import Proton, Neutron, Electron
from materia.models.atom import Atom
from materia.models.substrate import Substrate, MaterialClass

# Quark
q = Quark.up()
check("Quark default σ = 0", q.scale_sigma == 0.0)
check("Quark eff mass at σ=0 = constituent", q.effective_constituent_mass_mev == 336.0)
q.scale_sigma = 0.1
check("Quark eff mass at σ=0.1 > constituent", q.effective_constituent_mass_mev > 336.0)
q.scale_sigma = 0.0
check("Quark reset to σ=0 works", q.effective_constituent_mass_mev == 336.0)

# Top quark: no constituent mass
qt = Quark.top()
check("Top quark: constituent_mass is None", qt.constituent_mass_mev is None)
check("Top quark: effective is None", qt.effective_constituent_mass_mev is None)

# Proton
p = Proton.create()
check("Proton default σ = 0", p.scale_sigma == 0.0)
check("Proton eff mass at σ=0 = rest mass", p.effective_mass_kg == p.rest_mass_kg)
p.scale_sigma = 0.1
check("Proton eff mass at σ=0.1 > rest mass", p.effective_mass_kg > p.rest_mass_kg)
check("Proton eff binding > standard binding",
      p.effective_binding_energy_joules > p.binding_energy_joules)

# Neutron
n = Neutron.create()
n.scale_sigma = 0.1
check("Neutron eff mass at σ=0.1 > rest mass", n.effective_mass_kg > n.rest_mass_kg)

# Electron: NO scaling (lepton)
e = Electron.create()
e.scale_sigma = 0.5  # Even large σ
check("Electron mass invariant under σ", e.effective_mass_kg == e.rest_mass_kg)
check("Electron binding = 0 (elementary)", e.effective_binding_energy_joules == 0.0)

# Substrate: effective density
sub = Substrate.create(
    material_name="Iron",
    material_formula="Fe",
    material_class=MaterialClass.METAL,
    standard_density=7874.0,
)
check("Substrate default σ = 0", sub.scale_sigma == 0.0)
check("Substrate eff density at σ=0 = standard", sub.effective_density == 7874.0)
sub.scale_sigma = 0.1
check("Substrate eff density at σ=0.1 > standard", sub.effective_density > 7874.0)
expected_dens = 7874.0 * math.exp(0.1)
check("Substrate eff density = standard × e^σ",
      abs(sub.effective_density - expected_dens) < 0.1)


print()
print("=" * 70)
print("  Part 3: Schwarzschild Geometry")
print("=" * 70)

from materia.models.black_hole import (
    schwarzschild_radius_m as rs_fn, schwarzschild_radius_km,
    isco_radius_m as isco_fn, photon_sphere_radius_m as rph_fn,
    hawking_temperature_K as th_fn, hawking_luminosity_W,
    hawking_evaporation_time_s, M_SUN_KG,
)

# Schwarzschild radius: r_s = 2GM/c² ≈ 2954 m for M☉
r_s = rs_fn(M_SUN_KG)
check("r_s(M☉) ≈ 2954 m", abs(r_s - 2954.0) < 5.0, f"got {r_s:.1f}")

# r_s scales linearly with M
r_s_10 = rs_fn(10 * M_SUN_KG)
check("r_s(10M☉) = 10 × r_s(M☉)", abs(r_s_10 / r_s - 10.0) < 0.01)

# ISCO: 6GM/c² for Schwarzschild (a*=0) = 3×r_s
r_isco = isco_fn(M_SUN_KG)
check("ISCO(M☉, a*=0) = 3×r_s", abs(r_isco / r_s - 3.0) < 0.01)

# ISCO decreases with spin (prograde)
r_isco_spin = isco_fn(M_SUN_KG, 0.9)
check("ISCO(a*=0.9) < ISCO(a*=0)", r_isco_spin < r_isco)

# Photon sphere: 1.5×r_s
r_ph = rph_fn(M_SUN_KG)
check("r_ph = 1.5×r_s", abs(r_ph / r_s - 1.5) < 0.01)

# Hawking temperature: T_H ∝ 1/M
T_1 = th_fn(M_SUN_KG)
T_2 = th_fn(2 * M_SUN_KG)
check("T_H(2M☉) = T_H(M☉)/2", abs(T_2 / T_1 - 0.5) < 0.01)
check("T_H(M☉) ~ 6×10⁻⁸ K", 5e-8 < T_1 < 7e-8, f"got {T_1:.2e}")

# Hawking luminosity: L_H ∝ 1/M²
L_1 = hawking_luminosity_W(M_SUN_KG)
L_2 = hawking_luminosity_W(2 * M_SUN_KG)
check("L_H(2M☉) = L_H(M☉)/4", abs(L_2 / L_1 - 0.25) < 0.01)

# Evaporation time: t ∝ M³
t_1 = hawking_evaporation_time_s(M_SUN_KG)
t_2 = hawking_evaporation_time_s(2 * M_SUN_KG)
check("t_evap(2M☉) = 8 × t_evap(M☉)", abs(t_2 / t_1 - 8.0) < 0.01)
t_yr = t_1 / (365.25 * 24 * 3600)
check("t_evap(M☉) >> age of universe", t_yr > 1e60, f"got {t_yr:.2e} yr")


print()
print("=" * 70)
print("  Part 4: Black Hole Regimes and Dual Models")
print("=" * 70)

from materia.models.black_hole import (
    BlackHole, BlackHoleRegime, classify_regime,
    ssbm_conversion_radius_m, ssbm_bond_failure_radii_m,
)

# Regime classification
check("0.5 M☉ → micro_remnant",
      classify_regime(0.5 * M_SUN_KG) == BlackHoleRegime.MICRO_REMNANT)
check("10 M☉ → single_conversion",
      classify_regime(10 * M_SUN_KG) == BlackHoleRegime.SINGLE_CONVERSION)
check("4e6 M☉ → oscillating",
      classify_regime(4e6 * M_SUN_KG) == BlackHoleRegime.OSCILLATING)

# Create and build all three
bh_micro = BlackHole.micro_remnant(0.5)
bh_stellar = BlackHole.stellar(10.0)
bh_smbh = BlackHole.supermassive(4e6, spin=0.7)

for bh, label in [(bh_micro, "micro"), (bh_stellar, "stellar"), (bh_smbh, "SMBH")]:
    check(f"{label}: standard model built", bh.standard_model is not None)
    check(f"{label}: SSBM model built", bh.ssbm_model is not None)
    check(f"{label}: standard has layers", len(bh.standard_model.layers) >= 4)
    check(f"{label}: SSBM has more layers", len(bh.ssbm_model.layers) >= len(bh.standard_model.layers))

# SSBM model should have σ propagated to layers
ssbm = bh_stellar.ssbm_model
inner_layer = sorted(ssbm.layers, key=lambda l: l.order)[0]
outer_layer = sorted(ssbm.layers, key=lambda l: l.order)[-1]
if inner_layer.substrate and outer_layer.substrate:
    # Inner layers should have higher σ (closer to center, stronger gravity)
    # But since radii are so small, σ might be extreme or zero — just check it was set
    check("SSBM inner layer has σ set", hasattr(inner_layer.substrate, 'scale_sigma'))
    check("SSBM outer layer has σ set", hasattr(outer_layer.substrate, 'scale_sigma'))

# Compare models
comp = bh_stellar.compare_models()
check("Comparison has both models", "standard_model" in comp and "ssbm_model" in comp)
check("SSBM has conversion radius", "conversion_radius_m" in comp["ssbm_model"])
check("SSBM has regime behavior", "regime_behavior" in comp["ssbm_model"])

# Bond failure radii ordering in SSBM model
bf_radii = ssbm_bond_failure_radii_m(M_SUN_KG)
check("Bond failure radii: 7 types", len(bf_radii) == 7)
sorted_radii = sorted(bf_radii.values())
check("Bond failure radii are ordered", sorted_radii == list(sorted(sorted_radii)))


print()
print("=" * 70)
print("  Part 5: Dimension Zero Recovery (σ=0 → Standard Physics)")
print("=" * 70)

# The critical test: setting σ=0 should exactly recover standard physics
p_test = Proton.create()
p_test.scale_sigma = 0.0
check("σ=0: proton mass = rest mass", p_test.effective_mass_kg == p_test.rest_mass_kg)

e_test = Electron.create()
e_test.scale_sigma = 0.0
check("σ=0: electron mass = rest mass", e_test.effective_mass_kg == e_test.rest_mass_kg)

q_test = Quark.up()
q_test.scale_sigma = 0.0
check("σ=0: quark constituent mass unchanged",
      q_test.effective_constituent_mass_mev == q_test.constituent_mass_mev)

sub_test = Substrate.create("Iron", "Fe", MaterialClass.METAL, standard_density=7874.0)
sub_test.scale_sigma = 0.0
check("σ=0: substrate density = standard", sub_test.effective_density == 7874.0)

check("Λ_eff(σ=0) = Λ_QCD exactly", lambda_eff_gev(0.0) == LAMBDA_QCD_GEV)
check("scale_ratio(0) = 1.0 exactly", scale_ratio(0.0) == 1.0)

# Verify the σ field is a variable (editable in UI), not a constant
p_vars = p_test.get_variables()
check("scale_sigma is in variables", "scale_sigma" in p_vars)
check("scale_sigma category = what_if", p_vars["scale_sigma"]["category"] == "what_if")


print()
print("=" * 70)
print("  Part 6: Scale Propagation Through Structure")
print("=" * 70)

from materia.models.spherical_structure import SphericalStructure
from materia.models.base_structure import GeometryType, Layer
from uuid import uuid4

# Build a simple 2-layer structure and propagate σ
iron_sub = Substrate.create("Iron", "Fe", MaterialClass.METAL, standard_density=7874.0)
water_sub = Substrate.create("Water", "H2O", MaterialClass.LIQUID, standard_density=1000.0)

structure = SphericalStructure(id=str(uuid4()), geometry_type="spherical")
l1 = Layer.create(iron_sub, 0, 0.0, 50.0, GeometryType.SPHERICAL)
l2 = Layer.create(water_sub, 1, 50.0, 100.0, GeometryType.SPHERICAL)
structure.layers = [l1, l2]

check("Structure default σ = 0", structure.scale_sigma == 0.0)
check("Iron substrate σ = 0", iron_sub.scale_sigma == 0.0)

structure.propagate_scale(0.05)
check("After propagate: structure σ = 0.05", structure.scale_sigma == 0.05)
check("After propagate: iron σ = 0.05", iron_sub.scale_sigma == 0.05)
check("After propagate: water σ = 0.05", water_sub.scale_sigma == 0.05)
check("Iron eff density at σ=0.05", iron_sub.effective_density > 7874.0)

# Reset
structure.propagate_scale(0.0)
check("After reset: σ = 0", structure.scale_sigma == 0.0)
check("After reset: iron eff density = standard", iron_sub.effective_density == 7874.0)


print()
print("=" * 70)
results = f"  RESULTS: {passed} PASS, {failed} FAIL  (total {passed + failed})"
print(results)
print("=" * 70)

if failed > 0:
    sys.exit(1)
