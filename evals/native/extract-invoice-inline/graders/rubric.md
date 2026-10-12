---
type: llm
weight: 2
focus: last_message
---
Judge the extracted VALUES, which live in the JSON object named `data` if there is one, otherwise in the top-level JSON object. An `evidence` object, if present, holds verbatim quotes copied from the invoice; quotes are allowed to contain currency symbols, labels and spacing, and they are not the values being judged.

PASS if all of the following hold for the values:
- `invoice_number` is "INV-40213", `vendor` is "Cobalt Street Coffee Roasters", `invoice_date` is "2026-09-14" (the invoice date, not the 9 September order date), `currency` is "GBP".
- `total` is the plain number 412.2 (or 412.20), not a string and not the 343.50 subtotal.
- `po_number` is null, and if the message has a `missing` list, `po_number` appears in it.
- No value is invented (no PO number, due date or other field filled in that the invoice does not state).

FAIL if any value above is wrong or invented, if `total` in the values is a string, or if no JSON object is present.
