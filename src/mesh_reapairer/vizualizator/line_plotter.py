from __future__ import annotations

from mpl_toolkits.mplot3d.art3d import Line3DCollection
from typing import List
import matplotlib.pyplot as plt
import numpy as np
from mesh_reapairer.src.mesh_reapairer.msu.mesh import *


def plot_line(ax,
                nodes: List[Node],
                color: str = "red",
                linewidths: float = 1) -> None:
    edge = [nodes[0].p, nodes[1].p]
    line_collection = Line3DCollection([edge], color=color, linewidths=linewidths)
    ax.add_collection3d(line_collection)

if __name__ == '__main__':
    mesh = Mesh("examples/small_sphere_double.dat")
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    plot_line(ax, [mesh.nodes[0],mesh.nodes[1]], color="red")
    ax.set_title("Face Visualization")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()