# The run record format, its version, and the place it stores an origin label

Date: 2026-11-12
Status: Proposed

## Context

`schema/` held one placeholder README. That README named the planned file, the JSON Schema of the run record format, and stated that a corpus reuses the format, so a change to the format needs a decision record. The Python coding standard required the host to write every run record against that schema, and it called a record that fails the schema an error. No schema existed, so the run record writer had nothing to write against, and the report had no input.

Thinkbook section 9 named the six sections of a record: `run`, `firmware`, `nodes`, `setup`, `declared`, and `cells`. It named the file `bolis-<run id>.json`. The accepted record [2026-11-11-control-line-command-fields.md](./2026-11-11-control-line-command-fields.md) added the `cell` and `stats` fields to the `cells` section, and it stated which values a host labels `[measured]` and which it labels `[configured]`. The accepted record [2026-10-01-reproducibility-verification.md](./2026-10-01-reproducibility-verification.md) made a verification pair of two runs the test of a reproduced result, and thinkbook section 9 gave the `run` section the run ID of the other run of that pair. The field inventory was therefore settled across those sources, and the format that carries it was not.

The accepted record [2026-10-01-number-origin-labels.md](./2026-10-01-number-origin-labels.md) stated that the run record format stores a label for every number. It did not state where a label sits beside a number. It also stated that a number from a Bolis report that appears in a public reply carries its label, so a number leaves the record and keeps the label.

Specification section 7 kept the host offline, stated that a record stores no MAC address, and stated that a record carries no device identifier that the user did not add.

Two records at `Status: Proposed` on 2026-11-12 deferred four questions to this record. The reply timeout record left the host keeping a partial record when a run stops. The frame header encoding record left the place the host writes a record, the text form of a run ID, and the behavior of a host that cannot read that place.

If nothing was decided, the run record writer would fix the format by accident, and a corpus would hold records in a shape that no file defines.

## Alternatives considered

- A label declared in the schema for each field, which the number origin labels record rules out, because that record stores a label for every number.
- A label in a sibling key, such as `packets_received_label`, which doubles the key space and lets a key and its label drift apart.
- A label in one map per section, which a number loses when a reply quotes that number alone.
- A label suffixed onto the key name, which collides with the rule that a key naming a quantity ends with its unit.
- One version key shared with `proto` or with `manifest_version`, which ties three contracts that change on their own schedules.
- No version key, which leaves a reader of an old record guessing which format it follows.
- A hand-written checker in the host, which gives the format two definitions that can disagree.
- Validation in the tests alone, which lets a malformed record reach a corpus from an installed release.
- The run ID as hexadecimal text, which adds a second form of a value that fits a JSON integer exactly.
- A record that holds the valid attempt of a cell alone, which hides the attempt that a node reset invalidated.
- A record written only at the end of a run, which loses every cell when a run stops.

## Decision

This record fixes the format, its version, the place a label sits, and the file. It does not restate the field inventory. Thinkbook section 9 and the command fields record name the fields, and `schema/run-record.schema.json` states them normatively.

**The schema.** The schema lives at `schema/run-record.schema.json` and follows the JSON Schema 2020-12 dialect. It carries `$schema` and `$id`. The schema is the normative statement of the format, and this record states the rules that shape it.

**The version.** A record carries `record_version`, an integer that names the version of this format, and the first version is 1. That key is separate from `proto`, which names the control line contract, and from `manifest_version`, which names the firmware manifest layout, because the three contracts change on their own schedules. The firmware image carriage record set that pattern.

**A label beside a number.** Every number that states a quantity of the run is an object with two keys, `value` and `label`. `label` holds `measured`, `configured`, `derived`, or `declared`.

```json
"packets_received": {"value": 1987, "label": "measured"},
"power_set_value": {"value": 44, "label": "configured"},
"loss_ratio": {"value": 0.0065, "label": "derived"},
"distance_m": {"value": 2.0, "label": "declared"}
```

A number keeps its label when a reply quotes that number alone, which the number origin labels record requires. A histogram is one object, whose `value` holds the array of bin counts, because every bin of a histogram shares one origin.

The keys of the format itself carry no label. `record_version`, the index of an array, and the length of an array state the shape of the file rather than a quantity of the run. A timestamp is text in RFC 3339 form with a `Z` suffix, so no label applies to it either. This reading narrows the number origin labels record from every number to every number that states a quantity of the run, and a reviewer who reads that record more widely stops this one.

**The file.** The host writes `bolis-<run id>.json`. `run_id` is the unsigned 32-bit integer that the `role` command carries and that a sender stamps into the frame header, and the file name states the same value in decimal digits. One value therefore takes one form in the record, on the control line, in the frame header, and in the file name.

The host writes into the directory that `--out` names, and into the working directory when the user gives no `--out`. Before a run starts, the host reads the run IDs of the records in that directory, for the uniqueness check that the frame header encoding record states. If the host cannot read that directory, or cannot write to it, it stops before the first cell and names the directory. A run that the host cannot record is a run that wasted a bench.

**A run that stops.** The `run` section carries `status`, which holds `complete` or `stopped`, and a `stopped` record carries `stopped_reason`. The host writes the record when a run stops, with the cells that ran. A reader tells a short run from a complete one by `status` rather than by counting cells.

**A cell that a node invalidated.** Each entry of `cells` is one attempt. An entry carries `valid`, which holds false when a node reset during that attempt, and the rerun of that cell is a further entry. A record therefore holds the attempt that failed beside the attempt that replaced it. The drift band of thinkbook section 8 rests on which cells ran, so a record that drops an attempt cannot be audited.

**Validation.** The host validates every record against the schema before it writes the file. The host package takes `jsonschema` as a dependency for that check. One definition of the format then governs the writer, the tests, and any reader of the corpus.

**Privacy.** No key of the format holds a MAC address, and no key holds a device identifier. The `declared` section holds what the user typed, and the user chooses what to type there.

## Consequences

- This record fixes the format, and a corpus reuses the format, so a change to any rule here needs a new record.
- `record_version` rises when a key changes meaning, moves, or leaves. A record of an older version stays readable, because its version states which rules it follows.
- The object form of a number costs size against a bare number. A default plan holds 36 cells and 2 passes, so the cost falls on a file that one machine writes and one report reads.
- The host package gains `jsonschema` beside `esptool`. No record gates a dependency of the host package today, because the dependency scope record covers components of the firmware alone. A record that gates a host dependency would close that gap, and this record does not close it.
- A reviewer who reads the number origin labels record as covering `record_version` and array lengths rejects the narrowing above, and this record changes before it is accepted.
- The host reads a directory before a run and writes one file after it, which keeps the offline guarantee of specification section 7.
- A run that stops still produces a record, so a bench session that fails late keeps its cells.
- A record can hold two entries for one cell, so a reader of `cells` filters on `valid` before it computes a loss quantity.
- The report reads `label` beside each number and prints the legend of the four labels, which the number origin labels record requires.
- `schema/README.md` is a placeholder, so the change that adds the schema deletes that file.
- The run record writer and the report both depend on this record, so neither one is written until the status changes.
- Watch the first record that a user shares. It is the first time the format meets a reader outside this repository, and nothing in the format identifies the machine that wrote it.
