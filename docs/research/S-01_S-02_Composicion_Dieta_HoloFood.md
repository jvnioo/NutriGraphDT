# Composición de la dieta basal de HoloFood (S-01 / S-02)

**NutriGraphDT — Issue [#238](https://github.com/jvnioo/NutriGraphDT/issues/238)**  
**Preparado por:** @MaxiiCC · **Para revisión de:** Vicente (@hirojika)  
**Fecha:** 2 de noviembre de 2026 · **Estado:** borrador, pendiente de revisión

## 1. Qué se buscó

La tarea consistió en averiguar qué ingredientes formaban la dieta basal de los pollos de HoloFood en cada etapa de alimentación y comprobar cómo se relaciona el trabajo de Duangnumsawang et al. (2022) con los ensayos de D1 (`CA`, `CB` y `CC`).

Esto es relevante porque D1 registra el tipo de tratamiento alimentario, pero no incluye el detalle de los ingredientes de la dieta. Sin esa información, NutriGraphDT todavía no puede representar con respaldo documental la relación entre la dieta y los sustratos que podrían aprovechar los microorganismos.

## 2. Fuentes revisadas

- **Tous et al. (2022)**, [DOI 10.3389/fphys.2022.884925](https://doi.org/10.3389/fphys.2022.884925). Se revisó el artículo y su **Tabla suplementaria S1**, disponible en la primera página del archivo de material suplementario. Esta tabla distingue tres experimentos (A, B y C) y tres fases por experimento.
- **Duangnumsawang et al. (2022)**, [DOI 10.3389/fphys.2022.935870](https://doi.org/10.3389/fphys.2022.935870). Se utilizó la Tabla 1 y la sección de materiales y métodos para contrastar ingredientes, edades y diseño experimental.
- **Portal de HoloFood**, [diseño experimental](https://www.holofooddata.org/analysis-summary/holofood-chicken-experimental-design) y registros de animales, para revisar los códigos de ensayo.
- **Repositorio NutriGraphDT**, especialmente la issue #238, `docs/data-sources/holofood-source.md`, `docs/graph/graph-integrity-rules.md` y el documento D-06 (§9).

Se mantuvieron los valores originales de las tablas. Las sumas se calcularon aparte para revisar posibles problemas de transcripción, sin modificar los datos publicados.

## 3. Composición de las dietas (S-01)

La Tabla S1 de Tous contiene **nueve formulaciones**: una para cada combinación de experimento (A, B y C) y fase (0–7, 7–21 y 21–35 días). Se observan diferencias entre experimentos; por ejemplo, el trigo en la fase inicial es 52,75 en A, 52,31 en B y 54,30 en C.

En la fuente, la sección de ingredientes se titula `Ingredient (g/kg)`. Por ahora se conservan **los números tal como aparecen**, sin convertirlos. La duda sobre la unidad se explica en el apartado 5.

### Experimento A

| Ingrediente (nombre de S1) | 0–7 días | 7–21 días | 21–35 días |
|---|---:|---:|---:|
| Wheat (Trigo) | 52.75 | 61.24 | 61.97 |
| Soybean 48% (Harina de soja 48 % PB) | 39.4 | 30.5 | 15.8 |
| Extruded Soyabean (Soja extruida) | — | — | 15 |
| Soyabean oil (Aceite de soja) | 4.16 | 4.8 | — |
| Animal fat (5 Sysfeed) (Grasa animal (5 Sysfeed)) | — | — | 4.01 |
| Dicalcium phosphate (Fosfato dicálcico) | 1.84 | 1.66 | 1.5 |
| Calcium carbonate (Carbonato de calcio) | 0.53 | 0.48 | 0.44 |
| Vitamin-Mineral premix (Premezcla vitamínico-mineral) | 0.4 | 0.4 | 0.4 |
| Sodium chloride (Cloruro de sodio) | 0.37 | 0.37 | 0.53 |
| DL-methionine (DL-metionina) | 0.27 | 0.23 | 0.19 |
| L-lysine HCL (L-lisina HCl) | 0.16 | 0.19 | 0.15 |
| Choline Chloride (Cloruro de colina) | 0.03 | 0.05 | 0.05 |
| L-threonine (L-treonina) | 0.05 | 0.05 | 0.04 |
| Sodium bicarbonate (Bicarbonato de sodio) | — | 0.01 | — |
| Antioxidant (Noxyfeed 56P) (Antioxidante Noxyfeed 56P) | 0.02 | 0.02 | 0.02 |
| **Total calculado** | **99.98** | **100.00** | **100.10** |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. Los totales son cálculos propios a partir de los valores publicados.*

### Experimento B

| Ingrediente (nombre de S1) | 0–7 días | 7–21 días | 21–35 días |
|---|---:|---:|---:|
| Wheat (Trigo) | 52.31 | 60.52 | 61.05 |
| Soybean 48% (Harina de soja 48 % PB) | 39.88 | 31.24 | 16.79 |
| Extruded Soyabean (Soja extruida) | — | — | 15 |
| Soyabean oil (Aceite de soja) | 4.18 | 4.85 | — |
| Animal fat (5 Sysfeed) (Grasa animal (5 Sysfeed)) | — | — | 4.08 |
| Dicalcium phosphate (Fosfato dicálcico) | 1.84 | 1.66 | 1.5 |
| Calcium carbonate (Carbonato de calcio) | 0.48 | 0.44 | 0.39 |
| Vitamin-Mineral premix (Premezcla vitamínico-mineral) | 0.4 | 0.4 | 0.4 |
| Sodium chloride (Cloruro de sodio) | 0.37 | 0.38 | 0.36 |
| DL-methionine (DL-metionina) | 0.28 | 0.24 | 0.2 |
| L-lysine HCL (L-lisina HCl) | 0.15 | 0.17 | 0.14 |
| Choline Chloride (Cloruro de colina) | 0.03 | 0.05 | 0.05 |
| L-threonine (L-treonina) | 0.05 | 0.05 | 0.04 |
| Sodium bicarbonate (Bicarbonato de sodio) | — | — | — |
| Antioxidant (Noxyfeed 56P) (Antioxidante Noxyfeed 56P) | 0.02 | 0.02 | 0.02 |
| **Total calculado** | **99.99** | **100.02** | **100.02** |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. Los totales son cálculos propios a partir de los valores publicados.*

### Experimento C

| Ingrediente (nombre de S1) | 0–7 días | 7–21 días | 21–35 días |
|---|---:|---:|---:|
| Wheat (Trigo) | 54.3 | 62.19 | 62.15 |
| Soybean 48% (Harina de soja 48 % PB) | 38.02 | 29.66 | 15.75 |
| Extruded Soyabean (Soja extruida) | — | — | 15 |
| Soyabean oil (Aceite de soja) | 4.01 | 4.71 | — |
| Animal fat (5 Sysfeed) (Grasa animal (5 Sysfeed)) | — | — | 3.98 |
| Dicalcium phosphate (Fosfato dicálcico) | 1.86 | 1.67 | 1.5 |
| Calcium carbonate (Carbonato de calcio) | 0.49 | 0.44 | 0.39 |
| Vitamin-Mineral premix (Premezcla vitamínico-mineral) | 0.4 | 0.4 | 0.4 |
| Sodium chloride (Cloruro de sodio) | 0.37 | 0.35 | 0.35 |
| DL-methionine (DL-metionina) | 0.28 | 0.23 | 0.19 |
| L-lysine HCL (L-lisina HCl) | 0.16 | 0.18 | 0.15 |
| Choline Chloride (Cloruro de colina) | 0.05 | 0.06 | 0.06 |
| L-threonine (L-treonina) | 0.05 | 0.05 | 0.04 |
| Sodium bicarbonate (Bicarbonato de sodio) | — | 0.04 | — |
| Antioxidant (Noxyfeed 56P) (Antioxidante Noxyfeed 56P) | 0.02 | 0.02 | 0.02 |
| **Total calculado** | **100.01** | **100.00** | **99.98** |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. Los totales son cálculos propios a partir de los valores publicados.*

### Nutrientes informados en el suplemento

La tabla también incluye información nutricional. Son valores distintos a los porcentajes de ingredientes y no deberían mezclarse con la composición de la receta.

| Variable / unidad de presentación | A 0–7 | A 7–21 | A 21–35 | B 0–7 | B 7–21 | B 21–35 | C 0–7 | C 7–21 | C 21–35 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Energía metabolizable (kcal/kg) | 2900 | 3000 | 3100 | 2900 | 3000 | 3100 | 2900 | 3000 | 3100 |
| Materia seca (g/kg) | 879 | 881 | 882 | 879 | 881 | 882 | 871 | 874 | 878 |
| Proteína bruta (g/kg) | 255 | 223 | 206 | 241 | 209 | 194 | 241 | 210 | 195 |
| Extracto etéreo (g/kg) | 57.0 | 63.4 | 81.5 | 57.0 | 64.0 | 82.0 | 56.8 | 63.8 | 82.6 |

*Fuente: Tous et al. (2022), Tabla suplementaria S1, p. 1. La energía se informa en kcal/kg; las otras variables se presentan en g/kg.*

## 4. Comparación con Duangnumsawang

La Tabla 1 de Duangnumsawang usa explícitamente `Ingredients (%)` y sus valores se parecen mucho a los del **experimento A** de Tous. La coincidencia es clara en la mayoría de ingredientes de las fases inicial y de crecimiento, pero no es total.

Estas son las diferencias que conviene dejar registradas:

| Fase | Campo | Duangnumsawang (Tabla 1) | S1-A | Lectura crítica |
|---|---|---:|---:|---|
| Inicial | Wheat | 52.8 | 52.75 | Diferencia que puede ser compatible con redondeo, sin prueba del proceso editorial |
| Inicial | Dicalcium phosphate | 1.85 | 1.84 | Diferencia literal de 0,01 |
| Crecimiento | Wheat | 61.2 | 61.24 | Diferencia que puede ser compatible con redondeo, sin prueba del proceso editorial |
| Final | Wheat | 62.0 | 61.97 | Diferencia que puede ser compatible con redondeo, sin prueba del proceso editorial |
| Final | Soybean 48% | 15.9 | 15.8 | Diferencia explícita, no redondeo demostrable |
| Final | Soyabean oil | 0.00 | - | Diferencia entre valor explícito y guion; no imputar |
| Final | Sodium chloride | 0.35 | 0.53 | Diferencia explícita, no redondeo demostrable |
| Final | Sodium bicarbonate | 0.002 | - | Diferencia entre valor explícito y guion; no imputar |

En la fase final, por ejemplo, el cloruro de sodio es **0,35** en Duangnumsawang y **0,53** en Tous-A. También hay una diferencia entre 15,9 y 15,8 para la harina de soja. No sería correcto explicar ambas cifras como un simple redondeo.

Los análisis nutricionales tampoco son iguales:

| Nutriente | Duangnumsawang: Inicial / Crecimiento / Final (g/kg) | Tous S1-A: Inicial / Crecimiento / Final (g/kg) |
|---|---|---|
| Materia seca | 892 / 894 / 901 | 879 / 881 / 882 |
| Proteína bruta | 245 / 213 / 201 | 255 / 223 / 206 |
| Extracto etéreo | 57 / 63 / 84 | 57,0 / 63,4 / 81,5 |

Esto permite decir que **la formulación publicada por Duangnumsawang se parece especialmente a la del ensayo A**, pero no confirma por sí solo que se trate del mismo lote de alimento o que los autores hayan elegido deliberadamente A como referencia para todos los ensayos.

## 5. Dos dudas sobre las tablas que es importante aclarar

**Unidad de los ingredientes.** La Tabla S1 dice `g/kg`, pero cada formulación suma aproximadamente 100; si todas las cifras fueran realmente gramos por kilogramo de alimento, lo esperable sería una suma cercana a 1.000. Además, Duangnumsawang presenta cifras semejantes bajo `Ingredients (%)`. Por eso, la lectura **como porcentajes es la más razonable**, aunque no encontramos una aclaración editorial formal que permita llamar a esto una errata confirmada.

| Experimento | 0–7 días | 7–21 días | 21–35 días |
|---|---:|---:|---:|
| A | 99,98 | 100,00 | 100,10 |
| B | 99,99 | 100,02 | 100,02 |
| C | 100,01 | 100,00 | 99,98 |

**Días de cada fase.** Las publicaciones no expresan los períodos de la misma manera:

| Documento | Inicial | Crecimiento | Final |
|---|---|---|---|
| Tous, texto principal | 0–9 | 10–23 | 24–37 |
| Tous, Tabla suplementaria S1 | 0–7 | 7–21 | 21–35 |
| Duangnumsawang, Tabla 1 | 0–7 | 8–21 | 22–37 |

No se encontró una explicación que resuelva completamente estas diferencias. Para documentar S1 se respetaron los períodos del encabezado original. Antes de usar la información por animal, habrá que decidir con qué criterio se relaciona cada fase con los días de muestreo (7, 21 y 35).

## 6. Relación con los ensayos de D1 (S-02)

Tous describe tres experimentos de 960 pollos y 24 corrales cada uno. Duangnumsawang presenta un diseño de 2.880 pollos en 72 corrales, además de tratamientos, razas y edades de muestreo compatibles con HoloFood. También hay coincidencias en la aprobación ética (10226) y el financiamiento del proyecto.

Estos antecedentes **respaldan una relación estrecha entre ambos trabajos y el conjunto experimental de HoloFood**, pero no equivalen a una identificación de cada animal o muestra analizada.

En el portal de HoloFood se pueden consultar estas fichas:

| Código `trial_code` | Descripción en el portal | Ejemplo de registro |
|---|---|---|
| `CA` | Trial 1 | [SAMEA112905145](https://www.holofooddata.org/animal/SAMEA112905145) |
| `CB` | Trial 2 | [SAMEA112904847](https://www.holofooddata.org/animal/SAMEA112904847) |
| `CC` | Trial 3 | [SAMEA112905246](https://www.holofooddata.org/animal/SAMEA112905246) |

Con esos registros se puede sostener que **CA, CB y CC corresponden a Trial 1, Trial 2 y Trial 3** en el portal. Lo que no quedó comprobado mediante un identificador cruzado es que los ensayos numerados correspondan exactamente a A, B y C de Tous en ese mismo orden. La asociación parece razonable, pero las fechas de los registros y las estaciones mencionadas en la publicación no encajan con claridad.

Por lo mismo, **no corresponde asignar automáticamente las dietas A/B/C a los animales CA/CB/CC**. La issue permite dejar por escrito una correspondencia no demostrable, siempre que se explique el motivo.

Una precaución adicional: en D1 `CC` también identifica el tratamiento Control. Es importante indicar siempre si se está hablando del código de ensayo (`trial_code`) o del tratamiento.

## 7. Qué se puede entregar a Desarrollo

La Tabla S1 permite preparar la composición basal **por experimento y fase**, conservando cada ingrediente con `component_id`, `value` y `unit`, como pide la issue. El anexo presenta todos los valores numéricos en ese formato, con identificadores propuestos.

Por ejemplo:

```json
{"component_id": "wheat", "value": 52.75, "unit": "%"}
```

Este ejemplo representa el trigo del experimento A en la fase inicial. **La unidad `%` es una interpretación pendiente de aprobación** y `wheat` es un identificador propuesto. No se ha modificado el código del proyecto ni se han asignado esas cantidades a animales concretos.

Tampoco podemos calcular directamente los sustratos fermentables que llegan al ciego utilizando solo los porcentajes de ingredientes. Para eso haría falta información o una transformación adicional.

## 8. Conclusiones

La composición de las dietas basales está documentada para los tres experimentos y sus tres fases en la Tabla S1 de Tous. Las formulaciones son similares, pero presentan variaciones reales que conviene conservar en vez de reemplazarlas por una dieta promedio.

La Tabla 1 de Duangnumsawang tiene una coincidencia muy cercana con la formulación A, especialmente en las dos primeras fases. Aun así, hay diferencias que impiden considerarlas la misma tabla sin reservas.

Respecto de S-02, se pudo confirmar la numeración de los ensayos en registros del portal y reunir evidencias que relacionan ambos artículos con HoloFood. **Sigue pendiente demostrar el cruce exacto entre la nomenclatura A/B/C de Tous y CA/CB/CC de D1**, o aceptar formalmente esa limitación como parte del informe.

## 9. Puntos que me gustaría revisar con Vicente

1. Si es adecuado trabajar los valores de S1 como **porcentajes**, dejando constancia del encabezado original `g/kg`.
2. Cómo documentar los días de cada fase, dadas las diferencias entre las fuentes.
3. Si hay otro registro del proyecto que permita relacionar de manera explícita A/B/C con CA/CB/CC.
4. Si los `component_id` propuestos en el anexo sirven para la documentación o deben ajustarse al vocabulario que use Desarrollo.
5. Si basta con dejar documentadas las diferencias entre Duangnumsawang y Tous o conviene consultar a los autores.

Este archivo es un **borrador para revisión de Vicente**. La emisión oficial y su incorporación en `docs/research/` quedan pendientes de la aprobación correspondiente.

## Referencias

- Tous, N., et al. (2022). *Novel strategies to improve chicken performance and welfare by unveiling host-microbiota interactions through hologenomics*. *Frontiers in Physiology*, 13, 884925. https://doi.org/10.3389/fphys.2022.884925. **Ver Tabla suplementaria S1, p. 1.**
- Duangnumsawang, Y., et al. (2022). *Alterations in bacterial metabolites, cytokines, and mucosal integrity in the caecum of broilers caused by feed additives and host-related factors*. *Frontiers in Physiology*, 13, 935870. https://doi.org/10.3389/fphys.2022.935870. **Ver Tabla 1 y métodos.**
- HoloFood Data Portal. *HoloFood Chicken Experimental Design*. https://www.holofooddata.org/analysis-summary/holofood-chicken-experimental-design.
- NutriGraphDT. [Issue #238](https://github.com/jvnioo/NutriGraphDT/issues/238) y documentación del repositorio.

---

## Anexo: detalle de los ingredientes para `diet.composition`

A continuación se dejan los valores de la Tabla S1 con un identificador propuesto por ingrediente. El objetivo es que Desarrollo pueda revisarlos sin tener que volver a transcribir el suplemento.

La columna `unit` aparece como `%` **de forma provisional**, porque las cantidades suman aproximadamente 100 y son coherentes con los porcentajes publicados en Duangnumsawang. El encabezado original de Tous dice `Ingredient (g/kg)`; **no debe considerarse una unidad validada hasta que Vicente revise esta discrepancia**. Los `component_id` también son propuestas y no nombres canónicos aprobados.

Cada fila corresponde a Tous et al. (2022), Tabla suplementaria S1, p. 1. Los guiones originales se muestran en la segunda tabla y no se reemplazaron por ceros.

| Experimento S1 | Fase literal (días) | `component_id` (propuesto) | `value` (valor S1) | `unit` (propuesta) | Ingrediente original | Fuente |
|---|---|---|---:|---|---|---|
| A | 0–7 | `wheat` | 52.75 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| A | 0–7 | `soybean_meal_48cp` | 39.4 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| A | 0–7 | `soybean_oil` | 4.16 | `%` † | Soyabean oil | Tous 2022, S1 p. 1 |
| A | 0–7 | `dicalcium_phosphate` | 1.84 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| A | 0–7 | `calcium_carbonate` | 0.53 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| A | 0–7 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| A | 0–7 | `sodium_chloride` | 0.37 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| A | 0–7 | `dl_methionine` | 0.27 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| A | 0–7 | `l_lysine_hcl` | 0.16 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| A | 0–7 | `choline_chloride` | 0.03 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| A | 0–7 | `l_threonine` | 0.05 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| A | 0–7 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| A | 7–21 | `wheat` | 61.24 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| A | 7–21 | `soybean_meal_48cp` | 30.5 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| A | 7–21 | `soybean_oil` | 4.8 | `%` † | Soyabean oil | Tous 2022, S1 p. 1 |
| A | 7–21 | `dicalcium_phosphate` | 1.66 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| A | 7–21 | `calcium_carbonate` | 0.48 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| A | 7–21 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| A | 7–21 | `sodium_chloride` | 0.37 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| A | 7–21 | `dl_methionine` | 0.23 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| A | 7–21 | `l_lysine_hcl` | 0.19 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| A | 7–21 | `choline_chloride` | 0.05 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| A | 7–21 | `l_threonine` | 0.05 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| A | 7–21 | `sodium_bicarbonate` | 0.01 | `%` † | Sodium bicarbonate | Tous 2022, S1 p. 1 |
| A | 7–21 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| A | 21–35 | `wheat` | 61.97 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| A | 21–35 | `soybean_meal_48cp` | 15.8 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| A | 21–35 | `extruded_soybean` | 15 | `%` † | Extruded Soyabean | Tous 2022, S1 p. 1 |
| A | 21–35 | `animal_fat_5_sysfeed` | 4.01 | `%` † | Animal fat (5 Sysfeed) | Tous 2022, S1 p. 1 |
| A | 21–35 | `dicalcium_phosphate` | 1.5 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| A | 21–35 | `calcium_carbonate` | 0.44 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| A | 21–35 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| A | 21–35 | `sodium_chloride` | 0.53 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| A | 21–35 | `dl_methionine` | 0.19 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| A | 21–35 | `l_lysine_hcl` | 0.15 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| A | 21–35 | `choline_chloride` | 0.05 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| A | 21–35 | `l_threonine` | 0.04 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| A | 21–35 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| B | 0–7 | `wheat` | 52.31 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| B | 0–7 | `soybean_meal_48cp` | 39.88 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| B | 0–7 | `soybean_oil` | 4.18 | `%` † | Soyabean oil | Tous 2022, S1 p. 1 |
| B | 0–7 | `dicalcium_phosphate` | 1.84 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| B | 0–7 | `calcium_carbonate` | 0.48 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| B | 0–7 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| B | 0–7 | `sodium_chloride` | 0.37 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| B | 0–7 | `dl_methionine` | 0.28 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| B | 0–7 | `l_lysine_hcl` | 0.15 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| B | 0–7 | `choline_chloride` | 0.03 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| B | 0–7 | `l_threonine` | 0.05 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| B | 0–7 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| B | 7–21 | `wheat` | 60.52 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| B | 7–21 | `soybean_meal_48cp` | 31.24 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| B | 7–21 | `soybean_oil` | 4.85 | `%` † | Soyabean oil | Tous 2022, S1 p. 1 |
| B | 7–21 | `dicalcium_phosphate` | 1.66 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| B | 7–21 | `calcium_carbonate` | 0.44 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| B | 7–21 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| B | 7–21 | `sodium_chloride` | 0.38 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| B | 7–21 | `dl_methionine` | 0.24 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| B | 7–21 | `l_lysine_hcl` | 0.17 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| B | 7–21 | `choline_chloride` | 0.05 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| B | 7–21 | `l_threonine` | 0.05 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| B | 7–21 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| B | 21–35 | `wheat` | 61.05 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| B | 21–35 | `soybean_meal_48cp` | 16.79 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| B | 21–35 | `extruded_soybean` | 15 | `%` † | Extruded Soyabean | Tous 2022, S1 p. 1 |
| B | 21–35 | `animal_fat_5_sysfeed` | 4.08 | `%` † | Animal fat (5 Sysfeed) | Tous 2022, S1 p. 1 |
| B | 21–35 | `dicalcium_phosphate` | 1.5 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| B | 21–35 | `calcium_carbonate` | 0.39 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| B | 21–35 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| B | 21–35 | `sodium_chloride` | 0.36 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| B | 21–35 | `dl_methionine` | 0.2 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| B | 21–35 | `l_lysine_hcl` | 0.14 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| B | 21–35 | `choline_chloride` | 0.05 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| B | 21–35 | `l_threonine` | 0.04 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| B | 21–35 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| C | 0–7 | `wheat` | 54.3 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| C | 0–7 | `soybean_meal_48cp` | 38.02 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| C | 0–7 | `soybean_oil` | 4.01 | `%` † | Soyabean oil | Tous 2022, S1 p. 1 |
| C | 0–7 | `dicalcium_phosphate` | 1.86 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| C | 0–7 | `calcium_carbonate` | 0.49 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| C | 0–7 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| C | 0–7 | `sodium_chloride` | 0.37 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| C | 0–7 | `dl_methionine` | 0.28 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| C | 0–7 | `l_lysine_hcl` | 0.16 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| C | 0–7 | `choline_chloride` | 0.05 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| C | 0–7 | `l_threonine` | 0.05 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| C | 0–7 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| C | 7–21 | `wheat` | 62.19 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| C | 7–21 | `soybean_meal_48cp` | 29.66 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| C | 7–21 | `soybean_oil` | 4.71 | `%` † | Soyabean oil | Tous 2022, S1 p. 1 |
| C | 7–21 | `dicalcium_phosphate` | 1.67 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| C | 7–21 | `calcium_carbonate` | 0.44 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| C | 7–21 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| C | 7–21 | `sodium_chloride` | 0.35 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| C | 7–21 | `dl_methionine` | 0.23 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| C | 7–21 | `l_lysine_hcl` | 0.18 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| C | 7–21 | `choline_chloride` | 0.06 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| C | 7–21 | `l_threonine` | 0.05 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| C | 7–21 | `sodium_bicarbonate` | 0.04 | `%` † | Sodium bicarbonate | Tous 2022, S1 p. 1 |
| C | 7–21 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |
| C | 21–35 | `wheat` | 62.15 | `%` † | Wheat | Tous 2022, S1 p. 1 |
| C | 21–35 | `soybean_meal_48cp` | 15.75 | `%` † | Soybean 48% | Tous 2022, S1 p. 1 |
| C | 21–35 | `extruded_soybean` | 15 | `%` † | Extruded Soyabean | Tous 2022, S1 p. 1 |
| C | 21–35 | `animal_fat_5_sysfeed` | 3.98 | `%` † | Animal fat (5 Sysfeed) | Tous 2022, S1 p. 1 |
| C | 21–35 | `dicalcium_phosphate` | 1.5 | `%` † | Dicalcium phosphate | Tous 2022, S1 p. 1 |
| C | 21–35 | `calcium_carbonate` | 0.39 | `%` † | Calcium carbonate | Tous 2022, S1 p. 1 |
| C | 21–35 | `vitamin_mineral_premix` | 0.4 | `%` † | Vitamin-Mineral premix | Tous 2022, S1 p. 1 |
| C | 21–35 | `sodium_chloride` | 0.35 | `%` † | Sodium chloride | Tous 2022, S1 p. 1 |
| C | 21–35 | `dl_methionine` | 0.19 | `%` † | DL-methionine | Tous 2022, S1 p. 1 |
| C | 21–35 | `l_lysine_hcl` | 0.15 | `%` † | L-lysine HCL | Tous 2022, S1 p. 1 |
| C | 21–35 | `choline_chloride` | 0.06 | `%` † | Choline Chloride | Tous 2022, S1 p. 1 |
| C | 21–35 | `l_threonine` | 0.04 | `%` † | L-threonine | Tous 2022, S1 p. 1 |
| C | 21–35 | `antioxidant_noxyfeed_56p` | 0.02 | `%` † | Antioxidant (Noxyfeed 56P) | Tous 2022, S1 p. 1 |

**Control de datos:** 113 valores numéricos y 22 guiones originales, correspondientes a 15 ingredientes posibles en cada una de las nueve formulaciones. Ningún guion se convirtió en cero.

† La unidad `%` es una interpretación por validar; el encabezado original dice `g/kg`.

### Ingredientes que figuran con guion en S1

| Experimento S1 | Fase literal (días) | Ingrediente sin valor numérico en S1 | Interpretación |
|---|---|---|---|
| A | 0–7 | Extruded Soyabean | Guion literal; no se asigna `value` |
| A | 0–7 | Animal fat (5 Sysfeed) | Guion literal; no se asigna `value` |
| A | 0–7 | Sodium bicarbonate | Guion literal; no se asigna `value` |
| A | 7–21 | Extruded Soyabean | Guion literal; no se asigna `value` |
| A | 7–21 | Animal fat (5 Sysfeed) | Guion literal; no se asigna `value` |
| A | 21–35 | Soyabean oil | Guion literal; no se asigna `value` |
| A | 21–35 | Sodium bicarbonate | Guion literal; no se asigna `value` |
| B | 0–7 | Extruded Soyabean | Guion literal; no se asigna `value` |
| B | 0–7 | Animal fat (5 Sysfeed) | Guion literal; no se asigna `value` |
| B | 0–7 | Sodium bicarbonate | Guion literal; no se asigna `value` |
| B | 7–21 | Extruded Soyabean | Guion literal; no se asigna `value` |
| B | 7–21 | Animal fat (5 Sysfeed) | Guion literal; no se asigna `value` |
| B | 7–21 | Sodium bicarbonate | Guion literal; no se asigna `value` |
| B | 21–35 | Soyabean oil | Guion literal; no se asigna `value` |
| B | 21–35 | Sodium bicarbonate | Guion literal; no se asigna `value` |
| C | 0–7 | Extruded Soyabean | Guion literal; no se asigna `value` |
| C | 0–7 | Animal fat (5 Sysfeed) | Guion literal; no se asigna `value` |
| C | 0–7 | Sodium bicarbonate | Guion literal; no se asigna `value` |
| C | 7–21 | Extruded Soyabean | Guion literal; no se asigna `value` |
| C | 7–21 | Animal fat (5 Sysfeed) | Guion literal; no se asigna `value` |
| C | 21–35 | Soyabean oil | Guion literal; no se asigna `value` |
| C | 21–35 | Sodium bicarbonate | Guion literal; no se asigna `value` |
