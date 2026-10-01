# Bolis ESP-IDF component

This directory is the ESP-IDF component `fortunelabs-io/bolis` on the ESP Component Registry. The registry uploads this directory only.

The component owns the radio during a run (`docs/adr/2026-10-01-radio-ownership-and-prebuilt-firmware.md`). It requires ESP-IDF v5.5 or later (`docs/adr/2026-10-01-esp-idf-v5-5-minimum.md`).

## Public API

```c
#include "bolis.h"

esp_err_t bol_start(void);
```

`bol_start` initializes WiFi in station mode, keeps the WiFi settings in RAM, sets the country code, starts WiFi, disables power save, and initializes ESP-NOW. If WiFi is already initialized, it returns `ESP_ERR_INVALID_STATE` and leaves the radio unchanged.

## Configuration

| Symbol | Default | Purpose |
|---|---|---|
| `BOL_COUNTRY_CODE` | `"01"` | The country code that the component sets. It limits the channels that a run can sweep |

## Files

| Path | Contents |
|---|---|
| `include/bolis.h` | The public header |
| `src/bol_radio.c` | The radio owner and `bol_start` |
| `priv_include/` | The private headers |
| `examples/bench/` | The example project for source builds and for the prebuilt images |

Planned modules (thinkbook section 7): the console module, the frame header encoder and decoder, the sender task, the receiver task, and the counters of each pass.

## License

Apache-2.0 (`docs/adr/2026-10-01-apache-2-0-license.md`). The repository root holds the license text in `LICENSE`.
