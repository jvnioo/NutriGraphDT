# Guía de uso del dataset sintético

- **Tarea:** DS-07 — Documentar el dataset y preparar un ejemplo de uso (#8).
- **Versión del esquema:** `1.0.0`. **Versión del generador descrita:** `0.1.0.dev0`.

Esta guía explica cómo generar, exportar, cargar y explorar el dataset sintético con el
código disponible en `nutrigraphdt.data.synthetic`. El contrato de datos está en la
[especificación](synthetic-dataset-spec.md), y los valores concretos de cada campo en el
[diccionario](synthetic-dataset-dictionary.md).

> **Advertencia.** NutriGraphDT es un prototipo académico de factibilidad computacional. El
> dataset sintético sirve para desarrollar y probar el flujo `data -> graph -> models`. No
> sustituye experimentación *in vivo* ni *in vitro*, no es una recomendación nutricional
> comercial y ningún resultado obtenido con él constituye una conclusión biológica.

## Qué está disponible y qué no

| Disponible (DS-02 a DS-06, A35-1) | Aún no implementado |
|---|---|
| Generación determinista de nodos y aristas sintéticas. | Codificación definitiva de features (el prototipo usa `prototype-0.1`, provisional). |
| Escenarios basal e intervenido (`crude_protein` 215 → 270 g/kg). | Partición de datos, normalización y vocabularios versionados. |
| Exportación a JSON Lines + `metadata.json` y carga sin pérdida. | Módulos `models`, `constraints`, `simulation`, `explainability` y `api`. |
| Targets sintéticos de AGCC en `outputs.jsonl` (A35-1). | `README.md` dentro del directorio exportado. |
| Prototipo `HeteroData` y archivos `graphs/*.pt` con `--graphs` ([guía](../graph/heterodata-prototype.md)). | |
| Validación de integridad del contrato al exportar y al cargar, y de los grafos ([reglas](../graph/graph-integrity-rules.md)). | |
| Scripts de generación, exploración y validación. | |

## Tipos de datos: sintéticos, simulados, predichos y observados

El contrato distingue cuatro orígenes de un valor. Este dataset contiene **solo el primero**.

| Tipo | Significado en NutriGraphDT | Presencia en este dataset |
|---|---|---|
| **Sintético** | Valor generado por código a partir de catálogos, semillas y rangos convencionales. | Todo: nodos, aristas, instancias y metadatos. Se identifica con `is_synthetic: true`, `source_id` / `evidence_id` = `SYNTHETIC_V1` y `evidence_status: "synthetic"`. |
| **Simulado** | Resultado de ejecutar un escenario en un módulo de simulación sobre un modelo entrenado. | Ninguno. El escenario intervenido es una **modificación manual** de un valor de entrada. No simula una respuesta del sistema. |
| **Predicho** | Salida de un modelo, con `measured_or_predicted: "predicted"` y `model_version`. | Ninguno. No hay modelos implementados. |
| **Observado / medido** | Dato real con procedencia verificable (`measured`, `observed`, `annotated`). | Ninguno. La validación exige `evidence_status: "synthetic"` en todas las aristas. |

Nombres como `measured_in`, `16S_amplicon` o `cecal_content` pertenecen al vocabulario del
contrato. En este dataset no indican que se haya medido o secuenciado algo.

## Instalación

Requisitos: Git y Python 3.11 o superior. No hace falta GPU, servicios de pago ni
dependencias externas en tiempo de ejecución.

```bash
git clone https://github.com/jvnioo/NutriGraphDT.git
cd NutriGraphDT
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\Activate.ps1   # Windows PowerShell
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Los comandos siguientes se ejecutan desde la raíz del repositorio con el entorno activado.

## Generar el dataset desde la línea de comandos

```bash
# Escenarios basal e intervenido (opción por defecto)
python scripts/generate_synthetic_dataset.py

# Una sola instancia con una semilla propia
python scripts/generate_synthetic_dataset.py --seed 7 --output artifacts/synthetic/seed-7

# Reemplazar un dataset ya exportado
python scripts/generate_synthetic_dataset.py --overwrite
```

| Opción | Efecto |
|---|---|
| `--output DIR` | Directorio de salida; por defecto `artifacts/synthetic/v1`. |
| `--seed N` | Genera una instancia (`synthetic:graph:0001`) con semilla `N` para nodos y aristas, en lugar de los escenarios. |
| `--overwrite` | Permite reemplazar un directorio que ya contiene `metadata.json`. |

Salida esperada con la versión `0.1.0.dev0`:

```text
Dataset sintético exportado en artifacts/synthetic/v1
  instancias: 2  nodos: 64  aristas: 156
```

Con `--seed 7` se obtiene 1 instancia, 32 nodos y 75 aristas. `artifacts/` está en
`.gitignore`: los datasets generados son artefactos locales y no deben subirse al
repositorio.

### Estructura exportada

```text
artifacts/synthetic/v1/
├── metadata.json          # identidad, semilla, configuración efectiva, vocabularios y conteos
└── raw/
    ├── instances.jsonl    # una línea por grafo (instancia)
    ├── nodes.jsonl        # una línea por nodo
    ├── edges.jsonl        # una línea por arista
    └── outputs.jsonl      # targets sintéticos de AGCC (una salida por metabolito objetivo)
```

Con `--graphs` se agrega `graphs/`, con un `.pt` por instancia y su `manifest.json` (ver el
[prototipo HeteroData](../graph/heterodata-prototype.md)).

Los archivos están en UTF-8, con un objeto JSON por línea, fin de línea `\n` en todos los
sistemas operativos, claves ordenadas y registros en el orden determinista de la
especificación. `metadata.json` se escribe al final: si existe, la exportación terminó.

## Cargar y explorar el dataset

### Script de ejemplo

`scripts/explore_synthetic_dataset.py` carga un dataset exportado a través de la interfaz
pública, lo valida y muestra un resumen:

```bash
python scripts/generate_synthetic_dataset.py
python scripts/explore_synthetic_dataset.py
python scripts/explore_synthetic_dataset.py --input artifacts/synthetic/seed-7
```

Salida (abreviada) para los escenarios por defecto:

```text
dataset_id: synthetic-scenarios-v1
schema_version: 1.0.0  generator_version: 0.1.0.dev0
is_synthetic: True  random_seed: 42
instancias: 2  nodos: 64  aristas: 156  salidas: 6

[synthetic:scenario:basal:0001] scenario_id=basal
  diet_treatment: synthetic_basal_diet
  nodos: additive=1, diet=1, function=8, host=1, metabolite=5, phenotype=2, substrate=4, taxon=10
  aristas:
    additive|modulates|function: 1
    ...

Componentes de dieta que difieren entre basal e intervención:
  crude_protein: 215.0 -> 270.0 g/kg [sintético]
```

### Desde Python

Todas las funciones y tipos usados aquí se importan desde `nutrigraphdt.data.synthetic`:

```python
from nutrigraphdt.data.synthetic import export_dataset, generate_scenario_dataset, load_dataset

dataset = generate_scenario_dataset()
root = export_dataset(dataset, "artifacts/synthetic/v1", overwrite=True)

loaded = load_dataset(root)  # valida formato e integridad al cargar
assert loaded == dataset  # round-trip sin pérdida

graph_id = loaded.instances[0].graph_id
taxa = [n for n in loaded.nodes if n.graph_id == graph_id and n.node_type == "taxon"]
has_capacity = [
    e for e in loaded.edges if e.graph_id == graph_id and e.relation_type == "has_capacity"
]
print(sum(n.attributes["abundance"] for n in taxa))  # ≈ 1.0
print(has_capacity[0].to_dict())
```

`SyntheticDataset` expone `metadata` (dict), `instances` (`InstanceRecord`), `nodes`
(`Node`), `edges` (`Edge`) y `outputs` (`OutputRecord`), siempre en el orden determinista de
la especificación. Cada `Edge` expone `edge_type`, la tupla `(origen, relación, destino)`
que usará `HeteroData`. Un dataset puede contener varias instancias, así que conviene filtrar
por `graph_id` antes de construir un grafo.

## Configurar el generador

Una instancia propia se genera con `generate_synthetic_dataset`. Las semillas de nodos y
aristas deben coincidir para que `metadata.json` identifique el dataset con una sola semilla:

```python
from nutrigraphdt.data.synthetic import (
    NodeCountConfig,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    export_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.data.synthetic.edges import (
    SUBSTRATE_AVAILABLE_TO_TAXON,
    TAXON_HAS_CAPACITY_FUNCTION,
)
from nutrigraphdt.data.synthetic.nodes import SyntheticRangeConfig

node_config = SyntheticNodeConfig(
    graph_id="synthetic:graph:0002",
    random_seed=7,
    counts=NodeCountConfig(taxon=20, function=12),
    ranges=SyntheticRangeConfig(substrate_quantity_low=5.0, substrate_quantity_high=80.0),
)
edge_config = SyntheticEdgeConfig(
    random_seed=7,
    relation_probabilities={
        SUBSTRATE_AVAILABLE_TO_TAXON: 0.5,
        TAXON_HAS_CAPACITY_FUNCTION: 0.3,
    },
)
dataset = generate_synthetic_dataset(node_config, edge_config, dataset_id="synthetic-custom")
export_dataset(dataset, "artifacts/synthetic/custom", overwrite=True)
```

| Objeto | Parámetros principales |
|---|---|
| `SyntheticNodeConfig` | `graph_id`, `source_id`, `species`, `gut_segment`, `cohort_id`, `counts`, `random_seed`, `timepoint_days`, `ranges`. |
| `NodeCountConfig` | Número de nodos por tipo (por defecto 1, 1, 4, 10, 8, 5, 1, 2). |
| `SyntheticRangeConfig` | Rangos globales de sustratos, funciones, metabolitos, fenotipos y peso del huésped, y parámetros Gamma de los taxones. |
| `SyntheticEdgeConfig` | `random_seed`, `evidence_id`, `evidence_method`, `relation_probabilities`, `interaction_types`, `non_modulating_control_labels`. |

`relation_probabilities` **reemplaza** por completo los valores por defecto: una relación
que no aparece en el diccionario no se genera. En el ejemplo anterior solo se generan
aristas `available_to` y `has_capacity`.

Los escenarios basal e intervenido no se pueden configurar desde la API pública: usan
valores fijos del módulo `scenarios` (semilla 42 y conteos por defecto).

Cualquier rango o valor configurado sigue siendo una convención sintética. No se debe
presentar como fisiológico sin la revisión científica correspondiente.

## Reproducibilidad

- Con la misma versión del generador, la misma configuración y la misma semilla, el dataset
  exportado es **idéntico byte a byte**. Se verificó exportando dos veces y comparando los
  directorios con `diff -r`, y lo comprueban `tests/unit/test_synthetic_export.py` y
  `tests/integration/test_synthetic_dataset_roundtrip.py`.
- Cada combinación `(semilla, graph_id, tipo de nodo)` y `(semilla, graph_id, relación)` usa
  su propio generador aleatorio sembrado con texto, así que el resultado no depende de
  `PYTHONHASHSEED` ni del orden de entrada de los nodos. En el par de escenarios por defecto,
  el basal se genera primero y el intervenido copia sus nodos y aristas, reasignando su
  `graph_id`; esto conserva una única realización sintética para la comparación.
- `metadata.json` registra la configuración efectiva, la semilla, las versiones y los conteos
  por instancia. Para reproducir un dataset basta con esos metadatos y el commit del código.
- Cambiar `graph_id` cambia los valores aleatorios, porque forma parte de la semilla (ver
  [Limitaciones](#limitaciones)).

## Errores comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `Ya existe un dataset en <dir>. Agrega --overwrite para reemplazarlo.` (script) o `FileExistsError` (API) | El directorio ya contiene `metadata.json`. | Usa `--overwrite` / `overwrite=True`, o elige otro `--output`. |
| `No se pudo leer el dataset: No existe <dir>/metadata.json` (script de exploración) | El dataset no se generó, o la ruta de `--input` es incorrecta. | Ejecuta `python scripts/generate_synthetic_dataset.py` o corrige `--input`. |
| `ModuleNotFoundError: No module named 'nutrigraphdt'` | El paquete no está instalado en el entorno activo. | Activa `.venv` y ejecuta `pip install -e ".[dev]"`. |
| `ValueError: La semilla de nodos y la de aristas deben coincidir…` | `SyntheticNodeConfig.random_seed` ≠ `SyntheticEdgeConfig.random_seed`. | Usa la misma semilla en ambas configuraciones. |
| `ValueError: Relación no permitida por la especificación: …` | `relation_probabilities` contiene una tupla fuera del catálogo de 11 relaciones. | Usa las constantes de `nutrigraphdt.data.synthetic.edges` o `ALLOWED_RELATIONS`. |
| `DatasetFormatError: <archivo>:<línea>: …` | Falta un archivo, hay una línea vacía, JSON inválido, un `NaN`/`Infinity`, un campo con tipo incorrecto o un `schema_version` distinto de `1.0.0`. | Regenera el dataset. No edites los JSONL a mano. |
| `DatasetValidationError: …` | Los archivos se leen pero incumplen el contrato; por ejemplo, `is_synthetic: false` o una arista que apunta a un nodo inexistente. | Regenera el dataset. El mensaje enumera todos los incumplimientos. |

## Limitaciones

Limitaciones científicas:

- **Nada es evidencia.** Los valores, relaciones, densidades de aristas, dosis y rangos son
  convenciones computacionales. Los géneros bacterianos, sustratos y metabolitos reales
  aparecen solo como etiquetas.
- **Unidades nominales.** Con la escala por defecto, los fenotipos toman valores entre 0 y 1
  aunque declaren unidades como `g` o `ug/mL`. No interpretes esos valores en su unidad.
- **Sin efectos modelados.** El par por defecto comparte los nodos, atributos y aristas
  generados; solo cambia `crude_protein` (215 → 270 g/kg) en la composición de la dieta. El
  escenario intervenido no propaga ese cambio a sustratos, taxones ni metabolitos: no existe una
  ecuación bioquímica ni un modelo que lo haga. Por eso los targets AGCC sintéticos quedan
  idénticos entre escenarios; no interpretes esa igualdad como evidencia de ausencia de un
  efecto biológico.
- **Decisiones pendientes de Investigación.** Especie y segmento (`chicken`, `cecum`),
  variable objetivo, ontologías, criterios de evidencia y particiones siguen provisionales
  (§ "Decisiones provisionales pendientes de Investigación" de la
  [especificación](synthetic-dataset-spec.md)).

Limitaciones técnicas:

- La conversión a `HeteroData` es un prototipo con codificación provisional (`prototype-0.1`),
  sin normalización ni categorías codificadas.
- Los targets de `outputs.jsonl` son sintéticos (`synthetic`), y `timepoint` de las instancias
  es `null`.
- El generador estándar no produce valores ausentes (`missing_mask` siempre `{}`), aunque
  el contrato los admite.
