# 1. ¿Cumple cada arquitectura la spec?

Las tres comparten §0.1–0.3, así que primero lo común, luego lo propio de cada una.

**Común a las tres (cumple):**
- El orden de problemas coincide con la lista de la spec: «the checkout (not a git checkout, then shallow); H; the base branch; the coverage (unusable, then `coverage-not-ancestor`, then `no-shared-lines`); the full run's JUnit…; the rerun file…; the floor configuration». A lo recorre en `evaluate.evaluate`, B en `load.load_run`, C en `app.evaluate_command`.
- Leer los bytes del JUnit antes del recorrido para la clave («`head` and `junit_sha256` are the run's key») sin decidir rechazo temprano: correcto en las tres.
- Dedup y salidas: «it appends its record unless one with the same key, reason and input is already there, and exits with 3» — las tres tienen `has_rejected` con esa firma; K3, K7, K10, K11 encajan.

**Común a las tres (interpretaciones no dichas por la spec, no contradicciones):**
- `--rootdir` absoluto o con `..` → error de uso. La spec solo dice «pytest's rootdir, relative to the repository root, if it is not the repository root».
- `--pr` «ASCII digits, above 0» y la resolución de `--base` son reglas añadidas, benignas.
- Ninguna interfaz fija dónde vive la frase obligatoria del report: «The report says that its figures belong to the all-affected selector». Trivial, pero sin casa asignada.

**A:** cumple. Sus desviaciones son de organización, no de conducta: el propio informe admite que «four modules (`evaluate`, `coverage_at_m`, `junit`, `floor`) choose reasons, inputs and messages», frente al requisito estricto «never quote what a file holds» y los textos por motivo; A puede cumplirlos, solo reparte la verificación.

**B:** cumple. El corte shell/puro no altera ninguna salida; `record`/`record_file` cubren «reads the record file… creates it when it appends».

**C:** cumple sobre el papel, con dos reservas:
- El puerto codifica en silencio una respuesta que la spec no fija: `read_bytes` → «None: no such file» frente a `read_text` → «None: cannot be read». La spec distingue «missing or is not well-formed XML» (junit) de «cannot be read or has an invalid pattern» (floor), pero nunca dice qué es un JUnit existente e ilegible; el puerto decide (excepción → salida 1).
- El cumplimiento del módulo más arriesgado (`workspace.py`, que según su tabla produce K1–K12) descansa en «adapter tests» que nombra pero no diseña; los tests en memoria no lo ejecutan.

Las tres difieren por igual los ocho huecos de §7 —decisión explícita del informe («Each one is left open»)—, coherente con una spec que los deja abiertos. No encontré contradicciones de conducta en ninguna.

# 2. ¿Qué problema de A resuelve la estructura extra de B y de C?

**B resuelve dos problemas reales y uno anticipado:**
- *Real, de segundo orden:* centralizar el vocabulario de motivos/entradas/mensajes. La spec dedica un párrafo entero a los mensajes («They name inputs by their path, and commits as given, and never quote what a file holds», el consejo de `no-shared-lines`, «names the configuration file and the pattern's line number»); en A esa verificación se reparte en cuatro módulos. Y ni siquiera es completo: el aviso de ya-grabado y el error de no-registro siguen en `cli`.
- *Real pero modesto:* los bytes exactos de K1/K2 como test puro. En A el ensamblado vive en `evaluate.py` y solo se prueba extremo a extremo. Modesto porque A ya prueba `pair_of`, `select`, `judge`, `encode`, `decode` con literales (lo dice su propia tabla de costes), y porque los [core] de rechazo siguen necesitando repositorio real en B: «the problem order still needs one repository state per problem, as in A», y «K1 depends on both halves, so it needs a pure test and an end-to-end one».
- *Anticipado:* crecimiento («later slices (the solver, file tracing) grow `evaluate.py`»). La spec los saca de Slice 1: «Not in Slice 1, though not ruled out: the solver, shards and order (§5)… file tracing (§6)».

**C sobre B:** solo resuelve velocidad y aislamiento de los tests [core] en memoria. La spec exige rendimiento de la herramienta, no de su suite («takes under 60 s and under 1 GB»), así que el beneficio es anticipado; y el riesgo que crea es real: «a fake that lies can hide a [core] defect», cuando «the traps found for this note… all live in `GitWorkspace`, which in-memory tests never run». C acaba necesitando tres familias de tests («its own tests against real repositories, plus contract tests») para cubrir lo que B cubre con dos.

Nota decisiva: las tablas de §5 muestran que los tres exponen la misma superficie core —la elección no cambia la exposición al riesgo, solo la ergonomía del test.

# 3. Defectos de cada una

**A:**
- `evaluate.py` hace cuatro cosas: clave, orden de problemas, matching/selección/veredicto, campos del registro. El informe lo admite: «a change to a selection rule edits the file that also holds the problem order and the record».
- La excepción `Rejected` se define en `records.py` y la lanzan los lectores de entradas: el vocabulario no tiene casa.
- «One module per input, each reading and interpreting its input» no se cumple en su propio listado: ninguna función lee el rerun (`parse_junit` recibe bytes; `evaluate` recibe `junit_bytes`, pero los bytes del rerun no tienen dueño).
- `coverage_at_m.py` mezcla E/S (copia temporal, cabecera SQLite) con el mapeo puro de paths al árbol de M; el mapeo no se prueba sin fichero.
- `cli.py` acumula argumentos, dos comandos, decisiones de append/exit, stderr y catch-all.

**B:**
- Quince ficheros para dos comandos; `record` y `record_file` parten un concepto por la línea shell/puro con nombres casi idénticos.
- `RunInputs` es un paquete ancho (once campos) que acopla cada módulo puro con cada entrada a la vez.
- La frontera pierde: `coverage_io` importa `node_id_of` de `matrix`; la dirección de la dependencia existe porque el corte la exige, no porque el problema la pida.
- `load.py` concentra clave, orden, todos los mensajes y `RunInputs` —cohesivo, pero es el punto único de fallo de los cuatro vocabularios.

**C:**
- El falso duplica la especificación de conducta del puerto; su mantenimiento honesto cuesta las tres familias de tests.
- Contratos `None` inconsistentes entre `read_bytes` y `read_text` (arriba), con una interpretación de la spec incrustada y sin documentar contra ella.
- `Workspace` fusiona tres mundos externos (subproceso git, sistema de ficheros, API de coverage) en un puerto; «every new query changes the port, the real workspace and the fake».
- `app.evaluate_command` reconcentra lo que A concentraba en `evaluate.py` y parte el «then» [core] del append entre quien decide (`app`) y quien ejecuta (`cli`): K3/K10 («the record file is left byte for byte as it was») depende de que dos módulos coincidan.

**Riesgos:** no encuentro niveles mal asignados. El análisis de §5.1 es correcto («once a key has an evaluated record, a corrected tool cannot replace it»), el report es medium con razón (recomputable), y la costura decide/actúa de C está bien marcada como core en ambos lados —el defecto es la costura, no el nivel. **Modelo de datos:** completo para lo fijado; sus silencios coinciden exactamente con los huecos de §7 (`Test.row` no decide si una fila vacía es fila; `RawCoverage` no tiene sitio para un fichero medido sin líneas).

# 4. Efectos irreversibles y huecos

**Efectos de §5.3:**
1. *Escritura en el coverage de entrada:* real si cierra la lectura del código (sin verificar: `_start_using()` borra el fichero; `read()` escribe el esquema; SQLite abre un fichero de 0 bytes). Si es cierto, el diagnóstico aplica la regla de la propia spec («A module with an irreversible effect that no [core] example observes means a missing example») y el ejemplo candidato es válido: fijaría la mitigación de la copia.
2. *Texto en el log:* el efecto es real, pero el informe se pasa medio hueco. Afirma «No example observes the messages that end in exit 1», y la spec sí observa uno de los dos: «names the file and the line number in its error message, without quoting the line, and exits with 1». Solo el mensaje del fallo inesperado queda sin observar; el hueco es más estrecho de lo dicho.
3. *Red por git:* el comportamiento es plausible (sin verificar: lazy-fetch de diff/ls-tree/merge-base en clon parcial), pero con el Deployment de la spec («The checkout has the whole history (`fetch-depth: 0`)») el clon parcial está fuera de alcance: riesgo anticipado salvo cambio de deployment.
4. *Append truncado / creación del fichero:* análisis correcto — una línea sin newline rompe todo report posterior con salida 1, «loud, not wrong», consistente con «a line… that ends in a carriage return or lacks its newline»; crear el fichero está dicho en prosa, solo falta ejemplo. Bien priorizado.

No encuentro efectos irreversibles adicionales de peso (la copia temporal ya la mencionan; el stdout del report es la misma clase que el stderr).

**Huecos que faltan:**
- *Conflictos entre registros rechazados con la misma clave y `pr` distinto* (misma cabeza+junit en dos PRs): la regla de conflicto solo cubre evaluados («If two evaluated runs' records have the same key but differ») y la dedup de rechazados es (clave, motivo, entrada).
- *«Falta» frente a «existe pero ilegible»* para junit/rerun/coverage (directorio, permisos): la spec dice «missing» para junit/coverage y «cannot be read» para floor; el tercer caso no tiene asignación — y el puerto de C ya lo responde en silencio.
- *Finales de línea del floor config:* la spec blinda el registro contra CRLF pero no al floor; «spaces at either end of a line are not part of its pattern» no quita `\r`, así que un fichero CRLF produce patrones con CR final que casan con nada, sin rechazo.
- *Merge-base ambiguo:* el informe lo anota en §6 («it is unspecified which best one is output») pero no como hueco; hace el diff —y el registro— dependiente de la versión de git, y el invariante «the two record files end up byte-identical» no acota entornos.

De los ocho de §7, todos son reales; el 5 (internal error de pytest contando como fallo no medido → caught) es el más afilado porque replica la distorsión que la spec rechaza para collection errors («evaluated, it would always count as caught») —sin verificar la forma del testcase en pytest 9.1.1—; el 4 solo muerde con writers distintos de pytest, y la spec fija que el JUnit lo escribe el propio pytest del PR.

# 5. Elección

A. Las tres implementan la misma conducta y los riesgos de primer orden —los que el propio informe llama trampas: coverage borrando ficheros, flags de git, defaults de defusedxml, el registro exacto al byte— deben probarse contra las herramientas reales en cualquier opción, de modo que el núcleo puro de B y el falso de C compran comodidad de test, no cumplimiento. La única ventaja de B que esta spec fuerza de verdad —una sola casa para motivos, entradas y mensajes— es de segundo orden y no justifica seis módulos más ni un `RunInputs` ancho para una herramienta de dos comandos con el formato de registro congelado; C compra velocidad de test anticipada al precio de un falso que debe imitar justo los comportamientos con más probabilidad de estar mal. Elijo A, aceptando como coste vigilado que el vocabulario de mensajes repartido en cuatro módulos obliga a revisar «never quote what a file holds» en cuatro sitios.
