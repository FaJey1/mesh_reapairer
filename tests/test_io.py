from __future__ import annotations

from pathlib import Path

from mesh_reapairer.src.mesh_reapairer.infrastructure.io import load_mesh, save_mesh
from mesh_reapairer.src.mesh_reapairer.msu import Mesh


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    mesh = Mesh(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )

    out_path = tmp_path / "mesh.json"
    save_mesh(mesh, out_path)
    loaded = load_mesh(out_path)

    assert list(loaded.vertices) == list(mesh.vertices)
    assert list(loaded.faces) == list(mesh.faces)
