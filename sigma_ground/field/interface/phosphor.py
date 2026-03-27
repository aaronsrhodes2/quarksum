"""
Phosphorescent screen model for particle-impact simulations.

No hardcoded material constants. τ (decay lifetime) and λ_emission
are caller-supplied parameters — this module owns only the physics
of what happens to a screen once those properties are chosen.

──────────────────────────────────────────────────────────────────────────────
PHYSICS
──────────────────────────────────────────────────────────────────────────────

Phosphorescence is a spin-forbidden radiative transition (T₁ → S₀).
The excited state decays exponentially:

    I(t) = I₀ × exp(−t / τ)         [FIRST_PRINCIPLES: dN/dt = −N/τ]

τ is the caller's responsibility. It is a measured property of the
specific material chosen for the screen. This module makes no assumption
about what that material is.

σ-INVARIANCE: The decay rate 1/τ is set by EM (spin-orbit coupling,
electronic transition energies). It does not depend on QCD or σ.
Confirmed: nuclear charge Z is invariant; nuclear MASS doesn't enter
atomic electron structure.

──────────────────────────────────────────────────────────────────────────────
SCREEN MODEL
──────────────────────────────────────────────────────────────────────────────

The screen is a 1-D grid of pixels (y-axis).
Each pixel accumulates hits. Each hit deposits brightness 1.0 at
time t_hit. At any later time t, that hit contributes:

    brightness = exp(−(t − t_hit) / τ)

Total pixel brightness = sum over all hits of their decayed contributions.

For N >> 1 particles, the hit distribution approaches |ψ(y)|²,
and the brightness profile reveals the interference pattern.

──────────────────────────────────────────────────────────────────────────────
"""

import math


class PhosphorScreen:
    """A 1-D phosphorescent screen that accumulates particle hits.

    Each pixel tracks the times of all hits it has received.
    Brightness at any moment is the sum of decayed contributions.

    Args:
        y_min:   left edge of screen (meters)
        y_max:   right edge of screen (meters)
        n_pixels: number of pixels
        tau:     phosphorescence decay time constant (seconds) — caller supplied
    """

    def __init__(self, y_min, y_max, n_pixels, tau):
        if n_pixels < 2:
            raise ValueError("n_pixels must be at least 2")
        if tau <= 0.0:
            raise ValueError("tau must be positive")
        if y_max <= y_min:
            raise ValueError("y_max must be greater than y_min")

        self.y_min    = y_min
        self.y_max    = y_max
        self.n_pixels = n_pixels
        self.tau      = tau

        self._dy      = (y_max - y_min) / n_pixels

        # Each pixel holds a list of hit times (seconds)
        self._hits    = [[] for _ in range(n_pixels)]

        # Running hit count per pixel (for pattern analysis, unaffected by decay)
        self.hit_counts = [0] * n_pixels

        # Total hits recorded
        self.total_hits = 0

    # ── Geometry ──────────────────────────────────────────────────────────────

    def y_to_pixel(self, y):
        """Convert y position (meters) to pixel index. Returns None if off screen."""
        if y < self.y_min or y >= self.y_max:
            return None
        return int((y - self.y_min) / self._dy)

    def pixel_center(self, i):
        """Y position (meters) at center of pixel i."""
        return self.y_min + (i + 0.5) * self._dy

    def y_array(self):
        """List of pixel center y-positions (meters)."""
        return [self.pixel_center(i) for i in range(self.n_pixels)]

    # ── Recording hits ────────────────────────────────────────────────────────

    def record_hit(self, y, t):
        """Record a particle impact at position y (meters) at time t (seconds).

        Args:
            y: impact position in meters
            t: time of impact in seconds

        Returns:
            pixel index that was hit, or None if off screen
        """
        idx = self.y_to_pixel(y)
        if idx is None:
            return None
        self._hits[idx].append(t)
        self.hit_counts[idx] += 1
        self.total_hits += 1
        return idx

    # ── Brightness ────────────────────────────────────────────────────────────

    def pixel_brightness(self, i, t_now):
        """Brightness of pixel i at time t_now.

        B(t) = Σ_k exp(−(t_now − t_k) / τ)   for all hits t_k ≤ t_now

        FIRST_PRINCIPLES: each hit is an independent excited state;
        total brightness is superposition of decaying contributions.

        Args:
            i:     pixel index
            t_now: current time (seconds)

        Returns:
            brightness (dimensionless, ≥ 0)
        """
        total = 0.0
        inv_tau = 1.0 / self.tau
        for t_hit in self._hits[i]:
            dt = t_now - t_hit
            if dt >= 0.0:
                total += math.exp(-dt * inv_tau)
        return total

    def brightness_profile(self, t_now):
        """Brightness at every pixel at time t_now.

        Returns:
            list of brightness values, length n_pixels
        """
        return [self.pixel_brightness(i, t_now) for i in range(self.n_pixels)]

    def hit_profile(self):
        """Raw hit counts per pixel (unweighted by decay).

        This is the ground truth of the interference pattern —
        independent of τ, t_now, or any display choices.

        Returns:
            list of int, length n_pixels
        """
        return list(self.hit_counts)

    # ── Pattern analysis ──────────────────────────────────────────────────────

    def peak_pixel(self):
        """Pixel index with the most hits."""
        return max(range(self.n_pixels), key=lambda i: self.hit_counts[i])

    def fringe_visibility_measured(self):
        """Measure fringe visibility from the accumulated hit profile.

        V = (I_max - I_min) / (I_max + I_min)

        Uses the raw hit counts (not decayed brightness) so the result
        is independent of when you look at the screen.

        Returns:
            measured visibility V in [0, 1], or None if no hits recorded
        """
        if self.total_hits == 0:
            return None
        I_max = max(self.hit_counts)
        I_min = min(self.hit_counts)
        denom = I_max + I_min
        if denom == 0:
            return 0.0
        return (I_max - I_min) / denom

    def half_width_half_max(self):
        """HWHM of central peak in meters, from hit profile.

        Finds the peak, then walks outward until the count drops to half.
        Returns None if fewer than 3 pixels have hits.

        Returns:
            HWHM in meters, or None
        """
        counts = self.hit_counts
        peak_i = self.peak_pixel()
        half = counts[peak_i] / 2.0

        # Walk right
        right_i = peak_i
        for i in range(peak_i, self.n_pixels):
            if counts[i] < half:
                right_i = i
                break

        # Walk left
        left_i = peak_i
        for i in range(peak_i, -1, -1):
            if counts[i] < half:
                left_i = i
                break

        half_width_pixels = (right_i - left_i) / 2.0
        return half_width_pixels * self._dy

    def summarise(self):
        """Print a compact summary of the screen state."""
        print(f"PhosphorScreen: {self.n_pixels} pixels, "
              f"y=[{self.y_min*1e3:.1f}, {self.y_max*1e3:.1f}] mm, "
              f"τ={self.tau*1e3:.1f} ms")
        print(f"  Total hits: {self.total_hits}")
        peak_i = self.peak_pixel() if self.total_hits > 0 else None
        if peak_i is not None:
            print(f"  Peak pixel: {peak_i} "
                  f"(y={self.pixel_center(peak_i)*1e3:.2f} mm, "
                  f"hits={self.hit_counts[peak_i]})")
        V = self.fringe_visibility_measured()
        if V is not None:
            print(f"  Measured visibility: {V:.3f}")


# ── Functional interface (stateless) ─────────────────────────────────────────

def phosphor_brightness(I0, t, tau):
    """Brightness of a single hit at time t after impact.

    I(t) = I₀ × exp(−t / τ)

    FIRST_PRINCIPLES: identical to any two-state exponential decay.
    Same mathematics as nuclear decay, radioactive series, RC discharge.

    Args:
        I0:  initial brightness at t=0 (arbitrary units)
        t:   time since impact (seconds), must be ≥ 0
        tau: decay time constant (seconds)

    Returns:
        brightness at time t
    """
    if t < 0:
        raise ValueError("t must be non-negative")
    return I0 * math.exp(-t / tau)


def build_ascii_histogram(hit_counts, width=60, symbol='█'):
    """Render hit_counts as a horizontal ASCII histogram.

    Useful for quick sanity checks in the terminal.

    Args:
        hit_counts: list of int (from PhosphorScreen.hit_profile())
        width:      character width of the longest bar
        symbol:     character to use for bars

    Returns:
        multi-line string
    """
    if not hit_counts or max(hit_counts) == 0:
        return "(no hits)"
    scale = width / max(hit_counts)
    lines = []
    for i, count in enumerate(hit_counts):
        bar = symbol * int(count * scale)
        lines.append(f"{i:4d} | {bar} {count}")
    return "\n".join(lines)
