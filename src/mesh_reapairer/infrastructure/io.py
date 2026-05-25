from __future__ import annotations

import json
from pathlib import Path

from mesh_reapairer.src.mesh_reapairer.msu import Mesh


def load_mesh(file_path: Path | str) -> Mesh:
    """
    Загрузить сетку из файла.

    Args:
        file_path: Путь к файлу сетки (.dat, .json)

    Returns:
        Загруженная сетка

    Raises:
        FileNotFoundError: Если файл не найден
        ValueError: Если формат файла не поддерживается
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Mesh file not found: {path}")

    # Поддерживаем .dat файлы (MSU формат)
    if path.suffix == ".dat":
        return Mesh(str(path))

    # Поддерживаем .json файлы (для результатов)
    if path.suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Если это результат с сеткой внутри
        if "mesh" in data:
            # TODO: Десериализация из JSON
            raise NotImplementedError("JSON mesh loading not yet implemented")
        raise ValueError(f"Invalid JSON mesh format: {path}")

    raise ValueError(f"Unsupported mesh format: {path.suffix}")


def save_mesh(mesh: Mesh, file_path: Path | str) -> None:
    """
    Сохранить сетку в файл.

    Args:
        mesh: Сетка для сохранения
        file_path: Путь к выходному файлу (.json, .dat)

    Raises:
        ValueError: Если формат файла не поддерживается
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Сохранение в JSON (простой формат для результатов)
    if path.suffix == ".json":
        data = {
            "mesh": {
                "num_faces": len(mesh.faces),
                "num_nodes": len(mesh.nodes),
                "num_edges": len(mesh.edges),
            },
            "metadata": {
                "format": "mesh_reapairer_v1",
                "description": "Repaired mesh (placeholder format)",
            },
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return

    # Сохранение в .dat формат (MSU)
    if path.suffix == ".dat":
        # TODO: Сериализация в .dat формат
        raise NotImplementedError("DAT mesh saving not yet implemented")

    raise ValueError(f"Unsupported mesh format: {path.suffix}")


__all__ = ["load_mesh", "save_mesh"]