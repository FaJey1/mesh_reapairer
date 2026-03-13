from __future__ import annotations

from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

import matplotlib.pyplot as plt
import numpy as np
from mesh_reapairer.msu.mesh import *

from mesh_reapairer.vizualizator.plane_plotter import *


def plot_face(ax,
               face: Face, 
               color: str = "blue", 
               edges_enable: bool = False,
               edges_linewidths: float = 0.3,
               draw_aabb: bool = False,
               label: bool = False,
               alpha: bool = 0.3,
               plane: bool = False,
               plane_size: float =0.5,
               plane_alpha: float =0.1) -> None:
    coords = np.array(face.points())
    poly_collection = Poly3DCollection(
        [coords],
        alpha=alpha,
        facecolors=color,
        edgecolors="black" if edges_enable else "none",
        linewidths=edges_linewidths if edges_enable else 0.0
    )
    ax.add_collection3d(poly_collection)
    
    if draw_aabb:
        _min = coords.min(axis=0)
        _max = coords.max(axis=0)
        
        x, y, z = _min
        X, Y, Z = _max
        v = np.array([
            [x, y, z], [X, y, z], [X, Y, z], [x, Y, z], # нижняя грань
            [x, y, Z], [X, y, Z], [X, Y, Z], [x, Y, Z]  # верхняя грань
        ])
        
        edges = [
            [v[0], v[1]], [v[1], v[2]], [v[2], v[3]], [v[3], v[0]], # низ
            [v[4], v[5]], [v[5], v[6]], [v[6], v[7]], [v[7], v[4]], # верх
            [v[0], v[4]], [v[1], v[5]], [v[2], v[6]], [v[3], v[7]]  # вертикали
        ]
        
        line_collection = Line3DCollection(edges, colors='red', linewidths=0.8, linestyles='--')
        ax.add_collection3d(line_collection)
    
    if label:
        center = coords.mean(axis=0)
        ax.text(center[0], center[1], center[2], 
                s=face.glo_id,
                color='black',
                fontsize=8,
                fontweight='bold')
        
    if plane:
        plot_plane(ax=ax, face=face, color=color, alpha=plane_alpha, size=plane_size)

if __name__ == '__main__':
    mesh = Mesh("examples/small_sphere_double.dat")
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    plot_face(ax, mesh.faces[0], color="blue", edge_enable=True, draw_aabb=True, label=True, plane=True)
    ax.set_title("Face Visualization")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()