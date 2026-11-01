# Documentación de NutriGraphDT

| Carpeta | Contenido |
|---|---|
| [`process/`](process/) | Forma de trabajo de la Célula de Desarrollo: flujo Scrumban, tablero del proyecto, entorno de desarrollo y política de costos. |
| [`architecture/`](architecture/) | Límites de módulos, dirección de dependencias y diseño del pipeline de datos. |
| [`synthetic-dataset/`](synthetic-dataset/) | Contrato (DS-01), diccionario de datos y guía de uso del dataset sintético. |
| [`data-sources/`](data-sources/) | Fuentes de datos reales: cómo se obtienen, qué contienen y sus cautelas. |
| [`graph/`](graph/) | Esquema y diccionario del grafo, reglas de integridad, constructor, prototipo `HeteroData` y reportes de validación. |
| [`models/`](models/) | Partición, tabla de atributos, métricas, baselines y diseño de la GNN. |
| [`research/`](research/) | Documentos de Investigación: Esquema General del proyecto, estudio bibliométrico, revisión de repositorios y datasets, y respuestas a las solicitudes de Desarrollo. |

## Índice

- **Demo**
  - [Demo de avance en Streamlit](demo.md)
- **Proceso**
  - [Flujo de trabajo](process/workflow.md)
  - [Guía del GitHub Project](process/project-board-guide.md)
  - [Entorno de desarrollo](process/development.md)
  - [Política de costos](process/cost-policy.md)
- **Arquitectura**
  - [Arquitectura](architecture/architecture.md)
  - [Diseño del pipeline de datos](architecture/data-pipeline-design.md)
- **Dataset sintético**
  - [Especificación (DS-01)](synthetic-dataset/synthetic-dataset-spec.md)
  - [Diccionario de datos](synthetic-dataset/synthetic-dataset-dictionary.md)
  - [Guía de uso](synthetic-dataset/synthetic-dataset-usage.md)
- **Fuentes reales**
  - [D1 HoloFood (pollo)](data-sources/holofood-source.md)
- **Grafo**
  - [Esquema v1](graph/graph-schema-v1.md)
  - [Diccionario de datos del grafo](graph/graph-data-dictionary.md)
  - [Reglas de integridad](graph/graph-integrity-rules.md)
  - [Propuesta de evidencia y escenario (reglas 1.2.0; contrastada por Investigación)](graph/evidence-and-scenario-proposal.md)
  - [Guía de validación](graph/graph-validation-usage.md)
  - [Prototipo `HeteroData`](graph/heterodata-prototype.md)
  - [Reporte de validación del prototipo sintético](graph/prototype-validation-report.md)
  - [Constructor desde datos preprocesados](graph/graph-builder.md)
  - [Reporte de validación de los grafos reales](graph/real-graph-validation-report.md)
  - [Contrato de datos v2 (aprobado por Investigación el 25-10-2026)](graph/data-contract-v2.md)
- **Modelos**
  - [Interfaz de restricciones y registro de violaciones (A57-P1, #163)](models/constraints.md)
  - [Revisión cruzada de PRs del módulo de restricciones (A57-P6, #165)](models/constraints-pr-cross-review.md)
  - [Tabla de atributos (A40-3)](models/tabular-features.md)
  - [Métricas de evaluación (A40-2)](models/metrics.md)
  - [Baselines no basados en grafos (A40-4, A40-5)](models/baselines.md)
  - [Diseño de la arquitectura GNN (A41-1)](models/gnn-architecture.md)
  - [Componentes compartidos de las GNN (A41-5)](models/gnn-components.md)
  - [GNN homogénea de referencia `homo_sage` (A41-2)](models/gnn-homo-sage.md)
  - [Prueba de sobreajuste de las GNN (A41-7)](models/gnn-overfit-check.md)
  - [Pipeline de entrenamiento GNN y `train_gnn.py` (A44-1, A44-3 a A44-6)](models/gnn-training.md)
  - [Escalado de features y targets (A44-2)](models/gnn-scaling.md)
  - [Búsqueda de hiperparámetros y variabilidad por semilla (A45-5)](models/gnn-tuning.md)
  - [Comparación GNN frente a baselines y curvas de aprendizaje (A45-6, A45-7)](models/gnn-evaluation.md)
  - [Validación cruzada por corral de D1 (D-07, #139)](models/cross-validation.md)
  - [Baselines de D1 con objetivo composicional y CV por corral (#140)](models/baselines-d1-composition.md)
  - [GNN de D1 con objetivo composicional y CV por corral (#142)](models/gnn-d1-composition.md)
  - [Revisión cruzada de PRs del módulo GNN (A52-P1, #159)](models/gnn-pr-cross-review.md)
  - [Perfilado de entrenamiento en CPU y filtrado de taxones raros (A52-P2, #160)](models/gnn-cpu-profiling.md)
  - [Cobertura de tests de modelos y del pipeline de entrenamiento (A52-P3, #154)](models/gnn-test-coverage.md)
  - [Protocolo de evaluación con/sin restricciones y criterios de aceptación (A55-P1, #155)](models/constraints-evaluation-protocol.md)
  - [Contrato de salida de las explicaciones (A55-P3, #156)](models/explanation-contract.md)
  - [Prueba de concepto de explicadores de PyG sobre las GNN heterogéneas (A55-P2, #157)](models/explainers-poc.md)
  - [Revisión cruzada del protocolo y del contrato de explicaciones con Investigación (A55-P4, #158)](models/explanations-protocol-review.md)
  - [Wrapper de explicadores para HeteroData y compatibilidad (A60-P1, #170)](models/explainer-wrapper-compatibility.md)
  - [Revisión de Pull Requests y criterios del módulo de explicabilidad (A60-P5, #167)](models/explainability-pr-cross-review.md)
- **Investigación**
  - [Esquema General del proyecto](research/Esquema_General_del_proyecto_Microbioma_Digital.md)
  - [Estudio bibliométrico](<research/Estudio Bibliometrico — PIA Microbioma Digital.md>)
  - [Repositorios y datasets](<research/Repositorios y Datasets — PIA Microbioma Digital.md>)
  - [Respuesta a la solicitud de revisión v1.1 (16-10-2026)](<research/Respuesta de Investigación a la Solicitud de revisión v1.1.md>)
  - [Respuesta a la respuesta de Desarrollo (25-10-2026)](<research/Respuesta de Investigación a la Respuesta de Desarrollo.md>)
  - [D-06 · Restricciones bioquímicas para D1 (29-10-2026)](<research/D-06 — Restricciones bioquímicas para D1.md>)
