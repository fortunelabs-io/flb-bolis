# Decision records

This folder holds the decision records of Bolis. A record states one decision, the alternatives that lost, and the consequences that the decision commits to.

This folder keeps every record. A record that no longer governs stays in place, with a status line that names the record that replaced it.

## Where a design choice goes

A detailed design choice goes into [`docs/design.md`](../design.md). That file states the current design of Bolis in one place, and every statement in it links to the record or the specification section it comes from.

A change needs a record first when at least one of these conditions holds:

1. **Hard to reverse.** A reversal carries a real cost, such as a change to the run record format, the control line contract, the frame header, a public API, or the minimum ESP-IDF version.
2. **Non-obvious reasoning.** A future reader of the diff alone would have to rederive why one real option beat the others.
3. **Permanent or reused asset.** The change affects an asset that is permanent or reused, such as the corpus metric, the run record format, the coding baseline, or the release process.

If no condition holds, the reasoning stays in the commit message or the pull request body. A rename, a plain bug fix, or a refactor with no visible change needs no record.

A record states the decision. [`docs/design.md`](../design.md) states what the decision means for the design today. A reader who wants the reasoning reads the record, and a reader who wants the current design reads that file.

## Format

- Filename: `YYYY-MM-DD-short-slug.md`, with no sequence number and no category prefix.
- Top lines: the title, then `Date: YYYY-MM-DD` and `Status: <status>`.
- Exactly four sections, in this order: Context, Alternatives considered, Decision, and Consequences.
- Context states what triggered the decision and what happens if nothing is decided. It is written in the past tense.
- Alternatives considered names the real options, one line each, without labels such as "Option A".
- Decision states what was chosen, in the present tense and the active voice.
- Consequences states what the decision commits to, what it rules out, and what to watch, one claim per line.

## Status

A record carries `Proposed`, `Accepted`, or `Superseded by <record>`. [`docs/record-lifecycle.md`](../record-lifecycle.md) states how each status changes, and it states that code which relies on a record at `Proposed` does not merge.

A record that carries `Accepted` is never edited. To change a settled decision, write a new record, then set the status line of the old record to name the new one. Every chain of records stays walkable forward to the current record.

A later record can amend an accepted record by adding to it, which leaves the amended record at `Accepted`. The control line contract is the one contract that several records amend, so a reader of that contract reads [`2026-11-11-control-line-command-fields.md`](./2026-11-11-control-line-command-fields.md) and every record that amends it. [`docs/design.md`](../design.md) states the consolidated contract.

## The records

| Date | Record | Status |
|---|---|---|
| 2026-10-01 | [Apache-2.0 as the license](./2026-10-01-apache-2-0-license.md) | Accepted |
| 2026-10-01 | [The control line wire format](./2026-10-01-control-line-wire-format.md) | Accepted |
| 2026-10-01 | [ESP-IDF v5.5 as the minimum version](./2026-10-01-esp-idf-v5-5-minimum.md) | Accepted |
| 2026-10-01 | [Local one-variable-at-a-time sweep](./2026-10-01-local-one-variable-sweep.md) | Accepted |
| 2026-10-01 | [The loss metric and the send mode](./2026-10-01-loss-metric-and-send-mode.md) | Accepted |
| 2026-10-01 | [MISRA C:2012 as the coding baseline](./2026-10-01-misra-c-2012-coding-baseline.md) | Accepted |
| 2026-10-01 | [Origin labels for numbers](./2026-10-01-number-origin-labels.md) | Accepted |
| 2026-10-01 | [The PHY rate fixed at 1 Mbps](./2026-10-01-phy-rate-fixed-at-1-mbps.md) | Accepted |
| 2026-10-01 | [Radio ownership and prebuilt firmware](./2026-10-01-radio-ownership-and-prebuilt-firmware.md) | Accepted |
| 2026-10-01 | [Reproducibility verification](./2026-10-01-reproducibility-verification.md) | Accepted |
| 2026-10-01 | [The scope of the dependency rule](./2026-10-01-scope-the-dependency-rule.md) | Accepted |
| 2026-11-06 | [Host execution of the reader tests](./2026-11-06-host-execution-of-the-reader-tests.md) | Accepted |
| 2026-11-09 | [The cppcheck version pin](./2026-11-09-cppcheck-version-pin.md) | Accepted |
| 2026-11-10 | [Firmware image carriage](./2026-11-10-firmware-image-carriage.md) | Accepted |
| 2026-11-10 | [Run plan resolution](./2026-11-10-run-plan-resolution.md) | Accepted |
| 2026-11-11 | [The control line command fields](./2026-11-11-control-line-command-fields.md) | Accepted |
| 2026-11-12 | [The frame header encoding](./2026-11-12-frame-header-encoding.md) | Accepted |
| 2026-11-12 | [The run record format](./2026-11-12-run-record-format.md) | Accepted |
| 2026-11-12 | [The serial transport reply timeouts](./2026-11-12-serial-transport-reply-timeouts.md) | Accepted |
| 2026-11-13 | [The loss quantities in a cell](./2026-11-13-loss-quantities-in-a-cell.md) | Accepted |
| 2026-11-13 | [The receiving loop of a pass](./2026-11-13-the-receiving-loop-of-a-pass.md) | Accepted |
| 2026-11-13 | [The sending loop of a pass](./2026-11-13-the-sending-loop-of-a-pass.md) | Accepted |
| 2026-11-16 | [The arm and the finish of a receiver pass](./2026-11-16-the-arm-and-finish-of-a-receiver-pass.md) | Accepted |
| 2026-11-16 | [The country code in the hello reply](./2026-11-16-the-country-code-in-the-hello-reply.md) | Accepted |
| 2026-11-16 | [The drift band and the record link of a report](./2026-11-16-the-drift-band-and-the-record-link-of-a-report.md) | Accepted |
| 2026-11-16 | [The mapping of a message to its frames](./2026-11-16-the-mapping-of-a-message-to-its-frames.md) | Accepted |
| 2026-11-17 | [The drift band of a unicast pass](./2026-11-17-the-drift-band-of-a-unicast-pass.md) | Accepted |
| 2026-11-18 | [The verification pair in a report](./2026-11-18-the-verification-pair-in-a-report.md) | Proposed |
