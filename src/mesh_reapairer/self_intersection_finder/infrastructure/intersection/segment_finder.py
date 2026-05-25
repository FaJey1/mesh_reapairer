"""
Поиск сегмента пересечения двух треугольников.

На основе классификационных кодов определяет общий сегмент пересечения.
"""
import logging
from typing import Optional, List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Node

from ...application.config import IntersectionConfig
from ...domain.entities import Segment
from ...domain.value_objects import ClassificationCode


class SegmentFinder:
    """
    Поиск сегмента пересечения двух треугольников.

    Реализует интерфейс ISegmentFinder из domain.interfaces.
    """

    def __init__(self, config: IntersectionConfig, logger: logging.Logger):
        """
        Инициализация.

        Args:
            config: Конфигурация поиска пересечений
            logger: Логгер
        """
        self.config = config
        self.eps = config.epsilon
        self.logger = logger

    def find_intersection_segment(
        self,
        face_a: 'Face',
        face_b: 'Face',
        codes_ab: ClassificationCode,
        points_ab: List[Optional['Node']],
        codes_ba: ClassificationCode,
        points_ba: List[Optional['Node']]
    ) -> Optional[Segment]:
        """
        Найти сегмент пересечения двух граней.

        Args:
            face_a, face_b: Грани
            codes_ab: Классификация A относительно B
            points_ab: Точки пересечения A с плоскостью B
            codes_ba: Классификация B относительно A
            points_ba: Точки пересечения B с плоскостью A

        Returns:
            Сегмент пересечения или None
        """
        # Находим точки пересечения для обеих граней
        intersection_nodes_ab = [p for p in points_ab if p is not None]
        intersection_nodes_ba = [p for p in points_ba if p is not None]

        # Должно быть ровно 2 точки на каждой грани для валидного пересечения
        if len(intersection_nodes_ab) != 2 or len(intersection_nodes_ba) != 2:
            return None

        # Находим общий сегмент (пересечение двух отрезков на линии пересечения плоскостей)
        common_segment = self._find_common_segment_1d(
            intersection_nodes_ab,
            intersection_nodes_ba
        )

        if common_segment is None or len(common_segment) < 2:
            return None

        # Создаем объект Segment
        segment = Segment(
            nodes=common_segment,
            face_a=face_a,
            face_b=face_b,
            face_a_classificator=[codes_ab.codes, points_ab],
            face_b_classificator=[codes_ba.codes, points_ba]
        )

        return segment

    def _find_common_segment_1d(
        self,
        segment_a: List['Node'],
        segment_b: List['Node']
    ) -> Optional[List['Node']]:
        """
        Найти общий сегмент двух отрезков на линии пересечения плоскостей.

        Проецируем оба отрезка на линию пересечения и находим их пересечение.

        Args:
            segment_a: Два узла первого отрезка
            segment_b: Два узла второго отрезка

        Returns:
            Список узлов общего сегмента (может быть пустым) или None
        """
        # Получаем координаты точек
        p0_a, p1_a = segment_a[0].p, segment_a[1].p
        p0_b, p1_b = segment_b[0].p, segment_b[1].p

        # Направление линии пересечения (векторное произведение нормалей плоскостей)
        # Упрощение: используем вектор между точками первого отрезка
        direction = p1_a - p0_a
        direction_norm = np.linalg.norm(direction)

        if direction_norm < self.eps:
            return None

        direction = direction / direction_norm

        # Проецируем все точки на направление
        t0_a = 0.0  # p0_a проецируется в 0 (базис)
        t1_a = np.dot(p1_a - p0_a, direction)

        t0_b = np.dot(p0_b - p0_a, direction)
        t1_b = np.dot(p1_b - p0_a, direction)

        # Нормализуем: t0 < t1 для обоих отрезков
        if t0_a > t1_a:
            t0_a, t1_a = t1_a, t0_a
            p0_a, p1_a = p1_a, p0_a

        if t0_b > t1_b:
            t0_b, t1_b = t1_b, t0_b
            p0_b, p1_b = p1_b, p0_b

        # Находим пересечение интервалов [t0_a, t1_a] и [t0_b, t1_b]
        t_start = max(t0_a, t0_b)
        t_end = min(t1_a, t1_b)

        # Если интервалы не пересекаются
        if t_start > t_end + self.eps:
            return None

        # Восстанавливаем 3D точки
        from mesh_reapairer.src.mesh_reapairer.msu.mesh import Node

        start_point = p0_a + t_start * direction
        end_point = p0_a + t_end * direction

        # Проверяем, что точки не совпадают
        if np.linalg.norm(end_point - start_point) < self.eps:
            return None

        return [Node(start_point), Node(end_point)]
