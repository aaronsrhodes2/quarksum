"""
Renderer — traces rays through the scene and computes colors.

The rendering equation (physically correct):
    L(x, ω) = Le(x, ω) + ∫ f(x, ωi, ωo) Li(x, ωi) cos(θi) dωi

Simplified for our renderer:
    color = ambient + diffuse × (N·L) + specular × (R·V)^n

Where:
    N = surface normal (from geometry)
    L = light direction
    R = reflected light direction
    V = view direction
    f = BRDF (from material properties)

All lighting is electromagnetic → σ-INVARIANT.
"""

from .raytracer import render_scene, render_to_svg

__all__ = ['render_scene', 'render_to_svg']
