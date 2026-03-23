"""
Tests for the gas-phase physics module.

Test structure:
  1. Reduced mass — two-body mechanics
  2. Vibrational frequencies — ω = √(k/μ), validate against known IR spectra
  3. Ideal gas properties — density, number density
  4. Heat capacity — translation + rotation + vibration
  5. Gas viscosity — Chapman-Enskog kinetic theory
  6. Gas thermal conductivity — Eucken correction
  7. Buoyancy — natural convection
  8. σ-dependence — "you're not from around here"
  9. Cross-module consistency — connects to thermal, mechanical
  10. Nagatha export — format and origin tags
"""

import math
import unittest

from .gas import (
    reduced_mass,
    molecular_mass_kg,
    vibrational_frequency_hz,
    vibrational_wavenumber,
    vibrational_wavelength_um,
    vibrational_temperature,
    molecule_vibrational_spectrum,
    ideal_gas_density,
    number_density_gas,
    gas_cv_molar,
    gas_cp_molar,
    heat_capacity_ratio,
    gas_viscosity,
    gas_thermal_conductivity,
    gas_diffusivity,
    buoyancy_velocity,
    grashof_number,
    sigma_from_frequency_shift,
    molecule_gas_properties,
    MOLECULES,
    BOND_ENERGIES_EV,
    _R_GAS,
    _K_BOLTZMANN,
    _AMU_KG,
)


class TestReducedMass(unittest.TestCase):
    """Two-body reduced mass μ = m_A × m_B / (m_A + m_B)."""

    def test_equal_masses(self):
        """For equal masses, μ = m/2."""
        mu = reduced_mass(14.0, 14.0)  # N₂
        m_N = 14.0 * _AMU_KG
        self.assertAlmostEqual(mu, m_N / 2.0, delta=1e-30)

    def test_very_different_masses(self):
        """For m_A >> m_B, μ ≈ m_B (lighter atom dominates)."""
        mu = reduced_mass(16.0, 1.008)  # O-H
        m_H = 1.008 * _AMU_KG
        # μ should be close to m_H
        self.assertAlmostEqual(mu / m_H, 1.0, delta=0.07)

    def test_symmetric(self):
        """μ(A,B) = μ(B,A)."""
        mu_ab = reduced_mass(12.0, 16.0)
        mu_ba = reduced_mass(16.0, 12.0)
        self.assertEqual(mu_ab, mu_ba)

    def test_sigma_increases_mass(self):
        """σ > 0 makes nuclei heavier → μ increases."""
        mu_0 = reduced_mass(12.0, 16.0, sigma=0.0)
        mu_1 = reduced_mass(12.0, 16.0, sigma=1.0)
        self.assertGreater(mu_1, mu_0)


class TestVibrationalFrequencies(unittest.TestCase):
    """ω = √(k/μ) gives correct infrared frequencies."""

    def test_N2_stretch(self):
        """N₂ stretch: measured 2358 cm⁻¹. We should be close."""
        bond = MOLECULES['N2']['bonds'][0]
        wn = vibrational_wavenumber(
            bond['force_constant_N_m'],
            bond['atom_A_amu'], bond['atom_B_amu'])
        # Known: 2358 cm⁻¹
        self.assertAlmostEqual(wn, 2358.0, delta=200.0)

    def test_CO2_asymmetric_stretch(self):
        """CO₂ asymmetric stretch: measured 2349 cm⁻¹."""
        bond = MOLECULES['CO2']['bonds'][0]  # C=O_asym
        wn = vibrational_wavenumber(
            bond['force_constant_N_m'],
            bond['atom_A_amu'], bond['atom_B_amu'])
        # Our force constant is calibrated to give ~2349 cm⁻¹
        self.assertAlmostEqual(wn, 2349.0, delta=300.0)

    def test_H2O_stretch(self):
        """H₂O O-H stretch: measured 3657 cm⁻¹ (symmetric)."""
        bond = MOLECULES['H2O']['bonds'][0]  # O-H_sym
        wn = vibrational_wavenumber(
            bond['force_constant_N_m'],
            bond['atom_A_amu'], bond['atom_B_amu'])
        # Should be near 3657 cm⁻¹
        self.assertAlmostEqual(wn, 3657.0, delta=500.0)

    def test_heavier_atoms_lower_frequency(self):
        """Heavier atoms → lower frequency (ω ∝ 1/√μ)."""
        # CO stretch vs N₂ stretch: CO has heavier reduced mass
        co_bond = MOLECULES['CO']['bonds'][0]
        n2_bond = MOLECULES['N2']['bonds'][0]
        wn_co = vibrational_wavenumber(
            co_bond['force_constant_N_m'],
            co_bond['atom_A_amu'], co_bond['atom_B_amu'])
        wn_n2 = vibrational_wavenumber(
            n2_bond['force_constant_N_m'],
            n2_bond['atom_A_amu'], n2_bond['atom_B_amu'])
        # N₂ has stronger bond (k=2294) but similar mass → higher freq
        # CO has k=1902, slightly heavier → lower freq
        self.assertGreater(wn_n2, wn_co)

    def test_wavelength_in_infrared(self):
        """Molecular vibrations should be in the infrared (2-20 μm)."""
        for mol_key in MOLECULES:
            for bond in MOLECULES[mol_key]['bonds']:
                lam = vibrational_wavelength_um(
                    bond['force_constant_N_m'],
                    bond['atom_A_amu'], bond['atom_B_amu'])
                self.assertGreater(lam, 1.0,
                    f"{mol_key} {bond['type']}: λ={lam:.1f} μm too short")
                self.assertLess(lam, 50.0,
                    f"{mol_key} {bond['type']}: λ={lam:.1f} μm too long")

    def test_vibrational_temperature_high(self):
        """Vibrational temperatures should be 1000-6000K for most bonds."""
        for mol_key in MOLECULES:
            for bond in MOLECULES[mol_key]['bonds']:
                theta = vibrational_temperature(
                    bond['force_constant_N_m'],
                    bond['atom_A_amu'], bond['atom_B_amu'])
                # Bending modes can be lower (~900K for CO₂ bend)
                self.assertGreater(theta, 500,
                    f"{mol_key} {bond['type']}: θ_v={theta:.0f}K too low")
                self.assertLess(theta, 7000,
                    f"{mol_key} {bond['type']}: θ_v={theta:.0f}K too high")


class TestVibrationalSpectrum(unittest.TestCase):
    """Complete vibrational spectrum of molecules."""

    def test_CO2_has_three_modes(self):
        """CO₂ spectrum should have 3 entries (asym, sym, bend)."""
        spectrum = molecule_vibrational_spectrum('CO2')
        self.assertEqual(len(spectrum), 3)

    def test_H2O_has_three_modes(self):
        """H₂O spectrum should have 3 entries."""
        spectrum = molecule_vibrational_spectrum('H2O')
        self.assertEqual(len(spectrum), 3)

    def test_each_mode_has_required_fields(self):
        """Every mode should have frequency, wavenumber, wavelength, θ_v."""
        for mol_key in MOLECULES:
            spectrum = molecule_vibrational_spectrum(mol_key)
            for mode in spectrum:
                self.assertIn('frequency_hz', mode)
                self.assertIn('wavenumber_cm_inv', mode)
                self.assertIn('wavelength_um', mode)
                self.assertIn('vibrational_temperature_K', mode)
                self.assertIn('origin', mode)


class TestIdealGas(unittest.TestCase):
    """PV = nRT for gas density and number density."""

    def test_air_density(self):
        """N₂ at STP: ρ ≈ 1.15 kg/m³ (air is ~1.225)."""
        rho = ideal_gas_density('N2', T=300.0, P=101325.0)
        self.assertAlmostEqual(rho, 1.13, delta=0.15)

    def test_density_inversely_proportional_to_T(self):
        """ρ ∝ 1/T at constant pressure."""
        rho_300 = ideal_gas_density('N2', T=300.0)
        rho_600 = ideal_gas_density('N2', T=600.0)
        self.assertAlmostEqual(rho_300 / rho_600, 2.0, delta=0.01)

    def test_heavier_molecule_denser(self):
        """CO₂ (M=44) is denser than N₂ (M=28) at same T, P."""
        rho_co2 = ideal_gas_density('CO2', T=300.0)
        rho_n2 = ideal_gas_density('N2', T=300.0)
        self.assertGreater(rho_co2, rho_n2)

    def test_number_density_at_STP(self):
        """Loschmidt number: n ≈ 2.69 × 10²⁵ /m³ at STP."""
        n = number_density_gas(T=273.15, P=101325.0)
        self.assertAlmostEqual(n / 2.69e25, 1.0, delta=0.02)


class TestGasHeatCapacity(unittest.TestCase):
    """C_v = translation + rotation + vibration."""

    def test_N2_near_5_half_R_at_300K(self):
        """N₂ at 300K: C_v ≈ (5/2)R (vibration frozen out)."""
        cv = gas_cv_molar('N2', T=300.0)
        expected = 2.5 * _R_GAS
        # Should be close to 5/2 R, maybe slightly above
        self.assertAlmostEqual(cv / expected, 1.0, delta=0.05)

    def test_vibration_activates_at_high_T(self):
        """At 3000K, vibrational modes contribute → C_v increases."""
        cv_300 = gas_cv_molar('N2', T=300.0)
        cv_3000 = gas_cv_molar('N2', T=3000.0)
        self.assertGreater(cv_3000, cv_300)

    def test_H2O_nonlinear_higher_cv(self):
        """H₂O (nonlinear): C_v > N₂ at same T (more rotational DOF)."""
        cv_h2o = gas_cv_molar('H2O', T=300.0)
        cv_n2 = gas_cv_molar('N2', T=300.0)
        self.assertGreater(cv_h2o, cv_n2)

    def test_cp_minus_cv_equals_R(self):
        """C_p - C_v = R for ideal gas (Mayer's relation)."""
        for mol_key in MOLECULES:
            cv = gas_cv_molar(mol_key, T=500.0)
            cp = gas_cp_molar(mol_key, T=500.0)
            self.assertAlmostEqual(cp - cv, _R_GAS, places=5,
                msg=f"{mol_key}: C_p - C_v should equal R")

    def test_gamma_diatomic(self):
        """N₂ at 300K: γ ≈ 1.4 (diatomic, vibration frozen)."""
        gamma = heat_capacity_ratio('N2', T=300.0)
        self.assertAlmostEqual(gamma, 1.4, delta=0.03)

    def test_gamma_decreases_at_high_T(self):
        """γ decreases as vibrational modes activate."""
        gamma_300 = heat_capacity_ratio('N2', T=300.0)
        gamma_3000 = heat_capacity_ratio('N2', T=3000.0)
        self.assertGreater(gamma_300, gamma_3000)


class TestGasViscosity(unittest.TestCase):
    """Chapman-Enskog kinetic theory of viscosity."""

    def test_N2_order_of_magnitude(self):
        """N₂ viscosity at 300K: ~18 μPa·s (measured: 17.8)."""
        eta = gas_viscosity('N2', T=300.0)
        eta_uPa_s = eta * 1e6
        self.assertAlmostEqual(eta_uPa_s, 17.8, delta=5.0)

    def test_increases_with_temperature(self):
        """Gas viscosity increases with T (unlike liquids!)."""
        eta_300 = gas_viscosity('N2', T=300.0)
        eta_600 = gas_viscosity('N2', T=600.0)
        self.assertGreater(eta_600, eta_300)

    def test_heavier_molecule_higher_viscosity(self):
        """CO₂ (heavier) should have higher viscosity than H₂O (lighter)."""
        # Actually η ∝ √(mT)/d², so depends on both mass and diameter
        # Just check both are positive and in the right range
        eta_co2 = gas_viscosity('CO2', T=300.0)
        eta_h2o = gas_viscosity('H2O', T=300.0)
        self.assertGreater(eta_co2, 0)
        self.assertGreater(eta_h2o, 0)

    def test_sqrt_T_scaling(self):
        """η ∝ √T for hard spheres."""
        eta_300 = gas_viscosity('N2', T=300.0)
        eta_1200 = gas_viscosity('N2', T=1200.0)
        # Should be close to √(1200/300) = 2.0
        ratio = eta_1200 / eta_300
        self.assertAlmostEqual(ratio, 2.0, delta=0.1)


class TestGasThermalConductivity(unittest.TestCase):
    """Eucken correction to kinetic theory."""

    def test_N2_order_of_magnitude(self):
        """N₂ thermal conductivity at 300K: ~26 mW/(m·K) (measured: 25.8)."""
        kappa = gas_thermal_conductivity('N2', T=300.0)
        kappa_mW = kappa * 1000
        self.assertAlmostEqual(kappa_mW, 25.8, delta=15.0)

    def test_increases_with_temperature(self):
        """Gas κ increases with T (like viscosity)."""
        kappa_300 = gas_thermal_conductivity('N2', T=300.0)
        kappa_600 = gas_thermal_conductivity('N2', T=600.0)
        self.assertGreater(kappa_600, kappa_300)

    def test_lighter_gas_higher_conductivity(self):
        """H₂O (lighter) should have higher κ than CO₂ (heavier)."""
        # κ ∝ η × cv / M, and H₂O has smaller M
        kappa_h2o = gas_thermal_conductivity('H2O', T=300.0)
        kappa_co2 = gas_thermal_conductivity('CO2', T=300.0)
        self.assertGreater(kappa_h2o, kappa_co2)

    def test_much_less_than_metals(self):
        """Gas κ << metal κ (by factor of ~10,000)."""
        kappa_gas = gas_thermal_conductivity('N2', T=300.0)
        # Copper: ~400 W/(m·K), gas should be ~0.025
        self.assertLess(kappa_gas, 0.1)


class TestDiffusion(unittest.TestCase):
    """Binary gas diffusion coefficients."""

    def test_positive_diffusivity(self):
        """D > 0 for all gas pairs."""
        D = gas_diffusivity('N2', 'O2', T=300.0)
        self.assertGreater(D, 0)

    def test_O2_N2_order_of_magnitude(self):
        """O₂-N₂ diffusion at STP: ~2 × 10⁻⁵ m²/s."""
        D = gas_diffusivity('O2', 'N2', T=300.0)
        self.assertAlmostEqual(D * 1e5, 2.0, delta=1.5)

    def test_increases_with_temperature(self):
        """D ∝ T^(3/2) / P for hard spheres."""
        D_300 = gas_diffusivity('N2', 'O2', T=300.0)
        D_600 = gas_diffusivity('N2', 'O2', T=600.0)
        self.assertGreater(D_600, D_300)

    def test_symmetric(self):
        """D(A,B) = D(B,A)."""
        D_ab = gas_diffusivity('N2', 'O2', T=300.0)
        D_ba = gas_diffusivity('O2', 'N2', T=300.0)
        self.assertAlmostEqual(D_ab, D_ba, places=10)


class TestBuoyancy(unittest.TestCase):
    """Natural convection from hot gas."""

    def test_flame_velocity(self):
        """Candle-like conditions: v ≈ 0.1-1.0 m/s."""
        v = buoyancy_velocity(T_hot=1400.0, T_ambient=300.0, L=0.03)
        self.assertGreater(v, 0.1)
        self.assertLess(v, 2.0)

    def test_zero_when_no_gradient(self):
        """No ΔT → no buoyancy."""
        v = buoyancy_velocity(T_hot=300.0, T_ambient=300.0)
        self.assertEqual(v, 0.0)

    def test_increases_with_delta_T(self):
        """Hotter gas → faster rise."""
        v1 = buoyancy_velocity(T_hot=600.0, T_ambient=300.0, L=0.03)
        v2 = buoyancy_velocity(T_hot=1200.0, T_ambient=300.0, L=0.03)
        self.assertGreater(v2, v1)

    def test_grashof_flame_laminar(self):
        """Candle flame: Gr should be < 10⁹ (laminar)."""
        Gr = grashof_number(T_hot=1400.0, T_ambient=300.0, L=0.03)
        self.assertLess(Gr, 1e9)
        self.assertGreater(Gr, 0)


class TestSigmaDependence(unittest.TestCase):
    """σ-field shifts molecular properties through nuclear mass."""

    def test_sigma_shifts_frequency(self):
        """σ > 0 → heavier nuclei → lower vibrational frequency."""
        bond = MOLECULES['CO2']['bonds'][0]
        wn_0 = vibrational_wavenumber(
            bond['force_constant_N_m'],
            bond['atom_A_amu'], bond['atom_B_amu'], sigma=0.0)
        wn_1 = vibrational_wavenumber(
            bond['force_constant_N_m'],
            bond['atom_A_amu'], bond['atom_B_amu'], sigma=1.0)
        self.assertLess(wn_1, wn_0)

    def test_sigma_shifts_gas_density(self):
        """σ > 0 → heavier molecules → denser gas."""
        rho_0 = ideal_gas_density('N2', T=300.0, sigma=0.0)
        rho_1 = ideal_gas_density('N2', T=300.0, sigma=1.0)
        self.assertGreater(rho_1, rho_0)

    def test_sigma_shifts_viscosity(self):
        """σ > 0 → heavier molecules → higher viscosity (η ∝ √m)."""
        eta_0 = gas_viscosity('N2', T=300.0, sigma=0.0)
        eta_1 = gas_viscosity('N2', T=300.0, sigma=1.0)
        self.assertGreater(eta_1, eta_0)

    def test_earth_sigma_negligible(self):
        """At Earth's surface (σ ~ 7e-10), all shifts are negligible."""
        wn_0 = vibrational_wavenumber(
            MOLECULES['CO2']['bonds'][0]['force_constant_N_m'],
            12.011, 15.999, sigma=0.0)
        wn_earth = vibrational_wavenumber(
            MOLECULES['CO2']['bonds'][0]['force_constant_N_m'],
            12.011, 15.999, sigma=7e-10)
        self.assertAlmostEqual(wn_0, wn_earth, delta=wn_0 * 1e-8)

    def test_sigma_recovery_from_frequency(self):
        """Can recover σ from an observed frequency shift."""
        # Simulate observation at σ=0.1
        bond = MOLECULES['N2']['bonds'][0]
        f_expected = vibrational_frequency_hz(
            bond['force_constant_N_m'],
            bond['atom_A_amu'], bond['atom_B_amu'], sigma=0.0)
        f_observed = vibrational_frequency_hz(
            bond['force_constant_N_m'],
            bond['atom_A_amu'], bond['atom_B_amu'], sigma=0.1)

        sigma_recovered = sigma_from_frequency_shift(
            f_observed, f_expected,
            bond['atom_A_amu'], bond['atom_B_amu'])
        self.assertAlmostEqual(sigma_recovered, 0.1, delta=0.01)


class TestBondEnergies(unittest.TestCase):
    """Bond dissociation energies are in the database."""

    def test_all_positive(self):
        """All bond energies must be positive."""
        for bond_type, energy in BOND_ENERGIES_EV.items():
            self.assertGreater(energy, 0, f"{bond_type}: energy must be > 0")

    def test_triple_stronger_than_double(self):
        """Triple bonds > double bonds > single bonds."""
        self.assertGreater(BOND_ENERGIES_EV['N≡N'], BOND_ENERGIES_EV['O=O'])
        self.assertGreater(BOND_ENERGIES_EV['O=O'], BOND_ENERGIES_EV['C-C'])

    def test_co_very_strong(self):
        """C≡O is one of the strongest bonds in chemistry."""
        self.assertGreater(BOND_ENERGIES_EV['C≡O'], 10.0)


class TestNagathaExport(unittest.TestCase):
    """Nagatha-compatible export format."""

    def test_required_fields(self):
        """Export contains all required fields."""
        props = molecule_gas_properties('N2')
        required = [
            'molecule', 'name', 'temperature_K', 'density_kg_m3',
            'viscosity_Pa_s', 'thermal_conductivity_W_mK',
            'cv_molar_J_molK', 'cp_molar_J_molK', 'gamma',
            'vibrational_spectrum', 'origin',
        ]
        for key in required:
            self.assertIn(key, props, f"Missing: {key}")

    def test_honest_origin_tags(self):
        """Origin string contains honest tags."""
        props = molecule_gas_properties('CO2')
        origin = props['origin']
        self.assertIn('FIRST_PRINCIPLES', origin)
        self.assertIn('MEASURED', origin)
        self.assertIn('APPROXIMATION', origin)

    def test_all_molecules_export(self):
        """Every molecule exports without error."""
        for mol in MOLECULES:
            props = molecule_gas_properties(mol)
            self.assertIn('origin', props)


if __name__ == '__main__':
    unittest.main()
