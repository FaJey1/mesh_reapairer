from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import networkx as nx

import numpy as np

from mesh_reapairer.msu.mesh import Mesh, Face, Node
from mesh_reapairer.self_intersection_finder.intersection_finder import IntersectionFinder
from mesh_reapairer.vizualizator.face_plotter import *
from mesh_reapairer.vizualizator.segment_plotter import *


logger = logging.getLogger(__name__)
#logging.basicConfig(filename="bvh_builder.log", level=logging.DEBUG)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


@dataclass
class BVHNode:
    node_id: int = -1
    is_leaf: bool = False
    children: Tuple[Optional["BVHNode"], Optional["BVHNode"]] = (None, None)
    primitives: List["BVHPrimitive"] = field(default_factory=list)
    split_value: float = 0.0
    # Кэш AABB узла (min, max) для ускорения boxes_intersect и обхода
    bounding_box: Optional[Tuple[np.ndarray, np.ndarray]] = None


@dataclass
class BVHPrimitive:
    bounding_box: Tuple[float, float] = None
    face: List[Face] = None


@dataclass
class ESCFaceAABB:
    bounding_boxes: List[Tuple[float, float]] = None
    face: List[Face] = None


class BVHBuilder:
    def __init__(self, mesh: Mesh, eps: int =1e-2):
        self.mesh = mesh
        self.eps = eps
        self.primitives = []
        self.esc_aabb_on_face = []
        self.node_id = 0
        self.root_node = BVHNode()
        self.nodes = 0
        self.graph = nx.DiGraph()
        
        self.f_fix = {}
        self.p_valid = []
        self.p_invalid = []
  
    
    def get_aabb_box(self, face: Face) -> Tuple[float, float]:
        coords = np.array(face.points())
        _min = coords.min(axis=0)
        _max = coords.max(axis=0)
        return _min, _max
    
    
    def surface_area_aabb(self, aabb: Tuple[float, float]) -> float:
        mn, mx = aabb
        d = mx - mn
        return 2.0 * (d[0]*d[1] + d[1]*d[2] + d[2]*d[0])
    
    
    def axis_of_largest_extent(self, box: Tuple[float, float]) -> int:
        mn, mx = box
        return int(np.argmax(mx - mn))
    
    
    def center_axis(self, box: Tuple[float, float], axis: int) -> float:
        mn, mx = box
        return 0.5 * (mn[axis] + mx[axis])
    
    
    def split_box(self, box: Tuple[float, float], axis: int, split: float)-> Tuple[Tuple[float, float], Tuple[float, float]]:
        mn, mx = box

        mn1, mx1 = mn.copy(), mx.copy()
        mn2, mx2 = mn.copy(), mx.copy()

        mx1[axis] = split
        mn2[axis] = split

        return (mn1, mx1), (mn2, mx2)
    
    
    def face_intersects_box(self, aabb: Tuple[float, float], box) -> bool:
        fmin, fmax = aabb
        bmin, bmax = box
        return np.all(fmax >= bmin) and np.all(fmin <= bmax)
    
    
    def early_split_clipping(self,
                             face: Face,
                             sa_max: Optional[float] = None,) -> List[Tuple[float, float]]:
        aabb = self.get_aabb_box(face)
        boxes_stack = [aabb]
        bounding_boxes = []
        esc_bounding_boxes = []
        if not sa_max:
            sa_max = self.surface_area_aabb(aabb) * 0.7
            logger.debug("BVHBuilder: sa_max %s in early_split_clipping", sa_max)
        
        while boxes_stack:
            box = boxes_stack.pop()
            
            sa_current = self.surface_area_aabb(box)
            
            if sa_current <= sa_max:
                bounding_boxes.append(BVHPrimitive(box, face))
                esc_bounding_boxes.append(box)
                continue
            
            axis = self.axis_of_largest_extent(box)
            split = self.center_axis(box, axis)
            
            box_neg, box_pos = self.split_box(box, axis, split)
            if self.face_intersects_box(aabb, box_neg):
                boxes_stack.append(box_neg)

            if self.face_intersects_box(aabb, box_pos):
                boxes_stack.append(box_pos)
                
            if sa_current < sa_max:
                sa_max = sa_current
                
        self.esc_aabb_on_face.append(ESCFaceAABB(esc_bounding_boxes, face))
        return bounding_boxes
    
    
    def surface_area_box(self, box: Tuple[float, float]) -> float:
        mn, mx = box
        d = np.maximum(mx - mn, 0.0)  # размеры по осям (dx, dy, dz)
        return 2.0 * (d[0] * d[1] + d[1] * d[2] + d[0] * d[2])
    
    
    def find_best_split_sah(self, primitives):
        """
        Находит лучшее разбиение примитивов по SAH.
        Гарантированно возвращает две непустые группы или None, если деление невозможно.
        """
        parent_box = self.compute_bounds(primitives)
        parent_area = self.surface_area_box(parent_box)

        if parent_area <= self.eps or len(primitives) <= 1:
            return None, None, None

        best_cost = float("inf")
        best_axis = None
        best_left = None
        best_right = None

        for axis in range(3):
            # сортировка по центру AABB с tie-breaker по индексу, чтобы избежать одинаковых значений
            sorted_prims = sorted(
                enumerate(primitives),
                key=lambda t: 0.5 * (t[1].bounding_box[0][axis] + t[1].bounding_box[1][axis]) + self.eps * t[0]
            )
            sorted_prims = [p for idx, p in sorted_prims]

            n = len(sorted_prims)
            if n <= 1:
                continue

            # prefix bounds
            left_bounds = [None] * n
            bounds = None
            for i in range(n):
                box = sorted_prims[i].bounding_box
                if bounds is None:
                    bounds = box
                else:
                    mn, mx = bounds
                    bmn, bmx = box
                    bounds = (np.minimum(mn, bmn), np.maximum(mx, bmx))
                left_bounds[i] = bounds

            # suffix bounds
            right_bounds = [None] * n
            bounds = None
            for i in reversed(range(n)):
                box = sorted_prims[i].bounding_box
                if bounds is None:
                    bounds = box
                else:
                    mn, mx = bounds
                    bmn, bmx = box
                    bounds = (np.minimum(mn, bmn), np.maximum(mx, bmx))
                right_bounds[i] = bounds

            # перебор split-позиций
            for i in range(1, n):
                left_count = i
                right_count = n - i
                SA_L = self.surface_area_box(left_bounds[i - 1])
                SA_R = self.surface_area_box(right_bounds[i])

                cost = left_count * (SA_L / parent_area) + right_count * (SA_R / parent_area)

                # только если обе стороны непустые
                left_candidate = sorted_prims[:i]
                right_candidate = sorted_prims[i:]
                if len(left_candidate) == 0 or len(right_candidate) == 0:
                    continue

                if cost < best_cost:
                    best_cost = cost
                    best_axis = axis
                    best_left = left_candidate
                    best_right = right_candidate

        # защита: если деление невозможно
        if best_axis is None or best_left is None or best_right is None:
            return None, None, None

        return best_axis, best_left, best_right
    
    
    def split_by_vah(self):
        pass
    
    
    def compute_bounds(self, primitives):
        mins = []
        maxs = []

        for p in primitives:
            mn, mx = p.bounding_box
            mins.append(mn)
            maxs.append(mx)

        return np.min(mins, axis=0), np.max(maxs, axis=0)
    
    
    def prepare_mesh(self, esc_enable: bool = False):
        logger.info("BVHBuilder: prepare mesh started, esc: %s", esc_enable)
        for face in self.mesh.faces:
            if esc_enable:
                bounding_boxes = self.early_split_clipping(face)
                self.primitives += bounding_boxes
            else:
                bounding_box = self.get_aabb_box(face)
                self.primitives.append(BVHPrimitive(bounding_box, face))
        logger.info("BVHBuilder: total primitives: %s", len(self.primitives))
        logger.info("BVHBuilder: prepare_mesh finished")
    
    
    def build_node(self, primitives, face_on_leaf=1, split_func="sah"):
        node = BVHNode()
        node.node_id = self.node_id
        self.node_id += 1

        if len(primitives) <= face_on_leaf:
            node.is_leaf = True
            node.primitives = primitives
            # кэшируем AABB для листа один раз
            node.bounding_box = self.compute_bounds(primitives)
            logger.debug("BVHBuilder: build node №%s, leaf: %s, primitives: %s", 
                          node.node_id, node.is_leaf, len(node.primitives))
            return node

        if  split_func == "sah":
            axis, left, right = self.find_best_split_sah(primitives)
        elif split_func == "vah":
            axis, left, right = self.find_best_split_sah(primitives)
        else:
            raise ValueError("BVHBuilder: build_node unknown split function")

        if axis is None or not left or not right:
            # Если разделение не удалось, делаем лист
            node.is_leaf = True
            node.primitives = primitives
            node.children = ()
            node.bounding_box = self.compute_bounds(primitives)
            logger.debug("BVHBuilder: cant split, build node №%s, leaf: %s, primitives: %s,", 
                          node.node_id, node.is_leaf, len(node.primitives))
            return node

        # рекурсия только с непустыми списками
        left_child = self.build_node(left, face_on_leaf=face_on_leaf, split_func=split_func)
        right_child = self.build_node(right, face_on_leaf=face_on_leaf, split_func=split_func)
        node.children = (left_child, right_child)
        # AABB внутреннего узла — объединение AABB детей
        if left_child.bounding_box is not None and right_child.bounding_box is not None:
            mn1, mx1 = left_child.bounding_box
            mn2, mx2 = right_child.bounding_box
            node.bounding_box = (np.minimum(mn1, mn2), np.maximum(mx1, mx2))
        logger.debug("BVHBuilder: build node №%s, leaf: %s", node.node_id, node.is_leaf)
        return node
    
    
    def build_tree(self, face_on_leaf=1, split_func: str = "sah"):
        logger.info("BVHBuilder: build_tree started")
        if not self.primitives:
            return None

        self.node_id = 0
        self.root_node = self.build_node(self.primitives, face_on_leaf=face_on_leaf, split_func=split_func)
        logger.info("BVHBuilder: build root node №%s, primitives: %s, total nodes: %s", self.root_node.node_id, len(self.root_node.primitives), self.node_id-1)
        logger.info("BVHBuilder: build_node finished")
        
    
    def get_tree_graph(self):
        if self.root_node is None:
            raise RuntimeError("BVH: tree is not built. Call build_tree() first.")
        root = self.root_node

        def _dfs(node: BVHNode) -> None:
            self.graph.add_node(
                node.node_id,
                label=str(node.node_id),
                is_leaf=node.is_leaf,
            )
            for child in node.children:
                if child is not None and child.primitives is not None:
                    self.graph.add_edge(node.node_id, child.node_id)
                    _dfs(child)

        _dfs(root)

        logger.info(
            "BVHTree: build_graph finished; nodes=%d, edges=%d",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )

        return self.graph
    
    
    def boxes_intersect(self, node1: BVHNode, node2: BVHNode) -> bool:
        """
        Быстрая проверка пересечения AABB двух узлов.

        Использует заранее закэшированные bounding_box у узлов, чтобы
        избежать повторных рекурсивных обходов поддеревьев.
        """
        if node1.bounding_box is None or node2.bounding_box is None:
            return False

        min1, max1 = node1.bounding_box
        min2, max2 = node2.bounding_box

        # проверка пересечения по всем осям
        return bool(
            not (
                max1[0] < min2[0]
                or max2[0] < min1[0]
                or max1[1] < min2[1]
                or max2[1] < min1[1]
                or max1[2] < min2[2]
                or max2[2] < min1[2]
            )
        )
    
    def traversal_tree(self):
        if self.root_node is None:
            raise RuntimeError("BVH: tree is not built. Call build_tree() first.")
        logger.info("BVHBuilder: traversal_tree started")

        # Инициализация кэша проверенных пар
        checked_pairs = set()
        # Стек для обхода: пары узлов
        stack = [(self.root_node, self.root_node)]

        while stack:
            node1, node2 = stack.pop()
            if node1 is None or node2 is None:
                continue

            # Проверяем пересечение AABB узлов
            if not self.boxes_intersect(node1, node2):
                continue

            # Если оба узла листы, проверяем все примитивы попарно
            if node1.is_leaf and node2.is_leaf:
                for primitive_a in node1.primitives:
                    for primitive_b in node2.primitives:
                        if primitive_a.face.glo_id == primitive_b.face.glo_id:
                            continue  # не проверяем один и тот же примитив
                        pair_key = tuple(sorted([primitive_a.face.glo_id, primitive_b.face.glo_id]))
                        if pair_key in checked_pairs:
                            continue
                        checked_pairs.add(pair_key)

                        pair1 = IntersectionFinder(eps=self.eps)
                        find_segment, status, broken = pair1.find_intersection_segment(primitive_a.face, primitive_b.face)

                        # Обработка результатов
                        if find_segment and status == 1 and broken == 0:
                            # успешное пересечение
                            self.p_valid.append((primitive_a.face, primitive_b.face, find_segment))
                            if primitive_a.face.glo_id not in self.f_fix.keys():
                                self.f_fix[primitive_a.face.glo_id] = (primitive_a.face, [])
                            if primitive_b.face.glo_id not in self.f_fix.keys():
                                self.f_fix[primitive_b.face.glo_id] = (primitive_b.face, [])
                            self.f_fix[primitive_a.face.glo_id][1].append(find_segment)
                            self.f_fix[primitive_b.face.glo_id][1].append(find_segment)
                        elif (find_segment is None and status == 1 and broken == 1) or \
                            (find_segment is None and status == 0 and broken in (0, 1)):
                            # сломанные пересечения
                            self.p_invalid.append((primitive_a.face, primitive_b.face))
                        # if find_segment is None and status == 0: пропускаем
                continue

            # Если хотя бы один узел не лист, добавляем детей в стек
            children1 = [node1] if node1.is_leaf else [node1.children[0], node1.children[1]]
            children2 = [node2] if node2.is_leaf else [node2.children[0], node2.children[1]]

            for c1 in children1:
                for c2 in children2:
                    if c1 is None or c2 is None:
                        continue
                    # Добавляем только если AABB пересекаются
                    if self.boxes_intersect(c1, c2):
                        stack.append((c1, c2))
        logger.debug("BVHBuilder: f_fix: %s, p_valid: %s, p_invalid: %s", len(self.f_fix), len(self.p_valid), len(self.p_invalid))
        logger.info("BVHBuilder: traversal_tree finished")
    
    
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(levelname)s: %(message)s'
    )
    mesh = Mesh("examples/small_sphere_double.dat")
    #mesh = Mesh("examples/sphere_double.dat")
    mesh = Mesh("examples/bunny_double.dat")
    
    bvh = BVHBuilder(mesh=mesh, eps=1e-12)
    bvh.prepare_mesh(esc_enable=False)
    bvh.build_tree(face_on_leaf=1, split_func="sah")
    bvh.traversal_tree()
