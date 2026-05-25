"""
Обработка параллельных и копланарных плоскостей.

Специальные случаи:
- Параллельные плоскости с большим расстоянием - отброс
- Копланарные треугольники - поиск пересечения на плоскости
- Совпадающие грани - слияние
"""
import logging
from typing import Optional, List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Mesh, Node

from ...application.config import IntersectionConfig
from ...utils.geometry import (
    face_to_plane,
    are_faces_coincident,
    project_point_to_2d,
    point_in_triangle_2d
)


class ParallelPlaneHandler:
    """
    Обработка параллельных и копланарных плоскостей.

    Реализует интерфейс IParallelPlaneHandler из domain.interfaces.
    """

    def __init__(self, config: IntersectionConfig, logger: logging.Logger):
        """
        Инициализация.

        Args:
            config: Конфигурация поиска пересечений
            logger: Логгер
        """
        self.config = config
        self.logger = logger

    def should_reject_parallel(self, face_a: 'Face', face_b: 'Face') -> bool:
        """
        Проверить, нужно ли отбросить пару параллельных граней.

        Плоскости параллельны если угол между нормалями близок к 0 или π.
        Отбрасываем, если расстояние между плоскостями > threshold.

        Args:
            face_a, face_b: Грани

        Returns:
            True если нужно отбросить пару
        """
        plane_a = face_to_plane(face_a)
        plane_b = face_to_plane(face_b)

        # Проверка параллельности нормалей
        if not plane_a.is_parallel_to(plane_b, self.config.parallel_angle_threshold):
            return False

        # Вычислить расстояние между параллельными плоскостями
        # Берем центр грани A и измеряем расстояние до плоскости B
        point_a = face_a.center()
        distance = plane_b.distance_to_point(point_a)

        if distance > self.config.parallel_distance_threshold:
            self.logger.debug(
                f"Rejecting parallel faces {face_a.glo_id}-{face_b.glo_id}: "
                f"distance={distance:.2e}"
            )
            return True

        return False

    def find_coplanar_intersection(
        self,
        face_a: 'Face',
        face_b: 'Face'
    ) -> Optional[List['Node']]:
        """
        Найти пересечение компланарных треугольников.

        Упрощенная версия: проецируем на 2D и проверяем пересечение.
        Полная реализация (Sutherland-Hodgman clipping) может быть добавлена позже.

        Args:
            face_a, face_b: Копланарные грани

        Returns:
            Список узлов пересечения или None
        """
        if not self.config.coplanar_search_enabled:
            return None

        self.logger.debug(
            f"Searching coplanar intersection: {face_a.glo_id}-{face_b.glo_id}"
        )

        # Проверяем, совпадают ли грани
        if are_faces_coincident(face_a, face_b, self.config.epsilon):
            self.logger.debug("Faces are coincident, not just coplanar")
            return None

        # Проецируем треугольники на 2D
        # Выбираем ось проекции (максимальная компонента нормали)
        normal = face_a.normal
        if normal is None:
            face_a.calculate_normal()
            normal = face_a.normal

        axis = int(np.argmax(np.abs(normal)))

        # Проекция точек на 2D
        points_a_2d = [project_point_to_2d(p, axis) for p in face_a.points()]
        points_b_2d = [project_point_to_2d(p, axis) for p in face_b.points()]

        # Упрощенная проверка: есть ли точки одного треугольника внутри другого
        intersection_points_3d = []

        # Проверяем точки A в B
        for i, point_2d in enumerate(points_a_2d):
            if point_in_triangle_2d(point_2d, *points_b_2d):
                intersection_points_3d.append(face_a.points()[i])

        # Проверяем точки B в A
        for i, point_2d in enumerate(points_b_2d):
            if point_in_triangle_2d(point_2d, *points_a_2d):
                intersection_points_3d.append(face_b.points()[i])

        if not intersection_points_3d:
            return []

        # Создаем узлы
        from mesh_reapairer.src.mesh_reapairer.msu.mesh import Node
        return [Node(p) for p in intersection_points_3d]

    def handle_coincident_faces(
        self,
        face_a: 'Face',
        face_b: 'Face',
        mesh: 'Mesh'
    ) -> None:
        """
        Обработать совпадающие грани: заменить одну другой, изменить топологию.

        WARNING: Изменяет сетку!

        Args:
            face_a, face_b: Совпадающие грани
            mesh: Сетка (для изменения топологии)
        """
        self.logger.warning(
            f"Coincident faces detected: {face_a.glo_id} and {face_b.glo_id}. "
            f"Merging..."
        )

        # Копируем данные из face_b в face_a
        face_a.copy_data_from(face_b)

        # Удаляем face_b из сетки
        if face_b in mesh.faces:
            mesh.faces.remove(face_b)

        # Обновляем ребра: переносим инцидентность с face_b на face_a
        for edge in face_b.edges:
            if face_b in edge.faces:
                edge.faces.remove(face_b)
                if face_a not in edge.faces:
                    edge.faces.append(face_a)

        self.logger.info(f"Merged face {face_b.glo_id} into {face_a.glo_id}")
