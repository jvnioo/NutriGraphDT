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
  (A44-2, A44-3). La copia de su `run.json` en `runs/` permite verificar la semilla, la
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
| `runs/…/<run_id>.json` | Copia del `run.json` de cada corrida, sin checkpoints. |
| `configs/models/tuned/<dataset>_<variante>.yaml` | Configuración elegida; se lee con `--model-config` de `train_gnn.py`. |

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
