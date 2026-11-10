# Primeras explicaciones de animales reales de D1 (A71-P3, #280)

- **Variante:** `hetero_sage` (brazo `free`) evaluada fuera de fold (C-05).
- **Cohorte evaluada:** 56 animales de `D1_holofood`; faltantes: 0.
- **Salidas explicadas:** `log_butyrate_acetate`, `log_propionate_acetate`.
- **Subgrafo top-k:** k = 5 aristas por valor absoluto con desempate léxico determinista.
- **Explicador:** `EdgeGradientSaliency` (determinista, gradiente exacto sobre aristas).
- **Semillas del plan:** 10 (0, 1, 2, 3, 4, 5, 6, 7, 8, 9); cada animal se explica con el modelo de cada semilla en que estuvo en test.

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
2. **El modelo explicado no supera a los modelos tabulares (#266, #268).** Con la configuración por omisión, que es la que se explica aquí, `hetero_sage` tiene 4,11 pp
   de MAE de fracciones: es peor que `ridge` por familia (3,69 pp; Δ +0,42 pp [+0,05; +0,79]) y no se distingue
   de `ridge` sobre el diseño (3,98 pp) ni de `day_only` (4,03 pp). Se explica un modelo sin ventaja predictiva demostrada.
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
| `log_butyrate_acetate` | 56 | 1.0000 | 0.4332 | 0 / 56 (0.0 %) |
| `log_propionate_acetate` | 56 | 1.0000 | 0.4553 | 0 / 56 (0.0 %) |

**$\hat{\Phi}$ entre semillas del explicador vale 1 por construcción:** `EdgeGradientSaliency` es determinista, así que repetirlo con otra semilla da el mismo top-k. Ese valor no mide robustez. La estabilidad informativa es la del plan, donde cambian la partición y el modelo.

## 4. Cómo leer el top-k

| Salida | Apariciones de aristas | `measured_in` | `produces` | `has_capacity` | `produces` hacia un AGCC ajeno a la salida | Apariciones de taxones |
|---|---:|---:|---:|---:|---:|---:|
| `log_butyrate_acetate` | 2800 | 72.4 % | 27.4 % | 0.3 % | 37.9 % | 8 |
| `log_propionate_acetate` | 2800 | 72.1 % | 27.7 % | 0.2 % | 38.3 % | 6 |

- **Casi todo el top-k son aristas que tienen todos los animales de la cohorte.** `measured_in` une los AGCC medidos con el huésped, y `produces` sale de KEGG: ninguna depende del animal. El top-k dice qué partes fijas del grafo usa el modelo, no qué diferencia a un animal de otro.
- **`has_capacity`, la única relación por la que entra la abundancia de los géneros, casi no aparece**, y tampoco los taxones. Estas explicaciones no permiten nombrar qué géneros explican las diferencias en la composición de AGCC entre animales. Es coherente con que el modelo no supere a `day_only`.
- **La importancia no sigue la ruta biológica de la salida.** Una arista hacia un AGCC que no interviene en la razón explicada (por ejemplo, producción de propionato para `log_butyrate_acetate`) solo influye a través de la lectura del huésped. Es una propiedad del modelo, no de la bioquímica.

## 5. Elementos más frecuentes en el subgrafo top-k

Aparición relativa de taxones, funciones KO y aristas en el subgrafo top-k:

### Salida `log_butyrate_acetate`

#### Taxones más frecuentes en el subgrafo top-k
| Género / Taxón | Frecuencia | Apariciones |
|---|---:|---:|
| `g__Faecalibacterium` | 1.1 % | 6 |
| `g__Butyricimonas` | 0.2 % | 1 |
| `g__Acinetobacter` | 0.2 % | 1 |

#### Funciones (KO) más frecuentes en el subgrafo top-k
| Función (KO) | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `ko:K00925` | 29.1 % | 163 | `annotated` |
| `ko:K00932` | 20.4 % | 114 | `annotated` |
| `ko:K01034` | 19.8 % | 111 | `annotated` |
| `ko:K01026` | 19.5 % | 109 | `annotated` |
| `ko:K00929` | 18.6 % | 104 | `annotated` |
| `ko:K01035` | 18.6 % | 104 | `annotated` |
| `ko:K22214` | 12.1 % | 68 | `annotated` |

#### Aristas con mayor frecuencia en el subgrafo top-k
| Arista | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `(function:ko:K00925) -[produces]-> (metabolite:acetate)` | 29.1 % | 163 | `annotated` |
| `(function:ko:K00932) -[produces]-> (metabolite:propionate)` | 20.2 % | 113 | `annotated` |
| `(function:ko:K01034) -[produces]-> (metabolite:butyrate)` | 19.8 % | 111 | `annotated` |
| `(function:ko:K01026) -[produces]-> (metabolite:propionate)` | 19.5 % | 109 | `annotated` |
| `(function:ko:K01035) -[produces]-> (metabolite:butyrate)` | 18.4 % | 103 | `annotated` |
| `(function:ko:K00929) -[produces]-> (metabolite:butyrate)` | 17.7 % | 99 | `annotated` |
| `(function:ko:K22214) -[produces]-> (metabolite:propionate)` | 12.1 % | 68 | `annotated` |
| `(metabolite:butyrate) -[measured_in]-> (host:SAMEA112904743:host)` | 1.8 % | 10 | `observed` |

### Salida `log_propionate_acetate`

#### Taxones más frecuentes en el subgrafo top-k
| Género / Taxón | Frecuencia | Apariciones |
|---|---:|---:|
| `g__Acinetobacter` | 0.5 % | 3 |
| `g__Faecalibacterium` | 0.4 % | 2 |
| `g__Butyricimonas` | 0.2 % | 1 |

#### Funciones (KO) más frecuentes en el subgrafo top-k
| Función (KO) | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `ko:K00925` | 27.7 % | 155 | `annotated` |
| `ko:K00932` | 22.5 % | 126 | `annotated` |
| `ko:K00929` | 22.3 % | 125 | `annotated` |
| `ko:K01026` | 20.0 % | 112 | `annotated` |
| `ko:K01034` | 16.4 % | 92 | `annotated` |
| `ko:K22214` | 15.9 % | 89 | `annotated` |
| `ko:K01035` | 14.8 % | 83 | `annotated` |

#### Aristas con mayor frecuencia en el subgrafo top-k
| Arista | Frecuencia | Apariciones | Evidencia |
|---|---:|---:|---|
| `(function:ko:K00925) -[produces]-> (metabolite:acetate)` | 27.7 % | 155 | `annotated` |
| `(function:ko:K00929) -[produces]-> (metabolite:butyrate)` | 22.0 % | 123 | `annotated` |
| `(function:ko:K00932) -[produces]-> (metabolite:propionate)` | 22.0 % | 123 | `annotated` |
| `(function:ko:K01026) -[produces]-> (metabolite:propionate)` | 20.0 % | 112 | `annotated` |
| `(function:ko:K01034) -[produces]-> (metabolite:butyrate)` | 16.4 % | 92 | `annotated` |
| `(function:ko:K22214) -[produces]-> (metabolite:propionate)` | 15.7 % | 88 | `annotated` |
| `(function:ko:K01035) -[produces]-> (metabolite:butyrate)` | 14.6 % | 82 | `annotated` |
| `(metabolite:butyrate) -[measured_in]-> (host:SAMEA112904743:host)` | 1.8 % | 10 | `observed` |

## 6. Advertencias obligatorias del contrato (C-02, EXP-08)

Toda explicación emitida incluye las advertencias de interpretación exigidas:
- `association_not_causation`: Importancia calculada refleja asociación dentro del modelo, no causalidad.
- `importance_is_not_evidence`: La importancia matemática no equivale a evidencia biológica.
- `diet_day_confounding`: Confusión entre dieta y día de muestreo en la cohorte de D1.
- `exploratory_treatment_contrast`: Desbalance muestral (34/15/7 animales); contrastes son exploratorios.
- `model_not_better_than_day_only`: La GNN no supera consistentemente al baseline ingenuo de día.

## 7. Conclusiones y recomendaciones para el informe

1. Presentar las explicaciones como una inspección técnica de sensibilidad de la red sobre una
   **estructura funcional anotada**, evitando terminología causal o mecanística.
2. Subrayar que los resultados de propionato carecen de representatividad por la cobertura del 2,1 %.
3. Acompañar siempre cada visualización con la advertencia de estabilidad y el desglose de evidencias.
4. No usar estas explicaciones para atribuir la composición de AGCC a géneros concretos: el top-k está hecho casi solo de aristas que comparten todos los animales (sección 4).
