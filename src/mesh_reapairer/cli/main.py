"""
mesh-reapairer CLI — detect and repair self-intersections in polygonal meshes.

Usage examples:
    mesh-reapairer examples/bunny_double.dat results/bunny.json
    mesh-reapairer examples/sphere_double.dat results/sphere.json --visualize
    mesh-reapairer examples/small_sphere_double.dat results/out.json \\
        --log-level DEBUG --visualize --intersection-graph
    mesh-reapairer examples/dragon_double.dat results/dragon.json \\
        --log-level info --visualize --intersection-graph \\
        --demo-remove-segments 10 --epsilon 1e-7
    mesh-reapairer examples/sphere_double.dat --visualize --visualize-mode separate
    mesh-reapairer examples/sphere_double.dat --visualize \\
        --visualize-config visualize-config.json
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import click


# ── Visual configuration ───────────────────────────────────────────────────────

@dataclass
class VisualConfig:
    """All visual parameters for the pipeline visualization."""
    # ── Figure layout ─────────────────────────────────────────────────────────
    figure_width: float = 24.0
    figure_height: float = 5.0
    figure_dpi: int = 100
    suptitle_fontsize: int = 10

    # ── Single-panel window size (used in 'separate' mode) ────────────────────
    single_panel_width: float = 10.0
    single_panel_height: float = 8.0

    # ── Panel 1 — Original mesh ───────────────────────────────────────────────
    original_face_color: str = "#90CAF9"
    original_face_alpha: float = 0.4

    # ── Panel 2 — Background faces (shown faintly in panels 2–4) ─────────────
    background_face_color: str = "#CCCCCC"
    background_face_alpha: float = 0.08

    # ── Panel 3 — Intersecting / highlighted faces ────────────────────────────
    highlighted_face_color: str = "#FF8A80"
    highlighted_face_alpha: float = 0.7

    # ── Panel 4 — New triangles after triangulation ───────────────────────────
    new_face_color: str = "#A5D6A7"
    new_face_alpha: float = 0.70
    kept_face_color: str = "#CCCCCC"
    kept_face_alpha: float = 0.10

    # ── Panel 5 — Outer surface ───────────────────────────────────────────────
    outer_face_color: str = "#4CAF50"
    outer_face_alpha: float = 0.6

    # ── Panel 7 — Inner faces (shown before removal) ──────────────────────────
    inner_face_color: str = "#FFCCBC"
    inner_face_alpha: float = 0.35

    # ── Face edges (wireframe overlay) ────────────────────────────────────────
    face_edges_show: bool = True
    face_edge_color: str = "black"
    face_edge_linewidth: float = 0.3

    # ── Intersection segments ─────────────────────────────────────────────────
    segment_color: str = "red"
    segment_linewidth: float = 2.0
    # reduced linewidth used in panel 4 (after-triangulation)
    segment_linewidth_panel4: float = 1.0

    # ── Intersection graph (panel 2) ──────────────────────────────────────────
    graph_alpha_color: str = "green"
    graph_alpha_linewidth: float = 2.0
    graph_beta_color: str = "orange"
    graph_beta_linewidth: float = 1.2
    graph_beta_linestyle: str = "dashed"
    graph_recovered_color: str = "red"
    graph_recovered_linewidth: float = 2.5
    graph_node_color: str = "blue"
    graph_node_size: float = 12.0

    # ── Axis labels and titles ────────────────────────────────────────────────
    axis_label_fontsize: int = 6
    tick_fontsize: int = 5
    panel_title_fontsize: int = 8
    panel_title_pad: float = 4.0

    # ── Custom panel titles (use {placeholders} for dynamic values) ───────────
    # Available placeholders:
    #   panel1: {n_faces}
    #   panel2: {n_segments}
    #   panel3: {n_highlighted}
    #   panel4: {n_split}, {n_new}
    #   panel5: {n_faces}, {n_removed}
    panel1_title: str = "1. Original\n{n_faces} faces"
    panel2_title: str = "2. Intersection graph\n{n_segments} segments"
    panel3_title: str = "3. Intersecting cells\n{n_highlighted} highlighted"
    panel4_title: str = "4. After triangulation\n{n_split} split → {n_new} new"
    panel5_title: str = "5. Outer surface\n{n_faces} faces ({n_removed} removed)"


def _load_visual_config(path: Optional[Path]) -> VisualConfig:
    """Load VisualConfig from a JSON file; unknown keys are silently ignored."""
    cfg = VisualConfig()
    if path is None:
        return cfg
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for key, val in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, val)
            else:
                logging.getLogger("mesh_reapairer.cli").warning(
                    f"visualize-config: unknown key '{key}' — ignored"
                )
    except Exception as exc:
        raise click.ClickException(f"Cannot read --visualize-config: {exc}") from exc
    return cfg


# ── Logging setup ─────────────────────────────────────────────────────────────

def _setup_logging(log_level: str, log_file: Path | None, quiet: bool) -> None:
    fmt = "[%(asctime)s] [%(name)s.%(funcName)s] %(levelname)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    numeric = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = []
    if not quiet:
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(numeric)
        h.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        handlers.append(h)
    if log_file:
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setLevel(numeric)
        fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        handlers.append(fh)

    logging.basicConfig(level=numeric, handlers=handlers, format=fmt,
                        datefmt=datefmt, force=True)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


# ── CLI definition ─────────────────────────────────────────────────────────────

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="INPUT",
)
@click.argument(
    "output_file",
    required=False,
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    metavar="OUTPUT",
)
# ── Intersection detection ────────────────────────────────────────────────────
@click.option(
    "--epsilon", "-e",
    type=float, default=1e-10, show_default=True,
    help="Geometric tolerance for intersection tests.",
)
@click.option(
    "--interpolation-mode",
    type=click.Choice(["vertices", "edges"], case_sensitive=False),
    default="vertices", show_default=True,
    help="Intersection graph interpolation mode.",
)
@click.option(
    "--demo-remove-segments",
    type=click.FloatRange(0.0, 100.0),
    default=0.0, show_default=True,
    metavar="PCT",
    help="DEMO: randomly drop PCT% of intersection segments to stress-test graph recovery.",
)
# ── Restoration ───────────────────────────────────────────────────────────────
@click.option(
    "--restore/--no-restore",
    default=True, show_default=True,
    help="Запустить триангуляцию + удаление внутренних граней после обнаружения.",
)
@click.option(
    "--inner-removal/--no-inner-removal",
    default=True, show_default=True,
    help="Удалять внутренние грани после триангуляции (требует --restore).",
)
@click.option(
    "--cleanup/--no-cleanup",
    default=True, show_default=True,
    help="Очищать свободные рёбра и изолированные вершины после восстановления.",
)
@click.option(
    "--save-result",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None, metavar="PATH",
    help=(
        "Сохранить восстановленную сетку в файл .dat (формат MSU). "
        "Используется mesh.store() — полное сохранение топологии и данных."
    ),
)
# ── Visualization ─────────────────────────────────────────────────────────────
@click.option(
    "--visualize", "-v",
    is_flag=True, default=False,
    help="Show 5-panel pipeline visualization after processing.",
)
@click.option(
    "--intersection-graph", "-g",
    is_flag=True, default=False,
    help="Show the intersection graph J(M,W) before and after recovery.",
)
@click.option(
    "--show-intersecting-cells",
    is_flag=True, default=False,
    help="Show only the intersecting cells + segments (no full pipeline).",
)
@click.option(
    "--visualize-mode",
    type=str,
    default="combined", show_default=True,
    help=(
        "combined — all 8 panels in one figure; "
        "separate — each panel in its own window; "
        "1,3,5 — only the specified panel numbers (1-8)."
    ),
)
@click.option(
    "--visualize-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None, metavar="JSON",
    help="JSON file with visual style overrides (colors, linewidths, alpha, etc.).",
)
# ── Logging ───────────────────────────────────────────────────────────────────
@click.option(
    "--log-level", "-l",
    type=click.Choice(["debug", "info", "warning", "error", "critical"],
                      case_sensitive=False),
    default="info", show_default=True,
    help="Console/file logging verbosity.",
)
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write logs to FILE (in addition to stdout).",
)
@click.option(
    "--quiet", "-q",
    is_flag=True, default=False,
    help="Suppress stdout logging (use with --log-file).",
)
def main(
    input_file: Path,
    output_file: Path | None,
    epsilon: float,
    interpolation_mode: str,
    demo_remove_segments: float,
    restore: bool,
    inner_removal: bool,
    cleanup: bool,
    save_result: Path | None,
    visualize: bool,
    intersection_graph: bool,
    show_intersecting_cells: bool,
    visualize_mode: str,
    visualize_config: Path | None,
    log_level: str,
    log_file: Path | None,
    quiet: bool,
) -> None:
    """
    Detect and repair self-intersections in a polygonal mesh.

    \b
    INPUT   Path to the input mesh (.dat format).
    OUTPUT  Path for the repaired mesh/stats (.json or .dat).
            If omitted, results are only shown in the terminal.

    \b
    Pipeline stages:
      1. Load mesh
      2. Find self-intersections (BVH + Skorkovska classification)
      3. Recover intersection graph J(M,W)
      4. Triangulate faces along intersection lines       [--restore]
      5. Remove inner faces (BFS walk)                   [--inner-removal]
      6. Save result                                     [OUTPUT]

    \b
    Examples:
      mesh-reapairer examples/small_sphere_double.dat
      mesh-reapairer examples/bunny_double.dat results/bunny.json --log-level info
      mesh-reapairer examples/dragon_double.dat results/dragon.json \\
          --log-level info --visualize --intersection-graph
      mesh-reapairer examples/sphere_double.dat results/sphere.json \\
          --demo-remove-segments 10 --epsilon 1e-7 --visualize
    """
    # ── Logging ───────────────────────────────────────────────────────────────
    _setup_logging(log_level, log_file, quiet)
    logger = logging.getLogger("mesh_reapairer.cli")

    # ── Late imports (after logging is configured) ────────────────────────────
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
    from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import (
        find_self_intersections,
        SelfIntersectionFinderConfig,
        GraphRecoveryConfig,
        IntersectionConfig,
        BVHConfig,
    )
    from mesh_reapairer.src.mesh_reapairer.restorer import restore_mesh as _restore_mesh
    from mesh_reapairer.src.mesh_reapairer.restorer.application.config import RestorerConfig

    t0_total = time.time()

    # ── 1. Load mesh ──────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"Input : {input_file}")
    if output_file:
        logger.info(f"Output: {output_file}")
    logger.info("=" * 60)

    mesh = Mesh()
    mesh.load(str(input_file))
    n_faces_orig = len(mesh.faces)
    n_nodes_orig = len(mesh.nodes)
    logger.info(f"Loaded: {n_faces_orig} faces, {n_nodes_orig} nodes")

    # ── 2. Find intersections ─────────────────────────────────────────────────
    cfg = SelfIntersectionFinderConfig(
        bvh=BVHConfig(),
        intersection=IntersectionConfig(epsilon=epsilon),
        recovery=GraphRecoveryConfig(interpolation_mode=interpolation_mode),
    )

    if demo_remove_segments > 0.0:
        logger.warning(
            f"DEMO MODE: randomly dropping {demo_remove_segments:.1f}%% of segments"
        )

    result = find_self_intersections(
        mesh=mesh,
        config=cfg,
        enable_visualization=intersection_graph,
        demo_remove_segments_percent=demo_remove_segments,
    )

    n_pairs = len(result.valid_pairs)
    n_affected = len(result.face_intersections)
    logger.info(f"Found {n_pairs} intersection pairs across {n_affected} faces")

    if n_pairs == 0:
        click.echo("No self-intersections found — mesh is clean.")
        _write_output(output_file, mesh, result, None, logger)
        return

    # Optional cell view only
    if show_intersecting_cells:
        _show_cells(mesh, result)
        return

    # ── 3. Restore ────────────────────────────────────────────────────────────
    restoration = None
    if restore:
        rcfg = RestorerConfig(
            epsilon=epsilon,
            enable_inner_removal=inner_removal,
            enable_cleanup=cleanup,
        )
        restoration = _restore_mesh(mesh=mesh, intersection_result=result, config=rcfg)
        logger.info(
            f"Restored: triangulated={restoration.faces_triangulated}, "
            f"new_faces={restoration.new_faces_created}, "
            f"removed={restoration.faces_removed}, "
            f"outer={restoration.outer_faces_count}"
        )
        logger.info(f"Final mesh: {len(mesh.faces)} faces, {len(mesh.nodes)} nodes")

    elapsed = time.time() - t0_total
    logger.info(f"Total time: {elapsed*1000:.1f} ms")

    # ── 4. Сохранение восстановленной сетки в .dat ────────────────────────────
    if save_result is not None:
        _save_mesh_dat(save_result, mesh, logger)

    # ── 5. Visualize ──────────────────────────────────────────────────────────
    if visualize:
        vcfg = _load_visual_config(visualize_config)
        _show_pipeline(input_file, result, restoration, mesh, vcfg, visualize_mode)

    # ── 6. Save JSON stats ────────────────────────────────────────────────────
    _write_output(output_file, mesh, result, restoration, logger)
    click.echo(
        f"Done. {n_pairs} intersections | "
        f"{len(mesh.faces)} faces remaining"
        + (f" | {elapsed*1000:.0f} ms" if elapsed < 600 else "")
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_mesh_dat(path: Path, mesh, logger) -> None:
    """Сохранить восстановленную сетку в файл .dat средствами MSU."""
    path = Path(path)
    if path.suffix.lower() != ".dat":
        raise click.ClickException(
            f"--save-result: ожидается расширение .dat, получено '{path.suffix}'"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.store(str(path))
    logger.info(f"Восстановленная сетка сохранена → {path}")


def _write_output(output_file, mesh, result, restoration, logger) -> None:
    if output_file is None:
        return
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if output_file.suffix == ".json":
        data: dict = {
            "mesh": {
                "faces": len(mesh.faces),
                "nodes": len(mesh.nodes),
                "edges": len(mesh.edges),
            },
            "intersections": {
                "valid_pairs": len(result.valid_pairs),
                "affected_faces": len(result.face_intersections),
                "impossible_pairs": len(result.impossible_pairs),
                "parallel_rejected": len(result.parallel_rejected),
            },
        }
        if restoration is not None:
            data["restoration"] = {
                "faces_triangulated": restoration.faces_triangulated,
                "new_faces_created": restoration.new_faces_created,
                "neighbor_faces_split": restoration.neighbor_faces_split,
                "faces_removed": restoration.faces_removed,
                "outer_faces_count": restoration.outer_faces_count,
                "triangulation_ms": round(restoration.triangulation_time_ms, 2),
                "removal_ms": round(restoration.removal_time_ms, 2),
            }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved stats → {output_file}")

    elif output_file.suffix == ".dat":
        raise click.ClickException(
            ".dat export not yet implemented. Use .json for stats output."
        )
    else:
        raise click.ClickException(
            f"Unsupported output format: {output_file.suffix} (use .json)"
        )


def _show_cells(mesh, result) -> None:
    """Single panel: intersecting cells + segments."""
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

    intersecting_ids = set(result.face_intersections.keys())
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    reg = [f for f in mesh.faces if f.glo_id not in intersecting_ids]
    hi = [f for f in mesh.faces if f.glo_id in intersecting_ids]

    if reg:
        ax.add_collection3d(Poly3DCollection(
            [np.array(f.points()) for f in reg],
            alpha=0.1, facecolors="#CCCCCC", edgecolors="none"))
    if hi:
        ax.add_collection3d(Poly3DCollection(
            [np.array(f.points()) for f in hi],
            alpha=0.6, facecolors="#FF8A80", edgecolors="black", linewidths=0.5))

    lines = [[s.nodes[0].p, s.nodes[-1].p]
              for _, _, s in result.valid_pairs if s.nodes and len(s.nodes) >= 2]
    if lines:
        ax.add_collection3d(Line3DCollection(lines, colors="red", linewidths=2))

    all_pts = np.array([n.p for n in mesh.nodes])
    mn, mx = all_pts.min(0), all_pts.max(0)
    mid = (mn + mx) / 2
    r = max((mx - mn).max() / 2, 1e-3)
    ax.set_xlim(mid[0]-r, mid[0]+r); ax.set_ylim(mid[1]-r, mid[1]+r); ax.set_zlim(mid[2]-r, mid[2]+r)
    ax.set_title(f"Intersecting cells: {len(hi)}, segments: {len(result.valid_pairs)}")
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
    plt.tight_layout(); plt.show()


def _show_pipeline(
    input_file,
    result,
    restoration,
    final_mesh,
    vcfg: "VisualConfig | None" = None,
    mode: str = "combined",
) -> None:
    """
    7-panel pipeline visualization.

    mode: 'combined' — все 7 в одном figure;
          'separate' — каждая в своём окне;
          '1,3,5'   — только указанные номера панелей.
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh as _Mesh

    if vcfg is None:
        vcfg = VisualConfig()

    ec = vcfg.face_edge_color if vcfg.face_edges_show else "none"

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _draw(ax, faces, color, alpha, lw=None):
        if not faces:
            return
        lw = lw if lw is not None else vcfg.face_edge_linewidth
        ax.add_collection3d(Poly3DCollection(
            [np.array(f.points()) for f in faces],
            alpha=alpha, facecolors=color,
            edgecolors=ec,
            linewidths=lw))

    def _segs(ax, pairs, lw=None):
        lw = lw if lw is not None else vcfg.segment_linewidth
        lines = [[s.nodes[0].p, s.nodes[-1].p]
                 for _, _, s in pairs if s.nodes and len(s.nodes) >= 2]
        if lines:
            ax.add_collection3d(Line3DCollection(
                lines, colors=vcfg.segment_color, linewidths=lw))

    def _draw_graph(ax, graph_snap):
        """Нарисовать граф пересечения из снапшота."""
        if graph_snap is None:
            return
        try:
            from mesh_reapairer.src.mesh_reapairer.self_intersection_finder.infrastructure.repairer import EdgeType
            al, be, rc = [], [], []
            nodes = graph_snap.nodes
            for e in graph_snap.edges.values():
                n1 = nodes.get(e.node1.node_id)
                n2 = nodes.get(e.node2.node_id)
                if not n1 or not n2:
                    continue
                seg = [n1.point, n2.point]
                if e.edge_type == EdgeType.RECOVERED:
                    rc.append(seg)
                elif e.edge_type == EdgeType.ALPHA:
                    al.append(seg)
                else:
                    be.append(seg)
            if al:
                ax.add_collection3d(Line3DCollection(
                    al, colors=vcfg.graph_alpha_color,
                    linewidths=vcfg.graph_alpha_linewidth))
            if be:
                ax.add_collection3d(Line3DCollection(
                    be, colors=vcfg.graph_beta_color,
                    linewidths=vcfg.graph_beta_linewidth,
                    linestyles=vcfg.graph_beta_linestyle))
            if rc:
                ax.add_collection3d(Line3DCollection(
                    rc, colors=vcfg.graph_recovered_color,
                    linewidths=vcfg.graph_recovered_linewidth))
            if nodes:
                pts_g = np.array([n.point for n in nodes.values()])
                ax.scatter(pts_g[:, 0], pts_g[:, 1], pts_g[:, 2],
                           c=vcfg.graph_node_color, s=vcfg.graph_node_size, zorder=5)
        except Exception:
            pass

    def _set_axes(ax, pts, title):
        ax.set_title(title, fontsize=vcfg.panel_title_fontsize, pad=vcfg.panel_title_pad)
        fs = vcfg.axis_label_fontsize
        ax.set_xlabel("X", fontsize=fs)
        ax.set_ylabel("Y", fontsize=fs)
        ax.set_zlabel("Z", fontsize=fs)
        ax.tick_params(labelsize=vcfg.tick_fontsize)
        if len(pts):
            mn, mx = pts.min(0), pts.max(0)
            mid = (mn + mx) / 2
            r = max((mx - mn).max() / 2, 1e-3)
            ax.set_xlim(mid[0] - r, mid[0] + r)
            ax.set_ylim(mid[1] - r, mid[1] + r)
            ax.set_zlim(mid[2] - r, mid[2] + r)

    # ── Load pristine copy ────────────────────────────────────────────────────
    m_clean = _Mesh()
    m_clean.load(str(input_file))
    all_pts = np.array([n.p for n in m_clean.nodes])
    intersecting_ids = set(result.face_intersections.keys())
    f_fix_ids = set(result.f_fix.keys())
    new_face_ids = restoration.new_face_ids if restoration else set()
    new_count = len(new_face_ids) if restoration else 0
    inner_geoms = restoration.inner_face_geometries if restoration else []
    removed_count = restoration.removed_faces_count if restoration else 0

    # Zone-based coloring for original mesh
    zones = list({z.name for z in m_clean.zones})
    import random as _rnd
    _rnd.seed(42)
    zone_colors = {z: "#{:02x}{:02x}{:02x}".format(
        _rnd.randint(100, 220), _rnd.randint(100, 220), _rnd.randint(100, 220))
        for z in zones}

    def _zone_color(f):
        return zone_colors.get(getattr(f.zone, "name", ""), vcfg.original_face_color)

    # ── Panel draw functions ──────────────────────────────────────────────────

    def _panel1(ax):
        """1. Исходная сетка (цвета по зонам)."""
        if len(zones) > 1:
            for z in zones:
                zf = [f for f in m_clean.faces if getattr(f.zone, "name", "") == z]
                _draw(ax, zf, zone_colors[z], vcfg.original_face_alpha)
        else:
            _draw(ax, m_clean.faces, vcfg.original_face_color, vcfg.original_face_alpha)
        _set_axes(ax, all_pts, f"1. Original\n{len(m_clean.faces)} faces")

    def _panel2(ax):
        """2. Граф пересечения ДО восстановления."""
        _draw(ax, m_clean.faces, vcfg.background_face_color, vcfg.background_face_alpha)
        _draw_graph(ax, result.intersection_graph_before)
        _set_axes(ax, all_pts,
                  f"2. Graph BEFORE\n{len(result.valid_pairs)} segments")

    def _panel3(ax):
        """3. Граф пересечения ПОСЛЕ восстановления + ломаная пересечения."""
        _draw(ax, m_clean.faces, vcfg.background_face_color, vcfg.background_face_alpha)
        _draw_graph(ax, result.intersection_graph_after)
        _segs(ax, result.valid_pairs)
        _set_axes(ax, all_pts,
                  f"3. Graph AFTER\n{len(result.valid_pairs)} segments")

    def _panel4(ax):
        """4. Только ломаная пересечения на прозрачной сетке."""
        _draw(ax, m_clean.faces, vcfg.background_face_color, 0.05)
        _segs(ax, result.valid_pairs, lw=2.5)
        _set_axes(ax, all_pts,
                  f"4. Seam polyline\n{len(result.valid_pairs)} segments")

    def _panel5(ax):
        """5. Только f_fix ячейки."""
        bg = [f for f in m_clean.faces if f.glo_id not in f_fix_ids]
        hi = [f for f in m_clean.faces if f.glo_id in f_fix_ids]
        _draw(ax, bg, vcfg.background_face_color, vcfg.background_face_alpha)
        _draw(ax, hi, vcfg.highlighted_face_color, vcfg.highlighted_face_alpha, lw=0.4)
        _segs(ax, result.valid_pairs, lw=1.5)
        _set_axes(ax, all_pts, f"5. f_fix cells\n{len(f_fix_ids)} faces")

    def _panel6(ax):
        """6. Новые треугольники + ломаная пересечения."""
        if restoration and new_face_ids:
            new_faces = [f for f in final_mesh.faces if f.glo_id in new_face_ids]
            _draw(ax, new_faces, vcfg.new_face_color, vcfg.new_face_alpha, lw=0.4)
        _segs(ax, result.valid_pairs, lw=vcfg.segment_linewidth_panel4)
        _set_axes(ax, all_pts, f"6. New triangles\n{new_count} faces")

    def _panel7(ax):
        """7. После триангуляции: старые серые, новые зелёные, внутренние розовые."""
        if restoration:
            old_kept = [f for f in final_mesh.faces if f.glo_id not in new_face_ids]
            new_faces = [f for f in final_mesh.faces if f.glo_id in new_face_ids]
            _draw(ax, old_kept, vcfg.kept_face_color, max(vcfg.kept_face_alpha, 0.15))
            _draw(ax, new_faces, vcfg.new_face_color, vcfg.new_face_alpha, lw=0.4)
            # Рисуем удалённые внутренние грани (сохранены до удаления)
            if inner_geoms:
                ax.add_collection3d(Poly3DCollection(
                    [list(g) for g in inner_geoms],
                    alpha=vcfg.inner_face_alpha,
                    facecolors=vcfg.inner_face_color,
                    edgecolors="none",
                ))
        else:
            _draw(ax, list(final_mesh.faces), vcfg.original_face_color,
                  vcfg.original_face_alpha)
        n_total = len(final_mesh.faces) + len(inner_geoms)
        _set_axes(ax, all_pts,
                  f"7. After triangulation\n{n_total} faces ({len(inner_geoms)} inner)")

    def _panel8(ax):
        """8. Финальная сетка после удаления внутренних граней."""
        if restoration:
            old_kept = [f for f in final_mesh.faces if f.glo_id not in new_face_ids]
            new_faces = [f for f in final_mesh.faces if f.glo_id in new_face_ids]
            _draw(ax, old_kept, vcfg.outer_face_color, vcfg.outer_face_alpha)
            _draw(ax, new_faces, vcfg.outer_face_color, vcfg.outer_face_alpha, lw=0.4)
        else:
            _draw(ax, list(final_mesh.faces), vcfg.outer_face_color, vcfg.outer_face_alpha)
        _set_axes(ax, all_pts,
                  f"8. Final mesh\n{len(final_mesh.faces)} faces"
                  + (f" ({removed_count} removed)" if removed_count else ""))

    panel_fns = [_panel1, _panel2, _panel3, _panel4, _panel5, _panel6, _panel7, _panel8]
    suptitle = f"mesh-reapairer — {Path(input_file).name}"

    # Determine which panels to show
    if mode.lower() == "separate":
        selected = list(range(1, 9))
        for i in selected:
            fig = plt.figure(
                figsize=(vcfg.single_panel_width, vcfg.single_panel_height),
                dpi=vcfg.figure_dpi)
            fig.suptitle(suptitle, fontsize=vcfg.suptitle_fontsize)
            ax = fig.add_subplot(1, 1, 1, projection="3d")
            panel_fns[i - 1](ax)
            plt.tight_layout()
            plt.show()
    elif mode.lower() == "combined":
        n = 8
        fig = plt.figure(figsize=(vcfg.figure_width * 8 / 5, vcfg.figure_height),
                         dpi=vcfg.figure_dpi)
        fig.suptitle(suptitle, fontsize=vcfg.suptitle_fontsize)
        for i, fn in enumerate(panel_fns, 1):
            ax = fig.add_subplot(1, n, i, projection="3d")
            fn(ax)
        plt.tight_layout()
        plt.show()
    else:
        # Parse as comma-separated panel numbers: "1,4,5"
        try:
            selected = [int(x.strip()) for x in mode.split(",") if x.strip().isdigit()]
            selected = [x for x in selected if 1 <= x <= 8]
        except Exception:
            selected = list(range(1, 9))
        if not selected:
            selected = list(range(1, 9))
        n = len(selected)
        fig = plt.figure(
            figsize=(vcfg.single_panel_width * n, vcfg.single_panel_height),
            dpi=vcfg.figure_dpi)
        fig.suptitle(suptitle, fontsize=vcfg.suptitle_fontsize)
        for col, panel_num in enumerate(selected, 1):
            ax = fig.add_subplot(1, n, col, projection="3d")
            panel_fns[panel_num - 1](ax)
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
