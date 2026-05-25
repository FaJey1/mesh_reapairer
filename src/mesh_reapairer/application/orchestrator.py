from __future__ import annotations

from mesh_reapairer.src.mesh_reapairer.msu import Mesh
from mesh_reapairer.src.mesh_reapairer.restorer import restore_mesh
from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import (
    find_self_intersections,
    SelfIntersectionFinderConfig,
    GraphRecoveryConfig
)

from mesh_reapairer.src.mesh_reapairer.vizualizator import plot_intersection_result

def repair_mesh(
    input_mesh: Mesh,
    *,
    enable_visualization: bool = False,
    demo_remove_segments_percent: float = 0.0,
    interpolation_mode: str = 'vertices',
    visualize_intersection_graph: bool = False
) -> Mesh:
    """
    Высокоуровневый сценарий восстановления сетки.

    Конвейер:
    1. Поиск самопересечений с использованием BVH-дерева
    2. (Опционально) Визуализация результатов
    3. Передача найденных пересечений в модуль восстановления
    4. Возврат восстановленной сетки

    Args:
        input_mesh: Входная сетка
        enable_visualization: Показать визуализацию результатов поиска пересечений
        demo_remove_segments_percent: DEMO: процент удаляемых сегментов для тестирования восстановления
        interpolation_mode: Режим интерполяции ('vertices' или 'edges')
        visualize_intersection_graph: Показать граф пересечений BEFORE/AFTER восстановления

    Returns:
        Восстановленная сетка
    """
    # Создаем конфигурацию с заданным режимом интерполяции
    config = SelfIntersectionFinderConfig(
        recovery=GraphRecoveryConfig(
            interpolation_mode=interpolation_mode
        )
    )

    # Поиск самопересечений с визуализацией графа (если включена)
    result = find_self_intersections(
        mesh=input_mesh,
        config=config,
        enable_visualization=visualize_intersection_graph,
        demo_remove_segments_percent=demo_remove_segments_percent
    )

    # Визуализация результатов (если включена)
    if enable_visualization:
        plot_intersection_result(
            mesh=input_mesh,
            result=result,
            show_all_faces=True,
            show_border_faces=True,
            show_segments=True,
            faces_alpha=0.1,
            border_alpha=0.5,
            border_color="pink",
            segment_color="red",
            segment_linewidth=3.0,
        )

    restore_mesh(mesh=input_mesh, intersection_result=result)
    return input_mesh
