"""
Diagnostic: trace why 13 boundary edges after triangulation expand to 224 after inner removal.
"""
from __future__ import annotations

import sys
import logging
from collections import deque

logging.disable(logging.CRITICAL)

BASE = "/Users/tsyngalevpavel/Documents/RAN/PhD/mesh_reapairer"
sys.path.insert(0, BASE + "/src")

from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import find_self_intersections
from mesh_reapairer.restorer.infrastructure.triangulator.face_triangulator import FaceTriangulator

def topology(mesh):
    boundary = [e for e in mesh.edges if e.is_border()]
    ring = [e for e in mesh.edges if len(e.faces) > 2]
    V = len(mesh.nodes)
    E = len(mesh.edges)
    F = len(mesh.faces)
    return V, E, F, len(boundary), len(ring), V - E + F

dat = sys.argv[1] if len(sys.argv) > 1 else BASE + "/examples/sphere_double.dat"
print(f"Loading {dat}...")
mesh = Mesh()
mesh.load(dat)
print(f"Original: F={len(mesh.faces)}")

result = find_self_intersections(mesh)
print(f"Intersections: {len(result.valid_pairs)} pairs")

tri = FaceTriangulator()
ft, nf, ns, inner_face_ids = tri.triangulate_all(mesh, result)
V, E, F, b, r, chi = topology(mesh)
print(f"After tri: V={V} E={E} F={F} boundary={b} ring={r} chi={chi}")
print(f"inner_face_ids count: {len(inner_face_ids)}")

# Find the 13 boundary edges after triangulation
boundary_edges_after_tri = [e for e in mesh.edges if e.is_border()]
print(f"\nBoundary edges after tri ({len(boundary_edges_after_tri)}):")
for e in boundary_edges_after_tri[:20]:
    fids = [f.glo_id for f in e.faces]
    nids = [n.glo_id for n in e.nodes]
    inner_flag = [f.glo_id in inner_face_ids for f in e.faces]
    print(f"  edge nodes={nids} faces={fids} inner_flags={inner_flag}")

# Now simulate BFS manually and find which faces are reachable/unreachable
def find_outer_bfs(mesh, inner_face_ids_set):
    import numpy as np
    start = min(mesh.faces, key=lambda f: f.center()[0])
    visited = set()
    q = deque([start])
    while q:
        face = q.popleft()
        if face in visited:
            continue
        visited.add(face)
        for edge in face.edges:
            n_faces = len(edge.faces)
            if n_faces == 0:
                continue
            elif n_faces <= 2:
                nb = face.neighbour(edge)
                if nb is not None and nb not in visited and nb.glo_id not in inner_face_ids_set:
                    q.append(nb)
            else:
                # ring edge: min-angle neighbor
                pretenders = [f for f in edge.faces if f is not face and f.glo_id not in inner_face_ids_set]
                if pretenders:
                    p0, p1 = edge.nodes[0].p, edge.nodes[1].p
                    d = p1 - p0
                    d_len = float(np.linalg.norm(d))
                    if d_len < 1e-15:
                        nb = pretenders[0]
                    else:
                        d = d / d_len
                        ec = (p0 + p1) * 0.5
                        def perp(v):
                            return v - float(np.dot(v, d)) * d
                        v_ref = perp(face.center() - ec)
                        v_ref_len = float(np.linalg.norm(v_ref))
                        if v_ref_len < 1e-15:
                            nb = pretenders[0]
                        else:
                            v_ref = v_ref / v_ref_len
                            n = face.triangle().normal()
                            n_perp = perp(n)
                            n_perp_len = float(np.linalg.norm(n_perp))
                            if n_perp_len < 1e-15:
                                nb = pretenders[0]
                            else:
                                n_perp = n_perp / n_perp_len
                                y_2d = np.cross(d, v_ref)
                                n_side = float(np.dot(n_perp, y_2d))
                                rotation_sign = 1.0 if n_side >= 0.0 else -1.0
                                best = None
                                min_angle = float("inf")
                                for f in pretenders:
                                    v = perp(f.center() - ec)
                                    v_len = float(np.linalg.norm(v))
                                    if v_len < 1e-15:
                                        continue
                                    v = v / v_len
                                    cos_a = float(np.clip(np.dot(v_ref, v), -1.0, 1.0))
                                    sin_a_ccw = float(np.dot(np.cross(v_ref, v), d))
                                    sin_a = rotation_sign * sin_a_ccw
                                    angle = float(np.arctan2(sin_a, cos_a))
                                    if angle <= 1e-9:
                                        angle += 2.0 * np.pi
                                    if angle < min_angle:
                                        min_angle = angle
                                        best = f
                                nb = best if best is not None else pretenders[0]
                    if nb is not None and nb not in visited:
                        q.append(nb)
    return visited

import numpy as np
outer = find_outer_bfs(mesh, inner_face_ids)
inner_bfs = [f for f in mesh.faces if f not in outer]

print(f"\nBFS result: outer={len(outer)}, inner(to delete)={len(inner_bfs)}")

# Which faces adjacent to the 13 boundary edges are in inner_bfs?
print("\nBoundary edge faces: outer vs inner_bfs:")
for e in boundary_edges_after_tri[:20]:
    fids = [f.glo_id for f in e.faces]
    status = ["OUTER" if f in outer else "INNER(del)" for f in e.faces]
    print(f"  edge nodes={[n.glo_id for n in e.nodes]} faces={list(zip(fids,status))}")

# How many of the faces adjacent to boundary edges would be deleted?
deleted_boundary_face_ids = set()
for e in boundary_edges_after_tri:
    for f in e.faces:
        if f not in outer:
            deleted_boundary_face_ids.add(f.glo_id)

print(f"\nFaces adjacent to boundary edges that BFS marks as inner: {len(deleted_boundary_face_ids)}")

# After deletion, simulate what edges become boundary
# Build edge->faces map after simulated deletion
deleted_ids = {f.glo_id for f in inner_bfs}
new_boundary = []
for e in mesh.edges:
    remaining = [f for f in e.faces if f.glo_id not in deleted_ids]
    if len(remaining) == 1:
        new_boundary.append(e)

print(f"\nSimulated boundary after inner removal: {len(new_boundary)}")

# Check: are all inner_face_ids faces in inner_bfs?
inner_ids_in_bfs = inner_face_ids & {f.glo_id for f in inner_bfs}
inner_ids_in_outer = inner_face_ids & {f.glo_id for f in outer}
print(f"\ninner_face_ids marked but BFS kept (outer): {len(inner_ids_in_outer)}")
print(f"inner_face_ids marked and BFS removed (inner): {len(inner_ids_in_bfs)}")

# Examine any inner_face_ids that BFS kept as outer
if inner_ids_in_outer:
    print("Sample inner_face_ids that BFS classifies as outer:")
    for fid in list(inner_ids_in_outer)[:5]:
        f = next(x for x in mesh.faces if x.glo_id == fid)
        print(f"  glo_id={fid} center={f.center().round(4)}")

# Find connected components after deletion
def connected_components(faces):
    face_set = set(faces)
    fid_to_face = {f.glo_id: f for f in faces}
    visited = set()
    components = []
    for start in faces:
        if start in visited:
            continue
        comp = []
        q = deque([start])
        while q:
            f = q.popleft()
            if f in visited:
                continue
            visited.add(f)
            comp.append(f)
            for e in f.edges:
                for nb in e.faces:
                    if nb in face_set and nb not in visited:
                        q.append(nb)
        components.append(comp)
    return components

outer_comps = connected_components(list(outer))
print(f"\nConnected components of outer faces: {len(outer_comps)}")
for i, comp in enumerate(sorted(outer_comps, key=len, reverse=True)[:5]):
    print(f"  comp {i}: {len(comp)} faces")
