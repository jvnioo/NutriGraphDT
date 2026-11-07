# Decisión: relaciones `function → produces → metabolite` y nivel de función en D1

**Emite:** Investigación. **Estado:** versión 1.0, pendiente de emisión por el sublíder (#257).
**Fecha:** 2026-11-07.
**Issues:** #257. Se coordina con #236 (tabla S-04), #175 (aristas `has_capacity`) y #256 (grafo
mínimo de D1).
**Evidencia:**

- `configs/functions/scfa_produces_d1.tsv`: las 9 relaciones aprobadas, en el formato que pide
  #257;
- `docs/research/scfa_has_capacity_preview.tsv`: qué funciones de ese conjunto tienen los géneros
  `1:1` del catálogo (vista previa para #175);
- `docs/research/build_scfa_function_edges.py`: script que comprueba cada relación en KEGG REST y
  genera ambos archivos.

**Respuesta corta.** La función es un **ortólogo de KEGG (KO)**, en `produces` y en
`has_capacity`. El conjunto se limita a **9 KO**: los que catalizan el paso que libera el AGCC
libre desde su acil-CoA o acil-fosfato. Hay 1 para acetato, 4 para propionato y 4 para
n-butirato, y cada relación está anotada en KEGG Release 120.0. No entran metabolitos
intermedios. Con la tabla S-04 de #236, el acetato queda alcanzable desde 35 géneros (36,1 % de
las lecturas a género) y el butirato desde 14 (35,8 %). El **propionato** solo desde 7 (2,1 %):
la anotación del catálogo no capta sus rutas principales. Es la limitación más importante de este
tramo.

## 1. Nivel de función: KO de KEGG

**Decisión.** `function_id = ko:<KO>`, por ejemplo `ko:K00929`. Es el mismo nivel para
`has_capacity` (#175) y para `produces`, así que los dos tramos se unen en el mismo nodo.

| Alternativa | ¿Sirve para `has_capacity`? | ¿Sirve para `produces`? | Decisión |
|---|---|---|---|
| **KO** | Sí: el catálogo anota cada gen con `KEGG_ko` (eggNOG-mapper 2.1.3, genomes pipeline v2.0.0). | Sí: KEGG enlaza cada KO con reacciones y cada reacción con sus compuestos. | **Adoptada** |
| Módulo KEGG | Sí: el catálogo publica la completitud de módulos por especie (`pangenome_functions/kegg_completeness`). | Solo para acetato: KEGG no tiene módulos de producción de propionato ni de butirato (búsqueda del 07-11-2026). | Descartada |
| Ruta KEGG (`map…`) | Demasiado amplia: `map00650` incluye producción y degradación de butirato. | No distingue la dirección. | Descartada |
| Familia CAZy | Sí | No: las CAZy degradan polisacáridos y pertenecen al lado del sustrato, que #258 decide. | Fuera de D1 este semestre |

El identificador KEGG va en `function_id` y no en `evidence_source` (respuesta del 25-10-2026,
pregunta 5).

## 2. Conjunto de funciones y relaciones aprobadas

**Regla.** Se aprueba `ko:<KO> → produces → <AGCC>` cuando se cumplen las tres condiciones:

1. KEGG enlaza el KO con una reacción que contiene el AGCC.
2. Esa reacción libera el AGCC libre desde su acil-CoA o su acil-fosfato, por transferencia de CoA
   o por fosfotransferencia. Son los pasos terminales de las rutas fermentativas que forman
   acetato, propionato y butirato en el intestino (Louis y Flint 2017).
3. La actividad no es secundaria de una enzima que KEGG asigna a otro AGCC.

| `function_id` | `metabolite_id` | Reacciones KEGG | Paso | `evidence_method` | `evidence_source` |
|---|---|---|---|---|---|
| `ko:K00925` | `acetate` | R00315 | *ackA*, acetato quinasa (ruta Pta-AckA, módulo M00579) | `database_annotation` | `KEGG@120.0` |
| `ko:K01026` | `propionate` | R00928, R01449 | *pct*, propionato CoA-transferasa (ruta del acrilato) | `database_annotation` | `KEGG@120.0` |
| `ko:K22214` | `propionate` | R11773 | *scpC*, propionil-CoA:succinil-CoA transferasa | `database_annotation` | `KEGG@120.0` |
| `ko:K00932` | `propionate` | R01353 | *tdcD*, propionato quinasa | `database_annotation` | `KEGG@120.0` |
| `ko:K19697` | `propionate` | R01353 | *pduW*, propionato quinasa (ruta del propanodiol) | `database_annotation` | `KEGG@120.0` |
| `ko:K00929` | `butyrate` | R01688 | *buk*, butirato quinasa (ruta Ptb-Buk) | `database_annotation` | `KEGG@120.0` |
| `ko:K01034` | `butyrate` | R01179, R01365 | *atoD*, CoA-transferasa, subunidad alfa | `database_annotation` | `KEGG@120.0` |
| `ko:K01035` | `butyrate` | R01179, R01365 | *atoA*, CoA-transferasa, subunidad beta | `database_annotation` | `KEGG@120.0` |
| `ko:K19709` | `butyrate` | R01179 | *ydiF*, butiril-CoA:acetato CoA-transferasa | `database_annotation` | `KEGG@120.0` |

Todas son `annotated`, nunca `observed` (V-01). Las CoA-transferasas de propionato y de
butirato consumen acetato en la dirección fermentativa. Por eso no tienen arista hacia `acetate`.

**Exclusiones**, con su motivo:

| Candidato en KEGG | Motivo |
|---|---|
| `K00925` (*ackA*) → propionato (R01353) | Actividad secundaria de la acetato quinasa. Enlazaría al propionato casi todos los géneros, tengan o no una ruta hacia propionil-CoA. Viola la condición 3. |
| Ligasas AMP-dependientes (`K01895`, `K01908`, `K01896`, `K01913`; R00925, R01354, R01176) | Activan el AGCC a acil-CoA, es decir, lo consumen. Viola la condición 2. |
| Ligasas ADP-dependientes (`K01905`, `K22224`, `K24012`; R00920) | KEGG las asigna al acetato (EC 6.2.1.13), y su dirección depende del organismo. |
| `K01067` (acetil-CoA hidrolasa) | No pertenece al módulo de producción de acetato de KEGG (M00579). |
| `K00634` (*ptb*), `K00625` y `K13788` (*pta*) | Forman el acil-fosfato, no el AGCC libre. Su paso siguiente (*buk*, *ackA*) ya está en el conjunto. |
| Marcadores de ruta (`K01604` *mmdA*, `K20626` *lcdA*, `K13922` *pduP*; Reichardt et al. 2014) | Producen intermediarios (propionil-CoA), no propionato. Para usarlos harían falta nodos intermedios y una relación de consumo que el esquema no tiene (sección 3). |
| R01355, R05366, R13136, R13556 y R01689 | Degradación de otros compuestos u oxidación del AGCC. |

## 3. Metabolitos

- **Solo los tres AGCC objetivo** reciben `produces`: `acetate`, `propionate` y `butyrate`. Son
  los identificadores canónicos de `MetaboliteLoader`; los compuestos KEGG son C00033, C00163 y
  C00246.
- **No se incluyen intermediarios este semestre**, ni lactatos ni propionil-CoA ni succinato. El
  esquema v1 no tiene una relación `metabolite → function` para el consumo. Un nodo `lactate`
  solo recibiría aristas `produces` y no llevaría a ningún AGCC: sería un extremo muerto. El
  intercambio de lactato entre bacterias que lo producen y bacterias que lo convierten en butirato
  o propionato queda como limitación. Representarlo exigiría un cambio de esquema o
  `cross_feeds`, que es hipotética y no entra a los grafos de entrenamiento.
- Los lactatos y los AGCC menores siguen sin entrar a `x` en ningún escenario (R-01, pregunta 2).

## 4. Regla de `has_capacity` para estas funciones (coordinación con #175 y #236)

- **Taxones:** solo los géneros `1:1` de la tabla S-04 cuyo género GTDB está en el catálogo
  (decisión de #236).
- **Funciones:** solo los 9 KO de la sección 2. El grafo de D1 tiene, a lo sumo, 9 nodos
  `function`. No se cargan las miles de funciones del catálogo, que no llegarían a ningún
  metabolito.
- **Agregación al género:** un género tiene `has_capacity` hacia un KO si **al menos una** de sus
  especies representativas en el catálogo tiene ese KO en su anotación eggNOG
  (`<especie>_eggNOG.tsv`, columna `KEGG_ko`). Los 1322 representantes del catálogo son MAG, con
  completitud desde 50,9 % (filtro QS ≥ 50 del pipeline). La falta de un gen en un MAG incompleto no
  demuestra que el género no lo tenga, y `has_capacity` describe capacidad, no actividad (esquema
  v1).
- **Soporte:** se recomienda guardar en la arista la fracción de especies con el KO
  (`species_with_ko / species` en la vista previa). Agregarla como atributo cambia el contrato de
  la relación. Desarrollo decide si entra en #175 o se informa solo en el reporte.
- **`evidence_source`:** `mgnify-chicken-gut@v1.0.1`, como fija la decisión de #236 (sección 7),
  con `evidence_method = database_annotation`.

## 5. Vista previa: qué AGCC alcanza cada género

Calculada con la tabla S-04 propuesta en #236, que aún no está en `main`. Si esa tabla cambia,
el script regenera la vista previa.

| AGCC | Géneros con al menos un KO | % de las lecturas a género | Géneros principales |
|---|---:|---:|---|
| Acetato | 35 | 36,1 | *Faecalibacterium*, *Eisenbergiella*, *Anaerotignum*, *Anaerotruncus* |
| n-Butirato | 14 | 35,8 | *Faecalibacterium* (*buk* en 5 de 8 especies), *Eisenbergiella* (9 de 10), *Anaerotruncus* |
| Propionato | 7 | 2,1 | *Anaerotignum* (*pct* en 3 de 3), *Anaerostipes* (1 de 3) |
| Ninguno | 8 | 0,9 | *Akkermansia*, *Holdemania* y otros 6 |

*Anaerotignum*, al que se enlaza `g__Tyzzerella` de SILVA 132, tiene *pct* en sus tres especies.
Concuerda con la ruta del acrilato de *A. propionicum*, que hasta 2017 se llamaba *Clostridium
propionicum* (Ueki et al. 2017). Sirve como control de que la anotación y el enlace taxonómico se
unen bien.

## 6. Uso en el modelo (pregunta 4 de #257)

Lo que la relación aporta, según Investigación:

1. **Diferencia los tres metabolitos.** Sin `produces`, los nodos `acetate`, `propionate` y
   `butyrate` solo se distinguen por su identificador. Con `produces`, cada uno recibe mensajes
   solo de sus funciones productoras y, a través de ellas, de los géneros que las portan.
2. **Explicaciones con ruta.** En F7, una explicación puede nombrar el camino
   `género → KO → AGCC`, con estado `annotated` en los dos tramos, en lugar de una importancia de
   taxón sin mecanismo.

Para Desarrollo, lo que se desprende del código de `main` (`c016a82`):

- `function` **sí** entra a la lectura (`EXCLUDED_FROM_READOUT` solo excluye `metabolite` y
  `phenotype`), y el constructor agrega las inversas `rev_*`. Con `has_capacity`, cada nodo
  función recibe la abundancia de los géneros que la portan, distinta en cada animal, desde la
  primera capa. Ese tramo puede influir en la predicción aunque `produces` no lo haga.
- `produces` solo llega a la predicción a través de `metabolite → measured_in → host`. Hacen
  falta 3 capas: taxón → función, función → metabolito y metabolito → huésped. La grilla de A45-5
  incluye `num_layers = 3`. Medirlo, con una ablación con y sin `produces`, corresponde a
  Desarrollo.
- `produces` no filtra el objetivo: la concentración medida vive en `y`, no en `x` del metabolito
  (contrato v2 §1).

## 7. Supuestos y limitaciones

1. **Capacidad anotada no es actividad demostrada.** Las reacciones de KEGG no son específicas del
   ciego de pollo, y los pasos terminales son reversibles. La dirección fermentativa es un
   supuesto tomado de la literatura (Louis y Flint 2017).
2. **La anotación del catálogo no capta las rutas principales de propionato.** eggNOG anota la
   metilmalonil-CoA mutasa (`K01847`) y la epimerasa (`K05606`) de la ruta del succinato en las 7
   especies de *Parabacteroides* y en 3 de las 5 de *Prevotella*. No asigna *mmdA* (`K01604`) a
   ninguna, ni un KO terminal de propionato. El propionato queda alcanzable solo desde el 2,1 % de las
   lecturas a género. Cualquier explicación sobre propionato en D1 tendrá muy poco soporte
   estructural.
3. **La butiril-CoA:acetato CoA-transferasa (*but*) no tiene KO en KEGG.** Es una CoA-transferasa
   de la familia III (Charrier et al. 2006), y es la vía terminal principal de *Faecalibacterium*
   (Louis y Flint 2017). En el catálogo, la única CoA-transferasa de la familia III anotada en
   *Faecalibacterium* (2 de 8 especies) lleva `K07749`, formil-CoA transferasa. Con KEGG no se
   puede saber si es *but*. La arista de *Faecalibacterium* hacia butirato descansa en *buk* (5 de
   8 especies), que no sería su ruta principal. Representar *but*
   exigiría una anotación por similitud fuera de KEGG, como la de Vital et al. (2014), y se deja
   fuera de este semestre.
4. **Subunidades.** *atoD* y *atoA* son subunidades de la misma enzima y quedan como dos nodos.
   Unirlas en un nodo sería un cambio de Desarrollo que no altera la regla.
5. **Versión de KEGG.** KEGG publica actualizaciones continuas. Las aristas registran
   `KEGG@120.0` y el archivo, la fecha de la base KO consultada (06-11-2026). El script falla si
   una relación deja de estar en KEGG.
6. **Sin servicios de pago.** KEGG REST es de uso libre para usuarios académicos (KEGG, *Academic
   use of KEGG*). El catálogo se descarga del FTP público de MGnify.

## 8. Consecuencia para Desarrollo

- **#175** crea `has_capacity` solo hacia los 9 KO, con la regla de la sección 4.
- **`produces`**: las 9 aristas de `configs/functions/scfa_produces_d1.tsv`, iguales en los 185
  grafos, cuando el grafo tiene el nodo función correspondiente. Las reglas `1.3.0` ya admiten
  `KEGG@<versión>` como base de `produces`.
- **Nodo `function`:** `function_id = ko:<KO>`. `function_type` y `annotation_source` (esquema
  v1) los fija Desarrollo; se sugiere `kegg_ortholog` y `eggNOG-mapper 2.1.3 (MGnify genomes
  pipeline v2.0.0)`.
- Con esto, el tramo `taxón → función → metabolito` de D1 queda definido. Lo que falta para el
  grafo mínimo lo decide #256.

## Referencias

- Cantalapiedra, C. P. et al. (2021). eggNOG-mapper v2: functional annotation, orthology
  assignments, and domain prediction at the metagenomic scale. *Molecular Biology and Evolution*,
  38(12), 5825–5829. doi:10.1093/molbev/msab293.
- Charrier, C. et al. (2006). A novel class of CoA-transferase involved in short-chain fatty acid
  metabolism in butyrate-producing human colonic bacteria. *Microbiology*, 152(1), 179–185.
  doi:10.1099/mic.0.28412-0.
- Kanehisa, M. et al. (2023). KEGG for taxonomy-based analysis of pathways and genomes. *Nucleic
  Acids Research*, 51(D1), D587–D592. doi:10.1093/nar/gkac963. Datos: KEGG Release 120.0,
  https://rest.kegg.jp, consultado el 07-11-2026.
- Louis, P. y Flint, H. J. (2017). Formation of propionate and butyrate by the human colonic
  microbiota. *Environmental Microbiology*, 19(1), 29–41. doi:10.1111/1462-2920.13589.
- Reichardt, N. et al. (2014). Phylogenetic distribution of three pathways for propionate
  production within the human gut microbiota. *The ISME Journal*, 8(6), 1323–1335.
  doi:10.1038/ismej.2014.14.
- Ueki, A. et al. (2017). Description of *Anaerotignum aminivorans* gen. nov., sp. nov., a
  strictly anaerobic, amino-acid-decomposing bacterium isolated from a methanogenic reactor, and
  reclassification of *Clostridium propionicum*, *Clostridium neopropionicum* and *Clostridium
  lactatifermentans* as species of the genus *Anaerotignum*. *International Journal of
  Systematic and Evolutionary Microbiology*, 67, 4146–4153. doi:10.1099/ijsem.0.002268.
- Vital, M., Howe, A. C. y Tiedje, J. M. (2014). Revealing the bacterial butyrate synthesis
  pathways by analyzing (meta)genomic data. *mBio*, 5(2), e00889-14. doi:10.1128/mBio.00889-14.
- MGnify chicken-gut v1.0.1, genomes pipeline v2.0.0:
  https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_genomes/chicken-gut/v1.0.1/

## Emisión y control de versiones

**Tabla A.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | Decisión: relaciones `function → produces → metabolite` y nivel de función en D1 |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Alcance | Issue #257 |
| Versión | 1.0 |
| Estado | **Pendiente de emisión.** El sublíder confirma el nivel de función (sección 1), el conjunto (sección 2) y la regla de agregación (sección 4). |

**Tabla B.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 1.0 | 07-11-2026 | Nivel de función, 9 relaciones aprobadas, metabolitos, regla de `has_capacity` y vista previa. | Investigación, para emisión del sublíder |
