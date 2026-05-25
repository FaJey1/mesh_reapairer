"""
Обход BVH дерева для поиска кандидатов на пересечение.

Реализует оптимизированный итеративный обход с использованием стека.
"""
import logging
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face

from ...domain.entities import BVHNode


class BVHTraverser:
    """
    Обход BVH дерева для поиска пар кандидатов на пересечение.

    Реализует интерфейс IBVHTraverser из domain.interfaces.
    """

    def __init__(self, pair_cache, adjacency_cache, logger: logging.Logger):
        """
        Инициализация.

        Args:
            pair_cache: Кэш проверенных пар (IPairCache)
            adjacency_cache: Кэш смежности граней (AdjacencyCache)
            logger: Логгер
        """
        self.pair_cache = pair_cache
        self.adjacency_cache = adjacency_cache
        self.logger = logger
        self._neighbors_filtered = 0

    def find_candidates(self, root: BVHNode) -> List[Tuple['Face', 'Face']]:
        """
        Обойти BVH дерево и найти пары кандидатов на пересечение.

        Использует итеративный обход с стеком для проверки
        самопересечений (каждый узел с самим собой и потомками).

        Args:
            root: Корневой узел BVH дерева

        Returns:
            Список пар граней (face_a, face_b) - кандидаты на пересечение
        """
        candidates = []
        stack = [(root, root)]  # Стек пар узлов для проверки
        nodes_visited = 0
        aabb_tests = 0
        aabb_hits = 0
        self._neighbors_filtered = 0  # Сбросить счетчик

        self.logger.debug("Starting BVH traversal")

        while stack:
            node1, node2 = stack.pop()
            nodes_visited += 1

            # AABB тест: проверяем пересечение ограничивающих параллелепипедов
            aabb_tests += 1
            if not node1.bounding_box.intersects(node2.bounding_box):
                continue

            aabb_hits += 1

            # Оба узла - листья: проверяем примитивы
            if node1.is_leaf and node2.is_leaf:
                self._check_leaf_pairs(node1, node2, candidates)
                continue

            # Раскрываем узлы: один или оба внутренние
            self._expand_nodes(node1, node2, stack)

        # Логируем статистику
        self.logger.info(
            f"Traversal complete: visited={nodes_visited}, "
            f"aabb_tests={aabb_tests}, aabb_hits={aabb_hits}, "
            f"neighbors_filtered={self._neighbors_filtered}, "
            f"candidates={len(candidates)}"
        )

        cache_stats = self.pair_cache.stats()
        self.logger.info(
            f"Cache: size={cache_stats['size']}, "
            f"hits={cache_stats['hits']}, "
            f"misses={cache_stats['misses']}, "
            f"hit_rate={cache_stats['hit_rate']:.1%}"
        )

        return candidates

    def _check_leaf_pairs(
        self,
        node1: BVHNode,
        node2: BVHNode,
        candidates: List[Tuple['Face', 'Face']]
    ) -> None:
        """
        Проверить пары примитивов в двух листьях.

        Фильтрация:
        1. Пропуск грани с самой собой
        2. Пропуск соседей (adjacency cache) - РАННЯЯ ФИЛЬТРАЦИЯ
        3. Кэш проверенных пар
        4. AABB тест примитивов

        Args:
            node1, node2: Листья BVH
            candidates: Список кандидатов (изменяется на месте)
        """
        for prim1 in node1.primitives:
            for prim2 in node2.primitives:
                # 1. Не проверяем грань с самой собой
                if prim1.face.glo_id == prim2.face.glo_id:
                    continue

                # 2. ОПТИМИЗАЦИЯ: Пропускаем соседей (общее ребро)
                # Проверяем РАНЬШЕ всех остальных проверок
                if self.adjacency_cache.are_neighbors(prim1.face.glo_id, prim2.face.glo_id):
                    self._neighbors_filtered += 1
                    continue

                # 3. Кэш: проверяем, была ли пара уже проверена
                # ОПТИМИЗАЦИЯ: избегаем дубликатов
                if self.pair_cache.is_checked(prim1.face.glo_id, prim2.face.glo_id):
                    continue

                # Помечаем пару как проверенную
                self.pair_cache.mark_checked(prim1.face.glo_id, prim2.face.glo_id)

                # 4. AABB тест примитивов (более точный, чем узлов)
                if not prim1.bounding_box.intersects(prim2.bounding_box):
                    continue

                # Добавляем в кандидаты
                candidates.append((prim1.face, prim2.face))

    def _expand_nodes(
        self,
        node1: BVHNode,
        node2: BVHNode,
        stack: List[Tuple[BVHNode, BVHNode]]
    ) -> None:
        """
        Раскрыть узлы и добавить дочерние пары в стек.

        Стратегия:
        - Если оба внутренние: добавляем все комбинации детей (4 пары)
        - Если один лист, другой внутренний: раскрываем внутренний

        Args:
            node1, node2: Узлы для раскрытия
            stack: Стек (изменяется на месте)
        """
        # Оба внутренние узлы
        if not node1.is_leaf and not node2.is_leaf:
            left1, right1 = node1.children
            left2, right2 = node2.children

            # Добавляем все комбинации (избегая дубликатов для симметричных пар)
            if node1.node_id == node2.node_id:
                # Самопересечение: (L, L), (L, R), (R, R)
                stack.append((left1, left1))
                stack.append((left1, right1))
                stack.append((right1, right1))
            else:
                # Разные узлы: все 4 комбинации
                stack.append((left1, left2))
                stack.append((left1, right2))
                stack.append((right1, left2))
                stack.append((right1, right2))

        # node1 лист, node2 внутренний
        elif node1.is_leaf and not node2.is_leaf:
            left2, right2 = node2.children
            stack.append((node1, left2))
            stack.append((node1, right2))

        # node1 внутренний, node2 лист
        elif not node1.is_leaf and node2.is_leaf:
            left1, right1 = node1.children
            stack.append((left1, node2))
            stack.append((right1, node2))

        # Оба листья - не должно попасть сюда (обрабатывается в _check_leaf_pairs)
        else:
            self.logger.warning("Unexpected: both nodes are leaves in _expand_nodes")
