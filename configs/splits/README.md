# Particiones de datos versionadas (`configs/splits/`)

Este directorio contiene las particiones canónicas train / validation / test de los datasets del proyecto, generadas sin fuga de datos (*data leakage*) y bajo control de versiones.

Tanto los modelos de referencia (*baselines*: Random Forest, Ridge, MLP, etc.) como las arquitecturas basadas en grafos (GNN) deben utilizar exactamente estas particiones para asegurar que las comparaciones de rendimiento sean científicamente válidas e idénticas en cualquier entorno de ejecución (local, CI o reproducción externa).

## Archivos disponibles

- `d1_holofood.json`: Partición del dataset real **D1 HoloFood** (pollo).
  - **Agrupamiento**: por corral (`pen_code`). Como los tratamientos dietarios se asignaron al azar a nivel de corral, aislar corrales enteros evita la transferencia de efectos de lote o cohabitación entre subconjuntos.
  - **Estratificación**: por tratamiento dietario (`diet_treatment_code` / `diet_treatment_name`), tolerando estratos pequeños.
  - **Semilla**: determinista (`seed = 42`).
  - **Ratios canónicos**: 60 % entrenamiento (`train`), 20 % validación (`val`), 20 % prueba (`test`).

## Uso en Python

```python
from nutrigraphdt.data.split import get_split

# Devuelve la partición canónica (por defecto D1 HoloFood)
split = get_split()

# Desempaquetado directo
train_ids, val_ids, test_ids = split

# Acceso como atributos o como diccionario
print(f"Train: {len(split.train)}, Val: {len(split.val)}, Test: {len(split.test)}")
print(split["train"])

# Filtrado directo de HeteroData o diccionarios de muestras
train_graphs, val_graphs, test_graphs = split.filter(graphs_dict)

# Máscaras booleanas (para PyTorch/NumPy)
masks = split.mask(sample_id_list)
```

## Regeneración o nuevas particiones

Para generar una partición personalizada o para un nuevo dataset:

```bash
python scripts/create_split.py --input tests/fixtures/holofood/metadata.tsv --output configs/splits/d1_holofood.json --seed 42
```
