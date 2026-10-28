# Protocolo de evaluación con/sin restricciones y criterios de aceptación (A55-P1, #155)

Este documento define el protocolo formal, reproducible y estandarizado para la evaluación y
comparación de modelos predictivos (redes neuronales sobre grafos heterogéneos y baselines
competitivos) entrenados **con y sin restricciones bioquímicas/fisiológicas** en el marco de la
fase F5 de NutriGraphDT (Actividad A55-P1).

Para garantizar coherencia metodológica y comparabilidad directa con los avances de F4, este
protocolo adopta íntegramente:
1. El **esquema de validación cruzada por corral** (`StratifiedGroupKFold`, $k = 5$, 10 semillas)
   fijado por D-07 e implementado en [#139](cross-validation.md).
2. El **objetivo composicional de los AGCC** (fracciones molares mediante log-razones y total
   desacoplado $\ln T$) y la batería de métricas de D-03 implementados en [#146](metrics.md#4-objetivo-composicional-y-métricas-de-d-03-contrato-v2-146)
   (`nutrigraphdt.models.composition`).
3. El estado de entrega de las restricciones bioquímicas y estequiométricas (**D-06**),
   declarando formalmente las tolerancias y ecuaciones que se encuentran pendientes de la
   Actividad 78 de Investigación, sin inventar parámetros arbitrarios.

> [!NOTE]
> **Estado: propuesta de Desarrollo, sin aprobación científica.** La revisión con Investigación
> se registra en [`explanations-protocol-review.md`](explanations-protocol-review.md) (A55-P4,
> #158). Los valores marcados como provisionales no se usan como base estable hasta recibir
> respuesta escrita.

---

## 1. Esquema de partición y protocolo sin fuga (D-07, #139)

La evaluación comparativa de variantes libres vs. restringidas debe ejecutarse estrictamente
sobre la infraestructura de validación cruzada establecida en D-07:

### 1.1 Cohorte oficial supervisada
- **Datos base:** Cohorte oficial D1 HoloFood de 56 animales (`configs/cohorts/d1_holofood.json`,
  [#138](https://github.com/jvnioo/NutriGraphDT/issues/138)), tras excluir muestras con menos de
  1000 lecturas SSU o con AGCC objetivo faltantes (acetato, propionato y n-butirato medidos en
  $\text{mmol/kg}$ de digesta fresca, matriz `caecum_content`).
- **Composición de cohortes por dieta:** 34 animales en dieta Control, 15 en Probiótico y 7 en
  Fitobiótico (desbalance 34/15/7, limitación L1).

### 1.2 Plan de folds versionado
- **Plan canónico:** `configs/splits/d1_holofood_cv.json` (hash SHA-256 canónico verificado).
- **Estructura:** `StratifiedGroupKFold` con $k = 5$ folds y 10 semillas fijas ($S \in \{0, 1, \dots, 9\}$),
  totalizando exactamente **50 folds evaluados**.
- **Grupo:** `pen_code` (identificador único del corral). Ningún corral puede figurar
  simultáneamente en el conjunto de entrenamiento y de prueba del mismo fold.
- **Estrato:** `diet_treatment_code`. Cada fold contiene representación de las tres dietas
  experimentales.
- **Distribución:** Cada fold cuenta con 10 a 12 animales y 5 a 8 corrales.

### 1.3 Protocolo estricto contra fuga de información (*Data Leakage*)
Para asegurar una estimación no sesgada del error de generalización fuera de corral:
1. **Ajuste dependiente exclusivo de `train`:** Todo preprocesamiento dependiente de la muestra
   (ajuste de medias y desviaciones de atributos en `FeatureScaler`, estandarización de las salidas
   en `TargetScaler`, imputaciones y aprendizaje de pesos) se ajusta única y exclusivamente con los
   animales de entrenamiento del fold (`train_ids`).
2. **Detención temprana interna:** En modelos neuronales iterativos (GNN), la detención temprana
   no debe evaluar el subconjunto de prueba del fold. Se utiliza `split_inner_validation` apartando
   un quinto de los corrales del entrenamiento mediante `StratifiedGroupKFold` interno con semilla
   determinista derivada (`base + semilla_plan × 100 + fold`). Los pesos de la mejor época se
   congelan antes de inferir sobre el conjunto de prueba (`test_ids`).
3. **Selección de hiperparámetros:** Si se optimizan hiperparámetros de regularización o
   penalización de restricciones ($\lambda_{\text{constraint}}$), la búsqueda se puntúa
   exclusivamente sobre la validación interna de los folds de entrenamiento correspondientes a las
   semillas de selección (`--selection-seeds`), registrando `test_used: false`. El conjunto de prueba
   se evalúa una sola vez con la configuración seleccionada.
4. **Pareamiento estricto:** El modelo sin restricciones (brazo no restringido, $M_0$) y el modelo
   con restricciones (brazo restringido, $M_C$) deben entrenarse y evaluarse exactamente sobre los
   mismos 50 folds y con las mismas semillas de inicialización de optimizadores, garantizando
   estimaciones pareadas por fold.

---

## 2. Espacio objetivo, transformaciones y métricas predictivas (D-03, #146)

La comparación de desempeño predictivo se rige por la especificación de
`nutrigraphdt.models.composition` (`COMPOSITIONAL_TARGET_VERSION = "1.0.0"`).

### 2.1 Salidas del modelo y transformaciones
Para cada animal $i$, el modelo emite un vector tridimensional:
$$\hat{\mathbf{z}}_i = \left(\hat{z}_{1,i}, \hat{z}_{2,i}, \widehat{\ln T}_i\right)$$
donde:
- $\hat{z}_{1,i}$: predicción de la log-razón centrada en acetato $\ln(\text{propionato} / \text{acetato})$.
- $\hat{z}_{2,i}$: predicción de la log-razón $\ln(\text{butirato} / \text{acetato})$.
- $\widehat{\ln T}_i$: predicción del logaritmo de la concentración total molar
  $T_i = \text{acetato}_i + \text{propionato}_i + \text{butirato}_i$.

**Inversa canónica a fracciones molares:**
$$\hat{p}_{k,i} = \frac{\exp(\hat{\ell}_{k,i})}{\sum_{j \in \{a, p, b\}} \exp(\hat{\ell}_{j,i})}, \quad \text{con } \hat{\boldsymbol{\ell}}_i = (0, \hat{z}_{1,i}, \hat{z}_{2,i})$$

**Reconstrucción de concentraciones molares absolutas ($\text{mmol/kg}$ digesta fresca):**
$$\hat{c}_{k,i} = \hat{T}_i \cdot \hat{p}_{k,i} = \exp\left(\widehat{\ln T}_i\right) \cdot \hat{p}_{k,i}$$

### 2.2 Batería de métricas predictivas (D-03)
Calculadas mediante `evaluate_composition` tanto a nivel global (`group = "all"`) como por día de
muestreo (`group` $\in \{7, 21, 35\}$, los días de la cohorte de D1; ver
[`covariates.py`](../../src/nutrigraphdt/data/covariates.py) y #158, P-01):

| Dimensión | Métrica | Nombre en reporte | Unidad | Descripción |
|---|---|---|---|---|
| **Composición** | Error Absoluto Medio | `fraction_mae_pp` | puntos porcentuales (pp) | MAE entre $100 \cdot p_{k}$ y $100 \cdot \hat{p}_{k}$ por AGCC y macro-promedio (`average`). |
| **Composición** | Coeficiente de determinación | `fraction_r2` | adimensional ($\le 1.0$) | Proporción de varianza explicada en la proporción de cada AGCC y promedio. |
| **Escala total** | Error Absoluto Medio | `log_total_mae` | $\ln(\text{mmol/kg})$ | MAE sobre la escala logarítmica total $\ln T$. |
| **Escala total** | Coeficiente de determinación | `log_total_r2` | adimensional ($\le 1.0$) | $R^2$ sobre $\ln T$ (evalúa capacidad predictiva de la biomasa total). |
| **Concentración** | Error Absoluto Medio | `reconstructed_mae` | $\text{mmol/kg}$ | MAE en concentraciones físicas reconstruidas $\hat{c}_k$ por AGCC y promedio. |
| **Concentración** | Coeficiente de determinación | `reconstructed_r2` | adimensional ($\le 1.0$) | $R^2$ en concentraciones físicas reconstruidas por AGCC y promedio. |

---

## 3. Taxonomía de restricciones y métricas de violaciones (F5 / D-06)

En el gemelo digital NutriGraphDT conviven restricciones de naturaleza matemática/estructural y
restricciones bioquímicas procedentes del conocimiento biológico.

### 3.1 Clasificación de restricciones

```text
Restricciones
 ├── Estructurales / Intrínsecas (garantizadas por diseño composicional en GNN)
 │    ├── No-negatividad estricta: c_k >= 0, p_k >= 0
 │    └── Cierre simplex: sum(p_k) = 1
 └── Fisiológicas / Bioquímicas externas (módulo constraints, F5 / D-06)
      ├── Balances de fermentación estequiométrica (Wolin, 1960; en fracciones p_k)
      ├── Balances de masa de sustrato a producto (requieren T_total)
      └── Rangos fisiológicos de pH y capacidad buffer cecal
```

1. **No-negatividad y cierre unitario:**
   - En modelos que operan en el espacio composicional ($\text{alr}$ con inversa $\text{softmax}$ y
     $\exp(\widehat{\ln T})$), las predicciones $\hat{p}_k$ y $\hat{c}_k$ son estrictamente
     positivas y suman 1 por construcción matemática.
   - Para baselines directos o arquitecturas desacopladas que predicen en $\mathbb{R}^3$, la
     no-negatividad y el cierre simplex son restricciones activas que pueden violarse.
2. **Ecuaciones estequiométricas y balances molares (D-06):**
   - Según los principios de Investigación (sección 4.6 de la *Respuesta a la Solicitud v1.1*),
     las relaciones estequiométricas entre acetato, propionato y butirato (e.g. balances de
     recuperación de hidrógeno según Wolin, 1960) se expresan en **proporciones molares** ($p_i$),
     pudiendo aplicarse directamente a la composición predicha.
   - Los balances de masa absolutos requieren la escala total $T$, cuyo $R^2$ fuera de corral en
     D1 es cercano a cero ($R^2 \approx 0$).

### 3.2 Declaración explícita sobre tolerancias pendientes de D-06
> [!IMPORTANT]
> **Estado de D-06 (Actividad 78 de Investigación): PENDIENTE.**
> Las ecuaciones bioquímicas definitivas, sus formulaciones analíticas exactas y las tolerancias
> numéricas admisibles ($\epsilon_{\text{biochem}}$ o intervalos $[L_k, U_k]$) corresponden a la
> entrega formal de Investigación previa al desarrollo del módulo de restricciones en F5.
>
> **Política de integridad científica:** Desarrollo **no inventa** valores de tolerancia,
> constantes cinéticas ni límites arbitrarios. Las métricas de violación se definen de forma
> genérica y paramétrica, listas para recibir los operadores y tolerancias formales de D-06.

### 3.3 Formalización matemática de métricas de violación
Dada una restricción general indexada por $j$:
- De desigualdad: $h_j(\hat{\mathbf{y}}_i) \le 0$
- De igualdad con tolerancia $\epsilon_j \ge 0$ (fijada por D-06): $|g_j(\hat{\mathbf{y}}_i)| \le \epsilon_j$

Se define la **magnitud puntual de violación** para la muestra $i$ como:
$$v_{j,i} = \begin{cases}
\max\left(0, h_j(\hat{\mathbf{y}}_i)\right) & \text{si es desigualdad} \\
\max\left(0, |g_j(\hat{\mathbf{y}}_i)| - \epsilon_j\right) & \text{si es igualdad con tolerancia}
\end{cases}$$

A partir de $v_{j,i}$, se calculan cuatro métricas estandarizadas sobre el conjunto de evaluación
de tamaño $N$:

#### 1. Tasa de Violación (*Violation Rate*, $\text{VR}_j$)
Porcentaje de instancias que transgreden el espacio biológicamente factible:
$$\text{VR}_j = \frac{100}{N} \sum_{i=1}^N \mathbb{I}(v_{j,i} > 0) \quad [\%]$$

#### 2. Magnitud Media de Violación (*Violation Mean Magnitude*, $\text{VMM}_j$)
Grado promedio de desviación respecto a la frontera de factibilidad:
$$\text{VMM}_j = \frac{1}{N} \sum_{i=1}^N v_{j,i}$$
Complementariamente, para evitar atenuación por muestras factibles, se reporta la magnitud
condicional a violación:
$$\text{VMM}_{j|\text{viol}} = \frac{\sum_{i=1}^N v_{j,i}}{\sum_{i=1}^N \mathbb{I}(v_{j,i} > 0)} \quad (\text{definida si } \text{VR}_j > 0)$$

#### 3. Magnitud en Peor Caso (*Violation Worst-case Magnitude*, $\text{VWM}_j$)
Penalización máxima observada y percentil 95 ($P_{95}$) para detectar anomalías extremas:
$$\text{VWM}_j = \max_{1 \le i \le N} v_{j,i}$$

#### 4. Tasa de Factibilidad Total Conjunta (*Joint Feasibility Rate*, $\text{FR}$)
Porcentaje de muestras que satisfacen simultáneamente la totalidad de restricciones activas
$J$:
$$\text{FR} = \frac{100}{N} \sum_{i=1}^N \prod_{j=1}^J \mathbb{I}(v_{j,i} = 0) \quad [\%]$$

---

## 4. Análisis estadístico e incertidumbre

La comparación de un modelo con restricciones ($M_C$) frente a su homólogo libre ($M_0$) no debe
basarse en promedios aislados, sino en la distribución de diferencias a través de los corrales y
semillas.

### 4.1 Agregación jerárquica de resultados
Para cada modelo y métrica, el agregador de la validación cruzada (`aggregate_fold_reports`)
genera:
- `_mean`: media aritmética entre los 50 folds ($10 \text{ semillas} \times 5 \text{ folds}$).
- `_std`: desviación estándar total entre los 50 folds (captura variabilidad inter-corral e
  inter-semilla combinada).
- `_seed_std`: desviación estándar entre las 10 medias por semilla (aisla la variabilidad debida
  únicamente al particionamiento estocástico).
- `_n`: número efectivo de folds evaluados (diagnóstico de celdas no estimables).

### 4.2 Inferencia estadística pareada en CV repetida
Dado que las predicciones provienen de los mismos 50 folds, las comparaciones métricas se efectúan
sobre el vector de diferencias pareadas:
$$\Delta_{s,k} = \text{Métrica}(M_C)_{s,k} - \text{Métrica}(M_0)_{s,k}$$
para la semilla $s \in \{0, \dots, 9\}$ y el fold $k \in \{0, \dots, 4\}$.

> [!CAUTION]
> **Riesgo estadístico: Dependencia por solapamiento en CV repetida.**
> En validación cruzada con $k = 5$, cada par de folds dentro de una misma semilla comparte el
> 75% de sus datos de entrenamiento. Un test $t$ de Student pareado convencional ignora esta
> correlación residual, subestima la varianza del error y produce tasas de falsos positivos
> (error Tipo I) severamente infladas (Dietterich, 1998; Bouckaert & Frank, 2004).

Para reportar significancia formal, el protocolo exige:
1. **Test $t$ corregido para CV repetida (Nadeau & Bengio, 2003; Bouckaert & Frank, 2004):**
   La varianza del estimador de la diferencia media $\bar{\Delta}$ se ajusta por la fracción de
   muestras de prueba frente a entrenamiento:
   $$\sigma^2_{\text{corregida}} = \left(\frac{1}{K \cdot S} + \frac{n_{\text{test}}}{n_{\text{train}}}\right) s^2_{\Delta}$$
   donde $n_{\text{test}} / n_{\text{train}} \approx \frac{1}{4} = 0.25$, $K = 5$ folds y $S = 10$
   semillas. El estadístico $t_{\text{corr}} = \bar{\Delta} / \sigma_{\text{corregida}}$ sigue una
   distribución $t$ con $K \cdot S - 1 = 49$ grados de libertad.
2. **Test no paramétrico de Wilcoxon:** Test de rangos con signo pareado sobre las 10 medias
   consolidadas por semilla ($N = 10$), inmune a supuestos distribucionales de normalidad en las
   diferencias.

### 4.3 Distinción entre significancia estadística y relevancia práctica
Un p-valor significativo ($p < 0.05$) no implica necesariamente un beneficio biológico o técnico.
El protocolo define:
- **Magnitud del efecto (d de Cohen pareada):**
  $$d = \frac{\bar{\Delta}}{s_{\Delta}}$$
  Interpretada como despreciable ($|d| < 0.2$), pequeña ($0.2 \le |d| < 0.5$), mediana
  ($0.5 \le |d| < 0.8$) o grande ($|d| \ge 0.8$).
- **Región de Equivalencia Práctica (*ROPE* - Region of Practical Equivalence):**
  Se fija un umbral $\delta_{\text{ROPE}} = 1.0 \text{ pp}$ en el MAE macro de fracciones.
  **Valor provisional propuesto por Desarrollo, sin fuente de Investigación**: queda pendiente
  de confirmación en la revisión de #158 (P-02).
  Diferencias predictivas dentro de $[-\delta_{\text{ROPE}}, +\delta_{\text{ROPE}}]$ se consideran
  prácticamente equivalentes en exactitud composicional.

---

## 5. Criterios de aceptación multicriterio

La decisión de adoptar un modelo con restricciones ($M_C$) frente a un modelo sin restricciones
($M_0$) se estructura mediante un marco de decisión jerárquico que pondera factibilidad biológica,
calidad predictiva y estabilidad:

```text
Decisión con/sin restricciones
 │
 ├── 1. Factibilidad (Violaciones):
 │    ¿Reduce VR y VMM significativamente hacia 0 (dentro de tolerancia D-06)?
 │    ├── NO  ──> RECHAZO: la restricción no se impone efectivamente.
 │    └── SÍ
 │         │
 │         └── 2. Calidad Predictiva (No-inferioridad en D-03):
 │              ¿Se degrada el MAE de fracciones en más de delta_ROPE (1.0 pp)?
 │              ├── SÍ  ──> RECHAZO: costo predictivo excesivo frente a la restricción.
 │              └── NO
 │                   │
 │                   └── 3. Estabilidad y Dispersión:
 │                        ¿La dispersión _seed_std y _std se mantiene controlada?
 │                        ├── SÍ ──> ACEPTACIÓN (Clasificación según tabla)
 │                        └── NO ──> RECHAZO: optimización inestable.
```

### Matriz de clasificación de resultados

| Clasificación | Desempeño predictivo ($\Delta \text{MAE}$) | Violaciones ($\Delta \text{VR}$, $\Delta \text{VMM}$) | Decisión | Racional |
|---|---|---|---|---|
| **Superioridad Dual** | Mejora estadísticamente significativa ($\Delta \text{MAE} < 0$, $p < 0.05$) | Reducción significativa ($\Delta \text{VR} < 0$, $\text{VR} \to 0$) | **Aprobado (Preferido)** | La restricción actúa como regularizador inductivo beneficioso. |
| **Factibilidad sin Costo** | Prácticamente equivalente ($|\Delta \text{MAE}| \le \delta_{\text{ROPE}}$) | Reducción significativa ($\Delta \text{VR} < 0$) | **Aprobado** | Se gana plausibilidad biológica sin perder precisión. |
| **Degradación Aceptable** | Ligero deterioro ($0 < \Delta \text{MAE} \le \delta_{\text{ROPE}}$, no significativo) | Eliminación total ($\text{VR} = 0$) | **Aprobado con reserva** | Prioriza validez mecanicista para simulación de escenarios. |
| **Costo Inadmisible** | Deterioro sustancial ($\Delta \text{MAE} > \delta_{\text{ROPE}}$, $p < 0.05$) | Reducción de violaciones | **Rechazado** | La formulación de la restricción distorsiona el aprendizaje empírico. |
| **Inoperante** | Sin cambio o deterioro | Sin reducción significativa en violaciones | **Rechazado** | El mecanismo de restricción no es efectivo. |

---

## 6. Reporte por día de muestreo y cautelas metodológicas

### 6.1 Reporte estratificado por día
El reporte de validación cruzada debe desglosar las métricas para cada día de muestreo:
- Días evaluados: día 7, día 21 y día 35 (los únicos de la cohorte de D1; corregido en #158,
  P-01).
- La columna `group` de `MetricRow` toma los valores `"all"`, `"7"`, `"21"` y `"35"`.

### 6.2 Cautelas metodológicas y notas científicas
> [!WARNING]
> **Confusión entre Dieta y Día de Muestreo (D-03):**
> En el diseño experimental de D1 HoloFood, el día de muestreo aporta **25 de los 47 puntos de
> $R^2$** del diseño en la log-razón $\ln(\text{propionato}/\text{acetato})$. Además, en el día 35
> la casi totalidad de los animales pertenecen al grupo Control. Por tanto, la maduración
> temporal del huésped domina la variabilidad de los AGCC.

> [!CAUTION]
> **Comparaciones entre tratamientos estrictamente exploratorias:**
> Debido al desbalance 34/15/7 de la cohorte oficial de 56 animales (consecuencia de la exclusión
> justificada de 3 animales en H-01/R-04), cualquier contraste de medias entre dietas (Control vs.
> Probiótico vs. Fitobiótico) debe catalogarse explícitamente como **exploratorio** en todos los
> reportes de F5.

### 6.3 Comparación obligatoria contra el baseline `day_only`
Para verificar si las restricciones o las GNN capturan biología real más allá de la curva de
edad:
- Todo reporte comparativo debe incluir `day_only` (modelo que asigna la media observada del día
  de muestreo en el conjunto de entrenamiento).
- Ningún modelo restringido o libre puede declararse con capacidad de aprendizaje biológico
  genuina si su desempeño no supera holgadamente a `day_only` en las métricas de composición fuera
  de corral.

---

## 7. Tratamiento de configuraciones no estimables y casos borde

Para asegurar que los scripts de evaluación operen sin interrupciones y sin introducir sesgos
artificiales por imputaciones inválidas, se aplican las siguientes reglas:

| Caso Borde / Configuración | Comportamiento en Validación | Manejo en Agregación (`aggregate_fold_reports`) |
|---|---|---|
| **Fold sin un día de muestreo** (ej. día 21 ausente en semillas 3, 7 y 8 por distribución de corrales en D-07) | La celda del día ausente en ese fold se evalúa como `NaN` (no estimable). No se genera predicción artificial. | Se omite de la media y desviación estándar de ese día. El conteo efectivo de folds se reporta en la fila `_n` (e.g. `n = 47` en lugar de 50). |
| **Animal con target no válido** (AGCC faltante, $\le 0$ o no finito) | Máscara booleana `valid = False`. Excluido de la pérdida de entrenamiento y del cálculo de métricas composicionales. | No afecta las métricas. Se reporta en los metadatos de ejecución el total de animales válidos ($N_{\text{valid}} = 56$). |
| **Divergencia numérica en modelo restringido** (gradientes explosivos o multiplicadores de Lagrange $\to \infty$) | El fold se registra como fallido (`status: "failed"`). Las predicciones de ese fold se marcan como no disponibles. | No se reemplaza por ceros ni por la media. Si la tasa de folds fallidos es $> 0\%$, el modelo reprueba el criterio de estabilidad. |
| **Varianza empírica nula en subconjunto** ($\sum (y_i - \bar{y})^2 = 0$) | Regla estándar de `nutrigraphdt.models.metrics.r2_score`: Si $SS_{\text{res}} = 0$, $R^2 = 1.0$; si $SS_{\text{res}} > 0$, $R^2 = 0.0$. | Se procesa matemáticamente sin arrojar excepción de división por cero. |

---

## 8. Formato de artefactos y reproducibilidad

Toda ejecución comparativa bajo este protocolo debe generar en su carpeta de salida
(`reports/constraints/<experimento>/`) los siguientes artefactos versionados:

1. `report.md`: Documento ejecutivo consolidado que incluye:
   - Declaración de conformidad con D-03, D-07 y estado de D-06.
   - Tablas comparativas globales y por día de muestreo (`_mean ± _std`).
   - Tabla de violaciones (VR, VMM, VWM, FR) para brazo libre vs. restringido.
   - Evaluación formal de los criterios de aceptación y decisión recomendada.
   - Advertencias metodológicas de confusión de dieta/día y desbalance 34/15/7.
2. `metrics.csv`: Métricas agregadas por modelo, grupo y métrica con sufijos `_mean`, `_std`,
   `_seed_std` y `_n`.
3. `violations.csv`: Resumen cuantitativo de violaciones por modelo, fold y restricción.
4. `fold_metrics.csv`: Desglose granular de métricas predictivas para cada uno de los 50 folds.
5. `run.json`: Metadatos de procedencia, incluyendo:
   - Commit SHA del repositorio.
   - Checksum SHA-256 de `configs/splits/d1_holofood_cv.json` y `configs/cohorts/d1_holofood.json`.
   - Versión del contrato de objetivo composicional (`COMPOSITIONAL_TARGET_VERSION`).
   - Entorno computacional, semillas empleadas y tiempo de ejecución.

---

## 9. Trazabilidad y referencias cruzadas

- **Issue de origen:** [#155](https://github.com/jvnioo/NutriGraphDT/issues/155) (A55-P1, F5).
- **Validación cruzada por corral:** [#139](https://github.com/jvnioo/NutriGraphDT/issues/139),
  documentada en [cross-validation.md](cross-validation.md).
- **Contrato composicional y métricas D-03:** [#146](https://github.com/jvnioo/NutriGraphDT/issues/146),
  documentada en [metrics.md](metrics.md).
- **Cohorte supervisada D1 (56 animales):** [#138](https://github.com/jvnioo/NutriGraphDT/issues/138).
- **Líneas base de referencia:** [baselines-d1-composition.md](baselines-d1-composition.md) ([#140](https://github.com/jvnioo/NutriGraphDT/issues/140))
  y [gnn-d1-composition.md](gnn-d1-composition.md) ([#142](https://github.com/jvnioo/NutriGraphDT/issues/142)).
- **Formalización D-06:** Actividad 78 de Investigación (pendiente antes del desarrollo de
  modelos en F5).
- **Referencias bibliográficas clave:**
  - Wolin, M. J. (1960). A theoretical rumen fermentation balance. *Journal of Dairy Science*, 43(10), 1452–1459.
  - Dietterich, T. G. (1998). Approximate statistical tests for comparing supervised classification learning algorithms. *Neural Computation*, 10(7), 1895–1923.
  - Nadeau, C., & Bengio, Y. (2003). Inference for the generalization error. *Machine Learning*, 52(3), 239–281.
  - Bouckaert, R. R., & Frank, E. (2004). Evaluating the replicability of significance tests for comparing learning algorithms. *Advances in Knowledge Discovery and Data Mining*, 3056, 3–12.
