# Pull requests and commits

## Commit messages

- Write the subject line in the imperative mood and in sentence case.
- Keep the subject line at 72 characters or fewer, with no final period. Example: `Add the unicast pass to the sender task`.
- Leave one blank line after the subject line.
- In the body, state why the change exists. Wrap the body at 72 characters.
- If an ADR governs the change, name its filename in the body.
- Keep one logical change per commit.

## PR title

Write the PR title in the same form as a commit subject line.

## PR body

A PR body is a record of a decision, not a summary of a diff. Complete the six fields in this order. Do not add, remove, or rename a field. If information for a field is missing, ask the founder. Do not invent it.

```markdown
## What changed
<one or two lines>

## Why
<the decision this PR embodies>

## Alternatives considered
<what else was on the table, and why it lost>

## ADR
<filename, or None>

## Measurements
<every number labeled. Omit this section if the PR states no numbers>

## Reusable asset
<DECISION_LOG.md entry name, or None>
```

The empty marker is `None`. The Fortune Labs template uses a dash as the empty marker, and this repository writes `None` because the writing standard forbids the em dash.

## Field rules

1. **What changed.** State the effect of the diff in one or two lines.
2. **Why.** State the decision, not a restatement of the code. If the PR adds or changes a MISRA deviation, name the deviation ID here.
3. **Alternatives considered.** Name the real options and why each one lost. Never leave this field empty. One line is enough for a small decision. Do not label options with letters or numbers.
4. **ADR.** Name the governing ADR filename. If the change is consequential and no ADR exists, state that an ADR must exist before merge. Do not guess a filename. Otherwise write `None`.
5. **Measurements.** Label every number `[borrowed: <source>]` or `[measured: <run or link>]`. A number from a Bolis run carries `[measured: <run ID or record link>]`. State an unreproduced number as pending.
6. **Reusable asset.** If the PR touches an asset with a `DECISION_LOG.md`, name the log entry. Otherwise write `None`.

Write the body in the writing standard (`writing.md`).

## Review of a PR body

Name each missing piece specifically:

- No alternative, even for a small decision.
- `None` in the ADR field for a consequential change.
- A number without a label.
- A number that blends a borrowed part and a measured part without a derivation.
- A touched asset with a `DECISION_LOG.md` that the body does not name.
