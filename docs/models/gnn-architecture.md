# Diseño de la arquitectura GNN (A41-1)

Documento de diseño de A41-1 (#77). Fija las decisiones que comparten las tres variantes de GNN
de la actividad 41, para que difieran solo en la convolución y se comparen entre sí y con los
baselines de A40 en igualdad de condiciones. Lo implementan:

| Issue | Componente |
|---|---|
| A41-5 (#81) | Encoders por tipo de nodo, lectura por grafo y cabeza de regresión |
| A41-2 (#78) | `homo_sage`: GraphSAGE homogénea de referencia |
| A41-3 (#79) | `hetero_sage`: GraphSAGE heterogénea (`HeteroConv` + `SAGEConv`) |
| A41-4 (#80) | `hetero_gat`: variante heterogénea con atención (`HeteroConv` + `GATConv`) |
| A41-6 (#82) | Tests tensoriales de las tres variantes |
| A41-7 (#83) | Prueba de sobreajuste a un lote sintético pequeño |
| A41-8 (#84) | Configuración YAML y fábrica `build_model` |

> **Alcance.** Son decisiones de ingeniería para un primer modelo comparable, no una elección
> científica de la familia de GNN: [architecture.md](../architecture/architecture.md) deja esa
> elección a la evaluación comparativa. Los hiperparámetros son valores iniciales para que las
> variantes arranquen igual; su ajuste es parte del pipeline de entrenamiento (act. 44).

## 1. Punto de partida

Lo que entregan las actividades anteriores y condiciona el diseño:

- **Un `HeteroData` por instancia.** El constructor (A39-1, [graph-builder.md](../graph/graph-builder.md))
  y el prototipo sintético ([heterodata-prototype.md](../graph/heterodata-prototype.md)) generan
  un grafo por animal o muestra, con `x` y `missing_mask` por tipo de nodo, y los AGCC en
  `data["metabolite"].y` (`[N_metabolite, 1]`) con `y_mask`.
- **Los grafos reales de D1 no tienen la ruta mecanística.** En HoloFood los 1315 nodos `taxon`
  y el nodo `diet` no tienen aristas: la fuente no declara taxón → función → metabolito ni
  dieta → sustrato. La única relación es `metabolite → measured_in → host`
  ([real-graph-validation-report.md](../graph/real-graph-validation-report.md)). El dataset
  sintético sí contiene las once tripletas del [esquema v1](../graph/graph-schema-v1.md).
- **Algunos tipos no tienen columnas.** En D1, `diet` y `metabolite` tienen `x` de forma
  `[N, 0]`; en el sintético, `metabolite` y `phenotype`.
- **La comparación es por muestra.** La partición de A40-1 agrupa por corral (`pen_code`) en D1 y
  por muestra en el sintético; la tabla de A40-3 tiene una fila por muestra con tres columnas
  objetivo; las métricas de A40-2 reciben matrices `[N, 3]` en el orden
  `DEFAULT_SCFA_TARGETS = ("acetate", "propionate", "butyrate")`.

## 2. Nivel de predicción: por grafo

**Decisión:** la GNN predice **un vector de tres AGCC por grafo** (por animal o muestra), con
lectura (*pooling*) por tipo de nodo. No predice por nodo `metabolite`.

Razones:

1. **La predicción por nodo no ve la microbiota en D1.** Con paso de mensajes, un nodo
   `metabolite` solo recibe información de sus vecinos. En D1 su único vecino es el huésped, y
   los taxones están aislados: las abundancias nunca llegarían a los AGCC, sin importar el
   número de capas. Con lectura por grafo, la representación de cada taxón (su encoder y, si
   tiene aristas, sus vecinos) entra en la predicción aunque esté aislado.
2. **Es la misma unidad que los baselines.** A40-3 y A40-4/5 predicen una fila de tres AGCC por
   muestra, y la partición de A40-1 asigna muestras completas a cada subconjunto. Una salida
   `[B, 3]` por lote de `B` grafos se evalúa directamente con `evaluate_predictions`.
3. **No depende de una anotación pendiente.** La alternativa (agregar aristas taxón → función
   anotadas, punto S-03 pedido a Investigación) cambiaría el grafo, no el modelo. Si esas aristas
   llegan, el mismo diseño las usa sin cambios: la convolución heterogénea toma cada tripleta
   presente (§5), y la lectura por grafo sigue siendo válida.

En la interfaz del Issue, **`N_objetivo` es el número de grafos del lote** (`B`), no el número
de nodos `metabolite`.

### 2.1 Target por grafo

Una transformación previa al modelo (A41-5) lleva los AGCC de los nodos `metabolite` a
atributos del grafo:

| Atributo | Forma | Contenido |
|---|---|---|
| `data.y_graph` | `[1, 3]`, `float32` | Acetato, propionato y butirato, en ese orden. `0.0` donde falta. |
| `data.y_graph_mask` | `[1, 3]`, `bool` | `true` donde el AGCC tiene valor (`y_mask` del nodo correspondiente). |

Al agrupar en lotes, PyG concatena estos atributos en `[B, 3]`. Un nodo `metabolite` se asigna a
un AGCC por su `chemical_id` canónico, con el mismo mapeo que usa A40-3
(`nutrigraphdt.models.tabular`): en D1 el `node_id` ya es el nombre canónico (`acetate`), y en
el sintético los `node_id` son opacos (`synthetic:metabolite:0001`) y el nombre se lee de
`raw_attributes["chemical_id"]`. Los demás metabolitos (lactato, succinato, valerato…) quedan
fuera del target.

Las instancias sin ningún AGCC (124 de 185 en D1) no aportan a la pérdida ni a las métricas. La
pérdida es un MSE enmascarado: solo cuenta las celdas con `y_graph_mask = true`. Para comparar
con los baselines, que exigen los tres AGCC por muestra, las métricas se calculan sobre las
muestras con los tres valores.

### 2.2 Sin fuga del target

- `x` de `metabolite` no contiene la concentración (DS-01 y el constructor ya lo garantizan).
- **La lectura excluye `metabolite` y `phenotype`.** Son los nodos objetivo y de resultado; en
  D1 la cantidad de nodos `metabolite` (de 2 a 8) depende de qué se midió en cada animal.
  Siguen participando en el paso de mensajes cuando el grafo los conecta (en el sintético,
  `function → produces → metabolite → measured_in → host` es la ruta mecanística), pero su
  representación no entra a la cabeza.
- **Test obligatorio (A41-6):** cambiar `data["metabolite"].y`, `y_mask`, `y_graph` o
  `y_graph_mask` no cambia la salida del modelo.

## 3. Interfaz común de los modelos

Las tres variantes heredan de una clase base común de A41-5 y cumplen este contrato:

```python
class SCFAGraphModel(torch.nn.Module):
    target_names: tuple[str, ...] = DEFAULT_SCFA_TARGETS  # acetate, propionate, butyrate

    def __init__(self, metadata: GraphMetadata, config: ModelConfig) -> None: ...

    def forward(self, data: HeteroData) -> Tensor:
        """Devuelve un tensor float32 de forma [B, 3], sin NaN ni infinitos."""
```

**Entrada.** Un `HeteroData`, individual o un lote de
`torch_geometric.loader.DataLoader`, que:

1. pasó la compuerta `prepare_graphs_for_model` (reglas de tensores, ver
   [graph-validation-usage.md](../graph/graph-validation-usage.md));
2. tiene relaciones inversas, agregadas con `add_reverse_edges` (`nutrigraphdt.graph.builder`)
   **después** de validar, porque EDG-01 prohíbe las inversas en los registros;
3. tiene `y_graph` e `y_graph_mask` (§2.1).

El modelo lee `x_dict`, `edge_index_dict` y `batch_dict`. Si el grafo no viene de un lote (no hay
`batch`), se asume un solo grafo (`B = 1`). El modelo no lee `y`, `y_mask`, `y_graph`,
`raw_attributes` ni la evidencia.

**Salida.** `Tensor` `float32` `[B, 3]`, columnas en el orden de `target_names`, en la escala
estandarizada del target (§6.2). Quien entrena invierte la escala antes de llamar a
`evaluate_predictions`, para reportar en las unidades de la fuente.

**Construcción.** `metadata` describe el dataset, no un grafo: los tipos de nodo con su número
de columnas de `x` (de `node_feature_schema` en los metadatos del dataset) y la **unión** de
tipos de arista de todos sus grafos, incluidas las inversas. Así, un grafo que no tiene alguna
relación usa el mismo modelo. `config` lo valida y lo construye la fábrica de A41-8
(`build_model(cfg)`).

**Inicialización.** Las capas con dimensiones perezosas (`(-1, -1)`) se inicializan con un
forward sobre un lote de entrenamiento **antes** de crear el optimizador.

## 4. Componentes compartidos (A41-5)

```text
x_t, missing_mask_t ──► encoder_t ──► h_t^0 ──► [convolución × L, con residual] ──► h_t^L
                                                                                     │
                     lectura: media por grafo de cada tipo t ∉ {metabolite, phenotype}
                                                                                     │
                                     concatenar en orden fijo de tipos ──► MLP ──► [B, 3]
```

- **Encoder por tipo de nodo.** `Linear(2·F_t, hidden)` sobre `[x_t ‖ missing_mask_t]`. La
  máscara entra como feature para que un `0.0` ausente no se confunda con un cero medido. Un
  tipo con `F_t = 0` usa un vector aprendido por tipo (`hidden` parámetros), igual para todos sus
  nodos.
- **Residual.** Entre capas, `h_t^{l+1} = h_t^l + dropout(act(conv_t(h^l)))`. Es necesario, no
  opcional: `HeteroConv` solo devuelve los tipos que son destino de alguna arista, así que un
  tipo aislado (`taxon` y `diet` en D1) desaparecería en la primera capa. Con el residual
  conserva su representación del encoder.
- **Lectura.** Media de los nodos de cada tipo dentro de cada grafo (`global_mean_pool` con
  `batch_dict[t]`), para los tipos de entrada: `diet`, `additive`, `substrate`, `taxon`,
  `function` y `host`. Un tipo sin nodos en un grafo aporta un vector de ceros. Las medias se
  concatenan en el orden de `NODE_TYPES`, así que la dimensión es `6·hidden` en cualquier
  dataset.
- **Cabeza de regresión.** `Linear(6·hidden, hidden) → ReLU → Dropout → Linear(hidden, 3)`. Sin
  activación final: la salida está estandarizada y puede ser negativa. La no negatividad en
  unidades reales se mide con `negative_pct` (A40-2) y se trata en la fase F5.

## 5. Variantes

Las tres usan los mismos encoders, residual, lectura y cabeza; solo cambia la convolución.

| Variante | Issue | Convolución por capa | Tipos de nodo y arista |
|---|---|---|---|
| `homo_sage` | A41-2 | `SAGEConv(hidden, hidden, aggr="mean")` | Ignorados: encoders → `to_homogeneous()` → convolución → vuelta a `h_t` con `node_type`. |
| `hetero_sage` | A41-3 | `HeteroConv({r: SAGEConv((-1, -1), hidden, aggr="mean")}, aggr="sum")` | Una convolución por tripleta, incluidas las inversas `rev_*`. |
| `hetero_gat` | A41-4 | `HeteroConv({r: GATConv((-1, -1), hidden // heads, heads=heads, add_self_loops=False)}, aggr="sum")` | Ídem, con atención por relación; las cabezas se concatenan (`heads · hidden // heads = hidden`). |

- `homo_sage` es el control: mide cuánto aporta distinguir tipos. La proyección por tipo ocurre
  antes de `to_homogeneous()`, porque los tipos tienen distinto número de columnas.
- En `hetero_sage` y `hetero_gat`, el diccionario de convoluciones se arma con la unión de
  tripletas de `metadata`, así que **todas las relaciones del esquema presentes en el dataset
  participan** (criterio de A41-3). En D1 son `measured_in` y `rev_measured_in`; en el sintético,
  las 11 tripletas y sus 11 inversas. En la última capa solo se crean las que llegan a la lectura
  (§5.1).
- `add_self_loops=False` es obligatorio en `GATConv` con grafos bipartitos (origen y destino de
  distinto tipo). El residual cumple el papel del lazo propio.
- `edge_attr` no se usa en v1: solo `diet → provides → substrate` tiene una columna
  (`proportion`), y las demás relaciones tienen `[E, 0]`.

### 5.1 Convoluciones que no llegan a la predicción (#111)

**Decisión:** `hetero_sage` y `hetero_gat` **no crean** las convoluciones cuya salida no puede
llegar a la lectura. Las tripletas de cada capa las da `layer_edge_types(metadata, num_layers)`
(`nutrigraphdt.models.gnn.base`), que recorre las capas desde la última:

1. en la última capa se conservan las tripletas cuyo destino entra a la lectura
   (`READOUT_NODE_TYPES`), es decir, ninguna hacia `metabolite` ni `phenotype`;
2. en cada capa anterior se agregan los tipos que son origen de alguna tripleta ya conservada,
   porque su embedding alimenta esa convolución, y se conservan las tripletas hacia ellos.

Con relaciones inversas (siempre presentes tras `add_reverse_edges`), todo tipo es origen de
alguna tripleta, así que solo se poda la última capa: 5 de 22 tripletas en el sintético (las que
van hacia `metabolite` o `phenotype`) y `rev_measured_in` en D1, que queda con `measured_in` como
única convolución de la última capa. Sin inversas, la regla también poda capas anteriores.

**Por qué no mantenerlas.** No reciben gradiente con ningún dato, así que conservan la
inicialización aleatoria. Con `L = 2` y `hidden = 8` sobre el grafo sintético eran 15 de 150
parámetros en `hetero_sage` y 25 de 238 en `hetero_gat`. Además de costar cómputo en cada
`forward`, en `hetero_gat` exponían por `forward_with_attention` pesos de atención de la última
capa hacia `metabolite` (por ejemplo `function → produces → metabolite`, la ruta mecanística)
calculados con parámetros sin entrenar, que la fase F7 podría haber leído como explicación. Un
tipo sin convolución en una capa conserva su embedding por el residual (§4), así que la
predicción es la misma función de los parámetros que quedan. Con una misma semilla, los pesos
iniciales sí cambian respecto de la versión anterior, porque se crean menos parámetros.
`homo_sage` no se ve afectado: comparte una sola convolución entre todos los tipos.

**Causas dependientes de los datos en `hetero_gat`.** Aun con la poda, `GATConv` deja sin
gradiente `att_src`, `att_dst` y `lin_dst` de una relación cuando cada destino tiene un solo
vecino: el softmax sobre un vecino vale 1, sin importar los parámetros. En el sintético de
escenarios son 48 de los 213 parámetros que quedan (10 relaciones de la primera capa y 6 de la
última, tres tensores cada una). En D1 le ocurre siempre a `host → rev_measured_in → metabolite`
(cada metabolito tiene un solo huésped) en las capas donde existe, todas menos la última. No
requiere acción en el modelo: esa relación se comporta como una proyección lineal, igual que en
`hetero_sage`. Sí afecta la interpretación: sus pesos de atención valen 1 por construcción y no
deben usarse como explicación. La otra causa observada (el encoder de `host` y de `additive` sin
gradiente en el sintético) viene de columnas constantes, que valen 0 tras estandarizar; se
resuelve con datos que varían, no en el modelo.

## 6. Hiperparámetros iniciales

| Hiperparámetro | Valor inicial | Rango para el ajuste (act. 44) | Motivo |
|---|---|---|---|
| Dimensión oculta (`hidden`) | 64 | 32, 64, 128 | Pocas muestras con target (61 en D1): una capacidad mayor sobreajusta. |
| Número de capas (`L`) | 2 | 1, 2, 3 | La lectura ya combina todos los tipos. En el sintético, 2 capas llevan taxón → función a la lectura por `function` y función → metabolito → huésped por `host`; la cadena completa taxón → función → metabolito → huésped necesita 3 (§5.1). |
| Dropout | 0.2 | 0.0 a 0.5 | Entre capas y en la cabeza. |
| Agregación de vecinos (`SAGEConv`) | `mean` | `mean`, `max`, `sum` | `mean` no depende del grado, que varía mucho entre tipos. |
| Agregación entre relaciones (`HeteroConv`) | `sum` | `sum`, `mean` | Valor por defecto de PyG. |
| Cabezas de atención (`hetero_gat`) | 4 | 1, 2, 4 | `hidden` debe ser divisible por `heads`. |
| Activación | ReLU | — | |
| Lectura | media por tipo | media, suma | La media no depende del número de taxones detectados. |

Valores iniciales del entrenamiento, para que A41-7 y la act. 44 partan igual: Adam con
`lr = 1e-3` y `weight_decay = 1e-4`, lotes de 16 grafos, semilla 42, como máximo 200 épocas con
detención temprana (paciencia 20) sobre el RMSE promedio de `val`.

### 6.1 Partición

Se usa la partición de A40-1 (`get_split()`), por `sample_id`: un grafo pertenece al subconjunto
de su `data.sample_id`. En el sintético, el grafo basal y el intervenido de una misma muestra
quedan en el mismo subconjunto. `test` no se usa para seleccionar hiperparámetros ni para la
detención temprana.

### 6.2 Escalado

Todo lo que se ajusta a los datos se ajusta **solo con `train`**, como en los baselines:

- **Features:** media y desviación estándar por columna de `x`, sobre los nodos de los grafos de
  `train`, ignorando las celdas con `missing_mask = true`. Se aplican a los tres subconjuntos.
  `x` no se normaliza en el constructor (`prototype-0.1` entrega valores crudos).
- **Target:** media y desviación estándar de cada AGCC sobre las muestras de `train` con valor.
  El modelo predice en esa escala; las métricas se calculan tras invertirla.

No se aplican transformaciones con supuestos biológicos (por ejemplo, logaritmo o CLR de las
abundancias): son una decisión pendiente con Investigación.

## 7. Limitaciones y decisiones abiertas

- **Covariables del huésped en `x` (#147).** En D1, `x` de `host` tiene 10 columnas one-hot:
  `trial_code` (3), `sampling_day` (3), `sex` (2) y `breed` (2), según el contrato v2 §3.
  `pen_code` y `body_weight_g` no son columnas. Las corridas D1 anteriores tenían una sola
  columna (`body_weight_g`), así que sus checkpoints no se cargan con los grafos nuevos.
- **El tratamiento dietario no está en `x`.** En D1 el nodo `diet` no tiene columnas y su
  `name` (`Control`, `Probiotic`, `Prebiotic`; este último es el fitobiótico `CE`) es una
  categoría que el constructor no codifica,
  mientras que los baselines sí usan `diet:treatment`. Hasta que el constructor codifique
  categorías, la GNN tiene menos información que los baselines en D1, y la comparación debe
  reportarlo.
- **D1 no ejercita la estructura.** Con taxones aislados, las tres variantes se reducen en D1 a
  encoders + lectura sobre los mismos nodos, y deberían rendir parecido. La diferencia entre
  variantes solo se puede medir en grafos con la ruta mecanística (el sintético, o D1 con la
  anotación taxón → función de S-03).
- **Muchos nodos por grafo.** Cada grafo de D1 tiene los 1315 taxones de la tabla de
  abundancias, frente a 61 muestras con target. Filtrar taxones raros con `train` es una opción
  de la act. 44, no de este diseño.
- **Partición versionada.** Desde A45-1 (#101), `configs/splits/d1_holofood.json` (versión
  2.0.0) cubre los 530 animales de D1. De los 59 grafos con los tres AGCC, `val` recibe solo 7;
  ver [configs/splits/README.md](../../configs/splits/README.md).
- **Gradientes nulos en A41-6.** Una convolución de una relación ausente en el lote no recibe
  gradiente. El test de gradientes debe usar un grafo sintético con las once tripletas. Con la
  poda del §5.1, en ese grafo controlado todos los parámetros reciben gradiente.
