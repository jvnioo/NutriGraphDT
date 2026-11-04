# Decisión: relaciones taxón → función para aristas `has_capacity` en D1

**Emite:** Investigación
**Fecha:** 2026-11-03
**Issues:** R-11, #175 (bloqueante), #173, #174, #185
**Evidencia:**
- `configs/taxonomy/s04_silva_gtdb_minimal.tsv`
- `docs/research/compare_silva_mgnify_genera.py`
- `docs/research/silva_mgnify_crosscheck.tsv`

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

De los **13 géneros `1:1`** en la tabla mínima actual:

- **10 presentes** en `chicken-gut v1.0.1` → **podrán generar aristas**:
  `Alistipes`, `Barnesiella`, `Bifidobacterium`, `Collinsella`, `Faecalibacterium`,
  `Mucispirillum`, `Parabacteroides`, `Roseburia`, `Akkermansia`, `Prevotella`.
- **3 ausentes** → **no generan aristas**:
  `Eggerthella`, `Enterorhabdus`, `Ruminococcus`.

## 4. Supuestos y limitaciones

1. **Cobertura parcial:** la tabla actual es **mínima** (20 filas). Los 1.317
   taxones de D1 no están cubiertos; la ampliación depende del piloto de R-03.
2. **`Ruminococcus`:** en GTDB r207 el género fue reclasificado en
   `Ruminococcus`, `Ruminococcus_A`, ..., `Ruminococcus_E`. El `no` refleja
   la ausencia del nombre exacto, no necesariamente ausencia biológica en el
   intestino de pollo. Se anota como limitación conocida; no se resuelve
   manualmente porque violaría la regla de fuente funcional única.
3. **`1:N` documentados pero excluidos:** `Bacteroides` y `Lactobacillus`
   mapean a múltiples géneros GTDB; no generan arista.
4. **`sin par` documentados pero excluidos:** `Subdoligranulum`, `Oscillibacter`,
   `Tyzzerella`, `Ruminiclostridium`, `Phascolarctobacterium`. Curación pendiente.
5. **Reproducibilidad:** el script pagina por número de página (no por `next`),
   con `page_size=100`, deduplicando por `id` de genoma. Total: 14 páginas,
   1.322 genomas únicos.
6. **Sin servicios de pago:** toda la evidencia se obtuvo vía API pública de
   MGnify y descargas abiertas de SILVA/GTDB.

## 5. Consecuencia para Desarrollo

- **Desarrollo puede empezar a crear aristas `has_capacity`** para los 10
  géneros con `present_in_chicken_gut_v1_0_1 = yes` en
  `silva_mgnify_crosscheck.tsv`.
- **No se crearán aristas** para los 3 géneros con `no`, ni para los `1:N`,
  ni para los `sin par`.
- Este documento desbloquea el issue #175.
