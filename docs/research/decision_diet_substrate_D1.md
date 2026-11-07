# Decisión: `diet → provides → substrate` y `substrate → available_to → taxon` en D1

**Emite:** Investigación. **Estado:** versión 1.0, pendiente de emisión por el sublíder (#258).
**Fecha:** 2026-11-07.
**Issues:** #258. Parte de
[S-01 y S-02 — Composición de la dieta basal de HoloFood](<S-01 y S-02 — Composición de la dieta basal de HoloFood.md>)
(LIM-1, LIM-3 y LIM-4). Se coordina con #256 (grafo mínimo de D1).

**Respuesta corta.** Las dos relaciones se **declaran como limitación de D1 este semestre** y no
se implementan. Feedtables tiene una entrada para 11 de los 15 ingredientes de S1, incluidos los
tres que aportan carbohidratos, así que la traducción a fracciones de la dieta sería posible. Pero
esas aristas no aportarían información a D1. La dieta basal es la misma en los tres tratamientos, y
su composición queda determinada por el ensayo y el día, que ya entran como covariables (LIM-4).
Además, la parte de esas fracciones que llega al ciego no se mide. Y `available_to` no tiene una
fuente que la sostenga sin usar los datos de evaluación. En D1, el nodo `diet` sigue conectado al
modelo solo por su atributo de tratamiento. **No se puede afirmar** que la dieta actúe a través del
microbioma.

## 1. Evaluación de las fuentes de traducción (pregunta 1)

**Feedtables** (INRAE-CIRAD-AFZ, https://www.feedtables.com, consultado el 07-11-2026):

| Ingrediente de S1 | Entrada de Feedtables | Observación |
|---|---|---|
| Wheat | `Wheat, soft` | S1 no dice si es trigo blando o duro; se supone blando. |
| Soybean 48% | `Soybean meal, oil < 5%, 48% protein + oil` | Coincide. |
| Extruded Soyabean | `Soybean, whole, extruded` | Se supone soja entera (con su aceite). |
| Soyabean oil | `Soybean oil` | Sin carbohidratos. |
| Animal fat (5 Sysfeed) | Sin entrada única | Producto comercial; Feedtables separa `Tallow`, `Lard` y `Poultry fat`. |
| Dicalcium phosphate | `Dicalcium phosphate anhydrous` o `… dihydrate` | S1 no indica la forma. Sin carbohidratos. |
| Calcium carbonate, Sodium chloride, Sodium bicarbonate | Entradas homónimas | Minerales, sin carbohidratos. |
| DL-methionine, L-lysine HCL, L-threonine | `DL-methionine`, `L-lysine HCl`, `L-threonine` | Aminoácidos de síntesis. |
| Vitamin-Mineral premix, Choline Chloride, Antioxidant (Noxyfeed 56P) | Sin entrada | Productos comerciales o aditivos. |

- **Cobertura:** 11 de 15 ingredientes tienen entrada, algunos con un supuesto. Los que aportan
  carbohidratos son trigo, harina de soja y soja extruida, y suman más del 90 % de la dieta en
  todas las fases (Tablas 3 a 5 de S-01). Los tres están cubiertos.
- **Qué traduce:** fracciones de la dieta por kilo de alimento: almidón, azúcares totales, NDF, ADF,
  lignina y paredes celulares insolubles en agua. No son sustratos del ciego (sección 3).
- **Versión y licencia:** el sitio solo indica «© 2017-2024 INRAE CIRAD AFZ» y no publica un número
  de versión. Su página *Terms of use* contiene texto de relleno («Lorem ipsum…»), así que **los
  términos de reutilización no están establecidos**. La versión publicada de las tablas es el libro
  de Sauvant, Perez y Tran (2004), que sí es citable con DOI (`literature_curation`, R-07), pero sus
  valores no son los del sitio actual.

**FooDB** (https://foodb.ca): **no evaluada**. El sitio respondió HTTP 403 a las consultas
automáticas del 07-11-2026, y no se intentó eludir ese bloqueo. La decisión no depende de esta
evaluación: los motivos de la sección 3 valen para cualquier fuente de traducción. Si en un
semestre futuro se reabre la pregunta, la evaluación de FooDB se hace con una consulta manual.

## 2. Asignación a los animales (pregunta 2 y LIM-1)

LIM-1 sigue abierta: no está demostrada la correspondencia entre los experimentos A, B y C de Tous
et al. (2022) y los ensayos `CA`, `CB` y `CC`. Una composición común por fase sería técnicamente
posible, porque las nueve formulaciones difieren poco: por ejemplo, el trigo de la fase inicial es
527,5, 523,1 o 543 `g_kg` según el experimento (S-01, sección 2). Pero no resolvería el problema de
fondo de la sección 3, así que **no se adopta**.

## 3. Por qué se declara como limitación (preguntas 3 y 4)

1. **No distingue tratamientos (LIM-4).** La dieta basal es la misma para Control, Probiótico y
   Fitobiótico (`CC`, `CO`, `CE`). Los aditivos son lo que cambia entre ellos, y `modulates` es
   hipotética y no entra a los grafos de entrenamiento (respuesta del 16-10-2026, V-01, respuesta
   3). Una arista `provides` con el mismo valor para todos los animales de una fase no dice nada
   del efecto del tratamiento.
2. **Repite las covariables (LIM-4).** La composición de un animal queda determinada por su fase,
   es decir, por `sampling_day` (y por `trial_code` si se resolviera LIM-1). Las dos ya entran a
   `x` del huésped. Los pesos de `provides` serían una función de esas covariables.
3. **Fracción de la dieta no es sustrato del ciego.** En el pollo, la digestión del almidón en el
   intestino delgado es alta (Svihus 2014). El ciego fermenta sobre todo lo que escapa a la
   digestión, como polisacáridos no amiláceos y oligosacáridos (Józefiak et al. 2004). Cuánto de
   cada fracción llega al ciego depende de la digestibilidad, que D1 no mide. Una arista
   `diet → provides → substrate` diría cuánto almidón *contiene* la dieta, no cuánto *recibe* el
   microbioma.
4. **`available_to` no tiene fuente.** Solo admite `inferred` (V-01) y no puede usar los datos de
   evaluación de D1. La única vía con sustento sería inferir, desde las familias CAZy del catálogo,
   qué géneros pueden degradar cada sustrato. Eso exige una curación nueva de Investigación (de qué
   sustrato a qué familias CAZy), que no está en el plan del semestre (criterio C2 de la respuesta
   del 25-10-2026).
5. **Costo frente a valor.** Implementarlas exigiría nodos `substrate`, la traducción de los
   ingredientes, la curación de `available_to` y la validación de todo ello. Por los puntos 1 y 2,
   el modelo no ganaría información. Declarar la limitación no resta validez; ocultarla sí
   (criterio C4).

## 4. Decisión

| Relación | Decisión | Motivo principal |
|---|---|---|
| `diet → provides → substrate` | **Limitación declarada**; no se implementa en D1 este semestre. | No distingue tratamientos y repite las covariables (sección 3, puntos 1 y 2). |
| `substrate → available_to → taxon` | **Limitación declarada**; no se crea. | Sin fuente que no use los datos de evaluación (sección 3, punto 4). |

**Qué se puede afirmar con D1:**

- El tratamiento entra al modelo como atributo del nodo `diet` (#176) y el diseño, como covariables
  del huésped. Una diferencia de predicción entre tratamientos es una asociación con el tratamiento,
  exploratoria por el desbalance de la cohorte (L1 de la respuesta del 25-10-2026).
- **No** se puede afirmar que la dieta o los aditivos actúen *a través* del microbioma. El grafo de
  D1 no contiene el camino `dieta → sustrato → taxón`. Ninguna explicación de F7 sobre D1 puede
  presentar un efecto de la dieta como mediado por el microbioma.

**Qué no cambia:**

- El grafo sintético conserva las dos relaciones; esta decisión es solo para D1.
- La composición de S-01 (Anexos A y B) sigue disponible si se resuelve LIM-1.
- NOD-12 mantiene `substrate` como advertencia en datos reales (D-08).

**Cuándo reabrir:** con un conjunto de datos en que la dieta basal varíe entre tratamientos, o con
mediciones de sustratos en el contenido cecal. Ninguno de los dos existe en D1.

## 5. Supuestos y limitaciones

1. La cobertura de Feedtables se evaluó por nombre de ingrediente. Los valores no se descargaron
   porque la decisión no los usa, y no se versiona ninguno.
2. Los términos de reutilización de Feedtables no están publicados. Si se reabre la pregunta, hay
   que resolverlos antes de versionar valores.
3. FooDB no se evaluó (sección 1).
4. La afirmación sobre la digestión del almidón y la fermentación cecal es general para el pollo
   (Svihus 2014; Józefiak et al. 2004). No se midió en los animales de D1.
5. No se usó ningún servicio de pago.

## Referencias

- Józefiak, D., Rutkowski, A. y Martin, S. A. (2004). Carbohydrate fermentation in the avian ceca:
  a review. *Animal Feed Science and Technology*, 113, 1–15.
  doi:10.1016/j.anifeedsci.2003.09.007.
- Sauvant, D., Perez, J.-M. y Tran, G. (Eds.) (2004). *Tables of composition and nutritional value
  of feed materials*. Wageningen Academic Publishers. doi:10.3920/978-90-8686-668-7. Versión en
  línea: https://www.feedtables.com (INRAE-CIRAD-AFZ), consultada el 07-11-2026.
- Svihus, B. (2014). Starch digestion capacity of poultry. *Poultry Science*, 93, 2394–2399.
  doi:10.3382/ps.2014-03905.
- Tous, N. et al. (2022). Citada en S-01 y S-02, de donde se toman los 15 ingredientes de S1.

## Emisión y control de versiones

**Tabla A.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | Decisión: `diet → provides → substrate` y `substrate → available_to → taxon` en D1 |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Alcance | Issue #258 |
| Versión | 1.0 |
| Estado | **Pendiente de emisión.** El sublíder confirma la decisión de la sección 4. |

**Tabla B.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 1.0 | 07-11-2026 | Evaluación de Feedtables, decisión sobre las dos relaciones y lo que se puede afirmar con D1. | Investigación, para emisión del sublíder |
