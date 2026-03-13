## mesh_reapairer

Приложение/библиотека для:

- **поиска самопересечений сетки** (`self_intersection_finder`)
- **восстановления сетки** (`restorer`)
- **визуализации этапов восстановления** (`vizualizator`)
- **описания структуры сетки** (`msu`)

Проект собран по принципам **чистой архитектуры**: доменные модули отделены от orchestration (application) и технических адаптеров (infrastructure).

---

## Структура проекта

Код лежит в `src/` (src-layout), тесты — в `tests/`, примеры — в `examples/`.

```
mesh_reapairer/
  docs/                      # документация внутри репозитория (см. docs.md)
    architecture.md
    usage.md
  examples/
    meshes/
      simple_triangle.json
      self_intersecting_dummy.json
    run_repair.py
  scripts/                   # entrypoints для tooling (PyInstaller)
    mesh_reapairer_entry.py
  src/mesh_reapairer/
    application/             # use-cases / orchestrator
    cli/                     # CLI entry point
    infrastructure/          # IO + plotting backend adapters
    msu/                     # структура сетки (domain)
    restorer/                # восстановление (domain)
    self_intersection_finder/# поиск самопересечений (domain)
    vizualizator/            # визуализация (domain API)
  tests/
  pyproject.toml
  pytest.ini
  .pre-commit-config.yaml
  python-style.md
  uv-python.md
```

---

## Модульные зависимости (как вы описали)

- `mesh_reapairer` → `self_intersection_finder`, `restorer`, `vizualizator`, `msu`
- `self_intersection_finder` → `bvh_builder`, `intersection_finder`, `border_restorer`
- `restorer` → `triangulator`, `fixer`
- `vizualizator` → `face_plotter`, `segment_plotter`, `line_plotter`, `plane_plotter`, `point_plotter`, `mesh_plotter`

Назначения:

- **`self_intersection_finder`**: ищет самопересечения сетки
  - **`bvh_builder`**: строит/обходит BVH
  - **`intersection_finder`**: ищет пересечения ячеек/примитивов
  - **`border_restorer`**: чинит границу в области пересечения
  - **`main.py`**: склейка шагов в единый pipeline `find_self_intersections`
- **`restorer`**: восстанавливает сетку
  - **`triangulator`**: триангуляция ячеек/полигонов
  - **`fixer`**: удаление внутренней части самопересечения и финальная очистка
- **`vizualizator`**: визуализирует этапы восстановления сетки
- **`msu`**: структура сетки (вершины/грани) — базовый доменный слой

---

## Документация

В проекте поддерживается принцип “Source of Truth — репозиторий” (см. `docs.md`).

- **архитектура**: `docs/architecture.md`
- **использование**: `docs/usage.md`
- **uv и окружение**: `uv-python.md`
- **стиль / линтер / тайпчекер**: `python-style.md`

---

## Окружение и зависимости (uv)

Рекомендуемый флоу — через `uv` (подробнее в `uv-python.md`):

```bash
# Установка uv (macOS, один из вариантов)
brew install uv

# 1) Установить Python 3.13 (если нужно)
uv python install 3.13

# 2) Создать виртуальное окружение
uv venv --python 3.13

# 3) Установить зависимости (включая dev-группу)
uv sync
```

### Альтернатива без uv (venv + pip)

Если `uv` недоступен, можно использовать стандартный `venv` и extras `dev`:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

### Опциональная зависимость Graphviz / pygraphviz

`pygraphviz` требует системный Graphviz (заголовки `cgraph.h`). На macOS:

```bash
brew install graphviz
python -m pip install -e ".[dev,graphviz]"
```
Установка pygraphviz для MacOS
```bash
  pip install pygraphviz \
  --no-cache-dir \
  --config-settings="--global-option=build_ext" \
  --config-settings="--global-option=-I/opt/homebrew/opt/graphviz/include/" \
  --config-settings="--global-option=-L/opt/homebrew/opt/graphviz/lib/"
```

---

## Запуск приложения

### Через CLI (console script)

После `uv sync` доступен entrypoint `mesh-reapairer`:

```bash
uv run mesh-reapairer examples/meshes/self_intersecting_dummy.json examples/meshes/out.json
```

### Через Python API

```bash
uv run python -c "from mesh_reapairer import repair_mesh; from mesh_reapairer.infrastructure.io import load_mesh; m=load_mesh('examples/meshes/simple_triangle.json'); _=repair_mesh(m); print('ok')"
```

### Пример-скрипт

```bash
uv run python examples/run_repair.py
```

---

## Качество кода: форматирование, линтер, типы, тесты

Конфиг и best practices берутся из `python-style.md` и `pyproject.toml`.

### Ruff (форматирование)

```bash
uv run ruff format .        # если используете uv
ruff format .               # если активирован venv и ruff установлен
```

### Ruff (линт)

```bash
uv run ruff check .         # uv
uv run ruff check . --fix

ruff check .                # venv
ruff check . --fix
```

### Mypy (type checking)

```bash
uv run mypy .               # uv
mypy .                      # venv
```

### Pytest

```bash
uv run pytest               # uv
pytest                      # venv
```

---

## Сборка

### 1) Сборка Python-пакета (wheel + sdist)

`uv` умеет собирать дистрибутивы в `dist/`:

```bash
uv build                    # uv

# venv: wheel/sdist сборка через build (нужно установить)
python -m pip install -U build
python -m build
```

Результат: `dist/*.whl` и `dist/*.tar.gz`.

### 2) Сборка standalone бинарника (PyInstaller)

Для сборки “одним файлом” используется PyInstaller (dev dependency).

```bash
uv run pyinstaller --onefile --name mesh-reapairer scripts/mesh_reapairer_entry.py   # uv
pyinstaller --onefile --name mesh-reapairer scripts/mesh_reapairer_entry.py         # venv
```

Результат на macOS: `dist/mesh-reapairer` (исполняемый файл).

Проверка:

```bash
./dist/mesh-reapairer examples/meshes/simple_triangle.json /tmp/out.json
```

---

## Pre-commit (опционально)

```bash
uv sync
pre-commit install
pre-commit run --all-files
```
