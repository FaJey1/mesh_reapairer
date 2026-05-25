"""
Trace why specific faces are unreachable by BFS despite not being in inner_face_ids.
"""
from __future__ import annotations
import sys, logging
from collections import deque
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
ft, nf, ns, inner_face_ids = tri.triangulate_all(mesh, result)

# Faces adjacent to boundary edges that aren't in inner_face_ids:
target_ids = {8181, 8381, 8186}

face_map = {f.glo_id: f for f in mesh.faces}
print(f"inner_face_ids count: {len(inner_face_ids)}")
print(f"Total faces: {len(mesh.faces)}")

for fid in sorted(target_ids):
    f = face_map.get(fid)
    if f is None:
        print(f"Face {fid}: NOT FOUND")
        continue
    print(f"\n=== Face {fid} ===")
    print(f"  nodes: {[n.glo_id for n in f.nodes]}")
    print(f"  center: {f.center().round(4)}")
    print(f"  in inner_face_ids: {fid in inner_face_ids}")
    print(f"  edges ({len(f.edges)}):")
    for e in f.edges:
        nb_faces = e.faces
        nids = [n.glo_id for n in e.nodes]
        is_border = e.is_border()
        nb_info = []
        for nb in nb_faces:
            if nb is not f:
                inner_flag = nb.glo_id in inner_face_ids
                nb_info.append(f"face={nb.glo_id}(inner={inner_flag})")
        ring = len(nb_faces) > 2
        print(f"    edge {nids}: border={is_border} ring={ring} neighbors={nb_info}")

# Check if any path exists from outermost to target faces ignoring inner_face_ids
start = min(mesh.faces, key=lambda f: f.center()[0])
print(f"\nOutermost face: glo_id={start.glo_id}, center={start.center().round(4)}")

# BFS ignoring inner_face_ids (to see if target faces are even topologically connected)
visited_no_filter = set()
q = deque([start])
while q:
    face = q.popleft()
    if face in visited_no_filter:
        continue
    visited_no_filter.add(face)
    for e in face.edges:
        for nb in e.faces:
            if nb not in visited_no_filter:
                q.append(nb)
unreachable_all = [f for f in mesh.faces if f not in visited_no_filter]
print(f"Without any filter: visited={len(visited_no_filter)}, unreachable={len(unreachable_all)}")
for f in unreachable_all[:5]:
    print(f"  unreachable: glo_id={f.glo_id} in_inner={f.glo_id in inner_face_ids}")

# For each target face: what's the shortest path from outermost, ignoring inner_face_ids?
print("\nPath from outermost to target faces (ignoring inner_face_ids):")
for fid in sorted(target_ids):
    target = face_map.get(fid)
    if target is None:
        continue
    # BFS with path tracking
    prev = {start: None}
    q2 = deque([start])
    found = False
    while q2:
        cur = q2.popleft()
        if cur is target:
            found = True
            break
        for e in cur.edges:
            for nb in e.faces:
                if nb not in prev:
                    prev[nb] = cur
                    q2.append(nb)
    if found:
        path = []
        node = target
        while node is not None:
            path.append(node.glo_id)
            node = prev.get(node)
        path.reverse()
        print(f"  Path to {fid} (len={len(path)}): {path[:10]}...")
        # Find first inner_face_ids face on path
        for pid in path:
            if pid in inner_face_ids:
                print(f"    BLOCKED at face {pid} (in inner_face_ids)")
                # What edge connects pid to its prev?
                break
    else:
        print(f"  Face {fid}: no path found even without filter!")

# Check which edges block BFS from reaching targets
print("\nDetailed BFS path analysis (with inner_face_ids filter):")
for fid in sorted(target_ids):
    target = face_map.get(fid)
    if target is None:
        continue
    # Find faces 1-3 hops from target
    near = {target}
    frontier = [target]
    for hop in range(3):
        next_frontier = []
        for f in frontier:
            for e in f.edges:
                for nb in e.faces:
                    if nb not in near:
                        near.add(nb)
                        next_frontier.append(nb)
        frontier = next_frontier
    print(f"\n  Target {fid}: {len(near)} faces within 3 hops")
    inner_near = [f.glo_id for f in near if f.glo_id in inner_face_ids]
    outer_near = [f.glo_id for f in near if f.glo_id not in inner_face_ids]
    print(f"    inner nearby: {inner_near[:20]}")
    print(f"    outer nearby (non-inner): {outer_near[:20]}")
