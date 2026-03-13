from __future__ import annotations

from collections.abc import Sequence

from mesh_reapairer.msu import Mesh
from mesh_reapairer.restorer.fixer import remove_inner_parts
from mesh_reapairer.restorer.triangulator import triangulate_cells
from mesh_reapairer.self_intersection_finder.intersection_finder import SelfIntersection


def restore_mesh(mesh: Mesh, intersections: Sequence[SelfIntersection]) -> Mesh:
    """
    High-level mesh restoration pipeline.

    Placeholder implementation that wires the stages together and returns the mesh unchanged.
    """
    triangulated = triangulate_cells(mesh=mesh)
    restored = remove_inner_parts(mesh=triangulated, intersections=intersections)
    return restored
