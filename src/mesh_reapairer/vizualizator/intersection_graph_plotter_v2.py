"""
Визуализация графа пересечений (новая версия для IntersectionGraph).

Показывает граф J(M,W) с α-ребрами (valid), β-ребрами (potential),
и RECOVERED ребрами (восстановленные).
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.infrastructure.repairer.intersection_graph import IntersectionGraph

from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.infrastructure.repairer import EdgeType


def plot_intersection_graph_v2(
    graph: 'IntersectionGraph',
    title: str = "Intersection Graph",
    *,
    scale: float = 1.0,
    show_labels: bool = True
) -> None:
    """
    Визуализация графа пересечений J(M,W).

    Args:
        graph: Граф пересечений
        title: Заголовок графика
        scale: Масштаб координат
        show_labels: Показывать метки узлов
    """
    if not graph.nodes:
        print(f"{title}: No nodes to plot")
        return

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    # 1. Собираем координаты всех узлов
    all_points = []
    for node in graph.nodes.values():
        all_points.append(node.point)

    all_points = np.array(all_points)
    scene_center = np.mean(all_points, axis=0)

    # 2. Категоризуем узлы
    alpha_nodes = []      # Узлы с сегментом (зеленые)
    beta_nodes = []       # Узлы без сегмента (желтые)
    anchor_nodes = []     # Якоря: α-узлы с degree=1 (красные)

    for node_id, node in graph.nodes.items():
        coord = (node.point - scene_center) * scale

        if node.segment is not None:
            # α-узел (есть сегмент)
            alpha_degree = graph.degree(node_id, edge_type=EdgeType.ALPHA)
            if alpha_degree == 1:
                anchor_nodes.append((node_id, node, coord))
            else:
                alpha_nodes.append((node_id, node, coord))
        else:
            # β-узел (нет сегмента)
            beta_nodes.append((node_id, node, coord))

    # 3. Собираем ребра по типам
    alpha_edges = []
    beta_edges = []
    recovered_edges = []

    for edge in graph.edges.values():
        node1_coord = (edge.node1.point - scene_center) * scale
        node2_coord = (edge.node2.point - scene_center) * scale
        segment = [node1_coord, node2_coord]

        if edge.edge_type == EdgeType.ALPHA:
            alpha_edges.append(segment)
        elif edge.edge_type == EdgeType.BETA:
            beta_edges.append(segment)
        elif edge.edge_type == EdgeType.RECOVERED:
            recovered_edges.append(segment)

    # 4. Отрисовка узлов
    if alpha_nodes:
        coords = np.array([c for _, _, c in alpha_nodes])
        ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2],
                   color="green", s=50, label=f"α-nodes ({len(alpha_nodes)})", alpha=0.8)

    if anchor_nodes:
        coords = np.array([c for _, _, c in anchor_nodes])
        ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2],
                   color="red", s=100, label=f"Anchors ({len(anchor_nodes)})",
                   marker='o', edgecolors='darkred', linewidths=2)

    if beta_nodes:
        coords = np.array([c for _, _, c in beta_nodes])
        ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2],
                   color="yellow", s=60, label=f"β-nodes ({len(beta_nodes)})",
                   edgecolors="orange", alpha=0.7)

    # 5. Отрисовка ребер
    if alpha_edges:
        ax.add_collection3d(Line3DCollection(
            alpha_edges, colors="black", linewidths=1.5,
            label=f"α-edges ({len(alpha_edges)})"
        ))

    if recovered_edges:
        ax.add_collection3d(Line3DCollection(
            recovered_edges, colors="blue", linewidths=2.0, linestyles="-",
            label=f"RECOVERED edges ({len(recovered_edges)})", alpha=0.7
        ))

    if beta_edges:
        ax.add_collection3d(Line3DCollection(
            beta_edges, colors="purple", linewidths=0.8, linestyles="--",
            label=f"β-edges ({len(beta_edges)})", alpha=0.4
        ))

    # 6. Метки узлов (опционально)
    if show_labels:
        for node_id, node, coord in alpha_nodes[:20]:  # Первые 20
            label = f"[{node.face_a.glo_id},{node.face_b.glo_id}]"
            ax.text(coord[0], coord[1], coord[2], label, size=6, color='green', alpha=0.6)

        for node_id, node, coord in anchor_nodes[:10]:  # Первые 10 якорей
            label = f"A{node_id}"
            ax.text(coord[0], coord[1], coord[2], label, size=8, color='red', weight='bold')

        for node_id, node, coord in beta_nodes[:15]:  # Первые 15
            label = f"β{node_id}"
            ax.text(coord[0], coord[1], coord[2], label, size=6, color='orange', alpha=0.6)

    # 7. Настройка осей и легенды
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    # Автомасштаб для сохранения пропорций
    max_range = (all_points - scene_center).max() * scale
    ax.set_xlim(-max_range, max_range)
    ax.set_ylim(-max_range, max_range)
    ax.set_zlim(-max_range, max_range)

    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def plot_intersection_graph_before_after(
    graph_before: 'IntersectionGraph',
    graph_after: 'IntersectionGraph',
    *,
    scale: float = 1.0,
    show_labels: bool = False
) -> None:
    """
    Визуализация графа BEFORE и AFTER восстановления на одном окне.

    Args:
        graph_before: Граф ДО восстановления
        graph_after: Граф ПОСЛЕ восстановления
        scale: Масштаб координат
        show_labels: Показывать метки узлов
    """
    fig = plt.figure(figsize=(18, 8))

    # BEFORE (слева) - показываем все ребра
    ax1 = fig.add_subplot(121, projection='3d')
    _plot_graph_on_axis(ax1, graph_before, "BEFORE Recovery", scale, show_labels, show_beta=True)

    # AFTER (справа) - НЕ показываем неиспользованные β-ребра
    ax2 = fig.add_subplot(122, projection='3d')
    _plot_graph_on_axis(ax2, graph_after, "AFTER Recovery", scale, show_labels, show_beta=False)

    plt.tight_layout()
    plt.show()


def _plot_graph_on_axis(ax, graph, title, scale, show_labels, show_beta=True):
    """
    Вспомогательная функция для отрисовки графа на заданной оси.

    Args:
        show_beta: Показывать β-ребра (неиспользованные пути).
                   Для графа AFTER рекомендуется False.
    """
    if not graph.nodes:
        ax.set_title(f"{title}: No nodes")
        return

    # Собираем координаты
    all_points = np.array([node.point for node in graph.nodes.values()])
    scene_center = np.mean(all_points, axis=0)

    # Категоризуем узлы
    alpha_coords = []
    anchor_coords = []
    beta_coords = []

    for node_id, node in graph.nodes.items():
        coord = (node.point - scene_center) * scale

        if node.segment is not None:
            alpha_degree = graph.degree(node_id, edge_type=EdgeType.ALPHA)
            if alpha_degree == 1:
                anchor_coords.append(coord)
            else:
                alpha_coords.append(coord)
        else:
            beta_coords.append(coord)

    # Собираем ребра
    alpha_edges = []
    beta_edges = []
    recovered_edges = []

    for edge in graph.edges.values():
        node1_coord = (edge.node1.point - scene_center) * scale
        node2_coord = (edge.node2.point - scene_center) * scale
        segment = [node1_coord, node2_coord]

        if edge.edge_type == EdgeType.ALPHA:
            alpha_edges.append(segment)
        elif edge.edge_type == EdgeType.BETA:
            beta_edges.append(segment)
        elif edge.edge_type == EdgeType.RECOVERED:
            recovered_edges.append(segment)

    # Отрисовка
    stats = graph.stats()

    if alpha_coords:
        alpha_coords = np.array(alpha_coords)
        ax.scatter(alpha_coords[:, 0], alpha_coords[:, 1], alpha_coords[:, 2],
                   color="green", s=40, alpha=0.7)

    if anchor_coords:
        anchor_coords = np.array(anchor_coords)
        ax.scatter(anchor_coords[:, 0], anchor_coords[:, 1], anchor_coords[:, 2],
                   color="red", s=80, marker='o', edgecolors='darkred', linewidths=2)

    if beta_coords:
        beta_coords = np.array(beta_coords)
        ax.scatter(beta_coords[:, 0], beta_coords[:, 1], beta_coords[:, 2],
                   color="yellow", s=50, edgecolors="orange", alpha=0.6)

    if alpha_edges:
        ax.add_collection3d(Line3DCollection(alpha_edges, colors="black", linewidths=1.2))

    if recovered_edges:
        ax.add_collection3d(Line3DCollection(recovered_edges, colors="blue", linewidths=1.8, alpha=0.7))

    # β-ребра показываем только если show_beta=True (для BEFORE графа)
    if beta_edges and show_beta:
        ax.add_collection3d(Line3DCollection(beta_edges, colors="purple", linewidths=0.6,
                                            linestyles="--", alpha=0.3))

    # Заголовок с статистикой
    title_text = (
        f"{title}\n"
        f"Nodes: {stats['nodes']} | Anchors: {stats['anchors']}\n"
        f"α-edges: {stats['alpha_edges']} | β-edges: {stats['beta_edges']} | "
        f"Recovered: {stats['recovered_edges']}"
    )
    ax.set_title(title_text, fontsize=11, fontweight='bold')
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    # Автомасштаб
    max_range = (all_points - scene_center).max() * scale
    ax.set_xlim(-max_range, max_range)
    ax.set_ylim(-max_range, max_range)
    ax.set_zlim(-max_range, max_range)
    ax.grid(True, alpha=0.2)
