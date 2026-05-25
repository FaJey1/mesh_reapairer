"""
Визуализация результатов поиска самопересечений.

Показывает:
- Полную сетку с полупрозрачными гранями
- Граничные ячейки (с пересечениями) выделенным цветом
- Сегменты пересечений
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Mesh
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import IntersectionResult

logger = logging.getLogger(__name__)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

_MAX_FACES_DEFAULT = 50_000


def _batch_faces(
    ax,
    faces,
    color_fn,
    alpha: float,
    edges_enable: bool = False,
    edges_linewidths: float = 0.3,
) -> None:
    if not faces:
        return
    verts = [np.array(f.points()) for f in faces]
    colors = [color_fn(f) for f in faces]
    col = Poly3DCollection(
        verts,
        alpha=alpha,
        facecolors=colors,
        edgecolors="black" if edges_enable else "none",
        linewidths=edges_linewidths if edges_enable else 0.0,
    )
    ax.add_collection3d(col)


def _batch_segments(ax, segments, color: str, linewidth: float) -> None:
    lines = []
    for seg in segments:
        if not seg.nodes or len(seg.nodes) < 2:
            continue
        pts = [n.p for n in seg.nodes]
        for i in range(len(pts) - 1):
            lines.append([pts[i], pts[i + 1]])
    if lines:
        col = Line3DCollection(lines, colors=color, linewidths=linewidth)
        ax.add_collection3d(col)


def _make_zone_color_fn(mesh: "Mesh"):
    zones = list({zone.name for zone in mesh.zones})
    rand_colors = np.random.rand(len(zones), 3)
    color_map = {z: c for z, c in zip(zones, rand_colors)}
    return lambda f: color_map.get(f.zone.name)


def plot_intersection_result(
    mesh: "Mesh",
    result: "IntersectionResult",
    show_all_faces: bool = True,
    show_border_faces: bool = True,
    show_segments: bool = True,
    faces_alpha: float = 0.1,
    border_alpha: float = 0.5,
    border_color: str = "pink",
    segment_color: str = "red",
    segment_linewidth: float = 3.0,
    title: str | None = None,
    max_faces: int = _MAX_FACES_DEFAULT,
) -> None:
    """
    Визуализировать результаты поиска самопересечений.

    Args:
        mesh: Треугольная сетка
        result: Результат поиска пересечений (IntersectionResult)
        show_all_faces: Показывать все грани сетки (полупрозрачные)
        show_border_faces: Показывать граничные грани (с пересечениями)
        show_segments: Показывать сегменты пересечений
        faces_alpha: Прозрачность обычных граней
        border_alpha: Прозрачность граничных граней
        border_color: Цвет граничных граней
        segment_color: Цвет сегментов пересечений
        segment_linewidth: Толщина линий сегментов
        title: Заголовок графика (по умолчанию генерируется автоматически)
        max_faces: Максимальное число граней для отрисовки (stride-sampling при превышении)
    """
    border_faces = set()
    for face_a, face_b, segment in result.valid_pairs:
        border_faces.add(face_a)
        border_faces.add(face_b)
    segments = [segment for _, _, segment in result.valid_pairs]

    logger.info(f"Visualizing: {len(border_faces)} border faces, {len(segments)} segments")

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection="3d")

    # 1. All faces (semi-transparent, batch)
    if show_all_faces:
        color_fn = _make_zone_color_fn(mesh)
        faces_to_draw = mesh.faces
        if len(faces_to_draw) > max_faces:
            step = max(1, len(faces_to_draw) // max_faces)
            faces_to_draw = faces_to_draw[::step]
            logger.warning(
                f"Large mesh: rendering {len(faces_to_draw)}/{len(mesh.faces)} faces "
                f"(stride={step})"
            )
        _batch_faces(ax, faces_to_draw, color_fn, faces_alpha)

    # 2. Border faces (with intersections, batch)
    if show_border_faces:
        _batch_faces(
            ax,
            list(border_faces),
            lambda f: border_color,
            border_alpha,
            edges_enable=True,
            edges_linewidths=0.5,
        )

    # 3. Intersection segments (batch Line3DCollection)
    if show_segments:
        _batch_segments(ax, segments, segment_color, segment_linewidth)

    if title is None:
        title = (
            f"Intersection Result: {len(result.valid_pairs)} intersections, "
            f"{len(result.impossible_pairs)} impossible, "
            f"{len(result.parallel_rejected)} parallel rejected"
        )

    ax.set_title(title)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    plt.tight_layout()
    plt.show()


def plot_intersection_result_multi(
    mesh: "Mesh",
    result: "IntersectionResult",
    max_faces: int = _MAX_FACES_DEFAULT,
) -> None:
    """
    Визуализировать результаты в 2 подграфиках:
    1. Полная сетка + сегменты пересечений
    2. Только граничные грани + сегменты (valid)

    Args:
        mesh: Треугольная сетка
        result: Результат поиска пересечений
        max_faces: Максимальное число граней для отрисовки
    """
    fig = plt.figure(figsize=(14, 6))

    color_fn = _make_zone_color_fn(mesh)
    faces_to_draw = mesh.faces
    if len(faces_to_draw) > max_faces:
        step = max(1, len(faces_to_draw) // max_faces)
        faces_to_draw = faces_to_draw[::step]

    # 1. Full mesh with intersection segments
    ax1 = fig.add_subplot(121, projection="3d")
    _batch_faces(ax1, faces_to_draw, color_fn, alpha=0.3)
    _batch_segments(ax1, [s for _, _, s in result.valid_pairs], "red", 2.0)
    ax1.set_title(f"Full Mesh ({len(mesh.faces)} faces)")

    # 2. Border faces + segments
    ax2 = fig.add_subplot(122, projection="3d")
    border_faces = set()
    for face_a, face_b, _ in result.valid_pairs:
        border_faces.add(face_a)
        border_faces.add(face_b)
    _batch_faces(ax2, list(border_faces), lambda f: "green", 0.5, edges_enable=True)
    _batch_segments(ax2, [s for _, _, s in result.valid_pairs], "red", 3.0)
    ax2.set_title(f"Valid Intersections ({len(result.valid_pairs)})")

    plt.tight_layout()
    plt.show()


__all__ = [
    "plot_intersection_result",
    "plot_intersection_result_multi",
]
