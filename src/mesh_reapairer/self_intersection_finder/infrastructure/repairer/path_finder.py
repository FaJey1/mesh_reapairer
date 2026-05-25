"""
Поиск путей в графе пересечений.

Реализует модифицированный алгоритм Дейкстры для поиска путей
между якорями через β-ребра с ограничениями.
"""
from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Set, Tuple, Dict

if TYPE_CHECKING:
    pass

from .intersection_graph import IntersectionGraph, EdgeType


@dataclass
class PathResult:
    """
    Результат поиска пути.

    Attributes:
        source: Начальная вершина (якорь)
        target: Конечная вершина (якорь)
        path: Список ID вершин пути (от source до target)
        distance: Евклидова длина пути
        weight: Суммарный вес пути
        found: True если путь найден
    """
    source: int
    target: int
    path: List[int]
    distance: float
    weight: float
    found: bool


class PathFinder:
    """
    Поисковик путей в графе пересечений.

    Реализует модифицированный алгоритм Дейкстры с ограничениями
    на длину и вес пути для поиска путей между якорями.
    """

    def __init__(
        self,
        graph: IntersectionGraph,
        max_distance: float = 1.0,
        max_weight: float = 10.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Инициализация.

        Args:
            graph: Граф пересечений
            max_distance: Максимальная евклидова длина пути (d_max)
            max_weight: Максимальный вес пути (w_max)
            logger: Логгер
        """
        self.graph = graph
        self.max_distance = max_distance
        self.max_weight = max_weight
        self.logger = logger or logging.getLogger(__name__)

    def find_paths_between_anchors(self) -> List[PathResult]:
        """
        Найти минимальный набор путей, соединяющих все якоря.

        Использует алгоритм построения минимального остовного дерева (MST)
        на графе якорей. Вместо поиска путей между ВСЕМИ парами (O(n²)),
        находит минимальный набор из n-1 путей для n якорей.

        Returns:
            Список путей, образующих MST якорей
        """
        if not self.graph.anchors:
            self.logger.warning("No anchors found in graph")
            return []

        anchor_list = list(self.graph.anchors)
        n = len(anchor_list)

        if n < 2:
            self.logger.info("Less than 2 anchors, no paths needed")
            return []

        self.logger.info(f"Finding MST paths to connect {n} anchors")

        # 1. Вычисляем кратчайшие пути между всеми парами якорей
        distances_matrix = {}
        paths_matrix = {}

        for i, anchor in enumerate(anchor_list):
            dist, parent = self._dijkstra_distances(anchor)

            for j, target in enumerate(anchor_list):
                if i >= j:  # Избегаем дубликатов и самих себя
                    continue

                if target in dist:
                    distances_matrix[(i, j)] = dist[target]
                    path = self._reconstruct_path(parent, anchor, target)
                    paths_matrix[(i, j)] = (anchor, target, path, dist[target])

        if not distances_matrix:
            self.logger.warning("No paths found between any anchor pairs")
            return []

        # 2. Строим MST с помощью алгоритма Крускала
        edges = [(distances_matrix[(i, j)], i, j)
                 for (i, j) in distances_matrix.keys()]
        edges.sort()  # Сортируем по весу (расстоянию)

        # Union-Find для MST
        parent_uf = list(range(n))

        def find(x):
            if parent_uf[x] != x:
                parent_uf[x] = find(parent_uf[x])
            return parent_uf[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent_uf[px] = py
                return True
            return False

        # 3. Выбираем ребра для MST
        mst_paths = []
        unique_pairs = set()  # Для проверки уникальности пар

        for weight, i, j in edges:
            if union(i, j):
                source, target, path, distance = paths_matrix[(i, j)]

                # Проверяем уникальность пары (source, target)
                pair_key = tuple(sorted([source, target]))
                if pair_key in unique_pairs:
                    self.logger.warning(
                        f"Duplicate path between anchors {source}-{target}, skipping"
                    )
                    continue

                unique_pairs.add(pair_key)

                mst_paths.append(PathResult(
                    source=source,
                    target=target,
                    path=path,
                    distance=distance,
                    weight=distance,
                    found=True
                ))

                if len(mst_paths) == n - 1:  # MST содержит n-1 ребро
                    break

        self.logger.info(
            f"MST: selected {len(mst_paths)} unique paths to connect {n} anchors "
            f"(expected {n-1})"
        )

        # Диагностика: проверяем несвязные компоненты
        if len(mst_paths) < n - 1:
            # Находим несвязные компоненты через Union-Find
            components = {}
            for i in range(n):
                root = find(i)
                if root not in components:
                    components[root] = []
                components[root].append(anchor_list[i])

            self.logger.warning(
                f"Graph has {len(components)} disconnected components! "
                f"Some anchors cannot be connected via β-nodes."
            )
            for comp_id, (root, anchors) in enumerate(components.items(), 1):
                anchor_str = str(anchors[:5]) + "..." if len(anchors) > 5 else str(anchors)
                self.logger.warning(
                    f"  Component {comp_id}: {len(anchors)} anchors - {anchor_str}"
                )

        return mst_paths

    def _dijkstra_distances(self, source: int) -> Tuple[Dict[int, float], Dict[int, Optional[int]]]:
        """
        Модифицированный алгоритм Дейкстры от якоря (возвращает distances и parents).

        Ищет кратчайшие пути от якоря до всех достижимых вершин
        через β-ребра с ограничениями на длину и вес пути.

        Args:
            source: ID якоря-источника

        Returns:
            (distances, parents) - словари расстояний и предков
        """
        # Инициализация
        dist = {source: 0.0}  # d(v) - евклидова длина пути
        weight = {source: 0.0}  # w(v) - суммарный вес пути
        parent = {source: None}  # p(v) - предыдущая вершина в пути
        visited = set()

        # Приоритетная очередь: (distance, node_id)
        pq = [(0.0, source)]

        while pq:
            current_dist, current = heapq.heappop(pq)

            # Пропускаем если уже посетили
            if current in visited:
                continue

            visited.add(current)

            # Обходим только β-ребра
            neighbors = self.graph.get_neighbors(current, edge_type=EdgeType.BETA)

            for neighbor in neighbors:
                if neighbor in visited:
                    continue

                # Получаем ребро и его вес
                edge = self.graph.get_edge(current, neighbor)
                if edge is None:
                    continue

                # Вычисляем новые dist и weight
                new_dist = dist[current] + edge.weight
                new_weight = weight[current] + edge.weight

                # ОГРАНИЧЕНИЯ: проверяем пороги
                if new_dist > self.max_distance:
                    continue
                if new_weight > self.max_weight:
                    continue

                # Обновляем если нашли более короткий путь
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    weight[neighbor] = new_weight
                    parent[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))

        return dist, parent

    def _reconstruct_path(
        self,
        parent: Dict[int, Optional[int]],
        source: int,
        target: int
    ) -> List[int]:
        """
        Восстановить путь из parent map.

        Args:
            parent: Словарь родителей {node_id: parent_id}
            source: Начальная вершина
            target: Конечная вершина

        Returns:
            Список ID вершин пути от source до target
        """
        path = []
        current = target

        while current is not None:
            path.append(current)
            current = parent.get(current)

        path.reverse()
        return path

    def mark_recovered_edges(self, paths: List[PathResult]) -> None:
        """
        Отметить восстановленные ребра в графе.

        Для каждого найденного пути помечает β-ребра как RECOVERED.

        Args:
            paths: Список найденных путей
        """
        recovered_count = 0
        path_details = []  # Для логирования

        for path_result in paths:
            if not path_result.found or len(path_result.path) < 2:
                continue

            path_length = len(path_result.path)
            path_edges = 0

            # Проходим по ребрам пути
            for i in range(len(path_result.path) - 1):
                node1_id = path_result.path[i]
                node2_id = path_result.path[i + 1]

                edge = self.graph.get_edge(node1_id, node2_id)
                if edge and edge.edge_type == EdgeType.BETA:
                    edge.edge_type = EdgeType.RECOVERED
                    recovered_count += 1
                    path_edges += 1

            if path_length > 0:
                path_details.append(
                    f"  {path_result.source}→{path_result.target}: "
                    f"{path_length} nodes, {path_edges} edges"
                )

        self.logger.info(f"Marked {recovered_count} edges as RECOVERED from {len(paths)} paths")
        if path_details and self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Path details:\n" + "\n".join(path_details[:10]))

        # Удаляем неиспользованные β-ребра (которые не стали RECOVERED)
        self._remove_unused_beta_edges()

    def _remove_unused_beta_edges(self) -> None:
        """
        Удалить все β-ребра, которые не были использованы в MST-путях.

        После mark_recovered_edges остаются только ALPHA, BETA и RECOVERED ребра.
        BETA ребра, которые не стали RECOVERED - это неиспользованные альтернативные пути.
        Удаляем их для чистоты графа.
        """
        edges_to_remove = []

        for edge_id, edge in self.graph.edges.items():
            if edge.edge_type == EdgeType.BETA:
                edges_to_remove.append(edge_id)

        if edges_to_remove:
            for edge_id in edges_to_remove:
                self.graph.remove_edge(edge_id)

            self.logger.info(
                f"Removed {len(edges_to_remove)} unused β-edges "
                f"(not part of MST paths)"
            )


__all__ = ['PathFinder', 'PathResult']
