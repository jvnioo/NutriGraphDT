# Revisión de PRs y criterios del ciclo de entrenamiento con restricciones (A66-P5, #177)

Este informe contrasta los entregables A66-P1 a A66-P4 con sus PRs, pruebas y documentación, y
deja trazados los bloqueos que siguen abiertos. Solo se considera cumplido un criterio que tiene
una fuente concreta.

- **Estado del código revisado:** `main` en `ee23efc` (merge de #230, el último de A66).
- **Fuentes:**
  - Issues #181, #183, #179, #184 y #177;
  - PRs #226, #227, #228 y #230, con sus commits, reviews y campos de merge en la API de GitHub;
  - código, tests y documentación integrados.
- **Autoría y límite de independencia:** el autor de los cuatro PRs y de este informe es
  `jvnioo`. Es una auditoría de trazabilidad y evidencia: **no reemplaza la revisión humana
  independiente** que exige #177.

**Estado (02-11-2026): cerrado** con R-1 como excepción aceptada por el líder (§4).

---

## 1. Criterios de #177

| Criterio | Estado | Evidencia y detalle |
|---|---|---|
| Cada PR tiene revisión de otra persona y checks citados en su descripción | **Parcial — excepción aceptada** | Los cuatro PRs citan los checks del estado final (§2), pero ninguno tiene una review de GitHub: los cuatro los mergeó su autor tras los checks locales, con la excepción que el líder autorizó el 01-11-2026 para destrabar la cadena A66 → A68. La excepción figura en cada PR (R-1). |
| Los criterios de pérdida, folds, violaciones e integración tienen evidencia verificable | Cumplido | §3. |
| El resumen final identifica cualquier bloqueo científico pendiente | Cumplido | §4. |

---

## 2. Inventario de Pull Requests

`merged_by` es el campo `merged_by.login` de la API de GitHub.

| PR | Issue | Autor | Review de otra persona | Último commit | Checks citados (estado final) | Merge; `merged_by` |
|---|---|---|---|---|---|---|
| [#226](https://github.com/jvnioo/NutriGraphDT/pull/226) | [#181](https://github.com/jvnioo/NutriGraphDT/issues/181), A66-P1 | `jvnioo` | Ninguna (excepción autorizada) | `f9ed1d7` | ruff, ruff format, mypy (100 fuentes), `NUTRIGRAPHDT_REQUIRE_GRAPH=1 pytest`: 2532 pasados, 2 omitidos | `bf2ac97`; `jvnioo` |
| [#227](https://github.com/jvnioo/NutriGraphDT/pull/227) | [#179](https://github.com/jvnioo/NutriGraphDT/issues/179), A66-P3 | `jvnioo` | Ninguna (excepción autorizada) | `d7a2d69` | ídem: 2537 pasados, 2 omitidos | `52ebc86`; `jvnioo` |
| [#228](https://github.com/jvnioo/NutriGraphDT/pull/228) | [#183](https://github.com/jvnioo/NutriGraphDT/issues/183), A66-P2 | `jvnioo` | Ninguna (excepción autorizada) | `ca3c4ad` | ídem: 2540 pasados, 2 omitidos | `cad0ab8`; `jvnioo` |
| [#230](https://github.com/jvnioo/NutriGraphDT/pull/230) | [#184](https://github.com/jvnioo/NutriGraphDT/issues/184), A66-P4 | `jvnioo` | Ninguna (excepción autorizada) | `54b3aed` | ídem: 2557 pasados, 2 omitidos | `ee23efc`; `jvnioo` |

Los dos tests omitidos en todas las corridas son las figuras de `test_plot_gnn_runs_script.py`,
que requieren matplotlib. Cada rama estaba al día con `main` al mergear, así que los checks de
cada PR corresponden al estado integrado de su merge.

---

## 3. Evidencia por criterio

### A66-P1: pérdida compuesta con registro separado (#181, PR #226)

| Criterio | Evidencia |
|---|---|
| Los registros permiten reconstruir la pérdida total | `test_total_loss_is_rebuilt_from_its_logged_components`: en cada época, `*_total_loss == *_data_loss + λ·*_bio_loss` en `train` y `val`, con la cota de D-06 activa. |
| La selección del mejor estado usa una métrica documentada, nunca la evaluación externa | `SELECTION_DESCRIPTION` (pérdida total en el val interno); el val interno sale de `split_inner_validation` sobre el train del fold (`test_split_inner_validation_agrupa_por_corral`). |
| Reanudación, máscaras y λ = 0 | `test_resumed_training_matches_the_uninterrupted_run` (historial y pesos idénticos), `test_resume_rejects_a_different_configuration`, `test_masked_animals_do_not_contribute_to_bio_loss` y `test_zero_lambda_never_calls_constraint_path`. |

### A66-P2: validación repetida por semillas y folds (#183, PR #228)

| Criterio | Evidencia |
|---|---|
| Ningún corral está en más de un fold de una semilla ni interviene en su propio ajuste | `verify_plan` en los consumidores (#172, `test_cv_consumers.py`); `run_compositional_fold` rechaza un corral compartido entre train y test o entre train y val interno (`test_run_compositional_fold_rechaza_un_corral_en_train_y_test`, `test_folds_never_share_animals_or_pens`). |
| Las tablas rastrean cada agregado a sus corridas | `seed`, `fold`, `model` y `edges_arm` en `fold_metrics.csv`, `epoch_violations.csv` y `folds.csv`; `train_seed` y `run_id` en `folds.csv` (test de integración del script). |
| Folds sin algún día de muestreo | Se calculan desde el plan (`fold_table`) y se nombran en el reporte y en `run.json` (`missing_day_folds`). |

### A66-P3: violaciones por época (#179, PR #227)

| Criterio | Evidencia |
|---|---|
| Un caso pequeño reproduce tasa, magnitud y denominador | `test_violation_log_reproduces_a_hand_computed_case`: p_p = 0,75 da h = 0,25, VR = 33,3 %, VMM = 0,25/3, VWM = 0,25, FR = 66,7 % y un animal excluido del denominador. |
| Los registros distinguen train, validación y evaluación, sin mezclar unidades | `subset` ∈ {`train`, `val`, `test`}, una fila por restricción con su unidad; `aggregate_violation_log` rechaza unidades mezcladas (`test_violation_aggregate_rejects_mixed_units`). |
| El monitoreo es independiente de la pérdida | `test_monitoring_with_zero_lambda_does_not_change_training`: con λ = 0, pesos e historial idénticos con y sin monitoreo. |

### A66-P4: integración del ciclo completo (#184, PR #230)

| Criterio | Evidencia |
|---|---|
| El flujo completo corre sin datos reales ni descargas | `tests/integration/test_constrained_cycle_synthetic.py`: cohorte sintética, plan por corral, pérdida compuesta, violaciones, checkpoint, recarga, agregación y reanudación. |
| Alterar λ, los folds o el checkpoint produce una falla detectable | `test_altered_lambda_is_detected_when_resuming`, `test_altered_folds_are_rejected` y `test_altered_checkpoint_is_detected`. |
| El test no se omite si el extra `graph` está disponible | Solo usa `importorskip` para torch, torch-geometric y scikit-learn, y `NUTRIGRAPHDT_REQUIRE_GRAPH=1` hace fallar la sesión si falta `graph`. En las corridas citadas no se omitió. |

---

## 4. Observaciones y bloqueos pendientes

### R-1 · Sin revisión independiente registrada

- **Estado:** **Decisión del líder (`jvnioo`, 02-11-2026):** se acepta la excepción documentada: los PRs se integraron con la excepción autorizada el 01-11-2026, sin review `APPROVED` en GitHub, que no se puede registrar retroactivamente. Con esa aceptación explícita el Issue se cierra.

- **Origen:** API de GitHub (§2).
- **Qué ocurre:** los cuatro PRs no tienen review; los mergeó su autor con la excepción del líder.
- **Consecuencia:** el primer criterio de #177 queda **No cumplido**. Una review posterior al
  merge puede registrarse como comentario en cada PR, pero no se convierte en `APPROVED`.
- **Responsable / acción:** un integrante de Desarrollo distinto del autor revisa #226, #227,
  #228 y #230 y deja su revisión escrita en #177.

### B-1 · La penalización de D-06 no actúa en D1 ni en la cohorte sintética observada

- **Estado:** confirmado por el barrido de #178 (λ no cambió ningún fold en D1 ni en el sintético) y por la evaluación sintética de #185 (brazos idénticos).

- **Origen:** D-06 §6. Las fracciones de propionato observadas llegan como máximo a 0,35 en la
  cohorte sintética y a 0,19 en las predicciones de las GNN de D1 (#142), frente a la cota 2/3.
- **Consecuencia:** con salidas composicionales, `L_bio` vale 0 y su gradiente también, así que
  `λ` no cambia el entrenamiento mientras ninguna predicción viole la cota. El barrido de λ
  (#178) y la evaluación pareada (#185) deben mostrarlo con sus números, no suponerlo.
- **Responsable:** Desarrollo, en #178 y #185.

### B-2 · Regla de decisión y δ pendientes de Investigación

- **Estado:** resuelta. Investigación emitió la respuesta a A55 (PR #217) y Desarrollo la aplicó en #244: δ = 0,5 pp, regla por IC con seis categorías y matriz de la Tabla 5.

- **Origen:** P-02 a P-06 de la revisión A55 (#158). La respuesta de Investigación (PR #217) está
  en borrador con cambios pedidos por el sublíder: δ = 0,5 pp provisional y la regla por IC
  corregido.
- **Consecuencia:** el protocolo vigente todavía usa δ_ROPE = 1,0 pp (provisional de
  Desarrollo) y la matriz de §5 sin reescribir. Las comparaciones de #185 informan Δ e IC, pero su
  clasificación depende de esa respuesta.
- **Responsable:** Investigación (#217) y Desarrollo (#158).

### B-3 · Taxones aislados

- **Estado:** resuelta. Investigación decidió en #236 y #239; Desarrollo implementó #175 y #266.

- **Origen:** S-04 sin entregar; #175 bloqueado.
- **Consecuencia:** en D1 la GNN usa los taxones solo por la lectura media; la ventaja estructural
  sigue sin probar.
- **Responsable:** Investigación (tabla S-04 curada) y Desarrollo (#175).

---

## 5. Verificación y cierre de #177

Cerrado el 02-11-2026: la evidencia de §3 cubre los criterios de A66, B-1 y B-2 están resueltas,
B-3 sigue en Investigación (#236, #239) y R-1 queda como excepción aceptada por el líder.
