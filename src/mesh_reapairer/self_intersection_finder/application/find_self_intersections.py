"""
Главный use case: поиск самопересечений в треугольной сетке.

Оркестрирует компоненты системы:
- BVH построение и обход
- Классификация пересечений
- Восстановление графа (graph recovery)
- Визуализация (опционально)
"""
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Set, Tuple

import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh

from .config import SelfIntersectionFinderConfig
from ..domain.entities import IntersectionResult, Segment
from ..infrastructure.bvh.builder import BVHBuilder
from ..infrastructure.bvh.traverser import BVHTraverser
from ..infrastructure.caching.pair_cache import PairCache
from ..infrastructure.caching.adjacency_cache import AdjacencyCache
from ..infrastructure.intersection.classifier import IntersectionClassifier
from ..infrastructure.intersection.segment_finder import SegmentFinder
from ..infrastructure.intersection.parallel_handler import ParallelPlaneHandler
from ..infrastructure.repairer import GraphBuilder, PathFinder, EdgeType
from ..infrastructure.repairer.segment_recovery import SegmentRecovery
from ..utils.logging_config import setup_logger
from ..utils.geometry import are_faces_coincident, is_segment_trivial_intersection


class FindSelfIntersectionsUseCase:
    """
    Главный use case: поиск самопересечений в сетке.

    Оркестрирует все компоненты и возвращает IntersectionResult.
    """

    def __init__(self, config: SelfIntersectionFinderConfig):
        self.config = config
        self.config.validate()

        self.logger = setup_logger(
            name='self_intersection_finder',
            level=config.logging_level,
            log_file=config.log_file
        )

        self.bvh_builder = BVHBuilder(config.bvh, self.logger)
        self.pair_cache = PairCache()
        self.adjacency_cache = AdjacencyCache()
        self.traverser = BVHTraverser(self.pair_cache, self.adjacency_cache, self.logger)
        self.classifier = IntersectionClassifier(config.intersection, self.logger)
        self.segment_finder = SegmentFinder(config.intersection, self.logger)
        self.parallel_handler = ParallelPlaneHandler(config.intersection, self.logger)

    def execute(
        self,
        mesh: 'Mesh',
        enable_visualization: bool = False,
        demo_remove_segments_percent: float = 0.0
    ) -> IntersectionResult:
        """
        Выполнить поиск самопересечений.

        Args:
            mesh: Треугольная сетка
            enable_visualization: Включить визуализацию графа пересечений
            demo_remove_segments_percent: DEMO: процент удаляемых valid сегментов (0-100)
        """
        self.logger.info("=" * 60)
        self.logger.info("=== Starting Self-Intersection Search ===")
        self.logger.info(
            f"Mesh: {len(mesh.faces)} faces, {len(mesh.nodes)} nodes, {len(mesh.edges)} edges"
        )
        self.logger.info("=" * 60)

        t0 = time.time()
        self.adjacency_cache.build(mesh)
        self.logger.info(f"Adjacency cache built in {(time.time() - t0) * 1000:.2f}ms")

        t0 = time.time()
        bvh_root = self.bvh_builder.build(mesh)
        build_time = (time.time() - t0) * 1000
        self.logger.info(f"BVH built in {build_time:.2f}ms")

        t0 = time.time()
        candidates = self.traverser.find_candidates(bvh_root)
        traversal_time = (time.time() - t0) * 1000
        self.logger.info(f"Found {len(candidates)} candidates in {traversal_time:.2f}ms")

        t0 = time.time()
        result = self._classify_candidates(candidates, mesh)
        classification_time = (time.time() - t0) * 1000

        if demo_remove_segments_percent > 0:
            self._demo_create_gaps(result, demo_remove_segments_percent)

        t0 = time.time()
        self._repairer_intersection(result, mesh, visualize=enable_visualization)
        repair_time = (time.time() - t0) * 1000

        result.total_candidates = len(candidates)
        result.checked_pairs = self.pair_cache.stats()['size']
        result.cache_hits = self.pair_cache.stats()['hits']
        result.build_time_ms = build_time
        result.traversal_time_ms = traversal_time
        result.classification_time_ms = classification_time
        result.repair_intersection_time_ms = repair_time

        self._log_summary(result)
        return result

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_candidates(self, candidates, mesh) -> IntersectionResult:
        """Классифицировать кандидатов на пересечение."""
        valid_pairs = []
        impossible_pairs = []
        parallel_rejected = []
        trivial_filtered = []
        face_intersections = defaultdict(list)

        for face_a, face_b in candidates:
            if self.parallel_handler.should_reject_parallel(face_a, face_b):
                parallel_rejected.append((face_a, face_b))
                continue

            try:
                codes_ab, codes_ba, is_coplanar = \
                    self.classifier.classify_edges_intersection(face_a, face_b)
            except Exception as e:
                self.logger.error(
                    f"Classification error for faces {face_a.glo_id}-{face_b.glo_id}: {e}"
                )
                continue

            if is_coplanar:
                if are_faces_coincident(face_a, face_b, self.config.intersection.epsilon):
                    if self.config.intersection.coplanar_search_enabled:
                        self.parallel_handler.handle_coincident_faces(face_a, face_b, mesh)
                    continue

                intersection_nodes = self.parallel_handler.find_coplanar_intersection(face_a, face_b)
                if intersection_nodes:
                    if is_segment_trivial_intersection(
                        intersection_nodes, face_a, face_b, self.config.intersection.epsilon
                    ):
                        trivial_filtered.append((face_a, face_b))
                        continue

                    segment = Segment(nodes=intersection_nodes, face_a=face_a, face_b=face_b)
                    valid_pairs.append((face_a, face_b, segment))
                    face_intersections[face_a.glo_id].append(segment)
                    face_intersections[face_b.glo_id].append(segment)
                continue

            if (codes_ab.to_list() in self.classifier.special_cases or
                    codes_ba.to_list() in self.classifier.special_cases):
                continue

            if (codes_ab.to_list() in self.classifier.impossible_cases or
                    codes_ba.to_list() in self.classifier.impossible_cases):
                impossible_pairs.append((face_a, face_b))
                continue

            segment = self.segment_finder.find_intersection_segment(
                face_a, face_b, codes_ab, codes_ab.points, codes_ba, codes_ba.points
            )
            if segment and segment.nodes:
                if is_segment_trivial_intersection(
                    segment.nodes, face_a, face_b, self.config.intersection.epsilon
                ):
                    trivial_filtered.append((face_a, face_b))
                    continue

                valid_pairs.append((face_a, face_b, segment))
                face_intersections[face_a.glo_id].append(segment)
                face_intersections[face_b.glo_id].append(segment)

        fi = dict(face_intersections)
        # Build f_fix: {face_id: (face_object, [segments])}
        face_map: dict = {}
        for face_a, face_b, seg in valid_pairs:
            face_map[face_a.glo_id] = face_a
            face_map[face_b.glo_id] = face_b
        f_fix = {fid: (face_map[fid], segs) for fid, segs in fi.items() if fid in face_map}

        return IntersectionResult(
            valid_pairs=valid_pairs,
            impossible_pairs=impossible_pairs,
            parallel_rejected=parallel_rejected,
            trivial_filtered=trivial_filtered,
            face_intersections=fi,
            f_fix=f_fix,
        )

    # ------------------------------------------------------------------
    # Graph recovery
    # ------------------------------------------------------------------

    def _repairer_intersection(
        self,
        result: IntersectionResult,
        mesh: 'Mesh',
        visualize: bool = False
    ) -> None:
        """
        Восстановление графа пересечений.

        Алгоритм:
        1. Строим граф J(M,W)
        2. Находим якоря (разрывы в линии пересечения)
        3. Ищем пути MST между якорями
        4. Восстанавливаем сегменты из путей
        5. Обрабатываем изолированные β-узлы
        6. Постобработка графа (стягивание, дедупликация)
        """
        if not self.config.recovery.enable_recovery:
            self.logger.info("Graph recovery disabled by config")
            return

        self.logger.info("=" * 60)
        self.logger.info("=== Starting Graph Recovery ===")

        graph_builder = GraphBuilder(
            logger=self.logger,
            max_distance_threshold=self.config.recovery.max_distance_threshold,
            enable_spatial_filter=self.config.recovery.enable_spatial_filter,
            enable_topological_filter=self.config.recovery.enable_topological_filter
        )
        graph = graph_builder.build_graph(result.valid_pairs, result.impossible_pairs)

        stats = graph.stats()
        self.logger.info(
            f"Graph J(M,W): {stats['nodes']} nodes, {stats['edges']} edges, "
            f"{stats['anchors']} anchors"
        )

        graph_before = self._create_graph_snapshot(graph)
        result.intersection_graph_before = graph_before
        if visualize:
            self._print_graph_stats(graph, "BEFORE Recovery")

        if self.config.recovery.use_adaptive_params:
            max_distance, max_weight = self._compute_adaptive_params(mesh)
        else:
            max_distance = self.config.recovery.max_distance
            max_weight = self.config.recovery.max_weight

        path_finder = PathFinder(
            graph=graph,
            max_distance=max_distance,
            max_weight=max_weight,
            logger=self.logger
        )
        paths = path_finder.find_paths_between_anchors()
        self.logger.info(f"Found {len(paths)} paths between anchors")

        # Удаляем изолированные якоря (не вошли ни в один путь MST)
        if paths:
            anchors_in_paths = {pr.source for pr in paths} | {pr.target for pr in paths}
            isolated_anchors = graph.anchors - anchors_in_paths
            if isolated_anchors:
                self.logger.warning(
                    f"Removing {len(isolated_anchors)} isolated anchors (no β-path available)"
                )
                for anchor_id in isolated_anchors:
                    graph.remove_node(anchor_id)
                graph.find_anchors()

        path_finder.mark_recovered_edges(paths)
        self.logger.info(
            f"Graph after recovery: {graph.stats()['recovered_edges']} edges recovered"
        )

        segment_recovery = SegmentRecovery(
            mode=self.config.recovery.interpolation_mode,
            logger=self.logger
        )

        if self.config.recovery.enable_segment_recovery and paths:
            segment_recovery.recover_from_paths(result, graph, paths, mesh)
            graph.update_all_edge_types()
            graph.find_anchors()
            self.logger.info(
                f"After path recovery: {graph.stats()['anchors']} anchors remain"
            )

        if self.config.recovery.enable_segment_recovery:
            segment_recovery.recover_isolated_nodes(result, graph, mesh)
            graph.update_all_edge_types()
            self._remove_duplicate_edges(graph)
            graph.find_anchors()
            self.logger.info(
                f"After isolated recovery: {graph.stats()['anchors']} anchors remain"
            )

        self._contract_low_degree_nodes(graph)

        final = graph.stats()
        self.logger.info(
            f"Final graph state: {final['nodes']} nodes, "
            f"{final['edges']} edges, {final['anchors']} anchors"
        )

        if final['anchors'] > 0:
            self.logger.warning(
                f"WARNING: {final['anchors']} anchors remain after recovery! "
                f"Intersection line is NOT closed."
            )
            if final['anchors'] % 2 != 0:
                self.logger.error(
                    f"CRITICAL: {final['anchors']} is an ODD number! "
                    f"Anchors should always come in pairs."
                )
            self._log_remaining_anchors(graph)

        if visualize:
            self._print_graph_stats(graph, "AFTER Recovery")
            if graph_before is not None:
                self.logger.info("Showing intersection graph visualization (BEFORE/AFTER)...")
                try:
                    from mesh_reapairer.src.mesh_reapairer.vizualizator import plot_intersection_graph_before_after
                    plot_intersection_graph_before_after(graph_before, graph, show_labels=False)
                except Exception as e:
                    self.logger.error(f"Error during graph visualization: {e}")

        # Capture graph snapshot after recovery
        result.intersection_graph_after = self._create_graph_snapshot(graph)

        # Update f_fix from recovered face_intersections
        face_map: dict = {}
        for face_a, face_b, seg in result.valid_pairs:
            face_map[face_a.glo_id] = face_a
            face_map[face_b.glo_id] = face_b
        result.f_fix = {
            fid: (face_map[fid], segs)
            for fid, segs in result.face_intersections.items()
            if fid in face_map
        }

        self.logger.info(f"f_fix built: {len(result.f_fix)} faces require triangulation")
        self.logger.info("=== Graph Recovery Complete ===")
        self.logger.info("=" * 60)

    def _log_remaining_anchors(self, graph) -> None:
        """Детальная информация об оставшихся якорях."""
        self.logger.warning("Analyzing remaining anchors:")
        for anchor_id in list(graph.anchors)[:10]:
            node = graph.nodes.get(anchor_id)
            if not node:
                continue
            neighbors = graph.adjacency.get(anchor_id, [])
            neighbor_info = []
            for nid in neighbors:
                edge = graph.get_edge(anchor_id, nid)
                nnode = graph.nodes.get(nid)
                seg_str = "seg" if (nnode and nnode.segment) else "no_seg"
                et = edge.edge_type.name if edge else "?"
                neighbor_info.append(f"{nid}({et},{seg_str})")
            self.logger.warning(
                f"  Anchor {anchor_id}: deg={graph.degree(anchor_id)}, "
                f"α={graph.degree(anchor_id, EdgeType.ALPHA)}, "
                f"β={graph.degree(anchor_id, EdgeType.BETA)}, "
                f"rec={graph.degree(anchor_id, EdgeType.RECOVERED)}, "
                f"has_segment={'YES' if node.segment else 'NO'}, "
                f"neighbors=[{', '.join(neighbor_info)}]"
            )

    # ------------------------------------------------------------------
    # Graph post-processing
    # ------------------------------------------------------------------

    def _remove_duplicate_edges(self, graph) -> int:
        """Удалить дублирующие ребра (короткие циклы длины 2)."""
        edge_pairs: dict = {}
        for edge_id, edge in list(graph.edges.items()):
            key = (min(edge.node1.node_id, edge.node2.node_id),
                   max(edge.node1.node_id, edge.node2.node_id))
            edge_pairs.setdefault(key, []).append(edge_id)

        removed = 0
        for edge_ids in edge_pairs.values():
            for edge_id in edge_ids[1:]:
                if edge_id in graph.edges:
                    graph.remove_edge(edge_id)
                    removed += 1

        if removed:
            self.logger.info(f"Removed {removed} duplicate edges (short cycles)")
        return removed

    def _contract_low_degree_nodes(self, graph) -> None:
        """Стянуть висячие вершины (degree < 2 без α-ребер)."""
        removed_total = 0
        while True:
            to_remove = [
                node_id for node_id in list(graph.nodes)
                if graph.degree(node_id) < 2
                and graph.degree(node_id, EdgeType.ALPHA) == 0
            ]
            if not to_remove:
                break
            for node_id in to_remove:
                graph.remove_node(node_id)
                removed_total += 1

        if removed_total:
            self.logger.info(f"Contracted {removed_total} low-degree nodes")
        graph.find_anchors()

    # ------------------------------------------------------------------
    # Adaptive parameters
    # ------------------------------------------------------------------

    def _compute_adaptive_params(self, mesh: 'Mesh') -> Tuple[float, float]:
        """Вычислить адаптивные параметры на основе среднего размера ребра."""
        edge_lengths = [
            np.linalg.norm(e.points()[1] - e.points()[0])
            for e in mesh.edges
        ]
        if not edge_lengths:
            return self.config.recovery.max_distance, self.config.recovery.max_weight

        avg = float(np.mean(edge_lengths))
        max_distance = avg * self.config.recovery.max_distance_multiplier
        max_weight = avg * self.config.recovery.max_weight_multiplier

        self.logger.info(
            f"Adaptive parameters: avg_edge_length={avg:.4f}, "
            f"max_distance={max_distance:.4f}, max_weight={max_weight:.4f}"
        )
        return max_distance, max_weight

    # ------------------------------------------------------------------
    # Visualization helpers
    # ------------------------------------------------------------------

    def _create_graph_snapshot(self, graph):
        """Создать легковесный снапшот графа для визуализации BEFORE/AFTER."""
        @dataclass
        class NodeSnap:
            node_id: int
            point: np.ndarray
            face_a: object
            face_b: object
            segment: object

        @dataclass
        class EdgeSnap:
            node1: object
            node2: object
            edge_type: object
            weight: float

        @dataclass
        class GraphSnap:
            nodes: Dict
            edges: Dict
            anchors: Set

            def stats(self):
                from ..infrastructure.repairer import EdgeType as ET
                return {
                    'nodes': len(self.nodes),
                    'edges': len(self.edges),
                    'alpha_edges': sum(1 for e in self.edges.values() if e.edge_type == ET.ALPHA),
                    'beta_edges': sum(1 for e in self.edges.values() if e.edge_type == ET.BETA),
                    'recovered_edges': sum(
                        1 for e in self.edges.values() if e.edge_type == ET.RECOVERED
                    ),
                    'anchors': len(self.anchors)
                }

            def degree(self, node_id, edge_type=None):
                return sum(
                    1 for e in self.edges.values()
                    if (e.node1.node_id == node_id or e.node2.node_id == node_id)
                    and (edge_type is None or e.edge_type == edge_type)
                )

        node_snaps = {
            nid: NodeSnap(n.node_id, n.point.copy(), n.face_a, n.face_b, n.segment)
            for nid, n in graph.nodes.items()
        }
        edge_snaps = {
            k: EdgeSnap(node_snaps[e.node1.node_id], node_snaps[e.node2.node_id],
                        e.edge_type, e.weight)
            for k, e in graph.edges.items()
        }
        return GraphSnap(nodes=node_snaps, edges=edge_snaps, anchors=graph.anchors.copy())

    def _print_graph_stats(self, graph, stage: str) -> None:
        """Вывести статистику графа."""
        self.logger.info("=" * 60)
        self.logger.info(f"=== Graph Stats: {stage} ===")

        s = graph.stats()
        self.logger.info(f"Total nodes: {s['nodes']}")
        self.logger.info(f"Total edges: {s['edges']}")
        self.logger.info(f"  α-edges (valid): {s['alpha_edges']}")
        self.logger.info(f"  β-edges (potential): {s['beta_edges']}")
        self.logger.info(f"  Recovered edges: {s['recovered_edges']}")
        self.logger.info(f"Anchors (degree=1): {s['anchors']}")

        degree_dist: dict = {}
        low_degree = []
        for node_id in graph.nodes:
            deg = graph.degree(node_id)
            degree_dist[deg] = degree_dist.get(deg, 0) + 1
            if deg < 2:
                low_degree.append(node_id)

        self.logger.info("Degree distribution:")
        for deg in sorted(degree_dist):
            self.logger.info(f"  degree {deg}: {degree_dist[deg]} nodes")

        if low_degree:
            self.logger.warning(
                f"Found {len(low_degree)} nodes with degree < 2 (should be contracted)"
            )

        components = graph.find_connected_components()
        self.logger.info(f"Connected components: {len(components)}")
        for i, comp in enumerate(components[:5]):
            self.logger.info(f"  Component {i}: {len(comp)} nodes")

        self.logger.info("=" * 60)

    # ------------------------------------------------------------------
    # Demo mode
    # ------------------------------------------------------------------

    def _demo_create_gaps(self, result: IntersectionResult, percent: float) -> None:
        """DEMO: Искусственно создать разрывы в линии пересечения."""
        if percent <= 0 or percent >= 100:
            return

        total = len(result.valid_pairs)
        if total == 0:
            return

        num_remove = max(1, int(total * percent / 100.0))
        self.logger.warning("=" * 60)
        self.logger.warning("DEMO MODE: Creating artificial gaps in intersection line")
        self.logger.warning(f"Removing {num_remove}/{total} valid pairs ({percent:.1f}%)")
        self.logger.warning("=" * 60)

        indices = sorted(random.sample(range(total), num_remove), reverse=True)
        for idx in indices:
            face_a, face_b, segment = result.valid_pairs.pop(idx)
            result.impossible_pairs.append((face_a, face_b))

            for face_id in (face_a.glo_id, face_b.glo_id):
                segs = result.face_intersections.get(face_id)
                if segs:
                    try:
                        segs.remove(segment)
                    except ValueError:
                        pass
                    if not segs:
                        del result.face_intersections[face_id]

        self.logger.info(
            f"DEMO: Created {num_remove} gaps. "
            f"Now: {len(result.valid_pairs)} valid, {len(result.impossible_pairs)} impossible"
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _log_summary(self, result: IntersectionResult) -> None:
        """Логировать итоговую статистику."""
        self.logger.info("=" * 60)
        self.logger.info("=== Self-Intersection Search Complete ===")
        self.logger.info(f"Valid intersections: {len(result.valid_pairs)}")
        self.logger.info(f"Impossible pairs: {len(result.impossible_pairs)}")
        self.logger.info(f"Parallel rejected: {len(result.parallel_rejected)}")
        self.logger.info(f"Trivial filtered: {len(result.trivial_filtered)}")
        self.logger.info(f"Total candidates: {result.total_candidates}")
        self.logger.info(
            f"Cache: {result.cache_hits}/{result.checked_pairs} "
            f"({result.cache_hit_rate():.1%})"
        )
        self.logger.info("")
        self.logger.info("=== Performance ===")
        self.logger.info(f"Build time: {result.build_time_ms:.2f}ms")
        self.logger.info(f"Traversal time: {result.traversal_time_ms:.2f}ms")
        self.logger.info(f"Classification time: {result.classification_time_ms:.2f}ms")
        self.logger.info(f"Repair intersection time: {result.repair_intersection_time_ms:.2f}ms")
        self.logger.info(f"Total time: {result.total_time_ms():.2f}ms")
        self.logger.info("=" * 60)
