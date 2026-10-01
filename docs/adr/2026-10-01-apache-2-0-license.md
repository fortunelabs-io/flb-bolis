# Apache-2.0 as the license for Bolis

Date: 2026-10-01
Status: Proposed

## Context

The Bolis v0 specification (v0.4) section 8.1 named Apache-2.0 and marked it `[proposal]`, and it recorded that the founder confirms the license before the first release. The repository held no `LICENSE` file, so every right stayed reserved and no developer could use the code. The component manifest needs an SPDX identifier before the first upload to the ESP Component Registry, and the host package needs a license field before the first upload to PyPI. Specification section 8.1 also states that a developer must install, run, and read the report without contacting Fortune Labs, and that a step that requires contact is a defect. Specification section 10 assigns the base to Fortunelabs HK through contributor agreements. ESP-IDF, which every source build compiles against, carries Apache-2.0. A license grant reaches every copy already distributed, so a later change of license does not withdraw it. If nothing was decided, the repository would publish code that nobody holds the right to use, and both package uploads would stop.

## Alternatives considered

- Apache-2.0, which carries an express patent grant and a notice requirement.
- MIT, which is shorter and grants no patent rights in its text.
- BSD 3-Clause, which grants no patent rights in its text.
- GPL-3.0, which requires a derivative work to carry the same license.
- No license, which reserves every right to Fortunelabs HK.

## Decision

Bolis carries Apache-2.0. The scope is the firmware component, the example project, the host package, the run record schema, and the report builder. The repository root holds the full license text in `LICENSE`. The component manifest states `license: "Apache-2.0"`. The host package states the same SPDX identifier in `pyproject.toml`. Fortunelabs HK holds the copyright.

## Consequences

- A developer uses, modifies, and redistributes Bolis without contacting Fortune Labs.
- A user receives an express patent grant from each contributor.
- A contributor who starts patent litigation over Bolis loses that grant.
- The grant stays in force for every version already distributed.
- A later license decision reaches later versions only.
- The ESP Component Registry upload and the PyPI upload proceed.
- Bolis matches the license of ESP-IDF, so a source build mixes no conflicting terms.
- A third party ships a closed derivative of Bolis without publishing its changes.
- Apache-2.0 requires a notice file in a redistribution, which MIT does not.
- The copyright line needs the registered name of Fortunelabs HK, which this record does not state.
- A per-file SPDX identifier header is a separate choice, which this record does not make.
- Specification section 8.1 drops its `[proposal]` label in its next version.
