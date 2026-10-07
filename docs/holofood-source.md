# Fuente real D1: HoloFood (pollo)

Primera fuente real integrada al módulo de datos. Es el conjunto núcleo que recomienda la
[revisión de repositorios y datasets](<Repositorios y Datasets — PIA Microbioma Digital.md>)
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
| `scfa_caecum_content.tsv` | `D1_holofood_scfa_content` | `MetaboliteLoader` | Acetato, propionato, n- e i-butirato, n- e i-valerato, D- y L-lactato del **contenido cecal**, en µmol/g de digesta (el loader los lleva a `mmol_kg`, factor 1). |
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
| Linajes SSU distintos | 1317 |

Diseño experimental (metadatos de los 530 animales): tres ensayos (`CA`, `CB`, `CC`), tres
tratamientos con el mismo código en todos los ensayos (`CC` Control, `CO` Probiótico,
`CE` Prebiótico), dos razas (Ross, Cobb), ambos sexos y muestreo en los días 7, 21 y 35. No hay
campos vacíos.

**El subconjunto emparejado está desbalanceado.** De los 59 animales con metagenoma y AGCC de
contenido, la mayoría son Control (37); Probiótico tiene 15 y Prebiótico 7, repartidos en
ensayos y días distintos. Alcanza para construir y validar grafos reales (A39), pero no para
estimar efectos de la dieta: cualquier comparación entre tratamientos con este subconjunto
debe declararse exploratoria.

## Decisiones y cautelas

- **Matrices separadas.** El portal declara `Body site` por muestra de AGCC: `caecum content`
  o `caecum tissue`. Se leen de la ficha, no del título, y cada matriz va a su tabla. El
  metagenoma es de contenido cecal, así que el emparejamiento directo es con
  `scfa_caecum_content.tsv`. Que las muestras rotuladas `tissue` informen la unidad
  "µmol/g digesta" es una inconsistencia del portal que debe revisar Investigación antes de
  usarlas como objetivo (Esquema General, §3: no equiparar matrices).
- **Solo marcadores individuales.** Las fichas de animal traen marcadores de tipo `PEN`
  (promedios del corral: FCR, ganancia diaria, peso medio). No se exportan como fenotipo del
  animal; `pen_code` queda en `metadata.tsv` para agrupar y para evitar fugas entre
  particiones (Esquema General, §6). Incorporarlos es una decisión pendiente.
- **Solo lecturas, no ensamblajes.** Las tablas de MGnify mezclan análisis de lecturas
  (`ERR…`) y de ensamblajes (`ERZ…`), cuyos conteos no son comparables. Se usan solo las
  lecturas. Un animal con varias corridas suma sus conteos (resecuenciación de la misma
  muestra).
- **Abundancia relativa, no biomasa.** Los conteos SSU de shotgun son composicionales.
- **Profundidad muy variable.** La mediana es ~24 000 lecturas SSU por animal, pero 5 animales
  tienen menos de 100 y 15 menos de 5000. Hace falta un umbral de profundidad mínima antes de
  normalizar; hoy `AbundancePreprocessor` no lo aplica.
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
- **Composición de las dietas.** La API solo nombra el tratamiento (Control, Probiótico,
  Prebiótico). La dieta basal, la cepa probiótica y el prebiótico hay que tomarlos de la
  publicación del ensayo para construir nodos de dieta, aditivo y sustrato.

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

## Siguientes pasos para Desarrollo

1. **Grafos reales (A39, hecho).** `attach_sample_context` lleva AGCC y metadatos a las tablas,
   y `build_hetero_graph` construye un `HeteroData` por animal; ver
   [`graph-builder.md`](graph-builder.md) y el
   [reporte de validación](real-graph-validation-report.md). La entrega a un modelo espera
   #62 a #64.
2. **Contratos y rango taxonómico.** #65 y #66.
3. **Preprocesamiento.** Umbral de profundidad mínima, rango taxonómico de trabajo y
   desambiguación de las dos colisiones de nombre en `AbundanceLoader`.
4. **Investigación.** Cerrar: uso de las muestras `caecum tissue`, inclusión de marcadores de
   corral, composición de cada tratamiento, criterio de partición (por corral o ensayo) y si el
   desbalance del subconjunto emparejado obliga a sumar otra fuente (por ejemplo, los
   ensamblajes `ERZ…` excluidos aquí o D4 MTBLS560).

## Licencia y cita

Datos públicos de EMBL-EBI (HoloFood Data Portal, MGnify, ENA), sujetos a sus
[términos de uso](https://www.ebi.ac.uk/about/terms-of-use). Citar:

> Rogers, A. B., Kale, V., Baldi, G., et al. (2025). HoloFood Data Portal: Holo-omic datasets
> for analysing host–microbiota interactions in animal production. *Database, 2025*, baae112.
> https://doi.org/10.1093/database/baae112
