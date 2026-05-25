"""
Построение графа пересечений из результатов поиска.

Реализует построение графа I(M,W) и его расширения J(M,W).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import Segment

from .intersection_graph import IntersectionGraph, GraphNode, GraphEdge, EdgeType


class GraphBuilder:
    """
    Строитель графа пересечений.

    Строит граф I(M,W) из валидных пар и расширяет его до J(M,W)
    добавлением impossible пар с фильтрацией шума.
    """

    def __init__(
        self,
        logger: logging.Logger,
        max_distance_threshold: float = 0.1,
        enable_spatial_filter: bool = True,
        enable_topological_filter: bool = True
    ):
        """
        Инициализация.

        Args:
            logger: Логгер
            max_distance_threshold: Максимальное расстояние от impossible до valid пары
            enable_spatial_filter: Фильтровать по пространственной близости
            enable_topological_filter: Фильтровать по топологической близости (общая ячейка)
        """
        self.logger = logger
        self.max_distance_threshold = max_distance_threshold
        self.enable_spatial_filter = enable_spatial_filter
        self.enable_topological_filter = enable_topological_filter

    def build_graph(
        self,
        valid_pairs: List[Tuple[Face, Face, Segment]],
        impossible_pairs: List[Tuple[Face, Face]]
    ) -> IntersectionGraph:
        """
        Построить граф пересечений J(M,W).

        Args:
            valid_pairs: Список валидных пар с сегментами (α-вершины)
            impossible_pairs: Список невалидных пар (β-вершины)

        Returns:
            Граф пересечений J(M,W)
        """
        self.logger.info("Building intersection graph J(M,W)")

        graph = IntersectionGraph()

        # 1. Добавляем α-вершины (валидные пары)
        node_map = {}  # (face_a_id, face_b_id) -> node_id

        for face_a, face_b, segment in valid_pairs:
            key = self._make_key(face_a.glo_id, face_b.glo_id)

            node = GraphNode(
                face_a=face_a,
                face_b=face_b,
                segment=segment
            )
            node_id = graph.add_node(node)
            node_map[key] = node_id

        self.logger.debug(f"Added {len(valid_pairs)} α-nodes (valid pairs)")

        # 2. Фильтруем impossible пары (убираем шум)
        filtered_impossible = self._filter_impossible_pairs(
            valid_pairs, impossible_pairs
        )

        self.logger.info(
            f"Filtered impossible pairs: {len(impossible_pairs)} → {len(filtered_impossible)} "
            f"(removed {len(impossible_pairs) - len(filtered_impossible)} noisy pairs)"
        )

        # 3. Добавляем β-вершины (отфильтрованные impossible пары)
        for face_a, face_b in filtered_impossible:
            key = self._make_key(face_a.glo_id, face_b.glo_id)

            # Пропускаем дубликаты
            if key in node_map:
                continue

            node = GraphNode(
                face_a=face_a,
                face_b=face_b,
                segment=None  # Нет сегмента
            )
            node_id = graph.add_node(node)
            node_map[key] = node_id

        self.logger.debug(
            f"Added {len(filtered_impossible)} β-nodes (impossible pairs), "
            f"total nodes={len(graph.nodes)}"
        )

        # 3. Добавляем α-ребра (между смежными валидными парами)
        self._add_alpha_edges(graph, node_map, valid_pairs)

        # 4. Находим якоря (до добавления β-ребер!)
        graph.find_anchors()
        initial_anchors = len(graph.anchors)
        self.logger.debug(f"Found {initial_anchors} anchors before β-edges")

        # 5. Добавляем β-ребра ТОЛЬКО для якорей
        # Строим пути от якорей через промежуточные узлы к другим якорям
        self._add_beta_edges_for_anchors(graph, node_map)

        # 6. Фильтруем шум в графе
        self._filter_graph_noise(graph)

        # 7. Обновляем якоря после фильтрации
        graph.find_anchors()

        # 8. КРИТИЧНО: Удаляем β-ребра между якорями!
        # После фильтрации некоторые узлы могли стать якорями,
        # но между ними уже есть β-ребра (созданные до фильтрации).
        # Эти ребра нужно удалить, чтобы MST не находил прямые пути якорь→якорь.
        removed_anchor_edges = 0
        edges_to_remove = []
        beta_edges_count = 0
        anchor_to_anchor_beta_count = 0

        for edge_id, edge in graph.edges.items():
            if edge.edge_type == EdgeType.BETA:
                beta_edges_count += 1
                node1_is_anchor = edge.node1.node_id in graph.anchors
                node2_is_anchor = edge.node2.node_id in graph.anchors
                if node1_is_anchor and node2_is_anchor:
                    anchor_to_anchor_beta_count += 1
                    edges_to_remove.append(edge_id)

        self.logger.debug(
            f"Checked {beta_edges_count} β-edges, found {anchor_to_anchor_beta_count} "
            f"between anchors (out of {len(graph.anchors)} total anchors)"
        )

        for edge_id in edges_to_remove:
            graph.remove_edge(edge_id)
            removed_anchor_edges += 1

        if removed_anchor_edges > 0:
            self.logger.info(
                f"Removed {removed_anchor_edges} β-edges between anchors "
                f"(created before anchors were determined)"
            )

        stats = graph.stats()
        self.logger.info(
            f"Graph built: nodes={stats['nodes']}, edges={stats['edges']}, "
            f"α-edges={stats['alpha_edges']}, β-edges={stats['beta_edges']}, "
            f"anchors={stats['anchors']}"
        )

        return graph

    def _filter_graph_noise(self, graph: IntersectionGraph) -> None:
        """
        Фильтровать шум в графе.

        Удаляет:
        1. Маленькие изолированные компоненты (не связанные с основным циклом)
        2. Вершины с degree < 2, имеющие только β-ребра (не могут быть частью пути)

        Args:
            graph: Граф для фильтрации
        """
        self.logger.info("Filtering graph noise...")

        # 1. Найти связные компоненты
        components = graph.find_connected_components()
        if not components:
            return

        self.logger.info(f"Found {len(components)} connected components")
        for i, comp in enumerate(components[:5]):  # Логируем только первые 5
            self.logger.debug(f"Component {i}: {len(comp)} nodes")

        # 2. Удалить маленькие компоненты
        max_component_size = len(components[0])
        min_component_size = max(3, int(max_component_size * 0.05))  # 5% от максимума или минимум 3

        nodes_to_remove = []
        for component in components[1:]:  # Пропускаем самую большую
            if len(component) < min_component_size:
                nodes_to_remove.extend(component)

        if nodes_to_remove:
            self.logger.info(
                f"Removing {len(nodes_to_remove)} nodes from small components "
                f"(size < {min_component_size})"
            )
            for node_id in nodes_to_remove:
                graph.remove_node(node_id)

        # 3. Удалить вершины с degree < 2, имеющие только β-ребра
        low_degree_nodes = []
        for node_id in list(graph.nodes.keys()):
            total_degree = graph.degree(node_id)
            alpha_degree = graph.degree(node_id, edge_type=EdgeType.ALPHA)

            # Если degree < 2 И нет α-ребер → шум
            if total_degree < 2 and alpha_degree == 0:
                low_degree_nodes.append(node_id)

        if low_degree_nodes:
            self.logger.info(
                f"Removing {len(low_degree_nodes)} low-degree nodes "
                f"(degree < 2 with no α-edges)"
            )
            for node_id in low_degree_nodes:
                graph.remove_node(node_id)

        self.logger.info(
            f"Graph after noise filtering: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
        )

    def _make_key(self, face_a_id: int, face_b_id: int) -> tuple[int, int]:
        """Создать нормализованный ключ для пары ячеек."""
        return (min(face_a_id, face_b_id), max(face_a_id, face_b_id))

    def _filter_impossible_pairs(
        self,
        valid_pairs: List[Tuple[Face, Face, Segment]],
        impossible_pairs: List[Tuple[Face, Face]]
    ) -> List[Tuple[Face, Face]]:
        """
        Фильтровать impossible пары, оставляя только близкие к valid парам.

        Стратегия фильтрации:
        1. Топологическая близость: impossible пара имеет общую ячейку с valid парой
        2. Пространственная близость: расстояние до ближайшей valid пары < threshold

        Args:
            valid_pairs: Список валидных пар
            impossible_pairs: Список невалидных пар

        Returns:
            Отфильтрованный список impossible пар (без шума)
        """
        if not impossible_pairs:
            return []

        # Если фильтры отключены, возвращаем все
        if not self.enable_spatial_filter and not self.enable_topological_filter:
            return impossible_pairs

        # Предвычисляем центры валидных пар для пространственного фильтра
        valid_centers = []
        valid_face_ids = set()

        for face_a, face_b, segment in valid_pairs:
            # Центр пары = середина отрезка между центрами ячеек
            center_a = face_a.center()
            center_b = face_b.center()
            center = (center_a + center_b) / 2.0
            valid_centers.append(center)

            # Собираем ID ячеек для топологического фильтра
            valid_face_ids.add(face_a.glo_id)
            valid_face_ids.add(face_b.glo_id)

        import numpy as np
        valid_centers_arr = np.array(valid_centers)

        # Фильтруем impossible пары
        filtered = []

        for face_a, face_b in impossible_pairs:
            keep = False

            # 1. Топологический фильтр (быстрый)
            if self.enable_topological_filter:
                # Проверяем, есть ли общая ячейка с валидными парами
                impossible_face_ids = {face_a.glo_id, face_b.glo_id}
                if impossible_face_ids & valid_face_ids:
                    keep = True

            # 2. Пространственный фильтр (медленный, если топологический не прошел)
            if not keep and self.enable_spatial_filter:
                # Вычисляем центр impossible пары
                center_a = face_a.center()
                center_b = face_b.center()
                impossible_center = (center_a + center_b) / 2.0

                # Ищем расстояние до ближайшей валидной пары
                distances = np.linalg.norm(valid_centers_arr - impossible_center, axis=1)
                min_distance = np.min(distances)

                if min_distance <= self.max_distance_threshold:
                    keep = True

            if keep:
                filtered.append((face_a, face_b))

        return filtered

    def _add_alpha_edges(
        self,
        graph: IntersectionGraph,
        node_map: dict,
        valid_pairs: List[Tuple[Face, Face, Segment]]
    ) -> None:
        """
        Добавить α-ребра между смежными валидными парами.

        Две валидные пары смежны, если их сегменты имеют общую точку.
        """
        alpha_count = 0

        # Для каждой пары валидных пар проверяем смежность сегментов
        valid_list = list(valid_pairs)
        for i, (face_a1, face_b1, seg1) in enumerate(valid_list):
            key1 = self._make_key(face_a1.glo_id, face_b1.glo_id)
            node1_id = node_map.get(key1)
            if node1_id is None:
                continue

            for face_a2, face_b2, seg2 in valid_list[i+1:]:
                key2 = self._make_key(face_a2.glo_id, face_b2.glo_id)
                node2_id = node_map.get(key2)
                if node2_id is None:
                    continue

                # Проверяем смежность сегментов
                if self._are_segments_adjacent(seg1, seg2):
                    node1 = graph.nodes[node1_id]
                    node2 = graph.nodes[node2_id]

                    edge = GraphEdge(
                        node1=node1,
                        node2=node2,
                        edge_type=EdgeType.ALPHA
                    )
                    graph.add_edge(edge)
                    alpha_count += 1

        self.logger.debug(f"Added {alpha_count} α-edges")

    def _are_segments_adjacent(self, seg1: Segment, seg2: Segment, epsilon: float = 1e-8) -> bool:
        """
        Проверить, являются ли сегменты смежными (имеют общую точку).

        Args:
            seg1, seg2: Сегменты
            epsilon: Порог для сравнения точек

        Returns:
            True если сегменты смежны
        """
        if not seg1.nodes or not seg2.nodes:
            return False

        # Получаем координаты концов сегментов
        points1 = [n.p if hasattr(n, 'p') else n for n in seg1.nodes]
        points2 = [n.p if hasattr(n, 'p') else n for n in seg2.nodes]

        # Проверяем близость любых точек
        for p1 in points1:
            for p2 in points2:
                import numpy as np
                distance = np.linalg.norm(p1 - p2)
                if distance < epsilon:
                    return True

        return False

    def _add_beta_edges_for_anchors(
        self,
        graph: IntersectionGraph,
        node_map: dict
    ) -> None:
        """
        Добавить β-ребра для построения путей между якорями.

        Стратегия:
        1. Собираем все узлы, достижимые от якорей по общим граням (BFS без ограничения глубины)
        2. Строим полный β-подграф на этом множестве узлов

        Это гарантирует, что все якоря будут соединены путями.
        """
        if not graph.anchors:
            self.logger.debug("No anchors found, skipping β-edges")
            return

        anchor_nodes = [graph.nodes[anchor_id] for anchor_id in graph.anchors]
        all_nodes = list(graph.nodes.values())

        # 1. BFS от всех якорей ТОЛЬКО через β-узлы (без segment)
        # Якоря - это α-узлы с degree=1, они могут иметь segment
        # Путь восстановления: якорь → β-узлы → якорь
        recovery_nodes = set(graph.anchors)

        for anchor_node in anchor_nodes:
            visited = {anchor_node.node_id}
            queue = [anchor_node]

            while queue:
                current_node = queue.pop(0)

                # Ищем всех соседей (узлы с общей гранью)
                for neighbor_node in all_nodes:
                    if neighbor_node.node_id in visited:
                        continue

                    # Проверяем общую ячейку
                    if current_node.has_common_face(neighbor_node):
                        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: добавляем только β-узлы и якоря
                        # β-узел = узел без segment (кроме якорей)
                        is_anchor = neighbor_node.node_id in graph.anchors
                        is_beta_node = neighbor_node.segment is None

                        if is_anchor or is_beta_node:
                            recovery_nodes.add(neighbor_node.node_id)
                            visited.add(neighbor_node.node_id)

                            # Продолжаем BFS только через β-узлы
                            # Если достигли якоря, не идем дальше
                            if not is_anchor:
                                queue.append(neighbor_node)

        # 2. Добавляем только прямые β-ребра (1-hop соседи)
        # НЕ строим полный подграф - это создает избыточные пути
        beta_count = 0
        recovery_nodes_list = [graph.nodes[node_id] for node_id in recovery_nodes]

        for node in recovery_nodes_list:
            # Для каждого узла добавляем ребра только к его прямым соседям
            for neighbor_node in all_nodes:
                # Пропускаем если не в recovery subgraph
                if neighbor_node.node_id not in recovery_nodes:
                    continue

                # Пропускаем себя
                if neighbor_node.node_id == node.node_id:
                    continue

                # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: НЕ создаем β-ребра между двумя якорями!
                # Якоря должны соединяться ТОЛЬКО через промежуточные β-узлы
                node_is_anchor = node.node_id in graph.anchors
                neighbor_is_anchor = neighbor_node.node_id in graph.anchors

                if node_is_anchor and neighbor_is_anchor:
                    continue  # Пропускаем пару якорь→якорь

                # Проверяем, есть ли уже ребро (α или β)
                existing_edge = graph.get_edge(node.node_id, neighbor_node.node_id)
                if existing_edge:
                    continue

                # Добавляем β-ребро только если узлы - прямые соседи (общая грань)
                if node.has_common_face(neighbor_node):
                    edge = GraphEdge(
                        node1=node,
                        node2=neighbor_node,
                        edge_type=EdgeType.BETA
                    )
                    graph.add_edge(edge)
                    beta_count += 1

        self.logger.debug(
            f"Added {beta_count} β-edges (1-hop neighbors) for {len(anchor_nodes)} anchors "
            f"({len(recovery_nodes)} nodes in recovery subgraph)"
        )


__all__ = ['GraphBuilder']
