# Mesh Reapairer

Инструмент для обнаружения и восстановления самопересечений в треугольных сетках.

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Параметры CLI](#параметры-cli)
- [Python API](#python-api)
- [Тестовые модели](#тестовые-модели)
- [Архитектура](#архитектура)
- [Конфигурация](#конфигурация)

---

## Установка

```bash
# С uv (рекомендуется)
uv sync

# Или через pip
pip install -e ".[dev]"
```

**Требования:** Python 3.13+, numpy, matplotlib (для визуализации)

---

## Быстрый старт

```bash
# Активировать окружение
source .venv/bin/activate

# Базовый запуск (только статистика)
mesh-reapairer examples/bunny_double.dat

# Полный конвейер с сохранением статистики
mesh-reapairer examples/bunny_double.dat results/bunny.json --log-level info

# С визуализацией 5 панелей
mesh-reapairer examples/sphere_double.dat results/sphere.json \
    --log-level info --visualize --intersection-graph

# Сохранить восстановленную сетку в .dat
mesh-reapairer examples/bunny_double.dat results/bunny.json \
    --log-level info --save-result results/bunny_repaired.dat

# Режим демо: удалить 10% сегментов и проверить восстановление
mesh-reapairer examples/bunny_double.dat results/bunny.json \
    --log-level info --intersection-graph --demo-remove-segments 10
```

---

## Параметры CLI

```
mesh-reapairer [OPTIONS] INPUT [OUTPUT]
```

| Аргумент | Описание |
|----------|----------|
| `INPUT`  | Входная сетка (`.dat` формат MSU) |
| `OUTPUT` | Выходной файл статистики (`.json`). Если не указан — только вывод в терминал |

### Обнаружение пересечений

| Опция | По умолч. | Описание |
|-------|-----------|----------|
| `-e / --epsilon` | `1e-10` | Геометрический допуск для тестов пересечений |
| `--interpolation-mode` | `vertices` | Режим интерполяции графа: `vertices` (быстро) или `edges` (точно) |
| `--demo-remove-segments PCT` | `0.0` | DEMO: случайно убрать PCT% сегментов для тестирования восстановления |

### Восстановление сетки

| Опция | По умолч. | Описание |
|-------|-----------|----------|
| `--restore / --no-restore` | вкл. | Запускать триангуляцию + удаление внутренних граней |
| `--inner-removal / --no-inner-removal` | вкл. | Удалять внутренние грани после триангуляции |
| `--cleanup / --no-cleanup` | вкл. | Очищать свободные рёбра и изолированные вершины |
| `--save-result PATH` | нет | Сохранить восстановленную сетку в файл `.dat` (формат MSU) |

### Визуализация

| Опция | По умолч. | Описание |
|-------|-----------|----------|
| `-v / --visualize` | нет | Показать **5-панельную** визуализацию конвейера |
| `--visualize-mode` | `combined` | Режим: `combined` — все 5 панелей в одном окне; `separate` — каждая отдельно |
| `--visualize-config JSON` | нет | Путь к JSON-файлу с настройками стиля (цвета, толщины линий, прозрачность) |
| `-g / --intersection-graph` | нет | Показать граф J(M,W) до и после восстановления |
| `--show-intersecting-cells` | нет | Показать только пересекающиеся ячейки + сегменты |

### Логирование

| Опция | По умолч. | Описание |
|-------|-----------|----------|
| `-l / --log-level` | `info` | Уровень: `debug`, `info`, `warning`, `error`, `critical` |
| `--log-file FILE` | нет | Дополнительно записывать логи в файл |
| `-q / --quiet` | нет | Отключить вывод в консоль (используйте с `--log-file`) |

---

## Python API

### Базовое использование

```python
from mesh_reapairer.msu.mesh import Mesh
from mesh_reapairer.self_intersection_finder import find_self_intersections
from mesh_reapairer.restorer import restore_mesh
from mesh_reapairer.restorer.application.config import RestorerConfig

# Загрузка
mesh = Mesh()
mesh.load("examples/bunny_double.dat")

# Обнаружение самопересечений
result = find_self_intersections(mesh)
print(f"Найдено: {len(result.valid_pairs)} пар пересечений")
print(f"Затронуто граней: {len(result.face_intersections)}")

# Восстановление
config = RestorerConfig(enable_inner_removal=True, enable_cleanup=True)
restoration = restore_mesh(mesh, result, config)

print(f"Триангулировано: {restoration.faces_triangulated}")
print(f"Удалено внутренних: {restoration.faces_removed}")
print(f"Итого граней: {len(mesh.faces)}")

# Сохранение восстановленной сетки
mesh.store("results/bunny_repaired.dat")
```

### Тонкая настройка конфигурации

```python
from mesh_reapairer.self_intersection_finder import (
    find_self_intersections,
    SelfIntersectionFinderConfig,
    BVHConfig,
    IntersectionConfig,
    GraphRecoveryConfig,
)

config = SelfIntersectionFinderConfig(
    bvh=BVHConfig(
        max_primitives_per_leaf=1,
        sah_bins=32,
    ),
    intersection=IntersectionConfig(
        epsilon=1e-10,
        coplanar_search_enabled=True,
    ),
    recovery=GraphRecoveryConfig(
        enable_recovery=True,
        use_adaptive_params=True,
        max_distance_multiplier=10.0,
        interpolation_mode="vertices",  # "vertices" или "edges"
    ),
    logging_level="INFO",
)

result = find_self_intersections(mesh, config=config)
print(f"Найдено пересечений: {len(result.valid_pairs)}")
```

### Высокоуровневый API (оркестратор)

```python
from mesh_reapairer.application.orchestrator import repair_mesh

# Весь конвейер одной функцией
repaired = repair_mesh(
    mesh,
    enable_visualization=False,
    demo_remove_segments_percent=0.0,
    interpolation_mode="vertices",
    visualize_intersection_graph=False,
)
```

---

## Тестовые модели

| Модель | Файл | Граней | Пар пересечений |
|--------|------|--------|-----------------|
| Маленькая сфера | `small_sphere_double.dat` | ~160 | 36 |
| Сфера | `sphere_double.dat` | ~7 680 | ~950 |
| Заяц (bunny) | `bunny_double.dat` | ~9 982 | ~944 |
| Дракон (dragon) | `dragon_double.dat` | ~280 000 | зависит от конфигурации |

---

## Архитектура

Проект следует принципам **чистой архитектуры**:

```
mesh_reapairer/
├── cli/                            # CLI (click)
│   └── main.py
├── application/                    # Оркестрация
│   └── orchestrator.py
├── self_intersection_finder/       # Поиск и граф пересечений
│   ├── domain/                     # Доменная модель
│   │   ├── entities.py             # IntersectionResult, Segment
│   │   ├── value_objects.py        # AABB, Plane, ClassificationCode
│   │   └── enums.py                # IntersectionStatus, SplitStrategy
│   ├── application/                # Use cases
│   │   ├── config.py               # Конфигурация BVH / Intersection / Recovery
│   │   └── find_self_intersections.py  # Главный use case
│   ├── infrastructure/
│   │   ├── bvh/                    # BVH дерево (builder + traverser)
│   │   ├── caching/                # Кэш пар и соседей
│   │   ├── intersection/           # Классификация по Скорковской
│   │   └── repairer/               # Граф пересечений J(M,W)
│   │       ├── intersection_graph.py   # Структуры GraphNode, GraphEdge
│   │       ├── graph_builder.py        # Построение графа + фильтрация шума
│   │       ├── path_finder.py          # MST (Дейкстра + Крускал)
│   │       └── segment_recovery.py     # Геометрическая интерполяция
│   └── utils/
├── restorer/                       # Восстановление топологии
│   ├── application/
│   │   ├── config.py               # RestorerConfig
│   │   └── restore_mesh.py         # RestoreMeshUseCase
│   ├── domain/
│   │   └── entities.py             # RestorationResult
│   └── infrastructure/
│       ├── triangulator/           # FaceTriangulator
│       └── inner_remover/          # MeshWalker
├── msu/                            # Модель данных (Node, Edge, Face, Mesh)
├── infrastructure/                 # io.py (load_mesh)
└── vizualizator/                   # matplotlib визуализация
```

### Поток данных

```
Загрузка .dat
      │
      ▼
AdjacencyCache.build()        — кэш соседних граней
      │
      ▼
BVHBuilder.build()            — BVH дерево (SAH)
      │
      ▼
BVHTraverser.find_candidates()  — обход дерева, O(n log n)
      │
      ▼
Классификация пар             — алгоритм Скорковской
      │
      ▼
GraphBuilder.build_graph()    — граф J(M,W): α-узлы + β-узлы
      │
      ▼
PathFinder                    — MST (Дейкстра + Крускал) для якорей
      │
      ▼
SegmentRecovery               — интерполяция сегментов на путях
      │
      ▼
FaceTriangulator              — разбиение граней вдоль сегментов
      │
      ▼
MeshWalker                    — BFS-удаление внутренних граней
      │
      ▼
Очистка сетки                 — свободные рёбра, изолированные узлы
      │
      ▼
mesh.store() / stats .json
```

### Граф пересечений J(M,W)

- **α-узел** — пара граней с найденным сегментом пересечения
- **β-узел** — пара граней без сегмента (impossible pair), потенциальный пробел
- **α-ребро** — связь между соседними α-узлами (общая точка сегментов)
- **β-ребро** — временная связь для поиска пути восстановления
- **Якорь** — α-узел с ровно одним α-ребром (конец разрыва в линии пересечения)

Подробнее: [docs/architecture.md](docs/architecture.md)

---

## Конфигурация

```python
from mesh_reapairer.self_intersection_finder.application.config import (
    SelfIntersectionFinderConfig,
    BVHConfig,
    IntersectionConfig,
    GraphRecoveryConfig,
)

config = SelfIntersectionFinderConfig(
    bvh=BVHConfig(
        max_primitives_per_leaf=1,
        sah_bins=32,
    ),
    intersection=IntersectionConfig(
        epsilon=1e-10,
        coplanar_search_enabled=True,
    ),
    recovery=GraphRecoveryConfig(
        enable_recovery=True,
        use_adaptive_params=True,
        max_distance_multiplier=10.0,
        max_weight_multiplier=20.0,
        interpolation_mode="vertices",  # "vertices" или "edges"
        enable_segment_recovery=True,
    ),
    logging_level="INFO",
)
```

---

## Разработка

```bash
# Форматирование
uv run ruff format .

# Линтер
uv run ruff check . --fix

# Тесты
uv run pytest
```

---

## Документация

- [docs/architecture.md](docs/architecture.md) — подробная архитектура, алгоритмы, структуры данных
- [docs/usage.md](docs/usage.md) — расширенные примеры использования CLI
