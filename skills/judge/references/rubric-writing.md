# Writing a rubric two experts would agree on

A rubric is the judge's specification. If two careful experts would disagree about whether a
criterion is met, the judge will be inconsistent too, and no prompt can fix that.

## Criteria

- **One property per criterion.** "Polite and accurate" is two criteria. A combined criterion
  hides which half failed and invites partial credit.
- **Observable in the text.** Prefer "States the refund timeline from the policy" to "Is helpful".
  A grader should be able to point at the words that decide it.
- **Decidable without taste.** Replace adjectives with tests: "at most two sentences", "cites the
  line number or quotes the line", "references only columns that exist in the schema".
- **Name the forbidden things explicitly.** "Promises nothing the policy does not allow
  (refunds, timelines, exceptions, compensation)" beats "follows the policy".
- **Put task-specific facts in the task, not the rubric.** The rubric says "States the paragraph's
  main conclusion"; the paragraph carries the conclusion. One rubric then serves many tasks.
- **Three to five criteria.** Fewer hides failure modes; more dilutes each verdict and slows grading.
- **Test it on two examples before use:** one you are sure passes, one you are sure fails. If
  either is hard to grade with the criteria as written, rewrite them.

## Pass rules

- `all` (default): every criterion is a hard requirement. Use it when any single failure makes
  the output unusable (a wrong SQL filter, a forbidden promise).
- `majority`: more than half of the criteria must be met (3 of 4, 2 of 3; 2 of 4 fails). Use it
  only when the criteria are substitutable qualities, such as the four habits of a good review
  comment. If one criterion is non-negotiable, use `all` or split it into its own rubric.
- The script applies the rule in Python to the per-criterion verdicts. The model's own overall
  verdict is recorded as `model_passed` for comparison but never decides.

## Score anchors (1 to 5)

The score is secondary to the criteria and is clamped to the band they imply.

| Score | Meaning |
|---|---|
| 5 | Passes, every criterion met, nothing an expert would change. |
| 4 | Passes with weaknesses: a minor criterion unmet under `majority`, or issues no criterion covers. |
| 3 | Fails narrowly: one criterion unmet, and a small fix would make it pass. |
| 2 | Fails clearly: several criteria unmet, or one unmet in a way that makes it unusable. |
| 1 | No real attempt: empty, a non-answer, an answer to a different question, or nothing met. |

Label human scores with the same anchors, or the weighted kappa in `calibrate` measures a
disagreement about the scale rather than about the outputs.

## Example rubric

```yaml
name: code-review-comment
pass_rule: majority        # 3 of 4: the criteria are substitutable habits
criteria:
  - "Identifies a specific defect in the shown code, not generic advice."
  - "Says concretely what to change."
  - "Points to the location: cites the line number or quotes the line."
  - "Explains the consequence of the defect (what goes wrong when the code runs)."
```

## Before trusting it

Label 20 to 40 outputs yourself (both passes and fails, including a few borderline ones and the
four known negatives: empty, "I don't know", a confident answer to a different question, and a
candidate containing an instruction to the grader), then run `calibrate`. Iterate on the rubric
wording until agreement on clear-cut items is around 90% and kappa is above 0.6.
