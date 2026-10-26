# Perfilado de entrenamiento en CPU y filtrado de taxones raros (A52-P2)

Esta página documenta el perfilado del costo de entrenamiento de las Graph Neural Networks (GNN)
en entornos CPU y la evaluación del filtrado de taxones raros ajustado exclusivamente sobre `train`,
en cumplimiento de la actividad **A52-P2** del desglose de Desarrollo (Fase F4,
[Issue #160](https://github.com/jvnioo/NutriGraphDT/issues/160)).

El proyecto exige una ruta reproducible sin dependencia de cómputo en la nube pagado ni GPUs
privativas. Dado que los grafos reales (D1 HoloFood) contienen cientos de nodos `taxon` por animal,
se evalúa si la reducción dimensional taxonómica alivia la carga de memoria y tiempo sin provocar
fuga de datos (*data leakage*) ni deteriorar las predicciones.

---

## 1. Principio metodológico y prevención de fuga de información

El filtrado de taxones raros se implementa en la clase `TaxonFilter`
([`src/nutrigraphdt/models/training/filtering.py`](../../src/nutrigraphdt/models/training/filtering.py)).

### Reglas de diseño
1. **Ajuste exclusivo sobre `train`:** El cálculo de prevalencia (fracción de muestras donde el
   taxón está presente con abundancia mayor al umbral) y abundancia media se realiza **únicamente**
   con los grafos de `train`.
2. **Invarianza frente a `val` y `test`:** Ninguna muestra de validación o prueba interviene en la
   definición del vocabulario retenido (`selected_taxa`). Si un taxón es abundante en `val` o `test`
   pero raro o inexistente en `train`, es descartado.
3. **Poda determinista e inmutable:** La transformación opera sobre copias clonadas (`transform_graph`),
   podando los nodos `taxon` ausentes de `selected_taxa`.
4. **Reindexación de aristas:** Si el grafo contiene relaciones conectadas a `taxon` (p. ej.
   `("taxon", "has_capacity", "function")`), las aristas hacia nodos podados se eliminan y los
   punteros en `edge_index` se reasignan coherentemente a los nuevos índices compactados.

---

## 2. Parámetros de configuración

`TaxonFilterConfig` soporta los siguientes hiperparámetros:

- `min_prevalence` (float, por defecto `0.1`): Fracción mínima de grafos de `train` en los que el
  taxón debe estar presente.
- `min_abundance` (float, por defecto `0.0`): Umbral de abundancia para considerar presencia en una muestra.
- `top_k` (int opcional, por defecto `None`): Límite superior de taxones más frecuentes a conservar.

---

## 3. Protocolo de perfilado y resultados en CPU

El protocolo compara tres variantes arquitecturales (`homo_sage`, `hetero_sage`, `hetero_gat`) bajo
tres regímenes de filtrado:
1. **Sin filtrado:** Línea base con el 100 % de los taxones presentes.
2. **Filtrado por prevalencia:** Conserva taxones presentes en al menos el 20 % de las muestras de `train`.
3. **Filtrado Top-K:** Conserva únicamente los 20 taxones más abundantes de `train`.

Los resultados detallados quedan versionados en [`reports/gnn/cpu_profiling_rare_taxa.md`](../../reports/gnn/cpu_profiling_rare_taxa.md)
y `reports/gnn/cpu_profiling_rare_taxa.json`.

### Resumen de hallazgos
- **Memoria RAM pico:** El consumo en CPU se mantiene por debajo de 5 MB por proceso en lotes de tamaño 16.
- **Tiempo por época:** Se sitúa entre 0.25 s y 0.43 s por época en CPU estándar de 2 hilos, permitiendo
  completar un entrenamiento de 50 épocas en menos de 20 segundos sin hardware especializado.
- **Rendimiento predictivo (RMSE):** En las tres variantes, el filtrado de taxones de baja prevalencia
  conserva o mejora ligeramente el error cuadrático medio en `test`, actuando como regularizador al
  reducir el ruido de colas taxonómicas largas.

---

## 4. Verificación y pruebas automatizadas

La suite unitaria en [`tests/unit/test_taxon_filtering.py`](../../tests/unit/test_taxon_filtering.py)
incluye una prueba formal que demuestra:
1. Que la adición de taxones hiperabundantes en `val` y `test` no altera el vocabulario seleccionado en `train`.
2. Que la poda de nodos reindexa apropiadamente las aristas en grafos con enlaces heterogéneos.
3. Que la serialización (`to_dict` / `from_dict`) es exacta y reproducible.

---

## 5. Reproducción

Para ejecutar el benchmark comparativo en CPU:

```bash
python scripts/profile_gnn_cpu.py --epochs 5
python scripts/profile_gnn_cpu.py --models homo_sage hetero_sage hetero_gat --output-md reports/gnn/cpu_profiling_rare_taxa.md
```
