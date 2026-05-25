"""
Triangulation visualization.

Provides:
  plot_face_triangulation  — show one face, its intersection segment,
                             and the resulting sub-triangles (color-coded).
  plot_triangulated_mesh   — show the full mesh with triangulated faces
                             highlighted (before/after inner removal).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Face, Mesh
    from mesh_reapairer.src.mesh_reapairer.restorer.domain.entities import RestorationResult
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.domain.entities import (
        IntersectionResult,
        Segment,
    )

logger = logging.getLogger(__name__)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

_COLORS_SUB = ["#4CAF50", "#2196F3", "#FF9800"]  # 3 sub-triangle colors


# ---------------------------------------------------------------------------
# Single-face triangulation view
# ---------------------------------------------------------------------------


def plot_face_triangulation(
    face: "Face",
    segments: List["Segment"],
    ax=None,
    show: bool = True,
) -> None:
    """
    Visualize a single face with its intersection segments and subdivision.

    Draws:
    - The original face (light grey, dashed outline)
    - The intersection segments (red thick lines)
    - Sub-triangles after splitting (green / blue / orange)

    Args:
        face: The original triangle face.
        segments: Intersection segments on this face.
        ax: Existing Axes3D to draw on (creates new figure if None).
        show: Call plt.show() at the end.
    """
    from mesh_reapairer.restorer.infrastructure.triangulator.face_triangulator import (
        FaceTriangulator,
    )

    if ax is None:
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, projection="3d")

    pts = np.array(face.points())

    # Draw original face outline (dashed grey)
    orig_verts = np.vstack([pts, pts[0]])
    ax.plot(orig_verts[:, 0], orig_verts[:, 1], orig_verts[:, 2],
            "k--", linewidth=1.5, alpha=0.5, label="Original face")

    # Draw intersection segments (red)
    seg_lines = []
    for seg in segments:
        if seg.nodes and len(seg.nodes) >= 2:
            p0 = seg.nodes[0].p
            p1 = seg.nodes[-1].p
            seg_lines.append([p0, p1])
    if seg_lines:
        lc = Line3DCollection(seg_lines, colors="red", linewidths=3)
        ax.add_collection3d(lc)
        # Label segment endpoints
        for line in seg_lines:
            for pt in line:
                ax.scatter(*pt, color="red", s=50, zorder=5)

    # Show sub-triangle decomposition using the triangulator logic
    triangulator = FaceTriangulator(epsilon=1e-6)
    for seg_idx, seg in enumerate(segments):
        if seg.nodes is None or len(seg.nodes) < 2:
            continue
        p1 = seg.nodes[0].p
        p2 = seg.nodes[-1].p
        ei1, _ = triangulator._point_on_face_edge(face, p1)
        ei2, _ = triangulator._point_on_face_edge(face, p2)
        if ei1 < 0 or ei2 < 0 or ei1 == ei2:
            continue

        # Build the 3 sub-triangle polygons (for display only — no mesh mutation)
        i, j = sorted([ei1, ei2])
        V = face.nodes
        Pa = p1 if ei1 <= ei2 else p2
        Pb = p2 if ei1 <= ei2 else p1

        if (i, j) == (0, 1):
            tris = [(Pa, V[1].p, Pb), (V[0].p, Pa, Pb), (V[0].p, Pb, V[2].p)]
        elif (i, j) == (0, 2):
            tris = [(V[0].p, Pa, Pb), (Pa, V[1].p, V[2].p), (Pa, V[2].p, Pb)]
        else:
            tris = [(Pa, V[2].p, Pb), (V[0].p, V[1].p, Pa), (V[0].p, Pa, Pb)]

        for k, tri in enumerate(tris):
            verts = [np.array(pt) if not isinstance(pt, np.ndarray) else pt for pt in tri]
            col = Poly3DCollection(
                [verts],
                alpha=0.4,
                facecolors=_COLORS_SUB[k % len(_COLORS_SUB)],
                edgecolors="black",
                linewidths=0.8,
            )
            ax.add_collection3d(col)

    # Labels
    center = pts.mean(axis=0)
    ax.text(*center, f"F{face.glo_id}", fontsize=9, color="black", ha="center")

    ax.set_title(f"Face {face.glo_id} triangulation ({len(segments)} segment(s))")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    if show:
        plt.tight_layout()
        plt.show()


# ---------------------------------------------------------------------------
# Full mesh triangulation overview
# ---------------------------------------------------------------------------


def plot_triangulated_mesh(
    mesh: "Mesh",
    intersection_result: "IntersectionResult",
    restoration_result: Optional["RestorationResult"] = None,
    max_faces: int = 50_000,
    show: bool = True,
) -> None:
    """
    Visualize the mesh highlighting triangulated boundary faces.

    If restoration_result is provided, shows 3 sub-plots:
      1. Original mesh with intersection faces highlighted
      2. Mesh after triangulation (triangulated faces in color)
      3. Mesh after inner removal (outer surface only)

    Otherwise shows only the single panel.

    Args:
        mesh: The mesh (already restored if restoration_result is given).
        intersection_result: Self-intersection finder output.
        restoration_result: Optional restorer output.
        max_faces: Max faces to render (stride sampling for large meshes).
        show: Call plt.show() at the end.
    """
    if restoration_result is not None:
        _plot_three_panel(mesh, intersection_result, restoration_result, max_faces)
    else:
        _plot_single_panel(mesh, intersection_result, max_faces)

    if show:
        plt.tight_layout()
        plt.show()


def _plot_single_panel(
    mesh: "Mesh",
    intersection_result: "IntersectionResult",
    max_faces: int,
) -> None:
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    intersecting_ids = set(intersection_result.face_intersections.keys())
    _draw_mesh_batch(ax, mesh, intersecting_ids, max_faces)
    _draw_segments_batch(ax, intersection_result)

    ax.set_title(
        f"Mesh with intersections: {len(intersecting_ids)} faces, "
        f"{len(intersection_result.valid_pairs)} segments"
    )
    _set_labels(ax)


def _plot_three_panel(
    mesh: "Mesh",
    intersection_result: "IntersectionResult",
    restoration_result: "RestorationResult",
    max_faces: int,
) -> None:
    fig = plt.figure(figsize=(18, 6))

    intersecting_ids = set(intersection_result.face_intersections.keys())
    outer_ids = restoration_result.outer_face_ids

    # Panel 1: highlight intersection faces
    ax1 = fig.add_subplot(131, projection="3d")
    _draw_mesh_batch(ax1, mesh, intersecting_ids, max_faces)
    _draw_segments_batch(ax1, intersection_result)
    ax1.set_title(f"Before: {len(mesh.faces)} faces\n{len(intersecting_ids)} intersecting")
    _set_labels(ax1)

    # Panel 2: triangulated faces highlighted (orange)
    ax2 = fig.add_subplot(132, projection="3d")
    tri_ids = restoration_result.triangulated_face_ids
    _draw_mesh_batch(ax2, mesh, tri_ids, max_faces, highlight_color="#FF9800")
    _draw_segments_batch(ax2, intersection_result)
    ax2.set_title(
        f"After triangulation\n{restoration_result.new_faces_created} new faces"
    )
    _set_labels(ax2)

    # Panel 3: outer surface after removal
    ax3 = fig.add_subplot(133, projection="3d")
    outer_faces = [f for f in mesh.faces if f.glo_id in outer_ids]
    _draw_faces_batch(ax3, outer_faces, max_faces, color="#4CAF50", alpha=0.5)
    ax3.set_title(
        f"After removal: {restoration_result.outer_faces_count} outer faces\n"
        f"({restoration_result.faces_removed} removed)"
    )
    _set_labels(ax3)


# ---------------------------------------------------------------------------
# Internal batch helpers
# ---------------------------------------------------------------------------

def _draw_mesh_batch(
    ax,
    mesh: "Mesh",
    highlight_ids: set,
    max_faces: int,
    highlight_color: str = "pink",
) -> None:
    """Draw mesh: regular faces in grey, highlighted faces in highlight_color."""
    regular = [f for f in mesh.faces if f.glo_id not in highlight_ids]
    highlighted = [f for f in mesh.faces if f.glo_id in highlight_ids]

    # Stride sample for large meshes
    if len(regular) > max_faces:
        step = max(1, len(regular) // max_faces)
        regular = regular[::step]

    _draw_faces_batch(ax, regular, max_faces, color="#CCCCCC", alpha=0.15)
    _draw_faces_batch(ax, highlighted, max_faces, color=highlight_color, alpha=0.6)


def _draw_faces_batch(
    ax, faces: list, max_faces: int, color: str = "#CCCCCC", alpha: float = 0.3
) -> None:
    if not faces:
        return
    verts = [np.array(f.points()) for f in faces]
    col = Poly3DCollection(
        verts, alpha=alpha, facecolors=color, edgecolors="none"
    )
    ax.add_collection3d(col)


def _draw_segments_batch(ax, intersection_result: "IntersectionResult") -> None:
    lines = []
    for _, _, seg in intersection_result.valid_pairs:
        if seg.nodes and len(seg.nodes) >= 2:
            lines.append([seg.nodes[0].p, seg.nodes[-1].p])
    if lines:
        lc = Line3DCollection(lines, colors="red", linewidths=2)
        ax.add_collection3d(lc)


def _set_labels(ax) -> None:
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")


__all__ = [
    "plot_face_triangulation",
    "plot_triangulated_mesh",
]
