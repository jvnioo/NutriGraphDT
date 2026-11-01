# Revisión de Pull Requests y criterios del módulo de restricciones (A57-P6, #165)

Este informe registra la revisión cruzada de los entregables A57-P1 a A57-P5 del módulo
`nutrigraphdt.constraints`, contrasta cada Issue con su PR, pruebas y documentación científica,
y deja trazados los bloqueos que siguen abiertos. La revisión se limita a evidencia consultable:
un criterio no se considera cumplido sin una fuente concreta.

- **Estado del código revisado:** `main` en `cb6556e53d6152d5a23a8adbf12644f20b0d9653`
  (merge de #220; coincide con `origin/main` al preparar este informe).
- **Fuentes:** Issues #163, #161, #166, #164, #162 y #165; PRs #209, #210, #213, #219 y #220,
  sus commits, reviews, comentarios y campos de merge de la API de GitHub; código, tests y
  documentación integrada.
- **Autoría y límite de independencia:** prepara este informe `jarayael`, autor de los cinco PR
  revisados. Es una auditoría de trazabilidad y evidencia y **no reemplaza las revisiones humanas
  independientes ni las aprobaciones exigidas**.

Este informe **no cierra #165** mientras sigan pendientes: (1) confirmación escrita de las
revisiones y autorizaciones de merge, (2) el VR de `d06.hydrogen.propionate_bound` en D1, a
incorporar al trabajo de evaluación #185, y (3) la actualización del protocolo y de P-07 en #158.

---

## 1. Criterios de #165

| Criterio | Estado | Evidencia y detalle |
|---|---|---|
| Cada PR del alcance tiene revisión de otra persona y checks citados | **No cumplido** | La API no devuelve reviews registradas para ninguno de los cinco PRs. #210 sí tiene un comentario de revisión de `jvnioo` con checks; no es una review `APPROVED`. No encontré comentario de revisión equivalente en #209, #213, #219 o #220. Los PRs citan checks en sus descripciones, pero la existencia de resultados citados no acredita por sí sola la review. |
| No quedan observaciones sin resolver ni criterios marcados sin evidencia | **No cumplido** | Las matrices de §3 identifican evidencia para los criterios de A57-P1 a P5. Sin embargo, siguen abiertos la confirmación de revisión, el reporte del VR en D1 y la actualización de D-06/P-07. |
| Se publica un resumen con los PR revisados y bloqueos restantes | **Pendiente** | El comentario-resumen se publicará en #165 junto con el PR de este informe. Su texto está en el anexo. |

### Redacción condicional de la evidencia de revisión

**Estado actual (usar mientras no exista confirmación escrita en #165):**

> **No cumplido.** No hay reviews `APPROVED` ni evidencia escrita en #165 que confirme que
> `jvnioo` revisó y autorizó los cinco merges. El comentario de revisión existente en #210 no es
> una aprobación formal y no acredita los otros cuatro PRs.

**Redacción preparada si `jvnioo` confirma en #165 que revisó y autorizó los merges:**

> **Parcial.** La revisión independiente y la autorización de los merges quedaron confirmadas por
> escrito después del merge en #165, pero ninguno de los cinco PRs tiene una review formal
> `APPROVED` registrada en GitHub.

La respuesta actual de la API en #165 solo incluye el comentario previo sobre la entrega de D-06;
no contiene todavía esa confirmación.

---

## 2. Inventario de Pull Requests

Los valores de **merged_by** de la tabla son el valor del campo `merged_by.login` devuelto por la
API de GitHub para cada PR; no se infieren del autor, los commits ni de la conversación.

| PR | Issue / actividad | Autor del PR | Review de otra persona en GitHub | Último commit de rama | Checks citados para el estado final | Merge commit; `merged_by.login` |
|---|---|---|---|---|---|---|
| [#209](https://github.com/jvnioo/NutriGraphDT/pull/209) | [#163](https://github.com/jvnioo/NutriGraphDT/issues/163), A57-P1 | `jarayael` | Sin review registrada; sin comentario de revisión localizado. | `eae0a30212f3f7f5b8f2c0e4649f8e3aef774752` | `ruff check .` → All checks passed; `ruff format --check .` → 289 files; `mypy src` → 85 source files; `NUTRIGRAPHDT_REQUIRE_GRAPH=1 pytest` → 2375 passed, 2 skipped. El cuerpo no ancla esta verificación a un SHA. | `bb7734390dcd1058d8d2ef7e2babc9a33c89a7a7`; API: `merged_by.login = "jarayael"` |
| [#210](https://github.com/jvnioo/NutriGraphDT/pull/210) | [#161](https://github.com/jvnioo/NutriGraphDT/issues/161), A57-P2 | `jarayael` | Sin review registrada. Comentario de `jvnioo` dice “Revisado” e identifica el commit; es comentario, no review `APPROVED`. | `5ac919fa4f7b4b2cdf97c804139e8dd142e9989e` | `ruff check .` → All checks passed; `ruff format --check .` → 289 files; `mypy src` → 85 source files; `NUTRIGRAPHDT_REQUIRE_GRAPH=1 pytest -n 6` → 2388 passed, 2 skipped. El comentario identifica `5ac919f` como estado final. | `c6f2807b98c7ebf76527cff06589d786a38e96c8`; API: `merged_by.login = "jvnioo"` |
| [#213](https://github.com/jvnioo/NutriGraphDT/pull/213) | [#166](https://github.com/jvnioo/NutriGraphDT/issues/166), A57-P3 | `jarayael` | Sin review registrada ni comentario de revisión localizado. | `0f349ad1a900364e0678a4479e5fe1de0055cd95` | El cuerpo cita `ruff check .` → All checks passed; `ruff format --check .` → 310 files; `mypy src` → 95 source files; `NUTRIGRAPHDT_REQUIRE_GRAPH=1 python -m pytest` → 2457 passed, 3 skipped. **El último commit (cambio de una línea en `tests/unit/test_training_tracking.py`) solo se verificó con esos tests seleccionados y Ruff, no con la suite completa.** Los resultados de la suite del cuerpo no se atribuyen al commit final. | `74adff20d7adf64a578d8125511b39f13b563118`; API: `merged_by.login = "jarayael"` |
| [#219](https://github.com/jvnioo/NutriGraphDT/pull/219) | [#164](https://github.com/jvnioo/NutriGraphDT/issues/164), A57-P4 | `jarayael` | Sin review registrada ni comentario de revisión localizado. | `c5a3db0c07870cf071a541af6a6e747e9cc5617f` | `ruff check .` → All checks passed; `ruff format --check .` → 320 files; `mypy src` → 99 source files; `NUTRIGRAPHDT_REQUIRE_GRAPH=1 python -m pytest` → 2495 passed, 3 skipped. El cuerpo no ancla los checks a un SHA. | `45b5e722bd36f40712f9d7cd791d5008d843effb`; API: `merged_by.login = "jarayael"` |
| [#220](https://github.com/jvnioo/NutriGraphDT/pull/220) | [#162](https://github.com/jvnioo/NutriGraphDT/issues/162), A57-P5 | `jarayael` | Sin review registrada ni comentario de revisión localizado. | `51aa7c95504c630c29f918992a161ac9d14e4a47` | `ruff check .` → All checks passed; `ruff format --check .` → 321 files; `mypy src` → 99 source files; `NUTRIGRAPHDT_REQUIRE_GRAPH=1 python -m pytest -ra` → 2514 passed, 0 skipped. El cuerpo no ancla los checks a un SHA. | `cb6556e53d6152d5a23a8adbf12644f20b0d9653`; API: `merged_by.login = "jarayael"` |

**Declaración del autor y discrepancia de merge.** El autor de este informe (`jarayael`) declara que
los cinco merges fueron realizados o autorizados por el líder `jvnioo`. El campo de API
`merged_by.login` muestra
literalmente `jarayael` para #209, #213, #219 y #220, y `jvnioo` para #210. Por ello, queda
pendiente que `jvnioo` confirme por escrito en #165 que revisó y autorizó los merges atribuidos por
la API a `jarayael`. `merged_by` identifica quién ejecutó el merge; no demuestra por sí solo quién
lo autorizó.

No se encontraron check runs ni estados automáticos en los heads de los PR. Los checks indicados
arriba son resultados locales citados en cuerpos o comentarios, de acuerdo con el flujo del
repositorio. El hecho de que un PR cite checks no garantiza que cada línea de resultados corresponda
al último commit salvo donde la referencia al SHA lo indica expresamente.

---

## 3. Evidencia por criterio de aceptación de A57-P1 a A57-P5

### A57-P1 — interfaz y registro (#163, PR #209)

| Criterio | Estado | Evidencia |
|---|---|---|
| Añadir una restricción sin modificar el bucle de datos ni el modelo | Evidencia presente | El cuerpo de #209 describe la interfaz y penalización como consumidor independiente. `test_importing_constraints_does_not_import_training_package` en `tests/unit/test_constraints.py` comprueba el aislamiento respecto de `models.training`. |
| Calcular violaciones en unidades reales e identificarlas por muestra y tipo | Evidencia presente | `test_structural_constraints_report_real_unit_values_and_sample_ids` en `tests/unit/test_constraints.py`; contrato y unidades en `docs/models/constraints.md`. |
| Checks locales y pruebas tensoriales | Evidencia presente en `main` | Checks históricos citados en #209; además, la suite integrada de §4 valida el estado actual que contiene el PR. La suite del PR se cita como 2375 passed, 2 skipped. |

### A57-P2 — no negatividad (#161, PR #210)

| Criterio | Estado | Evidencia |
|---|---|---|
| Concentraciones reconstruidas no negativas o decisión documentada de penalización | Evidencia presente | `intrinsic_softmax` y el fallo explícito ante salidas no representables están descritos en `docs/models/constraints.md`; casos de reconstrucción y extremos en `tests/unit/test_composition.py` y `tests/unit/test_constraint_reconstruction.py`. |
| Máscaras preservadas, sin NaN/inf aceptados | Evidencia presente | Pruebas de entradas no finitas, gradientes y reconstrucción en `tests/unit/test_composition.py` y `tests/unit/test_constraint_reconstruction.py`; pruebas de máscaras en `tests/unit/test_constraints.py`. |
| Checks locales y extra `graph` | Evidencia presente | Checks citados en #210 y suite integrada con `NUTRIGRAPHDT_REQUIRE_GRAPH=1` en §4. La cita de comentario señala específicamente el head `5ac919f`. |

### A57-P3 — pérdida compuesta (#166, PR #213)

| Criterio | Estado | Evidencia |
|---|---|---|
| `λ=0` reproduce el control sin contribución bioquímica | Evidencia presente | `test_zero_lambda_never_calls_constraint_path` y comparación exacta de historial, mejor época y tensores `state_dict` descrita en el cuerpo de #213. |
| `run.json` y registros conservan lambda, términos y pérdidas separadas | Evidencia presente | Casos en `tests/unit/test_training_composite_loss.py` y `tests/unit/test_training_tracking.py`; campos y compatibilidad descritos en #213. |
| Checks locales y pruebas aplicables de gradiente/entrenamiento | Evidencia parcial en la rama; suite integrada actual verificada | #213 cita la suite con 2457 pasados, 3 omitidos, pero no acredita la suite completa en su último commit `0f349ad`. La suite del `main` integrado pasó en §4; la carencia de validación completa del head queda anotada, no se reescribe como validación histórica completa. |

### A57-P4 — restricción D-06 (#164, PR #219)

| Criterio | Estado | Evidencia |
|---|---|---|
| Ecuación y tolerancia enlazan fuente aprobada y versión | Evidencia presente | D-06 v1, §3.5, integrado por #218; `test_d06_metadata_and_source_provenance_match_approved_document` en `tests/unit/test_d06_constraints.py`. |
| Pruebas de cumplimiento, violación, máscaras y reconstrucción | Evidencia presente | `test_d06_operator_has_hand_computed_feasible_violating_and_boundary_cases` y pruebas de máscara/reconstrucción en `tests/unit/test_d06_constraints.py`. |
| Checks locales sin dependencias pagadas | Evidencia presente | Checks citados en #219; no se añade dependencia pagada y la suite integrada pasó en §4. |

### A57-P5 — pruebas unitarias (#162, PR #220)

| Criterio | Estado | Evidencia |
|---|---|---|
| Cada restricción tiene cumplimiento/violación con valores esperados independientes | Evidencia presente | Casos manuales en `tests/unit/test_constraints.py`, `tests/unit/test_d06_constraints.py` y `tests/unit/test_constraint_reconstruction.py`; tolerancias documentadas en `docs/models/constraints.md`. |
| Las pruebas nuevas no entrenan ni descargan datos reales | Evidencia presente en el alcance revisado | El cuerpo de #220 declara que las pruebas no entrenan, no crean loaders de entrenamiento y no leen `data/` ni `artifacts/`; el cambio se limita a tests y documentación. |
| Checks y pruebas no omitidas silenciosamente | Evidencia presente | #220 añade el modo estricto en `tests/conftest.py`; #220 cita 2514 passed, 0 skipped. La suite integrada repitió el modo estricto en §4. |

---

## 4. Verificación del `main` integrado

La rama `docs/165-constraints-pr-cross-review` y `origin/main` apuntaban al mismo commit
`cb6556e53d6152d5a23a8adbf12644f20b0d9653` antes de editar este informe. En ese `main` integrado
se ejecutaron los checks siguientes; son evidencia del estado integrado y cubren la suite completa
tras los heads de los cinco PRs:

```text
ruff check .
All checks passed!

ruff format --check .
321 files already formatted

mypy src
Success: no issues found in 99 source files

NUTRIGRAPHDT_REQUIRE_GRAPH=1 python -m pytest -ra
2514 passed, 0 skipped, 39595 warnings in 447.62s
```

La ejecución fue en Windows, Python 3.14.5. El último comando se ejecutó en PowerShell
estableciendo `NUTRIGRAPHDT_REQUIRE_GRAPH=1` y llamando
`.venv\Scripts\python.exe -m pytest -ra`. La salida incluyó un `FutureWarning` de Torch/JIT y
`PytestUnhandledThreadExceptionWarning` con `UnicodeDecodeError` del lector de subprocess en
`tests/integration/test_cohort_d1.py`; la suite terminó en verde. Esto es un hallazgo lateral de
portabilidad, no un fallo de A57. La ejecución dirigida de ese archivo terminó `4 passed, 1
warning`. El error distinto `No module named 'scripts'` con `pytest.exe` no se reprodujo en esta
revisión y no se presenta como hallazgo confirmado.

---

## 5. Observaciones y trabajo propuesto

### R-1 · Falta confirmación escrita de la revisión y autorización de los merges

- **Origen:** campos `merged_by` y reviews consultados en la API de GitHub para #209, #210, #213,
  #219 y #220; sección §2.
- **Qué ocurre:** solo #210 presenta un comentario de revisión de `jvnioo`; ningún PR tiene review
  registrada. Cuatro campos de API atribuyen el merge a `jarayael`, aunque el autor de este informe
  (`jarayael`) declara que todos fueron realizados o autorizados por `jvnioo`.
- **Consecuencia:** el primer criterio de #165 queda **No cumplido** hasta confirmación escrita
  del líder en #165. Si la confirmación se publica, el estado podrá pasar a **Parcial**, nunca a
  “APPROVED”: la review independiente habría sido confirmada después del merge, sin aprobación
  formal registrada en los PRs.
- **Responsable / acción:** `jvnioo`, confirmación escrita en #165. No es posible convertir estos
  PRs ya fusionados en reviews `APPROVED` retroactivas.

### R-2 · El protocolo y P-07 conservan el estado pendiente de D-06

- **Origen:** `constraints-evaluation-protocol.md` §3.2 y §9 todavía describen D-06 como pendiente;
  la fila P-07 de `explanations-protocol-review.md` sigue `pendiente`. D-06 v1 ya está integrada
  mediante #218. La Issue #158 permanece abierta.
- **Consecuencia:** contradicción entre el documento de Investigación entregado y los documentos
  de Desarrollo; P-07 no refleja la respuesta de Investigación. No cambiar protocolos dentro de
  A57-P6.
- **Responsable / acción:** Desarrollo en #158 debe actualizar la respuesta P-07 y coordinar la
  actualización del protocolo.

### R-3 · Falta el VR de `d06.hydrogen.propionate_bound` para D1

- **Origen:** `docs/models/constraints.md` indica que el reporte F5 debe confirmar `VR = 0`;
  D-06 §6 espera ese resultado. No se encontró un reporte de evaluación D1 con ese VR en `reports/`.
  Las pruebas de D-06 verifican casos manuales y composiciones publicadas, no el VR de predicciones
  evaluadas de D1.
- **Consecuencia:** no hay evidencia para afirmar que las predicciones de D1 tuvieron `VR = 0`.
  El criterio de generación de resultados para D1 debe mostrar el resultado, incluso si difiere
  del esperado.
- **Responsable / acción:** Desarrollo en la evaluación existente #185, con registros de
  violaciones relacionados con #179. El comentario propuesto para #185, que reporta el VR real y lo
  compara con D-06 §6, se entrega a `jvnioo` para que decida si lo publica.

### R-4 · Control de soporte empírico recomendado para F6

- **Origen:** D-06 §7 recomienda estimar mínimos y máximos por fracción usando solo el train y
  devolver “no estimable” si una predicción de escenario queda fuera de ese soporte.
- **Consecuencia:** no forma parte de A57/F5 ni es una restricción que deba entrar en la pérdida.
  No se crea una Issue desde este informe.
- **Responsable / acción:** Desarrollo/F6. La propuesta de Issue de control de soporte, con estado
  inicial sugerido `Blocked` hasta identificar el Issue dependiente del motor de escenarios, se
  entrega a `jvnioo` para que decida si la crea.

### L-1 · Warning de codificación en Windows (lateral, no bloquea A57)

- **Origen:** `tests/integration/test_cohort_d1.py` captura stdout/stderr del subprocess con
  `encoding="utf-8"`; en Windows el test pasa, pero el hilo lector emite `UnicodeDecodeError`
  (`0xf3`).
- **Consecuencia:** warning ruidoso y posible fragilidad de pruebas entre plataformas, no un fallo
  funcional de A57. Se propone una Issue de mantenimiento separada; no existe todavía.
- **Responsable:** Desarrollo/mantenimiento. La propuesta de Issue de mantenimiento se entrega a
  `jvnioo` para que decida si la crea. El supuesto error `No module named 'scripts'` no se
  reprodujo y no se eleva a observación confirmada.

### Acciones fuera de alcance — propuestas entregadas al líder

1. **Propuesta A:** Issue F6 para el control de soporte empírico de D-06 §7; borrador completo en
   el anexo.
2. **Propuesta B:** Issue de mantenimiento para eliminar el `UnicodeDecodeError` de
   `test_cohort_d1.py` en Windows; borrador completo en el anexo.
3. **Comentario propuesto para #185:** registrar el VR real de
   `d06.hydrogen.propionate_bound` en D1 y explicar cualquier diferencia respecto del VR esperado;
   texto completo en el anexo.
4. **Comentario-resumen para #165:** publicar el inventario de los cinco PRs, los resultados de
   checks integrados de §4 y los bloqueos R-1, R-2 y R-3; texto completo en el anexo. Se publicará
   junto con el PR de este informe.

Las propuestas A, B y el comentario para #185 se entregan al líder `jvnioo`, quien decidirá si
crea las Issues o publica el comentario. No se crea ninguna Issue ni se publica ningún comentario
en GitHub desde este informe.

---

## 6. Verificación y cierre de #165

El informe resume PRs, Issues, criterios, evidencia integrada y bloqueos pendientes. No cierra
#165: antes deben registrarse la confirmación de revisión/autoridad descrita en R-1, el resultado
de VR D1 en #185 y la actualización de D-06/P-07 en #158. La única publicación pendiente de este
informe es el comentario-resumen de #165, que se publicará junto con el PR. Las propuestas A, B y
el comentario para #185 quedan entregados a `jvnioo` para su decisión.

---

## Anexo A. Borrador completo de la Propuesta A — Issue de control de soporte empírico F6

**Título:** F6 — Control de soporte empírico para predicciones de escenarios

### Objective

Detectar predicciones de escenarios fuera del soporte empírico del conjunto con que se entrenó el
modelo y devolver «no estimable» en vez de un valor extrapolado sin cobertura.

### Context

D-06 v1, §7 recomienda este control para F6. No es una restricción bioquímica, no debe entrar en la
pérdida ni en la decisión comparativa de F5.

### Expected work

- [ ] Calcular mínimos y máximos por fracción usando únicamente el conjunto de entrenamiento del
  modelo congelado; en CV, usar el train de cada fold.
- [ ] Marcar predicciones fuera del intervalo y producir «no estimable» con su motivo.
- [ ] Documentar el comportamiento cuando el escenario y los datos permiten soporte por día de
  muestreo.

### Acceptance criteria

- [ ] El cálculo de soporte excluye validación y evaluación; los tests prueban límites, dentro y
  fuera de rango.
- [ ] Las predicciones fuera de soporte no se reportan como estimaciones numéricas válidas.
- [ ] Se registran intervalo, subconjunto fuente y motivo, sin percentiles ni umbrales científicos
  inventados.
- [ ] El control queda separado de la pérdida y de las restricciones D-06/F5.

### Dependencies

- [ ] Issue del motor de escenarios F6: identificar o crear antes de empezar e incorporar la
  relación nativa `blocked by`.

### Technical / scientific notes

Fuente: D-06 §7. Una vez identificada la dependencia del motor F6, estado inicial sugerido:
**Blocked**; no mover a Ready antes de poder integrarlo y revisarlo.

### Planning

**Size:** M · **Priority:** P1 · **Project phase:** F6

**Initial board state:** Blocked

### Cost check

- [x] This task can be completed without paid services, paid APIs, paid compute, subscriptions, or
  billing requirements.

### Ready checklist

- [x] The objective is clear.
- [x] Acceptance criteria are explicit.
- [ ] Critical dependency on the F6 scenario engine is identified and available.
- [x] The task is independently reviewable and no larger than `L`.
- [x] The task belongs to the Development Cell scope.

**Estado:** propuesta entregada a `jvnioo`; Issue no creada por este informe.

## Anexo B. Borrador completo de la Propuesta B — Issue de mantenimiento Windows

**Título:** Mantenimiento — Evitar `UnicodeDecodeError` al capturar subprocess en
`test_cohort_d1.py` en Windows

### Objective

Eliminar la excepción de decodificación del lector del subproceso en el test de reporte de cohorte
D1 en Windows, preservando las aserciones del test.

### Context

En `main`, `test_report_script_writes_official_and_sensitivity_tables` pasa, pero emite
`PytestUnhandledThreadExceptionWarning` por un byte `0xf3` incompatible con la decodificación UTF-8
configurada. Es independiente de A57.

### Expected work

- [ ] Determinar la codificación real de la salida capturada del subproceso en Windows.
- [ ] Ajustar la captura/decodificación para que sea explícita y portable.
- [ ] Validar el test con `python -m pytest` y con el ejecutable `pytest.exe` en Windows.

### Acceptance criteria

- [ ] El test conserva sus aserciones y pasa en Windows.
- [ ] No aparece `UnicodeDecodeError` ni `PytestUnhandledThreadExceptionWarning`.
- [ ] La salida de error esperada del proceso sigue verificándose; no se suprimen warnings de forma
  general.

### Dependencies

None.

### Technical / scientific notes

Evidencia observada en `tests/integration/test_cohort_d1.py`, en la captura del subprocess con
`encoding="utf-8"`. La ejecución dirigida terminó `4 passed, 1 warning`; no se reprodujo
`No module named 'scripts'`.

### Planning

**Size:** S · **Priority:** P2 · **Project phase:** F5

**Initial board state:** Backlog

### Cost check

- [x] This task can be completed without paid services, paid APIs, paid compute, subscriptions, or
  billing requirements.

### Ready checklist

- [x] The objective is clear.
- [x] Acceptance criteria are explicit.
- [x] Critical dependencies are available or an approved fallback is documented.
- [x] The task is independently reviewable and no larger than `L`.
- [x] The task belongs to the Development Cell scope.

**Estado:** propuesta entregada a `jvnioo`; Issue no creada por este informe.

## Anexo C. Texto propuesto para comentario en #185

> **Criterio adicional propuesto para A68-P2:** el reporte de D1 debe incluir el VR observado para
> `d06.hydrogen.propionate_bound` y contrastarlo con el `VR = 0` esperado en D-06 §6. Si el
> resultado difiere, registrar la población de predicciones evaluada y explicar la diferencia con
> evidencia; no asumir el valor esperado sin calcularlo.
>
> Esta es una recomendación de trazabilidad y verificación para F5. No modifica la definición de
> D-06 ni agrega una restricción o umbral.

**Estado:** texto propuesto, entregado a `jvnioo` para que decida si lo publica en #185.

## Anexo D. Texto del comentario-resumen para #165

> Revisé la trazabilidad de A57-P1 a A57-P5: #163 → #209, #161 → #210, #166 → #213, #164 → #219
> y #162 → #220. Los cinco PR están integrados en `main` (`cb6556e`).
>
> **Reviews:** no encontré reviews `APPROVED` registradas en GitHub para los cinco PRs. #210 tiene
> un comentario de revisión de `jvnioo`, pero no una aprobación formal; en los demás no encontré
> review ni comentario de revisión. El informe de A57-P6 no sustituye la revisión humana exigida.
>
> **Checks de ramas:** cada PR cita resultados locales, con la limitación de que la cita no
> identifica el SHA final en #209, #219 y #220. En #210 el comentario sí identifica el SHA final.
> En #213, el último commit —un cambio de una línea en `tests/unit/test_training_tracking.py`—
> solo se verificó con tests seleccionados y Ruff, no con la suite completa.
>
> **`main` integrado:** commit `cb6556e`; Ruff pasó, formato indicó 321 archivos, mypy no encontró
> problemas en 99 fuentes y `NUTRIGRAPHDT_REQUIRE_GRAPH=1 python -m pytest -ra` terminó con 2514
> pasados y 0 omitidos. La suite emitió 39 595 warnings, incluido el `UnicodeDecodeError` de un
> subprocess en Windows; quedó separado como hallazgo lateral.
>
> **Pendientes para cerrar la compuerta:** registrar la confirmación de revisión/autoridad; producir
> en el trabajo de evaluación F5 el VR D1 de `d06.hydrogen.propionate_bound` indicado por D-06 §6;
> y actualizar en #158 el estado de D-06/P-07 en el protocolo. El control de soporte empírico
> recomendado para F6 y el warning de Windows se entregan como propuestas al líder `jvnioo`; no
> son bloqueos de A57.
>
> Este resumen no declara #165 cumplido ni reemplaza la revisión humana independiente.

**Estado:** comentario-resumen pendiente de publicación; se publicará junto con el PR de este
informe.
