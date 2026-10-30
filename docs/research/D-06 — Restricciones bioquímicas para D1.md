# D-06 · Restricciones bioquímicas para D1

Oct 29, 2026

**PIA-2 · Microbioma Digital — Gemelo Digital Nutricional basado en GNN y PINNs.** Proyecto NutriGraphDT · De: Célula de Investigación · Para: Célula de Desarrollo · sublíder Julio Provoste Palacios · Gestión de Proyectos Informáticos · Sección 302 · UTEM · 2026-II. Entregable D-06 (Actividad 78: ecuaciones y tolerancias bioquímicas), comprometido en la observación P-07 de la revisión A55 ([#158](https://github.com/jvnioo/NutriGraphDT/issues/158); comentario del sublíder en el PR [#217](https://github.com/jvnioo/NutriGraphDT/pull/217)) para el 06-11-2026. Cumple el compromiso 11 de la *Respuesta de Investigación a la Respuesta de Desarrollo* (Tabla 7).

**Respuesta corta.** D-06 v1 entrega una sola restricción bioquímica con fuente, escrita en fracciones molares: `d06.hydrogen.propionate_bound`, $h(p) = p_p - 2(p_a + p_b) \le 0$, que con el cierre simplex equivale a $p_p \le 2/3$. No tiene parámetros, así que no usa datos de D1. Es una condición necesaria del balance de hidrógeno de la fermentación y sigue siendo válida si el sumidero de H₂ es la acetogénesis, como sugiere la evidencia en aves. El balance completo de Wolin (1960) no se aplica a D1: se formuló para el rumen y D1 no mide CH₄, H₂ ni CO₂. En la literatura independiente, la fracción de propionato del ciego de broilers no pasa de 0,12, así que la cota no se activa en D1 y F5 no distingue brazos composicionales. Su efecto solo puede evaluarse en el dataset sintético o en baselines que predicen en ℝ³. Para F6 se recomienda, aparte de D-06, un control de soporte empírico de las predicciones.

## 1. Propósito, alcance y fuentes revisadas

Este documento formaliza la primera versión de D-06 para que Desarrollo la codifique con el contrato de restricciones (`CONSTRAINTS_CONTRACT_VERSION = "1.0.0"`).

- **Alcance.** D1 HoloFood, contenido cecal, los tres AGCC objetivo de D-03 (acetato, propionato y n-butirato), en el espacio `fractions`.
- **Fuera de alcance.**
  - Restricciones en concentraciones: necesitan el total, que no se predice fuera del corral (§4.6 de la respuesta del 16-10-2026; protocolo §3.1).
  - Restricciones por día de muestreo: el operador del contrato solo recibe el tensor de fracciones, no el día (sección 3.5).
  - El dataset sintético: no se revisa aquí, aunque es donde la restricción puede activarse (sección 6).
- **Regla de circularidad.** Ningún límite se deriva de los datos de D1 con que se evalúan los modelos. La restricción de v1 no tiene parámetros; la recomendación para F6 (sección 7) usa solo el train, declarado.

**Tabla 1.** Fuentes revisadas

| N° | Fuente | Versión o fecha | Uso en este documento |
|---|---|---|---|
| 1 | Respuesta de Investigación a la Solicitud de revisión v1.1, §4.6 | v1.0, 16-10-2026 | Principios de D-06: relaciones en proporciones molares; balances absolutos necesitan el total |
| 2 | Respuesta de Investigación a la Respuesta de Desarrollo, Tabla 7 | v1.0, 25-10-2026 | Compromiso 11 (D-06) |
| 3 | Revisión A55, observación P-07 (#158, PR #217) | Comentario del sublíder | Alcance, responsable y fecha de D-06 |
| 4 | `docs/models/constraints-evaluation-protocol.md`, §3 y §5 | `main`, commit `fc8b43f` | Taxonomía de restricciones y paso 1 de la decisión |
| 5 | `docs/models/constraints.md` y `src/nutrigraphdt/constraints/` | `main`, commit `fc8b43f` | Forma que debe tener una restricción |
| 6 | `docs/data-sources/holofood-source.md` | `main`, commit `fc8b43f` | Variables que mide D1 |
| 7 | Literatura con DOI (Referencias) | Consultada el 29-10-2026 | Estequiometría, sumideros de H₂ y composición de referencia |

## 2. Qué mide D1 y qué no

Un balance de fermentación necesita los productos de la fermentación, incluidos los gases. D1 mide solo los ácidos orgánicos del contenido cecal.

**Tabla 2.** Variables de un balance de fermentación y su disponibilidad en D1

| Variable | ¿Medida en D1? | Fuente en el repositorio | Uso en D-06 v1 |
|---|---|---|---|
| Acetato, propionato y n-butirato (µmol/g de digesta fresca) | Sí; objetivo del modelo (D-03) | `docs/data-sources/holofood-source.md`, archivo `scfa_caecum_content.tsv` | Entran en la restricción como fracciones molares |
| i-butirato, n- e i-valerato, D- y L-lactato | Sí; no son objetivo | Ídem | No entran en v1; podrían acotar el supuesto S2 en una v2 (Tabla 7) |
| CH₄, H₂ y CO₂ | No | No figuran entre las variables de la fuente D1 | Impiden cerrar el balance de Wolin (sección 4) |
| Sustrato fermentado (composición de la dieta) | No | `docs/graph/real-graph-validation-report.md`, NOD-08: `diet.composition` ausente en las 185 instancias | Impide un balance de carbono |

Las fracciones molares no tienen unidad: el cociente es el mismo en µmol/g y en mmol/kg.

## 3. Restricción `d06.hydrogen.propionate_bound`

### 3.1 Estequiometría de partida

Las ecuaciones (E1) a (E4) son la **estequiometría estándar atribuida a Wolin (1960); original no verificado**. (E5) es la acetogénesis reductiva, que se agrega para la sección 3.4. Todas están balanceadas en C, H y O.

- (E1) Acetato: C₆H₁₂O₆ + 2 H₂O → 2 CH₃COOH + 2 CO₂ + 4 H₂, es decir, **2 H₂ liberados por mol de acetato**.
- (E2) Propionato: C₆H₁₂O₆ + 2 H₂ → 2 CH₃CH₂COOH + 2 H₂O, es decir, **1 H₂ consumido por mol de propionato**.
- (E3) Butirato: C₆H₁₂O₆ → CH₃CH₂CH₂COOH + 2 CO₂ + 2 H₂, es decir, **2 H₂ liberados por mol de butirato**.
- (E4) Metanogénesis: CO₂ + 4 H₂ → CH₄ + 2 H₂O.
- (E5) Acetogénesis reductiva: 2 CO₂ + 4 H₂ → CH₃COOH + 2 H₂O, es decir, **4 H₂ consumidos por mol de acetato**.

### 3.2 Derivación paso a paso

Sean $A$, $P$ y $B$ los moles de acetato, propionato y butirato formados en el mismo volumen de digesta. El acetato se separa en el formado por fermentación con liberación de H₂ ($A_f$, como en E1) y el formado sin liberar H₂ o consumiéndolo ($A_r$, por ejemplo por E5). Del mismo modo, el butirato se separa en $B_f$ y $B_r$.

1. **Producción de H₂.** Con S2 (Tabla 3), solo liberan H₂ las vías de (E1) y (E3), a lo más 2 mol por mol: $H_\text{prod} \le 2A_f + 2B_f$.
2. **Consumo por el propionato.** Con S3, cada mol de propionato consume al menos 1 mol de H₂ (E2): $H_P \ge P$.
3. **Otros sumideros.** Metanogénesis (E4), acetogénesis (E5), H₂ acumulado o eliminado como gas y cualquier otra reducción. Todos son no negativos y D1 no mide ninguno: $S \ge 0$.
4. **Balance.** Con S1 (no hay aporte externo de H₂), lo producido iguala a lo consumido: $H_\text{prod} = H_P + S$.
5. **Desigualdad.** Encadenando los pasos anteriores: $P \le H_P \le H_P + S = H_\text{prod} \le 2A_f + 2B_f$. Como $A_f \le A$ y $B_f \le B$: $P \le 2A + 2B$.
6. **En fracciones.** Al dividir por $A + P + B > 0$: $p_p \le 2(p_a + p_b)$. Con el cierre $p_a + p_b = 1 - p_p$, equivale a $p_p \le 2/3$.

La restricción es entonces $h(p) = p_p - 2(p_a + p_b) \le 0$. No necesita el total ni ningún parámetro.

### 3.3 Supuestos

**Tabla 3.** Supuestos de la cota

| N° | Supuesto | Qué pasa si no se cumple | Fuente o estado |
|---|---|---|---|
| S1 | No hay aporte externo neto de H₂ al ciego: todo el H₂ se produce allí por fermentación. | Un aporte externo permitiría formar más propionato que el que cubren el acetato y el butirato. | SIN FUENTE para el ciego de aves. |
| S2 | Las únicas vías que liberan H₂ son las que forman acetato y butirato, con 2 mol de H₂ por mol como máximo (E1, E3). Otras fuentes, como la fermentación de proteínas hacia ácidos de cadena ramificada, se suponen despreciables. | Una fuente adicional de H₂ aumentaría la producción por encima de $2A + 2B$. | Apoyo parcial: Bautil et al. (2021) describen los ácidos de cadena ramificada del ciego como despreciables a los 36 días. Magnitud general: SIN FUENTE. |
| S3 | Todo el propionato se forma consumiendo al menos 1 mol de H₂ por mol, como en la vía desde hexosa (E2). | El **propionato de origen no carbohidrato** (por ejemplo, desde aminoácidos) que no consuma H₂ rompe la cota. | Proporción en el ciego de aves: **SIN FUENTE**. |
| S4 | El H₂ acumulado o eliminado como gas cuenta como sumidero no negativo. | Ninguno: es parte de $S \ge 0$. | Definición del balance. |

### 3.4 Por qué sigue siendo válida con acetogénesis

La acetogénesis reductiva (E5) consume H₂ y forma acetato. Con ella, el propionato que realmente puede formarse queda bajo un **límite real más estricto que la cota**:

$$P \le 2A_f + 2B_f - S \le 2A + 2B.$$

La acetogénesis lo hace más estricto por dos vías:

- agrega un sumidero no negativo ($4A_r$ dentro de $S$), que resta H₂ disponible para el propionato;
- parte del acetato medido no liberó H₂ ($A_f = A - A_r \le A$), mientras que la cota cuenta todo $A$.

Lo mismo ocurre con la metanogénesis (E4), con el H₂ acumulado y con cualquier vía que forme acetato o butirato sin liberar H₂: todas reducen el límite real sin cambiar la cota. Por eso la cota sigue siendo válida como condición necesaria, aunque quede todavía más lejos de ese límite, y no depende de cuál sea el sumidero dominante. Es relevante porque en el ciego de pollo los acetógenos parecen ser el principal consumidor de H₂ (Cisek et al., 2023; sección 4). La cota solo falla si se violan S1, S2 o S3.

### 3.5 Especificación para Desarrollo

**Tabla 4.** Especificación de la restricción en el contrato de restricciones 1.0.0

| Campo | Valor |
|---|---|
| `name` | `d06.hydrogen.propionate_bound` |
| `kind` | `inequality` |
| `space` | `fractions` |
| `unit` | `1` |
| `tolerance` | `0.0` (el contrato exige 0 en las desigualdades) |
| `version` | `1.0.0` |
| `status` | `active` |
| Operador | $h(p) = p_p - 2(p_a + p_b)$. Con las columnas en el orden del catálogo estructural (acetato, propionato, butirato): `values[:, 1] - 2.0 * (values[:, 0] + values[:, 2])` |
| Parámetros | Ninguno |
| Forma equivalente con cierre | $p_p \le 2/3$ |

El operador del contrato recibe solo el tensor de fracciones `[B, 3]`. Una versión por día de muestreo exigiría agregar el día a `ConstraintInputs`, un cambio de contrato que no se pide en v1.

## 4. Por qué el balance completo de Wolin no se aplica a D1

El balance de Wolin (1960) es una igualdad: supone que el H₂ que no consume el propionato termina en metano, $\text{CH}_4 = (2A + 2B - P)/4$. Aplicarlo a D1 requiere tres cosas que no se cumplen.

**Tabla 5.** Requisitos del balance completo y su estado en D1

| Requisito | Estado en D1 o en aves | Fuente |
|---|---|---|
| Un sistema como el del balance original | Wolin (1960) se formuló para el **rumen**, no para el ciego de aves. | Wolin (1960) |
| Medir el sumidero (CH₄) y, para un balance completo, H₂ y CO₂ | D1 no mide gases. | Tabla 2 |
| Que el metano sea el sumidero principal | En el ciego de pollo, los acetógenos dominan entre los consumidores de H₂ por abundancia de genes (*acsB*). Los metanógenos tienen mediana 0 log10/g en el conjunto de aves estudiado, que incluye aves SPF experimentales; en broilers comerciales la media es 4,24 log10/g. Es potencial génico, no flujo. | Cisek et al. (2023) |
| Que el balance cierre con los productos medidos | En cultivos de 24 h con inóculo cecal de gallinas ponedoras y almidón, midiendo CH₄, H₂ y AGV, la recuperación de H fue incompleta (70,5–82,1 %), con cerca de 1 % de H₂ en el espacio de cabeza. Solo se leyó el resumen; el texto completo es un escaneo sin capa de texto. | Marounek et al. (1996) |

En consecuencia, una igualdad con tolerancia exigiría datos de gases y un modelo del sumidero de H₂ en aves que hoy no tienen fuente. D-06 v1 se limita a la condición necesaria de la sección 3, que no depende del sumidero.

## 5. Composición de los AGCC en la literatura independiente

La Tabla 6 no fija ningún límite, porque la restricción no tiene parámetros. Muestra cuánta holgura tiene la cota frente a la composición publicada. Las fracciones son **cálculo nuestro**, con denominador acetato + propionato + butirato, a partir de **medias de grupo**. Ninguna fuente da valores por animal.

**Tabla 6.** Fracciones molares en el ciego de broilers (fuentes independientes de D1)

| Fuente | Aves y dieta | Día | Dato publicado | $p_a$ | $p_p$ | $p_b$ | $h(p)$ |
|---|---|---|---|---|---|---|---|
| van der Wielen et al. (2000) | Cobb; dieta no declarada, con antibióticos promotores del crecimiento | ≥ 15 | 70 / 8 / 24 µmol/g (meseta indicada en el texto; base húmeda o seca no declarada) | 0,686 | 0,078 | 0,235 | −1,76 |
| Mátis et al. (2022), control | Ross 308 machos; maíz, trigo y soya | 10 | 79,37 / 2,18 / 5,83 µmol/g (Tabla 5) | 0,908 | 0,025 | 0,067 | −1,93 |
| Mátis et al. (2022), control | Ídem | 21 | 62,66 / 3,43 / 7,44 µmol/g (Tabla 5) | 0,852 | 0,047 | 0,101 | −1,86 |
| Bautil et al. (2021) | Ross 308 machos; trigo y soya | 36 | 73,9 / 11,5 / 13,4 % del total de AGCC (texto, §3.6) | 0,748 | 0,116 | 0,136 | −1,65 |

Notas a la Tabla 6:

- **van der Wielen et al. (2000).** Los valores por edad solo están en una figura. El texto indica que el propionato y el butirato se detectan recién entre los días 12 y 15.
- **Mátis et al. (2022).** El tratamiento está confundido con el corral (un corral por grupo, n = 10). El artículo es inconsistente en la unidad: la Tabla 5 dice µmol/g y los métodos, nmol/g.
- **Bautil et al. (2021).** El total incluye el valerato. El texto no aclara si los porcentajes agrupan los tratamientos; el butirato del grupo control es 10,7 %.

El acetato domina en todos los casos. La mayor fracción de propionato es 0,116, frente a una cota de 0,667: la holgura es de más de cinco veces.

## 6. Conclusión declarada

- **En D1 la cota no se activa.** Ninguna composición publicada de ciego de broiler se acerca a $p_p = 2/3$ (Tabla 6). Un modelo que prediga composiciones cercanas a las observadas queda lejos de la frontera. Desarrollo lo confirma con el VR de la restricción en el reporte de F5.
- **F5 no distingue brazos composicionales en D1.** Las restricciones estructurales valen 0 por construcción (`docs/models/constraints.md`) y se espera lo mismo de esta cota. Con el paso 1 de §5 redactado como «¿cumple la tolerancia de D-06?» (P-07), ambos brazos lo cumplen, y la decisión recae en la calidad predictiva y la estabilidad.
- **Dónde puede evaluarse el efecto.** Solo en el dataset sintético o en baselines que predicen en ℝ³, que son los únicos casos en que la restricción puede activarse.

## 7. Recomendación para F6 (no es una restricción de D-06)

Los escenarios de F6 extrapolan, y allí sí puede haber predicciones fuera de lo observado. Se recomienda a Desarrollo un **control de soporte empírico**, que no entra en la pérdida ni en la decisión de F5:

1. Para cada fracción $k$ (acetato, propionato, butirato), calcular $L_k$ y $U_k$ como el mínimo y el máximo de $p_k$ en el conjunto con que se entrenó el modelo congelado; en validación cruzada, el train de cada fold. Se usan el mínimo y el máximo para no introducir un percentil sin fuente.
2. Si alguna fracción predicha en un escenario queda fuera de $[L_k, U_k]$, el resultado es **«no estimable»**, con el motivo, en vez de un número.

Esto aplica el criterio del Esquema General para escenarios (§5 y criterios de validación): la ausencia de cobertura devuelve «no estimable», no un número arbitrario. Es un control de cobertura, no una relación bioquímica. Si el motor de escenarios conoce el día de muestreo, el soporte puede calcularse por día; lo decide Desarrollo.

## 8. Qué haría falta para una D-06 v2

**Tabla 7.** Requisitos para una D-06 v2

| N° | Requisito | Para qué | Estado |
|---|---|---|---|
| 1 | Confirmar (E1) a (E4) en el original de Wolin (1960) | Citar la estequiometría con su fuente primaria | Pendiente; no bloquea v1 |
| 2 | Mediciones de CH₄ y H₂ (idealmente también CO₂) en ciego de pollo junto con los AGCC, en un dataset propio o publicado | Escribir el balance como igualdad con tolerancia | No disponible |
| 3 | Flujos de los sumideros de H₂ en aves (acetogénesis y metanogénesis), no solo abundancia de genes | Modelar el sumidero del balance | No disponible (Cisek et al., 2023, dan abundancia) |
| 4 | Composición por animal y por edad en estudios independientes de D1 | Fijar rangos por animal y por día | No disponible: solo hay medias de grupo |
| 5 | Agregar el día de muestreo a `ConstraintInputs` | Restricciones por día | Cambio de contrato; trabajo de Desarrollo |
| 6 | Acotar el propionato de origen no carbohidrato y otras fuentes de H₂ (S2, S3) | Reducir los supuestos de la cota | SIN FUENTE. Posible indicador: i-butirato e i-valerato del train, declarado |

## 9. Hallazgo lateral

Duangnumsawang et al. (2022) es parte del proyecto HoloFood (Horizon 2020, convenio 817729, según su sección de financiamiento) y repite el diseño de D1:

- probiótico con *Bacillus subtilis* DSM32324 y DSM32325 y *B. amyloliquefaciens* DSM25840, y fitobiótico de extracto de uva blanca;
- Ross308 y Cobb500, ambos sexos, factorial 3 × 2 × 2 de dieta, línea y sexo;
- muestreos en los días 7, 21 y 35, dieta de trigo y soya, y los mismos AGCC en µmol/g de muestra fresca.

**No es independiente de D1**, por eso no se usa en la Tabla 6 ni para fijar ningún límite. Probablemente responde **S-01** (composición de la dieta basal por fase, en su Tabla 1) y **S-02** (publicación del ensayo), y en parte el método analítico de los AGCC. Queda por verificar a qué ensayo de D1 corresponde (CA, CB o CC): el artículo describe un único ensayo de 37 días, no nombra la instalación y su aprobación ética es de la Generalitat de Catalunya.

## Emisión y control de versiones

Yo, **Vicente Fuentes Rodríguez**, sublíder del Área de Investigación del proyecto Microbioma Digital, confirmo la emisión de este documento a la Célula de Desarrollo.

**Tabla 8.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | D-06 · Restricciones bioquímicas para D1 |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Fecha de emisión | 29-10-2026 |
| Versión | 1.0 |
| Estado | Emitido |

**Tabla 9.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 1.0 | 29-10-2026 | D-06 v1: restricción `d06.hydrogen.propionate_bound`, límites del balance de Wolin en D1, composición de referencia, recomendación para F6 y requisitos de una v2. | Vicente Fuentes Rodríguez |

## Referencias

Área de Investigación · Microbioma Digital. (2026). *Respuesta de la Célula de Investigación a la Solicitud de revisión v1.1*, versión 1.0, 16-10-2026, §4.6. `docs/research/`.

Área de Investigación · Microbioma Digital. (2026). *Respuesta de Investigación a la Respuesta de Desarrollo*, versión 1.0, 25-10-2026, Tabla 7. `docs/research/`.

Área de Investigación · Microbioma Digital. (2026). *Esquema General del proyecto Microbioma Digital*, §5 y criterios de validación. `docs/research/`.

Bautil, A., Buyse, J., Goos, P., Bedford, M. R. y Courtin, C. M. (2021). Feed endoxylanase type and dose affect arabinoxylan hydrolysis and fermentation in ageing broilers. *Animal Nutrition*, 7(3), 787–800. https://doi.org/10.1016/j.aninu.2020.11.015

Célula de Desarrollo · NutriGraphDT. (2026). *Protocolo de evaluación con/sin restricciones* (`docs/models/constraints-evaluation-protocol.md`), *Interfaz de restricciones* (`docs/models/constraints.md`), *Fuente D1 HoloFood* (`docs/data-sources/holofood-source.md`) y *Reporte de validación de grafos reales* (`docs/graph/real-graph-validation-report.md`), commit `fc8b43f`. [Repositorio jvnioo/NutriGraphDT](https://github.com/jvnioo/NutriGraphDT).

Cisek, A. A., Dolka, B., Bąk, I. y Cukrowska, B. (2023). Microorganisms involved in hydrogen sink in the gastrointestinal tract of chickens. *International Journal of Molecular Sciences*, 24(7), 6674. https://doi.org/10.3390/ijms24076674

Duangnumsawang, Y., Zentek, J., Vahjen, W., Tarradas, J. y Goodarzi Boroojeni, F. (2022). Alterations in bacterial metabolites, cytokines, and mucosal integrity in the caecum of broilers caused by feed additives and host-related factors. *Frontiers in Physiology*, 13, 935870. https://doi.org/10.3389/fphys.2022.935870

Marounek, M., Rada, V. y Benda, V. (1996). Effect of ionophores and 2-bromoethanesulphonic acid in hen caecal methanogenic cultures. *Journal of Animal and Feed Sciences*, 5(4), 425–431. https://doi.org/10.22358/jafs/69620/1996

Mátis, G., Mackei, M., Boomsma, B., Fébel, H., Nadolna, K., Szymański, Ł., Edwards, J. E., Neogrády, Z. y Kozłowski, K. (2022). Dietary protected butyrate supplementation of broilers modulates intestinal tight junction proteins and stimulates endogenous production of short chain fatty acids in the caecum. *Animals*, 12(15), 1940. https://doi.org/10.3390/ani12151940

van der Wielen, P. W. J. J., Biesterveld, S., Notermans, S., Hofstra, H., Urlings, B. A. P. y van Knapen, F. (2000). Role of volatile fatty acids in development of the cecal microflora in broiler chickens during growth. *Applied and Environmental Microbiology*, 66(6), 2536–2540. https://doi.org/10.1128/AEM.66.6.2536-2540.2000

Wolin, M. J. (1960). A theoretical rumen fermentation balance. *Journal of Dairy Science*, 43(10), 1452–1459. https://doi.org/10.3168/jds.S0022-0302(60)90348-9 (original no verificado; cita confirmada en Crossref).
