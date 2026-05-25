from __future__ import annotations

import logging
from typing import List

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

from mesh_reapairer.src.mesh_reapairer.msu import Mesh
from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face
from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import Segment
from mesh_reapairer.src.mesh_reapairer.vizualizator.face_plotter import plot_face
from mesh_reapairer.src.mesh_reapairer.vizualizator.segment_plotter import plot_segment

logger = logging.getLogger(__name__)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


def _batch_render_faces(
    ax,
    faces: List[Face],
    color_fn,
    alpha: float,
    edges_enable: bool = False,
    edges_linewidths: float = 0.3,
) -> None:
    """Render all faces in a single Poly3DCollection call."""
    if not faces:
        return
    verts = [np.array(face.points()) for face in faces]
    colors = [color_fn(face) for face in faces]
    col = Poly3DCollection(
        verts,
        alpha=alpha,
        facecolors=colors,
        edgecolors="black" if edges_enable else "none",
        linewidths=edges_linewidths if edges_enable else 0.0,
    )
    ax.add_collection3d(col)


def _batch_render_segments(
    ax,
    segments: List[Segment],
    color: str,
    linewidths: float,
) -> None:
    """Render all segments in a single Line3DCollection call."""
    lines = []
    single_points = []
    for seg in segments:
        if not seg.nodes:
            continue
        if len(seg.nodes) == 1:
            single_points.append(seg.nodes[0])
            continue
        pts = [n.p for n in seg.nodes]
        for i in range(len(pts) - 1):
            lines.append([pts[i], pts[i + 1]])
    if lines:
        col = Line3DCollection(lines, colors=color, linewidths=linewidths)
        ax.add_collection3d(col)
    # Fallback for single-point segments
    for node in single_points:
        ax.scatter(*node.p, color=color, s=linewidths * 5)


def plot_mesh(
    mesh: Mesh,
    faces_enable: bool = True,
    faces_color: str = "",
    edges_enable: bool = False,
    edges_linewidths: float = 0.3,
    aabb_boxes_enable: bool = False,
    faces_label_enable: bool = False,
    faces_alpha: float = 0.3,
    faces_plane_enable: bool = False,
    faces_plane_size: float = 1.0,
    faces_plane_alpha: float = 0.1,
    intersection_segments_enable: bool = False,
    intersection_segments: List[Segment] = [],
    intersection_segments_linewidths: float = 1.0,
    intersection_segments_color: str = "red",
    border_enable: bool = False,
    border_faces: List[Face] = [],
    border_faces_alpha: float = 0.5,
    border_color: str = "blue",
    max_faces: int = 250_000,
) -> None:
    zones = list({zone.name for zone in mesh.zones})
    rand_colors = np.random.rand(len(zones), 3)
    color_map = {z: c for z, c in zip(zones, rand_colors)}

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="3d")

    if faces_enable:
        # Slow per-face path needed only when per-face decorations requested
        need_per_face = faces_label_enable or aabb_boxes_enable or faces_plane_enable
        faces_to_draw = mesh.faces
        if len(faces_to_draw) > max_faces and not need_per_face:
            step = max(1, len(faces_to_draw) // max_faces)
            faces_to_draw = faces_to_draw[::step]
            logger.warning(
                f"Large mesh: rendering {len(faces_to_draw)}/{len(mesh.faces)} faces "
                f"(stride={step}, set max_faces= to adjust)"
            )

        if need_per_face:
            for face in faces_to_draw:
                plot_face(
                    ax=ax,
                    face=face,
                    color=faces_color if faces_color else color_map.get(face.zone.name),
                    edges_enable=edges_enable,
                    edges_linewidths=edges_linewidths,
                    draw_aabb=aabb_boxes_enable,
                    label=faces_label_enable,
                    alpha=faces_alpha,
                    plane=faces_plane_enable,
                    plane_size=faces_plane_size,
                    plane_alpha=faces_plane_alpha,
                )
        else:
            if faces_color:
                color_fn = lambda f: faces_color  # noqa: E731
            else:
                color_fn = lambda f: color_map.get(f.zone.name)  # noqa: E731
            _batch_render_faces(
                ax, faces_to_draw, color_fn, faces_alpha, edges_enable, edges_linewidths
            )

    if intersection_segments_enable:
        if not intersection_segments:
            raise ValueError("mesh_plotter: intersection_segments not set but draw")
        _batch_render_segments(
            ax, intersection_segments, intersection_segments_color, intersection_segments_linewidths
        )

    if border_enable:
        if not border_faces:
            raise ValueError("mesh_plotter: border_faces not set but draw")
        _batch_render_faces(
            ax,
            border_faces,
            lambda f: border_color,
            border_faces_alpha,
            edges_enable,
            edges_linewidths,
        )

    ax.set_title(f"Mesh {mesh.title}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    mesh = Mesh("examples/small_sphere_double.dat")

    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import find_self_intersections

    result = find_self_intersections(mesh)

    border_faces = set()
    intersection_segments = []
    for face_a, face_b, segment in result.valid_pairs:
        border_faces.add(face_a)
        border_faces.add(face_b)
        intersection_segments.append(segment)

    plot_mesh(
        mesh=mesh,
        edges_enable=False,
        faces_enable=True,
        faces_label_enable=False,
        border_enable=True,
        border_color="pink",
        border_faces=list(border_faces),
        border_faces_alpha=0.3,
        intersection_segments_enable=True,
        intersection_segments=intersection_segments,
        intersection_segments_linewidths=4,
    )
