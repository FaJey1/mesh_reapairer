"""
Классификация пересечений треугольников.

Реализует метод Skorkovska et al. (article_2.md) для классификации
пересечений ребер треугольника с плоскостью.
"""
import logging
from typing import Tuple, List, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Edge, Node

from ...application.config import IntersectionConfig
from ...domain.value_objects import Plane, ClassificationCode
from ...utils.geometry import face_to_plane, are_faces_coplanar


class IntersectionClassifier:
    """
    Классификация пересечений треугольников по методу Skorkovska et al.

    Реализует интерфейс IIntersectionClassifier из domain.interfaces.
    """

    def __init__(self, config: IntersectionConfig, logger: logging.Logger):
        """
        Инициализация.

        Args:
            config: Конфигурация поиска пересечений
            logger: Логгер
        """
        self.config = config
        self.eps = config.epsilon  # Точность вычислений из единой конфигурации
        self.logger = logger

        # Невозможные комбинации кодов (из статьи Skorkovska)
        self.impossible_cases = [
            [0, 0, 1], [0, 0, 2], [0, 1, 2], [1, 2, 2], [2, 2, 2]
        ]

        # Спец случай: нет пересечений
        self.special_cases = [[0, 0, 0]]

    def classify_edges_intersection(
        self,
        face_a: 'Face',
        face_b: 'Face'
    ) -> Tuple[Optional[ClassificationCode], Optional[ClassificationCode], bool]:
        """
        Классифицировать пересечение двух граней.

        Args:
            face_a: Первая грань
            face_b: Вторая грань

        Returns:
            (codes_ab, codes_ba, is_coplanar)
            - codes_ab: Классификация ребер A относительно плоскости B
            - codes_ba: Классификация ребер B относительно плоскости A
            - is_coplanar: True если грани компланарны
        """
        # Плоскости граней
        plane_a = face_to_plane(face_a)
        plane_b = face_to_plane(face_b)

        # Проверка компланарности
        if are_faces_coplanar(face_a, face_b, self.eps):
            self.logger.debug(
                f"Faces {face_a.glo_id} and {face_b.glo_id} are coplanar"
            )
            return None, None, True

        # Классифицируем рёбра A относительно плоскости B
        codes_ab, points_ab = self._classify_face_plane(face_a, plane_b)

        # Классифицируем рёбра B относительно плоскости A
        codes_ba, points_ba = self._classify_face_plane(face_b, plane_a)

        # Исправление vertex cases (граничные случаи с вершинами)
        codes_ab, points_ab = self._fix_vertex_case(face_a, codes_ab, points_ab)
        codes_ba, points_ba = self._fix_vertex_case(face_b, codes_ba, points_ba)

        # Создаем ClassificationCode объекты
        classification_ab = ClassificationCode(codes=tuple(codes_ab), points=tuple(points_ab))
        classification_ba = ClassificationCode(codes=tuple(codes_ba), points=tuple(points_ba))

        return classification_ab, classification_ba, False

    def _classify_face_plane(
        self,
        face: 'Face',
        plane: Plane
    ) -> Tuple[List[int], List[Optional['Node']]]:
        """
        Классифицировать три ребра грани относительно плоскости.

        Args:
            face: Грань (треугольник)
            plane: Плоскость

        Returns:
            (codes, points)
            - codes: Список из 3 кодов (по одному на ребро)
            - points: Список из 3 точек пересечения (может содержать None)
        """
        codes = []
        points = []

        for edge in face.edges:
            code, point = self._edge_plane_class(edge, plane)
            codes.append(code)
            points.append(point)

        return codes, points

    def _edge_plane_class(
        self,
        edge: 'Edge',
        plane: Plane
    ) -> Tuple[int, Optional['Node']]:
        """
        Классифицировать пересечение ребра с плоскостью.

        Коды классификации (из Skorkovska et al.):
        - 0: точка пересечения вне ребра (компланарное или не пересекает)
        - 1: точка пересечения в вершине ребра
        - 2: точка пересечения внутри ребра

        Args:
            edge: Ребро
            plane: Плоскость

        Returns:
            (code, intersection_point)
        """
        from mesh_reapairer.src.mesh_reapairer.msu.mesh import Node  # Локальный импорт для избежания циклических зависимостей

        p0, p1 = edge.points()

        # Подписанные расстояния до плоскости
        d0 = plane.signed_distance(p0)
        d1 = plane.signed_distance(p1)

        # Оба конца на плоскости - компланарное ребро
        if abs(d0) < self.eps and abs(d1) < self.eps:
            return 0, None

        # По одну сторону от плоскости - нет пересечения
        if d0 * d1 > 0.0:
            return 0, None

        # Вычисляем параметр пересечения t ∈ [0, 1]
        # Точка пересечения: p = p0 + t * (p1 - p0)
        t = d0 / (d0 - d1)

        # Определяем тип пересечения
        if abs(t) < self.eps:
            # Пересечение в начале ребра (вершина p0)
            return 1, Node(p0)
        elif abs(t - 1.0) < self.eps:
            # Пересечение в конце ребра (вершина p1)
            return 1, Node(p1)
        else:
            # Пересечение внутри ребра
            intersection = p0 + t * (p1 - p0)
            return 2, Node(intersection)

    def _fix_vertex_case(
        self,
        face: 'Face',
        codes: List[int],
        points: List[Optional['Node']]
    ) -> Tuple[List[int], List[Optional['Node']]]:
        """
        Исправить граничные случаи с вершинами.

        Если две точки пересечения находятся в одной вершине,
        одну из них нужно убрать (заменить код на 0).

        Args:
            face: Грань
            codes: Коды классификации
            points: Точки пересечения

        Returns:
            (fixed_codes, fixed_points)
        """
        codes = codes.copy()
        points = points.copy()

        # Ищем повторяющиеся вершины
        for i in range(3):
            if codes[i] != 1 or points[i] is None:
                continue

            for j in range(i + 1, 3):
                if codes[j] != 1 or points[j] is None:
                    continue

                # Проверяем, совпадают ли точки
                dist = np.linalg.norm(points[i].p - points[j].p)
                if dist < self.eps:
                    # Заменяем вторую на 0 (убираем дубликат)
                    codes[j] = 0
                    points[j] = None

        return codes, points
