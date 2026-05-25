"""
Построение BVH (Bounding Volume Hierarchy) дерева с оптимизациями.

Реализует стратегии из научных статей:
- SAH (Surface Area Heuristic) с binning approach
- Early Split Clipping (ESC) с ограничениями
- LBVH (Linear BVH) с Morton codes (опционально)
"""
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from ...application.config import BVHConfig
from ...domain.entities import BVHNode, Primitive
from ...domain.enums import SplitStrategy
from ...domain.value_objects import AABB
from ...utils.geometry import (
    compute_face_aabb,
    compute_primitives_aabb,
    split_aabb,
    face_intersects_aabb
)


@dataclass
class Bin:
    """Bin для SAH разбиения (binning approach)."""
    primitives: List[Primitive]
    bounding_box: Optional[AABB] = None
    count: int = 0

    def add(self, primitive: Primitive):
        """Добавить примитив в bin."""
        self.primitives.append(primitive)
        self.count += 1

        if self.bounding_box is None:
            self.bounding_box = primitive.bounding_box
        else:
            self.bounding_box = self.bounding_box.union(primitive.bounding_box)


class BVHBuilder:
    """
    Построение BVH дерева с оптимизациями.

    Реализует интерфейс IBVHBuilder из domain.interfaces.
    """

    def __init__(self, config: BVHConfig, logger: logging.Logger):
        """
        Инициализация.

        Args:
            config: Конфигурация построения BVH
            logger: Логгер
        """
        self.config = config
        self.logger = logger
        self._next_id = 0  # Счетчик ID узлов
        self._original_surface_areas = {}  # Для ESC: исходные площади граней

    def build(self, mesh) -> BVHNode:
        """
        Построить BVH дерево для сетки.

        Args:
            mesh: Треугольная сетка (msu.Mesh)

        Returns:
            Корневой узел BVH дерева
        """
        self.logger.info(f"Building BVH with strategy={self.config.strategy.name}")

        # 1. Подготовка примитивов
        primitives = self._prepare_primitives(mesh)
        self.logger.info(f"Prepared {len(primitives)} primitives from {len(mesh.faces)} faces")

        # 2. Выбор стратегии построения
        if self.config.strategy == SplitStrategy.SAH:
            root = self._build_sah(primitives)
        elif self.config.strategy == SplitStrategy.LBVH:
            raise NotImplementedError("LBVH strategy not yet implemented")
        elif self.config.strategy == SplitStrategy.HYBRID:
            raise NotImplementedError("HYBRID strategy not yet implemented")
        else:
            raise ValueError(f"Unknown split strategy: {self.config.strategy}")

        # 3. Статистика
        depth = self._compute_depth(root)
        node_count = self._count_nodes(root)
        self.logger.info(f"BVH built: depth={depth}, nodes={node_count}")

        return root

    def _prepare_primitives(self, mesh) -> List[Primitive]:
        """
        Создать примитивы из граней сетки.

        Применяет Early Split Clipping (ESC) если включен в конфигурации.

        Args:
            mesh: Сетка

        Returns:
            Список примитивов
        """
        primitives = []

        for face in mesh.faces:
            # Вычисляем исходный AABB грани
            face_aabb = compute_face_aabb(face)
            self._original_surface_areas[face.glo_id] = face_aabb.surface_area()

            if self.config.enable_early_split_clipping:
                # ESC: разбиение крупных примитивов
                sub_primitives = self._early_split_clipping(
                    face=face,
                    aabb=face_aabb,
                    depth=0
                )
                primitives.extend(sub_primitives)
            else:
                # Один примитив на грань
                primitives.append(Primitive(bounding_box=face_aabb, face=face))

        return primitives

    def _early_split_clipping(
        self,
        face,
        aabb: AABB,
        depth: int
    ) -> List[Primitive]:
        """
        Early Split Clipping (ESC) с ограничениями.

        Рекурсивно разбивает AABB грани до тех пор, пока:
        - Глубина < max_depth
        - Площадь поверхности > min_surface_area
        - Площадь поверхности > threshold% от исходной

        Args:
            face: Грань
            aabb: Текущий AABB
            depth: Текущая глубина рекурсии

        Returns:
            Список примитивов
        """
        original_sa = self._original_surface_areas[face.glo_id]
        current_sa = aabb.surface_area()

        # Условия остановки
        if (depth >= self.config.esc_max_depth or
            current_sa <= self.config.esc_min_surface_area or
            current_sa <= original_sa * self.config.esc_surface_area_threshold):
            return [Primitive(bounding_box=aabb, face=face)]

        # Разбиение по оси максимального расширения
        axis = aabb.max_extent_axis()
        left_aabb, right_aabb = split_aabb(aabb, axis)

        # Проверяем, пересекает ли грань оба подпространства
        result = []

        if face_intersects_aabb(face, left_aabb):
            result.extend(self._early_split_clipping(face, left_aabb, depth + 1))

        if face_intersects_aabb(face, right_aabb):
            result.extend(self._early_split_clipping(face, right_aabb, depth + 1))

        # Если грань не пересекает ни одно подпространство, вернем исходный примитив
        if not result:
            return [Primitive(bounding_box=aabb, face=face)]

        return result

    def _build_sah(self, primitives: List[Primitive]) -> BVHNode:
        """
        Рекурсивное построение BVH с SAH (Surface Area Heuristic).

        Args:
            primitives: Список примитивов для узла

        Returns:
            Узел BVH дерева
        """
        # Условие листа
        if len(primitives) <= self.config.max_primitives_per_leaf:
            return self._create_leaf(primitives)

        # SAH разбиение
        best_axis, left_prims, right_prims = self._find_best_split_sah(primitives)

        # Если разбиение невозможно, создаем лист
        if best_axis is None or not left_prims or not right_prims:
            return self._create_leaf(primitives)

        # Рекурсивное построение дочерних узлов
        left_child = self._build_sah(left_prims)
        right_child = self._build_sah(right_prims)

        # Создание внутреннего узла
        bounding_box = left_child.bounding_box.union(right_child.bounding_box)

        node = BVHNode(
            node_id=self._get_next_id(),
            is_leaf=False,
            bounding_box=bounding_box,
            children=(left_child, right_child),
            primitives=[],
            split_axis=best_axis
        )

        return node

    def _find_best_split_sah(
        self,
        primitives: List[Primitive]
    ) -> Tuple[Optional[int], List[Primitive], List[Primitive]]:
        """
        Найти лучшее разбиение по SAH с binning approach.

        Binning approach значительно быстрее, чем полная сортировка:
        - Сложность: O(n) вместо O(n log n)
        - Разбиваем примитивы на фиксированное количество bins
        - Вычисляем SAH для границ bins

        Args:
            primitives: Примитивы для разбиения

        Returns:
            (best_axis, left_primitives, right_primitives)
            или (None, [], []) если разбиение невозможно
        """
        parent_bounds = compute_primitives_aabb(primitives)
        parent_sa = parent_bounds.surface_area()

        if parent_sa < 1e-15:
            return None, [], []

        best_cost = float('inf')
        best_split = None

        # Перебираем оси
        for axis in range(3):
            # Создаем bins для оси
            bins = self._create_bins(primitives, parent_bounds, axis)

            # Если все примитивы попали в один bin, пропускаем ось
            non_empty_bins = [b for b in bins if b.count > 0]
            if len(non_empty_bins) <= 1:
                continue

            # Вычисляем SAH для каждой границы bin
            for split_index in range(1, self.config.sah_bins):
                left_bins = bins[:split_index]
                right_bins = bins[split_index:]

                # Считаем примитивы в левой и правой частях
                left_count = sum(b.count for b in left_bins)
                right_count = sum(b.count for b in right_bins)

                if left_count == 0 or right_count == 0:
                    continue

                # Объединяем AABB bins
                left_bounds = self._union_bins_aabb(left_bins)
                right_bounds = self._union_bins_aabb(right_bins)

                if left_bounds is None or right_bounds is None:
                    continue

                # SAH cost
                left_sa = left_bounds.surface_area()
                right_sa = right_bounds.surface_area()

                cost = (
                    self.config.sah_traversal_cost +
                    self.config.sah_intersection_cost * (
                        (left_sa / parent_sa) * left_count +
                        (right_sa / parent_sa) * right_count
                    )
                )

                if cost < best_cost:
                    best_cost = cost
                    best_split = (axis, split_index, bins)

        # Если не нашли хорошее разбиение, возвращаем None
        if best_split is None:
            return None, [], []

        axis, split_index, bins = best_split

        # Собираем примитивы из bins
        left_prims = []
        for b in bins[:split_index]:
            left_prims.extend(b.primitives)

        right_prims = []
        for b in bins[split_index:]:
            right_prims.extend(b.primitives)

        return axis, left_prims, right_prims

    def _create_bins(
        self,
        primitives: List[Primitive],
        bounds: AABB,
        axis: int
    ) -> List[Bin]:
        """
        Создать bins для примитивов по указанной оси.

        Args:
            primitives: Примитивы
            bounds: AABB родительского узла
            axis: Ось разбиения

        Returns:
            Список bins
        """
        bins = [Bin(primitives=[]) for _ in range(self.config.sah_bins)]

        min_val = bounds.min_point[axis]
        max_val = bounds.max_point[axis]
        extent = max_val - min_val

        if extent < 1e-15:
            # Все примитивы в одной точке по этой оси
            bins[0].primitives = primitives
            bins[0].count = len(primitives)
            bins[0].bounding_box = compute_primitives_aabb(primitives)
            return bins

        # Распределяем примитивы по bins
        for prim in primitives:
            # Центр примитива
            center = prim.bounding_box.center()[axis]

            # Определяем bin (с защитой от выхода за границы)
            bin_index = int((center - min_val) / extent * self.config.sah_bins)
            bin_index = max(0, min(self.config.sah_bins - 1, bin_index))

            bins[bin_index].add(prim)

        return bins

    def _union_bins_aabb(self, bins: List[Bin]) -> Optional[AABB]:
        """
        Объединить AABB всех bins.

        Args:
            bins: Список bins

        Returns:
            Объединенный AABB или None если все bins пустые
        """
        non_empty = [b for b in bins if b.bounding_box is not None]

        if not non_empty:
            return None

        result = non_empty[0].bounding_box
        for b in non_empty[1:]:
            result = result.union(b.bounding_box)

        return result

    def _create_leaf(self, primitives: List[Primitive]) -> BVHNode:
        """
        Создать лист BVH дерева.

        Args:
            primitives: Примитивы листа

        Returns:
            Узел-лист
        """
        bounding_box = compute_primitives_aabb(primitives)

        return BVHNode(
            node_id=self._get_next_id(),
            is_leaf=True,
            bounding_box=bounding_box,
            children=(None, None),
            primitives=primitives
        )

    def _get_next_id(self) -> int:
        """Получить следующий ID узла."""
        node_id = self._next_id
        self._next_id += 1
        return node_id

    def _compute_depth(self, node: BVHNode) -> int:
        """
        Вычислить глубину дерева.

        Args:
            node: Корневой узел

        Returns:
            Максимальная глубина
        """
        if node.is_leaf:
            return 1

        left_depth = self._compute_depth(node.children[0]) if node.children[0] else 0
        right_depth = self._compute_depth(node.children[1]) if node.children[1] else 0

        return 1 + max(left_depth, right_depth)

    def _count_nodes(self, node: BVHNode) -> int:
        """
        Подсчитать количество узлов в дереве.

        Args:
            node: Корневой узел

        Returns:
            Количество узлов
        """
        if node.is_leaf:
            return 1

        left_count = self._count_nodes(node.children[0]) if node.children[0] else 0
        right_count = self._count_nodes(node.children[1]) if node.children[1] else 0

        return 1 + left_count + right_count
