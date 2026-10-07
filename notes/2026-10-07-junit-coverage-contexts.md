# Spike: ids del JUnit frente a contextos de `--cov-context=test`

Rama desechable para resolver las dudas de `docs/SPEC.md` sobre cómo casan los
casos del JUnit XML de pytest con los contextos que guarda pytest-cov. No es
código de distiller y `docs/SPEC.md` no se ha tocado.

Etiquetas: **FACT** = lo ejecuté y lo vi, con el escenario donde está la prueba;
**DOC** = documentación oficial, con enlace; **INFERENCE**; **OPINION**.

## Cómo reproducirlo

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python pytest==9.1.1 pytest-cov==7.1.0 coverage==7.16.2 defusedxml==0.7.1 pytest-xdist==3.8.0
uv venv .venv314 --python 3.14
uv pip install --python .venv314/bin/python pytest==9.1.1 pytest-cov==7.1.0 coverage==7.16.2 defusedxml==0.7.1 pytest-xdist==3.8.0
./run.sh
```

Cada escenario deja `out/<escenario>/pytest.log`, `junit.xml` y `report.txt`.
`report.txt` lo escribe `inspect_run.py`, que lee el `.coverage` solo con la API
pública de coverage (`measured_contexts()`, `measured_files()`,
`contexts_by_lineno()`). Versiones: CPython 3.12.3 y 3.14.6 en Linux (WSL2),
pytest 9.1.1, pytest-cov 7.1.0 y coverage 7.16.2, las últimas en PyPI el
2026-10-06, y pytest-xdist 3.8.0.

| Escenario | Qué cambia respecto a `main` |
|---|---|
| `main` | nada: configuración por defecto, Python 3.12 |
| `hooks` | el conftest define hooks que llaman a código medido (`SPIKE_HOOKS=1`) |
| `xunit1_prefix` | `-o junit_family=xunit1 --junit-prefix=pfx` |
| `order_reversed` | solo `test_vat` y `test_total`, en ese orden |
| `static_context` | contexto estático de coverage, `[run] context = ci` |
| `cov_tests_too` | también `--cov=tests` |
| `preplugin` | `-p spike_preplugin`, que importa `shop.preimport` antes de que arranque coverage |
| `xdist`, `xdist_repeat` | `-n 2`; y `-n 4` tres veces seguidas |
| `unescaped_ids` | `disable_test_id_escaping_and_forfeit_all_rights_to_community_support=true` |
| `collection_error`, `collection_error_continue` | un módulo que falla al importarse, sin y con `--continue-on-collection-errors` |
| `sysmon_on_312`, `pytrace`, `branch` | `COVERAGE_CORE=sysmon`; `COVERAGE_CORE=pytrace`; `--cov-branch` |
| `py314_default`, `py314_ctrace` | Python 3.14.6 sin configurar nada; y con `COVERAGE_CORE=ctrace` |
| `from_parent_dir` | pytest lanzado desde la raíz del repo, con `spike/tests/...` |
| `collision` (en `collision/out/`) | proyecto aparte con `tests/v1.2/test_x.py` y `tests/v1/2/test_x.py` |

## 1. Cómo casan los ids del JUnit con los contextos

- **DOC** El contexto es el id del test más la fase, "separated with a pipe symbol" ([pytest-cov, Contexts](https://pytest-cov.readthedocs.io/en/latest/contexts.html)). Esa página no dice nada de la colección, las fixtures ni xdist.
- **DOC** `junit_family` vale `xunit2` por defecto desde pytest 6.1 ([referencia](https://docs.pytest.org/en/stable/reference/reference.html#confval-junit_family)).
- **FACT** (`main`) En xunit2 cada `<testcase>` lleva solo `classname`, `name` y `time`. No trae el node id ni el fichero.
- **FACT** (`main`) La regla que se ve: `classname` es la ruta del node id con `/` cambiado por `.` y sin `.py`, seguida de las clases separadas por `.`; `name` es la función con sus parámetros.
  - `tests/test_tax.py::test_rate[es-0.21]` → (`tests.test_tax`, `test_rate[es-0.21]`)
  - `tests/test_tax.py::TestVat::test_param_method[1]` → (`tests.test_tax.TestVat`, `test_param_method[1]`)
  - `tests/test_tax.py::TestVat::TestNested::test_inner` → (`tests.test_tax.TestVat.TestNested`, `test_inner`)
  - `tests/test_xunit_styles.py::TestUnittestStyle::test_one`, un `unittest.TestCase` → (`tests.test_xunit_styles.TestUnittestStyle`, `test_one`)
- **FACT** (`main`) Aplicando esa regla a los node ids de los contextos casan 27 de los 30 `<testcase>`, ninguno ambiguo. Casan también los parámetros con `|`, `::`, `/`, `.`, espacios, corchetes anidados, no-ASCII y un carácter de control.
- **FACT** (los 18 escenarios) Mi reimplementación de la regla, de 9 líneas en `inspect_run.py`, da lo mismo que la función privada de pytest `_pytest.junitxml.mangle_test_address` para todos los node ids vistos.
- **FACT** (`main`) Los 3 que no casan: `test_no_src_code`, que no ejecuta nada de `src/` y por eso no tiene ningún contexto; `test_skipped`, igual; y un test que cambia su `classname` con `record_xml_attribute`.
- **FACT** (`cov_tests_too`) Midiendo también `tests/`, `test_no_src_code` pasa a tener contexto (las líneas de su propio fichero). `test_skipped` sigue sin él.
- **FACT** (`main`) Por defecto pytest escapa el no-ASCII y los caracteres de control igual en los dos lados (`test_odd_ids[a\xf1o]`, con la barra literal), y casan.
- **FACT** (`unescaped_ids`) Sin ese escapado, `año` casa (UTF-8 en los dos lados) pero el carácter de control no: el contexto lleva el carácter 0x07 y el JUnit escribe `#x07`.
- **FACT** (`collision`) Dos tests distintos, `tests/v1.2/test_x.py::test_m` y `tests/v1/2/test_x.py::test_m`, salen en el JUnit con el mismo par (`tests.v1.2.test_x`, `test_m`).
- **INFERENCE** Con xunit2 no hay forma fiable de saber cuál de esos dos `<testcase>` es cuál, y en general no se puede reconstruir el node id desde el JUnit: la regla pierde información.
- **FACT** (`main`) Sin shards, un mismo par sale dos veces en un JUnit: un test que falla en la llamada y da error en el teardown deja un `<testcase>` con `<failure>` y otro con `<error>`.
- **DOC** `--junit-prefix` "Prepend prefix to classnames in junit-xml output" ([referencia](https://docs.pytest.org/en/stable/reference/reference.html#cmdoption-junit-prefix)), y `record_xml_attribute` "can also be used to override existing values" ([output](https://docs.pytest.org/en/stable/how-to/output.html#record-xml-attribute)).
- **FACT** (`xunit1_prefix`) Con `--junit-prefix=pfx` todos los `classname` empiezan por `pfx.` y casan 0 de 30.
- **FACT** (`main`) `record_xml_attribute("classname", ...)` cambia el `classname` aunque pytest avise de que es incompatible con xunit2. (`xdist`) Con `-n 2` el cambio no se aplica y el test casa.
- **FACT** (`static_context`) Con `[run] context = ci` los contextos pasan a ser `ci|<node id>|<fase>`; partiendo por el último `|` casan 0 de 30.
- **FACT** (`xunit1_prefix`) Con `junit_family=xunit1` aparecen `file`, relativo al rootdir, y `line`, contada desde 0: `def test_create` está en la línea 4 y sale `line="3"`.
- **FACT** (`from_parent_dir`) Lanzado desde la raíz del repo con `spike/tests/...`, la terminal muestra `spike/tests/test_tax.py::test_vat`, pero los contextos y el JUnit dicen `tests/test_tax.py::test_vat`: son relativos al rootdir (`spike/`), no al directorio desde el que se lanza.
- **FACT** (`main`) coverage guarda rutas absolutas: `/home/sergi/code/distiller/spike/src/shop/tax.py`.
- **FACT** (`collection_error`) Un módulo que falla al importarse da `<testcase classname="" name="broken.test_broken">` con `<error message="collection failure">`. Sin `--continue-on-collection-errors` no corre ningún test y el `.coverage` queda sin ficheros ni contextos.

## 2. Formato de los contextos y fases

- **DOC** La fase es "one of "setup", "run", or "teardown"" ([pytest-cov, Contexts](https://pytest-cov.readthedocs.io/en/latest/contexts.html)).
- **FACT** (`main`) Formato exacto: `<node id>|setup`, `<node id>|run` y `<node id>|teardown`. La fase de llamada se llama `run`, no `call`.
- **FACT** (`main`) Una fase solo tiene contexto si en ella se ejecutó alguna línea medida, así que un test tiene de 0 a 3 contextos. `test_vat`, que pide la fixture de sesión ya montada, solo tiene `|run`.
- **FACT** (`main`) Partir por el último `|` separa bien la fase aunque el id lleve `|`: `test_odd_ids[a|b]|run`.
- **FACT** (`main`) El contexto cambia antes de montar y antes de desmontar las fixtures: lo que hace una fixture al montarse cae en el `|setup` del test, no en el teardown del anterior.
- **DOC** En `unittest.TestCase` el setup y el teardown se hacen "during the call phase" ([unittest](https://docs.pytest.org/en/stable/how-to/unittest.html#pdb-unittest-note)).
- **FACT** (`main`) `setUp` y `tearDown` caen en `|run`; `setUpClass` en `test_one|setup` y `tearDownClass` en `test_two|teardown`. Los `setup_method`/`teardown_method` de estilo pytest caen en `|setup` y `|teardown`.
- **DOC** coverage dice: "the code run by the test runner before (and between) tests will be in the empty context" ([coverage, Measurement contexts](https://coverage.readthedocs.io/en/7.16.2/contexts.html)).
- **FACT** (`hooks`) Con pytest-cov eso solo se cumple antes del primer test. `pytest_runtest_logstart` del test N+1 cae en el `|teardown` del test N, y `pytest_runtest_logfinish` en el `|teardown` del propio test. Con esos hooks, `test_no_src_code` y `test_skipped` pasan a tener fila.
- **FACT** (`hooks`) Lo que corre en `pytest_sessionfinish` no queda en ningún contexto.
- **INFERENCE** Lo explica el código de pytest-cov 7.1.0 (`src/pytest_cov/plugin.py`): solo cambia de contexto en `pytest_runtest_setup`, `pytest_runtest_call` y `pytest_runtest_teardown`, nunca vuelve a `""`, y para y guarda coverage al acabar `pytest_runtestloop`, antes de `pytest_sessionfinish`.
- **DOC** Con contexto estático y dinámico a la vez, "they are joined with a pipe symbol" ([coverage, Measurement contexts](https://coverage.readthedocs.io/en/7.16.2/contexts.html)).

## 3. A qué test va lo que ejecuta una fixture de sesión

- **DOC** "Fixtures are created when first requested by a test"; las de módulo se destruyen "during teardown of the last test in the module" y las de sesión "at the end of the test session" ([fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html#fixture-scopes)).
- **FACT** (`main`) El setup de la fixture de sesión (`db.connect()`) cae en `test_total|setup`, el primer test que la pide. `test_vat`, que la pide después, no recibe nada de ella.
- **FACT** (`main`) Su teardown (`db.close()`, tras el `yield`) cae en `test_last_does_not_use_database|teardown`, el último test de la sesión, que nunca pidió la fixture. Con una fixture de módulo pasa lo mismo: su teardown cae en el último test del módulo, que no la usa.
- **FACT** (`main`) El `time` del JUnit reparte igual: `test_total` 0,328 s, que incluye un `sleep(0.3)` del setup, y `test_vat` 0,001 s.
- **DOC** Por defecto `junit_duration_report = total`, que incluye "setup, call, and teardown times" ([referencia](https://docs.pytest.org/en/stable/reference/reference.html#confval-junit_duration_report)).
- **FACT** (`order_reversed`) Cambiando el orden cambian las filas: `connect` pasa a `test_vat|setup` y `close` a `test_total|teardown` (y `test_vat` pasa a 0,311 s).
- **FACT** (`xdist`) Con `-n 2` cada worker monta su propia copia; `test_last_does_not_use_database`, último de un worker que nunca montó la fixture, se queda sin contexto.
- **FACT** (`xdist_repeat`) Con `-n 4`, tres ejecuciones idénticas dieron tres atribuciones distintas: `connect` cayó en dos tests en las ejecuciones 1 y 3 y en uno en la 2, y `close` cayó cada vez en tests distintos.

## 4. A qué contexto van las líneas que se ejecutan al importar durante la colección

- **DOC** "Any code measured before a dynamic context is set will be recorded in this empty context" ([coverage, Measurement contexts](https://coverage.readthedocs.io/en/7.16.2/contexts.html)).
- **FACT** (`main`) Las líneas de módulo de lo que importan los tests y el conftest al coleccionar van al contexto `""`, incluidas las líneas `def`. Por eso 13 de los 14 ficheros medidos tienen líneas en `""`; solo es import-only el que no tiene ninguna en un contexto de test: `__init__.py`, `cases.py`, `confimport.py`, `constants.py` y `hooks.py`, cuyos hooks están apagados en `main`.
- **FACT** (`main`) También va a `""` el cuerpo de una función que se llama al coleccionar: `vat_cases()`, que genera los parámetros de un `parametrize`. (`hooks`) Y lo que corre en `pytest_sessionstart` y `pytest_collection_finish`.
- **FACT** (`main`) Si el primer import ocurre dentro de un test, las líneas de módulo van a ese test: `lazy.py` cae en `test_lazy_import|run` y no tiene ninguna en `""`.
- **FACT** (`preplugin`) Si un plugin cargado con `-p` importa el módulo antes de que pytest-cov arranque coverage, sus líneas de módulo no quedan en ningún contexto; los cuerpos de función que se ejecutan después sí.
- **FACT** (`static_context`) Con contexto estático, `""` pasa a ser `ci`.
- **FACT** (`xdist`) Con xdist las líneas de import siguen en `""`.

## Hallazgo no buscado: el núcleo de medición de coverage

- **DOC** El núcleo `sysmon` es "the default in Python 3.14+" y "does not yet support plugins, dynamic contexts, or some concurrency libraries" ([coverage, config](https://coverage.readthedocs.io/en/7.16.2/config.html#config-run-core)). El changelog de 7.15.3 dice que, "using the context API as pytest-cov does, contexts would be silently dropped. Now a warning is issued" ([changes](https://coverage.readthedocs.io/en/7.16.2/changes.html#changes-7-15-3)).
- **FACT** (`py314_default`) En Python 3.14.6, sin configurar nada, coverage usa `sysmon`, avisa una vez con `CoverageWarning: Dynamic contexts aren't supported with core=sysmon; context data may be incomplete (no-sysmon-context)` y los datos salen incompletos: 19 contextos en vez de 34; casan 14 de 30 `<testcase>` en vez de 27.
- **FACT** (`sysmon_on_312`) Lo mismo en Python 3.12 con `COVERAGE_CORE=sysmon`.
- **FACT** (`compare_with_main.txt`) `py314_ctrace`, `pytrace` y `branch` dan un `report.txt` idéntico al de `main`, sin contar los tiempos.
- **FACT** (`report.txt`, línea "recorded lines by how many test contexts") Con `sysmon` ninguna línea quedó en más de un contexto de test, solo en el de la primera vez que se ejecutó. Con `ctrace` hay líneas en 2, 5, 7 y 8 contextos.
- **FACT** La tabla `meta` del `.coverage` solo guarda `version` y `has_arcs`, sin rastro del núcleo. La miré con sqlite, fuera de la API pública.
- **INFERENCE** El fichero de datos, por sí solo, no dice que se usó `sysmon`; el aviso solo queda en la salida de pytest.

## Lo aprendido

- **INFERENCE** Con la configuración por defecto de pytest, casar es sencillo: se pasa cada node id de los contextos por la regla de pytest y se busca su par (`classname`, `name`) en el JUnit. Al revés no se puede, porque la regla pierde información.
- **INFERENCE** Casi todo lo que rompe el emparejamiento (`--junit-prefix`, `record_xml_attribute`, un contexto estático, ids sin escapar con caracteres de control) deja tests sin fila, que el SPEC ya trata como unmeasured: el lado seguro. Una colisión solo cae del lado seguro si se trata como unmeasured en lugar de elegir uno de los dos.
- **INFERENCE** "Sin fila" junta tres cosas: tests nuevos o renombrados, tests que no ejecutan código medido y tests saltados. La cuota de unmeasured del informe no aislará los fallos de emparejamiento.
- **INFERENCE** El ejemplo de selección del SPEC con `src/shop/db.py` (solo `test_total`) solo se cumple si el teardown de la fixture no ejecuta ninguna línea de `db.py`; si la ejecuta, el último test de la sesión también entra. El caso límite "those lines count only in test_total's row" vale para el setup, no para el teardown.
- **INFERENCE** Las filas dependen del orden y del reparto entre workers de la ejecución en M: el mismo commit puede dar filas distintas.
- **INFERENCE** `sysmon` rompe la premisa del SPEC de que un emparejamiento malo falla hacia el lado seguro: un test con fila parcial cuenta como medido, pero no se selecciona cuando cambia un fichero que sí usa. Eso infla a la vez los fallos y el ahorro, y en Python 3.14+ es lo que sale por defecto.
- **OPINION** El SPEC debería decidir qué hacer con datos de `sysmon`: rechazarlos como entrada inutilizable o exigir `core = ctrace` en la ejecución de M. Que ninguna línea esté en dos contextos de test es una pista para detectarlo, pero solo la he visto en este proyecto.
- **INFERENCE** El lector de JUnit tiene que juntar los resultados de un par repetido aunque no haya shards (`failure` más `error`).
- **INFERENCE** Como coverage guarda rutas absolutas, convertirlas es el caso normal, no el caso límite que describe el SPEC.
- **INFERENCE** Que un fichero sea import-only depende de cuándo se importa: un import perezoso lo mete en la fila de un test, un import temprano desde un plugin lo deja sin medir y generar parámetros de `parametrize` con él lo deja import-only.

## Lo que sigue sin saberse

- Solo probé CPython 3.12.3 y 3.14.6 en Linux, con las versiones de arriba. No sé cómo se comportan versiones anteriores, otros sistemas ni Windows.
- No probé plugins que reordenan, repiten o reintentan tests (pytest-randomly, pytest-rerunfailures, pytest-repeat, flaky), ni los subtests que pytest 9 trae de serie, doctests o pytest-bdd.
- No probé hilos, subprocesos ni bucles de eventos async con scope amplio. **DOC** pytest-cov 7.0.0 "Dropped support for subprocesses measurement" ([changelog](https://pytest-cov.readthedocs.io/en/latest/changelog.html)).
- No probé a combinar varios `.coverage` (`coverage combine`, `--cov-append`), que es como saldría una M ejecutada en shards.
- No sé si `--junit-prefix`, `record_xml_attribute`, los contextos estáticos o los directorios con puntos son frecuentes en repos reales.
- La regla de pytest vive en una función privada; solo la comparé en 9.1.1. No sé si cambiará.
- No sé si pytest-cov acabará forzando `ctrace` con `--cov-context`, ni si `sysmon` llegará a soportar contextos.
- No medí el rendimiento de `contexts_by_lineno()` a la escala del SPEC (10.000 tests, 2.000 ficheros).
