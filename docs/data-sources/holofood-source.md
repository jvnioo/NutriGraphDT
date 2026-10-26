# Fuente real D1: HoloFood (pollo)

Primera fuente real integrada al módulo de datos. Es el conjunto núcleo que recomienda la
[revisión de repositorios y datasets](<../research/Repositorios y Datasets — PIA Microbioma Digital.md>)
(D1, nivel A): el único identificado que reúne, para **el mismo animal**, microbioma, AGCC,
dieta y fenotipo bajo tratamientos dietarios controlados (Rogers et al., 2025).

## Obtener los datos

```bash
pip install -e ".[dev]"
python scripts/fetch_holofood.py            # salida en data/raw/D1_holofood/
```

No requiere credenciales. La primera ejecución hace ~1600 consultas a servicios públicos de
EMBL-EBI y tarda entre 30 y 60 minutos; las respuestas quedan en `data/raw/D1_holofood/_cache/`
y una segunda ejecución termina en segundos. `--refresh` ignora la caché. `data/raw/` está
ignorado por Git: los datos no se versionan, se regeneran con el script.

Al terminar, `manifest.json` registra la fecha de descarga, los servicios y estudios
consultados, los conteos de cobertura y el SHA-256 de cada tabla. El test
`tests/integration/test_holofood_source.py` comprueba esos checksums y procesa la descarga
completa cuando existe.

## De dónde sale cada dato

| Servicio | Qué aporta |
|---|---|
| HoloFood Data Portal (`https://www.holofooddata.org/api`, `/export/samples`) | Lista de muestras con su animal; ficha de cada animal (tratamiento, sexo, raza, día de muestreo, peso); AGCC de cada muestra de metabolómica dirigida. |
| MGnify API v1 (`https://www.ebi.ac.uk/metagenomics/api/v1`) | Tablas de abundancia taxonómica SSU rRNA (pipeline 5.0) de los estudios HoloFood de pollo. |
| ENA Portal API (`filereport`, `read_run`) | Correspondencia corrida (`ERR…`) → BioSample, para atribuir cada columna de MGnify a un animal. |

## Tablas generadas

Todas usan como `sample_id` la **accesión BioSample del animal** (`SAMEA…`), que es la clave
común entre ómicas. Cada tabla se registra como una fuente propia en `configs/sources.json`,
porque cada loader lee un archivo.

| Archivo | `source_id` | Loader | Contenido |
|---|---|---|---|
| `abundance_ssu_caecum.tsv` | `D1_holofood` | `AbundanceLoader` | Conteos SSU por linaje (filas) y animal (columnas), contenido cecal. El loader normaliza a abundancia relativa. |
| `scfa_caecum_content.tsv` | `D1_holofood_scfa_content` | `MetaboliteLoader` | Acetato, propionato, n- e i-butirato, n- e i-valerato, D- y L-lactato del **contenido cecal**, en µmol/g de digesta fresca (base húmeda; el loader los lleva a `mmol_kg`, factor 1). |
| `scfa_caecum_tissue.tsv` | `D1_holofood_scfa_tissue` | `MetaboliteLoader` | Las mismas columnas para las muestras que el portal rotula `caecum tissue`. |
| `metadata.tsv` | `D1_holofood_metadata` | `MetadataLoader` | Ensayo, corral, tratamiento dietario (código y nombre), sexo, raza, día de muestreo y peso individual (g). |
| `sample_map.tsv` | — | — | Por animal: código, BioSample y corridas del metagenoma, estudio de MGnify y BioSamples de AGCC. Sirve para auditar cada fila hasta su origen. |

## Cobertura

Descarga del 2026-10-07 (MGnify pipeline 5.0; estudios MGYS00005766, MGYS00006042, MGYS00006062, MGYS00006532, MGYS00006533 y MGYS00006651):

| Conteo | Valor |
|---|---|
| Animales de pollo en el portal | 656 |
| Corridas de contenido cecal atribuidas a un animal | 189 |
| Animales con metagenoma cecal (`abundance_ssu_caecum.tsv`) | 185 |
| Animales con AGCC de contenido cecal (`scfa_caecum_content.tsv`) | 248 (12 filas sin valores) |
| Animales con AGCC rotulados `caecum tissue` | 224 |
| Animales con metadatos (`metadata.tsv`) | 530 |
| **Metagenoma + AGCC de contenido, ambos con valores** | **59** (57 con ≥ 1000 lecturas) |
| **Cohorte supervisada** ([abajo](#cohorte-supervisada-138)) | **56** |
| Linajes SSU distintos | 1317 |

Diseño experimental (metadatos de los 530 animales): tres ensayos (`CA`, `CB`, `CC`), tres
tratamientos con el mismo código en todos los ensayos (`CC` Control, `CO` Probiótico,
`CE` Fitobiótico, que la API nombra «Prebiotic»), dos razas (Ross, Cobb), ambos sexos y
muestreo en los días 7, 21 y 35. No hay campos vacíos.

**El subconjunto emparejado está desbalanceado.** De los 59 animales con metagenoma y AGCC de
contenido, la mayoría son Control (37); Probiótico tiene 15 y Fitobiótico 7, repartidos en
ensayos y días distintos. Alcanza para construir y validar grafos reales (A39), pero no para
estimar efectos de la dieta: cualquier comparación entre tratamientos con este subconjunto
debe declararse exploratoria.

## Decisiones y cautelas

- **Respuestas parciales de ENA (descarga del 2026-10-14 UTC).** El `filereport` de ENA devolvió de
  forma intermitente respuestas con solo la cabecera o con una corrida para proyectos que tienen
  decenas o cientos (PRJEB39110, PRJEB41323, PRJEB47613, PRJEB46550). El script las guarda en
  `_cache/` como si fueran completas, y la descarga resultante tenía 93 animales con metagenoma en
  lugar de 185. Antes de usar una descarga, compare los conteos de `manifest.json` con la tabla de
  Cobertura (189 corridas, 185 animales con metagenoma, 61 con metagenoma y AGCC de contenido).
  Si no coinciden, borre de `_cache/` las respuestas de ENA y vuelva a ejecutar el script: el
  resto de la caché se reutiliza. Con ese procedimiento, la descarga del 2026-10-14 reprodujo los
  conteos del 2026-10-07.
- **Matrices separadas.** El portal declara `Body site` por muestra de AGCC: `caecum content`
  o `caecum tissue`. Se leen de la ficha, no del título, y cada matriz va a su tabla. El
  metagenoma es de contenido cecal, así que el emparejamiento directo es con
  `scfa_caecum_content.tsv`. Que las muestras rotuladas `tissue` informen la unidad
  "µmol/g digesta" es una inconsistencia del portal. Investigación confirmó que no se usan en
  F4, ni como objetivo ni como entrada (V-03); su naturaleza depende del método analítico del
  ensayo (S-02). Ningún animal tiene AGCC de ambas matrices (248 de contenido y 224 «tissue»,
  sin intersección) y ningún perfil «tissue» coincide con uno de contenido, así que comparar
  matrices no permite detectar un error de rótulo.
- **Unidad en base húmeda.** Las tablas del portal no traen materia seca: los AGCC están en
  µmol/g de digesta fresca y no son comparables con estudios que informan base seca (V-06).
- **Perfiles de AGCC repetidos.** Cuatro pares de animales tienen el mismo perfil de AGCC de
  contenido: SAMEA112904748/SAMEA112905038, SAMEA112904768/SAMEA112905318,
  SAMEA112905210/SAMEA112905365 y SAMEA112905116/SAMEA112905124 (el primero trae los valores
  del segundo redondeados). Dos pares unen corrales y dietas distintos. Investigación pide
  excluir los 8 de todo análisis de AGCC hasta que el portal lo aclare (Tabla 6, N° 3); solo
  SAMEA112905124 tiene metagenoma. La exclusión se aplica con la cohorte supervisada (#138).
- **Solo marcadores individuales.** Las fichas de animal traen marcadores de tipo `PEN`
  (promedios del corral: FCR, ganancia diaria, peso medio). No se exportan como fenotipo del
  animal; `pen_code` queda en `metadata.tsv` para agrupar y para evitar fugas entre
  particiones (Esquema General, §6). Investigación confirmó que no se usan en F4 y que nunca
  serán un fenotipo del animal (V-04): el total de AGCC se agrupa por corral × día de
  sacrificio (ICC = 0,53), así que toda variable de corral está confundida con la ocasión de
  muestreo.
- **Solo lecturas, no ensamblajes.** Las tablas de MGnify mezclan análisis de lecturas
  (`ERR…`) y de ensamblajes (`ERZ…`), cuyos conteos no son comparables. Se usan solo las
  lecturas. Un animal con varias corridas suma sus conteos (resecuenciación de la misma
  muestra). Investigación lo confirmó para F4 (V-05); antes de reabrirlo pide contar cuántos
  animales con AGCC agregarían los ensamblajes (#141).
- **Abundancia relativa, no biomasa.** Los conteos SSU de shotgun son composicionales.
- **Profundidad muy variable.** La mediana es ~24 000 lecturas SSU por animal, pero 5 animales
  tienen menos de 100 y 15 menos de 5000. Investigación fijó un umbral provisional de
  **≥ 1000 lecturas SSU** por animal, con sensibilidad a 5000 (S-05). De los 59 animales con
  metagenoma y AGCC, quedan bajo el umbral SAMEA112905331 (1 lectura) y SAMEA112905107 (84);
  ninguno es SAMEA112905124. El umbral se aplica con la cohorte supervisada (#138), no en
  `AbundancePreprocessor`.
- **Rangos mezclados.** MGnify asigna cada lectura al rango más profundo que puede resolver:
  hay 472 linajes a nivel de especie, 467 de género, 171 de familia y el resto en rangos
  superiores. `AbundanceLoader` usa el rango más profundo con nombre como `taxon_id`, de modo
  que los nodos `taxon` quedan en niveles distintos. Elegir un rango de trabajo (por ejemplo,
  agregar a género) es una decisión pendiente.
- **Dos colisiones de nombre.** En SILVA, `p__Actinobacteria` y `c__Actinobacteria` (y lo
  mismo con Deferribacteres) comparten nombre; el loader los reduce al mismo `taxon_id` y suma
  sus conteos, con una advertencia en `payload.extra["errors"]`.
- **Un punto temporal por animal.** Cada animal se muestrea una vez (día 7, 21 o 35, en
  `sampling_day`); los tres tipos de dato de un animal comparten ese momento.
- **Lactato D y L se mantienen separados** (`d-lactate`, `l-lactate`); no se suman en
  `lactate`.
- **Composición de las dietas.** La API solo nombra el tratamiento. Según el
  [resumen de diseño experimental](https://www.holofooddata.org/analysis-summary/holofood-chicken-experimental-design)
  del portal, el ensayo es de bloques completos aleatorizados (factorial línea × sexo × dieta,
  tratamiento asignado por corral) y las dietas son:
  - `CC` **Control**: dieta basal de trigo y soya, sin enzimas, antibióticos ni coccidiostatos;
  - `CO` **Probiótico**: *Bacillus subtilis* DSM 32324 y DSM 32325 y *B. amyloliquefaciens*
    DSM 25840, 0,75 g/kg de alimento;
  - `CE` **Fitobiótico**, aunque la API lo nombra "Prebiotic": extracto de uva blanca
    (procianidinas y polifenoles), 0,75 g/kg.

  La composición de la dieta basal hay que tomarla de la publicación para construir nodos de
  sustrato.
- **Escenario.** Cada animal es una observación (`scenario_id = "observed"`, reglas 1.2.0), no
  un escenario basal o intervenido: un animal Control es un brazo control real, no el
  contrafactual de un animal tratado. Ver la
  [propuesta de evidencia y escenario](../graph/evidence-and-scenario-proposal.md).

## Ensamblajes `ERZ…`: cuántos animales sumarían (#141)

Antes de reabrir la decisión de usar solo lecturas (V-05, S-06), Investigación pidió contar
cuántos animales **con AGCC de contenido** sumarían los ensamblajes. Con
`python scripts/count_holofood_assemblies.py` (detalle en
[`reports/holofood/assemblies.md`](../../reports/holofood/assemblies.md)), sobre la descarga
del 2026-10-15:

| Paso | Animales |
|---|---:|
| Con ensamblaje de metagenoma de contenido cecal en las tablas SSU de MGnify | 229 |
| − Ya tienen perfil de lecturas | 71 |
| = Solo con ensamblaje | 158 |
| … con los tres AGCC de contenido, sin perfiles repetidos | **107** |
| … cuyo perfil de ensamblaje alcanza 1000 conteos SSU | 0 |
| … con corridas de lectura crudas en ENA que MGnify no perfiló | 107 |

- **Los perfiles de ensamblaje no sirven tal como están.** Tienen una mediana de 117 conteos
  SSU (máximo 252), porque cuentan asignaciones sobre contigs, no lecturas. Ninguno alcanza el
  umbral de la cohorte, y mezclarlos con los perfiles de lecturas rompería la unidad de las
  abundancias.
- **Las lecturas crudas sí existen.** Los 107 animales tienen corridas `ERR…` en ENA (estudio
  MGYS00006062, PRJEB41323) que MGnify solo analizó como ensamblaje. Perfilarlas, por ejemplo
  con Kraken2/Bracken contra el catálogo MGnify chicken-gut v1.0.1 (ruta que recomienda
  Investigación en V-05), llevaría la cohorte de 56 hasta 163 animales.
- **Los 107 están balanceados:**

  | | `CC` / `CO` / `CE` |
  |---|---|
  | Animales | 35 / 35 / 37 |
  | Corrales | 20 / 21 / 21 |

  Por día: 27, 40 y 40 (días 7, 21 y 35). Por ensayo: 31, 33 y 43 (`CA`, `CB`, `CC`).
  Corregirían en buena parte el desbalance 34/15/7 de la cohorte actual (limitación L1).

Investigación decidió evaluarlo con un piloto fuera de la ruta crítica de F4 (R-03, 25-10-2026):
perfilar unos 5 animales, incluidos algunos de la cohorte para comparar con su perfil MGnify, y
registrar horas y disco antes de decidir si se escala. Si se escala, se perfilan los 163 animales
con el mismo método. Hacerlo implica descargar y procesar los FASTQ localmente, sin servicios
pagos.

## Uso en código

```python
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline

sources = load_sources("configs/sources.json")

# Instancias y features de taxón (A34-4), una instancia por animal.
result = DataPipeline(sources).run(["D1_holofood"], output_dir="data/processed/D1_holofood")

# AGCC y metadatos: todavía no los integra el pipeline (ver "Siguientes pasos").
scfa = MetaboliteLoader(sources["D1_holofood_scfa_content"]).load()
meta = MetadataLoader(sources["D1_holofood_metadata"]).load()
```

`DataPipeline` asigna loaders por formato y registra `AbundanceLoader` para `tsv`; las fuentes
de AGCC y metadatos se cargan con su loader explícito.

## Partición train/val/test (A40-1)

Para comparar baselines y modelos GNN sobre una misma base metodológica sin fuga de información
(*data leakage*), la partición oficial está versionada en `configs/splits/d1_holofood.json` y se
expone mediante `get_split()`:

```python
from nutrigraphdt.data.split import get_split

# Partición única, versionada e idéntica entre ejecuciones
split = get_split()  # o get_split("D1_holofood")

train_ids, val_ids, test_ids = split
print(f"Train: {len(split.train)}, Val: {len(split.val)}, Test: {len(split.test)}")
```

- **Agrupamiento por corral (`pen_code`):** el tratamiento fue asignado al azar por corral, de modo
  que separar animales de un mismo corral entre train y test filtraría efectos de cohabitación.
  Todos los animales de un corral quedan asignados al mismo subconjunto.
- **Estratificación:** por tratamiento dietario (`diet_treatment_code`), tolerando estratos con
  pocos corrales.
- **Semilla fija:** `seed = 42`.
- **Ratios:** 60 % train, 20 % val, 20 % test.

## Cohorte supervisada (#138)

La partición reparte los 530 animales con metadatos, pero solo una parte tiene metagenoma y los
tres AGCC principales. Los baselines (`compare_baselines.py --dataset d1`) y la GNN
(`train_gnn.py` y `tune_gnn.py --dataset d1`) entrenan y evalúan solo con la **cohorte
supervisada**, que fija `configs/cohorts/d1_holofood.json` según la respuesta de Investigación
a la solicitud de revisión v1.1 (D-03, S-05 y Tabla 6):

1. **Metagenoma y AGCC:** columna en `abundance_ssu_caecum.tsv` y acetato, propionato y
   n-butirato medidos en `scfa_caecum_content.tsv`.
2. **Exclusiones:** los 8 animales con perfiles de AGCC repetidos (4 pares), cada uno con su
   motivo en la configuración. Solo SAMEA112905124 (corral CC03) tiene metagenoma; los otros 7
   ya quedaban fuera en el paso 1.
3. **Profundidad:** al menos `min_ssu_reads` lecturas SSU (1000), contadas sobre los conteos
   crudos de la tabla de abundancias.

Conteos sobre la descarga del 2026-10-15 (`python scripts/report_cohort.py`, detalle en
[`reports/cohort/d1_holofood.md`](../../reports/cohort/d1_holofood.md)):

| Paso | Animales | `CC` / `CO` / `CE` | Corrales por tratamiento |
|---|---:|---|---|
| Metagenoma + 3 AGCC de contenido | 59 | 37 / 15 / 7 | 16 / 10 / 6 |
| − SAMEA112905124 (perfil repetido) | 58 | 36 / 15 / 7 | 16 / 10 / 6 |
| − < 1000 lecturas (SAMEA112905331: 1; SAMEA112905107: 84) | **56** | 34 / 15 / 7 | 15 / 10 / 6 |
| Sensibilidad: ≥ 5000 lecturas | 50 | 30 / 14 / 6 | 15 / 9 / 5 |

```python
from nutrigraphdt.data.cohort import load_cohort
from nutrigraphdt.data.config import load_sources

cohort = load_cohort(load_sources("configs/sources.json"))
len(cohort)  # 56
cohort.summary()  # versión, umbral y animales quitados en cada paso
load_cohort(load_sources("configs/sources.json"), min_ssu_reads=5000)  # sensibilidad
```

- Cada `run.json` registra la cohorte usada: `source.cohort` en la GNN y `cohort` en los
  baselines. `subsets.<subconjunto>.outside_cohort` cuenta los grafos con AGCC que quedaron
  fuera por no pertenecer a ella.
- La exclusión de los perfiles repetidos es provisional: Investigación avisará al portal. Si el
  portal los corrige, la lista cambia y la configuración sube de versión.
- Los reportes de A45-2 a A45-6 se generaron antes de la cohorte (59 animales con los tres
  AGCC). Se rehacen con la validación cruzada por corral (#139, #140 y #142).

## Siguientes pasos para Desarrollo


1. **Grafos reales (A39, hecho).** `attach_sample_context` lleva AGCC y metadatos a las tablas,
   y `build_hetero_graph` construye un `HeteroData` por animal; ver
   [`graph-builder.md`](../graph/graph-builder.md) y el
   [reporte de validación](../graph/real-graph-validation-report.md). Los 185 grafos cumplen
   los contratos (#62 a #66), pero **no todos sirven para entrenar**: solo 61 tienen nodos de
   metabolito, y el conjunto supervisado es la cohorte de 56 animales (#138). Desde las reglas
   de integridad 1.3.0 (#137), los grafos sin metabolito no se entregan a ningún modelo en F4
   (D-08, alcance confirmado en R-02 de la respuesta de Investigación del 25-10-2026): quedan
   construidos y validados, y la decisión se reabre si se define una tarea sin objetivo.
2. **Preprocesamiento.** El umbral de profundidad ya se aplica con la cohorte (#138). Quedan
   el rango taxonómico de trabajo (género, con nombres puenteados de SILVA 132 a GTDB r207;
   D-04) y las dos colisiones de nombre: Investigación pide no sumarlas e incluir el prefijo
   de rango en `taxon_id` (S-04). Ambos cambios se ordenan en el contrato v2 (#136).
3. **Investigación.** Respondió el 16-10-2026
   ([respuesta a la solicitud de revisión v1.1](<../research/Respuesta de Investigación a la Solicitud de revisión v1.1.md>)):
   excluye las muestras `caecum tissue` y los marcadores de corral de F4, fija la partición
   por corral con validación cruzada (#139) y cambia el objetivo a la composición de los AGCC
   (contrato v2, #136). El 25-10-2026 respondió la respuesta de Desarrollo
   ([respuesta a la respuesta de Desarrollo](<../research/Respuesta de Investigación a la Respuesta de Desarrollo.md>)):
   aprueba el contrato v2 con tres cambios previos (#186), confirma la cohorte de 56 animales
   (R-04) y acepta evaluar con un piloto el perfilado de los 107 animales con lecturas crudas,
   fuera de la ruta crítica de F4 (R-03, #141). Siguen pendientes la publicación del ensayo y
   la dieta basal
   (S-01, S-02), la tabla de equivalencias SILVA → GTDB (S-04), las ecuaciones bioquímicas
   (D-06) y la evaluación de D4 MTBLS560 (S-06). El desbalance 34/15/7 de la cohorte obliga a
   declarar exploratoria toda comparación entre tratamientos (limitación L1).

## Licencia y cita

Datos públicos de EMBL-EBI (HoloFood Data Portal, MGnify, ENA), sujetos a sus
[términos de uso](https://www.ebi.ac.uk/about/terms-of-use). Citar:

> Rogers, A. B., Kale, V., Baldi, G., et al. (2025). HoloFood Data Portal: Holo-omic datasets
> for analysing host–microbiota interactions in animal production. *Database, 2025*, baae112.
> https://doi.org/10.1093/database/baae112
