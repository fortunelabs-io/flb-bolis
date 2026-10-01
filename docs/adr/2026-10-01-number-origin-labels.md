# Origin labels for numbers in Bolis artifacts

Date: 2026-10-01
Status: Accepted

## Context

The Bolis v0 specification (v0.3) requires an origin label beside every number in the report. The existing label set in Fortune Labs documents describes the origin of claims, and it was not built for the numbers in a run record. Those numbers come from four origins. A node counts or reads some of them during the run. Bolis sets some of them, such as the requested transmit power. The report script computes some of them, such as a loss ratio or an interval. The user types some of them, such as the distance between the nodes. If every number carried `[measured]`, a distance typed by the user would read as a measured value. Numbers from a Bolis report also appear in public replies, which carry origin labels under the Social Media Communication Language SOP. If nothing was decided, the report script would have no rule for labeling a number.

## Alternatives considered

- Map every record number onto the existing claim labels.
- Add three labels for numbers, scoped to Bolis artifacts.
- Add three labels for numbers to the label set of all Fortune Labs documents.
- Add two labels for numbers, and exempt configured values from labels.

## Decision

Bolis artifacts use four labels for numbers. `[measured]` keeps its existing meaning: a value counted or read on a node during the run. `[configured]` marks a value that Bolis set. `[derived]` marks a value computed only from `[measured]` values. `[declared]` marks a value that the user typed and that Bolis did not check. The scope is the run record, the report, and any number from a Bolis report that appears in a public reply. Each report carries a legend of the four labels. The label set of other Fortune Labs documents stays unchanged.

## Consequences

- A reader can tell a counted value from a typed value.
- Claim labels in documents and number labels in Bolis artifacts exist side by side.
- A public reply that quotes a Bolis number carries its number label and a link to the run record.
- A value computed from a `[configured]` or `[declared]` input does not carry `[derived]`.
- Such a value carries the label of that input.
- The run record format stores a label for every number.
- The adoption of these labels in other Fortune Labs documents needs a separate ADR at the level of the shared label set.
- Thinkbook section 9 and specification section 6 state these labels in their next versions.
