# Respuesta de Investigación a la revisión A55

Nov 1, 2026

**PIA-2 · Microbioma Digital — Gemelo Digital Nutricional basado en GNN y PINNs.** Proyecto
NutriGraphDT · De: Célula de Investigación · Para: Célula de Desarrollo (sublíder Julio Provoste
Palacios) · Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II. Responde a la
revisión cruzada del protocolo y del contrato de explicaciones (A55-P4,
[#158](https://github.com/jvnioo/NutriGraphDT/issues/158)), registrada en
[`docs/models/explanations-protocol-review.md`](../models/explanations-protocol-review.md).

**Respuesta corta.** Investigación responde las 15 observaciones de la revisión y agrega una
nueva, C-09. Fija $\delta_\text{ROPE} = 0{,}5$ pp como valor provisional y reemplaza la matriz de
§5 del protocolo por una regla de decisión con intervalos y seis categorías ordenadas. La
estabilidad se exige solo sobre `_std`. En explicabilidad: una salida se explica solo si el modelo
supera a `dummy_mean` en esa salida (hoy z1 y z2, no ln T). Toda explicación de D1 lleva seis
advertencias obligatorias. Ninguna explicación se interpreta hasta que el explicador pase el
control con objetivos permutados de #168. P-07 se derivó a D-06, ya emitida (#218).

## 1. Propósito, alcance y fuentes revisadas

Este documento responde por identificador cada observación de la revisión A55 y deja registro de
la decisión, la respuesta, la fuente o justificación y el efecto esperado. Las respuestas a P-07 y
C-08 son las que emitió el sublíder de Investigación en el
[comentario del 29-10-2026](https://github.com/jvnioo/NutriGraphDT/pull/217#issuecomment-6508986333)
del PR #217, que reemplazan la asignación inicial a Maximiliano Campos y Felipe Cruz.

**Tabla 1.** Fuentes revisadas

| N° | Fuente | Versión | Uso en esta respuesta |
|---|---|---|---|
| 1 | `docs/models/explanations-protocol-review.md` | `main`, commit `0d1be4d` | Las 15 observaciones y el procedimiento de registro |
| 2 | `docs/models/constraints-evaluation-protocol.md` | `main`, commit `0d1be4d` | P-01 a P-07 |
| 3 | `docs/models/explanation-contract.md` (contrato 1.0.0) | `main`, commit `0d1be4d` | C-01 a C-05, C-07 a C-09 |
| 4 | `docs/models/explainers-poc.md` y `reports/explainability/explainers_poc.md` (#157) | `main`, commit `0d1be4d` | C-06 |
| 5 | `docs/models/explainability-pr-cross-review.md` (#216) | `main`, commit `0d1be4d` | L-1 (C-07), L-2 (C-04) y L-4 (C-09) |
| 6 | `reports/gnn/d1_composition/` (#142) y `reports/baselines/d1_composition/` (#140) | Corridas del 26-10-2026, anteriores a #176 | Todas las cifras nuevas |
| 7 | `reports/cv/d1_pen_folds.md` | `main` | Fitobiótico por fold (C-02) |
| 8 | `docs/research/D-06 — Restricciones bioquímicas para D1.md` | v1.0, 29-10-2026 | P-07 |
| 9 | Literatura con DOI (sección 6) | Consultada el 28-10 y el 01-11-2026 | Valores y métodos |

**Cómo se obtuvieron las cifras nuevas.** Las diferencias pareadas, los intervalos corregidos y
las pruebas se calcularon con `fold_metrics.csv` de los reportes #142 y #140: grupo `all`, los
mismos 50 folds para todos los modelos. El intervalo corregido usa la varianza de Nadeau y Bengio
con $n_\text{test}/n_\text{train} = 0{,}25$ y 49 grados de libertad, como §4.2 del protocolo.
Desarrollo y el sublíder de Investigación reprodujeron todas las cifras de forma independiente en
el PR #217. Donde una cifra de D1 se usa para fijar un valor, se declara.

**Corridas anteriores a #176.** Las GNN de los reportes #142 se entrenaron antes de que #176
codificara el tratamiento en el nodo `diet` (01-11-2026). Las reglas de esta respuesta valen igual
para corridas nuevas, pero las cifras de estado (P-06, C-04) se recalculan cuando se reentrenen.

**Notación.** $\Delta = \text{MAE}(M_C) - \text{MAE}(M_0)$ en la métrica primaria (P-04), y
$[L, U]$ es su IC 95 % bilateral corregido. Decidir con $U$ equivale a una prueba unilateral con
$\alpha = 0{,}025$.

## 2. Resumen de decisiones

**Tabla 2.** Decisiones por observación

| ID | Decisión | Respuesta en una línea | Fuente o justificación | Efecto esperado |
|---|---|---|---|---|
| P-01 | Aceptada | Los días de D1 son 7, 21 y 35. | Vocabulario de `sampling_day` y filas por día de los reportes. | Ninguno. |
| P-02 | **Cambiada** | $\delta_\text{ROPE} = 0{,}5$ pp, provisional, congelado en un commit con fecha antes de correr cualquier brazo restringido. | 0,1·DE de Kruschke (2018), trasladado (≈ 0,58 pp); resolución del diseño (0,30–0,44 pp); con 1,0 pp se aceptaría perder toda la ganancia sobre el trivial (0,74 pp). Relevancia biológica: limitación. | Protocolo §4.3. |
| P-03 | **Cambiada** | Estable si no hay folds fallidos y `_std` ≤ 1,25 × `_std` del brazo libre. `_seed_std` es descriptiva. | Bootstrap de semillas: `_seed_std` rechazaría por ruido un brazo igual de estable entre el 23 % y el 42 % de las veces. SIN FUENTE para 1,25. | Protocolo §5, paso 3. |
| P-04 | **Cambiada** | Primaria de F5: MAE macro de fracciones, `group = all`; el resto, descriptivo. F4 no se reabre. Con más de un brazo restringido, Holm sobre los p de no inferioridad (α = 0,025 por familia). | Alexander et al. (2015); Holm (1979); en D1, R² y MAE llevan a la misma conclusión. | Protocolo §2.2, §4.2 y §5. |
| P-05 | **Cambiada** | Decide el IC del $t$ corregido con seis categorías ordenadas (Tabla 3). Wilcoxon es sensibilidad anticonservadora. | Nadeau y Bengio (2003); Bouckaert y Frank (2004); Dietterich (1998). En D1, Wilcoxon da p = 0,010 donde el $t$ corregido da p = 0,50. | Protocolo §4.2 y matriz de §5 (Tabla 4). |
| P-06 | **Cambiada** | §6.3 exige «supera»: $U < 0$ frente a `day_only`. «Supera holgadamente» ($U < -\delta$) es informativo e inalcanzable en D1. | Semianchos de 0,39 a 0,43 pp frente a `day_only`. Hoy ningún modelo supera a `day_only`. | Protocolo §6.3; advertencia en C-02. |
| P-07 | Derivada | Derivada a D-06 (Actividad 78, Vicente Fuentes). Hasta D-06, solo restricciones estructurales; el paso 1 de §5 pasa a «¿Cumple la tolerancia de D-06?». D-06 v1.0 se emitió el 29-10-2026 (#218). | Comentario del sublíder (29-10-2026); `docs/models/constraints.md`. | Ya aplicado en #232. |
| C-01 | Aceptada, con condiciones | Signo solo si el explicador lo entrega; `max_abs` a `[-1, 1]`; top-k por valor absoluto; línea base de IntegratedGradients declarada. | Sundararajan et al. (2017). | Contrato §2.4 y §2.5. |
| C-02 | **Cambiada** | Se aceptan las dos advertencias propuestas y se agregan cuatro: grupo Fitobiótico insuficiente, modelo no mejor que `day_only`, taxones aislados (S-04) e inestabilidad del explicador. | D-03, L1–L3; reporte #142; C-07. | Contrato §2.6 y wrapper. |
| C-03 | Aceptada | Estilo distinto y leyenda «hipotética», sin ocultarlas. | Principio 1 del contrato. | Visualización de F7. |
| C-04 | **Cambiada** | Una salida se explica solo si el modelo supera a `dummy_mean` en la métrica de esa salida. Hoy: z1 y z2 sí, ln T no. Las concentraciones no se explican en F7. | Prueba unilateral corregida (Tabla 6). Las atribuciones no se suman para dar la de $c_k$ (Aitchison, 1982; Sundararajan et al., 2017). | Contrato §2.3. Nombres de salida: resuelto en #222. |
| C-05 | Aceptada, con condiciones | Modelo del fold en que el animal estuvo en test, en las 10 semillas; nunca uno que lo vio en train; dos estabilidades separadas. | Protocolo §1.3 (sin fuga). | Wrapper; agregación en el contrato 1.1.0. |
| C-06 | Aceptada, con condiciones | Aristas con GNNExplainer sobre `hetero_sage` (principal) o `hetero_gat`; `homo_sage`, solo nodos y atributos; la atención no es explicación. En D1 las aristas no son informativas hasta S-04: solo atributos. | PoC #157; Jain y Wallace (2019); reporte #142. | Reporte de F7. |
| C-07 | **Cambiada** | Φ̂ de Nogueira et al. (2018) con ≥ 5 semillas del explicador; < 0,40 en la estimación puntual: `explainer_instability`; siempre con IC. Ninguna explicación se interpreta antes de pasar el control de #168. | Nogueira et al. (2018); Fleiss et al. (2003); L-1 de #216. Umbral provisional. | Contrato §2.6 y wrapper. |
| C-08 | Aceptada | El vocabulario de `evidence_method` del contrato es el de EDG-04 más `synthetic_generator`. | Comentario del sublíder (29-10-2026), verificado en el código. | Ya aplicado en #232 (prueba nueva). |
| C-09 | **Nueva** | En los reportes, la importancia de cada `rev_*` se suma a la de su arista directa y el top-k se elige solo entre aristas directas. | Las inversas no existen en los registros ni tienen evidencia (contrato §2.4). | Contrato §2.5 (versión mayor) y registro. |

Los efectos de código que antes apuntaban a #170 (cerrada, PR #211) van a Issues nuevas de
Desarrollo, que citan el identificador de la observación.

## 3. Protocolo de evaluación (A55-P1)

### P-01 · Días de muestreo

- **Decisión:** Aceptada.
- **Respuesta:** la cohorte de 56 animales solo tiene muestreos en los días 7, 21 y 35; la
  corrección de §2.2 y §6.1 es correcta.
- **Justificación:** coincide con el vocabulario de `sampling_day` en
  `src/nutrigraphdt/data/covariates.py` y con las filas por día de los reportes de baselines y GNN.
- **Efecto:** ninguno.

### P-02 · Valor de $\delta_\text{ROPE}$

- **Decisión:** Cambiada.
- **Respuesta:** $\delta_\text{ROPE} = 0{,}5$ pp en el MAE macro de fracciones (`group = all`),
  provisional. Se congela en un commit con fecha (el cambio de §4.3 del protocolo) **antes de
  correr cualquier brazo restringido**. #213 (pérdida $L_\text{datos} + \lambda L_\text{bio}$) ya
  está en `main`, así que el cambio es urgente; en `main` todavía no hay resultados en
  `reports/constraints/`. La decisión se toma con la regla de P-05.
- **Justificación.**

  **Tabla 5.** Enfoques para fijar δ

  | Enfoque | Resultado | Estado |
  |---|---|---|
  | (a) Literatura de predicción de composición de AGCC o de datos composicionales | No se encontró un margen publicado para el MAE de proporciones molares de AGCC. | SIN FUENTE |
  | (b) 0,1 desviación estándar de la respuesta, el ROPE por omisión de Kruschke (2018) | DE de las fracciones aproximada con el MAE de `dummy_mean` (4,63 pp): bajo normalidad, 4,63·√(π/2) ≈ 5,8 pp; 0,1·DE ≈ **0,58 pp**. | **Traslado:** Kruschke lo define para un parámetro en la escala de la respuesta, no para una diferencia de MAE entre modelos. Depende de D1. |
  | (c) Relevancia biológica | No se encontró un umbral de consenso para la diferencia de proporción molar que importa en nutrición avícola. | **Limitación declarada** |
  | (d) Resolución del diseño | Semiancho del IC corregido: ≈ 0,30 pp entre modelos parecidos (`hetero_sage` − `homo_sage`) y ≈ 0,44 pp entre modelos distintos (`homo_sage` − `dummy_mean`). Con un δ menor, la no inferioridad sería indemostrable aunque Δ = 0. | Calculado en D1 |
  | (e) Que no sea laxo | La mejor GNN supera a `dummy_mean` por 0,74 pp. Con 1,0 pp, un brazo restringido podría perder toda esa ganancia y pasar el paso 2. | Calculado en D1 |

  0,5 pp queda entre (d) y (b) y por debajo de (e).
- **Dependencia declarada:** (b), (d) y (e) usan resultados de D1. Para evitar circularidad, δ se
  fija antes de ver cualquier resultado de $M_C$ y no se cambia después. Si cambian la cohorte o
  la métrica primaria, se revisa.
- **Fuentes:** Kruschke (2018); Walker y Nowacki (2011).
- **Efecto:** en §4.3 del protocolo, 0,5 pp como «provisional de Investigación (P-02), dependiente
  de D1», con la relevancia biológica como limitación.

### P-03 · Umbral de estabilidad

- **Decisión:** Cambiada.
- **Respuesta:** el brazo restringido es estable si:
  1. no tiene folds fallidos (§7 del protocolo);
  2. su `_std` en la métrica primaria es ≤ 1,25 × la `_std` del brazo libre.

  `_seed_std` se informa como descriptiva, sin umbral.
- **Justificación.** «No mayor que», sin tolerancia, rechazaría por ruido. En D1, la `_std` de las
  tres variantes GNN, equivalentes en exactitud, va de 0,660 a 0,682. `_seed_std` se estima con
  solo 10 medias y es demasiado ruidosa para un umbral. El sublíder de Investigación lo mostró con
  un bootstrap pareado de las 10 semillas del plan (4000 remuestreos, los 5 folds de cada semilla
  juntos), reproducido para esta respuesta:

  | Par | P(razón `_seed_std` > 1,25) | IC 90 % | P(razón `_std` > 1,25) | IC 90 % |
  |---|---|---|---|---|
  | `hetero_sage` / `homo_sage` | 0,23 | [0,59; 1,58] | 0,00 | [0,90; 1,11] |
  | `hetero_gat` / `homo_sage` | 0,40 | [0,82; 2,09] | 0,01 | [0,93; 1,17] |
  | `hetero_gat` / `hetero_sage` | 0,42 | [0,81; 1,94] | 0,00 | [0,94; 1,16] |

  Con 1,25 sobre `_std`, un brazo igual de estable casi nunca se rechaza por ruido.
- **Fuente:** SIN FUENTE para 1,25 — propuesta provisional, calibrada con D1.
- **Efecto:** paso 3 de §5 del protocolo.

### P-04 · Métrica primaria y comparaciones múltiples

- **Decisión:** Cambiada.
- **Respuesta:**
  1. La métrica primaria de F5 es el **MAE macro de fracciones, `group = all`**, y es la única
     que entra a la decisión de §5. R², ln T, concentraciones y métricas por día o por
     restricción son descriptivas, sin pruebas de significancia.
  2. **Conciliación con F4.** El criterio de F4 (R² macro de fracciones) no se reabre. En D1, las
     dos métricas llevan a la misma conclusión:

     | Comparación | Δ R² macro [IC 95 % corregido] | Δ MAE macro, pp [IC 95 % corregido] | Conclusión |
     |---|---|---|---|
     | `homo_sage` − `random_forest` | −0,08 [−0,27; 0,11] | +0,09 [−0,32; 0,50] | No concluyente con ambas |
     | `homo_sage` − `day_only` | +0,03 [−0,13; 0,19] | −0,14 [−0,54; 0,27] | No concluyente con ambas |
     | `homo_sage` − `dummy_mean` | +0,31 [0,09; 0,52] | −0,74 [−1,18; −0,30] | La GNN es mejor con ambas |

  3. Se usa el MAE en F5 porque está en pp, la unidad de δ. El R² fuera de muestra depende de la
     varianza de cada fold de test, que con 10 a 12 animales es inestable (por día llega a −516).
     Alexander et al. (2015) recomiendan informar errores en la unidad de la respuesta.
  4. **Multiplicidad.** Si entra más de un brazo restringido frente al mismo $M_0$, se aplica
     Holm (1979) a los p de no inferioridad ($H_0$: Δ ≥ δ, $t$ corregido unilateral), con
     $\alpha = 0{,}025$ por familia. En ese caso, la no inferioridad se decide con el p ajustado y
     el IC se informa sin ajustar.
- **Efecto:** protocolo §2.2 (métrica primaria), §4.2 (Holm) y §5 (nota de conciliación con F4).

### P-05 · Regla de decisión estadística

- **Decisión:** Cambiada.
- **Respuesta:**
  1. Decide el IC 95 % bilateral corregido de Δ sobre los 50 folds. Se asigna la **primera**
     categoría de la Tabla 3 que se cumple.

     **Tabla 3.** Categorías ordenadas para el paso 2 de §5

     | Orden | Categoría | Regla | Paso 2 de §5 |
     |---|---|---|---|
     | 1 | Superior en la práctica | $U < -\delta$ | pasa |
     | 2 | Superior | $U < 0$ | pasa |
     | 3 | Equivalente | $L > -\delta$ y $U < \delta$ | pasa |
     | 4 | No inferior | $U < \delta$ | pasa |
     | 5 | No concluyente | $L < \delta \le U$ | rechazo |
     | 6 | Inferior en la práctica | $L \ge \delta$ | rechazo |

  2. Wilcoxon sobre las 10 medias por semilla se informa como sensibilidad, rotulado
     **anticonservador**, y nunca revierte la decisión.
  3. $n_\text{train}$ se cuenta como train + val interno, porque el procedimiento usa ambos. La
     razón observada en `folds.csv` es 0,25 en promedio (0,22 a 0,27), así que el 0,25 del
     protocolo se confirma. La razón usada se registra en `run.json`.
- **Matriz de §5.** La Tabla 4 reemplaza la matriz actual. La columna de violaciones sigue el
  paso 1 redactado en P-07.

  **Tabla 4.** Matriz de clasificación con las categorías de la Tabla 3

  | Clasificación | Paso 1 (tolerancia de D-06) | Paso 2 (categoría de Δ) | Decisión |
  |---|---|---|---|
  | Superioridad dual | Cumple | 1 o 2 | Aprobado (preferido) |
  | Factibilidad sin costo | Cumple | 3 con $L \le 0$, o 4 | Aprobado |
  | Degradación aceptable | Cumple | 3 con $L > 0$: equivalente, pero significativamente peor | Aprobado con reserva |
  | Costo inadmisible | Cumple | 5 o 6 | Rechazado |
  | Inoperante | No cumple | Cualquiera | Rechazado |

  En la categoría 4, $L \le -\delta$ (si no, sería 3), así que no puede ser significativamente
  peor. Si la cota de D-06 no se activa en D1 (D-06 §6), el paso 1 se cumple en ambos brazos y la decisión
  depende del paso 2 y de la estabilidad.
- **Justificación.** Las 10 medias por semilla no son independientes: todas reparten los mismos
  56 animales. Con n = 10, Wilcoxon da p ≈ 0,002 siempre que las 10 diferencias tengan el mismo
  signo, sin importar su tamaño. En D1 discrepa del $t$ corregido:

  | Comparación (MAE macro) | $t$ corregido, p | Wilcoxon (10 medias), p |
  |---|---|---|
  | `homo_sage` − `day_only` | 0,50 | 0,010 |
  | `random_forest` − `day_only` | 0,09 | 0,002 |
  | `homo_sage` − `random_forest` | 0,65 | 0,049 |

  Un $t$ pareado que ignora el solapamiento de los entrenamientos infla el error tipo I
  (Dietterich, 1998). El $t$ corregido lo incorpora (Nadeau y Bengio, 2003) y es el recomendado
  por replicabilidad (Bouckaert y Frank, 2004). Su versión bayesiana usa la misma heurística de
  correlación (Corani y Benavoli, 2015).
- **Efecto:** protocolo §4.2 (jerarquía de pruebas y rótulo de Wilcoxon) y §5 (Tablas 3 y 4).

### P-06 · «Supera holgadamente a `day_only`»

- **Decisión:** Cambiada.
- **Respuesta:** con $\Delta = \text{MAE}(M) - \text{MAE}(\texttt{day\_only})$:
  - §6.3 exige el nivel **«supera»**: $U < 0$;
  - **«supera holgadamente»** ($U < -\delta$) se informa como dato y se declara inalcanzable en D1.
  - La advertencia `model_not_better_than_day_only` (C-02) se retira cuando el modelo alcanza
    «supera».
- **Justificación:** los semianchos de las GNN frente a `day_only` van de 0,39 a 0,43 pp. Para
  $U < -0{,}5$ haría falta un $\hat\Delta$ cercano a −0,9 pp, y la mayor diferencia observada es
  −0,23 pp (`random_forest`). Estado actual: ningún modelo supera a `day_only` (`homo_sage`:
  −0,14 [−0,54; 0,27]; `random_forest`: −0,23 [−0,50; 0,04]).
- **Efecto:** protocolo §6.3.

### P-07 · Restricciones bioquímicas pendientes de D-06

Respuesta emitida por el sublíder de Investigación, incorporada sin cambios.

- **Decisión:** Derivada a D-06 (Actividad 78). Responsable: Vicente Fuentes Rodríguez, sublíder
  de Investigación. Fecha estimada: 06-11-2026.
- **Respuesta:**
  1. Hasta que se entregue D-06, F5 evalúa solo las restricciones estructurales: no negatividad de
     fracciones y concentraciones, y cierre simplex. Se acepta como limitación declarada.
  2. Las GNN composicionales cumplen esas restricciones por construcción. La inversa
     `softmax · exp(ln T)` da fracciones positivas que suman 1 y concentraciones positivas, así
     que el VR es 0 en ambos brazos y el paso 1 de §5 no los discrimina hasta D-06. Solo los
     modelos que predicen directamente en ℝ³ (baselines directos) pueden violarlas.
  3. El paso 1 de §5 se redacta como «¿Cumple la tolerancia de D-06?» y no como «¿Reduce VR y VMM
     significativamente hacia 0?».
  4. D-06 revisará si el balance de fermentación de Wolin (1960), formulado para rumiantes, aplica
     al ciego de aves.
- **Justificación:**
  - Con la redacción actual, si un brazo restringido y uno libre ya tienen VR = 0, ninguno puede
    «reducir» violaciones. El paso 1 los rechazaría como «inoperantes» aunque los dos sean
    factibles. Para decidir importa que las predicciones queden dentro de la tolerancia, no la
    diferencia de VR entre brazos.
  - `docs/models/constraints.md` (A57-P1) ya declara que, en las salidas composicionales, la no
    negatividad es una garantía matemática y que un VR de cero no constituye evidencia de mejora
    del modelo. La tolerancia de cierre (`STRUCTURAL_CLOSURE_TOLERANCE = 1e-6`) es numérica, no
    fisiológica.
  - Wolin (1960) es *A theoretical rumen fermentation balance*. El protocolo (§3.1) lo usa como
    balance en fracciones, pero el proyecto no ha comprobado que valga en el ciego de pollo. Esa
    verificación corresponde a D-06.
- **Efecto:**
  - Protocolo §3.2 y §5: declarar la limitación y reescribir el paso 1. Al reescribir la matriz de
    §5 (P-02 y P-05), la columna «Violaciones» de las filas «Superioridad dual», «Factibilidad sin
    costo» e «Inoperante» se adapta al mismo criterio.
  - Los reportes de F5 siguen informando VR, VMM, VWM y FR (§8), con la nota de que en los modelos
    composicionales valen 0 por construcción.
  - En el registro, Desarrollo enlaza esta respuesta y la tarea de D-06.

> **Actualización (01-11-2026).** D-06 v1.0 se emitió el 29-10-2026, antes de la fecha estimada
> (PR #218), y se implementó en #219. Su §4 responde el punto 4: el balance de Wolin no se aplica a
> D1 como igualdad. Los efectos en el protocolo se aplicaron en #232; la matriz adaptada es la
> Tabla 4.

## 4. Contrato de explicaciones (A55-P3) y prueba de concepto (A55-P2)

### C-01 · Importancia con signo

- **Decisión:** Aceptada, con condiciones.
- **Respuesta:**
  1. `[-1, 1]` solo para explicadores que entregan signo (por ejemplo IntegratedGradients),
     declarado en `scale` con `normalization = max_abs`. Por omisión, `[0, 1]`.
  2. Con escala con signo, el top-k se elige por **valor absoluto**; si no, se pierden las
     contribuciones negativas.
  3. La línea base de IntegratedGradients se declara en `explainer.config`, porque la atribución
     depende de ella (Sundararajan et al., 2017).
  4. Un signo positivo en `log_propionate_acetate` significa que el elemento aumenta la razón
     propionato/acetato en el modelo, no el propionato.
  5. No se comparan rankings con signo y sin signo.
- **Efecto:** contrato §2.5. Según §5 del contrato, cambiar la regla de selección sube la versión
  mayor; Desarrollo puede evitarlo con una regla nueva (`top_k_edges_by_abs_importance`).

### C-02 · Advertencias obligatorias para D1

- **Decisión:** Cambiada (acepta las dos propuestas y agrega cuatro).
- **Respuesta:**

  | `code` | Cuándo | Contenido del mensaje |
  |---|---|---|
  | `diet_day_confounding` | Siempre en D1 | La dieta está confundida con el día de muestreo: el día 35 es casi solo Control (D-03). |
  | `exploratory_treatment_contrast` | Siempre en D1 | Desbalance 34/15/7: toda comparación entre dietas es exploratoria (L1). |
  | `insufficient_group_size` | Si el animal explicado es Fitobiótico (`CE`) | Fitobiótico tiene 7 animales en 6 corrales, 1 o 2 por fold de test. Su explicación no permite conclusiones específicas de esa dieta, ni siquiera exploratorias. |
  | `model_not_better_than_day_only` | Siempre en D1 hasta que el modelo alcance «supera» (P-06) | El modelo no supera a `day_only` fuera de corral: en exactitud, no se distingue de la media por día. |
  | `isolated_taxa_pending_s04` | Siempre en D1 mientras S-04 esté abierta | Los taxones no tienen aristas a funciones ni metabolitos y no reciben mensajes; su importancia entra solo por la lectura del grafo (L2/L3). |
  | `explainer_instability` | Si Φ̂ < 0,40 (C-07) | El top-k cambia entre semillas del explicador; no interpretar elementos individuales. |

- **Importancia del nodo `diet`.** En las corridas de D1 anteriores a #176 (las de los reportes
  #142), el nodo `diet` tiene `x` de forma `[N, 0]` y no tiene aristas, y las covariables del
  huésped no incluyen el tratamiento. Su embedding es igual en todos los animales, así que
  cualquier importancia que reciba es un artefacto y **no se informa**. #176 (PR #224, fusionado el
  01-11-2026) codifica el tratamiento en el nodo `diet` con tres columnas one-hot, sin aristas. En
  modelos entrenados con esa codificación, la importancia del nodo `diet` o de esas columnas se
  informa siempre con `insufficient_group_size` y `exploratory_treatment_contrast`.
- **Justificación:** con 1 o 2 animales Fitobiótico por fold de test (`reports/cv/d1_pen_folds.md`),
  «exploratoria» no alcanza. `model_not_better_than_day_only` sale de P-06 e
  `isolated_taxa_pending_s04`, de la limitación del reporte #142.
- **Efecto:** contrato §2.6 y wrapper, en una Issue nueva de Desarrollo que cite C-02.

### C-03 · Aristas `hypothetical` en la visualización

- **Decisión:** Aceptada.
- **Respuesta:** estilo distinto (por ejemplo, línea discontinua) y leyenda «hipotética: sin
  respaldo empírico», sin ocultarlas ni sacarlas del top-k. Una importancia alta no la convierte
  en evidencia (principio 1 del contrato). Se sugiere una codificación visual propia para cada uno
  de los cinco estados de DS-01.
- **Efecto:** visualización de F7.

### C-04 · Qué salidas se explican

- **Decisión:** Cambiada.
- **Respuesta:**
  1. **Criterio general:** una salida se explica solo si el modelo supera a `dummy_mean` en la
     métrica de esa salida: `fraction_mae_pp` macro para z1 y z2, y `log_total_mae` para ln T.
     La prueba es el $t$ corregido unilateral: $U < 0$ en el IC 95 % bilateral corregido
     ($\alpha = 0{,}025$).

     **Tabla 6.** Estado actual en D1 (`group = all`, 50 folds)

     | Modelo − `dummy_mean` | `fraction_mae_pp` (pp) | `log_total_mae` (ln mmol/kg) |
     |---|---|---|
     | `homo_sage` | −0,74 [−1,18; −0,30] | +0,013 [−0,035; +0,060] |
     | `hetero_sage` | −0,69 [−1,13; −0,25] | +0,017 [−0,026; +0,060] |
     | `hetero_gat` | −0,69 [−1,21; −0,16] | +0,013 [−0,034; +0,060] |

     Hoy se explican z1 y z2, y ln T no.
  2. Las concentraciones reconstruidas no se explican en F7.
  3. z1 y z2 son razones respecto del acetato: la importancia para z1 no es «importancia para el
     propionato», y el acetato no tiene salida propia.
- **Por qué una concentración no se descompone.** Con $\boldsymbol\ell = (0, z_1, z_2)$,
  $\ln c_k = \ln T + \ell_k - \log\sum_j e^{\ell_j}$. El término log-suma-exp acopla z1 y z2 de
  forma no lineal (Aitchison, 1982). IntegratedGradients cumple el axioma de linealidad
  (Sundararajan et al., 2017), que vale solo para combinaciones lineales de salidas. GNNExplainer
  no cumple linealidad: optimiza una máscara por salida. En ninguno de los dos casos se pueden
  sumar las atribuciones de z1, z2 y ln T para obtener la de $c_k$. Para explicar una
  concentración habría que explicar directamente la función compuesta $c_k(\cdot)$; queda para una
  versión posterior.
- **Efecto:** contrato §2.3: en modelos composicionales de D1, `output` se limita a las salidas
  que cumplan el criterio. El nombre de las salidas en el explicador (L-2 de #216) ya está
  resuelto en #222.

### C-05 · Cuál de los 50 modelos explica a cada animal

- **Decisión:** Aceptada, con condiciones.
- **Respuesta:**
  1. Cada animal se explica con el modelo del fold en que estuvo en **test**, en cada una de las
     10 semillas.
  2. Nunca con un modelo que lo tuvo en train: se estaría explicando memorización.
  3. El escalado de atributos es el del fold de ese modelo (protocolo §1.3).
  4. Se informan dos estabilidades separadas: entre las 10 semillas del plan (cambian partición y
     entrenamiento, porque la semilla de entrenamiento se deriva de la del fold) y entre semillas
     del explicador con el modelo fijo (C-07).
  5. Un fold fallido no se reemplaza; se informa cuántas explicaciones tiene cada animal.
  6. La agregación entre modelos queda para el contrato `1.1.0`.
- **Implementabilidad:** 56 animales × 10 semillas × 2 salidas × ≥ 5 semillas del explicador
  son ≥ 5600 ejecuciones de GNNExplainer. Desarrollo estima el costo en CPU antes de fijar épocas.
- **Efecto:** selección del modelo fuera de fold en el wrapper, en una Issue nueva que cite C-05.

### C-06 · Explicadores por variante

- **Decisión:** Aceptada, con condiciones.
- **Respuesta:**
  - Aristas con GNNExplainer sobre **`hetero_sage`** (principal) o `hetero_gat`.
  - `homo_sage`, solo nodos y atributos.
  - La atención no se usa como explicación.
  - **En D1, las explicaciones de aristas no son informativas hasta que se cierre S-04.** La única
    relación es `metabolite → measured_in → host` y los 1315 taxones están aislados (reporte
    #142). Mientras tanto, en D1 solo se informa la importancia de atributos. `hetero_sage` sigue
    como variante principal para cuando haya aristas.
- **Justificación:** en `homo_sage` las máscaras de aristas no llegan a ninguna capa (PoC #157).
  Elegir `hetero_sage` no tiene costo medible: frente a `homo_sage`, Δ = +0,05 pp
  [−0,25; 0,35], equivalente con δ = 0,5 pp. Los pesos de atención suelen no coincidir con la
  importancia por gradiente (Jain y Wallace, 2019).
- **Efecto:** reporte de F7.

### C-07 · Estabilidad entre semillas del explicador

- **Decisión:** Cambiada (Investigación fija el umbral).
- **Respuesta:**
  1. **Requisito previo:** ninguna explicación se interpreta hasta que el explicador supere el
     control con objetivos permutados de #168. Según L-1 de
     `docs/models/explainability-pr-cross-review.md` (#216), GNNExplainer con su configuración por
     omisión dio la misma diferencia de importancia entre la ruta plantada y los distractores con
     el modelo entrenado que con uno entrenado sobre objetivos permutados.
  2. Por cada instancia, salida y modelo, el explicador corre con **al menos 5 semillas**, y la
     estabilidad del top-k se mide con el estimador **Φ̂ de Nogueira et al. (2018)**.
  3. El umbral se aplica a la **estimación puntual**, y siempre se informa el IC:
     - Φ̂ < 0,40: estabilidad pobre. Se agrega `explainer_instability` y no se interpretan los
       elementos individuales del top-k.
     - 0,40 ≤ Φ̂ < 0,75: intermedia a buena; se interpreta con cautela.
     - Φ̂ ≥ 0,75: excelente.
  4. La correlación de Kendall de los rangos se informa como complemento, sin umbral.
  5. **La estabilidad no prueba fidelidad:** un explicador puede ser estable y aun así no depender
     del modelo. Por eso el requisito 1 va primero.
- **Justificación.** Elegir el top-k en cada semilla es seleccionar k elementos de d en M
  repeticiones, el caso de Nogueira et al. (2018). Su estimador está corregido por azar (vale 0
  para una selección aleatoria), con k fijo coincide con el índice de Kuncheva y con dos
  categorías equivale al kappa de Fleiss. Los autores proponen la escala de Fleiss et al. (2003):
  pobre bajo 0,40, intermedia a buena entre 0,40 y 0,75, excelente sobre 0,75. La variabilidad
  entre ejecuciones de GNNExplainer está documentada (Zhao et al., 2023; Cvetković y Mitrović
  Dankulov, 2026), pero no se encontró un umbral de consenso para explicaciones de GNN (Agarwal et
  al., 2023, tampoco fija uno). **El 0,40 es un traslado desde la selección de atributos y es
  provisional.**
- **Efecto:** contrato §2.6 (las dos condiciones y la fila `explainer_instability`) y wrapper, en
  una Issue nueva que cite C-07.

### C-08 · Vocabulario de métodos de evidencia

Respuesta emitida por el sublíder de Investigación, incorporada sin cambios.

- **Decisión:** Aceptada.
- **Respuesta:** el vocabulario de `evidence_method` del contrato es el de EDG-04 (reglas 1.3.0)
  más `synthetic_generator`. Si EDG-04 cambia, el contrato se actualiza en la misma versión de las
  reglas.
- **Justificación:** comprobado en `main` (`fc8b43f`):
  - **EDG-04.** `EVIDENCE_METHOD_STATUS` en `src/nutrigraphdt/graph/validation/edges.py:120-131`
    tiene seis métodos:
    - `measurement` → `observed`;
    - `database_annotation` y `literature_curation` → `annotated`;
    - `model_prediction` y `statistical_association` → `inferred`;
    - `expert_hypothesis` → `hypothetical`.

    Coincide con la tabla «Vocabulario cerrado de `evidence_method`» de
    `docs/graph/graph-integrity-rules.md` (líneas 238–248).
  - **Contrato.** `EVIDENCE_METHOD_STATUS` en `src/nutrigraphdt/explainability/contract.py:36-46`
    tiene los mismos seis métodos con el mismo estado, más `synthetic_generator` → `synthetic`.
    EXP-06 lo aplica en `contract.py:310-327`.
  - **`synthetic_generator`.** Es el método por omisión del generador sintético
    (`src/nutrigraphdt/data/synthetic/edges.py:216`). También es el que el constructor asigna a
    una fila `synthetic` que no declara método (`src/nutrigraphdt/graph/builder.py:69-77`).
  - **Versión de las reglas.** Las vigentes son las 1.4.0 (`RULES_VERSION` en
    `src/nutrigraphdt/graph/validation/report.py:26`). La 1.4.0 solo agrega INS-08 y no cambia
    EDG-04, así que el vocabulario sigue siendo el de 1.3.0.
- **Efecto:** ninguno en el contrato. Las dos tablas están copiadas por separado en el código y
  ninguna prueba las compara: `EVIDENCE_METHOD_STATUS` no aparece en `tests/`. Para que el
  compromiso no dependa de la memoria, Desarrollo agrega una prueba que exija que el vocabulario
  del contrato sea el de EDG-04 más `synthetic_generator`.

> **Actualización (01-11-2026).** La prueba se agregó en #232
> (`test_contract_evidence_vocabulary_is_edg04_plus_synthetic_generator`).

### C-09 · Relaciones inversas en el top-k (observación nueva)

- **Origen:** L-4 de `docs/models/explainability-pr-cross-review.md` (#216), que deriva la
  pregunta a #158. Se pide a Desarrollo agregarla al registro como C-09.
- **Decisión:** propuesta de Investigación.
- **Respuesta:** en los reportes, la importancia de cada relación `rev_*` se suma a la de su
  arista directa, y el top-k se elige solo entre aristas directas.
- **Justificación:** las inversas las agrega la conversión a `HeteroData` para el paso de
  mensajes; no existen en los registros ni tienen evidencia (contrato §2.4: `evidence = null`).
  Dejarlas competir en el top-k desplaza aristas con evidencia por aristas que el grafo no declara.
- **Efecto:** Desarrollo decide la versión del contrato (cambia la regla de `selection`; por su
  §5, versión mayor) y cómo se normaliza la suma para que una escala `normalized` siga dentro de
  su rango, declarándolo en `scale.aggregation`.

## 5. Trabajo derivado y coordinación

- **Derivada:** solo P-07, a D-06, ya emitida (#218).
- **Cambios para Desarrollo**, en Issues nuevas que citen el identificador: advertencias de D1
  (C-02), Φ̂ y requisito de #168 (C-07), selección fuera de fold (C-05), top-k con signo (C-01) y
  `rev_*` (C-09). El cambio de C-04 en el código ya está resuelto (#222).
- **Protocolo:** §4.3 (δ, P-02), §2.2, §4.2 y §5 (P-03 a P-05, Tablas 3 y 4) y §6.3 (P-06). El
  cambio de §4.3 va primero y antes de cualquier corrida de brazos restringidos.
- **Reentrenamiento tras #176:** cuando se reentrenen las GNN de D1 con el tratamiento codificado,
  se recalculan el estado de P-06 y la Tabla 6, y se aplica la regla de C-02 sobre el nodo `diet`.

## 6. Referencias

| Referencia | DOI o enlace |
|---|---|
| Agarwal, C., Queen, O., Lakkaraju, H. y Zitnik, M. (2023). Evaluating explainability for graph neural networks. *Scientific Data*, 10. | [10.1038/s41597-023-01974-x](https://doi.org/10.1038/s41597-023-01974-x) |
| Aitchison, J. (1982). The statistical analysis of compositional data. *Journal of the Royal Statistical Society B*, 44(2), 139–177. | [10.1111/j.2517-6161.1982.tb01195.x](https://doi.org/10.1111/j.2517-6161.1982.tb01195.x) |
| Alexander, D. L. J., Tropsha, A. y Winkler, D. A. (2015). Beware of R²: simple, unambiguous assessment of the prediction accuracy of QSAR and QSPR models. *J. Chem. Inf. Model.*, 55(7), 1316–1322. | [10.1021/acs.jcim.5b00206](https://doi.org/10.1021/acs.jcim.5b00206) |
| Bouckaert, R. R. y Frank, E. (2004). Evaluating the replicability of significance tests for comparing learning algorithms. *PAKDD 2004*, LNCS 3056, 3–12. | [10.1007/978-3-540-24775-3_3](https://doi.org/10.1007/978-3-540-24775-3_3) |
| Corani, G. y Benavoli, A. (2015). A Bayesian approach for comparing cross-validated algorithms on multiple data sets. *Machine Learning*, 100, 285–304. | [10.1007/s10994-015-5486-z](https://doi.org/10.1007/s10994-015-5486-z) |
| Cvetković, D. y Mitrović Dankulov, M. (2026). Assessing the explainability of graph neural networks in random graphs classification task. *Journal of Complex Networks*, 14(2), cnag006. | [10.1093/comnet/cnag006](https://doi.org/10.1093/comnet/cnag006) |
| Dietterich, T. G. (1998). Approximate statistical tests for comparing supervised classification learning algorithms. *Neural Computation*, 10(7), 1895–1923. | [10.1162/089976698300017197](https://doi.org/10.1162/089976698300017197) |
| Fleiss, J. L., Levin, B. y Paik, M. C. (2003). *Statistical Methods for Rates and Proportions* (3.ª ed.). Wiley. | ISBN 978-0-471-52629-2 |
| Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2), 65–70. | [JSTOR 4615733](https://www.jstor.org/stable/4615733) |
| Jain, S. y Wallace, B. C. (2019). Attention is not explanation. *NAACL-HLT 2019*, 3543–3556. | [10.18653/v1/N19-1357](https://doi.org/10.18653/v1/N19-1357) |
| Kruschke, J. K. (2018). Rejecting or accepting parameter values in Bayesian estimation. *Advances in Methods and Practices in Psychological Science*, 1(2), 270–280. | [10.1177/2515245918771304](https://doi.org/10.1177/2515245918771304) |
| Nadeau, C. y Bengio, Y. (2003). Inference for the generalization error. *Machine Learning*, 52(3), 239–281. | [10.1023/A:1024068626366](https://doi.org/10.1023/A:1024068626366) |
| Nogueira, S., Sechidis, K. y Brown, G. (2018). On the stability of feature selection algorithms. *JMLR*, 18(174), 1–54. | [jmlr.org/papers/v18/17-514](https://jmlr.org/papers/v18/17-514.html) |
| Sundararajan, M., Taly, A. y Yan, Q. (2017). Axiomatic attribution for deep networks. *ICML 2017*, PMLR 70, 3319–3328. | [arXiv:1703.01365](https://arxiv.org/abs/1703.01365) |
| Walker, E. y Nowacki, A. S. (2011). Understanding equivalence and noninferiority testing. *J. Gen. Intern. Med.*, 26(2), 192–196. | [10.1007/s11606-010-1513-8](https://doi.org/10.1007/s11606-010-1513-8) |
| Wolin, M. J. (1960). A theoretical rumen fermentation balance. *Journal of Dairy Science*, 43(10), 1452–1459. | [10.3168/jds.S0022-0302(60)90348-9](https://doi.org/10.3168/jds.S0022-0302(60)90348-9) (original no verificado; cita confirmada en D-06) |
| Zhao, T., Luo, D., Zhang, X. y Wang, S. (2023). Faithful and consistent graph neural network explanations with rationale alignment. *ACM Transactions on Intelligent Systems and Technology*, 14(5), artículo 92, 1–23. | [10.1145/3616542](https://doi.org/10.1145/3616542) |

## Emisión y control de versiones

Yo, **Vicente Fuentes Rodríguez**, sublíder del Área de Investigación del proyecto Microbioma
Digital, confirmo la emisión de este documento a la Célula de Desarrollo.

**Tabla 7.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | Respuesta de Investigación a la revisión A55 |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Redacción | Benjamín Barrientos, Célula de Investigación |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Alcance | 16 observaciones: P-01 a P-07, C-01 a C-08 y C-09 (nueva) |
| Fecha de emisión | 01-11-2026 |
| Versión | 1.0 |
| Estado | Emitida |

**Tabla 8.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 0.1 | 29-10-2026 | Borrador: P-01 a P-06 y C-01 a C-07 (PR #217). | Benjamín Barrientos |
| 1.0 | 01-11-2026 | Aplica la revisión del sublíder en el PR #217: estabilidad solo sobre `_std` (P-03), Holm (P-04), regla de decisión con seis categorías y matriz de §5 (P-02, P-05), nivel «supera» frente a `day_only` (P-06), criterio de C-04, aristas no informativas en D1 (C-06), requisito de #168 (C-07) y nodo `diet` tras #176 (C-02). Incorpora P-07 y C-08 del sublíder y agrega C-09. | Benjamín Barrientos; revisión de Vicente Fuentes Rodríguez |
