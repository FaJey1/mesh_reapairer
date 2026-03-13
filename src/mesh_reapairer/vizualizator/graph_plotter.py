from __future__ import annotations

import networkx as nx
import matplotlib.pyplot as plt
from mesh_reapairer.self_intersection_finder.bvh_builder import *

def plot_graph(graph):
    """
    Визуализирует структуру BVH дерева в виде графа.
    
    Функция создаёт графическое представление структуры BVH дерева, где узлы
    представляют узлы дерева, а рёбра - связи между родительскими и дочерними узлами.
    
    Parameters
    ----------
    graph : networkx.Graph
        Граф структуры BVH дерева, созданный через BVHTree.build_graph().
    
    Notes
    -----
    Функция пытается использовать graphviz для лучшей визуализации структуры дерева.
    Если graphviz недоступен, используется spring_layout из networkx.
    """
    try:
        pos = nx.nx_agraph.graphviz_layout(graph, prog="dot")
    except:
        pos = nx.spring_layout(graph)

    labels = nx.get_node_attributes(graph, 'label')

    plt.figure(figsize=(12, 8))
    nx.draw(graph, pos, labels=labels, with_labels=True, node_size=350, node_color="lightblue", arrows=False, font_size=6)
    plt.title("BVH Tree Structure", fontsize=12)
    plt.show()
    
if __name__ == '__main__':
    mesh = Mesh("examples/small_sphere_double.dat")
    #mesh = Mesh("examples/sphere_double.dat")
    #mesh = Mesh("examples/bunny_double.dat")
    
    bvh = BVHBuilder(mesh=mesh)
    bvh.prepare_mesh(esc_enable=True)
    bvh.build_tree(face_on_leaf=1, split_func="sah")
    bvh.get_tree_graph()
    plot_graph(bvh.graph)
