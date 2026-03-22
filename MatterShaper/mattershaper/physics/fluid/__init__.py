"""
mattershaper.physics.fluid — SPH fluid dynamics.

Status: Foundation only — kernel and EOS implemented.
        Full SPH stepper (dam-break) is the next session.

Submodules:
    kernel.py — cubic spline smoothing kernel W(r,h) and grad W
    eos.py    — equation of state P(ρ, ρ₀, K) for liquids
"""

from .kernel import W, grad_W, smoothing_length
from .eos    import pressure_tait, pressure_ideal_gas

__all__ = ['W', 'grad_W', 'smoothing_length',
           'pressure_tait', 'pressure_ideal_gas']
