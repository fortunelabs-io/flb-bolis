# Bolis ESP-IDF component

This directory is the ESP-IDF component `fortunelabs-io/bolis` on the ESP Component Registry. The registry uploads this directory only.

The component owns the radio during a run (`docs/adr/2026-10-01-radio-ownership-and-prebuilt-firmware.md`). It requires ESP-IDF v5.5 or later (`docs/adr/2026-10-01-esp-idf-v5-5-minimum.md`).

## Public API

```c
#include "bolis.h"

esp_err_t bol_start(void);
```

`bol_start` initializes WiFi in station mode, keeps the WiFi settings in RAM, sets the country code, starts WiFi, disables power save, initializes ESP-NOW, and starts the control task on the console. If WiFi is already initialized, it returns `ESP_ERR_INVALID_STATE` and leaves the radio unchanged.

`bol_start` is the whole API. The host drives everything else over the control line, so a caller passes no role and no condition.

## The control line

The node and the host exchange one line at a time on the console. Each line starts with `@bol ` and carries one JSON object, so the application log and the control plane share one serial port. The node ignores every other line.

This component speaks contract version 2 and answers five commands.

| Command | Reply |
|---|---|
| `hello` | The chip, the revision, the ESP-IDF and ESP-NOW versions, the packet payload limit, the Bolis version, the firmware path, the ELF SHA-256, the state of the Bluetooth controller, and the country code |
| `role` | The role that the node took, and the address of the node |
| `cell` | The condition that the node applied, with the transmit power that the radio reports |
| `go` | The frames that the pass sent, at an interval during the pass and once at its end |
| `stats` | The counters of the pass, for the role that answered |

A node writes a line of at most 512 bytes. A command that the node cannot carry out draws a reply whose `ok` is false and whose `err` names an ESP-IDF error code.

## Configuration

| Symbol | Default | Purpose |
|---|---|---|
| `BOL_COUNTRY_CODE` | `"01"` | The country code that the component sets. It limits the channels that a run can sweep, and the `hello` reply states the code that the radio reports |
| `BOL_PREBUILT` | `n` | Marks the image as a release image, so the `hello` reply states the firmware path. CI sets it. A source build leaves it off |

## Files

| Path | Contents |
|---|---|
| `include/bolis.h` | The public header, which declares `bol_start` |
| `src/bol_radio.c` | The radio owner, `bol_start`, the condition of a cell, and the peers of a sender |
| `src/bol_console.c` | The control line: the reader, the five command handlers, and every reply |
| `src/bol_json.c` | The reader of the flat JSON object of a control line |
| `src/bol_node.c` | The state that a node holds between two commands, and the positions of a pass |
| `src/bol_frame.c` | The 14-byte frame header and the fill that follows it |
| `src/bol_sender.c` | The sending loop of a pass |
| `src/bol_receiver.c` | The receive callback, its queue, and the task that drains it |
| `src/bol_stats.c` | The counters of a sender and the bins of its histogram |
| `src/bol_rxstats.c` | The counters of a receiver and the bins of its run-length histogram |
| `priv_include/` | One private header per module above |
| `test/` | The reader tests, which run on the host |
| `examples/bench/` | The example project for source builds and for the prebuilt images |

The component allocates no heap. It creates every task, queue, and semaphore with static storage.

## License

Apache-2.0 (`docs/adr/2026-10-01-apache-2-0-license.md`). The repository root holds the license text in `LICENSE`.
