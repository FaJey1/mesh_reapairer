# Архитектура Mesh Reapairer

## Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Структура проекта](#структура-проекта)
3. [Конвейер обработки (6 шагов)](#конвейер-обработки)
4. [Шаг 1: Построение BVH](#шаг-1-построение-bvh)
5. [Шаг 2: Обход BVH и поиск кандидатов](#шаг-2-обход-bvh)
6. [Шаг 3: Классификация пересечений (Skorkovska)](#шаг-3-классификация-пересечений)
7. [Шаг 4: Граф пересечений и восстановление](#шаг-4-граф-пересечений-и-восстановление)
8. [Шаг 5: Констрейнтная триангуляция f_fix-ячеек](#шаг-5-триангуляция)
9. [Шаг 6: Удаление внутренних граней (MeshWalker)](#шаг-6-meshwalker)
10. [Модель данных MSU](#модель-данных-msu)
11. [Ключевые структуры данных](#ключевые-структуры-данных)
12. [Визуализация](#визуализация)
13. [Конфигурация](#конфигурация)
14. [Производительность](#производительность)

---

## Обзор архитектуры

Проект следует принципам **чистой архитектуры (Clean Architecture)**:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI  /  Python API                       │
│              cli/main.py  |  application/orchestrator.py     │
├─────────────────────────────────────────────────────────────┤
│                     Application Layer                        │
│       self_intersection_finder/application/                  │
│       restorer/application/                                  │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                            │
│     entities  │  value_objects  │  enums  │  interfaces      │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                       │
│   bvh  │  caching  │  intersection  │  repairer  │  io      │
│   fan_triangulator                                           │
└─────────────────────────────────────────────────────────────┘
```

**Принципы:**
- Domain не зависит от Infrastructure
- Application зависит только от Domain и конкретных Infrastructure-компонентов
- Зависимости всегда направлены внутрь (от CLI к Domain)

---

## Структура проекта

```
src/mesh_reapairer/
├── cli/
│   └── main.py                         # CLI (click), 7-панельная визуализация
├── application/
│   └── orchestrator.py                 # repair_mesh(): точка входа
│
├── self_intersection_finder/           # Модуль поиска самопересечений
│   ├── domain/
│   │   ├── entities.py                 # IntersectionResult, Segment, GraphNode
│   │   ├── value_objects.py            # AABB, IntersectionCodes
│   │   ├── enums.py                    # SplitStrategy, EdgeType
│   │   └── interfaces.py              # абстрактные интерфейсы
│   ├── application/
│   │   ├── config.py                   # BVHConfig, IntersectionConfig, GraphRecoveryConfig
│   │   └── find_self_intersections.py  # главный use case
│   ├── infrastructure/
│   │   ├── bvh/
│   │   │   ├── builder.py              # BVHBuilder: SAH + ESC
│   │   │   └── traverser.py            # BVHTraverser: итеративный self-collision обход
│   │   ├── caching/
│   │   │   ├── pair_cache.py           # HashSet проверенных пар
│   │   │   └── adjacency_cache.py      # Dict[face_id → set(adjacent_ids)]
│   │   ├── intersection/
│   │   │   ├── classifier.py           # IntersectionClassifier (Skorkovska et al.)
│   │   │   ├── segment_finder.py       # геометрический отрезок пересечения
│   │   │   └── parallel_handler.py     # параллельные/копланарные плоскости
│   │   └── repairer/
│   │       ├── intersection_graph.py   # IntersectionGraph, GraphNode, GraphEdge
│   │       ├── graph_builder.py        # построение J(M,W), фильтрация шума
│   │       ├── path_finder.py          # MST Крускала + Дейкстра
│   │       └── segment_recovery.py     # геометрическая интерполяция сегментов
│   └── utils/
│       ├── geometry.py
│       └── logging_config.py
│
├── restorer/                           # Модуль восстановления топологии
│   ├── application/
│   │   ├── config.py                   # RestorerConfig(epsilon, logging_level)
│   │   └── restore_mesh.py             # RestoreMeshUseCase
│   ├── domain/
│   │   └── entities.py                 # RestorationResult
│   └── infrastructure/
│       ├── fan_triangulator.py         # FanTriangulator — констрейнтная триангуляция
│       └── mesh_walker.py              # MeshWalker — BFS-удаление внутренних граней
│
├── msu/mesh.py                         # Node, Edge, Face, Mesh (адаптер данных)
├── infrastructure/io.py                # load_mesh / save_mesh
└── vizualizator/                       # matplotlib-визуализация
    ├── mesh_plotter.py
    ├── intersection_result_plotter.py
    └── intersection_graph_plotter_v2.py
```

---

## Конвейер обработки

Полный конвейер состоит из **6 шагов**:

```
Mesh (.dat)
    │
    ▼  ШАГ 1
AdjacencyCache.build() + BVHBuilder.build()
    → дерево AABB по граням (SAH-эвристика)
    │
    ▼  ШАГ 2
BVHTraverser.find_candidates()
    → List[(face_a, face_b)] — пары-кандидаты
    │
    ▼  ШАГ 3
_classify_candidates()
    → valid_pairs:       List[(face_a, face_b, segment)]
    → impossible_pairs:  List[(face_a, face_b)]          — артефакты
    → f_fix (первичный): Dict[face_id → (Face, [Segment])]
    │
    ▼  ШАГ 4
_repairer_intersection()
    → GraphBuilder строит J(M,W)
    → PathFinder (Дейкстра + Крускал) восстанавливает разрывы
    → SegmentRecovery интерполирует сегменты для β-узлов
    → f_fix (обновлённый): добавлены грани из восстановленных β-узлов
    → graph_before / graph_after — снапшоты для визуализации
    │
    ▼  ШАГ 5
FanTriangulator.triangulate(mesh, f_fix)
    → для каждой f_fix-грани: констрейнтная триангуляция вдоль хорд
    → исходные грани удалены, добавлены новые треугольники
    │
    ▼  ШАГ 6
MeshWalker.remove_inner_faces(mesh, new_face_ids)
    → BFS от min-x внешней грани через manifold/ring рёбра
    → непосещённые грани — внутренние → удалить
    │
    ▼
Итоговая сетка: mesh.store() → result.dat
Статистика:    output.json
```

**Выход шага 4 (`IntersectionResult`)** содержит:

| Поле | Тип | Описание |
|------|-----|----------|
| `valid_pairs` | `List[(Face, Face, Segment)]` | Подтверждённые пересечения |
| `impossible_pairs` | `List[(Face, Face)]` | Численные артефакты классификатора |
| `face_intersections` | `Dict[int, List[Segment]]` | face_id → список сегментов |
| `f_fix` | `Dict[int, (Face, List[Segment])]` | **Все** грани под триангуляцию |
| `intersection_graph_before` | `IntersectionGraph` | Снапшот графа до восстановления |
| `intersection_graph_after` | `IntersectionGraph` | Снапшот графа после восстановления |

---

## Шаг 1: Построение BVH

### BVHBuilder — стратегия SAH

BVH (Bounding Volume Hierarchy) — иерархическое дерево AABB (Axis-Aligned Bounding Box). Позволяет находить пары граней-кандидатов за O(F log F) вместо O(F²).

**SAH (Surface Area Heuristic)** минимизирует ожидаемое число пересечений при обходе:

```
Cost(split) = C_trav + C_int × (SA_L/SA_P × N_L + SA_R/SA_P × N_R)

  SA_L, SA_R  — площадь AABB левого/правого поддерева
  SA_P        — площадь AABB родителя
  N_L, N_R    — число примитивов
  C_trav      — стоимость обхода узла (default: 1.0)
  C_int       — стоимость теста пересечения (default: 1.0)
```

**Binning:** грани делятся на `sah_bins=32` корзины по центроиду вдоль каждой из 3 осей; SAH вычисляется для каждой из 31 границы. Сложность: O(n·bins) вместо O(n²).

**Early Split Clipping (ESC, опционально):** крупные треугольники обрезаются по AABB родителя — AABB становится точнее. Улучшает качество дерева ценой роста числа примитивов.

**Рекурсивное построение:**
```
build(primitives):
  if |primitives| ≤ max_per_leaf: return Leaf(primitives)
  best_axis, best_bin = argmin SAH_cost over (3 axes × 31 splits)
  L, R = partition(primitives, best_axis, best_bin)
  return InnerNode(build(L), build(R))
```

---

## Шаг 2: Обход BVH

### BVHTraverser — итеративный self-collision обход

Обход дерева с самим собой (self-collision traversal) для нахождения всех пар граней с перекрывающимися AABB:

```
stack = [(root, root)]

while stack:
    n1, n2 = stack.pop()
    if not AABB(n1) ∩ AABB(n2): continue          # отсечение по AABB

    if leaf(n1) and leaf(n2):
        for p1 in n1.prims, p2 in n2.prims:
            if p1 == p2: continue                   # одна и та же грань
            if adjacent(p1, p2): continue           # общее ребро (AdjacencyCache)
            if checked(p1, p2): continue            # уже проверяли (PairCache)
            mark_checked(p1, p2)
            if AABB(p1) ∩ AABB(p2): candidates += (p1, p2)
    else:
        if n1 is n2:                                # self-intersection узла
            push (L,L), (L,R), (R,R)
        else:
            push все 4 пары (Li, Rj)
```

**Оптимизации:**
- `AdjacencyCache` — предвычисленные словарь `face_id → set(neighbor_ids)`, O(1) проверка
- `PairCache` — `frozenset({id1,id2})` в HashSet, O(1) дедупликация
- Итеративный DFS — нет переполнения стека

---

## Шаг 3: Классификация пересечений

### IntersectionClassifier — метод Skorkovska et al.

Для каждой пары-кандидата `(face_a, face_b)` классифицируется каждое ребро одного треугольника относительно плоскости другого:

**Код ребра:**

| Код | Условие | Значение |
|-----|---------|----------|
| `0` | оба конца по одну сторону или на плоскости | нет пересечения |
| `1` | пересечение в вершине ребра (t ≈ 0 или t ≈ 1) | вершина |
| `2` | пересечение внутри ребра (0 < t < 1) | внутренняя точка |

```python
d0 = plane_b.signed_dist(p0)
d1 = plane_b.signed_dist(p1)
if abs(d0) < ε and abs(d1) < ε: code = 0       # ребро на плоскости
elif d0 * d1 > 0:               code = 0       # одна сторона
else:
    t = d0 / (d0 - d1)
    p = p0 + t*(p1-p0)
    code = 1 if (t < ε or t > 1-ε) else 2
```

Для пары треугольников получаем два кода-тройки: `codes_ab` (рёбра A против плоскости B) и `codes_ba` (рёбра B против плоскости A).

**Impossible cases** (числовые артефакты, невозможные при точной арифметике): `[0,0,1]`, `[0,0,2]`, `[0,1,2]`, `[1,2,2]`, `[2,2,2]` — попадают в `impossible_pairs`, используются при построении графа.

### SegmentFinder

Из кодов извлекается геометрический отрезок пересечения:
```
точки A ← {p из codes_ab с кодом 1 или 2}
точки B ← {p из codes_ba с кодом 1 или 2}
→ найти перекрытие двух отрезков на главной оси
→ Segment(node_start, node_end)
```

---

## Шаг 4: Граф пересечений и восстановление

### Структуры графа

**GraphNode** — узел = одна пара пересекающихся граней:
```python
face_a, face_b  — грани
segment         — отрезок пересечения (None у β-узлов)
point           — (center_a + center_b) / 2
is_anchor       — True если узел является «якорем» (degree_α == 1)
```

**EdgeType:**
- `ALPHA` — ребро между двумя α-узлами (оба с сегментами); образует линию пересечения
- `BETA` — ребро через β-узел (impossible_pair); рабочее, используется для поиска пути
- `RECOVERED` — β-ребро, выбранное MST; означает восстановленный разрыв

**Якорь** — α-узел с ровно одним α-ребром. Якоря всегда образуют пары — это концы разрывов в линии пересечения.

### GraphBuilder — построение J(M,W)

```
1. α-узлы  ← valid_pairs
2. Фильтр β-кандидатов из impossible_pairs:
     топологический: пара разделяет грань с каким-либо valid_pair
     пространственный: расстояние до ближайшей valid_pair < threshold
3. β-узлы  ← отфильтрованные impossible_pairs
4. α-рёбра: два α-узла соединяются, если их сегменты имеют общую точку (ε=1e-8)
5. Найти якоря (degree_α == 1)
6. β-рёбра: 1-hop соседи через общую грань (якорь↔β, β↔β; не якорь↔якорь)
7. Фильтрация шума: удалить малые компоненты (<5% от максимальной)
```

### PathFinder — MST + Дейкстра

**Задача:** соединить n якорей восстановленными путями через β-узлы.

**Решение:** MST на графе якорей → (n-1) путей.

```
1. Для каждого якоря s: Дейкстра(s) по β-рёбрам
      → dist[v], parent[v]  (с ограничением max_distance)

2. Матрица расстояний: W[i,j] = dist_from_i[anchor_j]

3. MST (Крускал + Union-Find):
      отсортировать рёбра якорь↔якорь по весу
      добавлять, пока не получим n-1 рёбро без цикла

4. Для каждого ребра MST: reconstruct_path(parent, ai, aj)
      → путь из node_id

5. mark_recovered_edges(): β-рёбра на путях → RECOVERED
```

**Адаптивные параметры:** `max_distance = avg_edge_length × 10`, `max_weight = avg_edge_length × 20`.

### SegmentRecovery

После нахождения путей — геометрическая интерполяция сегментов для β-узлов:

```
for each β-узел v на пути [prev → v → next]:
    start = get_connection_point(prev, v)
    end   = get_connection_point(v, next)
    v.segment = Segment([start, end])
```

`get_connection_point(from, to)` = ближайшая конечная точка сегмента `from` к общей грани пары `(from, to)`.

### Обновление f_fix

После восстановления:
```python
f_fix = {
    face_id: (face_obj, face_intersections[face_id])
    for face_id in face_intersections
    if face_id in face_map   # face_map = все грани из valid_pairs
}
```

`f_fix` включает как первично найденные грани, так и грани β-узлов с восстановленными сегментами.

---

## Шаг 5: Триангуляция

### FanTriangulator — констрейнтная триангуляция f_fix-ячеек

**Файл:** `restorer/infrastructure/fan_triangulator.py`

**Задача:** для каждой грани из `f_fix` — заменить её набором треугольников так, чтобы **линия пересечения стала общим ребром** между новыми треугольниками.

---

### Выбор метода триангуляции: почему не Делоне

При разработке рассматривались три подхода:

#### Вариант 1: Триангуляция Делоне (Delaunay)

Классическая триангуляция Делоне максимизирует минимальный угол (критерий описанной окружности): для любого треугольника `ABC` четвёртая точка любого соседнего треугольника должна находиться **вне** описанной окружности `ABC`.

**Почему не подходит:**
- Делоне **не гарантирует** вхождение заданных рёбер в результирующую сетку. Алгоритм автономно выбирает диагонали — хорда `P₀→P₁` (линия пересечения) может не попасть в триангуляцию.
- Критерий окружности ориентирован на качество углов, а не на топологическую корректность. Для физических симуляций это ценно, но для задачи ремонта сетки **топологический инвариант важнее качества углов**.
- Реализация нетривиальна: требует итерационного переворачивания рёбер (edge flips) и обработки особых случаев.

#### Вариант 2: Constrained Delaunay Triangulation (CDT)

CDT сначала вставляет все ограничения (constraint edges), затем применяет Делоне внутри каждой области.

**Почему не подходит:**
- CDT гарантирует наличие заданных рёбер **и** сохраняет свойство Делоне там, где возможно. Это избыточно для нашей задачи.
- Для небольших полигонов (4–6 вершин, 1–2 хорды), которые типичны при ремонте пересечений, CDT и наш метод дадут **одинаковый результат** — один и тот же набор из `n−2` треугольников.
- Вычислительная сложность выше без практического выигрыша.

#### Вариант 3: Констрейнтная веерная триангуляция (выбранный метод)

Рекурсивное разрезание граничного полигона вдоль хорд-констрейнтов, затем простой веер внутри каждого суб-полигона.

**Почему выбран:**
- **Гарантия топологической корректности**: хорда `P₀→P₁` становится ребром треугольника по построению — алгоритм буквально делит полигон по ней.
- **Простота и детерминизм**: нет итерационных шагов, нет edge flips, нет численных проблем с circumcircle-тестом.
- **Достаточное качество**: полигоны после разрезания по хордам, как правило, выпуклые или почти выпуклые, поэтому веер из первой вершины не создаёт вырожденных треугольников.
- **Оптимальное число треугольников**: `n−2` — то же, что у любой триангуляции без добавления новых вершин (теорема о триангуляции полигона).

#### Итоговое сравнение

| Критерий | Делоне | CDT | Наш метод |
|----------|--------|-----|-----------|
| Хорда P₀→P₁ гарантированно ребро | ✗ | ✓ | ✓ |
| Качество углов (max min-angle) | ✓ | ✓ | ~ |
| Сложность реализации | высокая | очень высокая | низкая |
| Детерминизм | зависит | зависит | ✓ |
| Число треугольников | n−2 | n−2 | n−2 |
| Подходит для ремонта сетки | ✗ | ✓ | ✓ |
| Численные edge cases | много | много | мало |

> **Вывод:** для задачи топологического ремонта (обеспечение корректного стыка на шве пересечения) оптимален наш метод — он проще CDT, детерминирован и гарантирует главное свойство.

---

### Алгоритм `_triangulate_face()`

**Шаг 1: Сбор cut-points на рёбрах грани**

Для грани `T = (V₀, V₁, V₂)` и каждого сегмента из её списка:
```
for segment in segments:
    for P in [segment.nodes[0].p, segment.nodes[-1].p]:
        for ei in {0,1,2}:          # рёбра e₀=V₀V₁, e₁=V₁V₂, e₂=V₂V₀
            t = _point_on_edge(P, V_ei, V_{ei+1})
            if t ∈ (ε, 1-ε):        # строго внутри ребра
                edge_cuts[ei].append((t, P))
```

`_point_on_edge(P, a, b)` вычисляет параметр `t = (P-a)·(b-a) / |b-a|²` и проверяет, что расстояние от `P` до точки `a + t(b-a)` мало (< ε).

**Шаг 2: Построение boundary-полигона**

```
polygon = []
for ei in {0, 1, 2}:
    polygon.append(V[ei])
    for (t, coords) in sorted(edge_cuts[ei], key=t):
        node = mesh.add_node(coords, zone, is_merge_nodes=True)
        polygon.append(node)
```

Для грани с cut-points `P₀` на e₀ (t=0.4) и `P₁` на e₁ (t=0.3):
```
polygon = [V₀, P₀, V₁, P₁, V₂]     (n = 5 вершин)
```

**Шаг 3: Построение хорд-констрейнтов**

Для каждого сегмента находим индексы его концов в полигоне:
```
for segment in segments:
    idxs = []
    for P in [segment.nodes[0].p, segment.nodes[-1].p]:
        k = index in polygon where |polygon[k].p - P| < ε×100
        if found: idxs.append(k)
    if len(idxs) == 2 and idxs[0] ≠ idxs[1]:
        i, j = sorted(idxs)
        if 2 ≤ j-i ≤ n-2:           # не вырожденная хорда
            chords.append((i, j))
```

**Шаг 4: Констрейнтная триангуляция — `_split_polygon(polygon, chords)`**

Рекурсивно разрезает полигон по хорде, затем веерно триангулирует каждую часть:

```python
def _split_polygon(polygon, chords):
    n = len(polygon)
    if n == 3: return [(polygon[0], polygon[1], polygon[2])]
    if not chords:
        # Простой веер из polygon[0] — допустимо, хорд нет
        return [(polygon[0], polygon[i], polygon[i+1])
                for i in range(1, n-1)]

    ci, cj = chords[0]    # ci < cj

    # Суб-полигон 1: polygon[ci..cj]
    sub1 = polygon[ci : cj+1]

    # Суб-полигон 2: polygon[cj..n-1] + polygon[0..ci]
    sub2 = polygon[cj:] + polygon[:ci+1]

    # Перенести оставшиеся хорды в соответствующие суб-полигоны
    sub1_chords = [(a-ci, b-ci) for (a,b) in chords[1:]
                   if ci<=a and b<=cj]
    sub2_chords = [remap_to_sub2(a,b) for (a,b) in chords[1:]
                   if a>=cj or b<=ci]

    return _split_polygon(sub1, sub1_chords) \
         + _split_polygon(sub2, sub2_chords)
```

**Пример** для `polygon = [V₀, P₀, V₁, P₁, V₂]`, хорда `(1, 3)` = `P₀→P₁`:

```
sub1 = [P₀, V₁, P₁]                         → 1 треугольник: (P₀, V₁, P₁)
sub2 = [P₁, V₂, V₀, P₀]                     → 2 треугольника: (P₁, V₂, V₀), (P₁, V₀, P₀)

Итог: (P₀, V₁, P₁), (P₁, V₂, V₀), (P₁, V₀, P₀)
```

Хорда `P₀–P₁` является **общим ребром** треугольников `(P₀, V₁, P₁)` и `(P₁, V₀, P₀)`.

#### Сравнение: простой веер vs. констрейнтная триангуляция

| | Простой веер | Констрейнтная |
|--|--|--|
| Хорда P₀→P₁ | проходит через interior | **является ребром треугольника** |
| Треугольники (пример) | 3 (фан из hub) | 3 (два суб-веера) |
| Число треугольников | n-2 | n-2 (то же самое) |
| Сегмент на ребре | ✗ | ✓ |
| Сложность | O(n) | O(n · k), k — число хорд |

#### Завершение `triangulate()`

```
1. Для каждой (face, segments) в f_fix:
     new_ids = _triangulate_face(mesh, face, segments, zone)
     → накопить new_face_ids
     → запомнить face для удаления

2. Для каждой исходной f_fix-грани:
     mesh.delete_face(face)
     → удаляет грань и все ссылки на неё из рёбер/зон

3. Вернуть (f_fix_ids, new_face_ids)
```

#### Топологические эффекты после триангуляции

После удаления f_fix-граней и добавления новых треугольников в сетке возникают два типа нестандартных рёбер:

**T-стыки (T-junctions, 1-face edge):**
Образуются на границе f_fix-региона. Ребро `V₀–V₁` соседней (не f_fix) грани раньше было 2-face (граничило с f_fix-гранью). После удаления f_fix-грани это ребро становится 1-face. Новые треугольники имеют частичные рёбра `[V₀, P]` и `[P, V₁]` — они не совпадают с `V₀–V₁`, поэтому топологической связи нет.

**Кольцевые рёбра (ring edges, 4-face edge):**
Образуются на шве пересечения. Хорда `P₀–P₁` входит в 2 новых треугольника от грани A (через её chord split) и в 2 новых треугольника от грани B. Итого 4 инцидентных грани — ring edge. Именно через эти рёбра работает критерий выбора внешнего соседа в MeshWalker.

```
       ← грань A →     ← грань B →
(P₀,V₁_A,P₁), (P₁,V₀_A,P₀) | (P₀,V₁_B,P₁), (P₁,V₀_B,P₀)
        ↑ обе пары делят ребро P₀–P₁ ↑
              ring edge (4 грани)
```

T-стыки (1-face) служат **барьерами** в BFS MeshWalker. Ring edges (4-face) требуют выбора внешнего соседа.

---

## Шаг 6: MeshWalker

### MeshWalker — BFS-удаление внутренних граней

**Файл:** `restorer/infrastructure/mesh_walker.py`  
**Источник алгоритма:** Meshcheryakov & Rybakov (2023), Section 5.2

**Задача:** после констрейнтной триангуляции сетка содержит как внешние, так и внутренние грани (части обеих исходных поверхностей). Нужно удалить внутренние грани, сохранив единую внешнюю оболочку.

#### Идея алгоритма

После разрезания граней вдоль шва пересечения внешние и внутренние грани оказываются **топологически разделены**: между ними нет обычных manifold-рёбер (2-face). Переходы возможны только через ring-рёбра (4-face) — и именно там нужно принимать решение, куда идти дальше.

Алгоритм начинает обход с заведомо внешней грани и достигает всех внешних граней, избегая внутренних.

#### Выбор стартовой грани

Грань с **минимальной x-координатой центра** среди не-новых (старых) граней. Геометрически это крайняя левая точка объекта — заведомо находится на внешней поверхности.

```python
start = min(
    (f for f in mesh.faces if f.glo_id not in new_face_ids),
    key=lambda f: f.center()[0]
)
```

#### Правила перехода в BFS

| Тип ребра | `len(edge.faces)` | Переход |
|-----------|-------------------|---------|
| Manifold  | 2 | `face.neighbour(edge)` — единственный сосед |
| Ring edge | > 2 | `face.outer_neighbour(edge)` — внешний сосед |
| T-стык    | 1 | нет перехода — барьер |

#### Критерий `outer_neighbour` (r_article_9, рис. 22)

Для кольцевого ребра с несколькими соседями выбирается грань, максимизирующая скалярное произведение нормали текущей грани на вектор к центру кандидата:

```python
def outer_neighbour(self, edge):
    """Реализовано в msu.Face (уже существует в кодовой базе)."""
    pretenders = [f for f in edge.faces if f != self]
    n = self.triangle().normal()
    O = edge.center()
    factors = [np.dot(n, f.center() - O) for f in pretenders]
    return pretenders[np.argmax(factors)]
```

Геометрический смысл: из всех граней, инцидентных кольцевому ребру, выбирается та, чей центр наиболее «совпадает» с направлением нормали текущей грани. Это соответствует повороту вокруг ребра в направлении **против** нормали — т.е. выбору «внешнего» продолжения поверхности.

#### Удаление и сохранение геометрии

Перед удалением координаты внутренних граней сохраняются в `RestorationResult.inner_face_geometries` — для визуализации панели 7 (показывает что было удалено).

```python
inner_geoms = [(f.nodes[0].p.copy(), f.nodes[1].p.copy(), f.nodes[2].p.copy())
               for f in inner_faces]
for f in inner_faces:
    mesh.delete_face(f)
mesh.delete_faces_free_edges()
mesh.delete_isolated_nodes()
```

#### RestorationResult (полный)

```python
@dataclass
class RestorationResult:
    mesh: Mesh

    # FanTriangulator
    f_fix_count: int = 0
    new_faces_count: int = 0
    f_fix_ids: Set[int] = field(default_factory=set)
    new_face_ids: Set[int] = field(default_factory=set)
    triangulation_time_ms: float = 0.0

    # MeshWalker
    removed_faces_count: int = 0
    walker_time_ms: float = 0.0
    outer_face_ids_set: Set[int] = field(default_factory=set)
    inner_face_geometries: list = field(default_factory=list)  # для viz
```

#### Примечание о T-стыках

T-стыки (1-face рёбра на границе f_fix-региона) служат естественными барьерами в BFS. Внутренние грани, изолированные от внешних через T-стыки, не будут посещены обходом и попадут в список на удаление. Это корректно: T-стыки находятся именно на шве пересечения — там, где разделяются внешняя и внутренняя части.

---

## Модель данных MSU

```python
class Node:
    p: np.ndarray       # координаты [x, y, z]

class Edge:
    nodes: List[Node]   # 2 вершины
    faces: List[Face]   # инцидентные грани (обычно 1 или 2)

class Face:
    nodes: List[Node]   # 3 вершины треугольника
    edges: List[Edge]   # 3 ребра
    glo_id: int         # глобальный идентификатор
    zone: Zone          # зона (для многозонных сеток)

    def center() -> np.ndarray
    def normal() -> np.ndarray
    def points() -> List[np.ndarray]   # [[x,y,z], [x,y,z], [x,y,z]]

class Mesh:
    nodes: List[Node]
    edges: List[Edge]
    faces: List[Face]
    zones: List[Zone]

    def add_node(coords, zone, is_merge_nodes=False) -> Node
    def add_face(n1, n2, n3, zone) -> Face
    def delete_face(face) -> None
    def find_face(n1, n2, n3) -> Optional[Face]
    def load(path) / store(path)
```

`add_node(..., is_merge_nodes=True)` — ищет существующий узел в заданном радиусе ε перед созданием нового. Используется для дедупликации cut-points.

---

## Ключевые структуры данных

### IntersectionGraph

```python
class IntersectionGraph:
    nodes: Dict[int, GraphNode]     # node_id → GraphNode
    edges: Dict[int, GraphEdge]     # edge_id → GraphEdge

class GraphNode:
    node_id: int
    face_a, face_b: Face
    segment: Optional[Segment]      # None у β-узлов
    point: np.ndarray               # геометрический центр узла
    is_anchor: bool                 # degree_α == 1

class GraphEdge:
    node1, node2: GraphNode
    edge_type: EdgeType             # ALPHA | BETA | RECOVERED
    weight: float                   # евклидово расстояние node1↔node2
```

### Segment

```python
class Segment:
    nodes: List[Node]       # [start_node, ..., end_node]
    face_a, face_b: Face    # грани, между которыми сегмент
```

### f_fix

```python
f_fix: Dict[int, Tuple[Face, List[Segment]]]
#             │         │        └── все сегменты пересечения грани
#             │         └── сам объект Face
#             └── face.glo_id
```

---

## Визуализация

### 8-панельный режим (CLI: `--visualize`)

| Панель | Название | Содержание |
|--------|----------|------------|
| 1 | Original mesh | Исходная сетка, цвет по зонам |
| 2 | Graph BEFORE | Граф J(M,W) до восстановления (α=зелёный, β=оранжевый) |
| 3 | Graph AFTER | Граф J(M,W) после восстановления + ломаная пересечения |
| 4 | Seam polyline | Только сегменты на прозрачной сетке (alpha=0.05) |
| 5 | f_fix cells | f_fix-грани выделены красным + сегменты |
| 6 | New triangles | Только новые треугольники (зелёные) + ломаная |
| 7 | After triangulation | Старые=серые, новые=зелёные, **внутренние=розовые** (до удаления) |
| 8 | Final mesh | Чистая внешняя поверхность после удаления внутренних граней |

Панель 7 специально показывает внутренние грани (сохранены до удаления MeshWalker'ом) — это наглядно демонстрирует, что было удалено.

**Режимы `--visualize-mode`:**
- `combined` — все 8 в одном окне
- `separate` — каждая панель в отдельном окне
- `1,4,7,8` — только указанные панели (1–8)

**Параметры стиля** задаются в `visualize-config.json`:
```json
{
  "face_edges_show": true,
  "face_edge_linewidth": 1.0,
  "face_edge_color": "black",
  "segment_linewidth": 2.0,
  "segment_linewidth_panel4": 1.0,
  "graph_alpha_color": "green",
  "graph_recovered_color": "red"
}
```

### Батчевая отрисовка

```python
# БЫЛО (медленно: N объектов):
for face in mesh.faces:
    ax.add_collection3d(Poly3DCollection([face.points()], ...))

# СТАЛО (быстро: 1 объект):
verts = np.array([f.points() for f in mesh.faces])
ax.add_collection3d(Poly3DCollection(verts, ...))
```

Ускорение ~100–1000× на больших сетках.

---

## Конфигурация

### BVHConfig

```python
strategy: SplitStrategy = SAH       # SAH | LBVH
max_primitives_per_leaf: int = 1
sah_bins: int = 32
sah_traversal_cost: float = 1.0
sah_intersection_cost: float = 1.0
enable_early_split_clipping: bool = False
esc_max_depth: int = 3
```

### IntersectionConfig

```python
epsilon: float = 1e-10
parallel_angle_threshold: float = 1e-6
parallel_distance_threshold: float = 1e-6
enable_pair_cache: bool = True
```

### GraphRecoveryConfig

```python
enable_recovery: bool = True
max_distance_threshold: float = 0.05
use_adaptive_params: bool = True
max_distance_multiplier: float = 10.0   # max_dist = avg_edge × 10
max_weight_multiplier: float = 20.0
enable_segment_recovery: bool = True
```

### RestorerConfig

```python
epsilon: float = 1e-6           # допуск для _point_on_edge и is_merge_nodes
logging_level: str = "INFO"
enable_inner_removal: bool = True   # запускать MeshWalker после триангуляции
enable_cleanup: bool = True         # удалять свободные рёбра и изолированные узлы
```

---

## Производительность

### Бенчмарки (small_sphere_double.dat, 160 граней)

| Шаг | Время | Результат |
|-----|-------|-----------|
| BVH Build | ~150 мс | 160 граней |
| BVH Traversal | ~7 мс | 944 кандидата |
| Classification | ~180 мс | 36 valid_pairs |
| Graph Recovery | ~15 мс | 0 якорей (граф связный) |
| FanTriangulator | ~47 мс | 38 f_fix → 109 новых треугольников |
| MeshWalker | ~2 мс | 115 внутренних удалено → 116 итоговых |
| **Total** | **~400 мс** | |

### Сложность алгоритмов

| Компонент | Время | Память |
|-----------|-------|--------|
| BVH Build (SAH) | O(F log F) | O(F) |
| BVH Traversal | O(F log F) avg | O(log F) стек |
| Classification | O(C), C = кандидаты | O(C) |
| GraphBuilder | O(V²) worst | O(V+E) |
| Dijkstra | O((V+E) log V) | O(V) |
| Kruskal MST | O(E log E) | O(V) |
| FanTriangulator | O(F · k · n) | O(n) |
| MeshWalker (BFS) | O(F + E) | O(F) |

`F` = граней, `V` = узлов графа, `C` = кандидатов, `k` = хорд на грань, `n` = вершин полигона.
