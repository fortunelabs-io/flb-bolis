# ESP-IDF v5.5 as the minimum version for Bolis

Date: 2026-10-01
Status: Accepted

## Context

Bolis needed a minimum ESP-IDF version for its component manifest. ESP-NOW v2.0 first appeared in ESP-IDF v5.4. A check of the official `esp_now.h` headers on 2026-10-01 found two differences between v5.4 and v5.5. In v5.4, the send callback takes the MAC address of the peer, and the v2.0 payload limit is 1490 bytes. In v5.5, the send callback takes `esp_now_send_info_t`, and the v2.0 payload limit is 1470 bytes. The v6.1 documentation shows the same send callback as v5.5. Espressif supports each release for 30 months: 12 months of service and 18 months of maintenance. ESP-IDF v5.4 was released on 2025-01-04, so its support ends about July 2027, and it receives only maintenance fixes. ESP-IDF v5.5 is supported through 2028-01-21. The stable release of the pioarduino platform for PlatformIO ships ESP-IDF v5.5.5. If nothing was decided, the manifest would accept versions with two callback signatures and two payload limits, and the corpus would mix two v2.0 frame boundaries.

## Alternatives considered

- Set the minimum at v5.4, the first version with ESP-NOW v2.0, and support both callback signatures and both payload limits.
- Set the minimum at v5.5.
- Set the minimum at v6.0.
- Support versions before v5.4 with ESP-NOW v1.0 only.

## Decision

The component manifest requires ESP-IDF v5.5 or later. Bolis uses one send callback signature. The component takes the v2.0 payload limit from `ESP_NOW_MAX_DATA_LEN_V2` at compile time. The run record stores the ESP-IDF version and the payload limit of each run. CI builds the component on v5.5 and on each later minor release that Espressif supports.

## Consequences

- Users on ESP-IDF v5.4 cannot run Bolis.
- The reach lost on v5.4 shrinks over time, because v5.4 support ends about July 2027.
- A second v2.0 payload limit in the corpus would have stayed permanent, so the corpus keeps one v2.0 frame boundary.
- The PlatformIO channel stays open through the pioarduino stable release.
- A later decision can lower the minimum without breaking existing users.
- A later decision that raises the minimum breaks existing users.
- A new ADR decides whether to raise the minimum before v5.5 support ends on 2028-01-21.
- The run record format gains a field for the ESP-IDF version and a field for the v2.0 payload limit.
- The thinkbook states the 1490-byte limit of v5.4 in its next version.
- Specification section 4 states the minimum ESP-IDF version in v0.4.
