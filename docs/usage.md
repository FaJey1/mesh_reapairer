# Руководство пользователя — mesh-reapairer

## Обзор

`mesh-reapairer` — инструмент командной строки для обнаружения и исправления самопересечений в треугольных поверхностных сетках.

**Конвейер обработки:**

```
Загрузка сетки
    │
    ▼
Поиск самопересечений (BVH + классификация Скорковской)
    │
    ▼
Восстановление графа пересечений J(M,W)
    │
    ▼
Триангуляция ячеек вдоль линий пересечения
    │
    ▼
Удаление внутренних граней (BFS-обход)
    │
    ▼
Очистка сетки (свободные рёбра, изолированные вершины)
    │
    ▼
Сохранение результата (.dat и/или статистика .json)
```

---

## Установка

```bash
pip install -e .
```

После установки команда `mesh-reapairer` доступна в терминале.

---

## Синтаксис

```
mesh-reapairer [OPTIONS] INPUT [OUTPUT]
```

| Аргумент | Описание |
|----------|----------|
| `INPUT`  | Входная сетка (`.dat` формат MSU) |
| `OUTPUT` | Выходной файл статистики (`.json`). Если не указан — только вывод в терминал |

---

## Опции

### Обнаружение пересечений

| Опция | По умолч. | Описание |
|-------|-----------|----------|
| `-e / --epsilon` | `1e-10` | Геометрический допуск для тестов пересечений |
| `--interpolation-mode` | `vertices` | Режим интерполяции графа: `vertices` (быстро) или `edges` (точно) |
| `--demo-remove-segments PCT` | `0.0` | DEMO: случайно убрать PCT% сегментов для тестирования восстановления графа |

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
| `--visualize-mode` | `combined` | Режим вывода: `combined` — все 5 панелей в одном окне; `separate` — каждая панель в отдельном окне |
| `--visualize-config JSON` | нет | Путь к JSON-файлу с настройками стиля (цвета, толщины линий, прозрачность и пр.) |
| `-g / --intersection-graph` | нет | Показать граф J(M,W) до и после восстановления |
| `--show-intersecting-cells` | нет | Показать только пересекающиеся ячейки + сегменты |

### Логирование

| Опция | По умолч. | Описание |
|-------|-----------|----------|
| `-l / --log-level` | `info` | Уровень: `debug`, `info`, `warning`, `error`, `critical` |
| `--log-file FILE` | нет | Дополнительно записывать логи в файл |
| `-q / --quiet` | нет | Отключить вывод в консоль (используйте с `--log-file`) |

---

## Примеры

### Базовый запуск (только статистика)

```bash
mesh-reapairer examples/small_sphere_double.dat
```

### Полный конвейер с сохранением статистики

```bash
mesh-reapairer examples/bunny_double.dat results/bunny.json --log-level info
```

### Сохранение восстановленной сетки в .dat

```bash
mesh-reapairer examples/bunny_double.dat results/bunny.json \
    --log-level info \
    --save-result results/bunny_repaired.dat
```

### Полная визуализация всех этапов

```bash
mesh-reapairer examples/sphere_double.dat results/sphere.json \
    --log-level info \
    --visualize \
    --intersection-graph
```

### Dragon mesh с визуализацией

```bash
mesh-reapairer examples/dragon_double.dat results/dragon.json \
    --log-level info \
    --visualize \
    --intersection-graph \
    --demo-remove-segments 10
```

### Каждая панель в отдельном окне

```bash
mesh-reapairer examples/sphere_double.dat results/sphere.json \
    --visualize --visualize-mode separate
```

### Визуализация с кастомными настройками стиля

```bash
mesh-reapairer examples/bunny_double.dat results/bunny.json \
    --visualize \
    --visualize-config visualize-config.json
```

### Только обнаружение (без исправления)

```bash
mesh-reapairer examples/bunny_double.dat results/bunny_detect.json \
    --no-restore \
    --show-intersecting-cells
```

### Тихий режим (только файл лога)

```bash
mesh-reapairer examples/dragon_double.dat results/dragon.json \
    --quiet \
    --log-file results/dragon.log \
    --log-level debug
```

### DEMO: тест восстановления графа при потере сегментов

```bash
mesh-reapairer examples/sphere_double.dat results/sphere_demo.json \
    --demo-remove-segments 20 \
    --intersection-graph \
    --log-level info
```

---

## Панели визуализации (`--visualize`)

При запуске с `--visualize` отображаются 5 панелей:

| # | Панель | Описание |
|---|--------|----------|
| 1 | **Исходная сетка** | Вся сетка до обработки |
| 2 | **Граф пересечений** | J(M,W): α-рёбра (зелёные), β-рёбра (оранжевые, пунктир), восстановленные (красные) |
| 3 | **Пересекающиеся ячейки** | Выделены красным, сегменты пересечений показаны линиями |
| 4 | **После триангуляции** | Новые ячейки (зелёные) на месте разбитых |
| 5 | **Итоговая поверхность** | Внешняя поверхность после удаления внутренних граней |

---

## Выходной JSON

Файл `.json` содержит статистику обработки:

```json
{
  "mesh": {
    "faces": 204,
    "nodes": 108,
    "edges": 306
  },
  "intersections": {
    "valid_pairs": 36,
    "affected_faces": 38,
    "impossible_pairs": 0,
    "parallel_rejected": 0
  },
  "restoration": {
    "faces_triangulated": 38,
    "new_faces_created": 182,
    "neighbor_faces_split": 0,
    "faces_removed": 0,
    "outer_faces_count": 270,
    "triangulation_ms": 12.5,
    "removal_ms": 2.1
  }
}
```

---

## Поддерживаемые форматы

| Формат | Чтение | Запись |
|--------|--------|--------|
| `.dat` (MSU Tecplot FETRIANGLE) | ✅ | ✅ (через `--save-result`) |
| `.json` (статистика) | ❌ | ✅ |

---

## Ожидаемые результаты

| Файл | Граней | Пар пересечений |
|------|--------|-----------------|
| `small_sphere_double.dat` | ~160 | 36 |
| `sphere_double.dat` | ~7 680 | ~950 |
| `bunny_double.dat` | ~9 982 | ~944 |
| `dragon_double.dat` | ~280 000 | зависит от конфигурации |

---

## Python API

```python
from mesh_reapairer.msu.mesh import Mesh
from mesh_reapairer.self_intersection_finder import find_self_intersections
from mesh_reapairer.restorer import restore_mesh
from mesh_reapairer.restorer.application.config import RestorerConfig

# Загрузка
mesh = Mesh()
mesh.load("examples/bunny_double.dat")

# Обнаружение
result = find_self_intersections(mesh)
print(f"Найдено: {len(result.valid_pairs)} пар пересечений")

# Исправление
config = RestorerConfig(enable_inner_removal=True, enable_cleanup=True)
restoration = restore_mesh(mesh, result, config)

print(f"Триангулировано: {restoration.faces_triangulated}")
print(f"Удалено внутренних: {restoration.faces_removed}")
print(f"Итого граней: {len(mesh.faces)}")

# Сохранение восстановленной сетки
mesh.store("results/bunny_repaired.dat")
```

---

## Архитектура (краткая)

```
mesh_reapairer/
├── cli/main.py                    ← точка входа CLI
├── msu/mesh.py                    ← базовые классы (Mesh, Face, Edge, Node)
├── self_intersection_finder/
│   ├── application/               ← use case: find_self_intersections()
│   ├── infrastructure/bvh/        ← построение и обход BVH-дерева
│   ├── infrastructure/intersection/  ← классификация (Скорковская)
│   └── infrastructure/repairer/   ← восстановление графа J(M,W)
├── restorer/
│   ├── application/               ← use case: restore_mesh()
│   ├── infrastructure/triangulator/  ← разбиение граней по линиям пересечения
│   └── infrastructure/inner_remover/ ← BFS-удаление внутренних граней
└── vizualizator/                  ← matplotlib визуализация
```

Полная архитектура: [architecture.md](architecture.md)
