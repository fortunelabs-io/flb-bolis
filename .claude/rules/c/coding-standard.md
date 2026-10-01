---
paths:
  - "**/*.c"
  - "**/*.h"
---

# C coding standard

## Scope and precedence

- These rules apply to C files and headers that Bolis authors: the firmware component and `examples/bench`.
- They do not apply to adopted code: ESP-IDF, FreeRTOS, newlib, the WiFi and ESP-NOW drivers, and every file under `managed_components/` or `build/`. Do not edit adopted code.
- Three sources govern Bolis C code: MISRA C:2012 with Amendments 1 and 2 (`misra-c-2012.md`), the SEI CERT C Coding Standard 2016 Edition (`cert-c-2016.md`), and the ESP-IDF style guide for layout.
- If the ESP-IDF style guide conflicts with MISRA C:2012 or CERT C, follow MISRA C:2012 or CERT C.
- Write C17. Do not use a C23 feature. The component compiles with `-std=gnu17` on every ESP-IDF version (decision 8).

## Layout

- Indent with 4 spaces. Do not use tabs.
- Keep lines at 120 characters or fewer.
- Put the opening brace of a function definition on its own line.
- Put the opening brace of a control statement on the line of the statement.
- Use braces for every loop body and every `if` and `else` body, even for one statement (MISRA 15.6).
- Format each changed file with `astyle_py` and the ESP-IDF rules file.

## Names

- Prefix every external function, type, and object with `bol_`. Prefix every macro and enumeration constant with `BOL_`.
- End every type name with `_t`.
- Name enumeration constants `BOL_<ENUM>_<VALUE>`.
- Prefix every object with static storage at file scope with `s_`.
- Never start an identifier with an underscore (MISRA 21.2, CERT DCL37-C).
- Put the unit at the end of the name of a quantity: `_us`, `_ms`, `_bytes`, `_dbm`, or `_qdbm` for 0.25 dBm steps. Example: `tx_power_qdbm`.

## Headers

- Guard every header with `#ifndef BOL_<NAME>_H`, `#define BOL_<NAME>_H`, and `#endif`. Do not use `#pragma once` (MISRA Dir 4.10 and Rule 1.2).
- Wrap the declarations of a public header in an `extern "C"` block under `#ifdef __cplusplus`.
- Order includes as the ESP-IDF style guide states: C standard headers, POSIX headers, common ESP-IDF headers, other component headers, public headers of this component, and private headers.
- Declare in a public header only what users of the API need. Hide a structure that users access through a pointer only (MISRA Dir 4.8).

## Types

- Use the fixed-width types of `<stdint.h>` and `bool` of `<stdbool.h>` (MISRA Dir 4.6).
- Use `int` only where an ESP-IDF signature requires it, such as the length parameter of the ESP-NOW receive callback.
- Use `uint8_t` for bytes. Use plain `char` only for text. The signedness of plain `char` is implementation-defined.
- Add a `U` suffix to every unsigned integer constant (MISRA 7.2).
- Do not use unions (MISRA 19.2) or bit-fields in a frame header.

## Memory

- Do not allocate heap memory in Bolis code (MISRA Dir 4.12 and Rule 21.3).
- Create FreeRTOS tasks and queues with static buffers: `xTaskCreateStatic` and `xQueueCreateStatic`.
- Do not use variable-length arrays (MISRA 18.8) or recursion (MISRA 17.2).
- Define each task stack size as a named constant. Its comment states the high-water mark from `uxTaskGetStackHighWaterMark` and the run that produced it.

## Errors

- Check every `esp_err_t` return value (MISRA Dir 4.7 and Rule 17.7, CERT ERR33-C).
- Do not use `ESP_ERROR_CHECK`. It aborts the node (MISRA 21.8), and a run must report a failure to the host.
- Do not use `ESP_RETURN_ON_ERROR`, `ESP_GOTO_ON_ERROR`, or similar macros. They hide a return or a jump (MISRA 15.1, 15.5, and Dir 4.9).
- Do not use `assert` to handle a runtime error.
- Give each function one exit at its end (MISRA 15.5). Keep the result in a local variable named `ret`.
- If a function can fail, return `esp_err_t`. Return an existing `ESP_ERR_` code when one fits.

## Concurrency

- The ESP-NOW receive callback runs in the WiFi task. In the callback, copy the packet header, the length, and the RSSI to a queue, and return (thinkbook section 7).
- Never block in a callback.
- Share data between tasks only through a FreeRTOS queue or inside a critical section.
- Do not use C11 atomics or C11 threads (MISRA 1.4).

## External input

- Treat every radio packet and every control line as untrusted (MISRA Dir 4.14).
- Check the length of a buffer before reading a field from it.
- Decode the 14-byte frame header byte by byte, or copy it with `memcpy` into a local object. Never cast a receive buffer to a structure pointer (MISRA 11.3, CERT EXP36-C and EXP39-C).
- Encode every multi-byte header field in one fixed byte order. The header documentation names that order.
- Reject a control line that exceeds the line buffer. Count every rejected packet and line.
- Never pass external data as a format string. Write `"%s"` and pass the data as an argument (CERT FIO30-C).

## Comments

- Use `//` for a one-line comment and `/* */` for a longer comment. Use `/** */` for Doxygen (`doxygen.md`).
- Never write `/*` or `//` inside a comment. This rule includes a URL (MISRA 3.1). Cite a document by its name.
- Do not leave code commented out (MISRA Dir 4.4).
- State why, not what. Follow `writing.md`.

## Time

- Read time with `esp_timer_get_time`, which returns microseconds as `int64_t`.
- Do not use `<time.h>` (MISRA 21.10).

## Invariants from decision records

- `bol_start` returns `ESP_ERR_INVALID_STATE` without a change to the radio if `esp_wifi_get_mode` does not return `ESP_ERR_WIFI_NOT_INIT` (decision 7).
- The component sets 1 Mbps for every peer it adds (decision 2).
- The component disables power save, so both nodes use `WIFI_PS_NONE`.
- The component takes the v2.0 payload limit `L` from `ESP_NOW_MAX_DATA_LEN_V2` at compile time (decision 3).
- The sender sends the next packet only after the send callback of the previous packet returns.
- Only the console module writes control lines, and each line starts with `@bol ` (thinkbook section 7).
