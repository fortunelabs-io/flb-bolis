# The dependency record rule covers components outside ESP-IDF

Date: 2026-10-01
Status: Accepted

## Context

The development procedure stated that a change which adds a dependency to the firmware component stops and needs a decision record, because a new dependency changes the adopted code in scope. The coding baseline record had already placed ESP-IDF, FreeRTOS, newlib, the radio drivers, and managed components outside the MISRA check, and it did so by category rather than by a list of components. A dependency on a component that ESP-IDF ships therefore adds no code that the baseline did not already classify. The radio owner added `esp_wifi`, `esp_netif`, `esp_event`, and `nvs_flash` to the component without a record, so the rule was already applied unevenly on the first firmware change. The console module of the control plane needs `esp_driver_uart` for a blocking read, because the UART hardware FIFO of the ESP32 holds 128 bytes while the accepted wire format allows a line of 512 bytes, and a poll interval cheap enough to run beside a sweep drops characters inside a line. The sender, the receiver, and the timebase each reach further ESP-IDF components. If nothing was decided, every one of those changes would stop for a record that restates the same reasoning, and the uneven application would stay in the repository.

## Alternatives considered

- Apply the rule to a dependency outside ESP-IDF only.
- Keep the rule as written, and write one record for each ESP-IDF component.
- Drop the rule, and record every dependency in the pull request body.
- List the permitted ESP-IDF components in the procedure, and record any addition to that list.

## Decision

A dependency on a component that ESP-IDF ships needs no decision record. The change adds the component to `REQUIRES` or `PRIV_REQUIRES`, and the pull request body names it and states why the change needs it.

A dependency on any other component stops the change and needs a decision record. This covers a component from the ESP Component Registry, a component from the PlatformIO registry, and a copy of third-party code inside this repository.

The coding baseline keeps every ESP-IDF component as adopted code, outside the MISRA check. This record changes no MISRA scope.

## Consequences

- The console module adds `esp_driver_uart` without a record.
- The four components that the radio owner added stand without a record.
- A pull request that adds an ESP-IDF component names it in its body and states why.
- A component from a registry still stops the change.
- The license, the supply chain, and the manifest of Bolis stay under review, because those risks arrive with a registry component and not with an ESP-IDF component.
- The MISRA scope does not change, because the coding baseline already covers every ESP-IDF component by category.
- A wider set of ESP-IDF components raises the image size, which the build reports on each change.
- A reviewer can no longer read every dependency decision in the record folder.
- The pull request body becomes the record of an ESP-IDF dependency.
- A check that the component manifest lists no dependency other than `idf` would keep this rule enforceable, and no such check exists yet.
- A later move away from ESP-IDF needs a new record.
- This record overrides the dependency rule of the development procedure, which an accepted record outranks.
