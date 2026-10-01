# Implementation-defined behavior that Bolis relies on

MISRA C:2012 Dir 1.1 requires a record of every implementation-defined behavior that the program relies on. This file holds that record for the native C code of Bolis.

The baseline is `docs/adr/2026-10-01-misra-c-2012-coding-baseline.md`. The component compiles with `-std=gnu17` on ESP-IDF v5.5 or later.

This file grows with the code. A change that relies on a new behavior adds its row in the same pull request.

## Toolchain

| Item | Value |
|---|---|
| Compiler | The GCC that ESP-IDF ships for the target chip |
| Language | C17, selected with `-std=gnu17` |
| First target | ESP32, a 32-bit little-endian chip |

## Behavior

| No. | Behavior | How Bolis handles it |
|---|---|---|
| 1 | The signedness of plain `char` | Bolis does not rely on it. Plain `char` holds text only. A byte is `uint8_t` |
| 2 | The width of the basic integer types | Bolis does not rely on it. Every quantity uses a fixed-width type from `<stdint.h>` (Dir 4.6). `int` appears only where an ESP-IDF signature requires it |
| 3 | The byte order of the chip | Bolis does not rely on it yet. The frame header fixes one byte order and states it, so a decoder reads a frame the same way on every chip |
| 4 | The representation of `esp_err_t` | Bolis does not rely on it. The code compares a value against a named `ESP_` constant and never against a literal |
| 5 | The value of a pointer converted to an integer | Bolis performs no such conversion |
| 6 | The layout of a bit-field | Bolis uses no bit-field (coding standard, Rule 19.2 area) |
| 7 | The behavior of the standard streams on the console | The console module owns it, under deviation record D-001 |

## Behavior that Bolis excludes

- Bolis allocates no heap memory, so it relies on no allocator behavior (Dir 4.12, Rule 21.3).
- Bolis uses no union, so it relies on no union representation (Rule 19.2).
- Bolis uses no variable-length array and no recursion (Rule 18.8, Rule 17.2).
- Bolis uses no C11 atomic and no C11 thread (Rule 1.4).
- Bolis uses no `<time.h>` function (Rule 21.10). It reads time with `esp_timer_get_time`, which returns microseconds as `int64_t`.
- Bolis uses no assembly language (Dir 4.2, Dir 4.3).
