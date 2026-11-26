# Incertidumbre y calibración de las predicciones de la cohorte sintética (A101-P1b, #391)

Generado con `python scripts/estimate_uncertainty.py --dataset synthetic`. Modelo: `homo_sage` con sin identidad; plan `configs/splits/synthetic_cohort_cv.json` con las semillas [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] (50 folds); ensamble de 5 modelos por fold y MC-dropout de 30 pasadas. Dispositivo `cpu`.

**Datos sintéticos** (60 animales de `build_synthetic_cohort`): la cobertura describe al modelo sobre la cohorte sintética, no a animales reales, y una diferencia entre escenarios no es un efecto biológico (#296). Es la calibración del intervalo que muestra la plataforma.

## Elección del método (solo con el val interno)

En cada fold se elige el método con menor log-verosimilitud negativa (NLL) de la normal predictiva en el val interno, sin escalar; el test no interviene. `ensemble`: 42 folds, `mc_dropout`: 8 folds.

## Cobertura en el val interno (antes y después del factor)

Media entre folds ± desviación entre folds. El factor de cada salida se ajusta al 80 % con el mismo val interno, así que su cobertura después del ajuste es optimista por construcción.

| Método | Salida | 50 % antes | 50 % después | 80 % antes | 80 % después | 90 % antes | 90 % después |
|---|---|---:|---:|---:|---:|---:|---:|
| `ensemble` | `log_propionate_acetate` | 5 % ± 7 % | 44 % ± 12 % | 13 % ± 11 % | 80 % ± 0 % | 17 % ± 11 % | 89 % ± 7 % |
| `ensemble` | `log_butyrate_acetate` | 9 % ± 8 % | 47 % ± 15 % | 19 % ± 11 % | 80 % ± 0 % | 23 % ± 14 % | 90 % ± 7 % |
| `ensemble` | `log_total` | 10 % ± 8 % | 44 % ± 14 % | 17 % ± 10 % | 80 % ± 0 % | 21 % ± 14 % | 89 % ± 7 % |
| `ensemble` | `acetate` | 8 % ± 9 % | 44 % ± 15 % | 14 % ± 12 % | 76 % ± 9 % | 18 % ± 14 % | 85 % ± 10 % |
| `ensemble` | `propionate` | 7 % ± 7 % | 51 % ± 10 % | 13 % ± 9 % | 81 % ± 7 % | 19 % ± 11 % | 90 % ± 7 % |
| `ensemble` | `butyrate` | 8 % ± 8 % | 51 % ± 15 % | 18 % ± 14 % | 82 % ± 7 % | 26 % ± 15 % | 91 % ± 7 % |
| `mc_dropout` | `log_propionate_acetate` | 5 % ± 6 % | 47 % ± 14 % | 9 % ± 9 % | 80 % ± 0 % | 12 % ± 12 % | 89 % ± 6 % |
| `mc_dropout` | `log_butyrate_acetate` | 6 % ± 7 % | 47 % ± 13 % | 11 % ± 9 % | 80 % ± 0 % | 16 % ± 11 % | 89 % ± 6 % |
| `mc_dropout` | `log_total` | 6 % ± 8 % | 50 % ± 14 % | 10 % ± 8 % | 80 % ± 0 % | 14 % ± 10 % | 88 % ± 7 % |
| `mc_dropout` | `acetate` | 6 % ± 9 % | 44 % ± 15 % | 10 % ± 12 % | 74 % ± 9 % | 13 % ± 13 % | 84 % ± 8 % |
| `mc_dropout` | `propionate` | 6 % ± 8 % | 51 % ± 15 % | 9 % ± 9 % | 81 % ± 7 % | 12 % ± 10 % | 89 % ± 7 % |
| `mc_dropout` | `butyrate` | 7 % ± 9 % | 52 % ± 12 % | 11 % ± 12 % | 81 % ± 9 % | 15 % ± 14 % | 90 % ± 8 % |
| `selected` | `log_propionate_acetate` | 5 % ± 6 % | 44 % ± 12 % | 13 % ± 11 % | 80 % ± 0 % | 17 % ± 11 % | 91 % ± 7 % |
| `selected` | `log_butyrate_acetate` | 9 % ± 8 % | 48 % ± 14 % | 18 % ± 11 % | 80 % ± 0 % | 23 % ± 13 % | 90 % ± 7 % |
| `selected` | `log_total` | 10 % ± 8 % | 44 % ± 13 % | 17 % ± 11 % | 80 % ± 0 % | 22 % ± 14 % | 89 % ± 6 % |
| `selected` | `acetate` | 8 % ± 9 % | 43 % ± 15 % | 14 % ± 12 % | 76 % ± 10 % | 18 % ± 14 % | 85 % ± 10 % |
| `selected` | `propionate` | 7 % ± 7 % | 50 % ± 11 % | 13 % ± 10 % | 81 % ± 8 % | 19 % ± 11 % | 90 % ± 7 % |
| `selected` | `butyrate` | 8 % ± 7 % | 51 % ± 14 % | 18 % ± 14 % | 82 % ± 7 % | 25 % ± 15 % | 92 % ± 7 % |

## Cobertura en el test de los folds (una sola evaluación)

Método elegido en cada fold, con su factor del val interno. Cobertura media por semilla (cada semilla reparte a los 60 animales), desviación entre semillas, intervalo de Wilson al 95 % con n = animales por semilla y veredicto: `compatible` si el nominal cae en el intervalo; si no, `subcobertura` o `sobrecobertura`.

| Salida | Nivel | Observada | Desv. semillas | Wilson 95 % | Ancho medio | Veredicto |
|---|---:|---:|---:|---|---:|---|
| `log_propionate_acetate` | 50 % | 46 % | 7 % | 33 %–58 % | 0.65 | compatible |
| `log_propionate_acetate` | 80 % | 75 % | 6 % | 63 %–84 % | 1.23 | compatible |
| `log_propionate_acetate` | 90 % | 85 % | 5 % | 74 %–92 % | 1.58 | compatible |
| `log_butyrate_acetate` | 50 % | 43 % | 7 % | 32 %–56 % | 0.592 | compatible |
| `log_butyrate_acetate` | 80 % | 74 % | 7 % | 61 %–83 % | 1.13 | compatible |
| `log_butyrate_acetate` | 90 % | 82 % | 7 % | 72 %–91 % | 1.44 | compatible |
| `log_total` | 50 % | 44 % | 6 % | 33 %–58 % | 0.218 | compatible |
| `log_total` | 80 % | 72 % | 7 % | 59 %–81 % | 0.415 | compatible |
| `log_total` | 90 % | 82 % | 4 % | 70 %–89 % | 0.532 | subcobertura |
| `acetate` | 50 % | 42 % | 6 % | 30 %–54 % | 0.105 | compatible |
| `acetate` | 80 % | 72 % | 7 % | 59 %–81 % | 0.198 | compatible |
| `acetate` | 90 % | 84 % | 4 % | 72 %–91 % | 0.251 | compatible |
| `propionate` | 50 % | 51 % | 5 % | 39 %–64 % | 0.1 | compatible |
| `propionate` | 80 % | 79 % | 4 % | 68 %–88 % | 0.188 | compatible |
| `propionate` | 90 % | 88 % | 4 % | 78 %–94 % | 0.239 | compatible |
| `butyrate` | 50 % | 49 % | 7 % | 36 %–61 % | 0.0862 | compatible |
| `butyrate` | 80 % | 76 % | 7 % | 65 %–86 % | 0.163 | compatible |
| `butyrate` | 90 % | 86 % | 5 % | 76 %–93 % | 0.208 | compatible |

**Conclusión de calibración:** **los intervalos no están calibrados** en el test en 1 de 18 combinaciones de salida y nivel (ver la tabla); no se deben citar como intervalos de ese nivel.

Sin el factor (intervalos crudos de cada método), en el test:

| Método | Salida | 50 % | 80 % | 90 % |
|---|---|---:|---:|---:|
| `ensemble` | `log_propionate_acetate` | 7 % | 13 % | 16 % |
| `ensemble` | `log_butyrate_acetate` | 10 % | 20 % | 24 % |
| `ensemble` | `log_total` | 9 % | 16 % | 20 % |
| `ensemble` | `acetate` | 7 % | 12 % | 14 % |
| `ensemble` | `propionate` | 6 % | 12 % | 16 % |
| `ensemble` | `butyrate` | 9 % | 20 % | 22 % |
| `mc_dropout` | `log_propionate_acetate` | 4 % | 6 % | 8 % |
| `mc_dropout` | `log_butyrate_acetate` | 6 % | 12 % | 15 % |
| `mc_dropout` | `log_total` | 6 % | 10 % | 12 % |
| `mc_dropout` | `acetate` | 4 % | 8 % | 11 % |
| `mc_dropout` | `propionate` | 3 % | 8 % | 11 % |
| `mc_dropout` | `butyrate` | 6 % | 11 % | 15 % |

Con el factor del val interno de cada fold, por método, en el test:

| Método | Salida | 50 % | 80 % | 90 % |
|---|---|---:|---:|---:|
| `ensemble` | `log_propionate_acetate` | 47 % (compatible) | 75 % (compatible) | 86 % (compatible) |
| `ensemble` | `log_butyrate_acetate` | 45 % (compatible) | 75 % (compatible) | 84 % (compatible) |
| `ensemble` | `log_total` | 45 % (compatible) | 71 % (compatible) | 81 % (subcobertura) |
| `ensemble` | `acetate` | 42 % (compatible) | 73 % (compatible) | 85 % (compatible) |
| `ensemble` | `propionate` | 52 % (compatible) | 80 % (compatible) | 89 % (compatible) |
| `ensemble` | `butyrate` | 52 % (compatible) | 78 % (compatible) | 87 % (compatible) |
| `mc_dropout` | `log_propionate_acetate` | 48 % (compatible) | 74 % (compatible) | 82 % (subcobertura) |
| `mc_dropout` | `log_butyrate_acetate` | 47 % (compatible) | 71 % (compatible) | 81 % (subcobertura) |
| `mc_dropout` | `log_total` | 49 % (compatible) | 71 % (compatible) | 82 % (subcobertura) |
| `mc_dropout` | `acetate` | 43 % (compatible) | 71 % (compatible) | 81 % (subcobertura) |
| `mc_dropout` | `propionate` | 52 % (compatible) | 78 % (compatible) | 84 % (compatible) |
| `mc_dropout` | `butyrate` | 50 % (compatible) | 76 % (compatible) | 84 % (compatible) |

## Factor para una corrida nueva (`calibration.json`)

Mediana, por salida, de los 50 factores de `mc_dropout` ajustados al 80 % en el val interno de cada fold: `log_propionate_acetate` 12.4, `log_butyrate_acetate` 8.22, `log_total` 9.29. Con el factor de cada fold, `mc_dropout` cubrió en el test: `log_propionate_acetate` 74 %, `log_butyrate_acetate` 71 %, `log_total` 71 %, `acetate` 71 %, `propionate` 78 %, `butyrate` 76 %.

Se aplica solo a una corrida con la misma configuración (conjunto, brazo de aristas, identidad de taxones, modelo y entrenamiento: `IntervalCalibration.mismatches`). La mediana usa los val internos de todos los folds, así que esa cobertura describe el procedimiento por fold, no el factor resumido.

## Coherencia bioquímica (A75-P3)

Sobre la predicción de test del modelo de cada fold (el miembro 0 del ensamble). Estados: `coherente`, `a revisar` o `sin fuente`. En la cohorte sintética no hay días ni Tabla 6 de D-06: A75-C4 compara con la composición generada y se omite A75-C5.

| ID | Comprobación | Resultado | Estado | Fuente |
|---|---|---|---|---|
| A75-C1 | Cierre de las fracciones predichas | máx. abs(p_a + p_p + p_b − 1) = 2.2e-16 en 600 predicciones | coherente | Contrato de datos v2, sección 1 (softmax de (0, z1, z2)) |
| A75-C2 | Cota de D-06: p_p ≤ 2/3 | 0 de 600 sobre la cota; máximo p_p = 0.490 | coherente | docs/research/D-06 — Restricciones bioquímicas para D1.md, secciones 3 y 6 |
| A75-C3 | Soporte empírico del train interno (mínimo y máximo por fracción) | acetate: 2 fuera; propionate: 2 fuera; butyrate: 0 fuera (de 600) | a revisar | docs/research/D-06 — Restricciones bioquímicas para D1.md, sección 7; `EmpiricalSupport` de #245 |
| A75-C4 | Fracción media predicha frente a la generada | acetate 0.639 (medida 0.633, rango 0.484–0.774); propionate 0.191 (medida 0.195, rango 0.103–0.346); butyrate 0.170 (medida 0.172, rango 0.084–0.285) | coherente | Cohorte sintética (build_synthetic_cohort), test de los folds |

## Limitaciones

- La dispersión de un ensamble de 5 modelos o de 30 pasadas de MC-dropout mide la variabilidad del modelo, no el error de predicción; por eso el factor del val interno puede ser grande.
- El val interno tiene unos 10 animales por fold: el factor de escala de cada fold es ruidoso. La evaluación no agrega factores entre folds, porque el val interno de un fold puede contener animales del test de otro; solo el factor para una corrida nueva (`calibration.json`) es la mediana de los folds.
- Los intervalos en `(z_1, z_2, ln T)` suponen una normal por salida; los de fracciones muestrean `z_1` y `z_2` como independientes.
- El val interno también decide la detención temprana: la NLL y el factor se calculan sobre animales que ya influyeron en el entrenamiento.
