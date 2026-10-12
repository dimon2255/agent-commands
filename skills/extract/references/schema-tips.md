# Writing a good extraction schema

The schema is the prompt that matters most: it decides what the model looks for, which of
several candidates it picks, and what "absent" looks like. Most extraction errors trace back
to a schema that left one of those open.

## Make absence expressible

- Every field that a document might not state should allow `null`:
  `{"type": ["string", "null"]}`, `{"type": ["number", "null"]}`.
- Keep such fields in `required`. "Required and nullable" means the answer always says
  something about the field: a value, or an explicit `null` that lands in `missing`.
- A field that is not nullable forces a value. If the text does not state it, the extractor
  reports a validation error rather than guessing, so make a field non-nullable only when
  every document is guaranteed to state it (a ticket header priority, say).
- Lists that can be empty (`action_items`, `line_items`) are plain arrays, not nullable: `[]`
  means "the text has none", which is a real answer.

## Name the right candidate in `description`

Documents carry look-alikes. The description is where you say which one you want:

```json
"invoice_date": {"type": ["string", "null"], "format": "date",
  "description": "Date the invoice was issued; not the order, delivery or due date"},
"total": {"type": ["number", "null"],
  "description": "Final amount due, including tax and after discounts"},
"due_date": {"type": ["string", "null"], "format": "date",
  "description": "Payment due date, only when a calendar date is printed"}
```

"Only when a calendar date is printed" is what stops a due date being computed from "Net 30".

## Closed sets are enums, with definitions

```json
"category": {"enum": ["billing", "shipping", "technical", "account", "other"],
  "description": "billing: charges, refunds, invoices. account: login, password, profile. other: anything else"}
```

- Define each value in the description, so a near-miss word in the text ("our accounting
  department") is mapped by meaning, not by spelling. Always include an `other`.
- For a nullable enum, put `null` in the list and leave out `type`:
  `{"enum": ["USD", "EUR", null]}`. The structured-output grammar rejects `enum` next to a
  type array such as `["string", "null"]`; the extractor drops the `type` for you, but writing
  it this way keeps the schema honest.

## Types that carry the normalisation

- Amounts: `number`, with the currency in its own field. Never a string like `"$1,234.50"`.
- Dates: `string` with `format: date` (ISO 8601). The validator checks it; the grammar cannot.
- Identifiers: `string`, optionally with a `pattern` (`"^TCK-[0-9]{5}$"`) that the validator
  enforces and the repair pass corrects.
- Booleans for yes/no facts (`refund_requested`), with a description that says what counts as
  yes. A non-nullable boolean reads as "false unless the text says so"; if "unknown" is a
  possible answer, make it `["boolean", "null"]`.

## Keep graded fields closed-form

Free text such as a summary cannot be checked exactly and invites paraphrase. Prefer closed
fields (IDs, dates, amounts, enums, names). When you need free text, keep it short and do not
compare it by exact match in an eval.

## Limits of the structured-output grammar (probed on claude-opus-5-5, 2026-10-12)

| Schema feature | Grammar | What the extractor does |
|---|---|---|
| `pattern`, `format`, `minLength` | accepted (enforcement not verified) | dropped from the grammar, enforced by the validator |
| `minimum` (`maximum`, `multipleOf` not probed) | rejected (400) | dropped from the grammar, enforced by the validator |
| `oneOf` | rejected | becomes `anyOf`; exclusivity checked by the validator |
| object without `additionalProperties: false` | rejected | set to `false` on every object |
| `additionalProperties` as a schema (free-form map) | rejected | closed to `false`; model maps as a list of `{key, value}` |
| more than 16 nullable or union-typed fields | rejected | not worked around: split the schema |
| `$defs` and `$ref` | accepted | kept, hoisted to the response root |
