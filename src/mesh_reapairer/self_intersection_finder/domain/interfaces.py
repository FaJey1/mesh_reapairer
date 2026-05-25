"""
Интерфейсы (Protocols) для модуля поиска самопересечений.

Использование Protocol обеспечивает инверсию зависимостей:
domain layer определяет интерфейсы, infrastructure layer их реализует.
"""
from typing import Protocol, List, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh, Face
    from .entities import BVHNode, Primitive, Segment, IntersectionResult
    from .value_objects import AABB, Plane, ClassificationCode


class IBVHBuilder(Protocol):
    """
    Интерфейс для построения BVH дерева.

    Реализации могут использовать разные стратегии (SAH, LBVH, HYBRID).
    """

    def build(self, mesh: 'Mesh') -> 'BVHNode':
        """
        Построить BVH дерево для сетки.

        Args:
            mesh: Треугольная сетка

        Returns:
            Корневой узел BVH дерева
        """
        ...


class IBVHTraverser(Protocol):
    """Интерфейс для обхода BVH дерева."""

    def find_candidates(self, root: 'BVHNode') -> List[Tuple['Face', 'Face']]:
        """
        Обойти BVH дерево и найти пары кандидатов на пересечение.

        Args:
            root: Корневой узел BVH дерева

        Returns:
            Список пар граней (face_a, face_b) - кандидаты на пересечение
        """
        ...


class IPairCache(Protocol):
    """Интерфейс для кэша проверенных пар."""

    def is_checked(self, id1: int, id2: int) -> bool:
        """
        Проверить, была ли пара уже проверена.

        Args:
            id1, id2: ID граней

        Returns:
            True если пара уже проверена
        """
        ...

    def mark_checked(self, id1: int, id2: int) -> None:
        """
        Пометить пару как проверенную.

        Args:
            id1, id2: ID граней
        """
        ...

    def stats(self) -> dict:
        """
        Получить статистику кэша.

        Returns:
            Словарь с метриками (size, hits, misses, hit_rate)
        """
        ...


class IIntersectionClassifier(Protocol):
    """Интерфейс для классификации пересечений граней."""

    def classify_edges_intersection(
        self,
        face_a: 'Face',
        face_b: 'Face'
    ) -> Tuple[Optional['ClassificationCode'], Optional['ClassificationCode'], bool]:
        """
        Классифицировать пересечение двух граней.

        Args:
            face_a: Первая грань
            face_b: Вторая грань

        Returns:
            (codes_ab, codes_ba, is_coplanar)
            codes_ab: Классификация ребер A относительно плоскости B
            codes_ba: Классификация ребер B относительно плоскости A
            is_coplanar: True если грани компланарны
        """
        ...


class ISegmentFinder(Protocol):
    """Интерфейс для поиска сегмента пересечения."""

    def find_intersection_segment(
        self,
        face_a: 'Face',
        face_b: 'Face',
        codes_ab: 'ClassificationCode',
        points_ab: List,
        codes_ba: 'ClassificationCode',
        points_ba: List
    ) -> Optional['Segment']:
        """
        Найти сегмент пересечения двух граней на основе классификации.

        Args:
            face_a, face_b: Грани
            codes_ab, points_ab: Классификация A относительно B
            codes_ba, points_ba: Классификация B относительно A

        Returns:
            Сегмент пересечения или None
        """
        ...


class IParallelPlaneHandler(Protocol):
    """Интерфейс для обработки параллельных и копланарных плоскостей."""

    def should_reject_parallel(self, face_a: 'Face', face_b: 'Face') -> bool:
        """
        Проверить, нужно ли отбросить пару из-за параллельности плоскостей.

        Args:
            face_a, face_b: Грани

        Returns:
            True если пару нужно отбросить
        """
        ...

    def find_coplanar_intersection(
        self,
        face_a: 'Face',
        face_b: 'Face'
    ) -> Optional[List]:
        """
        Найти пересечение копланарных треугольников.

        Args:
            face_a, face_b: Копланарные грани

        Returns:
            Список точек пересечения или None
        """
        ...

    def handle_coincident_faces(
        self,
        face_a: 'Face',
        face_b: 'Face',
        mesh: 'Mesh'
    ) -> None:
        """
        Обработать совпадающие грани (слияние).

        Args:
            face_a, face_b: Совпадающие грани
            mesh: Сетка (для изменения топологии)
        """
        ...
