# Record lifecycle

Two kinds of Bolis record carry a status: a decision record in `docs/adr/` and a deviation record in `docs/compliance/misra-deviations.md`. This file states how the status of each one changes.

This file settles nothing new. It states in the repository the conditions that `docs/adr/2026-10-01-misra-c-2012-coding-baseline.md` and `docs/compliance/misra-deviations.md` already carry, so that a reader of a checkout finds them in one place.

## Decision records

A decision record carries one of three statuses:

- `Proposed`. The record states a decision that is not settled.
- `Accepted`. The record states a settled decision.
- `Superseded by [YYYY-MM-DD-new-slug.md](./YYYY-MM-DD-new-slug.md)`. A later record replaced this one.

A record reaches `Accepted` only through a decision taken outside the change that proposes it. A merge of the proposing change is not that decision. A record reaches `main` while it carries `Proposed`, and the status changes only when that decision is taken.

A record that carries `Accepted` is never edited. To change a settled decision, write a new record. Then set the status line of the old record to name the new one. Every chain of records stays walkable forward to the current record.

## Deviation records

A deviation record carries one of three statuses: `Proposed`, `Approved`, or `Withdrawn`.

A record reaches `Approved` under the same condition as a decision record: a decision taken outside the change that proposes it.

`docs/compliance/misra-deviations.md` states the fields of a deviation record, the form of the suppression comment, and the records themselves.

## Code that depends on a record

Code that relies on a record at `Proposed` does not merge.

Writing that code is permitted once the decision is taken. Merging it waits for the status line, so that no change acts as its own acceptance.
