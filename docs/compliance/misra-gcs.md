# MISRA C:2012 guideline compliance summary

MISRA Compliance:2020 defines the guideline compliance summary. It lists every directive and every rule with one status: Compliant, Deviations, Violations, or Disapplied.

**Fortune Labs has not issued this summary.** This file records why, and what completes it.

## Why the summary is not issued

A summary states the category of every guideline. The licensed MISRA C:2012 text governs those categories. Fortune Labs does not hold a licensed copy, so no category in this repository is verified against the source that governs it. A summary built on unverified categories would state a compliance position that nobody checked.

The checker is also incomplete. The cppcheck MISRA addon needs the headline file that MISRA supplies for that purpose. That file is licensed from MISRA, it stays outside this repository, and it is not present. The MISRA guidelines therefore rest on manual review alone.

## What completes it

1. Fortune Labs obtains a licensed copy of MISRA C:2012 with Amendment 1 and Amendment 2.
2. A reviewer checks the category of every guideline against the licensed text.
3. Fortune Labs obtains the MISRA headline file for cppcheck and stores it outside this repository.
4. The cppcheck MISRA addon runs over the native files.
5. A reviewer decides every directive and every guideline that the checker does not report on.
6. This file replaces its current contents with the summary.

## Until then

Bolis makes no public claim of MISRA compliance. The coding baseline record states this condition, and it holds for the README, a release note, the ESP Component Registry description, and any public reply.

Bolis C code still follows MISRA C:2012 with Amendment 1 and Amendment 2 as its coding baseline. The absence of a summary limits the claim, not the practice.

## Current evidence

Each check below ran on 2026-10-01 against the firmware component on `main`.

| Check | Tool | Result |
|---|---|---|
| Build | ESP-IDF v5.5.4, target esp32 | No warning in a native file |
| Layout | astyle-py 1.1.0 with Astyle v3.1 | No native file changed |
| Static analysis | cppcheck 2.19.1, `--enable=style` | No finding in a native file |
| CERT C | Espressif LLVM 19.1.2, `cert-*` | No finding in a native file. Every finding came from an adopted header, under record D-002 |
| Documentation | Doxygen 1.14.0 | No warning |
| MISRA C:2012 | None | Manual review only |

The deviation records are in `misra-deviations.md`. The implementation-defined behavior is in `implementation-defined.md`.
