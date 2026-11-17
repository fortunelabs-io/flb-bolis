# MISRA C:2012 guideline compliance summary

MISRA Compliance:2020 defines the guideline compliance summary. It lists every directive and every rule with one status: Compliant, Deviations, Violations, or Disapplied.

**Fortune Labs has not issued this summary.** This file records why, and what completes it.

## Why the summary is not issued

A summary states the category of every guideline. The licensed MISRA C:2012 text governs those categories. Fortune Labs does not hold a licensed copy, so no category in this repository is verified against the source that governs it. A summary built on unverified categories would state a compliance position that nobody checked.

The checker is also incomplete. The cppcheck MISRA addon runs without the headline file that MISRA supplies, and it reports a guideline by its number. That file is licensed from MISRA, it stays outside this repository, and it is not present, so the addon names a guideline but prints no text for it. The addon also decides only the guidelines it implements. A manual review therefore covers every directive and every guideline that the addon does not report on.

## What completes it

1. Fortune Labs obtains a licensed copy of MISRA C:2012 with Amendment 1 and Amendment 2.
2. A reviewer checks the category of every guideline against the licensed text.
3. Fortune Labs obtains the MISRA headline file for cppcheck and stores it outside this repository.
4. The cppcheck MISRA addon runs over the native files with the rule texts, so each finding carries the text of its guideline.
5. A reviewer decides every directive and every guideline that the checker does not report on.
6. This file replaces its current contents with the summary.

## Until then

Bolis makes no public claim of MISRA compliance. The coding baseline record states this condition, and it holds for the README, a release note, the ESP Component Registry description, and any public reply.

Bolis C code still follows MISRA C:2012 with Amendment 1 and Amendment 2 as its coding baseline. The absence of a summary limits the claim, not the practice.

## Current evidence

Each check below ran on 2026-11-17 against the firmware component, its test component, and the bench example. The run covers `components/bolis/src`, `components/bolis/include`, `components/bolis/priv_include`, `components/bolis/test`, `components/bolis/test_apps`, and `components/bolis/examples/bench/main`, which hold 28 native files. It ran on `main` at commit 68a4735, which carries the five control line commands, the sending loop, the receiving loop, and the report builder.

| Check | Tool | Result |
|---|---|---|
| Build | ESP-IDF v5.5.4, target esp32, GCC and Clang | No warning in a native file |
| Layout | astyle-py 1.1.0 with Astyle v3.1 | No native file changed |
| Static analysis | cppcheck 2.19.1, `--enable=style` | No finding in a native file beside the ones that the MISRA addon reports |
| CERT C | Espressif LLVM 19.1.2, `cert-*` | 10 translation units, and no finding in a native file. Every finding came from an adopted header, under record D-002 |
| Documentation | Doxygen 1.14.0 | No warning |
| MISRA C:2012 | cppcheck 2.19.1 MISRA addon without the rule texts, and manual review | 21 findings over 4 native files: 11 of Rule 10.1 and 10 of Rule 10.4. Each one falls in the expansion of `ESP_LOGx` or `WIFI_INIT_CONFIG_DEFAULT`, under record D-002 |
| Reader tests | ESP-IDF unity, 97 test cases, run on the host | No failure. No case has run on a node |

The MISRA row states what the addon and the review found. It states no compliance position, because the addon reports a guideline by number only and decides only the guidelines it implements. The reader tests support Dir 4.1. They are not a MISRA check.

**How the MISRA run reaches every native file.** The addon runs once per compilation database, over `components/bolis/examples/bench/build` and `components/bolis/test_apps/json/build`. The test files compile in the second database only, so a run of the first alone reports no finding in them. The two runs together opened 50 files. The filter keeps every finding of a native file, and not the findings of the MISRA addon alone, because the plain style checks of cppcheck report a native finding that no guideline number carries.

## Inline suppressions

Each suppression below sits on the line above the code it covers, and each one names its guideline and its basis. A guideline in the Required category carries a deviation ID, and a guideline in the Advisory category carries a note.

| Guideline | Places | Basis |
|---|---|---|
| Rule 21.6 | 18 | Record D-001. The console module reads and writes the control line through the standard streams |
| Rule 8.7 | 18 | Note. Another file calls the function, and the addon reads one translation unit at a time |
| Rule 5.9 | 6 files | Note. The `TEST_CASE` macro of unity builds a function name from `__LINE__`, so two test files collide at one line number |
| Rule 11.5 | 5 | Note. A port or a task passes its context as `void *` |
| Rule 8.9 | 2 | Note. The object outlives the function that uses it, or it overruns the stack of the task |
| Rule 2.5 | 2 | Note. Another translation unit uses the macro, which the addon does not see |
| Rule 7.2 | 1 | Record D-002. The initializer is an adopted macro |
| Rule 10.8 | 1 | Record D-002. The cast sits in the expansion of an adopted assert macro |

The Rule 8.7 suppressions are permanent. Each one covers a function that a module in another file calls, and the addon reads a dump of one translation unit, so it cannot see that caller. An earlier wording stated that the caller arrived in a later change. Those changes landed, and the wording now states the reason that holds.

The deviation records are in `misra-deviations.md`. Both D-001 and D-002 reached `Approved` on 2026-10-01, so no merged code relies on a record with the status `Proposed`. The implementation-defined behavior is in `implementation-defined.md`.
