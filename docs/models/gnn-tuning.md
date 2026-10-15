# Búsqueda de hiperparámetros y variabilidad por semilla (A45-5)

`scripts/tune_gnn.py` responde dos preguntas antes de sacar conclusiones de A45-3 y A45-4:
cuánto cambia el resultado con la capacidad del modelo y cuánto con la semilla. Con 61 animales
con AGCC en D1 (7 en `val`), una sola corrida puede inducir a error. La lógica está en
`nutrigraphdt.models.training.tuning`; cada corrida se entrena con `run_training` (A44-6), igual
que `scripts/train_gnn.py`.

## Procedimiento

1. **Grilla.** Para la variante indicada con `--model`, se entrena cada combinación de
   `hidden_channels` ∈ {32, 64, 128} y `num_layers` ∈ {1, 2, 3}, el rango de ajuste del §6 de
   [gnn-architecture.md](gnn-architecture.md), con la primera semilla de `--seeds`. Los demás
   hiperparámetros salen de `configs/models/<variante>.yaml` y `configs/training/default.json`.
2. **Selección.** Se elige la combinación con menor RMSE promedio de `val`. Si hay empate, gana
   el modelo más chico (menos `hidden_channels` y luego menos `num_layers`).
3. **Semillas.** Se repiten con 5 semillas (por defecto 42 a 46) la configuración inicial de las
   tres variantes y la elegida. Se reportan media y desviación estándar muestral de RMSE, MAE y
   R² promedio en `val` y `test`. `--only-model` repite solo la variante de `--model`.

Una misma configuración y semilla se entrena una sola vez: por ejemplo, la corrida 64 × 2 con
semilla 42 de la grilla se reutiliza en la fase de semillas.

## `test` no interviene en la selección

- La selección (`select_best`) solo lee el RMSE de `val`; los tests verifican que cambiar las
  métricas de `test` no cambia la elección.
- `grid.csv` y `selection.json` solo tienen métricas de `val`. `selection.json` registra el
  criterio, cada candidata con su `run_id` y su RMSE de `val`, y `"test_used": false`.
- Dentro de cada corrida, el escalado se ajusta con `train` y la detención temprana usa `val`
  (A44-2, A44-3). La copia de su `run.json` en `run_records/` permite verificar la semilla, la
  configuración, la partición (SHA-256) y la mejor época de cada candidata.
- Las métricas de `test` solo aparecen en la fase de semillas (`seeds.csv`, `summary.csv`), después
  de elegir.

## Uso

Primero confirme el código con el árbol limpio, para que cada `run.json` registre el commit con
`dirty: false`. Corra cada dataset con la mejor variante de su reporte (menor RMSE promedio de
`val` en `reports/gnn/synthetic/` y `reports/gnn/d1/`):

```powershell
python .\scripts\tune_gnn.py --dataset synthetic --model hetero_gat
python .\scripts\tune_gnn.py --dataset d1 --model homo_sage
```

`--dataset d1` necesita los grafos guardados por `scripts/build_graph.py --save-graphs` (ver
[gnn-training.md](gnn-training.md)). La carga de datos es la misma de `train_gnn.py`, pero
scikit-learn solo se importa con `--dataset synthetic`, porque la cohorte sintética se arma con el
módulo de baselines: `d1` funciona en un equipo sin el extra `baselines`. Opciones principales:

| Opción | Por defecto | Uso |
|---|---|---|
| `--hidden`, `--layers` | `32 64 128`, `1 2 3` | Valores de la grilla. |
| `--seeds` | `42 43 44 45 46` | Semillas de la fase de repetición. |
| `--grid-seed` | La primera de `--seeds` | Semilla de la grilla. |
| `--only-model` | Desactivado | Repetir solo la variante de `--model`. |
| `--runs-dir` | `runs/tuning` | Corridas completas (ignoradas por Git), en `<dataset>/<variante>_h<hidden>_l<capas>/<run_id>/`. |
| `--output` | `reports/gnn/tuning/<dataset>` | Archivos del reporte. |
| `--selected-config` | `configs/models/tuned/<dataset>_<variante>.yaml` | Configuración elegida. |

También acepta las opciones de sobrescritura de `train_gnn.py` (`--max-epochs`, `--lr`, …),
salvo `--seed`: las semillas se indican con `--seeds` y `--grid-seed`.

## Salidas

| Archivo | Contenido |
|---|---|
| `grid.csv` | Una fila por combinación: semilla, `run_id` y RMSE, MAE y R² promedio de `val`. |
| `selection.json` | Criterio, candidatas, `run_id` y configuración elegida. |
| `seeds.csv` | Una fila por corrida de la fase de semillas, con `val` y `test`. |
| `summary.csv` | Media, desviación estándar y número de semillas por variante, configuración, subconjunto y métrica. |
| `report.md` | Grilla y tabla media ± desviación estándar del RMSE promedio. |
| `run_records/…/<run_id>.json` | Copia del `run.json` de cada corrida, sin checkpoints. La carpeta no se llama `runs/` porque `.gitignore` ignora toda carpeta con ese nombre. |
| `configs/models/tuned/<dataset>_<variante>.yaml` | Configuración elegida; se lee con `--model-config` de `train_gnn.py`. |

## Resultados (corridas del 15/10/2026, commit `6595cc1`)

Configuración de entrenamiento por defecto (`configs/training/default.json`), CPU. Detalle en
`reports/gnn/tuning/synthetic/` y `reports/gnn/tuning/d1/`. RMSE promedio de los tres AGCC,
media ± desviación estándar sobre las semillas 42 a 46.

**D1 HoloFood** (`homo_sage`, la de menor RMSE de `val` en A45-4; 31/7/21 animales con los tres
AGCC; Windows, Python 3.13):

| Variante | Configuración | RMSE val | RMSE test |
|---|---|---:|---:|
| `homo_sage` | inicial 64 × 2 | 9.49 ± 0.10 | 8.75 ± 0.06 |
| `hetero_sage` | inicial 64 × 2 | 9.53 ± 0.10 | 8.76 ± 0.02 |
| `hetero_gat` | inicial 64 × 2 | 9.53 ± 0.10 | 8.77 ± 0.07 |
| `homo_sage` | elegida 128 × 3 | 9.36 ± 0.06 | 8.78 ± 0.09 |
| `dummy_mean` (`reports/baselines/d1/`) | — | 10.93 | 9.75 |

**Cohorte sintética** (`hetero_gat`, la de menor RMSE de `val` en A45-3; 30/10/10 muestras;
Linux, Python 3.11, porque en el equipo con Windows el Control inteligente de aplicaciones
bloquea scipy y la cohorte requiere scikit-learn):

| Variante | Configuración | RMSE val | RMSE test |
|---|---|---:|---:|
| `homo_sage` | inicial 64 × 2 | 8.22 ± 0.12 | 7.06 ± 0.12 |
| `hetero_sage` | inicial 64 × 2 | 8.23 ± 0.06 | 7.03 ± 0.18 |
| `hetero_gat` | inicial 64 × 2 | 8.29 ± 0.13 | 7.05 ± 0.21 |
| `hetero_gat` | elegida 128 × 1 | 8.19 ± 0.09 | 7.02 ± 0.11 |
| `dummy_mean` (`reports/baselines/`) | — | 8.36 | 7.25 |

Lectura:

- **Reproducibilidad.** La corrida 64 × 2 con semilla 42 reproduce exactamente el RMSE de `val`
  de A45-3 (8.2047, `hetero_gat`) y de A45-4 (9.5211, `homo_sage`), en otro equipo y sistema
  operativo.
- **La configuración elegida no mejora en `test`.** En D1, 128 × 3 baja el RMSE de `val` de
  9.49 a 9.36, pero en `test` queda en 8.78 frente a 8.75 de la inicial: la mejora en `val`
  (7 animales) no se traslada. En el sintético, todas las diferencias caben en una desviación
  estándar. No hay evidencia para reemplazar la configuración inicial.
- **Las tres variantes son indistinguibles** dentro de la variabilidad por semilla (≈ 0.1 de
  RMSE), como anticipa el §7 del diseño: en D1 los taxones están aislados y en el sintético los
  AGCC no dependen de las entradas.
- En D1 todas las GNN tienen menor RMSE que `dummy_mean` en `val` y `test`; en el sintético
  la diferencia es pequeña y no interpretable (ver `reports/gnn/synthetic/report.md`).

## Limitaciones

- **La grilla usa una sola semilla.** Con `val` tan pequeño, la combinación elegida puede cambiar
  con otra semilla; la fase de semillas muestra si la mejora frente a la configuración inicial
  supera la variabilidad.
- **Cohorte sintética.** En el generador actual los AGCC no dependen de las entradas (ver
  `reports/gnn/synthetic/report.md`): la búsqueda verifica el procedimiento, no la capacidad
  predictiva.
- **La configuración elegida es provisional.** Alimenta la reunión de ajuste posterior al
  avance 2 (act. 49) y la fase F5; no reemplaza `configs/models/*.yaml`.
- **Reproducibilidad entre equipos.** El redondeo de punto flotante cambia entre CPU, GPU y
  sistemas operativos (ver [gnn-training.md](gnn-training.md)); los reportes registran el
  entorno de cada corrida.
