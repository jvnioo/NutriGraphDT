# Baselines trivial y lineales (A40-4)

Pisos de desempeño que la GNN debe superar. Están implementados en
`nutrigraphdt.models.baselines` y se entrenan sobre la tabla de atributos de A40-3
([`tabular-features.md`](tabular-features.md)) con la partición de A40-1. Las métricas son las
de A40-2 ([`metrics.md`](metrics.md)).

## Modelos

| Nombre | Estimador | Hiperparámetros ajustados |
|---|---|---|
| `dummy_mean` | `DummyRegressor(strategy="mean")`: predice la media de cada AGCC en `train` | — |
| `ridge` | `Pipeline(StandardScaler, Ridge)` | `alpha` |
| `elasticnet` | `Pipeline(StandardScaler, ElasticNet)` | `alpha`, `l1_ratio` |

Los tres modelos son multisalida: un solo modelo predice acetato, propionato y butirato a la
vez. `Ridge` y `ElasticNet` aceptan `y` con varias columnas de forma nativa, con los mismos
hiperparámetros para los tres AGCC.

## Protocolo

1. **Ajuste solo con `train`.** El `StandardScaler` está dentro del `Pipeline`, así que en cada
   fold de la validación cruzada se ajusta solo con la parte de entrenamiento del fold, y en el
   modelo final solo con `train`. `val` y `test` no intervienen en el escalado ni en la
   selección de hiperparámetros; una prueba unitaria lo verifica alterando sus atributos.
2. **Validación cruzada agrupada.** `GridSearchCV` con `GroupKFold` sobre `train`. El grupo lo
   entrega quien llama (`groups: sample_id -> grupo`) y debe ser la unidad de la partición de
   A40-1:
   - en D1, el corral (`pen_code`), como fija `configs/splits/d1_holofood.json`;
   - en la cohorte sintética, el `sample_id`: cada instancia es un animal distinto y el
     generador no define corrales.

   El Issue pide agrupar "por animal" en el texto y "por corral en D1" en la nota técnica. Se
   sigue la nota y A40-1: el corral contiene a los animales, así que agrupar por corral también
   evita que un mismo animal quede a ambos lados de un fold.
3. **Selección.** `scoring = neg_root_mean_squared_error`, promediado sobre los tres AGCC sin
   ponderar. Como los AGCC tienen escalas distintas, el acetato pesa más en la selección. Es una
   decisión de implementación configurable, no una exigencia del Issue.
4. **Evaluación.** El modelo reajustado con todo `train` se evalúa en `val` y `test` con
   `evaluate_predictions` (MAE, RMSE, R² y porcentaje de predicciones negativas por AGCC y
   promedio).

Si un subconjunto está vacío, si falta algún AGCC en una muestra, si falta el grupo de una muestra
de `train` o si `train` tiene menos grupos que folds, `train_linear_baselines` lanza `ValueError`
en lugar de omitir muestras o reducir los folds en silencio.

## Configuración

`configs/baselines/linear.json` versiona la grilla y la validación cruzada:

| Clave | Valor | Uso |
|---|---|---|
| `ridge_alphas` | 0.001 … 1000 (7 valores, escala log) | grilla de `Ridge.alpha` |
| `elasticnet_alphas` | 0.001 … 10 (5 valores, escala log) | grilla de `ElasticNet.alpha` |
| `elasticnet_l1_ratios` | 0.1, 0.5, 0.9 | grilla de `ElasticNet.l1_ratio` |
| `elasticnet_max_iter` | 10000 | iteraciones de descenso coordinado |
| `cv_folds` | 5 | folds de `GroupKFold` |
| `scoring` | `neg_root_mean_squared_error` | criterio de selección |

Son valores de partida habituales, no constantes científicas. `LinearBaselineConfig` rechaza
claves desconocidas o faltantes y valores fuera de rango.

## Uso

Requiere el extra `baselines` (scikit-learn, BSD-3-Clause; verificado con 1.9.1):

```bash
pip install -e ".[dev,baselines]"
python scripts/run_linear_baselines.py
```

El script arma una cohorte sintética de `--n-samples` instancias (semillas consecutivas desde
`--first-seed`), crea la partición con `create_split` (`--split-seed`), entrena y escribe en
`--output` (por defecto `artifacts/baselines/linear`, ignorado por Git) `report.csv`,
`report.md` y `run.json` con la configuración, las semillas, los tamaños y los hiperparámetros
elegidos.

Para D1, los grupos se leen del `pen_code` de la metadata:

```python
import csv

from nutrigraphdt.models import build_tabular_dataset, get_split
from nutrigraphdt.models.baselines import LinearBaselineConfig, train_linear_baselines

dataset = build_tabular_dataset(tables, split=get_split())  # tables: ver tabular-features.md
with open("data/raw/D1_holofood/metadata.tsv", encoding="utf-8") as handle:
    groups = {row["sample_id"]: row["pen_code"] for row in csv.DictReader(handle, delimiter="\t")}
config = LinearBaselineConfig.load("configs/baselines/linear.json")
result = train_linear_baselines(dataset, groups, config)
print(result.report.to_markdown())
```

La partición versionada de D1 deja 3 corrales en `train`, así que con esos datos hay que bajar
`cv_folds` a 3 o menos; con 5 folds la función rechaza la entrada.

## Registro: cohorte sintética

- Comando: `python scripts/run_linear_baselines.py` (valores por defecto).
- Datos: 50 instancias sintéticas, semillas 1 a 50; partición con semilla 42:
  30 `train`, 10 `val`, 10 `test`; 24 columnas numéricas después del one-hot.
- Configuración: `configs/baselines/linear.json` tal como está en el repositorio.
- Entorno: Python 3.12.0, scikit-learn 1.9.1, numpy 2.4.6.
- Hiperparámetros elegidos: `ridge.alpha = 1000`; `elasticnet.alpha = 10`,
  `elasticnet.l1_ratio = 0.9`.

Promedio de los tres AGCC:

| Modelo | Split | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| `dummy_mean` | val | 7.5050 | 8.3610 | -0.0501 |
| `dummy_mean` | test | 6.2485 | 7.2502 | -0.1804 |
| `ridge` | val | 7.5049 | 8.3715 | -0.0515 |
| `ridge` | test | 6.2431 | 7.2610 | -0.1842 |
| `elasticnet` | val | 7.5050 | 8.3610 | -0.0501 |
| `elasticnet` | test | 6.2485 | 7.2502 | -0.1804 |

Ningún modelo produjo predicciones negativas. La tabla por AGCC está en `report.md`.

**Interpretación.** El generador sintético asigna la concentración de cada AGCC sin relación
con los atributos (`nutrigraphdt.data.synthetic.nodes`). Por eso la validación cruzada elige la
regularización más fuerte de la grilla, y `ridge` y `elasticnet` quedan prácticamente en la
media, igual que `dummy_mean`. El resultado es coherente con los datos: muestra que el flujo de
entrenamiento, selección y evaluación funciona, pero **no** mide la capacidad predictiva de
ningún modelo ni sirve como referencia numérica para la GNN. La comparación válida requiere D1
u otro conjunto con objetivos medidos.

Las pruebas unitarias (`tests/unit/test_baselines.py`) usan objetivos lineales en los atributos
y verifican que `ridge` sí supera al piso de la media (R² > 0.9 en `val` y `test`).

## Limitaciones

- Los resultados sintéticos no tienen valor predictivo (ver Interpretación).
- La validación cruzada en D1 está limitada a 3 grupos en `train`, y `val` y `test` tienen 2 y
  1 corral: las métricas de D1 tendrán alta varianza.
- Un mismo `alpha` regulariza los tres AGCC; ajustar uno por objetivo queda fuera de A40-4.
