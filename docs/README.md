# Documentación de NutriGraphDT

| Carpeta | Contenido |
|---|---|
| [`process/`](process/) | Forma de trabajo de la Célula de Desarrollo: flujo Scrumban, tablero del proyecto, entorno de desarrollo y política de costos. |
| [`architecture/`](architecture/) | Límites de módulos, dirección de dependencias y diseño del pipeline de datos. |
| [`synthetic-dataset/`](synthetic-dataset/) | Contrato (DS-01), diccionario de datos y guía de uso del dataset sintético. |
| [`data-sources/`](data-sources/) | Fuentes de datos reales: cómo se obtienen, qué contienen y sus cautelas. |
| [`graph/`](graph/) | Esquema y diccionario del grafo, reglas de integridad, constructor, prototipo `HeteroData` y reportes de validación. |
| [`research/`](research/) | Documentos de Investigación: Esquema General del proyecto, estudio bibliométrico y revisión de repositorios y datasets. |

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
  - [Propuesta de evidencia y escenario (reglas 1.2.0, provisional)](graph/evidence-and-scenario-proposal.md)
  - [Guía de validación](graph/graph-validation-usage.md)
  - [Prototipo `HeteroData`](graph/heterodata-prototype.md)
  - [Reporte de validación del prototipo sintético](graph/prototype-validation-report.md)
  - [Constructor desde datos preprocesados](graph/graph-builder.md)
  - [Reporte de validación de los grafos reales](graph/real-graph-validation-report.md)
- **Investigación**
  - [Esquema General del proyecto](research/Esquema_General_del_proyecto_Microbioma_Digital.md)
  - [Estudio bibliométrico](<research/Estudio Bibliometrico — PIA Microbioma Digital.md>)
  - [Repositorios y datasets](<research/Repositorios y Datasets — PIA Microbioma Digital.md>)
