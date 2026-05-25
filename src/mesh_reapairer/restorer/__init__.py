"""
Модуль восстановления сетки.

Конвейер:
  1. FanTriangulator — веерная триангуляция f_fix-ячеек вдоль ломаной пересечения.

Быстрое использование:
    from mesh_reapairer.restorer import restore_mesh
    result = restore_mesh(mesh, intersection_result)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import IntersectionResult

from mesh_reapairer.src.mesh_reapairer.restorer.application.config import RestorerConfig
from mesh_reapairer.src.mesh_reapairer.restorer.application.restore_mesh import RestoreMeshUseCase
from mesh_reapairer.src.mesh_reapairer.restorer.domain.entities import RestorationResult
from mesh_reapairer.src.mesh_reapairer.restorer.infrastructure.fan_triangulator import FanTriangulator
from mesh_reapairer.src.mesh_reapairer.restorer.infrastructure.mesh_walker import MeshWalker


def restore_mesh(
    mesh: "Mesh",
    intersection_result: "IntersectionResult",
    config: Optional[RestorerConfig] = None,
) -> RestorationResult:
    """
    Веерная триангуляция f_fix-ячеек пересекающейся сетки.

    Изменяет `mesh` на месте:
      - Для каждой f_fix-ячейки строит упорядоченный полигон (вершины + точки пересечения).
      - Веерно триангулирует полигон из hub-вершины.
      - Удаляет исходные f_fix-ячейки.

    Args:
        mesh: Триангулированная поверхностная сетка (msu.Mesh).
        intersection_result: Результат find_self_intersections() с заполненным f_fix.
        config: Необязательный RestorerConfig; если None — значения по умолчанию.

    Returns:
        RestorationResult со статистикой.
    """
    use_case = RestoreMeshUseCase(config)
    return use_case.execute(mesh, intersection_result)


__all__ = [
    "restore_mesh",
    "RestoreMeshUseCase",
    "RestorerConfig",
    "RestorationResult",
    "FanTriangulator",
    "MeshWalker",
]
