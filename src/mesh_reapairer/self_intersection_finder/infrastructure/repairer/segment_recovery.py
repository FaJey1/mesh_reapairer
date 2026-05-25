"""
Восстановление сегментов пересечения из путей графа.

Отвечает за геометрическую интерполяцию сегментов для β-узлов,
найденных на путях MST между якорями.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, List

import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh

from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import IntersectionResult, Segment
from .intersection_graph import IntersectionGraph
from .path_finder import PathResult


class SegmentRecovery:
    """
    Восстанавливает сегменты пересечения для β-узлов.

    Для каждого β-узла на пути между якорями строит сегмент,
    соединяющий ближайшие точки соседних узлов.
    """

    def __init__(self, mode: str, logger: Optional[logging.Logger] = None):
        self.mode = mode
        self.logger = logger or logging.getLogger(__name__)

    def recover_from_paths(
        self,
        result: IntersectionResult,
        graph: IntersectionGraph,
        paths: List[PathResult],
        mesh: 'Mesh'
    ) -> int:
        """
        Восстановить сегменты из путей MST.

        Returns:
            Количество восстановленных сегментов
        """
        self.logger.info(f"Recovering {len(paths)} segments from paths (mode={self.mode})...")

        recovered_count = 0
        recovered_pairs: set = set()

        for path_idx, path_result in enumerate(paths):
            if not path_result.found or len(path_result.path) < 2:
                continue

            nodes = [graph.nodes[node_id] for node_id in path_result.path]

            for i, node in enumerate(nodes):
                if node.segment is not None:
                    graph.update_node_edge_types(node.node_id)
                    continue

                pair_key = (
                    min(node.face_a.glo_id, node.face_b.glo_id),
                    max(node.face_a.glo_id, node.face_b.glo_id)
                )
                if pair_key in recovered_pairs:
                    continue

                prev_node = nodes[i - 1] if i > 0 else None
                next_node = nodes[i + 1] if i < len(nodes) - 1 else None

                segment = self._create_segment_between_nodes(
                    node, prev_node, next_node, mesh
                )
                if not segment or not segment.nodes:
                    continue

                segment.face_a = node.face_a
                segment.face_b = node.face_b
                node.segment = segment
                graph.update_node_edge_types(node.node_id)

                self._add_to_result(result, node, segment)
                recovered_pairs.add(pair_key)
                recovered_count += 1

        self.logger.info(
            f"Recovered {recovered_count} segments from paths. "
            f"Total valid_pairs: {len(result.valid_pairs)}"
        )
        return recovered_count

    def recover_isolated_nodes(
        self,
        result: IntersectionResult,
        graph: IntersectionGraph,
        mesh: 'Mesh'
    ) -> int:
        """
        Восстановить β-узлы, которые не были на путях MST.

        Returns:
            Количество восстановленных сегментов
        """
        recovered_pairs = {
            (min(fa.glo_id, fb.glo_id), max(fa.glo_id, fb.glo_id))
            for fa, fb, _ in result.valid_pairs
        }

        isolated = [
            node for node in graph.nodes.values()
            if node.segment is None
            and (min(node.face_a.glo_id, node.face_b.glo_id),
                 max(node.face_a.glo_id, node.face_b.glo_id)) not in recovered_pairs
        ]

        if not isolated:
            self.logger.info("No isolated β-nodes to recover")
            return 0

        self.logger.info(f"Recovering {len(isolated)} isolated β-nodes...")
        recovered_count = 0

        for node in isolated:
            neighbors = graph.get_neighbors(node.node_id)
            neighbor_nodes = [graph.nodes[nid] for nid in neighbors if nid in graph.nodes]
            local_nodes = [node] + neighbor_nodes[:2]

            segment = self._interpolate_segment(local_nodes)
            if not segment or not segment.nodes:
                continue

            segment.face_a = node.face_a
            segment.face_b = node.face_b
            node.segment = segment
            graph.update_node_edge_types(node.node_id)

            self._add_to_result(result, node, segment)
            recovered_count += 1

        self.logger.info(f"Recovered {recovered_count} isolated β-nodes")
        return recovered_count

    def _create_segment_between_nodes(self, current_node, prev_node, next_node, mesh: 'Mesh'):
        """Создать сегмент для β-узла, соединяющий соседние узлы в пути."""
        from mesh_reapairer.src.mesh_reapairer.msu import Node as MsuNode

        start_point = self._get_connection_point(prev_node, current_node, mesh, is_start=True)
        end_point = self._get_connection_point(current_node, next_node, mesh, is_start=False)

        return Segment(
            nodes=[MsuNode(start_point), MsuNode(end_point)],
            face_a=current_node.face_a,
            face_b=current_node.face_b
        )

    def _get_connection_point(self, from_node, to_node, mesh: 'Mesh', is_start: bool) -> np.ndarray:
        """Найти точку соединения между двумя узлами."""
        if from_node is None or to_node is None:
            node = from_node if to_node is None else to_node
            return node.point.copy()

        if is_start:
            ref_node, target_node = from_node, to_node
        else:
            ref_node, target_node = from_node, to_node

        common_point = self._find_common_point(ref_node, target_node, mesh)

        if ref_node.segment is not None:
            target = common_point if common_point is not None else target_node.point
            return self._choose_closest_endpoint(ref_node.segment, target)

        if common_point is not None:
            return common_point

        return (ref_node.point + target_node.point) / 2.0

    def _find_common_point(self, node_i, node_j, mesh: 'Mesh') -> Optional[np.ndarray]:
        """Найти общую точку между двумя узлами через общие грани."""
        faces_i = {node_i.face_a, node_i.face_b}
        faces_j = {node_j.face_a, node_j.face_b}
        common_faces = faces_i & faces_j

        if not common_faces:
            return None

        common_face = next(iter(common_faces))
        other_face_i = next(iter(faces_i - {common_face}), None)
        other_face_j = next(iter(faces_j - {common_face}), None)

        if other_face_i and other_face_j:
            common_edge = self._find_common_edge(other_face_i, other_face_j)
            if common_edge:
                p1, p2 = common_edge.points()
                return (p1 + p2) / 2.0

        return common_face.center()

    def _find_common_edge(self, face_a, face_b):
        """Найти общее ребро между двумя гранями."""
        common = set(face_a.edges) & set(face_b.edges)
        return next(iter(common)) if common else None

    def _choose_closest_endpoint(self, segment, target: np.ndarray) -> np.ndarray:
        """Выбрать ближайшую конечную точку сегмента к целевой точке."""
        if not segment or not segment.nodes or len(segment.nodes) < 2:
            return target.copy()

        p0 = segment.nodes[0].p
        p1 = segment.nodes[-1].p
        return (p0 if np.linalg.norm(p0 - target) <= np.linalg.norm(p1 - target) else p1).copy()

    def _interpolate_segment(self, nodes: list) -> Optional[Segment]:
        """Создать сегмент через опорные точки узлов (для изолированных β-узлов)."""
        from mesh_reapairer.src.mesh_reapairer.msu import Node as MsuNode

        if len(nodes) < 1:
            return None

        points = [node.point for node in nodes]
        if len(points) < 2:
            return None

        return Segment(
            nodes=[MsuNode(points[0].copy()), MsuNode(points[-1].copy())],
            face_a=nodes[0].face_a,
            face_b=nodes[0].face_b
        )

    def _add_to_result(self, result: IntersectionResult, node, segment: Segment) -> None:
        """Добавить восстановленный сегмент в результат."""
        result.valid_pairs.append((node.face_a, node.face_b, segment))

        # Удаляем из impossible_pairs (O(n), но список обычно небольшой)
        for pair in list(result.impossible_pairs):
            fa, fb = pair
            if {fa.glo_id, fb.glo_id} == {node.face_a.glo_id, node.face_b.glo_id}:
                result.impossible_pairs.remove(pair)
                break

        fi_a = result.face_intersections
        fi_a.setdefault(node.face_a.glo_id, []).append(segment)
        fi_a.setdefault(node.face_b.glo_id, []).append(segment)


__all__ = ['SegmentRecovery']
