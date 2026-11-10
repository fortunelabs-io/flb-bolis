# The run command resolves a cell plan from the command line

Date: 2026-11-10
Status: Proposed

## Context

The merge of 2026-11-09 added `host/src/bolis/sweep.py`, which holds `build_plan` and `build_grid_plan`. `host/src/bolis/cli.py` called neither one. Its `_run_run` validated the two ports, the channel, the transmit power set value, and the payload size, then raised `BolisNotImplementedError`. Both builders needed a payload limit and a shuffle seed, and the command line offered neither, so neither builder was reachable. The parser also set `--channel`, `--power`, and `--payload` to the fallback values of thinkbook section 8 as argparse defaults, so a baseline that the user typed and an absent baseline arrived at the handler as the same three integers. Record `2026-10-01-local-one-variable-sweep.md` requires the run record to state which baseline applied, and `CellPlan.is_fallback_baseline` carries that flag, so those defaults made the flag unreachable. The control line reader, the flasher, and the JSON Schema of the run record did not exist, so a run could not complete and no test case could read a plan. If nothing is decided, the plan builders stay unreachable from the command line, and the first run record states a baseline source that no code computed.

## Alternatives considered

- Add a flag to the run command that prints the resolved plan and returns 0.
- Add a subcommand that prints a plan, which splits one user flow across two commands.
- Report the plan inside the message that `BolisNotImplementedError` carries, which adds no command line surface and gives a test case nothing to read.
- Print the plan on every run, before a pass sends its frames.
- Reach the builders when the control line exists, and leave the command line as it was.
- Name the flag `--dry-run`, which the writing standard forbids as an idiom.
- Reject a baseline that names one or two of the three values, and require all three together.
- Treat a baseline that names one or two values as no configuration, and sweep around the fallback baseline.
- Accept a seed on the command line, so one cell order repeats across runs.

## Decision

`bolis run` accepts `--print-plan`. With that flag, the command resolves the baseline, builds the plan, prints it, and returns 0. Without that flag, the command builds the same plan and then reports the missing control line, and its message names the plan.

`--limit` selects the packet payload limit, 250 bytes or 1470 bytes, and 1470 bytes is the default. `--plan` selects `default` or `grid`. Thinkbook section 8 states both options.

A baseline option that the user omits takes its fallback value. A plan carries the fallback baseline only when the user gives no channel, no transmit power, and no payload size.

The run command generates the shuffle seed and prints it. It accepts no seed option.

Every number that `--print-plan` writes carries a label of record `2026-10-01-number-origin-labels.md`. The cell count and the frames per cell carry `[configured]`, because thinkbook section 9 labels a value computed from a `[configured]` input with the label of that input.

## Consequences

- A plan reaches a reader before the control line exists, so the cell count, the cell order, and the baseline source are testable today.
- `is_fallback_baseline` follows from a real input, so the baseline source of record `2026-10-01-local-one-variable-sweep.md` is recorded rather than assumed.
- `--print-plan` returns 0 and a run without it returns 1. The two statuses report two different outcomes: a plan that was built, and a run that cannot start.
- `--print-plan` is public command line surface, so a later removal breaks a caller that scripts it.
- The printed form is not the report. Specification section 6 governs the report, and this output carries no chart, no interval, and no link to a run record.
- This rules out a seed on the command line, so repeating one exact cell order across runs needs a new record.
- A baseline that names one or two values counts as a configuration, so a run record states the user as its baseline source.
- The grid plan prints 968 cell lines, which reach a terminal rather than a file.
- The output names no MAC address, which follows specification section 7.
- Watch the label of the cell count when the report exists. A count that a run produces rather than a plan carries a different label.
