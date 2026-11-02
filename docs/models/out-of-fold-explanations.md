# Explicación fuera de fold (C-05, #241)

Aplica la decisión C-05 de la
[respuesta de Investigación a la revisión A55](../research/Respuesta%20de%20Investigación%20a%20la%20revisión%20A55.md)
(#158): **cada animal de D1 se explica con el modelo del fold en que estuvo en test**, en cada
semilla del plan. El código está en `nutrigraphdt.explainability.out_of_fold`; el formato de
cada explicación es el del [contrato 2.0.0](explanation-contract.md).

## 1. Reglas

1. **Modelo fuera de fold.** Para cada animal y semilla del plan se usa la corrida (#180) cuyo
   `run.json` lo tiene en `sample_ids.test`. Nunca una que lo tuvo en `train` ni en
   `inner_val`, porque el val interno decide la detención temprana y también influye en el
   modelo. Explicar con un modelo que vio al animal sería explicar memorización.
2. **Escalado del fold.** El grafo se escala con el `FeatureScaler` guardado en esa corrida
   (protocolo §1.3), nunca con uno ajustado sobre toda la cohorte.
3. **Dos estabilidades separadas:**
   - **Entre semillas del explicador, con el modelo fijo (C-07).** `explain_across_seeds`
     calcula Φ̂ con ≥ 5 semillas, su IC y `explainer_instability`.
   - **Entre semillas del plan.** Cambian la partición y el entrenamiento, porque la semilla
     de entrenamiento se deriva de la del fold. `AnimalExplanations.plan_phi` y `plan_ci`
     comparan el top-k de la **primera** semilla del explicador en cada modelo, así que entre
     modelos no cambia el explicador.
4. **Un fold fallido no se reemplaza.** Una corrida sin `checkpoint.pt` no se indexa. Sus
   animales quedan con menos explicaciones, y `OutOfFoldPlan.missing` y
   `explanation_counts()` informan cuántas tiene cada animal y qué semillas faltan.
5. **La agregación entre modelos** (por ejemplo, la importancia media de las 10 semillas) queda
   para una versión menor del contrato, como dice C-05.

## 2. Uso

```python
from nutrigraphdt.explainability import HeteroExplainer
from nutrigraphdt.explainability.out_of_fold import (
    explain_out_of_fold,
    index_runs,
    plan_out_of_fold,
)

runs = index_runs("runs/constraints/d1", variant="hetero_sage", edges_arm="free")
plan = plan_out_of_fold(runs, inputs.graphs, seeds=range(10))
print(plan.explanation_counts(), plan.missing)


def explain(model, graph, run, output, seed):
    explainer = HeteroExplainer(
        model, node_mask_type="attributes", edge_mask_type=None, epochs=200, seed=seed
    )
    return explainer.explain(graph, run=run, target=output)


results = explain_out_of_fold(
    plan,
    inputs.graphs,  # preparados como para entrenar, sin escalar
    explain,
    outputs=("log_propionate_acetate", "log_butyrate_acetate"),  # C-04
    explainer_seeds=range(5),  # C-07
    repo_root=".",
)
```

`plan_out_of_fold` rechaza (`OutOfFoldError`) corridas que mezclan variante, brazo o dataset,
dos corridas para el mismo `(semilla, fold)`, un animal en el test de dos folds de una semilla
y una corrida que tiene a un animal en test y en entrenamiento. Al explicar,
`explain_out_of_fold` vuelve a comprobar en el `run.json` cargado que el animal esté en test y
no en `train` ni `inner_val`, y que los grafos tengan las columnas y relaciones del
entrenamiento.

`tests/integration/test_out_of_fold_explanations.py` entrena 2 semillas × 2 folds sintéticos y
demuestra que ningún animal se explica con un modelo que lo tuvo en entrenamiento. También
comprueba que el grafo llega con el escalado de su fold y que un fold fallido se informa y no
se reemplaza.

## 3. Costo en CPU

C-05 pide estimar el costo antes de fijar épocas. Son 56 animales × 10 semillas × 2 salidas ×
5 semillas del explicador, es decir **5600 ejecuciones por variante**.
`scripts/estimate_explanation_cost.py` mide `GNNExplainer` sobre un grafo real de D1, con
máscara de atributos y sin aristas (C-06). Usa el modelo sin entrenar de cada variante, porque
el tiempo no depende de los pesos, y no entrena nada en D1. Resultado del 02-11-2026 en un AMD
Ryzen 5 9600X, con un hilo por ejecución
([`reports/explainability/explanation_cost.md`](../../reports/explainability/explanation_cost.md)):

| Variante | s por ejecución, 100 / 200 / 500 épocas | Horas para 5600, 1 proceso (100 / 200 / 500) |
|---|---|---|
| `hetero_sage` | 0,110 / 0,202 / 0,475 | 0,17 / 0,31 / 0,74 |
| `hetero_gat` | 0,139 / 0,259 / 0,616 | 0,22 / 0,40 / 0,96 |
| `homo_sage` | 0,248 / 0,476 / 1,153 | 0,39 / 0,74 / 1,79 |

**Conclusión.** El costo no limita la elección de épocas. Las tres variantes con 500 épocas
suman unas 3,5 h en un proceso y menos de una hora repartidas en los 6 hilos del equipo, sin
GPU ni servicios de pago. Hay que fijar las épocas por convergencia de la máscara (#171), no
por costo. El tiempo crecerá cuando S-04 conecte los taxones y se expliquen aristas: habrá que
volver a medir.

## 4. Límites

- **Tipos de arista vacíos.** `GNNExplainer` de PyG 2.8 falla (`max()` de un tensor vacío) con
  grafos que tienen un tipo de arista vacío. Así quedan los de la cohorte sintética tras
  `align_graph_types`. En D1 no pasa hoy, pero puede pasar cuando S-04 agregue relaciones que
  no todos los animales tienen. La prueba sintética usa `EdgeGradientSaliency`.
- **Nada se interpreta todavía.** Ninguna explicación se interpreta antes de que el explicador
  pase el control de ruta plantada de #168 (C-07). Hoy solo `EdgeGradientSaliency` lo pasó, y en
  D1 no puede usarse porque los taxones están aislados (C-06).
- **Corridas pendientes.** No hay corridas de D1 guardadas para explicar. Además, el
  entrenamiento en D1 está en pausa hasta que el grafo tenga contenido (#236, #239).
