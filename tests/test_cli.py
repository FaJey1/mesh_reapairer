from __future__ import annotations

from pathlib import Path

from mesh_reapairer.cli.main import main
from mesh_reapairer.infrastructure.io import load_mesh, save_mesh
from mesh_reapairer.msu import Mesh


def test_cli_main_writes_output(tmp_path: Path) -> None:
    input_mesh = Mesh(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    input_path = tmp_path / "in.json"
    output_path = tmp_path / "out.json"
    save_mesh(input_mesh, input_path)

    main([str(input_path), str(output_path)])

    loaded = load_mesh(output_path)
    assert list(loaded.vertices) == list(input_mesh.vertices)
    assert list(loaded.faces) == list(input_mesh.faces)
