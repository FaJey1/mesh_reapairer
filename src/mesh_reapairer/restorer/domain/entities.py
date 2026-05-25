from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Set, Tuple

import numpy as np

if TYPE_CHECKING:
    from mesh_reapairer.src.mesh_reapairer.msu.mesh import Mesh


@dataclass
class RestorationResult:
    """Результат триангуляции f_fix-ячеек + удаления внутренних граней."""

    mesh: "Mesh"

    # FanTriangulator stats
    f_fix_count: int = 0
    new_faces_count: int = 0
    f_fix_ids: Set[int] = field(default_factory=set)
    new_face_ids: Set[int] = field(default_factory=set)
    triangulation_time_ms: float = 0.0

    # MeshWalker stats
    removed_faces_count: int = 0
    walker_time_ms: float = 0.0
    outer_face_ids_set: Set[int] = field(default_factory=set)

    # Геометрия удалённых внутренних граней (для визуализации панели 7)
    inner_face_geometries: List[Tuple[np.ndarray, np.ndarray, np.ndarray]] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Свойства для совместимости с CLI
    # ------------------------------------------------------------------

    @property
    def faces_triangulated(self) -> int:
        return self.f_fix_count

    @property
    def new_faces_created(self) -> int:
        return self.new_faces_count

    @property
    def neighbor_faces_split(self) -> int:
        return 0

    @property
    def faces_removed(self) -> int:
        return self.removed_faces_count

    @property
    def outer_faces_count(self) -> int:
        return len(self.mesh.faces)

    @property
    def outer_face_ids(self) -> Set[int]:
        if self.outer_face_ids_set:
            return self.outer_face_ids_set
        return {f.glo_id for f in self.mesh.faces}

    @property
    def removal_time_ms(self) -> float:
        return self.walker_time_ms

    def total_time_ms(self) -> float:
        return self.triangulation_time_ms + self.walker_time_ms

    def summary(self) -> str:
        return (
            f"FanTriangulation: f_fix={self.f_fix_count}, "
            f"new={self.new_faces_count}, "
            f"removed_inner={self.removed_faces_count}, "
            f"time={self.triangulation_time_ms:.1f}+{self.walker_time_ms:.1f}ms"
        )
