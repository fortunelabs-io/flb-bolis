---
paths:
  - "**/*.c"
  - "**/*.h"
  - "**/Doxyfile"
---

# Doxygen documentation for C

Doxygen documents the C code. Python code uses docstrings (`python/coding-standard.md`).

## What to document

- Document every public function, type, structure member, enumeration constant, and macro in a public header.
- Give every source file and header a file block with `@file` and `@brief`. The `@brief` names the specification section, the thinkbook section, or the ADR that the file implements (MISRA Dir 3.1).
- Give every static function a `@brief` at least.
- Update the documentation in the same change as the code.

## Block form

- Use the Javadoc form `/** ... */` with `@` commands, as ESP-IDF does.
- Document a structure member, an enumeration constant, or a macro value with a trailing block `/*!< ... */` after the item.
- Group related functions with `/**@{*/` and `/**@}*/`.
- Never write `/*` or `//` inside a block. This rule includes a URL and a comment inside `@code` (MISRA 3.1). Cite a document by its name.
- Do not use `///` or `//!` blocks.

## Commands

| Command | Use |
|---|---|
| `@brief` | One sentence. Start with a verb in the third person, such as "Starts the control task." |
| `@param[in]`, `@param[out]`, `@param[in,out]` | One per parameter, with the unit and the valid range. |
| `@retval` | One per return code. State the state of the node after that code. |
| `@return` | Only for a function that returns a value, not a code. State the unit. |
| `@pre` | A condition that must hold before the call. |
| `@note` | The calling context, such as "Call only from a task. Do not call from the ESP-NOW receive callback." |
| `@warning` | A consequence that can corrupt a run or a record. |
| `@code` and `@endcode` | A short example without comments. |

## Content

- State the unit of every quantity, such as microseconds, bytes, dBm, or 0.25 dBm steps.
- State the byte order of every multi-byte field in a frame layout.
- State whether a function is safe to call from another task.
- Write every block in the writing standard (`writing.md`).

## Example

```c
/**
 * @brief Starts the Bolis radio owner and the control task.
 *
 * Initializes WiFi in station mode, disables power save, sets the country
 * code, initializes ESP-NOW, and starts the control task on the console.
 *
 * @pre WiFi is not initialized.
 * @note Call once, from a task.
 *
 * @retval ESP_OK                 The control task runs.
 * @retval ESP_ERR_INVALID_STATE  WiFi was already initialized. The radio is unchanged.
 * @retval Other                  The code that the failing ESP-IDF call returned.
 */
esp_err_t bol_start(void);
```

## Doxyfile

The tracked configuration lives in `docs/Doxyfile`. It sets these values:

| Option | Value |
|---|---|
| `OPTIMIZE_OUTPUT_FOR_C` | `YES` |
| `JAVADOC_AUTOBRIEF` | `NO` |
| `EXTRACT_STATIC` | `NO` |
| `WARN_IF_UNDOCUMENTED` | `YES` |
| `WARN_NO_PARAMDOC` | `YES` |
| `WARN_AS_ERROR` | `FAIL_ON_WARNINGS` |
| `INPUT` | The public include directory and the source directory of the component |
| `EXCLUDE_PATTERNS` | `*/managed_components/*` and `*/build/*` |

A Doxygen warning fails the documentation check.
