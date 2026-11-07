# Evaluación pareada con y sin restricciones en `D1_holofood` (A68-P2, #185)

Generado con `python scripts/evaluate_constraints.py` en 749 s.

## Método

- **Datos:** 56 animales; plan `configs/splits/d1_holofood_cv.json` (k = 5, semillas [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]).
- **Objetivo y métricas:** objetivo composicional del contrato v2 §1 (`COMPOSITIONAL_TARGET_VERSION = 1.0.0`) y métricas de D-03, globales y por día.
- **Brazos pareados (protocolo §1.3):** `free` (λ = 0) y `constrained` (λ elegida por el barrido de #178: `homo_sage` λ = 0.1, `hetero_sage` λ = 0.1, `hetero_gat` λ = 0.1), con los términos ['d06.hydrogen.propionate_bound'], en los mismos folds y con la misma semilla de entrenamiento (`42000 + semilla·100 + fold`). Escalado, val interno y detención temprana solo con el train de cada fold.
- **Entrenamiento:** YAML por omisión de cada variante en `configs/models/`; máx. 200 épocas, paciencia 20, dispositivo `cuda`.
- **Estado de D-06:** v1.0 (29-10-2026), una sola restricción, `d06.hydrogen.propionate_bound` (p_p ≤ 2/3). Se monitorean todas las restricciones del catálogo (contrato 1.0.0).

## Resultados globales (test de cada fold; media ± std entre folds)

| Variante | Brazo | MAE fracciones (pp) | R² fracciones | MAE ln T | MAE reconstruido |
|---|---|---:|---:|---:|---:|
| `homo_sage` | free | 4.19 ± 0.75 | -0.08 ± 0.41 | 0.27 ± 0.08 | 7.92 ± 1.46 |
| `homo_sage` | constrained | 4.19 ± 0.75 | -0.08 ± 0.41 | 0.27 ± 0.08 | 7.92 ± 1.46 |
| `hetero_sage` | free | 4.11 ± 0.71 | -0.02 ± 0.35 | 0.27 ± 0.08 | 7.93 ± 1.46 |
| `hetero_sage` | constrained | 4.11 ± 0.71 | -0.02 ± 0.35 | 0.27 ± 0.08 | 7.93 ± 1.46 |
| `hetero_gat` | free | 4.07 ± 0.70 | -0.02 ± 0.38 | 0.27 ± 0.07 | 7.77 ± 1.37 |
| `hetero_gat` | constrained | 4.07 ± 0.70 | -0.02 ± 0.38 | 0.27 ± 0.07 | 7.77 ± 1.37 |

Referencias de #140 (mismo plan, MAE de fracciones en pp):

- `dummy_mean`: 4.63 ± 0.75
- `day_only`: 4.03 ± 0.64

## MAE de fracciones por día de muestreo (pp)

| Variante | Brazo | Día 7 | Día 21 | Día 35 |
|---|---|---:|---:|---:|
| `homo_sage` | free | 4.69 ± 1.39 | 3.38 ± 1.10 | 4.14 ± 0.87 |
| `homo_sage` | constrained | 4.69 ± 1.39 | 3.38 ± 1.10 | 4.14 ± 0.87 |
| `hetero_sage` | free | 4.58 ± 1.28 | 3.43 ± 1.15 | 4.03 ± 0.85 |
| `hetero_sage` | constrained | 4.58 ± 1.28 | 3.43 ± 1.15 | 4.03 ± 0.85 |
| `hetero_gat` | free | 4.58 ± 1.35 | 3.20 ± 1.15 | 4.03 ± 0.85 |
| `hetero_gat` | constrained | 4.58 ± 1.35 | 3.20 ± 1.15 | 4.03 ± 0.85 |

## Violaciones en el test del fold

VR y FR en %, media ± std entre folds; VWM es el peor caso de todos los folds, en la unidad de cada restricción. Las estructurales valen 0 por construcción en la salida composicional.

| Variante | Brazo | Restricción | Unidad | VR (%) | VWM (máx.) | FR (%) |
|---|---|---|---|---:|---:|---:|
| `homo_sage` | free | `d06.hydrogen.propionate_bound` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | free | `structural.non_negative.concentrations.acetate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | free | `structural.non_negative.concentrations.butyrate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | free | `structural.non_negative.concentrations.propionate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | free | `structural.non_negative.fractions.acetate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | free | `structural.non_negative.fractions.butyrate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | free | `structural.non_negative.fractions.propionate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | free | `structural.simplex_closure` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `d06.hydrogen.propionate_bound` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `structural.non_negative.concentrations.acetate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `structural.non_negative.concentrations.butyrate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `structural.non_negative.concentrations.propionate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `structural.non_negative.fractions.acetate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `structural.non_negative.fractions.butyrate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `structural.non_negative.fractions.propionate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `homo_sage` | constrained | `structural.simplex_closure` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `d06.hydrogen.propionate_bound` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `structural.non_negative.concentrations.acetate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `structural.non_negative.concentrations.butyrate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `structural.non_negative.concentrations.propionate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `structural.non_negative.fractions.acetate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `structural.non_negative.fractions.butyrate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `structural.non_negative.fractions.propionate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | free | `structural.simplex_closure` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `d06.hydrogen.propionate_bound` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `structural.non_negative.concentrations.acetate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `structural.non_negative.concentrations.butyrate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `structural.non_negative.concentrations.propionate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `structural.non_negative.fractions.acetate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `structural.non_negative.fractions.butyrate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `structural.non_negative.fractions.propionate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_sage` | constrained | `structural.simplex_closure` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `d06.hydrogen.propionate_bound` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `structural.non_negative.concentrations.acetate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `structural.non_negative.concentrations.butyrate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `structural.non_negative.concentrations.propionate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `structural.non_negative.fractions.acetate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `structural.non_negative.fractions.butyrate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `structural.non_negative.fractions.propionate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | free | `structural.simplex_closure` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `d06.hydrogen.propionate_bound` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `structural.non_negative.concentrations.acetate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `structural.non_negative.concentrations.butyrate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `structural.non_negative.concentrations.propionate` | mmol/kg | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `structural.non_negative.fractions.acetate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `structural.non_negative.fractions.butyrate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `structural.non_negative.fractions.propionate` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |
| `hetero_gat` | constrained | `structural.simplex_closure` | 1 | 0.00 ± 0.00 | 0 | 100.00 ± 0.00 |

## Comparación pareada `constrained − free` (protocolo §4.2)

t corregido de Nadeau y Bengio (n_test/n_train = 0.250), IC 95 % bilateral, Wilcoxon sobre las medias por semilla y d de Cohen pareada. Si Δ = 0 en todos los folds, los dos brazos son idénticos y no hay estadístico.

| Variante | Métrica | free | constrained | Δ | IC 95 % | p (t corr.) | p (Wilcoxon) | d |
|---|---|---:|---:|---:|---|---:|---:|---:|
| `homo_sage` | `fraction_mae_pp` | 4.1944 | 4.1944 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `fraction_r2` | -0.0766 | -0.0766 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `log_total_mae` | 0.2704 | 0.2704 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `reconstructed_mae` | 7.9156 | 7.9156 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `VR_percent:d06.hydrogen.propionate_bound` | 0.0000 | 0.0000 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `fraction_mae_pp` | 4.1069 | 4.1069 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `fraction_r2` | -0.0221 | -0.0221 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `log_total_mae` | 0.2715 | 0.2715 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `reconstructed_mae` | 7.9284 | 7.9284 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `VR_percent:d06.hydrogen.propionate_bound` | 0.0000 | 0.0000 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `fraction_mae_pp` | 4.0698 | 4.0698 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `fraction_r2` | -0.0208 | -0.0208 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `log_total_mae` | 0.2685 | 0.2685 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `reconstructed_mae` | 7.7665 | 7.7665 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `VR_percent:d06.hydrogen.propionate_bound` | 0.0000 | 0.0000 | +0.0000 | [+0.0000; +0.0000] | — | — | — |

## Decisión de §5 del protocolo

Métrica primaria: MAE macro de fracciones (`all`). δ = 0.5 pp (P-02, provisional). Paso 1: VR = 0 de la cota de D-06 en el test de todos los folds del brazo restringido. Paso 2: categoría de la Tabla 4 con el IC de Δ. Paso 3: sin folds fallidos y `_std` ≤ 1.25 × la del brazo libre.

| Variante | Paso 1 | Categoría de Δ | `_std` free / constrained | Paso 3 | Clasificación | Decisión |
|---|---|---|---|---|---|---|
| `homo_sage` | cumple | 3. Equivalente | 0.751 / 0.751 | cumple | Factibilidad sin costo | Aprobado |
| `hetero_sage` | cumple | 3. Equivalente | 0.707 / 0.707 | cumple | Factibilidad sin costo | Aprobado |
| `hetero_gat` | cumple | 3. Equivalente | 0.701 / 0.701 | cumple | Factibilidad sin costo | Aprobado |

## Advertencias y limitaciones

- **Brazos idénticos.** Si Δ = 0 en todos los folds, la restricción no cambió el entrenamiento: la clasificación «Factibilidad sin costo» significa entonces que no costó nada porque no hizo nada, no que mejore la plausibilidad.
- **Penalización inactiva si nadie viola la cota.** Con salidas composicionales, `L_bio` vale 0 y su gradiente también mientras ninguna predicción supere p_p = 2/3: en ese caso los dos brazos coinciden (D-06 §6).
- **Grafo con estructura funcional anotada, no mecanística (#256).** 38 géneros con `has_capacity` hacia 7 KO, y los taxones llevan su linaje por familia multiplicado por la abundancia (#175, #266). La ruta llega al 36,1 % de las lecturas a género para acetato, al 35,8 % para butirato y al 2,1 % para propionato. Capacidad anotada no es actividad demostrada, y no se afirma ningún efecto de la dieta a través del microbioma (#258).
- **Desbalance 34/15/7 y dieta confundida con el día** (protocolo §6.2): toda comparación entre tratamientos es exploratoria.
- **Folds sin algún día (3):** semilla 3, fold 3: sin el día 21; semilla 7, fold 3: sin el día 21; semilla 8, fold 1: sin el día 21; esas celdas se omiten de la agregación por día (`_n`).
- Folds fallidos: 0 (`status = error` en `folds.csv`).

## Archivos

`metrics.csv`, `fold_metrics.csv`, `violations.csv`, `epoch_violations.csv`, `violations_summary.csv`, `paired.csv`, `folds.csv`, `predictions.csv` y `run.json`. Cada fila de `folds.csv` enlaza su corrida (`run_id`) con checkpoint en `runs_dir`.
