# Revisión cruzada del protocolo y del contrato de explicaciones con Investigación (A55-P4, #158)

- **De:** Célula de Desarrollo. **Para:** Célula de Investigación.
- **Estado:** **cerrado.** Investigación respondió las 16 observaciones en la [respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>)
  (v1.1, emitida el 01-11-2026 por Vicente Fuentes y aprobada en el PR #217). Ninguna queda
  `pendiente`: las del protocolo están aplicadas y las del contrato y la visualización pasaron a
  #240 a #243. Los valores marcados como provisionales siguen siéndolo.
- **Issue:** [#158](https://github.com/jvnioo/NutriGraphDT/issues/158).

## 1. Documentos revisados

Cada observación se refiere a una versión fija, para conservar la trazabilidad aunque los
documentos cambien después.

| Documento | Issue | Versión revisada | Estado del documento |
|---|---|---|---|
| [Protocolo de evaluación con/sin restricciones](constraints-evaluation-protocol.md) (A55-P1) | [#155](https://github.com/jvnioo/NutriGraphDT/issues/155) | `main`, commit [`7ac4437`](https://github.com/jvnioo/NutriGraphDT/blob/7ac443793b6ca9db032bb68ccf02acc89366898d/docs/models/constraints-evaluation-protocol.md) (PR #202), con la corrección P-01 de este PR | Fusionado; propuesta de Desarrollo |
| Contrato de salida de las explicaciones `nutrigraphdt-explanation` 1.0.0 (A55-P3) | [#156](https://github.com/jvnioo/NutriGraphDT/issues/156) | PR [#204](https://github.com/jvnioo/NutriGraphDT/pull/204), commit [`c6a1e94`](https://github.com/jvnioo/NutriGraphDT/blob/c6a1e943f1c3c4affdd75fb3a7766875b1412bc8/docs/models/explanation-contract.md) | En revisión; quedará en `docs/models/explanation-contract.md` |
| Prueba de concepto de explicadores de PyG (A55-P2) | [#157](https://github.com/jvnioo/NutriGraphDT/issues/157) | PR [#205](https://github.com/jvnioo/NutriGraphDT/pull/205) | En revisión; insumo de C-06 |

## 2. Qué se pide a Investigación

Responder cada observación de la sección 3 por su identificador con una de estas opciones:

1. **Aceptar** la propuesta de Desarrollo.
2. **Cambiarla**, indicando el valor, la regla o la fuente.
3. **Aceptarla como limitación declarada**, sin cambio.
4. **Derivarla** a una tarea propia, indicando responsable y fecha estimada.

Cada observación trae una propuesta de Desarrollo para que se pueda responder solo con
«aceptada» cuando corresponda. Las que **bloquean** trabajo de Desarrollo se marcan en la columna
«Bloquea»; las demás pueden esperar.

## 3. Observaciones

Estados: `pendiente`, `resuelta`, `limitación aceptada`, `convertida en issue`. Una observación
sale de `pendiente` solo con una respuesta escrita enlazada en la columna «Respuesta».

### 3.1 Protocolo de evaluación (A55-P1)

| ID | Sección | Observación o pregunta | Propuesta de Desarrollo | Responde | Bloquea | Estado | Respuesta |
|---|---|---|---|---|---|---|---|
| P-01 | §2.2, §6.1 | El protocolo listaba los días 14, 21, 28 y 35, pero la cohorte de D1 solo tiene los días **7, 21 y 35**: vocabulario de `sampling_day` en `src/nutrigraphdt/data/covariates.py` y filas por día de `reports/baselines/d1_composition/metrics.csv`. | Corregido en este PR a 7, 21 y 35; Investigación solo confirma. | Investigación | — | `resuelta` | Aceptada ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Sin cambios. |
| P-02 | §4.3 | $\delta_{\text{ROPE}} = 1.0$ pp en el MAE macro de fracciones lo fijó Desarrollo **sin fuente**. | Se mantiene como provisional y así queda marcado en el protocolo. Investigación confirma el valor o da otro con su justificación. | Investigación | Aplicar §5 | `resuelta` | Cambiada: δ = 0,5 pp, provisional y dependiente de D1; relevancia biológica como limitación ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Aplicado en el protocolo §4.3, congelado antes de la evaluación de D1 de #185. |
| P-03 | §5, paso 3 | El criterio de estabilidad («¿la dispersión `_seed_std` y `_std` se mantiene controlada?») no tiene umbral. | Regla relativa: el brazo restringido no puede tener `_std` mayor que el brazo libre en la métrica primaria. Investigación la acepta o propone otra. | Investigación | Aplicar §5 | `resuelta` | Cambiada: sin folds fallidos y `_std` ≤ 1,25 × `_std` del brazo libre; `_seed_std` descriptiva ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Aplicado en el protocolo §5, paso 3. |
| P-04 | §2.2, §4.2 | Se comparan muchas métricas (fracciones, $\ln T$, concentraciones) por día y por restricción, sin corrección por comparaciones múltiples. | Declarar una **métrica primaria** (MAE macro de fracciones, `group = all`) para la decisión de §5 y tratar el resto como descriptivo, sin pruebas de significancia. | Investigación | — | `resuelta` | Cambiada: métrica primaria MAE macro de fracciones (`all`); Holm con más de un brazo restringido; F4 no se reabre ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Aplicado en el protocolo §2.2 y §4.2. |
| P-05 | §4.2 | Si el test $t$ corregido y Wilcoxon discrepan, no se dice cuál decide. | El $t$ corregido sobre los 50 folds decide; Wilcoxon sobre las 10 medias por semilla se informa como sensibilidad. | Investigación | — | `resuelta` | Cambiada: decide el IC del t corregido con seis categorías; Wilcoxon es sensibilidad anticonservadora ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Aplicado en el protocolo §4.2 y §5 (Tablas 4 y 5). |
| P-06 | §6.3 | «Supera holgadamente a `day_only`» no está definido. | Usar la misma prueba pareada y el mismo $\delta_{\text{ROPE}}$ de §4 contra `day_only`. | Investigación | — | `resuelta` | Cambiada: «supera» = U < 0 frente a `day_only`; «holgadamente» (U < −δ) informativo ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Aplicado en el protocolo §6.3. |
| P-07 | §3.2 | Sin D-06 (Actividad 78: ecuaciones y tolerancias) no se puede aplicar el criterio de factibilidad de §5. | Investigación informa la fecha estimada de D-06. Mientras tanto, F5 evalúa solo las restricciones estructurales (no negatividad y cierre), declarándolo como limitación. | Investigación | Módulo de restricciones (F5) | `resuelta` | Derivada a D-06 (Actividad 78) por el sublíder de Investigación, Vicente Fuentes, en el [comentario del 29-10-2026](https://github.com/jvnioo/NutriGraphDT/issues/217#issuecomment-6508986333). D-06 v1.0 se emitió el 29-10-2026 (PR #218, `docs/research/D-06 — Restricciones bioquímicas para D1.md`) y se implementó en #219 (`d06.hydrogen.propionate_bound`). Efecto aplicado en el protocolo: §3.2 declara el estado de D-06 v1 y el paso 1 de §5 pasa a «¿cumple la tolerancia de D-06?»; la adaptación de la columna «Violaciones» de la matriz se hace junto con P-02 y P-05. |

### 3.2 Contrato de explicaciones (A55-P3) y prueba de concepto (A55-P2)

| ID | Sección | Observación o pregunta | Propuesta de Desarrollo | Responde | Bloquea | Estado | Respuesta |
|---|---|---|---|---|---|---|---|
| C-01 | Contrato §2.4 | ¿Se admite importancia **con signo** (`[-1, 1]`) en F7? | Admitirla solo para explicadores que la entregan (por ejemplo `IntegratedGradients`), declarándola en `scale`; por omisión, `[0, 1]`. | Investigación | — | `convertida en issue` | Aceptada con condiciones ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Contrato §2.4 y §2.5: #242. |
| C-02 | Contrato §2.6 | ¿Qué advertencias adicionales exige Investigación para las explicaciones de D1? | Agregar `diet_day_confounding` (dieta confundida con el día, D-03) y `exploratory_treatment_contrast` (desbalance 34/15/7) a toda explicación de D1. | Investigación | #170 | `convertida en issue` | Cambiada: seis advertencias obligatorias en D1 ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Contrato §2.6 y wrapper: #240. |
| C-03 | Contrato §2.4 | ¿Las aristas con `evidence_status = hypothetical` deben marcarse aparte en la visualización? | Sí: estilo distinto y leyenda «hipotética», sin ocultarlas. | Investigación | Visualización (F7) | `convertida en issue` | Aceptada: estilo y leyenda propios para `hypothetical` ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Visualización de F7: #243. |
| C-04 | Contrato §2.3 | ¿Qué salida se explica: las del modelo (`log_propionate_acetate`, `log_butyrate_acetate`, `log_total`) o las concentraciones reconstruidas? Una concentración reconstruida depende de las tres salidas a la vez. | Explicar solo las tres salidas del modelo; las concentraciones reconstruidas no se explican en F7. | Investigación | #170 | `convertida en issue` | Cambiada: se explica una salida solo si el modelo supera a `dummy_mean` en su métrica; hoy z1 y z2, no ln T ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Nombres de salida resueltos en #222; contrato §2.3: #240. |
| C-05 | Contrato §2.1 | Con validación cruzada por corral hay 50 modelos (10 semillas × 5 folds). ¿Cuál se explica? | Explicar cada animal con el modelo del fold en que estuvo en test (fuera de fold), sobre las 10 semillas, e informar la estabilidad entre semillas. La agregación entre modelos sería una versión menor del contrato (`1.1.0`). | Investigación | #170 | `convertida en issue` | Aceptada con condiciones: modelo del fold en que el animal estuvo en test ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Wrapper: #241. |
| C-06 | PoC #157 | La prueba de concepto muestra que `homo_sage` no admite máscaras de aristas y que `AttentionExplainer` solo funciona en `hetero_gat`. | En F7, las explicaciones de aristas se hacen con `GNNExplainer` sobre `hetero_sage` o `hetero_gat`; `homo_sage` solo recibe importancia de nodos y atributos; la atención no se usa como explicación. | Investigación | #170 | `convertida en issue` | Aceptada con condiciones: en D1 solo atributos hasta S-04; aristas con `hetero_sage` o `hetero_gat` ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Reporte de F7: #240. |
| C-07 | Contrato §2.6 | Los explicadores son estocásticos. ¿Se exige una estabilidad mínima entre semillas del explicador antes de interpretar una explicación? | Informar siempre la estabilidad (correlación de rangos del top-k entre semillas) y advertir cuando sea baja. **El umbral lo fija Investigación**; Desarrollo no propone un valor. | Investigación | #170 | `convertida en issue` | Cambiada: Φ̂ de Nogueira et al. (2018) con ≥ 5 semillas, < 0,40 → `explainer_instability`; requisito previo del control de #168, cumplido en #233 ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Contrato §2.6 y wrapper: #240. |
| C-08 | Contrato §3, EXP-06 | El vocabulario de métodos de evidencia del contrato es el de EDG-04 más `synthetic_generator`. | Confirmarlo; si EDG-04 cambia, el contrato se actualiza en la misma versión de las reglas. | Investigación | — | `resuelta` | Aceptada por el sublíder de Investigación en el [comentario del 29-10-2026](https://github.com/jvnioo/NutriGraphDT/issues/217#issuecomment-6508986333). Efecto pedido: una prueba que exija que el vocabulario del contrato sea el de EDG-04 más `synthetic_generator` (`test_contract_evidence_vocabulary_is_edg04_plus_synthetic_generator`). |
| C-09 | Contrato §2.5 | (Nueva, de Investigación; L-4 de #216.) ¿Compiten las relaciones `rev_*` en el top-k? | — | Investigación | — | `convertida en issue` | Propuesta de Investigación: la importancia de cada `rev_*` se suma a la de su arista directa y el top-k se elige solo entre directas ([respuesta A55](<../research/Respuesta de Investigación a la revisión A55.md>), `docs/research/Respuesta de Investigación a la revisión A55.md`). Contrato §2.5, versión mayor: #242. |

## 4. Cómo se registra la respuesta

1. Investigación responde por identificador, en un comentario de
   [#158](https://github.com/jvnioo/NutriGraphDT/issues/158) o en un documento
   `docs/research/Respuesta de Investigación a la revisión A55.md`.
2. Desarrollo actualiza la columna «Estado» y enlaza la respuesta en «Respuesta». Una observación
   `convertida en issue` enlaza también el Issue nuevo.
3. Los cambios que pida Investigación se hacen en los documentos revisados, en un PR que cite el
   identificador. El contrato sube de versión según su §5.
4. Cuando ninguna observación quede `pendiente`, se retira la nota «sin aprobación científica» de
   los documentos y se cierra #158. **Sin respuesta escrita no se declara aprobación.**

`tests/unit/test_explanations_protocol_review.py` comprueba que cada observación tiene un estado
válido y que ninguna sale de `pendiente` sin una respuesta enlazada.
