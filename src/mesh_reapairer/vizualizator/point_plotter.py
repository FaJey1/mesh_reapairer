from __future__ import annotations

from mpl_toolkits.mplot3d.art3d import Line3DCollection
from typing import List
import matplotlib.pyplot as plt
import numpy as np
from mesh_reapairer.src.mesh_reapairer.msu.mesh import *


def plot_point(ax,
                node: Node,
                color: str = "red",
                linewidths: float = 1) -> None:
    p = node.p
    ax.scatter(p[0], p[1], p[2], color=color, s=linewidths, marker='o')

if __name__ == '__main__':
    mesh = Mesh("examples/small_sphere_double.dat")
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    plot_point(ax, mesh.nodes[0], color="red")
    ax.set_title("Face Visualization")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()