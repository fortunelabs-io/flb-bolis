---
paths:
  - "**/CMakeLists.txt"
  - "**/*.cmake"
  - "**/Kconfig*"
  - "**/*.{yml,yaml}"
  - "**/*.json"
  - "**/*.{html,css,js}"
  - "**/*.sh"
---

# Other languages

## CMake

- Register the component with `idf_component_register`.
- List every source file by name. Do not use `file(GLOB)`.
- Put a dependency that only the sources use in `PRIV_REQUIRES`. Put a dependency that the public headers need in `REQUIRES`.
- Set the language standard for the component: `target_compile_options(${COMPONENT_LIB} PRIVATE -std=gnu17)` (decision 8).
- Do not add `-Werror` to the component. A newer compiler in the build of a user can add warnings. CI treats warnings as errors in its own build of `components/bolis/examples/bench`.

## Kconfig

- Prefix every symbol with `BOL_`.
- The prebuilt image sets `BOL_PREBUILT`, so the `hello` reply states the firmware path (thinkbook section 7). Its default is `n`.
- Write help text in the writing standard (`writing.md`).

## Component manifest (`idf_component.yml`)

- State `version`, `description`, `license`, `url`, and `repository`.
- The repository is `https://github.com/fortunelabs-io/flb-bolis`.
- The license is the SPDX identifier that the founder confirmed before the first release. Apache-2.0 is the proposal in specification section 8.1.
- Require ESP-IDF v5.5 or later under `dependencies` with `idf: ">=5.5"` (decision 3).

## GitHub Actions

- Pin every third-party action to a full-length commit SHA. Put the version in a comment after the SHA.
- Set `permissions: contents: read` at the top of each workflow. Raise a permission only for the job that needs it.
- Never use `pull_request_target` or `workflow_run` with a checkout of an untrusted pull request.
- Pass untrusted values, such as a PR title or a branch name, to a shell step through an environment variable. Never place them directly in a `run` script.
- Build the component on ESP-IDF v5.5 and on each later minor release that Espressif supports (decision 3).
- Build the release images from the tag on ESP-IDF v5.5.x (decision 7).

## YAML

- Indent with 2 spaces.
- Quote a string that YAML can read as another type, such as a version.

## JSON and the run record

- The run record format has a JSON Schema in the repository. Change the schema only through a PR. A change to the record format needs an ADR, because the corpus reuses the format.
- Every record carries the version of its format.
- Name keys in `snake_case`.
- Write times as ISO 8601 in UTC.
- Give every number its label (decision 5).
- Never store a MAC address.

## HTML report

- The report is one static file. It loads no font, script, style sheet, or image from a network (thinkbook section 10).
- Inline every style and every script. Draw charts as inline SVG.
- Escape every string from the run record before it enters the HTML. The `declared` section holds text that the user typed.
- Do not assign record data to `innerHTML`.
- Show the label of every number and a legend of the four labels (decision 5).
- Show the claim-limit sentence and the three limits of specification section 4.

## Shell

- Start every script with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Quote every variable expansion.
- Keep every script free of ShellCheck findings.
