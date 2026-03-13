from __future__ import annotations

from mesh_reapairer.msu import Mesh
from mesh_reapairer.restorer import restore_mesh
from mesh_reapairer.self_intersection_finder import find_self_intersections


def repair_mesh(input_mesh: Mesh, *, enable_visualization: bool = False) -> Mesh:
    """
    High-level mesh repair use case.

    For now this pipeline:
    - runs a no-op self-intersection finder;
    - runs a no-op restorer;
    - returns the input mesh unchanged.

    This keeps the public API stable while allowing incremental
    implementation of the underlying algorithms.
    """
    intersections = find_self_intersections(mesh=input_mesh)
    repaired_mesh = restore_mesh(mesh=input_mesh, intersections=intersections)
    _ = enable_visualization
    return repaired_mesh
