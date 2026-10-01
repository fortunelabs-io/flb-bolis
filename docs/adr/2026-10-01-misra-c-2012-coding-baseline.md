# MISRA C:2012 with Amendments 1 and 2 as the coding baseline for Bolis C code

Date: 2026-10-01
Status: Proposed

## Context

The founder asked for a coding standard for the Bolis repository and supplied MISRA C:2004 and the SEI CERT C Coding Standard, 2016 Edition, as the basis. MISRA C:2004 supports only C90. ESP-IDF v5.5 compiles C with `-std=gnu17` by default, and ESP-IDF v6.1 compiles with `-std=gnu23` by default. Bolis supports ESP-IDF v5.5 and later ([2026-10-01-esp-idf-v5-5-minimum.md](./2026-10-01-esp-idf-v5-5-minimum.md)), and the ESP-IDF headers that Bolis includes use features newer than C90. Under MISRA C:2004, every Bolis file would have needed a blanket deviation from the first rule. MISRA C:2012 with Amendment 2 supports C90, C99, C11, and C18, the ISO C standard of 2018 that GCC calls C17. MISRA published MISRA C:2023 in 2023 and MISRA C:2025 in 2025. The open-source cppcheck MISRA addon checks MISRA C:2012 with a headline file that MISRA supplies for that purpose. Full checkers for MISRA C:2023 and MISRA C:2025 are commercial tools. MISRA Compliance:2020 defines the categories, the deviation records, and the guideline compliance summary of a compliance claim. The SEI CERT C 2016 Edition covers C11 and permits internal derivative works. If nothing was decided, Bolis C code would have had no checkable baseline, and a claim of MISRA compliance would have had no defined meaning.

## Alternatives considered

- Follow MISRA C:2004 as supplied, with a blanket deviation for the C90 rule and for the ESP-IDF headers.
- Follow MISRA C:2012 with Amendments 1 and 2.
- Follow MISRA C:2023.
- Follow MISRA C:2025.
- Follow the SEI CERT C rules only, without MISRA.

## Decision

Bolis C code follows MISRA C:2012 with Amendment 1 and Amendment 2. Bolis C code also follows the 99 rules of the SEI CERT C Coding Standard, 2016 Edition. If both standards cover a construct, the stricter rule applies. MISRA Compliance:2020 defines the compliance process. The component compiles with `-std=gnu17` on every supported ESP-IDF version. ESP-IDF, FreeRTOS, newlib, the radio drivers, and managed components are adopted code, outside the check. The deviation records, the guideline compliance summary, and the list of implementation-defined behavior live in `docs/compliance/` in the repository. The founder approves each deviation record. Bolis re-categorizes no guideline and disapplies no advisory guideline. The cppcheck MISRA addon and a manual review check the MISRA guidelines. clang-tidy checks the CERT rules.

## Consequences

- Bolis C code can use the C99, C11, and C17 features that MISRA C:2012 with Amendment 2 permits.
- Bolis C code cannot use C23 features, even on ESP-IDF v6.x.
- The free checker covers part of the guidelines.
- The directives and the guidelines that no tool decides need a manual review in each C review.
- Fortune Labs needs its own licensed copy of MISRA C:2012 before it claims MISRA compliance in public.
- The MISRA headline file for cppcheck stays outside the repository, under the terms of MISRA.
- MISRA C:2004 rule numbers do not appear in Bolis code, comments, or records.
- Console input and output need a deviation record for Rule 21.6.
- A move to MISRA C:2023 or MISRA C:2025 needs a new ADR.
- The Python code of the host package follows a separate standard, outside this record.
