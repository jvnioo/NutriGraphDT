# Animales que sumarían los ensamblajes de HoloFood

Generado con `python scripts/count_holofood_assemblies.py` (#141). Descarga: `2026-10-15T05:02:32+00:00`. Exclusiones: `configs/cohorts/d1_holofood.json` (versión 1.0.0).

| Paso | Animales |
|---|---:|
| Con ensamblaje de metagenoma de contenido cecal en las tablas SSU de MGnify (525 columnas `ERZ`) | 229 |
| − Ya tienen perfil de lecturas (`ERR`) | 71 |
| = Solo con ensamblaje | 158 |
| … con los tres AGCC de contenido | 113 |
| … sin perfiles de AGCC repetidos: **sumarían** | **107** |
| … cuyo perfil de ensamblaje alcanza 1000 conteos SSU | 0 |
| … con corridas de lectura crudas en ENA sin perfil en MGnify | 107 |

Conteos SSU de sus perfiles de ensamblaje: mediana 117.0, máximo 252.0. Son asignaciones sobre contigs, no lecturas: no se comparan con el umbral de lecturas de la cohorte.

| Desglose de los que sumarían | CC / CO / CE |
|---|---|
| Animales por tratamiento | 35 / 35 / 37 |
| Corrales por tratamiento | 20 / 21 / 21 |

Por día de muestreo: día 7: 27, día 21: 40, día 35: 40. Por ensayo: `CA`: 31, `CB`: 33, `CC`: 43.

Tratamientos: `CC` Control, `CO` Probiótico, `CE` Fitobiótico.
