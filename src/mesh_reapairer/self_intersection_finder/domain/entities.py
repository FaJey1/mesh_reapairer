"""
Сущности для модуля поиска самопересечений.

Entities - это объекты с идентичностью и жизненным циклом.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Set, TYPE_CHECKING

from .value_objects import AABB

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Node

# Для избежания цикличных импортов, используем forward references
# Face и Node импортируются только для type hints


@dataclass
class BVHNode:
    """
    Узел BVH дерева.

    Attributes:
        node_id: Уникальный ID узла
        is_leaf: Флаг листа (True если узел не имеет детей)
        bounding_box: AABB узла (ограничивающий параллелепипед)
        children: Пара дочерних узлов (None, None) для листа
        primitives: Список примитивов в листе (пуст для внутренних узлов)
        split_axis: Ось разбиения (0=x, 1=y, 2=z), None для листа
    """
    node_id: int
    is_leaf: bool
    bounding_box: AABB
    children: Tuple[Optional['BVHNode'], Optional['BVHNode']]
    primitives: List['Primitive']
    split_axis: Optional[int] = None

    def __post_init__(self):
        """Валидация после инициализации."""
        if self.is_leaf:
            # Лист должен иметь примитивы и не иметь детей
            if not self.primitives:
                raise ValueError("Leaf node must have primitives")
            if any(self.children):
                raise ValueError("Leaf node cannot have children")
        else:
            # Внутренний узел должен иметь детей и не иметь примитивов
            if self.primitives:
                raise ValueError("Internal node cannot have primitives")
            if not all(self.children):
                raise ValueError("Internal node must have both children")
            if self.split_axis not in (0, 1, 2):
                raise ValueError("split_axis must be 0, 1, or 2")


@dataclass
class Primitive:
    """
    Примитив (треугольник с AABB).

    Примитив - это элементарный объект в BVH дереве.
    В нашем случае это треугольник (Face) с его ограничивающим параллелепипедом.

    Attributes:
        bounding_box: AABB примитива
        face: Грань сетки (треугольник)
        morton_code: Morton code для LBVH (опционально)
    """
    bounding_box: AABB
    face: 'Face'  # Forward reference
    morton_code: Optional[int] = None


@dataclass
class Segment:
    """
    Сегмент пересечения двух треугольников.

    Attributes:
        nodes: Список узлов (точек) сегмента (обычно 2 точки)
        face_a: Первая грань
        face_b: Вторая грань
        face_a_classificator: Классификация граней A относительно плоскости B
        face_b_classificator: Классификация граней B относительно плоскости A
    """
    nodes: Optional[List['Node']] = None
    face_a: Optional['Face'] = None
    face_b: Optional['Face'] = None
    face_a_classificator: Optional[List] = None
    face_b_classificator: Optional[List] = None


@dataclass
class IntersectionResult:
    """
    Результат поиска самопересечений в сетке.

    Содержит все найденные пересечения, статистику и метрики производительности.

    Attributes:
        valid_pairs: Список корректных пересечений (face_a, face_b, segment)
        impossible_pairs: Список пар с невозможной классификацией (численные ошибки)
        parallel_rejected: Список пар, отброшенных из-за параллельности плоскостей
        trivial_filtered: Список пар с тривиальными пересечениями (только в общих вершинах)
        face_intersections: Словарь face.glo_id -> список сегментов
        total_candidates: Общее количество кандидатов на пересечение
        checked_pairs: Количество проверенных пар
        cache_hits: Количество попаданий в кэш
        build_time_ms: Время построения BVH (миллисекунды)
        traversal_time_ms: Время обхода дерева (миллисекунды)
        classification_time_ms: Время классификации пересечений (миллисекунды)
        repair_intersection_time_ms: Время восстановления пересечений (миллисекунды)
    """
    valid_pairs: List[Tuple['Face', 'Face', Segment]] = field(default_factory=list)
    impossible_pairs: List[Tuple['Face', 'Face']] = field(default_factory=list)
    parallel_rejected: List[Tuple['Face', 'Face']] = field(default_factory=list)
    trivial_filtered: List[Tuple['Face', 'Face']] = field(default_factory=list)
    face_intersections: Dict[int, List[Segment]] = field(default_factory=dict)

    # f_fix: ячейки требующие триангуляции {face_id: (face, [segments])}
    f_fix: Dict[int, Tuple['Face', List[Segment]]] = field(default_factory=dict)

    # Снапшоты графа пересечения (до и после восстановления) для визуализации
    intersection_graph_before: Optional[Any] = None
    intersection_graph_after: Optional[Any] = None

    # Статистика
    total_candidates: int = 0
    checked_pairs: int = 0
    cache_hits: int = 0

    # Производительность
    build_time_ms: float = 0.0
    traversal_time_ms: float = 0.0
    classification_time_ms: float = 0.0
    repair_intersection_time_ms: float = 0.0

    def total_time_ms(self) -> float:
        """Полное время выполнения."""
        return self.build_time_ms + self.traversal_time_ms + self.classification_time_ms + self.repair_intersection_time_ms

    def cache_hit_rate(self) -> float:
        """Процент попаданий в кэш."""
        if self.checked_pairs == 0:
            return 0.0
        return self.cache_hits / self.checked_pairs

    def summary(self) -> str:
        """
        Получить текстовое резюме результатов.

        Returns:
            Многострочная строка с итогами
        """
        return f"""
=== Self-Intersection Search Results ===
Valid intersections: {len(self.valid_pairs)}
Impossible pairs: {len(self.impossible_pairs)}
Parallel rejected: {len(self.parallel_rejected)}
Trivial filtered: {len(self.trivial_filtered)}
Total candidates: {self.total_candidates}
Checked pairs: {self.checked_pairs}
Cache hits: {self.cache_hits} ({self.cache_hit_rate():.1%})

=== Performance ===
Build time: {self.build_time_ms:.2f}ms
Traversal time: {self.traversal_time_ms:.2f}ms
Classification time: {self.classification_time_ms:.2f}ms
Repair intersection time: {self.repair_intersection_time_ms:.2f}ms
Total time: {self.total_time_ms():.2f}ms
""".strip()
