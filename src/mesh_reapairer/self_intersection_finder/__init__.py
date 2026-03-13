"""
Self-intersection finder package.

Responsibilities:
- build and traverse a BVH over mesh primitives;
- detect potentially intersecting primitives;
- restore a consistent boundary in the intersection region;
- expose a high-level `find_self_intersections` API used by the restorer.
"""

from mesh_reapairer.self_intersection_finder.main import *

__all__ = ["find_self_intersections"]
