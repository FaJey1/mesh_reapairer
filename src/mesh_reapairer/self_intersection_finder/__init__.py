"""
Модуль поиска самопересечений треугольных сеток.

Использует BVH (Bounding Volume Hierarchy) для эффективного поиска
кандидатов на пересечение и классификацию по методу Skorkovska et al.

Пример использования:
    >>> from mesh_reapairer.msu import Mesh
    >>> from mesh_reapairer.self_intersection_finder import find_self_intersections
    >>>
    >>> mesh = Mesh("bunny.dat")
    >>> result = find_self_intersections(mesh)
    >>> print(f"Найдено {len(result.valid_pairs)} пересечений")
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh

# Публичный API
from .application.find_self_intersections import FindSelfIntersectionsUseCase
from .application.config import (
    SelfIntersectionFinderConfig,
    BVHConfig,
    IntersectionConfig,
    GraphRecoveryConfig
)
from .domain.entities import IntersectionResult, Segment
from .domain.enums import SplitStrategy, IntersectionStatus

# Backward compatibility alias
SelfIntersection = Segment

__version__ = "2.0.0"
__author__ = "Refactored with Clean Architecture principles"


def find_self_intersections(
    mesh: 'Mesh',
    config: Optional[SelfIntersectionFinderConfig] = None,
    enable_visualization: bool = False,
    demo_remove_segments_percent: float = 0.0
) -> IntersectionResult:
    """
    Найти самопересечения в треугольной сетке.

    Главная функция модуля - точка входа для пользователей.

    Args:
        mesh: Треугольная сетка (msu.Mesh)
        config: Конфигурация поиска (если None, используются рекомендуемые параметры)
        enable_visualization: Включить визуализацию графа пересечений
        demo_remove_segments_percent: DEMO: процент случайно удаляемых valid сегментов (0-100)

    Returns:
        IntersectionResult с найденными пересечениями

    Example:
        >>> from mesh_reapairer.msu import Mesh
        >>> from mesh_reapairer.self_intersection_finder import (
        ...     find_self_intersections,
        ...     SelfIntersectionFinderConfig,
        ...     BVHConfig,
        ...     SplitStrategy
        ... )
        >>>
        >>> # С конфигурацией по умолчанию
        >>> mesh = Mesh("bunny.dat")
        >>> result = find_self_intersections(mesh)
        >>>
        >>> # С пользовательской конфигурацией
        >>> config = SelfIntersectionFinderConfig(
        ...     bvh=BVHConfig(
        ...         strategy=SplitStrategy.SAH,
        ...         enable_early_split_clipping=True,
        ...         esc_max_depth=3,
        ...         sah_bins=32
        ...     ),
        ...     logging_level="DEBUG"
        ... )
        >>> result = find_self_intersections(mesh, config)
        >>>
        >>> # Вывод результатов
        >>> print(f"Valid intersections: {len(result.valid_pairs)}")
        >>> print(f"Build time: {result.build_time_ms:.2f}ms")
        >>>
        >>> # Face-centric view
        >>> for face_id, segments in result.face_intersections.items():
        ...     print(f"Face {face_id}: {len(segments)} intersections")
    """
    if config is None:
        config = SelfIntersectionFinderConfig.create_default()

    use_case = FindSelfIntersectionsUseCase(config)
    return use_case.execute(
        mesh,
        enable_visualization=enable_visualization,
        demo_remove_segments_percent=demo_remove_segments_percent
    )


__all__ = [
    # Главная функция
    'find_self_intersections',

    # Use case (для продвинутых пользователей)
    'FindSelfIntersectionsUseCase',

    # Конфигурация
    'SelfIntersectionFinderConfig',
    'BVHConfig',
    'IntersectionConfig',
    'GraphRecoveryConfig',

    # Результаты
    'IntersectionResult',
    'Segment',
    'SelfIntersection',  # Backward compatibility

    # Enums
    'SplitStrategy',
    'IntersectionStatus',

    # Метаданные
    '__version__',
]
