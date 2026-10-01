---
paths:
  - "**/*.c"
  - "**/*.h"
---

# MISRA C:2012 compliance

## Baseline

- Bolis C code follows MISRA C:2012 with Amendment 1 and Amendment 2 (decision 8). Amendment 2 extends the guidelines to C11 and C18.
- MISRA Compliance:2020 defines how Bolis claims compliance: categories, deviations, and the guideline compliance summary.
- MISRA C:2004 is superseded for Bolis. Do not cite a MISRA C:2004 rule number.
- The licensed MISRA C:2012 text governs. The summaries in `.claude/reference/misra-c-2012-catalog.md` are Fortune Labs paraphrases for orientation, not the guideline text.
- Never copy MISRA text into the repository, a comment, a commit message, or a PR body. Cite the guideline number only, such as "MISRA C:2012 Rule 17.7".
- Before the first compliance summary, check each category in the catalog against the licensed text.

## Scope

- Native code: every C file and header that Bolis authors. The full guideline set applies.
- Adopted code: ESP-IDF, FreeRTOS, newlib, the WiFi and ESP-NOW drivers, and every file under `managed_components/` or `build/`. Bolis does not modify or check adopted code.
- A finding that comes only from an adopted header, or from the expansion of an adopted macro such as `ESP_LOGI`, is not a Bolis violation. Record the class of such findings once in deviation record D-002.
- A finding in native code that only an adopted interface forces, such as a `void *` callback argument, is a Bolis finding. Handle it as its category states.

## Categories

| Category | Rule for Bolis code |
|---|---|
| Mandatory | Never violate. No deviation is possible. |
| Required | Violate only with a deviation record that the founder approved. |
| Advisory | Follow. A violation needs no deviation record. It needs an inline note that names the guideline and the reason. |

- Bolis re-categorizes no guideline and disapplies no advisory guideline. A change to this plan needs an ADR.
- Mark an advisory violation with a suppression comment on the line before the code, in this form: `// cppcheck-suppress misra-c2012-11.5 ; FreeRTOS passes the task argument as void *`.
- A required violation carries the same comment form with the deviation ID: `// cppcheck-suppress misra-c2012-21.6 ; D-001`.

## Deviation records

- Keep deviation records in `docs/compliance/misra-deviations.md`. This file is tracked.
- Give each record an ID `D-NNN`, a status (`Proposed`, `Approved`, or `Withdrawn`), and an approval date.
- Each record states the five parts that MISRA Compliance:2020 requires: the guidelines, the circumstances in which a violation is acceptable, the reason, the background, and the requirements with the risk assessment and the precautions.
- Each record names the files or the module where it applies.
- Claude drafts a record with status `Proposed`. Only the founder sets `Approved`.
- Code that relies on a `Proposed` record does not merge.

## Initial deviation records

These records are proposals until the founder approves them.

| ID | Guidelines | Circumstances | Precautions |
|---|---|---|---|
| D-001 | Rule 21.6 (Required) | The console module reads and writes control lines through `<stdio.h>`, because the ESP-IDF console is the control plane (thinkbook section 6). | Only the console module includes `<stdio.h>`. Buffers have fixed sizes. Every read is bounded. Every format string is a literal. The CERT C FIO rules apply. Rules 22.1 to 22.10 apply to the console streams. |
| D-002 | Findings that come only from adopted headers and adopted macro expansions | Bolis code includes ESP-IDF and FreeRTOS headers and calls their macros. | The check excludes adopted paths. A finding that a reviewer cannot trace to an adopted header or macro is a native finding. |

## Compliance files

- `docs/compliance/misra-gcs.md` holds the guideline compliance summary. It lists every guideline with one status: Compliant, Deviations, Violations, or Disapplied.
- `docs/compliance/implementation-defined.md` lists each implementation-defined behavior that Bolis relies on (MISRA Dir 1.1).
- Update a compliance file in the same PR that changes the status it records.

## Checks

- The cppcheck MISRA addon checks MISRA C:2012 with the headline file that MISRA supplies for cppcheck. Obtain that file from MISRA under its terms. Store it outside the repository. Never commit it.
- The checker does not decide every guideline. A reviewer checks the directives and every guideline that the checker does not report on.
- `skills/c-compliance-check/SKILL.md` holds the full procedure.

## Guidelines that Bolis code meets most often

- Rule 9.1 (Mandatory): give every automatic object a value before the first read.
- Rule 17.7 and Dir 4.7: use every return value, and test every `esp_err_t`.
- Rule 10.3, 10.4, and 10.8: keep the essential type of a value when it is assigned, combined, or cast.
- Rule 11.3: decode buffers with `memcpy` or byte access, never with a pointer cast.
- Rule 14.4: write `if (ptr != NULL)` and `if (count > 0U)`, never `if (ptr)` or `if (count)`.
- Rule 15.5 and 15.1: one exit at the end of each function, and no `goto`.
- Rule 16.4 and 16.3: every `switch` has `default`, and every clause ends with `break`.
- Rule 12.1: parenthesize mixed operators.
- Rule 21.3 and Dir 4.12: no heap allocation.
- Rule 14.3: an invariant condition is allowed only for the infinite loop of a task, written `for (;;)`.
