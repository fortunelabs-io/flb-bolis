# Bolis design

This file states the current design of Bolis in one place. A session on this repository starts from this file and from the operational state that sits beside the repository.

## How to read this file

Every statement here comes from a source, and the link beside it names that source. This file settles nothing new. A reader who wants the reasoning behind a choice reads the record that the link names, because a record states the alternatives that lost and this file states only the choice that won.

**Precedence.** Three sources describe the design, and they carry different dates.

1. An accepted decision record in [`docs/adr/`](./adr/) governs. The records post-date both documents below, and each one names the sections of those documents that change in their next version.
2. The Bolis v0 specification, v0.4, governs over the thinkbook. The thinkbook states that rule in its own opening ([thinkbook opening](./fortunelabs_bolis_thinkbook.md)).
3. The Bolis thinkbook, v0.2, holds the theory and the high-level design.

**Labels.** No Bolis run has produced a measurement, so no number in this file carries `[measured]`. The specification states that rule for itself ([specification opening](./fortunelabs_bolis_spec.md)), and the thinkbook states it for Part 2 ([thinkbook opening](./fortunelabs_bolis_thinkbook.md)). A value below carries `[proposal]` when the record that fixed it marked it so, which happens where the value rests on a distribution that the first run exists to measure. A value with no label is a settled choice that a record fixed.

**New detailed design.** A detailed design choice goes into this file. A choice that is hard to reverse, that rests on non-obvious reasoning, or that touches a reused asset goes into a new record first. [`docs/adr/README.md`](./adr/README.md) states that split.

## 1. What Bolis is

Bolis is a bench tool for ESP-NOW. It consists of firmware for two ESP32 nodes and a host CLI. It runs an automatic sweep on the ESP-NOW link between the two nodes and writes one report that shows which variable moves frame loss near the configuration of the user ([specification section 3](./fortunelabs_bolis_spec.md#3-one-sentence)).

The product exists for discovery first, for measured data second, and for money only if it comes ([specification section 1](./fortunelabs_bolis_spec.md#1-goal)).

The C function prefix is `bol_`, the host package is `bolis`, and the component is `fortunelabs-io/bolis` ([specification section 2](./fortunelabs_bolis_spec.md#2-name-and-identifiers)).

## 2. Scope of v0

In scope: ESP-NOW between two ESP32 nodes on one bench, both connected to one host by USB; prebuilt firmware per supported chip; a component for source builds; three sweep variables, which are channel, payload size, and transmit power; a sweep that changes one variable at a time; broadcast first-attempt loss in every run; a PHY rate fixed at 1 Mbps; power save off on both nodes; a host CLI that writes one run record per run; a static HTML report; and an origin label on every number ([specification section 4](./fortunelabs_bolis_spec.md#4-scope)).

Out of scope: energy measurement, integration into Arduino projects, WiFi links, LoRa links, a run setting for the PHY rate, a test of interactions between the sweep variables, field installation, a dashboard, and automatic diagnosis ([specification section 4](./fortunelabs_bolis_spec.md#4-scope)).

**Claim limit.** A report states how one configuration behaves under controlled conditions. Every report states three limits: its results apply to 1 Mbps, its conclusions hold at its baseline, and its sweep does not test interactions ([specification section 4](./fortunelabs_bolis_spec.md#4-scope)).

## 3. System shape

Bolis has two planes. The data plane is the ESP-NOW link under test. The control plane is a USB serial line from the host to each node. The control plane never uses the radio, so a failing channel cannot break the coordination of a channel change ([thinkbook section 6](./fortunelabs_bolis_thinkbook.md#6-system-overview)).

| Part | Runs on | Job |
|---|---|---|
| Bolis firmware | Both nodes | Takes a role from the host, applies each cell, sends or receives frames, counts, and reports |
| `bolis` host CLI, Python | The host | Flashes the nodes, orchestrates the sweep, writes the run record, and builds the report |
| `bol_` component | Source builds | Holds the firmware logic |
| Run record | A JSON file | Holds the conditions, the counters, and a label for every number |
| Report | A static HTML file | Shows the charts, the paragraph, the limits, and the label legend |

[thinkbook section 6](./fortunelabs_bolis_thinkbook.md#6-system-overview) states the parts.

Both nodes run the same firmware image, and the host assigns the sender role and the receiver role at run time ([`2026-10-01-radio-ownership-and-prebuilt-firmware.md`](./adr/2026-10-01-radio-ownership-and-prebuilt-firmware.md)).

The host sends nothing off the machine of the user ([specification section 7](./fortunelabs_bolis_spec.md#7-data-handling)).

## 4. The user flow

1. Install the host package with `pip install bolis`.
2. Connect two ESP32 boards to the host by USB.
3. Flash both boards with `bolis flash <port> <port>`.
4. Run the sweep with `bolis run <port> <port> --channel <c> --power <set value> --payload <bytes>`. The first port takes the sender role. `--mode unicast` adds the unicast pass.
5. Receive one report file beside the run record.

[specification section 5](./fortunelabs_bolis_spec.md#5-user-flow) states the flow, and [thinkbook section 6](./fortunelabs_bolis_thinkbook.md#6-system-overview) maps it to the design.

A user who needs a specific ESP-IDF version or sdkconfig replaces step 3 with a source build of the example project `components/bolis/examples/bench`, created with `idf.py create-project-from-example "fortunelabs-io/bolis:bench"` on ESP-IDF v5.5 or later ([thinkbook section 6](./fortunelabs_bolis_thinkbook.md#6-system-overview)).

`bolis run` also accepts `--print-plan`, which resolves the baseline, builds the plan, prints it, and returns 0. `--limit` selects the packet payload limit, which is 250 bytes or 1470 bytes, and 1470 bytes is the default. `--plan` selects `default` or `grid`. The command generates the shuffle seed and prints it, and it accepts no seed option ([`2026-11-10-run-plan-resolution.md`](./adr/2026-11-10-run-plan-resolution.md)).

`--out` names the directory that the host writes into, and the working directory applies when the user gives no `--out` ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

## 5. The firmware

### 5.1 Radio ownership and the start contract

The public API is one function ([thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol)):

```c
esp_err_t bol_start(void);
```

Bolis firmware owns the radio during a run. `bol_start` first calls `esp_wifi_get_mode`. If that call returns anything other than `ESP_ERR_WIFI_NOT_INIT`, WiFi is already initialized, and `bol_start` returns `ESP_ERR_INVALID_STATE` without changing the radio. Otherwise it initializes WiFi in station mode, disables power save, sets the country code, initializes ESP-NOW, registers the callbacks, and starts a control task on the console ([`2026-10-01-radio-ownership-and-prebuilt-firmware.md`](./adr/2026-10-01-radio-ownership-and-prebuilt-firmware.md), [thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol)).

The component sets 1 Mbps for every peer it adds ([`2026-10-01-phy-rate-fixed-at-1-mbps.md`](./adr/2026-10-01-phy-rate-fixed-at-1-mbps.md)).

The role is not an argument of the start function. The host sends it through the control protocol ([`2026-10-01-radio-ownership-and-prebuilt-firmware.md`](./adr/2026-10-01-radio-ownership-and-prebuilt-firmware.md)).

The prebuilt image builds with the Bluetooth controller disabled and with a Kconfig option that marks the image as prebuilt. A source build leaves that option off, so the `hello` reply states the firmware path ([thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol)).

The minimum ESP-IDF version is v5.5. The component uses one send callback signature and takes the v2.0 payload limit from `ESP_NOW_MAX_DATA_LEN_V2` at compile time ([`2026-10-01-esp-idf-v5-5-minimum.md`](./adr/2026-10-01-esp-idf-v5-5-minimum.md)).

A dependency on a component that ESP-IDF ships needs no decision record, and the pull request body names it and states why. A dependency on any other component stops the change and needs a record ([`2026-10-01-scope-the-dependency-rule.md`](./adr/2026-10-01-scope-the-dependency-rule.md)).

### 5.2 The control plane

**The envelope.** Every control line carries the prefix `@bol `, one JSON object, and a newline, in both directions. A reader ignores every other line, so the application log and the control plane share one serial line. A host line carries `cmd`, and a node line carries `reply`. Both carry `seq`, which the host raises for each command and the node copies into its reply. Both carry `proto`. A node reply carries `ok`, and a failed reply carries `err`, which holds the name of the ESP-IDF error code. A control line holds at most 512 bytes, including the prefix and the newline, and a node rejects a longer line and counts it. Key names use `snake_case`, and a key that names a quantity ends with its unit ([`2026-10-01-control-line-wire-format.md`](./adr/2026-10-01-control-line-wire-format.md)).

A node attaches no origin label to a value. The host attaches the label when it writes the run record ([`2026-10-01-control-line-wire-format.md`](./adr/2026-10-01-control-line-wire-format.md)).

**The contract version.** `proto` is 2. Version 2 has not shipped, so every key below reaches a node inside it. A key added after version 2 ships costs version 3 ([`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md), [`2026-11-12-frame-header-encoding.md`](./adr/2026-11-12-frame-header-encoding.md)).

The current contract is the command fields record plus four amendments. A reader of the contract reads all five ([`2026-11-16-the-arm-and-finish-of-a-receiver-pass.md`](./adr/2026-11-16-the-arm-and-finish-of-a-receiver-pass.md)).

| Command | Sent to | Keys | Reply keys |
|---|---|---|---|
| `hello` | Both nodes | None beyond the envelope | `chip`, `chip_revision`, `idf_version`, `espnow_version`, `payload_limit_bytes`, `bolis_version`, `firmware_path`, `elf_sha256`, `bluetooth_controller`, and `country_code` |
| `role` | Both nodes | `role`, `run_id`, and `peer_mac` when `role` holds `sender` | `role` and `mac` |
| `cell` | Both nodes | `cell_id`, `channel`, `power_set_value`, `payload_bytes`, `pass`, and `frames` | `cell_id`, `channel`, `payload_bytes`, and `power_set_value_read_back` |
| `go` | The sender | `cell_id`, `pass`, and `frames` | `cell_id`, `done`, and `frames_sent` |
| `stats` | Both nodes | `cell_id` and `pass` | `cell_id`, `pass`, `rejected_lines`, and the counters of the node that answered |

The nine original `hello` fields come from [`2026-10-01-control-line-wire-format.md`](./adr/2026-10-01-control-line-wire-format.md). `country_code` is the tenth field, read with `esp_wifi_get_country_code` after the radio starts, so the reply states the code that the radio holds rather than the macro that configured it ([`2026-11-16-the-country-code-in-the-hello-reply.md`](./adr/2026-11-16-the-country-code-in-the-hello-reply.md)). The widest `hello` reply measures 365 bytes against the 512-byte limit ([`2026-11-16-the-country-code-in-the-hello-reply.md`](./adr/2026-11-16-the-country-code-in-the-hello-reply.md)).

`elf_sha256` holds 64 lowercase hexadecimal characters, encoded from the 32 bytes of the application description. It does not use the ESP-IDF text helper, because that helper truncates to a configured length ([`2026-10-01-control-line-wire-format.md`](./adr/2026-10-01-control-line-wire-format.md)).

The keys of `role`, `cell`, `go`, and `stats` come from [`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md). `run_id` reaches `role` through [`2026-11-12-frame-header-encoding.md`](./adr/2026-11-12-frame-header-encoding.md). `pass` and `frames` reach `cell` through [`2026-11-16-the-arm-and-finish-of-a-receiver-pass.md`](./adr/2026-11-16-the-arm-and-finish-of-a-receiver-pass.md), and the host states the same `frames` on the `cell` and the `go` of one pass.

`cell_id` runs from 0 to 32767, and `pass` holds `broadcast` or `unicast` ([`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md)).

**The counters.** A sender reply carries `messages_sent`, `packets_sent`, `send_errors`, `callback_ok`, `callback_failed`, `no_mem_events`, and `send_to_callback_us_histogram`. A receiver reply carries `packets_received`, `duplicates`, `foreign_packets`, `messages_complete`, `messages_incomplete`, `corrupt_packets`, `loss_run_length_histogram`, `rssi_min_dbm`, `rssi_mean_dbm`, `rssi_max_dbm`, and `dropped_packets`. `send_errors` holds an array of objects, each carrying `err` and `count`. Each histogram holds 16 bins, from the lowest bin to the highest, and the last bin counts every value at or above its lower edge ([`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md), [`2026-11-13-the-receiving-loop-of-a-pass.md`](./adr/2026-11-13-the-receiving-loop-of-a-pass.md)).

At 16 bins, a sender reply measures 426 bytes and a receiver reply measures 458 bytes against the 512-byte limit. The receiver reply is the tighter of the two, and it leaves 54 bytes for a later field. A histogram wider than 16 bins needs a new record ([`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md)).

**The exchange of one cell.** The host sets the receiver first, so the receiver listens on the new channel before the first frame leaves the sender. A settle time after `done` catches late frames before the receiver reports. In a unicast run, the host repeats `go` and `stats` with the unicast pass before it moves to the next cell ([thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol)). The host sends `role` to the receiver before the sender, because the MAC address of the receiver reaches the sender as `peer_mac` ([`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md)).

The settle time between the last `go` reply and a `stats` command sits with the orchestrator and with no record ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

**The port and the timeouts.** The transport owns the port, the read timeout, and the retry of one command. It opens the port at 115200 baud, with eight data bits, no parity, one stop bit, and no flow control. It reads whole lines and discards every line that does not start with the prefix. It refuses a port name that pyserial reads as a URL, so no command reaches a serial server over a network ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

A sender writes a `go` reply at an interval during a pass, and not at the end alone. A reply during a pass carries `done` set to false and `frames_sent` set to the number of frames whose send callback has returned. The reply at the end carries `done` set to true. Every reply of one pass carries the `seq` of its `go` command. A sender writes a progress reply when 1000 ms have passed since its last line of that pass `[proposal]`, between two frames and never between a send and its callback ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

Every command other than `go` carries the short timeout, which is 2 s `[proposal]`. `go` carries a liveness timeout, which is 3 s `[proposal]`, and the host restarts it on every line that the node writes for the pass, so the timeout measures silence rather than the duration of a pass ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

The host refuses a node whose `proto` differs from its own, and it refuses a pair of nodes whose `hello` replies differ in firmware ([`2026-10-01-control-line-wire-format.md`](./adr/2026-10-01-control-line-wire-format.md)).

**MAC addresses.** A MAC address crosses the control line in the `role` command and the `role` reply only. No side writes a MAC address to a log, a run record, or a report ([`2026-10-01-control-line-wire-format.md`](./adr/2026-10-01-control-line-wire-format.md), [`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md)). The host holds MAC addresses only in memory ([specification section 7](./fortunelabs_bolis_spec.md#7-data-handling)).

### 5.3 The frame

Each ESP-NOW packet starts with a 14-byte header, so the smallest swept payload is 14 bytes ([thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol)).

| Field | Size | Purpose |
|---|---|---|
| Magic | 2 bytes | Marks a Bolis packet |
| Run ID | 4 bytes | Rejects packets from another run |
| Cell ID and pass | 2 bytes | The low 15 bits name the cell, and the top bit names the pass |
| Message ID | 4 bytes | Orders messages and exposes gaps |
| Fragment index and count | 2 bytes | Rebuilds messages |
| Fill | The rest of the frame | A pattern derived from the header, to detect truncation and corruption |

[`2026-11-12-frame-header-encoding.md`](./adr/2026-11-12-frame-header-encoding.md) fixes five encodings inside those widths.

- **Byte order.** Every multi-byte field is big-endian, with the most significant byte first, so a hex dump reads in field order.
- **Magic.** The magic holds `0x42` and then `0x4F` `[proposal]`, which reads as `BO` in a hex dump. The value avoids `0x0000` and `0xFFFF`, because erased memory and a stuck line produce those patterns.
- **Pass bit.** The pass bit is the most significant bit of the cell and pass field. It holds 0 for a broadcast pass and 1 for a unicast pass, so 0 names the pass that every run holds.
- **Fragment field.** The first byte holds the index, counting from 0, and the second byte holds the count.
- **Fill.** The fill holds every byte after the header, to the end of its frame. The byte at fill offset $i$ holds $f(i) = (s + i) \bmod 256$, where the frame seed is $s = (m + g) \bmod 256$, $m$ is the message ID, and $g$ is the fragment index. The fill detects a change to any byte of one frame and a frame shorter than its header implies. It does not tell one frame from another, and the header carries that job.

The header holds no version field, and its 14 bytes carry no spare byte. A run record therefore names the frame encoding of its run only through the ELF SHA-256 that the node reported ([`2026-11-12-frame-header-encoding.md`](./adr/2026-11-12-frame-header-encoding.md)).

A frame that fails the magic or the run ID counts in `foreign_packets`. A frame that fails the fill check, or that is shorter than its header implies, counts in `corrupt_packets` ([`2026-11-12-frame-header-encoding.md`](./adr/2026-11-12-frame-header-encoding.md)).

**The run ID.** The run ID is an unsigned 32-bit integer that the `role` command carries. The host draws it with `random.getrandbits(32)`, a sender stamps it into every frame, and a receiver rejects a frame whose run ID differs from the stored value. Before a run starts, the host compares the drawn value against the run IDs of the records in the directory it writes to, and it draws again on a match. A random draw of 32 bits reaches an even chance of a repeat at about 77,000 records, so a corpus large enough meets a repeat, and a corpus resolves a repeat when a shared record enters it. The draw is random rather than derived from the hardware, because a record carries no device identifier that the user did not add ([`2026-11-12-frame-header-encoding.md`](./adr/2026-11-12-frame-header-encoding.md), [specification section 7](./fortunelabs_bolis_spec.md#7-data-handling)).

**The mapping of a message to its frames.** A message of $p$ bytes maps to $n(p)$ frames, and those frames divide $p$ as evenly as they can. Let $n$ be $n(p)$, let $b$ be $\lfloor p / n \rfloor$, and let $r$ be $p \bmod n$. The first $r$ frames hold $b + 1$ bytes each, and the remaining $n - r$ frames hold $b$ bytes each. Each count holds the whole frame, which is the 14-byte header and the fill after it. The sender puts the frames of one message on the air in fragment index order, starting at index 0, and `fragment_count` holds $n$ ([`2026-11-16-the-mapping-of-a-message-to-its-frames.md`](./adr/2026-11-16-the-mapping-of-a-message-to-its-frames.md)).

| $p$ | $L$ | $n(p)$ | The frames |
|---|---|---|---|
| 14 | 1470 | 1 | 14 |
| 1470 | 1470 | 1 | 1470 |
| 1471 | 1470 | 2 | 736, 735 |
| 2941 | 1470 | 3 | 981, 980, 980 |
| 251 | 250 | 2 | 126, 125 |
| 501 | 250 | 3 | 167, 167, 167 |

Every frame of every payload of both lists holds its header, so the mapping states no padding rule and no minimum frame size. The bytes of one message on the air equal $p$ exactly. No frame of a fragmented cell sits at the limit, so the airtime that the thinkbook states for a full-size frame applies to an unfragmented cell only ([`2026-11-16-the-mapping-of-a-message-to-its-frames.md`](./adr/2026-11-16-the-mapping-of-a-message-to-its-frames.md)).

### 5.4 The sender

The sender sends the next packet after the callback of the previous packet returns, as the ESP-IDF guide recommends. It counts `esp_now_send` errors by code, and it bins the send-to-callback time into a histogram in memory, so the serial line carries only the histogram ([thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol)).

**The frame budget.** `frames` counts packets on the air. A pass sends whole messages only. The sender sends the next message while the packets of that message fit inside the remaining budget, and it stops when they do not. `packets_sent` therefore reaches the budget exactly when $n(p)$ divides it, and falls short of it by fewer than $n(p)$ packets otherwise. A message cut short at the budget would reach the receiver with a missing fragment and would state a loss that the link did not cause ([`2026-11-13-the-sending-loop-of-a-pass.md`](./adr/2026-11-13-the-sending-loop-of-a-pass.md)).

`messages_sent` is `packets_sent` divided by $n(p)$, with no remainder ([`2026-11-13-the-sending-loop-of-a-pass.md`](./adr/2026-11-13-the-sending-loop-of-a-pass.md)).

**The send-to-callback histogram.** The bins hold microseconds on a doubling scale `[proposal]`. Bin 0 holds every value below 64 microseconds. Bin $k$, for $k$ from 1 to 14, holds every value from $64 \times 2^{k-1}$ up to $64 \times 2^{k}$, excluding the upper edge. Bin 15 holds every value at or above 1048576 microseconds. The scale places the swept payload list across the middle of the range: the airtime of a 14-byte frame falls in bin 4, a 250-byte frame in bin 6, and a 1470-byte frame in bin 8. A callback cannot return before the airtime of its frame, so those bins are the floor of each cell, and the bins above them hold the retry structure that a unicast pass adds ([`2026-11-13-the-sending-loop-of-a-pass.md`](./adr/2026-11-13-the-sending-loop-of-a-pass.md)).

**A failed send.** The sender counts every `esp_now_send` error by its code. On `ESP_ERR_ESPNOW_NO_MEM` it waits 10 milliseconds `[proposal]`, counts one event in `no_mem_events`, and sends that packet again, for at most 10 such attempts `[proposal]`. After the last attempt it counts the error under its code in `send_errors`, counts the packet as neither sent nor delivered, and moves to the next packet. A pass therefore ends at its budget rather than at its first failure ([`2026-11-13-the-sending-loop-of-a-pass.md`](./adr/2026-11-13-the-sending-loop-of-a-pass.md)).

**The long-run guard.** A public issue reports that ESP-NOW stops sending after about 78,000 broadcast frames on one ESP-IDF v5.x build. A broadcast run sends about 72,000 frames and a unicast run about 144,000, so the guard is required. The firmware re-initializes ESP-NOW between passes, adds the peers again with the 1 Mbps rate, and counts `ESP_ERR_ESPNOW_NO_MEM` ([thinkbook section 8](./fortunelabs_bolis_thinkbook.md#8-sweep-design), [`2026-10-01-loss-metric-and-send-mode.md`](./adr/2026-10-01-loss-metric-and-send-mode.md)).

### 5.5 The receiver

The receive callback runs in the WiFi task, so it copies the packet header, the length, and the RSSI to a queue and returns. A lower-priority task checks the header and the fill, tracks sequence numbers per cell and pass, and updates the counters ([thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol)).

**The arm and the finish.** A receiver arms at `cell`. It holds the run from its `role` command, and it takes the cell, the pass, and the payload size from `cell`. It derives the packets of one message from the payload size and the payload limit. It finishes at `stats`, before it reads its counters, and it derives the positions of the pass from the frame budget that `cell` carried ([`2026-11-16-the-arm-and-finish-of-a-receiver-pass.md`](./adr/2026-11-16-the-arm-and-finish-of-a-receiver-pass.md)).

**The queue.** The queue between the callback and the task holds 32 entries `[proposal]`. Each entry holds the frame header, the length, and the RSSI, and not the payload ([`2026-11-13-the-receiving-loop-of-a-pass.md`](./adr/2026-11-13-the-receiving-loop-of-a-pass.md)).

**A packet that the node drops.** `dropped_packets` states the packets that reached the callback and that the node did not process. A dropped packet is not a loss of the link and not a corrupt frame. It states that the node did not keep up, so the report reads a cell with a count above zero as a cell that measured the node rather than the link ([`2026-11-13-the-receiving-loop-of-a-pass.md`](./adr/2026-11-13-the-receiving-loop-of-a-pass.md)).

**Sequence numbers.** The receiver derives the position of a packet inside its pass from the message ID and the fragment index of its header. It holds a window of the 64 most recent positions `[proposal]`. A packet whose position the window already marks counts in `duplicates`, and so does a packet below the floor of the window. The window bounds the memory of the receiver at 64 bits per pass ([`2026-11-13-the-receiving-loop-of-a-pass.md`](./adr/2026-11-13-the-receiving-loop-of-a-pass.md)).

**A message.** The receiver assembles one message at a time, because a pass sends whole messages in order. A message counts in `messages_complete` when every fragment of it arrives. It counts in `messages_incomplete` when a fragment of a later message arrives first, or when the pass ends with a fragment missing ([`2026-11-13-the-receiving-loop-of-a-pass.md`](./adr/2026-11-13-the-receiving-loop-of-a-pass.md)).

**The run-length histogram.** Bin $k$, for $k$ from 0 to 14, holds a run of exactly $k + 1$ lost packets. Bin 15 holds every run of 16 packets or more. The scale is linear, because the mass of a healthy pass sits at the shortest runs and a fit of the burst model needs resolution there ([`2026-11-13-the-receiving-loop-of-a-pass.md`](./adr/2026-11-13-the-receiving-loop-of-a-pass.md), [thinkbook section 3](./fortunelabs_bolis_thinkbook.md#3-cost-and-loss-model)).

**RSSI.** `rssi_min_dbm`, `rssi_mean_dbm`, and `rssi_max_dbm` cover the packets that passed the header check, and the mean is their arithmetic mean. A pass that received no such packet states no RSSI ([`2026-11-13-the-receiving-loop-of-a-pass.md`](./adr/2026-11-13-the-receiving-loop-of-a-pass.md)).

## 6. The sweep

A cell is one condition, which is a channel, a transmit power, and a payload size. A cell runs one pass per mode: a broadcast pass in every run, and a unicast pass after it in a unicast run. Every pass sends $N$ frames at 1 Mbps ([thinkbook section 8](./fortunelabs_bolis_thinkbook.md#8-sweep-design), [`2026-10-01-loss-metric-and-send-mode.md`](./adr/2026-10-01-loss-metric-and-send-mode.md), [`2026-10-01-phy-rate-fixed-at-1-mbps.md`](./adr/2026-10-01-phy-rate-fixed-at-1-mbps.md)).

The default plan changes one variable at a time around a baseline ([`2026-10-01-local-one-variable-sweep.md`](./adr/2026-10-01-local-one-variable-sweep.md)).

| Variable | Points |
|---|---|
| Channel | Every channel the country setting allows. Under the code `01` this is 1 to 11 |
| Transmit power | The 11 set values 8, 20, 28, 34, 44, 52, 56, 60, 66, 72, and 80, which map to 2 to 20 dBm |
| Payload, v1.0 | 14, 128, 249, 250, 251, 499, 500, and 501 bytes |
| Payload, v2.0 | 14, 250, 251, 1469, 1470, 1471, 2940, and 2941 bytes |

[thinkbook section 8](./fortunelabs_bolis_thinkbook.md#8-sweep-design) states the points, and [thinkbook section 4](./fortunelabs_bolis_thinkbook.md#4-variables-and-confounds) states the mechanism of each variable.

- **Payload list.** A run uses one payload list. The v2.0 list follows $L = 1470$ and is the default. `--limit 250` selects the v1.0 list, and the firmware then fragments messages at 250 bytes ([thinkbook section 8](./fortunelabs_bolis_thinkbook.md#8-sweep-design), [`2026-11-10-run-plan-resolution.md`](./adr/2026-11-10-run-plan-resolution.md)).
- **Baseline.** The baseline is the configuration of the user. Without a configuration, Bolis uses the fallback baseline, which is channel 1, power set value 44, and payload 128 bytes. A plan carries the fallback baseline only when the user gives no channel, no transmit power, and no payload size, so a baseline that names one or two values counts as a configuration. The run record states which baseline applied ([`2026-10-01-local-one-variable-sweep.md`](./adr/2026-10-01-local-one-variable-sweep.md), [`2026-11-10-run-plan-resolution.md`](./adr/2026-11-10-run-plan-resolution.md)).
- **Order.** The host shuffles the cells with a seed and records the seed, so slow drift spreads across all variables ([thinkbook section 8](./fortunelabs_bolis_thinkbook.md#8-sweep-design)).
- **Drift.** The baseline cell repeats after every 5 cells ([`2026-10-01-local-one-variable-sweep.md`](./adr/2026-10-01-local-one-variable-sweep.md), [thinkbook section 8](./fortunelabs_bolis_thinkbook.md#8-sweep-design)).
- **Frames per cell.** $N = 2000$ per cell and pass. At 5% loss, 2000 frames give a 95% interval half-width under 1 percentage point if losses are independent. With zero losses in $N$ frames, the 95% upper bound is about $3/N$, so at $N = 2000$ zero losses bound the loss below 0.15% ([`2026-10-01-local-one-variable-sweep.md`](./adr/2026-10-01-local-one-variable-sweep.md), [thinkbook section 3](./fortunelabs_bolis_thinkbook.md#3-cost-and-loss-model)).
- **Duration.** The default plan has about 36 cells per pass. A broadcast run sends about 72,000 frames, which takes about 4 minutes of sending for small payloads plus control time. Each cell of 1470-byte frames adds about 25 s of airtime. A unicast run doubles the frames and the time, to about 144,000 frames and about 8 minutes. The full grid of 11 channels, 11 power levels, and 8 payloads has 968 cells, about 1.9 million frames per pass, and about 1.7 hours per pass, and the user selects it with `--plan grid` ([thinkbook section 8](./fortunelabs_bolis_thinkbook.md#8-sweep-design), [`2026-10-01-local-one-variable-sweep.md`](./adr/2026-10-01-local-one-variable-sweep.md)).

**The channel authority.** The host holds no table of the channels that a country code allows, and it builds none. The channel list of a plan follows the range that the default code `01` allows, and the check that the host runs while it reads the command line keeps that range, so a channel of 12 fails before a port opens. A node refuses a channel that its own code does not allow, the `cell` command answers with that code, and the run stops at that cell and names it ([`2026-11-16-the-country-code-in-the-hello-reply.md`](./adr/2026-11-16-the-country-code-in-the-hello-reply.md)).

**The model behind the sweep.** The packet count of a message is $n(p) = \lceil p / L \rceil$. Inside one v2.0 frame the payload spreads over $k(p) = \lceil p / 250 \rceil$ elements. One frame with payload $p$ occupies $B(p) = 36 + p + 7\,k(p)$ bytes, and at rate $R$ it occupies $T(p) = 192\ \mu\text{s} + 8\,B(p) / R$. The loss estimate of a cell is $\hat{\ell} = \text{lost} / \text{sent}$, and the report uses the Wilson score interval at 95% ([thinkbook section 3](./fortunelabs_bolis_thinkbook.md#3-cost-and-loss-model)).

The payload sweep targets the step that $n(p)$ predicts. Under v1.0 with fragmentation, message loss rises by one step at $p = 251$, at $p = 501$, and at each further multiple of 250 plus one. Under v2.0, loss rises smoothly through 250 and 500, and the step moves to $p = 1471$ ([thinkbook section 3](./fortunelabs_bolis_thinkbook.md#3-cost-and-loss-model)).

**The loss metric.** Every run sends each cell in broadcast mode, and broadcast first-attempt loss is the base metric of every run. The corpus compares runs on this metric. In a unicast run, each cell runs a unicast pass after its broadcast pass, and the report adds post-retry loss and the send-to-callback time histogram for that pass. Each chart states its mode and its loss quantity ([`2026-10-01-loss-metric-and-send-mode.md`](./adr/2026-10-01-loss-metric-and-send-mode.md)).

**Locality.** A one-variable-at-a-time sweep finds effects that hold only at its baseline, because the variables interact. The report states that its conclusions hold at the baseline and that the sweep does not test interactions ([`2026-10-01-local-one-variable-sweep.md`](./adr/2026-10-01-local-one-variable-sweep.md), [thinkbook section 4](./fortunelabs_bolis_thinkbook.md#4-variables-and-confounds)).

## 7. The run record

The host writes one JSON file per run, named `bolis-<run id>.json`, where the run ID takes the same decimal form that the control line and the frame header carry. The host writes into the directory that `--out` names. If the host cannot read or write that directory, it stops before the first cell and names the directory ([thinkbook section 9](./fortunelabs_bolis_thinkbook.md#9-run-record-and-origin-labels), [`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

`schema/run-record.schema.json` is the normative statement of the format. It follows the JSON Schema 2020-12 dialect and carries `$schema` and `$id`. The host validates every record against the schema before it writes the file, and the host package takes `jsonschema` as a dependency for that check ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

| Section | Contents |
|---|---|
| `run` | Run ID, start and end time in UTC, Bolis version, run mode, plan, shuffle seed, and the run ID of the other run in a verification pair |
| `firmware` | Firmware path, ELF SHA-256, ESP-IDF version, ESP-NOW version, and the v2.0 payload limit $L$ |
| `nodes` | Role, chip model, and chip revision of each node |
| `setup` | Country code, PHY rate, power-save mode, state of the Bluetooth controller, payload list, and baseline source |
| `declared` | Distance, orientation, antenna, enclosure, and surroundings, as the user typed them |
| `cells` | For each cell and pass: the mode, the condition, the read-back values, the counters, and the loss quantities |

[thinkbook section 9](./fortunelabs_bolis_thinkbook.md#9-run-record-and-origin-labels) names the sections.

**The version.** A record carries `record_version`, and the first version is 1. That key is separate from `proto`, which names the control line contract, and from `manifest_version`, which names the firmware manifest layout, because the three contracts change on their own schedules. `record_version` rises when a key changes meaning, moves, or leaves ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

**A label beside a number.** Every number that states a quantity of the run is an object with two keys, `value` and `label`, and `label` holds `measured`, `configured`, `derived`, or `declared`. A number keeps its label when a reply quotes that number alone. A histogram is one object whose `value` holds the array of bin counts, because every bin shares one origin ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

```json
"packets_received": {"value": 1987, "label": "measured"},
"power_set_value": {"value": 44, "label": "configured"},
"loss_ratio": {"value": 0.0065, "label": "derived"},
"distance_m": {"value": 2.0, "label": "declared"}
```

The keys of the format itself carry no label. `record_version`, the index of an array, and the length of an array state the shape of the file rather than a quantity of the run, and a timestamp is text in RFC 3339 form with a `Z` suffix ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

**The four labels.** `[measured]` marks a value counted or read on a node during the run. `[configured]` marks a value that Bolis set. `[derived]` marks a value computed only from `[measured]` values. `[declared]` marks a value that the user typed and that Bolis did not check. A value computed from a `[configured]` or `[declared]` input carries the label of that input, not `[derived]` ([`2026-10-01-number-origin-labels.md`](./adr/2026-10-01-number-origin-labels.md), [thinkbook section 9](./fortunelabs_bolis_thinkbook.md#9-run-record-and-origin-labels)).

**A run that stops.** The `run` section carries `status`, which holds `complete` or `stopped`, and a `stopped` record carries `stopped_reason`. The host writes the record when a run stops, with the cells that ran ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

**A cell that a run invalidated.** Each entry of `cells` is one attempt. An entry carries `valid`, which holds false when the run invalidated that attempt, and the rerun of that cell is a further entry. A record therefore holds the attempt that failed beside the attempt that replaced it, so a reader filters on `valid` before computing a loss quantity ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md)).

**The loss quantities.** A broadcast pass states `first_attempt_loss`. A unicast pass states `post_retry_loss`. Both passes state `message_loss`. Each of the three is an object with `ratio`, `wilson_interval_low`, and `wilson_interval_high`, and each holds a `[derived]` number. The record holds the interval beside the ratio, because an interval that each reader computes again is an interval that two readers can disagree about, and the report reads these values rather than computing them. The level is fixed at 95% and no cell states it ([`2026-11-13-loss-quantities-in-a-cell.md`](./adr/2026-11-13-loss-quantities-in-a-cell.md)).

Each ratio divides counters that the same entry already states, over the cell and the pass of that entry:

- `first_attempt_loss.ratio` is `packets_sent` less `packets_received`, over `packets_sent`.
- `post_retry_loss.ratio` is `callback_failed` over `packets_sent`.
- `message_loss.ratio` is `messages_sent` less `messages_complete`, over `messages_sent`.

Message loss divides against the messages that the sender sent rather than the messages that the receiver saw, so a message that produced no fragment counts as lost. Each Wilson interval takes the same denominator as its ratio as the sample count. An entry whose `valid` is false states no loss quantity. A ratio whose denominator is zero is absent rather than zero ([`2026-11-13-loss-quantities-in-a-cell.md`](./adr/2026-11-13-loss-quantities-in-a-cell.md)).

**Privacy.** No key of the format holds a MAC address, and no key holds a device identifier. The `declared` section holds what the user typed ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md), [specification section 7](./fortunelabs_bolis_spec.md#7-data-handling)).

## 8. The report

The report builder reads the run record and writes one static HTML file, named `bolis-<run id>.html`, beside the record and in the directory that `--out` names. The file makes no network request ([thinkbook section 10](./fortunelabs_bolis_thinkbook.md#10-report-generation), [`2026-11-16-the-drift-band-and-the-record-link-of-a-report.md`](./adr/2026-11-16-the-drift-band-and-the-record-link-of-a-report.md)).

The sections follow [specification section 6](./fortunelabs_bolis_spec.md#6-report-contents) and [thinkbook section 10](./fortunelabs_bolis_thinkbook.md#10-report-generation):

- The test condition: the firmware path and hash, the ESP-IDF and ESP-NOW versions, $L$, the PHY rate, the country code, the run mode, the power-save mode, the state of the Bluetooth controller, and the declared geometry.
- One chart per swept variable and pass, with loss on the vertical axis. Each point carries its Wilson interval, and the drift band shows as a shaded range. Each chart states its mode and its loss quantity. The payload chart also shows message loss for payloads above $L$.
- For each unicast pass, the send-to-callback time histogram.
- One paragraph that names the variables that moved loss, with no cause. The baseline loss sits next to the paragraph, so a reader can recognize a baseline in a strong-signal region, where no variable moves loss.
- The coverage and the limits of the run, which are the claim-limit sentence, the 1 Mbps limit, the locality of the conclusions, and the absence of an interaction test.
- An origin label and a link to the run record beside every number, and a legend of the four labels.

**The drift band.** The drift band of one pass is a width. It is the difference between the highest and the lowest `ratio` of the loss quantity that the pass states, across the valid baseline cells of that pass. A broadcast pass reads `first_attempt_loss`, and a unicast pass reads `post_retry_loss`. A pass with fewer than two valid baseline cells has a drift band of 0. A chart shows the band as a shaded range from the lowest of those ratios to the highest ([`2026-11-16-the-drift-band-and-the-record-link-of-a-report.md`](./adr/2026-11-16-the-drift-band-and-the-record-link-of-a-report.md), [`2026-11-17-the-drift-band-of-a-unicast-pass.md`](./adr/2026-11-17-the-drift-band-of-a-unicast-pass.md)).

**The rule for moved loss.** A variable moved loss when two of its valid cells in one pass hold Wilson intervals that do not overlap and the difference between their ratios exceeds the drift band of that pass. The rule compares the ratios of the same quantity that the band read, so the band and the difference carry one unit on both passes. Both tests read the record and nothing else, so two readers of one record name the same variables. The paragraph names the variable, the two cells, and their values ([`2026-11-16-the-drift-band-and-the-record-link-of-a-report.md`](./adr/2026-11-16-the-drift-band-and-the-record-link-of-a-report.md), [`2026-11-17-the-drift-band-of-a-unicast-pass.md`](./adr/2026-11-17-the-drift-band-of-a-unicast-pass.md), [thinkbook section 10](./fortunelabs_bolis_thinkbook.md#10-report-generation)).

**The record link.** A number in a report links to `bolis-<run id>.json`, with a fragment that holds the JSON Pointer of the key that states it, as in `bolis-7.json#/cells/3/first_attempt_loss/ratio`. The report sits beside the record, so the link is relative. A browser opens the record and does not resolve the fragment inside it, so the fragment serves a reader who looks the key up and a tool that follows it ([`2026-11-16-the-drift-band-and-the-record-link-of-a-report.md`](./adr/2026-11-16-the-drift-band-and-the-record-link-of-a-report.md)).

**The mockup.** Until a verification pair passes, the repository shows a mockup with placeholders, and the mockup states that it is a mockup. `host/src/bolis/mockup.py` and `docs/mockup-report.html` reuse the text and the style of the report, so the mockup cannot drift from the report that a run writes ([specification section 6](./fortunelabs_bolis_spec.md#6-report-contents), [`2026-11-18-the-verification-pair-in-a-report.md`](./adr/2026-11-18-the-verification-pair-in-a-report.md)).

## 9. Reproducibility

A result counts as reproduced when a verification pair of two runs passes. Both runs use the same bench and the same declared geometry. Between the runs, both nodes are removed and placed again according to the declared geometry. The second run starts on a later calendar day. The pair passes when the baseline loss intervals of the two runs overlap and the lists of variables that moved loss are identical. Overlapping intervals are a weak test of equality, so the identical list carries most of the test ([`2026-10-01-reproducibility-verification.md`](./adr/2026-10-01-reproducibility-verification.md), [specification section 6](./fortunelabs_bolis_spec.md#6-report-contents)).

A pass shows that the declared geometry is enough to rebuild the result on the same bench. It does not show that the result holds on other hardware or at another site. A failed pair is published as a log entry in the same form as any other entry ([`2026-10-01-reproducibility-verification.md`](./adr/2026-10-01-reproducibility-verification.md)).

The `run` section of each record links to the other run of the pair ([thinkbook section 9](./fortunelabs_bolis_thinkbook.md#9-run-record-and-origin-labels)).

How a report states the pair is proposed and not settled. [`2026-11-18-the-verification-pair-in-a-report.md`](./adr/2026-11-18-the-verification-pair-in-a-report.md) carries `Status: Proposed`, so no statement of it governs, and code that relies on it does not merge ([`record-lifecycle.md`](./record-lifecycle.md)).

## 10. Failure handling

| Failure | Detection | Response |
|---|---|---|
| No image for the detected chip | Chip detection in the esptool Python API | Stop before writing, and name the supported chips |
| Different firmware on the two nodes | The `hello` replies | Stop before the first cell |
| WiFi already initialized, in a source build | `esp_wifi_get_mode` returns `ESP_OK` | `bol_start` returns `ESP_ERR_INVALID_STATE` and leaves the radio unchanged |
| `ESP_ERR_ESPNOW_NO_MEM` | Return code of `esp_now_send` | Wait, retry, and count |
| Node reset during a run | A new `hello` banner or a missing reply | Mark the cell invalid and rerun it once |
| Serial line loss | A reply timeout | Retry the command, then stop the run and keep the partial record |
| Channel mismatch | `ESP_ERR_ESPNOW_CHAN` | Stop the cell and report a configuration error |
| Truncated packets | Length and fill check | Flag the cell |

[thinkbook section 11](./fortunelabs_bolis_thinkbook.md#11-compatibility-failure-handling-and-distribution) states the table.

**Which failure a timeout names.** A timeout names one of three failures, and the host separates them by observation. If the transport reads a `hello` banner while a command is outstanding, the node reset, and the run marks the cell invalid and reruns it once. Otherwise the host retries the command once. A retry carries the next `seq`, and the transport discards every reply whose `seq` does not match the outstanding command. The retry budget is one, because the host cannot separate a lost line from a rejected line at the moment of a timeout and an identical retry reproduces a rejection. If the retry also times out, the host stops the run and keeps the partial record ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

The host does not retry a `go` command, because a retry sends the frames of a pass into a cell whose counters already moved. It marks the cell invalid and reruns it once, and if the rerun also falls silent it stops the run and keeps the partial record ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

A `hello` banner during a run costs the cell, because a reset node holds no role and no cell, so the host applies `role` and `cell` again before it reruns that cell ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

The `rejected_lines` counter separates a rejected line from a lost line after a run, and the host states it in the run record ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).

## 11. Distribution and release

The firmware, the component, and the base scripts are open. A developer must install, run, and read the report without contacting Fortune Labs, and a step that requires contact is a defect ([specification section 8.1](./fortunelabs_bolis_spec.md#81-the-rule)).

Bolis carries Apache-2.0. The scope is the firmware component, the example project, the host package, the run record schema, and the report builder. The repository root holds the full license text in `LICENSE`, the component manifest states `license: "Apache-2.0"`, and the host package states the same SPDX identifier in `pyproject.toml`. Fortunelabs HK holds the copyright ([`2026-10-01-apache-2-0-license.md`](./adr/2026-10-01-apache-2-0-license.md)).

The channels, in order, are the GitHub repository, PyPI, the ESP Component Registry, the PlatformIO registry, a direct reply on public threads, and a technical log. The GitHub repository comes first because every other channel links to it ([specification section 8.2](./fortunelabs_bolis_spec.md#82-channels-in-order)).

**The firmware images.** The host package carries one directory, `host/src/bolis/firmware/`. CI writes one image per supported chip and one `manifest.json` into that directory at release time, and git tracks neither the images nor the manifest. The manifest carries `manifest_version`, and the first version is 1. Each entry carries the file name, the SHA-256 of the image file, the ELF SHA-256 that the image reports in its `hello` reply, and the Bolis version that built it ([`2026-11-10-firmware-image-carriage.md`](./adr/2026-11-10-firmware-image-carriage.md)).

`bolis flash` detects the chip of each node through the esptool Python API, reads the manifest, and resolves the entry of the detected chip. It stops before it writes when the manifest names no entry for that chip. It computes the SHA-256 of the image file and refuses to write when the value differs from the entry. After the write, the host reads the `hello` reply and refuses the node when its `elf_sha256` differs from the entry. The run record states the ELF SHA-256 that the node reported, as a `[measured]` value ([`2026-11-10-firmware-image-carriage.md`](./adr/2026-11-10-firmware-image-carriage.md)).

Authenticity rests on the wheel that PyPI serves, because the manifest travels beside the images. The manifest detects corruption, and it does not detect substitution ([`2026-11-10-firmware-image-carriage.md`](./adr/2026-11-10-firmware-image-carriage.md)).

A source build reports the firmware path `source` and matches no manifest entry, so `bolis flash` serves the prebuilt path alone ([`2026-11-10-firmware-image-carriage.md`](./adr/2026-11-10-firmware-image-carriage.md)).

**Compatibility.** CI builds the component on ESP-IDF v5.5 and on each later minor release that Espressif supports. ESP-IDF v5.5 is supported through 2028-01-21, and a new record settles whether to raise the minimum before that date. The first chip is the ESP32, and the ESP32-S3, ESP32-C3, and ESP32-C6 follow as hardware allows, each with its own prebuilt image ([`2026-10-01-esp-idf-v5-5-minimum.md`](./adr/2026-10-01-esp-idf-v5-5-minimum.md), [thinkbook section 11](./fortunelabs_bolis_thinkbook.md#11-compatibility-failure-handling-and-distribution), [`2026-10-01-radio-ownership-and-prebuilt-firmware.md`](./adr/2026-10-01-radio-ownership-and-prebuilt-firmware.md)).

## 12. The coding baseline and the checks

Bolis C code follows MISRA C:2012 with Amendment 1 and Amendment 2, and the 99 rules of the SEI CERT C Coding Standard, 2016 Edition. If both standards cover a construct, the stricter rule applies. MISRA Compliance:2020 defines the compliance process. The component compiles with `-std=gnu17` on every supported ESP-IDF version, so Bolis C code cannot use C23 features even on ESP-IDF v6.x. ESP-IDF, FreeRTOS, newlib, the radio drivers, and managed components are adopted code, outside the check. The deviation records, the guideline compliance summary, and the list of implementation-defined behavior live in [`docs/compliance/`](./compliance/) ([`2026-10-01-misra-c-2012-coding-baseline.md`](./adr/2026-10-01-misra-c-2012-coding-baseline.md)).

The cppcheck MISRA addon and a manual review check the MISRA guidelines, and clang-tidy checks the CERT rules ([`2026-10-01-misra-c-2012-coding-baseline.md`](./adr/2026-10-01-misra-c-2012-coding-baseline.md)).

CI pins cppcheck 2.19.1, builds that version from source inside the container, prints the version that the build produced, and fails if the printed version differs from the pin. Every compliance claim names the checker version that produced it, and a change of the pinned version updates the workflow and the compliance summary in one change ([`2026-11-09-cppcheck-version-pin.md`](./adr/2026-11-09-cppcheck-version-pin.md)).

The reader test cases run on the host. `components/bolis/test/host_runner.c` supplies the hooks that `unity_config.h` of ESP-IDF expects, and `tools/prep test` compiles that runner, the test file, the reader source, and the unity sources of ESP-IDF with the host compiler, then runs the result. The host path covers the reader alone. The host compiler is not the target compiler, so CI on the linux target and a run on a node stay the authority ([`2026-11-06-host-execution-of-the-reader-tests.md`](./adr/2026-11-06-host-execution-of-the-reader-tests.md)).

The Python code of the host package follows a separate standard, outside the C baseline ([`2026-10-01-misra-c-2012-coding-baseline.md`](./adr/2026-10-01-misra-c-2012-coding-baseline.md)).

The status of a decision record and the status of a deviation record change under the conditions that [`record-lifecycle.md`](./record-lifecycle.md) states.

## 13. What this file does not state

- The values of the placeholders in specification sections 5, 8.4, 9, and 11 ([specification section 13](./fortunelabs_bolis_spec.md#13-open-items)).
- Whether a sample peer firmware is included for users with one ESP32 ([specification section 13](./fortunelabs_bolis_spec.md#13-open-items)).
- Whether a field version follows v0, or waits for demand from three users ([specification section 13](./fortunelabs_bolis_spec.md#13-open-items)).
- The split between the base at Fortunelabs HK and the v0 layer at PT Indonesia ([specification section 10](./fortunelabs_bolis_spec.md#10-entity-handling), [specification section 13](./fortunelabs_bolis_spec.md#13-open-items)).
- The trademark database checks for the name ([specification section 2](./fortunelabs_bolis_spec.md#2-name-and-identifiers), [specification section 13](./fortunelabs_bolis_spec.md#13-open-items)).
- A confirmation of the claim that no ready tool covers the same job. The claim stays `[borrowed]` ([specification section 13](./fortunelabs_bolis_spec.md#13-open-items), [thinkbook section 5](./fortunelabs_bolis_thinkbook.md#5-prior-work-and-the-gap)).
- The five facts of the bench spike ([specification section 13](./fortunelabs_bolis_spec.md#13-open-items), [thinkbook Part 3](./fortunelabs_bolis_thinkbook.md)).
- The settle time between the last `go` reply and a `stats` command ([`2026-11-12-serial-transport-reply-timeouts.md`](./adr/2026-11-12-serial-transport-reply-timeouts.md)).
- A timebase shared across the two nodes, energy, and one-way delay. All three stay outside v0 ([specification section 4](./fortunelabs_bolis_spec.md#4-scope), [thinkbook section 7](./fortunelabs_bolis_thinkbook.md#7-firmware-component-and-control-protocol), [`2026-11-11-control-line-command-fields.md`](./adr/2026-11-11-control-line-command-fields.md)).
- A record that gates a dependency of the host package. The dependency scope record covers components of the firmware alone ([`2026-11-12-run-record-format.md`](./adr/2026-11-12-run-record-format.md), [`2026-10-01-scope-the-dependency-rule.md`](./adr/2026-10-01-scope-the-dependency-rule.md)).
