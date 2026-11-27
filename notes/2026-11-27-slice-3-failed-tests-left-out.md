# Slice 3's failed tests left out, for classification, 2026-11-27

As the user asked on 2026-11-27: for each of the 70 failed tests that Slice 3's
replay left out of a selection, in 15 records, what a person needs to classify
it as one of D-021's causes, F, C, N or O, as D-022 applies them. D-031 has the
user classify them after the Next bet's outcome, as D-021 to D-023 did for the
window's 14.

Everything below is FACT, read from the copies of the records in this folder,
`2026-11-27-slice-3-records-<project>.jsonl`; the pilots' CSVs,
`pilot-search/<project>-red-runs.csv`; the pilots' configurations in `pilots/`;
the clones, `~/code/distiller-pilots/<project>`; and each pull request's folder
in the work directory, `~/code/distiller-replay/slice-3/<project>/<pr>/`, where
`junit.xml` is the full run at H, `rerun.xml` the rerun of its failed tests at
H, and `junit-m.xml` the run at M that recorded the coverage. Nothing was run
for this note, and the agent gives no cause and no inference about one: the
classification is the user's (Non-goals). Quotes keep printable ASCII and are
cut. Each test's row at M, with its run's paths with no column and import-only
ones, is in `2026-11-27-slice-3-report.txt`.

## What the 15 runs have in common

- M is the merge-base: in each record, `coverage_commit` is `merge_base`.
- Each pilot's coverage measures its own package alone, the `coverage_source`
  of its configuration: `zhaquirks`, `pydantic`, `mitmproxy` and
  `electricitymap`. A path outside it has no column, and so has a file that M
  does not hold.
- In 11 of the 15 runs no changed path has a column, so no test's row can hold
  one. In the other 4, zha-device-handlers #5200, pydantic #12294 and #12873,
  and electricitymaps-contrib #8515, no test left out holds a changed path in
  its row.
- No pull request changed the file of a test that it left out.
- 10 of pydantic's 11 runs change files under `pydantic-core/`: its Rust code,
  under `pydantic-core/src/`, which the pilot's build compiles into the
  extension module `pydantic_core._pydantic_core`, its Python package, under
  `pydantic-core/python/`, or its tests. None of those paths has a column.
- pydantic's #13345 and #13346 have one head, e75500892f78, and one M,
  5d4a3c8cb356, so their records leave out the same 6 tests; by D-021 each
  record's tests count, 12 in all.
- The 70 hold 59 distinct node ids, 9 of them in more than one record.
- Each of the 70 failed in the full run and again in the rerun. Each passed at
  M but the 2 of electricitymaps-contrib #8515, which failed at M too.

## The runs

| Pilot | PR | Run, start | CI job, in the CSV | H | M | Commits | Verdict | Changed paths, with a column | Left out |
|---|---|---|---|---|---|---|---|---|---|
| zha-device-handlers | #4801 | 22543324927, 2026-03-01T12:22:27Z | failed, steps no longer given | 96c2ece16b93 | becb06881a8a | 2 | missed | 1, 0 | 1 |
| zha-device-handlers | #5200 | 30426367609, 2026-07-29T05:52:37Z | failed in a test step, Run pytest | 8e5e7951096e | b139f815ce3e | 1 | missed | 1, 1 | 2 |
| pydantic | #12294 | 27846495863, 2026-06-19T20:15:18Z | failed in a test step, Run pytest | cd4e21cb72cc | 8dbb2a104f6c | 7 | caught | 49, 1 | 10 |
| pydantic | #12731 | 21199162244, 2026-01-21T06:05:52Z | failed, steps no longer given | e8a47ff1b429 | 2fdcf1c4ec24 | 1 | missed | 2, 0 | 21 |
| pydantic | #12831 | 22212866771, 2026-02-20T05:41:03Z | failed, steps no longer given | 339bee3b1fc7 | e2470302654d | 1 | missed | 4, 0 | 2 |
| pydantic | #12840 | 22252756085, 2026-02-21T07:25:43Z | failed, steps no longer given | 89317f810bbb | 12288b15e6f6 | 2 | missed | 2, 0 | 1 |
| pydantic | #12873 | 22532846438, 2026-03-01T01:03:44Z | failed, steps no longer given | cc66fd9dde22 | 95dc3ee5b191 | 3 | caught | 8, 1 | 13 |
| pydantic | #12944 | 23479201192, 2026-03-24T08:04:10Z | failed, steps no longer given | ae368a88fc2e | 0574aaab3f38 | 1 | missed | 4, 0 | 1 |
| pydantic | #13344 | 28203356016, 2026-06-25T22:03:22Z | failed in a test step, Run pytest | 7eb2b47bfc90 | 5d4a3c8cb356 | 1 | missed | 5, 0 | 2 |
| pydantic | #13345 | 28205637890, 2026-06-25T22:55:10Z | failed in a test step, Run pytest | e75500892f78 | 5d4a3c8cb356 | 1 | caught | 10, 0 | 6 |
| pydantic | #13346 | 28205802564, 2026-06-25T22:59:17Z | failed in a test step, Run pytest | e75500892f78 | 5d4a3c8cb356 | 1 | caught | 10, 0 | 6 |
| pydantic | #13502 | 30155047750, 2026-07-25T10:45:53Z | failed, steps no longer given | 76a864be17c1 | a2a6577d4c32 | 1 | missed | 3, 0 | 1 |
| pydantic | #13506 | 30216803342, 2026-07-26T19:25:05Z | failed in a test step, Run pytest | 08e699549e98 | a2a6577d4c32 | 1 | missed | 2, 0 | 1 |
| mitmproxy | #8424 | 34000151028, 2026-09-06T00:00:38Z | failed in a test step, Run tox -e py3.12 | f9210c5c867d | 2ac5b089d953 | 3 | missed | 3, 0 | 1 |
| electricitymaps-contrib | #8515 | 27272163882, 2026-06-10T11:11:08Z | failed in a test step, Run tests | 0cbc973a4854 | 19804e15f27b | 10 | caught | 195, 9 | 2 |

## zha-device-handlers

### #4801, missed

From the merge-base to H, 2 commits: "Apply pre-commit auto fixes"; "Add quirk for Tuya TS0726 multi-gang switch (Beseed/Moes)". The changed paths:

| Path | Change | Column |
|---|---|---|
| `zhaquirks/tuya/ts0726.py` | +206 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_tuya_spells.py::test_tuya_spell` | `tests/test_tuya_spells.py:79` | failure: AssertionError: assert 2 == 1 + where 2 = <AsyncMock id='140018861397232'>.call_count | failure, the same | passed |

`tests/test_tuya_spells.py` builds `ENCHANTED_QUIRKS` when it is imported: every
quirk in zigpy's `DEVICE_REGISTRY.registry_v1` that is an `EnchantedDevice`,
so every such quirk that `zhaquirks` registers when imported,
`zhaquirks/tuya/ts0726.py`'s among them at #4801's head. `test_tuya_spell`
configures each such device with `zigpy.zcl.Cluster.request` mocked, and asserts
that the mock was called as many times as the device has spells enabled.
#4801's only change adds `zhaquirks/tuya/ts0726.py`, which M does not hold, and
the test's row at M is `zhaquirks/__init__.py` and `zhaquirks/tuya/__init__.py`.

### #5200, missed

From the merge-base to H, 1 commit: "Add network LED switch for Sonoff S60ZBTPF smart plug". The changed paths:

| Path | Change | Column |
|---|---|---|
| `zhaquirks/sonoff/s60zbtpf.py` | +28 -0 | yes |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_sonoff_s60zbtpf.py::test_sonoff_plug_quirk_selection[8195-False]` | `tests/test_sonoff_s60zbtpf.py:43` | failure: assert True is False + where True = isinstance(<zhaquirks.sonoff.s60zbtpf.SonoffS60OnOff object at 0x717577e25b20>, SonoffS60OnOff) | failure, the same | passed |
| `tests/test_sonoff_s60zbtpf.py::test_sonoff_plug_quirk_selection[8196-False]` | `tests/test_sonoff_s60zbtpf.py:43` | failure: assert True is False + where True = isinstance(<zhaquirks.sonoff.s60zbtpf.SonoffS60OnOff object at 0x717577e274d0>, SonoffS60OnOff) | failure, the same | passed |

`test_sonoff_plug_quirk_selection` builds a device with
`zigpy_device_from_v2_quirk("SONOFF", "S60ZBTPF", ...)` for each firmware version
of its parameters, and asserts whether its clusters are `SonoffS60OnOff` and
`SonoffS60ElectricalMeasurement`; the two left out are the firmware versions
8195 and 8196, `S60_POWER_FIX_FW_VERSION` and one above it, for which it expects
neither. #5200's only change, `zhaquirks/sonoff/s60zbtpf.py`, has a column, and
both tests' row at M is `zhaquirks/device.py` alone.

## pydantic

`tests/test_docs.py` parametrizes `test_docs_examples` with
`find_examples(str(DOCS_ROOT))`, the code examples of the markdown files under
`docs/`, and `test_docstrings_examples` with `find_examples(str(SOURCES_ROOT))`,
those of the docstrings under `pydantic/`, so each node id names the file and
the lines of its example; each test runs its example and fails when what the
example prints differs from what the file writes, `Print output changed`. No
pull request below changes a file that such a node id names.

`test_public_internal`, in `tests/test_exports.py`, globs `pydantic/*.py` and
`pydantic/experimental/*.py`, and executes each module that is not imported
yet, through `importlib.util.spec_from_file_location` and
`spec.loader.exec_module`, giving up on a module only at an `ImportError`.

### #12294, caught

From the merge-base to H, 7 commits: "Merge remote-tracking branch 'origin/main' into dh/core-inline-definitions"; "import definition inlining patch from 'pydantic-core'"; "Merge branch 'main' into dh/core-inline-definitions", and 4 more. The changed paths:

49 paths, 1 of them with a column: `pydantic/_internal/_generate_schema.py`. Those with no column, by folder, the largest: `pydantic-core/src/validators/` 46, `pydantic-core/src/validators/shared/` 1, `pydantic-core/tests/validators/` 1.

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/benchmarks/test_model_eq.py::test_model_eq_extra_forbid` | `tests/benchmarks/test_model_eq.py:20` | failure: AttributeError: __init__ | failure, the same | passed |
| `tests/test_deprecated.py::test_construct` | `tests/test_deprecated.py:714` | failure: Failed: DID NOT WARN. No warnings of type (<class 'pydantic.warnings.PydanticDeprecatedSince20'>,) were emitted. Emitted warnings: []. | failure, the same | passed |
| `tests/test_deprecated.py::test_copy_and_set_values` | `tests/test_deprecated.py:750` | failure: AttributeError: __init__ | failure, the same | passed |
| `tests/test_deprecated.py::test_dict` | `tests/test_deprecated.py:668` | failure: AttributeError: __init__ | failure, the same | passed |
| `tests/test_deprecated.py::test_get_value` | `tests/test_deprecated.py:760` | failure: AttributeError: __init__ | failure, the same | passed |
| `tests/test_deprecated.py::test_json` | `tests/test_deprecated.py:674` | failure: AttributeError: __init__ | failure, the same | passed |
| `tests/test_deprecated.py::test_json_schema` | `tests/test_deprecated.py:723` | failure: AttributeError: __init__ | failure, the same | passed |
| `tests/test_deprecated.py::test_parse_file` | `tests/test_deprecated.py:699` | failure: Failed: DID NOT WARN. No warnings of type (<class 'pydantic.warnings.PydanticDeprecatedSince20'>,) were emitted. Emitted warnings: []. | failure, the same | passed |
| `tests/test_deprecated.py::test_parse_obj` | `tests/test_deprecated.py:690` | failure: Failed: DID NOT WARN. No warnings of type (<class 'pydantic.warnings.PydanticDeprecatedSince20'>,) were emitted. Emitted warnings: []. | failure, the same | passed |
| `tests/test_deprecated.py::test_validate` | `tests/test_deprecated.py:736` | failure: Failed: DID NOT WARN. No warnings of type (<class 'pydantic.warnings.PydanticDeprecatedSince20'>,) were emitted. Emitted warnings: []. | failure, the same | passed |

### #12731, missed

From the merge-base to H, 1 commit: "fix: use validator name instead of tag in tagged union error location". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/validators/union.rs` | +2 -2 | none |
| `pydantic-core/tests/validators/test_tagged_union.py` | +42 -4 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_discriminated_union.py::test_callable_discriminated_union_recursive` | `tests/test_discriminated_union.py:1667` | failure: AssertionError: assert [{'ctx': {'di...member', ...}] == [{'ctx': {'di...member', ...}] At index 0 diff: {'type': 'invalid_union_member', 'l | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_annotated_union` | `tests/test_discriminated_union.py:248` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[discriminator-discriminator]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[discriminator-field_discriminator]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[discriminator-field_str]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[field_discriminator-discriminator]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[field_discriminator-field_discriminator]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[field_discriminator-field_str]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[field_str-discriminator]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[field_str-field_discriminator]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_discriminated_union_validation[field_str-field_str]` | `tests/test_discriminated_union.py:144` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('pet', | failure, the same | passed |
| `tests/test_discriminated_union.py::test_generic` | `tests/test_discriminated_union.py:502` | failure: AssertionError: Regex pattern did not match. Regex: 'Container\\[str\\]\\nresult\\.Success\\.data' Input: "1 validation error for Container[ | failure, the same | passed |
| `tests/test_discriminated_union.py::test_sequence_discriminated_union_validation` | `tests/test_discriminated_union.py:1397` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('items' | failure, the same | passed |
| `tests/test_discriminated_union.py::test_sequence_discriminated_union_validation_with_validator` | `tests/test_discriminated_union.py:1437` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': ('items' | failure, the same | passed |
| `tests/test_discriminated_union.py::test_union_in_submodel` | `tests/test_discriminated_union.py:1165` | failure: assert [{'ctx': {'ex...odel1'", ...}] == [{'ctx': {'ex...odel1'", ...}] At index 0 diff: {'type': 'literal_error', 'loc': ('submodel', 'SubM | failure, the same | passed |
| `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:200-237]` | `tests/test_docs.py:190` | failure: Failed: Print output changed code: --- before +++ after @@ -229,208 +229,208 @@ Model(pet={'pet_type': 'dog'}, n=1) except ValidationError a | failure, the same | passed |
| `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:413-468]` | `tests/test_docs.py:190` | failure: Failed: Print output changed code: --- before +++ after @@ -451,430 +451,430 @@ Model(pet={'pet_type': 'cat', 'color': 'red'}, n='1') except | failure, the same | passed |
| `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:497-589]` | `tests/test_docs.py:190` | failure: Failed: Print output changed code: --- before +++ after @@ -565,518 +565,518 @@ DiscriminatedModel.model_validate({'x': {'x': {'x': 1}}}) ex | failure, the same | passed |
| `tests/test_docs.py::test_docstrings_examples[pydantic/types.py:3196-3221]` | `tests/test_docs.py:166` | failure: Failed: Print output changed code: --- before +++ after @@ -3213,3204 +3213,3204 @@ Model.model_validate(invalid_json_data) except Validatio | failure, the same | passed |
| `tests/test_types.py::test_json_value` | `tests/test_types.py:6708` | failure: AssertionError: assert [{'input': El...-json-value'}] == [{'input': El...-json-value'}] At index 0 diff: {'type': 'invalid-json-value', 'loc | failure, the same | passed |
| `tests/test_validate_call.py::test_annotated_discriminator` | `tests/test_validate_call.py:801` | failure: AssertionError: assert [{'input': {'...': 'missing'}] == [{'input': {'...': 'missing'}] At index 0 diff: {'type': 'missing', 'loc': (0, 'Dog | failure, the same | passed |

### #12831, missed

From the merge-base to H, 1 commit: "fix: exclude tag from error location for callable discriminators". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/validators/union.rs` | +13 -3 | none |
| `pydantic-core/tests/validators/test_tagged_union.py` | +1 -1 | none |
| `tests/test_discriminated_union.py` | +60 -2 | none |
| `tests/test_types.py` | +1 -1 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:497-589]` | `tests/test_docs.py:190` | failure: Failed: Print output changed code: --- before +++ after @@ -565,518 +565,518 @@ DiscriminatedModel.model_validate({'x': {'x': {'x': 1}}}) ex | failure, the same | passed |
| `tests/test_docs.py::test_docstrings_examples[pydantic/types.py:3194-3219]` | `tests/test_docs.py:166` | failure: Failed: Print output changed code: --- before +++ after @@ -3211,3202 +3211,3202 @@ Model.model_validate(invalid_json_data) except Validatio | failure, the same | passed |

### #12840, missed

From the merge-base to H, 2 commits: "Fix: Added AliasPath support for nested models in ElegantClass"; "Fix: Added AliasPath support for nested models in ElegantClass". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic/models.py` | +14 -0 | none |
| `pydantic/pydantic.py` | +15 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_exports.py::test_public_internal` | `tests/test_exports.py:33` | failure: NameError: name 'BaseModel' is not defined | failure, the same | passed |

#12840 adds `pydantic/models.py` and `pydantic/pydantic.py`, which M does not
hold, so neither has a column.

### #12873, caught

From the merge-base to H, 3 commits: "revert self schema"; "fix pydantic core test"; "Support return as is serializer". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/python/pydantic_core/__init__.py` | +2 -0 | none |
| `pydantic-core/python/pydantic_core/core_schema.py` | +21 -0 | none |
| `pydantic-core/src/serializers/shared.rs` | +2 -0 | none |
| `pydantic-core/src/serializers/type_serializers/mod.rs` | +1 -0 | none |
| `pydantic-core/src/serializers/type_serializers/return_as_is.rs` | +60 -0 | none |
| `pydantic-core/tests/serializers/test_return_as_is.py` | +30 -0 | none |
| `pydantic-core/tests/test_schema_functions.py` | +2 -1 | none |
| `pydantic/_internal/_generate_schema.py` | +3 -0 | yes |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_deprecated.py::test_json_schema` | `tests/test_deprecated.py:723` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_chain_schema` | `tests/test_json_schema.py:5968` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_deprecated_classes_json_schema[BaseModel]` | `tests/test_json_schema.py:6438` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_deprecated_classes_json_schema[pydantic-dataclass]` | `tests/test_json_schema.py:6438` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_json_schema_arguments_v3_aliases` | `tests/test_json_schema.py:7024` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_json_schema_arguments_v3_var_kwargs_unpacked_typed_dict_not_required` | `tests/test_json_schema.py:6997` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_json_schema_arguments_v3_var_kwargs_unpacked_typed_dict_required` | `tests/test_json_schema.py:6968` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_schema_no_definitions` | `tests/test_json_schema.py:1720` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_json_schema.py::test_union_format_primitive_type_array_deduplicated` | `tests/test_json_schema.py:7199` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_type_adapter.py::test_core_schema_respects_defer_build[schema-DataClassModel-config4]` | `tests/test_type_adapter.py:599` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_type_adapter.py::test_core_schema_respects_defer_build[schema-DynamicModel-config2]` | `tests/test_type_adapter.py:599` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_type_adapter.py::test_core_schema_respects_defer_build[schema-Model-config0]` | `tests/test_type_adapter.py:599` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |
| `tests/test_types_typeddict.py::test_typeddict_core_schema_no_cls_extra_config` | `tests/test_types_typeddict.py:1072` | failure: TypeError: No method for generating JsonSchema for core_schema.type='return-as-is' (expected: GenerateJsonSchema.return_as_is_schema) | failure, the same | passed |

### #12944, missed

From the merge-base to H, 1 commit: "Fix model_dump to include extra fields from __pydantic_extra__". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/serializers/fields.rs` | +11 -9 | none |
| `pydantic-core/src/serializers/type_serializers/model.rs` | +12 -1 | none |
| `pydantic-core/tests/serializers/test_model.py` | +96 -4 | none |
| `tests/test_main.py` | +122 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_serialize.py::test_serialize_extra_allow_subclass_1` | `tests/test_serialize.py:45` | failure: AssertionError: assert {'inner': {'x': 1, 'y': 2}} == {'inner': {'x': 1}} Differing items: {'inner': {'x': 1, 'y': 2}} != {'inner': {'x': 1} | failure, the same | passed |

### #13344, missed

From the merge-base to H, 1 commit: "fix: reset SerCheck level for collection item serializers in union context". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/serializers/type_serializers/dict.rs` | +5 -2 | none |
| `pydantic-core/src/serializers/type_serializers/list.rs` | +3 -1 | none |
| `pydantic-core/src/serializers/type_serializers/set_frozenset.rs` | +4 -1 | none |
| `pydantic-core/src/serializers/type_serializers/tuple.rs` | +1 -0 | none |
| `tests/test_type_adapter.py` | +48 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_serialize.py::test_subclass_support_unions_with_forward_ref` | `tests/test_serialize.py:1210` | failure: AssertionError: assert {'items': [{}, {}]} == {'items': [{'...'bar_id': 3}]} Differing items: {'items': [{}, {}]} != {'items': [{'bar_id': 1 | failure, the same | passed |
| `tests/test_types.py::test_union_compound_types` | `tests/test_types.py:5526` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'str' - serialized value may not be as expected [fi | failure, the same | passed |

### #13345, caught

From the merge-base to H, 1 commit: "fix: prevent inner unions in collections from incorrectly using top-level strict checking". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/serializers/extra.rs` | +6 -0 | none |
| `pydantic-core/src/serializers/type_serializers/dataclass.rs` | +1 -0 | none |
| `pydantic-core/src/serializers/type_serializers/dict.rs` | +8 -2 | none |
| `pydantic-core/src/serializers/type_serializers/list.rs` | +5 -1 | none |
| `pydantic-core/src/serializers/type_serializers/model.rs` | +1 -0 | none |
| `pydantic-core/src/serializers/type_serializers/set_frozenset.rs` | +6 -1 | none |
| `pydantic-core/src/serializers/type_serializers/tuple.rs` | +2 -0 | none |
| `pydantic-core/src/serializers/type_serializers/union.rs` | +1 -1 | none |
| `pydantic-core/tests/serializers/test_union.py` | +53 -0 | none |
| `tests/test_type_adapter.py` | +48 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/benchmarks/test_model_serialization.py::test_complex_model_serialization` | `tests/benchmarks/test_model_serialization.py:23` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'int' - serialized value may not be as expected [fi | failure, the same | passed |
| `tests/benchmarks/test_model_serialization.py::test_model_json_serialization` | `tests/benchmarks/test_model_serialization.py:38` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'int' - serialized value may not be as expected [fi | failure, the same | passed |
| `tests/test_root_model.py::test_root_model_dump_with_base_model[BR]` | `tests/test_root_model.py:468` | failure: AssertionError: assert [{}, {}, {'value': 'abc'}] == [1, 2, {'value': 'abc'}] At index 0 diff: {} != 1 Use -v to get more diff | failure, the same | passed |
| `tests/test_root_model.py::test_root_model_dump_with_base_model[RB]` | `tests/test_root_model.py:468` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'RModel' - serialized value may not be as expected | failure, the same | passed |
| `tests/test_serialize.py::test_subclass_support_unions_with_forward_ref` | `tests/test_serialize.py:1210` | failure: AssertionError: assert {'items': [{}, {}]} == {'items': [{'...'bar_id': 3}]} Differing items: {'items': [{}, {}]} != {'items': [{'bar_id': 1 | failure, the same | passed |
| `tests/test_types.py::test_union_compound_types` | `tests/test_types.py:5526` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'str' - serialized value may not be as expected [fi | failure, the same | passed |

### #13346, caught

From the merge-base to H, 1 commit: "fix: prevent inner unions in collections from incorrectly using top-level strict checking". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/serializers/extra.rs` | +6 -0 | none |
| `pydantic-core/src/serializers/type_serializers/dataclass.rs` | +1 -0 | none |
| `pydantic-core/src/serializers/type_serializers/dict.rs` | +8 -2 | none |
| `pydantic-core/src/serializers/type_serializers/list.rs` | +5 -1 | none |
| `pydantic-core/src/serializers/type_serializers/model.rs` | +1 -0 | none |
| `pydantic-core/src/serializers/type_serializers/set_frozenset.rs` | +6 -1 | none |
| `pydantic-core/src/serializers/type_serializers/tuple.rs` | +2 -0 | none |
| `pydantic-core/src/serializers/type_serializers/union.rs` | +1 -1 | none |
| `pydantic-core/tests/serializers/test_union.py` | +53 -0 | none |
| `tests/test_type_adapter.py` | +48 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/benchmarks/test_model_serialization.py::test_complex_model_serialization` | `tests/benchmarks/test_model_serialization.py:23` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'int' - serialized value may not be as expected [fi | failure, the same | passed |
| `tests/benchmarks/test_model_serialization.py::test_model_json_serialization` | `tests/benchmarks/test_model_serialization.py:38` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'int' - serialized value may not be as expected [fi | failure, the same | passed |
| `tests/test_root_model.py::test_root_model_dump_with_base_model[BR]` | `tests/test_root_model.py:468` | failure: AssertionError: assert [{}, {}, {'value': 'abc'}] == [1, 2, {'value': 'abc'}] At index 0 diff: {} != 1 Use -v to get more diff | failure, the same | passed |
| `tests/test_root_model.py::test_root_model_dump_with_base_model[RB]` | `tests/test_root_model.py:468` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'RModel' - serialized value may not be as expected | failure, the same | passed |
| `tests/test_serialize.py::test_subclass_support_unions_with_forward_ref` | `tests/test_serialize.py:1210` | failure: AssertionError: assert {'items': [{}, {}]} == {'items': [{'...'bar_id': 3}]} Differing items: {'items': [{}, {}]} != {'items': [{'bar_id': 1 | failure, the same | passed |
| `tests/test_types.py::test_union_compound_types` | `tests/test_types.py:5526` | failure: UserWarning: Pydantic serializer warnings: PydanticSerializationUnexpectedValue(Expected 'str' - serialized value may not be as expected [fi | failure, the same | passed |

### #13502, missed

From the merge-base to H, 1 commit: "Raise TypeError for invalid serializer index keys". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/serializers/type_serializers/function.rs` | +5 -4 | none |
| `pydantic-core/tests/serializers/test_functions.py` | +15 -0 | none |
| `tests/test_serialize.py` | +15 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_docs.py::test_docstrings_examples[pydantic/functional_serializers.py:96-144]` | `tests/test_docs.py:175` | failure: pydantic_core._pydantic_core.PydanticSerializationError: Error calling function 'convert_to_utc': TypeError: 'index_key' must be an 'int', ' | failure, the same | passed |

### #13506, missed

From the merge-base to H, 1 commit: "Raise explicit 'TypeError' on invalid 'index_key' serialization wrap handler". The changed paths:

| Path | Change | Column |
|---|---|---|
| `pydantic-core/src/serializers/type_serializers/function.rs` | +8 -3 | none |
| `tests/test_serialize.py` | +18 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `tests/test_docs.py::test_docstrings_examples[pydantic/functional_serializers.py:96-144]` | `tests/test_docs.py:175` | failure: pydantic_core._pydantic_core.PydanticSerializationError: Error calling function 'convert_to_utc': TypeError: 'index_key' is expected to be a | failure, the same | passed |

## mitmproxy

### #8424, missed

From the merge-base to H, 3 commits: "Show HTTP reason phrases for HTTP/2 and HTTP/3 via lookup table (issue #7694)"; "Add statusCodes.ts with HTTP reason phrase lookup table (issue #7694)"; "Add web/gen/status_codes.py to generate TypeScript status code mapping". The changed paths:

| Path | Change | Column |
|---|---|---|
| `web/gen/status_codes.py` | +86 -0 | none |
| `web/src/js/components/FlowView/HttpMessages.tsx` | +12 -1 | none |
| `web/src/js/statusCodes.ts` | +75 -0 | none |

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `test/mitmproxy/tools/web/test_app.py::test_generated_files[filename4]` | `test/mitmproxy/tools/web/test_app.py:40` | failure: File "/home/sergi/code/distiller-replay/slice-3/mitmproxy/8424/head/web/gen/status_codes.py", line 18 match = re.search(r"RESPONSES\s*=\s*\{ | failure, the same | passed |

`test_generated_files` is parametrized over `web/gen/*.py`, globbed when the
module is collected, and imports each as `web.gen.<name>` and awaits its
`make()`, then compares what it gives with the file that the generator writes.
#8424 adds `web/gen/status_codes.py`, and the full run's failure points at its
line 18. `web/` is outside the pilot's `coverage_source`.

## electricitymaps-contrib

### #8515, caught

From the merge-base to H, 10 commits: "feat(events): degrade gracefully on overlapping or ambiguous end_datetimes"; "Merge remote-tracking branch 'origin/master' into vik/end_date_POC"; "Merge remote-tracking branch 'origin/master' into vik/end_date_POC", and 7 more. The changed paths:

195 paths, 9 of them with a column: `electricitymap/contrib/lib/models/event_lists.py`, `electricitymap/contrib/lib/models/events.py`, `electricitymap/contrib/lib/tests/test_event_lists.py`, `electricitymap/contrib/lib/tests/test_events.py`, `electricitymap/contrib/parsers/BE.py`, `electricitymap/contrib/parsers/ENTSOE.py`, `electricitymap/contrib/parsers/IEMOP.py`, `electricitymap/contrib/parsers/TAIPOWER.py`, `electricitymap/contrib/parsers/tests/test_ENTSOE.py`. Those with no column, by folder, the largest: `electricitymap/contrib/parsers/tests/__snapshots__/` 51, `electricitymap/contrib/parsers/tests/__snapshots__/test_ONS/` 33, `electricitymap/contrib/parsers/tests/__snapshots__/test_MD/` 19, `electricitymap/contrib/parsers/tests/__snapshots__/test_ES/` 13, `electricitymap/contrib/parsers/tests/__snapshots__/test_ENTSOE/` 9, `electricitymap/contrib/parsers/tests/__snapshots__/test_FO/` 9.

| Node id | Code at H | Full run at H | Rerun | At M |
|---|---|---|---|---|
| `electricitymap/contrib/parsers/tests/test_JP_KN.py::test_snapshot_get_image_text_on_real_kepco_gifs` | `electricitymap/contrib/parsers/tests/test_JP_KN.py:41` | failure: FileNotFoundError: [Errno 2] No such file or directory: 'tesseract' | failure, the same | failure: FileNotFoundError: [Errno 2] No such file or directory: 'tesseract' |
| `electricitymap/contrib/parsers/tests/test_JP_KN.py::test_snapshot_reactor_rows_capacity_and_operation_percentage` | `electricitymap/contrib/parsers/tests/test_JP_KN.py:61` | failure: FileNotFoundError: [Errno 2] No such file or directory: 'tesseract' | failure, the same | failure: FileNotFoundError: [Errno 2] No such file or directory: 'tesseract' |

Both tests run the OCR of `JP_KN.get_image_text`, which their docstrings call a
Pillow and tesseract pipeline, over fixture images, with `urlopen` mocked.
Their row at M is `electricitymap/contrib/parsers/JP_KN.py` and the test file,
and no changed path of #8515 has `JP_KN` in it.

## The classification

For the user to fill, one row for each failed test left out of each record, as
D-021 counts them; D-022 says how a failure through another test, and one with
several paths, are classified.

| # | Run | Node id | Cause | Why |
|---|---|---|---|---|
| 1 | zha-device-handlers #4801 | `tests/test_tuya_spells.py::test_tuya_spell` | | |
| 2 | zha-device-handlers #5200 | `tests/test_sonoff_s60zbtpf.py::test_sonoff_plug_quirk_selection[8195-False]` | | |
| 3 | zha-device-handlers #5200 | `tests/test_sonoff_s60zbtpf.py::test_sonoff_plug_quirk_selection[8196-False]` | | |
| 4 | pydantic #12294 | `tests/benchmarks/test_model_eq.py::test_model_eq_extra_forbid` | | |
| 5 | pydantic #12294 | `tests/test_deprecated.py::test_construct` | | |
| 6 | pydantic #12294 | `tests/test_deprecated.py::test_copy_and_set_values` | | |
| 7 | pydantic #12294 | `tests/test_deprecated.py::test_dict` | | |
| 8 | pydantic #12294 | `tests/test_deprecated.py::test_get_value` | | |
| 9 | pydantic #12294 | `tests/test_deprecated.py::test_json` | | |
| 10 | pydantic #12294 | `tests/test_deprecated.py::test_json_schema` | | |
| 11 | pydantic #12294 | `tests/test_deprecated.py::test_parse_file` | | |
| 12 | pydantic #12294 | `tests/test_deprecated.py::test_parse_obj` | | |
| 13 | pydantic #12294 | `tests/test_deprecated.py::test_validate` | | |
| 14 | pydantic #12731 | `tests/test_discriminated_union.py::test_callable_discriminated_union_recursive` | | |
| 15 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_annotated_union` | | |
| 16 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[discriminator-discriminator]` | | |
| 17 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[discriminator-field_discriminator]` | | |
| 18 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[discriminator-field_str]` | | |
| 19 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[field_discriminator-discriminator]` | | |
| 20 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[field_discriminator-field_discriminator]` | | |
| 21 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[field_discriminator-field_str]` | | |
| 22 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[field_str-discriminator]` | | |
| 23 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[field_str-field_discriminator]` | | |
| 24 | pydantic #12731 | `tests/test_discriminated_union.py::test_discriminated_union_validation[field_str-field_str]` | | |
| 25 | pydantic #12731 | `tests/test_discriminated_union.py::test_generic` | | |
| 26 | pydantic #12731 | `tests/test_discriminated_union.py::test_sequence_discriminated_union_validation` | | |
| 27 | pydantic #12731 | `tests/test_discriminated_union.py::test_sequence_discriminated_union_validation_with_validator` | | |
| 28 | pydantic #12731 | `tests/test_discriminated_union.py::test_union_in_submodel` | | |
| 29 | pydantic #12731 | `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:200-237]` | | |
| 30 | pydantic #12731 | `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:413-468]` | | |
| 31 | pydantic #12731 | `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:497-589]` | | |
| 32 | pydantic #12731 | `tests/test_docs.py::test_docstrings_examples[pydantic/types.py:3196-3221]` | | |
| 33 | pydantic #12731 | `tests/test_types.py::test_json_value` | | |
| 34 | pydantic #12731 | `tests/test_validate_call.py::test_annotated_discriminator` | | |
| 35 | pydantic #12831 | `tests/test_docs.py::test_docs_examples[docs/concepts/unions.md:497-589]` | | |
| 36 | pydantic #12831 | `tests/test_docs.py::test_docstrings_examples[pydantic/types.py:3194-3219]` | | |
| 37 | pydantic #12840 | `tests/test_exports.py::test_public_internal` | | |
| 38 | pydantic #12873 | `tests/test_deprecated.py::test_json_schema` | | |
| 39 | pydantic #12873 | `tests/test_json_schema.py::test_chain_schema` | | |
| 40 | pydantic #12873 | `tests/test_json_schema.py::test_deprecated_classes_json_schema[BaseModel]` | | |
| 41 | pydantic #12873 | `tests/test_json_schema.py::test_deprecated_classes_json_schema[pydantic-dataclass]` | | |
| 42 | pydantic #12873 | `tests/test_json_schema.py::test_json_schema_arguments_v3_aliases` | | |
| 43 | pydantic #12873 | `tests/test_json_schema.py::test_json_schema_arguments_v3_var_kwargs_unpacked_typed_dict_not_required` | | |
| 44 | pydantic #12873 | `tests/test_json_schema.py::test_json_schema_arguments_v3_var_kwargs_unpacked_typed_dict_required` | | |
| 45 | pydantic #12873 | `tests/test_json_schema.py::test_schema_no_definitions` | | |
| 46 | pydantic #12873 | `tests/test_json_schema.py::test_union_format_primitive_type_array_deduplicated` | | |
| 47 | pydantic #12873 | `tests/test_type_adapter.py::test_core_schema_respects_defer_build[schema-DataClassModel-config4]` | | |
| 48 | pydantic #12873 | `tests/test_type_adapter.py::test_core_schema_respects_defer_build[schema-DynamicModel-config2]` | | |
| 49 | pydantic #12873 | `tests/test_type_adapter.py::test_core_schema_respects_defer_build[schema-Model-config0]` | | |
| 50 | pydantic #12873 | `tests/test_types_typeddict.py::test_typeddict_core_schema_no_cls_extra_config` | | |
| 51 | pydantic #12944 | `tests/test_serialize.py::test_serialize_extra_allow_subclass_1` | | |
| 52 | pydantic #13344 | `tests/test_serialize.py::test_subclass_support_unions_with_forward_ref` | | |
| 53 | pydantic #13344 | `tests/test_types.py::test_union_compound_types` | | |
| 54 | pydantic #13345 | `tests/benchmarks/test_model_serialization.py::test_complex_model_serialization` | | |
| 55 | pydantic #13345 | `tests/benchmarks/test_model_serialization.py::test_model_json_serialization` | | |
| 56 | pydantic #13345 | `tests/test_root_model.py::test_root_model_dump_with_base_model[BR]` | | |
| 57 | pydantic #13345 | `tests/test_root_model.py::test_root_model_dump_with_base_model[RB]` | | |
| 58 | pydantic #13345 | `tests/test_serialize.py::test_subclass_support_unions_with_forward_ref` | | |
| 59 | pydantic #13345 | `tests/test_types.py::test_union_compound_types` | | |
| 60 | pydantic #13346 | `tests/benchmarks/test_model_serialization.py::test_complex_model_serialization` | | |
| 61 | pydantic #13346 | `tests/benchmarks/test_model_serialization.py::test_model_json_serialization` | | |
| 62 | pydantic #13346 | `tests/test_root_model.py::test_root_model_dump_with_base_model[BR]` | | |
| 63 | pydantic #13346 | `tests/test_root_model.py::test_root_model_dump_with_base_model[RB]` | | |
| 64 | pydantic #13346 | `tests/test_serialize.py::test_subclass_support_unions_with_forward_ref` | | |
| 65 | pydantic #13346 | `tests/test_types.py::test_union_compound_types` | | |
| 66 | pydantic #13502 | `tests/test_docs.py::test_docstrings_examples[pydantic/functional_serializers.py:96-144]` | | |
| 67 | pydantic #13506 | `tests/test_docs.py::test_docstrings_examples[pydantic/functional_serializers.py:96-144]` | | |
| 68 | mitmproxy #8424 | `test/mitmproxy/tools/web/test_app.py::test_generated_files[filename4]` | | |
| 69 | electricitymaps-contrib #8515 | `electricitymap/contrib/parsers/tests/test_JP_KN.py::test_snapshot_get_image_text_on_real_kepco_gifs` | | |
| 70 | electricitymaps-contrib #8515 | `electricitymap/contrib/parsers/tests/test_JP_KN.py::test_snapshot_reactor_rows_capacity_and_operation_percentage` | | |

## The share, and what section 13.2 can conclude

D-021: for k file dependencies among n, the share is marginal when the
one-sided 95% Clopper-Pearson upper bound of k out of n is below 10%, not
marginal when 1 minus the upper bound of n - k out of n is above 10%, and
undecided otherwise. By `clopper_pearson_upper` (FACT, 2026-11-27):

| Failed tests left out | Marginal with | Not marginal with |
|---|---|---|
| Slice 3's 70 | at most 2 F | 12 F or more |
| those and the window's 14, which hold no F (D-023), 84 | at most 3 F | 14 F or more |

Between, the share is undecided. As D-021 says of the window's, these are not
independent draws: #13346's 6 are #13345's, 9 of #12731's 21 are
parametrizations of one test, and other node ids recur across records, so the
bound is narrower than they warrant. Which of the two counts the share takes is
the user's to decide, with the classification.

## Where each fact comes from

- The records: verdict, head, merge-base, M, the tests left out with their
  pairs, node ids and rows, the paths with no column and import-only.
- The CSVs: each run's id, start and the CI job's outcome.
- The clones: the commits from the merge-base to H, `git log`; the changed
  paths, `git diff --numstat --no-renames` from the merge-base to H; and the
  tests' code at H, `git show`.
- The work directory: each test's outcome and message in `junit.xml`,
  `rerun.xml` and `junit-m.xml`.
- The bounds: `clopper_pearson_upper` of `src/distiller/report.py`.
