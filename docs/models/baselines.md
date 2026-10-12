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
y partición en un solo comando, escribiendo en `reports/baselines/` y en `reports/` la tabla
comparativa (`baseline_comparison.md`, `baseline_comparison.csv`), el reporte completo
(`report.csv`, `report.md`), las importancias de atributos (`importances.csv`) y los metadatos
con los hiperparámetros elegidos (`run.json`).

Ambos scripts y el comparador unificado arman la misma cohorte sintética con
`build_synthetic_baseline_dataset`: `--n-samples` instancias (semillas consecutivas desde
`--first-seed`) y la partición de `create_split` (`--split-seed`). Con los mismos argumentos,
sus resultados son comparables.

Para D1, los grupos se leen del `pen_code` de la metadata:

```python
import csv

from nutrigraphdt.models import build_tabular_dataset, get_split
from nutrigraphdt.models.baselines import (
    LinearBaselineConfig,
    TreeBaselineConfig,
    train_all_baselines,
    train_linear_baselines,
    train_tree_baselines,
)

dataset = build_tabular_dataset(tables, split=get_split())  # tables: ver tabular-features.md
with open("data/raw/D1_holofood/metadata.tsv", encoding="utf-8") as handle:
    groups = {row["sample_id"]: row["pen_code"] for row in csv.DictReader(handle, delimiter="\t")}
all_baselines = train_all_baselines(
    dataset,
    groups,
    LinearBaselineConfig.load("configs/baselines/linear.json"),
    TreeBaselineConfig.load("configs/baselines/trees.json"),
)
print(all_baselines.report.to_markdown())
```

La partición versionada de D1 deja 3 corrales en `train`, así que con esos datos hay que bajar
`cv_folds` a 3 o menos; con 5 folds la función rechaza la entrada.

## Registro: cohorte sintética

- Comandos: `python scripts/run_linear_baselines.py` y `python scripts/run_tree_baselines.py`
  (valores por defecto).
- Datos: 50 instancias sintéticas, semillas 1 a 50; partición con semilla 42:
  30 `train`, 10 `val`, 10 `test`; 24 columnas numéricas después del one-hot.
- Configuración: `configs/baselines/linear.json` y `configs/baselines/trees.json` tal como
  están en el repositorio.
- Entorno: Python 3.12.0, scikit-learn 1.9.1, numpy 2.4.6.
- Hiperparámetros elegidos:
  - `ridge.alpha = 1000`; `elasticnet.alpha = 10`, `elasticnet.l1_ratio = 0.9`;
  - `random_forest`: `n_estimators = 300`, `max_depth = null`, `min_samples_leaf = 5`;
  - `hist_gradient_boosting`: `learning_rate = 0.05`, `max_iter = 100`, `max_depth = 3`,
    `min_samples_leaf = 2`.

Promedio de los tres AGCC:

| Modelo | Split | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| `dummy_mean` | val | 7.5050 | 8.3610 | -0.0501 |
| `dummy_mean` | test | 6.2485 | 7.2502 | -0.1804 |
| `ridge` | val | 7.5049 | 8.3715 | -0.0515 |
| `ridge` | test | 6.2431 | 7.2610 | -0.1842 |
| `elasticnet` | val | 7.5050 | 8.3610 | -0.0501 |
| `elasticnet` | test | 6.2485 | 7.2502 | -0.1804 |
| `random_forest` | val | 7.8706 | 8.7605 | -0.1308 |
| `random_forest` | test | 6.3666 | 7.3331 | -0.2026 |
| `hist_gradient_boosting` | val | 9.5900 | 10.3729 | -0.6167 |
| `hist_gradient_boosting` | test | 7.6145 | 8.6579 | -0.8970 |

Ningún modelo produjo predicciones negativas. La tabla por AGCC está en `report.md`.

**Interpretación.** El generador sintético asigna la concentración de cada AGCC sin relación
con los atributos (`nutrigraphdt.data.synthetic.nodes`), así que no hay señal que aprender:

- La validación cruzada elige la regularización más fuerte para los lineales, y `ridge` y
  `elasticnet` quedan prácticamente en la media, igual que `dummy_mean`.
- Los árboles quedan por debajo del piso de la media porque ajustan ruido; `hist_gradient_boosting`
  más, por tener menos regularización efectiva con 30 muestras.
- En `importances.csv`, 10 de los 24 atributos tienen importancia exactamente cero porque son
  constantes en `train` (composición de la dieta, aditivo, `host:age_days` y el tratamiento: el
  generador usa la misma dieta para todas las instancias). Entre los que varían (taxones,
  `host:body_weight_g`, `host:sex`), hay valores positivos y negativos de hasta -0.54: permutar
  un atributo con importancia negativa mejora el puntaje, señal de que el modelo ajustó ruido.
  Los atributos con mayor importancia positiva no coinciden entre los dos modelos y en la
  mayoría la desviación estándar supera a la media. Con 10 muestras en `val`, no son atributos
  relevantes.

El resultado es coherente con los datos: muestra que el flujo de entrenamiento, selección,
evaluación e importancia funciona, pero **no** mide la capacidad predictiva de ningún modelo,
no identifica atributos relevantes ni sirve como referencia numérica para la GNN. La
comparación válida requiere D1 u otro conjunto con objetivos medidos.

Las pruebas unitarias usan objetivos que sí dependen de los atributos: en
`tests/unit/test_baselines.py`, `ridge` supera al piso de la media (R² > 0.9 en `val` y `test`);
en `tests/unit/test_tree_baselines.py`, ambos árboles alcanzan R² > 0.5 en `test` y la importancia
de los atributos informativos supera a la del atributo de ruido.

## Limitaciones

- Los resultados sintéticos no tienen valor predictivo (ver Interpretación).
- La validación cruzada en D1 está limitada a 3 grupos en `train`, y `val` y `test` tienen 2 y
  1 corral: las métricas de D1 tendrán alta varianza, y la importancia por permutación sobre las
  2 muestras de `val` no será informativa.
- Una misma combinación de hiperparámetros se usa para los tres AGCC; ajustar una por objetivo
  queda fuera de A40-4 y A40-5.
- La importancia es agregada sobre los tres AGCC; una importancia por AGCC requeriría un
  `scoring` por objetivo.
