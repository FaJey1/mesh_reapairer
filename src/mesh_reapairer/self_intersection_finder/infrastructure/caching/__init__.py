"""
Модуль кэширования для оптимизации поиска пересечений.
"""

from .pair_cache import PairCache
from .adjacency_cache import AdjacencyCache

__all__ = ['PairCache', 'AdjacencyCache']