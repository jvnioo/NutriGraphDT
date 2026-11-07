# Por qué la GNN no aprovecha el perfil por familia en D1: diagnóstico (#268)

Generado con `python scripts/diagnose_gnn_microbiome.py`. La interpretación está en [`gnn-microbiome-diagnosis.md`](../../../docs/models/gnn-microbiome-diagnosis.md).

## Escala de la lectura (solo train interno)

Desviación entre animales de la media por grafo de cada columna, tras escalar (mediana):

| Bloque | Desviación |
|---|---:|
| `taxon` | 0.026 |
| `host` | 1.015 |
| `diet` | 1.015 |

## Curvas de `hetero_sage` sin detención temprana (solo train y val interno)

| Fold | Mejor época | Época 1: train / val | Época 5: train / val | Época 10: train / val | Época 20: train / val | Época 50: train / val | Época 100: train / val | Época 200: train / val |
|---:|---:|---|---|---|---|---|---|---|
| 0 | 3 | 1.13 / 1.08 | 0.83 / 1.10 | 0.70 / 1.07 | 0.58 / 1.44 | 0.40 / 1.43 | 0.21 / 1.35 | 0.11 / 1.20 |
| 1 | 4 | 1.02 / 0.88 | 0.75 / 0.86 | 0.68 / 0.89 | 0.56 / 0.98 | 0.41 / 1.06 | 0.22 / 1.16 | 0.14 / 1.10 |
| 2 | 16 | 1.02 / 2.11 | 0.89 / 1.78 | 0.73 / 1.82 | 0.65 / 1.82 | 0.49 / 1.89 | 0.30 / 2.15 | 0.13 / 2.34 |
| 3 | 21 | 1.07 / 1.25 | 0.88 / 1.19 | 0.80 / 1.03 | 0.67 / 0.92 | 0.41 / 1.40 | 0.30 / 2.14 | 0.15 / 2.05 |
| 4 | 19 | 1.08 / 0.78 | 0.86 / 0.73 | 0.81 / 0.52 | 0.68 / 0.51 | 0.42 / 0.68 | 0.27 / 0.91 | 0.18 / 1.08 |

## Grilla: `val_data_loss` media (semillas 0 y 1; el test no interviene)

| Variante | Configuración actual | Elegida | Pérdida elegida |
|---|---:|---|---:|
| `homo_sage` | 0.8937 | `profile1_linear0_wd0.1_h64` | 0.8655 |
| `hetero_sage` | 0.8833 | `profile1_linear0_wd0.01_h64` | 0.8518 |
| `hetero_gat` | 0.8656 | `profile0_linear0_wd0.0001_h64` | 0.8656 |

Efecto de cada factor, promediando sobre los demás:

| Variante | Factor | Nivel y pérdida media |
|---|---|---|
| `homo_sage` | `profile_block` | False: 0.9020, True: 0.8960 |
| `homo_sage` | `linear_head` | False: 0.8905, True: 0.9076 |
| `homo_sage` | `weight_decay` | 0.0001: 0.9038, 0.01: 0.9022, 0.1: 0.8911 |
| `homo_sage` | `hidden_channels` | 16: 0.9119, 64: 0.8861 |
| `hetero_sage` | `profile_block` | False: 0.8867, True: 0.8894 |
| `hetero_sage` | `linear_head` | False: 0.8818, True: 0.8942 |
| `hetero_sage` | `weight_decay` | 0.0001: 0.8874, 0.01: 0.8874, 0.1: 0.8893 |
| `hetero_sage` | `hidden_channels` | 16: 0.9050, 64: 0.8711 |
| `hetero_gat` | `profile_block` | False: 0.8936, True: 0.8973 |
| `hetero_gat` | `linear_head` | False: 0.8891, True: 0.9018 |
| `hetero_gat` | `weight_decay` | 0.0001: 0.8921, 0.01: 0.8969, 0.1: 0.8974 |
| `hetero_gat` | `hidden_channels` | 16: 0.9111, 64: 0.8798 |

## Evaluación única en el test de los folds

| Variante | Configuración | `fraction_mae_pp` | `fraction_r2` | `log_total_mae` | `reconstructed_mae` |
|---|---|---:|---:|---:|---:|
| `homo_sage` | `profile1_linear0_wd0.1_h64` | 3.92 ± 0.71 | 0.08 ± 0.33 | 0.26 ± 0.07 | 7.59 ± 1.42 |
| `hetero_sage` | `profile1_linear0_wd0.01_h64` | 3.90 ± 0.70 | 0.10 ± 0.33 | 0.27 ± 0.08 | 7.76 ± 1.60 |
| `hetero_gat` | `profile0_linear0_wd0.0001_h64` | 4.07 ± 0.70 | -0.02 ± 0.38 | 0.27 ± 0.07 | 7.77 ± 1.37 |

Violaciones de la cota de D-06 en el test: 0 de 150 folds con VR > 0.

## Comparaciones pareadas de `fraction_mae_pp`

`Δ = elegida − referencia`, con el t corregido de Nadeau y Bengio; negativo favorece a la elegida. Las demás métricas están en `paired.csv`.

| Comparación | Variante | Elegida | Referencia | Δ | IC 95 % | p |
|---|---|---:|---:|---:|---|---:|
| Frente a la configuración actual | `homo_sage` | 3.92 | 4.19 | -0.27 | [-0.65; +0.11] | 0.162 |
| Frente a ridge por familia | `homo_sage` | 3.92 | 3.69 | +0.24 | [-0.13; +0.60] | 0.196 |
| Frente a ridge sobre el diseño | `homo_sage` | 3.92 | 3.98 | -0.05 | [-0.44; +0.34] | 0.788 |
| Frente a la configuración actual | `hetero_sage` | 3.90 | 4.11 | -0.21 | [-0.68; +0.26] | 0.374 |
| Frente a ridge por familia | `hetero_sage` | 3.90 | 3.69 | +0.21 | [-0.15; +0.57] | 0.247 |
| Frente a ridge sobre el diseño | `hetero_sage` | 3.90 | 3.98 | -0.08 | [-0.45; +0.29] | 0.668 |
| Frente a la configuración actual | `hetero_gat` | 4.07 | 4.07 | +0.00 | [+0.00; +0.00] | — |
| Frente a ridge por familia | `hetero_gat` | 4.07 | 3.69 | +0.38 | [-0.01; +0.78] | 0.057 |
| Frente a ridge sobre el diseño | `hetero_gat` | 4.07 | 3.98 | +0.09 | [-0.35; +0.53] | 0.672 |

## Limitaciones

- Es un análisis exploratorio motivado por el resultado de #266: la evaluación es única, pero no independiente de lo que ya se había visto en ese test.
- La selección usa 10 folds con unos 9 animales de val interno; la pérdida es ruidosa, y la mejor época de cada fold la vuelve optimista.
- Ninguna evaluación de D1 se llama «mecanística» (#256).
