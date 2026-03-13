from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from mesh_reapairer.msu.mesh import Face, Node
from mesh_reapairer.vizualizator.face_plotter import *
from mesh_reapairer.vizualizator.segment_plotter import *


logger = logging.getLogger(__name__)
#logging.basicConfig(filename="intersection.log", level=logging.DEBUG)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


@dataclass
class Segment:
    nodes: List[Node] = None
    face_a: Face = None
    face_b: Face = None
    face_a_classificator: List[Tuple[Optional[Node], List[int]]] = None
    face_b_classificator: List[Tuple[Optional[Node], List[int]]] = None


class IntersectionFinder:
    def __init__(self, eps: int =1e-16):
        self.eps = eps
        self.classificator_node_id = 0
        self.impossible_cases = [[0, 0, 1], [0, 0, 2], [0, 1, 2], [1, 2, 2], [2, 2, 2]]
        self.special_cases = [[0, 0, 0]]
        
        
    def _is_neighbors(self, face_a: Face, face_b: Face):
        common_edges = set(face_a.edges) & set(face_b.edges)
        if common_edges:
            logger.debug("IntersectionFinder: face_%s, face_%s is neighbor, skip intersection check", face_a.glo_id, face_b.glo_id)
            return True
        
        logger.debug("IntersectionFinder: face_%s, face_%s is not neighbor, continue intersection check", face_a.glo_id, face_b.glo_id)
        return False


    def _get_face_plane(self, 
                       face: Face) -> Tuple[float, float, float, float]:
        """
        Находит уравнение плоскости для грани face: ax + by + cz + d = 0.

        Parameters
        ----------
        face : Face
            Грань (треугольник).

        Returns
        -------
        tuple[float, float, float, float]
            Коэффициенты (a, b, c, d) плоскости.
        """
        if face.normal is None:
            face.calculate_normal()
        n = face.normal
        a_pt = face.nodes[0].p
        d = -np.dot(n, a_pt)
        return float(n[0]), float(n[1]), float(n[2]), float(d)
    
    
    def _edge_plane_class(self, edge: Edge, plane: Tuple[float, float, float, float]):
        """
        p0, p1 : np.array
        d0, d1 : signed distances to plane
        """
        p0, p1 = edge.points()
        a, b, c, d = plane
        d0 = a * p0[0] + b * p0[1] + c * p0[2] + d
        d1 = a * p1[0] + b * p1[1] + c * p1[2] + d
        
        # оба почти на плоскости -> компланарное ребро
        if abs(d0) < self.eps and abs(d1) < self.eps:
            return 0, None

        # по одну сторону -> нет пересечения
        if d0 * d1 > 0.0:
            return 0, None

        # точка пересечения
        t = d0 / (d0 - d1)

        if abs(t) < self.eps:
            p = p0
            res_code = 1
        elif abs(t - 1.0) < self.eps:
            p = p1
            res_code = 1
        else:
            p = p0 + t * (p1 - p0)
            res_code = 2

        node = Node(p)
        node.glo_id = self.classificator_node_id
        self.classificator_node_id += 1
        
        return res_code, node
    
    
    def _classify_face_plane(self, face: Face, plane: Tuple[float, float, float, float]):
        combined = []
        for e in face.edges:
            code, pt = self._edge_plane_class(edge=e, plane=plane)
            combined.append((code, pt))
                
        combined.sort(key=lambda x: x[0])

        # Разделяем обратно на два списка
        codes = [item[0] for item in combined]
        points = [item[1] for item in combined]
        
        return codes, points


    def _faces_coplanar(self, face_a: Face, face_b: Face):
        plane_b = self._get_face_plane(face_b)

        for n in face_a.nodes:
            if abs(
                plane_b[0] * n.p[0]
            + plane_b[1] * n.p[1]
            + plane_b[2] * n.p[2]
            + plane_b[3]
            ) > self.eps:
                return False

        return True
    
    
    def _fix_vertex_case(self, face: Face, codes: List[int], points: List[Node]):
        if codes != [0, 1, 1]:
            return codes, points
    
        if None in points:
            return [0, 0, 0], []
        
        p = points[0].p
        for v in face.nodes:
            if np.max(np.abs(p - v.p)) < self.eps:
                return [0, 0, 0], []

        return codes, points
    
    
    def clasify_edges_intersection(self, 
                                   face_a: Face, 
                                   face_b: Face) -> Tuple[Tuple[List], Tuple[List], bool]:
        # --- компланарность ---
        if self._faces_coplanar(face_a, face_b):
            return tuple, tuple, True

        plane_a = self._get_face_plane(face_a)
        plane_b = self._get_face_plane(face_b)

        codes_ab, pts_ab = self._classify_face_plane(face_a, plane_b)
        codes_ba, pts_ba = self._classify_face_plane(face_b, plane_a)

        codes_ab, pts_ab = self._fix_vertex_case(face_a, codes_ab, pts_ab)
        codes_ba, pts_ba = self._fix_vertex_case(face_b, codes_ba, pts_ba)

        return (codes_ab, pts_ab), (codes_ba, pts_ba), False


    def find_common_intersection_segment(self,
                                         res_ab: Tuple[List],
                                         res_ba: Tuple[List]) -> List[Node]:
        nodes = []
        ab = []
        for code, node in zip(res_ab[0], res_ab[0]):
            if code in [1, 2]:
                ab.append(node)
        ba = []
        for code, node in zip(res_ba[0], res_ba[0]):
            if code in [1, 2]:
                ba.append(node)
        print(res_ab[0], res_ba[0])
        print(len(ab), len(ba))
        return nodes
        
        
    def _point_on_segment(self, p, a, b):
        ab = b - a
        ap = p - a

        # коллинеарность
        if np.linalg.norm(np.cross(ab, ap)) > self.eps:
            return False

        t = np.dot(ap, ab) / np.dot(ab, ab)
        return -self.eps <= t <= 1.0 + self.eps
    
    
    def _segment_segment_intersection(self, A0, A1, B0, B1):
        d = A1 - A0
        k = np.argmax(np.abs(d))  # ось

        def proj(p): return p[k]

        a0, a1 = proj(A0), proj(A1)
        b0, b1 = proj(B0), proj(B1)

        lo = max(min(a0, a1), min(b0, b1))
        hi = min(max(a0, a1), max(b0, b1))

        if hi < lo - self.eps:
            return []

        if abs(hi - lo) < self.eps:
            t = (lo - a0) / (a1 - a0)
            return [A0 + t * d]

        t0 = (lo - a0) / (a1 - a0)
        t1 = (hi - a0) / (a1 - a0)
        return [A0 + t0 * d, A0 + t1 * d]
    
    
    def _extract_intersection_nodes(self, codes: List[int], points: List[Node]):
        """
        Возвращает список Node, соответствующих кодам 1 и 2
        """
        res = []
        for c,p in zip(codes, points):
            if c in (1, 2):
                res.append(p)
        return res
    
    
    def find_common_intersection_segment(self, res_ab: Tuple, res_ba: Tuple):
        codes_ab, pts_ab = res_ab
        codes_ba, pts_ba = res_ba
        nodes = []
        ab_pts = self._extract_intersection_nodes(codes_ab, pts_ab)
        ba_pts = self._extract_intersection_nodes(codes_ba, pts_ba)

        # нет точек
        if not ab_pts or not ba_pts:
            return []

        # отрезок
        if len(ab_pts) == 2 and len(ba_pts) == 2:
            P = self._segment_segment_intersection(
                ab_pts[0].p, ab_pts[1].p,
                ba_pts[0].p, ba_pts[1].p
            )
            nodes = [Node(p) for p in P]

        # точка и отрезок
        if len(ab_pts) == 1 and len(ba_pts) == 2:
            p = ab_pts[0].p
            if self._point_on_segment(p, ba_pts[0].p, ba_pts[1].p):
                nodes = [Node(p)]

        if len(ba_pts) == 1 and len(ab_pts) == 2:
            p = ba_pts[0].p
            if self._point_on_segment(p, ab_pts[0].p, ab_pts[1].p):
                nodes = [Node(p)]

        # точка и точка
        if len(ab_pts) == 1 and len(ba_pts) == 1:
            if np.max(np.abs(ab_pts[0].p - ba_pts[0].p)) < self.eps:
                nodes = [Node(ab_pts[0].p)]
                
        for node in nodes:
            node.glo_id = self.classificator_node_id
            self.classificator_node_id += 1
        return nodes
    
    
    def find_intersection_segment(self,
                                    face_a: Face,
                                    face_b: Face
                                ) -> Tuple[Segment, int, int]:

        if self._is_neighbors(face_a, face_b):
            return Segment(), 0, 0

        classificator_ab, classificator_ba, is_complanar = self.clasify_edges_intersection(face_a, face_b)
        logger.debug("IntersectionFinder: check face_%s and face_%s, classificator_ab %s, classificator_ba %s", face_a.glo_id, face_b.glo_id, classificator_ab[0], classificator_ba[0])
        if is_complanar:
            logger.warning("IntersectionFinder: face_%s and face_%s is complanar", face_a.glo_id, face_b.glo_id)
            raise ValueError("is_complanar")

        if (
            classificator_ab[0] in self.special_cases
            or classificator_ba[0] in self.special_cases
        ):
            return Segment(), 0, 0

        if (
            classificator_ab[0] in self.impossible_cases
            or classificator_ba[0] in self.impossible_cases
        ):
            segment = Segment(
                nodes=None,
                face_a=face_a,
                face_b=face_b,
                face_a_classificator=classificator_ab,
                face_b_classificator=classificator_ba,
            )
            return segment, 1, 1

        nodes = self.find_common_intersection_segment(
            res_ab=classificator_ab,
            res_ba=classificator_ba,
        )
        if not nodes:
            return Segment(), 0, 0
        segment = Segment(
                            nodes=nodes,
                            face_a=face_a,
                            face_b=face_b,
                            face_a_classificator=classificator_ab,
                            face_b_classificator=classificator_ba)
        return segment, 1, 0
    


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(levelname)s: %(message)s'
    )
    mesh = Mesh("examples/small_sphere_double.dat")
    
    pair1 = IntersectionFinder()
    pair2 = IntersectionFinder()
    pair3 = IntersectionFinder()
    
    # касание в 1 точке
    find_segment, status, broken = pair1.find_intersection_segment(mesh.faces[53], mesh.faces[12])
    print(find_segment.nodes, status, broken)
    
    # касание по ребру 
    find_segment, status, broken = pair2.find_intersection_segment(mesh.faces[0], mesh.faces[2])
    print(find_segment.nodes, status, broken)
    
    # пересечение
    find_segment, status, broken = pair3.find_intersection_segment(mesh.faces[21], mesh.faces[97])
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    plot_face(ax, mesh.faces[53], color="blue", edges_enable=True, draw_aabb=True, label=True, plane=True)
    plot_face(ax, mesh.faces[12], color="red", edges_enable=True, draw_aabb=True, label=True, plane=True)
    # plot_face(ax, mesh.faces[21], color="blue", edges_enable=True, draw_aabb=True, label=True, plane=True)
    # plot_face(ax, mesh.faces[97], color="red", edges_enable=True, draw_aabb=True, label=True, plane=True)
    # plot_face(ax, mesh.faces[0], color="blue", edges_enable=True, draw_aabb=True, label=True, plane=True)
    # plot_face(ax, mesh.faces[2], color="red", edges_enable=True, draw_aabb=True, label=True, plane=True)
    # plot_face(ax, mesh.faces[0], color="blue", edges_enable=True, draw_aabb=True, label=True, plane=True)
    # plot_face(ax, mesh.faces[1], color="red", edges_enable=True, draw_aabb=True, label=True, plane=True)
    #plot_segment(ax, find_segment.nodes, color="red")
    ax.set_title("Face Visualization")
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()
    