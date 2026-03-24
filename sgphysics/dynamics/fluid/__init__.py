"""
sgphysics.dynamics.fluid — SPH fluid dynamics.

  kernel.py — Cubic spline smoothing kernel W(r,h) and grad W
  eos.py    — Equation of state P(ρ,ρ₀,K) for weakly compressible fluids
"""

from .kernel import W, grad_W, smoothing_length
from .eos    import (pressure_tait, pressure_tait_full,
                     pressure_ideal_gas, speed_of_sound_liquid)

__all__ = [
    'W', 'grad_W', 'smoothing_length',
    'pressure_tait', 'pressure_tait_full',
    'pressure_ideal_gas', 'speed_of_sound_liquid',
]
