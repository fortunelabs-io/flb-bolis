# The loss quantities that a cell entry states

Date: 2026-11-13
Status: Accepted

## Context

The run record format record made `schema/run-record.schema.json` the normative statement of the format, and it named thinkbook section 9 and the control line command fields record as the inventory that the schema states. The schema reached the repository with the six sections, the counters of each pass, and no loss quantity.

Thinkbook section 9 listed the loss quantities in the `cells` section. Thinkbook section 2 named three of them, and gave each one its own observable: first-attempt loss from sequence gaps at the receiver, post-retry loss from send callback failures at the sender, and message loss from missing fragments per message at the receiver. Thinkbook section 3.7 wrote the loss estimate of a cell as the lost frames over the sent frames, and it stated that the report uses the Wilson score interval at 95%. No source named a key for any of those quantities, and no source stated which counters each one divides.

Two sources pointed in different directions on one point. Thinkbook section 9 held the loss quantities in the record. Thinkbook section 3.7 assigned the interval to the report. A record that stores a quantity and a report that computes the same quantity disagree the moment one of them changes.

`record_version` stood at 1, and no run had written a record, so a key added before the first record cost no rise of that version. A key added afterward costs version 2.

The schema also required the counters of both nodes on every entry of `cells`. An attempt that a node reset ended, or that fell silent during its pass, completes no `stats` command, so such an entry carries no counters to require.

If nothing was decided, the change that computes a loss quantity would name its key, choose its denominator, and settle whether the record or the report holds the interval, all by accident, in an artifact that a corpus reuses.

## Alternatives considered

- Every loss quantity computed by the report and stored nowhere, which leaves a shared record without the conclusion that the record exists to carry.
- One loss object with a key that names which quantity it holds, which makes a reader read two keys to learn one.
- The ratio in the record and the interval in the report, which lets two readers of one record state two intervals.
- The lost count and the sent count stored beside each ratio, which repeats counters that the same entry already states.
- A confidence level stored in each cell, which lets one record hold two levels.
- A loss quantity on an attempt that the run invalidated, which states a conclusion from counters that no `stats` command completed.
- Message loss counted against the messages that the receiver saw, which drops a message that produced no fragment at all.
- Post-retry loss counted on a broadcast pass, where the driver allows no retry, so the quantity has no meaning.

## Decision

A cell entry states the loss quantities of its pass, under the names that thinkbook section 2 gives them. A broadcast pass states `first_attempt_loss`. A unicast pass states `post_retry_loss`. Both passes state `message_loss`.

Each of the three is an object with three keys, and each key holds a `[derived]` number:

```json
"first_attempt_loss": {
  "ratio": {"value": 0.0065, "label": "derived"},
  "wilson_interval_low": {"value": 0.0038, "label": "derived"},
  "wilson_interval_high": {"value": 0.0111, "label": "derived"}
}
```

The record holds the interval beside the ratio, because thinkbook section 9 holds the loss quantities in the record, and an interval that each reader computes again is an interval that two readers can disagree about. The report reads these values rather than computing them.

The interval is the Wilson score interval at 95%, which thinkbook section 3.7 states. The level is fixed here and no cell states it, so one record cannot hold two levels.

Each ratio divides counters that the same entry already states, and the host computes each one over the cell and the pass of that entry:

- `first_attempt_loss.ratio` is `packets_sent` less `packets_received`, over `packets_sent`.
- `post_retry_loss.ratio` is `callback_failed` over `packets_sent`.
- `message_loss.ratio` is `messages_sent` less `messages_complete`, over `messages_sent`.

The first count of each pair comes from the sender and the second from the receiver, except for `post_retry_loss`, which the sender states on its own. Message loss divides against the messages that the sender sent rather than the messages that the receiver saw, so a message that produced no fragment counts as lost.

Each Wilson interval takes the same denominator as its ratio as the sample count.

An entry whose `valid` is false states no loss quantity, and it states the counters of a node only when that node answered its `stats` command. A pass that a reset or a silence ended completes no such command, so the format requires no counter on such an entry.

A ratio of a pass whose denominator is zero is absent rather than zero, because no frame was sent and no share exists.

## Consequences

- The three quantities of thinkbook section 2 each hold one key, so a reader of a record names the quantity without reading the mode.
- These keys arrive while `record_version` is 1 and no run has written a record, so they cost no rise of that version. A key added after the first record costs version 2.
- The record holds a `[derived]` value beside the `[measured]` counters that produce it. A later change to a derivation makes a stored value disagree with a fresh computation, so a change to any derivation above needs a new record.
- The confidence level is fixed at 95%, so a change to it needs a new record.
- The report reads the loss quantities rather than computing them, so a shared record carries its conclusion to a reader who holds no report script.
- An entry that the run invalidated states no loss, so a reader filters on `valid` before it averages a cell.
- The schema stops requiring the counters of both nodes on every entry, because an invalidated attempt holds none.
- The drift band of thinkbook section 8 reads `first_attempt_loss` of the repeated baseline cells.
- A unicast pass states two quantities and a broadcast pass states two, so the report states which quantity each chart holds, which decision 2026-10-01-loss-metric-and-send-mode.md already requires.
- Watch a cell where `packets_received` exceeds `packets_sent`. A duplicate or a foreign frame that passed the header check would produce it, and the ratio would fall below zero.
