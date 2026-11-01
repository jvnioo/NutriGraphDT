# Evaluación pareada con y sin restricciones (A68-P2, #185)

Este documento describe cómo se entrenan y comparan las variantes GNN con restricciones ($M_C$)
y sin ellas ($M_0$) en D1 y en la cohorte sintética, según el protocolo A55-P1
([`constraints-evaluation-protocol.md`](constraints-evaluation-protocol.md)). Los resultados
están en `reports/constraints/<dataset>/`; cómo se eligió λ está en
[`constraints-lambda-sweep.md`](constraints-lambda-sweep.md) (#178).

## 1. Brazos pareados

`scripts/evaluate_constraints.py --dataset <d1|synthetic>` entrena cada variante (`homo_sage`,
`hetero_sage` y `hetero_gat`, con su YAML por omisión) en **todos** los folds del plan versionado,
con dos brazos:

| Brazo | λ | Términos |
|---|---|---|
| `free` ($M_0$) | 0 | ninguno |
| `constrained` ($M_C$) | la elegida por el barrido para la variante | los de `configs/constraints/lambda_sweep_<dataset>.json` |

Los dos brazos usan los mismos folds y la misma semilla de entrenamiento por fold
(`train_seed_base + semilla·100 + fold`), como exige el pareamiento estricto del protocolo §1.3.
En cada fold, el escalado, el val interno y la detención temprana usan solo el train
(`run_compositional_fold`, #183). Se monitorean todas las restricciones del catálogo (#179) y cada
fold guarda su corrida con checkpoint (#180).

## 2. Artefactos (protocolo §8)

| Archivo | Contenido |
|---|---|
| `report.md` | Método, métricas globales y por día por brazo, violaciones, comparación pareada y advertencias. |
| `metrics.csv` | Métricas de D-03 agregadas por variante, brazo, grupo y métrica (`_mean`, `_std`, `_seed_std`, `_n`). |
| `fold_metrics.csv` | Una fila por semilla, fold, variante, brazo, grupo y métrica. |
| `violations.csv` | Violaciones del test por variante, brazo, fold y restricción; `epoch_violations.csv` trae las de cada época. |
| `violations_summary.csv` | Violaciones del test agregadas entre folds y semillas. |
| `paired.csv` | `constrained − free` por variante y métrica. |
| `folds.csv` | Estado, semilla de entrenamiento, `run_id` y tamaños de cada fold. |
| `predictions.csv` | `(z_1, z_2, ln T)` de cada animal de test. |
| `run.json` | Commit, SHA-256 del plan (de bytes y canónico), de la configuración de la cohorte, de la selección y de la configuración del barrido; versiones, entorno, semillas y duración. |

## 3. Comparación pareada (protocolo §4.2)

`nutrigraphdt.models.paired_comparison.paired_comparison` calcula, sobre las diferencias por fold
$\Delta_{s,k} = \text{métrica}(M_C) - \text{métrica}(M_0)$:

- el **t corregido** de Nadeau y Bengio:
  $\sigma^2 = (1/(KS) + n_{test}/n_{train})\, s^2_\Delta$, con $KS - 1$ grados de libertad, su
  p bilateral y el IC 95 % bilateral. $n_{test}/n_{train}$ es el cociente medio entre el test de
  cada fold y su train (train interno más val interno);
- **Wilcoxon** sobre las medias por semilla;
- la **d de Cohen** pareada.

La implementación reproduce las cifras que Investigación recalculó por su cuenta en la revisión
del PR #217 sobre los reportes de #140 y #142. Por ejemplo, $\Delta$ MAE de `homo_sage` −
`dummy_mean` = −0,74 pp [−1,18; −0,30] (`tests/unit/test_paired_comparison.py`).

Se comparan el MAE macro de fracciones (la métrica primaria que propone P-04), el R² de
fracciones, el MAE de ln T, el MAE reconstruido y el VR de la cota de D-06 en el test.

## 4. Lo que el reporte no decide

La clasificación de §5 (δ, regla por IC y matriz) se está reescribiendo con Investigación (P-02,
P-05 y P-07; #158 y PR #217). El reporte informa Δ, IC, p y violaciones, pero no clasifica. Si la
penalización no actúa porque ninguna predicción viola la cota, los dos brazos coinciden en cada
fold: $\Delta = 0$ y no hay estadístico. Ese resultado se informa como tal.
