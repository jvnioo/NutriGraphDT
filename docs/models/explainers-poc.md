# Prueba de concepto de explicadores de PyG sobre las GNN heterogéneas (A55-P2, #157)

Exploración acotada para saber qué explicadores de `torch_geometric.explain` funcionan sobre
`HeteroData` con las tres variantes (`homo_sage`, `hetero_sage`, `hetero_gat`). **No es
arquitectura estable**: todo el código vive en `scripts/explainers_poc.py`. El wrapper estable
es #170, y el formato de salida de una explicación es el contrato de #156.

## Cómo reproducirla

```bash
pip install -e ".[dev,graph]"          # captum es opcional: ".[dev,graph,explain]"
python scripts/explainers_poc.py       # escribe reports/explainability/explainers_poc.{json,md}
```

El reporte [`reports/explainability/explainers_poc.md`](../../reports/explainability/explainers_poc.md)
registra las versiones, la configuración y, por variante y método, el estado, la forma de las
máscaras, los valores no nulos y el error textual. Sin `captum`, los métodos de Captum quedan como
`not_available`. La prueba `tests/integration/test_explainers_poc.py` lo ejecuta con 3 épocas.

## Qué se explica

- **Datos:** la primera instancia del generador sintético (`synthetic:graph:0001`). Son datos
  sintéticos y se declaran como tales.
- **Modelo:** cada variante **sin entrenar**, con pesos iniciales de semilla fija (157). Se
  construye un modelo nuevo para cada método. El objetivo es la compatibilidad técnica; los
  valores de importancia no significan nada.
- **Salida:** la columna `butyrate` de la predicción `[1, 3]`. PyG exige una sola salida en
  regresión (`mode = regression`, `task_level = graph`, `return_type = raw`, `index = 0`).

### Adaptador

Los explicadores llaman al modelo como `model(x_dict, edge_index_dict)`, pero los modelos del
proyecto reciben un `HeteroData`. `HeteroAdapter` reconstruye el grafo y devuelve una sola salida.
Dos decisiones:

- Los tipos de nodo sin columnas (`metabolite`, `phenotype`) no se pasan al explicador, porque una
  máscara sobre una `x` de ancho 0 no recibe gradiente. Se toman del grafo de plantilla, igual que
  `missing_mask`.
- Solo se explican las tripletas que reciben convolución en alguna capa (`layer_edge_types`). En el
  grafo sintético se omiten `host|exhibits|phenotype` y `metabolite|associated_with|phenotype`. El
  script verifica que quitarlas no cambia la predicción. Si se incluyen, `GNNExplainer` falla
  porque sus máscaras no reciben gradiente.

### Comprobaciones contra resultados silenciosos

Un explicador puede devolver una máscara de aristas con valores aunque el modelo nunca la use. Por
eso, antes de aceptar una máscara de aristas, el script mide:

1. cuántas capas `MessagePassing` la reciben (`set_hetero_masks`); y
2. si la predicción cambia al pasar todas las máscaras de 1 a 0.

Si alguna de las dos es cero, el resultado se marca `invalid`, no `ok`.

## Resultados

Ejecución con torch 2.14.1, torch_geometric 2.8.1, captum 0.9.0 y 30 épocas por explicador.

| Método | Máscaras pedidas | `homo_sage` | `hetero_sage` | `hetero_gat` |
|---|---|---|---|---|
| `GNNExplainer` | atributos + aristas | error | ok | ok |
| `GNNExplainer` | atributos | ok | ok | ok |
| `GNNExplainer` | nodos | ok | ok | ok |
| `CaptumExplainer("IntegratedGradients")` | atributos + aristas | error | ok | ok |
| `CaptumExplainer("Saliency")` | atributos | ok | ok | ok |
| `AttentionExplainer` | aristas | error | invalid | ok |
| `PGExplainer` (fenómeno) | aristas | **invalid** | ok | ok |

**Ruta compatible.** `GNNExplainer` con máscaras de atributos y de aristas sobre `hetero_sage` y
`hetero_gat`. No necesita dependencias adicionales y entrega las tres granularidades:

- atributos, `[nodos, columnas]` por tipo de nodo;
- nodos, `[nodos, 1]`, o la suma por fila de la de atributos;
- aristas, `[aristas]` por tripleta.

Con `captum`, `IntegratedGradients` es una alternativa basada en gradientes con las mismas
máscaras.

**Incompatibilidades, con evidencia.**

- **Máscaras de aristas en `homo_sage`.** `homo_sage` convierte el grafo a homogéneo dentro de
  `convolve`, así que las máscaras por tipo de arista no llegan a ninguna capa (0 capas; la
  predicción no cambia).
  - `GNNExplainer` e `IntegratedGradients` fallan de forma explícita.
  - `PGExplainer` **sí devuelve valores** (68 de 91 aristas no nulas), pero no explican nada. Es el
    caso que motivó la comprobación de alcance.
  - En esta variante solo valen las máscaras de nodos y de atributos.
- **`AttentionExplainer`** necesita capas de atención. Funciona solo en `hetero_gat`. En
  `hetero_sage` no devuelve máscara y en `homo_sage` falla. Además, **los pesos de atención no se
  interpretan como explicación por omisión**.
- **Estado compartido entre métodos.** Tras ejecutar `GNNExplainer` con máscaras de aristas,
  `CaptumExplainer` falla sobre el mismo objeto de modelo ("differentiated Tensor ... not used"),
  aunque `clear_masks` deja `explain` y las máscaras en su estado inicial. No se determinó la causa;
  por eso el script construye un modelo nuevo por método. #170 debería hacer lo mismo o investigarlo.

## Advertencias

- La importancia que asigna un explicador mide **asociación dentro del modelo, no causalidad**, y
  no es evidencia del dominio. La evidencia de una arista (`method_status`, referencias) se
  reporta por separado, según el contrato de #156.
- Modelos sin entrenar y datos sintéticos: este reporte no se debe citar como resultado
  biológico.
- Los explicadores son estocásticos (`GNNExplainer`, `PGExplainer`); se fija la semilla, pero un
  cambio de versión de PyG puede cambiar los valores.

## Preguntas abiertas para #170

- Cuántas épocas de `GNNExplainer` y qué regularización usar con un modelo entrenado. Hay que
  medirlo; aquí no se fijó ningún valor.
- Si `homo_sage` se explica solo con nodos y atributos, o si se le agrega soporte de máscaras de
  aristas.
- Si `captum` pasa a ser una dependencia del wrapper o sigue como extra opcional.
