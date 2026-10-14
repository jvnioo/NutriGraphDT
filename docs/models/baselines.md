# Baselines no basados en grafos (A40-4, A40-5, A40-6)

Pisos de desempeño que la GNN debe superar y referencia de cuánto aporta el grafo por sobre un
modelo tabular fuerte. Están implementados en `nutrigraphdt.models.baselines` y se entrenan
sobre la tabla de atributos de A40-3 ([`tabular-features.md`](tabular-features.md)) con la
partición de A40-1. Las métricas son las de A40-2 ([`metrics.md`](metrics.md)). La consolidación
en un único reporte y script comparativo (A40-6) provee la tabla para el informe de avance 2.

## Modelos

| Nombre | Issue | Estimador | Hiperparámetros ajustados |
|---|---|---|---|
| `dummy_mean` | A40-4 | `DummyRegressor(strategy="mean")`: predice la media de cada AGCC en `train` | — |
| `ridge` | A40-4 | `Pipeline(StandardScaler, Ridge)` | `alpha` |
| `elasticnet` | A40-4 | `Pipeline(StandardScaler, ElasticNet)` | `alpha`, `l1_ratio` |
| `random_forest` | A40-5 | `RandomForestRegressor` | `n_estimators`, `max_depth`, `min_samples_leaf` |
| `hist_gradient_boosting` | A40-5 | `MultiOutputRegressor(HistGradientBoostingRegressor)` | `learning_rate`, `max_iter`, `max_depth`, `min_samples_leaf` |

Todos predicen acetato, propionato y butirato. `Ridge`, `ElasticNet` y `RandomForestRegressor`
aceptan `y` con varias columnas de forma nativa. `HistGradientBoostingRegressor` predice un solo
objetivo, así que `MultiOutputRegressor` entrena una copia por AGCC. En todos los casos los tres
AGCC comparten la misma combinación de hiperparámetros. Los árboles no necesitan escalado.

## Protocolo

1. **Ajuste solo con `train`.** Todo lo que se ajusta a los datos (el `StandardScaler` de los
   lineales y los modelos) se ajusta solo con la parte de entrenamiento de cada fold y, en el
   modelo final, solo con `train`. `val` y `test` no intervienen en el ajuste ni en la selección
   de hiperparámetros; las pruebas unitarias lo verifican alterando sus atributos.
2. **Validación cruzada agrupada.** `GridSearchCV` con `GroupKFold` sobre `train`. El grupo lo
   entrega quien llama (`groups: sample_id -> grupo`) y debe ser la unidad de la partición de
   A40-1:
   - en D1, el corral (`pen_code`), como fija `configs/splits/d1_holofood.json`;
   - en la cohorte sintética, el `sample_id`: cada instancia es un animal distinto y el
     generador no define corrales.

   A40-4 y A40-5 piden agrupar "por animal" en el texto y "por corral en D1" en la nota
   técnica. Se sigue la nota y A40-1: el corral contiene a los animales, así que agrupar por
   corral también evita que un mismo animal quede a ambos lados de un fold.
3. **Selección.** `scoring = neg_root_mean_squared_error`, promediado sobre los tres AGCC sin
   ponderar. Como los AGCC tienen escalas distintas, el acetato pesa más en la selección. Es una
   decisión de implementación configurable, no una exigencia de los Issues.
4. **Evaluación.** El modelo reajustado con todo `train` se evalúa en `val` y `test` con
   `evaluate_predictions` (MAE, RMSE, R² y porcentaje de predicciones negativas por AGCC y
   promedio).
5. **Importancia de atributos (árboles).** Importancia por permutación
   (`sklearn.inspection.permutation_importance`) del modelo final, sobre `val`, con el mismo
   `scoring` y `permutation_repeats` permutaciones por atributo. Es la caída media del puntaje al
   permutar un atributo; un valor cercano a cero o negativo indica que el modelo no depende de
   él.
   - Se usa el mismo método para los dos modelos. `RandomForestRegressor` también ofrece
     importancia por impureza, pero `HistGradientBoostingRegressor` no, y las dos medidas no son
     comparables entre sí.
   - Se calcula sobre `val` porque no participa en el ajuste (sobre `train` mediría lo
     memorizado) y deja `test` intacto para la comparación final.
   - Es una importancia agregada sobre los tres AGCC y describe al modelo, no una relación
     causal ni biológica entre atributo y AGCC. Es el insumo para contrastar con la
     explicabilidad de la GNN.

`prepare_baseline_data` lanza `ValueError` si un subconjunto está vacío, si falta algún AGCC en
una muestra, si falta el grupo de una muestra de `train` o si `train` tiene menos grupos que
folds, en lugar de omitir muestras o reducir los folds en silencio.

## Configuración

Las grillas son valores de partida habituales, no constantes científicas.
`LinearBaselineConfig` y `TreeBaselineConfig` rechazan claves desconocidas o faltantes y valores
fuera de rango.

`configs/baselines/linear.json` (A40-4):

| Clave | Valor | Uso |
|---|---|---|
| `ridge_alphas` | 0.001 … 1000 (7 valores, escala log) | grilla de `Ridge.alpha` |
| `elasticnet_alphas` | 0.001 … 10 (5 valores, escala log) | grilla de `ElasticNet.alpha` |
| `elasticnet_l1_ratios` | 0.1, 0.5, 0.9 | grilla de `ElasticNet.l1_ratio` |
| `elasticnet_max_iter` | 10000 | iteraciones de descenso coordinado |
| `cv_folds` | 5 | folds de `GroupKFold` |
| `scoring` | `neg_root_mean_squared_error` | criterio de selección |

`configs/baselines/trees.json` (A40-5); en las profundidades, `null` es sin límite:

| Clave | Valor | Uso |
|---|---|---|
| `random_forest_n_estimators` | 300 | árboles del bosque |
| `random_forest_max_depth` | null, 3, 6 | profundidad máxima |
| `random_forest_min_samples_leaf` | 1, 3, 5 | muestras mínimas por hoja |
| `hist_gradient_boosting_learning_rate` | 0.05, 0.1 | tasa de aprendizaje |
| `hist_gradient_boosting_max_iter` | 100 | iteraciones de boosting |
| `hist_gradient_boosting_max_depth` | null, 3 | profundidad máxima |
| `hist_gradient_boosting_min_samples_leaf` | 2, 5 | muestras mínimas por hoja |
| `cv_folds` | 5 | folds de `GroupKFold` |
| `scoring` | `neg_root_mean_squared_error` | selección e importancia |
| `random_state` | 42 | semilla de los modelos y de la permutación |
| `permutation_repeats` | 10 | permutaciones por atributo |

El valor por defecto de `min_samples_leaf` en `HistGradientBoostingRegressor` es 20; con unas 24
muestras por fold de entrenamiento casi no habría divisiones, por eso la grilla usa 2 y 5.

## Uso

Requiere el extra `baselines` (scikit-learn, BSD-3-Clause; verificado con 1.9.1):

```bash
pip install -e ".[dev,baselines]"
python scripts/run_linear_baselines.py
python scripts/run_tree_baselines.py
python scripts/compare_baselines.py
```

`run_linear_baselines.py` y `run_tree_baselines.py` ejecutan cada familia por separado. El script
unificado `scripts/compare_baselines.py` (A40-6) ejecuta los 5 modelos sobre la misma cohorte
y partición en un solo comando, escribiendo en `reports/baselines/` la tabla comparativa
(`baseline_comparison.md`, `baseline_comparison.csv`), el reporte completo (`report.csv`,
`report.md`), las importancias de atributos (`importances.csv`) y los metadatos con los
hiperparámetros elegidos (`run.json`).

Ambos scripts y el comparador unificado arman la misma cohorte sintética con
`build_synthetic_baseline_dataset`: `--n-samples` instancias (semillas consecutivas desde
`--first-seed`) y la partición de `create_split` (`--split-seed`). Con los mismos argumentos,
sus resultados son comparables.

Para D1, los grupos se leen del `pen_code` de la metadata:

```python
import csv

from nutrigraphdt.models import build_tabular_dataset, get_split
from nutrigraphdt.models.baselines import train_all_baselines

dataset = build_tabular_dataset(tables, split=get_split())  # tables: ver tabular-features.md
with open("data/raw/D1_holofood/metadata.tsv", encoding="utf-8") as handle:
    groups = {row["sample_id"]: row["pen_code"] for row in csv.DictReader(handle, delimiter="\t")}
all_baselines = train_all_baselines(dataset, groups)
print(all_baselines.report.to_markdown())
```

La partición canónica de D1 (versión 2.0.0, A45-1) cubre los 530 animales con metadatos. Los
baselines solo pueden usar los 59 animales con grafo y los tres AGCC, que quedan repartidos en
31 animales y 17 corrales en `train`, 7 y 5 en `val`, y 21 y 10 en `test`. Con esos datos,
`cv_folds` no puede superar 17. Los animales sin AGCC hacen fallar `prepare_baseline_data`, así
que hay que filtrarlos antes (A45-2, #102).

## Registro: cohorte sintética (tabla consolidada A40-6)

La tabla consolidada para el informe de avance 2 se genera ejecutando:

```bash
python scripts/compare_baselines.py
```

### Resumen de la corrida consolidada

- **Comando:** `python scripts/compare_baselines.py` (o `python scripts/run_linear_baselines.py` y `python scripts/run_tree_baselines.py`).
- **Artefactos generados:** `reports/baselines/baseline_comparison.md`, `reports/baselines/baseline_comparison.csv`, `reports/baselines/report.md`, `reports/baselines/report.csv`, `reports/baselines/importances.csv` y `reports/baselines/run.json`.
- **Datos y cohorte:** 50 instancias sintéticas de la cohorte `synthetic_baseline_cohort` (semillas 1 a 50).
- **Partición (A40-1):** semilla 42, con división estratificada por tratamiento de dieta:
  - `train`: 30 instancias (60%).
  - `val`: 10 instancias (20%).
  - `test`: 10 instancias (20%).
- **Espacio de atributos (A40-3):** 24 columnas numéricas continuas/one-hot extraídas sin fuga de objetivo (`verify_no_target_leakage`).
- **Validación cruzada:** 5 folds agrupados con `GroupKFold` sobre `train` (en cohorte sintética, cada animal es su propio grupo al no modelarse corrales).
- **Métricas calculadas (A40-2):** MAE, RMSE, R² y porcentaje de predicciones negativas (% Neg), evaluadas por separado en `val` y `test` tanto a nivel individual por metabolito (acetato, propionato, butirato) como en promedio macro no ponderado.
- **Entorno verificado:** Python 3.12, scikit-learn 1.9.1, numpy 2.4.6.

### Hiperparámetros elegidos

La búsqueda en grilla optimizada por `GroupKFold(n_splits=5)` seleccionó los siguientes hiperparámetros (registrados en `reports/baselines/run.json`):

| Modelo | Hiperparámetros elegidos | Grilla explorada / Comportamiento |
|---|---|---|
| `dummy_mean` | Ninguno | Línea base trivial: predice la media de cada AGCC en `train`. |
| `ridge` | `alpha = 1000.0` | **Borde superior de la grilla** (`[0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]`). La optimización satura en la penalización máxima $L_2$ para contraer coeficientes hacia cero al no existir correlación real. |
| `elasticnet` | `alpha = 10.0`, `l1_ratio = 0.9` | Penalización máxima explorada con fuerte componente $L_1$. **Anula la totalidad de los coeficientes**, reproduciendo exactamente las predicciones y métricas de `dummy_mean`. |
| `random_forest` | `n_estimators = 300`, `max_depth = null`, `min_samples_leaf = 5` | Prefiere hojas más grandes (`min_samples_leaf = 5`) para mitigar el sobreajuste al ruido sintético. |
| `hist_gradient_boosting` | `learning_rate = 0.05`, `max_iter = 100`, `max_depth = 3`, `min_samples_leaf = 2` | Selecciona la menor tasa de aprendizaje (`0.05`) y árboles someros (`max_depth = 3`). |

### Resultados macro de la tabla comparativa

Promedio de los tres AGCC (resumen de `reports/baselines/baseline_comparison.md`):

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 7.5050 | 8.3610 | -0.0501 | 0.0% |
| `dummy_mean` | test | 6.2485 | 7.2502 | -0.1804 | 0.0% |
| `ridge` | val | 7.5049 | 8.3715 | -0.0515 | 0.0% |
| `ridge` | test | 6.2431 | 7.2610 | -0.1842 | 0.0% |
| `elasticnet` | val | 7.5050 | 8.3610 | -0.0501 | 0.0% |
| `elasticnet` | test | 6.2485 | 7.2502 | -0.1804 | 0.0% |
| `random_forest` | val | 7.8706 | 8.7605 | -0.1308 | 0.0% |
| `random_forest` | test | 6.3666 | 7.3331 | -0.2026 | 0.0% |
| `hist_gradient_boosting` | val | 9.5900 | 10.3729 | -0.6167 | 0.0% |
| `hist_gradient_boosting` | test | 7.6145 | 8.6579 | -0.8970 | 0.0% |

Ningún modelo produjo predicciones negativas (% Neg = 0.0%). Los desgloses por metabolito están en `reports/baselines/baseline_comparison.md` y `reports/baselines/report.md`.

### Interpretación y advertencia para el informe de avance 2

> [!WARNING]
> **Advertencia metodológica fundamental para el informe de avance 2**:
> Con los datos sintéticos actuales, **esta tabla no mide capacidad predictiva real ni debe presentarse como un piso de desempeño para la GNN**.
> Su único propósito es demostrar y auditar que el flujo metodológico completo (preparación sin fuga, partición versionada, validación cruzada agrupada, ajuste en grilla, cálculo de métricas e inferencia) funciona de extremo a extremo de forma reproducible.

**Fundamentos estadísticos del comportamiento observado:**

1. **Ausencia de señal predictiva en los datos sintéticos**: El generador de cohorte sintética asigna las concentraciones de cada AGCC sin dependencia funcional respecto a los 24 atributos tabulares del huésped y taxones (`nutrigraphdt.data.synthetic.nodes`). No existe señal verdadera que aprender.
2. **Ningún modelo supera la media (`dummy_mean`)**: Todos los modelos obtienen $R^2$ macro promedio negativo en `val` y `test` (desde $-0.18$ en `dummy_mean` hasta $-0.90$ en `hist_gradient_boosting`). Un $R^2$ negativo en el conjunto de prueba indica que el modelo predice peor que la media histórica del conjunto de entrenamiento.
3. **Regularización extrema en modelos lineales**:
   - `ridge` selecciona $\alpha = 1000.0$, el valor máximo en el borde superior de la grilla. Al carecer de correlación real entre $X$ e $y$, la validación cruzada empuja los coeficientes hacia cero tanto como la grilla lo permite.
   - `elasticnet` selecciona $\alpha = 10.0, l1\_ratio = 0.9$ y anula todos los coeficientes ($w = 0$). Sus predicciones son idénticas al intercepto (la media de `train`), arrojando exactamente las mismas métricas que `dummy_mean`.
4. **Sobreajuste al ruido en modelos de árboles**: Los árboles intentan segmentar variaciones espurias en las 30 muestras de `train`. `random_forest` degrada a $R^2 = -0.20$ en `test`, y `hist_gradient_boosting` cae a $R^2 = -0.90$ en `test`.
5. **Importancias de atributos no interpretables**: En `importances.csv`, 10 de los 24 atributos tienen importancia cero (constantes en la cohorte). Los restantes exhiben importancias cercanas a cero o negativas (hasta $-0.54$, lo que significa que romper la relación mediante permutación mejora el error porque destruye ruido memorizado).

### Alcance exclusivo a cohorte sintética vs. D1 HoloFood

Es imprescindible aclarar que la tabla consolidada es **estrictamente sintética**:
- La partición de datos reales D1 HoloFood (`configs/splits/d1_holofood.json`) cubre desde A45-1 (#101) los 530 animales de la descarga completa; los baselines todavía no se han ejecutado sobre ella (A45-2, #102).
- Una evaluación numérica válida que defina pisos reales para la GNN requerirá ejecutar este mismo protocolo sobre D1 HoloFood una vez completadas las particiones de la cohorte biológica real.

Las pruebas unitarias usan objetivos que sí dependen de los atributos: en
`tests/unit/test_baselines.py`, `ridge` supera al piso de la media (R² > 0.9 en `val` y `test`);
en `tests/unit/test_tree_baselines.py`, ambos árboles alcanzan R² > 0.5 en `test` y la importancia
de los atributos informativos supera a la del atributo de ruido.

## Limitaciones

- Los resultados sintéticos no tienen valor predictivo (ver Interpretación y advertencia).
- En D1, `val` tiene solo 7 animales con los tres AGCC (5 corrales) y `test` 21 (10 corrales):
  las métricas de D1 tendrán alta varianza, y la importancia por permutación sobre las 7
  muestras de `val` será poco informativa.
- Una misma combinación de hiperparámetros se usa para los tres AGCC; ajustar una por objetivo
  queda fuera de A40-4 y A40-5.
- La importancia es agregada sobre los tres AGCC; una importancia por AGCC requeriría un
  `scoring` por objetivo.
