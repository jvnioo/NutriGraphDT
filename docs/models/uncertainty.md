# Incertidumbre y calibración de las predicciones de D1 (A75-P1 y A75-P2; #283 y #284)

Hasta A75, las métricas de D1 solo informaban la dispersión entre folds y semillas: ninguna
predicción individual tenía un intervalo. Este documento describe cómo se estiman y se calibran.
El reporte generado está en [`reports/uncertainty/d1/`](../../reports/uncertainty/d1/report.md),
y la revisión de coherencia bioquímica en [`a75-biochemical-coherence.md`](a75-biochemical-coherence.md).

- **Código:** `nutrigraphdt.models.uncertainty`.
- **Script:** `scripts/estimate_uncertainty.py`.
- **Requisitos:** los extras `graph` y `baselines`, y los grafos de D1 guardados.

```bash
python scripts/build_graph.py --save-graphs --overwrite   # si no están guardados
python scripts/estimate_uncertainty.py                    # 10 semillas × 5 folds
python scripts/estimate_uncertainty.py --resume           # retoma una corrida cortada
```

## 1. Modelo y protocolo

- **Modelo:** `hetero_sage` con `configs/models/hetero_sage.yaml` y `TaxonIdentityConfig()`. Es la
  configuración por omisión, que #268 decidió no cambiar.
- **Plan y objetivo:**
  - folds de #139: 10 semillas × 5 folds, agrupados por corral;
  - objetivo composicional `(z_1, z_2, ln T)`;
  - semilla de entrenamiento de cada fold `42000 + 100 · semilla + fold`, igual que en #142, #185 y
    #266.
- **Por fold:**
  - un val interno por corral para la detención temprana (`split_inner_validation`);
  - codificación de los taxones y escalado ajustados con el train interno.

Cada animal de test recibe su intervalo **del modelo del fold en que estuvo en test**.

## 2. Dos métodos

| Método | Muestras por animal | Qué varía |
|---|---|---|
| `ensemble` | 5 modelos | La semilla de inicialización y del orden de los lotes. El train, el val interno y el escalado son los mismos. |
| `mc_dropout` | 30 pasadas | Las máscaras de dropout (`p = 0,2`), con el resto del modelo en `eval()`. Se aplica al modelo del fold. |

- **Ensamble:**
  - no se confunde con las 10 semillas del plan, que cambian la partición;
  - la semilla del miembro `m` es `semilla_fold + m · 1 000 000`, que nunca coincide con la de otro
    fold;
  - **el miembro 0 es exactamente el modelo de la evaluación de #266**
    (`test_member_zero_is_the_model_of_the_fold`).
- **MC-dropout:**
  - `mc_dropout` activa solo las capas de dropout y, al salir, restaura el modo de cada módulo;
  - las pasadas usan un generador propio con semilla y no alteran el generador global.

## 3. Intervalos

Cada método resume sus muestras con la media $\mu$ y la desviación $\sigma$ de cada salida
`(z_1, z_2, ln T)`. El intervalo de nivel $q$ es

$$\mu \pm s \cdot z_q \cdot \sigma, \qquad z_q = \Phi^{-1}\!\left(\tfrac{1+q}{2}\right),$$

con $s$ el factor de escala de la sección 4 ($s = 1$ sin calibrar).

**Fracciones.** Se toman 2000 muestras de la normal de $(z_1, z_2)$, cada una se transforma con la
softmax de $(0, z_1, z_2)$, y se usan los cuantiles empíricos. La fracción puntual es la softmax de
la media de $(z_1, z_2)$. **No se promedian fracciones**: el promedio de las fracciones de cada
muestra no es la composición de la media
(`test_fractions_are_the_softmax_of_the_mean_log_ratios`).

## 4. Calibración y elección del método, solo con el val interno

1. **Elección del método.** En cada fold se elige el método con menor log-verosimilitud negativa
   (NLL) de la normal predictiva en el val interno, sin escalar. La NLL es una regla de puntuación
   propia: premia a la vez la calibración y la estrechez. Ante un empate gana `ensemble`.
2. **Factor de escala.** Para cada método y salida,
   $s = \text{cuantil}_{0{,}8}\!\left(|y - \mu| / \sigma\right) / z_{0{,}8}$ en el val interno. Así,
   el intervalo del 80 % cubre el 80 % del val interno. Las fracciones heredan el factor de
   $z_1$ y $z_2$.
3. **Test.** Se predice una sola vez, al final, con el método y el factor ya fijados.

**Nada se agrega entre folds.** El val interno de un fold puede contener animales del test de otro,
así que un factor o una elección agregados filtrarían el test.

## 5. Cómo se lee la cobertura

`coverage.csv` y el reporte informan la cobertura nominal y la observada al 50, 80 y 90 %:

- por salida (las tres del modelo y las tres fracciones) y por día;
- en el val interno, antes y después del factor;
- en el test.

**Val interno.** Media y desviación entre folds. La cobertura después del factor es optimista,
porque el factor se ajustó con esos mismos animales.

**Test.**
- Cada semilla del plan reparte a los 56 animales en sus 5 folds. La cobertura por semilla tiene
  56 animales independientes.
- El reporte da la media de las 10 semillas, su desviación y un intervalo de Wilson al 95 % con
  n = 56, no 560: las semillas repiten animales.
- El veredicto es `compatible` si el nivel nominal cae en ese intervalo; si no, `subcobertura` o
  `sobrecobertura`.
- Si alguna salida o nivel no es `compatible`, el reporte dice que los intervalos **no están
  calibrados**.

**Con 56 animales, la cobertura por día es muy ruidosa:** el día 21 tiene unos 9 animales en total.

## 6. Salidas

| Archivo | Contenido |
|---|---|
| `report.md` | Elección del método, cobertura en el val interno y en el test, por día, coherencia y limitaciones |
| `coverage.csv` | Cobertura agregada por subconjunto, método, calibración, nivel, salida y día |
| `fold_coverage.csv` | Cubiertos y ancho medio por fold (incremental) |
| `predictions.csv` | Punto e intervalos de cada animal de test por método y calibración, y la predicción del modelo del fold (`reference`) |
| `selection.csv` | NLL del val interno, método elegido, factores, épocas de cada miembro y soporte por fold |
| `coherence.csv` | Hallazgos de A75-P3 |
| `run.json` | Configuración, versiones y commit |

## Limitaciones

- La dispersión de un ensamble o de MC-dropout mide la variabilidad del modelo, no el error de
  predicción. Por eso los intervalos crudos son angostos y el factor del val interno es grande.
- El val interno tiene unos 10 animales por fold, así que el factor de cada fold es ruidoso.
- Los intervalos de `(z_1, z_2, ln T)` suponen una normal por salida. Los de fracciones muestrean
  `z_1` y `z_2` como independientes.
- El val interno también decide la detención temprana: la NLL y el factor se calculan sobre
  animales que ya influyeron en el entrenamiento.
- El 80 % del factor y los niveles 50, 80 y 90 % son elecciones de Desarrollo pedidas por #284, no
  valores científicos.
