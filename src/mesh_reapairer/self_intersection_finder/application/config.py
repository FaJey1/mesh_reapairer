"""
Конфигурация для модуля поиска самопересечений.

Все параметры алгоритмов находятся в одном месте для гибкой настройки.
"""
from dataclasses import dataclass, field
from typing import Optional

from ..domain.enums import SplitStrategy


@dataclass
class BVHConfig:
    """
    Конфигурация построения BVH дерева.

    Attributes:
        strategy: Стратегия разбиения (SAH | LBVH | HYBRID)
        max_primitives_per_leaf: Максимальное количество примитивов в листе
        sah_bins: Количество bins для SAH (больше = точнее, но медленнее)
        sah_traversal_cost: Стоимость обхода узла для SAH
        sah_intersection_cost: Стоимость проверки пересечения для SAH
        enable_early_split_clipping: Включить Early Split Clipping
        esc_max_depth: Максимальная глубина рекурсии ESC
        esc_surface_area_threshold: Порог площади поверхности для ESC (0.7 = 70%)
        esc_min_surface_area: Минимальная площадь поверхности для остановки ESC
        morton_bits: Количество бит на ось для Morton codes (LBVH)
    """
    strategy: SplitStrategy = SplitStrategy.SAH
    max_primitives_per_leaf: int = 1

    # SAH parameters
    sah_bins: int = 32
    sah_traversal_cost: float = 1.0
    sah_intersection_cost: float = 1.0

    # ESC (Early Split Clipping) parameters
    enable_early_split_clipping: bool = False
    esc_max_depth: int = 3
    esc_surface_area_threshold: float = 0.7  # 70% от исходной площади
    esc_min_surface_area: float = 1e-6

    # Morton codes (LBVH) parameters
    morton_bits: int = 10  # 10 бит на ось = 30 бит total

    def validate(self) -> None:
        """Валидация параметров конфигурации."""
        if self.max_primitives_per_leaf < 1:
            raise ValueError("max_primitives_per_leaf must be >= 1")

        if self.sah_bins < 2:
            raise ValueError("sah_bins must be >= 2")

        if self.esc_max_depth < 0:
            raise ValueError("esc_max_depth must be >= 0")

        if not (0.0 < self.esc_surface_area_threshold <= 1.0):
            raise ValueError("esc_surface_area_threshold must be in (0.0, 1.0]")

        if self.esc_min_surface_area < 0:
            raise ValueError("esc_min_surface_area must be >= 0")

        if self.morton_bits < 1 or self.morton_bits > 21:
            raise ValueError("morton_bits must be in [1, 21] (max 63 bits total)")


@dataclass
class IntersectionConfig:
    """
    Конфигурация поиска пересечений.

    Attributes:
        epsilon: Точность вычислений с плавающей точкой (ЕДИНОЕ МЕСТО)
        parallel_angle_threshold: Порог угла для определения параллельности (радианы)
        parallel_distance_threshold: Минимальное расстояние между параллельными плоскостями для отброса
        coplanar_search_enabled: Включить поиск пересечений на копланарных гранях
        enable_pair_cache: Включить кэширование проверенных пар
    """
    epsilon: float = 1e-10  # ТОЧНОСТЬ ВЫЧИСЛЕНИЙ В ОДНОМ МЕСТЕ

    # Параллельные плоскости
    parallel_angle_threshold: float = 1e-6  # радианы
    parallel_distance_threshold: float = 1e-6  # единицы сетки

    # Копланарные грани
    coplanar_search_enabled: bool = True

    # Кэширование
    enable_pair_cache: bool = True

    def validate(self) -> None:
        """Валидация параметров конфигурации."""
        if self.epsilon <= 0:
            raise ValueError("epsilon must be > 0")

        if self.parallel_angle_threshold < 0:
            raise ValueError("parallel_angle_threshold must be >= 0")

        if self.parallel_distance_threshold < 0:
            raise ValueError("parallel_distance_threshold must be >= 0")


@dataclass
class GraphRecoveryConfig:
    """
    Конфигурация восстановления графа пересечений.

    Attributes:
        enable_recovery: Включить восстановление путей между якорями
        max_distance_threshold: Максимальное расстояние для фильтрации шумных impossible пар
        enable_spatial_filter: Включить пространственный фильтр impossible пар
        enable_topological_filter: Включить топологический фильтр impossible пар

        # PathFinder параметры
        use_adaptive_params: Автоматически подбирать max_distance и max_weight
        max_distance_multiplier: Множитель среднего размера ребра для max_distance
        max_weight_multiplier: Множитель для max_weight
        max_distance: Фиксированный порог евклидовой длины пути (если не adaptive)
        max_weight: Фиксированный порог веса пути (если не adaptive)

        # Segment recovery
        interpolation_mode: Режим интерполяции сегментов ('vertices' или 'edges')
        enable_segment_recovery: Восстанавливать сегменты из найденных путей
    """
    enable_recovery: bool = True

    # GraphBuilder фильтрация
    max_distance_threshold: float = 0.05
    enable_spatial_filter: bool = True
    enable_topological_filter: bool = True

    # PathFinder параметры
    use_adaptive_params: bool = True
    max_distance_multiplier: float = 10.0  # max_distance = avg_edge_length * multiplier
    max_weight_multiplier: float = 20.0     # max_weight = avg_edge_length * multiplier
    max_distance: float = 0.5               # Фиксированное значение (если не adaptive)
    max_weight: float = 5.0                 # Фиксированное значение (если не adaptive)

    # Segment recovery
    interpolation_mode: str = 'vertices'  # 'vertices' или 'edges'
    enable_segment_recovery: bool = True

    def validate(self) -> None:
        """Валидация параметров конфигурации."""
        if self.max_distance_threshold < 0:
            raise ValueError("max_distance_threshold must be >= 0")

        if self.max_distance_multiplier <= 0:
            raise ValueError("max_distance_multiplier must be > 0")

        if self.max_weight_multiplier <= 0:
            raise ValueError("max_weight_multiplier must be > 0")

        if self.max_distance <= 0:
            raise ValueError("max_distance must be > 0")

        if self.max_weight <= 0:
            raise ValueError("max_weight must be > 0")

        if self.interpolation_mode not in ('vertices', 'edges'):
            raise ValueError("interpolation_mode must be 'vertices' or 'edges'")


@dataclass
class SelfIntersectionFinderConfig:
    """
    Главная конфигурация модуля поиска самопересечений.

    Attributes:
        bvh: Конфигурация построения BVH
        intersection: Конфигурация поиска пересечений
        recovery: Конфигурация восстановления графа
        logging_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Опциональный путь к файлу логов
    """
    bvh: BVHConfig = field(default_factory=BVHConfig)
    intersection: IntersectionConfig = field(default_factory=IntersectionConfig)
    recovery: GraphRecoveryConfig = field(default_factory=GraphRecoveryConfig)
    logging_level: str = "INFO"
    log_file: Optional[str] = None

    def validate(self) -> None:
        """Валидация всей конфигурации."""
        self.bvh.validate()
        self.intersection.validate()
        self.recovery.validate()

        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.logging_level.upper() not in valid_levels:
            raise ValueError(f"logging_level must be one of {valid_levels}")

    @classmethod
    def create_default(cls) -> 'SelfIntersectionFinderConfig':
        """
        Создать конфигурацию по умолчанию (рекомендуемые параметры).

        Returns:
            Конфигурация с рекомендуемыми параметрами
        """
        return cls()

    @classmethod
    def create_fast(cls) -> 'SelfIntersectionFinderConfig':
        """
        Создать конфигурацию для быстрого построения (меньше точности).

        Returns:
            Конфигурация с параметрами для скорости
        """
        return cls(
            bvh=BVHConfig(
                strategy=SplitStrategy.SAH,
                enable_early_split_clipping=False,
                sah_bins=16,  # Меньше bins = быстрее
                max_primitives_per_leaf=2  # Больше примитивов в листе = меньше узлов
            ),
            intersection=IntersectionConfig(
                epsilon=1e-8,  # Меньше точность
                coplanar_search_enabled=False  # Отключаем копланарный поиск
            ),
            logging_level="WARNING"  # Меньше логов
        )

    @classmethod
    def create_accurate(cls) -> 'SelfIntersectionFinderConfig':
        """
        Создать конфигурацию для максимальной точности (медленнее).

        Returns:
            Конфигурация с параметрами для точности
        """
        return cls(
            bvh=BVHConfig(
                strategy=SplitStrategy.SAH,
                enable_early_split_clipping=True,
                esc_max_depth=4,
                sah_bins=64,  # Больше bins = точнее
                max_primitives_per_leaf=1
            ),
            intersection=IntersectionConfig(
                epsilon=1e-12,  # Максимальная точность
                parallel_angle_threshold=1e-8,
                parallel_distance_threshold=1e-8,
                coplanar_search_enabled=True
            ),
            logging_level="DEBUG"  # Подробные логи
        )
