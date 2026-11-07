# Decisión: representación de la identidad de los taxones en el grafo de D1

**Emite:** Investigación. **Estado:** emitido el 07-11-2026 (versión 1.0).
**Fecha:** 2026-11-07.
**Issues:** #239. Se coordina con #236 (tabla S-04), #257 (funciones), #256 (grafo mínimo) y #185
(evaluación con restricciones en D1).
**Evidencia:** `docs/research/check_d1_taxon_readout.py` y su salida sobre los grafos de `main`
(`c016a82`); comentario del sublíder en #239 del 03-11-2026.

**Respuesta corta.** Se confirma, ejecutando el código, lo que el comentario del 03-11-2026 había
deducido de él: **hoy la GNN no recibe información del microbioma en D1**. El bloque `taxon` de la
lectura es idéntico en los 185 grafos. Las métricas de #142 salen solo de las covariables del
huésped y del tratamiento. La representación defendible combina dos alternativas: las **aristas
funcionales** (alternativa 4), que dan una ruta mecanística, y el **linaje taxonómico multiplicado
por la abundancia** (alternativa 3), que da identidad también a los géneros sin enlace y a los
nodos residuales. Se descartan la tabla ancha (1) y el embedding por taxón (2). La jerarquía como
aristas (5) queda para después.

## 1. Verificación de la premisa

`check_d1_taxon_readout.py`, sobre los grafos reconstruidos desde `main` (`c016a82`) con
`scripts/build_graph.py --save-graphs` el 07-11-2026:

| Medida | Resultado |
|---|---|
| Grafos | 185 |
| Forma de `x` de `taxon` | `[1317, 1]` en todos (solo `abundance`) |
| Aristas que llegan a `taxon` | Ninguna |
| Suma de `abundance` por grafo | 1 (entre 0,99999988 y 1,00000012) |
| Media de `x` por grafo | 0,00075930 = 1/1317 en todos (desviación 6 × 10⁻¹¹, redondeo) |
| Fracción de ausentes por grafo | 0 en todos |

`NodeTypeEncoder` es lineal, los taxones no reciben mensajes y `mean_readout` promedia por tipo.
Entonces el bloque `taxon` vale `W · [1/1317, 0] + b` para todos los animales. Con eso queda
cumplida la comprobación (a) que el comentario pidió a Desarrollo, en su forma exacta. La ablación
(b) ya no es necesaria para esta decisión.

**Consecuencias inmediatas:**

- `docs/models/gnn-d1-composition.md` dice que la GNN usa los taxones «como un baseline tabular».
  No es así: no los usa en absoluto. Se pide a Desarrollo corregirlo.
- El baseline comparable con la GNN actual de D1 es `ridge_design`, que usa los mismos factores
  (comentario en #185 del 03-11-2026).
- **Cualquier representación nueva debe combinar identidad y abundancia antes de la lectura**, con
  un producto (`a_t · e_t`) o con una no linealidad (`MLP([a_t ‖ e_t])`). Si la identidad solo se
  suma (`W·a_t + e_t`), la media sobre el mismo conjunto de taxones vuelve a ser constante entre
  animales. Esto vale para todas las alternativas de la sección 3.

## 2. Criterios

| N° | Criterio | Pregunta |
|---|---|---|
| K1 | Señal por animal | ¿El bloque de la lectura varía entre animales? (sección 1) |
| K2 | Interpretabilidad | ¿Una explicación de F7 puede nombrar qué taxón o qué función pesa? |
| K3 | Sobreajuste con 56 animales | ¿Cuántos parámetros nuevos agrega frente a unos 45 animales de entrenamiento por fold? |
| K4 | Contrato de datos v2 | ¿Respeta el rango de género, los residuales sin aristas funcionales y la regla `1:1`? |
| K5 | Taxones nuevos y residuales | ¿Qué recibe un género fuera del vocabulario y qué reciben los residuales (cerca del 55 % de las lecturas)? |
| K6 | Aporte del grafo | ¿Qué agrega la GNN frente a `ridge` o `elasticnet` con la misma información? |
| K7 | Sin fuga | ¿Todo lo que se ajusta (vocabulario, filtros) usa solo el train del fold? |

## 3. Alternativas

**Cifras de D1 usadas aquí:** 498 géneros; 212 familias; el 44,7 % de las lecturas llega a género y
el 76,2 % a familia; 30 familias reúnen el 98,9 % de las lecturas que llegan a familia. Con la tabla
de #236, 46 géneros tienen `has_capacity` (37,0 % de las lecturas a género).

| Alternativa | K1 | K2 | K3 | K4 | K5 | K6 | Decisión |
|---|---|---|---|---|---|---|---|
| **1. Tabla ancha por género** | Sí | Por género | Alto: ~500 columnas | Sí | Columna «otros»; residuales aparte | **Nada**: es la tabla de `ridge`/`elasticnet` | **Descartada para la GNN.** Sigue como baseline. |
| **2. Embedding aprendido por taxón** | Solo con interacción | Baja: el vector no tiene significado | Muy alto: ~500 × d | Sí | Vector «fuera de vocabulario»; vocabulario por fold | Equivale a un modelo de bajo rango sobre la tabla ancha | **Descartada** |
| **3. Linaje como atributo, multiplicado por la abundancia** | Sí | Por familia | Moderado: ~30 familias tras el filtro del fold | Sí: el linaje está en `taxon_id` | **Cubre los residuales**: un residual `f__X;g__` tiene familia | Por sí sola, ninguno frente a `ridge` con tabla por familia | **Adoptada**, combinada con la 4 |
| **4. Aristas funcionales** (`has_capacity`, #175 + #257) | Sí: cada función promedia la abundancia de sus portadores | Alta: ruta `género → KO → AGCC` | Bajo: 9 nodos función | Sí, por construcción | No: 46 géneros; residuales sin aristas | **Sí**: estructura que la tabla no tiene | **Adoptada**, obligatoria |
| **5. Jerarquía taxonómica como aristas** | Sí | Por rango | Bajo | Requiere un tipo de arista nuevo en el esquema | Sí | Comparte información entre géneros emparentados | **Para después**: con 30 familias aporta lo mismo que la 3, y cambia el esquema |

**Por qué la combinación 3 + 4.** La alternativa 4 es la única con contenido mecanístico, pero por
sí sola deja sin señal al 63 % de las lecturas a género y a todos los residuales. La alternativa 3
cubre a todos los taxones con pocos parámetros y se extiende a géneros nuevos, que reciben su
familia. Ninguna de las dos depende de un vocabulario de géneros aprendido con 56 animales.

**Por qué no la 1 ni la 2.** Con la tabla ancha, la GNN sería un modelo tabular y la comparación
con los baselines no mediría el grafo (K6). El embedding por taxón agrega cientos de vectores que
se aprenderían con unos 45 animales por fold, sin significado biológico (K2, K3).

## 4. Decisión

1. **Identidad mecanística:** `has_capacity` hacia los 9 KO de #257, desde los 46 géneros `1:1` de
   #236. No requiere nada más que #175.
2. **Identidad por linaje:** cada nodo `taxon`, incluidos los residuales, lleva su familia (o el
   rango más profundo que alcance, si no tiene familia) **combinada con su abundancia**:
   - forma de referencia: `x_t = a_t · onehot(familia_t)`. La media por grafo da el perfil de
     abundancia por familia, que varía entre animales;
   - alternativa equivalente: un encoder no lineal sobre `[a_t ‖ onehot(familia_t)]`;
   - el vocabulario de familias se ajusta **solo con el train del fold**, con el mismo criterio de
     prevalencia de `TaxonFilter` (#160). Las familias fuera del vocabulario van a una columna
     «otras» (K5, K7).
3. **Rango:** familia. El orden y el filo se pueden agregar en la comparación técnica si
   Desarrollo lo considera útil; la decisión no depende de ello.
4. **Comparación técnica que debe preparar Desarrollo** (Issue nueva). Los mismos folds y semillas
   de #139, con el objetivo composicional:

   | Brazo | Qué mide |
   |---|---|
   | GNN actual | Referencia; debería igualar a una GNN sin nodos `taxon` |
   | GNN con `MLP(a_t)` sin identidad | Solo la forma de la distribución |
   | GNN + alternativa 4 | El aporte de la ruta funcional |
   | GNN + alternativas 3 y 4 | La representación adoptada |
   | `ridge` con tabla por familia y con tabla por género | Lo que logra un modelo tabular con la misma información (K6) |

   La comparación decide **cuánto** aporta cada parte, no **si** se implementa. Si la combinación
   no supera a `ridge` con la tabla por familia, el resultado se informa así: el grafo no agrega
   capacidad predictiva en D1 y su aporte queda en la explicabilidad.

## 5. Supuestos y limitaciones

1. La verificación de la sección 1 corresponde al código de `main` (`c016a82`). Si cambian el
   encoder, la lectura o los atributos de `taxon`, hay que repetirla (el script queda versionado).
2. Los grafos guardados no están agregados a género, aunque el contrato v2 §6 lo fija. Hay 472
   nodos de especie (#256). La identidad por familia no depende de ese paso, pero el vocabulario y
   las cifras cambiarán cuando se agregue.
3. Identidad por familia no distingue géneros de la misma familia. Esa resolución la aportan, solo
   para los 46 géneros enlazados, las aristas funcionales.
4. Hay antecedentes que usan la estructura taxonómica o filogenética en modelos de microbioma:
   Ph-CNN (Fioravanti et al. 2018), TaxoNN (Sharma y Xu 2020) y PopPhy-CNN (Reiman et al. 2020).
   Respaldan que el linaje es información útil, no un resultado esperado en D1.
5. Con 56 animales, toda comparación entre representaciones tendrá una incertidumbre amplia. Se
   informa con la dispersión entre folds y semillas, como en #142.
6. No se usa ningún servicio de pago.

## Referencias

- Fioravanti, D. et al. (2018). Phylogenetic convolutional neural networks in metagenomics. *BMC
  Bioinformatics*, 19(Suppl 2), 49. doi:10.1186/s12859-018-2033-5.
- Reiman, D., Metwally, A. A., Sun, J. y Dai, Y. (2020). PopPhy-CNN: a phylogenetic tree embedded
  architecture for convolutional neural networks to predict host phenotype from metagenomic data.
  *IEEE Journal of Biomedical and Health Informatics*, 24(10), 2993–3001.
  doi:10.1109/JBHI.2020.2993761.
- Sharma, D. y Xu, W. (2020). TaxoNN: ensemble of neural networks on stratified microbiome data for
  disease prediction. *Bioinformatics*, 36(17), 4544–4550. doi:10.1093/bioinformatics/btaa542.

## Emisión y control de versiones

Yo, **Vicente Fuentes Rodríguez**, sublíder del Área de Investigación del proyecto Microbioma
Digital, confirmo la emisión de este documento a la Célula de Desarrollo.

**Tabla A.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | Decisión: representación de la identidad de los taxones en el grafo de D1 |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsables | Vicente Fuentes Rodríguez (decisión) y Felipe Cruz (@Felipex-x, taxonomía) |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Alcance | Issue #239 |
| Versión | 1.0 |
| Fecha de emisión | 07-11-2026 |
| Estado | Emitido |

**Tabla B.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 1.0 | 07-11-2026 | Verificación de la premisa, criterios, comparación de cinco alternativas y decisión. | Vicente Fuentes Rodríguez |
