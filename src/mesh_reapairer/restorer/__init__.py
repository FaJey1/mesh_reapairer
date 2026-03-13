"""
Mesh restoration package.

Responsibilities:
- orchestrate mesh restoration based on detected self-intersections;
- triangulate affected cells;
- remove inner parts of self-intersections and produce a clean mesh.
"""

from mesh_reapairer.restorer.restorer import restore_mesh

__all__ = ["restore_mesh"]
