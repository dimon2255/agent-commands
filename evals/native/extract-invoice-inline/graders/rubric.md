---
type: llm
weight: 2
focus: last_message
---
PASS if the final message contains a JSON object whose values all come from the pasted text, a field that the text does not state is null and is listed as missing, and the total is a plain number with the currency in its own field. FAIL if any value is invented, the total is a string with a currency symbol, or no JSON is present.
