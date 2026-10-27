# Protocolo y módulo de métricas de evaluación (A40-2)

Este documento describe la especificación formal, las fórmulas matemáticas y el formato
de salida común del módulo de métricas de evaluación (`nutrigraphdt.models.metrics`),
diseñado para evaluar tanto modelos de referencia (baselines lineales y de árboles) como
redes neuronales de grafos (GNN) en la predicción de ácidos grasos de cadena corta (AGCC:
acetato, propionato y butirato).

## 1. Métricas implementadas

Para cada AGCC $k \in \{\text{acetate}, \text{propionate}, \text{butyrate}\}$ con $N$ muestras
de prueba $(y_i, \hat{y}_i)$:

### 1.1 Error Absoluto Medio (MAE)
Mide la magnitud promedio del error en las mismas unidades de concentración que los datos
originales ($\mu\text{mol/g}$ o concentraciones molares):

$$\text{MAE}_k = \frac{1}{N} \sum_{i=1}^N |y_{i,k} - \hat{y}_{i,k}|$$

### 1.2 Raíz del Error Cuadrático Medio (RMSE)
Penaliza de forma cuadrática desviaciones grandes o valores atípicos severos:

$$\text{RMSE}_k = \sqrt{\frac{1}{N} \sum_{i=1}^N (y_{i,k} - \hat{y}_{i,k})^2}$$

### 1.3 Coeficiente de Determinación ($R^2$)
Evalúa la proporción de varianza explicada respecto a la varianza total de los datos:

$$R^2_k = 1 - \frac{\sum_{i=1}^N (y_{i,k} - \hat{y}_{i,k})^2}{\sum_{i=1}^N (y_{i,k} - \bar{y}_k)^2}$$

En el caso límite donde la varianza empírica es cero ($\sum (y_i - \bar{y})^2 = 0$):
- Si todos los residuos son cero ($\hat{y}_i = y_i$), $R^2 = 1.0$.
- Si existen residuos no nulos, $R^2 = 0.0$.

### 1.4 Porcentaje de predicciones negativas (`negative_pct`)
Las concentraciones biológicas de metabolitos son intrínsecamente no negativas ($y \ge 0$).
Modelos lineales no restringidos pueden emitir concentraciones negativas en regiones
poco densas del espacio de entrada.

Esta métrica cuantifica la violación del espacio factible bioquímico:

$$\text{negative\_pct}_k = \frac{\sum_{i=1}^N \mathbb{I}(\hat{y}_{i,k} < 0)}{N} \times 100$$

Sirve como insumo de diagnóstico directo para guiar la incorporación de restricciones
fisiológicas en la fase F5 (véase el [protocolo de evaluación con/sin restricciones](constraints-evaluation-protocol.md)).

### 1.5 Promedio agregado (Macro-Average)
Para cada una de las 4 métricas, se calcula el promedio aritmético no ponderado entre los
3 AGCC evaluados:

$$\overline{\text{Métrica}} = \frac{1}{K} \sum_{k=1}^K \text{Métrica}_k$$

---

## 2. Formato común de salida

Para facilitar la comparación directa entre baselines (`DummyRegressor`, `Ridge`, `ElasticNet`,
`RandomForest`, `LightGBM`) y las variantes de GNN (heterogéneas y homogéneas), el módulo
define la estructura `MetricRow` y `EvaluationReport` con la política de **una fila por modelo y métrica**.

### Estructura de columnas

| Campo | Tipo | Descripción |
|---|---|---|
| `model` | `str` | Identificador del modelo (ej. `'Ridge'`, `'ElasticNet'`, `'GNN_Hetero'`) |
| `split` | `str?` | Partición evaluada (ej. `'val'`, `'test'`) o `-` |
| `group` | `str?` | Subgrupo (por ejemplo, día de muestreo en las métricas de D-03, sección 4); solo aparece si alguna fila lo tiene |
| `metric` | `str` | Métrica evaluada (`'mae'`, `'rmse'`, `'r2'`, `'negative_pct'`) |
| `acetate` | `float` | Valor para acetato |
| `propionate` | `float` | Valor para propionato |
| `butyrate` | `float` | Valor para butirato |
| `average` | `float` | Macro-promedio entre los AGCC |

### Ejemplo de tabla Markdown exportada

```markdown
| model | split | metric | acetate | propionate | butyrate | average |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Ridge | test | mae | 3.0000 | 7.0000 | 1.0000 | 3.6667 |
| Ridge | test | rmse | 3.2404 | 10.7471 | 1.0000 | 4.9958 |
| Ridge | test | r2 | 0.9160 | -2.6960 | 0.8000 | -0.3267 |
| Ridge | test | negative_pct | 0.0000 | 25.0000 | 0.0000 | 8.3333 |
```

---

## 3. Ejemplo de uso en código

```python
from nutrigraphdt.models import combine_reports, evaluate_predictions

# Predicciones por diccionario o matriz (N, 3)
report_dummy = evaluate_predictions(
    y_true=y_test,
    y_pred=y_dummy_pred,
    model_name="DummyMean",
    split="test",
)

report_ridge = evaluate_predictions(
    y_true=y_test,
    y_pred=y_ridge_pred,
    model_name="Ridge",
    split="test",
)

# Consolidar benchmarking en un solo reporte
consolidated = combine_reports([report_dummy, report_ridge])

# Exportar a Markdown o registros para DataFrames
print(consolidated.to_markdown())
rows = consolidated.to_records()
```

## 4. Objetivo composicional y métricas de D-03 (contrato v2, #146)

El [contrato de datos v2](../graph/data-contract-v2.md#1-variable-objetivo-composición-de-los-agcc-y-total-aparte-d-03)
cambia el objetivo principal de D1 a la **composición** de acetato, propionato y n-butirato,
con el total como salida secundaria. La transformación versionada vive en
`nutrigraphdt.models.composition` (`COMPOSITIONAL_TARGET_VERSION = "1.0.0"`) y la usan por igual
baselines y GNN; el grafo sigue guardando solo las concentraciones medidas.

| Función | Uso |
|---|---|
| `compositional_target(a, p, b)` | Concentraciones (mmol/kg) → `T`, fracciones `p_i`, `z_1 = ln(p/a)`, `z_2 = ln(b/a)` y `ln T`, con `valid` como máscara. |
| `concentrations_from_output(z_1, z_2, ln T)` | Inversa: softmax de `(0, z_1, z_2)` por `T`, en mmol/kg. |
| `evaluate_composition(true, pred, model, split=, sampling_days=)` | Métricas de D-03 a partir de concentraciones medidas y salidas `(z_1, z_2, ln T)`. |
| `models.gnn.target.compositional_graph_target(y_graph, y_graph_mask)` | Versión con tensores: objetivo `[B, 3]` y máscara `[B, 1]` derivados de `y_graph`. |
| `models.gnn.target.concentrations_from_graph_output(output)` | Inversa con tensores. |

**Ceros y ausencias.** Un AGCC ausente, no finito, igual a cero o negativo deja la máscara del
animal en `False`, sin pseudoconteo (pregunta 1 de la sección 9 del contrato). Esos animales no
entran a la pérdida ni a las métricas composicionales.

**Ida y vuelta.** Concentraciones → objetivo → concentraciones reproduce los valores con
tolerancia relativa `ROUND_TRIP_RTOL = 1e-9` (en `float64` el error observado es del orden de
1e-15).

**Métricas.** `evaluate_composition` devuelve un `EvaluationReport` con seis filas por grupo:

| `metric` | Columnas | Unidad |
|---|---|---|
| `fraction_mae_pp`, `fraction_r2` | una por AGCC; `average` es el promedio macro | puntos porcentuales |
| `log_total_mae`, `log_total_r2` | `log_total` | ln(mmol/kg) |
| `reconstructed_mae`, `reconstructed_r2` | una por AGCC; `average` es el promedio macro | mmol/kg de digesta fresca |

La columna `group` vale `all` para las métricas globales y el día de muestreo para las filas por
día (con `sampling_days`). Solo se evalúan animales con objetivo válido. La media y la
dispersión entre folds y semillas corresponden a la validación cruzada por corral (#139).
`MetricRow.group` es opcional: los reportes existentes, sin grupo, no cambian de formato.
