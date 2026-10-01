# Bolis v0 specification

*Fortune Labs. Working statement, v0.4. 2026-10-01.*

This page specifies the first product. Every item is a `[proposal]` until a run confirms it. No number on this page is `[measured]`. A value in angle brackets is a placeholder that the founder sets before the work starts. Section 14 lists the decision records behind this version. The Bolis thinkbook (v0.2) holds the theory and the high-level design.

**Change from v0.3.** Seven decision records changed this specification. Bolis is now prebuilt firmware plus a host CLI, and the user flow starts with the installation of the host package (sections 3, 5, and 8.2). Section 4 states the loss metric, the send mode, the PHY rate, the minimum ESP-IDF version, the payload limit, and the sweep plan. Section 6 states the test condition, the number labels, and the reproducibility rule. Sections 12 and 13 follow these changes. Section 14 is new.

---

## 1. Goal

Bolis is a baby step. It exists for three outcomes, in this order.

1. **Discovery.** Developers find Fortune Labs through a tool that solves a problem they already have, at low cost to Fortune Labs.
2. **Data.** Each run that a user chooses to share adds to the measured corpus (Threshold Bet, Loop A).
3. **Money, if it comes.** Bolis is free by design. A payment for interpretation or integration is a bonus and is not a success condition.

The product proves that Fortune Labs ships something people use. It does not test whether people pay. A later step tests that.

---

## 2. Name and identifiers

**Decision.** The founder chose the name Bolis on 2026-10-01. The decision is final for v0.

| Item | Value |
|---|---|
| Product name | Bolis |
| One-line description | Link sweep for ESP-NOW on ESP-IDF |
| Repository | `fortunelabs-io/flb-bolis` |
| PyPI, for the host CLI and the firmware images | `bolis` |
| ESP Component Registry, for source builds | `fortunelabs-io/bolis` |
| PlatformIO | `bolis` |
| C function prefix | `bol_` |

**Meaning.** *Bolis* (βολίς) is the Greek word for a sounding lead, the weight that sailors dropped on a line to measure the depth of unknown water. One sounding gives the depth at one point and one time. The report has the same limit (section 4, claim limit).

**Naming convention.** Fortune Labs names follow a classical register: Elision for ESCP, Obol for the harness, and Bolis for this product. The audience is worldwide, and the first market is the Greater Bay Area. A name is short and easy to say for speakers of English, Cantonese, and Mandarin.

The name does not contain "esp". Espressif owns ESP and ESP-NOW. The description names ESP-NOW only to state compatibility. The C prefix is `bol_` because `bl_` commonly marks bootloader code.

**Rejected names.** Each name below was rejected for the reason in its row. The search date is 2026-10-01 unless the row states otherwise.

| Name | Reason |
|---|---|
| Linkmeter, Linksweep | Existing products use them (v0.2) |
| Linkprobe | Active network link measurement projects use it, including a Rust CLI and the `linkprobe-core` crate |
| Linkgauge | An iperf3 desktop GUI for TCP, UDP, and ping tests uses it |
| Benchlink | Keysight uses BenchLink for its test and measurement software |
| Basanos | An ESP-IDF WiFi test tool for the ESP32-S3 uses it. The PyPI name is taken |
| Lacuna | Lacuna Space uses it for satellite IoT on LoRa |
| Groma, Trutina, Dokima, Libella, Siliqua, Siglum | Software projects use them. Libella and Siliqua are also taken on PyPI |
| Unting, Patok, Tilik | Outside the naming convention |

**Fallback.** Chalkous (χαλκοῦς), the bronze coin worth one eighth of an obol. A search found no software product with this exact name, and the PyPI name is free. Search results for it mix with "chalkos" and with products named Chalk. The name describes the position of the product under Obol, not its function.

**Clearance status.** A search on 2026-10-01 covered the web, GitHub, and PyPI. It found no software product named Bolis. The results show only surnames and small unrelated repositories. The PyPI name `bolis` is free. In Mexican Spanish, "bolis" names an ice pop. That use is outside classes 9 and 42, and it appears in general search results. The search is shallow and `[borrowed]`. Before publication the founder checks the Indonesian trademark database (classes 9 and 42), the WIPO Global Brand Database, and the Hong Kong IP Department database.

**Registration.** The repository exists as `fortunelabs-io/flb-bolis`. The `flb-` prefix marks a Fortune Labs repository, and the repository description states the function. The package names stay `bolis`, because PyPI and PlatformIO take the name from the package manifest, and the ESP Component Registry takes it from the upload command. GitHub redirects the old repository URL only while no repository in the organization takes the old name, so the name `bolis` stays unused there. The ESP Component Registry, PlatformIO, and PyPI names are taken with the first published package, because each of them requires a package. The ESP Component Registry uses the GitHub account name as the default namespace. If the registry does not grant `fortunelabs-io` through the GitHub login, the founder requests the namespace from Espressif through its Namespace Request Form. The founder files the trademark after the first independent install, unless a clearance search shows a filing risk earlier. The Fortune Labs mark comes first in the sequence. The owner of the Bolis mark follows the decision on the split between Fortunelabs HK and PT Indonesia (section 10).

---

## 3. One sentence

Bolis is a bench tool for ESP-NOW. It consists of firmware for two ESP32 nodes and a host CLI. It runs an automatic sweep on the ESP-NOW link between the two nodes and writes one report that shows which variable moves frame loss near the user's configuration.

---

## 4. Scope

**In v0**

- ESP-NOW between two ESP32 nodes on a bench. Both nodes connect by USB to one host.
- Prebuilt firmware for each supported chip, built on ESP-IDF v5.5.x. The host CLI flashes the same image to both nodes and assigns the sender and receiver roles. The ESP32 comes first (decision 7).
- A component for source builds on ESP-IDF v5.5 or later. The component owns the radio and refuses to start if WiFi is already initialized (decisions 3 and 7).
- Three sweep variables: channel, payload size around the frame boundary in `n(p) = ceil(p/L)`, and transmit power. `L` is 250 bytes for ESP-NOW v1.0 packets and 1470 bytes for v2.0 packets.
- A sweep that changes one variable at a time around the user's configuration, with 2000 frames per cell and pass. The full grid is an option (decision 4).
- Broadcast first-attempt loss in every run. In a unicast run, each cell adds a unicast pass with post-retry loss and the send-to-callback time histogram (decision 1).
- A PHY rate fixed at 1 Mbps (decision 2).
- Power save off on both nodes.
- A host CLI that collects the counters and writes one run record per run.
- A static HTML report.
- An origin label on every number: `[measured]`, `[configured]`, `[derived]`, or `[declared]` (decision 5).

**Out of v0**

- Energy measurement. The documentation states this.
- Integration into Arduino projects. Arduino users can run the default path.
- WiFi links and LoRa links.
- A run setting or a sweep variable for the PHY rate.
- A test of interactions between the sweep variables.
- Field installation. v0 does not diagnose a link at a customer site.
- A dashboard and automatic diagnosis.

**Claim limit.** The report answers one question: how does my configuration behave under controlled conditions. It does not claim to explain a failure in the field. The documentation and every report state this sentence. Every report also states three limits: its results apply to 1 Mbps, its conclusions hold at its baseline, and its sweep does not test interactions.

---

## 5. User flow

1. Install the host package: `pip install bolis`.
2. Connect two ESP32 boards to the host by USB.
3. Flash both boards with one host command.
4. Run one host command with the baseline configuration.
5. Receive one report file.

Steps 1 to 4 take about `<10>` minutes. A user who needs more time exposes a defect in the documentation or the API, and the founder logs it as such.

A user who needs a specific ESP-IDF version or sdkconfig builds the example project `examples/bench` from source. That path needs ESP-IDF v5.5 or later.

---

## 6. Report contents

- The test condition: the firmware path and version, the ESP-IDF version, the ESP-NOW version, the payload limit `L`, the PHY rate, the country code, the run mode, the power-save mode, the state of the Bluetooth controller, and the geometry that the user declared.
- One chart per sweep variable, with loss on the vertical axis. Each chart states its mode and its loss quantity.
- One paragraph that names the variables that moved loss. The paragraph does not state a cause. The baseline loss sits next to the paragraph.
- The coverage and the limits of the run, including the three limits in section 4.
- An origin label and a link to the run record beside every number, and a legend of the four labels.

**Reproducibility.** A result counts as reproduced when a verification pair passes (decision 6). Both runs of the pair use the same bench and the same declared geometry. Between the runs, the founder removes both nodes and places them again according to the declared geometry. The second run starts on a later calendar day. The pair passes when the baseline loss intervals of the two runs overlap and the lists of variables that moved loss are identical. Until a pair passes, the repository shows a mockup with placeholders. The mockup states that it is a mockup. A failed pair is published as a log entry (section 8.4).

---

## 7. Data handling

The host CLI sends nothing off the user's machine. The host package carries the firmware images, so flashing needs no network access. A user who wants to share a run record does so by choice, for example by attaching the file to an issue. The repository explains what a record contains: run ID, date, firmware version, test condition, and raw data. A record contains no device identifier that the user did not add. The record stores no MAC address.

The founder adds a shared record to the corpus only with the user's permission, with names removed. The permission is written in the issue thread.

---

## 8. Distribution

Bolis has no sales force. Reach depends on where developers already look.

### 8.1 The rule

The firmware, the component, and the base scripts are open, following the Hwaci pattern. A developer must install, run, and read the report without contacting Fortune Labs. A step that requires contact is a defect. `[proposal]` The license is Apache-2.0, which carries a patent grant. The founder confirms the license before the first release.

### 8.2 Channels, in order

| Order | Channel | Audience it holds | What Fortune Labs needs | Cost |
|---|---|---|---|---|
| 1 | GitHub repository | Developers who follow links from issues and posts | README, license, tagged release with one firmware image and its hash per chip, sample report | Low |
| 2 | PyPI | Developers who install tools with pip, including Arduino and PlatformIO users | The `bolis` host package with the firmware images | Low |
| 3 | ESP Component Registry | ESP-IDF users who build from source | Manifest file, README, license, GitHub login. A staging registry exists for tests | Low |
| 4 | PlatformIO registry | Developers who build from source in the PlatformIO toolchain | A `library.json` manifest, after the first ESP Component Registry release | Low |
| 5 | Direct reply on public threads | The person who already reported the problem | One reproduced result per thread, with a link | Time |
| 6 | Technical log at log.fortunelabs.com.hk | Search visitors | One short entry per experiment | Time |

The GitHub repository comes first because every other channel links to it.

### 8.3 The direct reply rule

A direct reply contains the problem the person described, one reproduced result (section 6) that relates to it, and a link to Bolis. A reply that only announces the product is not sent. The reply answers the question first and gives the link second.

Each reply follows the Social Media Communication Language SOP. Each number from a Bolis report carries its number label (section 4) and a link to the run record. The reply makes no claim about rank.

The founder logs each reply with the date, the thread, and the outcome. The outcome has four values: no response, response without install, install, and correction.

### 8.4 Publication rhythm

Twelve short honest entries across a year outperform one long entry (Threshold Bet 4.5). The founder publishes one log entry per `<n>` weeks. An entry reports one experiment with its condition, its result, and its artifact link. A failed run has the same form as any other entry.

### 8.5 Where v0 does not go

- No paid advertising.
- No outbound sales campaign.
- No comparison against another tool in a post unless the post states both measured values and both origin labels.

### 8.6 Result definitions

An event counts only when a person outside Fortune Labs spent their own effort.

| Event | Counts when |
|---|---|
| Independent install | A third party runs a sweep on their own hardware and sends the record or the report |
| Correction | A third party corrects a number, a method, or an assumption |
| Reproduction | A third party rebuilds a published result on their own hardware |
| Traceable enquiry | A message names Bolis or a log entry without being prompted |
| Shared record | A third party shares a run record with permission for the corpus |

Downloads, stars, and views do not count. The founder records the download count for reference only, because automated builds can inflate it.

---

## 9. Success and failure

Success has three levels. Only the first two define v0.

| Level | Condition | Reading |
|---|---|---|
| Discovery | `<k>` independent installs, corrections, or traceable enquiries arrive within `<N>` weeks | Fortune Labs is found through the product |
| Data | `<j>` shared records enter the corpus | Loop A receives field-adjacent input |
| Money | A person pays for interpretation, integration, or a follow-up audit | A bonus. It opens a later step |

The founder sets `<k>`, `<j>`, `<N>`, and the outreach count `<M>` before the first post and records them in the changelog.

| Result at the limit | Reading | Response |
|---|---|---|
| No install | The offer or the install friction is the problem | Reduce the steps or change the offer |
| Install, no shared record | People use the tool and keep the data | Ask for records in the report footer, and improve the reason to share |
| Install and shared records, no payment | The value is discovery and data | This is a success under the goal. Test a paid step later |

More features are not a response to a zero result.

---

## 10. Entity handling

Fortune Labs is one base with several representations.

- **Base, owned by Fortunelabs HK.** The harness, latent-c, the sweep logic, the run record format, and the report script. It is open.
- **v0 layer, operated by PT Indonesia.** Packaging, the sales page, client contracts, price, and support. The base does not depend on this layer.
- **Test for a new part.** If the part is useful to Fortune Labs when v0 is dropped, it enters the base. If it only helps to sell v0, it enters the v0 layer.

Contributor agreements assign IP to Fortunelabs HK. Client contracts let anonymous measurement data enter the corpus. The license between entities, the trademark permission, and the transfer pricing need review by a Hong Kong solicitor and an Indonesian tax adviser.

---

## 11. Support limit

The founder sets `<h>` hours per week for issues and questions. Items beyond the limit wait. A support load that grows past the limit is a signal to improve the documentation, and hours stay fixed.

---

## 12. Done conditions

1. A third party installs the host package, flashes two boards, and runs a sweep from the documentation alone, without asking a question.
2. One command writes the report without manual edits.
3. The repository holds a license, a README, a labeled mockup report, and a release with one firmware image and its hash per supported chip.
4. The host package is on PyPI under the cleared name.
5. The distribution log exists, and the limits `<k>`, `<j>`, `<N>`, `<M>`, `<n>`, and `<h>` are recorded in the changelog.

---

## 13. Open items

1. The values of the placeholders in sections 5, 8.4, 9, and 11.
2. Whether a sample peer firmware is included for users with one ESP32.
3. Whether a field version follows v0, or waits for demand from three users.
4. The ADR for the split between the base at HK and the v0 layer at PT.
5. The trademark database checks for Bolis in section 2.
6. A check of the claim that no ready tool covers the same job. Espressif's esp-now component offers manual commands for channel, rate, transmit power, and an iperf test. No tool found runs an automatic sweep across configuration variables and writes one report with origin labels. The search is shallow, and the claim stays `[borrowed]`.
7. The bench spike checks five facts before the code grows:
    - whether `esp_now_set_peer_rate_config` applies to the broadcast peer (decision 2),
    - whether the send failure near 78,000 broadcast frames occurs on a native ESP-IDF build (decision 1),
    - whether the read-back transmit power matches the quantization table,
    - whether the send-to-callback histogram shows the retry structure in unicast,
    - whether a verification pair passes on the founder's bench (decision 6).

---

## 14. Decision records

The records sit in the `docs/adr/` folder. Sections 4 to 7 cite them by number.

| No. | Decision | Record |
|---|---|---|
| 1 | Broadcast first-attempt loss as the base metric, with a unicast pass for unicast applications | `2026-10-01-loss-metric-and-send-mode.md` |
| 2 | PHY rate fixed at 1 Mbps for v0 | `2026-10-01-phy-rate-fixed-at-1-mbps.md` |
| 3 | ESP-IDF v5.5 as the minimum version | `2026-10-01-esp-idf-v5-5-minimum.md` |
| 4 | Local one-variable-at-a-time sweep, with 2000 frames per cell | `2026-10-01-local-one-variable-sweep.md` |
| 5 | Origin labels for numbers in Bolis artifacts | `2026-10-01-number-origin-labels.md` |
| 6 | Reproducibility verification by re-placing the nodes on a later day | `2026-10-01-reproducibility-verification.md` |
| 7 | Radio ownership and prebuilt firmware as the default path | `2026-10-01-radio-ownership-and-prebuilt-firmware.md` |

---

*The market is the final judge. Ship, and let it answer.*
