# Costo en CPU de las explicaciones fuera de fold (C-05, #241)

- **Comando:** `python scripts/estimate_explanation_cost.py --variants hetero_sage hetero_gat homo_sage --epochs 100 200 500 --repeats 5 --threads 1 --graphs-dir artifacts/graphs/D1_holofood`
- **Equipo:** AMD Ryzen 5 9600X 6-Core Processor, 6 hilos lógicos; torch 2.14.0+cpu, 1 hilo(s) por ejecución.
- **Grafo medido:** `SAMEA112904743` de D1_holofood (diet: 1, taxon: 1317, metabolite: 6, host: 1 nodos).
- **Ejecuciones por variante:** 56 animales × 10 semillas del plan × 2 salidas × 5 semillas del explicador = **5600**.
- **Medición:** `GNNExplainer` con máscara de atributos y sin máscara de aristas (C-06), modelo sin entrenar, mediana de 5 ejecuciones tras una de calentamiento.

| Variante | Épocas | s por ejecución (mín.–máx.) | Horas, 1 proceso | Horas, 6 procesos |
|---|---:|---:|---:|---:|
| `hetero_sage` | 100 | 0.110 (0.110–0.111) | 0.17 | 0.03 |
| `hetero_sage` | 200 | 0.202 (0.201–0.202) | 0.31 | 0.05 |
| `hetero_sage` | 500 | 0.475 (0.475–0.477) | 0.74 | 0.12 |
| `hetero_gat` | 100 | 0.139 (0.139–0.140) | 0.22 | 0.04 |
| `hetero_gat` | 200 | 0.259 (0.258–0.259) | 0.40 | 0.07 |
| `hetero_gat` | 500 | 0.616 (0.616–0.619) | 0.96 | 0.16 |
| `homo_sage` | 100 | 0.248 (0.247–0.251) | 0.39 | 0.07 |
| `homo_sage` | 200 | 0.476 (0.475–0.477) | 0.74 | 0.12 |
| `homo_sage` | 500 | 1.153 (1.151–1.290) | 1.79 | 0.30 |

La columna de 6 procesos supone ejecuciones independientes repartidas en los hilos lógicos del equipo, sin contar la carga de cada checkpoint (una vez por corrida, 50 por variante).
