"""
FanTriangulator — веерная триангуляция f_fix-ячеек вдоль ломаных пересечений.

Для каждой грани из f_fix:
  1. Находим точки пересечения сегментов с рёбрами грани (параметр t на ребре).
  2. Строим упорядоченный полигон: вершины + вставленные точки на рёбрах.
  3. Выбираем hub = первую вершину без cut-точек на инцидентных рёбрах.
  4. Веерная триангуляция из hub: hub → polygon[i] → polygon[i+1].
  5. Удаляем исходную грань.

T-стыки у соседних граней (не входящих в f_fix) — не обрабатываются (задача следующего этапа).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Mesh, Node
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import Segment

EPS = 1e-9


def _project_on_edge(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Параметр t ∈ [0,1] проекции точки p на отрезок a→b."""
    ab = b - a
    ab2 = float(np.dot(ab, ab))
    if ab2 < EPS:
        return 0.0
    return float(np.dot(p - a, ab) / ab2)


def _point_on_edge(p: np.ndarray, a: np.ndarray, b: np.ndarray, eps: float) -> Optional[float]:
    """
    Если p лежит на отрезке a→b (строго внутри), возвращает t ∈ (0,1).
    Иначе None.
    """
    t = _project_on_edge(p, a, b)
    if t <= eps or t >= 1.0 - eps:
        return None
    # Проверяем расстояние от p до точки a + t*(b-a)
    proj = a + t * (b - a)
    dist = float(np.linalg.norm(p - proj))
    if dist > eps:
        return None
    return t


class FanTriangulator:
    """Веерная триангуляция ячеек f_fix сетки."""

    def __init__(self, epsilon: float = 1e-6, logger: Optional[logging.Logger] = None):
        self.eps = epsilon
        self.logger = logger or logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def triangulate(
        self,
        mesh: "Mesh",
        f_fix: Dict[int, Tuple["Face", List["Segment"]]],
    ) -> Tuple[Set[int], Set[int]]:
        """
        Выполнить веерную триангуляцию всех f_fix-ячеек.

        Args:
            mesh: Сетка (изменяется на месте).
            f_fix: {face_id: (face, [segments])}.

        Returns:
            (f_fix_ids, new_face_ids) — множества glo_id.
        """
        if not mesh.zones:
            self.logger.warning("FanTriangulator: no zones in mesh")
            return set(), set()

        zone = mesh.zones[0]
        f_fix_ids: Set[int] = set()
        new_face_ids: Set[int] = set()

        faces_to_delete: List["Face"] = []

        for face_id, (face, segments) in f_fix.items():
            # Проверяем, что грань ещё в сетке
            if face not in mesh.faces:
                self.logger.debug(f"Face {face_id} already removed, skip")
                continue

            f_fix_ids.add(face_id)
            new_ids = self._triangulate_face(mesh, face, segments, zone)
            new_face_ids.update(new_ids)
            faces_to_delete.append(face)

        # Удаляем исходные f_fix-грани
        for face in faces_to_delete:
            try:
                mesh.delete_face(face)
            except Exception as e:
                self.logger.warning(f"delete_face failed for {face.glo_id}: {e}")

        self.logger.info(
            f"FanTriangulator: processed {len(f_fix_ids)} faces, "
            f"created {len(new_face_ids)} new triangles"
        )
        return f_fix_ids, new_face_ids

    # ------------------------------------------------------------------
    # Приватная логика
    # ------------------------------------------------------------------

    def _triangulate_face(
        self,
        mesh: "Mesh",
        face: "Face",
        segments: List["Segment"],
        zone,
    ) -> List[int]:
        """Веерная триангуляция одной грани. Возвращает glo_id новых граней."""
        V = list(face.nodes)  # [V0, V1, V2]
        if len(V) != 3:
            self.logger.warning(f"Face {face.glo_id} is not a triangle (n={len(V)}), skip")
            return []

        # 1. Собрать cut-points на каждом ребре
        # edge_cuts[ei] = sorted list of (t, coords)
        edge_cuts: Dict[int, List[Tuple[float, np.ndarray]]] = {0: [], 1: [], 2: []}

        for seg in segments:
            if not seg.nodes:
                continue
            pts = [seg.nodes[0].p, seg.nodes[-1].p]
            for pt_coords in pts:
                for ei in range(3):
                    a = V[ei].p
                    b = V[(ei + 1) % 3].p
                    t = _point_on_edge(pt_coords, a, b, self.eps)
                    if t is not None:
                        # Проверяем дубли по t
                        if not any(abs(t - et) < self.eps for et, _ in edge_cuts[ei]):
                            edge_cuts[ei].append((t, pt_coords.copy()))

        # Сортируем по t
        for ei in range(3):
            edge_cuts[ei].sort(key=lambda x: x[0])

        # Если нет ни одной cut-точки — нечего триангулировать
        total_cuts = sum(len(ec) for ec in edge_cuts.values())
        if total_cuts == 0:
            self.logger.debug(f"Face {face.glo_id}: no cut points found, skip")
            return []

        # 2. Строим упорядоченный полигон
        polygon: List["Node"] = []
        cut_node_indices: Set[int] = set()  # позиции cut-узлов в polygon

        for ei in range(3):
            polygon.append(V[ei])
            for t, coords in edge_cuts[ei]:
                n = mesh.add_node(coords, zone, is_merge_nodes=True)
                cut_node_indices.add(len(polygon))
                polygon.append(n)

        n_poly = len(polygon)
        if n_poly < 3:
            return []

        # 3. Выбрать hub = первая вершина без cut-точек на обоих инцидентных рёбрах
        #    Инцидентные рёбра для V[i]: ei=(i-1)%3 и ei=i
        hub_idx = self._choose_hub(V, edge_cuts, polygon)
        if hub_idx != 0:
            polygon = polygon[hub_idx:] + polygon[:hub_idx]

        # 4. Веерная триангуляция из hub = polygon[0]
        hub = polygon[0]
        new_ids: List[int] = []

        for i in range(1, n_poly - 1):
            b = polygon[i]
            c = polygon[i + 1]
            if hub is b or hub is c or b is c:
                continue
            if mesh.find_face(hub, b, c) is not None:
                continue
            # Добавляем узлы в зону если надо
            for nd in (hub, b, c):
                if nd not in zone.nodes:
                    zone.nodes.append(nd)
            new_face = mesh.add_face(hub, b, c, zone)
            if new_face is not None:
                new_ids.append(new_face.glo_id)

        self.logger.debug(
            f"Face {face.glo_id}: polygon={n_poly}, cuts={total_cuts}, "
            f"new_triangles={len(new_ids)}"
        )
        return new_ids

    def _choose_hub(
        self,
        V: List["Node"],
        edge_cuts: Dict[int, List],
        polygon: List["Node"],
    ) -> int:
        """
        Выбрать индекс hub в polygon.
        Предпочитаем вершину V[i], у которой обе инцидентные рёбра (ei=i-1 и ei=i)
        не имеют cut-точек — такой hub создаёт только «чистые» спицы.
        Если таких нет, берём V[0].
        """
        for i in range(3):
            ei_prev = (i - 1) % 3
            ei_cur = i
            if not edge_cuts[ei_prev] and not edge_cuts[ei_cur]:
                # Найти позицию V[i] в polygon (до rotate)
                try:
                    return polygon.index(V[i])
                except ValueError:
                    pass
        return 0
