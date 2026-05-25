"""
Кэш смежности (adjacency) граней для быстрой проверки соседства.

Предварительно строит карту соседей для всех граней сетки.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Set

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh, Face

logger = logging.getLogger(__name__)


class AdjacencyCache:
    """
    Кэш смежности граней - хранит для каждой грани список соседних граней.

    Соседи - это грани, которые имеют общее ребро.
    """

    def __init__(self):
        """Инициализация пустого кэша."""
        self._adjacency: Dict[int, Set[int]] = {}  # face_id -> {neighbor_face_ids}
        self._built = False

    def build(self, mesh: Mesh) -> None:
        """
        Построить кэш смежности для всей сетки.

        Args:
            mesh: Треугольная сетка

        Complexity: O(E * avg_faces_per_edge) ≈ O(F) для треугольной сетки
        """
        logger.debug(f"Building adjacency cache for {len(mesh.faces)} faces")

        self._adjacency.clear()

        # Инициализируем пустые множества для всех граней
        for face in mesh.faces:
            self._adjacency[face.glo_id] = set()

        # Проходим по всем ребрам, добавляем смежность
        for edge in mesh.edges:
            # У каждого ребра есть список инцидентных граней
            if not hasattr(edge, 'faces') or len(edge.faces) < 2:
                continue

            # Для каждой пары граней на этом ребре
            for i, face_a in enumerate(edge.faces):
                for face_b in edge.faces[i+1:]:
                    # Добавляем взаимную смежность
                    self._adjacency[face_a.glo_id].add(face_b.glo_id)
                    self._adjacency[face_b.glo_id].add(face_a.glo_id)

        self._built = True

        # Статистика
        total_neighbors = sum(len(neighbors) for neighbors in self._adjacency.values())
        avg_neighbors = total_neighbors / len(self._adjacency) if self._adjacency else 0

        logger.info(
            f"Adjacency cache built: {len(self._adjacency)} faces, "
            f"avg {avg_neighbors:.1f} neighbors/face"
        )

    def are_neighbors(self, face_a_id: int, face_b_id: int) -> bool:
        """
        Проверить, являются ли грани соседями (O(1) после построения кэша).

        Args:
            face_a_id, face_b_id: ID граней

        Returns:
            True если грани соседи (имеют общее ребро)

        Raises:
            RuntimeError: Если кэш не построен
        """
        if not self._built:
            raise RuntimeError("Adjacency cache not built. Call build() first.")

        return face_b_id in self._adjacency.get(face_a_id, set())

    def get_neighbors(self, face_id: int) -> Set[int]:
        """
        Получить всех соседей грани.

        Args:
            face_id: ID грани

        Returns:
            Множество ID соседних граней

        Raises:
            RuntimeError: Если кэш не построен
        """
        if not self._built:
            raise RuntimeError("Adjacency cache not built. Call build() first.")

        return self._adjacency.get(face_id, set())

    def stats(self) -> Dict[str, int]:
        """
        Статистика кэша.

        Returns:
            Словарь со статистикой
        """
        if not self._built:
            return {'built': 0}

        total_neighbors = sum(len(neighbors) for neighbors in self._adjacency.values())
        avg_neighbors = total_neighbors / len(self._adjacency) if self._adjacency else 0

        return {
            'built': 1,
            'faces': len(self._adjacency),
            'total_neighbor_pairs': total_neighbors // 2,  # Каждое ребро считается дважды
            'avg_neighbors_per_face': avg_neighbors,
        }


__all__ = ['AdjacencyCache']