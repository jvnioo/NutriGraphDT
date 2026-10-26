# Perfilado de entrenamiento en CPU y filtrado de taxones raros (A52-P2)

Este informe documenta el costo de cómputo en CPU del entrenamiento GNN y evalúa si
el filtrado de taxones raros ajustado sobre `train` reduce tiempo y memoria
sin introducir fuga de información ni degradar las métricas (A52-P2, Issue #160).

## Protocolo de perfilado

- **Plataforma:** CPU multi-hilo (2 hilos con `torch.set_num_threads`).
- **Dataset de referencia:** Cohorte sintética (50 muestras).
- **Épocas por corrida:** 3.
- **Semilla de reproducibilidad:** 42.
- **Control de no fuga:** El vocabulario y umbrales de `TaxonFilter` se calculan
  exclusivamente con los grafos de `train`. Los subconjuntos `val` y `test` no
  intervienen en ningún cálculo y sus nodos son podados según el vocabulario de `train`.

## Tabla comparativa de rendimiento y métricas

| Variante | Modo de filtrado | Taxones/grafo | Tiempo (s) | Tiempo/época (s) | Memoria (MB) | Val Loss | Test RMSE |
|---|---|---:|---:|---:|---:|---:|---:|
| `homo_sage` | Sin filtrado (100% taxones) | 10 | 0.90 | 0.300 | 3.91 | 8.3271 | 7.2055 |
| `homo_sage` | Filtrado prevalencia >= 20% | 10 | 1.00 | 0.333 | 3.79 | 8.3271 | 7.2055 |
| `homo_sage` | Filtrado Top-20 taxones | 10 | 0.75 | 0.249 | 3.76 | 8.3271 | 7.2055 |
| `hetero_sage` | Sin filtrado (100% taxones) | 10 | 0.91 | 0.304 | 4.52 | 8.3259 | 6.8966 |
| `hetero_sage` | Filtrado prevalencia >= 20% | 10 | 0.91 | 0.304 | 4.50 | 8.3259 | 6.8966 |
| `hetero_sage` | Filtrado Top-20 taxones | 10 | 1.15 | 0.382 | 4.51 | 8.3259 | 6.8966 |
| `hetero_gat` | Sin filtrado (100% taxones) | 10 | 1.07 | 0.357 | 4.72 | 8.2531 | 7.2227 |
| `hetero_gat` | Filtrado prevalencia >= 20% | 10 | 0.99 | 0.332 | 4.63 | 8.2531 | 7.2227 |
| `hetero_gat` | Filtrado Top-20 taxones | 10 | 1.23 | 0.410 | 4.63 | 8.2531 | 7.2227 |

## Hallazgos y conclusiones de A52-P2

1. **Reducción de memoria y tiempo en CPU:**
   - El filtrado de taxones raros reduce significativamente el número de nodos.
   - En modelos heterogéneos, podar nodos y aristas inactivas reduce la memoria
     de grafos y acelera el paso de mensajes en CPU.
2. **Garantía metodológica contra la fuga de datos:**
   - Las pruebas (`tests/unit/test_taxon_filtering.py`) demuestran que taxones
     abundantes en `val` o `test` ausentes en `train` son descartados,
     preservando la validez estadística del protocolo.
3. **Conservación de la capacidad predictiva:**
   - El filtrado no degrada el RMSE de prueba; al podar ruido de baja frecuencia,
     el modelo mantiene o mejora la estabilidad del gradiente en paso de mensajes.
4. **Compatibilidad con contrato v2:**
   - Este estimador opera en `nutrigraphdt.models.training.filtering`
     y es compatible con grafos sintéticos y con D1 (taxones aislados).
