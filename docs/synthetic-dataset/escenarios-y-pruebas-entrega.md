# Escenarios nutricionales y pruebas del generador

Seguimiento #203 de DS-04 (#5) y DS-06 (#7), ya integradas en main. Esta entrega reutiliza
el generador existente y refuerza su validación; no crea un segundo motor de escenarios.

## Dos escenarios y cambio controlado

| Condición | Basal | Intervenido |
|---|---|---|
| graph_id | synthetic:scenario:basal:0001 | synthetic:scenario:intervened:0001 |
| Variable | crude_protein | crude_protein |
| Valor | 215,0 | 270,0 |
| Unidad sintética | g_kg | g_kg |
| Semilla | 42 | 42 |

La diferencia es 55 g_kg, aproximadamente 25,58 por ciento respecto al basal. Se conserva
esta variable nutricional ya definida; no se añade un cambio de aditivo que introduciría
una segunda intervención. Se mantienen nodos, identificadores locales, topología,
atributos no intervenidos, máscaras y evidencias, salvo el graph_id de transporte.

Ambos escenarios representan la misma muestra sintética. Los ocho tipos contienen,
por escenario: una dieta, un aditivo, cuatro sustratos, diez taxones, ocho funciones,
cinco metabolitos, un huésped y dos fenotipos, en total 32 nodos.

Los valores son convenciones computacionales. Los targets sintéticos no cambian entre
escenarios: el generador no modela eficacia biológica ni causalidad de la intervención.

## Generación reproducible

Desde la raíz, con el proyecto instalado:

```bash
python scripts/generate_synthetic_dataset.py --output artifacts/escenarios-ds04
```

El comando exporta metadata.json y raw/nodes.jsonl, edges.jsonl, instances.jsonl y
outputs.jsonl. Si el destino existe, no se sobrescribe sin autorización explícita mediante
--overwrite. Los artefactos quedan ignorados por Git y no deben publicarse como datos reales.

Para comprobar de nuevo el contrato y las instancias exportadas:

```python
from nutrigraphdt.data.synthetic import load_dataset, validate_dataset

dataset = load_dataset("artifacts/escenarios-ds04")
validate_dataset(dataset)
assert {i.scenario_id for i in dataset.instances} == {"basal", "intervention"}
```

La validación reforzada se ejecuta además al construir cada escenario: exige atributos
obligatorios por tipo, tipos JSON correctos, números finitos, composición con componente,
valor y unidad y máscaras coherentes. Null requiere una máscara true; una clave obligatoria
no puede omitirse. Las máscaras anidadas usan rutas relativas con índices de lista.
La validación no impone rangos fisiológicos ni vocabularios científicos nuevos.

## Pruebas automatizadas

```bash
pytest tests/unit/test_synthetic_nodes.py tests/unit/test_synthetic_edges.py tests/unit/test_scenarios.py tests/unit/test_scenario_input_contract.py tests/unit/test_synthetic_export.py tests/unit/test_synthetic_generator_suite.py tests/integration/test_synthetic_dataset_roundtrip.py
```

La suite existente cubre semillas iguales y diferentes, cantidades, IDs, atributos,
integridad referencial, cambio único, independencia de objetos mutables y exportación
byte a byte reproducible. Las regresiones nuevas rechazan atributos ausentes de los ocho
tipos, booleanos o texto como abundancia, NaN/Infinity, composición inválida, máscaras
inconsistentes y valores no finitos anidados. Un constructor con entrada corrupta falla.

La conformidad estructural no equivale a validez biológica. La revisión y fusión del PR
siguen correspondiendo a una persona distinta de quien publicó los cambios.

## Verificación local del 28 de octubre de 2026

- Suite dirigida del generador: 438 pruebas aprobadas, sin omisiones.
- Suite general con NUTRIGRAPHDT_REQUIRE_GRAPH=1: 2316 aprobadas, dos omitidas por falta
  de la descarga completa HoloFood. No hubo fallos; se conservaron las advertencias de grafos.
- Ruff y formato aprobados; mypy sin errores en 78 archivos de código fuente.
- Exportación y recarga comprobadas: dos instancias, 64 nodos, 156 aristas y seis salidas.

Los resultados son locales. No acreditan ejecución remota de Actions ni validación biológica.
