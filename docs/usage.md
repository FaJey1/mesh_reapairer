 # Использование mesh_reapairer

## Высокоуровневый сценарий

1. Загрузить сетку (infrastructure-слой).
2. Передать её в application-пайплайн восстановления.
3. Получить восстановленную сетку и, при необходимости, визуализировать этапы.

## Пример (псевдокод)

```python
from mesh_reapairer.application.orchestrator import repair_mesh
from mesh_reapairer.infrastructure.io import load_mesh, save_mesh

input_mesh = load_mesh("examples/self_intersecting_mesh.txt")
repaired_mesh = repair_mesh(input_mesh)
save_mesh(repaired_mesh, "examples/self_intersecting_mesh_repaired.txt")
```

