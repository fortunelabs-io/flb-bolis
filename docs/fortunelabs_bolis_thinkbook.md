# Bolis thinkbook

*Fortune Labs. Thinkbook v0.2. 2026-10-01. Companion to the Bolis v0 specification, v0.4.*

This thinkbook holds the theory and the high-level design behind Bolis. The specification states what v0 delivers. This thinkbook states the mechanisms the design rests on and the shape of the design. Where the two disagree, the specification governs until the founder accepts a change. Part 3 lists the decision records behind this version.

**Labels.** A statement marked `[borrowed]` comes from documentation or a third party, and Fortune Labs has not rerun it. A statement marked `[proposal]` is a design choice or a model that no run has confirmed. No number in this thinkbook is `[measured]`. Section 9 defines the labels for numbers in Bolis artifacts. A key such as [S1] points to the sources at the end.

**Change from v0.1.** Seven decision records changed this thinkbook. Sections 1 and 3.1 state the v2.0 payload limit per ESP-IDF version: 1470 bytes on v5.5 and later, and 1490 bytes on v5.4. Section 3.7 states the independence assumption behind the intervals. Section 4 adds the interactions between the variables. Part 2 now describes prebuilt firmware plus a host CLI, a broadcast pass in every run, a unicast pass in unicast runs, four number labels, and a defined reproducibility verification. Part 3 lists the decision records and the checks for the bench spike. Formulas use LaTeX notation, and section 3.7 writes loss as $\ell$, so $p$ always means a payload size. The section numbers stay unchanged, because the decision records cite them.

---

## Part 1. Theoretical foundations

### 1. ESP-NOW at the link layer

ESP-NOW sends application data inside an IEEE 802.11 vendor-specific action frame, without a connection between the devices. [S1] `[borrowed]`

**Frame layout.** [S1] `[borrowed]`

| Part | Size |
|---|---|
| MAC header | 24 bytes |
| Category code | 1 byte |
| Organization identifier | 3 bytes |
| Random value | 4 bytes |
| Vendor-specific content | One or more elements. Each element has a 7-byte header and a body of up to 250 bytes |
| FCS | 4 bytes |

**Versions.** A v1.0 packet carries up to 250 bytes. A v2.0 packet spreads its payload across up to six elements inside one frame. The v2.0 limit depends on the ESP-IDF version: 1470 bytes on v5.5 and later, and 1490 bytes on v5.4. [S21] [S22] A v2.0 device receives both versions. A v1.0 device receives a v2.0 packet only up to 250 bytes, and truncates or discards a longer one. [S1] ESP-IDF supports v2.0 from v5.4. [S8] `[borrowed]`

**Rate and channel access.** The default bit rate is 1 Mbps. [S1] A 2025 study observed 802.11b frames at 1 Mbps on a 20 MHz channel, a slotted p-persistent backoff with slots of about 481 µs, and up to 31 retransmissions of one frame. [S5] A public ESP-IDF issue reports that the ESP32-C6 driver fixes the retry limit at 31. [S9] `[borrowed]`

**Acknowledgement.** The send callback reports success when the frame arrives at the MAC layer of the peer. Success does not guarantee that the application receives the data. [S1] Broadcast frames carry no acknowledgement and no retransmission. [S11] `[borrowed]`

**Peers and channel.** A peer's channel equals the local channel, or 0 for the current channel. A device holds at most 20 peers. [S1] `[borrowed]`

**Receive metadata.** From ESP-IDF v5.1, the receive callback carries the receive control fields, which include RSSI. [S3] `[borrowed]`

### 2. What loss means

"Frame loss" names three different quantities. Each quantity needs its own observable.

| Quantity | Definition | Observable |
|---|---|---|
| First-attempt loss | Share of frames whose first transmission fails | Sequence gaps at the receiver in broadcast mode, where no retry exists |
| Post-retry loss | Share of unicast frames that fail after all retries | Send callback failures at the sender |
| Message loss | Share of application messages of $p$ bytes that do not arrive whole | Missing fragments per message at the receiver |

Three further observables carry information about the link.

- **Send-to-callback time** at the sender. Each retry adds backoff time, so the distribution of this time shows the retry structure. The 2025 study rebuilt field delay distributions from this structure. [S5] `[borrowed]`
- **Duplicates** at the receiver in unicast mode. A lost acknowledgement causes a retry of a frame that already arrived, so the receiver sees one sequence number twice. The ESP-IDF guide recommends sequence numbers to drop duplicates. [S1] `[borrowed]`
- **Loss run lengths** at the receiver. They show whether losses arrive alone or in bursts.

In unicast, retries hide a degrading link until the driver exhausts its retries. Post-retry loss stays near zero and then rises fast (section 3.5). In broadcast, loss follows the first-attempt failure rate of the link.

Bolis therefore reports broadcast first-attempt loss in every run. In a unicast run, each cell adds a unicast pass, and the report adds post-retry loss and the send-to-callback time histogram for that pass. Each chart states its mode and its loss quantity (decision 1).

### 3. Cost and loss model

This section holds the formal model. Every model here is a `[proposal]` until a run tests it.

**3.1 Packet count.** An application message of $p$ bytes, with a maximum payload $L$ per packet, needs $n(p)$ packets.

$$n(p) = \left\lceil \frac{p}{L} \right\rceil$$

For v1.0, $L = 250$. For v2.0, $L = 1470$ on ESP-IDF v5.5 and later, and $L = 1490$ on v5.4 (section 1). Bolis requires v5.5 (decision 3), so the model uses $L = 1470$ for v2.0. Inside one v2.0 frame, the payload spreads over $k(p)$ elements.

$$k(p) = \left\lceil \frac{p}{250} \right\rceil$$

**3.2 Bytes on air.** One frame with payload $p$ occupies $B(p)$ bytes.

$$B(p) = 36 + p + 7\,k(p)$$

The 36 bytes are the MAC header, category code, organization identifier, random value, and FCS (section 1).

**3.3 Airtime.** At rate $R$, with the 192 µs long preamble and header of 802.11b, one frame occupies $T(p)$.

$$T(p) = 192\ \mu\text{s} + \frac{8\,B(p)}{R}$$

| Case | $p$ | $k(p)$ | $B(p)$ | $T(p)$ at 1 Mbps |
|---|---|---|---|---|
| v1.0, full packet | 250 bytes | 1 | 293 bytes | 2.54 ms |
| v2.0, full packet | 1470 bytes | 6 | 1548 bytes | 12.58 ms |

The 2025 study measured 2.67 to 2.78 ms from hand-off to first reception for 250-byte payloads. [S5] `[borrowed]` The model plus software latency fits that range.

**3.4 Frame error.** If bit errors arrive independently at rate $e$, a frame with payload $p$ fails with probability $F(p)$.

$$F(p) = 1 - (1 - e)^{8\,B(p)}$$

A message of $n(p)$ packets arrives whole with probability $P_{\text{whole}}(p)$, where $p_i$ is the payload of packet $i$.

$$P_{\text{whole}}(p) = \prod_{i=1}^{n(p)} \bigl(1 - F(p_i)\bigr)$$

Two predictions follow.

1. v1.0 with fragmentation by Bolis: message loss rises by one step at $p = 251$, $p = 501$, and each further multiple of 250 plus one. Each step adds a packet with its own chance to fail. This is the step pattern that $n(p)$ predicts and that the payload sweep targets.
2. v2.0: inside one frame, each element boundary adds only 7 bytes, so loss rises smoothly through 250 and 500. The step moves to $p = L + 1$, which is $p = 1471$.

**3.5 Retry cliff.** If each attempt fails independently with probability $q$, and the driver allows $r$ retries, post-retry loss is $P_{\text{post}}$.

$$P_{\text{post}} = q^{\,r+1}$$

With $r = 31$, $q = 0.5$ gives about $2.3 \times 10^{-10}$, and $q = 0.9$ gives about 0.034. Unicast loss therefore stays near zero until first-attempt loss approaches 1, then rises fast. Real channels produce correlated failures, so a real cliff is softer than this model.

**3.6 Bursts.** Independence fails when interference arrives in bursts. A two-state model (Gilbert-Elliott) describes this case: a good state with low loss, a bad state with high loss, and transition rates between them. The run-length histogram in each cell record allows a later fit of this model.

**3.7 Intervals and frames per cell.** The loss estimate of a cell is $\hat{\ell}$.

$$\hat{\ell} = \frac{\text{lost}}{\text{sent}}$$

The report uses the Wilson score interval at 95%. For a half-width $h$ at loss $\ell$, a cell needs about $N$ frames.

$$N \approx \frac{1.96^2\,\ell\,(1 - \ell)}{h^2}$$

| Expected loss | Half-width | Frames per cell |
|---|---|---|
| 5% | 1 percentage point | 1825 |
| 1% | 0.5 percentage points | 1522 |

With zero losses in $N$ frames, the 95% upper bound is about $3/N$ (the rule of three). At $N = 2000$, zero losses bound the loss below 0.15%.

The Wilson interval assumes that losses are independent. On an 802.11b mesh network, loss behaved as independent at time scales below about 0.1 s. At longer time scales, a minority of links showed bursty loss with correlation out to at least 1 s, and most links varied by only a few percent from one second to the next. [S32] `[borrowed]` A cell lasts several seconds (section 3.8), so on a bursty link the interval is too narrow. The run-length histogram (section 3.6) flags such a cell.

**3.8 Time per cell.** One community test sent about 320 frames per second, about 0.6 Mbit/s of payload. [S11] `[borrowed]` At that rate a 2000-frame cell takes about 6.3 s. A cell of 1470-byte v2.0 frames needs at least $2000 \times 12.58\ \text{ms}$, about 25 s of airtime. A unicast pass of the same cell lasts at least as long, and each retry adds backoff time.

### 4. Variables and confounds

Mechanisms with a source key are `[borrowed]`. Treatments are `[proposal]` unless a decision record locks them.

| Variable | Mechanism | Treatment in v0 | Recorded as |
|---|---|---|---|
| Channel | Other 2.4 GHz traffic on the same or an adjacent channel. The country setting limits the channels. The default setting "01" allows 1 to 11 [S2]. Both nodes share one channel [S1] | Swept | Channel, country code, RSSI |
| Transmit power | Sets the received power. Set values quantize to 11 levels from 2 to 20 dBm [S2]. At high power, nodes close together can overload the receiver [S12] | Swept over the 11 levels | Requested and read-back power |
| Payload size | Airtime and packet count (section 3) | Swept around the boundaries. The firmware takes $L$ from `ESP_NOW_MAX_DATA_LEN_V2` at compile time (decision 3) | $p$, $n(p)$, $k(p)$, ESP-NOW version, $L$ |
| PHY rate | Sets airtime and receiver sensitivity. The default is 1 Mbps. The API cannot read the rate back [S1] [S8] | Fixed at 1 Mbps for every pass (decision 2) | Configured rate |
| Power save | The default is `WIFI_PS_MIN_MODEM` [S2]. A device in modem sleep does not receive ESP-NOW data [S3] | Disabled on both nodes | Power-save mode |
| Bluetooth controller | The ESP32 shares the radio between WiFi and Bluetooth by time-division multiplexing, so an active controller takes time slices from WiFi [S35] | Disabled in the prebuilt image. A source build follows the sdkconfig of the user (decision 7) | Controller state |
| Geometry | Small changes in position or orientation change delivery sharply [S5] | Fixed per run | Distance, orientation, antenna, and enclosure, declared by the user |
| Software versions | Callback signatures, payload limits, and driver behavior change across ESP-IDF versions [S3] [S4] [S21] [S22] | Fixed per run. The prebuilt images use ESP-IDF v5.5.x, and source builds need v5.5 or later (decisions 3 and 7) | Firmware path, firmware hash, and the ESP-IDF, ESP-NOW, and Bolis versions |
| Chip | The retry limit and the power limits differ by chip [S9] | Fixed per run | Chip model and revision |
| Drift | Other traffic changes during a run | A baseline cell repeated through the run | Baseline loss over time |

The country codes that `esp_wifi_set_country_code` accepts include HK and do not include ID. [S2] `[borrowed]`

**Interactions between variables.** The variables in the table do not act alone. Packet loss grows with packet size at a rate that depends on the channel condition. [S29] Inside a transitional region of received power, a small change of transmit power or receiver position swings delivery, and outside that region the same change leaves delivery unchanged. Delivery in that region also varies over time, including between day and night. [S30] [S31] A sweep that changes one variable at a time therefore finds effects that hold only at its baseline. A factorial design estimates effects with less variance per run and detects interactions. [S33] A one-variable-at-a-time design that adapts to its results can do better for improvement when experimental error is small and interactions are strong. [S34] `[borrowed]` Bolis describes the configuration of the user and does not optimize it, so v0 keeps the one-variable-at-a-time plan and states its locality (decision 4).

### 5. Prior work and the gap

- **Distance studies.** Published studies measure delivery, latency, and range against distance: indoors [S6], outdoors in farmland and forest [S5], in a field test in Tanjungpinang [S7], and against WiFi and Bluetooth [S20]. The 2025 study notes that the earlier studies used default protocol settings. [S5] `[borrowed]`
- **Espressif tools.** The wireless_debug example of the espressif/esp-now component offers manual commands to set the channel, PHY rate, transmit power, and country code. It also offers an iperf command with ping and throughput modes. [S10] `[borrowed]`
- **Community testers.** Range testers count sequence gaps and print the result over serial [S13], or log received packets while a person carries one node to a greater distance [S11]. `[borrowed]`

No tool found runs an automatic sweep across configuration variables and writes one report with origin labels. Specification open item 6 records this result: the primitives exist, and the automation and the report do not. The search is shallow, so the claim stays `[borrowed]`. Espressif can add a sweep to wireless_debug at low cost. If it does, Bolis differs only in its report format and its corpus.

---

## Part 2. High-level design

Every design choice in Part 2 is a `[proposal]` until a run confirms it. Where a decision record locks a choice, the text names the record by its number in Part 3, for example (decision 4).

### 6. System overview

```
                    USB serial                    USB serial
                 (control plane)               (control plane)
 +------------------+       +---------------------+       +------------------+
 | Node A: sender   |<----->|  Host: bolis CLI    |<----->| Node B: receiver |
 | ESP32            |       |  flasher            |       | ESP32            |
 | Bolis firmware   |       |  orchestrator       |       | Bolis firmware   |
 +---------+--------+       |  run record writer  |       +---------^--------+
           |                |  report builder     |                 |
           |                +---------------------+                 |
           |                                                        |
           +------------- ESP-NOW frames (data plane) --------------+
```

Bolis has two planes. The data plane is the ESP-NOW link under test. The control plane is a USB serial line from the host to each node. The control plane never uses the radio, so a failing channel cannot break the coordination of a channel change.

Both nodes run the same firmware image. The host assigns the sender role and the receiver role at run time (decision 7). The diagram shows one assignment.

| Part | Runs on | Job |
|---|---|---|
| Bolis firmware | Both nodes | Takes a role from the host, applies each cell, sends or receives frames, counts, and reports |
| `bolis` host CLI, Python | The host | Flashes the nodes, orchestrates the sweep, writes the run record, and builds the report |
| `bol_` component | Source builds | Holds the firmware logic. The prebuilt images and the example project `examples/bench` build from it |
| Run record | A JSON file | Holds the conditions, the counters, and a label for every number |
| Report | A static HTML file | Shows the charts, the paragraph, the limits, and the label legend |

The user flow in specification section 5 maps to the design as follows.

1. Install the host package: `pip install bolis`.
2. Connect two ESP32 boards to the host by USB.
3. Flash both boards: `bolis flash <port> <port>`. The CLI detects the chip, takes the image for that chip from the package, and writes the same image to both boards through the esptool Python API. [S23]
4. Run the sweep: `bolis run <port> <port> --channel <c> --power <set value> --payload <bytes>`. The options give the configuration of the user as the baseline. Without them, Bolis uses the fallback baseline (section 8). The first port takes the sender role. `--mode unicast` adds the unicast pass (decision 1).
5. Receive one report file: `bolis-<run id>.html`, next to the run record.

A user who needs a specific ESP-IDF version or sdkconfig replaces step 3 of the default path with a source build. The user creates the example project with `idf.py create-project-from-example "fortunelabs-io/bolis:bench"`, then builds and flashes it with `idf.py` on ESP-IDF v5.5 or later. Step 4 stays the same.

The design needs both nodes on USB to one host. Specification section 4 places both nodes on one bench, so the constraint holds for v0.

### 7. Firmware component and control protocol

```c
esp_err_t bol_start(void);
```

`bol_start` first calls `esp_wifi_get_mode`. If the call returns anything other than `ESP_ERR_WIFI_NOT_INIT`, WiFi is already initialized, and `bol_start` returns `ESP_ERR_INVALID_STATE` without changing the radio (decision 7). Otherwise, `bol_start` initializes WiFi in station mode, disables power save, sets the country code, initializes ESP-NOW, registers the callbacks, and starts a control task on the console. The component sets 1 Mbps for every peer it adds (decision 2). It reads the state of the Bluetooth controller for the `hello` reply. The `app_main` of the prebuilt image and of `examples/bench` calls only `bol_start`. The role is no longer an argument of the function. The host sends it through the control protocol.

The prebuilt image builds with the Bluetooth controller disabled and with a Kconfig option that marks the image as prebuilt. A source build leaves that option off, so the `hello` reply states the firmware path.

**Control lines.** Control lines share the console with the application log. Each control line starts with `@bol ` and carries one JSON object. The host ignores every other line.

| Command | Sent to | Reply |
|---|---|---|
| `hello` | Both nodes | Chip, revision, ESP-IDF version, ESP-NOW version, $L$, Bolis version, firmware path, the ELF SHA-256 from the application description, and the state of the Bluetooth controller |
| `role` | Both nodes | The role the node took. The sender also receives the MAC address of the receiver for the unicast pass |
| `cell` | Both nodes | The applied condition, with the read-back transmit power |
| `go` | The sender | `done` when the callback of the last frame of the pass returns |
| `stats` | Both nodes | The counters of the pass |

```
Host                     Sender                   Receiver
 |-- cell c ------------------------------------------>|  set channel, arm
 |<------------------------------------------ ack c ---|
 |-- cell c ------------->|                            |
 |<------------- ack c ---|                            |
 |-- go c, broadcast ---->|~~~~ ESP-NOW frames ~~~~~~~>|
 |<------------- done c --|                            |
 |   (settle time)        |                            |
 |-- stats c ----------------------------------------->|
 |<----------------------------------- rx counters ----|
 |-- stats c ------------>|                            |
 |<--------- tx counters -|                            |
```

The host sets the receiver first, so the receiver listens on the new channel before the first frame leaves the sender. A settle time after `done` catches late frames before the receiver reports. In a unicast run, the host repeats `go` and `stats` with the unicast pass before it moves to the next cell (decision 1). The host holds MAC addresses only in memory (section 9).

**Data frame.** Each ESP-NOW packet starts with a 14-byte header.

| Field | Size | Purpose |
|---|---|---|
| Magic | 2 bytes | Marks a Bolis packet |
| Run ID | 4 bytes | Rejects packets from another run |
| Cell ID and pass | 2 bytes | The low 15 bits name the cell, and the top bit names the pass. Rejects late packets from the previous cell or pass |
| Message ID | 4 bytes | Orders messages and exposes gaps |
| Fragment index and count | 2 bytes | Rebuilds messages of $n(p)$ packets |
| Fill | $p - 14$ bytes | A pattern derived from the header, to detect truncation and corruption |

The smallest swept payload is therefore 14 bytes.

**Sender.** The sender sends the next packet after the callback of the previous packet returns, as the ESP-IDF guide recommends. [S1] It counts `esp_now_send` errors by code. On `ESP_ERR_ESPNOW_NO_MEM`, it waits, retries, and counts the event. It bins the send-to-callback time into a histogram in memory, so the serial line carries only the histogram.

**Receiver.** The receive callback runs in the WiFi task, so it only copies the packet header, the length, and the RSSI to a queue. [S1] A lower-priority task checks the header and the fill, tracks sequence numbers per cell and pass, and updates the counters.

Each node keeps one set of counters per pass.

| Counter | Node |
|---|---|
| Messages and packets sent | Sender |
| `esp_now_send` errors, by code | Sender |
| Callback successes and failures | Sender |
| Send-to-callback time histogram | Sender |
| Packets received, duplicates, packets from another cell or pass | Receiver |
| Messages complete and incomplete | Receiver |
| Loss run-length histogram | Receiver |
| RSSI minimum, mean, and maximum | Receiver |
| Truncated or corrupt packets | Receiver |

**Timebase.** One-way delay needs a shared timebase across the two nodes. Obol provides one through GPIO phase markers. v0 measures only the send-to-callback time, on the sender's own clock. Energy stays out of v0 (specification section 4), and a later version takes it from Obol.

### 8. Sweep design

A cell is one condition: channel, transmit power, and payload size. A cell runs one pass per mode: a broadcast pass in every run, and a unicast pass after it in a unicast run (decision 1). Every pass sends $N$ frames at 1 Mbps (decision 2). The default plan changes one variable at a time around a baseline (decision 4).

| Variable | Points |
|---|---|
| Channel | Every channel the country setting allows. Under "01" this is 1 to 11 |
| Transmit power | The 11 set values 8, 20, 28, 34, 44, 52, 56, 60, 66, 72, and 80, which map to 2 to 20 dBm |
| Payload, v1.0 | 14, 128, 249, 250, 251, 499, 500, and 501 bytes |
| Payload, v2.0 | 14, 250, 251, 1469, 1470, 1471, 2940, and 2941 bytes |

- **Payload list.** A run uses one payload list. The v2.0 list follows $L = 1470$ (section 3.1) and is the default. `--limit 250` selects the v1.0 list for an application that keeps its packets within 250 bytes. The firmware then fragments messages at 250 bytes.
- **Baseline.** The baseline is the configuration of the user: channel, transmit power, and payload size. Without a configuration, Bolis uses the fallback baseline: channel 1, power set value 44 (11 dBm), and payload 128 bytes. The middle power level keeps the fallback away from receiver overload on a bench. The run record states which baseline applied.
- **Order.** The host shuffles the cells with a seed and records the seed, so slow drift spreads across all variables.
- **Drift band.** The baseline cell repeats after every 5 cells. The spread of these repeats forms the drift band.
- **Frames per cell.** $N = 2000$ per cell and pass (section 3.7).
- **Duration.** The default plan has about 36 cells per pass. A broadcast run sends about 72,000 frames, which takes about 4 minutes of sending for small payloads plus control time. Each cell of 1470-byte frames adds about 25 s of airtime (section 3.8). A unicast run doubles the frames and the time: about 144,000 frames and about 8 minutes. The full grid of 11 channels, 11 power levels, and 8 payloads has 968 cells, about 1.9 million frames per pass, and about 1.7 hours per pass. The user selects the grid with `--plan grid`.
- **Limits.** The report states that its conclusions hold at the baseline and that the sweep does not test interactions (section 4).

**Long-run guard.** A public issue reports that ESP-NOW stops sending after about 78,000 broadcast frames on one ESP-IDF v5.x build, with `ESP_ERR_ESPNOW_NO_MEM`. [S14] `[borrowed]` A broadcast run sends about 72,000 frames, close to that figure, and a unicast run sends about 144,000. The guard is therefore required (decision 1). The firmware re-initializes ESP-NOW between passes, adds the peers again with the 1 Mbps rate, and counts `ESP_ERR_ESPNOW_NO_MEM`. The bench spike checks whether the problem exists on a native ESP-IDF build (Part 3).

### 9. Run record and origin labels

The host writes one JSON file per run: `bolis-<run id>.json`.

| Section | Contents |
|---|---|
| `run` | Run ID, start and end time in UTC, Bolis version, run mode, plan, shuffle seed, and the run ID of the other run in a verification pair |
| `firmware` | Firmware path (prebuilt or source), ELF SHA-256, ESP-IDF version, ESP-NOW version, and the v2.0 payload limit $L$ |
| `nodes` | Role, chip model, and chip revision of each node |
| `setup` | Country code, PHY rate, power-save mode, state of the Bluetooth controller, payload list, and baseline source (user or fallback) |
| `declared` | Distance, orientation, antenna, enclosure, and surroundings, as the user typed them |
| `cells` | For each cell and pass: the mode, the condition, the read-back values, the counters, and the loss quantities |

The record stores no MAC address. The host uses MAC addresses only in memory, to pair the nodes and to address the unicast pass. This follows specification section 7.

Every number in the record and the report carries one of four labels (decision 5).

| Label | Meaning | Example |
|---|---|---|
| `[measured]` | Counted or read on a node during the run | Packets received, RSSI, read-back transmit power |
| `[configured]` | A value that Bolis set | Requested transmit power, PHY rate, payload size, state of the Bluetooth controller |
| `[derived]` | Computed only from `[measured]` values | Loss ratio, Wilson interval |
| `[declared]` | Typed by the user and not checked by Bolis | Distance, antenna |

A value computed from a `[configured]` or `[declared]` input carries the label of that input, not `[derived]`. For example, $n(p)$ computed from the payload size carries `[configured]`. Each report carries a legend of the four labels. The labels for claims in Fortune Labs documents, such as the labels in this thinkbook, stay separate from these labels for numbers.

### 10. Report generation

The report builder reads the run record and writes one static HTML file. The file makes no network request. Its sections follow specification section 6.

- The test condition: the firmware path and hash, the ESP-IDF and ESP-NOW versions, $L$, the PHY rate, the country code, the run mode, the power-save mode, the state of the Bluetooth controller, and the declared geometry.
- One chart per swept variable and pass. Loss sits on the vertical axis. Each point carries its Wilson interval. The drift band shows as a shaded range. Each chart states its mode and its loss quantity: broadcast first-attempt loss, or unicast post-retry loss. The payload chart also shows message loss for payloads above $L$.
- For each unicast pass, the send-to-callback time histogram.
- One paragraph that names the variables that moved loss, with no cause. The baseline loss sits next to the paragraph, so a reader can recognize a baseline in a strong-signal region, where no variable moves loss (decision 4).
- The coverage and the limits of the run: the claim-limit sentence from specification section 4, the 1 Mbps limit, the locality of the conclusions, and the absence of an interaction test.
- An origin label and a link to the run-record entry beside every number, and a legend of the four labels (decision 5).

**Rule for "moved loss".** A variable moved loss if two of its cells have Wilson intervals that do not overlap, and their difference exceeds the drift band. The rule runs on the broadcast pass. In a unicast run, it also runs on the unicast pass, and the paragraph names the pass. The paragraph names the variable, the two cells, and their values. The rule is mechanical, so two readers of the same record reach the same paragraph.

**Reproducibility verification.** A result counts as reproduced when a verification pair of two runs passes (decision 6). Both runs use the same bench and the same declared geometry. Between the runs, the founder removes both nodes and places them again according to the declared geometry. The second run starts on a later calendar day. The pair passes when the baseline loss intervals of the two runs overlap and the lists of variables that moved loss are identical. Overlapping intervals are a weak test of equality, so the identical list carries most of the test. The `run` section of each record links to the other run of the pair. Until a pair passes, the repository shows the labeled mockup (specification section 6). A failed pair becomes a log entry.

### 11. Compatibility, failure handling, and distribution

**Compatibility.**

- The minimum ESP-IDF version is v5.5 (decision 3). The v5.4 header defines a send callback that takes the MAC address of the peer, and sets `ESP_NOW_MAX_DATA_LEN_V2` to 1490 bytes. The v5.5 header defines a send callback that takes `esp_now_send_info_t`, and sets the limit to 1470 bytes. [S21] [S22] The v6.1 documentation shows the same send callback as v5.5. [S1] `[borrowed]`
- Espressif supports each release for 30 months: 12 months of service and 18 months of maintenance. ESP-IDF v5.4 was released on 2025-01-04, so its support ends about July 2027. ESP-IDF v5.5 is supported through 2028-01-21. [S26] [S27] [S28] `[borrowed]` A new decision record settles whether to raise the minimum before that date.
- Bolis uses one send callback signature and takes $L$ from `ESP_NOW_MAX_DATA_LEN_V2` at compile time. CI builds the component on v5.5 and on each later minor release that Espressif supports. One project met the callback change only when a user moved from v5.4 to v6.0.1, because its CI ran v5.4. [S15] `[borrowed]`
- The per-peer rate API exists from v5.2, and the older rate API is gone in v6.0. [S3] `[borrowed]`
- The first chip is the ESP32. The ESP32-S3, ESP32-C3, and ESP32-C6 follow as hardware allows. Each supported chip needs its own prebuilt image (decision 7).

**Failure handling.**

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

**Distribution.** `[borrowed]` facts, `[proposal]` order.

- PyPI. The `bolis` host package carries one prebuilt image per supported chip, so flashing needs no network access. The CLI flashes through the esptool Python API, which detects the chip and writes images to flash. [S23]
- GitHub release. CI builds each image from the tagged source on ESP-IDF v5.5.x. Each release carries the images, the hash of each image, and the ELF SHA-256 that each image reports in `hello`, so a reader can match a run record to a release.
- ESP Component Registry, for source builds. The manifest needs only a version, and the license field takes an SPDX identifier. [S16] The registry uses the GitHub account name as the default namespace, and a staging registry exists for tests. [S17] Examples go in an `examples` directory and use `override_path` to find the component in the repository. [S16] `examples/bench` is the source-build path.
- PlatformIO. A library in `lib_deps` builds with the PlatformIO build system, and its root `CMakeLists.txt` goes unused. [S18] The pioarduino platform ships ESP-IDF v5.5.5 in its stable release. [S19] ESP-IDF v6 users cannot reach Bolis through this channel. PlatformIO therefore follows the registry, after the first registry release. PlatformIO users can also run the default path.
- Browser flasher, a candidate for a later version. Espressif offers ESP Launchpad, so that users can try prebuilt firmware without ESP-IDF. [S24] WLED, Tasmota, ESPHome, and ESPEasy install from the browser through ESP Web Tools. [S25]

---

## Part 3. Decision records

The records sit in the `docs/adr/` folder. Part 2 cites them by number.

| No. | Decision | Record |
|---|---|---|
| 1 | Broadcast first-attempt loss as the base metric, with a unicast pass for unicast applications | `2026-10-01-loss-metric-and-send-mode.md` |
| 2 | PHY rate fixed at 1 Mbps for v0 | `2026-10-01-phy-rate-fixed-at-1-mbps.md` |
| 3 | ESP-IDF v5.5 as the minimum version | `2026-10-01-esp-idf-v5-5-minimum.md` |
| 4 | Local one-variable-at-a-time sweep, with 2000 frames per cell | `2026-10-01-local-one-variable-sweep.md` |
| 5 | Origin labels for numbers in Bolis artifacts | `2026-10-01-number-origin-labels.md` |
| 6 | Reproducibility verification by re-placing the nodes on a later day | `2026-10-01-reproducibility-verification.md` |
| 7 | Radio ownership and prebuilt firmware as the default path | `2026-10-01-radio-ownership-and-prebuilt-firmware.md` |

**Checks for the bench spike.** The bench spike checks five facts before the code grows. Specification open item 7 holds the same list.

1. Whether `esp_now_set_peer_rate_config` applies to the broadcast peer (decision 2).
2. Whether the send failure near 78,000 broadcast frames occurs on a native ESP-IDF build (decision 1).
3. Whether the read-back transmit power matches the quantization table (section 4).
4. Whether the send-to-callback histogram shows the retry structure in unicast (section 2).
5. Whether a verification pair passes on the founder's bench (decision 6).

---

## Sources

Opened on 2026-10-01.

- [S1] [ESP-NOW, ESP-IDF Programming Guide v6.1](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_now.html)
- [S2] [Wi-Fi API, ESP-IDF Programming Guide v6.1](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_wifi.html)
- [S3] [ESP-FAQ: ESP-NOW](https://docs.espressif.com/projects/esp-faq/en/latest/application-solution/esp-now.html)
- [S4] [ESP-IDF v5.5 migration guide, Wi-Fi](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/migration-guides/release-5.x/5.5/wifi.html)
- [S5] [Becker et al., ESP-NOW Performance in Outdoor Environments, WONS 2025](https://dl.ifip.org/db/conf/wons/wons2025/1571077625.pdf)
- [S6] [Urazayev et al., Indoor Performance Evaluation of ESP-NOW, IEEE SIST 2023](https://ieeexplore.ieee.org/document/10223585/)
- [S7] [Field Testing and QoS Analysis of ESP-NOW Communication on ESP32, IEEE](https://ieeexplore.ieee.org/document/10824617/)
- [S8] [MicroPython espnow documentation](https://docs.micropython.org/en/latest/library/espnow.html)
- [S9] [ESP-IDF issue 12070, configurable TX retry count](https://github.com/espressif/esp-idf/issues/12070)
- [S10] [espressif/esp-now 2.5.2, wireless_debug example](https://components.espressif.com/components/espressif/esp-now/versions/2.5.2/examples/wireless_debug)
- [S11] [atomic14, ESP-Now range test](https://www.atomic14.com/videos/posts/oz0a7Ur7nko)
- [S12] [MeshCore release notes](https://github.com/smellyspice/MeshCore/releases)
- [S13] [BucketShoes, EspRangeTest](https://github.com/BucketShoes/EspRangeTest)
- [S14] [ESP-IDF issue 18682, ESP-NOW TX buffer pool](https://github.com/espressif/esp-idf/issues/18682)
- [S15] [RuView pull request 945, ESP-IDF v6.0 ESP-NOW callback compatibility](https://github.com/ruvnet/RuView/pull/945)
- [S16] [Packaging ESP-IDF components](https://docs.espressif.com/projects/idf-component-manager/en/latest/guides/packaging_components.html)
- [S17] [How to authenticate for publishing](https://docs.espressif.com/projects/idf-component-manager/en/latest/publish/how_to_authenticate.html)
- [S18] [PlatformIO Community, ESP-IDF libraries vs components](https://community.platformio.org/t/esp-idf-libraries-vs-components/47608)
- [S19] [pioarduino/platform-espressif32](https://github.com/pioarduino/platform-espressif32)
- [S20] [Eridani et al., Comparative Performance Study of ESP-NOW, Wi-Fi, Bluetooth, iSemantic 2021](https://ieeexplore.ieee.org/document/9573246/)
- [S21] [esp_now.h, ESP-IDF v5.4](https://github.com/espressif/esp-idf/blob/v5.4/components/esp_wifi/include/esp_now.h)
- [S22] [esp_now.h, ESP-IDF v5.5](https://github.com/espressif/esp-idf/blob/v5.5/components/esp_wifi/include/esp_now.h)
- [S23] [esptool, Embedding into custom scripts](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/scripting.html)
- [S24] [espressif/esp-launchpad](https://github.com/espressif/esp-launchpad)
- [S25] [ESP Web Tools](https://esphome.github.io/esp-web-tools/)
- [S26] [ESP-IDF versions](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/versions.html)
- [S27] [ESP-IDF roadmap](https://github.com/espressif/esp-idf/blob/master/ROADMAP.md)
- [S28] [ESP-IDF v5.5 released, Production ESP32](https://productionesp32.com/posts/idf-v5.5-released/)
- [S29] [Korhonen and Wang, Effect of Packet Size on Loss Rate and Delay in Wireless Links, IEEE WCNC 2005](https://smcnus.org/papers/5.Error_Robust_Audio_Streaming/2005_Effect_of_Packet_Size_on_Loss_Rate_and_Delay_in_Wireless_Links.pdf)
- [S30] [Son, Krishnamachari, and Heidemann, Experimental Study of the Effects of Transmission Power Control and Blacklisting in Wireless Sensor Networks, IEEE SECON 2004](https://anrg.usc.edu/www/papers/secon-pcbl.pdf)
- [S31] [Zhao and Govindan, Understanding Packet Delivery Performance in Dense Wireless Sensor Networks, ACM SenSys 2003](https://www.cse.iitb.ac.in/~br/webpage/courses/ictp-feb2007/topic05-pkt-delivery.pdf)
- [S32] [Aguayo et al., Link-level Measurements from an 802.11b Mesh Network, ACM SIGCOMM 2004](https://cseweb.ucsd.edu/~schulman/class/cse291_w17/docs/aguayo_roofnet.pdf)
- [S33] [Czitrom, One-Factor-at-a-Time versus Designed Experiments, The American Statistician 1999](https://polaris.imag.fr/arnaud.legrand/teaching/2011/EP_czitrom.pdf)
- [S34] [Frey, Engelhardt, and Greitzer, A Role for "One-Factor-at-a-Time" Experimentation in Parameter Design, Research in Engineering Design 2003](https://link.springer.com/article/10.1007/s00163-002-0026-9)
- [S35] [RF Coexistence, ESP-IDF Programming Guide v6.1](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/coexist.html)
