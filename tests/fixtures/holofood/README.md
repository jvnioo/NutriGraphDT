# Fixture HoloFood (D1)

Subconjunto **real** de la fuente D1, extraído de la salida de `scripts/fetch_holofood.py`
(descarga del 2026-10-07, MGnify pipeline 5.0). Contiene seis animales que tienen metagenoma
de contenido cecal con al menos 5000 lecturas SSU y AGCC completos de contenido cecal, dos por
tratamiento (Control, Probiótico, Prebiótico).

| Archivo | Contenido |
|---|---|
| `abundance_ssu_caecum.tsv` | Conteos SSU de los seis animales; solo los linajes con algún conteo no nulo. |
| `scfa_caecum_content.tsv` | AGCC del contenido cecal, en µmol/g de digesta. |
| `metadata.tsv` | Tratamiento, sexo, raza, día de muestreo y peso individual. |

Lo usa `tests/integration/test_holofood_source.py` con la configuración registrada en
`configs/sources.json`. Para regenerarlo, ejecute el script de descarga y reemplace estas
tablas por las mismas columnas y filas de `data/raw/D1_holofood/`.

Datos públicos de EMBL-EBI (HoloFood Data Portal, MGnify, ENA). Citar: Rogers et al. (2025),
*Database*, baae112. https://doi.org/10.1093/database/baae112
