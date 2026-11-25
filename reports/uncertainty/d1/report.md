# Incertidumbre, calibración y coherencia de las predicciones de D1 (A75, #282)

Generado con `python scripts/estimate_uncertainty.py`. Modelo: `hetero_sage` con `TaxonIdentityConfig()`; plan de #139 con las semillas [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] (50 folds); ensamble de 5 modelos por fold y MC-dropout de 30 pasadas. Dispositivo `cpu`.

**Revisión de Desarrollo, no aprobación de Investigación.** Con 56 animales, la cobertura por día es **muy ruidosa**: cada día tiene pocos animales por fold.

## Elección del método (solo con el val interno)

En cada fold se elige el método con menor log-verosimilitud negativa (NLL) de la normal predictiva en el val interno, sin escalar; el test no interviene. `ensemble`: 12 folds, `mc_dropout`: 38 folds.

## Cobertura en el val interno (antes y después del factor)

Media entre folds ± desviación entre folds. El factor de cada salida se ajusta al 80 % con el mismo val interno, así que su cobertura después del ajuste es optimista por construcción.

| Método | Salida | 50 % antes | 50 % después | 80 % antes | 80 % después | 90 % antes | 90 % después |
|---|---|---:|---:|---:|---:|---:|---:|
| `ensemble` | `log_propionate_acetate` | 6 % ± 8 % | 46 % ± 14 % | 13 % ± 12 % | 78 % ± 1 % | 20 % ± 13 % | 90 % ± 6 % |
| `ensemble` | `log_butyrate_acetate` | 10 % ± 11 % | 47 % ± 14 % | 20 % ± 13 % | 78 % ± 1 % | 25 % ± 14 % | 89 % ± 6 % |
| `ensemble` | `log_total` | 9 % ± 9 % | 48 % ± 13 % | 16 % ± 11 % | 78 % ± 1 % | 21 % ± 13 % | 88 % ± 7 % |
| `ensemble` | `acetate` | 11 % ± 9 % | 58 % ± 12 % | 21 % ± 11 % | 87 % ± 8 % | 28 % ± 11 % | 94 % ± 7 % |
| `ensemble` | `propionate` | 7 % ± 7 % | 47 % ± 14 % | 17 % ± 12 % | 76 % ± 6 % | 20 % ± 12 % | 88 % ± 7 % |
| `ensemble` | `butyrate` | 12 % ± 11 % | 49 % ± 14 % | 19 % ± 11 % | 79 % ± 7 % | 25 % ± 14 % | 88 % ± 6 % |
| `mc_dropout` | `log_propionate_acetate` | 7 % ± 8 % | 43 % ± 14 % | 12 % ± 9 % | 78 % ± 1 % | 15 % ± 10 % | 87 % ± 7 % |
| `mc_dropout` | `log_butyrate_acetate` | 10 % ± 9 % | 41 % ± 13 % | 18 % ± 13 % | 78 % ± 1 % | 23 % ± 14 % | 90 % ± 6 % |
| `mc_dropout` | `log_total` | 8 % ± 9 % | 41 % ± 15 % | 16 % ± 12 % | 78 % ± 1 % | 21 % ± 14 % | 89 % ± 7 % |
| `mc_dropout` | `acetate` | 12 % ± 9 % | 53 % ± 13 % | 21 % ± 12 % | 82 % ± 10 % | 26 % ± 14 % | 92 % ± 7 % |
| `mc_dropout` | `propionate` | 8 % ± 9 % | 43 % ± 13 % | 13 % ± 10 % | 77 % ± 5 % | 18 % ± 11 % | 86 % ± 7 % |
| `mc_dropout` | `butyrate` | 10 % ± 9 % | 42 % ± 12 % | 18 % ± 13 % | 77 % ± 9 % | 23 % ± 15 % | 90 % ± 6 % |
| `selected` | `log_propionate_acetate` | 7 % ± 8 % | 42 % ± 13 % | 13 % ± 9 % | 78 % ± 1 % | 17 % ± 9 % | 87 % ± 7 % |
| `selected` | `log_butyrate_acetate` | 11 % ± 11 % | 42 % ± 14 % | 19 % ± 13 % | 78 % ± 1 % | 25 % ± 14 % | 91 % ± 6 % |
| `selected` | `log_total` | 8 % ± 9 % | 43 % ± 14 % | 17 % ± 12 % | 78 % ± 1 % | 23 % ± 15 % | 89 % ± 7 % |
| `selected` | `acetate` | 12 % ± 9 % | 53 % ± 13 % | 22 % ± 12 % | 82 % ± 10 % | 27 % ± 14 % | 92 % ± 7 % |
| `selected` | `propionate` | 8 % ± 9 % | 43 % ± 13 % | 15 % ± 10 % | 77 % ± 5 % | 19 % ± 10 % | 86 % ± 6 % |
| `selected` | `butyrate` | 12 % ± 11 % | 44 % ± 12 % | 20 % ± 14 % | 77 % ± 8 % | 25 % ± 15 % | 89 % ± 6 % |

## Cobertura en el test de los folds (una sola evaluación)

Método elegido en cada fold, con su factor del val interno. Cobertura media por semilla (cada semilla reparte a los 56 animales), desviación entre semillas, intervalo de Wilson al 95 % con n = animales por semilla y veredicto: `compatible` si el nominal cae en el intervalo; si no, `subcobertura` o `sobrecobertura`.

| Salida | Nivel | Observada | Desv. semillas | Wilson 95 % | Ancho medio | Veredicto |
|---|---:|---:|---:|---|---:|---|
| `log_propionate_acetate` | 50 % | 53 % | 6 % | 41 %–66 % | 0.895 | compatible |
| `log_propionate_acetate` | 80 % | 82 % | 6 % | 70 %–90 % | 1.7 | compatible |
| `log_propionate_acetate` | 90 % | 89 % | 4 % | 79 %–95 % | 2.18 | compatible |
| `log_butyrate_acetate` | 50 % | 34 % | 6 % | 23 %–47 % | 0.411 | subcobertura |
| `log_butyrate_acetate` | 80 % | 63 % | 7 % | 49 %–74 % | 0.781 | subcobertura |
| `log_butyrate_acetate` | 90 % | 76 % | 7 % | 62 %–84 % | 1 | subcobertura |
| `log_total` | 50 % | 43 % | 10 % | 31 %–56 % | 0.375 | compatible |
| `log_total` | 80 % | 71 % | 7 % | 59 %–82 % | 0.713 | compatible |
| `log_total` | 90 % | 81 % | 6 % | 68 %–89 % | 0.915 | subcobertura |
| `acetate` | 50 % | 48 % | 4 % | 36 %–61 % | 0.0791 | compatible |
| `acetate` | 80 % | 76 % | 7 % | 64 %–86 % | 0.155 | compatible |
| `acetate` | 90 % | 86 % | 6 % | 74 %–93 % | 0.202 | compatible |
| `propionate` | 50 % | 52 % | 5 % | 39 %–64 % | 0.0659 | compatible |
| `propionate` | 80 % | 81 % | 5 % | 70 %–90 % | 0.133 | compatible |
| `propionate` | 90 % | 89 % | 6 % | 79 %–95 % | 0.178 | compatible |
| `butyrate` | 50 % | 35 % | 4 % | 24 %–49 % | 0.0575 | subcobertura |
| `butyrate` | 80 % | 66 % | 7 % | 53 %–77 % | 0.11 | subcobertura |
| `butyrate` | 90 % | 78 % | 5 % | 66 %–87 % | 0.142 | subcobertura |

**Conclusión de calibración:** **los intervalos no están calibrados** en el test en 7 de 18 combinaciones de salida y nivel (ver la tabla); no se deben citar como intervalos de ese nivel.

Sin el factor (intervalos crudos de cada método), en el test:

| Método | Salida | 50 % | 80 % | 90 % |
|---|---|---:|---:|---:|
| `ensemble` | `log_propionate_acetate` | 9 % | 19 % | 24 % |
| `ensemble` | `log_butyrate_acetate` | 9 % | 16 % | 19 % |
| `ensemble` | `log_total` | 9 % | 16 % | 21 % |
| `ensemble` | `acetate` | 9 % | 18 % | 23 % |
| `ensemble` | `propionate` | 10 % | 18 % | 24 % |
| `ensemble` | `butyrate` | 9 % | 17 % | 22 % |
| `mc_dropout` | `log_propionate_acetate` | 10 % | 18 % | 23 % |
| `mc_dropout` | `log_butyrate_acetate` | 7 % | 16 % | 21 % |
| `mc_dropout` | `log_total` | 8 % | 17 % | 21 % |
| `mc_dropout` | `acetate` | 8 % | 16 % | 20 % |
| `mc_dropout` | `propionate` | 10 % | 18 % | 23 % |
| `mc_dropout` | `butyrate` | 9 % | 17 % | 21 % |

### Por día de muestreo (test, método elegido, calibrado, 80 %)

| Salida | día 7 | día 21 | día 35 |
|---|---:|---:|---:|
| `log_propionate_acetate` | 64 % ± 7 % (n≈17) | 91 % ± 7 % (n≈9) | 90 % ± 7 % (n≈30) |
| `log_butyrate_acetate` | 55 % ± 9 % (n≈17) | 64 % ± 13 % (n≈9) | 67 % ± 9 % (n≈30) |
| `log_total` | 70 % ± 11 % (n≈17) | 79 % ± 12 % (n≈9) | 69 % ± 8 % (n≈30) |
| `acetate` | 59 % ± 11 % (n≈17) | 78 % ± 17 % (n≈9) | 85 % ± 4 % (n≈30) |
| `propionate` | 63 % ± 7 % (n≈17) | 90 % ± 8 % (n≈9) | 89 % ± 6 % (n≈30) |
| `butyrate` | 62 % ± 10 % (n≈17) | 64 % ± 16 % (n≈9) | 68 % ± 8 % (n≈30) |

## Coherencia bioquímica (A75-P3)

Sobre la predicción de test del modelo de cada fold (el miembro 0 del ensamble, que es el de #266). Estados: `coherente`, `a revisar` o `sin fuente`. Detalle y fuentes en [`docs/models/a75-biochemical-coherence.md`](../../../docs/models/a75-biochemical-coherence.md).

| ID | Comprobación | Resultado | Estado | Fuente |
|---|---|---|---|---|
| A75-C1 | Cierre de las fracciones predichas | máx. abs(p_a + p_p + p_b − 1) = 2.2e-16 en 560 predicciones | coherente | Contrato de datos v2, sección 1 (softmax de (0, z1, z2)) |
| A75-C2 | Cota de D-06: p_p ≤ 2/3 | 0 de 560 sobre la cota; máximo p_p = 0.167 | coherente | docs/research/D-06 — Restricciones bioquímicas para D1.md, secciones 3 y 6 |
| A75-C3 | Soporte empírico del train interno (mínimo y máximo por fracción) | acetate: 0 fuera; propionate: 0 fuera; butyrate: 0 fuera (de 560) | coherente | docs/research/D-06 — Restricciones bioquímicas para D1.md, sección 7; `EmpiricalSupport` de #245 |
| A75-C4-d7 | Fracción media predicha frente a la medida, día 7 | acetate 0.786 (medida 0.792, rango 0.657–0.862); propionate 0.056 (medida 0.060, rango 0.013–0.170); butyrate 0.157 (medida 0.149, rango 0.067–0.235) | coherente | Cohorte oficial de D1 (configs/cohorts/d1_holofood.json), test de los folds |
| A75-C4-d21 | Fracción media predicha frente a la medida, día 21 | acetate 0.782 (medida 0.795, rango 0.749–0.837); propionate 0.071 (medida 0.081, rango 0.031–0.126); butyrate 0.147 (medida 0.124, rango 0.074–0.187) | coherente | Cohorte oficial de D1 (configs/cohorts/d1_holofood.json), test de los folds |
| A75-C4-d35 | Fracción media predicha frente a la medida, día 35 | acetate 0.733 (medida 0.708, rango 0.602–0.801); propionate 0.096 (medida 0.105, rango 0.030–0.227); butyrate 0.172 (medida 0.187, rango 0.087–0.259) | coherente | Cohorte oficial de D1 (configs/cohorts/d1_holofood.json), test de los folds |
| A75-C5 | Fracciones predichas frente a la Tabla 6 de D-06 (medias de grupo) | p_p predicha: media 0.080, máximo 0.167; máximo publicado 0.116 | sin fuente | docs/research/D-06 — Restricciones bioquímicas para D1.md, sección 5 y Tabla 7, N° 4: no hay rangos por animal |

## Limitaciones

- La dispersión de un ensamble de 5 modelos o de 30 pasadas de MC-dropout mide la variabilidad del modelo, no el error de predicción; por eso el factor del val interno puede ser grande.
- El val interno tiene unos 10 animales por fold: el factor de escala de cada fold es ruidoso. No se agrega entre folds porque el val interno de un fold puede contener animales del test de otro.
- Los intervalos en `(z_1, z_2, ln T)` suponen una normal por salida; los de fracciones muestrean `z_1` y `z_2` como independientes.
- El val interno también decide la detención temprana: la NLL y el factor se calculan sobre animales que ya influyeron en el entrenamiento.
