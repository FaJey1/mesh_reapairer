"""
Геометрические утилиты для работы с треугольниками, AABB и пространственными вычислениями.
"""
from typing import List, Tuple, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Edge, Node

from ..domain.value_objects import AABB, Plane


def compute_face_aabb(face: 'Face') -> AABB:
    """
    Вычислить AABB для грани (треугольника).

    Args:
        face: Грань сетки

    Returns:
        AABB, содержащий все три вершины грани
    """
    p1, p2, p3 = face.points()
    points = np.array([p1, p2, p3])

    min_point = np.min(points, axis=0)
    max_point = np.max(points, axis=0)

    return AABB(min_point=min_point, max_point=max_point)


def compute_primitives_aabb(primitives: List) -> AABB:
    """
    Вычислить AABB для списка примитивов.

    Args:
        primitives: Список примитивов (каждый имеет bounding_box)

    Returns:
        AABB, содержащий все примитивы
    """
    if not primitives:
        raise ValueError("Cannot compute AABB for empty primitives list")

    # Объединяем все AABB примитивов
    result = primitives[0].bounding_box
    for prim in primitives[1:]:
        result = result.union(prim.bounding_box)

    return result


def face_to_plane(face: 'Face') -> Plane:
    """
    Создать плоскость из грани треугольника.

    Args:
        face: Грань сетки

    Returns:
        Плоскость, содержащая треугольник
    """
    p1, p2, p3 = face.points()
    return Plane.from_points(p1, p2, p3)


def are_faces_neighbors(face_a: 'Face', face_b: 'Face') -> bool:
    """
    Проверить, являются ли грани соседями (имеют общее ребро).

    Args:
        face_a, face_b: Грани

    Returns:
        True если грани имеют общее ребро
    """
    # Грани соседи, если имеют хотя бы одно общее ребро
    edges_a = set(face_a.edges)
    edges_b = set(face_b.edges)

    return bool(edges_a & edges_b)


def are_faces_coplanar(face_a: 'Face', face_b: 'Face', epsilon: float = 1e-10) -> bool:
    """
    Проверить, находятся ли грани в одной плоскости (компланарны).

    Args:
        face_a, face_b: Грани
        epsilon: Порог для численного сравнения

    Returns:
        True если грани компланарны
    """
    plane_a = face_to_plane(face_a)
    plane_b = face_to_plane(face_b)

    # Проверяем параллельность плоскостей
    if not plane_a.is_parallel_to(plane_b, epsilon):
        return False

    # Проверяем, что точка из face_b лежит на плоскости face_a
    point_b = face_b.center()
    distance = plane_a.distance_to_point(point_b)

    return distance < epsilon


def are_faces_coincident(face_a: 'Face', face_b: 'Face', epsilon: float = 1e-10) -> bool:
    """
    Проверить, совпадают ли грани (одинаковые вершины).

    Args:
        face_a, face_b: Грани
        epsilon: Порог для численного сравнения

    Returns:
        True если грани совпадают
    """
    # Получаем вершины обеих граней
    nodes_a = set(face_a.nodes)
    nodes_b = set(face_b.nodes)

    # Если не три общих вершины, то не совпадают
    if len(nodes_a & nodes_b) != 3:
        return False

    # Проверяем, что вершины действительно близки по координатам
    points_a = np.array([n.p for n in face_a.nodes])
    points_b = np.array([n.p for n in face_b.nodes])

    # Для каждой точки в A находим ближайшую в B
    for pa in points_a:
        distances = [np.linalg.norm(pa - pb) for pb in points_b]
        if min(distances) > epsilon:
            return False

    return True


def split_aabb(aabb: AABB, axis: int) -> Tuple[AABB, AABB]:
    """
    Разбить AABB пополам по заданной оси.

    Args:
        aabb: AABB для разбиения
        axis: Ось разбиения (0=x, 1=y, 2=z)

    Returns:
        Кортеж (left_aabb, right_aabb)
    """
    center = aabb.center()[axis]

    # Левый AABB
    left_max = aabb.max_point.copy()
    left_max[axis] = center
    left_aabb = AABB(min_point=aabb.min_point, max_point=left_max)

    # Правый AABB
    right_min = aabb.min_point.copy()
    right_min[axis] = center
    right_aabb = AABB(min_point=right_min, max_point=aabb.max_point)

    return left_aabb, right_aabb


def face_intersects_aabb(face: 'Face', aabb: AABB) -> bool:
    """
    Проверить, пересекает ли треугольник (грань) AABB.

    Использует SAT (Separating Axis Theorem) тест.

    Args:
        face: Грань (треугольник)
        aabb: AABB

    Returns:
        True если треугольник пересекает AABB
    """
    # Упрощенная версия: проверяем, пересекается ли AABB грани с заданным AABB
    face_aabb = compute_face_aabb(face)
    return face_aabb.intersects(aabb)


def triangle_area(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
    """
    Вычислить площадь треугольника по трем точкам.

    Args:
        p1, p2, p3: Вершины треугольника

    Returns:
        Площадь треугольника
    """
    # Векторы сторон
    v1 = p2 - p1
    v2 = p3 - p1

    # Площадь = 0.5 * |v1 × v2|
    cross = np.cross(v1, v2)
    return 0.5 * np.linalg.norm(cross)


def triangle_normal(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> np.ndarray:
    """
    Вычислить нормаль к треугольнику.

    Args:
        p1, p2, p3: Вершины треугольника

    Returns:
        Нормализованный вектор нормали
    """
    v1 = p2 - p1
    v2 = p3 - p1

    normal = np.cross(v1, v2)
    norm = np.linalg.norm(normal)

    if norm < 1e-15:
        raise ValueError("Degenerate triangle (zero area)")

    return normal / norm


def point_in_triangle_2d(p: np.ndarray, t1: np.ndarray, t2: np.ndarray, t3: np.ndarray) -> bool:
    """
    Проверить, находится ли точка внутри треугольника (2D тест).

    Использует барицентрические координаты.

    Args:
        p: Точка (2D)
        t1, t2, t3: Вершины треугольника (2D)

    Returns:
        True если точка внутри треугольника
    """
    # Барицентрические координаты
    v0 = t3 - t1
    v1 = t2 - t1
    v2 = p - t1

    dot00 = np.dot(v0, v0)
    dot01 = np.dot(v0, v1)
    dot02 = np.dot(v0, v2)
    dot11 = np.dot(v1, v1)
    dot12 = np.dot(v1, v2)

    inv_denom = 1.0 / (dot00 * dot11 - dot01 * dot01)
    u = (dot11 * dot02 - dot01 * dot12) * inv_denom
    v = (dot00 * dot12 - dot01 * dot02) * inv_denom

    return (u >= 0) and (v >= 0) and (u + v <= 1)


def project_point_to_2d(point_3d: np.ndarray, axis: int) -> np.ndarray:
    """
    Проецировать 3D точку на 2D плоскость, отбросив указанную ось.

    Args:
        point_3d: 3D точка
        axis: Ось для отбрасывания (0=x, 1=y, 2=z)

    Returns:
        2D точка
    """
    if axis == 0:  # Отбросить X
        return np.array([point_3d[1], point_3d[2]])
    elif axis == 1:  # Отбросить Y
        return np.array([point_3d[0], point_3d[2]])
    else:  # Отбросить Z
        return np.array([point_3d[0], point_3d[1]])


def unproject_point_from_2d(point_2d: np.ndarray, axis: int, value: float) -> np.ndarray:
    """
    Восстановить 3D точку из 2D проекции, добавив значение для отброшенной оси.

    Args:
        point_2d: 2D точка
        axis: Отброшенная ось (0=x, 1=y, 2=z)
        value: Значение для отброшенной оси

    Returns:
        3D точка
    """
    if axis == 0:  # Восстановить X
        return np.array([value, point_2d[0], point_2d[1]])
    elif axis == 1:  # Восстановить Y
        return np.array([point_2d[0], value, point_2d[1]])
    else:  # Восстановить Z
        return np.array([point_2d[0], point_2d[1], value])


def distance_between_points(p1: np.ndarray, p2: np.ndarray) -> float:
    """
    Вычислить евклидово расстояние между двумя точками.

    Args:
        p1, p2: 3D точки

    Returns:
        Расстояние
    """
    return np.linalg.norm(p2 - p1)


def get_shared_nodes(face_a: 'Face', face_b: 'Face') -> set:
    """
    Получить общие вершины двух граней.

    Args:
        face_a, face_b: Грани

    Returns:
        Множество общих узлов (Node)
    """
    nodes_a = set(face_a.nodes)
    nodes_b = set(face_b.nodes)
    return nodes_a & nodes_b


def is_point_shared_vertex(point: np.ndarray, face_a: 'Face', face_b: 'Face', epsilon: float = 1e-10) -> bool:
    """
    Проверить, является ли точка общей вершиной двух граней.

    Args:
        point: Координаты точки
        face_a, face_b: Грани
        epsilon: Порог численного сравнения

    Returns:
        True если точка совпадает с общей вершиной
    """
    shared_nodes = get_shared_nodes(face_a, face_b)

    for node in shared_nodes:
        distance = np.linalg.norm(point - node.p)
        if distance < epsilon:
            return True

    return False


def is_segment_trivial_intersection(
    segment_points: list,
    face_a: 'Face',
    face_b: 'Face',
    epsilon: float = 1e-10
) -> bool:
    """
    Проверить, является ли сегмент "тривиальным" пересечением (только в общей вершине).

    Правила фильтрации (СТРОГИЕ):
    1. Если нет общих вершин → НЕ тривиальное (реальное пересечение)
    2. Если сегмент пустой → тривиальное
    3. Если ВСЕ точки сегмента лежат в пределах epsilon от общих вершин → тривиальное
    4. Если хотя бы одна точка НЕ около общей вершины → НЕ тривиальное

    Args:
        segment_points: Список точек сегмента (Node или np.ndarray)
        face_a, face_b: Грани
        epsilon: Порог численного сравнения (увеличен для учета численных ошибок)

    Returns:
        True если сегмент тривиальный (нужно отфильтровать)
    """
    if not segment_points:
        return True

    # Получаем общие вершины
    shared_nodes = get_shared_nodes(face_a, face_b)

    # Если нет общих вершин - не может быть тривиального пересечения
    if not shared_nodes:
        return False

    # Координаты общих вершин
    shared_coords = [node.p for node in shared_nodes]

    # Получаем координаты точек сегмента
    segment_coords = []
    for p in segment_points:
        if hasattr(p, 'p'):  # Node
            segment_coords.append(p.p)
        else:  # np.ndarray
            segment_coords.append(p)

    # Проверяем каждую точку сегмента
    # Используем увеличенный epsilon для учета численных ошибок
    tolerance = epsilon * 100  # 1e-8 для стандартного epsilon=1e-10

    for seg_point in segment_coords:
        # Проверяем, близка ли эта точка к какой-либо общей вершине
        is_near_shared = False
        for shared_point in shared_coords:
            distance = np.linalg.norm(seg_point - shared_point)
            if distance < tolerance:
                is_near_shared = True
                break

        # Если хотя бы одна точка сегмента НЕ около общей вершины
        if not is_near_shared:
            return False

    # Все точки сегмента около общих вершин → тривиальное пересечение
    return True
