# Decisión: relaciones taxón → función para aristas `has_capacity` en D1

**Emite:** Investigación. **Pendiente de emisión por el sublíder** (#236).
**Fecha:** 2026-11-03; corregido en la revisión de Desarrollo el 2026-11-04 (sección 6).
**Issues:** R-11, #175 (bloqueante), #173, #174, #185
**Evidencia:**
- `configs/taxonomy/s04_silva_gtdb_minimal.tsv`
- `docs/research/compare_silva_mgnify_genera.py`
- `docs/research/silva_mgnify_crosscheck.tsv`
- `docs/research/verify_s04_gtdb_r207.py` y `docs/research/s04_gtdb_r207_evidence.tsv`

## 1. Regla aprobada

Se crearán aristas `has_capacity` **exclusivamente** para taxones con
`relationship = 1:1` en la tabla SILVA 132 → GTDB r207, y solo si el género
GTDB aparece en el catálogo `mgnify-chicken-gut@v1.0.1`. La fuente funcional
es única: el catálogo MGnify chicken-gut v1.0.1. No se acepta curación
bibliográfica manual para `has_capacity`.

## 2. Tratamiento de casos

| Caso | ¿Genera arista `has_capacity`? | Justificación |
|---|---|---|
| `1:1` + presente en catálogo | **Sí** | Enlace unívoco y funciones disponibles en la fuente aprobada |
| `1:1` + ausente en catálogo | **No** | No hay funciones que asignar desde la fuente aprobada |
| `1:N` | **No** | Un género SILVA mapea a varios GTDB; anotación no unívoca |
| `sin par` | **No** | Sin equivalencia unívoca en GTDB r207; curación pendiente |

## 3. Resultado del cruce

De los **8 géneros `1:1`** de la tabla tras la revisión de la sección 6:

- **7 presentes** en `chicken-gut v1.0.1` → **podrán generar aristas**:
  `Bifidobacterium`, `Collinsella`, `Faecalibacterium`, `Mucispirillum`, `Parabacteroides`,
  `Akkermansia`, `Prevotella`.
- **1 ausente** → **no genera aristas**: `Eggerthella`.

Estos 7 géneros cubren el 31,8 % de las lecturas asignadas a género (14,2 % del total, en los 185
animales con metagenoma). *Faecalibacterium* aporta 28,0 de esos 31,8 puntos, así que la ruta
taxón → función de D1 dependerá casi por completo de ese género.

## 4. Supuestos y limitaciones

1. **Cobertura parcial:** la tabla actual es **mínima** (20 filas). Los 1.317
   taxones de D1 no están cubiertos; la ampliación depende del piloto de R-03.
2. **`Ruminococcus`:** en GTDB r207 el género está dividido en `Ruminococcus`, `Ruminococcus_B`,
   ..., `Ruminococcus_G`, así que no es `1:1`: la tabla lo pasa a `1:N` (sección 6). No se resuelve
   manualmente porque violaría la regla de fuente funcional única.
3. **`1:N` documentados pero excluidos:** `Bacteroides`, `Lactobacillus`, `Alistipes`,
   `Barnesiella`, `Roseburia` y `Ruminococcus` mapean a múltiples géneros GTDB; no generan arista.
4. **`sin par` documentados pero excluidos:** `Subdoligranulum`, `Oscillibacter`,
   `Tyzzerella`, `Ruminiclostridium`, `Phascolarctobacterium`, `Enterorhabdus`. Curación pendiente.
5. **Reproducibilidad:** el script pagina por número de página (no por `next`),
   con `page_size=100`, deduplicando por `id` de genoma. Total: 14 páginas,
   1.322 genomas únicos.
6. **Sin servicios de pago:** toda la evidencia se obtuvo vía API pública de
   MGnify y los metadatos abiertos de GTDB r207.

## 5. Consecuencia para Desarrollo

- **Desarrollo puede crear aristas `has_capacity`** para los 7 géneros con
  `present_in_chicken_gut_v1_0_1 = yes` en `silva_mgnify_crosscheck.tsv`. Investigación ya los había
  aprobado entre los 10 originales.
- **No se crearán aristas** para `Eggerthella`, ni para los `1:N`, ni para los `sin par`.
- Este documento aporta a #175 la regla y esos 7 géneros. #175 sigue siendo el trabajo de
  implementación; la ampliación y la confirmación de la tabla siguen en #236.

## 6. Revisión de Desarrollo (2026-11-04)

La versión original aprobaba 10 géneros con un cruce por **nombre exacto** contra el catálogo, que
comprueba la presencia del género pero no que el enlace sea `1:1`. Desarrollo contrastó la tabla con
la columna `ssu_silva_taxonomy` de GTDB r207, la fuente que propuso la respuesta de Investigación
del 16-10-2026 (`verify_s04_gtdb_r207.py`, salida en `s04_gtdb_r207_evidence.tsv`). La tabla se
corrigió solo en el sentido conservador: **ninguna corrección crea aristas, solo las retira.**

| Género SILVA | Antes | Ahora | Evidencia en GTDB r207 (genomas con esa etiqueta SILVA) | En el catálogo |
|---|---|---|---|---|
| `Alistipes` | `1:1`, sí | `1:N` | 189: `Alistipes` 145, `Alistipes_A` 19, `Tidjanibacter` 9 | `Alistipes` 19, `Alistipes_A` 4 |
| `Barnesiella` | `1:1`, sí | `1:N` | 22: `Barnesiella` 15, `CABJAA01` 2 | `Barnesiella` 6, `Barnesiella_A` 2 |
| `Roseburia` | `1:1`, sí | `1:N` | 130: `Roseburia` 41, `14-2` 23, `RUG115` 21, `Agathobacter` 18 | `Roseburia` 1 |
| `Ruminococcus` | `1:1`, no | `1:N` | 293: `Ruminococcus_E` 124, `Ruminococcus_D` 63, `Ruminococcus` 36 | `Ruminococcus_B` 1, `_D` 1, `_G` 2 |
| `Enterorhabdus` | `1:1`, no | `sin par` | 31: `Adlercreutzia` 13, `Ellagibacter` 7. `g__Enterorhabdus` no existe en GTDB r207 | Ninguno |

**Límites de esta evidencia:**

- `ssu_silva_taxonomy` no está en SILVA 132: distingue géneros como `Limosilactobacillus`, que SILVA
  132 no tiene. Es indicativa para la curación, no un mapeo SILVA 132 directo. Por eso no se usa
  para declarar `1:1` nuevos.
- Ninguna etiqueta es perfectamente unívoca; hay asignaciones aisladas en casi todos los géneros
  (por ejemplo, `Faecalibacterium` 125 de 137). No se fijó un umbral: los 7 géneros que siguen en
  `1:1` son los que esta evidencia no contradice.

**Pendiente de Investigación (#236):**

1. Confirmar o revertir, con fuente, las cinco correcciones de la tabla.
2. Decidir el umbral para declarar `1:1`.
3. Completar la tabla: 20 de 499 géneros, sin fuente por fila y sin *Butyricicoccus*,
   *Eisenbergiella* ni *Blautia*.
4. Emitir este documento por el sublíder.
