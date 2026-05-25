"""
Full pipeline visualization: 5 panels showing each stage.

Usage:
    python scripts/visualize_pipeline.py [path/to/mesh.dat]

Panels:
  1. Original mesh
  2. Intersection graph J(M,W)
  3. Intersecting cells with segments
  4. Mesh after triangulation (new cells highlighted)
  5. Final mesh after inner removal
"""
from __future__ import annotations

import copy
import logging
import sys

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

logging.disable(logging.CRITICAL)


def _draw_faces(ax, faces, color="#CCCCCC", alpha=0.25, edges=True, edge_lw=0.3):
    if not faces:
        return
    verts = [np.array(f.points()) for f in faces]
    col = Poly3DCollection(
        verts, alpha=alpha, facecolors=color,
        edgecolors="black" if edges else "none",
        linewidths=edge_lw,
    )
    ax.add_collection3d(col)


def _draw_segments(ax, pairs, color="red", lw=2):
    lines = []
    for _, _, seg in pairs:
        if seg.nodes and len(seg.nodes) >= 2:
            lines.append([seg.nodes[0].p, seg.nodes[-1].p])
    if lines:
        ax.add_collection3d(Line3DCollection(lines, colors=color, linewidths=lw))


def _set_axes(ax, all_pts, title):
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("X", fontsize=7); ax.set_ylabel("Y", fontsize=7); ax.set_zlabel("Z", fontsize=7)
    ax.tick_params(labelsize=6)
    if len(all_pts):
        mn, mx = all_pts.min(0), all_pts.max(0)
        mid = (mn + mx) / 2
        r = max((mx - mn).max() / 2, 1e-3)
        ax.set_xlim(mid[0]-r, mid[0]+r)
        ax.set_ylim(mid[1]-r, mid[1]+r)
        ax.set_zlim(mid[2]-r, mid[2]+r)


def main():
    dat_file = sys.argv[1] if len(sys.argv) > 1 else "examples/small_sphere_double.dat"

    # ── Load & run pipeline ───────────────────────────────────────────────
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import find_self_intersections
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.infrastructure.repairer import (
        EdgeType,
    )
    from mesh_reapairer.restorer.infrastructure.triangulator.face_triangulator import (
        FaceTriangulator,
    )
    from mesh_reapairer.restorer.infrastructure.inner_remover.mesh_walker import (
        MeshWalker,
    )

    print(f"Loading {dat_file}…")
    mesh_orig = Mesh()
    mesh_orig.load(dat_file)

    # Keep a snapshot of original face coords for panel 1
    orig_pts = np.array([n.p for n in mesh_orig.nodes])

    print("Finding intersections…")
    result = find_self_intersections(mesh_orig)
    intersecting_ids = set(result.face_intersections.keys())
    print(f"  {len(result.valid_pairs)} pairs, {len(intersecting_ids)} faces")

    # --- snapshot mesh state after intersection (before triangulation) ---
    mesh_pre = mesh_orig          # same object, will be mutated below

    print("Triangulating…")
    tri = FaceTriangulator()
    ft, nf_count, ns = tri.triangulate_all(mesh_pre, result)
    print(f"  {ft} faces triangulated → {nf_count} new faces")

    # IDs that exist only after triangulation (the new sub-triangles)
    orig_ids_after_tri = {f.glo_id for f in mesh_pre.faces} - intersecting_ids
    new_tri_ids = set()
    for f in mesh_pre.faces:
        if f.glo_id not in {ff.glo_id for ff in mesh_orig.faces}:
            new_tri_ids.add(f.glo_id)

    # All faces after triangulation
    faces_after_tri = list(mesh_pre.faces)

    print("Removing inner faces…")
    walker = MeshWalker()
    removed, kept = walker.remove_inner_faces(mesh_pre)
    print(f"  removed={removed}, outer kept={kept}")

    mesh_pre.delete_faces_free_edges()
    mesh_pre.delete_isolated_nodes()
    outer_faces = list(mesh_pre.faces)
    print(f"Final mesh: {len(outer_faces)} faces")

    # ── Collect all mesh node positions for axis scaling ─────────────────
    all_pts = orig_pts  # use original extent

    # ── Figure setup: 1 row × 5 panels ───────────────────────────────────
    fig = plt.figure(figsize=(22, 5))
    fig.suptitle(f"Repair pipeline — {dat_file}", fontsize=11)

    axes = [fig.add_subplot(1, 5, i+1, projection="3d") for i in range(5)]

    # ── Panel 1: Original mesh ────────────────────────────────────────────
    ax = axes[0]
    # Re-load original mesh for clean rendering
    m0 = Mesh(); m0.load(dat_file)
    _draw_faces(ax, m0.faces, color="#90CAF9", alpha=0.4)
    _set_axes(ax, all_pts, f"1. Original\n{len(m0.faces)} faces")

    # ── Panel 2: Intersection graph J(M,W) ────────────────────────────────
    ax = axes[1]
    try:
        from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.infrastructure.repairer.intersection_graph import (
            IntersectionGraph,
        )
        graph = result.intersection_graph if hasattr(result, "intersection_graph") else None
    except Exception:
        graph = None

    # Draw all mesh faces faintly
    m1 = Mesh(); m1.load(dat_file)
    _draw_faces(ax, m1.faces, color="#CCCCCC", alpha=0.1, edges=False)

    # Draw graph edges
    if graph is not None:
        alpha_lines, beta_lines, recovered_lines = [], [], []
        for edge_id, edge in graph.edges.items():
            n1 = graph.nodes.get(edge.node1_id)
            n2 = graph.nodes.get(edge.node2_id)
            if n1 is None or n2 is None:
                continue
            seg = [n1.point, n2.point]
            if edge.edge_type == EdgeType.RECOVERED:
                recovered_lines.append(seg)
            elif edge.edge_type == EdgeType.ALPHA:
                alpha_lines.append(seg)
            else:
                beta_lines.append(seg)

        if alpha_lines:
            ax.add_collection3d(Line3DCollection(alpha_lines, colors="green", linewidths=2, label="α"))
        if beta_lines:
            ax.add_collection3d(Line3DCollection(beta_lines, colors="orange", linewidths=1.5, linestyles="dashed", label="β"))
        if recovered_lines:
            ax.add_collection3d(Line3DCollection(recovered_lines, colors="red", linewidths=2.5, label="recovered"))

        # Draw nodes as scatter
        node_pts = np.array([n.point for n in graph.nodes.values()])
        if len(node_pts):
            ax.scatter(node_pts[:,0], node_pts[:,1], node_pts[:,2], c="blue", s=15, zorder=5)
    else:
        # Fall back: just draw segments
        _draw_segments(ax, result.valid_pairs, color="red")

    _set_axes(ax, all_pts, f"2. Intersection graph\n{len(result.valid_pairs)} segments")

    # ── Panel 3: Intersecting cells + segments ────────────────────────────
    ax = axes[2]
    m2 = Mesh(); m2.load(dat_file)
    face_map2 = {f.glo_id: f for f in m2.faces}

    regular = [f for f in m2.faces if f.glo_id not in intersecting_ids]
    highlighted = [f for f in m2.faces if f.glo_id in intersecting_ids]

    _draw_faces(ax, regular, color="#CCCCCC", alpha=0.1, edges=False)
    _draw_faces(ax, highlighted, color="#FF8A80", alpha=0.7, edges=True, edge_lw=0.5)
    _draw_segments(ax, result.valid_pairs, color="red", lw=2)
    _set_axes(ax, all_pts, f"3. Intersecting cells\n{len(highlighted)} cells, {len(result.valid_pairs)} segs")

    # ── Panel 4: After triangulation ──────────────────────────────────────
    ax = axes[3]
    # faces_after_tri is the mesh state before removal
    tri_ids_set = {f.glo_id for f in faces_after_tri} - {f.glo_id for f in m2.faces}
    regular4 = [f for f in faces_after_tri if f.glo_id not in tri_ids_set and f.glo_id not in intersecting_ids]
    new4 = [f for f in faces_after_tri if f.glo_id in tri_ids_set]

    _draw_faces(ax, regular4, color="#CCCCCC", alpha=0.1, edges=False)
    _draw_faces(ax, new4, color="#A5D6A7", alpha=0.7, edges=True, edge_lw=0.5)
    _draw_segments(ax, result.valid_pairs, color="red", lw=1.5)
    _set_axes(ax, all_pts, f"4. After triangulation\n{ft} split, {nf_count} new cells")

    # ── Panel 5: Final outer surface ──────────────────────────────────────
    ax = axes[4]
    _draw_faces(ax, outer_faces, color="#4CAF50", alpha=0.6, edges=True, edge_lw=0.3)
    _set_axes(ax, all_pts, f"5. Outer surface\n{len(outer_faces)} faces ({removed} removed)")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
