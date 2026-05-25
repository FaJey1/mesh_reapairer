"""Debug why _can_split fails for all pairs."""
from __future__ import annotations
import sys, logging
import numpy as np

logging.disable(logging.CRITICAL)
BASE = "/Users/tsyngalevpavel/Documents/RAN/PhD/mesh_reapairer"
sys.path.insert(0, BASE + "/src")

from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import find_self_intersections
from mesh_reapairer.restorer.infrastructure.triangulator.face_triangulator import FaceTriangulator

dat = BASE + "/examples/sphere_double.dat"
mesh = Mesh()
mesh.load(dat)
result = find_self_intersections(mesh)

tri = FaceTriangulator()
zone = mesh.zones[0]
deleted_ids = set()
inner_face_ids = set()
split_map = {}

print(f"Total valid pairs: {len(result.valid_pairs)}")

pair_results = {"both_ok": 0, "a_fail": 0, "b_fail": 0, "both_fail": 0, "no_candidates": 0}

for i, (face_a, face_b, segment) in enumerate(result.valid_pairs[:10]):
    if segment.nodes is None or len(segment.nodes) < 2:
        continue

    n1 = mesh.add_node(segment.nodes[0].p.copy(), zone, is_merge_nodes=True)
    n2 = mesh.add_node(segment.nodes[-1].p.copy(), zone, is_merge_nodes=True)

    cands_a = tri._get_current_outer_faces(face_a, split_map, deleted_ids, inner_face_ids)
    cands_b = tri._get_current_outer_faces(face_b, split_map, deleted_ids, inner_face_ids)

    print(f"\nPair {i}: face_a={face_a.glo_id} face_b={face_b.glo_id}")
    print(f"  n1={n1.p.round(6)} n2={n2.p.round(6)}")
    print(f"  cands_a={[f.glo_id for f in cands_a]}, cands_b={[f.glo_id for f in cands_b]}")

    for f in cands_a:
        cs = tri._can_split(f, n1, n2)
        ei_in, _ = tri._point_on_face_edge(f, n1.p)
        ei_out, _ = tri._point_on_face_edge(f, n2.p)
        print(f"  cand_a={f.glo_id}: _can_split={cs} ei_in={ei_in} ei_out={ei_out}")
        if not cs:
            # Check each edge
            V = f.nodes
            for idx in range(3):
                t = tri._t_on_segment(n1.p, V[idx].p, V[(idx+1)%3].p)
                print(f"    edge {idx} ({V[idx].glo_id}-{V[(idx+1)%3].glo_id}): n1 t={t}")
            for idx in range(3):
                t = tri._t_on_segment(n2.p, V[idx].p, V[(idx+1)%3].p)
                print(f"    edge {idx} ({V[idx].glo_id}-{V[(idx+1)%3].glo_id}): n2 t={t}")

    for f in cands_b:
        cs = tri._can_split(f, n1, n2)
        ei_in, _ = tri._point_on_face_edge(f, n1.p)
        ei_out, _ = tri._point_on_face_edge(f, n2.p)
        print(f"  cand_b={f.glo_id}: _can_split={cs} ei_in={ei_in} ei_out={ei_out}")
