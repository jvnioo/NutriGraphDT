# S-01 y S-02 · Composición de la dieta basal de HoloFood

Nov 4, 2026

**PIA-2 · Microbioma Digital — Gemelo Digital Nutricional basado en GNN y PINNs.** Proyecto NutriGraphDT · De: Célula de Investigación · Para: Célula de Desarrollo · sublíder Julio Provoste Palacios · Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II. Responde a la issue [#238](https://github.com/jvnioo/NutriGraphDT/issues/238): composición de la dieta basal de D1 por fase (S-01) y ensayo de HoloFood al que corresponde Duangnumsawang et al. (2022) (S-02), preguntas que dejó abiertas el hallazgo lateral de D-06 (§9).

**Respuesta corta.** **S-01:** la Tabla suplementaria S1 de Tous et al. (2022) entrega la dieta basal de trigo y soja de los tres experimentos de HoloFood (A, B y C) en tres fases (0–7, 7–21 y 21–35 días): nueve formulaciones, 15 ingredientes posibles y cuatro nutrientes. El encabezado de S1 dice g/kg, pero los ingredientes suman cerca de 100: se leen como porcentaje y se registran en `g_kg` (valor × 10). Los nutrientes van a `diet.composition` (`crude_protein`, `crude_fat` y `dry_matter` en `g_kg`, y `metabolizable_energy` en `MJ_kg`). Los ingredientes van a `diet.ingredients`, y sus cantidades quedan en un anexo de trazabilidad. El reparto y los identificadores nuevos son una propuesta a confirmar con Desarrollo. **S-02:** no se puede establecer a qué ensayo de D1 (`CA`, `CB` o `CC`) corresponde Duangnumsawang et al. (2022). Su formulación es la más cercana a la del experimento A, pero en la fase final se aparta de A en el cloruro de sodio y la harina de soja. Además, su diseño (2.880 pollos en 72 corrales) tiene el tamaño de los tres experimentos juntos. **Alcance:** la correspondencia entre A, B y C y los ensayos `CA`, `CB` y `CC` no está demostrada, así que no se asigna composición a los animales de D1. La composición es la de la dieta basal común a los tres tratamientos; los aditivos van al nodo `additive`.

## 1. Propósito, alcance y fuentes revisadas

Este documento responde las dos preguntas de la issue #238. Deja la composición de la dieta basal en el formato del contrato (`component_id`, `value`, `unit`), lista para poblar el nodo `diet` de D1 si se resuelve la correspondencia de ensayos (sección 6).

- **Alcance.** Dieta basal de los ensayos de pollo de HoloFood (D1), por experimento y fase, según Tous et al. (2022), y su comparación con Duangnumsawang et al. (2022).
- **Fuera de alcance.**
  - Asignar una composición a cada animal de D1: depende de la correspondencia entre experimentos y ensayos (LIM-1).
  - Traducir ingredientes a sustratos fermentables para las aristas `diet → provides → substrate` (LIM-3).
  - Cambios de código o de contrato, que decide Desarrollo.
- **Regla de valores.** No se altera ningún valor publicado. Las únicas transformaciones son dos conversiones de unidad, declaradas en las secciones 2.1 y 2.3. Los guiones de S1 se conservan y ninguno se convierte en cero.

**Tabla 1.** Fuentes revisadas

| N° | Fuente | Versión o fecha | Uso en este documento |
|---|---|---|---|
| 1 | Tous et al. (2022), Tabla suplementaria S1, p. 1 | Transcrita el 02-11-2026 | Ingredientes y nutrientes de las nueve formulaciones (S-01) |
| 2 | Tous et al. (2022), texto principal | Consultado el 02-11-2026 y el 04-11-2026 | Diseño de los tres experimentos, períodos de alimentación, días de muestreo y aditivos |
| 3 | Duangnumsawang et al. (2022), Tabla 1 y sección 2 | Consultada el 02-11-2026 y el 04-11-2026 | Comparación con S1 y diseño del ensayo (S-02) |
| 4 | HoloFood Data Portal: resumen del diseño experimental y fichas de animal | Consultado el 02-11-2026 | Códigos de ensayo `CA`, `CB` y `CC` |
| 5 | `docs/data-sources/holofood-source.md` | `main`, commit `476615e` | Diseño de D1, tratamientos, dosis y días de muestreo |
| 6 | `docs/graph/data-contract-v2.md` §4 y `src/nutrigraphdt/data/schema.py` (`CANONICAL_UNITS`) | `main`, commit `476615e` | Unidades admitidas |
| 7 | `docs/graph/graph-data-dictionary.md`, `src/nutrigraphdt/data/synthetic/nodes.py` y `src/nutrigraphdt/graph/heterodata.py` | `main`, commit `476615e` | Atributos de `diet`, vocabulario de `diet.composition` y su codificación en `x` |
| 8 | `docs/research/D-06 — Restricciones bioquímicas para D1.md`, §9 | v1.0, 29-10-2026 | Origen de S-01 y S-02 |

**Cómo se obtuvieron las cifras.** El levantamiento del 02-11-2026 transcribió S1 y la Tabla 1 de Duangnumsawang. Para esta emisión se volvieron a leer en la fuente la Tabla 1 de Duangnumsawang y el texto de Tous (04-11-2026); los valores de Duangnumsawang coinciden con los transcritos. Los totales, las conversiones, las coincidencias entre formulaciones y los anexos se generaron con un script a partir de la transcripción. El script comprobó además que las Tablas 3 a 5 y el Anexo B tienen los mismos 113 valores.

**Notación.** En el cuerpo se usa coma decimal. En los Anexos A y B, `value` y `g_kg` usan punto decimal, como el formato de intercambio.

## 2. Composición de la dieta basal (S-01)

S1 contiene nueve formulaciones, una por experimento (A, B y C) y fase (0–7, 7–21 y 21–35 días), todas a base de trigo y harina de soja. Los experimentos difieren en cantidades menores; por ejemplo, el trigo de la fase inicial es 527,5 `g_kg` en A, 523,1 en B y 543 en C. Por eso se conservan las nueve formulaciones en lugar de un promedio.

### 2.1 Unidad de los ingredientes

El bloque de ingredientes de S1 se titula `Ingredient (g/kg)`, pero cada formulación suma cerca de 100, no de 1000 (Tabla 2). Duangnumsawang et al. (2022), con valores casi iguales a los del experimento A, titula el mismo bloque `Ingredients (%)`. Los valores de S1 se leen, por tanto, como porcentaje de la fórmula (SUP-1). La discrepancia del encabezado se registra como editorial y **no confirmada**: no se encontró una fe de erratas.

`%` no puede usarse como unidad. El contrato de datos v2 (§4) fija la notación de `data.schema.CANONICAL_UNITS`, y `%` no figura en ella. Los ingredientes se registran en `g_kg`, con 1 % = 10 g/kg (valor de S1 × 10). Por ejemplo, el trigo de A 0–7 pasa de 52,75 a 527,5 `g_kg`. Las Tablas 3 a 5 muestran el valor de S1 junto al valor en `g_kg`; el Anexo B usa solo `g_kg`.

**Tabla 2.** Suma de los ingredientes por formulación

| Experimento | 0–7 · S1 | 0–7 · `g_kg` | 7–21 · S1 | 7–21 · `g_kg` | 21–35 · S1 | 21–35 · `g_kg` |
|---|---:|---:|---:|---:|---:|---:|
| A | 99,98 | 999,8 | 100,00 | 1000 | 100,10 | 1001 |
| B | 99,99 | 999,9 | 100,02 | 1000,2 | 100,02 | 1000,2 |
| C | 100,01 | 1000,1 | 100,00 | 1000 | 99,98 | 999,8 |

*Fuente: cálculo propio a partir de Tous et al. (2022), Tabla suplementaria S1, p. 1. Las sumas van de 99,98 a 100,10 en la escala de S1, es decir, de 999,8 a 1001 `g_kg`.*

### 2.2 Ingredientes por experimento

**Tabla 3.** Experimento A

| Ingrediente (nombre en S1) | 0–7 · S1 | 0–7 · `g_kg` | 7–21 · S1 | 7–21 · `g_kg` | 21–35 · S1 | 21–35 · `g_kg` |
|---|---:|---:|---:|---:|---:|---:|
| Wheat · trigo | 52,75 | 527,5 | 61,24 | 612,4 | 61,97 | 619,7 |
| Soybean 48% · harina de soja 48 % PB | 39,4 | 394 | 30,5 | 305 | 15,8 | 158 |
| Extruded Soyabean · soja extruida | — | — | — | — | 15 | 150 |
| Soyabean oil · aceite de soja | 4,16 | 41,6 | 4,8 | 48 | — | — |
| Animal fat (5 Sysfeed) · grasa animal | — | — | — | — | 4,01 | 40,1 |
| Dicalcium phosphate · fosfato dicálcico | 1,84 | 18,4 | 1,66 | 16,6 | 1,5 | 15 |
| Calcium carbonate · carbonato de calcio | 0,53 | 5,3 | 0,48 | 4,8 | 0,44 | 4,4 |
| Vitamin-Mineral premix · premezcla vitamínico-mineral | 0,4 | 4 | 0,4 | 4 | 0,4 | 4 |
| Sodium chloride · cloruro de sodio | 0,37 | 3,7 | 0,37 | 3,7 | 0,53 | 5,3 |
| DL-methionine · DL-metionina | 0,27 | 2,7 | 0,23 | 2,3 | 0,19 | 1,9 |
| L-lysine HCL · L-lisina HCl | 0,16 | 1,6 | 0,19 | 1,9 | 0,15 | 1,5 |
| Choline Chloride · cloruro de colina | 0,03 | 0,3 | 0,05 | 0,5 | 0,05 | 0,5 |
| L-threonine · L-treonina | 0,05 | 0,5 | 0,05 | 0,5 | 0,04 | 0,4 |
| Sodium bicarbonate · bicarbonato de sodio | — | — | 0,01 | 0,1 | — | — |
| Antioxidant (Noxyfeed 56P) · antioxidante | 0,02 | 0,2 | 0,02 | 0,2 | 0,02 | 0,2 |
| **Total calculado** | **99,98** | **999,8** | **100,00** | **1000** | **100,10** | **1001** |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. `g_kg`: valor de S1 × 10 (sección 2.1). Totales: cálculo propio. —: guion en S1, sin valor.*

**Tabla 4.** Experimento B

| Ingrediente (nombre en S1) | 0–7 · S1 | 0–7 · `g_kg` | 7–21 · S1 | 7–21 · `g_kg` | 21–35 · S1 | 21–35 · `g_kg` |
|---|---:|---:|---:|---:|---:|---:|
| Wheat · trigo | 52,31 | 523,1 | 60,52 | 605,2 | 61,05 | 610,5 |
| Soybean 48% · harina de soja 48 % PB | 39,88 | 398,8 | 31,24 | 312,4 | 16,79 | 167,9 |
| Extruded Soyabean · soja extruida | — | — | — | — | 15 | 150 |
| Soyabean oil · aceite de soja | 4,18 | 41,8 | 4,85 | 48,5 | — | — |
| Animal fat (5 Sysfeed) · grasa animal | — | — | — | — | 4,08 | 40,8 |
| Dicalcium phosphate · fosfato dicálcico | 1,84 | 18,4 | 1,66 | 16,6 | 1,5 | 15 |
| Calcium carbonate · carbonato de calcio | 0,48 | 4,8 | 0,44 | 4,4 | 0,39 | 3,9 |
| Vitamin-Mineral premix · premezcla vitamínico-mineral | 0,4 | 4 | 0,4 | 4 | 0,4 | 4 |
| Sodium chloride · cloruro de sodio | 0,37 | 3,7 | 0,38 | 3,8 | 0,36 | 3,6 |
| DL-methionine · DL-metionina | 0,28 | 2,8 | 0,24 | 2,4 | 0,2 | 2 |
| L-lysine HCL · L-lisina HCl | 0,15 | 1,5 | 0,17 | 1,7 | 0,14 | 1,4 |
| Choline Chloride · cloruro de colina | 0,03 | 0,3 | 0,05 | 0,5 | 0,05 | 0,5 |
| L-threonine · L-treonina | 0,05 | 0,5 | 0,05 | 0,5 | 0,04 | 0,4 |
| Sodium bicarbonate · bicarbonato de sodio | — | — | — | — | — | — |
| Antioxidant (Noxyfeed 56P) · antioxidante | 0,02 | 0,2 | 0,02 | 0,2 | 0,02 | 0,2 |
| **Total calculado** | **99,99** | **999,9** | **100,02** | **1000,2** | **100,02** | **1000,2** |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. `g_kg`: valor de S1 × 10 (sección 2.1). Totales: cálculo propio. —: guion en S1, sin valor.*

**Tabla 5.** Experimento C

| Ingrediente (nombre en S1) | 0–7 · S1 | 0–7 · `g_kg` | 7–21 · S1 | 7–21 · `g_kg` | 21–35 · S1 | 21–35 · `g_kg` |
|---|---:|---:|---:|---:|---:|---:|
| Wheat · trigo | 54,3 | 543 | 62,19 | 621,9 | 62,15 | 621,5 |
| Soybean 48% · harina de soja 48 % PB | 38,02 | 380,2 | 29,66 | 296,6 | 15,75 | 157,5 |
| Extruded Soyabean · soja extruida | — | — | — | — | 15 | 150 |
| Soyabean oil · aceite de soja | 4,01 | 40,1 | 4,71 | 47,1 | — | — |
| Animal fat (5 Sysfeed) · grasa animal | — | — | — | — | 3,98 | 39,8 |
| Dicalcium phosphate · fosfato dicálcico | 1,86 | 18,6 | 1,67 | 16,7 | 1,5 | 15 |
| Calcium carbonate · carbonato de calcio | 0,49 | 4,9 | 0,44 | 4,4 | 0,39 | 3,9 |
| Vitamin-Mineral premix · premezcla vitamínico-mineral | 0,4 | 4 | 0,4 | 4 | 0,4 | 4 |
| Sodium chloride · cloruro de sodio | 0,37 | 3,7 | 0,35 | 3,5 | 0,35 | 3,5 |
| DL-methionine · DL-metionina | 0,28 | 2,8 | 0,23 | 2,3 | 0,19 | 1,9 |
| L-lysine HCL · L-lisina HCl | 0,16 | 1,6 | 0,18 | 1,8 | 0,15 | 1,5 |
| Choline Chloride · cloruro de colina | 0,05 | 0,5 | 0,06 | 0,6 | 0,06 | 0,6 |
| L-threonine · L-treonina | 0,05 | 0,5 | 0,05 | 0,5 | 0,04 | 0,4 |
| Sodium bicarbonate · bicarbonato de sodio | — | — | 0,04 | 0,4 | — | — |
| Antioxidant (Noxyfeed 56P) · antioxidante | 0,02 | 0,2 | 0,02 | 0,2 | 0,02 | 0,2 |
| **Total calculado** | **100,01** | **1000,1** | **100,00** | **1000** | **99,98** | **999,8** |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. `g_kg`: valor de S1 × 10 (sección 2.1). Totales: cálculo propio. —: guion en S1, sin valor.*

### 2.3 Nutrientes

S1 informa cuatro nutrientes por formulación. La energía metabolizable es la misma en los tres experimentos para cada fase, y la materia seca coincide en A y B.

**Tabla 6.** Nutrientes de S1, con la energía convertida a `MJ_kg`

| Variable en S1 | Unidad en S1 | A 0–7 | A 7–21 | A 21–35 | B 0–7 | B 7–21 | B 21–35 | C 0–7 | C 7–21 | C 21–35 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Energía metabolizable | kcal/kg | 2900 | 3000 | 3100 | 2900 | 3000 | 3100 | 2900 | 3000 | 3100 |
| Materia seca | g/kg | 879 | 881 | 882 | 879 | 881 | 882 | 871 | 874 | 878 |
| Proteína bruta | g/kg | 255 | 223 | 206 | 241 | 209 | 194 | 241 | 210 | 195 |
| Extracto etéreo | g/kg | 57,0 | 63,4 | 81,5 | 57,0 | 64,0 | 82,0 | 56,8 | 63,8 | 82,6 |
| Energía metabolizable, convertida | MJ/kg | 12,13 | 12,55 | 12,97 | 12,13 | 12,55 | 12,97 | 12,13 | 12,55 | 12,97 |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. Conversión: 1 kcal = 4,184 kJ, redondeada a dos decimales; 2900, 3000 y 3100 kcal/kg son 12,1336, 12,552 y 12,9704 MJ/kg (SUP-2). El texto de Tous indica que S1 reúne la composición estimada y la analítica; la transcripción no registra a cuál corresponde cada fila.*

## 3. Representación en el nodo `diet` (propuesta para Desarrollo)

En el repositorio, `diet.composition` lleva nutrientes, no ingredientes. El catálogo sintético (`data/synthetic/nodes.py`) usa `crude_protein`, `crude_fiber`, `crude_fat`, `metabolizable_energy`, `calcium` y `total_phosphorus`, en `g_kg` o `MJ_kg`. Los ingredientes van en un atributo aparte, `diet.ingredients` (`list[str]`, según el diccionario de datos del grafo). Además, `graph/heterodata.py` crea una columna de `x` del nodo `diet` por cada par (`component_id`, `unit`) de `composition`, así que todo lo que entra ahí pasa a ser una feature del modelo. La propuesta sigue ese reparto (Tabla 7).

**Tabla 7.** Destino propuesto de cada variable de S1

| Variable de S1 | Unidad en S1 | Atributo de `diet` | Identificador | `unit` | Conversión | Estado |
|---|---|---|---|---|---|---|
| Proteína bruta | g/kg | `composition` | `crude_protein` | `g_kg` | Ninguna | En el vocabulario sintético |
| Extracto etéreo | g/kg | `composition` | `crude_fat` | `g_kg` | Ninguna | En el vocabulario sintético |
| Energía metabolizable | kcal/kg | `composition` | `metabolizable_energy` | `MJ_kg` | × 4,184 / 1000 | En el vocabulario sintético |
| Materia seca | g/kg | `composition` | `dry_matter` | `g_kg` | Ninguna | **Nuevo; pendiente de confirmar** |
| 15 ingredientes | Porcentaje (sección 2.1) | `ingredients` | Los del Anexo B | — | Cantidades × 10, solo en el Anexo B | **Nuevos; pendientes de confirmar** |

*Fuente: Tabla 6 y Anexo B; vocabulario de `src/nutrigraphdt/data/synthetic/nodes.py` (`main`, commit `476615e`). El extracto etéreo es la determinación analítica de la grasa bruta.*

`diet.ingredients` es una lista sin cantidades. Lleva los identificadores de los ingredientes con valor en la formulación; un ingrediente con guion en S1 no se lista. Las listas se repiten entre formulaciones (Tabla 8).

**Tabla 8.** `diet.ingredients` por formulación

| Formulaciones | N.º | `diet.ingredients` |
|---|---:|---|
| A 0–7, B 0–7, B 7–21, C 0–7 | 12 | `wheat`, `soybean_meal_48cp`, `soybean_oil`, `dicalcium_phosphate`, `calcium_carbonate`, `vitamin_mineral_premix`, `sodium_chloride`, `dl_methionine`, `l_lysine_hcl`, `choline_chloride`, `l_threonine`, `antioxidant_noxyfeed_56p` |
| A 7–21, C 7–21 | 13 | `wheat`, `soybean_meal_48cp`, `soybean_oil`, `dicalcium_phosphate`, `calcium_carbonate`, `vitamin_mineral_premix`, `sodium_chloride`, `dl_methionine`, `l_lysine_hcl`, `choline_chloride`, `l_threonine`, `sodium_bicarbonate`, `antioxidant_noxyfeed_56p` |
| A 21–35, B 21–35, C 21–35 | 13 | `wheat`, `soybean_meal_48cp`, `extruded_soybean`, `animal_fat_5_sysfeed`, `dicalcium_phosphate`, `calcium_carbonate`, `vitamin_mineral_premix`, `sodium_chloride`, `dl_methionine`, `l_lysine_hcl`, `choline_chloride`, `l_threonine`, `antioxidant_noxyfeed_56p` |

*Fuente: Anexo B.*

Atributos propuestos para la formulación A 0–7, con los valores del Anexo A:

```json
{
  "ingredients": [
    "wheat", "soybean_meal_48cp", "soybean_oil", "dicalcium_phosphate",
    "calcium_carbonate", "vitamin_mineral_premix", "sodium_chloride", "dl_methionine",
    "l_lysine_hcl", "choline_chloride", "l_threonine", "antioxidant_noxyfeed_56p"
  ],
  "composition": [
    {"component_id": "crude_protein", "value": 255, "unit": "g_kg"},
    {"component_id": "crude_fat", "value": 57.0, "unit": "g_kg"},
    {"component_id": "metabolizable_energy", "value": 12.13, "unit": "MJ_kg"},
    {"component_id": "dry_matter", "value": 879, "unit": "g_kg"}
  ]
}
```

- **Propuesta a confirmar con Desarrollo (@jvnioo).** El reparto entre `composition` e `ingredients`, el `component_id` `dry_matter` y los identificadores de ingredientes son una propuesta (LIM-2). El catálogo sintético usa nombres más genéricos (`soybean_meal`, `limestone`, `salt`, `vitamin_premix`); la propuesta conserva los de S1, que son más específicos. Unificarlos lo decide Desarrollo.
- **Componentes sin valor.** S1 no informa fibra, calcio ni fósforo, así que `crude_fiber`, `calcium` y `total_phosphorus` no tendrían valor en D1. Duangnumsawang et al. (2022) informa calcio y fósforo total calculados, pero no se usan, porque el artículo no puede asignarse a un ensayo (sección 4).

## 4. Comparación con Duangnumsawang et al. (2022) (S-02)

Duangnumsawang et al. (2022) forma parte de HoloFood (D-06 §9). Su Tabla 1 titula los ingredientes `Ingredients (%)` y define tres fases: inicial (0–7 días), crecimiento (8–21) y final (22–37).

**Fases inicial y de crecimiento.** La Tabla 1 coincide con el experimento A en 13 de los 15 ingredientes de la fase inicial y en 14 de los 15 de la de crecimiento. B y C coinciden en 6 a 8 ingredientes por fase. Se cuenta como coincidencia el mismo valor numérico o un guion en ambas tablas. Hay tres diferencias con A. Dos son del trigo (52,8 frente a 52,75 y 61,2 frente a 61,24) y son compatibles con un redondeo a un decimal. La tercera es el fosfato dicálcico de la fase inicial (1,85 frente a 1,84).

**Fase final.** Ningún experimento coincide por completo (Tabla 9).

**Tabla 9.** Fase final de Duangnumsawang et al. (2022) frente a los experimentos A, B y C de S1

| Ingrediente (nombre en S1) | Duangnumsawang, 22–37 d | A, 21–35 d | B, 21–35 d | C, 21–35 d | Coincide exactamente con |
|---|---:|---:|---:|---:|---|
| Wheat · trigo | 62,0 | 61,97 | 61,05 | 62,15 | ninguno; A redondeado a un decimal da 62,0 |
| Soybean 48% · harina de soja 48 % PB | 15,9 | 15,8 | 16,79 | 15,75 | ninguno |
| Extruded Soyabean · soja extruida | 15,00 | 15 | 15 | 15 | A, B, C |
| Soyabean oil · aceite de soja | 0,00 | — | — | — | ninguno (guion en S1) |
| Animal fat (5 Sysfeed) · grasa animal | 4,01 | 4,01 | 4,08 | 3,98 | A |
| Dicalcium phosphate · fosfato dicálcico | 1,50 | 1,5 | 1,5 | 1,5 | A, B, C |
| Calcium carbonate · carbonato de calcio | 0,44 | 0,44 | 0,39 | 0,39 | A |
| Vitamin-Mineral premix · premezcla vitamínico-mineral | 0,40 | 0,4 | 0,4 | 0,4 | A, B, C |
| Sodium chloride · cloruro de sodio | 0,35 | 0,53 | 0,36 | 0,35 | C |
| DL-methionine · DL-metionina | 0,19 | 0,19 | 0,2 | 0,19 | A, C |
| L-lysine HCL · L-lisina HCl | 0,15 | 0,15 | 0,14 | 0,15 | A, C |
| Choline Chloride · cloruro de colina | 0,05 | 0,05 | 0,05 | 0,06 | A, B |
| L-threonine · L-treonina | 0,04 | 0,04 | 0,04 | 0,04 | A, B, C |
| Sodium bicarbonate · bicarbonato de sodio | 0,002 | — | — | — | ninguno (guion en S1) |
| Antioxidant (Noxyfeed 56P) · antioxidante | 0,02 | 0,02 | 0,02 | 0,02 | A, B, C |
| **Ingredientes que coinciden** | — | **10 de 15** | **6 de 15** | **8 de 15** | — |

*Fuente: Duangnumsawang et al. (2022), Tabla 1; Tous et al. (2022), Tabla suplementaria S1, p. 1. Valores en la escala publicada (porcentaje de la fórmula). Coincidencia: mismo valor numérico; un número frente a un guion no coincide.*

- **Cloruro de sodio:** 0,35, igual a C y a 0,01 de B (0,36); A tiene 0,53.
- **Harina de soja:** 15,9, distinta de A (15,8), B (16,79) y C (15,75).
- **Trigo:** 62,0, compatible con A redondeado a un decimal (61,97) y no con C (62,15).
- **Grasa animal, carbonato de calcio y colina:** iguales a A (4,01, 0,44 y 0,05) y distintos de C (3,98, 0,39 y 0,06).
- **Aceite de soja y bicarbonato de sodio:** Duangnumsawang informa 0,00 y 0,002 donde S1 tiene guion. No se imputan.

La fase final no coincide con A: el cloruro de sodio es el de C, y la harina de soja no es la de ningún experimento. Tampoco coincide con C, del que difiere en cinco ingredientes con valor en ambas tablas. Sigue siendo la más cercana a A, con 10 coincidencias de 15, frente a 8 con C y 6 con B.

**Nutrientes.** Los nutrientes analizados de Duangnumsawang no coinciden con ninguna formulación de S1 (Tabla 10). En las tres fases, la proteína bruta queda entre la de A y las de B y C, y la materia seca es mayor que en los tres experimentos.

**Tabla 10.** Nutrientes de Duangnumsawang et al. (2022) frente a S1 (g/kg; inicial / crecimiento / final)

| Nutriente (g/kg) | Duangnumsawang | A | B | C |
|---|---|---|---|---|
| Materia seca | 892 / 894 / 901 | 879 / 881 / 882 | 879 / 881 / 882 | 871 / 874 / 878 |
| Proteína bruta | 245 / 213 / 201 | 255 / 223 / 206 | 241 / 209 / 194 | 241 / 210 / 195 |
| Extracto etéreo | 57 / 63 / 84 | 57,0 / 63,4 / 81,5 | 57,0 / 64,0 / 82,0 | 56,8 / 63,8 / 82,6 |

*Fuente: Duangnumsawang et al. (2022), Tabla 1, nutrientes analizados; Tous et al. (2022), Tabla suplementaria S1, p. 1. La energía metabolizable es 2900, 3000 y 3100 kcal/kg en todos los casos (en Duangnumsawang, AME calculada).*

**Diseño.** Tous et al. (2022) describe tres experimentos idénticos, A en primavera, B en verano y C en otoño de 2019. Cada uno tiene 960 pollos en 24 corrales, 72 corrales en total. Duangnumsawang et al. (2022) describe un único experimento de 37 días con 2.880 pollos en 72 corrales y 6 corrales por tratamiento. Ese es el tamaño de los tres experimentos de Tous juntos, no el de uno. Ambos artículos tienen el mismo número de aprobación ética (10226, Generalitat de Catalunya). El tamaño es compatible con que Duangnumsawang reúna los tres ensayos, pero el artículo no lo dice y no se puede verificar.

**Respuesta a S-02.** No se puede establecer a qué ensayo de D1 (`CA`, `CB` o `CC`) corresponde Duangnumsawang et al. (2022), por tres razones:

1. El artículo describe un único ensayo de 37 días, sin nombrar la instalación ni usar códigos de ensayo, y su tamaño es el de los tres experimentos de Tous juntos.
2. Su fase final no coincide por completo con A ni con ningún otro experimento (Tabla 9), y sus nutrientes analizados no coinciden con ninguna formulación (Tabla 10).
3. No hay un identificador cruzado (código de ensayo, corral o fecha) entre el artículo y las fichas del portal.

Sí se sostienen dos cosas: que el artículo pertenece a HoloFood (D-06 §9) y que su formulación es la más cercana a la del experimento A. No se consultó a los autores; las diferencias quedan documentadas en las Tablas 9 y 10.

## 5. Fases de alimentación y días de muestreo

**Tabla 11.** Períodos de alimentación según cada fuente (días de edad)

| Fuente | Inicial | Crecimiento | Final |
|---|---|---|---|
| Tous et al. (2022), texto principal | 0–9 | 10–23 | 24–37 |
| Tous et al. (2022), Tabla suplementaria S1 | 0–7 | 7–21 | 21–35 |
| Duangnumsawang et al. (2022), Tabla 1 y métodos | 0–7 | 8–21 | 22–37 |

*Fuente: las indicadas en cada fila.*

Las fuentes no explican estas diferencias. Las tablas de este documento conservan los períodos literales de S1.

Los días de muestreo de D1 (7, 21 y 35) caen justo en los bordes de fase de S1. El día 7 cierra la fase 0–7 y abre la 7–21; el día 21 cierra la 7–21 y abre la 21–35; el día 35 cierra la 21–35. Para relacionar un día de muestreo con una formulación se declara un supuesto (SUP-3): **cada día de muestreo usa la fase consumida hasta ese día**.

- Día 7 → fase 0–7.
- Día 21 → fase 7–21.
- Día 35 → fase 21–35.

Tous et al. (2022) precisa que, por la carga de trabajo, el muestreo se hizo en los días 7–8, 21–22 y 35–37; D1 registra el día nominal. Con los períodos del texto de Tous, todos esos días caen dentro de la fase asignada. Con los de S1 y Duangnumsawang, un animal muestreado el día 8 o el 22 pudo recibir la dieta de la fase siguiente durante uno o dos días.

## 6. Relación con los ensayos de D1 y alcance

**Tabla 12.** Códigos de ensayo en el portal de HoloFood

| `trial_code` | Descripción en el portal | Ejemplo de ficha |
|---|---|---|
| `CA` | Trial 1 | [SAMEA112905145](https://www.holofooddata.org/animal/SAMEA112905145) |
| `CB` | Trial 2 | [SAMEA112904847](https://www.holofooddata.org/animal/SAMEA112904847) |
| `CC` | Trial 3 | [SAMEA112905246](https://www.holofooddata.org/animal/SAMEA112905246) |

*Fuente: HoloFood Data Portal, fichas de animal (consultadas el 02-11-2026).*

Las fichas del portal sostienen que `CA`, `CB` y `CC` corresponden a Trial 1, Trial 2 y Trial 3. Ningún identificador cruzado demuestra que Trial 1, 2 y 3 sean, en ese orden, los experimentos A, B y C de Tous. Las fechas de las fichas tampoco encajan con claridad con las estaciones que indica Tous (A en primavera, B en verano y C en otoño). La correspondencia queda como limitación formal (LIM-1), y **no se asigna una composición a los animales de D1**.

- **Dieta basal y aditivos.** Cada formulación de S1 es la dieta basal de su experimento y fase, común a los tres tratamientos de D1: `CC` (Control), `CO` (Probiótico) y `CE` (Fitobiótico). `CO` y `CE` agregan a esa dieta un aditivo a 0,75 g/kg de alimento (Tous et al., 2022; `holofood-source.md`). El aditivo no forma parte de `diet.composition`: corresponde al nodo `additive` del esquema del grafo, con `dose` 0,75 y `dose_unit` `g_kg`. Hoy D1 no construye nodos `additive`, y el tratamiento se codifica en el nodo `diet` (#176); agregar ese nodo lo decide Desarrollo.
- **`CC` tiene dos significados.** En D1, `CC` es a la vez un código de ensayo (`trial_code`) y el código del tratamiento Control. Todo uso de estas tablas debe calificar el código con su campo.

## 7. Supuestos y limitaciones

**Tabla 13.** Supuestos

| ID | Supuesto | Qué pasa si no se cumple | Fuente o estado |
|---|---|---|---|
| SUP-1 | Los ingredientes de S1 están en porcentaje de la fórmula, pese al encabezado `Ingredient (g/kg)`. | Los valores en `g_kg` serían diez veces mayores que los reales. | Sumas cercanas a 100 (Tabla 2) y encabezado `Ingredients (%)` en Duangnumsawang. Discrepancia editorial no confirmada. |
| SUP-2 | La energía se convierte con 1 kcal = 4,184 kJ y se redondea a dos decimales. | Con la caloría internacional (4,1868 kJ), los valores cambian menos de 0,01 MJ/kg. | Convención de esta emisión (Tabla 6). |
| SUP-3 | Cada día de muestreo usa la fase consumida hasta ese día: 7 → 0–7, 21 → 7–21 y 35 → 21–35. | Si el día de borde correspondiera a la fase que empieza, los animales de los días 7 y 21 tendrían la formulación siguiente. | Supuesto de esta emisión. Los días caen en los bordes de fase de S1; con los períodos del texto de Tous caen dentro de la fase asignada, aun con el muestreo real de los días 7–8, 21–22 y 35–37 (sección 5). |
| SUP-4 | Cada formulación de S1 es la dieta basal común a `CC`, `CO` y `CE` de su experimento, y los aditivos se agregan a ella. | La composición de `CO` y `CE` diferiría de la de `CC` más allá del aditivo. | Tous et al. (2022): tratamientos dieta basal, dieta basal con probiótico y dieta basal con fitobiótico. S1 no distingue tratamientos. |

*Fuente: secciones 2 a 6.*

**Tabla 14.** Limitaciones y puntos abiertos

| ID | Limitación | Efecto | Qué la cerraría o estado |
|---|---|---|---|
| LIM-1 | La correspondencia entre los experimentos A, B y C de Tous y los ensayos `CA`, `CB` y `CC` de D1 no está demostrada. | No se asigna composición a los animales de D1; `diet.composition` sigue ausente (NOD-08). | Un identificador cruzado entre la publicación y el portal (fechas, corrales o código de ensayo). Sin fuente identificada. |
| LIM-2 | El reparto entre `composition` e `ingredients`, el `component_id` `dry_matter` y los identificadores de ingredientes son una propuesta. | No se implementan hasta confirmarlos. | Confirmación de Desarrollo (@jvnioo). |
| LIM-3 | S1 entrega ingredientes y nutrientes, no sustratos fermentables. | Esta fuente no permite construir aristas `diet → provides → substrate`. | Una tabla de composición de ingredientes. El diccionario de datos del grafo nombra Feedtables y FooDB como fuentes complementarias para traducir dietas; no se evaluaron aquí. |
| LIM-4 | Aun resuelta LIM-1, la composición de un animal queda determinada por su ensayo y su día de muestreo (SUP-3), que ya entran a `x` del huésped como `trial_code` y `sampling_day`. | En D1, las columnas de composición no agregarían a `x` información que no esté ya en esas covariables; su valor está en habilitar las aristas de LIM-3. | Para tener en cuenta en Desarrollo. |
| LIM-5 | Duangnumsawang et al. (2022) no se asigna a ningún ensayo de D1 (sección 4). | Sus valores no se usan como composición de D1. | Cerrada en esta emisión: no se consultará a los autores y las diferencias quedan documentadas. |
| LIM-6 | Las fuentes no coinciden en los períodos de alimentación (Tabla 11). | Ninguno sobre la fase asignada a cada día (SUP-3). | Sin explicación en las fuentes; se conservan los períodos de S1. |

*Fuente: secciones 2 a 6.*

## Referencias

Área de Investigación · Microbioma Digital. (2026). *D-06 · Restricciones bioquímicas para D1*, versión 1.0, 29-10-2026, §9. `docs/research/`.

Célula de Desarrollo · NutriGraphDT. (2026). *Contrato de datos v2* (`docs/graph/data-contract-v2.md`), *Diccionario de datos del grafo* (`docs/graph/graph-data-dictionary.md`) y *Fuente D1 HoloFood* (`docs/data-sources/holofood-source.md`), commit `476615e`. [Repositorio jvnioo/NutriGraphDT](https://github.com/jvnioo/NutriGraphDT).

Duangnumsawang, Y., Zentek, J., Vahjen, W., Tarradas, J. y Goodarzi Boroojeni, F. (2022). Alterations in bacterial metabolites, cytokines, and mucosal integrity in the caecum of broilers caused by feed additives and host-related factors. *Frontiers in Physiology*, 13, 935870. https://doi.org/10.3389/fphys.2022.935870 (acceso abierto, CC BY 4.0).

HoloFood Data Portal. (s. f.). *HoloFood Chicken Experimental Design*. https://www.holofooddata.org/analysis-summary/holofood-chicken-experimental-design (consultado el 02-11-2026).

Tous, N., Marcos, S., Goodarzi Boroojeni, F., Pérez de Rozas, A., Zentek, J., Estonba, A., Sandvang, D., Gilbert, M. T. P., Esteve-Garcia, E., Finn, R., Alberdi, A. y Tarradas, J. (2022). Novel strategies to improve chicken performance and welfare by unveiling host-microbiota interactions through hologenomics. *Frontiers in Physiology*, 13, 884925. https://doi.org/10.3389/fphys.2022.884925 (Tabla suplementaria S1, p. 1; acceso abierto, CC BY 4.0).

## Anexo A. Nutrientes en formato `diet.composition`

Cuatro componentes por formulación, 36 filas. `value` usa punto decimal. La energía está convertida a `MJ_kg` (SUP-2); los demás componentes no tienen conversión.

**Tabla 15.** Nutrientes de las nueve formulaciones

| Experimento S1 | Fase S1 (días) | `component_id` | `value` | `unit` | Valor en S1 |
|---|---|---|---:|---|---|
| A | 0–7 | `crude_protein` | 255 | `g_kg` | 255 g/kg |
| A | 0–7 | `crude_fat` | 57.0 | `g_kg` | 57.0 g/kg |
| A | 0–7 | `metabolizable_energy` | 12.13 | `MJ_kg` | 2900 kcal/kg |
| A | 0–7 | `dry_matter` ‡ | 879 | `g_kg` | 879 g/kg |
| A | 7–21 | `crude_protein` | 223 | `g_kg` | 223 g/kg |
| A | 7–21 | `crude_fat` | 63.4 | `g_kg` | 63.4 g/kg |
| A | 7–21 | `metabolizable_energy` | 12.55 | `MJ_kg` | 3000 kcal/kg |
| A | 7–21 | `dry_matter` ‡ | 881 | `g_kg` | 881 g/kg |
| A | 21–35 | `crude_protein` | 206 | `g_kg` | 206 g/kg |
| A | 21–35 | `crude_fat` | 81.5 | `g_kg` | 81.5 g/kg |
| A | 21–35 | `metabolizable_energy` | 12.97 | `MJ_kg` | 3100 kcal/kg |
| A | 21–35 | `dry_matter` ‡ | 882 | `g_kg` | 882 g/kg |
| B | 0–7 | `crude_protein` | 241 | `g_kg` | 241 g/kg |
| B | 0–7 | `crude_fat` | 57.0 | `g_kg` | 57.0 g/kg |
| B | 0–7 | `metabolizable_energy` | 12.13 | `MJ_kg` | 2900 kcal/kg |
| B | 0–7 | `dry_matter` ‡ | 879 | `g_kg` | 879 g/kg |
| B | 7–21 | `crude_protein` | 209 | `g_kg` | 209 g/kg |
| B | 7–21 | `crude_fat` | 64.0 | `g_kg` | 64.0 g/kg |
| B | 7–21 | `metabolizable_energy` | 12.55 | `MJ_kg` | 3000 kcal/kg |
| B | 7–21 | `dry_matter` ‡ | 881 | `g_kg` | 881 g/kg |
| B | 21–35 | `crude_protein` | 194 | `g_kg` | 194 g/kg |
| B | 21–35 | `crude_fat` | 82.0 | `g_kg` | 82.0 g/kg |
| B | 21–35 | `metabolizable_energy` | 12.97 | `MJ_kg` | 3100 kcal/kg |
| B | 21–35 | `dry_matter` ‡ | 882 | `g_kg` | 882 g/kg |
| C | 0–7 | `crude_protein` | 241 | `g_kg` | 241 g/kg |
| C | 0–7 | `crude_fat` | 56.8 | `g_kg` | 56.8 g/kg |
| C | 0–7 | `metabolizable_energy` | 12.13 | `MJ_kg` | 2900 kcal/kg |
| C | 0–7 | `dry_matter` ‡ | 871 | `g_kg` | 871 g/kg |
| C | 7–21 | `crude_protein` | 210 | `g_kg` | 210 g/kg |
| C | 7–21 | `crude_fat` | 63.8 | `g_kg` | 63.8 g/kg |
| C | 7–21 | `metabolizable_energy` | 12.55 | `MJ_kg` | 3000 kcal/kg |
| C | 7–21 | `dry_matter` ‡ | 874 | `g_kg` | 874 g/kg |
| C | 21–35 | `crude_protein` | 195 | `g_kg` | 195 g/kg |
| C | 21–35 | `crude_fat` | 82.6 | `g_kg` | 82.6 g/kg |
| C | 21–35 | `metabolizable_energy` | 12.97 | `MJ_kg` | 3100 kcal/kg |
| C | 21–35 | `dry_matter` ‡ | 878 | `g_kg` | 878 g/kg |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. ‡ `dry_matter` es un `component_id` nuevo, pendiente de confirmar con Desarrollo (LIM-2).*

## Anexo B. Ingredientes en `g_kg` (trazabilidad)

Este anexo no entra en `diet.composition`. Respalda la lista de `diet.ingredients` (Tabla 8) con las cantidades de S1, para que Desarrollo no tenga que volver a transcribir el suplemento. Los identificadores son propuestas (LIM-2).

**Tabla 16.** Ingredientes de las nueve formulaciones

| Experimento S1 | Fase S1 (días) | Identificador propuesto | Ingrediente en S1 | Valor en S1 | `g_kg` |
|---|---|---|---|---:|---:|
| A | 0–7 | `wheat` | Wheat | 52.75 | 527.5 |
| A | 0–7 | `soybean_meal_48cp` | Soybean 48% | 39.4 | 394 |
| A | 0–7 | `soybean_oil` | Soyabean oil | 4.16 | 41.6 |
| A | 0–7 | `dicalcium_phosphate` | Dicalcium phosphate | 1.84 | 18.4 |
| A | 0–7 | `calcium_carbonate` | Calcium carbonate | 0.53 | 5.3 |
| A | 0–7 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| A | 0–7 | `sodium_chloride` | Sodium chloride | 0.37 | 3.7 |
| A | 0–7 | `dl_methionine` | DL-methionine | 0.27 | 2.7 |
| A | 0–7 | `l_lysine_hcl` | L-lysine HCL | 0.16 | 1.6 |
| A | 0–7 | `choline_chloride` | Choline Chloride | 0.03 | 0.3 |
| A | 0–7 | `l_threonine` | L-threonine | 0.05 | 0.5 |
| A | 0–7 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| A | 7–21 | `wheat` | Wheat | 61.24 | 612.4 |
| A | 7–21 | `soybean_meal_48cp` | Soybean 48% | 30.5 | 305 |
| A | 7–21 | `soybean_oil` | Soyabean oil | 4.8 | 48 |
| A | 7–21 | `dicalcium_phosphate` | Dicalcium phosphate | 1.66 | 16.6 |
| A | 7–21 | `calcium_carbonate` | Calcium carbonate | 0.48 | 4.8 |
| A | 7–21 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| A | 7–21 | `sodium_chloride` | Sodium chloride | 0.37 | 3.7 |
| A | 7–21 | `dl_methionine` | DL-methionine | 0.23 | 2.3 |
| A | 7–21 | `l_lysine_hcl` | L-lysine HCL | 0.19 | 1.9 |
| A | 7–21 | `choline_chloride` | Choline Chloride | 0.05 | 0.5 |
| A | 7–21 | `l_threonine` | L-threonine | 0.05 | 0.5 |
| A | 7–21 | `sodium_bicarbonate` | Sodium bicarbonate | 0.01 | 0.1 |
| A | 7–21 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| A | 21–35 | `wheat` | Wheat | 61.97 | 619.7 |
| A | 21–35 | `soybean_meal_48cp` | Soybean 48% | 15.8 | 158 |
| A | 21–35 | `extruded_soybean` | Extruded Soyabean | 15 | 150 |
| A | 21–35 | `animal_fat_5_sysfeed` | Animal fat (5 Sysfeed) | 4.01 | 40.1 |
| A | 21–35 | `dicalcium_phosphate` | Dicalcium phosphate | 1.5 | 15 |
| A | 21–35 | `calcium_carbonate` | Calcium carbonate | 0.44 | 4.4 |
| A | 21–35 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| A | 21–35 | `sodium_chloride` | Sodium chloride | 0.53 | 5.3 |
| A | 21–35 | `dl_methionine` | DL-methionine | 0.19 | 1.9 |
| A | 21–35 | `l_lysine_hcl` | L-lysine HCL | 0.15 | 1.5 |
| A | 21–35 | `choline_chloride` | Choline Chloride | 0.05 | 0.5 |
| A | 21–35 | `l_threonine` | L-threonine | 0.04 | 0.4 |
| A | 21–35 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| B | 0–7 | `wheat` | Wheat | 52.31 | 523.1 |
| B | 0–7 | `soybean_meal_48cp` | Soybean 48% | 39.88 | 398.8 |
| B | 0–7 | `soybean_oil` | Soyabean oil | 4.18 | 41.8 |
| B | 0–7 | `dicalcium_phosphate` | Dicalcium phosphate | 1.84 | 18.4 |
| B | 0–7 | `calcium_carbonate` | Calcium carbonate | 0.48 | 4.8 |
| B | 0–7 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| B | 0–7 | `sodium_chloride` | Sodium chloride | 0.37 | 3.7 |
| B | 0–7 | `dl_methionine` | DL-methionine | 0.28 | 2.8 |
| B | 0–7 | `l_lysine_hcl` | L-lysine HCL | 0.15 | 1.5 |
| B | 0–7 | `choline_chloride` | Choline Chloride | 0.03 | 0.3 |
| B | 0–7 | `l_threonine` | L-threonine | 0.05 | 0.5 |
| B | 0–7 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| B | 7–21 | `wheat` | Wheat | 60.52 | 605.2 |
| B | 7–21 | `soybean_meal_48cp` | Soybean 48% | 31.24 | 312.4 |
| B | 7–21 | `soybean_oil` | Soyabean oil | 4.85 | 48.5 |
| B | 7–21 | `dicalcium_phosphate` | Dicalcium phosphate | 1.66 | 16.6 |
| B | 7–21 | `calcium_carbonate` | Calcium carbonate | 0.44 | 4.4 |
| B | 7–21 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| B | 7–21 | `sodium_chloride` | Sodium chloride | 0.38 | 3.8 |
| B | 7–21 | `dl_methionine` | DL-methionine | 0.24 | 2.4 |
| B | 7–21 | `l_lysine_hcl` | L-lysine HCL | 0.17 | 1.7 |
| B | 7–21 | `choline_chloride` | Choline Chloride | 0.05 | 0.5 |
| B | 7–21 | `l_threonine` | L-threonine | 0.05 | 0.5 |
| B | 7–21 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| B | 21–35 | `wheat` | Wheat | 61.05 | 610.5 |
| B | 21–35 | `soybean_meal_48cp` | Soybean 48% | 16.79 | 167.9 |
| B | 21–35 | `extruded_soybean` | Extruded Soyabean | 15 | 150 |
| B | 21–35 | `animal_fat_5_sysfeed` | Animal fat (5 Sysfeed) | 4.08 | 40.8 |
| B | 21–35 | `dicalcium_phosphate` | Dicalcium phosphate | 1.5 | 15 |
| B | 21–35 | `calcium_carbonate` | Calcium carbonate | 0.39 | 3.9 |
| B | 21–35 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| B | 21–35 | `sodium_chloride` | Sodium chloride | 0.36 | 3.6 |
| B | 21–35 | `dl_methionine` | DL-methionine | 0.2 | 2 |
| B | 21–35 | `l_lysine_hcl` | L-lysine HCL | 0.14 | 1.4 |
| B | 21–35 | `choline_chloride` | Choline Chloride | 0.05 | 0.5 |
| B | 21–35 | `l_threonine` | L-threonine | 0.04 | 0.4 |
| B | 21–35 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| C | 0–7 | `wheat` | Wheat | 54.3 | 543 |
| C | 0–7 | `soybean_meal_48cp` | Soybean 48% | 38.02 | 380.2 |
| C | 0–7 | `soybean_oil` | Soyabean oil | 4.01 | 40.1 |
| C | 0–7 | `dicalcium_phosphate` | Dicalcium phosphate | 1.86 | 18.6 |
| C | 0–7 | `calcium_carbonate` | Calcium carbonate | 0.49 | 4.9 |
| C | 0–7 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| C | 0–7 | `sodium_chloride` | Sodium chloride | 0.37 | 3.7 |
| C | 0–7 | `dl_methionine` | DL-methionine | 0.28 | 2.8 |
| C | 0–7 | `l_lysine_hcl` | L-lysine HCL | 0.16 | 1.6 |
| C | 0–7 | `choline_chloride` | Choline Chloride | 0.05 | 0.5 |
| C | 0–7 | `l_threonine` | L-threonine | 0.05 | 0.5 |
| C | 0–7 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| C | 7–21 | `wheat` | Wheat | 62.19 | 621.9 |
| C | 7–21 | `soybean_meal_48cp` | Soybean 48% | 29.66 | 296.6 |
| C | 7–21 | `soybean_oil` | Soyabean oil | 4.71 | 47.1 |
| C | 7–21 | `dicalcium_phosphate` | Dicalcium phosphate | 1.67 | 16.7 |
| C | 7–21 | `calcium_carbonate` | Calcium carbonate | 0.44 | 4.4 |
| C | 7–21 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| C | 7–21 | `sodium_chloride` | Sodium chloride | 0.35 | 3.5 |
| C | 7–21 | `dl_methionine` | DL-methionine | 0.23 | 2.3 |
| C | 7–21 | `l_lysine_hcl` | L-lysine HCL | 0.18 | 1.8 |
| C | 7–21 | `choline_chloride` | Choline Chloride | 0.06 | 0.6 |
| C | 7–21 | `l_threonine` | L-threonine | 0.05 | 0.5 |
| C | 7–21 | `sodium_bicarbonate` | Sodium bicarbonate | 0.04 | 0.4 |
| C | 7–21 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |
| C | 21–35 | `wheat` | Wheat | 62.15 | 621.5 |
| C | 21–35 | `soybean_meal_48cp` | Soybean 48% | 15.75 | 157.5 |
| C | 21–35 | `extruded_soybean` | Extruded Soyabean | 15 | 150 |
| C | 21–35 | `animal_fat_5_sysfeed` | Animal fat (5 Sysfeed) | 3.98 | 39.8 |
| C | 21–35 | `dicalcium_phosphate` | Dicalcium phosphate | 1.5 | 15 |
| C | 21–35 | `calcium_carbonate` | Calcium carbonate | 0.39 | 3.9 |
| C | 21–35 | `vitamin_mineral_premix` | Vitamin-Mineral premix | 0.4 | 4 |
| C | 21–35 | `sodium_chloride` | Sodium chloride | 0.35 | 3.5 |
| C | 21–35 | `dl_methionine` | DL-methionine | 0.19 | 1.9 |
| C | 21–35 | `l_lysine_hcl` | L-lysine HCL | 0.15 | 1.5 |
| C | 21–35 | `choline_chloride` | Choline Chloride | 0.06 | 0.6 |
| C | 21–35 | `l_threonine` | L-threonine | 0.04 | 0.4 |
| C | 21–35 | `antioxidant_noxyfeed_56p` | Antioxidant (Noxyfeed 56P) | 0.02 | 0.2 |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. `g_kg`: valor de S1 × 10 (SUP-1).*

**Control de datos.** 113 valores numéricos y 22 guiones, para 15 ingredientes posibles en nueve formulaciones (135 celdas). Ningún guion se convirtió en cero. Las sumas por formulación de este anexo coinciden con la Tabla 2.

## Anexo C. Ingredientes con guion en S1

**Tabla 17.** Ingredientes sin valor numérico en S1

| Experimento S1 | Fase S1 (días) | Ingrediente con guion en S1 |
|---|---|---|
| A | 0–7 | Extruded Soyabean |
| A | 0–7 | Animal fat (5 Sysfeed) |
| A | 0–7 | Sodium bicarbonate |
| A | 7–21 | Extruded Soyabean |
| A | 7–21 | Animal fat (5 Sysfeed) |
| A | 21–35 | Soyabean oil |
| A | 21–35 | Sodium bicarbonate |
| B | 0–7 | Extruded Soyabean |
| B | 0–7 | Animal fat (5 Sysfeed) |
| B | 0–7 | Sodium bicarbonate |
| B | 7–21 | Extruded Soyabean |
| B | 7–21 | Animal fat (5 Sysfeed) |
| B | 7–21 | Sodium bicarbonate |
| B | 21–35 | Soyabean oil |
| B | 21–35 | Sodium bicarbonate |
| C | 0–7 | Extruded Soyabean |
| C | 0–7 | Animal fat (5 Sysfeed) |
| C | 0–7 | Sodium bicarbonate |
| C | 7–21 | Extruded Soyabean |
| C | 7–21 | Animal fat (5 Sysfeed) |
| C | 21–35 | Soyabean oil |
| C | 21–35 | Sodium bicarbonate |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. Un guion no tiene `value` y no se imputa.*

## Emisión y control de versiones

Yo, **Vicente Fuentes Rodríguez**, sublíder del Área de Investigación del proyecto Microbioma Digital, confirmo la emisión de este documento a la Célula de Desarrollo.

**Tabla 18.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | S-01 y S-02 · Composición de la dieta basal de HoloFood |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsable del levantamiento | Maximiliano Campos (@MaxiiCC), Célula de Investigación: hallazgo y transcripción de la Tabla S1 de Tous et al. (2022), comparación con Duangnumsawang et al. (2022) y control de datos |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Alcance | Issue #238: S-01 y S-02 |
| Fecha de emisión | 04-11-2026 |
| Versión | 1.0 |
| Estado | Emitido |

**Tabla 19.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 0.1 | 02-11-2026 | Levantamiento: transcripción de S1, comparación con Duangnumsawang et al. (2022) y control de datos (PR #254). | Maximiliano Campos |
| 1.0 | 04-11-2026 | Emisión: ingredientes en `g_kg`; nutrientes en `diet.composition` e ingredientes en `diet.ingredients`; comparación de la fase final con A, B y C, y respuesta a S-02; fase asignada a cada día de muestreo; alcance, supuestos y limitaciones. | Vicente Fuentes Rodríguez |
