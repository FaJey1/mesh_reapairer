from __future__ import annotations

from mesh_reapairer.src.mesh_reapairer import repair_mesh
from mesh_reapairer.src.mesh_reapairer.msu import Mesh


def test_repair_mesh_is_callable() -> None:
    mesh = Mesh(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    repaired = repair_mesh(mesh)

    assert repaired.vertices is mesh.vertices or list(repaired.vertices) == list(mesh.vertices)
    assert repaired.faces is mesh.faces or list(repaired.faces) == list(mesh.faces)
