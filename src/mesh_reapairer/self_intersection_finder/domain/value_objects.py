"""
Value Objects для модуля поиска самопересечений.

Value objects - это immutable объекты, которые определяются своими атрибутами.
"""
from dataclasses import dataclass
from typing import Tuple, List, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Node


@dataclass(frozen=True)
class AABB:
    """
    Axis-Aligned Bounding Box (AABB) - ограничивающий параллелепипед.

    Immutable объект, определяет прямоугольный параллелепипед с гранями
    параллельными осям координат.

    Attributes:
        min_point: Минимальная точка (x_min, y_min, z_min)
        max_point: Максимальная точка (x_max, y_max, z_max)
    """
    min_point: np.ndarray  # shape (3,)
    max_point: np.ndarray  # shape (3,)

    def __post_init__(self):
        """Валидация после инициализации."""
        if self.min_point.shape != (3,) or self.max_point.shape != (3,):
            raise ValueError("min_point and max_point must be 3D vectors")

        # Проверяем, что min <= max
        if not np.all(self.min_point <= self.max_point):
            raise ValueError("min_point must be <= max_point component-wise")

    def surface_area(self) -> float:
        """
        Вычислить площадь поверхности AABB.

        Returns:
            Площадь поверхности (2 * (dx*dy + dy*dz + dz*dx))
        """
        extents = self.max_point - self.min_point
        return 2.0 * (
            extents[0] * extents[1] +
            extents[1] * extents[2] +
            extents[2] * extents[0]
        )

    def volume(self) -> float:
        """
        Вычислить объем AABB.

        Returns:
            Объем (dx * dy * dz)
        """
        extents = self.max_point - self.min_point
        return extents[0] * extents[1] * extents[2]

    def center(self) -> np.ndarray:
        """
        Вычислить центр AABB.

        Returns:
            Центр (средняя точка)
        """
        return 0.5 * (self.min_point + self.max_point)

    def extents(self) -> np.ndarray:
        """
        Вычислить размеры AABB по каждой оси.

        Returns:
            Вектор размеров (dx, dy, dz)
        """
        return self.max_point - self.min_point

    def max_extent_axis(self) -> int:
        """
        Найти ось с максимальным размером.

        Returns:
            Индекс оси (0=x, 1=y, 2=z)
        """
        extents = self.extents()
        return int(np.argmax(extents))

    def intersects(self, other: 'AABB') -> bool:
        """
        Проверить пересечение с другим AABB.

        Args:
            other: Другой AABB

        Returns:
            True если AABB пересекаются
        """
        # Пересекаются, если проекции пересекаются на всех трех осях
        return (
            self.min_point[0] <= other.max_point[0] and
            self.max_point[0] >= other.min_point[0] and
            self.min_point[1] <= other.max_point[1] and
            self.max_point[1] >= other.min_point[1] and
            self.min_point[2] <= other.max_point[2] and
            self.max_point[2] >= other.min_point[2]
        )

    def contains_point(self, point: np.ndarray) -> bool:
        """
        Проверить, содержит ли AABB точку.

        Args:
            point: Точка (3D вектор)

        Returns:
            True если точка внутри AABB
        """
        return np.all(self.min_point <= point) and np.all(point <= self.max_point)

    def union(self, other: 'AABB') -> 'AABB':
        """
        Объединение с другим AABB.

        Args:
            other: Другой AABB

        Returns:
            Новый AABB, содержащий оба исходных
        """
        return AABB(
            min_point=np.minimum(self.min_point, other.min_point),
            max_point=np.maximum(self.max_point, other.max_point)
        )

    @staticmethod
    def from_points(points: List[np.ndarray]) -> 'AABB':
        """
        Создать AABB из списка точек.

        Args:
            points: Список 3D точек

        Returns:
            AABB, содержащий все точки
        """
        if not points:
            raise ValueError("Cannot create AABB from empty point list")

        points_array = np.array(points)
        return AABB(
            min_point=np.min(points_array, axis=0),
            max_point=np.max(points_array, axis=0)
        )


@dataclass(frozen=True)
class Plane:
    """
    Плоскость в 3D пространстве: ax + by + cz + d = 0.

    Immutable объект, представляющий плоскость через уравнение.

    Attributes:
        a, b, c: Коэффициенты нормали (a, b, c) - вектор нормали к плоскости
        d: Свободный член уравнения плоскости
    """
    a: float
    b: float
    c: float
    d: float

    def __post_init__(self):
        """Валидация после инициализации."""
        # Проверяем, что нормаль не нулевая
        normal_length = np.sqrt(self.a**2 + self.b**2 + self.c**2)
        if normal_length < 1e-15:
            raise ValueError("Plane normal cannot be zero")

    def normal(self) -> np.ndarray:
        """
        Получить вектор нормали к плоскости.

        Returns:
            Вектор нормали (a, b, c)
        """
        return np.array([self.a, self.b, self.c])

    def signed_distance(self, point: np.ndarray) -> float:
        """
        Вычислить подписанное расстояние от точки до плоскости.

        Args:
            point: 3D точка

        Returns:
            Подписанное расстояние (положительное - с одной стороны,
            отрицательное - с другой, 0 - на плоскости)
        """
        return self.a * point[0] + self.b * point[1] + self.c * point[2] + self.d

    def distance_to_point(self, point: np.ndarray) -> float:
        """
        Вычислить абсолютное расстояние от точки до плоскости.

        Args:
            point: 3D точка

        Returns:
            Абсолютное расстояние
        """
        normal_length = np.sqrt(self.a**2 + self.b**2 + self.c**2)
        return abs(self.signed_distance(point)) / normal_length

    def is_parallel_to(self, other: 'Plane', angle_threshold: float = 1e-6) -> bool:
        """
        Проверить параллельность с другой плоскостью.

        Плоскости параллельны, если их нормали параллельны (угол между ними близок к 0 или π).

        Args:
            other: Другая плоскость
            angle_threshold: Порог угла (в радианах)

        Returns:
            True если плоскости параллельны
        """
        normal1 = self.normal()
        normal2 = other.normal()

        # Нормализуем нормали
        normal1 = normal1 / np.linalg.norm(normal1)
        normal2 = normal2 / np.linalg.norm(normal2)

        # Скалярное произведение нормализованных нормалей
        dot_product = np.dot(normal1, normal2)

        # Параллельны если |dot| ≈ 1 (угол ≈ 0 или ≈ π)
        return abs(abs(dot_product) - 1.0) < angle_threshold

    @staticmethod
    def from_points(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> 'Plane':
        """
        Создать плоскость из трех точек.

        Args:
            p1, p2, p3: Три точки, определяющие плоскость (не коллинеарные)

        Returns:
            Плоскость, проходящая через эти точки
        """
        # Векторы на плоскости
        v1 = p2 - p1
        v2 = p3 - p1

        # Нормаль как векторное произведение
        normal = np.cross(v1, v2)

        # Проверка на коллинеарность
        if np.linalg.norm(normal) < 1e-15:
            raise ValueError("Points are collinear, cannot define a unique plane")

        # Нормализуем нормаль
        normal = normal / np.linalg.norm(normal)

        a, b, c = normal
        # Вычисляем d из условия, что p1 лежит на плоскости
        d = -(a * p1[0] + b * p1[1] + c * p1[2])

        return Plane(a, b, c, d)

    @staticmethod
    def from_normal_and_point(normal: np.ndarray, point: np.ndarray) -> 'Plane':
        """
        Создать плоскость из нормали и точки на плоскости.

        Args:
            normal: Вектор нормали (не обязательно нормализованный)
            point: Точка на плоскости

        Returns:
            Плоскость с заданной нормалью, проходящая через точку
        """
        # Нормализуем нормаль
        normal = normal / np.linalg.norm(normal)

        a, b, c = normal
        d = -(a * point[0] + b * point[1] + c * point[2])

        return Plane(a, b, c, d)


@dataclass(frozen=True)
class ClassificationCode:
    """
    Код классификации пересечения трех ребер треугольника с плоскостью.

    По методу Skorkovska et al. (article_2.md), каждое ребро классифицируется:
    - 0: точка пересечения вне ребра
    - 1: точка пересечения в вершине
    - 2: точка пересечения внутри ребра

    Attributes:
        codes: Кортеж из трех кодов (по одному на каждое ребро)
        points: Список точек пересечения (может содержать None)
    """
    codes: Tuple[int, int, int]
    points: Tuple[Optional['Node'], Optional['Node'], Optional['Node']]

    def __post_init__(self):
        """Валидация после инициализации."""
        if len(self.codes) != 3:
            raise ValueError("codes must contain exactly 3 elements")

        if len(self.points) != 3:
            raise ValueError("points must contain exactly 3 elements")

        # Проверяем, что коды в допустимом диапазоне
        for code in self.codes:
            if code not in (0, 1, 2):
                raise ValueError(f"Invalid classification code: {code}")

    def to_list(self) -> List[int]:
        """Преобразовать коды в список (для сравнения с impossible_cases)."""
        return list(self.codes)

    def __eq__(self, other):
        """Сравнение кодов."""
        if isinstance(other, ClassificationCode):
            return self.codes == other.codes
        elif isinstance(other, (list, tuple)):
            return self.codes == tuple(other)
        return False

    def __hash__(self):
        """Хэш для использования в множествах и словарях."""
        return hash(self.codes)
