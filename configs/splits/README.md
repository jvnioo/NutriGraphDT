# Particiones de datos versionadas (`configs/splits/`)

Este directorio contiene las particiones canónicas train / validation / test de los datasets del proyecto, generadas sin fuga de datos (*data leakage*) y bajo control de versiones.

Tanto los modelos de referencia (*baselines*: Random Forest, Ridge, MLP, etc.) como las arquitecturas basadas en grafos (GNN) deben utilizar exactamente estas particiones para asegurar que las comparaciones de rendimiento sean científicamente válidas e idénticas en cualquier entorno de ejecución (local, CI o reproducción externa).

## Archivos disponibles

- `d1_holofood.json`: Partición del dataset real **D1 HoloFood** (pollo), versión **2.0.0**.
  - **Agrupamiento**: por corral (`pen_code`). Como los tratamientos dietarios se asignaron al azar a nivel de corral, aislar corrales enteros evita la transferencia de efectos de lote o cohabitación entre subconjuntos.
  - **Estratificación**: por tratamiento dietario (`diet_treatment_code` / `diet_treatment_name`), tolerando estratos pequeños.
  - **Semilla**: determinista (`seed = 42`).
  - **Ratios canónicos**: 60 % entrenamiento (`train`), 20 % validación (`val`), 20 % prueba (`test`).

- `d1_holofood_cv.json`: validación cruzada por corral de D1 (D-07, #139), la evaluación
  principal de D1: asignación `semilla → sample_id → fold` de `StratifiedGroupKFold` (grupo
  `pen_code`, estrato dieta, k = 5, semillas 0 a 9) sobre la cohorte oficial de 56 animales. Se
  genera con `python scripts/create_cv_folds.py`; véase
  [`docs/models/cross-validation.md`](../../docs/models/cross-validation.md).

## D1 HoloFood, versión 2.0.0 (A45-1, #101)

Generada sobre la descarga completa de `scripts/fetch_holofood.py` (`metadata.tsv` con 530
animales; 185 con metagenoma cecal y grafo; 61 con AGCC de contenido cecal, de los cuales 59
tienen acetato, propionato y n-butirato con valor):

```bash
python scripts/fetch_holofood.py
python scripts/create_split.py --input data/raw/D1_holofood/metadata.tsv --overwrite
```

`create_split.py` escribe `version = "1.0.0"`; se subió a `2.0.0` a mano porque la pertenencia
cambia por completo respecto de la versión anterior.

| Subconjunto | Animales | Corrales | Con grafo | Corrales con grafo | Con grafo y los tres AGCC | Corrales con target | Tratamientos con target (CC/CO/CE) |
|---|---:|---:|---:|---:|---:|---:|---|
| `train` | 315 | 42 | 105 | 39 | 31 | 17 | 21 / 8 / 2 |
| `val` | 102 | 15 | 33 | 12 | 7 | 5 | 1 / 4 / 2 |
| `test` | 113 | 15 | 47 | 13 | 21 | 10 | 15 / 3 / 3 |
| **Total** | 530 | 72 | 185 | 64 | 59 | 32 | 37 / 15 / 7 |

- Los 185 animales con grafo están en la partición y ningún corral aparece en dos subconjuntos
  (`tests/integration/test_holofood_source.py`, con la descarga completa).
- **Máximo de `cv_folds` en los baselines (A45-2):** 17, los corrales de `train` con animales
  con target. Los animales sin AGCC no aportan a la pérdida ni a las métricas.
- **`val` queda con 7 animales con target (menos de 8).** La partición agrupa y estratifica sobre
  los 530 animales, pero solo 59 tienen target, y estos se concentran en pocos corrales.

### Alternativa documentada, no aplicada

Como `val` queda por debajo de 8 animales con target, el Issue pide documentar esta alternativa y
acordarla con el sublíder antes de aplicarla: generar la partición solo sobre los 59 animales
con grafo y los tres AGCC (misma agrupación, estratificación y semilla). Con
`create_split(..., seed=42)` sobre esos 59 animales quedaría:

| Subconjunto | Animales con target | Corrales | Tratamientos (CC/CO/CE) |
|---|---:|---:|---|
| `train` | 38 | 20 | 24 / 9 / 5 |
| `val` | 9 | 6 | 4 / 4 / 1 |
| `test` | 12 | 6 | 9 / 2 / 1 |

- **Ventajas:** `val` y `test` quedan más parejos en animales con target, y `train` sube a 20
  corrales.
- **Desventajas:** los 126 grafos de D1 sin los tres AGCC quedarían fuera de la partición (hoy se
  asignan aunque no aporten a la pérdida), y la partición dejaría de servir a cualquier análisis
  que use todos los animales con metadatos.

Hasta que el sublíder decida, la versión canónica es la de los 530 animales.

## Fixture de prueba

La partición anterior (versión 1.0.0, seis animales del fixture) se conserva en
`tests/fixtures/holofood/split.json`. Las pruebas que construyen tablas o grafos con el fixture la
cargan con `get_split(split_file=...)`; la partición canónica no depende de datos que no están en
el repositorio.

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
python scripts/create_split.py --input <metadatos.tsv> --output configs/splits/<dataset>.json --seed 42
```
