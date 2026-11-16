# The arm and the finish of a receiver pass

Date: 2026-11-16
Status: Accepted

## Context

The receiving loop record settled the counters, the queue, the duplicate window, and the histogram bins of a receiver, and the receiver module reached the repository with three entry points and no caller. `bol_receiver_arm` took the run, the cell, the pass, and the packets of one message. That module stated that a packet of another run, another cell, or another pass counts as a foreign packet, so the receiver takes the run, the cell, and the pass before the first frame arrives. `bol_receiver_finish` took the positions that the sender put on the air, and it counted the loss run that the end of a pass left open.

The command fields record gave a receiver three commands. `role` carried `role` and `run_id`. `cell` carried `cell_id`, `channel`, `power_set_value`, and `payload_bytes`. `stats` carried `cell_id` and `pass`. `go` carried `cell_id`, `pass`, and `frames`, and thinkbook section 7 sent `go` to the sender alone. `host/src/bolis/orchestrator.py` sent those three commands to the receiver, and it sent `go` to the sender.

A receiver therefore read the pass of a cell for the first time in the `stats` command that followed that pass, and it read the frame budget of that pass in no command. The arm needed the pass before the first frame, and the finish needed the positions that the pass sent. Neither value reached the node.

The command fields record had rejected the pass on `cell`, because that choice re-arms a node for each pass of one condition. The orchestrator already applied `cell` to both nodes once per pass, inside `_one_pass`, so the exchange of a cell held that re-arm.

`proto` version 2 held every key of these four commands, and no release had shipped it. A key that arrives before that version ships costs no rise of it. A key that arrives after it ships costs version 3.

If nothing was decided, the console would take the pass from a frame header, against the module that takes the pass before the first frame arrives. It would take the frame budget from a constant, and a receiver would close a pass whose length it never learned.

## Alternatives considered

- The pass and the frame budget on `cell`, which arms a receiver through the one command that the host already sends to it before every pass.
- `go` sent to the receiver as well, which gives a receiver a reply whose `done` and `frames_sent` state nothing that a receiver holds.
- The pass on `cell` and the frame budget on `stats`, which splits one arm across two commands.
- A receiver that arms itself from the first frame of a new cell and pass, which contradicts the receiving loop record, because `foreign_packets` counts a packet against a pass that the node already holds.
- A receiver that holds one counter set per cell and pass, which grows with the sweep and needs memory that the node does not hold.
- The frame budget held in the firmware, which keeps a `[configured]` value of the run record out of the exchange that sets it.
- The positions derived by the receiver from the highest position that arrived, which reads a pass that lost its last packets as a pass that ended early.

## Decision

The `cell` command carries `pass` and `frames`, beside `cell_id`, `channel`, `power_set_value`, and `payload_bytes`. `pass` holds `broadcast` or `unicast`, as it does on `go` and on `stats`. `frames` holds the frame budget of the pass that follows, as it does on `go`.

This amends the accepted record [2026-11-11-control-line-command-fields.md](./2026-11-11-control-line-command-fields.md), which states the four keys that `cell` carried. That record keeps `Status: Accepted`.

The `cell` reply is unchanged. It carries `cell_id`, `channel`, `payload_bytes`, and `power_set_value_read_back`.

A receiver arms at `cell`. It holds the run from its `role` command. It takes the cell, the pass, and the payload size from `cell`. It derives the packets of one message from the payload size and the payload limit. It passes those four values to `bol_receiver_arm`.

A receiver finishes at `stats`, before it reads its counters. It derives the positions of the pass from the frame budget that `cell` carried. A pass sends whole messages only, which the sending loop record fixes. The positions are therefore the whole messages that fit the budget, multiplied by the packets of one message.

A sender takes the pass and the frame budget from `go`, which carries both already. The two new keys bind no behavior of a sender.

The host states the same `frames` on the `cell` and the `go` of one pass.

```
@bol {"proto":2,"cmd":"cell","seq":7,"cell_id":12,"channel":6,
      "power_set_value":44,"payload_bytes":128,"pass":"broadcast","frames":2000}
@bol {"proto":2,"reply":"cell","seq":7,"ok":true,"cell_id":12,"channel":6,
      "payload_bytes":128,"power_set_value_read_back":44}
```

## Consequences

- `proto` stays at version 2, because that version has not shipped and these two keys reach a node inside it.
- This record amends the key set of the command fields record for the third time, after `run_id` on `role` and `dropped_packets` on a receiver reply.
- A reader of the control line contract reads the command fields record and every record that amends it.
- The `cell` reply is unchanged, so the run record format and its schema are unchanged.
- The host already applies `cell` to both nodes before every pass, so this record adds no exchange to a cell.
- A broadcast run sends `cell` once per cell, and a unicast run sends it twice, once per pass.
- `frames` reaches a node on two commands, and the host states one value on both.
- A `cell` that states a budget above the `go` of the same pass arms the receiver for positions that the sender never sends, and the receiver counts the difference as a loss of the link.
- The receiver derives the positions of a pass rather than counting them, so a sender that ends a pass early states that shortfall in `frames_sent` of its `go` reply rather than in the counters of the receiver.
- The `cell` command line grows by two keys and stays below the 512-byte limit that the wire format record sets.
- A `stats` command that reaches a receiver before the first `cell` of a run names an error, because the node holds no pass to finish.
- Watch the first run for a cell whose `foreign_packets` holds the whole pass. That count states an arm that took the wrong cell or the wrong pass, rather than a link that lost every frame.
