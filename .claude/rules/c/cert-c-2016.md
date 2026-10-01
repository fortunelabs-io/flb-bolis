---
paths:
  - "**/*.c"
  - "**/*.h"
---

# SEI CERT C rules

## Baseline

- Bolis C code follows the 99 rules of the SEI CERT C Coding Standard, 2016 Edition, beside MISRA C:2012 (decision 8).
- `.claude/reference/cert-c-2016-catalog.md` lists every rule with its level and its applicability to Bolis. Read it before a review of C code.
- If CERT C and MISRA C:2012 both cover a construct, follow the stricter rule.
- Several CERT rules cover constructs that MISRA C:2012 bans in Bolis code: flexible array members, `restrict`, variable-length arrays, `<signal.h>`, and heap allocation. Code that meets MISRA meets those CERT rules by absence.

## Levels

| Level | Priority | Rule for Bolis code |
|---|---|---|
| L1 | P12 to P27 | No open finding at merge. |
| L2 | P6 to P9 | Fix each finding, or state in the PR body why it is a false finding. |
| L3 | P1 to P4 | Fix each finding, or state in the PR body why it is a false finding. |

## L1 rules

These 17 rules carry the highest risk. Check each one in every C review.

| Rule | Bolis focus |
|---|---|
| EXP33-C | Initialize every local object before the first read, including every field of a decoded header. |
| EXP34-C | Check every pointer argument and every callback pointer for `NULL` before use. |
| ARR38-C | Pass `memcpy` and `memset` a length that fits the destination. |
| STR31-C | Size every text buffer for the data and the null terminator. |
| STR32-C | Pass only null-terminated text to a string function. |
| STR38-C | Bolis code uses no wide strings. |
| MEM30-C | Bolis code allocates no heap memory. |
| MEM34-C | Bolis code allocates no heap memory. |
| FIO30-C | Never pass external data as a format string, including to `ESP_LOGx`. |
| FIO34-C | In the console module, keep the result of a character read in an `int` and compare it with `EOF`. |
| FIO37-C | In the console module, do not assume that `fgets` returned a non-empty line. |
| ENV32-C | Bolis code registers no exit handler. |
| ENV33-C | Never call `system()`. |
| SIG30-C | Bolis code uses no signal handler. |
| ERR33-C | Detect and handle every library error. Apply the same rule to every `esp_err_t` return value. |
| MSC32-C | The firmware uses no pseudorandom generator. |
| MSC33-C | Bolis code does not use `<time.h>`. |

## Rules with the highest exposure in Bolis

- INT30-C: message IDs, frame counters, and histogram bins are unsigned. Check each one for wrap before an increment, or state why it cannot wrap in one run.
- INT31-C: check every narrowing conversion, such as an `int` length from the ESP-NOW callback into a `uint16_t` field.
- INT32-C: keep signed arithmetic, such as RSSI sums, within range for the largest cell.
- ARR30-C: check every index that comes from a received packet, such as the fragment index.
- EXP36-C and EXP39-C: decode received bytes with `memcpy` or byte access, never with a pointer cast.
- CON rules: apply them by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads.

## Checks

- clang-tidy runs the `cert-*` checks through `idf.py clang-check` (`skills/c-compliance-check/SKILL.md`).
- A reviewer checks every L1 rule that no tool reports on.
