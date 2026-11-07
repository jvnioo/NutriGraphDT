# Decisión: tabla S-04 y relaciones taxón → función para aristas `has_capacity` en D1

**Emite:** Investigación. **Estado:** versión 2.0, pendiente de emisión por el sublíder (#236).
**Fecha:** 2026-11-07. La versión 1.0 (2026-11-03, corregida por Desarrollo el 2026-11-04) queda
reemplazada; su contenido se resume en la sección 8.
**Issues:** #236 (S-04, R-11), #175 (bloqueante), #173, #174, #185. Se coordina con #257 (nivel
y conjunto de funciones) y #256 (grafo mínimo de D1).
**Evidencia:**

- `configs/taxonomy/s04_silva132_gtdb_r207.tsv`: tabla S-04 de los 498 géneros de D1;
- `docs/research/s04_silva132_gtdb_r207_evidence.tsv`: evidencia por fila;
- `docs/research/build_s04_silva132_gtdb_r207.py`: script que genera ambas.

**Respuesta corta.** La tabla S-04 cubre ahora los **498 géneros** de D1. Cada fila se decide con
una regla explícita sobre evidencia de **SILVA 132**, la versión de D1, y no de la versión más
reciente que usa la columna `ssu_silva_taxonomy` de GTDB (objeción de Desarrollo del
04-11-2026). **46 géneros** tienen enlace `1:1` con un género del catálogo chicken-gut v1.0.1 y
pueden recibir `has_capacity`. Cubren el **37,0 %** de las lecturas asignadas a género (16,5 % del
total), frente al 31,8 % de la versión 1.0. El resultado es estable: con umbrales entre 80 % y
95 % se mueve entre 36,3 % y 39,9 %. Se confirman las cinco correcciones de Desarrollo. Tres de
los siete géneros aprobados en la versión 1.0 dejan de generar aristas: *Bifidobacterium*,
*Parabacteroides* y *Mucispirillum*.

## 1. Regla

Se crean aristas `has_capacity` **exclusivamente** desde taxones de género con
`relationship = 1:1` en `configs/taxonomy/s04_silva132_gtdb_r207.tsv`, y solo si el género GTDB
de la columna `gtdb_taxon_id` tiene especies en el catálogo `mgnify-chicken-gut@v1.0.1`. La
función y su anotación se toman de ese catálogo, con el nivel y el conjunto de funciones que fija
la decisión de #257. No se acepta curación bibliográfica manual para `has_capacity` (R-07). Los
nodos residuales no reciben aristas (contrato v2 §6).

| Caso | ¿Genera `has_capacity`? | Justificación |
|---|---|---|
| `1:1` y el género GTDB está en el catálogo | **Sí** | Enlace unívoco y funciones en la fuente aprobada. |
| `1:1` y el género GTDB no está en el catálogo | No | Sin funciones que asignar desde la fuente aprobada. |
| `1:N` | No | El género SILVA corresponde a varios géneros GTDB; la anotación no es unívoca. |
| `sin par` | No | Evidencia insuficiente para declarar el enlace. |

## 2. Método de la tabla

**Evidencia de SILVA 132.** Cada genoma de GTDB r207 registra en `ssu_silva_blast_subject_id` la
secuencia SILVA (`acceso.inicio.fin`) con la que mejor alinea su 16S. Esa misma secuencia se
busca en la taxonomía de **SILVA 132 Ref** (`taxmap_slv_ssu_ref_132.txt.gz`), que le asigna su
ruta; `tax_slv_ssu_132.txt` indica qué elemento de la ruta es el género. La etiqueta resultante es
de SILVA 132, la misma versión con la que MGnify clasificó las lecturas de D1. Así se resuelve la
objeción de la sección 8: `ssu_silva_taxonomy` usa una versión posterior de SILVA y distingue
géneros que SILVA 132 no tiene, como *Limosilactobacillus*.

**Filtros sobre los genomas.**

1. **Solo aislados** (`ncbi_genome_category = none`). El 16S de un MAG puede venir de otro
   organismo por contaminación del binning; GTDB r207 lo advierte en `FILE_DESCRIPTIONS.txt`. La
   evidencia de este documento lo confirma: las 10 especies de otros géneros que llevaban la
   etiqueta *Faecalibacterium* eran MAG de un solo genoma, varias con 16S idéntico al 100 % a
   *Faecalibacterium*.
2. **Identidad del alineamiento ≥ 94,5 %**, el umbral de género de Yarza et al. (2014). No
   cambia el resultado (sección 4), pero evita etiquetar un genoma con un género SILVA al que su
   16S no pertenece.

**Unidad de conteo: la especie.** Cada especie de GTDB toma el género SILVA 132 mayoritario de sus
genomas. Así, una especie con cientos de genomas secuenciados pesa lo mismo que una especie rara.
Contar genomas sesgaba la evidencia hacia especies muy secuenciadas. Por ejemplo, ocultaba que 9
especies que GTDB r207 clasifica en *Galliscardovia* llevan la etiqueta *Bifidobacterium*. Ocho de
ellas tienen nombre NCBI *Bifidobacterium*, y la novena es *G. ingluviei*, aislada del buche de
una gallina ponedora (Pechar et al. 2017).

**Clasificación.** Para cada género SILVA 132 de D1:

- **`1:1`**: al menos **3** especies GTDB llevan la etiqueta, el género GTDB más frecuente reúne
  al menos el **90 %** de ellas y el catálogo no trae otro género de la misma raíz (por ejemplo,
  `Barnesiella_A` junto a `Barnesiella`). Esa variante suele faltar entre los aislados, así que
  la evidencia no la puede descartar.
- **`1:N`**: al menos 3 especies y no se cumple lo anterior.
- **`sin par`**: menos de 3 especies con la etiqueta. Incluye 35 nombres de D1 que no existen
  como género en SILVA 132, como `Clostridium` o `Ruminococcus`: SILVA 132 tiene `Ruminococcus 1`
  y `Ruminococcus 2`. Esos 35 nombres suman 0,42 % de las lecturas a género.

**Por qué 90 % y 3 especies.** No hay un umbral publicado para este puente entre taxonomías, así
que el valor es una **convención del proyecto**, no un dato científico. Con 3 a 9 especies, el
90 % exige unanimidad. Desde 10 especies, tolera hasta una de cada diez discordante, un nivel de
ruido que el método aún deja pasar. Exigir 3 especies evita declarar un enlace unívoco con una
sola observación. La sección 4 muestra que el resultado no depende de estos valores.

**Género GTDB distinto del nombre SILVA.** El enlace puede ir a un género con otro nombre cuando
la evidencia lo sostiene. Ejemplos: `g__Tyzzerella` → `g__Anaerotignum` (6 de 6 especies) y
`g__Candidatus_Arthromitus` → `g__Dwaynesavagella`. Una unión por nombre no los habría encontrado
(D-04).

## 3. Resultado

| Relación | Géneros | % de lecturas a género |
|---|---:|---:|
| `1:1` con el género GTDB en el catálogo | **46** | **37,0** |
| `1:1` sin el género GTDB en el catálogo | 72 | 0,5 |
| `1:N` | 143 | 56,3 |
| `sin par` | 237 | 6,2 |
| **Total** | **498** | **100,0** |

Lecturas a género: 44,7 % del total de lecturas SSU de los 185 animales con metagenoma. Los 46
géneros cubren el 16,5 % del total.

**Los diez géneros `1:1` de mayor abundancia que generan aristas:**

| Género SILVA 132 | Género GTDB r207 | % lecturas a género | Especies con la etiqueta | Especies en el catálogo |
|---|---|---:|---:|---:|
| `g__Faecalibacterium` | `g__Faecalibacterium` | 28,04 | 11 de 11 | 8 |
| `g__Eisenbergiella` | `g__Eisenbergiella` | 3,30 | 3 de 3 | 10 |
| `g__Tyzzerella` | `g__Anaerotignum` | 1,41 | 6 de 6 | 3 |
| `g__Anaerotruncus` | `g__Anaerotruncus` | 1,39 | 7 de 7 | 3 |
| `g__Akkermansia` | `g__Akkermansia` | 0,84 | 3 de 3 | 3 |
| `g__Anaerostipes` | `g__Anaerostipes` | 0,69 | 9 de 10 | 3 |
| `g__Fournierella` | `g__Fournierella` | 0,60 | 4 de 4 | 9 |
| `g__Odoribacter` | `g__Odoribacter` | 0,23 | 4 de 4 | 2 |
| `g__Streptococcus` | `g__Streptococcus` | 0,11 | 294 de 295 | 2 |
| `g__Butyricimonas` | `g__Butyricimonas` | 0,08 | 7 de 7 | 3 |

Los 36 restantes suman 0,29 % e incluyen *Prevotella* y *Collinsella*. La lista completa está en
la tabla. *Faecalibacterium* sigue aportando 28,0 de los 37,0 puntos.

**Géneros abundantes que quedan `1:N`** (sin arista), con la evidencia que lo decide:

| Género SILVA 132 | % lecturas a género | Especies GTDB con la etiqueta |
|---|---:|---|
| `g__Bacteroides` | 14,91 | *Bacteroides* 50, *Phocaeicola* 22, *Bacteroides_H* 4 |
| `g__Alistipes` | 7,34 | *Alistipes* 16, *Alistipes_A* 3, *Tidjanibacter* 1 |
| `g__Lactobacillus` | 6,55 | 263 especies en más de 20 géneros (división de 2020) |
| `g__Butyricicoccus` | 3,35 | *Agathobaculum* 3, *QXXE01* 1, *Butyricicoccus* 1 |
| `g__Blautia` | 2,46 | *Blautia_A* 24, *Blautia* 7, *Kineothrix* 2 |
| `g__Subdoligranulum` | 2,20 | *Gemmiger* 6 de 6, pero el catálogo trae *Gemmiger_A* |
| `g__Oscillibacter` | 2,04 | *Dysosmobacter* 8, *NSJ-62* 2, *Oscillibacter* 2 |

## 4. Sensibilidad

| Variante | Géneros `1:1` en el catálogo | % lecturas a género | % del total |
|---|---:|---:|---:|
| **Regla adoptada** (90 %, ≥ 3 especies, aislados, identidad ≥ 94,5 %) | **46** | **37,0** | **16,5** |
| Umbral 80 % | 53 | 39,9 | 17,8 |
| Umbral 95 % | 44 | 36,3 | 16,2 |
| ≥ 2 especies | 52 | 37,7 | 16,9 |
| ≥ 5 especies | 33 | 31,8 | 14,2 |
| Sin filtro de identidad | 46 | 37,0 | 16,5 |
| Con MAG | 43 | 8,0 | 3,6 |

- Entre 80 % y 95 % el resultado cambia menos de 3 puntos: no depende del umbral elegido.
- Incluir MAG hunde la cobertura porque los 16S contaminantes rompen la unanimidad de géneros
  como *Faecalibacterium*. Es la razón del filtro 1 de la sección 2.
- **Alternativa descartada: contar solo géneros presentes en el catálogo.** Habría pasado a
  `1:1` a *Bifidobacterium* y *Parabacteroides*, pero también a *Roseburia*, cuyo género
  dominante en GTDB (*14-2*, 10 de 23 especies) simplemente no se recuperó como MAG. La ausencia
  en el catálogo no demuestra ausencia en el ciego, así que esta variante crearía enlaces sin
  sustento.

## 5. Respuesta a lo pendiente de #236

1. **Las cinco correcciones de Desarrollo se confirman**, con la evidencia de SILVA 132:

   | Género | Versión 1.0 corregida | Esta versión | Evidencia (especies GTDB con la etiqueta SILVA 132) |
   |---|---|---|---|
   | `Alistipes` | `1:N` | `1:N` | *Alistipes* 16, *Alistipes_A* 3, otros 2 |
   | `Barnesiella` | `1:N` | `1:N` | *Barnesiella* 4 de 4, pero el catálogo trae *Barnesiella_A* (2 especies) |
   | `Roseburia` | `1:N` | `1:N` | *14-2* 10, *Roseburia* 5, otros 8 |
   | `Ruminococcus` | `1:N` | `sin par` | El nombre no existe como género en SILVA 132 |
   | `Enterorhabdus` | `sin par` | `1:N` | *Adlercreutzia* 3, *Ellagibacter* 1, otros 2 |

   Las dos diferencias de clase no cambian el resultado: ninguno de los dos genera arista.
2. **Umbral para declarar `1:1`:** 90 % de las especies, con al menos 3, sobre evidencia de
   SILVA 132 en aislados (sección 2).
3. **La tabla queda completa:** 498 géneros con fuente, versión y evidencia por fila. Incluye
   *Butyricicoccus* (`1:N`), *Eisenbergiella* (`1:1`) y *Blautia* (`1:N`).
4. **Emisión:** bloque final, a cargo del sublíder.

**Cambios en los siete géneros aprobados en la versión 1.0:**

| Género | Versión 1.0 | Esta versión | Motivo | % lecturas a género |
|---|---|---|---|---:|
| `Faecalibacterium` | `1:1` | `1:1` | 11 de 11 especies | 28,04 |
| `Akkermansia` | `1:1` | `1:1` | 3 de 3 | 0,84 |
| `Prevotella` | `1:1` | `1:1` | 22 de 22 | 0,06 |
| `Collinsella` | `1:1` | `1:1` | 19 de 19 | 0,03 |
| `Bifidobacterium` | `1:1` | **`1:N`** | 81 de 92; 9 especies en *Galliscardovia* (GTDB) | 1,73 |
| `Parabacteroides` | `1:1` | **`1:N`** | 15 de 17; *Marseille-P3160* y *Barb7* | 0,90 |
| `Mucispirillum` | `1:1` | **`sin par`** | 1 especie con la etiqueta | 0,16 |

Se retiran 2,8 puntos y se agregan 8,0 con géneros nuevos (sección 3).

## 6. Supuestos y limitaciones

1. **El puente es indirecto.** Un genoma se etiqueta con el género SILVA 132 de la secuencia con
   la que mejor alinea en la versión de SILVA que usó GTDB. Solo cuentan los genomas cuya mejor
   secuencia también está en SILVA 132 Ref: 100 061 de los 226 658 aislados con un 16S alineado
   con identidad ≥ 94,5 %. Los géneros descritos después de SILVA 132 (2017) tienen menos
   evidencia y tienden a quedar `sin par`.
2. **Los géneros solo conocidos por MAG no tienen evidencia.** Por eso la regla de la misma raíz
   en el catálogo (sección 2) y el resultado conservador de *Barnesiella* y *Subdoligranulum*.
3. **El 90 % y las 3 especies son una convención del proyecto**, sin fuente que la fije. La
   sección 4 muestra que el resultado no depende de ellos.
4. **Cobertura funcional.** El 63,0 % de las lecturas a género y el 83,5 % del total (sumando
   los residuales) quedan sin camino taxón → función, y *Faecalibacterium* aporta 28,0 de los
   37,0 puntos. La ruta funcional de D1 dependerá sobre todo de ese género (L2 de la respuesta
   del 25-10-2026).
5. **Enlace N:1.** Dos géneros SILVA pueden enlazarse al mismo género GTDB. Por ejemplo,
   `g__Gardnerella` → `g__Bifidobacterium` (0,001 %) recibe las funciones de las especies
   *Bifidobacterium* del catálogo, aunque `g__Bifidobacterium` mismo quede `1:N`. Se acepta: cada
   enlace es unívoco desde el lado de SILVA, que es el del grafo.
6. **Capacidad anotada no es actividad demostrada** (esquema v1, `has_capacity`).
7. **Sin servicios de pago.** GTDB r207, SILVA 132 (CC BY 4.0, según su `LICENSE.txt`) y el FTP
   de MGnify son públicos y gratuitos.

## 7. Consecuencia para Desarrollo (#175)

- **#175 puede usar esta tabla en lugar de `s04_silva_gtdb_minimal.tsv`.** El formato es el mismo
  (`SilvaGtdbMapping.load_tsv` la carga sin cambios). La tabla mínima queda reemplazada. Retirarla
  y actualizar `tests/unit/test_taxonomy.py`, que la usa como fixture, es decisión de Desarrollo.
- **El catálogo se consulta con `gtdb_taxon_id`, no con el nombre SILVA.** En 5 de los 46 enlaces
  los nombres difieren: `Tyzzerella` → `Anaerotignum`, `Candidatus_Arthromitus` →
  `Dwaynesavagella`, `Gardnerella` → `Bifidobacterium`, `Tessaracoccus` → `Arachnia` y
  `Candidatus_Phytoplasma` → `Phytoplasma`.
- **`evidence_source` de `has_capacity`.** Investigación fijó el 25-10-2026 (R-01, pregunta 5)
  que `evidence_source` registra de dónde sale el dato: `mgnify-chicken-gut@v1.0.1`. Las reglas
  `1.3.0` (`ANNOTATION_DATABASES` en `graph/validation/edges.py`) solo admiten `KEGG` o `CAZy`
  como base de `has_capacity`. Se pide a Desarrollo admitir `mgnify-chicken-gut` como base de
  `has_capacity`. La base de la anotación (KEGG) queda identificada por `function_id` (`ko:K…`,
  #257).
- **Si la tabla cambia, se regeneran las aristas.** El script reproduce la tabla con las mismas
  entradas; las versiones van en su encabezado.

## 8. Historial: versión 1.0 y revisión de Desarrollo

La versión 1.0 (2026-11-03) aprobaba aristas para 10 géneros de una tabla mínima de 20 filas,
cruzada por nombre exacto con el catálogo (`compare_silva_mgnify_genera.py`,
`silva_mgnify_crosscheck.tsv`). El 04-11-2026, Desarrollo la contrastó con `ssu_silva_taxonomy`
de GTDB r207 (`verify_s04_gtdb_r207.py`, `s04_gtdb_r207_evidence.tsv`) y la corrigió en sentido
conservador. Quedaron 7 géneros: `Alistipes`, `Barnesiella`, `Roseburia` y `Ruminococcus` pasaron
a `1:N`, y `Enterorhabdus`, a `sin par`. Desarrollo señaló dos límites que esta versión resuelve:
esa columna no es SILVA 132 (sección 2) y no había umbral para declarar `1:1` (sección 2). Esos
archivos se conservan como registro.

## Referencias

- Parks, D. H. et al. (2022). GTDB: an ongoing census of bacterial and archaeal diversity through
  a phylogenetically consistent, rank normalized and complete genome-based taxonomy. *Nucleic
  Acids Research*, 50(D1), D785–D794. doi:10.1093/nar/gkab776. Datos: release 207,
  https://data.gtdb.ecogenomic.org/releases/release207/207.0/
- Pechar, R. et al. (2017). *Galliscardovia ingluviei* gen. nov., sp. nov., a thermophilic
  bacterium of the family *Bifidobacteriaceae* isolated from the crop of a laying hen (*Gallus
  gallus* f. *domestica*). *International Journal of Systematic and Evolutionary Microbiology*,
  67, 2403–2411. doi:10.1099/ijsem.0.001972.
- Quast, C. et al. (2013). The SILVA ribosomal RNA gene database project: improved data processing
  and web-based tools. *Nucleic Acids Research*, 41(D1), D590–D596. doi:10.1093/nar/gks1219.
  Datos: release 132, https://www.arb-silva.de/fileadmin/silva_databases/release_132/
- Yarza, P. et al. (2014). Uniting the classification of cultured and uncultured bacteria and
  archaea using 16S rRNA gene sequences. *Nature Reviews Microbiology*, 12, 635–645.
  doi:10.1038/nrmicro3330.
- MGnify chicken-gut v1.0.1, genomes pipeline v2.0.0:
  https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_genomes/chicken-gut/v1.0.1/

## Emisión y control de versiones

**Tabla A.** Datos de emisión

| Campo | Detalle |
|---|---|
| Documento | Decisión: tabla S-04 y relaciones taxón → función para aristas `has_capacity` en D1 |
| Emitido por | Célula de Investigación · Proyecto NutriGraphDT |
| Responsable de la curación | Felipe Cruz (@Felipex-x), Célula de Investigación |
| Responsable de la emisión | Vicente Fuentes Rodríguez, sublíder del Área de Investigación |
| Destinatario | Célula de Desarrollo · sublíder Julio Provoste Palacios |
| Alcance | Issue #236 (S-04) |
| Versión | 2.0 |
| Estado | **Pendiente de emisión.** El sublíder confirma la regla de la sección 2 y los cambios de la sección 5. |

**Tabla B.** Control de versiones

| Versión | Fecha | Cambios | Responsable |
|---|---|---|---|
| 1.0 | 03-11-2026 | Regla `has_capacity` y cruce de 10 géneros con el catálogo (PR #255). | Felipe Cruz |
| 1.0 (rev.) | 04-11-2026 | Corrección conservadora con GTDB r207: quedan 7 géneros. | Julio Provoste (Desarrollo) |
| 2.0 | 07-11-2026 | Tabla de los 498 géneros con evidencia de SILVA 132, umbral explícito, sensibilidad y respuesta a lo pendiente de #236. | Investigación, para emisión del sublíder |
