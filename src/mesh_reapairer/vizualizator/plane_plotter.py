from __future__ import annotations

from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

import matplotlib.pyplot as plt
import numpy as np
from mesh_reapairer.src.mesh_reapairer.msu.mesh import *


def plot_plane(ax,
               face: Face, 
               color: str = "blue",
               alpha: float = 0.05,
               size: float = 1.0) -> None:
    center = np.array(face.center())
    if face.normal is None:
        face.calculate_normal()
    
    # Выбираем вспомогательный вектор для поиска тангенса
    tangent = np.array([1, 0, 0]) if abs(face.normal[0]) < 0.9 else np.array([0, 1, 0])
    u = np.cross(face.normal, tangent)
    u /= np.linalg.norm(u)
    v = np.cross(face.normal, u)
    
    # Устанавливаем соотношение сторон 1:2
    # d_u — короткая сторона, d_v — длинная сторона
    d_u = size 
    d_v = size
    
    plane_verts = np.array([
        center - d_u*u - d_v*v,
        center + d_u*u - d_v*v,
        center + d_u*u + d_v*v,
        center - d_u*u + d_v*v
    ])
    
    plane_collection = Poly3DCollection(
        [plane_verts],
        alpha=alpha,
        facecolors=color,
        edgecolors=color,
        linewidths=0.5
    )
    ax.add_collection3d(plane_collection)


if __name__ == '__main__':
    mesh = Mesh("examples/small_sphere_double.dat")
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    plot_plane(ax, mesh.faces[0], color="blue")
    ax.set_title("Face Visualization")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()