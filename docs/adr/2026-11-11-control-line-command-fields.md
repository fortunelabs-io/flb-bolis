# The field keys of the role, cell, go, and stats commands

Date: 2026-11-11
Status: Accepted

## Context

The accepted wire format record fixed the envelope of a control line, the nine fields of the `hello` reply, and nothing else. It named `role`, `cell`, `go`, and `stats` as commands of the contract and stated no key for any of them. `bol_handle_line` in `components/bolis/src/bol_console.c` recognized all four and answered each one with `ok` set to false and `err` set to `ESP_ERR_NOT_SUPPORTED`. `host/src/bolis/protocol.py` therefore took a generic mapping for the fields of a command, because a key invented there would have fixed the contract by accident. The host could reach a node, read its `hello` reply, and refuse a mismatched pair, and it could do nothing else. The orchestrator and the sender and receiver tasks were the next modules in both languages, and neither could be written. `s_rejected_line_count` was incremented and never read, under a suppression that named `stats` as its future reader. Thinkbook section 7 named the semantics of each command and the counters of each pass, and thinkbook section 9 listed the run record sections that those counters fill. If nothing was decided, the first module to send one of these four commands would fix every key by accident, and the firmware and the host would meet whichever shape each side guessed.

## Alternatives considered

- One `stats` reply per node and pass, carrying every counter that the node holds for that pass.
- One `stats` reply per counter group, which multiplies the exchanges of each cell.
- A command of its own for each histogram, which splits one reply across two contracts.
- The frame count held in the firmware, which keeps a `[configured]` value of the run record out of the exchange that sets it.
- The pass named on `cell` rather than on `go`, which re-arms a node for each pass of one condition.
- The send errors as an object keyed by the ESP-IDF error name, which puts a value where the contract names a key.
- A line limit above 512 bytes for the `stats` reply, which reopens the accepted wire format record.
- Histograms of no stated bin count, which a 512-byte line cannot hold.

## Decision

The contract version `proto` rises to 2. Every key below is new, and the wire format record states that a change to any key raises `proto`.

Key names stay `snake_case`, and a key naming a quantity ends with its unit, which the wire format record already requires.

`cell_id` is 0 to 32767. The frame header holds the cell in 15 bits and the pass in the top bit (thinkbook section 7), so the control line and the frame agree on that range. `pass` holds `broadcast` or `unicast`.

The `role` command carries `role`, which holds `sender` or `receiver`, and it carries `peer_mac` when `role` holds `sender`. The `role` reply carries `role` and `mac`, which states the MAC address of the node that answered. The host reads the MAC address of the receiver from that reply and sends it to the sender as `peer_mac` for the unicast pass.

The `cell` command carries `cell_id`, `channel`, `power_set_value`, and `payload_bytes`. The `cell` reply carries `cell_id`, `channel`, `payload_bytes`, and `power_set_value_read_back`, which states the value the radio reports rather than the value the host requested.

The `go` command carries `cell_id`, `pass`, and `frames`. The `go` reply carries `cell_id`, `done`, and `frames_sent`, and a node writes it when the send callback of the last frame of the pass returns.

The `stats` command carries `cell_id` and `pass`. A `stats` reply carries `cell_id`, `pass`, `rejected_lines`, and the counters of the node that answered, which thinkbook section 7 lists. A sender reply carries `messages_sent`, `packets_sent`, `send_errors`, `callback_ok`, `callback_failed`, `no_mem_events`, and `send_to_callback_us_histogram`. A receiver reply carries `packets_received`, `duplicates`, `foreign_packets`, `messages_complete`, `messages_incomplete`, `corrupt_packets`, `loss_run_length_histogram`, `rssi_min_dbm`, `rssi_mean_dbm`, and `rssi_max_dbm`.

`send_errors` holds an array of objects, each carrying `err` and `count`. `err` holds the name of the ESP-IDF error code, as the envelope already does for a failed reply.

Each histogram holds 16 bins, as an array of counts from the lowest bin to the highest. The last bin of each histogram counts every value at or above its lower edge.

```
@bol {"proto":2,"cmd":"cell","seq":7,"cell_id":12,"channel":6,
      "power_set_value":44,"payload_bytes":128}
@bol {"proto":2,"reply":"cell","seq":7,"ok":true,"cell_id":12,"channel":6,
      "payload_bytes":128,"power_set_value_read_back":44}
@bol {"proto":2,"cmd":"go","seq":8,"cell_id":12,"pass":"broadcast","frames":2000}
@bol {"proto":2,"reply":"go","seq":8,"ok":true,"cell_id":12,"done":true,
      "frames_sent":2000}
```

## Consequences

- `proto` rises to 2, so a host refuses a node built against version 1 at `hello`, before the first cell.
- `protocol.PROTO_VERSION` and `BOL_PROTO_VERSION` both change in the same release, and each one is 1 today.
- The `stats` reply fits one line. At 16 bins, and with every number at its widest, a sender reply measures 426 bytes and a receiver reply measures 458 bytes against the 512-byte limit.
- The receiver reply is the tighter of the two, and 16 bins leaves it 54 bytes. A histogram of 24 bins would leave 6 bytes, which is no room for a later field.
- A histogram wider than 16 bins needs a new record, because the line limit belongs to the wire format record.
- The sender bins the send-to-callback time in memory, so the serial line carries the histogram and no per-frame value, which thinkbook section 7 already states.
- `stats` reads the counter of rejected control lines, so the suppression of Rule 8.9 on `s_rejected_line_count` is removed in the change that implements this record.
- A `go` reply arrives after the pass ends. A pass of 2000 frames at 1470 bytes carries about 25 seconds of airtime, so the host holds a longer reply timeout for `go` than for any other command.
- A `role` reply carries a MAC address. No side writes it to a log, a run record, or a report, which specification section 7 requires.
- The host sends `role` to the receiver before the sender, because the MAC address of the receiver reaches the sender as `peer_mac`.
- The run record gains the `cell` and `stats` fields, which thinkbook section 9 already lists in its `cells` section.
- The host attaches an origin label to each of these values when it writes the run record. A counter of a node is `[measured]`, and a value the host sent is `[configured]`.
- Thinkbook section 7 states these keys in its next version.
- This record names no key for a timebase, for energy, or for one-way delay. Specification section 4 keeps all three outside v0.
- Watch the width of a `stats` reply as a counter is added. The next field has 54 bytes on the receiver line, and a wider reply needs a new record.
