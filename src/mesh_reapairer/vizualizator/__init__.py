"""
Visualization utilities for mesh_reapairer.

The package exposes narrow plotting functions for different geometric
primitives (faces, segments, lines, planes, points, full meshes).
Concrete plotting backends (e.g. matplotlib) are delegated to the
infrastructure layer.
"""

from mesh_reapairer.src.mesh_reapairer.vizualizator.intersection_result_plotter import (
    plot_intersection_result,
    plot_intersection_result_multi,
)
from mesh_reapairer.src.mesh_reapairer.vizualizator.intersection_graph_plotter_v2 import (
    plot_intersection_graph_v2,
    plot_intersection_graph_before_after,
)
from mesh_reapairer.src.mesh_reapairer.vizualizator.triangulation_plotter import (
    plot_face_triangulation,
    plot_triangulated_mesh,
)

__all__ = [
    "plot_face",
    "plot_line",
    "plot_point",
    "plot_mesh",
    "plot_plane",
    "plot_segment",
    "plot_intersection_result",
    "plot_intersection_result_multi",
    "plot_intersection_graph_v2",
    "plot_intersection_graph_before_after",
    "plot_face_triangulation",
    "plot_triangulated_mesh",
]
