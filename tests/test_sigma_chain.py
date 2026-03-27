"""Tests for the σ-aware mass decomposition chain.

TDD — these tests define the contract BEFORE implementation.

The sigma chain takes QuarkSum's existing mass decomposition and reweights
every QCD-dependent term at arbitrary σ, then verifies three-measure closure.

KEY PROPERTIES TESTED:
1. σ=0 EXACT RECOVERY — must reproduce standard physics exactly.
2. THREE-MEASURE IDENTITY — stable ≈ constituent − binding/c² at every σ.
3. MONOTONICITY — nucleon masses increase with σ > 0.
4. QCD/HIGGS DECOMPOSITION — correct split at any σ.
5. EXPONENTIAL SCALING — QCD part ∝ e^σ.
6. NUCLEON MASS FRACTIONS — ~99% QCD, ~1% Higgs, always.
7. CROSS-PROJECT LINK — QuarkSum σ values agree with Materia's scale_field.
"""

import math
import pytest

from sigma_ground.inventory.core.constants import CONSTANTS
from sigma_ground.inventory.core.sigma import (
    XI,
    LAMBDA_QCD_MEV,
    A_C_MEV,
    scale_ratio,
    lambda_eff_mev,
    proton_mass_kg,
    proton_mass_mev,
    neutron_mass_kg,
    neutron_mass_mev,
    nuclear_binding_mev,
    three_measures_nucleus,
    three_measures_atom,
    sigma_from_potential,
    nucleon_qcd_fraction,
)


# ── Helpers ────────────────────────────────────────────────────────────

SIGMA_RANGE = [0.0, 0.001, 0.01, 0.05, 0.0791, 0.1, 0.2, 0.5]
SIGMA_NEG = [-0.5, -0.2, -0.1, -0.05, -0.01, 0.0]


# ═══════════════════════════════════════════════════════════════════════
#  1. σ=0 EXACT RECOVERY
# ═══════════════════════════════════════════════════════════════════════

class TestZeroRecovery:
    """At σ=0, everything must return EXACTLY standard physics."""

    def test_scale_ratio_is_one(self):
        assert scale_ratio(0.0) == 1.0

    def test_lambda_eff_is_lambda_qcd(self):
        assert lambda_eff_mev(0.0) == LAMBDA_QCD_MEV

    def test_proton_mass_exact(self):
        """Proton mass at σ=0 must equal CONSTANTS.m_p to machine precision."""
        assert proton_mass_kg(0.0) == CONSTANTS.m_p

    def test_neutron_mass_exact(self):
        """Neutron mass at σ=0 must equal CONSTANTS.m_n to machine precision."""
        assert neutron_mass_kg(0.0) == CONSTANTS.m_n

    def test_proton_mass_mev_exact(self):
        """Proton mass in MeV at σ=0 is the standard value."""
        expected = CONSTANTS.m_p / (CONSTANTS.e * 1e6 / CONSTANTS.c_squared)
        assert proton_mass_mev(0.0) == pytest.approx(expected, rel=1e-12)

    def test_neutron_mass_mev_exact(self):
        """Neutron mass in MeV at σ=0 is the standard value."""
        expected = CONSTANTS.m_n / (CONSTANTS.e * 1e6 / CONSTANTS.c_squared)
        assert neutron_mass_mev(0.0) == pytest.approx(expected, rel=1e-12)

    def test_nuclear_binding_exact(self):
        """BE at σ=0 returns input exactly."""
        be = 492.2578  # Fe-56
        assert nuclear_binding_mev(be, Z=26, A=56, sigma=0.0) == be

    def test_nuclear_binding_zero_A(self):
        """A=0 returns input unchanged regardless of σ."""
        assert nuclear_binding_mev(10.0, Z=0, A=0, sigma=0.5) == 10.0

    def test_three_measures_nucleus_identity_at_zero(self):
        """Three-measure identity holds exactly at σ=0."""
        result = three_measures_nucleus(Z=26, N=30, be_mev=492.2578, sigma=0.0)
        assert result["identity_holds"] is True
        assert result["check_delta"] < 1e-14

    def test_three_measures_atom_electron_mass(self):
        """Atom measures include Z×m_e electrons at σ=0."""
        result = three_measures_atom(Z=26, N=30, be_mev=492.2578, sigma=0.0)
        assert result["electron_mass_kg"] == 26 * CONSTANTS.m_e

    def test_sigma_from_potential_zero_for_no_gravity(self):
        """σ=0 in flat spacetime (M=0 or r→∞)."""
        assert sigma_from_potential(1.0, 0.0) == 0.0
        assert sigma_from_potential(0.0, 1e30) == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  2. THREE-MEASURE IDENTITY AT ARBITRARY σ
# ═══════════════════════════════════════════════════════════════════════

class TestThreeMeasureIdentity:
    """stable = constituent − binding/c² must close at every σ."""

    @pytest.mark.parametrize("sigma", SIGMA_RANGE)
    def test_identity_positive_sigma(self, sigma):
        """Iron-56 three-measure identity at σ > 0."""
        result = three_measures_nucleus(Z=26, N=30, be_mev=492.2578, sigma=sigma)
        assert result["identity_holds"] is True, (
            f"Identity fails at σ={sigma}: delta={result['check_delta']}"
        )

    @pytest.mark.parametrize("sigma", SIGMA_NEG)
    def test_identity_negative_sigma(self, sigma):
        """Identity must also hold for σ < 0 (weaker QCD)."""
        result = three_measures_nucleus(Z=26, N=30, be_mev=492.2578, sigma=sigma)
        assert result["identity_holds"] is True

    def test_identity_hydrogen(self):
        """Hydrogen-1 (Z=1, N=0, BE=0) at various σ."""
        for sigma in SIGMA_RANGE:
            result = three_measures_nucleus(Z=1, N=0, be_mev=0.0, sigma=sigma)
            assert result["identity_holds"] is True

    def test_identity_helium4(self):
        """He-4 (Z=2, N=2, BE=28.296 MeV) at various σ."""
        for sigma in SIGMA_RANGE:
            result = three_measures_nucleus(Z=2, N=2, be_mev=28.296, sigma=sigma)
            assert result["identity_holds"] is True

    def test_identity_uranium(self):
        """U-238 (Z=92, N=146, BE=1801.7 MeV) — heavy nucleus."""
        for sigma in [0.0, 0.01, 0.05, 0.1]:
            result = three_measures_nucleus(Z=92, N=146, be_mev=1801.7, sigma=sigma)
            assert result["identity_holds"] is True

    def test_atom_identity(self):
        """Full atom: identity should hold since electrons are additive."""
        for sigma in [0.0, 0.01, 0.1]:
            nuc = three_measures_nucleus(Z=26, N=30, be_mev=492.2578, sigma=sigma)
            atm = three_measures_atom(Z=26, N=30, be_mev=492.2578, sigma=sigma)
            # Atom stable = nuc stable + e_mass
            assert atm["atom_stable_mass_kg"] == pytest.approx(
                nuc["stable_mass_kg"] + 26 * CONSTANTS.m_e, rel=1e-14
            )


# ═══════════════════════════════════════════════════════════════════════
#  3. MONOTONICITY
# ═══════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    """Physical quantities change monotonically with σ."""

    def test_proton_mass_increases(self):
        """Proton mass increases with σ (QCD strengthens)."""
        prev = proton_mass_kg(SIGMA_RANGE[0])
        for sigma in SIGMA_RANGE[1:]:
            curr = proton_mass_kg(sigma)
            assert curr >= prev, f"Proton mass decreased at σ={sigma}"
            prev = curr

    def test_neutron_mass_increases(self):
        """Neutron mass increases with σ."""
        prev = neutron_mass_kg(SIGMA_RANGE[0])
        for sigma in SIGMA_RANGE[1:]:
            curr = neutron_mass_kg(sigma)
            assert curr >= prev, f"Neutron mass decreased at σ={sigma}"
            prev = curr

    def test_binding_energy_increases_positive_sigma(self):
        """Nuclear binding energy (strong part) increases with σ > 0."""
        prev = nuclear_binding_mev(492.2578, 26, 56, SIGMA_RANGE[0])
        for sigma in SIGMA_RANGE[1:]:
            curr = nuclear_binding_mev(492.2578, 26, 56, sigma)
            assert curr >= prev, f"Binding decreased at σ={sigma}"
            prev = curr

    def test_scale_ratio_strictly_increases(self):
        """e^σ is strictly monotonic."""
        prev = scale_ratio(-1.0)
        for sigma in [-0.5, 0.0, 0.5, 1.0]:
            curr = scale_ratio(sigma)
            assert curr > prev, f"scale_ratio not strictly increasing at σ={sigma}"
            prev = curr

    def test_lambda_eff_increases(self):
        """Λ_eff increases with σ."""
        prev = lambda_eff_mev(SIGMA_RANGE[0])
        for sigma in SIGMA_RANGE[1:]:
            curr = lambda_eff_mev(sigma)
            assert curr >= prev
            prev = curr


# ═══════════════════════════════════════════════════════════════════════
#  4. QCD/HIGGS DECOMPOSITION
# ═══════════════════════════════════════════════════════════════════════

class TestQCDHiggsDecomposition:
    """The mass split into QCD and Higgs components."""

    def test_proton_qcd_fraction_at_zero(self):
        """~99% of proton mass is QCD at σ=0."""
        info = nucleon_qcd_fraction()
        assert 0.98 < info["proton"]["qcd_fraction"] < 1.0

    def test_neutron_qcd_fraction_at_zero(self):
        """~99% of neutron mass is QCD at σ=0."""
        info = nucleon_qcd_fraction()
        assert 0.98 < info["neutron"]["qcd_fraction"] < 1.0

    def test_higgs_fraction_is_complement(self):
        """Higgs + QCD = 1.0 exactly."""
        info = nucleon_qcd_fraction()
        for nucleon in ["proton", "neutron"]:
            total = info[nucleon]["qcd_fraction"] + info[nucleon]["higgs_fraction"]
            assert total == pytest.approx(1.0, rel=1e-14)

    def test_bare_quark_masses_match_constants(self):
        """Bare masses used in decomposition match CONSTANTS."""
        info = nucleon_qcd_fraction()
        expected_proton_bare = 2 * CONSTANTS.m_up_mev + CONSTANTS.m_down_mev
        expected_neutron_bare = CONSTANTS.m_up_mev + 2 * CONSTANTS.m_down_mev
        assert info["proton"]["bare_quarks_mev"] == pytest.approx(expected_proton_bare, rel=1e-12)
        assert info["neutron"]["bare_quarks_mev"] == pytest.approx(expected_neutron_bare, rel=1e-12)

    def test_qcd_fraction_increases_with_sigma(self):
        """As σ grows, QCD fraction asymptotically approaches 1.0."""
        for sigma in [0.0, 0.1, 1.0]:
            mp_total = proton_mass_mev(sigma)
            mp_bare = 2 * CONSTANTS.m_up_mev + CONSTANTS.m_down_mev  # Higgs — invariant
            qcd_frac = 1.0 - mp_bare / mp_total
            assert qcd_frac > 0.98, f"QCD fraction < 98% at σ={sigma}: {qcd_frac}"
            if sigma > 0:
                # At positive σ, QCD fraction should be even higher
                qcd_frac_zero = 1.0 - mp_bare / proton_mass_mev(0.0)
                assert qcd_frac >= qcd_frac_zero


# ═══════════════════════════════════════════════════════════════════════
#  5. EXPONENTIAL SCALING LAW
# ═══════════════════════════════════════════════════════════════════════

class TestExponentialScaling:
    """QCD-dependent quantities scale as e^σ."""

    def test_scale_ratio_is_exp(self):
        """scale_ratio(σ) == e^σ exactly."""
        for sigma in [-1.0, -0.5, 0.0, 0.5, 1.0, 2.0]:
            assert scale_ratio(sigma) == pytest.approx(math.exp(sigma), rel=1e-14)

    def test_scale_ratio_product_identity(self):
        """e^σ × e^{-σ} = 1."""
        for sigma in [0.01, 0.05, 0.1, 0.5, 1.0]:
            assert scale_ratio(sigma) * scale_ratio(-sigma) == pytest.approx(1.0, rel=1e-14)

    def test_proton_qcd_part_scales_exponentially(self):
        """The QCD part of proton mass scales as e^σ."""
        bare = 2 * CONSTANTS.m_up_mev + CONSTANTS.m_down_mev
        qcd_0 = proton_mass_mev(0.0) - bare

        for sigma in [0.01, 0.05, 0.1, 0.5]:
            qcd_sigma = proton_mass_mev(sigma) - bare
            ratio = qcd_sigma / qcd_0
            assert ratio == pytest.approx(math.exp(sigma), rel=1e-12), (
                f"QCD proton scaling wrong at σ={sigma}: ratio={ratio}, expected={math.exp(sigma)}"
            )

    def test_neutron_qcd_part_scales_exponentially(self):
        """The QCD part of neutron mass scales as e^σ."""
        bare = CONSTANTS.m_up_mev + 2 * CONSTANTS.m_down_mev
        qcd_0 = neutron_mass_mev(0.0) - bare

        for sigma in [0.01, 0.05, 0.1, 0.5]:
            qcd_sigma = neutron_mass_mev(sigma) - bare
            ratio = qcd_sigma / qcd_0
            assert ratio == pytest.approx(math.exp(sigma), rel=1e-12)

    def test_lambda_eff_scales_exponentially(self):
        """Λ_eff = Λ_QCD × e^σ."""
        for sigma in [0.01, 0.1, 0.5]:
            assert lambda_eff_mev(sigma) == pytest.approx(
                LAMBDA_QCD_MEV * math.exp(sigma), rel=1e-14
            )


# ═══════════════════════════════════════════════════════════════════════
#  6. NUCLEAR BINDING — SEMF DECOMPOSITION
# ═══════════════════════════════════════════════════════════════════════

class TestNuclearBinding:
    """Nuclear binding energy SEMF decomposition at σ."""

    def test_coulomb_invariant(self):
        """Coulomb part stays the same at any σ — it's EM."""
        Z, A = 26, 56
        coulomb = A_C_MEV * Z * (Z - 1) / (A ** (1.0 / 3.0))
        # At σ=0: BE = strong - coulomb, so strong = BE + coulomb
        be_0 = 492.2578
        strong = be_0 + coulomb

        for sigma in [0.01, 0.1, 0.5]:
            be_sigma = nuclear_binding_mev(be_0, Z, A, sigma)
            # BE(σ) = strong × e^σ - coulomb
            expected = strong * math.exp(sigma) - coulomb
            assert be_sigma == pytest.approx(expected, rel=1e-12)

    def test_strong_part_scales(self):
        """Strong part of binding scales with e^σ."""
        Z, A = 26, 56
        coulomb = A_C_MEV * Z * (Z - 1) / (A ** (1.0 / 3.0))
        be_0 = 492.2578
        strong_0 = be_0 + coulomb

        for sigma in [0.01, 0.1]:
            be_sigma = nuclear_binding_mev(be_0, Z, A, sigma)
            strong_sigma = be_sigma + coulomb
            ratio = strong_sigma / strong_0
            assert ratio == pytest.approx(math.exp(sigma), rel=1e-12)

    def test_hydrogen_no_binding(self):
        """Hydrogen has BE=0; at any σ, remains 0."""
        for sigma in SIGMA_RANGE:
            assert nuclear_binding_mev(0.0, 1, 1, sigma) == pytest.approx(0.0, abs=1e-14)


# ═══════════════════════════════════════════════════════════════════════
#  7. SIGMA FROM GRAVITATIONAL POTENTIAL
# ═══════════════════════════════════════════════════════════════════════

class TestSigmaFromPotential:
    """σ = ξ × GM/(rc²) — Newtonian potential coupling."""

    def test_earth_surface_negligible(self):
        """σ at Earth's surface is ~7e-10 — utterly negligible."""
        M_earth = 5.972e24
        R_earth = 6.371e6
        sigma = sigma_from_potential(R_earth, M_earth)
        assert sigma < 1e-8, f"Earth σ = {sigma}, expected < 1e-8"
        assert sigma > 0

    def test_sun_surface(self):
        """σ at Sun's surface — small but measurable in principle."""
        M_sun = 1.989e30
        R_sun = 6.957e8
        sigma = sigma_from_potential(R_sun, M_sun)
        assert 1e-7 < sigma < 1e-5, f"Sun surface σ = {sigma}"

    def test_neutron_star(self):
        """σ at neutron star surface — significant."""
        M_ns = 1.4 * 1.989e30
        R_ns = 10e3  # 10 km
        sigma = sigma_from_potential(R_ns, M_ns)
        assert 0.01 < sigma < 0.08, f"NS σ = {sigma}"

    def test_event_horizon_cap(self):
        """At event horizon, compactness caps at 0.5 → σ = ξ/2."""
        M_bh = 10 * 1.989e30
        G = 6.67430e-11
        r_horizon = 2 * G * M_bh / CONSTANTS.c_squared
        sigma = sigma_from_potential(r_horizon, M_bh)
        assert sigma == pytest.approx(XI / 2, rel=1e-10)

    def test_scales_linearly_with_mass(self):
        """σ ∝ M at fixed r."""
        r = 1e6  # 1000 km
        sigma_1 = sigma_from_potential(r, 1e30)
        sigma_2 = sigma_from_potential(r, 2e30)
        assert sigma_2 == pytest.approx(2 * sigma_1, rel=1e-10)

    def test_scales_inversely_with_radius(self):
        """σ ∝ 1/r at fixed M."""
        M = 1e30
        sigma_1 = sigma_from_potential(1e6, M)
        sigma_2 = sigma_from_potential(2e6, M)
        assert sigma_1 == pytest.approx(2 * sigma_2, rel=1e-10)


# ═══════════════════════════════════════════════════════════════════════
#  8. CONTINUITY — NO DISCONTINUITIES
# ═══════════════════════════════════════════════════════════════════════

class TestContinuity:
    """Functions must be continuous — no jumps between adjacent σ values."""

    def test_proton_mass_continuous(self):
        """Proton mass changes smoothly across σ."""
        sigmas = [i * 0.01 for i in range(-10, 11)]
        masses = [proton_mass_kg(s) for s in sigmas]
        for i in range(1, len(masses)):
            jump_pct = abs(masses[i] - masses[i-1]) / masses[i-1] * 100
            assert jump_pct < 2.0, f"Jump {jump_pct}% at σ={sigmas[i]}"

    def test_binding_energy_continuous(self):
        """Nuclear binding energy changes smoothly."""
        sigmas = [i * 0.01 for i in range(-10, 11)]
        bes = [nuclear_binding_mev(492.2578, 26, 56, s) for s in sigmas]
        for i in range(1, len(bes)):
            if bes[i-1] > 0:
                jump_pct = abs(bes[i] - bes[i-1]) / bes[i-1] * 100
                assert jump_pct < 5.0, f"BE jump {jump_pct}% at σ={sigmas[i]}"


# ═══════════════════════════════════════════════════════════════════════
#  9. SIGMA CHAIN — σ-AWARE CHECKSUM
# ═══════════════════════════════════════════════════════════════════════

class TestSigmaChain:
    """The σ-aware mass checksum that reweights the quark chain."""

    def test_import(self):
        """sigma_chain module exists and is importable."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_checksum_nucleus

    def test_sigma_zero_matches_standard(self):
        """At σ=0, sigma_checksum must reproduce standard mass exactly."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_checksum_nucleus

        result = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=0.0)
        # stable_mass should match standard Fe-56 nucleus mass
        expected_stable = (
            26 * CONSTANTS.m_p + 30 * CONSTANTS.m_n
            - 492.2578 * CONSTANTS.MeV_to_J / CONSTANTS.c_squared
        )
        assert result["stable_mass_kg"] == pytest.approx(expected_stable, rel=1e-10)

    def test_three_measure_closure(self):
        """Three measures close at every σ for the full checksum."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_checksum_nucleus

        for sigma in SIGMA_RANGE:
            result = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=sigma)
            assert result["identity_holds"] is True, (
                f"Checksum identity fails at σ={sigma}"
            )

    def test_qcd_mass_fraction(self):
        """QCD mass fraction is tracked in the checksum."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_checksum_nucleus

        result = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=0.0)
        assert "qcd_mass_fraction" in result
        assert 0.98 < result["qcd_mass_fraction"] < 1.0

    def test_higgs_mass_invariant(self):
        """Higgs contribution does not change with σ."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_checksum_nucleus

        r0 = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=0.0)
        r1 = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=0.1)
        r2 = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=0.5)

        assert r0["higgs_mass_kg"] == pytest.approx(r1["higgs_mass_kg"], rel=1e-14)
        assert r0["higgs_mass_kg"] == pytest.approx(r2["higgs_mass_kg"], rel=1e-14)

    def test_qcd_mass_scales_exponentially(self):
        """QCD contribution scales as e^σ."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_checksum_nucleus

        r0 = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=0.0)

        for sigma in [0.01, 0.1, 0.5]:
            r_s = sigma_checksum_nucleus(Z=26, N=30, be_mev=492.2578, sigma=sigma)
            ratio = r_s["qcd_mass_kg"] / r0["qcd_mass_kg"]
            assert ratio == pytest.approx(math.exp(sigma), rel=1e-10)

    def test_electron_mass_invariant(self):
        """Electrons don't scale with σ (they're Higgs/EM)."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_checksum_atom

        r0 = sigma_checksum_atom(Z=26, N=30, be_mev=492.2578, sigma=0.0)
        r1 = sigma_checksum_atom(Z=26, N=30, be_mev=492.2578, sigma=0.5)

        assert r0["electron_mass_kg"] == r1["electron_mass_kg"]

    def test_sigma_sweep_fe56(self):
        """Full σ-sweep for Fe-56: all three measures at each point."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_sweep

        results = sigma_sweep(Z=26, N=30, be_mev=492.2578,
                              sigma_values=SIGMA_RANGE)
        assert len(results) == len(SIGMA_RANGE)
        for r in results:
            assert r["identity_holds"] is True

    def test_sigma_sweep_returns_sigma_values(self):
        """Each result in the sweep carries its σ value."""
        from sigma_ground.inventory.checksum.sigma_chain import sigma_sweep

        results = sigma_sweep(Z=26, N=30, be_mev=492.2578,
                              sigma_values=[0.0, 0.1])
        assert results[0]["sigma"] == 0.0
        assert results[1]["sigma"] == 0.1
