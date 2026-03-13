"""
Visualization utilities for mesh_reapairer.

The package exposes narrow plotting functions for different geometric
primitives (faces, segments, lines, planes, points, full meshes).
Concrete plotting backends (e.g. matplotlib) are delegated to the
infrastructure layer.
"""

from mesh_reapairer.vizualizator import *

__all__ = ["plot_face", "plot_line", "plot_point", "plot_mesh", "plot_plane", "plot_segment"]
