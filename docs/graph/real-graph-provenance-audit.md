# Auditoría de procedencia del reporte de grafos reales (#174)

- **Fecha:** 07-11-2026.
- **Alcance:** [`real-graph-validation-report.md`](real-graph-validation-report.md), reglas `1.6.0`,
  descarga de D1 del 15-10-2026.
- **Versión revisada:** `main`, commit `608c1f8`, con los grafos de `scripts/build_graph.py`.
- **Realizada por:** Célula de Desarrollo, con la lista de verificación R-12 del encargo de
  Investigación para #174.

> **Esto no es una revisión de Investigación.** Investigación recibió la solicitud el 07-11-2026 y no
> había respondido al cierre. El sublíder de Desarrollo decidió cerrar #174 sin esa respuesta para no
> frenar el proyecto. Esta auditoría contrasta el reporte con los datos y con las decisiones que
> Investigación ya emitió por escrito; no agrega ni supone una aprobación suya. Si Investigación
> objeta algo, se reabre #174 o se abre una Issue.

## 1. Lista de verificación R-12

| Punto | Comprobación | Resultado |
|---|---|---|
| **Fuentes y versiones** | SHA-256 de los 5 archivos de D1 contra `manifest.json`: coinciden. Descarga `2026-10-15T05:02:32+00:00`. Reglas `1.6.0`, `schema_version` `1.0.0`. | Aceptada |
| **AGCC y unidades** | Contenido cecal, µmol/g de digesta fresca, llevado a `mmol_kg` con factor 1 ([`holofood-source.md`](../data-sources/holofood-source.md)). | Aceptada |
| **Cohorte 59 → 58** | Se quita `SAMEA112905124` por perfil repetido ([`reports/cohort/d1_holofood.md`](../../reports/cohort/d1_holofood.md)). | Limitación aceptada: la exclusión es provisional hasta que el portal lo corrija. |
| **Cohorte 58 → 56** | Se quitan `SAMEA112905107` y `SAMEA112905331` por el umbral de 1000 lecturas SSU (R-04). | Aceptada |
| **Normalización** | La abundancia relativa suma 1 en cada grafo después de agregar. | Aceptada |
| **Prefijo de rango, género y residuales** | 498 géneros y 378 residuales por grafo; 44,66 % de las lecturas a género, frente al 44,7 % de la decisión de #236. | Aceptada |
| **Aplicación de S-04** | Las 62 aristas `has_capacity` de los grafos son exactamente las de `has_capacity_d1.tsv`. Ninguna de las 11 470 parte de un taxón sin enlace `1:1` ni de un residual. Las aristas no dependen de coincidencias de nombre: `g__Bifidobacterium` (`1:N`) no recibe y `g__Tyzzerella` recibe por `g__Anaerotignum`. | Aceptada |
| **Evidencia** | Las 11 883 aristas funcionales son `annotated`; `has_capacity` lleva `database_annotation` y `mgnify-chicken-gut@v1.0.1`, y `produces`, `KEGG@120.0`. Tabla S-04 y `has_capacity_d1.tsv` reproducidas idénticas desde las fuentes públicas. | Aceptada |
| **Hallazgos por regla** | 124 `ERROR` NOD-12 (animales sin AGCC, R-02); NOD-12 advertencia 185; NOD-08 1110; CON-01 494; CON-03 309; CON-04 2. Todos esperables y explicados en el reporte, igual que cada diferencia con la ejecución anterior. | Aceptada |
| **Validez biológica** | El reporte y `report.json` declaran que la validación es estructural y que capacidad anotada no es actividad. No hay ninguna afirmación biológica más allá de eso. | Aceptada |

## 2. Decisiones de Desarrollo contrastadas con lo escrito

Son las cinco que se plantearon a Investigación en #174.

| Decisión | Respaldo escrito | Resultado |
|---|---|---|
| Las especies sin género van al residual de su rango, y se eliminan 30 géneros falsos. | Contrato v2 §6 y respuesta del 25-10-2026, R-01, pregunta 4: «toda lectura que no alcanza género se agrega en un nodo residual del rango más profundo que alcance». El resultado coincide con los 498 géneros de #236. | Aceptada |
| Los nodos conservan el nombre SILVA, y el género GTDB solo consulta el catálogo. | Decisión de #236: sección 6, punto 5 («desde el lado de SILVA, que es el del grafo»), y sección 7. | Aceptada |
| `function_type = kegg_ortholog` y `annotation_source = eggNOG-mapper 2.1.3 (…)`. | Decisión de #257, sección 8: los fija Desarrollo, y son los valores que sugiere. | Aceptada |
| La fracción de especies con el KO no entra al grafo. | Decisión de #257, sección 4: Desarrollo decide si entra o se informa. Queda en `has_capacity_d1.tsv`. | Aceptada |
| `taxon_links` declara los 118 enlaces `1:1` de S-04, no solo los 46 del catálogo. | **Sin pronunciamiento de Investigación.** EDG-04 pregunta si el enlace es `1:1`, y la tabla de capacidad limita las aristas a los géneros del catálogo, así que no cambia ninguna arista. | Limitación aceptada |

## 3. Limitaciones que siguen vigentes

Están declaradas en las decisiones de Investigación y en el reporte; esta auditoría no las resuelve.

- Solo 38 de los 876 taxones tienen aristas funcionales. La ruta llega al 36,1 % de las lecturas a género
  para acetato, al 35,8 % para butirato y al 2,1 % para propionato (#256, sección 5).
- El 55,3 % de las lecturas no llega a género y queda sin camino funcional.
- `dieta → sustrato → taxón` es una limitación declarada (#258).
- *but* no tiene KO, y eggNOG no asigna *mmdA* a *Parabacteroides* ni a *Prevotella* (#257, sección 7).
- La exclusión por perfiles repetidos es provisional.

No hay observaciones abiertas que exijan cambiar el reporte.
