# Respuesta de Investigación a la revisión A55

- **De:** Célula de Investigación (Benjamín Barrientos). **Para:** Célula de Desarrollo
  (contraparte: Julio Provoste Palacios).
- **Coordina y emite:** Vicente Fuentes Rodríguez, sublíder de Investigación.
- **Responde a:** R-13 de la *Solicitud de respuesta de Desarrollo a Investigación v1.0* e Issue
  [#158](https://github.com/jvnioo/NutriGraphDT/issues/158) (A55-P4).
- **Registro que se actualiza:** `docs/models/explanations-protocol-review.md`.
- **Fecha:** 29-10-2026. **Estado:** borrador para revisión con Vicente Fuentes; no es respuesta
  emitida hasta su visto bueno.
- **Alcance:** 13 observaciones (P-01 a P-06 y C-01 a C-07). P-07 la responde Maximiliano Campos
  y C-08, Felipe Cruz.
- **Versión de los insumos:** `main` en el commit `df7a66a` (28-10-2026): protocolo
  `constraints-evaluation-protocol.md`, contrato `nutrigraphdt-explanation` 1.0.0, prueba de
  concepto #157, wrapper #170 y reporte `reports/gnn/d1_composition/` (#142).

> **Cómo se obtuvieron las cifras nuevas.** Las diferencias pareadas, los intervalos corregidos y
> las pruebas de esta respuesta se calcularon con `reports/gnn/d1_composition/fold_metrics.csv` y
> `reports/baselines/d1_composition/fold_metrics.csv` (grupo `all`, MAE macro de fracciones en pp,
> los mismos 50 folds para todos los modelos). El intervalo corregido usa la varianza de Nadeau y
> Bengio con $n_\text{test}/n_\text{train} = 0{,}25$ y 49 grados de libertad, igual que §4.2 del
> protocolo. Son resultados de D1; donde se usan para fijar un valor, se declara.

---

## 1. Resumen de decisiones

| ID | Decisión | Respuesta en una línea | Fuente o justificación | Efecto esperado |
|---|---|---|---|---|
| P-01 | Aceptada | Los días de D1 son 7, 21 y 35. | Vocabulario de `sampling_day` y filas por día de los reportes. | Ninguno; se retira la marca de pendiente. |
| P-02 | **Cambiada** | $\delta_\text{ROPE} = 0{,}5$ pp (provisional, congelado antes de F5); la no inferioridad se decide con el límite superior del IC corregido. | Kruschke (2018): 0,1·DE ≈ 0,58 pp; resolución del diseño ≈ 0,30–0,44 pp; con 1,0 pp un brazo restringido podría perder toda la ganancia sobre el trivial (0,74 pp). | Cambiar §4.3 y §5 del protocolo; declarar la dependencia de D1. |
| P-03 | **Cambiada** | Estable si no hay folds fallidos y `_std` y `_seed_std` del brazo restringido son ≤ 1,25 veces los del libre. | SIN FUENTE para 1,25: calibrado con la variación entre variantes GNN equivalentes (hasta 1,17). Una regla sin tolerancia rechaza por ruido. | Cambiar §5, paso 3. |
| P-04 | **Cambiada** | Métrica primaria de F5: MAE macro de fracciones, `group = all`; R² y el resto, descriptivos. El criterio de F4 no se reabre: en D1 ambas métricas dan la misma conclusión. Si entra más de un brazo restringido, corrección de Holm. | Alexander et al. (2015); resultados pareados de D1. | Cambiar §2.2, §4.2 y §5; nota de conciliación con F4. |
| P-05 | **Cambiada** | Decide el IC del $t$ corregido sobre los 50 folds. Wilcoxon sobre 10 medias se informa como sensibilidad **anticonservadora** y nunca revierte la decisión. | Nadeau y Bengio (2003); Bouckaert y Frank (2004); Corani y Benavoli (2015). En D1, Wilcoxon da p = 0,010 donde el $t$ corregido da p = 0,50. | Cambiar §4.2 y §5. |
| P-06 | **Cambiada** | «Supera» = límite superior del IC corregido de Δ frente a `day_only` < 0; «supera holgadamente» = límite superior < −δ. | Coherencia con P-02 y P-05 (Kruschke, 2018). Hoy ninguna GNN supera a `day_only`. | Cambiar §6.3; agregar advertencia en C-02. |
| C-01 | Aceptada, con condiciones | Signo solo para explicadores que lo entregan; `max_abs` a `[-1, 1]`; el top-k se elige por valor absoluto; se declara la línea base de IntegratedGradients. | Sundararajan et al. (2017). | Contrato §2.4 y §2.5 (regla de selección con signo). |
| C-02 | **Cambiada** (amplía) | Se aceptan las dos advertencias propuestas y se agregan cuatro más: grupo Fitobiótico insuficiente, modelo no mejor que `day_only`, taxones aislados (S-04) e inestabilidad del explicador. | D-03, L1–L3; reporte #142; C-07. | Contrato §2.6 y wrapper #170. |
| C-03 | Aceptada | Estilo distinto y leyenda «hipotética», sin ocultarlas; la importancia no las valida. | Principio 1 del contrato. | Visualización de F7. |
| C-04 | **Cambiada** | En D1 se explican solo `log_propionate_acetate` y `log_butyrate_acetate`. `log_total` no se explica mientras no supere a `dummy_mean`. Las concentraciones no se explican en F7. **Hay que corregir el nombre de las salidas en el wrapper.** | La concentración no se descompone (axioma de linealidad, Sundararajan et al., 2017; Aitchison, 1982). R² de ln T: −0,35 frente a −0,32 del trivial. | Corrección en #170 y en el contrato §2.3. |
| C-05 | Aceptada, con condiciones | Cada animal se explica con el modelo del fold en que estuvo en test, en las 10 semillas. Nunca con un modelo que lo vio en train. La variabilidad entre semillas se informa por separado de la del explicador. | Protocolo §1.3 (sin fuga). | Wrapper #170; la agregación queda para el contrato 1.1.0. |
| C-06 | Aceptada | Aristas con GNNExplainer sobre `hetero_sage` (principal) o `hetero_gat`; `homo_sage` solo nodos y atributos; la atención no es explicación. Explicar `hetero_sage` no cuesta exactitud medible. | PoC #157; Jain y Wallace (2019). `hetero_sage` frente a `homo_sage`: Δ = +0,05 pp, IC [−0,25; 0,35]. | Ninguno nuevo en el código; se registra la variante principal. |
| C-07 | **Cambiada** (fija umbral) | Estabilidad del top-k con el estimador Φ̂ de Nogueira et al. (2018) en ≥ 5 semillas del explicador. Φ̂ < 0,40: advertencia y no interpretar el top-k. Φ̂ ≥ 0,75: estabilidad excelente. Umbral **provisional**. | Nogueira et al. (2018), escala de Fleiss et al. (2003). No hay umbral de consenso para explicaciones de GNN. | Wrapper #170, advertencia `explainer_instability`. |

---

## 2. Protocolo de evaluación (A55-P1)

### P-01 · Días de muestreo

- **Decisión:** Aceptada.
- **Respuesta:** la cohorte de 56 animales de D1 solo tiene muestreos en los días 7, 21 y 35. La
  corrección de §2.2 y §6.1 es correcta.
- **Justificación:** coincide con el vocabulario de `sampling_day` en
  `src/nutrigraphdt/data/covariates.py` y con las filas por día de los reportes de baselines y GNN.
- **Efecto:** ninguno en el código; la observación pasa a `resuelta`.

### P-02 · Valor de $\delta_\text{ROPE}$

- **Decisión:** Cambiada.
- **Respuesta:** $\delta_\text{ROPE} = 0{,}5$ pp en el MAE macro de fracciones (`group = all`),
  **provisional**, y se congela antes de correr cualquier brazo restringido de F5. Además, la
  pregunta 2 de §5 se formaliza como prueba de no inferioridad: el brazo restringido es no
  inferior si el límite superior del IC 95 % corregido de
  $\Delta = \text{MAE}(M_C) - \text{MAE}(M_0)$ es menor que $\delta$.
- **Justificación.** Se compararon los tres enfoques que pide el encargo y dos restricciones
  propias del diseño:

  | Enfoque | Resultado | Estado |
  |---|---|---|
  | (a) Literatura de predicción de composición de AGCC o de datos composicionales | No se encontró un margen de equivalencia publicado para MAE de proporciones molares de AGCC. | SIN FUENTE |
  | (b) Relativo a la variabilidad: 0,1 desviación estándar de la respuesta, el ROPE por omisión de Kruschke (2018) | La dispersión de las fracciones en D1 se aproxima con el MAE de `dummy_mean` (4,63 pp): bajo normalidad, DE ≈ 4,63·√(π/2) ≈ 5,8 pp, y 0,1·DE ≈ **0,58 pp**. | Con fuente; depende de D1 |
  | (c) Relevancia biológica: qué diferencia de proporción molar importa en nutrición avícola | No se encontró un umbral de consenso. Sí se observa que 0,5 pp es un orden de magnitud menor que la dispersión natural entre animales (≈ 5,8 pp). | SIN FUENTE |
  | (d) Resolución del diseño: semiancho del IC corregido | ≈ 0,30 pp entre modelos parecidos (`hetero_sage` frente a `homo_sage`) y ≈ 0,44 pp entre modelos distintos (`homo_sage` frente a `dummy_mean`). Un δ menor haría la no inferioridad indemostrable aunque Δ = 0. | Calculado en D1 |
  | (e) Que no sea laxo | La mejor GNN supera a `dummy_mean` por 0,74 pp. Con δ = 1,0 pp, un brazo restringido podría perder toda esa ganancia y seguir siendo «equivalente». Con δ = 0,5 pp, perder más de dos tercios de la ganancia lo rechaza. | Calculado en D1 |

  El valor de 0,5 pp cae entre la resolución del diseño (d) y el valor por omisión de Kruschke
  (b), y queda por debajo de la ganancia sobre el trivial (e). Se eligió el número redondo dentro
  de ese intervalo.
- **Dependencia declarada.** (b), (d) y (e) se calculan con resultados de D1. Para que no haya
  circularidad, δ se fija **ahora**, antes de ver cualquier resultado de $M_C$, y no se modifica
  después. Si cambia la cohorte o la métrica primaria, se revisa.
- **Coordinación:** este δ fija cuánto costo predictivo se acepta a cambio de reducir violaciones.
  Hay que compartirlo con Maximiliano Campos (P-07, D-06) antes de emitir.
- **Fuentes:** Kruschke (2018); Walker y Nowacki (2011) para la lógica de no inferioridad con
  intervalo.
- **Efecto:** en §4.3, cambiar 1,0 pp por 0,5 pp y la frase «provisional de Desarrollo» por
  «provisional de Investigación (P-02), dependiente de D1». En §5 (paso 2) y en la matriz de
  clasificación, usar la regla del límite superior del IC.

### P-03 · Umbral de estabilidad

- **Decisión:** Cambiada.
- **Respuesta:** el brazo restringido es estable si cumple las tres condiciones:
  1. ningún fold fallido (ya está en §7);
  2. `_std` de la métrica primaria ≤ 1,25 × `_std` del brazo libre;
  3. `_seed_std` de la métrica primaria ≤ 1,25 × `_seed_std` del brazo libre.
- **Justificación.** La propuesta de Desarrollo («no mayor que») no tiene tolerancia, así que
  rechazaría modelos igual de estables solo por ruido de muestreo. En D1, la `_std` de las tres
  variantes GNN, que son prácticamente equivalentes en exactitud, va de 0,660 a 0,682 (razón
  1,03). Su `_seed_std` va de 0,144 a 0,168 (razón 1,17). Además, gran parte de `_std` viene de
  la dificultad de los corrales de test de cada fold, que es común a ambos brazos. Por eso tiene
  sentido comparar con una razón, pero no exigir igualdad estricta.
- **Fuente:** SIN FUENTE para el factor 1,25 — propuesta provisional. Se calibró para quedar por
  encima de la mayor razón observada entre variantes equivalentes (1,17), y depende de D1.
- **Efecto:** reemplazar la pregunta del paso 3 de §5 por las tres condiciones.

### P-04 · Comparaciones múltiples y métrica primaria

- **Decisión:** Cambiada (acepta la métrica primaria y agrega conciliación y multiplicidad).
- **Respuesta:**
  1. La métrica primaria de F5 es el **MAE macro de fracciones, `group = all`**. Es la única que
     entra a la decisión de §5. El resto (R², ln T, concentraciones, métricas por día y por
     restricción) es descriptivo, sin pruebas de significancia.
  2. **Conciliación con F4.** El criterio de F4 (R² macro de fracciones) no se reabre: ya se
     aplicó y es una fase cerrada. En D1 las dos métricas llevan a la misma conclusión:

     | Comparación | Δ R² macro, IC 95 % corregido | Δ MAE macro (pp), IC 95 % corregido | Conclusión |
     |---|---|---|---|
     | `homo_sage` − `random_forest` | −0,08 [−0,27; 0,11] | +0,09 [−0,32; 0,50] | No concluyente con las dos métricas |
     | `homo_sage` − `day_only` | +0,03 [−0,13; 0,19] | −0,14 [−0,54; 0,27] | No concluyente con las dos métricas |
     | `homo_sage` − `dummy_mean` | +0,31 [0,09; 0,52] | −0,74 [−1,18; −0,30] | La GNN es mejor con las dos métricas |

  3. Se cambia de métrica en F5 porque: (i) el MAE está en pp, la misma unidad que δ; (ii) el R²
     fuera de muestra depende de la varianza de cada fold de test. Con 10 a 12 animales por fold
     es inestable, y por día llega a valores como −516. Alexander et al. (2015) recomiendan, para
     predicción externa, informar errores en la unidad de la respuesta y no depender del R².
  4. **Multiplicidad.** Si en §5 entra más de un brazo restringido frente al mismo $M_0$, las
     pruebas de no inferioridad se corrigen con Holm (1979) sobre el número de brazos.
- **Efecto:** en §2.2 marcar `fraction_mae_pp` (macro, `all`) como métrica primaria. Agregar a
  §5 la nota de conciliación con F4 y la corrección de Holm.

### P-05 · Discrepancia entre el $t$ corregido y Wilcoxon

- **Decisión:** Cambiada (acepta la propuesta y la precisa).
- **Respuesta:**
  1. Decide el **intervalo de confianza del $t$ corregido** sobre los 50 folds, aplicado a la
     regla de δ (P-02). Las cuatro lecturas posibles son: no inferior (límite superior < δ),
     equivalente (IC dentro de ±δ), superior (límite superior < 0) y superior en la práctica
     (límite superior < −δ).
  2. Wilcoxon sobre las 10 medias por semilla se informa como sensibilidad, rotulado como
     **anticonservador**, y nunca revierte la decisión.
  3. $n_\text{train}$ se cuenta como train + val interno, porque ambos los usa el procedimiento de
     aprendizaje (la detención temprana usa el val interno). Con esa definición, la razón
     observada en `folds.csv` es 0,25 en promedio (de 0,22 a 0,27), así que el 0,25 del protocolo
     se confirma. Se pide registrar en `run.json` la razón media usada.
- **Justificación.** Las 10 medias por semilla no son independientes: todas reparten los mismos
  56 animales. Wilcoxon las trata como independientes y además tiene poca resolución con n = 10:
  si las 10 diferencias tienen el mismo signo, da p ≈ 0,002 sin importar su tamaño. En D1 se
  observa la discrepancia:

  | Comparación (MAE macro) | $t$ corregido, p | Wilcoxon (10 medias), p |
  |---|---|---|
  | `homo_sage` − `day_only` | 0,50 | 0,010 |
  | `random_forest` − `day_only` | 0,09 | 0,002 |
  | `homo_sage` − `random_forest` | 0,65 | 0,049 |

  Si Wilcoxon decidiera, se declararían mejoras que el diseño no sostiene. El $t$ corregido
  incorpora la correlación por solapamiento de los conjuntos de entrenamiento (Nadeau y Bengio,
  2003), y Bouckaert y Frank (2004) lo recomiendan por replicabilidad. Su versión bayesiana (el
  $t$ correlacionado de Corani y Benavoli, 2015) usa la misma heurística de correlación y, con
  prior no informativo, coincide con la decisión frecuentista. Por eso la regla IC + δ equivale a
  la regla ROPE de Kruschke (2018).
- **Efecto:** cambiar §4.2 (jerarquía de pruebas y rótulo de Wilcoxon) y §5 (decisión por IC).

### P-06 · «Supera holgadamente a `day_only`»

- **Decisión:** Cambiada (precisa la propuesta).
- **Respuesta:** con la misma prueba pareada y el mismo δ, y con
  $\Delta = \text{MAE}(M) - \text{MAE}(\texttt{day\_only})$:
  - $M$ **supera** a `day_only` si el límite superior del IC 95 % corregido de Δ es < 0;
  - $M$ **supera holgadamente** a `day_only` si ese límite superior es < −δ (−0,5 pp).
- **Situación actual:** ninguna GNN supera a `day_only`. Para `homo_sage`,
  Δ = −0,14 pp con IC [−0,54; 0,27]; para `random_forest`, IC [−0,50; 0,04]. Según §6.3, hoy
  ningún modelo puede declararse con aprendizaje biológico más allá de la curva de edad. Esto se
  traslada a una advertencia obligatoria (C-02).
- **Efecto:** reemplazar la frase de §6.3 por la definición de dos niveles.

---

## 3. Contrato de explicaciones (A55-P3) y prueba de concepto (A55-P2)

### C-01 · Importancia con signo

- **Decisión:** Aceptada, con condiciones.
- **Respuesta:**
  1. `[-1, 1]` solo para explicadores que entregan signo (por ejemplo IntegratedGradients),
     declarado en `scale` con `normalization = max_abs`. Por omisión, `[0, 1]`.
  2. Con escala con signo, el subgrafo top-k se elige por **valor absoluto** de la importancia. Si
     no, se eligen solo las contribuciones positivas y se pierden las negativas, que pesan igual.
  3. La línea base (*baseline*) de IntegratedGradients se declara en `explainer.config`, porque la
     atribución depende de ella (Sundararajan et al., 2017).
  4. Interpretación: un signo positivo en `log_propionate_acetate` significa que el elemento
     aumenta la razón propionato/acetato en el modelo, no que aumente el propionato.
  5. No se comparan rankings con signo y sin signo entre sí.
- **Efecto:** el contrato §2.4 queda igual. El §2.5 necesita una regla de selección por valor
  absoluto para escalas con signo: según §5 del contrato, cambiar la regla de selección sube la
  versión mayor. Desarrollo decide si lo hace como una regla nueva (`top_k_edges_by_abs_importance`)
  para no romper la 1.0.0.

### C-02 · Advertencias obligatorias para D1

- **Decisión:** Cambiada (acepta las dos propuestas y agrega cuatro).
- **Respuesta:** toda explicación de D1 lleva, además de las advertencias de §2.6:

  | `code` | Cuándo | Contenido del mensaje |
  |---|---|---|
  | `diet_day_confounding` | Siempre en D1 (aceptada) | La dieta está confundida con el día de muestreo: el día 35 es casi solo Control (D-03). |
  | `exploratory_treatment_contrast` | Siempre en D1 (aceptada) | Desbalance 34/15/7: cualquier comparación entre dietas es exploratoria (L1). |
  | `insufficient_group_size` | Si el animal explicado es Fitobiótico (`CE`), o si la explicación informa importancia del nodo `diet` o del atributo de tratamiento | Fitobiótico tiene 7 animales en 6 corrales (1 a 2 por fold de test). Esa importancia no permite ninguna conclusión específica de la dieta, ni siquiera exploratoria. |
  | `model_not_better_than_day_only` | Siempre en D1 mientras se mantenga el resultado de P-06 | El modelo explicado no supera a `day_only` fuera de corral. La explicación describe un modelo que, en exactitud, no se distingue de la media por día. |
  | `isolated_taxa_pending_s04` | Siempre en D1 mientras S-04 esté abierta | Los taxones no tienen aristas a funciones ni metabolitos y no reciben mensajes. Su importancia entra solo por la lectura del grafo, como en un modelo tabular; no hay rutas mecanísticas que explicar (L2/L3). |
  | `explainer_instability` | Si la estabilidad de C-07 queda bajo el umbral | El top-k cambia entre semillas del explicador; no interpretar los elementos individuales. |

- **Justificación:** sobre el pedido del encargo, con 7 animales Fitobiótico «exploratoria» no
  alcanza: en cada fold de test hay 1 o 2, así que la explicación por dieta depende de muy pocos
  individuos. `model_not_better_than_day_only` sale de P-06. `isolated_taxa_pending_s04` sale de
  la limitación ya declarada en el reporte #142.
- **Efecto:** agregar las seis filas a la tabla de §2.6 del contrato (condicionadas a D1) y al
  wrapper #170. Desarrollo decide la versión del contrato.

### C-03 · Aristas `hypothetical` en la visualización

- **Decisión:** Aceptada.
- **Respuesta:** estilo distinto (por ejemplo, línea discontinua) y leyenda «hipotética: sin
  respaldo empírico», sin ocultarlas ni filtrarlas del top-k. La leyenda recuerda que una
  importancia alta en el modelo no convierte a la arista en evidencia (principio 1 del contrato).
  Se sugiere que los cinco estados de evidencia de DS-01 tengan una codificación visual propia.
- **Efecto:** solo visualización de F7.

### C-04 · Qué salidas se explican

- **Decisión:** Cambiada (acepta explicar salidas del modelo y restringe cuáles).
- **Respuesta:**
  1. En D1 se explican **solo `log_propionate_acetate` (z1) y `log_butyrate_acetate` (z2)**.
  2. `log_total` (ln T) **no se explica en D1** mientras su desempeño fuera de corral no supere a
     `dummy_mean` con la regla de P-06. Hoy su R² es −0,35 (`homo_sage`) frente a −0,32 del
     trivial, así que explicarla sería explicar ruido. En datos sintéticos sí se puede.
  3. Las concentraciones reconstruidas **no se explican en F7**.
  4. Interpretación: z1 y z2 son razones respecto del acetato. La importancia para z1 no es
     «importancia para el propionato», y el acetato no tiene salida propia que explicar.
- **Por qué una concentración no se descompone.** Con
  $\boldsymbol\ell = (0, z_1, z_2)$, el logaritmo de la concentración de cada AGCC es
  $\ln c_k = \ln T + \ell_k - \log\sum_j e^{\ell_j}$. El último término (log-suma-exp) acopla z1
  y z2 de forma no lineal: la fracción de cada AGCC depende de las dos log-razones a la vez
  (Aitchison, 1982). Los métodos de atribución por gradiente cumplen linealidad: la atribución de
  una combinación **lineal** de salidas es la combinación de las atribuciones (Sundararajan et
  al., 2017). Esa propiedad no vale para una función no lineal de las salidas. Por eso no se
  pueden sumar las importancias de z1, z2 y ln T para obtener la de $c_k$. Si en el futuro se
  quiere explicar una concentración, la vía correcta es explicar directamente la función
  compuesta $c_k(\cdot)$ como una salida escalar. Queda para una versión posterior del contrato.
- **Hallazgo en el código fusionado (prioridad alta).** En `main` (`df7a66a`), `HeteroExplainer`
  toma los nombres de salida de `model.target_names`. En las GNN ese atributo vale
  `("acetate", "propionate", "butyrate")` (`DEFAULT_SCFA_TARGETS`), pero la cabeza composicional
  devuelve `(z1, z2, ln T)`. Así, pedir `target="butyrate"` explica en realidad la columna 2, que
  es **ln T**. Pedir `acetate` explica z1, y la `unit` puede quedar mal. Desarrollo debe
  verificarlo y, si se confirma, usar `MODEL_OUTPUT_NAMES` para los modelos composicionales.
- **Efecto:** corrección en #170. En el contrato §2.3, `output` en D1 se limita a z1 y z2, y se
  retira la opción «o un AGCC» para modelos composicionales.

### C-05 · Cuál de los 50 modelos explica a cada animal

- **Decisión:** Aceptada, con condiciones.
- **Respuesta:**
  1. Cada animal se explica con el modelo del fold en que estuvo en **test**, en cada una de las
     10 semillas: 10 explicaciones por animal y salida.
  2. Nunca se explica a un animal con un modelo que lo tuvo en train, porque se estaría explicando
     memorización.
  3. El escalado de atributos que recibe el explicador es el del fold de ese modelo (protocolo
     §1.3).
  4. Se informan **dos estabilidades separadas**:
     - entre las 10 semillas del plan (cambia la partición y el entrenamiento);
     - entre semillas del explicador con el modelo fijo (C-07).

     La semilla de entrenamiento de cada fold se deriva de la del fold (reporte #142), así que la
     primera mezcla partición y optimización. Hay que declararlo.
  5. Un fold fallido no se reemplaza: ese animal queda con menos de 10 explicaciones y se informa
     cuántas tiene.
  6. La agregación entre modelos (por ejemplo, rango mediano) se deja para el contrato `1.1.0`,
     como propone Desarrollo.
- **Implementabilidad:** con 56 animales, 10 semillas, 2 salidas (z1, z2) y al menos 5 semillas
  del explicador, son 5600 ejecuciones de GNNExplainer o más. Desarrollo estima el costo en CPU
  antes de fijar el número de épocas (pregunta abierta de la PoC).
- **Efecto:** wrapper #170 (selección del modelo fuera de fold) y reporte de F7.

### C-06 · Explicadores por variante

- **Decisión:** Aceptada.
- **Respuesta:**
  - Las explicaciones de aristas se hacen con GNNExplainer, sobre **`hetero_sage` como variante
    principal** y `hetero_gat` como secundaria.
  - `homo_sage` solo recibe importancia de nodos y atributos.
  - La atención no se usa como explicación.
- **Justificación:**
  - La PoC #157 muestra que en `homo_sage` las máscaras de aristas no llegan a ninguna capa.
    PGExplainer devuelve valores igual, pero no explican nada.
  - Elegir `hetero_sage` no tiene costo medible: frente a `homo_sage`, Δ MAE = +0,05 pp con IC
    corregido [−0,25; 0,35], dentro de ±δ (equivalentes con P-02).
  - Que los pesos de atención no explican las predicciones está documentado: Jain y Wallace
    (2019) muestran que suelen no coincidir con la importancia por gradiente y que distintas
    atenciones dan la misma predicción.
  - Mientras S-04 esté abierta, las aristas que hay en D1 son pocas, así que las explicaciones de
    aristas en D1 tienen alcance limitado (advertencia `isolated_taxa_pending_s04`).
- **Efecto:** ninguno nuevo en el código. En el reporte de F7 se registra `hetero_sage` como
  variante explicada principal.

### C-07 · Estabilidad mínima entre semillas del explicador

- **Decisión:** Cambiada (Investigación fija el umbral).
- **Respuesta:**
  1. Para cada instancia, salida y modelo, se corre el explicador con **al menos 5 semillas**. Se
     calcula la estabilidad del conjunto top-k (aristas, o atributos en `homo_sage`) con el
     estimador **Φ̂ de Nogueira et al. (2018)**, informado con su intervalo de confianza.
  2. Escala de lectura (provisional):
     - **Φ̂ < 0,40:** estabilidad pobre. Se agrega `explainer_instability` y no se interpretan
       los elementos individuales del top-k.
     - **0,40 ≤ Φ̂ < 0,75:** intermedia a buena. Se interpreta con cautela.
     - **Φ̂ ≥ 0,75:** excelente.
  3. Como información complementaria, sin umbral, se informa la correlación de Kendall de los
     rangos del top-k.
- **Justificación.** Elegir el top-k en cada semilla es lo mismo que seleccionar k elementos de d
  en M repeticiones, el problema que trata Nogueira et al. (2018). Su estimador:
  - está corregido por azar (vale 0 si la selección es aleatoria);
  - con k fijo coincide con el índice de Kuncheva;
  - con dos categorías equivale al kappa de Fleiss.

  Los autores proponen leerlo con la escala de Fleiss et al. (2003): menos de 0,40 pobre, 0,40 a
  0,75 intermedio a bueno, más de 0,75 excelente. Se prefiere a Jaccard o Spearman sin corregir,
  porque esos no descuentan las coincidencias por azar cuando k es grande respecto de d.

  La necesidad de medir la estabilidad está documentada. Con GNNExplainer, el top-k de aristas
  cambia entre ejecuciones con distinta inicialización del explicador (Zhao et al., 2023), y la
  importancia de atributos varía con la semilla aun en modelos con exactitud perfecta (Cvetković y
  Mitrović Dankulov, 2026). Los marcos de evaluación de explicaciones de GNN (Agarwal et al., 2023) tampoco
  fijan un umbral. **No se encontró un umbral de consenso para explicaciones de GNN. El 0,40 se
  traslada desde la estabilidad de selección de atributos y queda como provisional.**
- **Fuentes:** Nogueira et al. (2018); Fleiss et al. (2003); Zhao et al. (2023); Cvetković y
  Mitrović Dankulov (2026); Agarwal et al. (2023).
- **Efecto:** wrapper #170 (cálculo de Φ̂ y advertencia) y contrato §2.6 (fila
  `explainer_instability`).

---

## 4. Trabajo derivado y coordinación

- **No hay observaciones «Derivadas»** a una tarea nueva de Investigación. Los cambios de código
  que salen de esta respuesta los hace Desarrollo, citando el identificador:
  - corrección de nombres de salida (C-04);
  - advertencias de D1 (C-02) y Φ̂ (C-07);
  - selección de modelo fuera de fold (C-05);
  - regla de top-k con signo (C-01).
- **P-07 (Maximiliano Campos):** δ = 0,5 pp (P-02) y la regla de estabilidad (P-03) fijan el
  costo predictivo aceptable frente a la reducción de violaciones. Hay que revisarlos juntos antes
  de emitir.
- **C-08 (Felipe Cruz):** su respuesta se consolida en este documento o se enlaza desde #158.

## 5. Referencias

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
| Zhao, T., Luo, D., Zhang, X. y Wang, S. (2023). Faithful and consistent graph neural network explanations with rationale alignment. | [arXiv:2301.02791](https://arxiv.org/abs/2301.02791) |

## 6. Preguntas abiertas

**Para Vicente Fuentes (antes de emitir):**

1. ¿Se acepta fijar δ con un criterio relativo a la variabilidad de D1 (P-02, enfoques b, d y e),
   a falta de un valor biológico con fuente? ¿Conviene derivar una revisión bibliográfica de
   relevancia biológica (enfoque c) con fecha posterior al 04-11?
2. ¿Se acepta trasladar la escala de Fleiss, vía Nogueira et al. (2018), como umbral provisional
   de estabilidad de explicaciones (C-07)?
3. ¿Se acepta excluir ln T de las explicaciones de D1 (C-04) aunque Desarrollo propuso las tres
   salidas?

**Para Desarrollo (Julio Provoste):**

1. Confirmar el hallazgo de nombres de salida del wrapper (C-04) y si afecta a explicaciones ya
   generadas.
2. Estimar el costo de C-05 + C-07 (≥ 5600 ejecuciones del explicador) para fijar épocas y número
   de semillas.
3. Decidir la versión del contrato para la regla de top-k con signo (C-01) y las advertencias de
   D1 (C-02).
