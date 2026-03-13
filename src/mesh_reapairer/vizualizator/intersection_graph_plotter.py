from __future__ import annotations

from collections.abc import Iterable

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection


def plot_intersection_graph(
    alpha_graphs: Iterable,
    beta_graphs: Iterable | None = None,
    *,
    scale: float = 1.0,
    debug: bool = False,
) -> None:

    fig = plt.figure(figsize=(10,10))
    ax = fig.add_subplot(111, projection='3d')

    # Собираем центры узлов (сегментов) и вычисляем центр сцены один раз
    centers_list: list[np.ndarray] = [
        np.asarray(graph.nodes[node]["center"], dtype=float)
        for graph in alpha_graphs
        for node in graph.nodes
    ]
    if beta_graphs is not None:
        centers_list.extend(
            [
                np.asarray(graph.nodes[node]["center"], dtype=float)
                for graph in beta_graphs
                for node in graph.nodes
            ]
        )

    if not centers_list:
        print("Нет сегментов")
        return
    scene_center = np.mean(np.stack(centers_list, axis=0), axis=0)

    # ------------------------------------------------
    # рисуем сегменты (вершины графа)

    xs_red: list[float] = []
    ys_red: list[float] = []
    zs_red: list[float] = []
    xs_green: list[float] = []
    ys_green: list[float] = []
    zs_green: list[float] = []
    xs_orange: list[float] = []
    ys_orange: list[float] = []
    zs_orange: list[float] = []
    xs_yellow: list[float] = []
    ys_yellow: list[float] = []
    zs_yellow: list[float] = []

    for graph in alpha_graphs:

        for node in graph.nodes:

            data = graph.nodes[node]

            center = np.asarray(data["center"], dtype=float) - scene_center
            degree = graph.degree(node)

            if degree == 1:
                xs_red.append(center[0] * scale)
                ys_red.append(center[1] * scale)
                zs_red.append(center[2] * scale)
            elif degree == 2:
                xs_green.append(center[0] * scale)
                ys_green.append(center[1] * scale)
                zs_green.append(center[2] * scale)
            else:
                if debug:
                    xs_orange.append(center[0] * scale)
                    ys_orange.append(center[1] * scale)
                    zs_orange.append(center[2] * scale)
                else:
                    xs_green.append(center[0] * scale)
                    ys_green.append(center[1] * scale)
                    zs_green.append(center[2] * scale)

            # подпись
            label = f"{node}"

            ax.text(
                center[0]*scale,
                center[1]*scale,
                center[2]*scale,
                label,
                size=6
            )

    # ------------------------------------------------
    # рисуем beta-вершины (пары из p_invalid) — жёлтым
    if beta_graphs is not None:
        for graph in beta_graphs:
            for node in graph.nodes:
                c = np.asarray(graph.nodes[node]["center"], dtype=float) - scene_center
                xs_yellow.append(c[0] * scale)
                ys_yellow.append(c[1] * scale)
                zs_yellow.append(c[2] * scale)
                
                label = f"{node}"
                ax.text(
                    c[0]*scale,
                    c[1]*scale,
                    c[2]*scale,
                    label,
                    size=6
                )

    # ------------------------------------------------
    # рисуем связи между сегментами

    segments: list[list[list[float]]] = []
    for graph in alpha_graphs:

        for u, v in graph.edges:

            c1 = np.asarray(graph.nodes[u]["center"], dtype=float) - scene_center
            c2 = np.asarray(graph.nodes[v]["center"], dtype=float) - scene_center
            segments.append(
                [
                    [c1[0] * scale, c1[1] * scale, c1[2] * scale],
                    [c2[0] * scale, c2[1] * scale, c2[2] * scale],
                ]
            )

    # Батчинг scatter (matplotlib резко быстрее, чем по одному вызову на узел)
    if xs_red:
        ax.scatter(xs_red, ys_red, zs_red, color="red", s=80)
    if xs_green:
        ax.scatter(xs_green, ys_green, zs_green, color="green", s=40)
    if xs_orange:
        ax.scatter(xs_orange, ys_orange, zs_orange, color="orange", s=70)
    if xs_yellow:
        ax.scatter(xs_yellow, ys_yellow, zs_yellow, color="yellow", s=60)

    # Батчинг линий через коллекцию
    if segments:
        lc = Line3DCollection(segments, colors="black", linewidths=1)
        ax.add_collection3d(lc)

    ax.set_title("Intersection Graph (oriented)")
    plt.show()


if __name__ == '__main__':
    from mesh_reapairer.msu.mesh import Mesh
    from mesh_reapairer.self_intersection_finder.bvh_builder import BVHBuilder
    from mesh_reapairer.self_intersection_finder.intersection_repairer import IntersectionRepairer

    mesh = Mesh("examples/small_sphere_double.dat")
    #mesh = Mesh("examples/sphere_double.dat")
    #mesh = Mesh("examples/bunny_double.dat")
    
    bvh = BVHBuilder(mesh=mesh, eps=1e-12)
    bvh.prepare_mesh(esc_enable=False)
    bvh.build_tree(face_on_leaf=1, split_func="sah")
    bvh.traversal_tree()
    
    p_valid = bvh.p_valid[0:3]
    p_valid += bvh.p_valid[5:7]
    p_valid += bvh.p_valid[9:]
    
    p_invalid = list(bvh.p_invalid)
    p_invalid += bvh.p_valid[4:5]
    p_invalid.append(bvh.p_valid[8])
    
    ir =IntersectionRepairer(p_valid, p_invalid, eps=1e-12)
    ir.build_alpha_area()
    ir.build_beta_area()
    
    #plot_intersection_graph(ir.alpha_graphs, ir.beta_graphs)
    # ir.find_lost_segments()
    # ir.build_alpha_area()
    # plot_intersection_graph(ir.alpha_graphs)
