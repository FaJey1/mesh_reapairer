from __future__ import annotations

import logging
from collections.abc import Iterable

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
from mesh_reapairer.self_intersection_finder.bvh_builder import BVHBuilder
from mesh_reapairer.self_intersection_finder.intersection_repairer import IntersectionRepairer

def plot_intersection_graph(
    alpha_graphs: Iterable,
    beta_graphs: Iterable | None = None,
    *,
    scale: float = 1.0,
    debug: bool = False,
) -> None:
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection='3d')

    # 1. Сбор всех центров для вычисления общего центра сцены
    all_nodes_data = []
    for graph in alpha_graphs:
        for node in graph.nodes:
            all_nodes_data.append(np.asarray(graph.nodes[node]["center"], dtype=float))
    
    if beta_graphs is not None:
        for graph in beta_graphs:
            for node in graph.nodes:
                all_nodes_data.append(np.asarray(graph.nodes[node]["center"], dtype=float))

    if not all_nodes_data:
        print("IntersectionRepairer: Нет данных для отрисовки")
        return

    scene_center = np.mean(np.stack(all_nodes_data, axis=0), axis=0)

    # Контейнеры для батчинга точек
    pts = {
        "red": ([], [], []),    # Альфа-якоря (deg=1)
        "green": ([], [], []),  # Альфа-внутренние
        "orange": ([], [], []), # Альфа-разветвления (deg > 2)
        "yellow": ([], [], [])  # Бетта-узлы
    }

    # 2. Обработка Alpha-графов
    alpha_segments = []
    anchor_nodes = []  # Якоря: (node, координаты)
    for graph in alpha_graphs:
        for node in graph.nodes:
            data = graph.nodes[node]
            c = (np.asarray(data["center"], dtype=float) - scene_center) * scale
            deg = graph.degree(node)

            if deg == 1:
                color = "red"
                anchor_nodes.append((node, c))  # Сохраняем узел и координаты якоря
            elif deg == 2:
                color = "green"
            else:
                color = "orange" if debug else "green"

            pts[color][0].append(c[0]); pts[color][1].append(c[1]); pts[color][2].append(c[2])

            label = f"[{node[0].glo_id},{node[1].glo_id}]"
            ax.text(c[0], c[1], c[2], label, size=6, alpha=0.7)

        for u, v in graph.edges:
            c1 = (np.asarray(graph.nodes[u]["center"], dtype=float) - scene_center) * scale
            c2 = (np.asarray(graph.nodes[v]["center"], dtype=float) - scene_center) * scale
            alpha_segments.append([c1, c2])

    # 3. Обработка Beta-графов
    beta_segments = []
    beta_nodes = []  # Бета-узлы: (node, координаты)
    if beta_graphs is not None:
        for graph in beta_graphs:
            for node in graph.nodes:
                data = graph.nodes[node]
                c = (np.asarray(data["center"], dtype=float) - scene_center) * scale
                pts["yellow"][0].append(c[0]); pts["yellow"][1].append(c[1]); pts["yellow"][2].append(c[2])
                beta_nodes.append((node, c))  # Сохраняем узел и координаты

                label = f"b[{node[0].glo_id},{node[1].glo_id}]"
                ax.text(c[0], c[1], c[2], label, size=6, color="purple")

            for u, v in graph.edges:
                c1 = (np.asarray(graph.nodes[u]["center"], dtype=float) - scene_center) * scale
                c2 = (np.asarray(graph.nodes[v]["center"], dtype=float) - scene_center) * scale
                beta_segments.append([c1, c2])

    # Создание сегментов между якорями и бета-узлами (только если есть общая ячейка)
    anchor_beta_segments = []
    for anchor_node, anchor_coord in anchor_nodes:
        for beta_node, beta_coord in beta_nodes:
            # Проверяем, есть ли общий треугольник (ячейка) между якорем и бета-узлом
            anchor_cells = {anchor_node[0], anchor_node[1]}
            beta_cells = {beta_node[0], beta_node[1]}
            if anchor_cells & beta_cells:  # Если есть пересечение множеств
                anchor_beta_segments.append([anchor_coord, beta_coord])

    # 4. Отрисовка
    # Точки
    if pts["red"][0]:    ax.scatter(*pts["red"], color="red", s=80, label="Alpha Anchor")
    if pts["green"][0]:  ax.scatter(*pts["green"], color="green", s=40, label="Alpha Internal")
    if pts["orange"][0]: ax.scatter(*pts["orange"], color="orange", s=70)
    if pts["yellow"][0]: ax.scatter(*pts["yellow"], color="yellow", s=60, edgecolors="purple", label="Beta")

    # Ребра Alpha (черные сплошные)
    if alpha_segments:
        ax.add_collection3d(Line3DCollection(alpha_segments, colors="black", linewidths=1.2))

    # Ребра Beta (фиолетовые пунктирные)
    if beta_segments:
        ax.add_collection3d(Line3DCollection(beta_segments, colors="purple", linewidths=0.8, linestyles="--", alpha=0.5))

    # Соединения якорей с бета-узлами (фиолетовые пунктирные)
    if anchor_beta_segments:
        ax.add_collection3d(Line3DCollection(anchor_beta_segments, colors="purple", linewidths=0.6, linestyles="--", alpha=0.3))

    ax.set_title("Intersection Graph: Alpha (solid) & Beta (dashed)")
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
    
    # Автомасштаб осей для сохранения пропорций
    all_pts = np.array(all_nodes_data) - scene_center
    max_range = (all_pts.max(axis=0) - all_pts.min(axis=0)).max() / 2.0 * scale
    ax.set_xlim(-max_range, max_range)
    ax.set_ylim(-max_range, max_range)
    ax.set_zlim(-max_range, max_range)

    plt.show()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(levelname)s: %(message)s'
    )
    
    mesh = Mesh("examples/small_sphere_double.dat")
    #mesh = Mesh("examples/sphere_double.dat")
    #mesh = Mesh("examples/bunny_double.dat")
    
    bvh = BVHBuilder(mesh=mesh, eps=1e-12)
    bvh.prepare_mesh(esc_enable=False)
    bvh.build_tree(face_on_leaf=1, split_func="sah")
    bvh.traversal_tree()
    
    p_valid = bvh.p_valid[:2]
    p_valid += bvh.p_valid[6:8]
    p_valid += bvh.p_valid[9:]
    
    p_invalid = bvh.p_invalid
    p_invalid += bvh.p_valid[2:6]
    p_invalid.append(bvh.p_valid[8])
    
    ir =IntersectionRepairer(mesh=mesh, p_valid=p_valid, p_invalid=p_invalid, eps=1e-12)
    #ir =IntersectionRepairer(mesh, bvh.p_valid, bvh.p_invalid, eps=1e-12)
    ir.build_alpha_area()
    ir.build_beta_area()
    plot_intersection_graph(alpha_graphs=ir.alpha_graphs, beta_graphs=ir.beta_graphs, debug=False)
    ir.find_lost_segments()
    plot_intersection_graph(alpha_graphs=ir.alpha_graphs,beta_graphs=ir.beta_graphs,debug=True)
