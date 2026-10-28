# Cohorte supervisada de D1_holofood (versión 1.0.0)

Generado con `python scripts/report_cohort.py`. Criterios en `configs/cohorts/d1_holofood.json`; referencia: Respuesta de la Célula de Investigación a la Solicitud de revisión v1.1 (v1.0, 16-10-2026): D-03, S-05 y Tabla 6, N° 3.

AGCC objetivo: `acetate`, `propionate`, `butyrate`.

Descarga: `2026-10-15T05:02:32+00:00` (`manifest.json`).

## Umbral de 1000 lecturas SSU (oficial): 56 animales

| Paso | Animales | CC / CO / CE | Corrales por tratamiento | Quitados |
|---|---:|---|---|---|
| Metagenoma y los AGCC objetivo medidos en el contenido cecal | 59 | 37 / 15 / 7 | 16 / 10 / 6 | — |
| Sin los animales excluidos por configuración (perfiles repetidos) | 58 | 36 / 15 / 7 | 16 / 10 / 6 | SAMEA112905124 |
| Con al menos 1000 lecturas SSU | 56 | 34 / 15 / 7 | 15 / 10 / 6 | SAMEA112905107, SAMEA112905331 |

## Umbral de 5000 lecturas SSU (sensibilidad): 50 animales

| Paso | Animales | CC / CO / CE | Corrales por tratamiento | Quitados |
|---|---:|---|---|---|
| Metagenoma y los AGCC objetivo medidos en el contenido cecal | 59 | 37 / 15 / 7 | 16 / 10 / 6 | — |
| Sin los animales excluidos por configuración (perfiles repetidos) | 58 | 36 / 15 / 7 | 16 / 10 / 6 | SAMEA112905124 |
| Con al menos 5000 lecturas SSU | 50 | 30 / 14 / 6 | 15 / 9 / 5 | SAMEA112904791, SAMEA112904845, SAMEA112904869, SAMEA112905068, SAMEA112905076, SAMEA112905107, SAMEA112905149, SAMEA112905331 |

Tratamientos: `CC` Control, `CO` Probiótico, `CE` Fitobiótico.

## Exclusiones configuradas

| `sample_id` | Motivo | Nota |
|---|---|---|
| SAMEA112904748 | `duplicated_scfa_profile` | Perfil de AGCC idéntico al de SAMEA112905038. |
| SAMEA112905038 | `duplicated_scfa_profile` | Perfil de AGCC idéntico al de SAMEA112904748. |
| SAMEA112904768 | `duplicated_scfa_profile` | Perfil de AGCC idéntico al de SAMEA112905318. |
| SAMEA112905318 | `duplicated_scfa_profile` | Perfil de AGCC idéntico al de SAMEA112904768. |
| SAMEA112905116 | `duplicated_scfa_profile` | Trae los valores de SAMEA112905124 redondeados. |
| SAMEA112905124 | `duplicated_scfa_profile` | Perfil repetido en SAMEA112905116; único de los ocho con metagenoma (corral CC03). |
| SAMEA112905210 | `duplicated_scfa_profile` | Perfil de AGCC idéntico al de SAMEA112905365. |
| SAMEA112905365 | `duplicated_scfa_profile` | Perfil de AGCC idéntico al de SAMEA112905210. |
