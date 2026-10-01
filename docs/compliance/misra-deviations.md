# MISRA C:2012 deviation records

Bolis C code follows MISRA C:2012 with Amendment 1 and Amendment 2 (`docs/adr/2026-10-01-misra-c-2012-coding-baseline.md`). MISRA Compliance:2020 defines the form of a deviation record.

This file cites a guideline by its number only. It carries no text from a MISRA document.

A record carries a status of `Proposed`, `Approved`, or `Withdrawn`. Only the founder sets `Approved`. Code that relies on a record with the status `Proposed` does not merge.

A violation of a Required guideline needs an approved record. A violation of an Advisory guideline needs no record, and it carries an inline note instead. Bolis re-categorizes no guideline and disapplies no guideline.

Mark a line that relies on a record with a suppression comment that names the guideline and the ID:

```c
// cppcheck-suppress misra-c2012-21.6 ; D-001
```

| ID | Guidelines | Status | Approved |
|---|---|---|---|
| D-001 | Rule 21.6 (Required) | Approved | 2026-10-01 |
| D-002 | Findings that arise only in adopted code | Approved | 2026-10-01 |

---

## D-001

**Guidelines.** Rule 21.6 (Required).

**Applies to.** The console module of the component `fortunelabs-io/bolis`, in `components/bolis/src/`. No other module.

**Circumstances in which a violation is acceptable.** The module reads a control line from the console and writes a reply to it. The control plane of Bolis is the console of the node (thinkbook section 7, `docs/adr/2026-10-01-control-line-wire-format.md`). No other module reads or writes a stream.

**Reason.** The control plane carries every command of a run, and a failing radio channel must not break it. The console is the only channel that reaches the host without the radio. ESP-IDF exposes the console through the standard input and output streams, so a module that drives the console uses them.

**Background.** The host sends one command per line, and a node answers with one line. A run cannot start without this exchange, so the design has no variant that avoids the console. The alternatives in the wire format record were a binary frame on the serial line, the ESP-IDF console component, and a second UART. Each of them still reaches the same streams, or it needs a second cable that the bench of a user does not have.

**Requirements, risk assessment, and precautions.**

- Only the console module includes `<stdio.h>`. A review of any other module that includes it rejects the change.
- Every buffer has a fixed size, and the module allocates no heap memory.
- Every read is bounded. The module rejects a line longer than the limit in the wire format record, and it counts each rejected line.
- Every format string is a string literal. The module never passes external data as a format string (CERT FIO30-C).
- The module keeps the result of a character read in an `int` and compares it with `EOF` (CERT FIO34-C).
- The module does not assume that a line read returned a non-empty line (CERT FIO37-C).
- Rules 22.1 to 22.10 apply to the console streams.
- The module treats every control line as untrusted input (Dir 4.14).
- The risk is bounded, because a malformed line reaches a parser with fixed buffers and a counted rejection path, and it never reaches the radio.

---

## D-002

**Guidelines.** Any guideline whose finding arises only in adopted code.

**Applies to.** Every native C file of Bolis, for findings that a reviewer traces to an adopted header or to the expansion of an adopted macro.

**Circumstances in which a violation is acceptable.** Bolis code includes ESP-IDF and FreeRTOS headers, and it calls their macros, such as `ESP_LOGI` and `WIFI_INIT_CONFIG_DEFAULT`. A checker reports the finding against the line of Bolis code that expands the macro, and not against the adopted header that defines it.

**Reason.** The coding baseline places ESP-IDF, FreeRTOS, newlib, the radio drivers, and every file under `managed_components` or `build` outside the check. Bolis does not modify adopted code. A finding that Bolis cannot fix without editing adopted code is not a Bolis violation.

**Background.** A clang-tidy run on 2026-10-01 generated 909 warnings and suppressed 891 in non-user code. Of the 18 that remained, every one came from an ESP-IDF header. No finding sat in a Bolis file.

**Requirements, risk assessment, and precautions.**

- The check excludes adopted paths by file filter and by header filter.
- A reviewer traces each finding to its origin. A finding that the reviewer cannot trace to an adopted header or macro is a native finding, and this record does not cover it.
- A finding that an adopted interface forces in native code, such as a `void *` callback argument, is a native finding. This record does not cover it.
- The risk is bounded, because the adopted code is a released ESP-IDF version that the run record names, and a reader can rebuild the same image from that version.
