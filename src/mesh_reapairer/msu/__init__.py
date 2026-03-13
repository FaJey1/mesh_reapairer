"""
Mesh structural utilities (MSU).

This module defines core data structures for representing polygonal meshes.
It is intentionally lightweight and independent of concrete algorithms
for intersection detection, restoration, or visualization.
"""

from mesh_reapairer.msu.mesh import *

__all__ = ["Node", "Edge", "Face", "Zone", "Mesh"]
