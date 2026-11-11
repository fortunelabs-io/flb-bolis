# cppcheck 2.19.1 pinned and built from source for the MISRA check

Date: 2026-11-09
Status: Accepted

## Context

The check workflow that merged on 2026-11-06 installed cppcheck with the apt of the `espressif/idf:release-v5.5` container. The config of that image names Ubuntu 24.04, and its apt carried cppcheck 2.13.0. The machine that produced the compliance evidence carried cppcheck 2.19.1 from the Fedora 43 package, and `docs/compliance/misra-gcs.md` recorded 2.19.1 as the version behind the compliance evidence. On the same sources, 2.19.1 reported 10 findings of Rule 10.1 and 9 findings of Rule 10.4, while 2.13.0 reported the same 10 findings of Rule 10.1 and none of Rule 10.4. A rerun on 2026-11-09 reproduced the figures of 2.19.1 over 18 files. CI therefore checked less than the compliance evidence claimed. Approved record D-002 covers every one of those findings, because each one arises in the expansion of an adopted macro, so no native code was at risk. mise lists no cppcheck, so the version cannot sit beside the ruff and the ShellCheck pins in `mise.toml`. The firmware sweep was the next body of C code, and it computes cell identifiers, payload sizes, transmit power set values, and histogram bins, which is where Rule 10.4 applies. If nothing was decided, the first compliance claim about the sweep would inherit a checker version that no tracked file stated, and a later Ubuntu release would change the result of the check without a change in this repository.

## Alternatives considered

- Build cppcheck 2.19.1 from source in the MISRA job, and assert the version that the build produced.
- Install the version that the apt of the image carries, and lower the compliance evidence to what that version reports.
- Move the MISRA job to a base image that already carries cppcheck 2.19.x.
- Run cppcheck in a job outside the ESP-IDF container, over the compilation databases that the build job uploads.
- Pin no version, and record the checker version of each run in the compliance summary.

## Decision

CI pins cppcheck 2.19.1, which is the version behind the compliance evidence. The MISRA job builds that version from source inside the container, prints the version that the build produced, and fails if the printed version differs from the pin. The workflow holds the version in one environment variable. `docs/compliance/misra-gcs.md` names the same version. Every compliance claim names the checker version that produced it. A change of the pinned version updates the workflow and the compliance summary in one change.

## Consequences

- CI and the compliance evidence check the same guidelines, so a claim in `docs/compliance/misra-gcs.md` holds for a pull request.
- Rule 10.4 stays under check before the sweep adds the arithmetic that the rule governs.
- The MISRA job gains 1 minute and 19 seconds for the source build, against the job timeout of 30 minutes. That figure covers the build requirements, the download, the compile, and the install, and it comes from the first run of the job.
- The source build needs no cache at that cost. A cache becomes a question again if a later cppcheck release lengthens the build.
- The job depends on the build requirements of cppcheck, which it installs in the container.
- This rules out reading the checker from apt, so a new release of the base image no longer changes the result of the check on its own.
- A contributor on another distribution can hold a different version, and the compliance procedure reports the version that it ran.
- A change of the pinned version changes the evidence behind the coding baseline, so it needs a new record.
- Watch the version assertion, because a binary that the image already carries would otherwise pass as the pinned one.
- The local compliance procedure names the pinned version in its next revision.
