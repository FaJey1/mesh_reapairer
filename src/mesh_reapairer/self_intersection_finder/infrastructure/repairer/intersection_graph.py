"""
Граф пересечений сеток.

Реализует структуры данных для представления графа I(M,W) и его расширения J(M,W)
согласно алгоритму из article_7.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, List, Set, Tuple, Optional
import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import Segment


class EdgeType(Enum):
    """
    Тип ребра в графе пересечений.

    α-ребра (ALPHA): соединяют валидные пары с найденными сегментами
    β-ребра (BETA): соединяют пары с общим элементом (для восстановления)
    """
    ALPHA = "alpha"  # Валидное ребро (есть сегмент)
    BETA = "beta"    # Потенциальное ребро (для восстановления)
    RECOVERED = "recovered"  # Восстановленное ребро


@dataclass
class GraphNode:
    """
    Вершина графа пересечений.

    Представляет пару пересекающихся ячеек (face_m, face_w).

    Attributes:
        face_a: Ячейка из первой сетки
        face_b: Ячейка из второй сетки (в нашем случае самопересечение - та же сетка)
        segment: Сегмент пересечения (None для impossible пар)
        point: Опорная точка вершины (середина отрезка между центрами ячеек)
        node_id: Уникальный ID вершины
        is_anchor: True если вершина является якорем (одно α-ребро)
    """
    face_a: Face
    face_b: Face
    segment: Optional[Segment] = None
    point: Optional[np.ndarray] = None
    node_id: Optional[int] = None
    is_anchor: bool = False

    def __post_init__(self):
        """Вычислить опорную точку если не задана."""
        if self.point is None:
            center_a = self.face_a.center()
            center_b = self.face_b.center()
            self.point = (center_a + center_b) / 2.0

    def __hash__(self):
        """Хеш для использования в set/dict."""
        # Используем отсортированную пару ID для симметричности
        return hash((min(self.face_a.glo_id, self.face_b.glo_id),
                     max(self.face_a.glo_id, self.face_b.glo_id)))

    def __eq__(self, other):
        """Сравнение вершин."""
        if not isinstance(other, GraphNode):
            return False
        return (
            {self.face_a.glo_id, self.face_b.glo_id} ==
            {other.face_a.glo_id, other.face_b.glo_id}
        )

    def has_common_face(self, other: GraphNode) -> bool:
        """
        Проверить, есть ли общая ячейка с другой вершиной.

        Args:
            other: Другая вершина

        Returns:
            True если есть общая ячейка
        """
        self_faces = {self.face_a.glo_id, self.face_b.glo_id}
        other_faces = {other.face_a.glo_id, other.face_b.glo_id}
        return bool(self_faces & other_faces)


@dataclass
class GraphEdge:
    """
    Ребро графа пересечений.

    Attributes:
        node1: Первая вершина
        node2: Вторая вершина
        edge_type: Тип ребра (ALPHA, BETA, RECOVERED)
        weight: Вес ребра (евклидово расстояние между опорными точками)
    """
    node1: GraphNode
    node2: GraphNode
    edge_type: EdgeType = EdgeType.BETA
    weight: float = 0.0

    def __post_init__(self):
        """Вычислить вес если не задан."""
        if self.weight == 0.0:
            self.weight = np.linalg.norm(self.node1.point - self.node2.point)

    def __hash__(self):
        """Хеш для использования в set/dict."""
        # Симметричный хеш
        return hash((min(hash(self.node1), hash(self.node2)),
                     max(hash(self.node1), hash(self.node2))))

    def __eq__(self, other):
        """Сравнение ребер."""
        if not isinstance(other, GraphEdge):
            return False
        return (
            (self.node1 == other.node1 and self.node2 == other.node2) or
            (self.node1 == other.node2 and self.node2 == other.node1)
        )


class IntersectionGraph:
    """
    Граф пересечений I(M,W) и его расширение J(M,W).

    Граф I: валидные пары с α-ребрами
    Граф J: I + impossible пары с β-ребрами

    Attributes:
        nodes: Словарь вершин {node_id: GraphNode}
        edges: Словарь ребер {(node_id1, node_id2): GraphEdge}
        adjacency: Списки смежности {node_id: [neighbor_ids]}
        anchors: Множество ID якорей
    """

    def __init__(self):
        """Инициализация пустого графа."""
        self.nodes: dict[int, GraphNode] = {}
        self.edges: dict[tuple[int, int], GraphEdge] = {}
        self.adjacency: dict[int, list[int]] = {}
        self.anchors: Set[int] = set()
        self._next_node_id = 0

    def add_node(self, node: GraphNode) -> int:
        """
        Добавить вершину в граф.

        Args:
            node: Вершина для добавления

        Returns:
            ID добавленной вершины
        """
        if node.node_id is None:
            node.node_id = self._next_node_id
            self._next_node_id += 1

        self.nodes[node.node_id] = node
        if node.node_id not in self.adjacency:
            self.adjacency[node.node_id] = []

        return node.node_id

    def add_edge(self, edge: GraphEdge) -> None:
        """
        Добавить ребро в граф.

        Args:
            edge: Ребро для добавления
        """
        node1_id = edge.node1.node_id
        node2_id = edge.node2.node_id

        if node1_id is None or node2_id is None:
            raise ValueError("Nodes must be added to graph before edges")

        # Симметричный ключ
        key = (min(node1_id, node2_id), max(node1_id, node2_id))
        self.edges[key] = edge

        # Обновляем списки смежности
        if node2_id not in self.adjacency[node1_id]:
            self.adjacency[node1_id].append(node2_id)
        if node1_id not in self.adjacency[node2_id]:
            self.adjacency[node2_id].append(node1_id)

    def get_edge(self, node1_id: int, node2_id: int) -> Optional[GraphEdge]:
        """
        Получить ребро между двумя вершинами.

        Args:
            node1_id, node2_id: ID вершин

        Returns:
            Ребро или None если нет ребра
        """
        key = (min(node1_id, node2_id), max(node1_id, node2_id))
        return self.edges.get(key)

    def remove_edge(self, edge_id: Tuple[int, int]) -> None:
        """
        Удалить ребро из графа.

        Args:
            edge_id: Ключ ребра (min_node_id, max_node_id)
        """
        if edge_id not in self.edges:
            return

        edge = self.edges[edge_id]
        node1_id = edge.node1.node_id
        node2_id = edge.node2.node_id

        # Удаляем из словаря ребер
        del self.edges[edge_id]

        # Удаляем из списков смежности
        if node2_id in self.adjacency[node1_id]:
            self.adjacency[node1_id].remove(node2_id)
        if node1_id in self.adjacency[node2_id]:
            self.adjacency[node2_id].remove(node1_id)

    def update_node_edge_types(self, node_id: int) -> int:
        """
        Обновить типы ребер, инцидентных узлу, после восстановления его сегмента.

        Если node.segment установлен (восстановлен), то β-ребра к соседним
        α-узлам должны стать α-ребрами.

        Args:
            node_id: ID узла

        Returns:
            Количество обновленных ребер
        """
        node = self.nodes.get(node_id)
        if not node or not node.segment:
            return 0

        updated_count = 0
        neighbors = self.adjacency.get(node_id, [])

        for neighbor_id in neighbors:
            neighbor = self.nodes.get(neighbor_id)
            if not neighbor:
                continue

            edge = self.get_edge(node_id, neighbor_id)
            if not edge:
                continue

            # Если оба узла имеют segment (α-узлы), ребро должно быть α-типа
            if node.segment and neighbor.segment:
                if edge.edge_type in (EdgeType.BETA, EdgeType.RECOVERED):
                    edge.edge_type = EdgeType.ALPHA
                    updated_count += 1

        return updated_count

    def update_all_edge_types(self) -> int:
        """
        Пересчитать типы ВСЕХ ребер в графе на основе node.segment.

        Если оба узла ребра имеют segment (восстановлены или были α-узлами),
        то ребро должно быть α-типа.

        Returns:
            Количество обновленных ребер
        """
        updated_count = 0

        for edge in self.edges.values():
            node1 = edge.node1
            node2 = edge.node2

            # Если оба узла имеют segment, ребро должно быть ALPHA
            if node1.segment and node2.segment:
                if edge.edge_type in (EdgeType.BETA, EdgeType.RECOVERED):
                    edge.edge_type = EdgeType.ALPHA
                    updated_count += 1

        return updated_count

    def find_anchors(self) -> Set[int]:
        """
        Найти якоря в графе.

        Якорь - вершина с ровно одним α-ребром.

        Returns:
            Множество ID якорей
        """
        self.anchors.clear()

        for node_id, node in self.nodes.items():
            # Считаем α-ребра для этой вершины
            alpha_count = 0
            for neighbor_id in self.adjacency.get(node_id, []):
                edge = self.get_edge(node_id, neighbor_id)
                if edge and edge.edge_type == EdgeType.ALPHA:
                    alpha_count += 1

            # Якорь = одно α-ребро
            if alpha_count == 1:
                self.anchors.add(node_id)
                node.is_anchor = True

        return self.anchors

    def get_neighbors(self, node_id: int, edge_type: Optional[EdgeType] = None) -> List[int]:
        """
        Получить соседей вершины.

        Args:
            node_id: ID вершины
            edge_type: Фильтр по типу ребра (None = все)

        Returns:
            Список ID соседних вершин
        """
        neighbors = []
        for neighbor_id in self.adjacency.get(node_id, []):
            edge = self.get_edge(node_id, neighbor_id)
            if edge is None:
                continue

            if edge_type is None or edge.edge_type == edge_type:
                neighbors.append(neighbor_id)

        return neighbors

    def degree(self, node_id: int, edge_type: Optional[EdgeType] = None) -> int:
        """
        Степень вершины (количество ребер).

        Args:
            node_id: ID вершины
            edge_type: Фильтр по типу ребра (None = все типы)

        Returns:
            Количество ребер
        """
        if edge_type is None:
            return len(self.adjacency.get(node_id, []))

        count = 0
        for neighbor_id in self.adjacency.get(node_id, []):
            edge = self.get_edge(node_id, neighbor_id)
            if edge and edge.edge_type == edge_type:
                count += 1
        return count

    def find_connected_components(self) -> List[Set[int]]:
        """
        Найти связные компоненты графа.

        Использует итеративный DFS вместо рекурсивного,
        чтобы избежать переполнения стека на больших графах.

        Returns:
            Список множеств ID вершин в каждой компоненте
        """
        visited = set()
        components = []

        for start_node_id in self.nodes:
            if start_node_id in visited:
                continue

            # Итеративный DFS с использованием стека
            component = set()
            stack = [start_node_id]

            while stack:
                node_id = stack.pop()

                if node_id in visited:
                    continue

                visited.add(node_id)
                component.add(node_id)

                # Добавляем всех непосещенных соседей в стек
                for neighbor_id in self.adjacency.get(node_id, []):
                    if neighbor_id not in visited:
                        stack.append(neighbor_id)

            components.append(component)

        # Сортируем по размеру (убывание)
        components.sort(key=len, reverse=True)
        return components

    def remove_node(self, node_id: int) -> None:
        """
        Удалить вершину из графа.

        Args:
            node_id: ID вершины для удаления
        """
        if node_id not in self.nodes:
            return

        # Удаляем все ребра с этой вершиной
        neighbors = list(self.adjacency.get(node_id, []))
        for neighbor_id in neighbors:
            key = (min(node_id, neighbor_id), max(node_id, neighbor_id))
            if key in self.edges:
                del self.edges[key]

            # Убираем из списка смежности соседа
            if node_id in self.adjacency.get(neighbor_id, []):
                self.adjacency[neighbor_id].remove(node_id)

        # Удаляем вершину
        del self.nodes[node_id]
        if node_id in self.adjacency:
            del self.adjacency[node_id]
        if node_id in self.anchors:
            self.anchors.remove(node_id)

    def stats(self) -> dict:
        """
        Статистика графа.

        Returns:
            Словарь со статистикой
        """
        alpha_edges = sum(1 for e in self.edges.values() if e.edge_type == EdgeType.ALPHA)
        beta_edges = sum(1 for e in self.edges.values() if e.edge_type == EdgeType.BETA)
        recovered_edges = sum(1 for e in self.edges.values() if e.edge_type == EdgeType.RECOVERED)

        return {
            'nodes': len(self.nodes),
            'edges': len(self.edges),
            'alpha_edges': alpha_edges,
            'beta_edges': beta_edges,
            'recovered_edges': recovered_edges,
            'anchors': len(self.anchors),
        }


__all__ = ['IntersectionGraph', 'GraphNode', 'GraphEdge', 'EdgeType']
