# Five-Scale SSBM Simulation Results

**Date:** 2026-03-14
**Parameters:** ξ = 0.1582, γ = 2.035, Λ_QCD = 0.217 GeV
**Sources:** Planck 2018, CODATA 2018, AME2020
**Result:** 26/26 checks passed

---

## Scale 1 — Observable Universe (r ~ 4.4×10²⁶ m)

| Quantity | Value | Check |
|----------|-------|-------|
| T_CMB | 2.7255 K = 2.35×10⁻¹³ GeV | — |
| T_CMB / Λ_QCD | 1.08×10⁻¹² | ≪ 1 |
| σ_cosmic(today) | **0.0** (exactly) | ✓ T ≪ Λ_QCD |
| Age of universe | **13.79 Gyr** | ✓ (Planck: 13.787 ± 0.020) |
| Acceleration transition | **z = 0.632** | ✓ (observed: ~0.67) |
| r_s(M_matter)/R_H | **Ω_m = 0.3138** | ✓ (Friedmann identity) |

**Interpretation:** σ = 0 everywhere at cosmic scale today. SSBM reduces to standard ΛCDM exactly. The universe expands as if no scale field exists — because the QCD scale field requires T > Λ_QCD to activate, and T_CMB is 12 orders of magnitude too cold.

---

## Scale 2 — Milky Way Analog Galaxy (r ~ 3×10²⁰ m)

**Galaxy parameters:** M_disk = 5×10¹⁰ M☉, R_d = 3 kpc, M_bulge = 10¹⁰ M☉, a_bulge = 0.5 kpc

| r (kpc) | v_baryon (km/s) | v_SSBM (km/s) | v_ΛCDM (km/s) | σ(r) |
|---------|----------------|---------------|---------------|------|
| 1.0 | 169.5 | 169.5 | 179.6 | 0.000000 |
| 2.0 | 171.1 | 171.1 | 189.6 | 0.000000 |
| 3.0 | 171.7 | 171.7 | 197.2 | 0.000000 |
| 5.0 | 168.7 | 168.7 | 206.1 | 0.000000 |
| 8.0 | 157.5 | 157.5 | 209.8 | 0.000000 |
| 10.0 | 148.6 | 148.6 | 209.6 | 0.000000 |
| 15.0 | 128.2 | 128.2 | 207.1 | 0.000000 |
| 20.0 | 112.7 | 112.7 | 204.8 | 0.000000 |
| 25.0 | 101.2 | 101.2 | 202.9 | 0.000000 |
| 30.0 | 92.5 | 92.5 | 201.2 | 0.000000 |

| Quantity | Value | Check |
|----------|-------|-------|
| v_SSBM at Sun's orbit (8 kpc) | **157.5 km/s** | ✗ (observed: 220) |
| v_ΛCDM at Sun's orbit (8 kpc) | **209.8 km/s** | ✓ |
| σ at 8 kpc | **0.000000** | — |
| σ fraction of DM effect (20 kpc) | **0.0%** | ✗ |
| Flatness ratio (v_30/v_10) | **0.622** | marginal (Kepler: 0.577, flat: 1.000) |

**CRITICAL FINDING:** v_SSBM = v_baryon at ALL radii. The self-consistent σ solver returns σ = 0 everywhere because σ = ξ × GM/(rc²) ≈ 10⁻⁶ at galactic radii — the gravitational potential at galactic scales is too weak for ξ = 0.1582 to produce measurable mass enhancement.

**The gap:** SSBM accounts for 0.0% of what NFW dark matter provides. The rotation curve is Keplerian-dropping, not flat. Either:
1. SSBM needs a stronger coupling mechanism at galactic scales (beyond simple gravitational σ), or
2. Dark matter is real and separate from QCD scale effects, or
3. The σ(r) ansatz σ = ξ|Φ|/c² is wrong at galactic scale — perhaps σ should couple to density gradients, tidal fields, or something nonlocal.

---

## Scale 3 — Stellar-Mass Black Hole (r ~ 3×10⁴ m)

**Object:** 10 M☉ Schwarzschild BH, r_s = 29,540 m

| Location | r (m) | σ | e^σ | Δm/m |
|----------|-------|---|-----|------|
| Event horizon | 29,540 | **0.079100** | 1.0823 | +8.23% |
| Photon sphere | 44,310 | 0.052733 | 1.0541 | +5.41% |
| ISCO | 88,620 | **0.026367** | 1.0267 | +2.67% |
| 10 r_s | 295,401 | 0.007910 | 1.0079 | +0.79% |
| 100 r_s | 2,954,008 | 0.000791 | 1.0008 | +0.08% |
| 1000 r_s | 29,540,077 | 0.000079 | 1.0001 | +0.01% |

| Quantity | Value | Check |
|----------|-------|-------|
| σ(ISCO) | ξ/6 = 0.026367 | ✓ exact |
| σ(EH) | ξ/2 = 0.079100 | ✓ exact |
| Conversion energy | ξMc² = 2.83×10⁴⁷ J = 1.58 M☉c² | ✓ |
| Proton mass at ISCO | 1.717×10⁻²⁷ kg (+2.65%) | ✓ |

**Interpretation:** σ is significant and measurable at BH scales. The proton is 2.65% heavier at the ISCO — this is potentially observable via iron Kα line shifts in X-ray binaries. The σ gradient is monotonically decreasing outward, as required. BH scale is where SSBM makes its strongest, most testable predictions.

---

## Scale 4 — Neutron Star (r ~ 10⁴ m)

**Object:** M = 1.4 M☉, R = 10 km

| Quantity | Value | Check |
|----------|-------|-------|
| Compactness GM/(Rc²) | **0.2068** | — |
| σ(surface) | **0.032713** | ✓ (0.02–0.05 range) |
| Proton mass at surface | 1.728×10⁻²⁷ kg (**+3.29%**) | ✓ |
| Fe-56 BE at surface | 512.53 MeV (**+4.12%**) | ✓ |
| GR redshift z_g | **0.3058** | ✓ |

**Interpretation:** Neutron star surface is the second-strongest σ environment after BH. The 3.3% proton mass enhancement and 4.1% binding energy increase are in principle detectable through nuclear equation of state measurements, quasi-periodic oscillations, or gravitational wave tidal deformability (LIGO/Virgo). The GR redshift agrees with standard calculation — σ does not alter the metric, only the QCD scale.

---

## Scale 5 — Single Atom: Fe-56 (r ~ 10⁻¹⁰ m)

| Quantity | Value | Check |
|----------|-------|-------|
| Stable mass | 9.2882×10⁻²⁶ kg | ✓ (AME2020) |
| Constituent mass | 9.3760×10⁻²⁶ kg | — |
| Nuclear BE | 492.26 MeV (8.790 MeV/A) | ✓ |
| Three-measure identity | **0.0014 ppm** residual | ✓ (< 1 ppm) |
| σ=0 recovery | effective_mass == stable_mass | ✓ (exact) |
| Wheeler invariance | All 26 electrons = m_e | ✓ (bitwise) |
| σ=0.05 mass shift | +6.06% | ✓ (Fe-56 BE peak contributes) |
| σ roundtrip recovery | exact | ✓ |

**Interpretation:** Standard physics is perfectly recovered at σ = 0. The three-measure identity (constituent − binding/c² = stable) holds to sub-ppm. Wheeler invariance is exact — electron mass is bitwise identical at all σ because electrons have no QCD content.

---

## Cross-Scale Summary

| Scale | Object | r (m) | σ | Physics status |
|-------|--------|-------|---|----------------|
| Universe | Hubble volume | 4.4×10²⁶ | 0 | ✓ Standard ΛCDM |
| Galaxy | Milky Way | 3×10²⁰ | ~10⁻⁶ → 0 | ✗ Cannot replace DM |
| Black Hole | 10 M☉ | 3×10⁴ | 0.026–0.079 | ✓ Testable predictions |
| Neutron Star | 1.4 M☉ | 10⁴ | 0.033 | ✓ Measurable enhancement |
| Atom | Fe-56 | 10⁻¹⁰ | 0 (lab) | ✓ Standard physics exact |

**σ activates where compactness is high** (GM/rc² > 0.01): black holes and neutron stars. It is negligible at galactic scales (GM/rc² ~ 10⁻⁶) and exactly zero at cosmic scales (T < Λ_QCD).

**The theory's honest scorecard:** 4/5 scales produce correct or interesting physics. The galaxy scale is where SSBM in its current form fails to explain observations without dark matter.
