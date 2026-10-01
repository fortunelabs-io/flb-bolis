---
name: c-compliance-check
description: Check Bolis C changes against MISRA C:2012, SEI CERT C 2016, the ESP-IDF layout, and the Doxygen rules, then report each finding. Use before a commit or a PR that changes a .c or .h file, and when the founder asks for a compliance review of C code.
---

# C compliance check

Run the steps in order. Report the result of every step. If a step cannot run, name the step and the reason, and continue with the next step. Never report a step as passed if it did not run.

## 1. List the changed files

Run `git diff --name-only main...HEAD -- '*.c' '*.h'`. Remove every path under `managed_components/` or `build/`. The rest are the native files of this check.

## 2. Build

1. Run `idf.py -C examples/bench build` with ESP-IDF v5.5.
2. Record every compiler warning in a native file. Treat each warning as a finding.
3. The build writes `examples/bench/build/compile_commands.json`. Steps 4 and 5 use it.

## 3. Layout

1. Run `astyle_py --rules=$IDF_PATH/tools/ci/astyle-rules.yml` on each native file.
2. If the tool changes a file, report the file. The founder decides whether the change enters the commit.

## 4. MISRA C:2012

1. Locate the MISRA headline file for cppcheck outside the repository. If it is missing, report that the MISRA check cannot run. Do not create the file.
2. Locate the addon file `misra.json` outside the repository. It names `misra.py` and passes `--rule-texts=<path to the headline file>`.
3. Run cppcheck on the native files:

   ```bash
   cppcheck --project=examples/bench/build/compile_commands.json \
     --addon=<path to misra.json> \
     --file-filter='<path of the native sources>/*' \
     --inline-suppr --enable=style \
     --suppress='*:<IDF_PATH>/*'
   ```

4. Read `.claude/reference/misra-c-2012-catalog.md`.
5. Review by hand every directive and every guideline that cppcheck does not report on. The review covers the changed lines.

## 5. CERT C

1. Run `IDF_TOOLCHAIN=clang idf.py -C examples/bench clang-check` with a `.clang-tidy` file that enables `cert-*`.
2. Keep only the warnings in native files from `warnings.txt`.
3. Read `.claude/reference/cert-c-2016-catalog.md`.
4. Review by hand each L1 rule in `rules/c/cert-c-2016.md` against the changed lines.

## 6. Documentation

1. Run `doxygen docs/Doxyfile`.
2. Treat each warning as a finding.

## 7. Triage

Handle each finding by its source and category:

| Finding | Action |
|---|---|
| MISRA Mandatory | Fix the code. No deviation is possible. |
| MISRA Required | Fix the code. If a fix is not possible, draft a deviation record with status `Proposed` in `docs/compliance/misra-deviations.md`, and stop for the approval of the founder. |
| MISRA Advisory | Fix the code. If a fix is not reasonable, add an inline suppression comment that names the guideline and the reason. |
| CERT L1 | Fix the code. |
| CERT L2 or L3 | Fix the code, or state in the PR body why the finding is false. |
| Compiler or Doxygen warning | Fix the code or the documentation. |
| Finding only in an adopted header or macro | Record it under deviation D-002. Do not edit adopted code. |

## 8. Compliance summary

If a guideline changes status, update `docs/compliance/misra-gcs.md` in the same change.

## 9. Report

Report one table with one row per step: the step, the command, the result, and the open findings. Then list each open finding with the file, the line, the guideline or rule, and a proposed fix.
