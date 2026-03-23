"""
Test 1: SMBH Accretion History vs. Dark Matter Halo Mass
=========================================================
Theory: Scale-Shifted Baryonic Matter & The Black Hole Nova Hypothesis
Author: Aaron Rhodes & Claude (Skippy)

PREDICTION:
    Dark matter halo mass should correlate with *cumulative gas accretion*
    through the central SMBH. Galaxies where the BH grew primarily by gas
    accretion should have higher M_halo / M_BH than merger-dominated galaxies.

    In standard cosmology: no such directional prediction exists.
    This test distinguishes the two.

HOW TO RUN:
    1. Register at https://www.tng-project.org/ (free academic access)
    2. pip install requests h5py numpy matplotlib scipy
    3. Set your API key: export TNG_API_KEY="your_key_here"
    4. python test1_tng_analysis.py

WHAT THIS PULLS FROM TNG:
    - SubhaloMass (total halo mass)
    - SubhaloBHMass (current BH mass)
    - SubhaloBHMdot (current BH accretion rate)
    - BlackholeMergers snapshots (to reconstruct merger mass)
    The ratio of (growth by accretion) vs (growth by mergers) for each BH.
"""

import os
import sys
import json
import requests
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# -----------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------
API_KEY = os.environ.get("TNG_API_KEY", "")  # set your key
BASE_URL = "https://www.tng-project.org/api"
SIM = "TNG100-1"      # 100 Mpc box, best balance of resolution & volume
SNAP = 99             # z=0 snapshot

# Mass thresholds (in TNG units: 10^10 M_sun / h where h=0.6774)
# 1 TNG mass unit = 10^10 * M_sun / 0.6774 = 1.476e40 kg
TNG_MASS_UNIT_MSUN = 1e10 / 0.6774  # solar masses per unit
MIN_BH_MASS_MSUN   = 1e7            # only look at real SMBHs
MIN_HALO_MASS_MSUN = 1e11           # only look at real halos

# -----------------------------------------------------------------------
# API HELPERS
# -----------------------------------------------------------------------
def get(path, params=None):
    """Make an authenticated GET request to the TNG API."""
    headers = {"api-key": API_KEY}
    url = f"{BASE_URL}/{path}" if not path.startswith("http") else path
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def get_subhalos(snap, limit=1000):
    """Pull subhalo catalog with BH and halo mass."""
    params = {
        "limit": limit,
        "bh_mass__gt": MIN_BH_MASS_MSUN / TNG_MASS_UNIT_MSUN,
        "mass__gt":    MIN_HALO_MASS_MSUN / TNG_MASS_UNIT_MSUN,
        "order_by":    "-bh_mass",
        "fields":      "id,mass,bh_mass,bh_mdot,pos_x,pos_y,pos_z",
    }
    return get(f"{SIM}/snapshots/{snap}/subhalos/", params)

def get_bh_mergers(snap):
    """Pull BH merger events up to snapshot snap."""
    return get(f"{SIM}/snapshots/{snap}/blackhole_mergers/",
               {"limit": 10000, "fields": "snap,id_out,mass_out,id_in,mass_in"})

# -----------------------------------------------------------------------
# ANALYSIS CORE
# -----------------------------------------------------------------------
def compute_accretion_fraction(subhalo_ids, merger_data):
    """
    For each subhalo, estimate what fraction of its BH mass came from
    mergers vs. gas accretion.

    Method:
      - BH final mass = gas_accreted + sum(merger_masses_absorbed)
      - f_accretion = gas_accreted / final_mass
      - f_merger    = sum(merger_masses) / final_mass

    This is approximate — we're reconstructing from the merger catalog.
    A cleaner version would use the BH detail particle files.
    """
    # Build merger dict: for each BH id, total mass absorbed via mergers
    merger_mass = {}
    for m in merger_data.get("results", []):
        bh_id = m["id_out"]
        # When id_out ate id_in, it gained mass_in
        merger_mass[bh_id] = merger_mass.get(bh_id, 0.0) + m["mass_in"]
    return merger_mass

def classify_growth_mode(bh_mass, merger_absorbed, threshold=0.5):
    """
    Classify growth mode.
    Returns f_accretion = fraction of BH mass from gas (not mergers).
    """
    if bh_mass <= 0:
        return None
    m_merger = min(merger_absorbed, bh_mass)  # can't exceed total mass
    f_accretion = 1.0 - (m_merger / bh_mass)
    return f_accretion

# -----------------------------------------------------------------------
# MAIN ANALYSIS
# -----------------------------------------------------------------------
def run_test():
    if not API_KEY:
        print("ERROR: Set TNG_API_KEY environment variable first.")
        print("  Register free at https://www.tng-project.org/users/register/")
        sys.exit(1)

    print(f"Pulling subhalo catalog from {SIM} snapshot {SNAP}...")
    subhalos = get_subhalos(SNAP, limit=2000)
    results = subhalos.get("results", [])
    print(f"  Got {len(results)} subhalos with M_BH > 10^7 Msun")

    print("Pulling BH merger history...")
    mergers = get_bh_mergers(SNAP)
    merger_mass = compute_accretion_fraction(
        [s["id"] for s in results], mergers
    )

    # Build arrays
    rows = []
    for s in results:
        bh_m   = s["bh_mass"] * TNG_MASS_UNIT_MSUN   # solar masses
        halo_m = s["mass"]    * TNG_MASS_UNIT_MSUN   # solar masses
        if bh_m < MIN_BH_MASS_MSUN or halo_m < MIN_HALO_MASS_MSUN:
            continue
        bh_id = s["id"]
        m_merger = merger_mass.get(bh_id, 0.0) * TNG_MASS_UNIT_MSUN
        f_acc = classify_growth_mode(bh_m, m_merger)
        if f_acc is None:
            continue
        rows.append({
            "subhalo_id":   bh_id,
            "bh_mass_msun": bh_m,
            "halo_mass_msun": halo_m,
            "ratio_log":    np.log10(halo_m / bh_m),
            "f_accretion":  f_acc,
            "f_merger":     1.0 - f_acc,
        })

    print(f"  {len(rows)} galaxies passed mass cuts")

    # Save raw data
    with open("test1_raw_data.json", "w") as f:
        json.dump(rows, f, indent=2)
    print("  Raw data saved to test1_raw_data.json")

    # Classify
    accretion_dom = [r for r in rows if r["f_accretion"] >= 0.5]
    merger_dom    = [r for r in rows if r["f_accretion"] <  0.5]
    print(f"\n  Accretion-dominated (f_acc >= 0.5): {len(accretion_dom)}")
    print(f"  Merger-dominated    (f_acc <  0.5): {len(merger_dom)}")

    # Key statistic: log10(M_halo / M_BH) in each class
    acc_ratios   = [r["ratio_log"] for r in accretion_dom]
    merge_ratios = [r["ratio_log"] for r in merger_dom]

    print("\n--- TEST 1 RESULT ---")
    print(f"  Mean log10(M_halo/M_BH) — accretion-dominated: {np.mean(acc_ratios):.3f}")
    print(f"  Mean log10(M_halo/M_BH) — merger-dominated:    {np.mean(merge_ratios):.3f}")
    delta = np.mean(acc_ratios) - np.mean(merge_ratios)
    print(f"  Difference (accretion - merger):                {delta:+.3f} dex")
    print()

    # Theory prediction: delta > 0 (accretion-dominated have more halo per BH mass)
    if delta > 0:
        print("  ✓ CONSISTENT WITH THEORY: Accretion-dominated BHs live in")
        print("    heavier halos per unit BH mass.")
    else:
        print("  ✗ INCONSISTENT WITH THEORY: Merger-dominated BHs have heavier")
        print("    halos per unit BH mass. Investigate further.")

    # t-test for statistical significance
    t, p = stats.ttest_ind(acc_ratios, merge_ratios)
    print(f"  t-statistic: {t:.3f},  p-value: {p:.4f}")
    if p < 0.05:
        print(f"  → Statistically significant (p < 0.05)")
    else:
        print(f"  → NOT statistically significant yet (p = {p:.3f})")

    # -----------------------------------------------------------------------
    # PLOT 1: M_halo/M_BH by growth mode
    # -----------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Histogram
    ax = axes[0]
    bins = np.linspace(1.5, 6.5, 30)
    ax.hist(acc_ratios,   bins=bins, alpha=0.6, label="Accretion-dominated",
            color="steelblue", density=True)
    ax.hist(merge_ratios, bins=bins, alpha=0.6, label="Merger-dominated",
            color="tomato", density=True)
    ax.axvline(np.mean(acc_ratios),   color="steelblue", ls="--", lw=2)
    ax.axvline(np.mean(merge_ratios), color="tomato",    ls="--", lw=2)
    ax.set_xlabel(r"$\log_{10}(M_\mathrm{halo} / M_\mathrm{BH})$", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.set_title("Test 1: Halo-to-BH Mass Ratio by Growth Mode\n(TNG100-1, z=0)", fontsize=11)
    ax.legend(fontsize=10)
    ax.text(0.97, 0.95, f"Δ = {delta:+.2f} dex\np = {p:.4f}",
            ha="right", va="top", transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    # Scatter: f_accretion vs ratio
    ax = axes[1]
    f_acc_arr = [r["f_accretion"] for r in rows]
    ratio_arr = [r["ratio_log"]   for r in rows]
    ax.scatter(f_acc_arr, ratio_arr, alpha=0.3, s=10, c="gray")
    # Running mean
    bins_f = np.linspace(0, 1, 20)
    bin_centers = 0.5 * (bins_f[:-1] + bins_f[1:])
    bin_means = []
    for lo, hi in zip(bins_f[:-1], bins_f[1:]):
        vals = [r["ratio_log"] for r in rows
                if lo <= r["f_accretion"] < hi]
        bin_means.append(np.mean(vals) if vals else np.nan)
    ax.plot(bin_centers, bin_means, "b-", lw=2, label="Running mean")
    ax.set_xlabel("Accretion fraction (f_acc)", fontsize=12)
    ax.set_ylabel(r"$\log_{10}(M_\mathrm{halo} / M_\mathrm{BH})$", fontsize=12)
    ax.set_title("Halo/BH Ratio vs. Growth Mode Fraction", fontsize=11)
    ax.legend()

    plt.tight_layout()
    plt.savefig("test1_result.png", dpi=150, bbox_inches="tight")
    print("\n  Plot saved to test1_result.png")

    return rows, delta, p

# -----------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------
if __name__ == "__main__":
    rows, delta, p = run_test()
    print("\nDone. Check test1_result.png for the figure.")
    print("Key question: Is delta > 0 with p < 0.05?")
    print("  If YES → supports SSBM dark matter mechanism")
    print("  If NO  → challenges the theory's accretion-halo link")
