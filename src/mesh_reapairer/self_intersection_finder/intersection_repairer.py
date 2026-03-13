from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from collections import defaultdict
from itertools import combinations

import networkx as nx
import numpy as np

from mesh_reapairer.msu.mesh import Mesh, Face, Node
from mesh_reapairer.self_intersection_finder.bvh_builder import BVHBuilder
from mesh_reapairer.self_intersection_finder.intersection_finder import Segment


logger = logging.getLogger(__name__)
#logging.basicConfig(filename="intersection.log", level=logging.DEBUG)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


class IntersectionRepairer:
    def __init__(self, p_valid, p_invalid, eps: float = 1e-8):
        self.p_valid = p_valid
        self.p_invalid = p_invalid
        self.eps = eps

        self.alpha_graphs = []
        self.alpha_anchors = []

        self.beta_graphs = []
        
        logger.debug(
            "IntersectionRepairer: p_valid=%s, p_invalid=%s",
            len(self.p_valid), len(self.p_invalid)
        )
    
    def _quantize_point(self, p):
        """Квантование точки по геометрическому eps."""
        arr = np.asarray(p, dtype=float)
        return tuple(np.round(arr / self.eps) * self.eps)

    
    def build_alpha_area(self):
        """
        Строит альфа-области пересечений как набор компонент связности графа.

        Узлы графа: пары (face_a_id, face_b_id) из `p_valid` (один узел на сегмент).
        Рёбра графа: наличие общей квантованной точки среди концов сегментов.
        """
        G = nx.Graph()
        point_index: dict[tuple[float, float, float], set[tuple[int, int]]] = defaultdict(set)
        quantize = self._quantize_point
        add_node = G.add_node

        # ------------------------------------------------
        # 1. создаём вершины графа (A,B)

        for face_a, face_b, segment in self.p_valid:

            if segment is None or segment.nodes is None:
                raise ValueError(
                    "IntersectionRepairer: build_alpha_area, segment cannot be None"
                )

            pair = tuple(sorted((face_a.glo_id, face_b.glo_id)))
            nodes = segment.nodes

            # -------------------------------
            # сегмент-точка

            if len(nodes) == 1:
                p0 = np.asarray(nodes[0].p, dtype=float)
                p1 = p0
            # -------------------------------
            # нормальный сегмент
            else:

                p0 = np.asarray(nodes[0].p, dtype=float)
                p1 = np.asarray(nodes[-1].p, dtype=float)

            center = (p0 + p1) * 0.5
            direction = p1 - p0

            # добавляем вершину
            add_node(
                pair,
                segment=segment,
                p0=p0,
                p1=p1,
                center=center,
                direction=direction
            )
            # -------------------------------
            # индексируем ТОЛЬКО концы сегмента
            p0q = quantize(p0)
            p1q = quantize(p1)
            point_index[p0q].add(pair)
            point_index[p1q].add(pair)

        # ------------------------------------------------
        # 2. строим рёбра через общие точки
        for p, pairs in point_index.items():
            if len(pairs) >= 2:
                # combinations гарантирует a != b
                G.add_edges_from(((a, b, {"point": p}) for a, b in combinations(pairs, 2)))

        # ------------------------------------------------
        # 4. компоненты связности

        self.alpha_graphs = []
        self.alpha_anchors = []

        for comp in nx.connected_components(G):
            sub = G.subgraph(comp).copy()
            self.alpha_graphs.append(sub)
            anchors = [node for node, deg in sub.degree() if deg == 1]
            self.alpha_anchors.append(anchors)

        logger.debug(
            "IntersectionRepairer: alpha areas: %s",
            len(self.alpha_graphs)
        )

        logger.debug(
            "IntersectionRepairer: anchors: %s",
            sum(len(a) for a in self.alpha_anchors)
        )


    def build_beta_area(self):
        """
        Строит beta-графы из `p_invalid`.

        Beta-узел = пара ячеек (face_a_id, face_b_id), для которой пересечение
        было невалидным / сломанным.

        Узлы графа: пары (min_id, max_id)
        Атрибуты узла:
        - faces: (face_a_id, face_b_id)
        - center: (center(face_a) + center(face_b)) / 2

        Сейчас beta-граф используется для визуализации, поэтому рёбра не строятся.
        """
        G = nx.Graph()

        for item in self.p_invalid:
            # ожидаемый формат: (face_a, face_b) или (face_a, face_b, ...)
            if not isinstance(item, (tuple, list)) or len(item) < 2:
                logger.debug(
                    "IntersectionRepairer: build_beta_area skip invalid item type=%s value=%r",
                    type(item),
                    item,
                )
                continue

            face_a = item[0]
            face_b = item[1]
            if not hasattr(face_a, "glo_id") or not hasattr(face_b, "glo_id"):
                logger.debug(
                    "IntersectionRepairer: build_beta_area skip item without faces: %r",
                    item.glo_id,
                )
                continue

            pair = tuple(sorted((face_a.glo_id, face_b.glo_id)))

            ca = np.asarray(face_a.center(), dtype=float)
            cb = np.asarray(face_b.center(), dtype=float)
            center = (ca + cb) * 0.5

            G.add_node(pair, faces=(face_a.glo_id, face_b.glo_id), center=center)

        self.beta_graphs = [G] if G.number_of_nodes() > 0 else []

        logger.debug(
            "IntersectionRepairer: build_beta_area candidates: %s",
            len(self.p_invalid),
        )
        logger.debug(
            "IntersectionRepairer: build_beta_area beta nodes: %s",
            G.number_of_nodes(),
        )


    def find_lost_segments(self) -> None:
        # проверяем попарно графы и их якоря
        # проверяем потерян ли был 1 сегмент и можно ли напрямую протянуть
        # например пара mesh.find_face_by_id(15), mesh.find_face_by_id(96) и mesh.find_face_by_id(47), mesh.find_face_by_id(124)
        # faces_for_debug = [mesh.find_face_by_id(15), mesh.find_face_by_id(96), mesh.find_face_by_id(47), mesh.find_face_by_id(124)]
        # for face in faces_for_debug:
        #     for f in face.neighbourhood():
        #         print(face.glo_id, f.glo_id)
        # выдал
        # 15 47
        # 15 33
        # 15 31
        # 96 124
        # 96 110
        # 96 108
        # 47 48
        # 47 15
        # 47 59
        # 124 125
        # 124 96
        # 124 136
        # то есть был потерян один сегмнет и можем напрямукю соединить две вершины (создаем новый сегмент и пишем в f_fix, p_valid)
        # если соседи ничего не дали сделай заглушку logger.debug(""IntersectionRepairer: find_lost_segments lost more one segment")
        # тогда мы ищем сегменты примерно, вначале используя p_invalid
        # if p_invalid not None - заглушка
        # else ищем через построение дуального графа (сделаем два варианта по ребрам и по вершинам) 
        # где крайние ячейки содержук якоря и ищем как кратчаший маршрут в дуальном графе либо по ребрам либо по середине ребра
        # т.е. в сетке надо как-то правильно восстановить участок ячеек между ячейками с якорями и найти кратчайший маршрут
        # вот пример организации сетки

        if not self.alpha_graphs or not self.alpha_anchors:
            logger.debug("IntersectionRepairer: find_lost_segments alpha-areas are not built")
            return

        # if not new_segments:
        #     if self.p_invalid:
        #         logger.debug(
        #             "IntersectionRepairer: find_lost_segments no direct neighbor-based segments found; "
        #             "approximate recovery using p_invalid is not implemented yet"
        #         )
        #     else:
        #         logger.debug(
        #             "IntersectionRepairer: find_lost_segments lost more one segment or topology is complex"
        #         )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(levelname)s: %(message)s'
    )
    mesh = Mesh("examples/small_sphere_double.dat")
    #mesh = Mesh("examples/sphere_double.dat")
    #mesh = Mesh("examples/bunny_double.dat")
    
    # faces_for_debug = [mesh.find_face_by_id(15), mesh.find_face_by_id(96), mesh.find_face_by_id(47), mesh.find_face_by_id(124)]
    # for face in faces_for_debug:
    #     for f in face.neighbourhood():
    #         print(face.glo_id, f.glo_id)
    
    bvh = BVHBuilder(mesh=mesh, eps=1e-12)
    bvh.prepare_mesh(esc_enable=False)
    bvh.build_tree(face_on_leaf=1, split_func="sah")
    bvh.traversal_tree()
    
    p_valid = bvh.p_valid[0:3]
    p_valid += bvh.p_valid[5:7]
    p_valid += bvh.p_valid[9:]
    
    p_invalid = bvh.p_invalid
    p_invalid += bvh.p_valid[4:5]
    p_invalid +=  bvh.p_valid[8]
    ir =IntersectionRepairer(p_valid, p_invalid, eps=1e-6)
    ir.build_alpha_area()
    ir.build_beta_area()
    # ir.find_lost_segments()
