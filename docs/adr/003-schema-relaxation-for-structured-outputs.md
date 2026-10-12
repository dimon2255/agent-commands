# ADR 003: Relax the schema for the output grammar, validate against the full schema

**Status:** Accepted, 2026-10-12

## Context

The `extract` skill asks Claude for JSON that matches a schema the user supplies. The
Messages API's structured outputs (`output_config.format` with `type: json_schema`)
guarantee the response parses and matches the schema's shape, but the grammar accepts
only a subset of JSON Schema. While building the skill against `claude-opus-5-5` the
following were rejected by the API (400) or ignored:

- rejected: a schema-valued `additionalProperties`, `oneOf`, `minimum`, an object without
  `additionalProperties: false`, and `enum` beside a nullable type;
- rejected: more than 16 nullable fields in one response object;
- ignored or unsupported: `pattern`, `format`, `minLength`, `maxLength`, `minItems`,
  `maxItems`, `multipleOf`, `uniqueItems`, `exclusiveMinimum`, `exclusiveMaximum`.

Users write schemas with exactly those keywords (`format: date`, `pattern` on an ID,
`enum` with a null option), and they expect them to be enforced.

## Decision

Keep two schemas. The **relaxed** schema (a deep copy with the unsupported keywords
stripped, `oneOf` rewritten to `anyOf`, `$defs` hoisted to the root) is sent to the API
as the output format. The **full** user schema is enforced afterwards in Python with
`jsonschema.Draft202012Validator` and a `FormatChecker`. A validation failure triggers one
repair call that shows the model the violations; a second failure is returned as-is with
the remaining errors listed, never hidden. Evidence quotes are one plain string per
top-level field, which keeps the response object inside the API's limits.

The same rule applies to the eval harness: the built-in `json_schema` grader runs with a
`FormatChecker`, so a date written as "March 3rd, 2026" fails `schema_valid` even though
the API's grammar would have accepted it.

## Consequences

- Positive: users keep their schemas unchanged; the API guarantees shape, Python
  guarantees constraints; the repair loop is bounded and its outcome is observable
  (`repairs`, `validation_errors_after_repair`).
- Negative: two validation passes and an extra prompt turn in the rare repair case; the
  stripped-keyword list is tied to what the API accepted on 2026-10-12 and must be
  revisited when the structured-outputs grammar changes.
- The limits above are recorded here because they are not obvious from the SDK docs and
  cost the builder several API round-trips to discover.
