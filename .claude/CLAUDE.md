# Bolis repository instructions

Bolis is a bench tool for ESP-NOW. It consists of firmware for two ESP32 nodes and a host CLI. The firmware sweeps the ESP-NOW link between the two nodes. The host CLI writes one report that shows which variable moves frame loss near the configuration of the user.

The `.claude/` directory is in `.gitignore`, so these instructions stay on this machine. A rule that CI or another contributor must also follow belongs in a tracked file as well, such as a file in `docs/compliance/`, `.github/`, or a tool configuration file.

## Sources of truth

- `adr/` holds the accepted decision records. An accepted record overrides any rule in `.claude/` that contradicts it.
- The Bolis specification v0.4 holds the scope. The Bolis thinkbook v0.2 holds the theory and the design.
- If a task depends on the specification or the thinkbook and the file is not in the repository, ask for it.
- If two sources disagree, stop and report the conflict. Do not pick one source silently.

The rules cite decision records by number.

| No. | Record |
|---|---|
| 1 | `2026-10-01-loss-metric-and-send-mode.md` |
| 2 | `2026-10-01-phy-rate-fixed-at-1-mbps.md` |
| 3 | `2026-10-01-esp-idf-v5-5-minimum.md` |
| 4 | `2026-10-01-local-one-variable-sweep.md` |
| 5 | `2026-10-01-number-origin-labels.md` |
| 6 | `2026-10-01-reproducibility-verification.md` |
| 7 | `2026-10-01-radio-ownership-and-prebuilt-firmware.md` |
| 8 | `2026-10-01-misra-c-2012-coding-baseline.md` |

## Layout

| Path | Contents |
|---|---|
| `components/bolis/` | The ESP-IDF component `fortunelabs-io/bolis`. The registry uploads this directory only |
| `components/bolis/examples/bench/` | The example project for source builds and for the prebuilt images |
| `host/` | The Python package `bolis`, with `pyproject.toml`, `src/bolis/`, and `tests/` |
| `host/src/bolis/firmware/` | The prebuilt images that CI places there at release time. Git does not track them |
| `schema/` | The JSON Schema of the run record format |
| `docs/Doxyfile` | The Doxygen configuration |
| `docs/compliance/` | The MISRA deviation records, the guideline compliance summary, and the implementation-defined behavior |
| `adr/` | The decision records |
| `.github/` | The PR template and the CI workflows |

A `README.md` that says "Delete this file" is a placeholder. Delete it in the PR that adds the first real file to its directory.

## Languages and versions

| Part | Language | Version |
|---|---|---|
| Firmware component `components/bolis/` and its example `components/bolis/examples/bench/` | C | C17, compiled with `-std=gnu17` on ESP-IDF v5.5 or later (decisions 3 and 8) |
| Host CLI, flasher, and report builder | Python | 3.10 or later, the minimum of esptool 5 |
| Build and package files | CMake, Kconfig, YAML, TOML | ESP-IDF component manager and PEP 621 formats |
| Run record | JSON | One file per run, checked against a JSON Schema |
| Report | HTML, CSS, and JavaScript | One static file that makes no network request |

Write C17 even when ESP-IDF v6.x compiles with `gnu23` by default. MISRA C:2012 with Amendment 2 covers C18 at most.

## Rule files

| File | Loads |
|---|---|
| `rules/writing.md` | Always |
| `rules/development-sop.md` | Always |
| `rules/pull-requests.md` | Always |
| `rules/decision-records.md` | Always |
| `rules/c/coding-standard.md` | When a C source file or header is read |
| `rules/c/misra-c-2012.md` | When a C source file or header is read |
| `rules/c/cert-c-2016.md` | When a C source file or header is read |
| `rules/c/doxygen.md` | When a C source file, a header, or a Doxyfile is read |
| `rules/python/coding-standard.md` | When a Python file or `pyproject.toml` is read |
| `rules/other-languages.md` | When a CMake, Kconfig, YAML, JSON, HTML, or shell file is read |

`reference/` holds the full MISRA C:2012 and CERT C catalogs with the Bolis status of each guideline. Read the matching catalog before a review of C code. `skills/c-compliance-check/` holds the check procedure for a C change.

## Always

- Never write an em dash in any file, comment, commit message, or PR body.
- Never invent a number, a measurement, a guideline text, a guideline category, a tool flag, or an ADR filename. If a value is unknown, write a placeholder in angle brackets and say so.
- Never copy text from a MISRA document into the repository, a comment, a commit message, or a PR body. Cite the guideline number only.
- Never commit a standard document, a PDF of a standard, a secret, a build output, or the `.claude/` directory.
- Before a change that is hard to reverse, run the ADR test in `rules/decision-records.md`.
- Keep the host CLI offline. The host package sends nothing off the machine of the user (specification section 7).
- Never store a MAC address in a run record, a report, or a log.
- Label every number in a run record, a report, or a public reply with `[measured]`, `[configured]`, `[derived]`, or `[declared]` (decision 5).

## Commands

These commands are the target. If a configuration file that a command needs does not exist, report it. Create a tool configuration only through a PR.

| Task | Command |
|---|---|
| Build the example | `idf.py -C components/bolis/examples/bench build` |
| Format C | `astyle_py --rules=$IDF_PATH/tools/ci/astyle-rules.yml <file>` |
| Check C against MISRA C:2012 | See `skills/c-compliance-check/SKILL.md` |
| Check C with clang-tidy | `IDF_TOOLCHAIN=clang idf.py -C components/bolis/examples/bench clang-check` |
| Build the C API documentation | `doxygen docs/Doxyfile` |
| Lint Python | `ruff check .` |
| Format Python | `ruff format .` |
| Check Python types | `mypy --strict <package directory>` |
| Test Python | `pytest` |
