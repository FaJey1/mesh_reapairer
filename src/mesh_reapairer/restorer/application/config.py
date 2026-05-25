from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RestorerConfig:
    """Конфигурация триангуляции + удаления внутренних граней."""

    epsilon: float = 1e-6
    logging_level: str = "INFO"

    # MeshWalker
    enable_inner_removal: bool = True
    enable_cleanup: bool = True   # удалять свободные рёбра и изолированные узлы

    @classmethod
    def create_default(cls) -> "RestorerConfig":
        return cls()

    @classmethod
    def create_debug(cls) -> "RestorerConfig":
        return cls(logging_level="DEBUG")
