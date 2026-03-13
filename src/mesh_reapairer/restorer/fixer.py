from __future__ import annotations

from collections.abc import Sequence

from mesh_reapairer.msu import Mesh
from mesh_reapairer.self_intersection_finder.intersection_finder import SelfIntersection


def remove_inner_parts(mesh: Mesh, intersections: Sequence[SelfIntersection]) -> Mesh:
    """
    Remove inner parts of self-intersections from the mesh.

    Placeholder that returns the input mesh unchanged.
    """
    _ = intersections
    return mesh
