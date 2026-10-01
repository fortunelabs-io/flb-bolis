# The control line wire format between the host and a node

Date: 2026-10-01
Status: Accepted

## Context

Thinkbook section 7 named the control plane, the `@bol ` prefix, one JSON object per line, and five commands: `hello`, `role`, `cell`, `go`, and `stats`. The radio ownership record moved the role from an argument of the start function to the control protocol. Part 2 of the thinkbook marks every design choice a proposal, and it left the wire contract open. It did not state the key names, how a reply matches its command, how a node reports a failure, how long a line may be, or how the two sides detect an incompatible pair. The prebuilt images ship inside the host package, and a source build follows its own schedule, so a user can hold a host package and a node image of different ages. The ESP-IDF helper that writes the ELF SHA-256 as text writes only as many characters as `CONFIG_APP_RETRIEVE_LEN_ELF_SHA` allows, and that option defaults to 9 characters, while the release process matches a run record to a release image by that hash. If nothing was decided, the first firmware module would fix the wire contract by accident, and the host would hold no way to refuse a node that speaks an older contract.

## Alternatives considered

- One JSON object per line behind the `@bol ` prefix, in both directions.
- A binary frame on the serial line, outside the console.
- The ESP-IDF console component, with its argument parser and plain text replies.
- A second UART for the control plane, separate from the log.

## Decision

Every control line carries the prefix `@bol `, one JSON object, and a newline. Both directions use the prefix. A reader ignores every other line on the console, so the application log and the control plane share one serial line.

A host line carries the key `cmd`. A node line carries the key `reply`. Both carry `seq`, an unsigned integer that the host raises for each command and the node copies into its reply. Both carry `proto`, an integer that names the version of this contract, and the first version is 1. A node reply carries `ok`. A reply with `ok` set to false carries `err`, which holds the name of the ESP-IDF error code.

A control line holds at most 512 bytes, including the prefix and the newline. A node rejects a longer line and counts it.

```
@bol {"proto":1,"cmd":"hello","seq":1}
@bol {"proto":1,"reply":"hello","seq":1,"ok":true,"chip":"esp32","chip_revision":301,
      "idf_version":"v5.5.4","espnow_version":2,"payload_limit_bytes":1470,
      "bolis_version":"0.1.0","firmware_path":"source","elf_sha256":"<64 hex characters>",
      "bluetooth_controller":"disabled"}
```

The `hello` reply states the ELF SHA-256 as 64 lowercase hexadecimal characters, encoded from the 32 bytes of the application description. It does not use the ESP-IDF text helper, because that helper truncates to a configured length.

The host refuses a node whose `proto` differs from its own, and it refuses a pair of nodes whose `hello` replies differ in firmware.

A MAC address crosses the control line in the `role` command only. No side writes a MAC address to a log, a run record, or a report.

A node attaches no origin label to a value. The host attaches the label when it writes the run record.

Key names use `snake_case`, and a key that names a quantity ends with its unit.

## Consequences

- The host detects an incompatible node at `hello`, before the first cell.
- A change to any key, command, or reply raises `proto` and needs a new record.
- The host and the firmware can ship on different schedules, because `proto` names the contract.
- A reader matches a run record to a release image, because the hash is complete.
- The control plane needs no second UART and no second cable.
- One serial line carries both the log and the control lines, so a stray log line that starts with the prefix would corrupt a reply.
- Only the console module writes a line that starts with the prefix.
- The console module reads and writes text, so it needs the deviation record for Rule 21.6.
- JSON costs more bytes per line than a binary frame, and the control plane carries no frame of a run, so the cost does not reach the measurement.
- A 512-byte limit fits the longest reply, which is `hello`, and it leaves room for a later field.
- A reply larger than the limit would need a new record.
- The run record format gains the `hello` fields, which thinkbook section 9 already lists.
- Thinkbook section 7 states this wire format in its next version.
