# Host execution of the reader tests

Date: 2026-11-06
Status: Proposed

## Context

The test cases in `components/bolis/test/test_bol_json.c` ran inside CI only. The CI job
built `components/bolis/test_apps/json` for the ESP-IDF linux target inside the
`espressif/idf` container, where the container provides the libbsd development headers.

That target did not build on a developer machine. The linux component of ESP-IDF wraps the
libbsd headers, and installing them needs root. A developer therefore pushed a branch to
learn whether the reader still passed its cases, and a failing case cost one CI round trip
to find.

If nothing is decided, the repository keeps test cases that only CI can execute, and the
local stages in `tools/prep` hold a test stage that never runs.

## Alternatives considered

Build the test app for the ESP-IDF linux target on the developer machine. It needs the
libbsd development headers and root access, which a developer machine may withhold.

Run the test app under qemu. It adds an emulator and a target image for cases that touch no
hardware.

Flash the test app to a node and read the result over the serial line. It makes a test run
depend on attached hardware that the reader never uses.

Leave the cases in CI alone and drop the test stage from `tools/prep`. It keeps the test
feedback one push away from the author of a change.

## Decision

The repository carries `components/bolis/test/host_runner.c`. The runner supplies the five
hooks that `unity_config.h` of ESP-IDF expects, `setUp`, `tearDown`, and a `main` that runs
every registered case.

`tools/prep test` compiles that runner, the test file, `components/bolis/src/bol_json.c`,
and the unity sources of ESP-IDF with the host compiler, then runs the result. The stage
needs no container, no root, and no node.

The ESP-IDF test app under `components/bolis/test_apps/json` stays, and the CI job keeps
building it for the linux target. The host run adds a second path to the same cases, and it
replaces neither the app nor the job.

## Consequences

A developer runs the reader cases on this machine in seconds.

The host path covers the reader alone, because `bol_json.c` includes `esp_err.h` and nothing
else of ESP-IDF.

A case that touches a radio, a FreeRTOS task, or NVS does not run under the runner. Such a
case belongs in the test app, which runs on a node.

The host compiler is not the target compiler, so a pass on the host does not prove a pass on
a node. CI on the linux target and a run on a node stay the authority.

`host_runner.c` is a file that Bolis authors, so the coding baseline covers it (decision
record `2026-10-01-misra-c-2012-coding-baseline.md`).

The runner defines `unity_testcase_register`, `unity_putc`, `unity_flush`, `unity_gets`, and
the three `unity_exec_time_` functions. ESP-IDF fixes each of those names, so the file holds
seven external names that carry no `bol_` prefix. The coding standard asks for that prefix,
and the file states the reason at each definition.

The runner depends on `TEST_CASE` registering a case through a constructor function rather
than through a linker section. Watch that mechanism on an ESP-IDF upgrade. A run that
reports zero cases points at a change there.

Watch for a result that differs between the host run and the CI run. A difference points at
an assumption about the compiler inside the reader.
