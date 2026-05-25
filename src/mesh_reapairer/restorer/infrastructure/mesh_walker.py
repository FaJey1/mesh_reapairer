"""
MeshWalker — удаление внутренних граней сетки после триангуляции.

Алгоритм (Meshcheryakov & Rybakov 2023, Section 5.2):
  1. Стартовая грань: минимальная x-координата центра среди не-новых граней.
  2. BFS через рёбра:
     - 2 инцидентных грани (manifold): переходим к соседу.
     - >2 граней (ring edge): переходим через face.outer_neighbour() —
       максимум dot(n̂_A, O→P_centroid), реализовано в msu.Face.
     - 1 грань (boundary / T-стык): барьер, не переходим.
  3. Непосещённые грани — внутренние → сохранить координаты → удалить.
  4. Очистить свободные рёбра и изолированные вершины.
"""
from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Mesh


class MeshWalker:
    """BFS-обход внешней поверхности для выделения и удаления внутренних граней."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def remove_inner_faces(
        self,
        mesh: "Mesh",
        new_face_ids: Set[int],
    ) -> Tuple[Set[int], int, List[Tuple[np.ndarray, np.ndarray, np.ndarray]]]:
        """
        Удалить внутренние грани методом BFS-обхода внешней поверхности.

        Args:
            mesh: Сетка после FanTriangulator (изменяется на месте).
            new_face_ids: glo_id новых треугольников (не используются как старт).

        Returns:
            (outer_face_ids, removed_count, inner_geoms)
            inner_geoms: координаты удалённых граней (для визуализации панели 7).
        """
        if not mesh.faces:
            return set(), 0, []

        start = self._find_start_face(mesh, new_face_ids)
        if start is None:
            self.logger.warning("MeshWalker: нет стартовой грани")
            return {f.glo_id for f in mesh.faces}, 0, []

        outer_ids = self._bfs(start)

        inner_faces = [f for f in list(mesh.faces) if f.glo_id not in outer_ids]

        # Сохраняем геометрию ДО удаления — для визуализации панели 7
        inner_geoms: List[Tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for f in inner_faces:
            if len(f.nodes) == 3:
                inner_geoms.append(
                    (f.nodes[0].p.copy(), f.nodes[1].p.copy(), f.nodes[2].p.copy())
                )

        removed = len(inner_faces)
        for f in inner_faces:
            try:
                mesh.delete_face(f)
            except Exception as exc:
                self.logger.warning(f"delete_face {f.glo_id}: {exc}")

        mesh.delete_faces_free_edges()
        mesh.delete_isolated_nodes()

        self.logger.info(
            f"MeshWalker: outer={len(outer_ids)}, removed={removed}, "
            f"after={len(mesh.faces)}"
        )
        return outer_ids, removed, inner_geoms

    # ------------------------------------------------------------------
    # Приватная логика
    # ------------------------------------------------------------------

    def _find_start_face(
        self,
        mesh: "Mesh",
        new_face_ids: Set[int],
    ) -> Optional["Face"]:
        """Грань с минимальной x-координатой центра среди не-новых (старых) граней."""
        candidates = [f for f in mesh.faces if f.glo_id not in new_face_ids]
        if not candidates:
            candidates = list(mesh.faces)
        if not candidates:
            return None
        return min(candidates, key=lambda f: float(f.center()[0]))

    def _bfs(self, start: "Face") -> Set[int]:
        """
        BFS от стартовой грани.

        Правила перехода:
          len(edge.faces) == 2  → face.neighbour(edge)        (manifold)
          len(edge.faces) >  2  → face.outer_neighbour(edge)  (ring edge, r_article_9)
          len(edge.faces) == 1  → барьер                      (T-стык)
        """
        visited: Set[int] = set()
        queue: deque = deque([start])
        visited.add(start.glo_id)

        while queue:
            face = queue.popleft()
            for edge in face.edges:
                n = len(edge.faces)
                if n == 2:
                    nb = face.neighbour(edge)
                    if nb is not None and nb.glo_id not in visited:
                        visited.add(nb.glo_id)
                        queue.append(nb)
                elif n > 2:
                    nb = face.outer_neighbour(edge)
                    if nb is not None and nb.glo_id not in visited:
                        visited.add(nb.glo_id)
                        queue.append(nb)
                # n == 1: T-junction — не переходим

        return visited
