# Figuras del proyecto: comando y procedencia (A115-P3, #346)

Toda figura que se entregue debe salir de un script del repositorio y decir con qué comando y con
qué commit se generó. Esta tabla lista las figuras versionadas.

| Figura | Comando | Procedencia | Datos |
|---|---|---|---|
| `reports/delivery/figures/scenarios.png` | `python scripts/plot_delivery.py` | `reports/delivery/figures/figures.json` (commit, entorno, corrida) | Sintéticos: catálogo de escenarios con la corrida de entrega |
| `reports/delivery/figures/metrics.png` | `python scripts/plot_delivery.py` | `reports/delivery/figures/figures.json` | Sintéticos: `reports/delivery/results.json` |
| `reports/gnn/figures/learning_curves_synthetic.png`, `predictions_synthetic.png` | `python scripts/plot_gnn_runs.py runs/<homo_sage> runs/<hetero_sage> runs/<hetero_gat>` | `reports/gnn/figures/diagnostics_synthetic.*` | Sintéticos (A45-7) |
| `reports/gnn/figures/learning_curves_d1.png`, `predictions_d1.png` | el mismo, con las corridas de D1 | `reports/gnn/figures/diagnostics_d1.*` | D1: resultado exploratorio (#296) |

Las figuras de A45-7 necesitan las corridas en `runs/`, que no se versionan: para regenerarlas hay
que volver a entrenar con `scripts/train_gnn.py`. Las de la entrega se regeneran desde un clon
limpio, sin red.

La Web App dibuja sus gráficos en vivo (`nutrigraphdt.demo.plots` y `nutrigraphdt.demo.results`);
una captura de la app para la entrega debe indicar el commit de la app y el escenario mostrado.
