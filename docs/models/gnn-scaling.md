# Escalado de features y targets para GNN (A44-2)

Este documento describe los escaladores `FeatureScaler` y `TargetScaler` en
`nutrigraphdt.models.training.scaling`, implementados según el §6.2 de
[gnn-architecture.md](gnn-architecture.md) para la actividad 44. Requiere el extra `graph`.

## Contexto y motivación

En la predicción de metabolitos (AGCC) con redes neuronales de grafos, los atributos de entrada
presentan órdenes de magnitud sumamente dispares:
- En D1 HoloFood, el peso corporal del huésped (`host`) es del orden de 100 g, mientras que las
  abundancias taxonómicas se encuentran normalizadas en proporciones o conteos pequeños.
- En el dataset sintético (`prototype-0.1`), dosificaciones de aditivos dietarios alcanzan $10^9$.

Sin estandarización, las magnitudes elevadas dominan la proyección inicial en `NodeTypeEncoder`
y desbalancean los gradientes, degradando el entrenamiento. Adicionalmente, los modelos de
referencia (baselines lineales de A40-4) incorporan `StandardScaler` en su pipeline ajustado
únicamente con `train`; la GNN debe seguir exactamente el mismo protocolo experimental para que
la comparación sea metodológicamente justa y reproducible.

## Reglas de diseño (§6.2)

1. **Ajuste exclusivo con train:** Toda estadística (media y desviación estándar) se calcula
   única y exclusivamente sobre los nodos y grafos del subconjunto `train`. Cualquier modificación
   en las particiones `val` o `test` mantiene las estadísticas de escalado inalteradas.
2. **Tratamiento de celdas ausentes:** Las celdas marcadas con `missing_mask = True` (ausencia de
   datos, regla NOD-07/TEN-07) se excluyen del cálculo de la media y la varianza. Tras aplicar la
   estandarización, las celdas ausentes se fijan estrictamente en `0.0` y conservan su
   `missing_mask` booleana original para que el `NodeTypeEncoder` las distinga de un valor medido.
3. **Inmutabilidad de grafos:** Las transformaciones sobre `HeteroData` se efectúan por defecto
   sobre copias profundas (`graph.clone()`), preservando intactos los grafos de entrada.
4. **Protección contra división por cero:**
   - Tipos de nodo sin atributos continuos ($F_t = 0$, como `diet` o `metabolite` en D1) conservan
     su representación sin error.
   - Columnas constantes (desviación estándar igual a cero) fijan su escala en $1.0$, transformando
     la columna observada en $0.0$ sin generar `NaN` ni infinitos.
5. **Inversión de escala antes de métricas:** El modelo optimiza sobre la escala estandarizada
   mediante `masked_mse_loss`. Antes de computar métricas con `evaluate_predictions` (A40-2), se
   aplica `TargetScaler.inverse_transform` para recuperar las unidades biológicas originales.
6. **Sin transformaciones no consensuadas:** No se aplican transformaciones logarítmicas ni
   CLR (Centered Log-Ratio) sobre abundancias taxonómicas, ya que constituyen una decisión
   pendiente con Investigación (§6.2).

## Componentes

### `FeatureScaler`

Estandariza los tensores `store.x` de cada tipo de nodo:

```python
from nutrigraphdt.models.training.scaling import FeatureScaler

# Ajuste sobre los grafos de entrenamiento
scaler = FeatureScaler.fit(train_graphs)

# Transformación de subconjuntos sin mutar los originales
train_scaled = scaler.transform(train_graphs)
val_scaled = scaler.transform(val_graphs)
test_scaled = scaler.transform(test_graphs)

# O mediante el atajo de subconjuntos
scaled_subsets = scaler.transform_subsets(
    {
        "train": train_graphs,
        "val": val_graphs,
        "test": test_graphs,
    }
)
```

Cada tipo de nodo almacena un objeto `NodeFeatureStats`:
- `mean`: tupla de medias por columna.
- `std`: tupla de desviaciones estándar por columna.
- `num_features`: dimensión de atributos $F_t$.
- `observed_count`: cantidad de celdas observadas (`missing_mask = False`) empleadas en el ajuste.

### `TargetScaler`

Estandariza los valores de `y_graph` para los tres AGCC (`acetate`, `propionate`, `butyrate`),
considerando únicamente las instancias con valor medido (`y_graph_mask = True`):

```python
from nutrigraphdt.models.training.scaling import TargetScaler

# Ajuste desde los grafos de entrenamiento o desde tensores
target_scaler = TargetScaler.fit(train_graphs)

# Transformación de tensores durante el bucle de entrenamiento
y_scaled = target_scaler.transform(batch.y_graph, mask=batch.y_graph_mask)

# Recuperación para evaluación en unidades originales
y_original = target_scaler.inverse_transform(predictions, mask=batch.y_graph_mask)
```

Garantiza que `inverse_transform(transform(y))` recupera los valores de $y$ dentro de la
tolerancia numérica de punto flotante ($< 10^{-5}$).

## Trazabilidad y serialización (A44-5)

Para guardar y restaurar los escaladores en los directorios de corrida (`runs/<run_id>/`):

```python
import json
from nutrigraphdt.models.training.scaling import scalers_from_dict, scalers_to_dict

# Exportar a diccionario serializable
run_metadata = scalers_to_dict(feature_scaler, target_scaler)
with open("scalers.json", "w", encoding="utf-8") as f:
    json.dump(run_metadata, f, indent=2)

# Restaurar en inferencia o reanudación
with open("scalers.json", "r", encoding="utf-8") as f:
    data = json.load(f)
reloaded_feature_scaler, reloaded_target_scaler = scalers_from_dict(data)
```

Ambas clases admiten además `to_dict()`, `from_dict()`, `to_json()` y `from_json()`.
