# Revisión de Pull Requests y criterios del módulo de explicabilidad (A60-P5, #167)

Este informe registra la revisión de los Pull Requests del módulo de explicabilidad
(`nutrigraphdt.explainability`), actividad **A60-P5** de la Fase F7
([Issue #167](https://github.com/jvnioo/NutriGraphDT/issues/167)). Contrasta cada PR con su Issue
y con el contrato de explicaciones A55-P3 ([`explanation-contract.md`](explanation-contract.md),
versión `1.0.0`), y deja trazadas las limitaciones que siguen abiertas.

- **Estado del código revisado:** `main` en `df7a66a` (merge de #215).
- **Fuentes:** los PRs, sus commits, reviews y comentarios en GitHub, y el código de `main`. Todo
  identificador citado (PR, commit, función, test) existe en esas fuentes.
- **Alcance:** A60-P1 a A60-P4. Los PRs de A57 (#210, #213) no forman parte del módulo.

---

## 1. Criterios de #167

| Criterio | Estado | Detalle |
|---|---|---|
| Cada PR tiene revisión de otra persona y resultados locales citados | **Parcial** | Los cuatro PRs los revisó y mergeó `jvnioo`, que no es el autor (`WAWARUSA`), y todos citan los checks del estado final. Pero #211 y #212 no tienen una review de GitHub registrada: la revisión consta como commits de corrección y un comentario, no como review `APPROVED` (§3, R-1). |
| No quedan salidas ambiguas ni afirmaciones causales sin sustento | **No cumplido** | Las advertencias `association_not_causation` e `importance_is_not_evidence` son obligatorias (EXP-08). Pero el nombre de la salida explicada es ambiguo en los modelos composicionales (§3, L-2). |
| El resumen final enlaza PR, issues y limitaciones abiertas | Cumplido | §2 y §3. |
| Dependencias A60-P1 a A60-P4 completas | **No cumplido** | #168 (A60-P4) sigue abierto (§3, L-1). |

Por eso este informe **no cierra #167**: se cierra cuando se resuelvan L-1 y L-2 y se actualice
la tabla.

---

## 2. Inventario de Pull Requests

| PR | Issue | Contenido | Correcciones del revisor antes del merge | Review registrada | Checks citados (estado final) | Merge |
|---|---|---|---|---|---|---|
| [#211](https://github.com/jvnioo/NutriGraphDT/pull/211) | [#170](https://github.com/jvnioo/NutriGraphDT/issues/170) (A60-P1, cerrado) | `HeteroExplainer` y adaptador para `HeteroData` (`wrapper.py`). | `8738846`: el wrapper se importa bajo demanda, se restaura el estado del modelo si falla la compatibilidad, y sin `graph_id` o sin `run` con datos reales se lanza `ValueError` en vez de inventar valores. | Solo comentario de `jvnioo` | Comentario del revisor sobre `f003847`: ruff, ruff format, mypy (86 archivos), `pytest -n 6` 2400 passed, 2 skipped | `5da0efc` |
| [#212](https://github.com/jvnioo/NutriGraphDT/pull/212) | [#171](https://github.com/jvnioo/NutriGraphDT/issues/171) (A60-P2, cerrado) | Importancias de nodos, atributos y aristas por tipo (`importance.py`). | `42786fb`: `compute_edge_importance` falla si una arista no inversa no declara evidencia o si un índice no tiene nodo (antes completaba valores). La documentación ahora dice lo que hace el código: un único `norm_factor` por grafo. | Solo comentario de `jvnioo` | Comentario del revisor sobre `42786fb`: ruff, ruff format, mypy (96 archivos), `pytest -n 6` 2469 passed, 2 skipped | `84e0269` |
| [#214](https://github.com/jvnioo/NutriGraphDT/pull/214) | [#169](https://github.com/jvnioo/NutriGraphDT/issues/169) (A60-P3, cerrado) | Subgrafo top-k y serialización JSON (`subgraph.py`). | `4d7edd0`: se retiró la regla `top_k_forward_edges_by_importance` (no existe en el contrato `1.0.0`). La vista ya no rellena importancias con `0.0` y lleva `run`, `explainer` y `scale`. Se corrigió un error de mypy y se revirtió un cambio ajeno en `pyproject.toml`. | `APPROVED` (`jvnioo`) | Cuerpo del PR sobre `4d7edd0`: ruff, ruff format, mypy (97 archivos), `pytest -n 6` 2482 passed, 2 skipped | `54b6dc2` |
| [#215](https://github.com/jvnioo/NutriGraphDT/pull/215) | [#168](https://github.com/jvnioo/NutriGraphDT/issues/168) (A60-P4, **abierto**) | Escenario sintético con ruta plantada (`tests/integration/test_mechanistic_pathway_explainer.py`). | `14f1c94`: los tests pasan a comprobar solo determinismo, que la explicación lista exactamente las aristas del grafo, y contrato y advertencias. Los originales no podían distinguir la ruta del control. Mergeado con `Refs #168`. | `APPROVED` (`jvnioo`) | Cuerpo del PR sobre `14f1c94`: ruff, ruff format, mypy (97 archivos), `pytest -n 6` 2489 passed, 2 skipped | `df7a66a` |

Ninguno de los cuatro PRs se mergeó con el código tal como lo envió su autor: todos recibieron
correcciones del revisor. Los detalles están en los comentarios y reviews de cada PR.

---

## 3. Observaciones y limitaciones abiertas

### L-1 · La recuperación de una ruta plantada no está demostrada (#168)

- **Origen:** revisión de #215; detalle en el
  [comentario de #168](https://github.com/jvnioo/NutriGraphDT/issues/168#issuecomment-6486821898)
  y en §7 de [`explainer-wrapper-compatibility.md`](explainer-wrapper-compatibility.md).
- **Qué pasa:** el criterio "los tests distinguen la ruta plantada del control negativo con
  criterios definidos previamente" no se cumple. En una exploración durante la revisión,
  `GNNExplainer` con su configuración por omisión dio la misma diferencia de importancia entre la
  ruta y los distractores para un modelo entrenado y para uno con targets permutados.
- **Consecuencia:** ninguna explicación del módulo debe presentarse como evidencia de que el
  explicador identifica rutas, ni siquiera en datos sintéticos.
- **Responsable:** Desarrollo, en #168. Falta fijar de antemano escenario, explicador,
  coeficientes y umbral.

### L-2 · Nombre de la salida explicada en modelos composicionales

- **Origen:** pregunta abierta del comentario de revisión de #211; confirmada en C-04 de la
  respuesta de Investigación ([#217](https://github.com/jvnioo/NutriGraphDT/pull/217)).
- **Qué pasa:** `SCFAGraphModel.target_names` vale `("acetate", "propionate", "butyrate")`
  (`DEFAULT_SCFA_TARGETS`). En cambio, el entrenamiento composicional
  (`models/training/compositional.py`) interpreta las columnas como `MODEL_OUTPUT_NAMES`
  `(z1, z2, ln T)`. `HeteroExplainer._resolve_target` toma `model.target_names`, así que
  `target="butyrate"` explica la columna 2 (ln T) y la registra como `butyrate` en
  `target.output`.
- **Consecuencia:** la salida queda ambigua (criterio 2 de #167).
- **Responsable:** Desarrollo; falta abrir el Issue de corrección, citando C-04.

### L-3 · Nombres de atributos sin `node_feature_names`

- **Origen:** comentario de revisión de #212.
- **Qué pasa:** el contrato pide que `attribute` sea el nombre de la columna en
  `node_feature_schema`. Ese esquema no viaja en el `HeteroData`, así que sin
  `node_feature_names` los atributos salen como `<tipo>_col_<j>`.
- **Consecuencia:** la explicación es válida, pero un lector no puede interpretar los atributos.
  `scripts/explain_synthetic.py` podría pasar los nombres desde los metadatos del dataset.

### L-4 · Relaciones inversas en el top-k

- **Origen:** revisión de #214; pregunta abierta en §10 de
  [`explainer-wrapper-compatibility.md`](explainer-wrapper-compatibility.md).
- **Qué pasa:** en el contrato `1.0.0` las relaciones `rev_*` compiten en el top-k. Excluirlas
  para la visualización exige una regla de `selection` nueva y, por §5 del contrato, una versión
  mayor. Se decide con Investigación en [#158](https://github.com/jvnioo/NutriGraphDT/issues/158).

### R-1 · Review formal ausente en #211 y #212

- **Qué pasa:** la revisión de estos PRs consta como commits de corrección del revisor y un
  comentario con los checks, pero no como review `APPROVED` en GitHub. AGENTS.md y
  [`workflow.md`](../process/workflow.md) piden una review aprobatoria de alguien distinto del
  autor antes del merge.
- **Acción:** no se puede registrar a posteriori sobre un PR ya mergeado. Queda constancia aquí.
  En los PRs siguientes (#214, #215) se registró la review.

---

## 4. Verificación de este informe

El PR de este informe solo cambia documentación (`docs/models/explainability-pr-cross-review.md`
y `docs/README.md`). Los checks locales sobre el estado final de su rama están citados en el PR.
