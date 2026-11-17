# The drift band of a unicast pass

Date: 2026-11-17
Status: Proposed

## Context

The record [2026-11-16-the-drift-band-and-the-record-link-of-a-report.md](./2026-11-16-the-drift-band-and-the-record-link-of-a-report.md) fixed the drift band of one pass as the difference between the highest and the lowest `ratio` of `first_attempt_loss` across the valid baseline cells of that pass. It also stated that a pass with fewer than two such cells has a drift band of 0.

That record was written while the report builder was being read against the broadcast pass, where `first_attempt_loss` is the quantity of every cell. It did not check the unicast pass.

The accepted record [2026-11-13-loss-quantities-in-a-cell.md](./2026-11-13-loss-quantities-in-a-cell.md) states which quantity each pass holds. A broadcast pass states `first_attempt_loss`. A unicast pass states `post_retry_loss`. Both state `message_loss`. A unicast pass therefore holds no `first_attempt_loss`, and `_loss_sections` in `host/src/bolis/orchestrator.py` writes none.

Read together, the two records give every unicast pass a drift band of 0, because no baseline cell of that pass holds the quantity that the band reads. The band does not fail and it raises no error. It silently becomes 0.

Thinkbook section 10 states that the rule for moved loss runs on the broadcast pass, and that in a unicast run it also runs on the unicast pass. With a band of 0, that rule on a unicast pass reduces to the test of the two Wilson intervals, and the drift of the bench stops guarding the conclusion. Thinkbook section 8 gives the band exactly that guarding purpose, so a unicast conclusion would rest on a weaker rule than a broadcast conclusion while the report named neither difference.

A unicast run records both passes of every cell, including every baseline repeat, so the quantity that a unicast band needs is present in the record.

If nothing was decided, the report would name variables on a unicast pass under a rule that no source intended, and a reader of the paragraph could not tell which rule produced it.

## Alternatives considered

- The band of a pass reading the loss quantity of that pass, which keeps the band and the difference in one quantity.
- The band of a unicast pass reading the broadcast band of the same run, which compares a post-retry difference against a first-attempt width and so tests two quantities against each other.
- A band of 0 on a unicast pass, which is what the two records now imply and which drops the guard that the band exists to give.
- The rule running on the broadcast pass alone, which contradicts thinkbook section 10.
- A second band key in the run record, which puts a value that the report derives into the format that the nodes fill.

## Decision

The drift band of one pass reads the loss quantity that the pass states. A broadcast pass reads `first_attempt_loss`, and a unicast pass reads `post_retry_loss`. Everything else about the band is unchanged: it is the difference between the highest and the lowest `ratio` of that quantity across the valid baseline cells of that pass, and a pass with fewer than two such cells has a band of 0.

The rule for moved loss compares the ratios of the same quantity that the band read, so the band and the difference carry one unit on both passes.

This amends [2026-11-16-the-drift-band-and-the-record-link-of-a-report.md](./2026-11-16-the-drift-band-and-the-record-link-of-a-report.md), which keeps `Status: Accepted`. That record names `first_attempt_loss` where it should name the quantity of the pass. Every other statement of it stands, including the shaded range, the record link, and the report file name.

## Consequences

- A unicast pass keeps the drift guard, so a unicast conclusion rests on the same rule as a broadcast conclusion.
- The band and the difference carry one quantity on each pass, so no comparison mixes a first-attempt width with a post-retry difference.
- A chart of a unicast pass shades the range of the post-retry ratios of its baseline repeats, which are the two numbers that its band comes from.
- The post-retry loss of a healthy pass sits below its first-attempt loss, so a unicast band is narrower than a broadcast band of the same bench. The rule is therefore not more lenient on the unicast pass for that reason alone.
- A reader of a report reproduces either paragraph from the record, because each band reads a quantity that the record states for that pass.
- This record amends a record that reached `Accepted` one day earlier. The error was a decision written against one pass and applied to two, and the check that caught it was reading the loss quantities record before writing the code.
- Watch the first unicast run for a band of 0 on the unicast pass. That value now means fewer than two valid baseline cells, and no longer a missing quantity.
