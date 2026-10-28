# Revisión cruzada de Pull Requests del módulo GNN (A52-P1)

Este informe documenta la auditoría y revisión cruzada de los Pull Requests correspondientes al
módulo de Graph Neural Networks (GNN), su pipeline de entrenamiento y la evaluación comparativa,
en cumplimiento de la actividad **A52-P1** del desglose de Desarrollo (Fase F4,
[Issue #159](https://github.com/jvnioo/NutriGraphDT/issues/159)).

El objetivo de esta tarea es auditar el estado real de integración del código, verificar que
todas las observaciones realizadas durante las revisiones técnicas hayan sido resueltas o
queden trazadas en un Issue específico con responsable asignado, y comprobar que ninguna
fusión haya eludido las validaciones locales del flujo Scrumban
([docs/process/workflow.md](../process/workflow.md)).

---

## 1. Alcance y marco de auditoría

El alcance de la auditoría comprende todos los PRs que introdujeron o modificaron:
1. Las arquitecturas de red (`nutrigraphdt.models.gnn`), componentes compartidos y fábrica de configuración.
2. El pipeline de preparación de datos, escalado, dataloaders y bucle de entrenamiento (`nutrigraphdt.models.training`).
3. El sistema de registro de experimentos y trazabilidad (`nutrigraphdt.models.tracking`).
4. Los scripts de ejecución y comparación (`scripts/train_gnn.py`, `scripts/report_gnn.py`, `scripts/tune_gnn.py`, `scripts/compare_models.py`, `scripts/plot_gnn_runs.py`).
5. Las evaluaciones sobre el dataset sintético y sobre D1 HoloFood (enfoque inicial y reevaluación composicional bajo contrato de datos v2).

### Criterios de aceptación auditados
- **Revisión cruzada registrada:** cada PR de la línea base debe contar con revisión técnica independiente.
- **Trazabilidad de observaciones:** ninguna observación de revisión puede quedar en el vacío; debe estar subsanada en el código o derivada a un Issue explícito.
- **Verificación local estricta:** pase limpio de `ruff check .`, `ruff format --check .`, `mypy src` y `pytest`.

---

## 2. Inventario exhaustivo de Pull Requests del módulo GNN

La siguiente tabla resume todos los Pull Requests integrados del módulo GNN y su pipeline:

| PR | Rama origen | Issue | Título y resumen | Estado | Revisor(es) |
|---|---|---|---|---|---|
| [#90](https://github.com/jvnioo/NutriGraphDT/pull/90) | `docs/77-gnn-architecture-design` | [#77](https://github.com/jvnioo/NutriGraphDT/issues/77) | `docs: diseño de la arquitectura GNN (A41-1)`: especificación de variantes `homo_sage`, `hetero_sage`, `hetero_gat`. | Merged | jvnioo |
| [#91](https://github.com/jvnioo/NutriGraphDT/pull/91) | `feat/81-gnn-encoders-head` | [#81](https://github.com/jvnioo/NutriGraphDT/issues/81) | `feat(A41-5): add shared GNN components, base model and graph target`: encoders por tipo de nodo, pooling y cabeza MLP. | Merged | jvnioo |
| [#93](https://github.com/jvnioo/NutriGraphDT/pull/93) | `feat/78-homo-sage` | [#78](https://github.com/jvnioo/NutriGraphDT/issues/78) | `feat(A41-2): add homogeneous GraphSAGE baseline (homo_sage)`: implementación homogénea sobre grafo homogeneizado. | Merged | jvnioo |
| [#94](https://github.com/jvnioo/NutriGraphDT/pull/94) | `feat/79-hetero-sage` | [#79](https://github.com/jvnioo/NutriGraphDT/issues/79) | `feat: add heterogeneous GraphSAGE model`: convolución heterogénea por tipo de relación. | Merged | jvnioo |
| [#109](https://github.com/jvnioo/NutriGraphDT/pull/109) | `feat/80-hetero-gat` | [#80](https://github.com/jvnioo/NutriGraphDT/issues/80) | `feat: add heterogeneous GAT model with attention weights`: atención sobre relaciones heterogéneas. | Merged | jvnioo |
| [#110](https://github.com/jvnioo/NutriGraphDT/pull/110) | `test/82-gnn-tensor-tests` | [#82](https://github.com/jvnioo/NutriGraphDT/issues/82) | `test: add common tensor tests for GNN variants`: suites parametrizadas de invariancia y tipos. | Merged | jvnioo |
| [#112](https://github.com/jvnioo/NutriGraphDT/pull/112) | `feat/84-model-config-factory` | [#84](https://github.com/jvnioo/NutriGraphDT/issues/84) | `feat: configuración YAML y fábrica de modelos GNN`: instanciación declarativa y validación Pydantic. | Merged | jvnioo |
| [#113](https://github.com/jvnioo/NutriGraphDT/pull/113) | `feat/98-training-config-seeds` | [#98](https://github.com/jvnioo/NutriGraphDT/issues/98) | `feat: configuración del entrenamiento y control de semillas (A44-4)`: seed generator determinista. | Merged | jvnioo |
| [#114](https://github.com/jvnioo/NutriGraphDT/pull/114) | `feat/83-gnn-overfit-check` | [#83](https://github.com/jvnioo/NutriGraphDT/issues/83) | `test: prueba de sobreajuste de las GNN a un lote sintético pequeño (A41-7)`: compuerta de sanidad. | Merged | jvnioo |
| [#116](https://github.com/jvnioo/NutriGraphDT/pull/116) | `feat/95-prepare-dataloaders` | [#95](https://github.com/jvnioo/NutriGraphDT/issues/95) | `feat: prepare training graphs and subset dataloaders`: construcción de `DataLoader` estratificados. | Merged | jvnioo |
| [#117](https://github.com/jvnioo/NutriGraphDT/pull/117) | `feat/96-train-scaler` | [#96](https://github.com/jvnioo/NutriGraphDT/issues/96) | `feat: escalado de features y target ajustado solo con train`: prevención de fuga de información. | Merged | jvnioo |
| [#120](https://github.com/jvnioo/NutriGraphDT/pull/120) | `refactor/111-prune-unreachable-convs` | [#111](https://github.com/jvnioo/NutriGraphDT/issues/111) | `refactor: no crear convoluciones que no llegan a la lectura`: poda de operaciones inertes en grafo. | Merged | jvnioo |
| [#121](https://github.com/jvnioo/NutriGraphDT/pull/121) | `feat/97-training-loop` | [#97](https://github.com/jvnioo/NutriGraphDT/issues/97) | `feat: bucle de entrenamiento con detención temprana`: ciclo train/val/early stopping. | Merged | jvnioo |
| [#122](https://github.com/jvnioo/NutriGraphDT/pull/122) | `feat/99-run-tracking` | [#99](https://github.com/jvnioo/NutriGraphDT/issues/99) | `feat: trazabilidad de corridas con registro, checkpoint y recarga`: formato canónico `run.json`. | Merged | jvnioo |
| [#123](https://github.com/jvnioo/NutriGraphDT/pull/123) | `fix/119-batch-common-schema` | [#119](https://github.com/jvnioo/NutriGraphDT/issues/119) | `fix: alinear los tipos de nodo y arista antes de agrupar en lotes`: evita desajustes en PyG batching. | Merged | jvnioo |
| [#125](https://github.com/jvnioo/NutriGraphDT/pull/125) | `feat/100-train-gnn-script` | [#100](https://github.com/jvnioo/NutriGraphDT/issues/100) | `feat: script train_gnn.py para entrenar una variante de principio a fin`: CLI principal de F4. | Merged | jvnioo |
| [#126](https://github.com/jvnioo/NutriGraphDT/pull/126) | `docs/119-overfit-figures` | [#119](https://github.com/jvnioo/NutriGraphDT/issues/119) | `docs: regenerar las cifras de la prueba de sobreajuste tras #120 y #123`. | Merged | jvnioo |
| [#128](https://github.com/jvnioo/NutriGraphDT/pull/128) | `feat/103-gnn-synthetic-eval` | [#103](https://github.com/jvnioo/NutriGraphDT/issues/103) | `feat: evaluate GNN variants on the synthetic cohort`: ejecución de las 3 variantes en cohorte sintética. | Merged | jvnioo |
| [#129](https://github.com/jvnioo/NutriGraphDT/pull/129) | `feat/104-gnn-d1-eval` | [#104](https://github.com/jvnioo/NutriGraphDT/issues/104) | `feat(gnn): evaluación de variantes GNN en D1 HoloFood (A45-4)`: corridas sobre descarga completa D1. | Merged | jvnioo |
| [#130](https://github.com/jvnioo/NutriGraphDT/pull/130) | `feat/105-gnn-hparam-seeds` | [#105](https://github.com/jvnioo/NutriGraphDT/issues/105) | `feat(A45-5): bounded hyperparameter search and seed variability`: grilla acotada (32, 64, 128; 1 a 3 capas) y 5 semillas. | Merged | jvnioo |
| [#131](https://github.com/jvnioo/NutriGraphDT/pull/131) | `feat/106-model-comparison` | [#106](https://github.com/jvnioo/NutriGraphDT/issues/106) | `A45-6 — Tabla comparativa GNN vs. baselines para el avance 2`: consolidación de métricas de baselines y GNN. | Merged | jvnioo |
| [#132](https://github.com/jvnioo/NutriGraphDT/pull/132) | `feat/107-gnn-learning-curves` | [#107](https://github.com/jvnioo/NutriGraphDT/issues/107) | `A45-7 — Curvas de aprendizaje y diagnóstico de predicciones`: gráficos predicho vs medido y pérdidas. | Merged | jvnioo |
| [#134](https://github.com/jvnioo/NutriGraphDT/pull/134) | `feat/108-reproduce-run` | [#108](https://github.com/jvnioo/NutriGraphDT/issues/108) | `feat(A45-8): verificar la reproducibilidad de una corrida registrada`: auditoría de reejecución idéntica. | Merged | jvnioo |
| [#188](https://github.com/jvnioo/NutriGraphDT/pull/188) | `fix/133-split-hash-canonical` | [#133](https://github.com/jvnioo/NutriGraphDT/issues/133) | `fix: hash de la partición sobre el JSON canónico, independiente de CRLF/LF`. | Merged | jvnioo |
| [#190](https://github.com/jvnioo/NutriGraphDT/pull/190) | `feat/139-pen-cross-validation` | [#139](https://github.com/jvnioo/NutriGraphDT/issues/139) | `feat: validación cruzada por corral de D1 (StratifiedGroupKFold, k = 5)`: mitigación del sesgo por corral. | Merged | jvnioo |
| [#189](https://github.com/jvnioo/NutriGraphDT/pull/189) | `feat/146-scfa-compositional-target` | [#146](https://github.com/jvnioo/NutriGraphDT/issues/146) | `feat: objetivo composicional de AGCC y métricas de D-03`: log-razones y log T desacoplado. | Merged | jvnioo |
| [#191](https://github.com/jvnioo/NutriGraphDT/pull/191) | `feat/147-host-covariates` | [#147](https://github.com/jvnioo/NutriGraphDT/issues/147) | `feat: covariables del huésped del contrato v2 (ensayo, corral, día, sexo y raza)`. | Merged | jvnioo |
| [#194](https://github.com/jvnioo/NutriGraphDT/pull/194) | `feat/140-baselines-d1-composition` | [#140](https://github.com/jvnioo/NutriGraphDT/issues/140) | `feat: baselines de D1 con objetivo composicional, log T y baseline solo de día`. | Merged | jvnioo |
| [#197](https://github.com/jvnioo/NutriGraphDT/pull/197) | `feat/142-gnn-d1-compositional-eval` | [#142](https://github.com/jvnioo/NutriGraphDT/issues/142) | `feat: reevaluación de las GNN sobre D1 composicional con CV por corral (#142)`. | Merged | jvnioo |

---

## 3. Auditoría de observaciones de revisión y su resolución

Durante el ciclo de integración de las actividades A44, A45 y A52 surgieron observaciones técnicas sustantivas. Se audita su tratamiento:

### Observación 1: La variabilidad por semilla no mide incertidumbre de generalización en test
- **PR afectado:** [#131](https://github.com/jvnioo/NutriGraphDT/pull/131) (A45-6, Tabla comparativa de avance 2).
- **Observación realizada por:** `jvnioo` (Revisión `CHANGES_REQUESTED`).
- **Detalle técnico:** El borrador afirmaba que la diferencia entre GNN y `ridge` (0.18 a 0.26 de RMSE) superaba la variabilidad por semilla medida en A45-5 (0.02 a 0.09). El revisor objetó que esa desviación sólo captura el ruido estocástico del optimizador con los mismos 21 animales de prueba, no la incertidumbre de muestreo poblacional ni la varianza de `ridge`.
- **Acción tomada y responsable:** Sergio-R5 aplicó en commit `db03148` la corrección en `docs/models/gnn-evaluation.md` y `reports/comparison/model_comparison.md`, eliminando la conclusión y declarando la diferencia como **no concluyente**. Se propuso como solución rigurosa el bootstrap por corral y la validación cruzada.
- **Issue derivado:** Derivó en el diseño de validación cruzada por corral ([#139](https://github.com/jvnioo/NutriGraphDT/issues/139)), implementado y cerrado.

### Observación 2: Calificación de F4 como provisional ante la Respuesta de Investigación v1.1
- **PRs afectados:** [#131](https://github.com/jvnioo/NutriGraphDT/pull/131) y [#132](https://github.com/jvnioo/NutriGraphDT/pull/132).
- **Observación realizada por:** `jvnioo`.
- **Detalle técnico:** La Respuesta de Investigación del 16-10-2026 alteró el marco científico: exclusión de animales repetidos (SAMEA112905124, etc.), cohorte oficial en 58 animales, confusión entre dieta y día de muestreo (día 35), y reformulación a objetivo composicional. No correspondía presentar el cumplimiento del Hito F4 como definitivo sobre un único conjunto de prueba estático.
- **Acción tomada y responsable:** Se etiquetó formalmente el criterio como **provisional** en tablas y textos de documentación. Se documentaron las advertencias correspondientes.
- **Issues derivados:** [#138](https://github.com/jvnioo/NutriGraphDT/issues/138) (Cohorte oficial D1 de 58 animales), [#139](https://github.com/jvnioo/NutriGraphDT/issues/139) (Validación cruzada por corral), [#140](https://github.com/jvnioo/NutriGraphDT/issues/140) (Baselines composicionales) y [#142](https://github.com/jvnioo/NutriGraphDT/issues/142) (Reevaluación GNN composicional). Todos integrados y cerrados.

### Observación 3: Declaración de base húmeda en unidades
- **PR afectado:** [#131](https://github.com/jvnioo/NutriGraphDT/pull/131) y [#132](https://github.com/jvnioo/NutriGraphDT/pull/132).
- **Observación realizada por:** `jvnioo`.
- **Detalle técnico:** Indicación explícita de `mmol/kg de digesta fresca (base húmeda)` en cumplimiento de la decisión V-06 de Investigación.
- **Acción tomada y responsable:** Actualizada la rotulación de figuras diagnósticas y reportes Markdown por Bruce Varela y Sergio-R5. Consolidado formalmente en el contrato de datos v2 mediante el Issue [#148](https://github.com/jvnioo/NutriGraphDT/issues/148) (PR [#193](https://github.com/jvnioo/NutriGraphDT/pull/193)).

### Observación 4: Incompatibilidad de fin de línea (CRLF vs. LF) en hash de partición
- **PR afectado:** [#131](https://github.com/jvnioo/NutriGraphDT/pull/131) (Notas de revisión).
- **Detalle técnico:** En Windows, `configs/splits/d1_holofood.json` se clonaba con CRLF, produciendo un SHA-256 de bytes distinto al calculado en entornos Linux (`1ae708...` vs `b6dd7d...`), provocando fallos en la verificación de integridad entre plataformas.
- **Acción tomada y responsable:** Se creó el Issue [#133](https://github.com/jvnioo/NutriGraphDT/issues/133) asignado a Sergio-R5. Resuelto en PR [#188](https://github.com/jvnioo/NutriGraphDT/pull/188), estandarizando el hash sobre el contenido JSON canónico (independiente de saltos de línea).

### Observación 5: Poda de convoluciones desconectadas (dead graph paths)
- **Componente afectado:** `nutrigraphdt.models.gnn.hetero`.
- **Detalle técnico:** En grafos heterogéneos donde ciertos tipos de nodo no poseen aristas hacia el nodo de lectura (`readout`), la instanciación de capas de convolución generaba sobrecosto en GPU/CPU e inconsistencias de gradiente.
- **Acción tomada y responsable:** Registrado en Issue [#111](https://github.com/jvnioo/NutriGraphDT/issues/111), resuelto y verificado por jvnioo en PR [#120](https://github.com/jvnioo/NutriGraphDT/pull/120).

### Observación 6: Reasignación espuria de aristas en batching heterogéneo
- **Componente afectado:** `nutrigraphdt.models.training`.
- **Detalle técnico:** Al agrupar en lotes grafos heterogéneos donde alguna instancia carecía de un tipo particular de arista, `torch_geometric.data.Batch` producía desplazamientos erróneos de punteros de arista.
- **Acción tomada y responsable:** Registrado en Issue [#119](https://github.com/jvnioo/NutriGraphDT/issues/119), resuelto en PR [#123](https://github.com/jvnioo/NutriGraphDT/pull/123) mediante la homogenización previa del esquema con tensores vacíos.

---

## 4. Matriz de trazabilidad con Issues derivados

| Observación / Brecha técnica | Issue original | Issue derivado | Responsable | Estado final |
|---|---|---|---|---|
| Incertidumbre de muestreo por corral y sesgo de partición única | [#106](https://github.com/jvnioo/NutriGraphDT/issues/106) | [#139](https://github.com/jvnioo/NutriGraphDT/issues/139) | Sergio-R5 | Resuelto en PR [#190](https://github.com/jvnioo/NutriGraphDT/pull/190) |
| Cohorte oficial de 58 animales y exclusión de perfiles repetidos | [#106](https://github.com/jvnioo/NutriGraphDT/issues/106) | [#138](https://github.com/jvnioo/NutriGraphDT/issues/138) | jvnioo | Resuelto en PR [#143](https://github.com/jvnioo/NutriGraphDT/pull/143) |
| Reevaluación de baselines en D1 con variable composicional y log T | [#106](https://github.com/jvnioo/NutriGraphDT/issues/106) | [#140](https://github.com/jvnioo/NutriGraphDT/issues/140) | jvnioo | Resuelto en PR [#194](https://github.com/jvnioo/NutriGraphDT/pull/194) |
| Reevaluación de GNN en D1 con objetivo composicional y CV corral | [#106](https://github.com/jvnioo/NutriGraphDT/issues/106) | [#142](https://github.com/jvnioo/NutriGraphDT/issues/142) | jvnioo | Resuelto en PR [#197](https://github.com/jvnioo/NutriGraphDT/pull/197) |
| Determinismo del hash de partición en entornos multiplataforma | [#106](https://github.com/jvnioo/NutriGraphDT/issues/106) | [#133](https://github.com/jvnioo/NutriGraphDT/issues/133) | Sergio-R5 | Resuelto en PR [#188](https://github.com/jvnioo/NutriGraphDT/pull/188) |
| Estandarización de base húmeda, notación de unidades y sample matrix | [#106](https://github.com/jvnioo/NutriGraphDT/issues/106) | [#148](https://github.com/jvnioo/NutriGraphDT/issues/148) | jvnioo, Sergio-R5 | Resuelto en PR [#193](https://github.com/jvnioo/NutriGraphDT/pull/193) |
| Perfilado de cómputo en CPU y filtrado sin fuga de información | A52 | [#160](https://github.com/jvnioo/NutriGraphDT/issues/160) | jvnioo | Asignado para implementación en A52-P2 |
| Demostrador visual interactivo desacoplado del pipeline central | Fuera de tablero | [#127](https://github.com/jvnioo/NutriGraphDT/pull/127) | jvnioo | En revisión individual |

---

## 5. Auditoría de comprobaciones locales y reproducibilidad

Se comprobó que todos los Pull Requests integrados del módulo GNN cuentan con el respaldo de las cuatro herramientas de verificación del repositorio:

```bash
ruff check .            # Calidad de código, importaciones, convenciones
ruff format --check .   # Formateo canónico
mypy src                # Tipado estático estricto
pytest                  # Suites unitarias e integrales
```

En la línea base actual sobre `main`, la totalidad de la suite pasa limpiamente con más de 2200 pruebas unitarias y de integración activas.

---

## 6. Dictamen de la revisión cruzada (A52-P1)

1. **Estado del módulo:** El módulo GNN y su pipeline de entrenamiento presentan una arquitectura coherente, modular y estrictamente desacoplada de la ingesta de datos y de la infraestructura pagada.
2. **Cierre de observaciones:** No existen observaciones técnicas pendientes sin resolver o sin responsable asignado dentro del alcance del módulo GNN. Todas las sugerencias emitidas en las revisiones de las actividades A41, A44 y A45 fueron integradas en el código base o canalizadas mediante los Issues del contrato v2 (#133, #138, #139, #140, #142, #146, #147, #148).
3. **Paso siguiente de A52:** Habilitada la ejecución de la actividad **A52-P2** ([Issue #160](https://github.com/jvnioo/NutriGraphDT/issues/160)) para el perfilado de costos en CPU y evaluación del filtrado de taxones raros ajustado exclusivamente sobre `train`.
