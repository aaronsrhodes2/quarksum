"""
SSBM Formula Audit — Every equation traced to its origin.

□σ = −ξR is the single equation. Everything else is either:

  CORE     — Derived directly from □σ = −ξR
  MEASURED — A number from experiment (PDG, Planck, CODATA, etc.)
  FIRST_PRINCIPLES — From established physics (Coulomb's law, GR, etc.)
  EXTERNAL — Borrowed from a model outside SSBM (marked for ejection)
  TAUTOLOGICAL — True by construction (useful but not predictive)

This module makes the provenance of every formula VISIBLE.
No hidden assumptions.
"""

import time


# ═══════════════════════════════════════════════════════════════════════
#  FORMULA REGISTRY
# ═══════════════════════════════════════════════════════════════════════

# Origin categories
CORE = 'CORE'                       # from □σ = −ξR
MEASURED = 'MEASURED'               # experimental input
FIRST_PRINCIPLES = 'FIRST_PRINCIPLES'  # established physics, no SSBM needed
EXTERNAL = 'EXTERNAL'               # borrowed — mark for review/ejection
TAUTOLOGICAL = 'TAUTOLOGICAL'       # true by construction
DERIVED = 'DERIVED'                 # follows from CORE + MEASURED

ORIGIN_SYMBOLS = {
    CORE: '■',
    MEASURED: '◆',
    FIRST_PRINCIPLES: '○',
    EXTERNAL: '△',
    TAUTOLOGICAL: '◇',
    DERIVED: '□',
}


def build_audit():
    """Build the complete formula audit.

    Returns list of dicts, one per formula, with:
        module, name, equation, origin, note, eject (bool)
    """
    formulas = []

    # ── constants.py ──────────────────────────────────────────────
    formulas.append({
        'module': 'constants',
        'name': 'ξ (baryon fraction)',
        'equation': 'Ω_b / (Ω_b + Ω_c) = 0.1582',
        'origin': MEASURED,
        'note': 'Planck 2018: Ω_b h² = 0.02237, Ω_c h² = 0.1200',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'Λ_QCD',
        'equation': 'Λ_QCD = 217 MeV',
        'origin': MEASURED,
        'note': 'PDG reference value for QCD confinement scale',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'γ (spectral index)',
        'equation': 'γ = 3 − n_s = 2.035',
        'origin': MEASURED,
        'note': 'Planck 2018: n_s = 0.9649 ± 0.0042',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'σ_conv',
        'equation': 'σ_conv = −ln(ξ)',
        'origin': CORE,
        'note': 'Conversion threshold derived from □σ = −ξR at confinement limit',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'Quark masses (m_u, m_d)',
        'equation': 'm_u = 2.16 MeV, m_d = 4.67 MeV',
        'origin': MEASURED,
        'note': 'PDG 2020. Higgs-origin masses, σ-INVARIANT.',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'Nucleon mass decomposition',
        'equation': 'm_p = m_bare + m_QCD = 8.99 + 929.28 MeV',
        'origin': MEASURED,
        'note': 'BMW lattice QCD collaboration. 99.04% is QCD.',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'Coulomb coefficient a_C',
        'equation': 'a_C = (3/5) × e²/(4πε₀r₀) = 0.7111 MeV',
        'origin': FIRST_PRINCIPLES,
        'note': 'Pure electrostatics. NOT from SEMF. Inputs: e, ε₀, r₀ (all measured).',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'η (entanglement fraction)',
        'equation': 'η = 0.4153',
        'origin': DERIVED,
        'note': 'DERIVED from dark energy constraint: ρ_DE = η × ρ_QCD × (e^σ_conv − 1). Concrete value.',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'Nuclear matter constants (n₀, K, E_sat, J_sym)',
        'equation': 'n₀=0.16 fm⁻³, K=230 MeV, E_sat=−16 MeV, J_sym=32 MeV',
        'origin': MEASURED,
        'note': 'QCD observables from nuclear scattering & giant monopole resonances.',
        'eject': False,
    })
    formulas.append({
        'module': 'constants',
        'name': 'M_Hubble',
        'equation': 'M_H = c³/(2GH₀)',
        'origin': FIRST_PRINCIPLES,
        'note': 'Standard GR Hubble mass. Uses measured H₀ = 67.4 km/s/Mpc.',
        'eject': False,
    })

    # ── scale.py ──────────────────────────────────────────────────
    formulas.append({
        'module': 'scale',
        'name': 'σ(R) canonical field equation',
        'equation': 'σ(R) = −ξR (static solution of □σ = −ξR)',
        'origin': CORE,
        'note': 'Single source of truth. Everything else derives from this.',
        'eject': False,
    })
    formulas.append({
        'module': 'scale',
        'name': 'σ from potential',
        'equation': 'σ = ξ × G × M / (r × c²)',
        'origin': CORE,
        'note': 'Direct from □σ = −ξR in static spherically symmetric limit.',
        'eject': False,
    })
    formulas.append({
        'module': 'scale',
        'name': 'Λ_eff(σ)',
        'equation': 'Λ_eff = Λ_QCD × e^σ',
        'origin': CORE,
        'note': 'Core SSBM: QCD scale shifts with gravitational potential.',
        'eject': False,
    })
    formulas.append({
        'module': 'scale',
        'name': 'σ at event horizon',
        'equation': 'σ_horizon = ξ/2 (always)',
        'origin': CORE,
        'note': 'Evaluated at r = r_s = 2GM/c². σ = ξGM/(rc²) = ξ/2.',
        'eject': False,
    })

    # ── nucleon.py ────────────────────────────────────────────────
    formulas.append({
        'module': 'nucleon',
        'name': 'Proton mass at σ',
        'equation': 'm_p(σ) = m_bare + m_QCD × e^σ',
        'origin': CORE,
        'note': 'Higgs part invariant, QCD part scales with Λ_eff. Central prediction.',
        'eject': False,
    })

    # ── binding.py ────────────────────────────────────────────────
    formulas.append({
        'module': 'binding',
        'name': 'Coulomb energy',
        'equation': 'E_C = a_C × Z(Z−1) / A^(1/3)',
        'origin': FIRST_PRINCIPLES,
        'note': 'Coulomb self-energy of uniform charge sphere. σ-INVARIANT.',
        'eject': False,
    })
    formulas.append({
        'module': 'binding',
        'name': 'Binding energy at σ',
        'equation': 'BE(σ) = BE_strong × e^σ − BE_Coulomb',
        'origin': CORE,
        'note': 'Strong scales, EM invariant. Directly from Λ_eff(σ).',
        'eject': False,
    })

    # ── nesting.py ────────────────────────────────────────────────
    formulas.append({
        'module': 'nesting',
        'name': 'Level mass',
        'equation': 'M_N = M_Hubble × ξ^N',
        'origin': CORE,
        'note': 'Each level inherits fraction ξ. Follows from □σ = −ξR at horizons.',
        'eject': False,
    })
    formulas.append({
        'module': 'nesting',
        'name': 'Level count',
        'equation': 'N_max = log(M_Planck/M_Hubble) / log(ξ) = 76',
        'origin': DERIVED,
        'note': 'Derived from CORE + MEASURED (M_Planck, M_Hubble, ξ).',
        'eject': False,
    })
    formulas.append({
        'module': 'nesting',
        'name': 'F_BH (BH mass fraction)',
        'equation': 'F_BH ≈ 0.01',
        'origin': MEASURED,
        'note': ('Magorrian/M-σ relation: M_BH/M_bulge ≈ 0.002-0.013 (Kormendy & Ho 2013). '
                 'Observational data, like n₀ or Λ_QCD.'),
        'eject': False,
    })
    formulas.append({
        'module': 'nesting',
        'name': 'Funnel sum S',
        'equation': 'S = 1 / (1 − F_BH × ξ)',
        'origin': DERIVED,
        'note': 'Geometric series from CORE + MEASURED inputs.',
        'eject': False,
    })
    formulas.append({
        'module': 'nesting',
        'name': 'Bekenstein-Hawking entropy',
        'equation': 'S_BH = 4πGM²/(ℏc)',
        'origin': FIRST_PRINCIPLES,
        'note': 'Standard GR/QFT result (Bekenstein 1973, Hawking 1975). Not SSBM.',
        'eject': False,
    })

    # ── unsolved.py ───────────────────────────────────────────────
    formulas.append({
        'module': 'unsolved',
        'name': 'Exponential disc profile',
        'equation': 'M_enc(r) = M_total × [1 − (1+r/r_d) × e^(−r/r_d)]',
        'origin': MEASURED,
        'note': ('Observed galaxy morphology — this is what galaxies look like '
                 '(Freeman 1970). Measured input to rotation curve analysis, like n₀ for NS.'),
        'eject': False,
    })
    formulas.append({
        'module': 'unsolved',
        'name': 'Chandrasekhar Fermi gas (exact)',
        'equation': 'ε,P = Chandrasekhar integrals with m_n(σ)',
        'origin': FIRST_PRINCIPLES,
        'note': ('QM identity: exact relativistic degenerate gas integrals '
                 '(Chandrasekhar 1935). SSBM input: m_n(σ).'),
        'eject': False,
    })
    formulas.append({
        'module': 'unsolved',
        'name': 'Nuclear interaction (QCD meson exchange)',
        'equation': 'P_nuc from K_sat, E_sat with e^σ scaling',
        'origin': CORE,
        'note': ('QCD meson exchange scales with Λ_QCD × e^σ. '
                 'K_sat = 230 MeV (MEASURED). σ-dependence from □σ = −ξR.'),
        'eject': False,
    })
    formulas.append({
        'module': 'unsolved',
        'name': 'TOV integration (full)',
        'equation': 'dP/dr = −G(ε+P)(M+4πr³P/c²)/[c²r²(1−2GM/rc²)]',
        'origin': FIRST_PRINCIPLES,
        'note': ('GR hydrostatic equilibrium (Einstein + perfect fluid). '
                 'M_TOV = 2.071 M☉ from SSBM EOS. No borrowed APR/M_TOV.'),
        'eject': False,
    })
    formulas.append({
        'module': 'unsolved',
        'name': 'Nuclear saturation density',
        'equation': 'n₀ = 0.16 fm⁻³',
        'origin': MEASURED,
        'note': 'Measured nuclear physics constant. Appropriate input.',
        'eject': False,
    })

    # ── entanglement.py ───────────────────────────────────────────
    formulas.append({
        'module': 'entanglement',
        'name': 'Dark energy from η',
        'equation': 'ρ_DE = η × ρ_released = η × ρ_matter × f_QCD × (e^σ_conv − 1)',
        'origin': CORE,
        'note': 'SSBM prediction: coherent fraction of released QCD energy at σ_conv.',
        'eject': False,
    })
    formulas.append({
        'module': 'entanglement',
        'name': 'σ coherence',
        'equation': 'σ_eff = σ_local − (η/2)(σ_local − σ_mean)',
        'origin': CORE,
        'note': 'Entanglement pulls σ toward cosmic mean. New SSBM prediction.',
        'eject': False,
    })
    formulas.append({
        'module': 'entanglement',
        'name': 'Hawking temperature',
        'equation': 'T_H = ℏc³/(8πGMk_B)',
        'origin': FIRST_PRINCIPLES,
        'note': 'Hawking 1974. Standard QFT in curved spacetime. Not SSBM.',
        'eject': False,
    })
    formulas.append({
        'module': 'entanglement',
        'name': 'Stefan-Boltzmann radiation',
        'equation': 'P = σ_SB × T⁴ × A',
        'origin': FIRST_PRINCIPLES,
        'note': 'Standard thermodynamics. Used for Hawking power estimate.',
        'eject': False,
    })
    formulas.append({
        'module': 'entanglement',
        'name': 'Cosmological parameters (Ω_b, Ω_c, Ω_Λ, H₀)',
        'equation': 'Ω_b=0.049, Ω_c=0.264, Ω_Λ=0.685, H₀=67.4',
        'origin': MEASURED,
        'note': 'Planck 2018 best-fit values. Inputs to the model.',
        'eject': False,
    })

    # ── verify.py ─────────────────────────────────────────────────
    formulas.append({
        'module': 'verify',
        'name': 'Wheeler invariance',
        'equation': 'm_constituent = m_stable + BE',
        'origin': CORE,
        'note': ('Mass closure: constituent mass = stable mass + binding energy. '
                 'Verified at 48 nuclear states across σ. The CORE test.'),
        'eject': False,
    })

    # ── dark matter ratio ─────────────────────────────────────────
    formulas.append({
        'module': 'tests_breaking',
        'name': 'Dark matter ratio',
        'equation': '(1−ξ)/ξ = Ω_c/Ω_b',
        'origin': TAUTOLOGICAL,
        'note': ('By construction: ξ IS Ω_b/(Ω_b+Ω_c). The ratio follows. '
                 'The mechanism (photon confinement per nesting level) is CORE '
                 'but the ratio is TAUTOLOGICAL.'),
        'eject': False,
    })

    # ── irregular.py ──────────────────────────────────────────────
    formulas.append({
        'module': 'irregular',
        'name': 'Ellipsoidal gravitational potential',
        'equation': 'Φ = −πGρ × Σ(A_i × x_i²) with elliptic integrals',
        'origin': FIRST_PRINCIPLES,
        'note': 'Newtonian gravity for uniform-density ellipsoid. Classical mechanics.',
        'eject': False,
    })

    return formulas


def count_by_origin(formulas):
    """Count formulas by origin category."""
    counts = {}
    for f in formulas:
        o = f['origin']
        counts[o] = counts.get(o, 0) + 1
    return counts


def eject_candidates(formulas):
    """Return formulas marked for ejection."""
    return [f for f in formulas if f['eject']]


def print_audit():
    """Print the full formula audit."""
    t0 = time.perf_counter()
    formulas = build_audit()
    counts = count_by_origin(formulas)
    ejects = eject_candidates(formulas)

    print()
    print("  ╔═══════════════════════════════════════════════════════════╗")
    print("  ║          SSBM FORMULA AUDIT — PROVENANCE TRACE          ║")
    print("  ╚═══════════════════════════════════════════════════════════╝")
    print()

    # Group by module
    modules = {}
    for f in formulas:
        modules.setdefault(f['module'], []).append(f)

    for mod, flist in modules.items():
        print(f"  ── {mod}.py ──")
        for f in flist:
            sym = ORIGIN_SYMBOLS.get(f['origin'], '?')
            eject_mark = ' ⚠ EJECT' if f['eject'] else ''
            print(f"    {sym} [{f['origin']:<18s}] {f['name']}{eject_mark}")
            print(f"      {f['equation']}")
            if f['note']:
                # Wrap note at 65 chars
                note = f['note']
                while note:
                    print(f"      → {note[:65]}")
                    note = note[65:]
            print()

    # Summary
    print("  ═══════════════════════════════════════════════════════════")
    print("  SUMMARY")
    print("  ═══════════════════════════════════════════════════════════")
    total = len(formulas)
    for origin in [CORE, DERIVED, MEASURED, FIRST_PRINCIPLES, TAUTOLOGICAL, EXTERNAL]:
        c = counts.get(origin, 0)
        sym = ORIGIN_SYMBOLS.get(origin, '?')
        pct = c / total * 100
        print(f"    {sym} {origin:<18s}  {c:2d} / {total}  ({pct:4.1f}%)")
    print()

    # Ejection candidates
    if ejects:
        print(f"  ⚠  {len(ejects)} FORMULAS MARKED FOR EJECTION:")
        for f in ejects:
            print(f"     • {f['module']}.{f['name']}")
            print(f"       {f['note'][:70]}")
        print()
        print("  These formulas are EXTERNAL — not derived from □σ = −ξR.")
        print("  They can be:")
        print("    1. Replaced with SSBM-derived versions (preferred)")
        print("    2. Quarantined in a separate 'comparison' module")
        print("    3. Kept but clearly labeled as external scaffolding")
    else:
        print("  ✓ No formulas marked for ejection.")

    elapsed = time.perf_counter() - t0
    print(f"\n  Audited {total} formulas in {elapsed*1000:.1f} ms\n")

    return formulas
