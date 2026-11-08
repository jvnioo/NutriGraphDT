# Primeras explicaciones de animales reales de D1 (A71-P3, #280)

- **Variante:** `hetero_sage` (brazo `free`) evaluada fuera de fold (C-05).
- **Cohorte evaluada:** 56 animales de `D1_holofood`; faltantes: 0.
- **Salidas explicadas:** `log_butyrate_acetate`, `log_propionate_acetate`.
- **Subgrafo top-k:** k = 5 aristas por valor absoluto con desempate léxico determinista.
- **Explicador:** `EdgeGradientSaliency` (determinista, gradiente exacto sobre aristas).

## 1. Lo que se puede y no se puede afirmar (decisión #256, sección 4)

| Se puede afirmar | No se puede afirmar |
|---|---|
| Las asociaciones aprendidas por la GNN entre entradas del grafo y salidas de AGCC. | Causalidad, actividad metabólica ni flujo funcional real en el ciego. |
| Qué géneros y KO aparecen con mayor frecuencia relativa en el subgrafo top-k. | Que la dieta o los aditivos actúen a través del microbioma (#258). |
| Estabilidad cuantitativa del top-k entre semillas del explicador (C-07) y del plan. | Validación biológica ni mecanismos confirmados sin evidencia experimental independiente. |
| Que la estructura es funcional anotada basada en homología y catálogos públicos. | Estructura mecanística demostrada para las interacciones. |

## 2. Marco metodológico y límites del modelo

1. **Estructura funcional anotada, no mecanística (#256).** La red conecta taxones agregados a nivel
   de género con capacidades metabólicas anotadas (`has_capacity`) y metabolitos (`produces`).
   No modela cinética enzimática, dinámica poblacional ni absorción intestinal.
2. **La GNN no supera a `ridge` por familia (#268).** En D1, la GNN alcanza 3,90 pp de MAE macro
   de fracciones frente a 3,69 pp de `ridge_family`. La diferencia no es estadísticamente demostrable
   y el grafo no añade ventaja predictiva demostrable sobre los baselines tabulares.
3. **Explicación estrictamente fuera de fold (C-05, #241).** Cada animal se explica exclusivamente con
   el modelo del fold en que estuvo en test y con el escalador ajustado únicamente en el conjunto
   de entrenamiento de ese fold. Se previene cualquier memorización o fuga de datos.
4. **Cobertura por AGCC (#256, sección 5).** La cobertura de la ruta funcional es heterogénea entre metabolitos:

| AGCC | Géneros con ruta | % lecturas a género | % del total de lecturas | Soporte de la ruta |
|---|---:|---:|---:|---|
| Acetato | 35 | 36,1 % | 16,1 % | Moderado (*Faecalibacterium* dominante) |
| n-Butirato | 14 | 35,8 % | 16,0 % | Moderado (*Faecalibacterium* dominante) |
| Propionato | 7 | 2,1 % | 0,9 % | **Muy bajo soporte**: solo 2,1 % de lecturas |

> [!WARNING]
> **Bajo soporte del propionato:** Para el propionato, solo el 2,1 % de las lecturas a género y
> el 0,9 % del total poseen anotación en la ruta. Las explicaciones sobre `log_propionate_acetate`
> tienen base empírica muy limitada y no deben interpretarse como representativas del ciego.

## 3. Análisis de estabilidad (A71-P2, #279)

Se midieron las dos estabilidades de forma independiente, conforme a la regla C-07:
- **Estabilidad entre semillas del explicador:** Índice $\hat{\Phi}$ de Nogueira et al. (2018) con IC 95 %
  asintótico, comparando las selecciones del top-k con el modelo fijo a lo largo de 5 semillas.
- **Estabilidad entre semillas del plan:** $\hat{\Phi}_{plan}$ evaluado sobre la primera corrida de cada modelo.
- **Umbral de inestabilidad:** 0,40. *Aclaración:* El umbral 0,40 es **provisional** (trasladado desde
  selección de variables en aprendizaje estadístico) y no constituye un estándar establecido en la literatura.

| Salida | Animales evaluados | $\hat{\Phi}$ medio explicador | $\hat{\Phi}$ medio plan | Animales bajo umbral (< 0,40) |
|---|---:|---:|---:|---:|
| `log_butyrate_acetate` | 56 | 1.0000 | 0.4345 | 0 / 56 (0.0 %) |
| `log_propionate_acetate` | 56 | 1.0000 | 0.4920 | 0 / 56 (0.0 %) |

## 4. Elementos más frecuentes en el subgrafo top-k

Aparición relativa de taxones, funciones KO y aristas en el subgrafo top-k:

### Salida `log_butyrate_acetate`

#### Taxones más frecuentes en el subgrafo top-k
| Género / Taxón | Frecuencia | Apariciones |
|---|---:|---:|
| `g__Faecalibacterium` | 0.9 % | 1 |

#### Funciones (KO) más frecuentes en el subgrafo top-k
| Función (KO) | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `ko:K00932` | 22.3 % | 25 | `annotated` |
| `ko:K01026` | 21.4 % | 24 | `annotated` |
| `ko:K22214` | 20.5 % | 23 | `annotated` |
| `ko:K00925` | 15.2 % | 17 | `annotated` |
| `ko:K01034` | 13.4 % | 15 | `annotated` |
| `ko:K01035` | 11.6 % | 13 | `annotated` |
| `ko:K00929` | 7.1 % | 8 | `annotated` |

#### Aristas con mayor frecuencia en el subgrafo top-k
| Arista | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `(function:ko:K00932) -[produces]-> (metabolite:propionate)` | 22.3 % | 25 | `annotated` |
| `(function:ko:K01026) -[produces]-> (metabolite:propionate)` | 21.4 % | 24 | `annotated` |
| `(function:ko:K22214) -[produces]-> (metabolite:propionate)` | 20.5 % | 23 | `annotated` |
| `(function:ko:K00925) -[produces]-> (metabolite:acetate)` | 15.2 % | 17 | `annotated` |
| `(function:ko:K01034) -[produces]-> (metabolite:butyrate)` | 13.4 % | 15 | `annotated` |
| `(function:ko:K01035) -[produces]-> (metabolite:butyrate)` | 11.6 % | 13 | `annotated` |
| `(function:ko:K00929) -[produces]-> (metabolite:butyrate)` | 7.1 % | 8 | `annotated` |
| `(metabolite:butyrate) -[measured_in]-> (host:SAMEA112904743:host)` | 1.8 % | 2 | `observed` |

### Salida `log_propionate_acetate`

#### Taxones más frecuentes en el subgrafo top-k
| Género / Taxón | Frecuencia | Apariciones |
|---|---:|---:|
| *Sin taxones en top-k* | — | — |

#### Funciones (KO) más frecuentes en el subgrafo top-k
| Función (KO) | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `ko:K00925` | 32.1 % | 36 | `annotated` |
| `ko:K01035` | 26.8 % | 30 | `annotated` |
| `ko:K00932` | 25.9 % | 29 | `annotated` |
| `ko:K01034` | 25.0 % | 28 | `annotated` |
| `ko:K00929` | 23.2 % | 26 | `annotated` |
| `ko:K01026` | 21.4 % | 24 | `annotated` |
| `ko:K22214` | 18.8 % | 21 | `annotated` |

#### Aristas con mayor frecuencia en el subgrafo top-k
| Arista | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `(function:ko:K00925) -[produces]-> (metabolite:acetate)` | 32.1 % | 36 | `annotated` |
| `(function:ko:K01035) -[produces]-> (metabolite:butyrate)` | 26.8 % | 30 | `annotated` |
| `(function:ko:K00932) -[produces]-> (metabolite:propionate)` | 25.9 % | 29 | `annotated` |
| `(function:ko:K01034) -[produces]-> (metabolite:butyrate)` | 25.0 % | 28 | `annotated` |
| `(function:ko:K00929) -[produces]-> (metabolite:butyrate)` | 23.2 % | 26 | `annotated` |
| `(function:ko:K01026) -[produces]-> (metabolite:propionate)` | 21.4 % | 24 | `annotated` |
| `(function:ko:K22214) -[produces]-> (metabolite:propionate)` | 18.8 % | 21 | `annotated` |
| `(metabolite:propionate) -[measured_in]-> (host:SAMEA112904743:host)` | 1.8 % | 2 | `observed` |

## 5. Advertencias obligatorias del contrato (C-02, EXP-08)

Toda explicación emitida incluye las advertencias de interpretación exigidas:
- `association_not_causation`: Importancia calculada refleja asociación dentro del modelo, no causalidad.
- `importance_is_not_evidence`: La importancia matemática no equivale a evidencia biológica.
- `diet_day_confounding`: Confusión entre dieta y día de muestreo en la cohorte de D1.
- `exploratory_treatment_contrast`: Desbalance muestral (34/15/7 animales); contrastes son exploratorios.
- `model_not_better_than_day_only`: La GNN no supera consistentemente al baseline ingenuo de día.

## 6. Conclusiones y recomendaciones para el informe

1. Presentar las explicaciones como una inspección técnica de sensibilidad de la red sobre una
   **estructura funcional anotada**, evitando terminología causal o mecanística.
2. Subrayar que los resultados de propionato carecen de representatividad por la cobertura del 2,1 %.
3. Acompañar siempre cada visualización con la advertencia de estabilidad y el desglose de evidencias.
