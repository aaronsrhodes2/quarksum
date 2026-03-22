#!/usr/bin/env python3
"""Generate GW150914 waveform visualization."""

import sys
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/quarksum")
sys.path.insert(0, "/sessions/loving-pensive-euler/mnt/Materia/qamss")

from materia.models.gw_waveform import GW150914, generate_imr_waveform

# Generate waveform
params = GW150914
wf = generate_imr_waveform(params, f_low=20.0, dt=1.0/4096.0)

# Focus on the last ~0.35s (where the signal is visible)
t = wf.t
h = wf.h_plus
f = wf.f_gw

# Find where signal becomes visible (strain > 0.1 × peak)
threshold = 0.1 * wf.peak_strain
visible_mask = np.abs(h) > threshold * 0.3
if np.any(visible_mask):
    t_start = t[visible_mask][0] - 0.05
else:
    t_start = t[-1] - 0.35

# Time relative to merger (peak strain)
t_merger = t[np.argmax(np.abs(h))]
t_rel = t - t_merger

mask = t_rel > -0.30
t_plot = t_rel[mask]
h_plot = h[mask]
f_plot = f[mask]
labels = wf.phase_label[mask]

# Create figure
fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1.5, 1.5]})
fig.patch.set_facecolor('#0a0a14')

# ── Panel 1: Strain waveform ──────────────────────────────────
ax1 = axes[0]
ax1.set_facecolor('#0a0a14')

# Color by phase
insp_mask = labels == 'inspiral'
merg_mask = labels == 'merger'
ring_mask = labels == 'ringdown'

ax1.plot(t_plot[insp_mask] * 1e3, h_plot[insp_mask] * 1e21,
         color='#4488ff', linewidth=0.8, label='Inspiral (PN)')
ax1.plot(t_plot[merg_mask] * 1e3, h_plot[merg_mask] * 1e21,
         color='#ff4444', linewidth=1.2, label='Merger')
ax1.plot(t_plot[ring_mask] * 1e3, h_plot[ring_mask] * 1e21,
         color='#44ff88', linewidth=0.8, label='Ringdown (QNM)')

# Envelope
# Simple envelope via peak tracking (no scipy needed)
try:
    from numpy.fft import fft, ifft
    # Hilbert transform via FFT
    N = len(h_plot)
    H = fft(h_plot)
    H[1:N//2] *= 2
    H[N//2+1:] = 0
    analytic = ifft(H)
    envelope = np.abs(analytic)
    ax1.plot(t_plot * 1e3, envelope * 1e21, color='#ffffff', linewidth=0.4, alpha=0.4)
    ax1.plot(t_plot * 1e3, -envelope * 1e21, color='#ffffff', linewidth=0.4, alpha=0.4)
except:
    pass

ax1.axvline(0, color='#ff8844', linewidth=0.5, alpha=0.5, linestyle='--')
ax1.text(1, max(h_plot * 1e21) * 0.85, 'merger', color='#ff8844', fontsize=9, alpha=0.7)

ax1.set_ylabel('Strain h(t) × 10²¹', color='white', fontsize=11)
ax1.set_title('GW150914 — Binary Black Hole Merger\n'
              'Computed from post-Newtonian inspiral + QNM ringdown (SSBM/Materia)',
              color='white', fontsize=13, fontweight='bold', pad=12)
ax1.legend(loc='upper left', fontsize=9, facecolor='#1a1a2e', edgecolor='#333',
           labelcolor='white')
ax1.tick_params(colors='white')
ax1.spines['bottom'].set_color('#333')
ax1.spines['left'].set_color('#333')
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.grid(True, alpha=0.1, color='white')

# ── Panel 2: Frequency evolution ──────────────────────────────
ax2 = axes[1]
ax2.set_facecolor('#0a0a14')

ax2.plot(t_plot[insp_mask] * 1e3, f_plot[insp_mask], color='#4488ff', linewidth=1)
ax2.plot(t_plot[merg_mask] * 1e3, f_plot[merg_mask], color='#ff4444', linewidth=1.2)
ax2.plot(t_plot[ring_mask] * 1e3, f_plot[ring_mask], color='#44ff88', linewidth=1)

# Mark key frequencies
ax2.axhline(params.f_isco_hz, color='#ffaa44', linewidth=0.5, linestyle=':', alpha=0.6)
ax2.text(-280, params.f_isco_hz + 5, f'f_ISCO = {params.f_isco_hz:.0f} Hz',
         color='#ffaa44', fontsize=8, alpha=0.7)
ax2.axhline(params.f_qnm_hz, color='#44ff88', linewidth=0.5, linestyle=':', alpha=0.6)
ax2.text(-280, params.f_qnm_hz + 5, f'f_QNM = {params.f_qnm_hz:.0f} Hz',
         color='#44ff88', fontsize=8, alpha=0.7)

ax2.set_ylabel('GW Frequency (Hz)', color='white', fontsize=11)
ax2.tick_params(colors='white')
ax2.spines['bottom'].set_color('#333')
ax2.spines['left'].set_color('#333')
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.grid(True, alpha=0.1, color='white')
ax2.set_ylim(0, max(f_plot) * 1.15)

# ── Panel 3: SSBM interior ───────────────────────────────────
ax3 = axes[2]
ax3.set_facecolor('#0a0a14')
ax3.set_xlim(t_plot[0] * 1e3, t_plot[-1] * 1e3)
ax3.set_ylim(0, 1)

# Draw the two daughter universes merging
# Before merger: two separate circles shrinking toward each other
# After merger: one circle
merger_ms = 0  # merger at t=0

# Separation (schematic)
n_pts = 100
t_sch = np.linspace(t_plot[0] * 1e3, t_plot[-1] * 1e3, n_pts)
r_A = 0.12  # visual radius
r_B = 0.10

for i, ti in enumerate(t_sch):
    if ti < merger_ms - 50:
        # Two separate: draw outlines
        sep = 0.3 * (1.0 - ti / (merger_ms - 50)) + 0.05
        if i % 5 == 0:
            c1 = plt.Circle((ti, 0.5 + sep/2), r_A, fill=False,
                           edgecolor='#4488ff', linewidth=0.3, alpha=0.3)
            c2 = plt.Circle((ti, 0.5 - sep/2), r_B, fill=False,
                           edgecolor='#ff8844', linewidth=0.3, alpha=0.3)
            ax3.add_patch(c1)
            ax3.add_patch(c2)
    elif ti < merger_ms + 20:
        # Merging
        if i % 3 == 0:
            c = plt.Circle((ti, 0.5), r_A + r_B, fill=False,
                          edgecolor='#ff4444', linewidth=0.5, alpha=0.5)
            ax3.add_patch(c)
    else:
        # One combined
        if i % 5 == 0:
            c = plt.Circle((ti, 0.5), r_A + r_B - 0.02, fill=False,
                          edgecolor='#44ff88', linewidth=0.3, alpha=0.3)
            ax3.add_patch(c)

ax3.text(-250, 0.85, 'SSBM: Two daughter\nuniverses', color='#4488ff',
         fontsize=8, ha='center')
ax3.text(0, 0.85, 'Collision', color='#ff4444', fontsize=8, ha='center')
ax3.text(30, 0.85, 'One combined\nuniverse', color='#44ff88', fontsize=8, ha='center')

ax3.set_xlabel('Time relative to merger (ms)', color='white', fontsize=11)
ax3.set_ylabel('SSBM Interior', color='white', fontsize=11)
ax3.tick_params(colors='white')
ax3.spines['bottom'].set_color('#333')
ax3.spines['left'].set_color('#333')
ax3.spines['top'].set_visible(False)
ax3.spines['right'].set_visible(False)
ax3.set_yticks([])

# ── Info box ──────────────────────────────────────────────────
info_text = (
    f"m₁ = {params.m1_solar:.0f} M☉   m₂ = {params.m2_solar:.0f} M☉   "
    f"M_c = {params.chirp_mass_solar:.1f} M☉\n"
    f"D = {params.distance_mpc:.0f} Mpc   "
    f"M_rem = {params.remnant_mass_solar:.0f} M☉   "
    f"a* = {params.remnant_spin:.2f}\n"
    f"Peak h = {wf.peak_strain:.2e}   "
    f"f_peak = {wf.peak_frequency_hz:.0f} Hz   "
    f"ξ = {0.1582}"
)
fig.text(0.98, 0.02, info_text, color='#888', fontsize=7, ha='right',
         va='bottom', family='monospace')

plt.tight_layout()
outpath = "/sessions/loving-pensive-euler/mnt/quarksum/theory/gw150914_waveform.png"
plt.savefig(outpath, dpi=200, facecolor='#0a0a14', edgecolor='none',
            bbox_inches='tight')
print(f"Saved to: {outpath}")
plt.close()
