# Cobertura de tests de modelos y del pipeline de entrenamiento (A52-P3)

Esta página registra las brechas de pruebas que cubre la actividad **A52-P3**
([Issue #154](https://github.com/jvnioo/NutriGraphDT/issues/154)), cómo se comprobó que las
pruebas nuevas detectan regresiones y los riesgos que quedan fuera de alcance. El objetivo es
reforzar contratos y casos borde del entrenamiento, no subir un porcentaje.

## 1. Método

1. Se midió la cobertura de `nutrigraphdt.models` con la suite completa (`pytest --cov`) y se
   leyeron las líneas sin cubrir de escalado, bucle, pipeline y trazabilidad.
2. Se priorizaron los comportamientos que pide la issue: máscaras, escalado, semillas, detención
   temprana, checkpoints y recarga. Las máscaras de la pérdida (`masked_mse_loss`) y `set_seed`
   ya tenían pruebas directas (`test_gnn_base.py`, `test_training_config.py`) y no se duplicaron.
   El hash canónico de la partición es de #133 y ya se prueba en `test_training_tracking.py` y
   `test_split.py`; aquí no se reimplementa.
3. Cada prueba nueva se validó con una **mutación** del código fuente: se introdujo a mano la
   regresión que debe detectar, se comprobó que la prueba falla y se restauró el archivo.

## 2. Brechas cubiertas

| Componente | Comportamiento | Prueba | Mutación detectada |
|---|---|---|---|
| `FeatureScaler` | Rechaza `train` vacío, anchos de `x` distintos entre grafos y `missing_mask` con otra forma | `test_scaling.py::TestScalingContracts` | — (validaciones de entrada) |
| `FeatureScaler` | Una columna nunca observada en `train` queda neutral (media 0, desviación 1) | `test_column_never_observed_in_train_is_neutral` | media `NaN` en esa columna |
| `FeatureScaler` | Sin ajustar no transforma; rechaza un grafo con otro número de columnas | `TestScalingContracts` | — |
| `TargetScaler` | Sin ajustar, `mean`, `std`, `transform` e `inverse_transform` fallan en lugar de devolver valores por omisión | `test_unfitted_target_scaler_raises_instead_of_returning_defaults` | — |
| `TargetScaler` | Con máscara, la inversa deja en `0.0` los AGCC no medidos | `test_inverse_transform_zeroes_unmeasured_cells` | se quita el `torch.where` de la máscara |
| `TargetScaler` | Ancho y forma de máscara inválidos; AGCC sin mediciones en `train`; ida y vuelta JSON exacta | `TestScalingContracts` | — |
| Detención temprana | Un empate con el mejor RMSE de `val` no es mejora; la mejor época es la primera | `test_a_tie_with_the_best_rmse_is_not_an_improvement` | `<` cambiado por `<=` |
| Detención temprana | Con `patience = 1` se detiene en la primera época sin mejora | `test_patience_of_one_stops_at_the_first_epoch_without_improvement` | `>=` cambiado por `>` |
| Detención temprana | `improved` marca exactamente los mínimos estrictos; sin detención, se corren `max_epochs` | `test_improvement_flags_mark_strict_new_minima` | — |
| Bucle | `train` sin ningún AGCC medido se rechaza antes de entrenar | `test_train_without_measured_targets_is_rejected` | se elimina la comprobación |
| `Predictions` | Sin filas completas no hay métricas; `to_records` deja `None` en lo no medido | `test_predictions_without_complete_rows_cannot_be_evaluated` | — |
| `predict` | Un `DataLoader` vacío da cero filas con el ancho y el tipo de máscara correctos | `test_predict_on_an_empty_loader_returns_no_rows` | — |
| Checkpoint | `checkpoint.pt` tiene exactamente los pesos del modelo guardado | `test_checkpoint_holds_exactly_the_weights_of_the_saved_model` | ver §4 |
| Recarga | Falla sin `checkpoint.pt`, con una arquitectura distinta de la registrada y con pesos faltantes | `test_training_tracking.py` | `load_state_dict(strict=False)` |
| Recarga | `LoadedRun` expone `run_id`, configuraciones y escalado guardados | `test_loaded_run_exposes_its_id_and_configuration` | — |
| `run_training` | La corrida recargada predice exactamente lo que registró `predictions.csv` | `tests/integration/test_training_pipeline.py` | — |
| `run_training` | Misma semilla, mismo checkpoint y mismas predicciones; otra semilla cambia los pesos | `test_same_seed_reproduces_the_checkpoint_and_predictions`, `test_another_seed_changes_the_trained_weights` | se elimina `set_seed` |
| `run_training` | El escalado se ajusta solo con `train`: alterar `val` y `test` no cambia `run.json` | `test_scaling_is_fitted_with_train_only` | ajuste con `train + val` o `train + test` |
| `run_training` | Un subconjunto vacío no aparece en predicciones ni métricas; `train` vacío se rechaza sin crear la corrida | `test_training_pipeline.py` | — |

`run_training` solo se probaba antes con D1 (`test_report_gnn_d1.py`) o a través de los scripts.
La prueba de integración nueva lo ejecuta dentro del proceso con la cohorte sintética, sin
descargas.

## 3. Cobertura medida

Suite completa con `NUTRIGRAPHDT_REQUIRE_GRAPH=1`, CPU, Python 3.14, torch 2.15.0 y
torch_geometric 2.8.1.

| Módulo | Antes | Después |
|---|---|---|
| `models/training/scaling.py` | 88 % | 97 % |
| `models/training/loop.py` | 98 % | 99 % |
| `models/training/pipeline.py` | 96 % | 100 % |
| `models/training/tracking.py` | 97 % | 97 % |
| `nutrigraphdt.models` (total) | 95 % | 96 % |

`tracking.py` solo gana una línea (`LoadedRun.run_id`): sus pruebas nuevas recorren sobre todo
líneas que ya estaban cubiertas, pero fijan resultados que antes no se comprobaban (pesos
faltantes, arquitectura distinta, checkpoint ausente).

## 4. Riesgos fuera de alcance

- **Checkpoint en GPU.** `save_run` mueve los pesos a CPU antes de guardar. En un equipo solo con
  CPU, quitar ese paso no cambia nada, así que ninguna prueba local puede detectarlo. Habría que
  probarlo en un equipo con CUDA, que el proyecto no exige.
- **Determinismo entre plataformas.** Las pruebas comparan dos corridas en el mismo equipo. La
  igualdad bit a bit entre Windows y Linux, o entre versiones de PyTorch, no está garantizada. La
  comprueba `scripts/reproduce_run.py` con tolerancias (A45-3).
- **Filtrado de taxones y prueba de sobreajuste.** `models/training/filtering.py` (87 %) y
  `models/gnn/sanity.py` (81 %) son de A52-P2 y A41-7. Sus líneas sin cubrir son sobre todo
  mensajes de error de entradas inválidas y no se priorizaron.
- **Empates de RMSE en entrenamientos reales.** El empate se prueba anulando el paso del
  optimizador; en un entrenamiento normal casi nunca hay empates exactos.
