"""
RestoreMeshUseCase — триангуляция f_fix-ячеек + удаление внутренних граней.

Конвейер:
  1. FanTriangulator — констрейнтная веерная триангуляция f_fix-ячеек.
  2. MeshWalker      — BFS-обход внешней поверхности, удаление внутренних граней.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import IntersectionResult

from .config import RestorerConfig
from ..domain.entities import RestorationResult
from ..infrastructure.fan_triangulator import FanTriangulator
from ..infrastructure.mesh_walker import MeshWalker


class RestoreMeshUseCase:
    """Триангуляция f_fix-ячеек + BFS-удаление внутренних граней."""

    def __init__(self, config: Optional[RestorerConfig] = None):
        self.config = config or RestorerConfig.create_default()
        self.logger = logging.getLogger("mesh_reapairer.restorer")
        self.logger.setLevel(getattr(logging, self.config.logging_level, logging.INFO))
        self.triangulator = FanTriangulator(epsilon=self.config.epsilon, logger=self.logger)
        self.walker = MeshWalker(logger=self.logger)

    def execute(
        self,
        mesh: "Mesh",
        intersection_result: "IntersectionResult",
    ) -> RestorationResult:
        """
        Выполнить триангуляцию f_fix-ячеек и удалить внутренние грани.

        Args:
            mesh: Сетка (изменяется на месте).
            intersection_result: Результат find_self_intersections() с f_fix.

        Returns:
            RestorationResult со статистикой.
        """
        result = RestorationResult(mesh=mesh)
        f_fix = intersection_result.f_fix

        if not f_fix:
            self.logger.info("RestoreMesh: f_fix пуст, нечего обрабатывать")
            return result

        self.logger.info(
            f"RestoreMesh: триангуляция {len(f_fix)} f_fix-ячеек, "
            f"сетка: {len(mesh.faces)} граней, {len(mesh.nodes)} узлов"
        )

        # ── Шаг 1: FanTriangulator ────────────────────────────────────────────
        t0 = time.perf_counter()
        f_fix_ids, new_face_ids = self.triangulator.triangulate(mesh, f_fix)
        result.triangulation_time_ms = (time.perf_counter() - t0) * 1000
        result.f_fix_count = len(f_fix_ids)
        result.new_faces_count = len(new_face_ids)
        result.f_fix_ids = f_fix_ids
        result.new_face_ids = new_face_ids

        self.logger.info(
            f"FanTriangulator: {result.f_fix_count} ячеек, "
            f"{result.new_faces_count} новых треугольников, "
            f"сетка: {len(mesh.faces)} граней"
        )

        # ── Шаг 2: MeshWalker ─────────────────────────────────────────────────
        if self.config.enable_inner_removal:
            t1 = time.perf_counter()
            outer_ids, removed, inner_geoms = self.walker.remove_inner_faces(
                mesh, new_face_ids
            )
            result.walker_time_ms = (time.perf_counter() - t1) * 1000
            result.removed_faces_count = removed
            result.outer_face_ids_set = outer_ids
            result.inner_face_geometries = inner_geoms

            self.logger.info(
                f"MeshWalker: удалено {removed} внутренних граней, "
                f"осталось {len(mesh.faces)} граней, "
                f"время={result.walker_time_ms:.1f}мс"
            )
        else:
            self.logger.info("MeshWalker: отключён (enable_inner_removal=False)")

        self.logger.info(
            f"RestoreMesh: итог — {len(mesh.faces)} граней, "
            f"{len(mesh.nodes)} узлов, "
            f"total={result.total_time_ms():.1f}мс"
        )
        return result
