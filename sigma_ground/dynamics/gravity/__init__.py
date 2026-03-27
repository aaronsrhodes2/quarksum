"""
sgphysics.dynamics.gravity — Tree-based gravitational acceleration.

  barnes_hut.py — Barnes-Hut O(N log N) gravity (theta-MAC criterion)
"""

from .barnes_hut import QuadTree

__all__ = ['QuadTree']
