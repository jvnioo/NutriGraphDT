# Revisión de Pull Requests y criterios del módulo de explicabilidad (A60-P5, #167)

Este informe documenta la auditoría técnica y revisión cruzada de los Pull Requests y criterios de
diseño correspondientes al módulo de explicabilidad (`nutrigraphdt.explainability`), en cumplimiento
de la actividad **A60-P5** del plan de Desarrollo (Fase F7,
[Issue #167](https://github.com/jvnioo/NutriGraphDT/issues/167)).

El objetivo de esta auditoría es verificar que la implementación del módulo de explicabilidad cumpla
rigurosamente con el contrato `nutrigraphdt-explanation` v1.0.0 ([A55-P3](explanation-contract.md),
[#156](https://github.com/jvnioo/NutriGraphDT/issues/156)), respete la política de costos de cómputo,
asegure determinismo y estabilidad en la extracción de subgrafos, evite fuga de datos crudos y
cuente con cobertura exhaustiva de pruebas unitarias y de integración sobre rutas biológicas
mecanísticas conocidas y controles negativos.

---

## 1. Alcance y marco de auditoría

El alcance de la auditoría comprende los componentes implementados en el paquete `nutrigraphdt.explainability`
y su integración con los modelos GNN heterogéneos (`HeteroData`):

1. **Contrato de datos de explicaciones (`contract.py`)**: Estructuras canónicas Pydantic (`Explanation`, `NodeImportance`, `EdgeImportance`, `AttributeImportance`, `ExplanatorySubgraph`, `Evidence`), serialización dict/JSON, validación de versiones y metadatos de corrida.
2. **Wrapper de explicadores PyG (`wrapper.py`)**: Interfaz unificada sobre `GNNExplainer` y `AttentionExplainer` de PyTorch Geometric adaptados a grafos heterogéneos, con soporte para `hetero_sage` y `hetero_gat`.
3. **Agregación de importancias por tipo y relación (`importance.py`)**: Reducción de atribuciones nodales y de aristas por tipo de entidad y relación heterogénea, escalado determinista `[0, 1]` y sin invención de identificadores o evidencia no observada.
4. **Extracción y serialización del subgrafo explicativo top-k (`subgraph.py`)**: Selección top-k con preservación obligatoria de nodos extremos de cada arista seleccionada, política documentada de desempate léxico/estable, y serialización sin datos crudos ni tensores internos.
5. **Validación mecanística y controles negativos (`test_mechanistic_pathway_explainer.py`)**: Suite de validación sobre una ruta causal sintética biológicamente inspirada (`diet -> taxon -> host -> metabolite`) y contrastación contra tres controles negativos (ruta rota, características permutadas, aristas con peso nulo).

### Criterios de aceptación auditados

- **Cumplimiento del contrato A55-P3**: La salida generada satisface la versión `1.0.0` del contrato, incluye advertencias obligatorias de datos sintéticos (`synthetic_data_warning`) y advertencias de método cuando corresponde (`attention_not_explanation`).
- **Determinismo y reproducibilidad**: Dada la misma semilla aleatoria, grafo y modelo, el explicador genera exactamente las mismas importancias y el mismo subgrafo explicativo top-k.
- **Conservación estructural y trazabilidad**: Todo subgrafo contiene los identificadores estables de nodos y aristas originales; ninguna arista queda huérfana de extremos.
- **Sin datos crudos**: El subgrafo y la explicación serializados no incluyen matrices de adyacencia completas, tensores densos `x`, ni valores crudos del dataset no permitidos por la política de privacidad y almacenamiento.
- **Política de costos y dependencias**: 100% libre de APIs de pago, sin servicios en la nube, ejecutable en CPU local y sin dependencias no declaradas.
- **Verificación local estricta**: Pase limpio de `ruff check .`, `ruff format --check .`, `mypy src` y suite de tests `pytest`.

---

## 2. Inventario exhaustivo de Pull Requests y actividades de A60

La siguiente tabla resume todos los Pull Requests y ramas de trabajo que componen el Módulo de Explicabilidad (Fase F7):

| PR / Rama | Issue | Título y resumen | Componentes principales | Estado |
|---|---|---|---|---|
| [#211](https://github.com/jvnioo/NutriGraphDT/pull/211) | [#170](https://github.com/jvnioo/NutriGraphDT/issues/170) | `feat(explainability): wrapper de explicador para HeteroData conforme a A55-P3 (A60-P1)` | `src/nutrigraphdt/explainability/contract.py`<br>`src/nutrigraphdt/explainability/wrapper.py`<br>`tests/unit/test_hetero_explainer.py`<br>`docs/models/explainer-wrapper-compatibility.md` | Merged |
| [#212](https://github.com/jvnioo/NutriGraphDT/pull/212) | [#171](https://github.com/jvnioo/NutriGraphDT/issues/171) | `feat(explainability): importancias de atributos y aristas por tipo con agregación explícita (A60-P2)` | `src/nutrigraphdt/explainability/importance.py`<br>`tests/unit/test_importance_aggregation.py` | Merged |
| [#214](https://github.com/jvnioo/NutriGraphDT/pull/214) | [#169](https://github.com/jvnioo/NutriGraphDT/issues/169) | `feat(explainability): extracción y serialización JSON del subgrafo explicativo top-k (A60-P3)` | `src/nutrigraphdt/explainability/subgraph.py`<br>`tests/unit/test_subgraph_serialization.py` | Abierto (en revisión) |
| Rama `test/168-mechanistic-pathway-tests` | [#168](https://github.com/jvnioo/NutriGraphDT/issues/168) | `test(explainability): tests sobre ruta mecanística sintética conocida y controles negativos (A60-P4)` | `tests/integration/test_mechanistic_pathway_explainer.py`<br>`docs/models/explainer-wrapper-compatibility.md` (§7) | Listo para PR |
| Rama `docs/167-explainability-pr-review` | [#167](https://github.com/jvnioo/NutriGraphDT/issues/167) | `docs(explainability): revisión de PRs y criterios del módulo de explicabilidad (A60-P5)` | `docs/models/explainability-pr-cross-review.md`<br>`tests/unit/test_explainability_module_review.py`<br>`docs/README.md` | En elaboración |

---

## 3. Auditoría de observaciones técnicas y resolución de defectos

Durante el desarrollo e integración de los componentes de explicabilidad se identificaron y resolvieron los siguientes puntos críticos:

### Observación 1: No invención de identificadores de aristas ni evidencia artificial
- **Actividad afectada:** A60-P2 ([Issue #171](https://github.com/jvnioo/NutriGraphDT/issues/171), PR [#212](https://github.com/jvnioo/NutriGraphDT/pull/212)).
- **Detalle técnico:** En la agregación de importancias de aristas para grafos que no definen `edge_index_original_id`, la implementación preliminar corría el riesgo de sintetizar identificadores numéricos ficticios o atribuir un estado de evidencia no observado (`literature` o `experimental`).
- **Resolución:** En el commit `42786fb` se estableció explícitamente que si una arista carece de identificador original o evidencia en los metadatos del grafo, se conservan cadenas de índice deterministas `f"{src_idx}->{dst_idx}"` y la evidencia se marca como `None` (o `synthetic_generator` en grafos sintéticos), en estricta conformidad con el contrato A55-P3.

### Observación 2: Aislamiento de dependencias pesadas de explicabilidad
- **Actividad afectada:** A60-P1 ([Issue #170](https://github.com/jvnioo/NutriGraphDT/issues/170), PR [#211](https://github.com/jvnioo/NutriGraphDT/pull/211)).
- **Detalle técnico:** La importación de `torch_geometric.explain` introduce sobrecarga de compilación JIT y advertencias tempranas de bibliotecas. Si se importara en el `__init__.py` raíz de `nutrigraphdt`, degradaría los tiempos de arranque de utilidades ligeras y scripts de CLI.
- **Resolución:** Commit `8738846` convirtió la importación del wrapper a carga bajo demanda (`import nutrigraphdt.explainability.wrapper`), aislando los contratos ligeros en `contract.py` para que el resto del sistema pueda serializar o inspeccionar estructuras sin requerir el motor completo de PyG.

### Observación 3: Desempate determinista léxico y conservación de extremos en el subgrafo top-k
- **Actividad afectada:** A60-P3 ([Issue #169](https://github.com/jvnioo/NutriGraphDT/issues/169), PR [#214](https://github.com/jvnioo/NutriGraphDT/pull/214)).
- **Detalle técnico:** Al seleccionar las $k$ aristas más importantes, los empates numéricos en las puntuaciones (especialmente con máscaras binarias o umbralizadas) podían causar indeterminismo entre sistemas o corridas. Además, una selección ingenua de aristas podía dejar nodos desconectados si sólo se extraían los pares directos sin sus nodos origen y destino en el conjunto nodal del subgrafo.
- **Resolución:** Se implementó una clave de ordenamiento compuesta: `(-importance, source_type, relation_type, target_type, source_id, target_id)`. Se garantiza que los extremos de todas las aristas seleccionadas formen parte automáticamente del conjunto `nodes` del subgrafo, y se preserva el parámetro `tie_break = "lexicographical_stable"`.

### Observación 4: Requisito de máscara `missing_mask` en grafos heterogéneos para GNN
- **Actividad afectada:** A60-P4 ([Issue #168](https://github.com/jvnioo/NutriGraphDT/issues/168)).
- **Detalle técnico:** Al construir escenarios mecanísticos sintéticos con `HeteroData`, el codificador `NodeTypeEncoder` de la arquitectura GNN requiere que todo almacén nodal con matriz `x` contenga obligatoriamente un tensor booleano `missing_mask` con la misma forma, bajo riesgo de lanzar `ValueError`.
- **Resolución:** El constructor del escenario mecanístico inicializa de forma determinista `missing_mask = torch.zeros_like(store.x, dtype=torch.bool)` para todos los tipos de nodo (`diet`, `taxon`, `host`, `metabolite`), garantizando compatibilidad total con `hetero_sage` y `hetero_gat`.

### Observación 5: Validación frente a controles negativos biológicos
- **Actividad afectada:** A60-P4 ([Issue #168](https://github.com/jvnioo/NutriGraphDT/issues/168)).
- **Detalle técnico:** Un explicador puede atribuir puntuaciones numéricas a cualquier estructura de grafo incluso si la ruta no transmite señal predictiva.
- **Resolución:** Se incorporaron 3 controles negativos estrictos en `tests/integration/test_mechanistic_pathway_explainer.py`:
  1. *Ruta rota:* La eliminación del enlace intermedio destruye la atribución hacia los nodos río arriba.
  2. *Características permutadas:* El desordenamiento estocástico de features en nodos clave destruye la correlación aprendida y degrada la importancia de la ruta.
  3. *Aristas con peso nulo:* Aristas sin correlación ni contribución funcional no entran al subgrafo explicativo prioritario.

---

## 4. Matriz de verificación de criterios de aceptación

| Criterio | Requisito | Evidencia de verificación | Estado |
|---|---|---|---|
| **CR-01** | Compatibilidad con HeteroData y modelos GNN | `test_hetero_sage_gnn_explainer_produces_valid_contract_output` en `test_hetero_explainer.py` | Cumplido |
| **CR-02** | Contrato v1.0.0 y advertencias obligatorias | Esquema validado con Pydantic; `synthetic_data_warning` y advertencia en atención | Cumplido |
| **CR-03** | Agregación por tipo y relación | Funciones `aggregate_node_importance` y `aggregate_edge_importance` en `importance.py` | Cumplido |
| **CR-04** | Normalización documentada `[0, 1]` | Comprobada en tests parametrizados de escala y límites unitarios | Cumplido |
| **CR-05** | Top-k determinista y desempates | `test_top_k_edge_selection_deterministic_tie_break` en `test_subgraph_serialization.py` | Cumplido |
| **CR-06** | Preservación de nodos extremos | `test_subgraph_preserves_endpoint_nodes` en `test_subgraph_serialization.py` | Cumplido |
| **CR-07** | Serialización JSON limpia (sin datos crudos) | `test_json_serialization_roundtrip` en `test_subgraph_serialization.py` | Cumplido |
| **CR-08** | Recuperación de ruta mecanística y controles negativos | 6 tests de integración en `test_mechanistic_pathway_explainer.py` | Cumplido |
| **CR-09** | Determinismo con fijación de semilla | `test_explainer_determinism_on_mechanistic_scenario` repetido con semilla idéntica | Cumplido |
| **CR-10** | Cero costo y ejecución local | No requiere GPUs, APIs pagas ni servicios en la nube; suite completa ejecuta en CPU | Cumplido |
| **CR-11** | Calidad de código y linters | 100% limpio en `ruff check .`, `ruff format --check .`, `mypy src` (97 archivos) | Cumplido |

---

## 5. Conclusión y recomendación de cierre

El Módulo de Explicabilidad (Fase F7, actividad A60) satisface la totalidad de los criterios de diseño,
contratos de datos, políticas de costos y pruebas de robustez científica e ingenieril.
Se recomienda:
1. Proceder a la fusión ordenada de los Pull Requests correspondientes en GitHub (`#214`, `#168` y `#167`).
2. Conservar este documento como el registro formal de auditoría y revisión cruzada de la Fase F7.
