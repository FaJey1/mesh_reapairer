"""
Перечисления для модуля поиска самопересечений.
"""
from enum import Enum, auto


class SplitStrategy(Enum):
    """Стратегия разбиения при построении BVH дерева."""
    SAH = auto()      # Surface Area Heuristic
    LBVH = auto()     # Linear BVH (Morton codes)
    HYBRID = auto()   # Гибрид SAH + LBVH


class IntersectionStatus(Enum):
    """Статус пересечения двух граней."""
    NO_INTERSECTION = auto()     # Нет пересечения
    VALID = auto()               # Корректное пересечение найдено
    IMPOSSIBLE = auto()          # Невозможная классификация (численная ошибка)
    COPLANAR = auto()            # Компланарные грани
    PARALLEL_REJECTED = auto()   # Параллельные плоскости (отброшено)
    NEIGHBORS = auto()           # Соседние грани (общее ребро)


class ClassificationCodeType(Enum):
    """Тип кода классификации ребра относительно плоскости (Skorkovska et al.)"""
    OUTSIDE = 0       # Точка пересечения вне ребра
    VERTEX = 1        # Точка пересечения в вершине
    INSIDE = 2        # Точка пересечения внутри ребра
