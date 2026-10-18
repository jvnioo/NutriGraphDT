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
- **Modelos**
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
- **Investigación**
  - [Esquema General del proyecto](research/Esquema_General_del_proyecto_Microbioma_Digital.md)
  - [Estudio bibliométrico](<research/Estudio Bibliometrico — PIA Microbioma Digital.md>)
  - [Repositorios y datasets](<research/Repositorios y Datasets — PIA Microbioma Digital.md>)
  - [Respuesta a la solicitud de revisión v1.1 (16-10-2026)](<research/Respuesta de Investigación a la Solicitud de revisión v1.1.md>)
