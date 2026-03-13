from __future__ import annotations

from mesh_reapairer.vizualizator.point_plotter import *
from mesh_reapairer.vizualizator.line_plotter import *


def plot_segment(ax,
                nodes: List[Node],
                color: str = "red",
                linewidths: float = 1) -> None:
    if len(nodes) == 1:
        plot_point(ax, node=nodes[0], color=color, linewidths=linewidths)
        return
    plot_line(ax, nodes=nodes, color=color, linewidths=linewidths)


if __name__ == '__main__':
    mesh = Mesh("examples/small_sphere_double.dat")
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    plot_segment(ax, [mesh.nodes[0],mesh.nodes[1]], color="red")
    plot_segment(ax, [mesh.nodes[2]], color="red")
    ax.set_title("Face Visualization")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()
