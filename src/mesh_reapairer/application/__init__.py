"""
Application layer for mesh_reapairer.

Exposes high-level use cases (orchestrators) that compose domain modules
into end-user workflows.
"""

from mesh_reapairer.application.orchestrator import repair_mesh

__all__ = ["repair_mesh"]
