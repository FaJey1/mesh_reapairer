"""
Quick pipeline test with topology metrics.
"""
from __future__ import annotations
import sys, logging

logging.disable(logging.CRITICAL)
BASE = "/Users/tsyngalevpavel/Documents/RAN/PhD/mesh_reapairer"
sys.path.insert(0, BASE + "/src")

from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh
from mesh_reapairer.src.mesh_reapairer.self_intersection_finder import find_self_intersections
from mesh_reapairer.src.mesh_reapairer.restorer.application.restore_mesh import RestoreMeshUseCase

def topo(mesh, label):
    b = [e for e in mesh.edges if e.is_border()]
    r = [e for e in mesh.edges if len(e.faces) > 2]
    V, E, F = len(mesh.nodes), len(mesh.edges), len(mesh.faces)
    chi = V - E + F
    print(f"{label}: F={F} V={V} E={E} boundary={len(b)} ring={len(r)} χ={chi}")
    return len(b), len(r), chi

dat = sys.argv[1] if len(sys.argv) > 1 else BASE + "/examples/sphere_double.dat"
out = sys.argv[2] if len(sys.argv) > 2 else None

print(f"Loading {dat}...")
mesh = Mesh()
mesh.load(dat)
topo(mesh, "Original")

result = find_self_intersections(mesh)
print(f"Intersections: {len(result.valid_pairs)} pairs")

restorer = RestoreMeshUseCase()
res = restorer.execute(mesh, result)

b, r, chi = topo(mesh, "Final")

if out:
    mesh.save(out)
    print(f"Saved: {out}")

if b == 0 and r == 0 and chi == 2:
    print("✓ PERFECT: closed manifold")
elif b == 0:
    print(f"✓ No boundary edges (ring={r}, χ={chi})")
else:
    print(f"✗ Has boundary edges: {b}")
