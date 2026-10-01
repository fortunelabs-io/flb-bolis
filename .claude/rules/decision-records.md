# Decision records

These rules follow the Fortune Labs ADR standard.

## The ADR test

Answer yes or no before any other step. A change needs an ADR only if at least one condition is true:

1. **Hard to reverse.** A reversal carries a real cost, such as a change to the run record format, the control protocol, the frame header, a public API, or the minimum ESP-IDF version.
2. **Non-obvious reasoning.** A future reader of the diff alone would have to rederive why one real option beat the others.
3. **Permanent or reused asset.** The change affects an asset that is permanent or reused, such as the corpus metric, the run record format, the coding baseline, or the release process.

If no condition is true, the reasoning stays in the commit message or the PR body. A rename, a plain bug fix, or a refactor with no visible change needs no ADR. If the case is unclear, name the condition that comes closest and explain why.

## Format

- Location: `adr/`.
- Filename: `YYYY-MM-DD-short-slug.md`, with no sequence number and no category prefix.
- Top lines: the title, then `Date: YYYY-MM-DD` and `Status: <status>`.
- Exactly four sections, in this order: Context, Alternatives considered, Decision, and Consequences.
- Context states what triggered the decision and what happens if nothing is decided. Write it in the past tense.
- Alternatives considered names the real options, one line each. Write the options without labels such as "Option A".
- Decision states what was chosen. Write it in the present tense and the active voice.
- Consequences states what the decision commits to, what it rules out, and what to watch. One claim per line.
- Write every section in the writing standard (`writing.md`).

## Status and superseding

- Never edit an ADR after its status reaches `Accepted`.
- To change a decision, write a new ADR. Then change the status line of the old ADR to `Superseded by [YYYY-MM-DD-new-slug.md](./YYYY-MM-DD-new-slug.md)`.
- Keep every chain of ADRs walkable forward to the current one.
- Claude drafts an ADR with `Status: Proposed`. Only the founder sets `Accepted`.

## DECISION_LOG.md

- Give each reused template, module, or calibration package a `DECISION_LOG.md` at its root.
- Each entry is one table row with six fields: Date, Version, Type (`added`, `changed`, `deprecated`, or `fixed`), Change (one line), ADR (the filename, or `None`), and Author.
- Append new entries at the bottom, oldest to newest.
- Move the log together with its asset.
