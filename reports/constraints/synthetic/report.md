# Evaluación pareada con y sin restricciones en `synthetic_cohort` (A68-P2, #185)

Generado con `python scripts/evaluate_constraints.py` en 1444 s.

## Método

- **Datos:** 60 animales; plan `configs/splits/synthetic_cohort_cv.json` (k = 5, semillas [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]).
- **Objetivo y métricas:** objetivo composicional del contrato v2 §1 (`COMPOSITIONAL_TARGET_VERSION = 1.0.0`) y métricas de D-03, globales y por día.
- **Brazos pareados (protocolo §1.3):** `free` (λ = 0) y `constrained` (λ elegida por el barrido de #178: `homo_sage` λ = 0.1, `hetero_sage` λ = 0.1, `hetero_gat` λ = 0.1), con los términos ['d06.hydrogen.propionate_bound'], en los mismos folds y con la misma semilla de entrenamiento (`42000 + semilla·100 + fold`). Escalado, val interno y detención temprana solo con el train de cada fold.
- **Entrenamiento:** YAML por omisión de cada variante en `configs/models/`; máx. 200 épocas, paciencia 20, dispositivo `cuda`.
- **Estado de D-06:** v1.0 (29-10-2026), una sola restricción, `d06.hydrogen.propionate_bound` (p_p ≤ 2/3). Se monitorean todas las restricciones del catálogo (contrato 1.0.0).

## Resultados globales (test de cada fold; media ± std entre folds)

| Variante | Brazo | MAE fracciones (pp) | R² fracciones | MAE ln T | MAE reconstruido |
|---|---|---:|---:|---:|---:|
| `homo_sage` | free | 5.10 ± 0.65 | -0.23 ± 0.28 | 0.12 ± 0.02 | 6.73 ± 0.68 |
| `homo_sage` | constrained | 5.10 ± 0.65 | -0.23 ± 0.28 | 0.12 ± 0.02 | 6.73 ± 0.68 |
| `hetero_sage` | free | 5.15 ± 0.67 | -0.27 ± 0.26 | 0.12 ± 0.02 | 6.86 ± 0.71 |
| `hetero_sage` | constrained | 5.15 ± 0.67 | -0.27 ± 0.26 | 0.12 ± 0.02 | 6.86 ± 0.71 |
| `hetero_gat` | free | 5.18 ± 0.65 | -0.29 ± 0.32 | 0.12 ± 0.02 | 6.91 ± 0.72 |
| `hetero_gat` | constrained | 5.18 ± 0.65 | -0.29 ± 0.32 | 0.12 ± 0.02 | 6.91 ± 0.72 |

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
| `homo_sage` | `fraction_mae_pp` | 5.1033 | 5.1033 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `fraction_r2` | -0.2343 | -0.2343 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `log_total_mae` | 0.1172 | 0.1172 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `reconstructed_mae` | 6.7264 | 6.7264 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `homo_sage` | `VR_percent:d06.hydrogen.propionate_bound` | 0.0000 | 0.0000 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `fraction_mae_pp` | 5.1510 | 5.1510 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `fraction_r2` | -0.2657 | -0.2657 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `log_total_mae` | 0.1207 | 0.1207 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `reconstructed_mae` | 6.8611 | 6.8611 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_sage` | `VR_percent:d06.hydrogen.propionate_bound` | 0.0000 | 0.0000 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `fraction_mae_pp` | 5.1779 | 5.1779 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `fraction_r2` | -0.2922 | -0.2922 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `log_total_mae` | 0.1211 | 0.1211 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `reconstructed_mae` | 6.9133 | 6.9133 | +0.0000 | [+0.0000; +0.0000] | — | — | — |
| `hetero_gat` | `VR_percent:d06.hydrogen.propionate_bound` | 0.0000 | 0.0000 | +0.0000 | [+0.0000; +0.0000] | — | — | — |

## Decisión de §5 del protocolo

Métrica primaria: MAE macro de fracciones (`all`). δ = 0.5 pp (P-02, provisional). Paso 1: VR = 0 de la cota de D-06 en el test de todos los folds del brazo restringido. Paso 2: categoría de la Tabla 4 con el IC de Δ. Paso 3: sin folds fallidos y `_std` ≤ 1.25 × la del brazo libre.

| Variante | Paso 1 | Categoría de Δ | `_std` free / constrained | Paso 3 | Clasificación | Decisión |
|---|---|---|---|---|---|---|
| `homo_sage` | cumple | 3. Equivalente | 0.649 / 0.649 | cumple | Factibilidad sin costo | Aprobado |
| `hetero_sage` | cumple | 3. Equivalente | 0.666 / 0.666 | cumple | Factibilidad sin costo | Aprobado |
| `hetero_gat` | cumple | 3. Equivalente | 0.654 / 0.654 | cumple | Factibilidad sin costo | Aprobado |

## Advertencias y limitaciones

- **Brazos idénticos.** Si Δ = 0 en todos los folds, la restricción no cambió el entrenamiento: la clasificación «Factibilidad sin costo» significa entonces que no costó nada porque no hizo nada, no que mejore la plausibilidad.
- **Penalización inactiva si nadie viola la cota.** Con salidas composicionales, `L_bio` vale 0 y su gradiente también mientras ninguna predicción supere p_p = 2/3: en ese caso los dos brazos coinciden (D-06 §6).
- **Cohorte sintética.** Sus animales no son reales: cada uno es su propio grupo y no hay dietas ni días de muestreo. Sirve para comprobar el método, no la biología.
- Folds fallidos: 0 (`status = error` en `folds.csv`).

## Archivos

`metrics.csv`, `fold_metrics.csv`, `violations.csv`, `epoch_violations.csv`, `violations_summary.csv`, `paired.csv`, `folds.csv`, `predictions.csv` y `run.json`. Cada fila de `folds.csv` enlaza su corrida (`run_id`) con checkpoint en `runs_dir`.
