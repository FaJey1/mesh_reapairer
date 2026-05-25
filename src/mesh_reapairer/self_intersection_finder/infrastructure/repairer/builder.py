import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from ...application.config import BVHConfig
from ...domain.entities import BVHNode, Primitive
from ...domain.enums import SplitStrategy
from ...domain.value_objects import AABB
from ...utils.geometry import (
    compute_face_aabb,
    compute_primitives_aabb,
    split_aabb,
    face_intersects_aabb
)

class IntersectionRepairer:
    def __init__(self, mesh, p_valid, p_invalid, eps: float = 1e-8):
        self.p_valid = p_valid
        self.p_invalid = p_invalid
        self.eps = eps
