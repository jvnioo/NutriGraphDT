# Revisión de coherencia bioquímica de las predicciones de D1 (A75-P3, #285)

- **Tipo:** revisión de Desarrollo, **no una aprobación de Investigación**. Como pide #285, no se
  espera una respuesta nueva de Investigación: el contraste se hace con lo que ella ya emitió (D-06,
  #256 y #257), y se le notifica el resultado en el PR.
- **Qué se revisa:** las predicciones de test del modelo de cada fold. Es `hetero_sage` con
  `TaxonIdentityConfig()`, el miembro 0 del ensamble de A75 y el mismo modelo de #266: 56 animales ×
  10 semillas del plan de #139, 560 predicciones.
- **Dónde está:** el cálculo lo hace `scripts/estimate_uncertainty.py`
  ([`uncertainty.md`](uncertainty.md)), y las cifras están en
  [`reports/uncertainty/d1/coherence.csv`](../../reports/uncertainty/d1/coherence.csv) y en la
  sección «Coherencia bioquímica» de su [`report.md`](../../reports/uncertainty/d1/report.md).
- **Valores nuevos:** ninguno. Cada comprobación usa una regla con fuente o un rango que sale de
  los datos.

## Estados

| Estado | Significado |
|---|---|
| `coherente` | La predicción cumple una condición con fuente. |
| `a revisar` | No la cumple; requiere análisis. |
| `sin fuente` | No hay una referencia con la que juzgarla; solo se informa. |

## Hallazgos

| ID | Comprobación | Resultado | Estado | Fuente |
|---|---|---|---|---|
| A75-C1 | Cierre de las fracciones | La suma se aparta de 1 en a lo más 2,2·10⁻¹⁶ (tolerancia numérica 10⁻⁹) | `coherente` | Contrato de datos v2, sección 1: las fracciones son la softmax de `(0, z_1, z_2)` |
| A75-C2 | Cota de D-06, $p_p \le 2/3$ | 0 de 560 sobre la cota; $p_p$ máxima predicha 0,167 | `coherente` | D-06, secciones 3 y 6 |
| A75-C3 | Soporte empírico: cada fracción dentro del mínimo y el máximo del train interno del fold | 0 de 560 fuera, en las tres fracciones | `coherente` | D-06, sección 7; `EmpiricalSupport` de #245 |
| A75-C4 | Fracción media predicha por día frente a la medida en el test de los folds | En los días 7, 21 y 35, la media predicha de cada fracción cae dentro del rango medido de ese día | `coherente` | Cohorte oficial de D1 (`configs/cohorts/d1_holofood.json`) |
| A75-C5 | Fracciones predichas frente a la Tabla 6 de D-06 | $p_p$ predicha: media 0,080, máximo 0,167. El máximo publicado es 0,116, una media de grupo | `sin fuente` | D-06, sección 5 y Tabla 7, N° 4 |

**Lectura de A75-C4.** Por día, la media predicha queda cerca de la medida (la tabla de
`coherence.csv` trae las tres fracciones). Por ejemplo, en el día 35 el acetato predicho promedia
0,733 frente a 0,708 medido, y el butirato 0,172 frente a 0,187. El modelo **contrae hacia la media**:
reproduce la tendencia por día, pero no los extremos de cada día.

**Lectura de A75-C5.** El 0,167 supera a la mayor fracción de propionato de la Tabla 6. Eso no es
una incoherencia:

- la Tabla 6 reúne **medias de grupo** de otros estudios;
- la cohorte de D1 tiene animales medidos con $p_p$ de hasta 0,227 en el día 35;
- D-06 declara que **no hay rangos por animal con fuente** (Tabla 7, N° 4).

Se informa sin estado de coherencia.

## Preguntas para Investigación

Ninguna nueva. La única referencia que faltaría, rangos de composición por animal y por día, ya está
declarada como no disponible en D-06 (Tabla 7, N° 4). Por eso no se abre una Issue.

## Relación con la incertidumbre (A75-P2)

Las fracciones son coherentes en promedio, pero sus intervalos no siempre cubren lo medido. En el
test, los del butirato y de `log_butyrate_acetate` muestran **subcobertura** en los tres niveles, y
los del día 7 cubren menos que los de los días 21 y 35 ([`uncertainty.md`](uncertainty.md), sección
5). La coherencia de las medias no basta para citar un intervalo.
