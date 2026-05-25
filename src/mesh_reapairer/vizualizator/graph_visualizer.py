"""
Визуализация графа пересечений.

Отрисовывает граф I(M,W) и J(M,W) до и после восстановления путей.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.infrastructure.repairer import (
        IntersectionGraph,
        EdgeType,
    )

from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.infrastructure.repairer import EdgeType


def plot_graph_before_recovery(graph: IntersectionGraph, title: str = "Intersection Graph: Before Recovery") -> None:
    """
    Визуализация графа BEFORE восстановления.

    Показывает:
    - Красные точки: узлы с degree < 2 (якоря, проблемные узлы)
    - Зеленые точки: внутренние вершины с сегментами
    - Желтые точки: невалидные пары (impossible)
    - Черные линии: α-ребра (валидные)
    - Фиолетовые пунктир: β-ребра

    Args:
        graph: Граф пересечений
        title: Заголовок графика
    """
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Собираем все точки для вычисления центра сцены
    all_points = np.array([node.point for node in graph.nodes.values()])
    if len(all_points) == 0:
        print("Graph is empty, nothing to plot")
        return

    scene_center = np.mean(all_points, axis=0)

    # Контейнеры для батчинга точек
    low_degree_nodes = []  # degree < 2 (красные)
    alpha_nodes = []  # Валидные внутренние (зеленые)
    beta_nodes = []  # Невалидные (желтые)

    # Собираем вершины по типам
    for node_id, node in graph.nodes.items():
        point = node.point - scene_center

        # Проверяем степень вершины
        degree = graph.degree(node_id)

        if degree < 2:
            # Низкая степень → красный (проблемные узлы/якоря)
            low_degree_nodes.append(point)
            color = "red"
        elif node.segment is not None:
            # Валидная пара → зеленый
            alpha_nodes.append(point)
            color = "green"
        else:
            # Невалидная пара → желтый
            beta_nodes.append(point)
            color = "yellow"

        # Подпись вершины
        label = f"[{node.face_a.glo_id},{node.face_b.glo_id}]"
        ax.text(point[0], point[1], point[2], label, size=6, alpha=0.7)

    # Собираем ребра
    alpha_segments = []
    beta_segments = []

    for edge in graph.edges.values():
        p1 = edge.node1.point - scene_center
        p2 = edge.node2.point - scene_center

        if edge.edge_type == EdgeType.ALPHA:
            alpha_segments.append([p1, p2])
        elif edge.edge_type == EdgeType.BETA:
            beta_segments.append([p1, p2])

    # Отрисовка точек
    if low_degree_nodes:
        low_deg_arr = np.array(low_degree_nodes)
        ax.scatter(low_deg_arr[:, 0], low_deg_arr[:, 1], low_deg_arr[:, 2],
                   color="red", s=100, label="Low degree (< 2)", edgecolors="black", linewidths=1.5)

    if alpha_nodes:
        alpha_arr = np.array(alpha_nodes)
        ax.scatter(alpha_arr[:, 0], alpha_arr[:, 1], alpha_arr[:, 2],
                   color="green", s=50, label="Valid nodes", alpha=0.8)

    if beta_nodes:
        beta_arr = np.array(beta_nodes)
        ax.scatter(beta_arr[:, 0], beta_arr[:, 1], beta_arr[:, 2],
                   color="yellow", s=60, label="Impossible nodes",
                   edgecolors="purple", linewidths=1, alpha=0.7)

    # Отрисовка ребер
    if alpha_segments:
        ax.add_collection3d(Line3DCollection(
            alpha_segments, colors="black", linewidths=2, label="α-edges"
        ))

    if beta_segments:
        ax.add_collection3d(Line3DCollection(
            beta_segments, colors="purple", linewidths=0.8,
            linestyles="--", alpha=0.4, label="β-edges"
        ))

    # Настройка осей
    _configure_axes(ax, all_points - scene_center, title)

    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_graph_after_recovery(
    graph: IntersectionGraph,
    title: str = "Intersection Graph: After Recovery"
) -> None:
    """
    Визуализация графа AFTER восстановления.

    Показывает:
    - Красные точки: узлы с degree < 2 (якоря, проблемные узлы)
    - Зеленые точки: внутренние вершины с сегментами
    - Желтые точки: невалидные пары (impossible)
    - Черные линии: α-ребра (валидные)
    - Синие линии: восстановленные ребра (RECOVERED)
    - Серые пунктир: оставшиеся β-ребра

    Args:
        graph: Граф пересечений
        title: Заголовок графика
    """
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Собираем все точки для вычисления центра сцены
    all_points = np.array([node.point for node in graph.nodes.values()])
    if len(all_points) == 0:
        print("Graph is empty, nothing to plot")
        return

    scene_center = np.mean(all_points, axis=0)

    # Контейнеры для батчинга точек
    low_degree_nodes = []  # degree < 2 (красные)
    alpha_nodes = []  # Валидные внутренние (зеленые)
    beta_nodes = []  # Невалидные (желтые)

    # Собираем вершины по типам
    for node_id, node in graph.nodes.items():
        point = node.point - scene_center

        # Проверяем степень вершины
        degree = graph.degree(node_id)

        if degree < 2:
            # Низкая степень → красный (проблемные узлы/якоря)
            low_degree_nodes.append(point)
        elif node.segment is not None:
            # Валидная пара → зеленый
            alpha_nodes.append(point)
        else:
            # Невалидная пара → желтый
            beta_nodes.append(point)

        # Подпись вершины
        label = f"[{node.face_a.glo_id},{node.face_b.glo_id}]"
        ax.text(point[0], point[1], point[2], label, size=6, alpha=0.7)

    # Собираем ребра
    alpha_segments = []
    recovered_segments = []
    beta_segments = []

    for edge in graph.edges.values():
        p1 = edge.node1.point - scene_center
        p2 = edge.node2.point - scene_center

        if edge.edge_type == EdgeType.ALPHA:
            alpha_segments.append([p1, p2])
        elif edge.edge_type == EdgeType.RECOVERED:
            recovered_segments.append([p1, p2])
        elif edge.edge_type == EdgeType.BETA:
            beta_segments.append([p1, p2])

    # Отрисовка точек
    if low_degree_nodes:
        low_deg_arr = np.array(low_degree_nodes)
        ax.scatter(low_deg_arr[:, 0], low_deg_arr[:, 1], low_deg_arr[:, 2],
                   color="red", s=100, label="Low degree (< 2)", edgecolors="black", linewidths=1.5)

    if alpha_nodes:
        alpha_arr = np.array(alpha_nodes)
        ax.scatter(alpha_arr[:, 0], alpha_arr[:, 1], alpha_arr[:, 2],
                   color="green", s=50, label="Valid nodes", alpha=0.8)

    if beta_nodes:
        beta_arr = np.array(beta_nodes)
        ax.scatter(beta_arr[:, 0], beta_arr[:, 1], beta_arr[:, 2],
                   color="yellow", s=60, label="Impossible nodes",
                   edgecolors="purple", linewidths=1, alpha=0.7)

    # Отрисовка ребер
    if alpha_segments:
        ax.add_collection3d(Line3DCollection(
            alpha_segments, colors="black", linewidths=2, label="α-edges"
        ))

    if recovered_segments:
        ax.add_collection3d(Line3DCollection(
            recovered_segments, colors="blue", linewidths=2.5,
            label="Recovered edges", alpha=0.9
        ))

    if beta_segments:
        ax.add_collection3d(Line3DCollection(
            beta_segments, colors="gray", linewidths=0.5,
            linestyles="--", alpha=0.2, label="β-edges"
        ))

    # Настройка осей
    _configure_axes(ax, all_points - scene_center, title)

    plt.legend()
    plt.tight_layout()
    plt.show()


def _configure_axes(ax, points: np.ndarray, title: str) -> None:
    """
    Настроить оси для 3D графика.

    Args:
        ax: Matplotlib 3D axes
        points: Массив точек (уже центрированных)
        title: Заголовок
    """
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('X', fontsize=10)
    ax.set_ylabel('Y', fontsize=10)
    ax.set_zlabel('Z', fontsize=10)

    # Автомасштабирование с сохранением пропорций
    max_range = (points.max(axis=0) - points.min(axis=0)).max() / 2.0
    ax.set_xlim(-max_range, max_range)
    ax.set_ylim(-max_range, max_range)
    ax.set_zlim(-max_range, max_range)

    # Сетка
    ax.grid(True, alpha=0.3)


__all__ = ['plot_graph_before_recovery', 'plot_graph_after_recovery']
