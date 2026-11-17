# U02 fail-first oracle

Authority: `.unit/SPEC.md`, including Amendment B. The test command is
`python3 -m unittest discover -s tests/core/schema -t .`.
The boundary under test is `lineage/core/schema.py`; the discovery package is
`tests/core/schema/__init__.py`. Tests use only the Python standard library.

The stub exports `MAX_JSON_BYTES`, `MAX_DEPTH`, `SchemaError`, `strict_loads`
and `validate` with the specification's signatures. Every callable stub body
raises `NotImplementedError("U02 stub")`. No implementation is supplied.
The test harness never treats that exception as an expected successful result.

## Acceptance map

Names below are method names. `StrictJSONTests` is in
`tests/core/schema/test_strict_json.py`; `ValidationTests` is in
`tests/core/schema/test_validation.py`. Every rejection helper checks the
exception class, `code`, `reason`, `pointer`, `schema_pointer` and exact string.

| Acceptance | Test methods |
|---|---|
| A1 | `StrictJSONTests.test_a01_import_and_calls_are_silent_and_independent`; `StrictJSONTests.test_a01_exact_signatures_and_constants` |
| A2 | `StrictJSONTests.test_a02_all_root_types_text_and_bytes`; `ValidationTests.test_a02_valid_nested_values_and_return_none` |
| A3 | `StrictJSONTests.test_a03_syntax_hostility_text_and_bytes`; `StrictJSONTests.test_a03_large_integer_never_leaks_interpreter_valueerror` |
| A4 | `StrictJSONTests.test_a04_exact_byte_cap_accepts_valid_whitespace_padding`; `StrictJSONTests.test_a04_text_over_byte_cap`; `StrictJSONTests.test_a04_byte_size_is_checked_before_utf8_decoding`; `StrictJSONTests.test_a26_byte_cap_rejection` |
| A5 | `StrictJSONTests.test_a05_non_ascii_utf8_accounting`; `StrictJSONTests.test_a05_raw_types_and_subclasses_are_rejected`; `StrictJSONTests.test_a05_oversized_surrogate_text_encodes_strictly_first` |
| A6 | `StrictJSONTests.test_a06_duplicate_names_at_every_depth_and_decoded_equivalence`; `StrictJSONTests.test_a06_sibling_names_and_canonical_unicode_remain_distinct`; `StrictJSONTests.test_a26_nested_duplicate_rejection` |
| A7 | `StrictJSONTests.test_a07_non_finite_tokens_and_overflow`; `StrictJSONTests.test_a07_finite_numbers_and_quoted_spellings`; `StrictJSONTests.test_a03_large_integer_never_leaks_interpreter_valueerror`; `StrictJSONTests.test_a26_non_finite_rejection` |
| A8 | `StrictJSONTests.test_a08_invalid_utf8_and_no_encoding_autodetection`; `StrictJSONTests.test_a08_escaped_and_literal_unpaired_surrogates`; `StrictJSONTests.test_a08_paired_surrogates_and_multilingual_roundtrip` |
| A9 | `StrictJSONTests.test_a09_loader_depth_boundary`; `StrictJSONTests.test_a09_parser_recursion_is_normalized`; `ValidationTests.test_a09_direct_value_depth_boundaries`; `ValidationTests.test_a09_direct_cycles_and_shared_noncycles`; `ValidationTests.test_a09_schema_depth_counts_containers_including_literal_values`; `ValidationTests.test_a09_schema_cycles_point_to_back_edge`; `ValidationTests.test_a09_schema_shared_containers_are_allowed` |
| A10 | `ValidationTests.test_a10_schema_must_be_native_object`; `ValidationTests.test_a10_malformed_scalar_operands`; `ValidationTests.test_a10_invalid_union_required_and_enum_entries`; `ValidationTests.test_a10_child_schemas_and_schema_native_types` |
| A11 | `ValidationTests.test_a11_unreachable_malformed_children_preflight_first`; `ValidationTests.test_a11_non_json_values_in_schema_literals`; `ValidationTests.test_a09_schema_cycles_point_to_back_edge` |
| A12 | `ValidationTests.test_a12_unsupported_keywords_at_root_and_child`; `ValidationTests.test_a12_subschema_additional_properties_is_never_ignored`; `ValidationTests.test_a12_annotations_are_passive_and_string_only` |
| A13 | `ValidationTests.test_a13_all_native_types_no_coercion`; `ValidationTests.test_a13_union_null_and_absent_are_distinct`; `ValidationTests.test_a26_boolean_is_not_integer` |
| A14 | `ValidationTests.test_a14_non_json_python_inputs_everywhere`; `ValidationTests.test_a14_non_string_keys_report_containing_object`; `ValidationTests.test_a14_non_finite_and_unicode_direct_values`; `ValidationTests.test_a14_surrogate_key_reports_key_or_containing_object` |
| A15 | `ValidationTests.test_a15_required_closed_objects_and_optional_preservation`; `ValidationTests.test_a15_empty_required_and_undeclared_required_name` |
| A16 | `ValidationTests.test_a16_recursive_closed_objects_and_full_pointers`; `ValidationTests.test_a26_unknown_key_escaped_pointer` |
| A17 | `ValidationTests.test_a17_permissive_defaults_and_type_specific_applicability` |
| A18 | `ValidationTests.test_a18_array_bounds_inclusive_and_empty_arrays`; `ValidationTests.test_a18_array_items_after_valid_prefix_and_nested_pointers` |
| A19 | `ValidationTests.test_a19_uniqueness_deep_containers_and_numeric_equality`; `ValidationTests.test_a22_huge_int_float_equality_never_overflows` |
| A20 | `ValidationTests.test_a20_string_length_counts_unicode_codepoints`; `ValidationTests.test_a20_pattern_search_no_implicit_flags_or_anchors` |
| A21 | `ValidationTests.test_a21_numeric_bounds_are_inclusive_without_null_coercion`; `ValidationTests.test_a21_invalid_count_length_and_numeric_operands`; `ValidationTests.test_a21_reversed_matching_bounds_are_schema_errors` |
| A22 | `ValidationTests.test_a22_enum_and_const_scalars_containers_and_null`; `ValidationTests.test_a22_enum_distinguishes_bool_and_number_and_is_conjunctive`; `ValidationTests.test_a22_huge_int_float_equality_never_overflows` |
| A23 | `StrictJSONTests.test_a23_raw_error_never_exposes_sensitive_scalar`; `ValidationTests.test_a23_schemaerror_constructor_and_sanitized_string`; `ValidationTests.test_a23_sensitive_scalar_never_leaks_in_diagnostics`; shared diagnostic helpers |
| A24 | `ValidationTests.test_a24_deterministic_required_properties_arrays_and_type_order`; `ValidationTests.test_a24_schema_preflight_unsupported_lexical_and_unreachable_order`; `ValidationTests.test_a24_unresolved_error_precedence_is_still_repeatable`; `ValidationTests.test_a24_ambiguous_schema_keyword_order_is_stable` |
| A25 | `ValidationTests.test_a25_success_failure_and_reused_pattern_schema_are_pure`; `ValidationTests.test_a25_failed_schema_preflight_does_not_mutate_inputs`; isolation guards and identity snapshots |
| A26 | `StrictJSONTests.test_a26_byte_cap_rejection`; `StrictJSONTests.test_a26_nested_duplicate_rejection`; `StrictJSONTests.test_a26_non_finite_rejection`; `ValidationTests.test_a26_boolean_is_not_integer`; `ValidationTests.test_a26_unknown_key_escaped_pointer`; `ValidationTests.test_a26_permissive_doubles_fail_five_assertion_oracles` |

## Amendment B and unresolved choices

Amendment B is a review amendment asking for several decisions; it does not
actually choose between all of its alternatives. Tests enforce the specified
behavior without inventing a contract:

| Issue | Oracle treatment |
|---|---|
| Error selection | Schema preflight precedes assertions; unsupported keywords sort lexically; required names and object/property traversal sort lexically; arrays use index order; declared type precedes type-specific assertions. For unspecified remaining keyword order and full-versus-lazy value checks, require a permitted diagnostic and insertion-order independence. |
| Subschema-valued `additionalProperties` | Reject at its exact keyword pointer with either `invalid_schema` or `unsupported_keyword`, the alternatives left open by Amendment B. |
| Large integer lexemes | Permit exact native-integer acceptance or sanitized `invalid_json`; require text and byte decisions to match. Interpreter exceptions never qualify. |
| Raw subclasses and Unicode precedence | Reject subclasses with `input_type`, reject schema dictionary subclasses with `invalid_schema`, and encode text strictly before byte sizing. Oversized text with a surrogate gives `invalid_unicode`; oversized bytes fail size before decoding. |
| Surrogate keys and schema boundaries | For an invalid direct key, permit the containing object or child pointer as left open by Amendment B. Schema cycles use the back-edge pointer; excessive schema depth uses the first disallowed container. |
| Empty required and numeric equality | Accept empty `required`; compare huge integers and floats without overflow or rounding-based false equality. |
| Operand-location granularity | For duplicate/invalid list operands, permit the keyword or offending entry pointer. For reversed bounds, permit either conflicting bound's pointer. Other tested locations are exact. The base specification does not select one of those granularities. |

The A26 harness temporarily substitutes `json.loads` and an always-accepting
validator in memory, runs the same independent negative methods, and requires
an assertion failure from each, with no errors or skips. Patches restore the
actual boundary before the harness calls it. It neither writes a permissive
implementation nor makes an unimplemented boundary pass.

## Contract reconciliation still required

`docs/INTERFACES.md` defines `SchemaStore`, `decode`, `canonical`, `digest`,
`load_record`, and a different `validate` signature requiring `store` and
`base`. It also allows boolean schemas, references and combinators, treats
`default` as an annotation, uses another loader cap, and restricts integers.
Those requirements conflict with this unit's explicit API and subset.
The tests target the assigned `.unit/SPEC.md`; K0 compatibility is unresolved,
not claimed, and no shared contract or schema file is modified. Reconciliation
belongs to orchestration before these tests can certify K0 compatibility.

No network, process-group operations, signal sending, real sleeps, model calls
or dependency installation occur in the oracle. Source imports remain allowed
while application filesystem/network/environment access and output are guarded.
The mandate is scoped to `.unit/SPEC.md`, Amendment B and the supplied corpus.
